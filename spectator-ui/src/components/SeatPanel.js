import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import clsx from "clsx";
import { formatMoney } from "../utils/cards";
import { Card } from "./Card";
function formatAction(event) {
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
export function SeatPanel({ seat, isActive, highlight, lastAction, canSkip, canForfeit, onSkip, onForfeit }) {
    const cards = seat.hole ?? [];
    return (_jsxs("div", { className: clsx("seat", {
            "seat--active": Boolean(isActive),
            "seat--folded": Boolean(seat.has_folded),
            "seat--highlight": Boolean(highlight)
        }), children: [_jsxs("div", { className: "seat__header", children: [_jsxs("div", { className: "seat__identity", children: [_jsx("span", { className: "seat__name", children: seat.team }), seat.is_button && _jsx("span", { className: "seat__badge", children: "BTN" })] }), _jsxs("div", { className: "seat__stack-group", children: [!seat.connected && _jsx("span", { className: "seat__status-dot", title: "Disconnected" }), _jsx("span", { className: "seat__stack", children: formatMoney(seat.stack) })] })] }), _jsxs("div", { className: "seat__cards", children: [_jsx(Card, { card: cards[0], dimmed: seat.has_folded }), _jsx(Card, { card: cards[1], dimmed: seat.has_folded })] }), _jsx("div", { className: "seat__meta", children: seat.has_folded
                    ? "Folded"
                    : lastAction
                        ? formatAction(lastAction)
                        : seat.committed
                            ? `In pot ${formatMoney(seat.committed)}`
                            : "\u00A0" }), (canSkip || canForfeit) && (_jsxs("div", { className: "seat__actions", children: [canSkip && (_jsx("button", { className: "seat__action seat__action--skip", type: "button", onClick: onSkip, title: "Skip this bot", "aria-label": "Skip this bot", children: _jsx("span", { className: "sr-only", children: "Skip this bot" }) })), canForfeit && (_jsx("button", { className: "seat__action seat__action--danger", type: "button", onClick: onForfeit, title: "Forfeit seat", "aria-label": "Forfeit seat", children: _jsx("span", { className: "sr-only", children: "Forfeit seat" }) }))] }))] }));
}
