from __future__ import annotations

from src.game.models import EffectCard, EffectKind, ProposalCard, Season


_SEASON_MAP = {
    "P": Season.SPRING,
    "S": Season.SUMMER,
    "A": Season.AUTUMN,
    "W": Season.WINTER,
}


def _seq(code: str) -> tuple[Season, ...]:
    return tuple(_SEASON_MAP[ch] for ch in code)


PROPOSAL_CARDS: tuple[ProposalCard, ...] = (
    ProposalCard("Winter Solstice", _seq("WWP"), _seq("WWWW")),
    ProposalCard("Winter Awake", _seq("WWP"), _seq("WPSS")),
    ProposalCard("Winter in Chorus", _seq("WPS"), _seq("WWWA")),
    ProposalCard("Winter All-Aglow", _seq("WWW"), _seq("PPAA")),
    ProposalCard("Winter in Harmony", _seq("WPS"), _seq("WWPP")),
    ProposalCard("Spring Equinox", _seq("PPS"), _seq("PPPP")),
    ProposalCard("Spring-At-The-Door", _seq("PPS"), _seq("PSWW")),
    ProposalCard("Spring In Quiet", _seq("PPP"), _seq("SSWW")),
    ProposalCard("Spring Overflowing", _seq("PSA"), _seq("PPSS")),
    ProposalCard("Spring In Bloom", _seq("PSA"), _seq("PPPW")),
    ProposalCard("Autumn Equinox", _seq("AAW"), _seq("AAAA")),
    ProposalCard("Autumn In Flight", _seq("AAA"), _seq("WWPP")),
    ProposalCard("Autumn In Memory", _seq("AWP"), _seq("AAWW")),
    ProposalCard("Autumn In Mourning", _seq("AAW"), _seq("AWPP")),
    ProposalCard("Autumn In Vain", _seq("AWP"), _seq("AAAW")),
    ProposalCard("Summer Solstice", _seq("SSA"), _seq("SSSS")),
    ProposalCard("Summer Singing", _seq("SAW"), _seq("SSAA")),
    ProposalCard("Summer Bursting", _seq("SSS"), _seq("AAPP")),
    ProposalCard("Summer Waking", _seq("SAW"), _seq("SSSP")),
    ProposalCard("Summer in Glory", _seq("SSA"), _seq("SAWW")),
)


_EFFECT_DESCRIPTIONS = {
    "Clairvoyant": "Proposal deck is face-up and visible to all players.",
    "Shotgun": "Token 1 player can break ties.",
    "Flea Market": "Players can trade other players' promise tokens.",
    "Highway Robbery": "Each player takes 1 promise token from another player.",
    "Jubilee": "All promise tokens return to their owners.",
    "Secret Santa": "Each player gives 1 promise token to another player.",
    "Transformation": "Players may transform promise tokens into tokens from different players.",
}


EFFECT_CARDS: tuple[EffectCard, ...] = (
    EffectCard("Clairvoyant", EffectKind.TOGGLE, _EFFECT_DESCRIPTIONS["Clairvoyant"]),
    EffectCard("Shotgun", EffectKind.TOGGLE, _EFFECT_DESCRIPTIONS["Shotgun"]),
    EffectCard("Flea Market", EffectKind.TOGGLE, _EFFECT_DESCRIPTIONS["Flea Market"]),
    EffectCard("Highway Robbery", EffectKind.EVENT, _EFFECT_DESCRIPTIONS["Highway Robbery"]),
    EffectCard("Jubilee", EffectKind.EVENT, _EFFECT_DESCRIPTIONS["Jubilee"]),
    EffectCard("Secret Santa", EffectKind.EVENT, _EFFECT_DESCRIPTIONS["Secret Santa"]),
    EffectCard("Transformation", EffectKind.EVENT, _EFFECT_DESCRIPTIONS["Transformation"]),
    EffectCard("Null 1", EffectKind.NULL, "No effect."),
    EffectCard("Null 2", EffectKind.NULL, "No effect."),
    EffectCard("Null 3", EffectKind.NULL, "No effect."),
    EffectCard("Null 4", EffectKind.NULL, "No effect."),
    EffectCard("Null 5", EffectKind.NULL, "No effect."),
    EffectCard("Null 6", EffectKind.NULL, "No effect."),
    EffectCard("Null 7", EffectKind.NULL, "No effect."),
    EffectCard("Null 8", EffectKind.NULL, "No effect."),
)
