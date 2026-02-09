from __future__ import annotations

import os

import pytest

from src.agents.player_agent import PlayerAgent
from src.config.settings import SimulationConfig
from src.game.models import Character
from src.llm.bedrock_client import BedrockConverseClient
from src.llm.json_utils import extract_json_object


pytestmark = pytest.mark.bedrock



def _skip_if_not_enabled() -> None:
    if os.getenv("RUN_BEDROCK_TESTS") != "1":
        pytest.skip("Set RUN_BEDROCK_TESTS=1 to run live Bedrock tests")


@pytest.mark.asyncio
async def test_bedrock_converse_returns_json_text() -> None:
    _skip_if_not_enabled()
    cfg = SimulationConfig(max_rounds=1, max_tokens=120)
    client = BedrockConverseClient(cfg)

    result = await client.converse(
        "Return JSON only.",
        "Respond exactly as a JSON object with key ok=true",
        temperature=0.6,
        max_tokens=80,
    )
    obj = extract_json_object(result.text)
    assert "ok" in obj


@pytest.mark.asyncio
async def test_player_agent_negotiation_action_schema_live() -> None:
    _skip_if_not_enabled()
    cfg = SimulationConfig(max_rounds=1, max_tokens=200)
    client = BedrockConverseClient(cfg)
    agent = PlayerAgent(name="Carmichael", llm=client, character=Character.CARMICHAEL)

    response = await agent.negotiation_action(
        state={"round": 1, "phase": "negotiation", "proposals": ["A", "B"]},
        transcript_tail=["Quincy [binding]: I will vote proposal 0"],
        scratchpad="I need winter bells",
    )
    assert "utterance" in response
    assert "attempt_take_token" in response
    assert "scratchpad" in response
