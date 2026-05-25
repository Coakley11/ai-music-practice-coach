"""Verified core song charts — reference harmony for renderer, backing, and practice.

One list item = one bar. Slash chords and extensions (D/F#, A7sus4, Am7b5) are preserved.
"""

from __future__ import annotations

from typing import Any

# --- Across the Universe (The Beatles) — written key D ---
# One list item = one bar (repeated chord = sustained harmonic rhythm).


def _hold(chord: str, bars: int) -> list[str]:
    return [chord] * max(1, int(bars))


_ACROSS_VERSE_PHRASE_A = (
    _hold("D", 1)
    + _hold("Bm", 1)
    + _hold("F#m", 2)
    + _hold("Em7", 2)
    + _hold("A", 1)
    + _hold("A7", 1)
)

_ACROSS_VERSE_PHRASE_B = (
    _hold("D", 1)
    + _hold("Bm", 1)
    + _hold("F#m", 2)
    + _hold("Em7", 2)
    + _hold("Gm", 2)
)

_ACROSS_VERSE = list(_ACROSS_VERSE_PHRASE_A + _ACROSS_VERSE_PHRASE_B)

_ACROSS_CHORUS = (
    _hold("D", 2)
    + _hold("A7sus4", 2)
    + _hold("A", 2)
    + _hold("A7", 2)
    + _hold("G", 2)
    + _hold("D", 2)
)

_ACROSS_OUTRO = _hold("D", 4)

_ACROSS_SECTION_ORDER: list[str] = [
    "Verse 1",
    "Chorus 1",
    "Verse 2",
    "Chorus 2",
    "Verse 3",
    "Chorus 3",
    "Outro",
]

_ACROSS_SECTIONS: dict[str, list[str]] = {
    "Verse 1": list(_ACROSS_VERSE),
    "Chorus 1": list(_ACROSS_CHORUS),
    "Verse 2": list(_ACROSS_VERSE),
    "Chorus 2": list(_ACROSS_CHORUS),
    "Verse 3": list(_ACROSS_VERSE),
    "Chorus 3": list(_ACROSS_CHORUS),
    "Outro": list(_ACROSS_OUTRO),
}

_ACROSS_BEGINNER: dict[str, list[str]] = {
    name: [c.replace("Em7", "Em").replace("A7sus4", "A7") for c in chords]
    for name, chords in _ACROSS_SECTIONS.items()
}

_ACROSS_LYRIC_CUES: dict[str, list[str]] = {
    "Verse 1": [
        "Words are flowing out like endless rain into a paper cup",
        "They slither wildly as they slip away across the universe",
        "Pools of sorrow, waves of joy are drifting through my opened mind",
        "Possessing and caressing me",
    ],
    "Chorus 1": [
        "Jai guru deva om",
        "Nothing's gonna change my world",
        "Nothing's gonna change my world",
    ],
    "Verse 2": [
        "Images of broken light which dance before me like a million eyes",
        "They call me on and on across the universe",
        "Thoughts meander like a restless wind inside a letterbox",
        "They tumble blindly as they make their way across the universe",
    ],
    "Chorus 2": [
        "Jai guru deva om",
        "Nothing's gonna change my world",
        "Nothing's gonna change my world",
    ],
    "Verse 3": [
        "Sounds of laughter, shades of life are ringing through my opened ears",
        "Inciting and inviting me",
        "Limitless undying love which shines around me like a million suns",
        "And calls me on and on across the universe",
    ],
    "Chorus 3": [
        "Jai guru deva om",
        "Nothing's gonna change my world",
        "Nothing's gonna change my world",
    ],
    "Outro": [
        "JAI",
        "GURU",
        "DEVA",
        "OM",
    ],
}

# --- Uptown Girl (Billy Joel) — written key D ---

_UPTOWN_INTRO = ["D", "Em", "D/F#", "G", "A"]

_UPTOWN_VERSE = [
    "D",
    "Em",
    "D/F#",
    "G",
    "A",
    "D",
    "Em",
    "D/F#",
    "G",
    "A",
]

_UPTOWN_INTERLUDE = ["F", "G", "E", "Am", "G"]

_UPTOWN_BRIDGE = [
    "Bb",
    "Gm",
    "Cm",
    "F",
    "Bb",
    "Gm",
    "Am7b5",
    "D7",
    "G",
    "Em",
    "Am",
    "A",
]

_UPTOWN_OUTRO = ["D", "Em", "D/F#", "G", "A", "D"]

_UPTOWN_SECTIONS: dict[str, list[str]] = {
    "Intro": list(_UPTOWN_INTRO),
    "Verse": list(_UPTOWN_VERSE),
    "Chorus": list(_UPTOWN_VERSE),
    "Interlude": list(_UPTOWN_INTERLUDE),
    "Bridge": list(_UPTOWN_BRIDGE),
    "Outro": list(_UPTOWN_OUTRO),
}

_UPTOWN_BEGINNER: dict[str, list[str]] = {
    "Intro": ["D", "Em", "D/F#", "G", "A"],
    "Verse": ["D", "Em", "D/F#", "G", "A", "D", "Em", "D/F#", "G", "A"],
    "Chorus": ["D", "Em", "D/F#", "G", "A", "D", "Em", "D/F#", "G", "A"],
    "Interlude": ["F", "G", "E", "Am", "G"],
    "Bridge": ["Bb", "Gm", "Cm", "F", "Bb", "Gm", "Am7b5", "D7", "G", "Em", "Am", "A"],
    "Outro": ["D", "Em", "D/F#", "G", "A", "D"],
}

_UPTOWN_LYRIC_CUES: dict[str, list[str]] = {
    "Intro": ["Oh oh oh oh oh oh oh", "Oh oh oh oh oh oh oh"],
    "Verse": [
        "Uptown girl — she's been living in her uptown world",
        "I bet she never had a back street guy",
        "I bet her mama never told her why — I'm gonna try for an",
    ],
    "Chorus": [
        "Uptown girl — you know I've seen her in her uptown world",
        "She's getting tired of her high class toys",
        "And all her presents from her uptown boys — she's got a choice",
    ],
    "Interlude": ["Oh oh oh oh oh oh oh oh oh", "Oh oh oh oh oh oh"],
    "Bridge": [
        "And when she's walking she's looking so fine",
        "And when she's talking she'll say that she's mine",
        "She'll say I'm not so tough just because I'm in love with an",
    ],
    "Outro": [
        "Uptown girl — she's my uptown girl",
        "You know I'm in love with an uptown girl",
    ],
}

VERIFIED_CORE_REFERENCE_KEYS: frozenset[tuple[str, str]] = frozenset(
    {
        ("Across the Universe", "The Beatles"),
        ("Uptown Girl", "Billy Joel"),
    }
)

_REFERENCE_BY_KEY: dict[tuple[str, str], dict[str, Any]] = {
    ("Across the Universe", "The Beatles"): {
        "key": "D",
        "genre": "Rock",
        "default_bpm": 92,
        "default_groove": "Ballad",
        "time_signature": "4/4",
        "sections": _ACROSS_SECTIONS,
        "section_order": list(_ACROSS_SECTION_ORDER),
        "beginner": _ACROSS_BEGINNER,
        "lyric_cues": _ACROSS_LYRIC_CUES,
        "guitar_tabs": {
            "D": "xx0232",
            "Bm": "x24432",
            "F#m": "244222",
            "Em7": "022030",
            "A": "x02220",
            "A7sus4": "x02030",
            "A7": "x02023",
            "G": "320003",
            "Gm": "355333",
        },
        "arrangement_notes": (
            "Verified core reference in D (~92 BPM). Form: "
            "**Verse 1 → Chorus 1 → Verse 2 → Chorus 2 → Verse 3 → Chorus 3 → Outro** "
            "(D major ×4). Verse: **D–Bm–F#m(2)–Em7(2)–A–A7**, repeat with **Gm(2)**. "
            "Chorus: **D(2)–A7sus4(2)–A(2)–A7(2)–G(2)–D(2)** then stops (12 bars). "
            "One chart bar = one playback bar."
        ),
    },
    ("Uptown Girl", "Billy Joel"): {
        "key": "D",
        "genre": "Pop",
        "default_bpm": 172,
        "sections": _UPTOWN_SECTIONS,
        "beginner": _UPTOWN_BEGINNER,
        "lyric_cues": _UPTOWN_LYRIC_CUES,
        "guitar_tabs": {
            "D": "xx0232",
            "Em": "022000",
            "D/F#": "2x0232",
            "G": "320003",
            "A": "x02220",
            "F": "133211",
            "E": "022100",
            "Am": "x02210",
            "Bb": "x13331",
            "Gm": "355333",
            "Cm": "x35543",
            "Am7b5": "x01010",
            "D7": "xx0212",
        },
        "arrangement_notes": (
            "Verified core reference in D: doo-wop pop with D/F# bass, "
            "bridge Am7b5–D7, and full slash-chord bass motion preserved."
        ),
    },
}


def is_verified_core_reference(title: str, artist: str) -> bool:
    return (title, artist) in VERIFIED_CORE_REFERENCE_KEYS


def reference_for(title: str, artist: str) -> dict[str, Any] | None:
    return _REFERENCE_BY_KEY.get((title, artist))


def chart_versions_for_reference(title: str, artist: str) -> dict[str, dict[str, list[str]]] | None:
    ref = reference_for(title, artist)
    if not ref:
        return None
    inter = ref["sections"]
    beg = ref.get("beginner") or inter
    return {
        "Beginner": beg,
        "Intermediate": inter,
        "Advanced": inter,
    }


def lyric_cues_for_reference(title: str, artist: str) -> dict[str, list[str]]:
    ref = reference_for(title, artist)
    if not ref:
        return {}
    return dict(ref.get("lyric_cues") or {})
