const SUIT_MAP: Record<string, string> = {
  h: "♥",
  d: "♦",
  c: "♣",
  s: "♠"
};

const RANK_MAP: Record<string, string> = {
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

export interface PrettyCard {
  label: string;
  suit: keyof typeof SUIT_MAP | "?";
  glyph: string;
  rank: string;
}

export function toPrettyCard(card?: string | null): PrettyCard {
  if (!card || card.length !== 2) {
    return {
      label: "??",
      suit: "?",
      glyph: "??",
      rank: "??"
    };
  }
  const rank = RANK_MAP[card[0]] ?? card[0];
  const suit = card[1] as keyof typeof SUIT_MAP;
  const glyph = `${rank}${SUIT_MAP[suit] ?? ""}`;
  return {
    label: card,
    suit,
    glyph,
    rank
  };
}

export function formatMoney(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || Number.isNaN(amount)) {
    return "—";
  }
  const formatted = amount.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  });
  return `$${formatted}`;
}
