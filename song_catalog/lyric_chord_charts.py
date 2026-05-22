"""Lyric-aligned chord charts (Ultimate Guitar layout) for select catalog songs."""

from __future__ import annotations

from typing import Any

from song_catalog.we_are_the_champions import (
    CHAMPIONS_ARRANGEMENT_NOTES,
    CHAMPIONS_GUITAR_TABS,
    CHAMPIONS_LYRIC_CHART,
    CHAMPIONS_SECTIONS,
)
from songs.lyric_chord_renderer import sections_from_lyric_chart

LyricSection = dict[str, Any]

_VERSE_WAITING = [
    {"chords": ["D", "Bm", "G", "D"]},
    {"chords": ["A", "Bm", "G", "D"]},
]

_WAITING_VERSE_1_LYRICS = [
    "Me and all my friends",
    "We're all misunderstood",
    "They say we stand for nothing and",
    "There's no way we ever could",
    "Now we see everything that's going wrong",
    "With the world and those who lead it",
    "We just feel like we don't have the means",
    "To rise above and beat it",
]

_WAITING_VERSE_2_LYRICS = [
    "It's not that we don't care, we just know that the fight ain't fair",
    "So we keep on waiting",
    "Waiting on the world to change",
    "One day our generation",
    "Is gonna rule the population",
    "When we unite ourselves",
    "We become a better nation",
    "And we're waiting on the world to change",
]

_WAITING_CHORUS_LINES = [
    {"chords": ["D", "Bm"], "lyrics": "And when you trust your television"},
    {"chords": ["G", "D"], "lyrics": "What you get is what you got"},
    {"chords": ["A", "Bm"], "lyrics": "'Cause when they own the information"},
    {"chords": ["G", "D"], "lyrics": "They can bend it all they want"},
    {"chords": ["D", "Em"], "lyrics": "That's why we're waiting"},
    {"chords": ["Bm", "Em7"], "lyrics": "Waiting on the world to change"},
    {"chords": ["A", "Bm"], "lyrics": "We keep on waiting"},
    {"chords": ["G", "D"], "lyrics": "Waiting on the world to change"},
]

WAITING_ON_THE_WORLD_CHART: list[LyricSection] = [
    {
        "section": "Verse 1",
        "progression_block": _VERSE_WAITING,
        "progression_repeat": 4,
        "lyrics": _WAITING_VERSE_1_LYRICS,
    },
    {
        "section": "Chorus",
        "lines": list(_WAITING_CHORUS_LINES),
    },
    {
        "section": "Verse 2",
        "progression_block": _VERSE_WAITING,
        "progression_repeat": 4,
        "lyrics": _WAITING_VERSE_2_LYRICS,
    },
    {
        "section": "Bridge",
        "lines": [
            {"chords": ["Dm7"], "lyrics": ""},
            {"chords": ["Dm7"], "lyrics": ""},
            {"chords": ["Dm7"], "lyrics": ""},
            {"chords": ["Dm7"], "lyrics": ""},
            {"chords": ["D", "Bm", "G", "D"], "lyrics": "Then back to the main groove"},
            {"chords": ["A", "Bm", "G", "D"], "lyrics": "One chord per bar — ride the pocket"},
        ],
    },
    {
        "section": "Final Chorus",
        "lines": list(_WAITING_CHORUS_LINES),
    },
]

_SAY_MAIN = [{"chords": ["G", "C", "Em", "D"]}]

_SAY_VERSE_LYRICS = [
    "Take all of your wasted honor",
    "Every little past frustration",
    "Take all of your so-called problems",
    "Better put 'em in quotations",
    "Say what you need to say",
    "Say what you need to say",
    "Say what you need to say",
    "Say what you need to say",
]

_SAY_CHORUS_LINES = [
    {"chords": ["G", "C"], "lyrics": "Even if your hands are shaking"},
    {"chords": ["Em", "D"], "lyrics": "And your faith is broken"},
    {"chords": ["G", "C"], "lyrics": "Even if your eyes are closing"},
    {"chords": ["Em", "D"], "lyrics": "Say it anyway"},
]

SAY_CHART: list[LyricSection] = [
    {
        "section": "Verse",
        "progression_block": _SAY_MAIN,
        "progression_repeat": 4,
        "lyrics": _SAY_VERSE_LYRICS,
    },
    {
        "section": "Chorus",
        "lines": list(_SAY_CHORUS_LINES),
    },
    {
        "section": "Bridge",
        "lines": [
            {"chords": ["Am", "C", "D"], "lyrics": "Walking like a one man army"},
            {"chords": ["Am", "C", "D"], "lyrics": "Fighting with the shadows in your head"},
            {"chords": ["Am", "C", "D"], "lyrics": "Living out the same old moment"},
            {"chords": ["Am", "C", "D"], "lyrics": "Knowing that it's all a waste of time"},
        ],
    },
    {
        "section": "Final Chorus",
        "lines": [
            {"chords": ["Em", "G"], "lyrics": "Say what you need to say"},
            {"chords": ["C7", "C7"], "lyrics": "Say what you need to say"},
            {"chords": ["Em", "G"], "lyrics": "Say what you need to say"},
            {"chords": ["C7", "C7"], "lyrics": "Say what you need to say"},
        ],
    },
]

LYRIC_CHORD_CHARTS: dict[tuple[str, str], dict[str, Any]] = {
    ("Waiting on the World to Change", "John Mayer"): {
        "key": "D",
        "chart": WAITING_ON_THE_WORLD_CHART,
        "sections": sections_from_lyric_chart(WAITING_ON_THE_WORLD_CHART),
        "arrangement_notes": (
            "Main chart in D: verse D–Bm–G–D then A–Bm–G–D; chorus uses paired half-lines; "
            "bridge vamps Dm7 then returns to the verse turnaround."
        ),
        "default_bpm": 96,
        "default_groove": "Pop groove",
        "guitar_tabs": {
            "D": "xx0232",
            "Bm": "x24432",
            "G": "320003",
            "A": "x02220",
            "Em": "022000",
            "Em7": "022030",
            "Dm7": "xx0211",
        },
    },
    ("We Are the Champions", "Queen"): {
        "key": "Cm",
        "chart": CHAMPIONS_LYRIC_CHART,
        "sections": sections_from_lyric_chart(CHAMPIONS_LYRIC_CHART),
        "arrangement_notes": CHAMPIONS_ARRANGEMENT_NOTES,
        "default_bpm": 107,
        "default_groove": "Rock groove",
        "guitar_tabs": CHAMPIONS_GUITAR_TABS,
    },
    ("Say", "John Mayer"): {
        "key": "G",
        "chart": SAY_CHART,
        "sections": sections_from_lyric_chart(SAY_CHART),
        "arrangement_notes": (
            "Main loop G–C–Em–D; chorus pairs G–C / Em–D; bridge Am–C–D; "
            "final chorus Em–G then C7 hold."
        ),
        "default_bpm": 82,
        "default_groove": "Pop groove",
        "guitar_tabs": {
            "G": "320003",
            "C": "x32010",
            "Em": "022000",
            "D": "xx0232",
            "Am": "x02210",
            "C7": "x32310",
            "Em7": "022030",
        },
    },
}


def has_lyric_chord_chart(title: str, artist: str) -> bool:
    return (title, artist) in LYRIC_CHORD_CHARTS


def lyric_chord_chart_for_song(title: str, artist: str) -> dict[str, Any] | None:
    return LYRIC_CHORD_CHARTS.get((title, artist))


def lyric_chord_sections_for_song(title: str, artist: str) -> dict[str, list[str]] | None:
    row = lyric_chord_chart_for_song(title, artist)
    if not row:
        return None
    return dict(row.get("sections") or {})
