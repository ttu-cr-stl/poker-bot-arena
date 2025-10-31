from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from core.game import GameEngine
from core.models import ActionType, TableConfig

LOGGER = logging.getLogger("poker_host")

# HostServer glues the poker engine to WebSocket clients (bots).
# Every network concern lives here; the GameEngine stays pure.


@dataclass
class ClientSession:
    seat: int
    team: str
    websocket: WebSocketServerProtocol
    join_code: str


@dataclass
class PendingAction:
    seat: int
    deadline: float
    timer_task: asyncio.Task


class HostServer:
    def __init__(
        self,
        config: TableConfig,
    ) -> None:
        # GameEngine handles cards; this class handles sockets and pacing.
        self.engine = GameEngine(config)
        self.sessions: Dict[int, ClientSession] = {}
        self.pending_action: Optional[PendingAction] = None
        self.lock = asyncio.Lock()

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        # websockets.serve keeps accepting clients until the process stops.
        async with websockets.serve(self._handle_connection, host, port):
            LOGGER.info("Host server listening on %s:%s", host, port)
            await asyncio.Future()

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        # First message must be "hello" so we know who we are talking to.
        hello = await self._read_message(websocket)
        if hello is None or hello.get("type") != "hello":
            await self._send_error(websocket, code="BAD_HELLO", msg="Expected hello")
            await websocket.close()
            return

        team = hello.get("team")
        join_code = hello.get("join_code")
        if not isinstance(team, str) or not isinstance(join_code, str):
            await self._send_error(websocket, code="BAD_SCHEMA", msg="team/join_code required")
            await websocket.close()
            return

        try:
            async with self.lock:
                seat = self.engine.assign_seat(team, join_code)
        except ValueError as exc:
            code = str(exc)
            await self._send_error(websocket, code=code, msg="Seat claim rejected")
            await websocket.close()
            return
        except RuntimeError:
            await self._send_error(websocket, code="TABLE_FULL", msg="No seats available")
            await websocket.close()
            return

        # Replace existing connection if any.
        previous = self.sessions.get(seat.seat)
        if previous:
            await previous.websocket.close(code=4000, reason="Replaced by new connection")

        session = ClientSession(seat=seat.seat, team=team, websocket=websocket, join_code=join_code)
        self.sessions[seat.seat] = session
        async with self.lock:
            self.engine.set_connected(seat.seat, True)
        LOGGER.info(
            "Seat %s claimed by %s (stack=%s)",
            seat.seat,
            team,
            seat.stack,
        )

        await self._send_json(websocket, "welcome", {
            "table_id": "T-1",
            "seat": seat.seat,
            "config": {
                "variant": self.engine.config.variant,
                "seats": self.engine.config.seats,
                "starting_stack": self.engine.config.starting_stack,
                "sb": self.engine.config.sb,
                "bb": self.engine.config.bb,
                "move_time_ms": self.engine.config.move_time_ms,
            },
        })

        await self._broadcast("lobby", self.engine.lobby_state())

        snapshot_payload: Optional[Dict[str, object]] = None
        start_needed = False
        async with self.lock:
            if self.engine.hand:
                snapshot_payload = self.engine.snapshot_payload(seat.seat, self._time_remaining_ms())
            elif self.engine.can_start_hand():
                start_needed = True

        if snapshot_payload:
            await self._send_json(websocket, "snapshot", snapshot_payload)
        if start_needed:
            await self._maybe_start_hand()

        try:
            async for raw in websocket:
                message = self._decode(raw)
                if message.get("type") == "action":
                    await self._handle_action(session, message)
                else:
                    await self._send_error(websocket, code="UNKNOWN_TYPE", msg="Unsupported message type")
        except websockets.ConnectionClosed:
            pass
        finally:
            async with self.lock:
                self.engine.set_connected(seat.seat, False)
        self.sessions.pop(seat.seat, None)
        LOGGER.info("Seat %s (%s) disconnected", seat.seat, team)
        await self._broadcast("lobby", self.engine.lobby_state())

    async def _maybe_start_hand(self) -> None:
        async with self.lock:
            if self.engine.hand or not self.engine.can_start_hand():
                return
            ctx = self.engine.start_hand()
            start_payload = self.engine.start_hand_payload(ctx)
            pre_events = self.engine.consume_pre_events()

        await self._broadcast("start_hand", start_payload)
        for event in pre_events:
            await self._broadcast("event", event)
        await self._prompt_next_actor()

    async def _prompt_next_actor(self) -> None:
        hand_ready_to_finish = False
        async with self.lock:
            next_seat = self.engine.next_actor()
            if next_seat is None:
                hand_ready_to_finish = self.engine.is_hand_complete()
            else:
                payload = self.engine.act_payload(next_seat)

        if next_seat is None:
            if hand_ready_to_finish:
                await self._maybe_finish_hand()
            return

        session = self.sessions.get(next_seat)
        if not session:
            return
        if self.engine.hand and self.engine.hand.phase == self.engine.hand.phase.SHOWDOWN:
            await self._maybe_finish_hand()
            return
        await self._send_json(session.websocket, "act", payload)
        await self._schedule_timer(next_seat)

    async def _handle_action(self, session: ClientSession, message: Dict[str, object]) -> None:
        hand_id = message.get("hand_id")
        action_name = message.get("action")
        amount = message.get("amount")

        async with self.lock:
            if not self.engine.hand or hand_id != self.engine.hand.hand_id:
                await self._send_error(session.websocket, code="ACTION_TOO_LATE", msg="Hand no longer active")
                return
            if not self.pending_action or self.pending_action.seat != session.seat:
                await self._send_error(session.websocket, code="OUT_OF_TURN", msg="Not your turn")
                return

            try:
                action = ActionType(action_name)
            except Exception:
                await self._send_error(session.websocket, code="INVALID_ACTION", msg="Unknown action")
                return

            if action == ActionType.RAISE_TO and not isinstance(amount, int):
                await self._send_error(session.websocket, code="BAD_SCHEMA", msg="amount required for raise")
                return

            if self.pending_action:
                self.pending_action.timer_task.cancel()
                self.pending_action = None

            try:
                events = self.engine.apply_action(session.seat, action, amount)
            except ValueError as exc:
                LOGGER.warning(
                    "Rejected action seat=%s action=%s amount=%s reason=%s",
                    session.seat,
                    action,
                    amount,
                    exc,
                )
                await self._send_error(session.websocket, code="INVALID_ACTION", msg=str(exc))
                return

        LOGGER.debug(
            "Applied action hand=%s seat=%s action=%s amount=%s",
            self.engine.hand.hand_id if self.engine.hand else None,
            session.seat,
            action,
            amount,
        )

        await self._broadcast_events(events)
        await self._prompt_next_actor()

    async def _maybe_finish_hand(self) -> None:
        if not self.engine.is_hand_complete():
            return
        end_payload = self.engine.end_hand_payload()
        await self._broadcast("end_hand", end_payload)
        LOGGER.info(
            "Hand %s finished; stacks=%s",
            end_payload["hand_id"],
            end_payload["stacks"],
        )

        match_over = self.engine.is_match_over()
        if match_over:
            await self._broadcast("match_end", self.engine.match_result_payload())
            self.engine.hand = None
            LOGGER.info("Match over: %s", self.engine.match_result_payload().get("winner"))
            return

        self.engine.hand = None
        await self._maybe_start_hand()

    async def _schedule_timer(self, seat_idx: int) -> None:
        if self.engine.config.move_time_ms <= 0:
            if self.pending_action:
                self.pending_action.timer_task.cancel()
                self.pending_action = None
            return
        if self.pending_action:
            self.pending_action.timer_task.cancel()
            self.pending_action = None

        deadline = time.monotonic() + (self.engine.config.move_time_ms / 1000)
        task = asyncio.create_task(self._timer_expired(seat_idx, deadline))
        self.pending_action = PendingAction(seat=seat_idx, deadline=deadline, timer_task=task)

    async def _timer_expired(self, seat_idx: int, deadline: float) -> None:
        await asyncio.sleep(max(0, deadline - time.monotonic()))
        async with self.lock:
            if not self.pending_action or self.pending_action.seat != seat_idx:
                return
            events = self._apply_fallback_locked(seat_idx)
            self.pending_action = None
        LOGGER.info("Timer expired; forcing action for seat %s", seat_idx)
        await self._broadcast_events(events)
        await self._prompt_next_actor()

    def _apply_fallback_locked(self, seat_idx: int) -> list[dict[str, object]]:
        action, amount = self._fallback_decision_locked(seat_idx)
        return self.engine.apply_action(seat_idx, action, amount)

    def _fallback_decision_locked(self, seat_idx: int) -> tuple[ActionType, Optional[int]]:
        legal, call_amount, _, _ = self.engine.legal_actions(seat_idx)
        # Matches the documented timeout preference: check > call > fold.
        if ActionType.CHECK in legal:
            return ActionType.CHECK, None
        if ActionType.CALL in legal:
            return ActionType.CALL, None
        return ActionType.FOLD, None

    async def _broadcast(
        self,
        msg_type: str,
        payload: Dict[str, object],
    ) -> None:
        async with self.lock:
            targets = [session.websocket for session in self.sessions.values()]
        if not targets:
            return
        message = self._envelope(msg_type, payload)
        await asyncio.gather(*(socket.send(message) for socket in targets), return_exceptions=True)

    async def _broadcast_events(self, events):
        for event in events:
            await self._broadcast("event", event)

    async def _handle_skip_request(self) -> None:
        async with self.lock:
            if not self.engine.hand:
                return
            seat_idx = self.engine.next_actor()
            if seat_idx is None:
                return
            if self.pending_action and self.pending_action.seat == seat_idx:
                self.pending_action.timer_task.cancel()
                self.pending_action = None
            events = self._apply_fallback_locked(seat_idx)
        LOGGER.info("Manual skip applied to seat %s", seat_idx)
        await self._broadcast("admin", {"event": "SKIP", "seat": seat_idx})
        await self._broadcast_events(events)
        await self._prompt_next_actor()

    async def _send_json(self, websocket: WebSocketServerProtocol, msg_type: str, payload: Dict[str, object]) -> None:
        try:
            await websocket.send(self._envelope(msg_type, payload))
        except websockets.ConnectionClosed:
            pass

    async def _send_error(self, websocket: WebSocketServerProtocol, code: str, msg: str) -> None:
        await self._send_json(websocket, "error", {"code": code, "msg": msg})

    def _envelope(self, msg_type: str, payload: Dict[str, object]) -> str:
        body = {"type": msg_type, "v": 1, "ts": datetime.now(timezone.utc).isoformat()}
        body.update(payload)
        return json.dumps(body)

    async def _read_message(self, websocket: WebSocketServerProtocol) -> Optional[Dict[str, object]]:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=5)
            return self._decode(raw)
        except Exception:
            return None

    def _decode(self, raw: str) -> Dict[str, object]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _time_remaining_ms(self) -> int:
        if not self.pending_action:
            return self.engine.config.move_time_ms
        remaining = int(max(0, self.pending_action.deadline - time.monotonic()) * 1000)
        return remaining
