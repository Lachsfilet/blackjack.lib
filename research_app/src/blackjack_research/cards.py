from __future__ import annotations

from collections import Counter
from typing import Iterable

RANKS: tuple[str, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
TEN_VALUE = {"10", "J", "Q", "K"}


def card_rank(card: str) -> str:
    if len(card) == 3:
        return "10"
    return card[0]


def card_value(rank: str) -> int:
    if rank in TEN_VALUE:
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total_from_ranks(ranks: Iterable[str]) -> tuple[int, bool]:
    cards = list(ranks)
    total = sum(card_value(r) for r in cards)
    aces = sum(1 for r in cards if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def hand_total_from_cards(cards: Iterable[str]) -> tuple[int, bool]:
    return hand_total_from_ranks(card_rank(card) for card in cards)


def shoe_composition_from_cards(cards: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter(card_rank(c) for c in cards)
    return {rank: counts.get(rank, 0) for rank in RANKS}
