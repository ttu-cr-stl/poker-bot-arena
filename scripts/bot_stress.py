#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import websockets

from host.models import ActionType, TableConfig
from host.server import HostServer

LOGGER = logging.getLogger("bot_stress")


# ---------------------------------------------------------------------------
# Bot strategies
# ---------------------------------------------------------------------------
def passive_strategy(message: Dict[str, object]) -> Tuple[str, int | None]:
    """Default bot: check if possible, otherwise call, then fold."""
    legal = message.get("legal", [])
    if "CHECK" in legal:
        return ActionType.CHECK.value, None
    if "CALL" in legal:
        return ActionType.CALL.value, None
    if "RAISE_TO" in legal:
        return ActionType.RAISE_TO.value, message.get("min_raise_to")
    return ActionType.FOLD.value, None


def min_raise_strategy(message: Dict[str, object]) -> Tuple[str, int | None]:
    """Aggressive bot: raise when allowed, fall back to call/check."""
    legal = message.get("legal", [])
    if "RAISE_TO" in legal and message.get("min_raise_to"):
        return ActionType.RAISE_TO.value, message["min_raise_to"]
    if "CALL" in legal:
        return ActionType.CALL.value, None
    if "CHECK" in legal:
        return ActionType.CHECK.value, None
    return ActionType.FOLD.value, None


def random_strategy(message: Dict[str, object]) -> Tuple[str, int | None]:
    """Random bot: choose a random action."""
    legal = message.get("legal", [])
    if "RAISE_TO" in legal and message.get("min_raise_to"):
        return ActionType.RAISE_TO.value, message["min_raise_to"]
    if "CALL" in legal:
        return ActionType.CALL.value, None
    return ActionType.FOLD.value, None


# Update this list to try out alternate personalities per bot.
# (team name, join code, decision function)
STRATEGIES: List[Tuple[str, str, Callable[[Dict[str, object]], Tuple[str, int | None]]]] = [
    ("PassiveBot", "PASS1", passive_strategy),
    ("CallerBot", "CALL2", passive_strategy),
    ("AggroBot", "AGRO3", min_raise_strategy),
    ("RaiserBot", "RAIS4", min_raise_strategy),
]


@dataclass
class BotStats:
    actions_taken: int = 0
    hands_seen: int = 0


async def run_bot(
    *,
    team: str,
    join_code: str,
    strategy: Callable[[Dict[str, object]], Tuple[str, int | None]],
    url: str,
    stop_event: asyncio.Event,
    event_queue: asyncio.Queue[Tuple[str, str]],
    stats: Dict[str, BotStats],
) -> None:
    """Connect a single bot client to the host server and play until told to stop."""
    try:
        async with websockets.connect(url) as ws:
            hello = {"type": "hello", "v": 1, "team": team, "join_code": join_code}
            await ws.send(json.dumps(hello))
            stats[team] = BotStats()

            while True:
                if stop_event.is_set():
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    break

                message = json.loads(raw)
                msg_type = message.get("type")

                if msg_type == "act":
                    action, amount = strategy(message)
                    payload = {
                        "type": "action",
                        "v": 1,
                        "hand_id": message["hand_id"],
                        "action": action,
                    }
                    if action == ActionType.RAISE_TO.value:
                        payload["amount"] = int(amount or message.get("min_raise_to", 0))
                    await ws.send(json.dumps(payload))
                    stats[team].actions_taken += 1

                elif msg_type == "end_hand":
                    stats[team].hands_seen += 1
                    hand_id = message.get("hand_id")
                    if hand_id:
                        event_queue.put_nowait(("end_hand", hand_id))

                elif msg_type == "match_end":
                    LOGGER.info("Bot %s received match_end", team)
                    stop_event.set()
                    break

    except Exception as exc:
        LOGGER.exception("Bot %s terminated due to error: %s", team, exc)


async def monitor_hands(
    *,
    target_hands: int,
    event_queue: asyncio.Queue[Tuple[str, str]],
    stop_event: asyncio.Event,
) -> None:
    """Count completed hands and signal stop once the target is reached."""
    seen: Dict[str, None] = {}
    try:
        while not stop_event.is_set():
            kind, hand_id = await event_queue.get()
            if kind == "end_hand" and hand_id not in seen:
                seen[hand_id] = None
                if len(seen) >= target_hands:
                    stop_event.set()
                    return
    except asyncio.CancelledError:
        return


async def run_simulation(args: argparse.Namespace) -> None:
    strategies = STRATEGIES[: args.players]
    if len(strategies) != args.players:
        raise SystemExit(f"Requested {args.players} players, but only {len(STRATEGIES)} strategies configured.")

    config = TableConfig(
        seats=args.players,
        starting_stack=args.starting_stack,
        sb=args.sb,
        bb=args.bb,
        move_time_ms=args.move_time_ms,
    )
    server = HostServer(config)

    url = f"ws://{args.host}:{args.port}/ws"
    stop_event = asyncio.Event()
    event_queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()
    stats: Dict[str, BotStats] = {}

    LOGGER.info(
        "Starting host server on %s:%s for %s players, %s target hands",
        args.host,
        args.port,
        args.players,
        args.hands,
    )

    server_task = asyncio.create_task(server.start(args.host, args.port))
    await asyncio.sleep(0.25)  # allow server socket to bind

    bot_tasks = [
        asyncio.create_task(
            run_bot(
                team=team,
                join_code=join_code,
                strategy=strategy,
                url=url,
                stop_event=stop_event,
                event_queue=event_queue,
                stats=stats,
            )
        )
        for team, join_code, strategy in strategies
    ]
    monitor_task = asyncio.create_task(
        monitor_hands(target_hands=args.hands, event_queue=event_queue, stop_event=stop_event)
    )

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user, stopping simulation.")
        stop_event.set()
    finally:
        stop_event.set()
        await asyncio.sleep(0)  # yield to bots so they can notice the stop event

        for task in bot_tasks:
            task.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*bot_tasks, return_exceptions=True)

        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task

        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

    LOGGER.info("Simulation complete. Summary:")
    for team, bot_stat in stats.items():
        LOGGER.info("  %-12s -> %3d hands, %4d actions", team, bot_stat.hands_seen, bot_stat.actions_taken)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spin up the host server and basic bots for stress testing.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the embedded server.")
    parser.add_argument("--port", type=int, default=8765, help="Port for the embedded server.")
    parser.add_argument("--players", type=int, default=len(STRATEGIES), help="Number of bots to launch.")
    parser.add_argument("--hands", type=int, default=200, help="Number of completed hands before stopping.")
    parser.add_argument("--starting-stack", type=int, default=1_000, help="Starting stack per player.")
    parser.add_argument("--sb", type=int, default=10, help="Small blind size.")
    parser.add_argument("--bb", type=int, default=20, help="Big blind size.")
    parser.add_argument("--move-time-ms", type=int, default=5_000, help="Timer per decision in milliseconds.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, etc.).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")
    asyncio.run(run_simulation(args))


if __name__ == "__main__":
    main()
