from __future__ import annotations

from src.config.settings import SimulationConfig
from src.game.engine import RulesEngine
from src.game.models import Character, Phase


def _engine() -> RulesEngine:
    engine = RulesEngine(SimulationConfig(max_rounds=2, seed=7, negotiation_word_cap=5))
    engine.start_round()
    return engine


def test_vote_token_three_must_be_first() -> None:
    engine = _engine()
    assert engine.state.phase == Phase.NEGOTIATION

    assert not engine.take_token(Character.CARMICHAEL, 1)
    assert engine.take_token(Character.CARMICHAEL, 3)
    assert engine.take_token(Character.QUINCY, 1)


def test_negotiation_word_cap_mutes_player() -> None:
    engine = _engine()

    kept, muted = engine.record_utterance(Character.CARMICHAEL, "one two three four five six", binding_allowed=True)
    assert kept == "one two three four five"
    assert muted

    kept_2, muted_2 = engine.record_utterance(Character.CARMICHAEL, "extra words", binding_allowed=True)
    assert kept_2 == ""
    assert muted_2


def test_voting_order_and_vote_changes() -> None:
    engine = _engine()
    engine.take_token(Character.CARMICHAEL, 3)
    engine.take_token(Character.QUINCY, 1)
    engine.take_token(Character.MEDICI, 2)
    engine.take_token(Character.DAMBROSIO, 4)
    engine.enter_voting_phase()

    assert engine.cast_vote(Character.QUINCY, 0)
    assert engine.cast_vote(Character.MEDICI, 1)
    assert engine.cast_vote(Character.CARMICHAEL, 1)
    assert engine.cast_vote(Character.DAMBROSIO, 1)

    # Quincy holds one Medici token to enable method 1.
    engine.state.holdings[Character.QUINCY][Character.MEDICI] = 1
    engine.state.spendable_holdings[Character.QUINCY][Character.MEDICI] = 1
    assert engine.change_vote_using_target_token(Character.QUINCY, Character.MEDICI, 0)
    assert engine.state.votes[Character.MEDICI] == 0


def test_newly_received_promise_tokens_are_not_spendable_until_next_round() -> None:
    engine = _engine()
    engine.take_token(Character.CARMICHAEL, 3)
    engine.take_token(Character.QUINCY, 1)
    engine.take_token(Character.MEDICI, 2)
    engine.take_token(Character.DAMBROSIO, 4)
    engine.enter_voting_phase()

    assert engine.cast_vote(Character.QUINCY, 0)
    assert engine.cast_vote(Character.MEDICI, 1)
    assert engine.cast_vote(Character.CARMICHAEL, 1)
    assert engine.cast_vote(Character.DAMBROSIO, 1)

    engine.state.holdings[Character.QUINCY][Character.MEDICI] = 1
    engine.state.spendable_holdings[Character.QUINCY][Character.MEDICI] = 1
    assert engine.change_vote_using_target_token(Character.QUINCY, Character.MEDICI, 0)

    # Medici received their own token back this round, but it is not spendable until next round.
    assert not engine.change_vote_using_target_token(Character.MEDICI, Character.QUINCY, 1)


def test_shotgun_breaks_tie() -> None:
    engine = _engine()
    engine.state.active_toggles.add("Shotgun")
    engine.take_token(Character.CARMICHAEL, 3)
    engine.take_token(Character.QUINCY, 1)
    engine.take_token(Character.MEDICI, 2)
    engine.take_token(Character.DAMBROSIO, 4)
    engine.enter_voting_phase()

    assert engine.cast_vote(Character.QUINCY, 1)  # token 1 vote decides tie
    assert engine.cast_vote(Character.MEDICI, 0)
    assert engine.cast_vote(Character.CARMICHAEL, 0)
    assert engine.cast_vote(Character.DAMBROSIO, 1)

    result = engine.resolve_round()
    assert result.passed_proposal_index == 1


def test_export_public_state_includes_holdings() -> None:
    engine = _engine()
    state = engine.export_public_state()
    holdings = state.get("holdings")
    assert isinstance(holdings, dict)
    assert holdings["Carmichael"]["Carmichael"] == 5
    assert holdings["Quincy"]["Quincy"] == 5


def test_referee_can_force_existing_vote_only() -> None:
    engine = _engine()
    engine.take_token(Character.CARMICHAEL, 3)
    engine.take_token(Character.QUINCY, 1)
    engine.take_token(Character.MEDICI, 2)
    engine.take_token(Character.DAMBROSIO, 4)
    engine.enter_voting_phase()

    assert engine.cast_vote(Character.QUINCY, 0)
    assert engine.force_vote_by_referee(Character.QUINCY, 1)
    assert engine.state.votes[Character.QUINCY] == 1
    assert not engine.force_vote_by_referee(Character.CARMICHAEL, 1)
