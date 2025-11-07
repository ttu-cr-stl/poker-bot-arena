import type { SpectatorHandTimeline } from "../types";
interface HandTimelineProps {
    hands: SpectatorHandTimeline[];
    currentHandId?: string;
    liveHandId?: string;
    onSelect: (handId: string) => void;
}
export declare function HandTimeline({ hands, currentHandId, liveHandId, onSelect }: HandTimelineProps): import("react/jsx-runtime").JSX.Element;
export {};
