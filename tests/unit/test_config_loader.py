from __future__ import annotations

from pathlib import Path

from src.config.loader import load_simulation_config


def test_load_simulation_config_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
region: us-west-2
max_rounds: 7
win_threshold: 18
seed: 99
temperature: 0.55
strategy_doc_enabled: false
visual_step_delay_seconds: 0.4
request_retry_backoff_seconds: [0.5, 1.5]
agent_models:
  Carmichael: model-sonnet
  Referee: model-haiku
strategy_doc_players: [Carmichael, Quincy]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_simulation_config(str(config_path))

    assert cfg.region == "us-west-2"
    assert cfg.max_rounds == 7
    assert cfg.win_threshold == 18
    assert cfg.seed == 99
    assert cfg.temperature == 0.55
    assert cfg.strategy_doc_enabled is False
    assert cfg.visual_step_delay_seconds == 0.4
    assert cfg.request_retry_backoff_seconds == (0.5, 1.5)
    assert cfg.agent_models == {"Carmichael": "model-sonnet", "Referee": "model-haiku"}
    assert cfg.strategy_doc_players == ["Carmichael", "Quincy"]
