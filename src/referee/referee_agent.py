from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.base_agent import BaseAgent


@dataclass
class RefereeAgent(BaseAgent):
    async def evaluate_phase_change(
        self,
        from_phase: str,
        to_phase: str,
        state: dict[str, Any],
        transcript_tail: list[str],
        contracts: dict[str, Any],
    ) -> dict[str, Any]:
        system_prompt = (
            "You are the authoritative referee for Rat Scramble. "
            "Your rulings are final. "
            "Infer agreements from context. "
            "Agreements made before voting are binding. "
            "During voting, players cannot create NEW binding agreements. "
            "Binding agreements cannot be broken; enforce compliance whenever possible. "
            "Agreements can be voided only by explicit mutual agreement of all relevant parties. "
            "Return plain text rulings only. "
            "Do not return JSON."
        )
        user_prompt = f"""
Phase transition: {from_phase} -> {to_phase}

Current public state:
{state}

Recent transcript:
{transcript_tail}

Existing contracts:
{contracts}

Return plain text only, one ruling per line.
Guidance:
- Call out binding commitments you infer.
- State whether any commitment was breached or enforced.
- If vote state must be enforced, include a clear sentence like:
  "Final authoritative vote state: Quincy set to proposal 1."
""".strip()
        result = await self.llm.converse(system_prompt, user_prompt)
        rulings = self._split_rulings(result.text)
        data: dict[str, Any] = {"rulings": rulings}
        if not rulings and result.text.strip():
            data["rulings"] = [result.text.strip()[:500]]
            data["_parse_warning"] = "fallback_from_plaintext"
        data["_prompt"] = {"system": system_prompt, "user": user_prompt}
        data["_raw_text"] = result.text
        data["_raw_response"] = result.raw_response
        data["_attempts"] = result.attempts
        return data

    def _split_rulings(self, text: str) -> list[str]:
        lines: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            line = line.lstrip("-* ").strip()
            if line and line[0].isdigit():
                line = line.split(".", 1)[-1].strip()
            if line:
                lines.append(line[:500])
        return lines
