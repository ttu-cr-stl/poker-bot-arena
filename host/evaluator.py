from __future__ import annotations

import itertools
from typing import Iterable, List, Optional, Sequence, Tuple

from .cards import Card, parse_label

RANK_ORDER = "23456789TJQKA"
RANK_VALUE = {rank: idx for idx, rank in enumerate(RANK_ORDER, start=2)}


def evaluate_best(cards: Sequence[Card]) -> Tuple[int, List[int]]:
    """Return a strength tuple for up to 7 cards (Texas Hold'em). Higher is better."""
    best: Optional[Tuple[int, List[int]]] = None
    for combo in itertools.combinations(cards, 5):
        rank = _evaluate_five(combo)
        if best is None or rank > best:
            best = rank
    assert best is not None
    return best


def _evaluate_five(cards: Iterable[Card]) -> Tuple[int, List[int]]:
    ranks = sorted((RANK_VALUE[card.rank] for card in cards), reverse=True)
    suits = [card.suit for card in cards]

    is_flush = len(set(suits)) == 1
    straight_high = _straight_high(cards)

    counts = {}
    for card in cards:
        counts.setdefault(card.rank, 0)
        counts[card.rank] += 1

    ordered_counts = sorted(counts.items(), key=lambda x: (x[1], RANK_VALUE[x[0]]), reverse=True)
    count_values = sorted(counts.values(), reverse=True)

    if straight_high and is_flush:
        return (8, [straight_high])
    if count_values[0] == 4:
        four_rank = RANK_VALUE[ordered_counts[0][0]]
        kicker = max(RANK_VALUE[r] for r, c in ordered_counts if r != ordered_counts[0][0])
        return (7, [four_rank, kicker])
    if count_values[0] == 3 and count_values[1] == 2:
        trips = RANK_VALUE[ordered_counts[0][0]]
        pair = RANK_VALUE[ordered_counts[1][0]]
        return (6, [trips, pair])
    if is_flush:
        return (5, ranks)
    if straight_high:
        return (4, [straight_high])
    if count_values[0] == 3:
        trips_rank = RANK_VALUE[ordered_counts[0][0]]
        kickers = [RANK_VALUE[r] for r, c in ordered_counts[1:]]
        return (3, [trips_rank] + kickers)
    if count_values[0] == 2 and count_values[1] == 2:
        pair_high = RANK_VALUE[ordered_counts[0][0]]
        pair_low = RANK_VALUE[ordered_counts[1][0]]
        kicker = max(RANK_VALUE[r] for r, c in ordered_counts if c == 1)
        return (2, [pair_high, pair_low, kicker])
    if count_values[0] == 2:
        pair_rank = RANK_VALUE[ordered_counts[0][0]]
        kickers = [RANK_VALUE[r] for r, c in ordered_counts[1:]]
        return (1, [pair_rank] + kickers)
    return (0, ranks)


def _straight_high(cards: Iterable[Card]) -> Optional[int]:
    ranks = {RANK_VALUE[card.rank] for card in cards}
    if 14 in ranks:  # Ace low
        ranks.add(1)
    ordered = sorted(ranks)
    for idx in range(len(ordered) - 4):
        window = ordered[idx : idx + 5]
        if window == list(range(window[0], window[0] + 5)):
            return window[-1]
    if set([14, 5, 4, 3, 2]).issubset(ranks):
        return 5
    return None


def parse_cards(labels: Sequence[str]) -> List[Card]:
    return [parse_label(label) for label in labels]
