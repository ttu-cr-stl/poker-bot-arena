from __future__ import annotations

from typing import Iterable, Tuple

from core.game import GameEngine, HandContext
from core.models import ActionType, TableConfig


def create_engine(
    *,
    seats: int = 4,
    starting_stack: int = 1_000,
    sb: int = 10,
    bb: int = 20,
    move_time_ms: int = 15_000,
) -> GameEngine:
    """Instantiate a game engine with a populated table."""
    engine = GameEngine(
        TableConfig(seats=seats, starting_stack=starting_stack, sb=sb, bb=bb, move_time_ms=move_time_ms)
    )
    for idx in range(seats):
        engine.assign_seat(f"Player{idx}")
    return engine


def start_hand(engine: GameEngine, seed: int = 42) -> HandContext:
    ctx = engine.start_hand(seed=seed)
    assert ctx is not None
    return ctx


def perform_actions(engine: GameEngine, actions: Iterable[Tuple[int, ActionType, int | None]]) -> None:
    """Apply a scripted sequence of actions (seat, action, amount)."""
    for seat_idx, action, amount in actions:
        engine.apply_action(seat_idx, action, amount)


def auto_complete_hand(engine: GameEngine) -> None:
    """Advance the current hand with straightforward actions until completion."""
    while not engine.is_hand_complete():
        actor = engine.next_actor()
        if actor is None:
            break
        legal, *_ = engine.legal_actions(actor)
        if ActionType.CHECK in legal:
            engine.apply_action(actor, ActionType.CHECK, None)
        elif ActionType.CALL in legal:
            engine.apply_action(actor, ActionType.CALL, None)
        else:
            engine.apply_action(actor, ActionType.FOLD, None)
