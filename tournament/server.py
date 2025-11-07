from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

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


@dataclass
class PendingAction:
    seat: int
    deadline: float
    timer_task: Optional[asyncio.Task] = None


@dataclass
class SpectatorHandRecord:
    hand_id: str
    opening_stacks: Dict[int, int]
    frames: List[Dict[str, object]] = field(default_factory=list)
    results: Optional[List[Dict[str, object]]] = None
    next_event_id: int = 0


class HostServer:
    def __init__(
        self,
        config: TableConfig,
        hand_control: str = "auto",
    ) -> None:
        # GameEngine handles cards; this class handles sockets and pacing.
        self.engine = GameEngine(config)
        self.table_id = "T-1"
        self.sessions: Dict[int, ClientSession] = {}
        self.pending_action: Optional[PendingAction] = None
        self.lock = asyncio.Lock()
        self.hand_control = hand_control
        self.manual_start_armed = False
        self.awaiting_manual_start = hand_control == "operator"
        self.spectators: Set[WebSocketServerProtocol] = set()
        self.spectator_hands: Dict[str, SpectatorHandRecord] = {}
        self.spectator_history: List[str] = []
        self.spectator_history_limit = 20
        self.active_hand_id: Optional[str] = None
        self.latest_hand_id: Optional[str] = None

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
        role_raw = hello.get("role") or "player"
        role = role_raw.strip().casefold() if isinstance(role_raw, str) else "player"
        if role in ("spectator", "operator"):
            can_control = role == "operator" or bool(hello.get("control"))
            await self._handle_spectator_session(websocket, can_control=can_control)
            return
        team_raw = hello.get("team")
        if not isinstance(team_raw, str):
            await self._send_error(websocket, code="BAD_SCHEMA", msg="team required")
            await websocket.close()
            return
        team = team_raw.strip()
        if not team:
            await self._send_error(websocket, code="BAD_SCHEMA", msg="team required")
            await websocket.close()
            return

        try:
            async with self.lock:
                seat = self.engine.assign_seat(team)
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

        session = ClientSession(seat=seat.seat, team=seat.team, websocket=websocket)
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
            "table_id": self.table_id,
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

        await self._publish_lobby()

        snapshot_payload: Optional[Dict[str, object]] = None
        pending_act: Optional[Dict[str, object]] = None
        start_needed = False
        async with self.lock:
            if self.engine.hand:
                snapshot_payload = self.engine.snapshot_payload(seat.seat, self._time_remaining_ms())
                if self.pending_action and self.pending_action.seat == seat.seat:
                    pending_act = self.engine.act_payload(seat.seat)
                    # Update remaining time on reconnect so the bot sees the correct clock.
                    remaining = self._time_remaining_ms()
                    try:
                        pending_act["you"]["time_ms"] = remaining  # type: ignore[index]
                    except Exception:
                        pass
            elif self.engine.can_start_hand():
                start_needed = True

        if snapshot_payload:
            await self._send_json(websocket, "snapshot", snapshot_payload)
        if pending_act:
            await self._send_json(websocket, "act", pending_act)
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
        await self._publish_lobby()

    async def _handle_spectator_session(self, websocket: WebSocketServerProtocol, *, can_control: bool) -> None:
        LOGGER.info("Spectator connected%s", " (control)" if can_control else "")
        async with self.lock:
            self.spectators.add(websocket)
            lobby_payload = self._spectator_lobby_payload_locked()
            snapshot_payload = self._latest_snapshot_locked()
            status_payload = self._spectator_status_locked()
        if lobby_payload is not None:
            await self._send_json(websocket, "spectator/lobby", lobby_payload)
        if snapshot_payload is not None:
            await self._send_json(websocket, "spectator/snapshot", snapshot_payload)
        if status_payload is not None:
            await self._send_json(websocket, "spectator/status", status_payload)
        try:
            async for raw in websocket:
                message = self._decode(raw)
                if not message:
                    continue
                if can_control and message.get("type") == "control":
                    await self._handle_control_command(message, websocket)
                    continue
                LOGGER.warning("Spectator sent unsupported message; closing connection")
                await websocket.close(code=4403, reason="Spectators are read-only")
                break
        except websockets.ConnectionClosed:
            pass
        finally:
            async with self.lock:
                self.spectators.discard(websocket)
            LOGGER.info("Spectator disconnected")

    async def _maybe_start_hand(self) -> None:
        async with self.lock:
            if self.engine.hand or not self.engine.can_start_hand():
                return
            if self._manual_mode() and not self.manual_start_armed:
                return
            ctx = self.engine.start_hand()
            start_payload = self.engine.start_hand_payload(ctx)
            pre_events = self.engine.consume_pre_events()
            opening_stacks = {entry["seat"]: entry["stack"] for entry in start_payload["stacks"]}
            spectator_state = self._start_spectator_hand_locked(opening_stacks)
            if self._manual_mode():
                self.manual_start_armed = False
                self.awaiting_manual_start = False

        await self._broadcast("start_hand", start_payload)
        if spectator_state:
            await self._broadcast_spectator("spectator/start_hand", {"state": spectator_state})
        await self._broadcast_events(pre_events)
        await self._prompt_next_actor()
        await self._publish_status()

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
            LOGGER.info(
                "Seat %s is disconnected; waiting for reconnection or operator input",
                next_seat,
            )
            self._set_pending_action(next_seat)
            await self._publish_status()
            return
        if self.engine.hand and self.engine.hand.phase == self.engine.hand.phase.SHOWDOWN:
            await self._maybe_finish_hand()
            return
        await self._send_json(session.websocket, "act", payload)
        self._set_pending_action(next_seat)

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
                if self.pending_action.timer_task:
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
        await self._publish_spectator_hand_end(end_payload)
        LOGGER.info(
            "Hand %s finished; stacks=%s",
            end_payload["hand_id"],
            end_payload["stacks"],
        )

        match_over = self.engine.is_match_over()
        if match_over:
            await self._broadcast("match_end", self.engine.match_result_payload())
        async with self.lock:
            self.engine.hand = None
            self.active_hand_id = None
            if self._manual_mode():
                if match_over:
                    self.awaiting_manual_start = False
                    self.manual_start_armed = False
                else:
                    self.awaiting_manual_start = True
                    self.manual_start_armed = False
        await self._publish_status()
        if match_over:
            LOGGER.info("Match over: %s", self.engine.match_result_payload().get("winner"))
            return

        await self._maybe_start_hand()

    def _set_pending_action(self, seat_idx: int) -> None:
        self.pending_action = PendingAction(seat=seat_idx, deadline=time.monotonic(), timer_task=None)

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
            await self._publish_spectator_event(event)

    async def _handle_skip_request(self) -> None:
        async with self.lock:
            if not self.engine.hand:
                return
            seat_idx = self.engine.next_actor()
            if seat_idx is None:
                return
            if self.pending_action and self.pending_action.seat == seat_idx:
                self.pending_action = None
            events = self._apply_fallback_locked(seat_idx)
        LOGGER.info("Manual skip applied to seat %s", seat_idx)
        await self._broadcast("admin", {"event": "SKIP", "seat": seat_idx})
        await self._broadcast_events(events)
        await self._prompt_next_actor()

    async def _publish_lobby(self) -> None:
        async with self.lock:
            lobby_state = self.engine.lobby_state()
            spectator_payload = self._format_spectator_lobby(lobby_state)
            status_payload = self._spectator_status_locked()
        await self._broadcast("lobby", lobby_state)
        await self._broadcast_spectator("spectator/lobby", spectator_payload)
        await self._broadcast_spectator("spectator/status", status_payload)

    def _spectator_lobby_payload_locked(self) -> Dict[str, object]:
        return self._format_spectator_lobby(self.engine.lobby_state())

    def _format_spectator_lobby(self, lobby_state: Dict[str, object]) -> Dict[str, object]:
        players = lobby_state.get("players", [])
        seats = [
            {
                "seat": player["seat"],
                "team": player["team"],
                "stack": player["stack"],
                "connected": player["connected"],
            }
            for player in players
        ]
        return {"seats": seats}

    def _manual_mode(self) -> bool:
        return self.hand_control == "operator"

    def _spectator_status_locked(self) -> Dict[str, object]:
        hand = self.engine.hand
        active_hand_id = hand.hand_id if hand else None
        players_ready = len([seat for seat in self.engine.seats if seat and seat.stack > 0])
        return {
            "table_id": self.table_id,
            "hand_control": self.hand_control,
            "awaiting_manual_start": self._manual_mode() and self.awaiting_manual_start,
            "manual_start_armed": self._manual_mode() and self.manual_start_armed,
            "in_hand": bool(hand),
            "active_hand_id": active_hand_id,
            "players_ready": players_ready,
            "can_start": self.engine.can_start_hand(),
            "total_seats": self.engine.config.seats,
        }

    async def _publish_status(self) -> None:
        async with self.lock:
            payload = self._spectator_status_locked()
        await self._broadcast_spectator("spectator/status", payload)

    async def _handle_control_command(self, message: Dict[str, object], websocket: WebSocketServerProtocol) -> None:
        command_raw = message.get("command") or message.get("cmd")
        if not isinstance(command_raw, str):
            await self._send_json(websocket, "control/error", {"error": "COMMAND_REQUIRED"})
            return
        command = command_raw.strip().upper()
        if command == "START_HAND":
            status = await self._command_start_hand()
            await self._send_json(websocket, "control/ack", {"command": command, "status": status})
        elif command == "SKIP_ACTION":
            await self._handle_skip_request()
            await self._send_json(websocket, "control/ack", {"command": command, "status": "applied"})
        elif command == "REQUEST_STATUS":
            await self._publish_status()
            await self._send_json(websocket, "control/ack", {"command": command, "status": "sent"})
        else:
            await self._send_json(websocket, "control/error", {"command": command, "error": "UNKNOWN_COMMAND"})

    async def _command_start_hand(self) -> str:
        async with self.lock:
            if self.engine.hand:
                return "hand_in_progress"
            if self._manual_mode():
                self.manual_start_armed = True
                self.awaiting_manual_start = False
            ready_now = self.engine.can_start_hand()
        await self._publish_status()
        await self._maybe_start_hand()
        async with self.lock:
            if self.engine.hand:
                return "started"
            if not ready_now:
                return "waiting_for_players"
            if self._manual_mode() and self.manual_start_armed:
                return "queued"
        return "pending"

    async def _command_forfeit_seat(self, seat_idx: int) -> str:
        close_session: Optional[ClientSession] = None
        async with self.lock:
            if seat_idx < 0 or seat_idx >= len(self.engine.seats):
                return "invalid_seat"
            player = self.engine.seats[seat_idx]
            if player is None:
                return "seat_empty"
            if self.engine.hand:
                return "hand_in_progress"
            player.stack = 0
            player.connected = False
            player.has_folded = True
            player.hole_cards.clear()
            close_session = self.sessions.pop(seat_idx, None)
        if close_session:
            try:
                await close_session.websocket.close(code=4401, reason="Seat forfeited by operator")
            except Exception:
                pass
        await self._publish_lobby()
        await self._publish_status()
        return "removed"

    def _latest_snapshot_locked(self) -> Optional[Dict[str, object]]:
        if not self.latest_hand_id:
            return None
        record = self.spectator_hands.get(self.latest_hand_id)
        if not record or not record.frames:
            return None
        payload: Dict[str, object] = {
            "hand_id": record.hand_id,
            "frames": list(record.frames),
        }
        if record.results:
            payload["results"] = record.results
        return payload

    async def _broadcast_spectator(self, msg_type: str, payload: Dict[str, object]) -> None:
        async with self.lock:
            targets = list(self.spectators)
        if not targets:
            return
        message = self._envelope(msg_type, payload)
        await asyncio.gather(*(socket.send(message) for socket in targets), return_exceptions=True)

    def _start_spectator_hand_locked(self, opening_stacks: Dict[int, int]) -> Optional[Dict[str, object]]:
        state = self._spectator_state_locked()
        if not state:
            return None
        hand_id = state["hand_id"]
        record = SpectatorHandRecord(hand_id=hand_id, opening_stacks=dict(opening_stacks))
        self.spectator_hands[hand_id] = record
        self.spectator_history.append(hand_id)
        self.active_hand_id = hand_id
        self.latest_hand_id = hand_id
        self._trim_spectator_history_locked()
        self._append_spectator_frame_locked(record, state, label="Hand start")
        return state

    def _spectator_state_locked(self) -> Optional[Dict[str, object]]:
        return self.engine.spectator_state(self.table_id, self._time_remaining_ms())

    def _append_spectator_frame_locked(
        self,
        record: SpectatorHandRecord,
        state: Dict[str, object],
        *,
        event: Optional[Dict[str, object]] = None,
        label: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        ts = self._now_ts()
        frame: Dict[str, object] = {"ts": ts, "state": state}
        event_payload: Optional[Dict[str, object]] = None
        if event is not None:
            event_payload = dict(event)
            if "id" not in event_payload:
                event_payload["id"] = f"{record.hand_id}:{record.next_event_id}"
            record.next_event_id += 1
            frame["event"] = event_payload
        if label:
            frame["label"] = label
        record.frames.append(frame)
        return event_payload

    def _trim_spectator_history_locked(self) -> None:
        while len(self.spectator_history) > self.spectator_history_limit:
            old_id = self.spectator_history.pop(0)
            if old_id == self.active_hand_id or old_id == self.latest_hand_id:
                self.spectator_history.insert(0, old_id)
                break
            self.spectator_hands.pop(old_id, None)

    def _active_record_locked(self) -> Optional[SpectatorHandRecord]:
        if not self.active_hand_id:
            return None
        return self.spectator_hands.get(self.active_hand_id)

    async def _publish_spectator_event(self, event: Dict[str, object]) -> None:
        async with self.lock:
            record = self._active_record_locked()
            if not record:
                return
            state = self._spectator_state_locked()
            if not state:
                return
            event_payload = self._append_spectator_frame_locked(record, state, event=event)
            hand_id = record.hand_id
        if not event_payload:
            return
        await self._broadcast_spectator(
            "spectator/event",
            {"hand_id": hand_id, "event": event_payload, "state": state},
        )

    async def _publish_spectator_hand_end(self, end_payload: Dict[str, object]) -> None:
        async with self.lock:
            record = self._active_record_locked()
            state = self._spectator_state_locked() if self.engine.hand else None
            if record and state:
                self._append_spectator_frame_locked(record, state, label="Hand complete")
            elif not state:
                state = self._fallback_state_from_payload_locked(end_payload)
            results = None
            if record:
                results = self._build_results_locked(record, end_payload)
                record.results = results
            hand_id = end_payload["hand_id"]
        payload: Dict[str, object] = {
            "hand_id": hand_id,
            "state": state,
            "results": results or [],
        }
        await self._broadcast_spectator("spectator/end_hand", payload)

    def _build_results_locked(
        self,
        record: SpectatorHandRecord,
        end_payload: Dict[str, object],
    ) -> List[Dict[str, object]]:
        final_lookup = {entry["seat"]: entry["stack"] for entry in end_payload.get("stacks", [])}
        results: List[Dict[str, object]] = []
        for seat, stack in final_lookup.items():
            opening = record.opening_stacks.get(seat)
            result = {"seat": seat, "stack": stack}
            if opening is not None:
                result["amount"] = stack - opening
            results.append(result)
        self._attach_showdown_ranks(record, results)
        return sorted(results, key=lambda item: item["seat"])

    def _attach_showdown_ranks(self, record: SpectatorHandRecord, results: List[Dict[str, object]]) -> None:
        rank_lookup: Dict[int, str] = {}
        for frame in record.frames:
            event = frame.get("event")
            if not event:
                continue
            if event.get("ev") == "SHOWDOWN" and "seat" in event and "rank" in event:
                rank_lookup[event["seat"]] = event["rank"]
        for result in results:
            seat = result["seat"]
            if seat in rank_lookup:
                result["rank"] = rank_lookup[seat]

    def _fallback_state_from_payload_locked(self, end_payload: Dict[str, object]) -> Dict[str, object]:
        ctx = self.engine.hand
        seats: List[Dict[str, object]] = []
        for entry in end_payload.get("stacks", []):
            idx = entry["seat"]
            seat = self.engine.seats[idx]
            seats.append(
                {
                    "seat": idx,
                    "team": seat.team if seat else f"Seat {idx}",
                    "stack": entry["stack"],
                    "committed": seat.committed if seat else 0,
                    "hole": list(seat.hole_cards) if seat else [],
                    "has_folded": seat.has_folded if seat else False,
                    "connected": seat.connected if seat else False,
                    "is_button": ctx.button == idx if ctx else False,
                }
            )
        community = [card.label for card in ctx.community] if ctx else []
        return {
            "hand_id": end_payload["hand_id"],
            "table_id": self.table_id,
            "pot": 0,
            "phase": "SHOWDOWN",
            "community": community,
            "seats": seats,
            "next_actor": None,
            "time_remaining_ms": None,
            "sb": self.engine.config.sb,
            "bb": self.engine.config.bb,
        }

    def _now_ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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
        return self.engine.config.move_time_ms
