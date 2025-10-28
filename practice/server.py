from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any, Dict, Optional

import websockets

from core.game import GameEngine
from core.models import ActionType, TableConfig
from practice.bots import baseline_strategy

LOGGER = logging.getLogger("practice_host")

# Each incoming connection gets its own PracticeSession.


class PracticeSession:
    """Handles a single remote bot against our baseline bot."""

    def __init__(self, websocket: websockets.WebSocketServerProtocol, config: TableConfig) -> None:
        self.websocket = websocket
        self.engine = GameEngine(config)
        self.remote_seat: Optional[int] = None
        self.house_seat: Optional[int] = None

    async def run(self) -> None:
        # One practice match = repeated heads-up hands until someone busts.
        await self._assign_seats()
        while True:
            if not self.engine.can_start_hand():
                break
            ctx = self.engine.start_hand()
            await self._send_json({
                "type": "start_hand",
                "hand_id": ctx.hand_id,
                "button": ctx.button,
            })
            await self._play_hand()

        await self._send_json({
            "type": "match_end",
            "winner": self.engine.match_result_payload().get("winner"),
        })

    async def _assign_seats(self) -> None:
        # Reserve seat 0 for remote, seat 1 for house bot.
        remote = self.engine.assign_seat("REMOTE", "REMOTE")
        self.remote_seat = remote.seat
        house = self.engine.assign_seat("HOUSE", "HOUSE")
        self.house_seat = house.seat

    async def _play_hand(self) -> None:
        assert self.remote_seat is not None and self.house_seat is not None
        while not self.engine.is_hand_complete():
            seat_idx = self.engine.next_actor()
            if seat_idx is None:
                await asyncio.sleep(0)
                continue

            if seat_idx == self.remote_seat:
                # Remote bot chooses; wait for their JSON response.
                action, amount = await self._prompt_remote()
            else:
                # House bot is instant and runs locally.
                action, amount = baseline_strategy(self.engine, seat_idx)

            events = self.engine.apply_action(seat_idx, action, amount)
            for event in events:
                await self._send_json({"type": "event", **event})

        await self._send_json(self.engine.end_hand_payload() | {"type": "end_hand"})

    async def _prompt_remote(self) -> tuple[ActionType, Optional[int]]:
        assert self.remote_seat is not None
        payload = self.engine.act_payload(self.remote_seat)
        await self._send_json({"type": "act", **payload})
        while True:
            raw = await self.websocket.recv()
            message = json.loads(raw)
            if message.get("type") != "action":
                continue
            action = ActionType(message["action"])
            amount = message.get("amount")
            return action, amount

    async def _send_json(self, payload: Dict[str, Any]) -> None:
        await self.websocket.send(json.dumps({"v": 1, **payload}))


async def handle_connection(websocket: websockets.WebSocketServerProtocol, config: TableConfig) -> None:
    # Basic handshake using same protocol fields.
    hello_raw = await websocket.recv()
    hello = json.loads(hello_raw)
    if hello.get("type") != "hello":
        await websocket.send(json.dumps({"type": "error", "code": "BAD_HELLO", "msg": "Expected hello"}))
        return
    await websocket.send(json.dumps({
        "type": "welcome",
        "v": 1,
        "table_id": "PRACTICE",
        "seat": 0,
        "config": {
            "variant": config.variant,
            "seats": config.seats,
            "starting_stack": config.starting_stack,
            "sb": config.sb,
            "bb": config.bb,
        },
    }))

    session = PracticeSession(websocket, config)
    try:
        await session.run()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Practice session crashed: %s", exc)


async def run_server(host: str, port: int, config: TableConfig) -> None:
    async def _handler(ws):
        await handle_connection(ws, config)

    async with websockets.serve(_handler, host, port):
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
