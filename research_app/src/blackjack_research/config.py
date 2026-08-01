from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from blackjack_engine import Rules, SurrenderOption


@dataclass(frozen=True, slots=True)
class RuleConfig:
    decks: int = 6
    dealer_hits_soft_17: bool = False
    double_after_split: bool = True
    resplit_aces: bool = False
    surrender: Literal["none", "late", "early"] = "late"
    blackjack_payout: tuple[int, int] = (3, 2)
    penetration_fraction: float = 0.25
    insurance: bool = True
    min_bet_units: int = 1
    max_bet_units: int = 20
    max_resplits: int = 3

    def to_engine_rules(self) -> Rules:
        surrender = {
            "none": SurrenderOption.NONE,
            "late": SurrenderOption.LATE,
            "early": SurrenderOption.EARLY,
        }[self.surrender]
        return Rules(
            decks=self.decks,
            dealer_hits_soft_17=self.dealer_hits_soft_17,
            double_after_split=self.double_after_split,
            resplit_aces=self.resplit_aces,
            surrender=surrender,
            blackjack_payout_numerator=self.blackjack_payout[0],
            blackjack_payout_denominator=self.blackjack_payout[1],
            penetration_fraction=self.penetration_fraction,
            allow_insurance=self.insurance,
            base_bet_units=self.min_bet_units,
            max_bet_units=self.max_bet_units,
            max_resplits=self.max_resplits,
        )


PRESETS: dict[str, RuleConfig] = {
    "casino_typical": RuleConfig(
        decks=6,
        dealer_hits_soft_17=False,
        double_after_split=True,
        resplit_aces=False,
        surrender="late",
        blackjack_payout=(3, 2),
        penetration_fraction=0.25,
        insurance=True,
        min_bet_units=1,
        max_bet_units=20,
        max_resplits=3,
    ),
    "optimal_play_conditions": RuleConfig(
        decks=1,
        dealer_hits_soft_17=False,
        double_after_split=True,
        resplit_aces=True,
        surrender="late",
        blackjack_payout=(3, 2),
        penetration_fraction=0.2,
        insurance=True,
        min_bet_units=1,
        max_bet_units=10,
        max_resplits=3,
    ),
    "counter_friendly_shoe": RuleConfig(
        decks=2,
        dealer_hits_soft_17=False,
        double_after_split=True,
        resplit_aces=True,
        surrender="late",
        blackjack_payout=(3, 2),
        penetration_fraction=0.1,
        insurance=True,
        min_bet_units=1,
        max_bet_units=40,
        max_resplits=4,
    ),
}
