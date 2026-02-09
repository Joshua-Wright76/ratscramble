from __future__ import annotations

from src.config.settings import SimulationConfig
from src.game.models import Character
from src.game.orchestrator import SimulationOrchestrator


def test_orchestrator_applies_agent_model_overrides(tmp_path) -> None:
    cfg = SimulationConfig(
        max_rounds=1,
        seed=17,
        log_root=str(tmp_path),
        model_id="model-default-haiku",
        agent_models={
            "Carmichael": "model-sonnet",
            "Referee": "model-referee-sonnet",
        },
    )
    orchestrator = SimulationOrchestrator(cfg, visual=False)

    assert orchestrator.player_agents[Character.CARMICHAEL].llm.config.model_id == "model-sonnet"
    assert orchestrator.player_agents[Character.QUINCY].llm.config.model_id == "model-default-haiku"
    assert orchestrator.referee.llm.config.model_id == "model-referee-sonnet"


def test_usage_snapshot_accumulates_bedrock_token_counts(tmp_path) -> None:
    orchestrator = SimulationOrchestrator(
        SimulationConfig(max_rounds=1, seed=13, log_root=str(tmp_path)),
        visual=False,
    )
    usage = orchestrator._extract_usage_from_raw_response(
        {
            "usage": {
                "inputTokens": 101,
                "outputTokens": 9,
                "totalTokens": 110,
                "cacheReadInputTokens": 4,
                "cacheWriteInputTokens": 2,
            }
        }
    )
    orchestrator._accumulate_usage("Quincy", usage)
    snapshot = orchestrator._usage_snapshot()

    assert snapshot["tokens_total"]["input_tokens"] == 101
    assert snapshot["tokens_total"]["output_tokens"] == 9
    assert snapshot["tokens_total"]["total_tokens"] == 110
    assert snapshot["requests_total"] == 1
    assert snapshot["by_actor_total"]["Quincy"]["total_tokens"] == 110


def test_referee_ruling_json_blob_is_humanized(tmp_path) -> None:
    orchestrator = SimulationOrchestrator(
        SimulationConfig(max_rounds=1, seed=19, log_root=str(tmp_path)),
        visual=False,
    )
    lines = orchestrator._humanize_referee_rulings(
        {
            "rulings": [
                "```json\n"
                '{"rulings": ["Voting phase complete.", "No new binding agreements created."]}'
                "\n```"
            ]
        }
    )

    assert lines == ["Voting phase complete.", "No new binding agreements created."]


def test_infers_contract_from_referee_ruling_text(tmp_path) -> None:
    orchestrator = SimulationOrchestrator(
        SimulationConfig(max_rounds=1, seed=23, log_root=str(tmp_path)),
        visual=False,
    )
    orchestrator._infer_contracts_from_rulings(
        [
            "1. Carmichael committed to support Summer outcomes in Round 2 if Medici votes for Winter now."
        ]
    )

    assert len(orchestrator.engine.state.contracts) == 1
    contract = next(iter(orchestrator.engine.state.contracts.values()))
    assert "Carmichael committed to support Summer outcomes in Round 2" in contract.text
    party_names = {party.value for party in contract.parties}
    assert "Carmichael" in party_names
    assert "Medici" in party_names


def test_infers_vote_enforcement_from_referee_ruling_text(tmp_path) -> None:
    orchestrator = SimulationOrchestrator(
        SimulationConfig(max_rounds=1, seed=29, log_root=str(tmp_path)),
        visual=False,
    )
    engine = orchestrator.engine
    engine.start_round()
    engine.take_token(Character.CARMICHAEL, 3)
    engine.take_token(Character.QUINCY, 1)
    engine.take_token(Character.MEDICI, 2)
    engine.take_token(Character.DAMBROSIO, 4)
    engine.enter_voting_phase()
    assert engine.cast_vote(Character.QUINCY, 0)

    orchestrator._apply_inferred_referee_enforcement_from_rulings(
        "voting",
        "resolution",
        [
            "Final authoritative vote state: D'Ambrosio's last token-based vote change set Quincy to proposal 1."
        ],
    )

    assert engine.state.votes[Character.QUINCY] == 1
