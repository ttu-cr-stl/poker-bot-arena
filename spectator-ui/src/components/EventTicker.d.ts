import type { SpectatorEvent, SpectatorSeatState } from "../types";
interface EventTickerProps {
    events: {
        event: SpectatorEvent;
        seats: SpectatorSeatState[];
        board: string[];
        ts?: string;
    }[];
}
export declare function EventTicker({ events }: EventTickerProps): import("react/jsx-runtime").JSX.Element;
export {};
