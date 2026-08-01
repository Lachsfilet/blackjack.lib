from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from blackjack_engine import GameEngine, PlayerAction, Rules, SurrenderOption, append_hand_results_csv


def _load_rules_config(path: str | None) -> dict:
    if not path:
        return {}
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("YAML support requires pyyaml to be installed") from exc
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _random_strategy(rng: random.Random):
    def strategy(engine: GameEngine, hand, options: list[PlayerAction]):
        if PlayerAction.TAKE_INSURANCE in options and PlayerAction.DECLINE_INSURANCE in options:
            return PlayerAction.DECLINE_INSURANCE
        if hand.total >= 17 and PlayerAction.STAND in options:
            return PlayerAction.STAND
        weighted = [a for a in options if a not in {PlayerAction.SURRENDER, PlayerAction.SPLIT, PlayerAction.DOUBLE}]
        choices = weighted if weighted else options
        return rng.choice(choices)

    return strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic blackjack engine hands")
    parser.add_argument("--decks", type=int, default=6)
    parser.add_argument("--penetration", type=float, default=0.25)
    parser.add_argument("--hands", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--csv-output", type=str, default=None)
    parser.add_argument("--rules-config", type=str, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = _load_rules_config(args.rules_config)
    if "surrender" in config and isinstance(config["surrender"], str):
        config["surrender"] = SurrenderOption(config["surrender"])

    rules = Rules(decks=args.decks, penetration_fraction=args.penetration, **config)
    engine = GameEngine(rules=rules, seed=args.seed)
    rng = random.Random(args.seed)
    strategy = _random_strategy(rng)

    total_profit = 0
    for _ in range(args.hands):
        settlements = engine.play_full_hand_using_strategy(strategy, bet_amount=rules.base_bet_units)
        total_profit += sum(result["net_profit_cents"] for result in settlements)
        if args.csv_output:
            append_hand_results_csv(args.csv_output, settlements)

    print(f"Hands: {args.hands}")
    print(f"Total profit: {total_profit / 100:.2f}")


if __name__ == "__main__":
    main()
