import { jsx as _jsx } from "react/jsx-runtime";
import clsx from "clsx";
import { toPrettyCard } from "../utils/cards";
export function Card({ card, hidden, dimmed, size = "md" }) {
    const pretty = toPrettyCard(hidden ? null : card);
    const isRed = pretty.suit === "h" || pretty.suit === "d";
    return (_jsx("div", { className: clsx("card", {
            "card--dim": dimmed,
            "card--empty": pretty.suit === "?",
            "card--red": isRed,
            "card--sm": size === "sm",
            "card--xs": size === "xs"
        }), "aria-label": pretty.label, role: "img", children: _jsx("span", { children: pretty.glyph }) }));
}
