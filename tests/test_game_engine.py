import itertools

import pytest

from core.cards import Card, RANKS, SUITS
from core.game import GameEngine
from core.models import ActionType, TableConfig


def setup_engine(seed: int = 42) -> tuple[GameEngine, list[int]]:
    engine = GameEngine(TableConfig(seats=4, starting_stack=1000, sb=10, bb=20))
    engine.assign_seat("Alpha")
    engine.assign_seat("Beta")
    engine.assign_seat("Gamma")
    engine.assign_seat("Delta")
    ctx = engine.start_hand(seed=seed)
    assert ctx is not None
    return engine, [seat.seat for seat in engine.seats if seat]


def drain_to_next_round(engine: GameEngine) -> None:
    """Let every remaining actor check/call to advance the phase."""
    while True:
        seat_idx = engine.next_actor()
        if seat_idx is None:
            break
        legal, *_ = engine.legal_actions(seat_idx)
        if ActionType.CHECK in legal:
            engine.apply_action(seat_idx, ActionType.CHECK, None)
        elif ActionType.CALL in legal:
            engine.apply_action(seat_idx, ActionType.CALL, None)
        else:
            engine.apply_action(seat_idx, ActionType.FOLD, None)
        if engine.hand and engine.hand.phase in (engine.hand.phase.TURN, engine.hand.phase.RIVER, engine.hand.phase.SHOWDOWN):
            break


def test_start_hand_assigns_button_and_blinds():
    engine, seats = setup_engine()
    ctx = engine.hand
    assert ctx is not None
    assert ctx.button == seats[0]
    pre_events = engine.consume_pre_events()
    assert pre_events == [
        {
            "ev": "POST_BLINDS",
            "sb_seat": seats[1],
            "bb_seat": seats[2],
            "sb": engine.config.sb,
            "bb": engine.config.bb,
        }
    ]


def test_heads_up_button_posts_small_blind_and_acts_first():
    engine = GameEngine(TableConfig(seats=2, starting_stack=1000, sb=10, bb=20))
    seat_btn = engine.assign_seat("Button")
    seat_bb = engine.assign_seat("BigBlind")
    ctx = engine.start_hand(seed=123)
    assert ctx is not None
    assert ctx.button == seat_btn.seat
    pre_events = engine.consume_pre_events()
    assert pre_events[0]["sb_seat"] == seat_btn.seat
    assert pre_events[0]["bb_seat"] == seat_bb.seat
    first_actor = engine.next_actor()
    assert first_actor == seat_btn.seat


def test_action_payload_has_flat_legal_fields():
    engine, _ = setup_engine()
    seat = engine.next_actor()
    payload = engine.act_payload(seat)
    assert payload["legal"] == ["FOLD", "CALL", "RAISE_TO"]
    assert payload["call_amount"] == engine.hand.current_bet - engine.seats[seat].committed
    assert "min_raise_to" in payload and "max_raise_to" in payload
    assert payload["pot"] == engine.config.sb + engine.config.bb
    assert payload["current_bet"] == engine.config.bb
    assert payload["min_raise_increment"] == engine.config.bb


def test_raise_updates_pot_and_pending_callers():
    engine, _ = setup_engine()
    actor = engine.next_actor()
    min_raise = engine.legal_actions(actor)[2]
    events = engine.apply_action(actor, ActionType.RAISE_TO, min_raise)
    assert any(ev["ev"] == "BET" for ev in events)
    assert engine.hand.current_bet == min_raise
    assert engine.hand.last_raise_seat == actor


def test_showdown_awards_side_pot_and_flags_elimination():
    engine, _ = setup_engine(seed=7)
    # Force player 1 all-in with a raise, others call to showdown
    actor = engine.next_actor()
    min_raise = engine.legal_actions(actor)[2]
    engine.apply_action(actor, ActionType.RAISE_TO, min_raise)
    aggregated_events = []
    while True:
        seat_idx = engine.next_actor()
        if seat_idx is None:
            break
        legal, *_ = engine.legal_actions(seat_idx)
        if ActionType.CHECK in legal:
            events = engine.apply_action(seat_idx, ActionType.CHECK, None)
        elif ActionType.CALL in legal:
            events = engine.apply_action(seat_idx, ActionType.CALL, None)
        else:
            events = engine.apply_action(seat_idx, ActionType.FOLD, None)
        aggregated_events.extend(events)
        if engine.is_hand_complete():
            break

    assert engine.is_hand_complete()
    assert any(ev["ev"] == "SHOWDOWN" for ev in aggregated_events)
    assert any(ev["ev"] == "POT_AWARD" for ev in aggregated_events)


def test_snapshot_includes_legal_when_actor():
    engine, _ = setup_engine()
    actor = engine.next_actor()
    snapshot = engine.snapshot_payload(actor, time_ms_remaining=4000)
    assert snapshot["next_actor"] == actor
    assert snapshot["legal"] == ["FOLD", "CALL", "RAISE_TO"]
    assert snapshot["call_amount"] is not None
    assert snapshot["min_raise_to"] is not None
    assert snapshot["max_raise_to"] is not None


def test_match_result_payload_when_match_over():
    engine = GameEngine(TableConfig(seats=2, starting_stack=100))
    seat_a = engine.assign_seat("Alpha")
    seat_b = engine.assign_seat("Beta")
    seat_b.stack = 0
    assert engine.is_match_over()
    payload = engine.match_result_payload()
    winner = payload["winner"]
    assert winner["team"] == "Alpha"
    assert any(entry["team"] == "Beta" for entry in payload["final_stacks"])


def test_split_pot_results_in_equal_awards(monkeypatch):
    engine = GameEngine(TableConfig(seats=2, starting_stack=1000, sb=50, bb=100))
    engine.assign_seat("Alpha")
    engine.assign_seat("Beta")

    used = []
    def card(rank, suit):
        used.append((rank, suit))
        return Card(rank, suit)

    custom_cards = [
        card("8", "c"), card("9", "d"),  # Seat order: BB first card, button second
        card("T", "s"), card("J", "c"),
        card("2", "h"), card("3", "d"), card("4", "c"),
        card("5", "s"), card("6", "h"),
    ]

    for rank in RANKS:
        for suit in SUITS:
            if (rank, suit) not in used:
                custom_cards.append(Card(rank, suit))

    monkeypatch.setattr("core.game.build_deck", lambda seed=None: list(custom_cards))

    ctx = engine.start_hand()
    assert ctx is not None

    aggregated = []
    while True:
        seat_idx = engine.next_actor()
        if seat_idx is None:
            break
        legal, call_amount, min_raise_to, max_raise_to = engine.legal_actions(seat_idx)
        if ActionType.CALL in legal:
            events = engine.apply_action(seat_idx, ActionType.CALL, None)
        elif ActionType.CHECK in legal:
            events = engine.apply_action(seat_idx, ActionType.CHECK, None)
        else:
            events = engine.apply_action(seat_idx, ActionType.FOLD, None)
        aggregated.extend(events)
        if engine.is_hand_complete():
            break

    assert engine.is_hand_complete()
    awards = [event for event in aggregated if event["ev"] == "POT_AWARD"]
    assert len(awards) == 2
    assert sum(event["amount"] for event in awards) == engine.config.bb * 2
    stacks = [seat.stack for seat in engine.seats if seat]
    assert stacks == [1000, 1000]


def test_multiple_hands_rotate_button_and_reset_state():
    engine = GameEngine(TableConfig(seats=3, starting_stack=500, sb=10, bb=20))
    engine.assign_seat("Alpha")
    engine.assign_seat("Beta")
    engine.assign_seat("Gamma")

    first_ctx = engine.start_hand(seed=10)
    assert first_ctx.button == 0

    winner = 0
    aggregated = []
    while True:
        seat_idx = engine.next_actor()
        if seat_idx is None:
            break
        if seat_idx == winner:
            legal, *_ = engine.legal_actions(seat_idx)
            if ActionType.CHECK in legal:
                events = engine.apply_action(seat_idx, ActionType.CHECK, None)
            else:
                events = engine.apply_action(seat_idx, ActionType.CALL, None)
        else:
            events = engine.apply_action(seat_idx, ActionType.FOLD, None)
        aggregated.extend(events)
        if engine.is_hand_complete():
            break

    assert engine.is_hand_complete()
    engine.hand = None

    second_ctx = engine.start_hand(seed=20)
    assert second_ctx.button == 1
    stacks = [seat.stack for seat in engine.seats if seat]
    assert stacks[0] > stacks[1] and stacks[0] > stacks[2]


def test_fold_immediately_ends_hand_without_extra_prompt():
    engine = GameEngine(TableConfig(seats=2, starting_stack=500, sb=10, bb=20))
    engine.assign_seat("Alpha")
    engine.assign_seat("Beta")
    ctx = engine.start_hand(seed=5)
    assert ctx is not None

    # Actor is seat after big blind
    actor = engine.next_actor()
    legal, *_ = engine.legal_actions(actor)
    assert "FOLD" in legal
    events = engine.apply_action(actor, ActionType.FOLD, None)
    assert any(ev["ev"] == "FOLD" for ev in events)
    assert any(ev["ev"] == "POT_AWARD" for ev in events)
    assert engine.is_hand_complete()
    assert not ctx.actor_queue
    assert not ctx.pending_callers


def test_all_in_creates_side_pot_and_awards_correctly():
    engine = GameEngine(TableConfig(seats=3, starting_stack=500, sb=10, bb=20))
    engine.assign_seat("A")
    engine.assign_seat("B")
    engine.assign_seat("C")
    ctx = engine.start_hand(seed=15)
    assert ctx is not None

    # Seat order: 0 button, 1 sb, 2 bb → first actor seat 0 (button)
    seat = engine.next_actor()
    engine.seats[seat].stack = 100  # short stack all-in
    legal, min_raise, *_ = engine.legal_actions(seat)
    engine.apply_action(seat, ActionType.RAISE_TO, engine.seats[seat].stack + engine.seats[seat].committed)

    # Other players call
    while not engine.is_hand_complete():
        actor = engine.next_actor()
        if actor is None:
            break
        legal, *_ = engine.legal_actions(actor)
        if ActionType.CALL in legal:
            engine.apply_action(actor, ActionType.CALL, None)
        elif ActionType.CHECK in legal:
            engine.apply_action(actor, ActionType.CHECK, None)
        else:
            engine.apply_action(actor, ActionType.FOLD, None)

    assert engine.is_hand_complete()
    assert not ctx.pending_callers


def test_multiway_split_returns_equal_shares(monkeypatch):
    engine = GameEngine(TableConfig(seats=3, starting_stack=1000, sb=10, bb=20))
    for name in ("A", "B", "C"):
        engine.assign_seat(name)

    # Build deck to force everyone to same straight
    from core.cards import Card

    deck = [
        Card("2", "h"), Card("2", "d"), Card("2", "c"),
        Card("3", "h"), Card("3", "d"), Card("3", "c"),
        Card("4", "s"), Card("5", "s"), Card("6", "s"), Card("7", "s"), Card("8", "s"),
    ]
    monkeypatch.setattr("core.game.build_deck", lambda seed=None: list(deck))

    ctx = engine.start_hand()
    assert ctx is not None
    while not engine.is_hand_complete():
        actor = engine.next_actor()
        if actor is None:
            break
        legal, *_ = engine.legal_actions(actor)
        if ActionType.CALL in legal:
            engine.apply_action(actor, ActionType.CALL, None)
        elif ActionType.CHECK in legal:
            engine.apply_action(actor, ActionType.CHECK, None)
        else:
            engine.apply_action(actor, ActionType.FOLD, None)

    stacks = [seat.stack for seat in engine.seats if seat]
    assert len(set(stacks)) == 1


def test_min_raise_caps_when_stack_exact(monkeypatch):
    engine = GameEngine(TableConfig(seats=2, starting_stack=200, sb=10, bb=20))
    engine.assign_seat("A")
    engine.assign_seat("B")
    ctx = engine.start_hand(seed=123)
    assert ctx is not None

    actor = engine.next_actor()
    seat = engine.seats[actor]
    seat.stack = ctx.current_bet + ctx.min_raise_increment - seat.committed
    legal, call_amount, min_raise_to, max_raise_to = engine.legal_actions(actor)
    assert min_raise_to == max_raise_to
    events = engine.apply_action(actor, ActionType.RAISE_TO, min_raise_to)
    assert any(ev["ev"] == "BET" for ev in events)


def test_zero_to_call_prefers_check():
    engine = GameEngine(TableConfig(seats=2, starting_stack=200, sb=10, bb=20))
    engine.assign_seat("A")
    engine.assign_seat("B")
    ctx = engine.start_hand(seed=33)
    assert ctx is not None

    # Force current bet equal to actor commitment
    actor = engine.next_actor()
    seat = engine.seats[actor]
    seat.committed = ctx.current_bet
    legal, call_amount, *_ = engine.legal_actions(actor)
    assert "CHECK" in legal
    assert call_amount is None
    events = engine.apply_action(actor, ActionType.CHECK, None)
    assert any(ev["ev"] == "CHECK" for ev in events)


def test_fold_cascade_post_flop_finishes_hand():
    engine = GameEngine(TableConfig(seats=3, starting_stack=300, sb=10, bb=20))
    engine.assign_seat("A")
    engine.assign_seat("B")
    engine.assign_seat("C")
    ctx = engine.start_hand(seed=50)
    assert ctx is not None

    # Move through flop with minimal betting
    while ctx.phase != ctx.phase.FLOP:
        actor = engine.next_actor()
        legal, *_ = engine.legal_actions(actor)
        if ActionType.CALL in legal:
            engine.apply_action(actor, ActionType.CALL, None)
        elif ActionType.CHECK in legal:
            engine.apply_action(actor, ActionType.CHECK, None)

    # Two players fold, leaving one
    remaining = engine.next_actor()
    fold_targets = [remaining, engine._next_active_seat(remaining)]
    for seat_idx in fold_targets:
        engine.apply_action(seat_idx, ActionType.FOLD, None)

    assert engine.is_hand_complete()
    assert ctx.phase == ctx.phase.SHOWDOWN


def test_match_end_when_last_player_busts():
    engine = GameEngine(TableConfig(seats=2, starting_stack=100, sb=10, bb=20))
    seat_a = engine.assign_seat("Alpha")
    seat_b = engine.assign_seat("Beta")
    seat_b.stack = 0
    assert engine.is_match_over()
    payload = engine.match_result_payload()
    assert payload["winner"]["team"] == "Alpha"


def test_snapshot_includes_values_when_actor():
    engine = GameEngine(TableConfig(seats=2, starting_stack=200, sb=10, bb=20))
    engine.assign_seat("A")
    engine.assign_seat("B")
    ctx = engine.start_hand(seed=44)
    assert ctx is not None
    actor = engine.next_actor()
    snapshot = engine.snapshot_payload(actor, time_ms_remaining=3000)
    assert snapshot["legal"] == ["FOLD", "CALL", "RAISE_TO"]
    assert snapshot["call_amount"] is not None
    assert snapshot["min_raise_to"] is not None
    assert snapshot["max_raise_to"] is not None


def test_timer_fallback_prefers_check_then_call_then_fold():
    engine = GameEngine(TableConfig(seats=2, starting_stack=200, sb=10, bb=20, move_time_ms=1000))
    engine.assign_seat("A")
    engine.assign_seat("B")
    ctx = engine.start_hand(seed=60)
    assert ctx is not None

    # First prompt: actor should have CALL legal
    actor = engine.next_actor()
    legal, *_ = engine.legal_actions(actor)
    assert ActionType.CALL in legal
    events = engine.apply_action(actor, ActionType.CALL, None)
    assert any(ev["ev"] == "CALL" for ev in events)


def test_spectator_state_includes_omniscient_view():
    engine = GameEngine(TableConfig(seats=3, starting_stack=500, sb=10, bb=20))
    engine.assign_seat("Alpha")
    engine.assign_seat("Beta")
    engine.assign_seat("Gamma")
    ctx = engine.start_hand(seed=99)
    assert ctx is not None

    state = engine.spectator_state(table_id="T-1", time_ms_remaining=8000)
    assert state is not None
    assert state["hand_id"].startswith("H-")
    assert state["phase"] == ctx.phase.value
    assert state["pot"] >= engine.config.sb + engine.config.bb
    assert state["sb"] == engine.config.sb
    assert state["bb"] == engine.config.bb

    seats = {entry["seat"]: entry for entry in state["seats"]}
    assert len(seats) == 3
    assert all(len(entry["hole"]) == 2 for entry in seats.values())
    assert any(entry["is_button"] for entry in seats.values())
    assert state["next_actor"] in seats
    # Since spectator view is omniscient, each seat exposes committed stack data.
    assert all("committed" in entry for entry in seats.values())
