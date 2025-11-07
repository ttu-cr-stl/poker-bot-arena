function formatBoardCards(cards, fallback) {
    if (cards && cards.length) {
        return cards.join(" ");
    }
    if (Array.isArray(fallback) && fallback.length) {
        return fallback.join(" ");
    }
    if (typeof fallback === "string" && fallback) {
        return fallback;
    }
    return undefined;
}
export function describeEvent(event, seats, board) {
    if (!event) {
        return "";
    }
    const actor = typeof event.seat === "number" ? seats.find((seat) => seat.seat === event.seat) : undefined;
    const actorName = actor?.team ?? (typeof event.seat === "number" ? `Seat ${event.seat}` : "");
    const amount = event.amount !== undefined ? `$${event.amount}` : "";
    switch (event.ev) {
        case "BET":
        case "RAISE":
        case "RAISE_TO":
            return `${actorName} bet ${amount}`;
        case "CALL":
            return `${actorName} called ${amount}`;
        case "FOLD":
            return `${actorName} folded`;
        case "CHECK":
            return `${actorName} checked`;
        case "POST_BLINDS":
            return "Blinds posted";
        case "SHOWDOWN": {
            const rankLabel = event.rank ? event.rank.replace(/_/g, " ") : "";
            return `${actorName} showed ${event.cards?.join(" ") ?? ""} ${rankLabel}`.trim();
        }
        case "POT_AWARD":
            return `${actorName} won ${amount}`;
        case "FLOP": {
            const label = formatBoardCards(event.cards, board?.slice(0, 3));
            return label ? `Flop ${label}` : "Flop dealt";
        }
        case "TURN": {
            const turnCard = event.cards?.[0] ?? board?.[3];
            return turnCard ? `Turn ${turnCard}` : "Turn dealt";
        }
        case "RIVER": {
            const riverCard = event.cards?.[0] ?? board?.[4];
            return riverCard ? `River ${riverCard}` : "River dealt";
        }
        default:
            return event.description ?? event.ev;
    }
}
