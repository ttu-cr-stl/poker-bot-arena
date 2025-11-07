import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { EventTicker } from "./components/EventTicker";
import { PlaybackControls } from "./components/PlaybackControls";
import { SeatPanel } from "./components/SeatPanel";
import { Card } from "./components/Card";
import { useSpectatorStore } from "./hooks/useSpectatorStore";
import { HandTimeline } from "./components/HandTimeline";
import { formatMoney } from "./utils/cards";
import { ControlPanel } from "./components/ControlPanel";
function chunkSeats(items) {
    const midpoint = Math.ceil(items.length / 2);
    return [items.slice(0, midpoint), items.slice(midpoint)];
}
function framePot(frame) {
    if (!frame) {
        return "$0";
    }
    return formatMoney(frame.state.pot);
}
const SPEED_BASE_MULTIPLIER = 1.35;
function useCurrentHand(hands, preferred) {
    return useMemo(() => {
        if (preferred && hands[preferred]) {
            return hands[preferred];
        }
        const allHands = Object.values(hands);
        if (!allHands.length) {
            return undefined;
        }
        return allHands[allHands.length - 1];
    }, [hands, preferred]);
}
function summarizeStatus(status) {
    if (!status) {
        return "Waiting for data";
    }
    if (status.in_hand) {
        return "Hand in progress";
    }
    if (status.awaiting_manual_start) {
        return "Waiting for operator";
    }
    if (status.manual_start_armed) {
        return "Next hand queued";
    }
    if (!status.can_start) {
        return "Waiting for players";
    }
    return "Ready";
}
export default function App() {
    const { state, connection, selectHand, canControl, requestNextHand, setConfig, sendControl } = useSpectatorStore();
    const currentHand = useCurrentHand(state.hands, state.currentHandId);
    const frames = currentHand?.frames ?? [];
    const [playhead, setPlayhead] = useState(() => (frames.length ? frames.length - 1 : 0));
    const [playbackTarget, setPlaybackTarget] = useState(() => (frames.length ? frames.length - 1 : 0));
    const [isPlaying, setIsPlaying] = useState(true);
    const [followLive, setFollowLive] = useState(true);
    const [speed, setSpeed] = useState(1);
    const [showConfig, setShowConfig] = useState(true);
    const [autoInput, setAutoInput] = useState("5");
    const [autoRemaining, setAutoRemaining] = useState(0);
    const autoTriggerRef = useRef(false);
    const status = state.status;
    const liveHandId = status?.active_hand_id ?? currentHand?.handId;
    const annotatedFrames = useMemo(() => {
        const streetResetEvents = new Set(["FLOP", "TURN", "RIVER"]);
        let history = {};
        let lastPhase;
        return frames.map((frame) => {
            const phase = frame.state.phase;
            const event = frame.event;
            const shouldReset = (typeof phase === "string" && phase !== lastPhase) ||
                (event?.ev && streetResetEvents.has(event.ev));
            if (shouldReset) {
                history = {};
            }
            const nextHistory = { ...history };
            if (event && typeof event.seat === "number") {
                nextHistory[event.seat] = event;
            }
            history = nextHistory;
            if (typeof phase === "string") {
                lastPhase = phase;
            }
            return {
                frame,
                seatActions: nextHistory
            };
        });
    }, [frames]);
    useEffect(() => {
        const target = Math.max(0, frames.length - 1);
        setPlaybackTarget(target);
        setPlayhead((prev) => Math.min(prev, target));
    }, [frames.length]);
    const lastHandIdRef = useRef();
    useEffect(() => {
        const handId = currentHand?.handId;
        if (!handId) {
            lastHandIdRef.current = undefined;
            setPlayhead(0);
            setPlaybackTarget(0);
            setIsPlaying(false);
            setFollowLive(true);
            return;
        }
        if (lastHandIdRef.current !== handId) {
            lastHandIdRef.current = handId;
            const target = Math.max(0, frames.length - 1);
            setPlayhead(0);
            setPlaybackTarget(target);
            const shouldFollow = handId === liveHandId;
            setFollowLive(shouldFollow);
            setIsPlaying(shouldFollow);
        }
    }, [currentHand?.handId, frames.length, liveHandId]);
    useEffect(() => {
        if (!isPlaying || !frames.length) {
            return;
        }
        if (playhead >= playbackTarget) {
            if (!followLive) {
                setIsPlaying(false);
            }
            return;
        }
        const intervalDuration = Math.max(200, 1000 / (speed * SPEED_BASE_MULTIPLIER));
        const interval = window.setInterval(() => {
            setPlayhead((prev) => {
                if (prev >= playbackTarget) {
                    if (!followLive) {
                        setIsPlaying(false);
                    }
                    return prev;
                }
                return prev + 1;
            });
        }, intervalDuration);
        return () => window.clearInterval(interval);
    }, [isPlaying, frames.length, playhead, playbackTarget, followLive, speed]);
    const goTo = useCallback((index, userInitiated = false) => {
        if (!frames.length) {
            return;
        }
        const clamped = Math.max(0, Math.min(index, playbackTarget));
        setPlayhead(clamped);
        if (userInitiated) {
            setFollowLive(clamped >= playbackTarget);
        }
    }, [frames.length, playbackTarget]);
    const handleStepBackward = () => {
        goTo(playhead - 1, true);
    };
    const handleStepForward = () => {
        goTo(playhead + 1, true);
    };
    const handlePlay = () => {
        if (!frames.length) {
            return;
        }
        setFollowLive(playhead >= playbackTarget);
        setIsPlaying(true);
    };
    const handlePause = () => {
        setIsPlaying(false);
    };
    const handleJumpLive = () => {
        if (!frames.length) {
            return;
        }
        setFollowLive(true);
        setIsPlaying(true);
        goTo(playbackTarget);
    };
    const currentFrameEntry = annotatedFrames.length
        ? annotatedFrames[Math.max(0, Math.min(playhead, annotatedFrames.length - 1))]
        : undefined;
    const frame = currentFrameEntry?.frame;
    const seatActions = currentFrameEntry?.seatActions ?? {};
    const communityCards = frame?.state.community ?? [];
    const lobbyMap = useMemo(() => {
        const bySeat = {};
        state.lobby.forEach((entry) => {
            bySeat[entry.seat] = {
                seat: entry.seat,
                team: entry.team,
                stack: entry.stack,
                connected: entry.connected,
                hole: [],
                committed: 0,
                has_folded: false
            };
        });
        return bySeat;
    }, [state.lobby]);
    const seatCount = useMemo(() => {
        if (status?.total_seats) {
            return status.total_seats;
        }
        if (frame) {
            return frame.state.seats.length;
        }
        return state.lobby.length;
    }, [status?.total_seats, frame, state.lobby.length]);
    const seatsForDisplay = useMemo(() => {
        if (seatCount === 0) {
            return [];
        }
        const list = [];
        const liveSeatMap = {};
        frame?.state.seats.forEach((seat) => {
            liveSeatMap[seat.seat] = seat;
        });
        for (let index = 0; index < seatCount; index++) {
            const liveSeat = liveSeatMap[index];
            if (liveSeat) {
                list.push({
                    ...liveSeat,
                    connected: lobbyMap[index]?.connected ?? true,
                    placeholder: false
                });
                continue;
            }
            if (lobbyMap[index]) {
                list.push({
                    ...lobbyMap[index],
                    placeholder: false
                });
                continue;
            }
            list.push({
                seat: index,
                team: `Seat ${index + 1}`,
                stack: 0,
                hole: [],
                committed: 0,
                has_folded: true,
                connected: false,
                placeholder: true
            });
        }
        return list;
    }, [frame, lobbyMap, seatCount]);
    const [topSeats, bottomSeats] = chunkSeats(seatsForDisplay);
    const connectionLabel = connection === "open"
        ? "Connected"
        : connection === "connecting"
            ? "Connecting…"
            : connection === "error"
                ? "Connection error"
                : connection === "closed"
                    ? "Disconnected"
                    : "Waiting";
    const connectionError = connection === "error" || (connection === "closed" && !frames.length && !state.status);
    const phaseText = frame?.state.phase ?? "—";
    const activeSeat = frame?.state.next_actor ?? null;
    const hasFrames = frames.length > 0;
    const atLatestFrame = hasFrames ? playhead >= playbackTarget : false;
    const tickerEvents = useMemo(() => {
        if (!annotatedFrames.length) {
            return [];
        }
        const clampedIndex = Math.max(0, Math.min(playhead, annotatedFrames.length - 1));
        const sliceStart = Math.max(0, clampedIndex - 5);
        return annotatedFrames
            .slice(sliceStart, clampedIndex + 1)
            .map((entry) => entry.frame)
            .filter((entry) => entry.event)
            .map((entry) => ({
            event: entry.event,
            seats: entry.state.seats,
            board: entry.state.community,
            ts: entry.ts
        }))
            .reverse();
    }, [annotatedFrames, playhead]);
    const autoPlayActive = autoRemaining > 0;
    const statusText = summarizeStatus(status);
    const playersReady = status ? `${status.players_ready ?? 0}/${status.total_seats ?? "—"}` : "—";
    const allHands = useMemo(() => Object.values(state.hands), [state.hands]);
    const canAutoStart = canControl &&
        status?.hand_control === "operator" &&
        !status?.in_hand &&
        status?.can_start &&
        !status?.manual_start_armed;
    const canSeatActions = Boolean(canControl && status?.hand_control === "operator" && !autoPlayActive);
    useEffect(() => {
        if (!canControl || status?.hand_control !== "operator") {
            setAutoRemaining(0);
            return;
        }
        if (autoRemaining > 0 && canAutoStart && !autoTriggerRef.current) {
            autoTriggerRef.current = true;
            requestNextHand();
        }
        if (autoTriggerRef.current && status?.in_hand) {
            autoTriggerRef.current = false;
            setAutoRemaining((prev) => (prev > 0 ? prev - 1 : 0));
        }
    }, [autoRemaining, canAutoStart, status?.in_hand, canControl, status?.hand_control, requestNextHand]);
    useEffect(() => {
        if (!autoPlayActive) {
            return;
        }
        setIsPlaying(false);
        setFollowLive(true);
        setPlayhead(playbackTarget);
    }, [autoPlayActive, playbackTarget]);
    const handleAutoStart = () => {
        const parsed = Math.max(1, Number.parseInt(autoInput, 10) || 0);
        setAutoRemaining(parsed);
    };
    const handleAutoStop = () => {
        setAutoRemaining(0);
        autoTriggerRef.current = false;
    };
    const canStartNextHand = Boolean(canControl &&
        status?.hand_control === "operator" &&
        !status?.in_hand &&
        status?.can_start &&
        !status?.manual_start_armed);
    const controlButtonLabel = status?.manual_start_armed ? "Waiting for players" : "Start next hand";
    return (_jsxs("div", { className: "app", children: [_jsxs("div", { className: "app__sidebar", children: [showConfig && _jsx(ControlPanel, { state: state, connection: connection, onConfigChange: setConfig }), _jsx(HandTimeline, { hands: allHands, currentHandId: currentHand?.handId, liveHandId: liveHandId ?? undefined, onSelect: (handId) => {
                            selectHand(handId);
                            const shouldFollow = handId === liveHandId;
                            setFollowLive(shouldFollow);
                            setIsPlaying(shouldFollow);
                        } })] }), _jsxs("div", { className: `app__main ${showConfig ? "" : "app__main--full"}`, children: [_jsxs("header", { className: "app__header", children: [_jsxs("div", { children: [_jsx("h1", { className: "app__title", children: "Poker Bot Arena" }), _jsx("p", { className: "app__subtitle", children: "Architect\u2019s-eye view of the bot wars." })] }), _jsxs("div", { className: "app__header-buttons", children: [_jsx("button", { className: "config-toggle", type: "button", onClick: () => setShowConfig((prev) => !prev), children: showConfig ? "Hide config" : "Show config" }), _jsx("div", { className: `connection connection--${connection}`, children: connectionLabel })] })] }), connectionError && (_jsx("div", { className: "banner banner--error", children: "Unable to reach the tournament host at the configured WebSocket URL. Double-check the `ws=` parameter or start the server, then refresh." })), _jsxs("section", { className: "status-panel", children: [_jsxs("div", { className: "status-panel__info", children: [_jsx("span", { className: "status-panel__label", children: "State" }), _jsx("span", { className: "status-panel__value", children: statusText })] }), _jsxs("div", { className: "status-panel__info", children: [_jsx("span", { className: "status-panel__label", children: "Players Ready" }), _jsx("span", { className: "status-panel__value", children: playersReady })] }), canControl && status?.hand_control === "operator" && (_jsxs("div", { className: "status-panel__actions", children: [_jsxs("div", { className: "auto-controls", children: [_jsxs("label", { className: "auto-controls__label", children: ["Autoplay", _jsx("input", { type: "number", min: 1, value: autoInput, onChange: (event) => setAutoInput(event.target.value), disabled: autoPlayActive })] }), autoRemaining > 0 && _jsxs("span", { className: "auto-controls__remaining", children: [autoRemaining, " left"] }), _jsx("button", { className: "auto-controls__start", type: "button", onClick: handleAutoStart, disabled: autoPlayActive, children: "Start" }), _jsx("button", { className: "auto-controls__stop", type: "button", onClick: handleAutoStop, disabled: !autoPlayActive, children: "Stop" })] }), _jsx("button", { className: "status-panel__button", onClick: requestNextHand, disabled: !canStartNextHand || autoPlayActive, type: "button", children: controlButtonLabel })] }))] }), _jsxs("section", { className: "hand-meta", children: [_jsxs("div", { className: "hand-meta__item", children: [_jsx("span", { className: "hand-meta__label", children: "Pot" }), _jsx("span", { className: "hand-meta__value", children: framePot(frame) })] }), _jsxs("div", { className: "hand-meta__item", children: [_jsx("span", { className: "hand-meta__label", children: "Phase" }), _jsx("span", { className: "hand-meta__value", children: phaseText })] }), _jsxs("div", { className: "hand-meta__item", children: [_jsx("span", { className: "hand-meta__label", children: "Hand" }), _jsx("span", { className: "hand-meta__value", children: currentHand?.handId ?? "—" })] })] }), state.lobby.length === 0 && !frame ? (_jsx("div", { className: "empty-table", children: _jsx("p", { children: "No teams have connected yet. Seats will appear here as soon as bots claim them." }) })) : (_jsxs("main", { className: "table", children: [_jsxs("div", { className: "table__community", children: [_jsx("div", { className: "table__pot", children: framePot(frame) }), _jsx("div", { className: "table__cards", children: [0, 1, 2, 3, 4].map((index) => (_jsx(Card, { card: communityCards[index] }, index))) })] }), _jsx(EventTicker, { events: tickerEvents }), _jsx("div", { className: "table__row table__row--top", children: topSeats.map((seat) => {
                                    const seatId = seat.seat;
                                    const canForfeitSeat = Boolean(canSeatActions && !seat.placeholder);
                                    const handleSkip = () => {
                                        if (window.confirm(`Skip ${seat.team}?`)) {
                                            sendControl("SKIP_ACTION");
                                        }
                                    };
                                    const handleForfeit = () => {
                                        if (window.confirm(`Forfeit ${seat.team}'s seat?`)) {
                                            sendControl("FORFEIT_SEAT", { seat: seatId });
                                        }
                                    };
                                    return (_jsx(SeatPanel, { seat: seat, isActive: frame ? seatId === activeSeat : false, highlight: frame ? Boolean(frame?.state.next_actor === seatId) : false, lastAction: seatActions[seatId], canSkip: Boolean(frame && canSeatActions && seatId === activeSeat), canForfeit: canForfeitSeat, onSkip: handleSkip, onForfeit: handleForfeit }, seatId));
                                }) }), _jsx("div", { className: "table__row table__row--bottom", children: bottomSeats.map((seat) => {
                                    const seatId = seat.seat;
                                    const canForfeitSeat = Boolean(canSeatActions && !seat.placeholder);
                                    const handleSkip = () => {
                                        if (window.confirm(`Skip ${seat.team}?`)) {
                                            sendControl("SKIP_ACTION");
                                        }
                                    };
                                    const handleForfeit = () => {
                                        if (window.confirm(`Forfeit ${seat.team}'s seat?`)) {
                                            sendControl("FORFEIT_SEAT", { seat: seatId });
                                        }
                                    };
                                    return (_jsx(SeatPanel, { seat: seat, isActive: frame ? seatId === activeSeat : false, highlight: frame ? Boolean(frame?.state.next_actor === seatId) : false, lastAction: seatActions[seatId], canSkip: Boolean(frame && canSeatActions && seatId === activeSeat), canForfeit: canForfeitSeat, onSkip: handleSkip, onForfeit: handleForfeit }, seatId));
                                }) })] })), _jsx(PlaybackControls, { isPlaying: isPlaying, canStepBackward: hasFrames && playhead > 0, canStepForward: hasFrames && playhead < playbackTarget, onPlay: handlePlay, onPause: handlePause, onStepBackward: handleStepBackward, onStepForward: handleStepForward, onSpeedChange: setSpeed, speed: speed, isLive: atLatestFrame && followLive, onJumpToLive: handleJumpLive })] })] }));
}
