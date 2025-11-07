import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import clsx from "clsx";
import { Card } from "./Card";
import { formatMoney } from "../utils/cards";
const RANK_SEQUENCE = "23456789TJQKA";
const RANK_VALUE = RANK_SEQUENCE.split("").reduce((acc, rank, index) => {
    acc[rank] = index + 2;
    return acc;
}, {});
function parseCardLabel(card) {
    if (!card || card.length !== 2) {
        return undefined;
    }
    const rank = card[0];
    const suit = card[1];
    const value = RANK_VALUE[rank];
    if (!value) {
        return undefined;
    }
    return { label: card, rank, suit, value };
}
function getStraightHigh(cards) {
    const values = new Set(cards.map((card) => card.value));
    if (values.has(14)) {
        values.add(1);
    }
    const ordered = Array.from(values).sort((a, b) => a - b);
    let best;
    for (let i = 0; i <= ordered.length - 5; i++) {
        let streak = 1;
        for (let j = i + 1; j < ordered.length && streak < 5; j++) {
            if (ordered[j] === ordered[i] + streak) {
                streak += 1;
            }
            else if (ordered[j] > ordered[i] + streak) {
                break;
            }
        }
        if (streak >= 5) {
            best = ordered[i] + 4;
        }
    }
    return best;
}
function evaluateFive(cards) {
    const valuesDesc = cards
        .map((card) => card.value)
        .sort((a, b) => b - a);
    const suits = cards.map((card) => card.suit);
    const isFlush = suits.every((suit) => suit === suits[0]);
    const straightHigh = getStraightHigh(cards);
    const counts = {};
    cards.forEach((card) => {
        counts[card.rank] = (counts[card.rank] ?? 0) + 1;
    });
    const orderedCounts = Object.entries(counts).sort((a, b) => {
        if (b[1] !== a[1]) {
            return b[1] - a[1];
        }
        return (RANK_VALUE[b[0]] ?? 0) - (RANK_VALUE[a[0]] ?? 0);
    });
    const countValues = Object.values(counts).sort((a, b) => b - a);
    const maxCount = countValues[0] ?? 0;
    const nextCount = countValues[1] ?? 0;
    if (straightHigh && isFlush) {
        return { strength: 8, kickers: [straightHigh] };
    }
    if (maxCount === 4) {
        const fourRank = RANK_VALUE[orderedCounts[0][0]] ?? 0;
        const kicker = orderedCounts
            .filter(([, count]) => count === 1)
            .map(([rank]) => RANK_VALUE[rank] ?? 0)
            .sort((a, b) => b - a)[0] ?? 0;
        return { strength: 7, kickers: [fourRank, kicker] };
    }
    if (maxCount === 3 && nextCount === 2) {
        const tripsRank = RANK_VALUE[orderedCounts.find(([, count]) => count === 3)?.[0] ?? ""] ?? 0;
        const pairRank = RANK_VALUE[orderedCounts.find(([, count]) => count === 2)?.[0] ?? ""] ?? 0;
        return { strength: 6, kickers: [tripsRank, pairRank] };
    }
    if (isFlush) {
        return { strength: 5, kickers: valuesDesc };
    }
    if (straightHigh) {
        return { strength: 4, kickers: [straightHigh] };
    }
    if (maxCount === 3) {
        const tripsRank = RANK_VALUE[orderedCounts.find(([, count]) => count === 3)?.[0] ?? ""] ?? 0;
        const kickers = orderedCounts
            .filter(([, count]) => count === 1)
            .map(([rank]) => RANK_VALUE[rank] ?? 0)
            .sort((a, b) => b - a);
        return { strength: 3, kickers: [tripsRank, ...kickers] };
    }
    if (maxCount === 2 && nextCount === 2) {
        const pairValues = orderedCounts
            .filter(([, count]) => count === 2)
            .map(([rank]) => RANK_VALUE[rank] ?? 0)
            .sort((a, b) => b - a);
        const kicker = orderedCounts
            .filter(([, count]) => count === 1)
            .map(([rank]) => RANK_VALUE[rank] ?? 0)
            .sort((a, b) => b - a)[0] ?? 0;
        return { strength: 2, kickers: [...pairValues, kicker] };
    }
    if (maxCount === 2) {
        const pairRank = RANK_VALUE[orderedCounts.find(([, count]) => count === 2)?.[0] ?? ""] ?? 0;
        const kickers = orderedCounts
            .filter(([, count]) => count === 1)
            .map(([rank]) => RANK_VALUE[rank] ?? 0)
            .sort((a, b) => b - a);
        return { strength: 1, kickers: [pairRank, ...kickers] };
    }
    return { strength: 0, kickers: valuesDesc };
}
function compareHandRank(a, b) {
    if (a.strength !== b.strength) {
        return a.strength - b.strength;
    }
    const length = Math.max(a.kickers.length, b.kickers.length);
    for (let i = 0; i < length; i++) {
        const diff = (a.kickers[i] ?? 0) - (b.kickers[i] ?? 0);
        if (diff !== 0) {
            return diff;
        }
    }
    return 0;
}
function selectBestFive(cards) {
    const parsed = cards.map((card) => parseCardLabel(card)).filter(Boolean);
    if (parsed.length <= 5) {
        return parsed.map((card) => card.label);
    }
    let bestRank;
    let bestCombo = [];
    const length = parsed.length;
    for (let a = 0; a < length - 4; a++) {
        for (let b = a + 1; b < length - 3; b++) {
            for (let c = b + 1; c < length - 2; c++) {
                for (let d = c + 1; d < length - 1; d++) {
                    for (let e = d + 1; e < length; e++) {
                        const combo = [parsed[a], parsed[b], parsed[c], parsed[d], parsed[e]];
                        const rank = evaluateFive(combo);
                        if (!bestRank || compareHandRank(rank, bestRank) > 0) {
                            bestRank = rank;
                            bestCombo = combo.map((card) => card.label);
                        }
                    }
                }
            }
        }
    }
    return bestCombo.length ? bestCombo : parsed.slice(0, 5).map((card) => card.label);
}
function padCards(cards) {
    const padded = [...cards];
    while (padded.length < 5) {
        padded.push(undefined);
    }
    return padded.slice(0, 5);
}
function getWinnerCards(board, seat) {
    if (seat) {
        const combined = [...(seat.hole ?? []), ...board].filter((label) => Boolean(label));
        const best = combined.length >= 5 ? selectBestFive(combined) : combined;
        return padCards(best);
    }
    return padCards(board);
}
export function HandTimeline({ hands, currentHandId, liveHandId, onSelect }) {
    if (!hands.length) {
        return (_jsx("div", { className: "timeline", children: _jsx("p", { className: "timeline__empty", children: "Hands will appear here once play begins." }) }));
    }
    const sorted = [...hands].sort((a, b) => a.handId.localeCompare(b.handId));
    return (_jsxs("div", { className: "timeline", children: [_jsx("h3", { className: "timeline__title", children: "Hands" }), _jsx("div", { className: "timeline__list", children: sorted.map((hand) => {
                    const isCurrent = hand.handId === currentHandId;
                    const isLive = hand.handId === liveHandId && !hand.closed;
                    const lastFrame = hand.frames[hand.frames.length - 1];
                    const board = lastFrame?.state.community ?? [];
                    const historyResults = hand.results ?? [];
                    const winnerResult = historyResults.reduce((best, result) => {
                        if (result.amount !== undefined && result.amount > (best?.amount ?? Number.NEGATIVE_INFINITY)) {
                            return result;
                        }
                        return best;
                    }, undefined);
                    const winnerSeat = winnerResult?.seat;
                    const winnerSeatState = winnerSeat !== undefined ? lastFrame?.state.seats.find((seat) => seat.seat === winnerSeat) : undefined;
                    const winnerName = (winnerSeatState?.team ??
                        (winnerSeat !== undefined ? `Seat ${winnerSeat}` : hand.closed ? "—" : "In progress")) ?? "In progress";
                    const potValue = historyResults.length > 0
                        ? historyResults.reduce((sum, result) => sum + Math.max(0, result.amount ?? 0), 0)
                        : lastFrame?.state.pot ?? 0;
                    const cardsToShow = getWinnerCards(board, winnerSeatState);
                    return (_jsxs("button", { className: clsx("timeline__item", {
                            "timeline__item--active": isCurrent,
                            "timeline__item--live": isLive
                        }), onClick: () => onSelect(hand.handId), type: "button", children: [_jsx("div", { className: "timeline__cards", "aria-label": `Winning cards for ${winnerName}`, children: cardsToShow.map((card, index) => (_jsx(Card, { card: card, size: "xs", hidden: !card }, `${hand.handId}-${index}`))) }), _jsxs("div", { className: "timeline__meta", children: [_jsx("span", { className: "timeline__winner-name", children: winnerName }), _jsx("span", { className: "timeline__pot", children: formatMoney(potValue) })] })] }, hand.handId));
                }) })] }));
}
