from __future__ import annotations

import random
import uuid
from dataclasses import asdict
from typing import Any, Callable

from .models import Card, Hand, PlayerAction
from .rules import Rules, SurrenderOption

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
TEN_VALUE_RANKS = {"10", "J", "Q", "K"}


class Shoe:
    def __init__(self, decks: int = 6, seed: int | None = None) -> None:
        self.decks = decks
        self.seed = seed
        self._rng = random.Random(seed)
        self.shoe_id = str(uuid.uuid4())
        self._cards: list[Card] = []
        self.shuffle(seed=seed)

    def _build_cards(self) -> list[Card]:
        return [Card(rank, suit) for _ in range(self.decks) for suit in SUITS for rank in RANKS]

    def shuffle(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
            self._rng = random.Random(seed)
        self._cards = self._build_cards()
        self._rng.shuffle(self._cards)
        self.shoe_id = str(uuid.uuid4())

    def reset(self) -> None:
        self.shuffle(seed=self.seed)

    def draw(self) -> Card:
        if not self._cards:
            raise RuntimeError("shoe is empty")
        return self._cards.pop()

    def remaining_cards(self) -> int:
        return len(self._cards)

    @property
    def total_cards(self) -> int:
        return self.decks * 52

    def needs_reshuffle(self, penetration_fraction: float) -> bool:
        cutoff = int(self.total_cards * penetration_fraction)
        return self.remaining_cards() <= cutoff


class GameEngine:
    def __init__(
        self,
        rules: Rules | None = None,
        seed: int | None = None,
        logger: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.rules = rules or Rules()
        self.rules.validate()
        self.seed = seed
        self.shoe = Shoe(decks=self.rules.decks, seed=seed)
        self.logger = logger
        self._hand_index = 0
        self._action_log: dict[int, list[str]] = {}
        self._player_hands: list[Hand] = []
        self._active_hand_index = 0
        self._dealer_hand = Hand()
        self._current_bet_cents = self.rules.base_bet_units * self.rules.unit_cents
        self._hand_active = False
        self._dealer_has_blackjack = False
        self._insurance_offer_open = False
        self._shoe_remaining_before_hand = 0

    @property
    def player_hands(self) -> list[Hand]:
        return self._player_hands

    @property
    def dealer_hand(self) -> Hand:
        return self._dealer_hand

    @property
    def active_hand(self) -> Hand | None:
        if not self._hand_active:
            return None
        if self._active_hand_index >= len(self._player_hands):
            return None
        return self._player_hands[self._active_hand_index]

    def set_rules(self, rules: Rules) -> None:
        rules.validate()
        self.rules = rules
        self.shoe = Shoe(decks=self.rules.decks, seed=self.seed)

    def reset_shoe(self) -> None:
        self.shoe = Shoe(decks=self.rules.decks, seed=self.seed)

    def shuffle(self, seed: int | None = None) -> None:
        self.shoe.shuffle(seed)

    def remaining_cards(self) -> int:
        return self.shoe.remaining_cards()

    def _bet_to_cents(self, bet_amount: int | float | None) -> int:
        if bet_amount is None:
            return self.rules.base_bet_units * self.rules.unit_cents
        if isinstance(bet_amount, int):
            if bet_amount <= self.rules.max_bet_units:
                return bet_amount * self.rules.unit_cents
            return bet_amount
        return int(round(bet_amount * 100))

    def deal_initial_hand(self, bet_amount: int | float | None = None) -> tuple[Hand, Card]:
        if self._hand_active:
            raise RuntimeError("current hand must be resolved before dealing")
        if self.shoe.needs_reshuffle(self.rules.penetration_fraction):
            self.shoe.reset()

        self._shoe_remaining_before_hand = self.shoe.remaining_cards()
        self._hand_index += 1
        self._dealer_has_blackjack = False
        self._insurance_offer_open = False
        self._current_bet_cents = self._bet_to_cents(bet_amount)
        self._player_hands = [Hand(bet_cents=self._current_bet_cents)]
        self._active_hand_index = 0
        self._dealer_hand = Hand()
        self._action_log = {0: []}
        self._hand_active = True

        self._player_hands[0].add_card(self.shoe.draw())
        self._dealer_hand.add_card(self.shoe.draw())
        self._player_hands[0].add_card(self.shoe.draw())
        self._dealer_hand.add_card(self.shoe.draw())

        dealer_upcard = self._dealer_hand.cards[0]
        if self.rules.allow_insurance and dealer_upcard.rank == "A":
            self._insurance_offer_open = True

        if self.rules.dealer_peek and (
            dealer_upcard.rank == "A" or dealer_upcard.rank in TEN_VALUE_RANKS
        ):
            self._dealer_has_blackjack = self._dealer_hand.is_blackjack
            if self._dealer_has_blackjack:
                for hand in self._player_hands:
                    hand.is_completed = True

        if self._player_hands[0].is_blackjack and not self._dealer_has_blackjack:
            self._player_hands[0].is_completed = True

        return self._player_hands[0], dealer_upcard

    def _advance_active_hand(self) -> None:
        while self._active_hand_index < len(self._player_hands) and self._player_hands[
            self._active_hand_index
        ].is_completed:
            self._active_hand_index += 1

    def _validate_active_hand(self) -> Hand:
        if not self._hand_active:
            raise RuntimeError("no active hand")
        hand = self.active_hand
        if hand is None:
            raise RuntimeError("no playable hand")
        return hand

    def play_player_action(
        self,
        player_id: int,
        action: PlayerAction,
        optional_params: dict[str, Any] | None = None,
    ) -> None:
        del player_id
        params = optional_params or {}

        if action in {PlayerAction.TAKE_INSURANCE, PlayerAction.DECLINE_INSURANCE}:
            self._handle_insurance_action(action, params)
            return

        hand = self._validate_active_hand()

        if action == PlayerAction.HIT:
            hand.actions.append(action)
            hand.add_card(self.shoe.draw())
            self._action_log.setdefault(self._active_hand_index, []).append(action.value)
            if hand.is_bust or (hand.is_split_aces and self.rules.split_aces_one_card_only):
                hand.is_completed = True
                self._advance_active_hand()
            return

        if action == PlayerAction.STAND:
            hand.actions.append(action)
            self._action_log.setdefault(self._active_hand_index, []).append(action.value)
            hand.is_completed = True
            self._advance_active_hand()
            return

        if action == PlayerAction.DOUBLE:
            self._handle_double(hand)
            self._action_log.setdefault(self._active_hand_index, []).append(action.value)
            hand.is_completed = True
            self._advance_active_hand()
            return

        if action == PlayerAction.SPLIT:
            self._handle_split(hand)
            return

        if action == PlayerAction.SURRENDER:
            self._handle_surrender(hand)
            self._action_log.setdefault(self._active_hand_index, []).append(action.value)
            hand.is_completed = True
            self._advance_active_hand()
            return

        raise ValueError(f"unsupported action: {action}")

    def _handle_insurance_action(self, action: PlayerAction, params: dict[str, Any]) -> None:
        if not self._insurance_offer_open:
            raise ValueError("insurance is not available")
        hand = self._player_hands[0]
        if hand.insurance_bet_cents:
            raise ValueError("insurance already set")
        if action == PlayerAction.DECLINE_INSURANCE:
            self._insurance_offer_open = False
            return

        amount = params.get("insurance_bet_cents", hand.bet_cents // 2)
        if amount < 0 or amount > hand.bet_cents // 2:
            raise ValueError("insurance must be between 0 and half the original bet")
        hand.insurance_bet_cents = amount
        self._insurance_offer_open = False

    def _handle_double(self, hand: Hand) -> None:
        if len(hand.cards) != 2:
            raise ValueError("double is only allowed on exactly two cards")
        if hand.is_split_hand and not self.rules.double_after_split:
            raise ValueError("double after split is not allowed")
        hand.actions.append(PlayerAction.DOUBLE)
        hand.bet_cents *= 2
        hand.is_doubled = True
        hand.add_card(self.shoe.draw())

    def _handle_split(self, hand: Hand) -> None:
        if not hand.can_split:
            raise ValueError("split requires a pair")
        if len(self._player_hands) >= self.rules.max_resplits + 1:
            raise ValueError("maximum split hands reached")
        rank = hand.cards[0].rank
        if rank == "A" and hand.is_split_hand and not self.rules.resplit_aces:
            raise ValueError("resplitting aces is not allowed")

        card_left, card_right = hand.cards
        left = Hand(
            cards=[card_left],
            bet_cents=hand.bet_cents,
            is_split_hand=True,
            is_split_aces=rank == "A",
        )
        right = Hand(
            cards=[card_right],
            bet_cents=hand.bet_cents,
            is_split_hand=True,
            is_split_aces=rank == "A",
        )
        left.add_card(self.shoe.draw())
        right.add_card(self.shoe.draw())

        self._player_hands = (
            self._player_hands[: self._active_hand_index]
            + [left, right]
            + self._player_hands[self._active_hand_index + 1 :]
        )

        updated_log: dict[int, list[str]] = {}
        for idx, old_idx in enumerate(sorted(self._action_log)):
            updated_log[idx if idx < self._active_hand_index else idx + 1] = self._action_log[old_idx]
        self._action_log = updated_log
        self._action_log[self._active_hand_index] = [PlayerAction.SPLIT.value]
        self._action_log[self._active_hand_index + 1] = [PlayerAction.SPLIT.value]

        if rank == "A" and self.rules.split_aces_one_card_only:
            left.is_completed = True
            right.is_completed = True

        self._advance_active_hand()

    def _handle_surrender(self, hand: Hand) -> None:
        if self.rules.surrender == SurrenderOption.NONE:
            raise ValueError("surrender is not allowed")
        if len(hand.cards) != 2 or hand.actions:
            raise ValueError("surrender is only allowed as first action on a two-card hand")
        if self.rules.surrender == SurrenderOption.EARLY:
            hand.surrendered_early = True
            return
        if self._dealer_has_blackjack:
            raise ValueError("late surrender is unavailable when dealer has blackjack")
        hand.surrendered_late = True

    def _all_player_hands_finished(self) -> bool:
        return all(hand.is_completed for hand in self._player_hands)

    def _play_dealer(self) -> None:
        if self._dealer_has_blackjack:
            return
        while True:
            total, soft = self._dealer_hand.totals()
            if total > 21:
                return
            if total > 17:
                return
            if total == 17:
                if soft and self.rules.dealer_hits_soft_17:
                    self._dealer_hand.add_card(self.shoe.draw())
                    continue
                return
            self._dealer_hand.add_card(self.shoe.draw())

    def resolve_dealer_and_settle(self) -> list[dict[str, Any]]:
        if not self._hand_active:
            raise RuntimeError("no active hand to resolve")
        if not self._all_player_hands_finished() and not self._dealer_has_blackjack:
            raise RuntimeError("all player hands must be completed before resolving")

        if not self.rules.dealer_peek and self._dealer_hand.is_blackjack:
            self._dealer_has_blackjack = True

        self._play_dealer()
        dealer_total = self._dealer_hand.total
        dealer_blackjack = self._dealer_hand.is_blackjack
        dealer_bust = dealer_total > 21

        settlements: list[dict[str, Any]] = []
        for idx, hand in enumerate(self._player_hands):
            insurance_net = 0
            insurance_bet = hand.insurance_bet_cents if idx == 0 else 0
            if insurance_bet:
                insurance_net = insurance_bet * 2 if dealer_blackjack else -insurance_bet

            if hand.surrendered_early:
                outcome = "surrender"
                hand_net = -(hand.bet_cents // 2)
            elif hand.surrendered_late and dealer_blackjack:
                outcome = "lose"
                hand_net = -hand.bet_cents
            elif hand.surrendered_late:
                outcome = "surrender"
                hand_net = -(hand.bet_cents // 2)
            elif hand.is_bust:
                outcome = "lose"
                hand_net = -hand.bet_cents
            elif dealer_blackjack and hand.is_blackjack:
                outcome = "push"
                hand_net = 0
            elif dealer_blackjack:
                outcome = "lose"
                hand_net = -hand.bet_cents
            elif hand.is_blackjack:
                outcome = "blackjack"
                hand_net = (hand.bet_cents * self.rules.blackjack_payout_numerator) // self.rules.blackjack_payout_denominator
            elif dealer_bust:
                outcome = "win"
                hand_net = hand.bet_cents
            elif hand.total > dealer_total:
                outcome = "win"
                hand_net = hand.bet_cents
            elif hand.total < dealer_total:
                outcome = "lose"
                hand_net = -hand.bet_cents
            else:
                outcome = "push"
                hand_net = 0

            net = hand_net + insurance_net
            settlements.append(
                {
                    "shoe_id": self.shoe.shoe_id,
                    "hand_index": self._hand_index,
                    "seed": self.seed,
                    "player_position": 0,
                    "hand_position": idx,
                    "player_cards": hand.to_card_strings(),
                    "dealer_upcard": str(self._dealer_hand.cards[0]),
                    "dealer_final_cards": self._dealer_hand.to_card_strings(),
                    "actions": self._action_log.get(idx, []),
                    "bet_cents": hand.bet_cents,
                    "insurance_bet_cents": insurance_bet,
                    "outcome": outcome,
                    "net_profit_cents": net,
                    "net_profit": net / 100.0,
                    "shoe_remaining_cards_before_hand": self._shoe_remaining_before_hand,
                }
            )

        if self.logger:
            self.logger(
                {
                    "shoe_id": self.shoe.shoe_id,
                    "hand_index": self._hand_index,
                    "seed": self.seed,
                    "player_position": 0,
                    "player_hands": [hand.to_card_strings() for hand in self._player_hands],
                    "dealer_upcard": str(self._dealer_hand.cards[0]),
                    "dealer_final_cards": self._dealer_hand.to_card_strings(),
                    "actions": {k: v[:] for k, v in self._action_log.items()},
                    "settlements": settlements,
                    "shoe_remaining_cards_before_hand": self._shoe_remaining_before_hand,
                }
            )

        self._hand_active = False
        return settlements

    def legal_actions(self) -> list[PlayerAction]:
        hand = self.active_hand
        if hand is None:
            return []
        actions = [PlayerAction.HIT, PlayerAction.STAND]
        if len(hand.cards) == 2:
            if not hand.is_split_hand or self.rules.double_after_split:
                actions.append(PlayerAction.DOUBLE)
            if hand.can_split and len(self._player_hands) < self.rules.max_resplits + 1:
                if hand.cards[0].rank != "A" or not hand.is_split_hand or self.rules.resplit_aces:
                    actions.append(PlayerAction.SPLIT)
            if self.rules.surrender != SurrenderOption.NONE and not hand.actions:
                actions.append(PlayerAction.SURRENDER)
        if hand.is_split_aces and self.rules.split_aces_one_card_only:
            return [PlayerAction.STAND]
        return actions

    def play_full_hand_using_strategy(
        self,
        strategy_callback: Callable[["GameEngine", Hand, list[PlayerAction]], PlayerAction | tuple[PlayerAction, dict[str, Any]]],
        bet_amount: int | float | None = None,
    ) -> list[dict[str, Any]]:
        self.deal_initial_hand(bet_amount=bet_amount)

        if self._insurance_offer_open:
            response = strategy_callback(self, self._player_hands[0], [PlayerAction.TAKE_INSURANCE, PlayerAction.DECLINE_INSURANCE])
            if isinstance(response, tuple):
                action, params = response
            else:
                action, params = response, {}
            self.play_player_action(0, action, params)

        while self.active_hand and not self._dealer_has_blackjack:
            options = self.legal_actions()
            response = strategy_callback(self, self.active_hand, options)
            if isinstance(response, tuple):
                action, params = response
            else:
                action, params = response, {}
            if action not in options:
                raise ValueError(f"strategy returned illegal action: {action}")
            self.play_player_action(0, action, params)

        return self.resolve_dealer_and_settle()
