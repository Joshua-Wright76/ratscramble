from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationConfig:
    aws_profile: str | None = None
    region: str = "us-west-2"
    model_id: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    max_rounds: int = 10
    win_threshold: int = 15
    seed: int = 42
    temperature: float = 0.6
    max_tokens: int = 450
    negotiation_word_cap: int = 500
    round_timeout_seconds: int = 600
    negotiation_deadlock_seconds: int = 20
    no_action_cooldown_base_seconds: float = 0.25
    no_action_cooldown_max_seconds: float = 2.0
    request_retries: int = 2
    request_retry_backoff_seconds: tuple[float, float] = (1.0, 2.0)
    llm_request_timeout_seconds: int = 45
    log_root: str = "logs"
    e2e_rounds: int = 3
    agent_models: dict[str, str] = field(default_factory=dict)
