#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets
from websockets import WebSocketClientProtocol

logging.basicConfig(level=logging.INFO)


@dataclass
class ActContext:
    hand_id: str
    legal: list[str]
    call_amount: Optional[int]
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]
    time_ms: int


class ManualClient:
    def __init__(self, team: str, join_code: str, url: str) -> None:
        self.team = team
        self.join_code = join_code
        self.url = url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.last_act: Optional[ActContext] = None

    async def run(self) -> None:
        async with websockets.connect(self.url) as ws:
            self.websocket = ws
            await self._send(
                {
                    "type": "hello",
                    "v": 1,
                    "team": self.team,
                    "join_code": self.join_code,
                }
            )
            await self._loop()

    async def _loop(self) -> None:
        assert self.websocket is not None
        while True:
            raw = await self.websocket.recv()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            self._print_message(msg)

            if msg_type == "act":
                await self._handle_act(msg)
            elif msg_type == "match_end":
                print("Match ended. Press Ctrl+C to exit.")
                break

    async def _handle_act(self, msg: Dict[str, Any]) -> None:
        ctx = ActContext(
            hand_id=msg["hand_id"],
            legal=list(msg.get("legal", [])),
            call_amount=msg.get("call_amount"),
            min_raise_to=msg.get("min_raise_to"),
            max_raise_to=msg.get("max_raise_to"),
            time_ms=msg.get("you", {}).get("time_ms", 0),
        )
        self.last_act = ctx
        deadline = time.monotonic() + ctx.time_ms / 1000 if ctx.time_ms else None

        while True:
            action = self._prompt_action(ctx, deadline)
            if action is None:
                continue
            await self._send(action)
            break

    def _prompt_action(self, ctx: ActContext, deadline: Optional[float]) -> Optional[Dict[str, Any]]:
        remaining = None
        if deadline:
            remaining = max(0, int(deadline - time.monotonic()))
        prompt = "Action [" + "/".join(ctx.legal) + "](h=help): "
        if remaining is not None:
            prompt = f"({remaining}s left) {prompt}"

        choice = input(prompt).strip().upper()
        if not choice:
            default = self._default_action(ctx)
            print(f"Using default: {default}")
            choice = default

        if choice == "H":
            self._print_act_help(ctx)
            return None

        if choice not in ctx.legal:
            print("Illegal selection. Try again.")
            return None

        payload = {
            "type": "action",
            "v": 1,
            "hand_id": ctx.hand_id,
            "action": choice,
        }

        if choice == "RAISE_TO":
            amount = self._prompt_raise_amount(ctx)
            if amount is None:
                return None
            payload["amount"] = amount
        elif choice == "CALL" and ctx.call_amount:
            print(f"Calling {ctx.call_amount} chips")

        return payload

    def _default_action(self, ctx: ActContext) -> str:
        if "CALL" in ctx.legal:
            return "CALL"
        if "CHECK" in ctx.legal:
            return "CHECK"
        return ctx.legal[0]

    def _prompt_raise_amount(self, ctx: ActContext) -> Optional[int]:
        assert ctx.min_raise_to is not None
        assert ctx.max_raise_to is not None
        prompt = f"Raise to amount [{ctx.min_raise_to}-{ctx.max_raise_to}]: "
        value = input(prompt).strip()
        if not value:
            print("Raise cancelled")
            return None
        try:
            amount = int(value)
        except ValueError:
            print("Enter a valid integer")
            return None
        if amount < ctx.min_raise_to or amount > ctx.max_raise_to:
            print("Amount out of bounds")
            return None
        return amount

    def _print_message(self, msg: Dict[str, Any]) -> None:
        msg_type = msg.get("type")
        header = f"\n>>> {msg_type.upper()}"
        print(header)
        if msg_type == "welcome":
            print(f"Seat: {msg['seat']}, config: {json.dumps(msg['config'])}")
        elif msg_type == "lobby":
            players = ", ".join(
                f"{p['seat']}:{p['team']} ({'✓' if p['connected'] else '×'})"
                for p in msg.get("players", [])
            )
            print(f"Lobby: {players}")
        elif msg_type == "start_hand":
            print(f"Hand {msg['hand_id']} seed={msg['seed']} button={msg['button']}")
        elif msg_type == "act":
            you = msg.get("you", {})
            print(
                f"Your hand: {you.get('hole')} | stack={you.get('stack')} | to_call={you.get('to_call')}"
            )
            print(
                f"Legal: {msg.get('legal')} | call={msg.get('call_amount')} | min_raise={msg.get('min_raise_to')}"
            )
            if msg.get("time_ms"):
                print(f"Move clock: {msg['time_ms']} ms")
        elif msg_type == "event":
            ev = msg.get("ev")
            summary = {k: v for k, v in msg.items() if k not in {"type", "v", "ts", "ev"}}
            print(f"Event {ev}: {summary}")
        elif msg_type == "snapshot":
            print(
                f"Snapshot hand={msg['at_hand_id']} phase={msg['phase']} next_actor={msg['next_actor']}"
            )
        elif msg_type == "end_hand":
            print(f"Stacks: {msg.get('stacks')}")
        elif msg_type == "error":
            print(f"Error {msg.get('code')}: {msg.get('msg')}")
        elif msg_type == "match_end":
            print(f"Winner: {msg.get('winner')} | stacks: {msg.get('final_stacks')}")
        else:
            print(json.dumps(msg, indent=2))

    def _print_act_help(self, ctx: ActContext) -> None:
        print("Options:")
        for opt in ctx.legal:
            if opt == "FOLD":
                print("  FOLD  → give up the pot")
            elif opt == "CHECK":
                print("  CHECK → pass the action with no chips")
            elif opt == "CALL":
                print(f"  CALL  → match {ctx.call_amount} chips")
            elif opt == "RAISE_TO":
                print(
                    f"  RAISE_TO → choose amount between {ctx.min_raise_to} and {ctx.max_raise_to}"
                )

    async def _send(self, payload: Dict[str, Any]) -> None:
        assert self.websocket is not None
        await self.websocket.send(json.dumps(payload))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poker Bot Arena manual client")
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws")
    parser.add_argument("--team", required=True)
    parser.add_argument("--code", required=True, help="Join code")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    client = ManualClient(team=args.team, join_code=args.code, url=args.url)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nSession closed")


if __name__ == "__main__":
    main(sys.argv[1:])
