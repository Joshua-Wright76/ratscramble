from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


CHARACTER_STYLES: dict[str, str] = {
    "Carmichael": "green",
    "Medici": "red",
    "Quincy": "orange1",
    "D'Ambrosio": "blue",
    "Referee": "bright_cyan",
}
CHARACTER_ORDER: tuple[str, ...] = ("Carmichael", "Quincy", "Medici", "D'Ambrosio")


@dataclass
class GameDisplay:
    max_lines: int = 20
    chat_lines: list[str] = field(default_factory=list)
    ruling_lines: list[str] = field(default_factory=list)
    event_lines: list[str] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)

    def add_chat(self, line: str) -> None:
        self.chat_lines.append(line)
        self.chat_lines = self.chat_lines[-self.max_lines :]

    def add_ruling(self, line: str) -> None:
        self.ruling_lines.append(line)
        self.ruling_lines = self.ruling_lines[-self.max_lines :]

    def add_event(self, line: str) -> None:
        self.event_lines.append(line)
        self.event_lines = self.event_lines[-self.max_lines :]

    def set_state(self, state: dict[str, Any]) -> None:
        self.state_snapshot = state

    def _style_character_names(self, content: str) -> Text:
        styled = Text(content)
        for name, style in CHARACTER_STYLES.items():
            styled.highlight_words([name], style=style, case_sensitive=True)
        return styled

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
            Layout(name="state", ratio=2),
        )
        layout["bottom"].split_row(
            Layout(name="rulings", ratio=2),
            Layout(name="events", ratio=2),
            Layout(name="usage", ratio=2),
        )

        chat_text = self._style_character_names("\n".join(self.chat_lines) or "No chat yet")
        rulings_text = self._style_character_names("\n".join(self.ruling_lines) or "No rulings yet")
        events_text = self._style_character_names("\n".join(self.event_lines) or "No events yet")

        state_table = Table(show_header=False, box=None, pad_edge=False)
        for key in ("round", "phase", "proposals", "token_assignments", "votes", "bells", "toggles", "word_counts"):
            value = self.state_snapshot.get(key, "-")
            state_table.add_row(str(key), self._style_character_names(str(value)))

        layout["chat"].update(Panel(chat_text, title="Public Negotiation / Voting Chat"))
        layout["state"].update(Panel(Group(state_table, self._render_holdings_table()), title="Game State"))
        layout["rulings"].update(Panel(rulings_text, title="Referee Rulings"))
        layout["events"].update(Panel(events_text, title="Events"))
        layout["usage"].update(Panel(self._render_usage_panel(), title="LLM Usage"))
        return layout
