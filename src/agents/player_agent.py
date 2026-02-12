from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.game.models import Character


CHARACTER_PERSONAS = {
    Character.CARMICHAEL: "You are Carmichael (green robot), prioritize Winter strongly, Spring moderately, avoid Summer.",
    Character.QUINCY: "You are Quincy (orange elder with bowtie), prioritize Autumn strongly, Winter moderately, avoid Spring.",
    Character.MEDICI: "You are Medici (red cat), prioritize Summer strongly, Autumn moderately, avoid Winter.",
    Character.DAMBROSIO: "You are D'Ambrosio (blue long-haired strategist), prioritize Spring strongly, Summer moderately, avoid Autumn.",
}

INTERESTS_BRIEF = (
    "Known character interests (public, common knowledge):\n"
    "- Carmichael: +2 Winter, +1 Spring, -1 Summer\n"
    "- Quincy: +2 Autumn, +1 Winter, -1 Spring\n"
    "- Medici: +2 Summer, +1 Autumn, -1 Winter\n"
    "- D'Ambrosio: +2 Spring, +1 Summer, -1 Autumn\n"
    "Assume all players already know this. Do not spend Round 1 repeating introductions unless strategically useful."
)


def _load_strategy_brief() -> str:
    strategy_path = Path(__file__).resolve().parents[2] / "STRATEGY.md"
    try:
        text = strategy_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    return f"\n\nStrategic guidance:\n{text}"


STRATEGY_BRIEF = _load_strategy_brief()


NEGOTIATION_TOOLS: list[dict[str, Any]] = [
    {
        "toolSpec": {
            "name": "say_public",
            "description": "Send a public negotiation message without taking a vote token.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": ["message"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "take_vote_token",
            "description": "Take a vote token in negotiation. Optionally include a public message.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "token": {"type": "integer", "enum": [1, 2, 3, 4]},
                        "message": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": ["token"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "no_action",
            "description": "Do nothing this turn. May include a short reason.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": [],
                }
            },
        }
    },
]


VOTING_TOOLS: list[dict[str, Any]] = [
    {
        "toolSpec": {
            "name": "cast_vote",
            "description": "Cast your vote for one proposal. Optionally include a short public message.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "proposal_index": {"type": "integer", "enum": [0, 1]},
                        "message": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": ["proposal_index"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "no_action",
            "description": "Forfeit this action and do nothing.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": [],
                }
            },
        }
    },
]


VOTE_CHANGE_TOOLS: list[dict[str, Any]] = [
    {
        "toolSpec": {
            "name": "use_target_token",
            "description": "Use one target-owned token you hold to change target vote.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "new_vote": {"type": "integer", "enum": [0, 1]},
                        "message": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": ["new_vote"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "force_with_three_tokens",
            "description": "Give target 3 of your own tokens to force target vote change.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "new_vote": {"type": "integer", "enum": [0, 1]},
                        "message": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": ["new_vote"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "no_action",
            "description": "Do not change the target vote.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "private_note": {"type": "string"},
                    },
                    "required": [],
                }
            },
        }
    },
]


@dataclass
class PlayerAgent(BaseAgent):
    character: Character
    negotiation_word_cap: int = 500
    use_strategy_doc: bool = True

    async def negotiation_action(self, state: dict[str, Any], transcript_tail: list[str], scratchpad: str) -> dict[str, Any]:
        system_prompt = self._system_prompt()
        legal_tokens = self._legal_negotiation_tokens(state)
        user_prompt = f"""
Current public state:
{state}

Recent public transcript:
{transcript_tail}

Your private scratchpad (persist this across rounds):
{scratchpad}

You are in NEGOTIATION phase.
Use exactly one tool call now.
Rules reminders:
- {self.negotiation_word_cap}-word cap for your negotiation speech in this round; if you hit it, you are muted.
- Agreements made before voting are binding and cannot be broken unless all parties explicitly void them.
- Once you take a vote token, you cannot make NEW binding agreements.
- Vote token 3 must be taken first.
- Your legal vote-token options right now: {legal_tokens if legal_tokens else "none"}.
- If no legal vote token is available, do not call take_vote_token.
- Use the optional private_note field in your tool input for private planning memory; private_note is never public.
""".strip()
        result = await self.llm.converse_with_tools(
            system_prompt,
            user_prompt,
            tools=NEGOTIATION_TOOLS,
            tool_choice="any",
        )

        tool = self._first_tool_call(result.tool_calls)
        if tool is None:
            utterance = self._sanitize_text(result.text)
            data = {
                "utterance": utterance,
                "attempt_take_token": None,
                "scratchpad": scratchpad,
                "_parse_warning": "no_tool_call_returned",
                "_control_action": "fallback_text",
            }
        else:
            name = tool["name"]
            payload = tool["input"] if isinstance(tool["input"], dict) else {}
            private_note = self._extract_private_note(payload)
            if name == "take_vote_token":
                token = payload.get("token")
                attempt = int(token) if isinstance(token, int) else None
                utterance = self._sanitize_text(str(payload.get("message", "")))
                data = {
                    "utterance": utterance,
                    "attempt_take_token": attempt,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "take_vote_token",
                }
            elif name == "say_public":
                utterance = self._sanitize_text(str(payload.get("message", "")))
                inferred_attempt = self._infer_explicit_take_token(utterance)
                data = {
                    "utterance": utterance,
                    "attempt_take_token": inferred_attempt,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "say_public",
                }
            else:
                reason = self._sanitize_text(str(payload.get("reason", "")))
                data = {
                    "utterance": "",
                    "attempt_take_token": None,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "no_action",
                    "_control_reason": reason,
                }

        data["_prompt"] = {"system": system_prompt, "user": user_prompt, "tools": NEGOTIATION_TOOLS}
        data["_raw_text"] = result.text
        data["_raw_response"] = result.raw_response
        data["_attempts"] = result.attempts
        data["_tool_calls"] = result.tool_calls
        return data

    async def voting_action(
        self,
        state: dict[str, Any],
        transcript_tail: list[str],
        scratchpad: str,
        token_number: int,
    ) -> dict[str, Any]:
        system_prompt = self._system_prompt()
        user_prompt = f"""
Current public state:
{state}

Recent public transcript:
{transcript_tail}

Your private scratchpad:
{scratchpad}

You hold vote token {token_number}. Voting order is 1,2,3,4.
Use exactly one tool call now.
Use the optional private_note field in your tool input for private planning memory; private_note is never public.
""".strip()
        result = await self.llm.converse_with_tools(
            system_prompt,
            user_prompt,
            tools=VOTING_TOOLS,
            tool_choice="any",
        )

        tool = self._first_tool_call(result.tool_calls)
        if tool is None:
            utterance = self._sanitize_text(result.text)
            data = {
                "utterance": utterance,
                "vote": 0,
                "scratchpad": scratchpad,
                "_parse_warning": "no_tool_call_returned",
                "_control_action": "fallback_text",
            }
        else:
            payload = tool["input"] if isinstance(tool["input"], dict) else {}
            private_note = self._extract_private_note(payload)
            if tool["name"] == "cast_vote":
                proposal = payload.get("proposal_index")
                vote = int(proposal) if isinstance(proposal, int) and proposal in (0, 1) else 0
                utterance = self._sanitize_text(str(payload.get("message", "")))
                data = {
                    "utterance": utterance,
                    "vote": vote,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "cast_vote",
                }
            else:
                reason = self._sanitize_text(str(payload.get("reason", "")))
                data = {
                    "utterance": "",
                    "vote": 0,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "no_action",
                    "_control_reason": reason,
                }

        data["_prompt"] = {"system": system_prompt, "user": user_prompt, "tools": VOTING_TOOLS}
        data["_raw_text"] = result.text
        data["_raw_response"] = result.raw_response
        data["_attempts"] = result.attempts
        data["_tool_calls"] = result.tool_calls
        return data

    async def vote_change_action(
        self,
        state: dict[str, Any],
        transcript_tail: list[str],
        scratchpad: str,
        target_player: Character,
    ) -> dict[str, Any]:
        system_prompt = self._system_prompt()
        user_prompt = f"""
Current public state:
{state}

Recent public transcript:
{transcript_tail}

Your private scratchpad:
{scratchpad}

A vote-change window is open for target voter: {target_player.value}.
Use exactly one tool call now.
Use the optional private_note field in your tool input for private planning memory; private_note is never public.
""".strip()
        result = await self.llm.converse_with_tools(
            system_prompt,
            user_prompt,
            tools=VOTE_CHANGE_TOOLS,
            tool_choice="any",
        )

        tool = self._first_tool_call(result.tool_calls)
        if tool is None:
            utterance = self._sanitize_text(result.text)
            data = {
                "utterance": utterance,
                "action": "none",
                "new_vote": None,
                "scratchpad": scratchpad,
                "_parse_warning": "no_tool_call_returned",
                "_control_action": "fallback_text",
            }
        else:
            payload = tool["input"] if isinstance(tool["input"], dict) else {}
            private_note = self._extract_private_note(payload)
            if tool["name"] in {"use_target_token", "force_with_three_tokens"}:
                new_vote = payload.get("new_vote")
                vote = int(new_vote) if isinstance(new_vote, int) and new_vote in (0, 1) else None
                utterance = self._sanitize_text(str(payload.get("message", "")))
                data = {
                    "utterance": utterance,
                    "action": tool["name"],
                    "new_vote": vote,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": tool["name"],
                }
            else:
                reason = self._sanitize_text(str(payload.get("reason", "")))
                data = {
                    "utterance": "",
                    "action": "none",
                    "new_vote": None,
                    "scratchpad": self._next_scratchpad(scratchpad, private_note),
                    "_control_action": "no_action",
                    "_control_reason": reason,
                }

        data["_prompt"] = {"system": system_prompt, "user": user_prompt, "tools": VOTE_CHANGE_TOOLS}
        data["_raw_text"] = result.text
        data["_raw_response"] = result.raw_response
        data["_attempts"] = result.attempts
        data["_tool_calls"] = result.tool_calls
        return data

    def _system_prompt(self) -> str:
        strategy_block = STRATEGY_BRIEF if self.use_strategy_doc else ""
        return (
            "You are a game-playing AI in Rat Scramble. "
            f"{CHARACTER_PERSONAS[self.character]} "
            "Use tools for actions. Keep messages concise and strategic. "
            "The referee can override actions that violate binding contracts."
            f"\n\n{INTERESTS_BRIEF}"
            f"{strategy_block}"
        )

    def _sanitize_text(self, text: str) -> str:
        return " ".join((text or "").strip().split())[:500]

    def _extract_private_note(self, payload: dict[str, Any]) -> str:
        return self._sanitize_text(str(payload.get("private_note", "")))

    def _first_tool_call(self, tool_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not tool_calls:
            return None
        call = tool_calls[0]
        name = str(call.get("name", "")).strip()
        payload = call.get("input", {})
        return {"name": name, "input": payload}

    def _infer_explicit_take_token(self, utterance: str) -> int | None:
        match = re.search(r"\b(?:i|we)\s+(?:will\s+)?(?:take|grab|pick)\s+(?:vote\s+)?token\s*([1-4])\b", utterance, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _legal_negotiation_tokens(self, state: dict[str, Any]) -> list[int]:
        assignments_raw = state.get("token_assignments", {})
        if not isinstance(assignments_raw, dict):
            return []

        assigned_tokens: set[int] = set()
        assigned_players: set[str] = set()
        for token_raw, player_raw in assignments_raw.items():
            try:
                assigned_tokens.add(int(token_raw))
            except Exception:
                continue
            if isinstance(player_raw, str):
                assigned_players.add(player_raw)

        if self.character.value in assigned_players:
            return []
        if 3 not in assigned_tokens:
            return [3]
        return [token for token in (4, 2, 1) if token not in assigned_tokens]

    def _next_scratchpad(self, scratchpad: str, private_note: str) -> str:
        if not private_note:
            return scratchpad
        update = f"Private note: {private_note}"
        combined = f"{scratchpad}\n{update}".strip()
        return combined[-4000:]
