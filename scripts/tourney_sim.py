#!/usr/bin/env python3
"""Simulate a short tournament with randomly behaved bots.

This script spins up the tournament host in-process and connects a handful of
toy bots. Each bot picks a random strategy per hand so you can exercise the
engine in a non-deterministic environment.

Example:
    python scripts/tourney_sim.py --players 4 --hands 50
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets

from core.models import ActionType, TableConfig
from tournament.server import HostServer

LOGGER = logging.getLogger("tourney_sim")


@dataclass
class BotProfile:
    name: str
    join_code: str
    rng: random.Random


def choose_action(message: Dict[str, Any], rng: random.Random) -> tuple[str, Optional[int]]:
    """Pick a random (but legal) action with lightweight heuristics."""

    legal = list(message.get("legal", []))
    if not legal:
        return "FOLD", None

    call_amount = message.get("call_amount") or 0
    min_raise = message.get("min_raise_to")
    max_raise = message.get("max_raise_to")
    you = message.get("you", {})
    stack = you.get("stack", 0)
    committed = you.get("committed", 0)

    phase = message.get("phase")

    # Prefer checking preflop with junk, otherwise choose randomly.
    if "CHECK" in legal and phase == "PRE_FLOP" and call_amount == 0:
        hole = message.get("you", {}).get("hole", [])
        ranks = {card[0] for card in hole}
        if not ranks.intersection({"A", "K", "Q", "J"}) and rng.random() < 0.7:
            return "CHECK", None

    choice = rng.choice(legal)

    if choice == "RAISE_TO":
        available = stack + call_amount
        min_total = call_amount + committed
        if not min_raise or available < min_raise or available <= min_total:
            return ("CALL" if "CALL" in legal else "FOLD"), None
        upper = min(max_raise or available, available)
        lower = max(min_raise, min_total)
        if lower > upper:
            return ("CALL" if "CALL" in legal else "FOLD"), None
        target = upper if rng.random() < 0.25 else rng.randint(lower, upper)
        return "RAISE_TO", target

    if choice == "CALL":
        return "CALL", None

    if choice == "CHECK":
        return "CHECK", None

    return "FOLD", None


def safe_action(message: Dict[str, Any]) -> tuple[str, Optional[int]]:
    if "CHECK" in message.get("legal", []):
        return "CHECK", None
    if "CALL" in message.get("legal", []):
        return "CALL", None
    return "FOLD", None


async def run_bot(profile: BotProfile, url: str, stop_event: asyncio.Event) -> None:
    """Connect a single random bot to the host until the tournament ends."""

    try:
        async with websockets.connect(url) as ws:
            hello = {
                "type": "hello",
                "v": 1,
                "team": profile.name,
                "join_code": profile.join_code,
            }
            await ws.send(json.dumps(hello))

            pending_ctx: Optional[Dict[str, Any]] = None
            while not stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    break

                message = json.loads(raw)
                msg_type = message.get("type")

                if msg_type == "act":
                    action, amount = choose_action(message, profile.rng)
                    if action == "RAISE_TO" and amount is not None and amount < message.get("min_raise_to", 0):
                        action, amount = safe_action(message)
                    payload = {
                        "type": "action",
                        "v": 1,
                        "hand_id": message["hand_id"],
                        "action": action,
                    }
                    if amount is not None:
                        payload["amount"] = int(amount)
                    await ws.send(json.dumps(payload))
                    pending_ctx = message

                elif msg_type == "match_end":
                    LOGGER.info("%s received match_end", profile.name)
                    stop_event.set()
                    break

                elif msg_type == "error" and pending_ctx:
                    LOGGER.warning(
                        "%s received error %s; sending safe fallback",
                        profile.name,
                        message,
                    )
                    fallback_action, fallback_amount = safe_action(pending_ctx)
                    payload = {
                        "type": "action",
                        "v": 1,
                        "hand_id": pending_ctx["hand_id"],
                        "action": fallback_action,
                    }
                    if fallback_amount is not None:
                        payload["amount"] = fallback_amount
                    await ws.send(json.dumps(payload))
                    pending_ctx = None

    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Bot %s crashed: %s", profile.name, exc)


async def progress_logger(stop_event: asyncio.Event, interval: float) -> None:
    while not stop_event.is_set():
        LOGGER.info("Simulation still running…")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def run_simulation(args: argparse.Namespace) -> None:
    config = TableConfig(
        seats=args.players,
        starting_stack=args.starting_stack,
        sb=args.sb,
        bb=args.bb,
        move_time_ms=args.move_time,
    )

    host = HostServer(config)

    server_task = asyncio.create_task(host.start(args.host, args.port))
    await asyncio.sleep(0.5)  # give the socket time to bind

    stop_event = asyncio.Event()

    profiles = [
        BotProfile(
            name=f"SimBot{i}",
            join_code=f"CODE{i}",
            rng=random.Random(args.seed + i),
        )
        for i in range(args.players)
    ]

    bot_tasks = [
        asyncio.create_task(run_bot(profile, f"ws://{args.host}:{args.port}/ws", stop_event))
        for profile in profiles
    ]

    # Stop once the desired number of hands have completed or a timeout occurs.
    heartbeat = asyncio.create_task(progress_logger(stop_event, interval=5.0))

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=args.timeout)
    except asyncio.TimeoutError:
        LOGGER.warning("Simulation timed out; stopping bots")
    finally:
        stop_event.set()
        for task in bot_tasks:
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*bot_tasks, return_exceptions=True)
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local tournament simulation with random bots")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--players", type=int, default=4)
    parser.add_argument("--starting-stack", type=int, default=5_000)
    parser.add_argument("--sb", type=int, default=25)
    parser.add_argument("--bb", type=int, default=50)
    parser.add_argument("--move-time", type=int, default=5_000)
    parser.add_argument("--timeout", type=float, default=60.0, help="max seconds to run before stopping")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    try:
        asyncio.run(run_simulation(args))
    except KeyboardInterrupt:
        LOGGER.info("Simulation interrupted; shutting down")


if __name__ == "__main__":
    main()
