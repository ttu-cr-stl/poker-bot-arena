import type { SpectatorEvent, SpectatorSeatState } from "../types";
import { describeEvent } from "../utils/events";

interface EventTickerProps {
  events: { event: SpectatorEvent; seats: SpectatorSeatState[]; board: string[]; ts?: string }[];
}

export function EventTicker({ events }: EventTickerProps) {
  if (!events.length) {
    return (
      <div className="ticker">
        <span className="ticker__item ticker__item--empty">Waiting for action…</span>
      </div>
    );
  }
  return (
    <div className="ticker">
      {events.map(({ event, seats, board, ts }, index) => (
        <span className="ticker__item" key={`${event.id ?? index}-${ts ?? index}`}>
          <span className="ticker__bullet">•</span>
          {describeEvent(event, seats, board)}
        </span>
      ))}
    </div>
  );
}
