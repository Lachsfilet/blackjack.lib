from __future__ import annotations

import random
from dataclasses import dataclass

from .cards import TEN_VALUE, card_rank
from .solver import PerfectEVSolver, SolverDecision
from .state import GameState


class Agent:
    name: str

    def choose_action(self, state: GameState, legal_actions: tuple[str, ...]) -> str:
        raise NotImplementedError

    def choose_bet_units(self, _state: GameState | None = None) -> int:
        return 1

    def observe_round(self, _settlements: list[dict], _state: GameState) -> None:
        return


@dataclass(slots=True)
class RandomLegalAgent(Agent):
    seed: int = 0
    name: str = "random"

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose_action(self, state: GameState, legal_actions: tuple[str, ...]) -> str:
        del state
        return self._rng.choice(list(legal_actions))


@dataclass(slots=True)
class BasicStrategyAgent(Agent):
    name: str = "basic"

    def choose_action(self, state: GameState, legal_actions: tuple[str, ...]) -> str:
        if state.insurance_offered:
            return "decline_insurance"
        if state.active_hand_index is None:
            raise ValueError("terminal state")
        hand = state.player_hands[state.active_hand_index]
        dealer_rank = card_rank(state.dealer_upcard)

        if "surrender" in legal_actions and len(hand.cards) == 2:
            if hand.total == 16 and dealer_rank in {"9", "10", "A", "J", "Q", "K"}:
                return "surrender"
            if hand.total == 15 and dealer_rank == "10":
                return "surrender"

        if "split" in legal_actions and len(hand.cards) == 2:
            pair = card_rank(hand.cards[0])
            if pair in {"A", "8"}:
                return "split"
            if pair in {"10", "J", "Q", "K", "5"}:
                pass
            elif pair == "9" and dealer_rank in {"2", "3", "4", "5", "6", "8", "9"}:
                return "split"
            elif pair == "7" and dealer_rank in {"2", "3", "4", "5", "6", "7"}:
                return "split"
            elif pair == "6" and dealer_rank in {"2", "3", "4", "5", "6"}:
                return "split"
            elif pair == "4" and dealer_rank in {"5", "6"}:
                return "split"
            elif pair in {"2", "3"} and dealer_rank in {"2", "3", "4", "5", "6", "7"}:
                return "split"

        if hand.is_soft and len(hand.cards) == 2 and "double" in legal_actions:
            if hand.total in {13, 14} and dealer_rank in {"5", "6"}:
                return "double"
            if hand.total in {15, 16} and dealer_rank in {"4", "5", "6"}:
                return "double"
            if hand.total == 17 and dealer_rank in {"3", "4", "5", "6"}:
                return "double"
            if hand.total == 18 and dealer_rank in {"3", "4", "5", "6"}:
                return "double"

        if "double" in legal_actions and len(hand.cards) == 2:
            if hand.total == 11:
                return "double"
            if hand.total == 10 and dealer_rank not in {"10", "A", "J", "Q", "K"}:
                return "double"
            if hand.total == 9 and dealer_rank in {"3", "4", "5", "6"}:
                return "double"

        if hand.is_soft:
            if hand.total <= 17:
                return "hit"
            if hand.total == 18 and dealer_rank in {"9", "10", "A", "J", "Q", "K"}:
                return "hit"
            return "stand"

        if hand.total <= 11:
            return "hit"
        if hand.total == 12:
            return "stand" if dealer_rank in {"4", "5", "6"} else "hit"
        if 13 <= hand.total <= 16:
            return "stand" if dealer_rank in {"2", "3", "4", "5", "6"} else "hit"
        return "stand"


@dataclass(slots=True)
class PerfectAgent(Agent):
    solver: PerfectEVSolver
    name: str = "perfect"
    last_decision: SolverDecision | None = None

    def choose_action(self, state: GameState, legal_actions: tuple[str, ...]) -> str:
        decision = self.solver.choose_action(state)
        self.last_decision = decision
        if decision.action not in legal_actions:
            return legal_actions[0]
        return decision.action


@dataclass(slots=True)
class _CountingAgent(BasicStrategyAgent):
    running_count: float = 0.0
    true_count: float = 0.0
    name: str = "counting"

    def observe_round(self, settlements: list[dict], state: GameState) -> None:
        cards: list[str] = []
        for row in settlements:
            cards.extend(row["player_cards"])
            cards.extend(row["dealer_final_cards"])
        for card in cards:
            self.running_count += self._tag(card_rank(card))
        decks_remaining = max(state.shoe_remaining / 52.0, 0.25)
        self.true_count = self.running_count / decks_remaining

    def choose_bet_units(self, _state: GameState | None = None) -> int:
        if self.true_count <= 1:
            return 1
        return min(1 + int(self.true_count), 20)

    def choose_action(self, state: GameState, legal_actions: tuple[str, ...]) -> str:
        if state.insurance_offered:
            return "take_insurance" if self.true_count >= 3 else "decline_insurance"
        return super().choose_action(state, legal_actions)

    def _tag(self, rank: str) -> float:
        raise NotImplementedError


@dataclass(slots=True)
class HiLoAgent(_CountingAgent):
    name: str = "hilo"

    def _tag(self, rank: str) -> float:
        if rank in {"2", "3", "4", "5", "6"}:
            return 1
        if rank in {"10", "J", "Q", "K", "A"}:
            return -1
        return 0


@dataclass(slots=True)
class OmegaIISideCountAgent(_CountingAgent):
    ace_side_count: int = 0
    name: str = "omega2"

    def _tag(self, rank: str) -> float:
        if rank in {"4", "5", "6"}:
            return 2
        if rank in {"2", "3", "7"}:
            return 1
        if rank == "9":
            return -1
        if rank in TEN_VALUE:
            return -2
        if rank == "A":
            self.ace_side_count += 1
            return 0
        return 0

    def choose_bet_units(self, _state: GameState | None = None) -> int:
        edge = self.true_count + (self.ace_side_count * 0.1)
        if edge <= 1:
            return 1
        return min(1 + int(edge), 30)


def build_agent(name: str, solver: PerfectEVSolver | None = None, seed: int = 0) -> Agent:
    key = name.lower()
    if key == "perfect":
        if solver is None:
            raise ValueError("perfect agent requires solver")
        return PerfectAgent(solver=solver)
    if key == "random":
        return RandomLegalAgent(seed=seed)
    if key == "basic":
        return BasicStrategyAgent()
    if key == "hilo":
        return HiLoAgent()
    if key in {"omega2", "omegaii"}:
        return OmegaIISideCountAgent()
    raise ValueError(f"unknown agent: {name}")
