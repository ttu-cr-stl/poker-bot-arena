from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional

import websockets
from http import HTTPStatus

from core.game import GameEngine
from core.models import ActionType, TableConfig
from practice.bots import baseline_strategy

LOGGER = logging.getLogger("practice_host")

AB_SEAT_ORDER = {"A": 0, "B": 1}


class PracticeServerError(Exception):
    def __init__(self, code: str, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


def _config_payload(config: TableConfig) -> Dict[str, Any]:
    return {
        "variant": config.variant,
        "seats": config.seats,
        "starting_stack": config.starting_stack,
        "sb": config.sb,
        "bb": config.bb,
    }


async def _send_error(websocket: websockets.WebSocketServerProtocol, code: str, msg: str) -> None:
    await websocket.send(json.dumps({"type": "error", "code": code, "msg": msg}))

@dataclass
class RemoteBotClient:
    team_label: str
    websocket: websockets.WebSocketServerProtocol
    preferred_seat: int = 0
    seat_idx: Optional[int] = None

    async def send_json(self, payload: Dict[str, Any]) -> None:
        await self.websocket.send(json.dumps({"v": 1, **payload}))


# Each incoming table run is coordinated through PracticeSession.


class PracticeSession:
    """Handles one practice table with N remote bots + the baseline bot."""

    def __init__(
        self,
        config: TableConfig,
        remote_players: List[RemoteBotClient],
        house_team: str = "HOUSE",
    ) -> None:
        if not remote_players:
            raise ValueError("At least one remote player required")
        self.engine = GameEngine(config)
        self.remote_players = list(remote_players)
        self.remote_by_seat: Dict[int, RemoteBotClient] = {}
        self.house_team = house_team
        self.house_seat: Optional[int] = None

    async def run(self) -> None:
        # One practice match = repeated hands until only one stack remains.
        await self._assign_seats()
        while True:
            if not self.engine.can_start_hand():
                break
            ctx = self.engine.start_hand()
            await self._broadcast_json({"type": "start_hand", **self.engine.start_hand_payload(ctx)})
            for event in self.engine.consume_pre_events():
                await self._broadcast_json({"type": "event", **event})
            await self._play_hand()

        await self._broadcast_json({"type": "match_end", **self.engine.match_result_payload()})

    async def _assign_seats(self) -> None:
        needed = len(self.remote_players) + 1
        if needed > self.engine.config.seats:
            raise RuntimeError("Table config does not have enough seats")

        for remote in sorted(self.remote_players, key=lambda r: r.preferred_seat):
            seat = self.engine.assign_seat(remote.team_label)
            remote.seat_idx = seat.seat
            self.remote_by_seat[seat.seat] = remote

        house = self.engine.assign_seat(self.house_team)
        self.house_seat = house.seat

    async def _play_hand(self) -> None:
        assert self.house_seat is not None
        while not self.engine.is_hand_complete():
            seat_idx = self.engine.next_actor()
            if seat_idx is None:
                await asyncio.sleep(0)
                continue

            remote = self.remote_by_seat.get(seat_idx)
            if remote is not None:
                action, amount = await self._prompt_remote(remote)
            else:
                # House bot is instant and runs locally.
                action, amount = baseline_strategy(self.engine, seat_idx)

            events = self.engine.apply_action(seat_idx, action, amount)
            for event in events:
                await self._broadcast_json({"type": "event", **event})

        await self._broadcast_json(self.engine.end_hand_payload() | {"type": "end_hand"})

    async def _prompt_remote(self, remote: RemoteBotClient) -> tuple[ActionType, Optional[int]]:
        assert remote.seat_idx is not None
        payload = self.engine.act_payload(remote.seat_idx)
        await remote.send_json({"type": "act", **payload})
        while True:
            raw = await remote.websocket.recv()
            message = json.loads(raw)
            if message.get("type") != "action":
                continue
            action = ActionType(message["action"])
            amount = message.get("amount")
            return action, amount

    async def _broadcast_json(self, payload: Dict[str, Any]) -> None:
        for remote in self.remote_players:
            await remote.send_json(payload)


class ABTable:
    def __init__(self, team: str, team_key: str, config: TableConfig) -> None:
        self.team = team
        self.team_key = team_key
        self.config = config
        self.bots: Dict[str, RemoteBotClient] = {}
        self.wait_tasks: Dict[str, asyncio.Task] = {}
        self.session_task: Optional[asyncio.Task] = None
        self.done_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self.session_starting = False

    def should_remove(self) -> bool:
        if self.done_event.is_set():
            return True
        return not self.bots and self.session_task is None

    async def attach(self, label: str, remote: RemoteBotClient) -> None:
        upper_label = label.strip().upper()
        if not upper_label:
            raise PracticeServerError("BAD_BOT_LABEL", "Bot label required")
        if upper_label not in AB_SEAT_ORDER:
            raise PracticeServerError("BAD_BOT_LABEL", "Bot label must be A or B")

        remote.preferred_seat = AB_SEAT_ORDER[upper_label]
        remote.team_label = f"{self.team} ({upper_label})"

        start_session = False
        async with self.lock:
            if self.session_task and not self.session_task.done():
                raise PracticeServerError("AB_IN_PROGRESS", "A/B table already running for this team")
            if upper_label in self.bots:
                raise PracticeServerError("BOT_SLOT_TAKEN", f"Bot {upper_label} already connected")

            self.bots[upper_label] = remote
            if len(self.bots) == len(AB_SEAT_ORDER):
                self.session_starting = True
                for task in self.wait_tasks.values():
                    task.cancel()
                self.wait_tasks.clear()
                start_session = True
            else:
                self.wait_tasks[upper_label] = asyncio.create_task(self._wait_for_disconnect(remote, upper_label))

        await remote.send_json({
            "type": "welcome",
            "table_id": "PRACTICE",
            "seat": remote.preferred_seat,
            "config": _config_payload(self.config),
        })

        if start_session:
            self.session_task = asyncio.create_task(self._run_session())
            self.session_starting = False
        elif len(self.bots) < len(AB_SEAT_ORDER):
            await remote.send_json({
                "type": "ab_status",
                "state": "WAITING_FOR_PARTNER",
                "bot": upper_label,
            })

        await self._wait_for_completion(remote)

    async def _run_session(self) -> None:
        remotes = sorted(self.bots.values(), key=lambda r: r.preferred_seat)
        session = PracticeSession(self.config, remotes, house_team=f"{self.team} (HOUSE)")
        try:
            await session.run()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Practice A/B session crashed for %s: %s", self.team, exc)
            raise
        finally:
            self.done_event.set()

    async def _wait_for_disconnect(self, remote: RemoteBotClient, label: str) -> None:
        try:
            await remote.websocket.wait_closed()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            pass
        async with self.lock:
            self.wait_tasks.pop(label, None)
            can_remove = (self.session_task is None) and (not self.session_starting)
            if can_remove and self.bots.get(label) is remote:
                self.bots.pop(label, None)

    async def _wait_for_completion(self, remote: RemoteBotClient) -> None:
        wait_done = asyncio.create_task(self.done_event.wait())
        wait_closed = asyncio.create_task(remote.websocket.wait_closed())
        try:
            done, _ = await asyncio.wait(
                [wait_done, wait_closed],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if wait_done in done:
                return
            if wait_closed in done and not self.done_event.is_set():
                if self.session_task:
                    await self.session_task
                return
        finally:
            for task in (wait_done, wait_closed):
                if not task.done():
                    task.cancel()


class ABTableManager:
    def __init__(self, base_config: TableConfig) -> None:
        self.base_config = base_config
        self.tables: Dict[str, ABTable] = {}
        self.lock = asyncio.Lock()

    async def attach(self, team: str, websocket: websockets.WebSocketServerProtocol, bot_label: str) -> None:
        team_display = team or "REMOTE"
        team_key = team_display.strip().casefold()
        async with self.lock:
            table = self.tables.get(team_key)
            if table is None or table.should_remove():
                config = replace(self.base_config, seats=len(AB_SEAT_ORDER) + 1)
                table = ABTable(team=team_display, team_key=team_key, config=config)
                self.tables[team_key] = table
            team_display = table.team
        try:
            await table.attach(bot_label, RemoteBotClient(team_label=team_display, websocket=websocket))
        finally:
            if table.should_remove():
                async with self.lock:
                    current = self.tables.get(team_key)
                    if current is table and table.should_remove():
                        self.tables.pop(team_key, None)


async def handle_connection(
    websocket: websockets.WebSocketServerProtocol,
    config: TableConfig,
    ab_manager: ABTableManager,
) -> None:
    # Basic handshake using same protocol fields.
    hello_raw = await websocket.recv()
    hello = json.loads(hello_raw)
    if hello.get("type") != "hello":
        await _send_error(websocket, "BAD_HELLO", "Expected hello")
        return

    team_raw = hello.get("team")
    team = team_raw.strip() if isinstance(team_raw, str) else "REMOTE"
    if not team:
        team = "REMOTE"

    bot_label: Optional[str] = None
    if "bot" in hello:
        bot_raw = hello.get("bot")
        if isinstance(bot_raw, str):
            trimmed = bot_raw.strip()
            if trimmed:
                candidate = trimmed.upper()
                if candidate not in AB_SEAT_ORDER:
                    await _send_error(websocket, "BAD_BOT_LABEL", "Use --bot A or --bot B")
                    return
                bot_label = candidate
        elif bot_raw is not None:
            await _send_error(websocket, "BAD_BOT_LABEL", "bot must be a string")
            return

    if bot_label:
        try:
            await ab_manager.attach(team, websocket, bot_label)
        except PracticeServerError as exc:
            await _send_error(websocket, exc.code, exc.msg)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Practice A/B session crashed for %s (%s): %s", team, bot_label, exc)
        return

    remote = RemoteBotClient(team_label=team, websocket=websocket, preferred_seat=0)
    await remote.send_json({
        "type": "welcome",
        "table_id": "PRACTICE",
        "seat": remote.preferred_seat,
        "config": _config_payload(config),
    })

    session = PracticeSession(config, [remote])
    try:
        await session.run()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Practice session crashed: %s", exc)


async def _process_request(path, request_headers):
    """Return a simple HTTP response for health checks."""

    upgrade_header = request_headers.get("Upgrade", "").lower()
    if upgrade_header == "websocket":
        return None  # let the WebSocket handshake continue

    if path in {"/", "/health", "/healthz"}:
        body = b"practice server running\n"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        return HTTPStatus.OK, headers, body
    body = b"not found\n"
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    return HTTPStatus.NOT_FOUND, headers, body


async def run_server(host: str, port: int, config: TableConfig) -> None:
    ab_manager = ABTableManager(config)

    async def _handler(ws):
        await handle_connection(ws, config, ab_manager)

    async with websockets.serve(_handler, host, port, process_request=_process_request):
        LOGGER.info("Practice server listening on %s:%s", host, port)
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote vs sample-bot practice server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--starting-stack", type=int, default=5_000)
    parser.add_argument("--sb", type=int, default=25)
    parser.add_argument("--bb", type=int, default=50)
    args = parser.parse_args()

    config = TableConfig(seats=2, starting_stack=args.starting_stack, sb=args.sb, bb=args.bb)
    asyncio.run(run_server(args.host, args.port, config))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
