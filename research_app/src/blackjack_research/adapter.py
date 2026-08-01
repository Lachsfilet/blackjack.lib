from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blackjack_engine import GameEngine, PlayerAction

from .cards import shoe_composition_from_cards
from .config import RuleConfig
from .state import GameState, HandState


@dataclass(slots=True)
class StepResult:
    state: GameState
    terminal: bool
    payout_units: float | None


class BlackjackAdapter:
    def __init__(self, config: RuleConfig, seed: int | None = None) -> None:
        self.config = config
        self.seed = seed
        self.engine = GameEngine(rules=config.to_engine_rules(), seed=seed)
        self._last_settlements: list[dict[str, Any]] | None = None

    def reset(self, seed: int | None = None) -> GameState:
        if seed is not None:
            self.seed = seed
        self.engine = GameEngine(rules=self.config.to_engine_rules(), seed=self.seed)
        self._last_settlements = None
        return self.start_hand()

    def start_hand(self, bet_units: int | None = None) -> GameState:
        self._last_settlements = None
        self.engine.deal_initial_hand(bet_amount=bet_units)
        return self.get_state()

    def step(self, action: str, params: dict[str, Any] | None = None) -> StepResult:
        self.engine.play_player_action(0, PlayerAction(action), optional_params=params)
        if self.engine.active_hand is None:
            self._last_settlements = self.engine.resolve_dealer_and_settle()
        state = self.get_state()
        return StepResult(state=state, terminal=state.terminal, payout_units=state.payout_units)

    def legal_actions(self, state: GameState | None = None) -> tuple[str, ...]:
        if state is not None:
            return state.legal_actions
        if getattr(self.engine, "_insurance_offer_open"):
            return (PlayerAction.TAKE_INSURANCE.value, PlayerAction.DECLINE_INSURANCE.value)
        return tuple(action.value for action in self.engine.legal_actions())

    def is_terminal(self, state: GameState) -> bool:
        return state.terminal

    def payout(self, state: GameState) -> float:
        if state.payout_units is None:
            raise ValueError("payout unavailable for non-terminal state")
        return state.payout_units

    def get_state(self, visible_only: bool = False) -> GameState:
        hands = tuple(self._hand_state(hand) for hand in self.engine.player_hands)
        active_hand_index: int | None = getattr(self.engine, "_active_hand_index")
        if self.engine.active_hand is None:
            active_hand_index = None

        legal_actions = self.legal_actions()
        insurance = getattr(self.engine, "_insurance_offer_open")

        dealer_cards = self.engine.dealer_hand.to_card_strings() if self.engine.dealer_hand.cards else []
        dealer_up = dealer_cards[0] if dealer_cards else ""
        dealer_hole = None
        if not visible_only and len(dealer_cards) > 1:
            dealer_hole = dealer_cards[1]

        composition = shoe_composition_from_cards(str(c) for c in self.engine.shoe._cards)
        payout_units: float | None = None
        terminal = self.engine.active_hand is None and self._last_settlements is not None
        if terminal:
            payout_units = sum(row["net_profit_cents"] for row in self._last_settlements) / 100.0

        active = self.engine.active_hand
        return GameState(
            player_hands=hands,
            active_hand_index=active_hand_index,
            dealer_upcard=dealer_up,
            dealer_hole_card=dealer_hole,
            legal_actions=legal_actions,
            can_double=PlayerAction.DOUBLE.value in legal_actions,
            can_surrender=PlayerAction.SURRENDER.value in legal_actions,
            can_split=PlayerAction.SPLIT.value in legal_actions,
            insurance_offered=insurance,
            terminal=terminal,
            payout_units=payout_units,
            shoe_composition=composition,
            shoe_remaining=self.engine.remaining_cards(),
            split_hands=len(hands),
        )

    def get_last_settlements(self) -> list[dict[str, Any]]:
        if self._last_settlements is None:
            return []
        return self._last_settlements

    @staticmethod
    def _hand_state(hand: Any) -> HandState:
        return HandState(
            cards=tuple(hand.to_card_strings()),
            total=hand.total,
            is_soft=hand.is_soft,
            is_blackjack=hand.is_blackjack,
            is_bust=hand.is_bust,
            can_split=hand.can_split,
            is_split_hand=hand.is_split_hand,
            is_split_aces=hand.is_split_aces,
            is_doubled=hand.is_doubled,
            surrendered_early=hand.surrendered_early,
            surrendered_late=hand.surrendered_late,
        )
