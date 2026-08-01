from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .adapter import BlackjackAdapter
from .agents import Agent


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    hands: int
    ev_per_hand: float
    standard_error: float
    ci95_low: float
    ci95_high: float
    win_rate: float
    push_rate: float
    loss_rate: float
    action_frequencies: dict[str, float]
    bankroll_curve_flat: list[float]
    bankroll_curve_spread: list[float]


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    agent: str
    ev_per_hand: float
    standard_error: float
    ci95: tuple[float, float]


def simulate(agent: Agent, adapter: BlackjackAdapter, hands: int, seed: int) -> SimulationMetrics:
    adapter.reset(seed=seed)
    returns: list[float] = []
    action_counts: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    bankroll_flat = [0.0]
    bankroll_spread = [0.0]

    for _ in range(hands):
        state = adapter.start_hand(bet_units=agent.choose_bet_units(None))

        while not state.terminal:
            legal = adapter.legal_actions(state)
            action = agent.choose_action(state, legal)
            action_counts[action] += 1
            state = adapter.step(action).state

        payout = adapter.payout(state)
        returns.append(payout)
        settlements = adapter.get_last_settlements()
        net_cents = sum(row["net_profit_cents"] for row in settlements)
        bet_cents = sum(row["bet_cents"] for row in settlements)
        flat_units = net_cents / bet_cents if bet_cents else 0.0
        bankroll_flat.append(bankroll_flat[-1] + flat_units)
        bankroll_spread.append(bankroll_spread[-1] + payout)

        if payout > 0:
            outcomes["win"] += 1
        elif payout < 0:
            outcomes["loss"] += 1
        else:
            outcomes["push"] += 1

        agent.observe_round(settlements, state)

    mean = sum(returns) / hands
    variance = sum((x - mean) ** 2 for x in returns) / max(hands - 1, 1)
    se = math.sqrt(variance / hands)
    ci_delta = 1.96 * se

    total_actions = sum(action_counts.values()) or 1
    freqs = {action: count / total_actions for action, count in action_counts.items()}

    return SimulationMetrics(
        hands=hands,
        ev_per_hand=mean,
        standard_error=se,
        ci95_low=mean - ci_delta,
        ci95_high=mean + ci_delta,
        win_rate=outcomes["win"] / hands,
        push_rate=outcomes["push"] / hands,
        loss_rate=outcomes["loss"] / hands,
        action_frequencies=freqs,
        bankroll_curve_flat=bankroll_flat,
        bankroll_curve_spread=bankroll_spread,
    )


def benchmark(agent_results: dict[str, SimulationMetrics], perfect_name: str = "perfect") -> tuple[list[BenchmarkRow], dict[str, float]]:
    rows: list[BenchmarkRow] = []
    perfect_ev = agent_results[perfect_name].ev_per_hand
    edge: dict[str, float] = {}
    for name, metrics in agent_results.items():
        rows.append(
            BenchmarkRow(
                agent=name,
                ev_per_hand=metrics.ev_per_hand,
                standard_error=metrics.standard_error,
                ci95=(metrics.ci95_low, metrics.ci95_high),
            )
        )
        if name != perfect_name:
            edge[name] = perfect_ev - metrics.ev_per_hand
    return rows, edge
