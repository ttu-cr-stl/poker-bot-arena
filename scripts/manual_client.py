#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import websockets
from websockets import WebSocketClientProtocol

logging.basicConfig(level=logging.INFO)

# ManualClient mirrors what a bot does but with terminal prompts.


@dataclass
class ActContext:
    hand_id: str
    legal: list[str]
    call_amount: Optional[int]
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]
    time_ms: int


@dataclass
class PlayerState:
    seat: int
    stack: int = 0
    committed: int = 0
    has_folded: bool = False


@dataclass
class HandState:
    hand_id: str
    button: int
    community: list[str] = field(default_factory=list)
    pot: int = 0
    current_bet: int = 0
    min_raise_increment: int = 0
    phase: str = "PRE_FLOP"
    players: Dict[int, PlayerState] = field(default_factory=dict)


class ManualClient:
    def __init__(self, team: str, url: str) -> None:
        self.team = team
        self.url = url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.last_act: Optional[ActContext] = None
        self.seat: Optional[int] = None
        self.hand_state: Optional[HandState] = None
        self.recent_events: deque[str] = deque(maxlen=6)

    async def run(self) -> None:
        async with websockets.connect(self.url) as ws:
            self.websocket = ws
            await self._send(
                {
                    "type": "hello",
                    "v": 1,
                    "team": self.team,
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
            self.seat = msg.get("seat")
        elif msg_type == "lobby":
            players = ", ".join(
                f"{p['seat']}:{p['team']} ({'✓' if p['connected'] else '×'})"
                for p in msg.get("players", [])
            )
            print(f"Lobby: {players}")
        elif msg_type == "start_hand":
            self._start_hand_state(msg)
            print(f"Hand {msg['hand_id']} seed={msg['seed']} button={msg['button']}")
            stacks = msg.get("stacks", [])
            if stacks:
                seated = ", ".join(f"{entry['seat']}:{entry['stack']}" for entry in stacks)
                print(f"Starting stacks: {seated}")
        elif msg_type == "act":
            self._sync_state_from_act(msg)
            self._render_act_view(msg)
        elif msg_type == "event":
            self._apply_event(msg)
            ev = msg.get("ev")
            summary = {k: v for k, v in msg.items() if k not in {"type", "v", "ts", "ev"}}
            print(f"Event {ev}: {summary}")
        elif msg_type == "snapshot":
            print(
                f"Snapshot hand={msg['at_hand_id']} phase={msg['phase']} next_actor={msg['next_actor']}"
            )
        elif msg_type == "end_hand":
            print(f"Stacks: {msg.get('stacks')}")
            self.hand_state = None
        elif msg_type == "error":
            print(f"Error {msg.get('code')}: {msg.get('msg')}")
        elif msg_type == "match_end":
            print(f"Winner: {msg.get('winner')} | stacks: {msg.get('final_stacks')}")
            self.hand_state = None
        else:
            print(json.dumps(msg, indent=2))

    def _start_hand_state(self, msg: Dict[str, Any]) -> None:
        stacks = msg.get("stacks", [])
        players = {
            entry["seat"]: PlayerState(seat=entry["seat"], stack=entry.get("stack", 0))
            for entry in stacks
        }
        self.hand_state = HandState(
            hand_id=msg["hand_id"],
            button=msg["button"],
            community=[],
            pot=0,
            current_bet=0,
            min_raise_increment=0,
            phase="PRE_FLOP",
            players=players,
        )
        self.recent_events.clear()

    def _ensure_player(self, seat: Optional[int]) -> Optional[PlayerState]:
        if seat is None or self.hand_state is None:
            return None
        players = self.hand_state.players
        state = players.get(seat)
        if state is None:
            state = PlayerState(seat=seat)
            players[seat] = state
        return state

    def _adjust_player(
        self,
        seat: Optional[int],
        *,
        stack_delta: int = 0,
        committed_delta: int = 0,
        reset_commit: bool = False,
    ) -> None:
        player = self._ensure_player(seat)
        if player is None:
            return
        player.stack = max(0, player.stack + stack_delta)
        if reset_commit:
            player.committed = 0
        else:
            player.committed = max(0, player.committed + committed_delta)

    def _reset_committed(self) -> None:
        if not self.hand_state:
            return
        for player in self.hand_state.players.values():
            player.committed = 0

    def _apply_event(self, msg: Dict[str, Any]) -> None:
        if msg.get("type") != "event" or not self.hand_state:
            return
        ev = msg.get("ev")
        hs = self.hand_state
        summary: Optional[str] = None
        if ev == "POST_BLINDS":
            sb = msg.get("sb", 0) or 0
            bb = msg.get("bb", 0) or 0
            hs.pot += sb + bb
            self._adjust_player(msg.get("sb_seat"), stack_delta=-sb, committed_delta=sb)
            self._adjust_player(msg.get("bb_seat"), stack_delta=-bb, committed_delta=bb)
            summary = f"Blinds: SB {msg.get('sb_seat')} {sb}, BB {msg.get('bb_seat')} {bb}"
        elif ev == "BET":
            amount = msg.get("amount", 0) or 0
            hs.pot += amount
            self._adjust_player(msg.get("seat"), stack_delta=-amount, committed_delta=amount)
            summary = f"Seat {msg.get('seat')} bet {amount}"
        elif ev == "CALL":
            amount = msg.get("amount", 0) or 0
            hs.pot += amount
            self._adjust_player(msg.get("seat"), stack_delta=-amount, committed_delta=amount)
            summary = f"Seat {msg.get('seat')} call {amount}"
        elif ev == "FOLD":
            player = self._ensure_player(msg.get("seat"))
            if player:
                player.has_folded = True
            summary = f"Seat {msg.get('seat')} fold"
        elif ev == "CHECK":
            pass
            summary = f"Seat {msg.get('seat')} check"
        elif ev == "FLOP":
            cards = msg.get("cards", [])
            hs.community.extend(cards)
            hs.phase = "FLOP"
            self._reset_committed()
            summary = f"Flop: {' '.join(cards)}"
        elif ev == "TURN":
            card = msg.get("card")
            if card:
                hs.community.append(card)
            hs.phase = "TURN"
            self._reset_committed()
            summary = f"Turn: {card}"
        elif ev == "RIVER":
            card = msg.get("card")
            if card:
                hs.community.append(card)
            hs.phase = "RIVER"
            self._reset_committed()
            summary = f"River: {card}"
        elif ev == "SHOWDOWN":
            hs.phase = "SHOWDOWN"
            summary = f"Showdown seat {msg.get('seat')}"
        elif ev == "POT_AWARD":
            amount = msg.get("amount", 0) or 0
            hs.pot = max(0, hs.pot - amount)
            self._adjust_player(msg.get("seat"), stack_delta=amount, reset_commit=True)
            summary = f"Payout seat {msg.get('seat')} +{amount}"
        elif ev == "ELIMINATED":
            player = self._ensure_player(msg.get("seat"))
            if player:
                player.has_folded = True
            summary = f"Seat {msg.get('seat')} eliminated"
        if summary:
            self.recent_events.append(summary)

    def _sync_state_from_act(self, msg: Dict[str, Any]) -> None:
        hs = self.hand_state
        table = msg.get("table", {})
        button = table.get("button")
        if hs is None or hs.hand_id != msg.get("hand_id"):
            self.hand_state = HandState(
                hand_id=msg["hand_id"],
                button=button if button is not None else -1,
            )
            hs = self.hand_state
        if button is not None:
            hs.button = button
        hs.phase = msg.get("phase", hs.phase)
        community = msg.get("community")
        if community is not None:
            hs.community = list(community)
        if "pot" in msg:
            hs.pot = msg.get("pot", hs.pot)
        if "current_bet" in msg:
            hs.current_bet = msg.get("current_bet", hs.current_bet)
        if "min_raise_increment" in msg:
            hs.min_raise_increment = msg.get("min_raise_increment", hs.min_raise_increment)
        for entry in msg.get("players", []):
            player = self._ensure_player(entry.get("seat"))
            if player:
                player.stack = entry.get("stack", player.stack)
                player.committed = entry.get("committed", player.committed)
                player.has_folded = entry.get("has_folded", player.has_folded)
        acting_seat = msg.get("seat")
        you = msg.get("you", {})
        player = self._ensure_player(acting_seat)
        if player:
            player.stack = you.get("stack", player.stack)
            player.committed = you.get("committed", player.committed)
            player.has_folded = False if acting_seat == self.seat else player.has_folded

    def _render_act_view(self, msg: Dict[str, Any]) -> None:
        hs = self.hand_state
        seat = msg.get("seat")
        you = msg.get("you", {})
        board = " ".join(hs.community) if hs and hs.community else "--"
        pot_display = hs.pot if hs else "?"
        round_committed = sum(player.committed for player in hs.players.values()) if hs else 0
        call_amount = msg.get("call_amount")
        min_raise_to = msg.get("min_raise_to")
        max_raise_to = msg.get("max_raise_to")
        if min_raise_to is not None and max_raise_to is not None:
            raise_range = f"{min_raise_to}–{max_raise_to}"
        elif min_raise_to is not None:
            raise_range = f"{min_raise_to}+"
        else:
            raise_range = "N/A"

        print(
            f"Hand {msg['hand_id']} | Phase {msg['phase']} | Board {board} | Pot={pot_display} | Current bet={hs.current_bet if hs else '?'} | Min raise inc={hs.min_raise_increment if hs else '?'}"
        )
        print(
            "You: hole={hole} stack={stack} committed={committed} to_call={to_call} time={time}ms".format(
                hole=you.get("hole"),
                stack=you.get("stack"),
                committed=you.get("committed"),
                to_call=you.get("to_call"),
                time=you.get("time_ms", 0),
            )
        )
        print(f"Legal: {msg.get('legal')} | call={call_amount} | raise_range={raise_range}")
        print(f"Round committed (all players): {round_committed}")
        if hs and hs.players:
            print("Table:")
            for idx in sorted(hs.players):
                player = hs.players[idx]
                marker = "→" if idx == seat else " "
                tags = []
                if idx == hs.button:
                    tags.append("BTN")
                if idx == self.seat:
                    tags.append("ME")
                if player.has_folded:
                    tags.append("FOLD")
                label = ",".join(tags) if tags else ""
                if label:
                    label = f" [{label}]"
                print(
                    f"  {marker}Seat {idx:>2}: stack={player.stack:>5} committed={player.committed:>5}{label}"
                )
        if self.recent_events:
            print("Recent:")
            for entry in reversed(self.recent_events):
                print(f"  {entry}")
        else:
            print("Recent: (none)")

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
    parser.add_argument("--url", default="ws://127.0.0.1:9876/ws")
    parser.add_argument("--team", required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    client = ManualClient(team=args.team, url=args.url)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nSession closed")


if __name__ == "__main__":
    main(sys.argv[1:])
