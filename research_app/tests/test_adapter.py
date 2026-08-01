from __future__ import annotations

from blackjack_engine import Card
from blackjack_research.adapter import BlackjackAdapter
from blackjack_research.config import PRESETS


def rig_shoe(adapter: BlackjackAdapter, cards: list[Card]) -> None:
    filler = [Card("2", "♣") for _ in range(adapter.engine.shoe.total_cards)]
    adapter.engine.shoe._cards = filler + list(reversed(cards))


def c(rank: str, suit: str = "♠") -> Card:
    return Card(rank, suit)


def test_legal_actions_include_split_and_surrender() -> None:
    adapter = BlackjackAdapter(PRESETS["casino_typical"], seed=10)
    adapter.start_hand()
    rig_shoe(adapter, [c("8"), c("6"), c("8"), c("9")])
    state = adapter.start_hand()
    assert "split" in state.legal_actions
    assert "surrender" in state.legal_actions


def test_payout_logic_resolves_terminal_state() -> None:
    adapter = BlackjackAdapter(PRESETS["casino_typical"], seed=11)
    rig_shoe(adapter, [c("10"), c("7"), c("9"), c("6"), c("8")])
    state = adapter.start_hand()
    while not state.terminal:
        state = adapter.step("stand").state
    assert adapter.payout(state) in {-1.0, 0.0, 1.0, 1.5}


def test_deterministic_seed_sequence() -> None:
    a1 = BlackjackAdapter(PRESETS["casino_typical"], seed=42)
    a2 = BlackjackAdapter(PRESETS["casino_typical"], seed=42)

    payouts1: list[float] = []
    payouts2: list[float] = []

    for adapter, target in ((a1, payouts1), (a2, payouts2)):
        adapter.reset(seed=42)
        for _ in range(10):
            state = adapter.start_hand()
            while not state.terminal:
                state = adapter.step("stand").state
            target.append(adapter.payout(state))

    assert payouts1 == payouts2
