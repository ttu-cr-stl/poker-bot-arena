import clsx from "clsx";
import { toPrettyCard } from "../utils/cards";

interface CardProps {
  card?: string | null;
  hidden?: boolean;
  dimmed?: boolean;
  size?: "md" | "sm" | "xs";
}

export function Card({ card, hidden, dimmed, size = "md" }: CardProps) {
  const pretty = toPrettyCard(hidden ? null : card);
  const isRed = pretty.suit === "h" || pretty.suit === "d";
  return (
    <div
      className={clsx("card", {
        "card--dim": dimmed,
        "card--empty": pretty.suit === "?",
        "card--red": isRed,
        "card--sm": size === "sm",
        "card--xs": size === "xs"
      })}
      aria-label={pretty.label}
      role="img"
    >
      <span>{pretty.glyph}</span>
    </div>
  );
}
