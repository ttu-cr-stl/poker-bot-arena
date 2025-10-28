from __future__ import annotations

from typing import Optional, Tuple

from core.game import GameEngine
from core.models import ActionType


def baseline_strategy(engine: GameEngine, seat_idx: int) -> Tuple[ActionType, Optional[int]]:
    """Tiny demo bot: call/check most spots, raise with strong preflop holdings."""

    legal, call_amount, min_raise_to, max_raise_to = engine.legal_actions(seat_idx)

    # Always fold if folding is only option.
    if len(legal) == 1 and legal[0] == ActionType.FOLD:
        return ActionType.FOLD, None

    # Prefer checking when no chips are at risk.
    if ActionType.CHECK in legal:
        return ActionType.CHECK, None

    # Rough hand strength: keep it simple by looking at hole cards.
    seat = engine.seats[seat_idx]
    hole = seat.hole_cards if seat else []
    strong_ranks = {"A", "K", "Q", "J"}

    if ActionType.RAISE_TO in legal and hole and all(card[0] in strong_ranks for card in hole):
        amount = max_raise_to or min_raise_to or call_amount or 0
        return ActionType.RAISE_TO, amount

    # Fall back to calling if legal.
    if ActionType.CALL in legal:
        return ActionType.CALL, None

    return ActionType.FOLD, None
