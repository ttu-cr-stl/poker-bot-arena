import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { describeEvent } from "../utils/events";
export function EventTicker({ events }) {
    if (!events.length) {
        return (_jsx("div", { className: "ticker", children: _jsx("span", { className: "ticker__item ticker__item--empty", children: "Waiting for action\u2026" }) }));
    }
    return (_jsx("div", { className: "ticker", children: events.map(({ event, seats, board, ts }, index) => (_jsxs("span", { className: "ticker__item", children: [_jsx("span", { className: "ticker__bullet", children: "\u2022" }), describeEvent(event, seats, board)] }, `${event.id ?? index}-${ts ?? index}`))) }));
}
