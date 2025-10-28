from core.models import ActionType

from .helpers import create_engine, start_hand


def test_multiple_raises_update_min_increment_and_last_raiser():
    engine = create_engine(seats=3, starting_stack=500, sb=5, bb=10)
    ctx = start_hand(engine, seed=303)
    initial_bet = ctx.current_bet

    first_actor = engine.next_actor()
    _, _, min_raise_to, _ = engine.legal_actions(first_actor)
    first_events = engine.apply_action(first_actor, ActionType.RAISE_TO, min_raise_to)
    assert any(ev["ev"] == "BET" for ev in first_events)
    assert engine.hand is not None
    assert engine.hand.current_bet == min_raise_to
    assert engine.hand.min_raise_increment == min_raise_to - initial_bet
    assert engine.hand.last_raise_seat == first_actor

    second_actor = engine.next_actor()
    _, _, second_min_raise, _ = engine.legal_actions(second_actor)
    second_events = engine.apply_action(second_actor, ActionType.RAISE_TO, second_min_raise)
    assert any(ev["ev"] == "BET" for ev in second_events)
    assert engine.hand.current_bet == second_min_raise
    assert engine.hand.min_raise_increment == second_min_raise - min_raise_to
    assert engine.hand.last_raise_seat == second_actor


def test_multiway_all_ins_create_side_pots_and_awards():
    engine = create_engine(seats=3, starting_stack=500, sb=5, bb=10)
    engine.seats[0].stack = 100  # type: ignore[assignment]
    engine.seats[1].stack = 300  # type: ignore[assignment]
    engine.seats[2].stack = 500  # type: ignore[assignment]
    start_hand(engine, seed=404)

    aggregated_events = []

    first_actor = engine.next_actor()
    _, _, _, max_raise0 = engine.legal_actions(first_actor)
    aggregated_events.extend(engine.apply_action(first_actor, ActionType.RAISE_TO, max_raise0))

    second_actor = engine.next_actor()
    _, _, _, max_raise1 = engine.legal_actions(second_actor)
    aggregated_events.extend(engine.apply_action(second_actor, ActionType.RAISE_TO, max_raise1))

    third_actor = engine.next_actor()
    legal, *_ = engine.legal_actions(third_actor)
    assert ActionType.CALL in legal
    aggregated_events.extend(engine.apply_action(third_actor, ActionType.CALL, None))

    # Confirm side-pot structure before community cards run out.
    pots = engine._build_side_pots()
    assert len(pots) == 2
    assert pots[0][0] > 0 and pots[1][0] > 0

    # Finish the hand with straightforward actions.
    while not engine.is_hand_complete():
        actor = engine.next_actor()
        if actor is None:
            break
        legal, *_ = engine.legal_actions(actor)
        if ActionType.CHECK in legal:
            aggregated_events.extend(engine.apply_action(actor, ActionType.CHECK, None))
        elif ActionType.CALL in legal:
            aggregated_events.extend(engine.apply_action(actor, ActionType.CALL, None))
        else:
            aggregated_events.extend(engine.apply_action(actor, ActionType.FOLD, None))

    awards = [event for event in aggregated_events if event["ev"] == "POT_AWARD"]
    assert len(awards) >= 1
    assert engine.is_hand_complete()
