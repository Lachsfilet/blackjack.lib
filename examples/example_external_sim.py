from blackjack_engine import GameEngine, PlayerAction, Rules


def simple_strategy(engine: GameEngine, hand, options):
    if PlayerAction.TAKE_INSURANCE in options:
        return PlayerAction.DECLINE_INSURANCE
    if hand.total >= 17:
        return PlayerAction.STAND
    return PlayerAction.HIT


def run_simulation() -> None:
    rules = Rules(decks=6, penetration_fraction=0.25)
    engine = GameEngine(rules=rules, seed=1234)

    for _ in range(5):
        settlements = engine.play_full_hand_using_strategy(simple_strategy, bet_amount=1)
        print(settlements)


if __name__ == "__main__":
    run_simulation()
