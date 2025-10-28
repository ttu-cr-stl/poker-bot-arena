import pytest

from core.cards import Card, deal
from core.models import ActionType

from .helpers import create_engine, start_hand


def test_check_when_facing_bet_raises_value_error():
    engine = create_engine()
    start_hand(engine, seed=101)
    actor = engine.next_actor()

    with pytest.raises(ValueError, match="Cannot check"):
        engine.apply_action(actor, ActionType.CHECK, None)


def test_call_with_no_amount_to_call_rejected():
    engine = create_engine()
    ctx = start_hand(engine, seed=202)
    actor = engine.next_actor()
    seat = engine.seats[actor]
    assert seat is not None
    seat.committed = ctx.current_bet

    with pytest.raises(ValueError, match="Nothing to call"):
        engine.apply_action(actor, ActionType.CALL, None)


def test_legal_actions_requires_active_seat():
    engine = create_engine()
    start_hand(engine)
    engine.seats[2] = None

    with pytest.raises(RuntimeError, match="Seat not active"):
        engine.legal_actions(2)


def test_apply_action_rejects_unknown_action():
    engine = create_engine()
    start_hand(engine)
    actor = engine.next_actor()

    with pytest.raises(ValueError, match="Unsupported action"):
        engine.apply_action(actor, None, None)  # type: ignore[arg-type]


def test_deal_raises_when_deck_exhausted():
    deck = [Card("A", "h"), Card("K", "d")]
    deal(deck, 2)
    with pytest.raises(ValueError, match="Not enough cards"):
        deal(deck, 1)
