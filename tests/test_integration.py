import asyncio
import json
import time

import pytest

from core.game import GameEngine
from core.models import ActionType, Phase, TableConfig
from tournament.server import ClientSession, HostServer, PendingAction


# Fake sockets so we can exercise async paths without opening real connections.
class DummyWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self, *args, **kwargs) -> None:
        self.closed = True


class DummyTask:
    def cancel(self) -> None:
        pass


def setup_server(num_players: int = 2, move_time_ms: int = 100) -> tuple[HostServer, list[ClientSession], list[DummyWebSocket]]:
    server = HostServer(
        TableConfig(seats=num_players, starting_stack=200, sb=5, bb=10, move_time_ms=move_time_ms)
    )
    sessions: list[ClientSession] = []
    sockets: list[DummyWebSocket] = []

    for idx in range(num_players):
        seat = server.engine.assign_seat(f"Team{idx}", f"CODE{idx}")
        websocket = DummyWebSocket()
        session = ClientSession(seat=seat.seat, team=seat.team, websocket=websocket, join_code=seat.join_code)
        server.sessions[seat.seat] = session
        server.engine.set_connected(seat.seat, True)
        sessions.append(session)
        sockets.append(websocket)

    return server, sessions, sockets


def test_handle_action_rejects_out_of_turn():
    server, sessions, sockets = setup_server()
    ctx = server.engine.start_hand(seed=50)
    server.pending_action = PendingAction(seat=sessions[0].seat, deadline=time.monotonic() + 1, timer_task=DummyTask())

    asyncio.run(server._handle_action(sessions[1], {"hand_id": ctx.hand_id, "action": ActionType.CALL.value}))

    assert sockets[1].sent, "Expected error message for out-of-turn action"
    payload = json.loads(sockets[1].sent[-1])
    assert payload["type"] == "error"
    assert payload["code"] == "OUT_OF_TURN"


def test_timer_expired_prefers_check(monkeypatch):
    server, _, _ = setup_server()
    start_ctx = server.engine.start_hand(seed=60)
    actor = server.engine.next_actor()
    assert actor is not None
    seat = server.engine.seats[actor]
    assert seat is not None
    seat.committed = start_ctx.current_bet

    events: list[dict[str, object]] = []

    async def capture_events(payload):
        events.extend(payload)

    async def noop_prompt():
        return None

    monkeypatch.setattr(server, "_broadcast_events", capture_events)
    monkeypatch.setattr(server, "_prompt_next_actor", noop_prompt)

    server.pending_action = PendingAction(seat=actor, deadline=time.monotonic() + 0.1, timer_task=DummyTask())
    asyncio.run(server._timer_expired(actor, time.monotonic()))

    assert events
    assert events[-1]["ev"] == "CHECK"


def test_timer_expired_prefers_call_when_check_not_available(monkeypatch):
    server, _, _ = setup_server()
    start_ctx = server.engine.start_hand(seed=70)
    actor = server.engine.next_actor()
    assert actor is not None
    seat = server.engine.seats[actor]
    assert seat is not None
    seat.committed = start_ctx.current_bet - 1

    events: list[dict[str, object]] = []

    async def capture_events(payload):
        events.extend(payload)

    async def noop_prompt():
        return None

    monkeypatch.setattr(server, "_broadcast_events", capture_events)
    monkeypatch.setattr(server, "_prompt_next_actor", noop_prompt)

    server.pending_action = PendingAction(seat=actor, deadline=time.monotonic() + 0.1, timer_task=DummyTask())
    asyncio.run(server._timer_expired(actor, time.monotonic()))

    assert events
    assert events[-1]["ev"] == "CALL"


def test_timer_expired_folds_when_no_stack(monkeypatch):
    server, _, _ = setup_server()
    start_ctx = server.engine.start_hand(seed=80)
    actor = server.engine.next_actor()
    assert actor is not None
    seat = server.engine.seats[actor]
    assert seat is not None
    seat.stack = 0
    seat.committed = 0
    server.engine.hand.current_bet = start_ctx.current_bet + 10

    events: list[dict[str, object]] = []

    async def capture_events(payload):
        events.extend(payload)

    async def noop_prompt():
        return None

    monkeypatch.setattr(server, "_broadcast_events", capture_events)
    monkeypatch.setattr(server, "_prompt_next_actor", noop_prompt)

    server.pending_action = PendingAction(seat=actor, deadline=time.monotonic() + 0.1, timer_task=DummyTask())
    asyncio.run(server._timer_expired(actor, time.monotonic()))

    assert events
    assert any(event["ev"] == "FOLD" for event in events)


def test_maybe_finish_hand_emits_match_end(monkeypatch):
    server, _, _ = setup_server()
    ctx = server.engine.start_hand(seed=90)
    ctx.phase = Phase.SHOWDOWN
    ctx.pot = 0
    server.engine.seats[1].stack = 0  # type: ignore[assignment]

    messages: list[tuple[str, dict[str, object]]] = []

    async def capture_broadcast(msg_type, payload, **kwargs):
        messages.append((msg_type, payload))

    monkeypatch.setattr(server, "_broadcast", capture_broadcast)

    asyncio.run(server._maybe_finish_hand())

    types = [msg for msg, _ in messages]
    assert "end_hand" in types
    assert "match_end" in types
    assert server.engine.hand is None


def test_schedule_timer_disabled_when_move_time_zero():
    server, _, _ = setup_server(move_time_ms=0)
    ctx = server.engine.start_hand(seed=42)
    actor = server.engine.next_actor()
    assert actor is not None

    asyncio.run(server._schedule_timer(actor))

    assert server.pending_action is None


def test_skip_request_applies_fallback(monkeypatch):
    server, _, _ = setup_server(move_time_ms=0)
    server.engine.start_hand(seed=77)

    events: list[dict[str, object]] = []
    messages: list[tuple[str, dict[str, object]]] = []

    async def capture_events(payload):
        events.extend(payload)

    async def capture_broadcast(msg_type, payload, **kwargs):
        messages.append((msg_type, payload))

    monkeypatch.setattr(server, "_broadcast_events", capture_events)
    monkeypatch.setattr(server, "_broadcast", capture_broadcast)

    asyncio.run(server._handle_skip_request())

    assert events, "Expected fallback events after skip"
    assert any(msg for msg in messages if msg[0] == "admin")
