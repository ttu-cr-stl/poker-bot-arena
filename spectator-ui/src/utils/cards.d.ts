declare const SUIT_MAP: Record<string, string>;
export interface PrettyCard {
    label: string;
    suit: keyof typeof SUIT_MAP | "?";
    glyph: string;
    rank: string;
}
export declare function toPrettyCard(card?: string | null): PrettyCard;
export declare function formatMoney(amount: number | undefined | null): string;
export {};
