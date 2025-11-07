interface PlaybackControlsProps {
    isPlaying: boolean;
    canStepBackward: boolean;
    canStepForward: boolean;
    onPlay: () => void;
    onPause: () => void;
    onStepBackward: () => void;
    onStepForward: () => void;
    onSpeedChange: (speed: number) => void;
    speed: number;
    speeds?: number[];
    isLive: boolean;
    onJumpToLive: () => void;
}
export declare function PlaybackControls({ isPlaying, canStepBackward, canStepForward, onPlay, onPause, onStepBackward, onStepForward, onSpeedChange, speed, speeds, isLive, onJumpToLive }: PlaybackControlsProps): import("react/jsx-runtime").JSX.Element;
export {};
