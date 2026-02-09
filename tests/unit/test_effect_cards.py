from __future__ import annotations

from src.game.cards import EFFECT_CARDS


def test_gemini_season_removed_from_active_effect_deck() -> None:
    effect_names = {card.name for card in EFFECT_CARDS}
    assert "Gemini Season" not in effect_names
