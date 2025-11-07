from __future__ import annotations

import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from .cards import Card, build_deck, deal
from .evaluator import evaluate_best, parse_cards
from .models import ActionType, Phase, PlayerSeat, TableConfig

# GameEngine keeps all table state in memory. No networking lives here—only
# poker rules, chip accounting, and betting order.


@dataclass
class HandContext:
    # All mutable info about the current hand (deck, pot, actor queue, etc.).
    hand_id: str
    seed: int
    button: int
    deck: List[Card]
    community: List[Card] = field(default_factory=list)
    phase: Phase = Phase.PRE_FLOP
    pot: int = 0
    current_bet: int = 0
    min_raise_increment: int = 0
    last_raise_seat: Optional[int] = None
    pending_callers: set[int] = field(default_factory=set)
    actor_queue: Deque[int] = field(default_factory=deque)
    pre_events: List[Dict[str, object]] = field(default_factory=list)


def describe_rank(score: Tuple[int, List[int]]) -> str:
    category, kickers = score
    if category == 8:
        return "straight_flush"
    if category == 7:
        return "four_of_a_kind"
    if category == 6:
        return "full_house"
    if category == 5:
        return "flush"
    if category == 4:
        return "straight"
    if category == 3:
        return "three_of_a_kind"
    if category == 2:
        return "two_pair"
    if category == 1:
        return "pair"
    return "high_card"


class GameEngine:
    """No-Limit Texas Hold'em engine for a single table."""

    def __init__(self, config: TableConfig) -> None:
        self.config = config
        self.seats: List[Optional[PlayerSeat]] = [None] * config.seats
        self.button: Optional[int] = None
        self.hand_counter = 0
        self.hand: Optional[HandContext] = None

    # Seat management -------------------------------------------------

    def assign_seat(self, team: str) -> PlayerSeat:
        team_display = team.strip()
        if not team_display:
            raise ValueError("TEAM_REQUIRED")

        team_key = self._normalize_team(team_display)
        existing = self._find_seat_by_key(team_key)
        if existing:
            if existing.team != team_display:
                existing.team = team_display
            return existing

        for idx in range(self.config.seats):
            seat = self.seats[idx]
            if seat is None:
                seat = PlayerSeat(seat=idx, team=team_display, team_key=team_key, stack=self.config.starting_stack)
                self.seats[idx] = seat
                return seat

        raise RuntimeError("Table is full")

    def _normalize_team(self, team: str) -> str:
        return team.strip().casefold()

    def _find_seat_by_key(self, team_key: str) -> Optional[PlayerSeat]:
        for seat in self.seats:
            if seat and seat.team_key == team_key:
                return seat
        return None

    def seating_order(self) -> List[int]:
        return [seat.seat for seat in self.seats if seat and seat.stack > 0]

    # Hand lifecycle --------------------------------------------------
    def can_start_hand(self) -> bool:
        active = [seat for seat in self.seats if seat and seat.stack > 0]
        return len(active) >= 2

    def start_hand(self, seed: Optional[int] = None) -> HandContext:
        if not self.can_start_hand():
            raise RuntimeError("Not enough active players to start a hand")

        active = [seat for seat in self.seats if seat and seat.stack > 0]
        for seat in active:
            seat.reset_for_hand()

        if seed is None:
            seed = int(time.time() * 1000) & 0xFFFFFFFF
        deck = build_deck(seed)

        # Move button
        if self.button is None:
            self.button = active[0].seat
        else:
            self.button = self._next_active_seat(self.button)

        hand_id = f"H-{time.strftime('%Y%m%d')}-{self.hand_counter:05d}"
        self.hand_counter += 1

        ctx = HandContext(
            hand_id=hand_id,
            seed=seed,
            button=self.button,
            deck=deck,
            community=[],
            phase=Phase.PRE_FLOP,
            pot=0,
            current_bet=0,
            min_raise_increment=self.config.bb,
            last_raise_seat=None,
            pending_callers=set(),
            actor_queue=deque(),
        )

        self._deal_hole_cards(ctx)
        self._post_blinds(ctx)
        self._setup_betting_round(ctx, preflop=True)
        self.hand = ctx
        return ctx

    def _deal_hole_cards(self, ctx: HandContext) -> None:
        ordered = self._active_seats_starting_from(ctx.button)
        for _ in range(2):
            for seat_idx in ordered:
                seat = self.seats[seat_idx]
                if seat is None:
                    continue
                card = deal(ctx.deck, 1)[0]
                seat.hole_cards.append(card.label)

    def _post_blinds(self, ctx: HandContext) -> None:
        active = [seat for seat in self.seats if seat and seat.stack > 0]
        if len(active) < 2:
            raise RuntimeError("Not enough active seats for blinds")

        heads_up = len(active) == 2
        if heads_up:
            sb_seat = ctx.button
            bb_seat = self._next_active_seat(ctx.button)
        else:
            sb_seat = self._next_active_seat(ctx.button)
            bb_seat = self._next_active_seat(sb_seat)
        sb_player = self.seats[sb_seat]
        bb_player = self.seats[bb_seat]
        assert sb_player and bb_player

        self._commit_chips(sb_player, min(sb_player.stack, self.config.sb), ctx)
        self._commit_chips(bb_player, min(bb_player.stack, self.config.bb), ctx)

        ctx.current_bet = max(player.committed for player in (sb_player, bb_player))
        ctx.min_raise_increment = self.config.bb
        ctx.last_raise_seat = bb_seat
        ctx.pre_events.append(
            {
                "ev": "POST_BLINDS",
                "sb_seat": sb_seat,
                "bb_seat": bb_seat,
                "sb": self.config.sb,
                "bb": self.config.bb,
            }
        )

    def _setup_betting_round(self, ctx: HandContext, preflop: bool) -> None:
        ctx.pending_callers.clear()
        ctx.actor_queue.clear()

        actionable = [seat.seat for seat in self.seats if seat and not seat.has_folded and seat.stack > 0]
        ctx.pending_callers.update(actionable)

        if preflop:
            active = [seat for seat in self.seats if seat and seat.stack > 0]
            heads_up = len(active) == 2
            if heads_up and self.button is not None:
                start_seat = self.button
            else:
                start_seat = self._next_active_seat(ctx.last_raise_seat)  # seat after big blind
        else:
            start_seat = self._next_active_seat(ctx.button)
            ctx.current_bet = 0
            ctx.min_raise_increment = self.config.bb
            ctx.last_raise_seat = None
            for seat_idx in actionable:
                seat = self.seats[seat_idx]
                if seat:
                    seat.reset_for_round()

        ctx.actor_queue.extend(self._rotation_from(start_seat))

    def _rotation_from(self, start: int) -> List[int]:
        seats = []
        idx = start % self.config.seats
        for _ in range(self.config.seats):
            seat = self.seats[idx]
            if seat and not seat.has_folded:
                seats.append(idx)
            idx = (idx + 1) % self.config.seats
        return seats

    def _active_seats_starting_from(self, start: int) -> List[int]:
        first = self._next_active_seat(start)
        ordered = []
        idx = first
        while True:
            seat = self.seats[idx]
            if seat and seat.stack > 0 and not seat.has_folded:
                ordered.append(idx)
            idx = (idx + 1) % self.config.seats
            if idx == first:
                break
        return ordered

    def _next_active_seat(self, start: Optional[int]) -> int:
        if start is None:
            raise RuntimeError("No start seat defined")
        idx = (start + 1) % self.config.seats
        while True:
            seat = self.seats[idx]
            if seat and seat.stack > 0 and not seat.has_folded:
                return idx
            idx = (idx + 1) % self.config.seats

    def _commit_chips(self, seat: PlayerSeat, amount: int, ctx: HandContext) -> None:
        amount = min(amount, seat.stack)
        seat.stack -= amount
        seat.committed += amount
        seat.total_in_pot += amount
        ctx.pot += amount

    # Action handling -------------------------------------------------
    def legal_actions(self, seat_idx: int) -> Tuple[List[ActionType], Optional[int], Optional[int], Optional[int]]:
        if not self.hand:
            raise RuntimeError("Hand not in progress")
        ctx = self.hand
        seat = self.seats[seat_idx]
        if seat is None or seat.has_folded:
            raise RuntimeError("Seat not active")

        # Return every legal move plus helper numbers (amount to call, min/max raise).
        legal: List[ActionType] = [ActionType.FOLD]
        call_amount = ctx.current_bet - seat.committed
        if call_amount <= 0:
            legal.append(ActionType.CHECK)
        elif seat.stack > 0:
            legal.append(ActionType.CALL)
        elif seat.stack == 0 and call_amount > 0:
            # All-in for less was already committed; nothing to do.
            call_amount = None

        max_raise_to = None
        min_raise_to = None
        if seat.stack > 0:
            min_raise_to = ctx.current_bet + ctx.min_raise_increment
            if seat.stack + seat.committed > min_raise_to:
                max_raise_to = seat.stack + seat.committed
                legal.append(ActionType.RAISE_TO)
            elif seat.stack + seat.committed > ctx.current_bet:
                max_raise_to = seat.stack + seat.committed
                min_raise_to = max_raise_to
                legal.append(ActionType.RAISE_TO)

        return legal, (call_amount if call_amount and call_amount > 0 else None), min_raise_to, max_raise_to

    def apply_action(self, seat_idx: int, action: ActionType, amount: Optional[int]) -> List[Dict[str, object]]:
        if not self.hand:
            raise RuntimeError("Hand not active")
        ctx = self.hand
        seat = self.seats[seat_idx]
        if seat is None or seat.has_folded:
            raise RuntimeError("Seat not active")

        events: List[Dict[str, object]] = []

        # Each branch records what happened so the server can broadcast it.
        if action == ActionType.FOLD:
            seat.has_folded = True
            ctx.pending_callers.discard(seat_idx)
            events.append({"ev": "FOLD", "seat": seat_idx})
        elif action == ActionType.CHECK:
            if ctx.current_bet > seat.committed:
                raise ValueError("Cannot check when facing a bet")
            ctx.pending_callers.discard(seat_idx)
            events.append({"ev": "CHECK", "seat": seat_idx})
        elif action == ActionType.CALL:
            call_amount = ctx.current_bet - seat.committed
            if call_amount <= 0:
                raise ValueError("Nothing to call")
            self._commit_chips(seat, call_amount, ctx)
            ctx.pending_callers.discard(seat_idx)
            events.append({"ev": "CALL", "seat": seat_idx, "amount": call_amount})
        elif action == ActionType.RAISE_TO:
            if amount is None:
                raise ValueError("Raise requires amount")
            max_raise_to = seat.stack + seat.committed
            if amount > max_raise_to:
                raise ValueError("Raise exceeds stack")
            if amount <= ctx.current_bet:
                raise ValueError("Raise must exceed current bet")
            min_raise_to = ctx.current_bet + ctx.min_raise_increment
            short_all_in = amount < min_raise_to
            if short_all_in and amount != max_raise_to:
                raise ValueError("Raise below minimum")
            if not short_all_in and amount < min_raise_to:
                raise ValueError("Raise below minimum")

            additional = amount - seat.committed
            self._commit_chips(seat, additional, ctx)
            previous_bet = ctx.current_bet
            ctx.current_bet = amount
            if not short_all_in:
                ctx.min_raise_increment = amount - previous_bet
                ctx.last_raise_seat = seat_idx
            ctx.pending_callers = {
                s
                for s in self._active_seats()
                if s != seat_idx and self.seats[s] and self.seats[s].stack > 0
            }
            events.append({"ev": "BET", "seat": seat_idx, "amount": additional})
        else:
            raise ValueError(f"Unsupported action {action}")

        if seat.stack == 0:
            ctx.pending_callers.discard(seat_idx)

        events.extend(self._advance_after_action(ctx))
        return events

    def _advance_after_action(self, ctx: HandContext) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        active = self._active_seats()
        if len(active) == 1:
            winner_idx = active[0]
            winner = self.seats[winner_idx]
            assert winner
            if ctx.pot > 0:
                winner.stack += ctx.pot
                events.append({"ev": "POT_AWARD", "seat": winner_idx, "amount": ctx.pot})
                ctx.pot = 0
            ctx.phase = Phase.SHOWDOWN
            ctx.pending_callers.clear()
            ctx.actor_queue.clear()
            for seat in self.seats:
                if seat:
                    seat.committed = 0
                    seat.total_in_pot = 0
            return events

        if ctx.actor_queue:
            ctx.actor_queue.append(ctx.actor_queue.popleft())
        while ctx.actor_queue:
            next_seat = ctx.actor_queue[0]
            seat = self.seats[next_seat]
            if seat and not seat.has_folded and (seat.stack > 0 or ctx.current_bet > seat.committed):
                break
            ctx.actor_queue.popleft()

        if not ctx.pending_callers:
            events.extend(self._advance_phase(ctx))

        return events

    def _advance_phase(self, ctx: HandContext) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []

        def reveal(ev: str, cards: List[Card]) -> None:
            events.append({"ev": ev, "cards": [card.label for card in cards]})

        progressed = False
        while True:
            if ctx.phase == Phase.PRE_FLOP:
                ctx.phase = Phase.FLOP
                cards = deal(ctx.deck, 3)
                ctx.community.extend(cards)
                reveal("FLOP", cards)
            elif ctx.phase == Phase.FLOP:
                ctx.phase = Phase.TURN
                cards = deal(ctx.deck, 1)
                ctx.community.extend(cards)
                events.append({"ev": "TURN", "card": cards[0].label})
            elif ctx.phase == Phase.TURN:
                ctx.phase = Phase.RIVER
                cards = deal(ctx.deck, 1)
                ctx.community.extend(cards)
                events.append({"ev": "RIVER", "card": cards[0].label})
            else:
                ctx.phase = Phase.SHOWDOWN
                events.extend(self._resolve_showdown(ctx))
                return events

            progressed = True

            for seat_idx in self._active_seats():
                seat = self.seats[seat_idx]
                if seat:
                    seat.reset_for_round()

            ctx.current_bet = 0
            ctx.min_raise_increment = self.config.bb
            ctx.last_raise_seat = None
            ctx.pending_callers = {
                s
                for s in self._active_seats()
                if self.seats[s] and self.seats[s].stack > 0
            }
            if ctx.pending_callers:
                start = self._next_active_seat(ctx.button)
                ctx.actor_queue = deque(self._rotation_from(start))
                break

            # No players with chips left → continue revealing to showdown.
            if ctx.phase == Phase.SHOWDOWN:
                break

        if progressed and ctx.phase != Phase.SHOWDOWN:
            # betting continues
            return events

        return events

    # Public/Snapshot helpers -----------------------------------------
    def lobby_state(self) -> Dict[str, object]:
        return {
            "players": [
                {
                    "seat": seat_idx,
                    "team": seat.team,
                    "connected": seat.connected,
                    "stack": seat.stack,
                }
                for seat_idx, seat in enumerate(self.seats)
                if seat is not None
            ]
        }

    def set_connected(self, seat_idx: int, connected: bool) -> None:
        seat = self.seats[seat_idx]
        if seat:
            seat.connected = connected

    def start_hand_payload(self, ctx: HandContext) -> Dict[str, object]:
        return {
            "hand_id": ctx.hand_id,
            "seed": ctx.seed,
            "button": ctx.button,
            "stacks": [
                {"seat": seat_idx, "stack": seat.stack + seat.total_in_pot}
                for seat_idx, seat in enumerate(self.seats)
                if seat is not None
            ],
        }

    def consume_pre_events(self) -> List[Dict[str, object]]:
        if not self.hand:
            return []
        events = list(self.hand.pre_events)
        self.hand.pre_events.clear()
        return events

    def next_actor(self) -> Optional[int]:
        if not self.hand:
            return None
        while self.hand.actor_queue and (
            (self.seats[self.hand.actor_queue[0]] is None)
            or self.seats[self.hand.actor_queue[0]].has_folded
        ):
            self.hand.actor_queue.popleft()
        return self.hand.actor_queue[0] if self.hand.actor_queue else None

    def act_payload(self, seat_idx: int) -> Dict[str, object]:
        if not self.hand:
            raise RuntimeError("Hand not active")
        ctx = self.hand
        seat = self.seats[seat_idx]
        if seat is None:
            raise RuntimeError("Seat empty")

        legal, call_amount, min_raise_to, max_raise_to = self.legal_actions(seat_idx)
        to_call = max(ctx.current_bet - seat.committed, 0)

        return {
            "hand_id": ctx.hand_id,
            "seat": seat_idx,
            "phase": ctx.phase.value,
            "pot": ctx.pot,
            "current_bet": ctx.current_bet,
            "min_raise_increment": ctx.min_raise_increment,
            "you": {
                "hole": list(seat.hole_cards),
                "stack": seat.stack,
                "committed": seat.committed,
                "to_call": to_call,
                "time_ms": self.config.move_time_ms,
            },
            "table": {
                "sb": self.config.sb,
                "bb": self.config.bb,
                "seats": self.config.seats,
                "button": ctx.button,
            },
            "players": [
                {
                    "seat": idx,
                    "stack": s.stack,
                    "has_folded": s.has_folded,
                    "committed": s.committed,
                }
                for idx, s in enumerate(self.seats)
                if s is not None
            ],
            "community": [card.label for card in ctx.community],
            "legal": [action.value for action in legal],
            "call_amount": call_amount,
            "min_raise_to": min_raise_to,
            "max_raise_to": max_raise_to,
        }

    def snapshot_payload(self, seat_idx: int, time_ms_remaining: int) -> Dict[str, object]:
        if not self.hand:
            raise RuntimeError("Hand not active")
        ctx = self.hand
        seat = self.seats[seat_idx]
        if seat is None:
            raise RuntimeError("Seat empty")

        next_actor = self.next_actor()
        legal, call_amount, min_raise_to, max_raise_to = self.legal_actions(seat_idx)

        payload = {
            "at_hand_id": ctx.hand_id,
            "phase": ctx.phase.value,
            "you": {
                "seat": seat_idx,
                "hole": list(seat.hole_cards),
                "stack": seat.stack,
                "to_call": max(ctx.current_bet - seat.committed, 0),
            },
            "players": [
                {
                    "seat": idx,
                    "stack": s.stack,
                    "has_folded": s.has_folded,
                    "committed": s.committed,
                }
                for idx, s in enumerate(self.seats)
                if s is not None
            ],
            "community": [card.label for card in ctx.community],
            "next_actor": next_actor,
            "time_ms_remaining": time_ms_remaining,
        }

        if next_actor == seat_idx:
            payload["legal"] = [action.value for action in legal]
            payload["call_amount"] = call_amount
            payload["min_raise_to"] = min_raise_to
            payload["max_raise_to"] = max_raise_to

        return payload

    def spectator_state(self, table_id: str, time_ms_remaining: Optional[int]) -> Optional[Dict[str, object]]:
        if not self.hand:
            return None
        ctx = self.hand
        next_actor = self.next_actor()
        seats = []
        for idx, seat in enumerate(self.seats):
            if seat is None:
                continue
            seats.append(
                {
                    "seat": idx,
                    "team": seat.team,
                    "stack": seat.stack,
                    "committed": seat.committed,
                    "hole": list(seat.hole_cards),
                    "has_folded": seat.has_folded,
                    "connected": seat.connected,
                    "is_button": ctx.button == idx if ctx.button is not None else False,
                }
            )
        return {
            "hand_id": ctx.hand_id,
            "table_id": table_id,
            "pot": ctx.pot,
            "phase": ctx.phase.value,
            "community": [card.label for card in ctx.community],
            "seats": seats,
            "next_actor": next_actor,
            "time_remaining_ms": time_ms_remaining if next_actor is not None else None,
            "sb": self.config.sb,
            "bb": self.config.bb,
        }

    def end_hand_payload(self) -> Dict[str, object]:
        if not self.hand:
            raise RuntimeError("Hand not active")
        ctx = self.hand
        return {
            "hand_id": ctx.hand_id,
            "stacks": [
                {"seat": idx, "stack": seat.stack}
                for idx, seat in enumerate(self.seats)
                if seat is not None
            ],
        }

    def is_hand_complete(self) -> bool:
        return bool(self.hand and self.hand.phase == Phase.SHOWDOWN and self.hand.pot == 0)

    def is_match_over(self) -> bool:
        active = [seat for seat in self.seats if seat and seat.stack > 0]
        return len(active) <= 1

    def match_result_payload(self) -> Dict[str, object]:
        active = [seat for seat in self.seats if seat and seat.stack > 0]
        winner = active[0] if active else None
        return {
            "winner": {"seat": winner.seat, "team": winner.team} if winner else None,
            "final_stacks": [
                {"seat": seat.seat, "team": seat.team, "stack": seat.stack}
                for seat in self.seats
                if seat is not None
            ],
        }

    def _resolve_showdown(self, ctx: HandContext) -> List[Dict[str, object]]:
        events: List[Dict[str, object]] = []
        board = list(ctx.community)
        board_labels = [card.label for card in board]

        scores: Dict[int, Tuple[int, List[int]]] = {}
        for seat_idx in self._active_seats():
            seat = self.seats[seat_idx]
            if seat is None or seat.has_folded:
                continue
            cards = parse_cards(seat.hole_cards) + board
            score = evaluate_best(cards)
            scores[seat_idx] = score
            events.append(
                {
                    "ev": "SHOWDOWN",
                    "seat": seat_idx,
                    "hand": list(seat.hole_cards),
                    "board": board_labels,
                    "rank": describe_rank(score),
                }
            )

        for pot_value, contenders in self._build_side_pots():
            if pot_value <= 0 or not contenders:
                continue
            best = max(scores[seat] for seat in contenders)
            winners = [seat for seat in contenders if scores[seat] == best]
            share, remainder = divmod(pot_value, len(winners))
            for idx, seat_idx in enumerate(sorted(winners)):
                payout = share + (1 if idx < remainder else 0)
                seat = self.seats[seat_idx]
                if seat:
                    seat.stack += payout
                events.append({"ev": "POT_AWARD", "seat": seat_idx, "amount": payout})
            ctx.pot -= pot_value

        eliminated = [seat.seat for seat in self.seats if seat and seat.stack == 0]
        for seat_idx in eliminated:
            events.append({"ev": "ELIMINATED", "seat": seat_idx})

        ctx.pending_callers.clear()
        ctx.actor_queue.clear()
        for seat in self.seats:
            if seat:
                seat.committed = 0
                seat.total_in_pot = 0
        return events

    def _build_side_pots(self) -> List[Tuple[int, List[int]]]:
        remaining: Dict[int, int] = {
            seat_idx: seat.total_in_pot
            for seat_idx, seat in enumerate(self.seats)
            if seat and seat.total_in_pot > 0
        }

        pots: List[Tuple[int, List[int]]] = []
        while True:
            active = [seat_idx for seat_idx, amount in remaining.items() if amount > 0]
            if not active:
                break
            min_amount = min(remaining[seat_idx] for seat_idx in active)
            eligible = list(active)
            pot_total = 0
            for seat_idx in eligible:
                take = min(min_amount, remaining[seat_idx])
                pot_total += take
                remaining[seat_idx] -= take
            contenders = [seat_idx for seat_idx in eligible if self.seats[seat_idx] and not self.seats[seat_idx].has_folded]
            pots.append((pot_total, contenders))
        return pots

    def _active_seats(self) -> List[int]:
        return [seat.seat for seat in self.seats if seat and not seat.has_folded]
