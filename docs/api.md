# API Reference (Short)

## Core classes

- `Rules`: table/game rule configuration
- `Shoe`: multi-deck card shoe with deterministic shuffling
- `Card`: rank/suit card model
- `Hand`: mutable hand with totals/blackjack/bust helpers
- `PlayerAction`: action enum (`hit`, `stand`, `double`, `split`, `surrender`, `take_insurance`, `decline_insurance`)
- `GameEngine`: hand lifecycle and settlement engine

## GameEngine methods

- `deal_initial_hand(bet_amount=None)`
- `play_player_action(player_id, action, optional_params=None)`
- `resolve_dealer_and_settle()`
- `play_full_hand_using_strategy(strategy_callback, bet_amount=None)`
- `set_rules(rules)`
- `reset_shoe()`
- `shuffle(seed=None)`
- `remaining_cards()`

## IO helper

- `append_hand_results_csv(path, settlements)`
