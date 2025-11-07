import clsx from "clsx";

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

const DEFAULT_SPEEDS = [0.25, 0.5, 1, 1.5, 2];

export function PlaybackControls({
  isPlaying,
  canStepBackward,
  canStepForward,
  onPlay,
  onPause,
  onStepBackward,
  onStepForward,
  onSpeedChange,
  speed,
  speeds = DEFAULT_SPEEDS,
  isLive,
  onJumpToLive
}: PlaybackControlsProps) {
  return (
    <div className="controls">
      <div className="controls__buttons">
        <button className="controls__btn" onClick={onStepBackward} disabled={!canStepBackward} aria-label="Step backward">
          ⏮
        </button>
        {isPlaying ? (
          <button className="controls__btn controls__btn--primary" onClick={onPause} aria-label="Pause playback">
            ⏸ Pause
          </button>
        ) : (
          <button className="controls__btn controls__btn--primary" onClick={onPlay} disabled={!canStepForward} aria-label="Play">
            ▶ Play
          </button>
        )}
        <button className="controls__btn" onClick={onStepForward} disabled={!canStepForward} aria-label="Step forward">
          ⏭
        </button>
      </div>
      <div className="controls__section">
        <span className="controls__label">Speed</span>
        <div className="speed-buttons">
          {speeds.map((option) => (
            <button
              key={option}
              type="button"
              className={clsx("speed-button", { "speed-button--active": speed === option })}
              onClick={() => onSpeedChange(option)}
            >
              {option}×
            </button>
          ))}
        </div>
      </div>
      <div className="controls__section">
        <button
          className={clsx("controls__btn controls__btn--secondary", {
            "controls__btn--live": isLive
          })}
          onClick={onJumpToLive}
          disabled={isLive}
        >
          {isLive ? "Live" : "Jump to live"}
        </button>
      </div>
    </div>
  );
}
