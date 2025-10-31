#!/usr/bin/env python3
"""
Starter bot template for Poker Bot Arena teams.

Usage:
    python sample_bot.py --team MyBot --code SECRET \
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
STREAM_HANDLER = logging.StreamHandler()
STREAM_HANDLER.setFormatter(logging.Formatter("%(message)s"))
if not LOGGER.handlers:
    LOGGER.addHandler(STREAM_HANDLER)
LOGGER.propagate = False

USE_UNICODE_CARDS = True
SUIT_SYMBOLS = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}


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
    """Very simple strategy used as a starting point for students."""

    # Training wheels strategy: check → call small → fold.
    # Prefer checking whenever it is free.
    if "CHECK" in ctx.legal:
        return "CHECK", None

    # Call small bets to see cheap showdowns.
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


async def play_hand(websocket: websockets.WebSocketServerProtocol, team_name: str) -> None:
    """Listen for host messages, respond to act prompts, and log hand summaries."""

    state: Dict[str, Any] = {
        "seat": None,
        "seat_count": None,
        "hand_id": None,
        "phase": "PRE_FLOP",
        "phase_label": "PRE",
        "hand_log": None,
        "hand_counter": 0,
        "team_name": team_name,
        "seat_map": {},
    }

    def set_phase(raw_phase: Optional[str]) -> None:
        if not raw_phase:
            return
        state["phase"] = raw_phase
        state["phase_label"] = {
            "PRE_FLOP": "PRE",
            "FLOP": "FLOP",
            "TURN": "TURN",
            "RIVER": "RIVER",
            "SHOWDOWN": "SHOW",
        }.get(raw_phase, raw_phase)

    def seat_label(seat: Optional[int]) -> str:
        if seat is None:
            return "Seat ?"
        if seat == state.get("seat"):
            name = state.get("team_name") or f"Seat {seat}"
            return f"{name} (bot, seat {seat})"
        seat_count = state.get("seat_count")
        team = state.get("seat_map", {}).get(seat)
        if team:
            if seat_count == 2:
                return f"{team} (opponent, seat {seat})"
            return f"{team} (seat {seat})"
        if seat_count == 2:
            return f"Opponent (seat {seat})"
        return f"Seat {seat}"

    def format_stacks(stacks: list[dict[str, Any]]) -> str:
        if not stacks:
            return "-"
        return ", ".join(
            f"{seat_label(entry.get('seat'))}:{entry.get('stack')}"
            for entry in stacks
        )

    async for raw in websocket:
        message = json.loads(raw)
        msg_type = message.get("type")

        if msg_type == "welcome":
            state["seat"] = message.get("seat")
            cfg = message.get("config", {})
            state["seat_count"] = cfg.get("seats")
            register_seat(state, state["seat"], state.get("team_name"))
            LOGGER.info(
                "[welcome] seat %s | variant=%s seats=%s sb=%s bb=%s",
                seat_label(state["seat"]),
                cfg.get("variant"),
                cfg.get("seats"),
                cfg.get("sb"),
                cfg.get("bb"),
            )
            continue

        if msg_type == "start_hand":
            # Reset per-hand state and record baseline info for the recap.
            state["hand_id"] = message.get("hand_id")
            set_phase("PRE_FLOP")
            log = {
                "hand_id": state["hand_id"],
                "button": message.get("button"),
                "start_stacks": message.get("stacks", []),
                "actions": {"PRE": [], "FLOP": [], "TURN": [], "RIVER": []},
                "board": [],
                "board_by_phase": {},
                "showdown": [],
                "payouts": [],
                "eliminations": [],
            }
            state["hand_log"] = log
            LOGGER.info(
                "[hand %s] start | button %s | stacks %s",
                state["hand_id"],
                seat_label(log["button"]),
                format_stacks(log["start_stacks"]),
            )
            continue

        if msg_type == "lobby":
            # Keep track of player names when the host sends lobby updates.
            players = message.get("players", [])
            for player in players:
                register_seat(state, player.get("seat"), player.get("team"))
            continue

        if msg_type == "event":
            # Record table events to replay later in the summary.
            log = state.get("hand_log")
            if log is None:
                continue
            ev = message.get("ev")
            if ev == "POST_BLINDS":
                log["actions"]["PRE"].append(f"{seat_label(message.get('sb_seat'))} posts SB {message.get('sb')}")
                log["actions"]["PRE"].append(f"{seat_label(message.get('bb_seat'))} posts BB {message.get('bb')}")
            elif ev in {"BET", "CALL", "CHECK", "FOLD"}:
                verbs = {
                    "BET": "bets",
                    "CALL": "calls",
                    "CHECK": "checks",
                    "FOLD": "folds",
                }
                amount = message.get("amount")
                amount_str = f" {amount}" if amount is not None else ""
                phase_key = state.get("phase_label", "PRE")
                log["actions"].setdefault(phase_key, [])
                log["actions"][phase_key].append(f"{seat_label(message.get('seat'))} {verbs[ev]}{amount_str}")
            elif ev == "FLOP":
                set_phase("FLOP")
                log["board"] = list(message.get("cards", []))
                log["board_by_phase"]["FLOP"] = list(log["board"])
            elif ev == "TURN":
                card = message.get("card")
                if card:
                    log["board"].append(card)
                set_phase("TURN")
                log["board_by_phase"]["TURN"] = list(log["board"])
            elif ev == "RIVER":
                card = message.get("card")
                if card:
                    log["board"].append(card)
                set_phase("RIVER")
                log["board_by_phase"]["RIVER"] = list(log["board"])
            elif ev == "SHOWDOWN":
                set_phase("SHOWDOWN")
                log["showdown"].append(
                    {
                        "seat": message.get("seat"),
                        "hand": list(message.get("hand", [])),
                        "rank": message.get("rank"),
                    }
                )
            elif ev == "POT_AWARD":
                log["payouts"].append(
                    {
                        "seat": message.get("seat"),
                        "amount": message.get("amount"),
                    }
                )
            elif ev == "ELIMINATED":
                seat = message.get("seat")
                if seat is not None:
                    log["eliminations"].append(seat)
            else:
                LOGGER.debug("Unhandled event %s for hand %s", ev, state.get("hand_id"))
            continue

        if msg_type == "act":
            # Host is asking us to act; choose a move and respond.
            set_phase(message.get("phase"))
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
            continue

        if msg_type == "end_hand":
            # Emit a human-readable recap now that the hand is complete.
            log = state.get("hand_log")
            final_stacks = format_stacks(message.get("stacks", []))
            hand_id = message.get("hand_id") or state.get("hand_id")
            if log:
                LOGGER.info(
                    "[hand %s] summary | button %s | start stacks %s",
                    log["hand_id"],
                    seat_label(log["button"]),
                    format_stacks(log["start_stacks"]),
                )
                phase_order = [
                    ("PRE", "Preflop"),
                    ("FLOP", "Flop"),
                    ("TURN", "Turn"),
                    ("RIVER", "River"),
                ]
                actions = log.get("actions", {})
                board_by_phase = log.get("board_by_phase", {})
                for key, label in phase_order:
                    entries = actions.get(key, [])
                    board_cards = None if key == "PRE" else board_by_phase.get(key)
                    if not entries and not board_cards:
                        continue
                    if key == "PRE":
                        LOGGER.info("  %s:", label)
                    else:
                        board_str = render_cards(board_cards) if board_cards else "--"
                        LOGGER.info("  %s [%s]:", label, board_str)
                    for entry in entries:
                        LOGGER.info("    %s", entry)
                if log["showdown"]:
                    LOGGER.info("  Showdown:")
                    for entry in log["showdown"]:
                        LOGGER.info(
                            "    %s shows %s (%s)",
                            seat_label(entry["seat"]),
                            render_cards(entry["hand"]),
                            entry.get("rank"),
                        )
                if log["payouts"]:
                    LOGGER.info("  Payouts:")
                    for entry in log["payouts"]:
                        LOGGER.info("    %s +%s", seat_label(entry["seat"]), entry["amount"])
                if log["eliminations"]:
                    eliminated = ", ".join(seat_label(seat) for seat in log["eliminations"])
                    LOGGER.info("  Eliminated: %s", eliminated)
                state["hand_counter"] = state.get("hand_counter", 0) + 1
            LOGGER.info("[hand %s] end | stacks %s", hand_id, final_stacks)
            LOGGER.info("")
            state["hand_log"] = None
            continue

        if msg_type == "match_end":
            final_stacks = message.get("final_stacks", [])
            for entry in final_stacks:
                register_seat(state, entry.get("seat"), entry.get("team"))
            winner = message.get("winner") or {}
            winner_label = (
                f"{seat_label(winner.get('seat'))}"
                if winner
                else "None"
            )
            LOGGER.info(
                "[match] winner=%s final_stacks=%s",
                winner_label,
                format_stacks(message.get("final_stacks", [])),
            )
            LOGGER.info("")
            break

        if msg_type == "error":
            LOGGER.warning("[error] %s", message)
            continue

        if msg_type == "snapshot":
            LOGGER.debug("[snapshot] %s", message)
            continue

        LOGGER.debug("Ignoring message type=%s", msg_type)


async def run_bot(team: str, join_code: str, url: str) -> None:
    try:
        async with websockets.connect(url) as ws:
            hello = {
                "type": "hello",
                "v": 1,
                "team": team,
                "join_code": join_code,
            }
            await ws.send(json.dumps(hello))
            LOGGER.info("[connect] %s as %s", url, team)
            # Stay inside play_hand until the server sends match_end.
            await play_hand(ws, team)
    except websockets.exceptions.InvalidStatusCode as exc:
        if exc.status_code in {502, 503}:  # typical cold-start codes on Render/Fly free tiers
            LOGGER.error("Server reported %s (service warming up?). Wait 30s and retry.", exc.status_code)
        else:
            LOGGER.error("Failed to connect: %s", exc)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample Poker Bot client")
    parser.add_argument("--team", required=True, help="Team name registered with the host")
    parser.add_argument("--code", required=True, help="Join code provided by organizers")
    parser.add_argument("--url", default="ws://127.0.0.1:9876/ws", help="WebSocket URL")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    LOGGER.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(run_bot(args.team, args.code, args.url))


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def register_seat(state: Dict[str, Any], seat: Optional[int], team: Optional[str]) -> None:
    """Remember which team is sitting in each seat so logs can use names."""

    if seat is None or team is None:
        return
    state.setdefault("seat_map", {})[seat] = team


def render_card(card: str) -> str:
    """Return a card such as 'Ah' rendered with a unicode suit if enabled."""

    if USE_UNICODE_CARDS and len(card) == 2 and card[1] in SUIT_SYMBOLS:
        return card[0] + SUIT_SYMBOLS[card[1]]
    return card


def render_cards(cards: list[str]) -> str:
    """Render a sequence of cards for logging."""

    if not cards:
        return "--"
    return " ".join(render_card(card) for card in cards)


if __name__ == "__main__":
    main()
