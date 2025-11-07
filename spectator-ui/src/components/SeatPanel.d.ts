import type { SpectatorEvent, SpectatorSeatState } from "../types";
interface SeatPanelProps {
    seat: SpectatorSeatState;
    isActive?: boolean;
    highlight?: boolean;
    lastAction?: SpectatorEvent;
    canSkip?: boolean;
    canForfeit?: boolean;
    onSkip?: () => void;
    onForfeit?: () => void;
}
export declare function SeatPanel({ seat, isActive, highlight, lastAction, canSkip, canForfeit, onSkip, onForfeit }: SeatPanelProps): import("react/jsx-runtime").JSX.Element;
export {};
