import pytest

from core.game import GameEngine
from core.models import ActionType, TableConfig

from .helpers import start_hand


def test_table_capacity_limit_enforced():
    engine = GameEngine(TableConfig(seats=6))
    for idx in range(6):
        seat = engine.assign_seat(f"Team{idx}")
        assert seat.seat == idx
    with pytest.raises(RuntimeError, match="Table is full"):
        engine.assign_seat("Overflow")


def test_engine_handles_thousand_hands_round_robin():
    engine = GameEngine(TableConfig(seats=6, starting_stack=2_000, sb=5, bb=10))
    for idx in range(engine.config.seats):
        engine.assign_seat(f"Stress{idx}")

    total_chips = sum(seat.stack for seat in engine.seats if seat)
    hands_played = 0

    for seed in range(1_000, 2_200):
        if not engine.can_start_hand():
            break
        start_hand(engine, seed=seed)
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
        engine.hand = None
        hands_played += 1

    assert hands_played >= 1_000
    remaining_total = sum(seat.stack for seat in engine.seats if seat)
    assert remaining_total == total_chips
