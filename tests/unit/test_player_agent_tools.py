from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.agents.player_agent import PlayerAgent
from src.game.models import Character
from src.llm.bedrock_client import LLMResult


@dataclass
class FakeLLM:
    result: LLMResult

    async def converse_with_tools(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self.result


def _result(tool_calls, text=""):
    return LLMResult(
        text=text,
        raw_response={"ok": True},
        attempts=1,
        stop_reason="tool_use",
        tool_calls=tool_calls,
    )


@pytest.mark.asyncio
async def test_negotiation_tool_take_token_maps_to_action() -> None:
    agent = PlayerAgent(
        name="Carmichael",
        llm=FakeLLM(
            _result(
                [
                    {
                        "name": "take_vote_token",
                        "input": {"token": 3, "message": "I take token 3 now."},
                        "tool_use_id": "x",
                    }
                ]
            )
        ),
        character=Character.CARMICHAEL,
    )

    action = await agent.negotiation_action(state={}, transcript_tail=[], scratchpad="")

    assert action["attempt_take_token"] == 3
    assert "token 3" in action["utterance"].lower()


@pytest.mark.asyncio
async def test_voting_tool_cast_vote_maps_to_vote() -> None:
    agent = PlayerAgent(
        name="Quincy",
        llm=FakeLLM(
            _result(
                [
                    {
                        "name": "cast_vote",
                        "input": {"proposal_index": 1, "message": "I vote for proposal 1."},
                        "tool_use_id": "y",
                    }
                ]
            )
        ),
        character=Character.QUINCY,
    )

    action = await agent.voting_action(state={}, transcript_tail=[], scratchpad="", token_number=1)

    assert action["vote"] == 1
    assert "proposal 1" in action["utterance"].lower()


@pytest.mark.asyncio
async def test_negotiation_no_action_is_silent() -> None:
    agent = PlayerAgent(
        name="Medici",
        llm=FakeLLM(
            _result(
                [
                    {
                        "name": "no_action",
                        "input": {"reason": "waiting for others"},
                        "tool_use_id": "z",
                    }
                ]
            )
        ),
        character=Character.MEDICI,
    )

    action = await agent.negotiation_action(state={}, transcript_tail=[], scratchpad="")

    assert action["attempt_take_token"] is None
    assert action["utterance"] == ""
    assert action["_control_action"] == "no_action"


@pytest.mark.asyncio
async def test_say_public_explicit_take_token_infers_attempt() -> None:
    agent = PlayerAgent(
        name="D'Ambrosio",
        llm=FakeLLM(
            _result(
                [
                    {
                        "name": "say_public",
                        "input": {"message": "I will take token 4 now and wait."},
                        "tool_use_id": "t",
                    }
                ]
            )
        ),
        character=Character.DAMBROSIO,
    )

    action = await agent.negotiation_action(state={}, transcript_tail=[], scratchpad="")

    assert action["attempt_take_token"] == 4
    assert action["_control_action"] == "say_public"


def test_legal_negotiation_tokens_from_state() -> None:
    agent = PlayerAgent(
        name="Carmichael",
        llm=FakeLLM(_result([])),
        character=Character.CARMICHAEL,
    )

    assert agent._legal_negotiation_tokens({"token_assignments": {}}) == [3]
    assert agent._legal_negotiation_tokens({"token_assignments": {"3": "Quincy", "4": "Medici"}}) == [2, 1]
    assert agent._legal_negotiation_tokens({"token_assignments": {"3": "Carmichael"}}) == []


def test_system_prompt_can_disable_strategy_doc() -> None:
    agent = PlayerAgent(
        name="Carmichael",
        llm=FakeLLM(_result([])),
        character=Character.CARMICHAEL,
        use_strategy_doc=False,
    )

    assert "Strategic guidance:" not in agent._system_prompt()


@pytest.mark.asyncio
async def test_negotiation_prompt_uses_configured_word_cap() -> None:
    agent = PlayerAgent(
        name="Carmichael",
        llm=FakeLLM(
            _result(
                [
                    {
                        "name": "no_action",
                        "input": {"reason": "waiting"},
                        "tool_use_id": "w",
                    }
                ]
            )
        ),
        character=Character.CARMICHAEL,
        negotiation_word_cap=321,
    )

    action = await agent.negotiation_action(state={}, transcript_tail=[], scratchpad="")
    prompt_text = action["_prompt"]["user"]

    assert "321-word cap" in prompt_text
