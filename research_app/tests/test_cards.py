from __future__ import annotations

from blackjack_research.cards import hand_total_from_cards


def test_hand_valuation_soft_and_hard() -> None:
    total, soft = hand_total_from_cards(["A♠", "6♦"])
    assert total == 17
    assert soft

    total, soft = hand_total_from_cards(["A♠", "6♦", "K♣"])
    assert total == 17
    assert not soft
