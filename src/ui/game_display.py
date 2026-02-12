from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.game.cards import PROPOSAL_CARDS


CHARACTER_STYLES: dict[str, str] = {
    "Carmichael": "green",
    "Medici": "red",
    "Quincy": "orange1",
    "D'Ambrosio": "blue",
    "Referee": "bright_cyan",
}
CHARACTER_ORDER: tuple[str, ...] = ("Carmichael", "Quincy", "Medici", "D'Ambrosio")
SENDER_EMOJI: dict[str, str] = {
    "Carmichael": "🤖",
    "Quincy": "🎩",
    "Medici": "🎨",
    "D'Ambrosio": "🧠",
    "Referee": "⚖️",
}
TOKEN_DOT = "●"
EVENT_PREFIX = "__EVENT__::"

PROPOSAL_TYPES: dict[str, str] = {
    "Winter Solstice": "max",
    "Winter in Chorus": "spread",
    "Winter All-Aglow": "wild",
    "Winter in Harmony": "rivalry",
    "Winter Awake": "upset",
    "Spring Equinox": "max",
    "Spring In Bloom": "spread",
    "Spring In Quiet": "wild",
    "Spring Overflowing": "rivalry",
    "Spring-At-The-Door": "upset",
    "Autumn Equinox": "max",
    "Autumn In Vain": "spread",
    "Autumn In Flight": "wild",
    "Autumn In Memory": "rivalry",
    "Autumn In Mourning": "upset",
    "Summer Solstice": "max",
    "Summer Waking": "spread",
    "Summer Bursting": "wild",
    "Summer Singing": "rivalry",
    "Summer in Glory": "upset",
}

PROPOSAL_PATTERNS: dict[str, tuple[str, str]] = {
    card.name: (
        " ".join(
            {
                "spring": "🌱",
                "summer": "☀️",
                "autumn": "🍂",
                "winter": "❄️",
            }.get(season.value, "?")
            for season in card.majority
        ),
        " ".join(
            {
                "spring": "🌱",
                "summer": "☀️",
                "autumn": "🍂",
                "winter": "❄️",
            }.get(season.value, "?")
            for season in card.consensus
        ),
    )
    for card in PROPOSAL_CARDS
}


@dataclass
class GameDisplay:
    max_lines: int = 20
    history_lines: int = 500
    chat_lines: list[str] = field(default_factory=list)
    ruling_lines: list[str] = field(default_factory=list)
    event_lines: list[str] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)

    def add_chat(self, line: str) -> None:
        self.chat_lines.append(line)
        self.chat_lines = self.chat_lines[-self.history_lines :]

    def add_ruling(self, line: str) -> None:
        self.ruling_lines.append(line)
        self.ruling_lines = self.ruling_lines[-self.history_lines :]

    def add_event(self, line: str) -> None:
        self.event_lines.append(line)
        self.event_lines = self.event_lines[-self.history_lines :]
        self.chat_lines.append(f"{EVENT_PREFIX}{line}")
        self.chat_lines = self.chat_lines[-self.history_lines :]

    def set_state(self, state: dict[str, Any]) -> None:
        self.state_snapshot = state

    def _style_character_names(self, content: str) -> Text:
        styled = Text(content)
        for name, style in CHARACTER_STYLES.items():
            styled.highlight_words([name], style=style, case_sensitive=True)
        return styled

    def _pane_lines(self, pane: str) -> list[str]:
        if pane == "chat":
            return self.chat_lines
        if pane == "rulings":
            return self.ruling_lines
        if pane == "events":
            return self.event_lines
        if pane == "state":
            return self._state_lines()
        if pane == "usage":
            return self._usage_lines()
        return []

    def _format_sender_line(self, line: str) -> Text:
        raw = line.strip()
        if ":" not in raw:
            return self._style_character_names(raw)
        sender, message = raw.split(":", 1)
        sender = sender.strip()
        if sender not in CHARACTER_STYLES and sender != "Referee":
            return self._style_character_names(raw)
        message = message.lstrip()
        emoji = SENDER_EMOJI.get(sender, "•")
        sender_style = CHARACTER_STYLES.get(sender, "white")
        text = Text()
        text.append(f"{emoji} ")
        text.append(sender, style=sender_style)
        text.append(": ")
        text.append(message)
        return text

    def _render_lines_as_text(self, pane: str, add_blank_between_messages: bool = False) -> Text:
        lines = self._pane_lines(pane)[-self.max_lines :]
        if not lines:
            return Text("No data yet")

        output = Text()
        for index, line in enumerate(lines):
            output.append(self._format_sender_line(line))
            if add_blank_between_messages:
                output.append("\n\n" if index < len(lines) - 1 else "")
            elif index < len(lines) - 1:
                output.append("\n")
        return output

    def _event_style(self, content: str) -> str:
        lower = content.lower()
        if any(word in lower for word in ("failed", "error", "timeout", "timed out")):
            return "bold red"
        if any(word in lower for word in ("warning", "deadlock")):
            return "bold yellow"
        if any(word in lower for word in ("complete", "ready", "started")):
            return "bold bright_cyan"
        return "cyan"

    def _render_chat_view(self) -> Group | Text:
        lines = self.chat_lines[-self.max_lines :]
        if not lines:
            return Text("No data yet")

        chunks: list[Any] = []
        for index, line in enumerate(lines):
            if line.startswith(EVENT_PREFIX):
                content = line[len(EVENT_PREFIX) :].strip()
                event_text = Text(content, style=self._event_style(content))
                chunks.append(Align.center(event_text))
            else:
                chunks.append(self._format_sender_line(line))

            if index < len(lines) - 1:
                chunks.append(Text(""))
        return Group(*chunks)

    def _state_lines(self) -> list[str]:
        round_number = self.state_snapshot.get("round", "-")
        phase = str(self.state_snapshot.get("phase", "-")).upper()
        proposals = self.state_snapshot.get("proposals", [])
        effects_raw = self.state_snapshot.get("effects", {})
        effects: dict[int, dict[str, str]] = {}
        if isinstance(effects_raw, dict):
            for key, value in effects_raw.items():
                try:
                    index = int(key)
                except Exception:
                    continue
                effects[index] = value if isinstance(value, dict) else {}

        votes = self.state_snapshot.get("votes", {}) if isinstance(self.state_snapshot.get("votes", {}), dict) else {}
        assignments_raw = self.state_snapshot.get("token_assignments", {})
        assignments: dict[str, int] = {}
        if isinstance(assignments_raw, dict):
            for token, player in assignments_raw.items():
                if isinstance(player, str):
                    try:
                        assignments[player] = int(token)
                    except Exception:
                        continue
        vote_changes = self.state_snapshot.get("vote_changes", {}) if isinstance(self.state_snapshot.get("vote_changes", {}), dict) else {}
        bells = self.state_snapshot.get("bells", {}) if isinstance(self.state_snapshot.get("bells", {}), dict) else {}
        toggles = self.state_snapshot.get("toggles", []) if isinstance(self.state_snapshot.get("toggles", []), list) else []
        word_counts = self.state_snapshot.get("word_counts", {}) if isinstance(self.state_snapshot.get("word_counts", {}), dict) else {}

        def _bar(value: int) -> str:
            return "#" * max(0, min(value, 14))

        season_order = ("spring", "summer", "autumn", "winter")
        lines: list[str] = []
        lines.append(f"ROUND {round_number} | PHASE {phase}")
        lines.append("=" * 48)
        lines.append("")

        lines.append("PROPOSAL BOARD")
        if isinstance(proposals, list) and proposals:
            for index, proposal in enumerate(proposals):
                name = str(proposal)
                p_type = PROPOSAL_TYPES.get(name, "unknown")
                majority_pattern, consensus_pattern = PROPOSAL_PATTERNS.get(name, ("---", "----"))
                effect_info = effects.get(index, {})
                majority_effect = str(effect_info.get("majority", "-"))
                consensus_effect = str(effect_info.get("consensus", "-"))

                lines.append(f"P{index}  {name}  [{p_type}]")
                lines.append(f"   majority  {majority_pattern}  | fx: {majority_effect}")
                lines.append(f"   consensus {consensus_pattern} | fx: {consensus_effect}")
                if index < len(proposals) - 1:
                    lines.append("")
        else:
            lines.append("No proposals visible.")

        lines.append("")
        lines.append("VOTES + TURN ORDER")
        for player in CHARACTER_ORDER:
            token = assignments.get(player)
            token_text = str(token) if token is not None else "-"
            vote_value = votes.get(player)
            vote_text = f"P{vote_value}" if isinstance(vote_value, int) else "-"
            flips = int(vote_changes.get(player, 0)) if player in vote_changes else 0
            lines.append(f"{player:11} token:{token_text:>2}  vote:{vote_text:>3}  flips:{flips}")

        lines.append("")
        lines.append("BELLS TRACKER")
        for season in season_order:
            value = int(bells.get(season, 0))
            lines.append(f"{season.title():7} {value:>2}  {_bar(value)}")

        lines.append("")
        lines.append("ACTIVE TOGGLES")
        if toggles:
            lines.append(", ".join(str(toggle) for toggle in toggles))
        else:
            lines.append("None")

        lines.append("")
        lines.append("NEGOTIATION WORD COUNTS")
        for player in CHARACTER_ORDER:
            lines.append(f"{player:11} {int(word_counts.get(player, 0))}")

        return lines

    def _render_state_text(self) -> Text:
        lines = self._state_lines()
        output = Text()
        for index, line in enumerate(lines):
            output.append(self._style_character_names(line))
            if index < len(lines) - 1:
                output.append("\n")

        holdings = self.state_snapshot.get("holdings", {})
        output.append("\n\nPromise Tokens (by holder, circle color = token owner)\n")
        for holder in CHARACTER_ORDER:
            holder_style = CHARACTER_STYLES.get(holder, "white")
            row = Text()
            row.append(f"{holder}: ", style=holder_style)
            owned = holdings.get(holder, {}) if isinstance(holdings, dict) else {}
            total = 0
            for owner in CHARACTER_ORDER:
                count = int(owned.get(owner, 0))
                total += count
                if count <= 0:
                    continue
                row.append(TOKEN_DOT * count, style=CHARACTER_STYLES.get(owner, "white"))
                row.append(" ")
            if total == 0:
                row.append("(none)")
            output.append(row)
            output.append("\n")

        legend = Text("Legend: ")
        for owner in CHARACTER_ORDER:
            legend.append(TOKEN_DOT, style=CHARACTER_STYLES.get(owner, "white"))
            legend.append(f" {owner}  ")
        output.append(legend)
        return output

    def _usage_lines(self) -> list[str]:
        usage = self.state_snapshot.get("llm_usage", {})
        tokens_round = usage.get("tokens_round", {}) if isinstance(usage, dict) else {}
        tokens_total = usage.get("tokens_total", {}) if isinstance(usage, dict) else {}
        requests_round = int(usage.get("requests_round", 0)) if isinstance(usage, dict) else 0
        requests_total = int(usage.get("requests_total", 0)) if isinstance(usage, dict) else 0

        lines = [
            f"requests: round={requests_round} total={requests_total}",
            f"input_tokens: round={int(tokens_round.get('input_tokens', 0))} total={int(tokens_total.get('input_tokens', 0))}",
            f"output_tokens: round={int(tokens_round.get('output_tokens', 0))} total={int(tokens_total.get('output_tokens', 0))}",
            f"total_tokens: round={int(tokens_round.get('total_tokens', 0))} total={int(tokens_total.get('total_tokens', 0))}",
            "",
            "By Agent",
        ]

        by_actor_round = usage.get("by_actor_round", {}) if isinstance(usage, dict) else {}
        by_actor_total = usage.get("by_actor_total", {}) if isinstance(usage, dict) else {}
        req_by_actor_round = usage.get("requests_by_actor_round", {}) if isinstance(usage, dict) else {}
        req_by_actor_total = usage.get("requests_by_actor_total", {}) if isinstance(usage, dict) else {}

        for actor in (*CHARACTER_ORDER, "Referee"):
            round_tokens = int(by_actor_round.get(actor, {}).get("total_tokens", 0))
            total_tokens = int(by_actor_total.get(actor, {}).get("total_tokens", 0))
            round_reqs = int(req_by_actor_round.get(actor, 0))
            total_reqs = int(req_by_actor_total.get(actor, 0))
            lines.append(
                f"{actor}: r_tok={round_tokens} t_tok={total_tokens} r_req={round_reqs} t_req={total_reqs}"
            )
        return lines

    def _scratchpad_lines(self) -> list[str]:
        raw = self.state_snapshot.get("scratchpads_view", {})
        scratchpads = raw if isinstance(raw, dict) else {}
        lines: list[str] = []
        for actor in (*CHARACTER_ORDER, "Referee"):
            text = str(scratchpads.get(actor, "")).strip()
            lines.append(f"{actor}")
            if text:
                for chunk in text.splitlines()[-4:]:
                    lines.append(f"  {chunk[:140]}")
            else:
                lines.append("  (empty)")
            lines.append("")
        return lines

    def _render_holdings_table(self) -> Table:
        holdings = self.state_snapshot.get("holdings", {})
        table = Table(title="Promise Holdings", show_header=True, box=None, pad_edge=False)
        table.add_column("Holder")
        for owner in CHARACTER_ORDER:
            table.add_column(owner, justify="right")

        for holder in CHARACTER_ORDER:
            row: list[str | Text] = [self._style_character_names(holder)]
            owned = holdings.get(holder, {}) if isinstance(holdings, dict) else {}
            for owner in CHARACTER_ORDER:
                row.append(str(int(owned.get(owner, 0))))
            table.add_row(*row)
        return table

    def _render_usage_panel(self) -> Group:
        usage = self.state_snapshot.get("llm_usage", {})
        tokens_round = usage.get("tokens_round", {}) if isinstance(usage, dict) else {}
        tokens_total = usage.get("tokens_total", {}) if isinstance(usage, dict) else {}
        requests_round = int(usage.get("requests_round", 0)) if isinstance(usage, dict) else 0
        requests_total = int(usage.get("requests_total", 0)) if isinstance(usage, dict) else 0

        summary = Table(title="Token Totals", show_header=True, box=None, pad_edge=False)
        summary.add_column("Metric")
        summary.add_column("Round", justify="right")
        summary.add_column("Total", justify="right")
        summary.add_row("Requests", str(requests_round), str(requests_total))
        summary.add_row(
            "Input",
            str(int(tokens_round.get("input_tokens", 0))),
            str(int(tokens_total.get("input_tokens", 0))),
        )
        summary.add_row(
            "Output",
            str(int(tokens_round.get("output_tokens", 0))),
            str(int(tokens_total.get("output_tokens", 0))),
        )
        summary.add_row(
            "Total",
            str(int(tokens_round.get("total_tokens", 0))),
            str(int(tokens_total.get("total_tokens", 0))),
        )

        by_actor_round = usage.get("by_actor_round", {}) if isinstance(usage, dict) else {}
        by_actor_total = usage.get("by_actor_total", {}) if isinstance(usage, dict) else {}
        req_by_actor_round = usage.get("requests_by_actor_round", {}) if isinstance(usage, dict) else {}
        req_by_actor_total = usage.get("requests_by_actor_total", {}) if isinstance(usage, dict) else {}

        actor_table = Table(title="By Agent", show_header=True, box=None, pad_edge=False)
        actor_table.add_column("Agent")
        actor_table.add_column("Round Tok", justify="right")
        actor_table.add_column("Total Tok", justify="right")
        actor_table.add_column("R Req", justify="right")
        actor_table.add_column("T Req", justify="right")
        for actor in (*CHARACTER_ORDER, "Referee"):
            round_tokens = int(by_actor_round.get(actor, {}).get("total_tokens", 0))
            total_tokens = int(by_actor_total.get(actor, {}).get("total_tokens", 0))
            round_reqs = int(req_by_actor_round.get(actor, 0))
            total_reqs = int(req_by_actor_total.get(actor, 0))
            actor_table.add_row(
                self._style_character_names(actor),
                str(round_tokens),
                str(total_tokens),
                str(round_reqs),
                str(total_reqs),
            )

        return Group(summary, actor_table)

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="top", ratio=2),
            Layout(name="bottom", ratio=1),
        )
        layout["top"].split_row(
            Layout(name="chat", ratio=3),
            Layout(name="scratchpads", ratio=2),
        )
        layout["bottom"].split_row(
            Layout(name="rulings", ratio=2),
            Layout(name="state", ratio=4),
            Layout(name="usage", ratio=2),
        )

        chat_text = self._render_chat_view()
        rulings_text = self._render_lines_as_text("rulings")
        state_text = self._render_state_text()
        usage_text = self._render_lines_as_text("usage")
        scratchpad_text = self._style_character_names("\n".join(self._scratchpad_lines()) or "No scratchpads yet")

        layout["chat"].update(Panel(chat_text, title="Public Negotiation / Voting Chat"))
        layout["scratchpads"].update(Panel(scratchpad_text, title="Agent Scratchpads"))
        layout["rulings"].update(Panel(rulings_text, title="Referee Rulings"))
        layout["state"].update(Panel(state_text, title="Game State"))
        layout["usage"].update(Panel(usage_text, title="LLM Usage"))
        return layout
