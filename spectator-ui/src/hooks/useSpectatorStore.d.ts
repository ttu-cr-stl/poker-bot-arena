import type { ConnectionStatus, SpectatorStoreState } from "../types";
interface SpectatorStoreOptions {
    demo?: boolean;
    demoIntervalMs?: number;
    control?: boolean;
    wsUrl?: string | null;
}
export interface SpectatorStore {
    state: SpectatorStoreState;
    connection: ConnectionStatus;
    selectHand: (handId?: string) => void;
    canControl: boolean;
    requestNextHand: () => void;
    setConfig: (config: Partial<{
        wsUrl: string | null;
    }>) => void;
    sendControl: (command: string, payload?: Record<string, unknown>) => void;
}
export declare function useSpectatorStore(options?: SpectatorStoreOptions): SpectatorStore;
export {};
