from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Phase(str, Enum):
    DEAL = "deal"
    NEGOTIATION = "negotiation"
    VOTING = "voting"
    RESOLUTION = "resolution"
    COMPLETE = "complete"


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class Character(str, Enum):
    CARMICHAEL = "Carmichael"
    QUINCY = "Quincy"
    MEDICI = "Medici"
    DAMBROSIO = "D'Ambrosio"


class OutcomeType(str, Enum):
    MAJORITY = "majority"
    CONSENSUS = "consensus"


class EffectKind(str, Enum):
    TOGGLE = "toggle"
    EVENT = "event"
    NULL = "null"


class ContractStatus(str, Enum):
    ACTIVE = "active"
    VOID = "void"
    FULFILLED = "fulfilled"
    BREACHED = "breached"


@dataclass
class ProposalCard:
    name: str
    majority: tuple[Season, ...]
    consensus: tuple[Season, ...]


@dataclass
class EffectCard:
    name: str
    kind: EffectKind
    description: str


@dataclass
class Contract:
    contract_id: str
    text: str
    parties: tuple[Character, ...]
    created_round: int
    status: ContractStatus = ContractStatus.ACTIVE
    notes: str = ""


@dataclass
class RoundResult:
    passed_proposal_index: int | None
    outcome_type: OutcomeType | None
    winning_votes: int
    applied_effect: str | None


@dataclass
class GameState:
    max_rounds: int
    round_number: int = 1
    phase: Phase = Phase.DEAL
    bells: dict[Season, int] = field(default_factory=lambda: {s: 0 for s in Season})
    token_assignments: dict[int, Character] = field(default_factory=dict)
    votes: dict[Character, int] = field(default_factory=dict)
    vote_changes: dict[Character, int] = field(default_factory=dict)
    voting_cursor: int = 0
    word_counts: dict[Character, int] = field(default_factory=dict)
    muted_players: set[Character] = field(default_factory=set)
    holdings: dict[Character, dict[Character, int]] = field(default_factory=dict)
    spendable_holdings: dict[Character, dict[Character, int]] = field(default_factory=dict)
    contracts: dict[str, Contract] = field(default_factory=dict)
    active_toggles: set[str] = field(default_factory=set)
    proposal_deck: list[ProposalCard] = field(default_factory=list)
    effect_deck: list[EffectCard] = field(default_factory=list)
    current_proposals: tuple[ProposalCard, ProposalCard] | None = None
    current_effects: dict[int, dict[OutcomeType, EffectCard]] = field(default_factory=dict)
    transcript: list[str] = field(default_factory=list)
    scratchpads: dict[Character, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


CHARACTER_ORDER: tuple[Character, ...] = (
    Character.CARMICHAEL,
    Character.QUINCY,
    Character.MEDICI,
    Character.DAMBROSIO,
)
