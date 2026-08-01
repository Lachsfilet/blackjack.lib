from __future__ import annotations

from blackjack_engine import Card
from blackjack_research.adapter import BlackjackAdapter
from blackjack_research.config import PRESETS
from blackjack_research.solver import PerfectEVSolver


def rig_shoe(adapter: BlackjackAdapter, cards: list[Card]) -> None:
    filler = [Card("2", "♣") for _ in range(adapter.engine.shoe.total_cards)]
    adapter.engine.shoe._cards = filler + list(reversed(cards))


def c(rank: str, suit: str = "♠") -> Card:
    return Card(rank, suit)


def test_solver_regression_fixed_state() -> None:
    config = PRESETS["optimal_play_conditions"]
    adapter = BlackjackAdapter(config, seed=9)
    rig_shoe(adapter, [c("10"), c("6"), c("10"), c("9")])
    state = adapter.start_hand()

    solver = PerfectEVSolver(config)
    decision = solver.choose_action(state)

    assert decision.action == "stand"
    assert "stand" in decision.action_evs
