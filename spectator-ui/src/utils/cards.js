const SUIT_MAP = {
    h: "♥",
    d: "♦",
    c: "♣",
    s: "♠"
};
const RANK_MAP = {
    A: "A",
    K: "K",
    Q: "Q",
    J: "J",
    T: "10",
    "9": "9",
    "8": "8",
    "7": "7",
    "6": "6",
    "5": "5",
    "4": "4",
    "3": "3",
    "2": "2"
};
export function toPrettyCard(card) {
    if (!card || card.length !== 2) {
        return {
            label: "??",
            suit: "?",
            glyph: "??",
            rank: "??"
        };
    }
    const rank = RANK_MAP[card[0]] ?? card[0];
    const suit = card[1];
    const glyph = `${rank}${SUIT_MAP[suit] ?? ""}`;
    return {
        label: card,
        suit,
        glyph,
        rank
    };
}
export function formatMoney(amount) {
    if (amount === undefined || amount === null || Number.isNaN(amount)) {
        return "—";
    }
    const formatted = amount.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
    return `$${formatted}`;
}
