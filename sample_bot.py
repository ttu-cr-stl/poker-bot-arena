#!/usr/bin/env python3
"""
Starter bot template for Poker Bot Arena teams.

Usage:
    python practice/sample_bot.py --team MyBot --code SECRET \
        --url ws://127.0.0.1:9876/ws

This script shows the core loop:
  * handshake with the host
  * wait for `act` prompts
  * choose an action based on the payload
  * handle simple reconnect logic and logging

Replace the `choose_action` function with your custom strategy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import websockets

LOGGER = logging.getLogger("sample_bot")


@dataclass
class ActionContext:
    hand_id: str
    seat: int
    phase: str
    legal: list[str]
    call_amount: Optional[int]
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]
    stack: int
    committed: int


def choose_action(ctx: ActionContext) -> Tuple[str, Optional[int]]:
    """Replace this with your decision logic."""

    # Training wheels strategy: check → call small → fold.
    if "CHECK" in ctx.legal:
        return "CHECK", None

    if "CALL" in ctx.legal and (ctx.call_amount or 0) <= 200:
        return "CALL", None

    if "RAISE_TO" in ctx.legal and ctx.min_raise_to:
        available = ctx.stack + (ctx.call_amount or 0)
        min_total = (ctx.call_amount or 0) + ctx.committed
        if available < ctx.min_raise_to or available <= min_total:
            return "CALL" if "CALL" in ctx.legal else ("CHECK" if "CHECK" in ctx.legal else "FOLD"), None
        target = max(ctx.min_raise_to, min_total)
        target = min(target, available)
        return "RAISE_TO", target

    return "FOLD", None


async def play_hand(websocket: websockets.WebSocketServerProtocol) -> None:
    async for raw in websocket:
        message = json.loads(raw)
        msg_type = message.get("type")

        if msg_type == "act":
            # Build a context object so choose_action is easy to test.
            ctx = ActionContext(
                hand_id=message["hand_id"],
                seat=message["seat"],
                phase=message["phase"],
                legal=message["legal"],
                call_amount=message.get("call_amount"),
                min_raise_to=message.get("min_raise_to"),
                max_raise_to=message.get("max_raise_to"),
                stack=message.get("you", {}).get("stack", 0),
                committed=message.get("you", {}).get("committed", 0),
            )
            action, amount = choose_action(ctx)
            if action == "RAISE_TO" and ctx.min_raise_to and amount is not None and amount < ctx.min_raise_to:
                LOGGER.warning("Clamping raise from %s to min %s", amount, ctx.min_raise_to)
                amount = ctx.min_raise_to
            payload: Dict[str, Any] = {
                "type": "action",
                "v": 1,
                "hand_id": ctx.hand_id,
                "action": action,
            }
            if amount is not None:
                payload["amount"] = int(amount)
            LOGGER.debug("Sending action: %s", payload)
            await websocket.send(json.dumps(payload))

        elif msg_type == "event":
            LOGGER.debug("Event: %s", message.get("ev"))
        elif msg_type == "end_hand":
            LOGGER.info("Hand finished: %s", message.get("hand_id"))
        elif msg_type == "match_end":
            LOGGER.info("Match result: %s", message.get("winner"))
            break
        elif msg_type == "error":
        LOGGER.warning("Server error: %s", message)
        else:
            LOGGER.debug("Ignoring message type=%s", msg_type)


async def run_bot(team: str, join_code: str, url: str) -> None:
    async with websockets.connect(url) as ws:
        hello = {
            "type": "hello",
            "v": 1,
            "team": team,
            "join_code": join_code,
        }
        await ws.send(json.dumps(hello))
        LOGGER.info("Connected to %s as %s", url, team)
        # Stay inside play_hand until the server sends match_end.
        await play_hand(ws)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample Poker Bot client")
    parser.add_argument("--team", required=True, help="Team name registered with the host")
    parser.add_argument("--code", required=True, help="Join code provided by organizers")
    parser.add_argument("--url", default="ws://127.0.0.1:9876/ws", help="WebSocket URL")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(run_bot(args.team, args.code, args.url))


if __name__ == "__main__":
    main()
