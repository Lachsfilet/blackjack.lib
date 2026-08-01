from __future__ import annotations

from pathlib import Path

import pytest

from blackjack_engine import (
    Card,
    GameEngine,
    PlayerAction,
    Rules,
    SurrenderOption,
    append_hand_results_csv,
)


def rig_shoe(engine: GameEngine, cards: list[Card]) -> None:
    filler = [Card("2", "♣") for _ in range(engine.shoe.total_cards)]
    engine.shoe._cards = filler + list(reversed(cards))


def c(rank: str, suit: str = "♠") -> Card:
    return Card(rank, suit)


def test_peek_and_insurance_resolve_correctly() -> None:
    engine = GameEngine(Rules(dealer_peek=True, allow_insurance=True), seed=1)
    rig_shoe(engine, [c("10"), c("A"), c("9"), c("K")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.TAKE_INSURANCE)
    settlements = engine.resolve_dealer_and_settle()

    assert settlements[0]["outcome"] == "lose"
    assert settlements[0]["insurance_bet_cents"] == 50
    assert settlements[0]["net_profit_cents"] == 0


def test_no_peek_late_surrender_loses_against_blackjack() -> None:
    rules = Rules(dealer_peek=False, surrender=SurrenderOption.LATE)
    engine = GameEngine(rules, seed=2)
    rig_shoe(engine, [c("10"), c("A"), c("6"), c("K")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.SURRENDER)
    settlements = engine.resolve_dealer_and_settle()

    assert settlements[0]["outcome"] == "lose"
    assert settlements[0]["net_profit_cents"] == -100


def test_early_surrender_beats_no_peek_blackjack() -> None:
    rules = Rules(dealer_peek=False, surrender=SurrenderOption.EARLY)
    engine = GameEngine(rules, seed=3)
    rig_shoe(engine, [c("10"), c("A"), c("6"), c("K")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.SURRENDER)
    settlements = engine.resolve_dealer_and_settle()

    assert settlements[0]["outcome"] == "surrender"
    assert settlements[0]["net_profit_cents"] == -50


def test_split_aces_one_card_only() -> None:
    rules = Rules(split_aces_one_card_only=True)
    engine = GameEngine(rules, seed=4)
    rig_shoe(engine, [c("A"), c("5"), c("A"), c("9"), c("10"), c("9")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.SPLIT)

    with pytest.raises(RuntimeError):
        engine.play_player_action(0, PlayerAction.HIT)

    settlements = engine.resolve_dealer_and_settle()
    assert len(settlements) == 2
    assert all(result["bet_cents"] == 100 for result in settlements)


def test_max_resplit_limit_is_enforced() -> None:
    rules = Rules(max_resplits=1)
    engine = GameEngine(rules, seed=5)
    rig_shoe(engine, [c("8"), c("5"), c("8"), c("9"), c("8"), c("2")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.SPLIT)

    with pytest.raises(ValueError, match="maximum split hands reached"):
        engine.play_player_action(0, PlayerAction.SPLIT)


def test_double_after_split_config_enforced() -> None:
    rules = Rules(double_after_split=False)
    engine = GameEngine(rules, seed=6)
    rig_shoe(engine, [c("8"), c("5"), c("8"), c("9"), c("3"), c("2")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.SPLIT)

    with pytest.raises(ValueError, match="double after split"):
        engine.play_player_action(0, PlayerAction.DOUBLE)


def test_blackjack_payout_and_push() -> None:
    engine = GameEngine(Rules(), seed=7)
    rig_shoe(engine, [c("A"), c("9"), c("K"), c("7"), c("8")])

    engine.deal_initial_hand(bet_amount=1)
    settlements = engine.resolve_dealer_and_settle()

    assert settlements[0]["outcome"] == "blackjack"
    assert settlements[0]["net_profit_cents"] == 150

    engine = GameEngine(Rules(), seed=8)
    rig_shoe(engine, [c("A"), c("A"), c("K"), c("K")])
    engine.deal_initial_hand(bet_amount=1)
    settlements = engine.resolve_dealer_and_settle()
    assert settlements[0]["outcome"] == "push"
    assert settlements[0]["net_profit_cents"] == 0


def test_money_cents_rounding_with_float_bet() -> None:
    engine = GameEngine(Rules(), seed=9)
    rig_shoe(engine, [c("A"), c("9"), c("K"), c("7"), c("8")])

    engine.deal_initial_hand(bet_amount=2.5)
    if engine.active_hand:
        engine.play_player_action(0, PlayerAction.STAND)
    settlements = engine.resolve_dealer_and_settle()

    assert settlements[0]["bet_cents"] == 250
    assert settlements[0]["net_profit_cents"] == 375


def test_csv_export_contains_required_columns(tmp_path: Path) -> None:
    engine = GameEngine(Rules(), seed=10)
    rig_shoe(engine, [c("10"), c("8"), c("7"), c("9"), c("5")])

    engine.deal_initial_hand(bet_amount=1)
    engine.play_player_action(0, PlayerAction.STAND)
    settlements = engine.resolve_dealer_and_settle()

    output = tmp_path / "results.csv"
    append_hand_results_csv(output, settlements)

    rows = output.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0].startswith("shoe_id,hand_index,seed")
    assert len(rows) == 2


def test_seeded_integration_flow() -> None:
    rules = Rules(decks=1)
    engine = GameEngine(rules=rules, seed=42)

    def stand_strategy(_engine, hand, options):
        if PlayerAction.TAKE_INSURANCE in options:
            return PlayerAction.DECLINE_INSURANCE
        return PlayerAction.STAND if PlayerAction.STAND in options else options[0]

    result = engine.play_full_hand_using_strategy(stand_strategy, bet_amount=1)
    assert len(result) >= 1
    assert result[0]["hand_index"] == 1
