from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PlayerAction(str, Enum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"
    TAKE_INSURANCE = "take_insurance"
    DECLINE_INSURANCE = "decline_insurance"


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        if self.rank in {"J", "Q", "K"}:
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    @property
    def is_ten_value(self) -> bool:
        return self.rank in {"10", "J", "Q", "K"}

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


@dataclass(slots=True)
class Hand:
    cards: list[Card] = field(default_factory=list)
    bet_cents: int = 0
    actions: list[PlayerAction] = field(default_factory=list)
    is_completed: bool = False
    is_split_hand: bool = False
    is_split_aces: bool = False
    is_doubled: bool = False
    insurance_bet_cents: int = 0
    surrendered_early: bool = False
    surrendered_late: bool = False

    def add_card(self, card: Card) -> None:
        self.cards.append(card)

    def totals(self) -> tuple[int, bool]:
        total = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == "A")
        while total > 21 and aces:
            total -= 10
            aces -= 1
        is_soft = any(card.rank == "A" for card in self.cards) and total <= 21 and aces > 0
        return total, is_soft

    @property
    def total(self) -> int:
        return self.totals()[0]

    @property
    def is_soft(self) -> bool:
        return self.totals()[1]

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.total == 21 and not self.is_split_hand

    @property
    def is_bust(self) -> bool:
        return self.total > 21

    @property
    def can_split(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    def to_card_strings(self) -> list[str]:
        return [str(card) for card in self.cards]
