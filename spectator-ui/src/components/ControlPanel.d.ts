import type { ConnectionStatus, SpectatorStoreState } from "../types";
interface ControlPanelProps {
    state: SpectatorStoreState;
    connection: ConnectionStatus;
    onConfigChange: (config: Partial<{
        wsUrl: string | null;
    }>) => void;
}
export declare function ControlPanel({ state, connection, onConfigChange }: ControlPanelProps): import("react/jsx-runtime").JSX.Element;
export {};
