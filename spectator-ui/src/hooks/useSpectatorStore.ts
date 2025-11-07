import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type {
  ConnectionStatus,
  SpectatorEndHandMessage,
  SpectatorEventMessage,
  SpectatorFrame,
  SpectatorHandTimeline,
  SpectatorLobbyMessage,
  SpectatorMessage,
  SpectatorSnapshotMessage,
  SpectatorStatusMessage,
  SpectatorStartHandMessage,
  SpectatorStoreState
} from "../types";

type StoreAction =
  | { type: "message"; message: SpectatorMessage }
  | { type: "select_hand"; handId?: string }
  | { type: "reset" }
  | { type: "meta"; meta: SpectatorStoreState["meta"] };

const initialState: SpectatorStoreState = {
  lobby: [],
  hands: {},
  currentHandId: undefined,
  status: undefined,
  meta: undefined
};

function framesEqual(a: SpectatorFrame, b: SpectatorFrame) {
  if (a.event?.id && b.event?.id) {
    return a.event.id === b.event.id;
  }
  if (a.ts && b.ts) {
    return a.ts === b.ts;
  }
  return false;
}

function applyLobby(state: SpectatorStoreState, message: SpectatorLobbyMessage): SpectatorStoreState {
  return {
    ...state,
    lobby: message.seats
  };
}

function applyStart(state: SpectatorStoreState, message: SpectatorStartHandMessage): SpectatorStoreState {
  const handId = message.state.hand_id;
  const frame: SpectatorFrame = {
    ts: message.ts,
    state: message.state,
    label: "Hand start"
  };
  const timeline: SpectatorHandTimeline = {
    handId,
    frames: [frame]
  };
  return {
    ...state,
    hands: {
      ...state.hands,
      [handId]: timeline
    },
    currentHandId: handId
  };
}

function applyEvent(state: SpectatorStoreState, message: SpectatorEventMessage): SpectatorStoreState {
  const handId = message.hand_id;
  const existing = state.hands[handId];
  const frame: SpectatorFrame = {
    ts: message.ts,
    state: message.state,
    event: message.event
  };
  let frames: SpectatorFrame[];
  if (existing) {
    const last = existing.frames.at(-1);
    if (last && framesEqual(last, frame)) {
      frames = existing.frames;
    } else {
      frames = existing.frames.concat(frame);
    }
  } else {
    frames = [frame];
  }
  const updated: SpectatorHandTimeline = {
    handId,
    frames,
    results: existing?.results,
    closed: existing?.closed
  };
  return {
    ...state,
    hands: {
      ...state.hands,
      [handId]: updated
    },
    currentHandId: state.currentHandId ?? handId
  };
}

function applyEnd(state: SpectatorStoreState, message: SpectatorEndHandMessage): SpectatorStoreState {
  const handId = message.hand_id;
  const existing = state.hands[handId];
  let frames = existing?.frames ?? [];
  const frame: SpectatorFrame = {
    ts: message.ts,
    state: message.state,
    label: "Hand complete"
  };
  const last = frames.at(-1);
  if (!last || !framesEqual(last, frame)) {
    frames = frames.concat(frame);
  }
  const updated: SpectatorHandTimeline = {
    handId,
    frames,
    results: message.results ?? existing?.results,
    closed: true
  };
  return {
    ...state,
    hands: {
      ...state.hands,
      [handId]: updated
    },
    currentHandId: state.currentHandId ?? handId
  };
}

function applySnapshot(state: SpectatorStoreState, message: SpectatorSnapshotMessage): SpectatorStoreState {
  const handId = message.hand_id;
  const timeline: SpectatorHandTimeline = {
    handId,
    frames: message.frames,
    results: message.results,
    closed: Boolean(message.results)
  };
  return {
    ...state,
    hands: {
      ...state.hands,
      [handId]: timeline
    },
    currentHandId: state.currentHandId ?? handId
  };
}

function applyStatus(state: SpectatorStoreState, message: SpectatorStatusMessage): SpectatorStoreState {
  return {
    ...state,
    status: message
  };
}

function reducer(state: SpectatorStoreState, action: StoreAction): SpectatorStoreState {
  switch (action.type) {
    case "reset":
      return initialState;
    case "select_hand":
      return {
        ...state,
        currentHandId: action.handId
      };
    case "meta":
      return {
        ...state,
        meta: action.meta
      };
    case "message":
      switch (action.message.type) {
        case "spectator/lobby":
          return applyLobby(state, action.message);
        case "spectator/start_hand":
          return applyStart(state, action.message);
        case "spectator/event":
          return applyEvent(state, action.message);
        case "spectator/end_hand":
          return applyEnd(state, action.message);
        case "spectator/snapshot":
          return applySnapshot(state, action.message);
        case "spectator/status":
          return applyStatus(state, action.message);
        default:
          return state;
      }
    default:
      return state;
  }
}

interface SpectatorStoreOptions {
  demo?: boolean;
  demoIntervalMs?: number;
  control?: boolean;
  wsUrl?: string | null;
}

function parseMessage(data: string): SpectatorMessage | undefined {
  try {
    const raw = JSON.parse(data);
    if (typeof raw?.type === "string" && raw.type.startsWith("spectator/")) {
      return raw as SpectatorMessage;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

const demoMessages: SpectatorMessage[] = [
  {
    type: "spectator/start_hand",
    ts: new Date().toISOString(),
    state: {
      hand_id: "H-DEMO-0001",
      table_id: "T-1",
      pot: 30,
      phase: "PRE_FLOP",
      community: [],
      sb: 10,
      bb: 20,
      seats: [
        { seat: 0, team: "Bot.A", stack: 990, hole: ["Ah", "Kd"], committed: 20, is_button: true },
        { seat: 1, team: "Bot.B", stack: 980, hole: ["7s", "7d"], committed: 10 },
        { seat: 2, team: "Bot.C", stack: 1000, hole: ["Qs", "Jh"], committed: 0 },
        { seat: 3, team: "Bot.D", stack: 1000, hole: ["9c", "9h"], committed: 0 }
      ],
      next_actor: 2,
      time_remaining_ms: 15000
    }
  },
  {
    type: "spectator/event",
    ts: new Date(Date.now() + 2000).toISOString(),
    hand_id: "H-DEMO-0001",
    event: { ev: "CALL", seat: 2, amount: 20, description: "Bot.C calls 20" },
    state: {
      hand_id: "H-DEMO-0001",
      table_id: "T-1",
      pot: 50,
      phase: "PRE_FLOP",
      community: [],
      seats: [
        { seat: 0, team: "Bot.A", stack: 990, hole: ["Ah", "Kd"], committed: 20, is_button: true },
        { seat: 1, team: "Bot.B", stack: 980, hole: ["7s", "7d"], committed: 10 },
        { seat: 2, team: "Bot.C", stack: 980, hole: ["Qs", "Jh"], committed: 20 },
        { seat: 3, team: "Bot.D", stack: 1000, hole: ["9c", "9h"], committed: 0 }
      ],
      next_actor: 3,
      time_remaining_ms: 12000,
      sb: 10,
      bb: 20
    }
  },
  {
    type: "spectator/event",
    ts: new Date(Date.now() + 4000).toISOString(),
    hand_id: "H-DEMO-0001",
    event: { ev: "RAISE", seat: 3, amount: 40, description: "Bot.D raises to 40" },
    state: {
      hand_id: "H-DEMO-0001",
      table_id: "T-1",
      pot: 90,
      phase: "PRE_FLOP",
      community: [],
      seats: [
        { seat: 0, team: "Bot.A", stack: 990, hole: ["Ah", "Kd"], committed: 20, is_button: true },
        { seat: 1, team: "Bot.B", stack: 960, hole: ["7s", "7d"], committed: 40 },
        { seat: 2, team: "Bot.C", stack: 960, hole: ["Qs", "Jh"], committed: 40 },
        { seat: 3, team: "Bot.D", stack: 960, hole: ["9c", "9h"], committed: 40 }
      ],
      next_actor: 0,
      time_remaining_ms: 10000,
      sb: 10,
      bb: 20
    }
  },
  {
    type: "spectator/event",
    ts: new Date(Date.now() + 6000).toISOString(),
    hand_id: "H-DEMO-0001",
    event: { ev: "FLOP", cards: ["As", "Qc", "7h"], description: "Flop revealed" },
    state: {
      hand_id: "H-DEMO-0001",
      table_id: "T-1",
      pot: 120,
      phase: "FLOP",
      community: ["As", "Qc", "7h"],
      seats: [
        { seat: 0, team: "Bot.A", stack: 970, hole: ["Ah", "Kd"], committed: 0, is_button: true },
        { seat: 1, team: "Bot.B", stack: 940, hole: ["7s", "7d"], committed: 0 },
        { seat: 2, team: "Bot.C", stack: 940, hole: ["Qs", "Jh"], committed: 0 },
        { seat: 3, team: "Bot.D", stack: 940, hole: ["9c", "9h"], committed: 0 }
      ],
      next_actor: 1,
      time_remaining_ms: 15000,
      sb: 10,
      bb: 20
    }
  },
  {
    type: "spectator/end_hand",
    ts: new Date(Date.now() + 8000).toISOString(),
    hand_id: "H-DEMO-0001",
    state: {
      hand_id: "H-DEMO-0001",
      table_id: "T-1",
      pot: 0,
      phase: "SHOWDOWN",
      community: ["As", "Qc", "7h", "9s", "2d"],
      seats: [
        { seat: 0, team: "Bot.A", stack: 1040, hole: ["Ah", "Kd"], committed: 0, is_button: true },
        { seat: 1, team: "Bot.B", stack: 920, hole: ["7s", "7d"], committed: 0 },
        { seat: 2, team: "Bot.C", stack: 920, hole: ["Qs", "Jh"], committed: 0 },
        { seat: 3, team: "Bot.D", stack: 920, hole: ["9c", "9h"], committed: 0 }
      ],
      next_actor: null,
      time_remaining_ms: null,
      sb: 10,
      bb: 20
    },
    results: [
      { seat: 0, stack: 1040, amount: 80, rank: "Pair of Aces" },
      { seat: 1, stack: 920, amount: -60 },
      { seat: 2, stack: 920, amount: -40 },
      { seat: 3, stack: 920, amount: -40 }
    ]
  }
];

export interface SpectatorStore {
  state: SpectatorStoreState;
  connection: ConnectionStatus;
  selectHand: (handId?: string) => void;
  canControl: boolean;
  requestNextHand: () => void;
  setConfig: (config: Partial<{ wsUrl: string | null }>) => void;
  sendControl: (command: string, payload?: Record<string, unknown>) => void;
}

function inferDefaultWsUrl(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  if (import.meta.env.VITE_SPECTATOR_WS) {
    return import.meta.env.VITE_SPECTATOR_WS;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.hostname}:8765/spectate`;
}

function parseBooleanParam(value: string | null): boolean | undefined {
  if (value === null) {
    return undefined;
  }
  if (["0", "false", "no", "off"].includes(value.toLowerCase())) {
    return false;
  }
  if (["1", "true", "yes", "on"].includes(value.toLowerCase())) {
    return true;
  }
  return undefined;
}

interface RuntimeConfig {
  ws?: string | null;
}

function readRuntimeConfig(): RuntimeConfig {
  if (typeof window === "undefined") {
    return {};
  }
  const params = new URLSearchParams(window.location.search);
  const config: RuntimeConfig = {};
  const ws = params.get("ws");
  if (ws !== null) {
    config.ws = ws || null;
  }
  return config;
}

export function useSpectatorStore(options: SpectatorStoreOptions = {}): SpectatorStore {
  const [connection, setConnection] = useState<ConnectionStatus>("idle");
  const [state, dispatch] = useReducer(reducer, initialState);
  const timers = useRef<number[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const [overrideConfig, setOverrideConfig] = useState<Partial<{ wsUrl: string | null }>>({});
  const runtimeConfig = useMemo(() => readRuntimeConfig(), []);
  const preferWs = useMemo(() => {
    if (overrideConfig.wsUrl !== undefined) {
      return overrideConfig.wsUrl;
    }
    if (options.wsUrl !== undefined) {
      return options.wsUrl;
    }
    if (runtimeConfig.ws !== undefined) {
      return runtimeConfig.ws;
    }
    return inferDefaultWsUrl();
  }, [overrideConfig.wsUrl, options.wsUrl, runtimeConfig.ws]);
  const defaultDemo = !preferWs;
  const demoMode = defaultDemo;
  useEffect(() => {
    dispatch({
      type: "meta",
      meta: {
        wsUrl: preferWs ?? null,
      },
    });
  }, [preferWs]);
  const controlEnabled = useMemo(() => {
    if (typeof options.control === "boolean") {
      return options.control;
    }
    return true;
  }, [options.control]);
  const wsUrl = demoMode ? null : preferWs;
  useEffect(() => {
    if (demoMode) {
      setConnection("open");
    }
  }, [demoMode]);

  useEffect(() => {
    dispatch({ type: "reset" });
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
    if (demoMode) {
      setConnection("open");
      demoMessages.forEach((message, index) => {
        const timeout = window.setTimeout(() => {
          dispatch({ type: "message", message });
        }, (options.demoIntervalMs ?? 1000) * index);
        timers.current.push(timeout);
      });
      return () => {
        timers.current.forEach((id) => window.clearTimeout(id));
        timers.current = [];
      };
    }
    if (!wsUrl) {
      return;
    }
    setConnection("connecting");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnection("open");
      const hello: Record<string, unknown> = {
        type: "hello",
        role: controlEnabled ? "operator" : "spectator",
      };
      if (controlEnabled) {
        hello["control"] = true;
      }
      ws.send(JSON.stringify(hello));
    };
    ws.onclose = () => {
      setConnection("closed");
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
    ws.onerror = () => {
      setConnection("error");
    };
    ws.onmessage = (event) => {
      const message = parseMessage(event.data);
      if (message) {
        dispatch({ type: "message", message });
      }
    };

    return () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [wsUrl, demoMode, options.demoIntervalMs, controlEnabled]);

  const selectHand = (handId?: string) => {
    dispatch({ type: "select_hand", handId });
  };

  const sendControl = useCallback(
    (command: string, payload: Record<string, unknown> = {}) => {
      if (!controlEnabled) {
        return;
      }
      const socket = wsRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "control", command, ...payload }));
      }
    },
    [controlEnabled]
  );

  const requestNextHand = useCallback(() => {
    sendControl("START_HAND");
  }, [sendControl]);

  const setConfig = (config: Partial<{ wsUrl: string | null }>) => {
    setOverrideConfig((prev) => ({ ...prev, ...config }));
  };

  return {
    state,
    connection,
    selectHand,
    canControl: controlEnabled,
    requestNextHand,
    setConfig,
    sendControl
  };
}
