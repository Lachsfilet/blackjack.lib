from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class HandState:
    cards: tuple[str, ...]
    total: int
    is_soft: bool
    is_blackjack: bool
    is_bust: bool
    can_split: bool
    is_split_hand: bool
    is_split_aces: bool
    is_doubled: bool
    surrendered_early: bool
    surrendered_late: bool


@dataclass(frozen=True, slots=True)
class GameState:
    player_hands: tuple[HandState, ...]
    active_hand_index: int | None
    dealer_upcard: str
    dealer_hole_card: str | None
    legal_actions: tuple[str, ...]
    can_double: bool
    can_surrender: bool
    can_split: bool
    insurance_offered: bool
    terminal: bool
    payout_units: float | None
    shoe_composition: dict[str, int]
    shoe_remaining: int
    split_hands: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
