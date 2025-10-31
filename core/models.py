from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


class Phase(str, Enum):
    PRE_FLOP = "PRE_FLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    SHOWDOWN = "SHOWDOWN"


class ActionType(str, Enum):
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    RAISE_TO = "RAISE_TO"


@dataclass
class TableConfig:
    seats: int = 6
    starting_stack: int = 10_000
    sb: int = 50
    bb: int = 100
    move_time_ms: int = 15_000
    variant: str = "HUNL"


@dataclass
class PlayerSeat:
    seat: int
    team: str
    team_key: str
    stack: int
    connected: bool = False
    committed: int = 0
    total_in_pot: int = 0
    has_folded: bool = False
    hole_cards: List[str] = field(default_factory=list)

    def reset_for_hand(self) -> None:
        self.committed = 0
        self.total_in_pot = 0
        self.has_folded = False
        self.hole_cards.clear()

    def reset_for_round(self) -> None:
        self.committed = 0


@dataclass
class LobbySnapshot:
    players: List[Dict[str, object]]


@dataclass
class Event:
    ev: str
    data: Dict[str, object] = field(default_factory=dict)


@dataclass
class ActionRequest:
    hand_id: str
    req_id: str
    action: ActionType
    amount: Optional[int] = None


@dataclass
class SeatActionWindow:
    legal: List[ActionType]
    call_amount: Optional[int]
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]


@dataclass
class Snapshot:
    at_hand_id: str
    phase: Phase
    you: Dict[str, object]
    players: List[Dict[str, object]]
    community: List[str]
    next_actor: Optional[int]
    time_ms_remaining: int
    legal: Optional[List[ActionType]] = None
    call_amount: Optional[int] = None
    min_raise_to: Optional[int] = None
    max_raise_to: Optional[int] = None
