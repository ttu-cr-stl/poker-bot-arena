export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";
export interface SpectatorSeatState {
    seat: number;
    team: string;
    stack: number;
    committed?: number;
    hole: string[];
    has_folded?: boolean;
    connected?: boolean;
    is_button?: boolean;
}
export interface SpectatorFrameState {
    hand_id: string;
    table_id?: string;
    pot: number;
    phase: string;
    community: string[];
    seats: SpectatorSeatState[];
    next_actor?: number | null;
    time_remaining_ms?: number | null;
    sb?: number;
    bb?: number;
}
export interface SpectatorEvent {
    id?: string;
    ev: string;
    seat?: number;
    amount?: number;
    cards?: string[];
    rank?: string;
    description?: string;
}
export interface SpectatorFrame {
    ts?: string;
    state: SpectatorFrameState;
    event?: SpectatorEvent;
    label?: string;
}
export interface SpectatorHandTimeline {
    handId: string;
    frames: SpectatorFrame[];
    results?: {
        seat: number;
        stack: number;
        amount?: number;
        rank?: string;
    }[];
    closed?: boolean;
}
export interface SpectatorLobbySeat {
    seat: number;
    team: string;
    stack: number;
    connected: boolean;
}
export interface SpectatorLobbyMessage {
    type: "spectator/lobby";
    seats: SpectatorLobbySeat[];
    ts?: string;
}
export interface SpectatorStartHandMessage {
    type: "spectator/start_hand";
    state: SpectatorFrameState;
    ts?: string;
}
export interface SpectatorEventMessage {
    type: "spectator/event";
    hand_id: string;
    state: SpectatorFrameState;
    event: SpectatorEvent;
    ts?: string;
}
export interface SpectatorEndHandMessage {
    type: "spectator/end_hand";
    hand_id: string;
    state: SpectatorFrameState;
    results: SpectatorHandTimeline["results"];
    ts?: string;
}
export interface SpectatorSnapshotMessage {
    type: "spectator/snapshot";
    hand_id: string;
    frames: SpectatorFrame[];
    results?: SpectatorHandTimeline["results"];
    ts?: string;
}
export interface SpectatorStatusMessage {
    type: "spectator/status";
    table_id?: string;
    hand_control: "auto" | "operator" | string;
    awaiting_manual_start?: boolean;
    manual_start_armed?: boolean;
    in_hand?: boolean;
    active_hand_id?: string | null;
    players_ready?: number;
    can_start?: boolean;
    total_seats?: number;
}
export type SpectatorMessage = SpectatorLobbyMessage | SpectatorStartHandMessage | SpectatorEventMessage | SpectatorEndHandMessage | SpectatorSnapshotMessage | SpectatorStatusMessage;
export interface SpectatorStoreState {
    lobby: SpectatorLobbySeat[];
    hands: Record<string, SpectatorHandTimeline>;
    currentHandId?: string;
    status?: SpectatorStatusMessage;
    meta?: {
        wsUrl: string | null;
    };
}
