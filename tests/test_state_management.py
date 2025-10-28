from core.models import ActionType

from .helpers import create_engine, start_hand


def test_hand_can_be_restarted_after_manual_interruption():
    engine = create_engine(seats=3, starting_stack=200, sb=5, bb=10)
    ctx1 = start_hand(engine, seed=11)
    assert ctx1.hand_id
    engine.hand = None

    ctx2 = start_hand(engine, seed=12)
    assert ctx2.hand_id != ctx1.hand_id
    for seat in engine.seats:
        if seat:
            assert len(seat.hole_cards) == 2


def test_set_connected_updates_lobby_snapshot():
    engine = create_engine(seats=3)
    start_hand(engine)
    engine.set_connected(1, True)
    lobby = engine.lobby_state()
    player_entry = next(item for item in lobby["players"] if item["seat"] == 1)
    assert player_entry["connected"] is True
    engine.set_connected(1, False)
    lobby = engine.lobby_state()
    player_entry = next(item for item in lobby["players"] if item["seat"] == 1)
    assert player_entry["connected"] is False


def test_button_rotation_skips_eliminated_players():
    engine = create_engine(seats=3, starting_stack=200, sb=5, bb=10)
    engine.seats[1].stack = 0  # type: ignore[assignment]
    ctx1 = start_hand(engine, seed=21)
    assert ctx1.button == 0
    ctx2 = start_hand(engine, seed=22)
    assert ctx2.button == 2


def test_commit_chips_never_drops_stack_below_zero():
    engine = create_engine(seats=2, starting_stack=120, sb=5, bb=10)
    engine.seats[0].stack = 15  # type: ignore[assignment]
    start_hand(engine, seed=33)
    actor = engine.next_actor()
    _, _, _, max_raise = engine.legal_actions(actor)
    engine.apply_action(actor, ActionType.RAISE_TO, max_raise)
    seat = engine.seats[actor]
    assert seat is not None
    assert seat.stack >= 0
    ctx = engine.hand
    assert ctx is not None
    total_in_pot = sum(s.total_in_pot for s in engine.seats if s)
    assert ctx.pot == total_in_pot
