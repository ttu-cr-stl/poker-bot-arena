import clsx from "clsx";
import type { SpectatorEvent, SpectatorSeatState } from "../types";
import { formatMoney } from "../utils/cards";
import { Card } from "./Card";

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

function formatAction(event?: SpectatorEvent): string {
  if (!event) {
    return "\u00A0";
  }
  const amount = event.amount !== undefined ? formatMoney(event.amount) : "";
  switch (event.ev) {
    case "BET":
    case "RAISE":
    case "RAISE_TO":
      return `Bet ${amount}`;
    case "CALL":
      return `Called ${amount}`;
    case "CHECK":
      return "Checked";
    case "FOLD":
      return "Folded";
    case "POT_AWARD":
      return `Won ${amount}`;
    case "SHOWDOWN":
      return "Showed cards";
    default:
      return event.description ?? event.ev;
  }
}

export function SeatPanel({ seat, isActive, highlight, lastAction, canSkip, canForfeit, onSkip, onForfeit }: SeatPanelProps) {
  const cards = seat.hole ?? [];
  return (
    <div
      className={clsx("seat", {
        "seat--active": Boolean(isActive),
        "seat--folded": Boolean(seat.has_folded),
        "seat--highlight": Boolean(highlight)
      })}
    >
      <div className="seat__header">
        <div className="seat__identity">
          <span className="seat__name">{seat.team}</span>
          {seat.is_button && <span className="seat__badge">BTN</span>}
        </div>
        <div className="seat__stack-group">
          {!seat.connected && <span className="seat__status-dot" title="Disconnected" />}
          <span className="seat__stack">{formatMoney(seat.stack)}</span>
        </div>
      </div>
      <div className="seat__cards">
        <Card card={cards[0]} dimmed={seat.has_folded} />
        <Card card={cards[1]} dimmed={seat.has_folded} />
      </div>
      <div className="seat__meta">
        {seat.has_folded
          ? "Folded"
          : lastAction
          ? formatAction(lastAction)
          : seat.committed
          ? `In pot ${formatMoney(seat.committed)}`
          : "\u00A0"}
      </div>
      {(canSkip || canForfeit) && (
        <div className="seat__actions">
          {canSkip && (
            <button
              className="seat__action seat__action--skip"
              type="button"
              onClick={onSkip}
              title="Skip this bot"
              aria-label="Skip this bot"
            >
              <span className="sr-only">Skip this bot</span>
            </button>
          )}
          {canForfeit && (
            <button
              className="seat__action seat__action--danger"
              type="button"
              onClick={onForfeit}
              title="Forfeit seat"
              aria-label="Forfeit seat"
            >
              <span className="sr-only">Forfeit seat</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
