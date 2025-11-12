from __future__ import annotations

import random
from typing import Optional, Tuple

from core.game import GameEngine
from core.models import ActionType, Phase


_RNG = random.Random()
_RANK_POINTS = {rank: idx for idx, rank in enumerate("23456789TJQKA", start=2)}


def _rough_hand_strength(hole: list[str]) -> int:
    """Very rough proxy for hand quality used to drive aggression choices."""
    if len(hole) < 2:
        return 0

    ranks = [card[0] for card in hole]
    suits = [card[1] for card in hole]
    values = [_RANK_POINTS.get(rank, 2) for rank in ranks]

    score = sum(values)
    if ranks[0] == ranks[1]:
        score += 14  # pairs are quite strong pre-flop
    else:
        gap = abs(values[0] - values[1])
        if gap == 1:
            score += 4
        elif gap == 2:
            score += 2
    if suits[0] == suits[1]:
        score += 3
    if min(values) >= 11:
        score += 2

    return score


def _should_raise(strength: int, phase: Phase, facing_bet: bool) -> bool:
    # Encourage more post-flop barreling and occasional light opens.
    base = 0.2 if facing_bet else 0.35
    phase_bonus = {
        Phase.PRE_FLOP: 0.0,
        Phase.FLOP: 0.05,
        Phase.TURN: 0.1,
        Phase.RIVER: 0.12,
    }.get(phase, 0.0)
    scaled_strength = min(strength / 45.0, 0.45)
    probability = min(0.85, base + phase_bonus + scaled_strength)

    # Always attack with premium holdings.
    if strength >= 36:
        return True
    return _RNG.random() < probability


def _choose_raise_amount(
    min_raise_to: Optional[int],
    max_raise_to: Optional[int],
    facing_bet: bool,
) -> int:
    if min_raise_to is None:
        raise ValueError("Raise requested without a minimum amount")
    if max_raise_to is None or max_raise_to <= min_raise_to:
        return min_raise_to

    span = max_raise_to - min_raise_to
    roll = _RNG.random()

    # Facing a bet → weight toward stronger responses, otherwise mix in more probes.
    if facing_bet:
        if roll < 0.2:
            return min_raise_to
        if roll > 0.85:
            return max_raise_to
    else:
        if roll < 0.35:
            return min_raise_to
        if roll > 0.9:
            return max_raise_to

    return min_raise_to + int(span * _RNG.random())


def baseline_strategy(engine: GameEngine, seat_idx: int) -> Tuple[ActionType, Optional[int]]:
    """Aggressive demo bot: mixes in random raises with a bias toward stronger holdings."""

    legal, call_amount, min_raise_to, max_raise_to = engine.legal_actions(seat_idx)

    # Always fold if folding is only option.
    if len(legal) == 1 and legal[0] == ActionType.FOLD:
        return ActionType.FOLD, None

    seat = engine.seats[seat_idx]
    hole = seat.hole_cards if seat else []
    strength = _rough_hand_strength(hole)
    phase = engine.hand.phase if engine.hand else Phase.PRE_FLOP
    facing_bet = call_amount is not None

    if ActionType.RAISE_TO in legal and hole and _should_raise(strength, phase, facing_bet):
        amount = _choose_raise_amount(min_raise_to, max_raise_to, facing_bet)
        return ActionType.RAISE_TO, amount

    # Fall back to calling if legal.
    if ActionType.CALL in legal:
        return ActionType.CALL, None

    # Prefer checking when no chips are at risk and no raise happened.
    if ActionType.CHECK in legal:
        return ActionType.CHECK, None

    return ActionType.FOLD, None
