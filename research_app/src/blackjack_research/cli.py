from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .adapter import BlackjackAdapter
from .agents import build_agent
from .config import PRESETS
from .simulation import benchmark, simulate
from .solver import PerfectEVSolver
from .state import GameState, HandState


def _state_from_json(raw: str) -> GameState:
    payload = json.loads(raw)
    hands = tuple(HandState(**hand) for hand in payload["player_hands"])
    payload["player_hands"] = hands
    payload["legal_actions"] = tuple(payload["legal_actions"])
    return GameState(**payload)


def _print_table(rows: list[dict[str, str]], headers: list[str]) -> None:
    widths = {h: max(len(h), max(len(row.get(h, "")) for row in rows)) for h in headers}
    print(" | ".join(h.ljust(widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(" | ".join(row.get(h, "").ljust(widths[h]) for h in headers))


def run_compute_action(args: argparse.Namespace) -> None:
    config = PRESETS[args.preset]
    solver = PerfectEVSolver(config)
    state = _state_from_json(args.state)
    decision = solver.choose_action(state)
    print(json.dumps({"action": decision.action, "ev_breakdown": decision.action_evs}, indent=2))


def run_simulate(args: argparse.Namespace) -> None:
    config = PRESETS[args.preset]
    solver = PerfectEVSolver(config)

    def run_agent(agent_name: str) -> dict:
        adapter = BlackjackAdapter(config=config, seed=args.seed)
        agent = build_agent(agent_name, solver=solver, seed=args.seed)
        metrics = simulate(agent=agent, adapter=adapter, hands=args.hands, seed=args.seed)
        return {
            "agent": agent_name,
            "ev_per_hand": f"{metrics.ev_per_hand:.6f}",
            "se": f"{metrics.standard_error:.6f}",
            "ci95": f"[{metrics.ci95_low:.6f}, {metrics.ci95_high:.6f}]",
            "win": f"{metrics.win_rate:.3%}",
            "push": f"{metrics.push_rate:.3%}",
            "loss": f"{metrics.loss_rate:.3%}",
        }

    rows = [run_agent(args.agent_a), run_agent(args.agent_b)]
    _print_table(rows, ["agent", "ev_per_hand", "se", "ci95", "win", "push", "loss"])


def run_benchmark(args: argparse.Namespace) -> None:
    config = PRESETS[args.preset]
    solver = PerfectEVSolver(config)
    names = ["perfect", "basic", "hilo", "omega2", "random"]
    results = {}
    for name in names:
        adapter = BlackjackAdapter(config=config, seed=args.seed)
        agent = build_agent(name, solver=solver, seed=args.seed)
        results[name] = simulate(agent=agent, adapter=adapter, hands=args.hands, seed=args.seed)

    rows, edge = benchmark(results)
    table_rows = [
        {
            "agent": row.agent,
            "ev_per_hand": f"{row.ev_per_hand:.6f}",
            "se": f"{row.standard_error:.6f}",
            "ci95": f"[{row.ci95[0]:.6f}, {row.ci95[1]:.6f}]",
            "computer_edge": f"{edge[row.agent]:.6f}" if row.agent in edge else "-",
        }
        for row in rows
    ]
    _print_table(table_rows, ["agent", "ev_per_hand", "se", "ci95", "computer_edge"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Blackjack research CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    compute_parser = sub.add_parser("compute-action")
    compute_parser.add_argument("--preset", default="casino_typical", choices=sorted(PRESETS))
    compute_parser.add_argument("--state", required=True, help="Serialized GameState JSON")
    compute_parser.set_defaults(func=run_compute_action)

    simulate_parser = sub.add_parser("simulate")
    simulate_parser.add_argument("--preset", default="casino_typical", choices=sorted(PRESETS))
    simulate_parser.add_argument("--agent-a", required=True, choices=["perfect", "basic", "hilo", "omega2", "random"])
    simulate_parser.add_argument("--agent-b", required=True, choices=["perfect", "basic", "hilo", "omega2", "random"])
    simulate_parser.add_argument("--hands", type=int, default=1_000_000)
    simulate_parser.add_argument("--seed", type=int, default=123)
    simulate_parser.set_defaults(func=run_simulate)

    benchmark_parser = sub.add_parser("benchmark")
    benchmark_parser.add_argument("--preset", default="optimal_play_conditions", choices=sorted(PRESETS))
    benchmark_parser.add_argument("--hands", type=int, default=1_000_000)
    benchmark_parser.add_argument("--seed", type=int, default=123)
    benchmark_parser.set_defaults(func=run_benchmark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
