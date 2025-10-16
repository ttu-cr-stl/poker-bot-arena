from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

RANKS = "AKQJT98765432"
SUITS = "hdcs"

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

    @property
    def label(self) -> str:
        return f"{self.rank}{self.suit}"


def build_deck(seed: Optional[int] = None) -> List[Card]:
    rng = random.Random(seed)
    deck = [Card(rank, suit) for rank in RANKS[::-1] for suit in SUITS]
    rng.shuffle(deck)
    return deck


def deal(deck: List[Card], count: int) -> List[Card]:
    if len(deck) < count:
        raise ValueError("Not enough cards left in deck")
    cards = deck[:count]
    del deck[:count]
    return cards


def cards_to_labels(cards: List[Card]) -> List[str]:
    return [card.label for card in cards]


def parse_label(label: str) -> Card:
    if len(label) != 2:
        raise ValueError(f"Invalid card label: {label}")
    return Card(label[0], label[1])
