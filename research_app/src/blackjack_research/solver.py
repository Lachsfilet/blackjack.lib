from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

from .cards import RANKS, TEN_VALUE, card_rank, card_value, hand_total_from_ranks
from .config import RuleConfig
from .state import GameState


class SolverDecision(NamedTuple):
    action: str
    action_evs: dict[str, float]


@dataclass(slots=True)
class _Node:
    hand: tuple[str, ...]
    dealer: tuple[str, ...]
    shoe: tuple[int, ...]
    can_double: bool
    can_split: bool
    can_surrender: bool
    split_depth: int
    split_hand: bool


class PerfectEVSolver:
    """Composition-dependent EV evaluator with split approximation."""

    def __init__(self, config: RuleConfig) -> None:
        self.config = config

    def choose_action(self, state: GameState) -> SolverDecision:
        legal = set(state.legal_actions)
        if not legal:
            raise ValueError("no legal action available")
        if state.insurance_offered:
            hole = state.dealer_hole_card
            take = hole is not None and card_rank(hole) in TEN_VALUE
            evs = {
                "take_insurance": 1.0 if take else -0.5,
                "decline_insurance": 0.0 if take else 0.0,
            }
            return SolverDecision("take_insurance" if take else "decline_insurance", evs)

        if state.active_hand_index is None:
            raise ValueError("terminal state")
        hand = state.player_hands[state.active_hand_index]
        dealer_cards = [state.dealer_upcard]
        if state.dealer_hole_card:
            dealer_cards.append(state.dealer_hole_card)

        node = _Node(
            hand=tuple(card_rank(c) for c in hand.cards),
            dealer=tuple(card_rank(c) for c in dealer_cards),
            shoe=tuple(state.shoe_composition[r] for r in RANKS),
            can_double="double" in legal,
            can_split="split" in legal,
            can_surrender="surrender" in legal,
            split_depth=0,
            split_hand=hand.is_split_hand,
        )
        action_evs = self._evaluate_node(node)
        filtered = {k: v for k, v in action_evs.items() if k in legal}
        action = max(filtered.items(), key=lambda item: item[1])[0]
        return SolverDecision(action, filtered)

    def _evaluate_node(self, node: _Node) -> dict[str, float]:
        return self._eval_cached(
            node.hand,
            node.dealer,
            node.shoe,
            node.can_double,
            node.can_split,
            node.can_surrender,
            node.split_depth,
            node.split_hand,
        )

    @lru_cache(maxsize=300000)
    def _eval_cached(
        self,
        hand: tuple[str, ...],
        dealer: tuple[str, ...],
        shoe: tuple[int, ...],
        can_double: bool,
        can_split: bool,
        can_surrender: bool,
        split_depth: int,
        split_hand: bool,
    ) -> dict[str, float]:
        total, _ = hand_total_from_ranks(hand)
        if total > 21:
            return {"stand": -1.0}

        evs: dict[str, float] = {"stand": self._stand_ev(hand, dealer, shoe, split_hand)}
        evs["hit"] = self._hit_ev(hand, dealer, shoe, split_depth, split_hand)

        if can_double and len(hand) == 2:
            evs["double"] = self._double_ev(hand, dealer, shoe, split_hand)
        if can_surrender and len(hand) == 2:
            evs["surrender"] = -0.5
        if can_split and len(hand) == 2 and hand[0] == hand[1] and split_depth < self.config.max_resplits:
            evs["split"] = self._split_ev(hand, dealer, shoe, split_depth)
        return evs

    def _stand_ev(self, hand: tuple[str, ...], dealer: tuple[str, ...], shoe: tuple[int, ...], split_hand: bool) -> float:
        player_total, _ = hand_total_from_ranks(hand)
        if player_total > 21:
            return -1.0
        if len(hand) == 2 and player_total == 21 and not split_hand:
            player_blackjack = True
        else:
            player_blackjack = False

        dealer_probs = self._dealer_probs(dealer, shoe)
        ev = 0.0
        for outcome, prob in dealer_probs.items():
            if outcome == "bust":
                ev += prob
                continue
            dealer_total = int(outcome)
            dealer_blackjack = len(dealer) == 2 and dealer_total == 21
            if dealer_blackjack and player_blackjack:
                ev += 0.0
            elif dealer_blackjack:
                ev -= prob
            elif player_blackjack:
                ev += prob * (self.config.blackjack_payout[0] / self.config.blackjack_payout[1])
            elif player_total > dealer_total:
                ev += prob
            elif player_total < dealer_total:
                ev -= prob
        return ev

    def _hit_ev(self, hand: tuple[str, ...], dealer: tuple[str, ...], shoe: tuple[int, ...], split_depth: int, split_hand: bool) -> float:
        total_cards = sum(shoe)
        if total_cards <= 0:
            return self._stand_ev(hand, dealer, shoe, split_hand)

        ev = 0.0
        for i, rank in enumerate(RANKS):
            count = shoe[i]
            if count <= 0:
                continue
            prob = count / total_cards
            next_shoe = list(shoe)
            next_shoe[i] -= 1
            next_hand = tuple((*hand, rank))
            t, _ = hand_total_from_ranks(next_hand)
            if t > 21:
                ev += prob * -1.0
                continue
            next_evs = self._eval_cached(
                next_hand,
                dealer,
                tuple(next_shoe),
                False,
                False,
                False,
                split_depth,
                split_hand,
            )
            ev += prob * max(next_evs.values())
        return ev

    def _double_ev(self, hand: tuple[str, ...], dealer: tuple[str, ...], shoe: tuple[int, ...], split_hand: bool) -> float:
        total_cards = sum(shoe)
        if total_cards <= 0:
            return 2.0 * self._stand_ev(hand, dealer, shoe, split_hand)
        ev = 0.0
        for i, rank in enumerate(RANKS):
            count = shoe[i]
            if count <= 0:
                continue
            prob = count / total_cards
            next_shoe = list(shoe)
            next_shoe[i] -= 1
            next_hand = tuple((*hand, rank))
            t, _ = hand_total_from_ranks(next_hand)
            if t > 21:
                ev += prob * -2.0
            else:
                ev += prob * (2.0 * self._stand_ev(next_hand, dealer, tuple(next_shoe), split_hand))
        return ev

    def _split_ev(self, hand: tuple[str, ...], dealer: tuple[str, ...], shoe: tuple[int, ...], split_depth: int) -> float:
        rank = hand[0]
        if rank == "A" and self.config.decks >= 1 and self.config.resplit_aces is False:
            pass
        total_cards = sum(shoe)
        if total_cards <= 1:
            return -1.0

        ev = 0.0
        for i, rank1 in enumerate(RANKS):
            c1 = shoe[i]
            if c1 <= 0:
                continue
            p1 = c1 / total_cards
            shoe1 = list(shoe)
            shoe1[i] -= 1
            rem = total_cards - 1
            for j, rank2 in enumerate(RANKS):
                c2 = shoe1[j]
                if c2 <= 0:
                    continue
                p2 = c2 / rem
                shoe2 = list(shoe1)
                shoe2[j] -= 1

                first = (rank, rank1)
                second = (rank, rank2)

                if rank == "A":
                    e1 = self._stand_ev(first, dealer, tuple(shoe2), True)
                    e2 = self._stand_ev(second, dealer, tuple(shoe2), True)
                else:
                    e1 = max(
                        self._eval_cached(first, dealer, tuple(shoe2), True, first[0] == first[1], False, split_depth + 1, True).values()
                    )
                    e2 = max(
                        self._eval_cached(second, dealer, tuple(shoe2), True, second[0] == second[1], False, split_depth + 1, True).values()
                    )
                ev += p1 * p2 * (e1 + e2)
        return ev

    @lru_cache(maxsize=500000)
    def _dealer_probs(self, dealer: tuple[str, ...], shoe: tuple[int, ...]) -> dict[str, float]:
        total, soft = hand_total_from_ranks(dealer)
        if total > 21:
            return {"bust": 1.0}
        if total > 17:
            return {str(total): 1.0}
        if total == 17 and (not soft or not self.config.dealer_hits_soft_17):
            return {"17": 1.0}

        cards = sum(shoe)
        if cards <= 0:
            return {str(total): 1.0}

        out: dict[str, float] = {}
        for i, rank in enumerate(RANKS):
            count = shoe[i]
            if count <= 0:
                continue
            prob = count / cards
            nxt_shoe = list(shoe)
            nxt_shoe[i] -= 1
            nxt = tuple((*dealer, rank))
            nxt_probs = self._dealer_probs(nxt, tuple(nxt_shoe))
            for key, value in nxt_probs.items():
                out[key] = out.get(key, 0.0) + prob * value
        return out
