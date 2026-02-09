from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config.settings import SimulationConfig


def load_simulation_config(path: str = "config.yml") -> SimulationConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError("config.yml must contain a top-level mapping")

    normalized = _normalize_config_values(data)
    return SimulationConfig(**normalized)


def _normalize_config_values(data: dict[str, Any]) -> dict[str, Any]:
    values = dict(data)
    if "request_retry_backoff_seconds" in values:
        raw = values["request_retry_backoff_seconds"]
        if isinstance(raw, list):
            values["request_retry_backoff_seconds"] = tuple(float(x) for x in raw)
    if "agent_models" in values:
        raw_models = values["agent_models"]
        if raw_models is None:
            values["agent_models"] = {}
        elif isinstance(raw_models, dict):
            normalized_models: dict[str, str] = {}
            for key, value in raw_models.items():
                if value is None:
                    continue
                normalized_models[str(key)] = str(value).strip()
            values["agent_models"] = normalized_models
        else:
            raise ValueError("config.yml field 'agent_models' must be a mapping of agent name to model ID")
    return values
