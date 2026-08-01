from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SurrenderOption(str, Enum):
    NONE = "none"
    LATE = "late"
    EARLY = "early"


@dataclass(slots=True)
class Rules:
    decks: int = 6
    penetration_fraction: float = 0.25
    dealer_hits_soft_17: bool = False
    blackjack_payout_numerator: int = 3
    blackjack_payout_denominator: int = 2
    dealer_peek: bool = True
    double_on_any_two: bool = True
    double_after_split: bool = True
    max_resplits: int = 3
    resplit_aces: bool = False
    split_aces_one_card_only: bool = True
    surrender: SurrenderOption = SurrenderOption.LATE
    allow_insurance: bool = True
    base_bet_units: int = 1
    max_bet_units: int = 100
    unit_cents: int = 100

    def validate(self) -> None:
        if not 1 <= self.decks <= 8:
            raise ValueError("decks must be between 1 and 8")
        if not 0 < self.penetration_fraction < 1:
            raise ValueError("penetration_fraction must be between 0 and 1")
        if self.blackjack_payout_denominator <= 0:
            raise ValueError("blackjack_payout_denominator must be > 0")
        if self.max_resplits < 0:
            raise ValueError("max_resplits must be >= 0")
        if self.base_bet_units <= 0 or self.max_bet_units < self.base_bet_units:
            raise ValueError("invalid base/max bet units")
        if self.unit_cents <= 0:
            raise ValueError("unit_cents must be > 0")
