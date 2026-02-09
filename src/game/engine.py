from __future__ import annotations

import random
import time

from src.config.settings import SimulationConfig
from src.game.cards import EFFECT_CARDS, PROPOSAL_CARDS
from src.game.models import (
    CHARACTER_ORDER,
    Character,
    Contract,
    ContractStatus,
    EffectCard,
    EffectKind,
    GameState,
    OutcomeType,
    Phase,
    RoundResult,
    Season,
)


CHARACTER_INTERESTS: dict[Character, dict[int, Season]] = {
    Character.CARMICHAEL: {2: Season.WINTER, 1: Season.SPRING, -1: Season.SUMMER},
    Character.QUINCY: {2: Season.AUTUMN, 1: Season.WINTER, -1: Season.SPRING},
    Character.MEDICI: {2: Season.SUMMER, 1: Season.AUTUMN, -1: Season.WINTER},
    Character.DAMBROSIO: {2: Season.SPRING, 1: Season.SUMMER, -1: Season.AUTUMN},
}


class RulesEngine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.state = self._new_state()

    def _new_state(self) -> GameState:
        proposal_deck = list(PROPOSAL_CARDS)
        effect_deck = list(EFFECT_CARDS)
        self.rng.shuffle(proposal_deck)
        self.rng.shuffle(effect_deck)
        state = GameState(max_rounds=self.config.max_rounds)
        state.proposal_deck = proposal_deck
        state.effect_deck = effect_deck
        state.word_counts = {c: 0 for c in CHARACTER_ORDER}
        state.vote_changes = {c: 0 for c in CHARACTER_ORDER}
        state.holdings = {
            holder: {owner: (5 if holder == owner else 0) for owner in CHARACTER_ORDER}
            for holder in CHARACTER_ORDER
        }
        state.scratchpads = {c: "" for c in CHARACTER_ORDER}
        state.metadata = {
            "seed": self.config.seed,
            "started_at": time.time(),
            "round_started_at": None,
        }
        return state

    def start_round(self) -> None:
        if self.state.round_number > self.state.max_rounds:
            self.state.phase = Phase.COMPLETE
            return
        if len(self.state.proposal_deck) < 2:
            raise RuntimeError("Proposal deck exhausted before max rounds were completed")
        self.state.phase = Phase.DEAL
        p1 = self.state.proposal_deck.pop()
        p2 = self.state.proposal_deck.pop()
        self.state.current_proposals = (p1, p2)
        effects = [self._draw_effect() for _ in range(4)]
        self.state.current_effects = {
            0: {OutcomeType.MAJORITY: effects[0], OutcomeType.CONSENSUS: effects[1]},
            1: {OutcomeType.MAJORITY: effects[2], OutcomeType.CONSENSUS: effects[3]},
        }
        self.state.phase = Phase.NEGOTIATION
        self.state.token_assignments = {}
        self.state.votes = {}
        self.state.voting_cursor = 0
        self.state.vote_changes = {c: 0 for c in CHARACTER_ORDER}
        self.state.word_counts = {c: 0 for c in CHARACTER_ORDER}
        self.state.muted_players = set()
        self.state.metadata["round_started_at"] = time.time()

    def _draw_effect(self) -> EffectCard:
        if not self.state.effect_deck:
            self.state.effect_deck = list(EFFECT_CARDS)
            self.rng.shuffle(self.state.effect_deck)
        return self.state.effect_deck.pop()

    def record_utterance(self, player: Character, text: str, binding_allowed: bool) -> tuple[str, bool]:
        text = (text or "").strip()
        if not text:
            return "", player in self.state.muted_players
        if self.state.phase != Phase.NEGOTIATION:
            self.state.transcript.append(f"{player.value}: {text}")
            return text, player in self.state.muted_players

        current_words = self.state.word_counts[player]
        words = text.split()
        remaining = self.config.negotiation_word_cap - current_words
        if remaining <= 0:
            self.state.muted_players.add(player)
            return "", True
        kept_words = words[:remaining]
        kept_text = " ".join(kept_words)
        self.state.word_counts[player] += len(kept_words)
        if self.state.word_counts[player] >= self.config.negotiation_word_cap:
            self.state.muted_players.add(player)
        binding_tag = "[binding]" if binding_allowed else "[non-binding]"
        self.state.transcript.append(f"{player.value} {binding_tag}: {kept_text}")
        return kept_text, player in self.state.muted_players

    def can_take_token(self, player: Character, token: int) -> bool:
        if self.state.phase != Phase.NEGOTIATION:
            return False
        if token not in (1, 2, 3, 4):
            return False
        if token in self.state.token_assignments:
            return False
        if player in self.state.token_assignments.values():
            return False
        if token == 3:
            return True
        return 3 in self.state.token_assignments

    def take_token(self, player: Character, token: int) -> bool:
        if not self.can_take_token(player, token):
            return False
        self.state.token_assignments[token] = player
        self.state.transcript.append(f"{player.value} took vote token {token}")
        return True

    def all_tokens_taken(self) -> bool:
        return len(self.state.token_assignments) == 4

    def enter_voting_phase(self) -> None:
        self.state.phase = Phase.VOTING
        self.state.transcript.append("Voting phase begins")

    def cast_vote(self, player: Character, proposal_index: int) -> bool:
        if self.state.phase != Phase.VOTING:
            return False
        if proposal_index not in (0, 1):
            return False
        expected_token = [1, 2, 3, 4][self.state.voting_cursor]
        if self.state.token_assignments.get(expected_token) != player:
            return False
        self.state.votes[player] = proposal_index
        self.state.voting_cursor += 1
        return True

    def force_vote_by_referee(self, player: Character, proposal_index: int) -> bool:
        if self.state.phase != Phase.VOTING:
            return False
        if proposal_index not in (0, 1):
            return False
        if player not in self.state.votes:
            return False
        self.state.votes[player] = proposal_index
        return True

    def can_change_vote(self, target: Character) -> bool:
        return self.state.phase == Phase.VOTING and target in self.state.votes and self.state.vote_changes[target] < 2

    def change_vote_using_target_token(
        self,
        actor: Character,
        target: Character,
        new_proposal_index: int,
    ) -> bool:
        if not self.can_change_vote(target):
            return False
        if self.state.holdings[actor][target] <= 0:
            return False
        self.state.holdings[actor][target] -= 1
        self.state.holdings[target][target] += 1
        self.state.votes[target] = new_proposal_index
        self.state.vote_changes[target] += 1
        self.state.transcript.append(
            f"{actor.value} changed {target.value}'s vote using a {target.value} token"
        )
        return True

    def force_vote_change_with_three_tokens(
        self,
        actor: Character,
        target: Character,
        new_proposal_index: int,
    ) -> bool:
        if not self.can_change_vote(target):
            return False
        if self.state.holdings[actor][actor] < 3:
            return False
        self.state.holdings[actor][actor] -= 3
        self.state.holdings[target][actor] += 3
        self.state.votes[target] = new_proposal_index
        self.state.vote_changes[target] += 1
        self.state.transcript.append(
            f"{actor.value} forced {target.value}'s vote change by giving 3 own tokens"
        )
        return True

    def add_or_update_contract(self, contract: Contract) -> None:
        self.state.contracts[contract.contract_id] = contract

    def void_contract(self, contract_id: str, notes: str = "") -> None:
        if contract_id not in self.state.contracts:
            return
        contract = self.state.contracts[contract_id]
        contract.status = ContractStatus.VOID
        contract.notes = notes

    def resolve_round(self) -> RoundResult:
        self.state.phase = Phase.RESOLUTION
        vote_counts = {0: 0, 1: 0}
        for proposal in self.state.votes.values():
            vote_counts[proposal] += 1

        passed: int | None
        outcome: OutcomeType | None
        winning_votes = max(vote_counts.values()) if vote_counts else 0

        if vote_counts[0] == vote_counts[1]:
            if "Shotgun" in self.state.active_toggles and self.state.token_assignments.get(1) in self.state.votes:
                tie_break_player = self.state.token_assignments[1]
                passed = self.state.votes[tie_break_player]
                outcome = OutcomeType.MAJORITY
                winning_votes = 3
            else:
                passed = None
                outcome = None
        else:
            passed = 0 if vote_counts[0] > vote_counts[1] else 1
            outcome = OutcomeType.CONSENSUS if winning_votes == 4 else OutcomeType.MAJORITY

        applied_effect: str | None = None
        if passed is not None and outcome is not None:
            proposal = self.state.current_proposals[passed]
            seasons = proposal.consensus if outcome == OutcomeType.CONSENSUS else proposal.majority
            for season in seasons:
                self.state.bells[season] += 1
            effect = self.state.current_effects[passed][outcome]
            applied_effect = effect.name
            self._apply_effect(effect)

        # Effects are reshuffled each round.
        self.state.effect_deck = list(EFFECT_CARDS)
        self.rng.shuffle(self.state.effect_deck)

        result = RoundResult(
            passed_proposal_index=passed,
            outcome_type=outcome,
            winning_votes=winning_votes,
            applied_effect=applied_effect,
        )

        self.state.round_number += 1
        if self.state.round_number > self.state.max_rounds:
            self.state.phase = Phase.COMPLETE
        return result

    def _apply_effect(self, effect: EffectCard) -> None:
        if effect.kind == EffectKind.NULL:
            return
        if effect.kind == EffectKind.TOGGLE:
            if effect.name in self.state.active_toggles:
                self.state.active_toggles.remove(effect.name)
            else:
                self.state.active_toggles.add(effect.name)
            self.state.transcript.append(f"Toggle effect updated: {effect.name}")
            return

        if effect.name == "Highway Robbery":
            self._apply_highway_robbery()
        elif effect.name == "Jubilee":
            self._apply_jubilee()
        elif effect.name == "Secret Santa":
            self._apply_secret_santa()
        elif effect.name == "Transformation":
            # Transformation choices are delegated to agents/referee in future iterations.
            self.state.transcript.append("Transformation triggered (no-op in v1 automation)")

    def _apply_highway_robbery(self) -> None:
        for thief in CHARACTER_ORDER:
            possible_targets = [
                target
                for target in CHARACTER_ORDER
                if target != thief and sum(self.state.holdings[target].values()) > 0
            ]
            if not possible_targets:
                continue
            target = self.rng.choice(possible_targets)
            available_owners = [owner for owner, count in self.state.holdings[target].items() if count > 0]
            if not available_owners:
                continue
            owner = self.rng.choice(available_owners)
            self.state.holdings[target][owner] -= 1
            self.state.holdings[thief][owner] += 1

    def _apply_jubilee(self) -> None:
        self.state.holdings = {
            holder: {owner: (5 if holder == owner else 0) for owner in CHARACTER_ORDER}
            for holder in CHARACTER_ORDER
        }

    def _apply_secret_santa(self) -> None:
        for giver in CHARACTER_ORDER:
            if self.state.holdings[giver][giver] <= 0:
                continue
            recipients = [p for p in CHARACTER_ORDER if p != giver]
            recipient = self.rng.choice(recipients)
            self.state.holdings[giver][giver] -= 1
            self.state.holdings[recipient][giver] += 1

    def get_token_order(self) -> list[Character]:
        return [self.state.token_assignments[token] for token in [1, 2, 3, 4]]

    def force_remaining_tokens_seeded(self) -> list[tuple[Character, int]]:
        taken_players = set(self.state.token_assignments.values())
        remaining_players = [p for p in CHARACTER_ORDER if p not in taken_players]
        remaining_tokens = [t for t in [3, 4, 2, 1] if t not in self.state.token_assignments]
        assignments: list[tuple[Character, int]] = []
        for token in remaining_tokens:
            if token == 3:
                # 3 can always be taken first from remaining pool.
                pass
            if not remaining_players:
                break
            player = remaining_players.pop(0)
            if self.can_take_token(player, token):
                self.take_token(player, token)
                assignments.append((player, token))
        return assignments

    def score_players(self) -> dict[Character, int]:
        scores: dict[Character, int] = {}
        for character in CHARACTER_ORDER:
            interests = CHARACTER_INTERESTS[character]
            score = (
                2 * self.state.bells[interests[2]]
                + self.state.bells[interests[1]]
                - self.state.bells[interests[-1]]
            )
            scores[character] = score
        return scores

    def export_public_state(self) -> dict[str, object]:
        proposals = self.state.current_proposals or ()
        current_effects = {
            idx: {
                outcome.value: effect.name
                for outcome, effect in outcome_map.items()
            }
            for idx, outcome_map in self.state.current_effects.items()
        }
        return {
            "round": self.state.round_number,
            "phase": self.state.phase.value,
            "proposals": [p.name for p in proposals],
            "effects": current_effects,
            "bells": {season.value: count for season, count in self.state.bells.items()},
            "token_assignments": {str(k): v.value for k, v in self.state.token_assignments.items()},
            "votes": {k.value: v for k, v in self.state.votes.items()},
            "vote_changes": {k.value: v for k, v in self.state.vote_changes.items()},
            "holdings": {
                holder.value: {owner.value: count for owner, count in owned.items()}
                for holder, owned in self.state.holdings.items()
            },
            "toggles": sorted(self.state.active_toggles),
            "word_counts": {k.value: v for k, v in self.state.word_counts.items()},
            "contracts": {
                k: {
                    "text": c.text,
                    "parties": [p.value for p in c.parties],
                    "status": c.status.value,
                    "round": c.created_round,
                    "notes": c.notes,
                }
                for k, c in self.state.contracts.items()
            },
        }
