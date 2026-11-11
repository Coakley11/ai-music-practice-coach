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

_SAY_INTRO_PATTERN = [{"chords": ["Bb", "Bbsus4", "Bb", "Bbsus4/C"]}]

# One list item = one bar. ``:3.5|X:0.5p`` = pushed anticipation on beat 3.5.
# BAR GRID CORRECTED (W21). These cells used to be written at half-bar
# granularity: the main loop took four bars for B♭–E♭–Gm–F, so every verse,
# chorus and turnaround was twice its played length and one pass of the chart
# ran 7:36 at 82 BPM against a 3:49 recording.
#
# The record puts TWO chords in a bar. The lyric-and-chord sheet the song is
# charted from writes the verse as "|Bb Eb | Gm F |" repeated 4x and labels it
# "Verse 2 (8 bars)" - a two-bar loop, four passes. Regridded to that:
# 78 bars = 3:48 against the 3:49 single.
#
# The pushes are kept, re-expressed on the halved grid: E♭ and F still enter an
# eighth before their slot, which is now the middle of the bar rather than the
# next downbeat. ":2|:2p" = two beats each, second chord pushed.
SAY_MAIN_LOOP = ["Bb:2|Eb:2p", "Gm:2|F:2p"]                      # 2 bars
SAY_INTRO_PATTERN_BARS = ["Bb", "Bbsus4", "Bb", "Bbsus4/C"]      # 4 bars
SAY_INTRO_BARS = SAY_INTRO_PATTERN_BARS * 2                       # 8 bars
SAY_BRIDGE_LOOP = ["Cm", "Eb:2|F:2p"]                             # 2 bars
SAY_BRIDGE_BARS = SAY_BRIDGE_LOOP * 3 + ["Eb", "Eb:2|F:2p"]      # 8 bars
SAY_FINAL_CHORUS_LOOP = ["Gm:2|Bb:2p", "Eb7"]                     # 2 bars

_SAY_MAIN = [{"chords": list(SAY_MAIN_LOOP)}]

_SAY_BRIDGE_LINES = [
    {"chords": list(SAY_BRIDGE_LOOP), "lyrics": "Walking like a one man army"},
    {"chords": list(SAY_BRIDGE_LOOP), "lyrics": "Fighting with the shadows in your head"},
    {"chords": list(SAY_BRIDGE_LOOP), "lyrics": "Living out the same old moment"},
    {"chords": ["Eb", "Eb:2|F:2p"], "lyrics": "Knowing that it's all a waste of time"},
]

_SAY_FINAL_CHORUS = [{"chords": list(SAY_FINAL_CHORUS_LOOP)}]

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
    {"chords": ["Bb:2|Eb:2p"], "lyrics": "Even if your hands are shaking"},
    {"chords": ["Gm:2|F:2p"], "lyrics": "And your faith is broken"},
    {"chords": ["Bb:2|Eb:2p"], "lyrics": "Even if your eyes are closing"},
    {"chords": ["Gm:2|F:2p"], "lyrics": "Say it anyway"},
]

SAY_CHART: list[LyricSection] = [
    {
        "section": "Intro",
        "progression_block": _SAY_INTRO_PATTERN,
        "progression_repeat": 2,
        "lyrics": [],
    },
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
        "lines": list(_SAY_BRIDGE_LINES),
    },
    {
        "section": "Final Chorus",
        "progression_block": _SAY_FINAL_CHORUS,
        "progression_repeat": 8,
        "lyrics": ["Say what you need to say"] * 8,
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
        "key": "Bb",
        "chart": SAY_CHART,
        "sections": {
            "Intro": list(SAY_INTRO_BARS),
            "Verse 1": list(SAY_MAIN_LOOP) * 4,
            "Chorus 1": list(SAY_MAIN_LOOP) * 4,
            "Turnaround 1": list(SAY_MAIN_LOOP),
            "Verse 2": list(SAY_MAIN_LOOP) * 4,
            "Chorus 2": list(SAY_MAIN_LOOP) * 4,
            "Turnaround 2": list(SAY_MAIN_LOOP),
            "Bridge": list(SAY_BRIDGE_BARS),
            "Turnaround 3": list(SAY_MAIN_LOOP),
            "Verse 3": list(SAY_MAIN_LOOP) * 4,
            "Final Chorus": list(SAY_FINAL_CHORUS_LOOP) * 8,
        },
        "arrangement_notes": (
            "B♭ major pop ballad (4/4, mid-tempo, straight 8ths); original key B♭ "
            "(play the G-shape chart with a capo on fret 3). Intro "
            "B♭ / B♭sus4 / B♭ / B♭sus4/C (two bars each, twice). Main loop "
            "B♭–E♭–Gm–F with E♭ and F pushed slightly early (``:0.5p``). "
            "Bridge Cm–Cm–E♭–F (×3) with pushed F, then E♭–E♭–E♭–F. Final chorus "
            "Gm–B♭ / E♭7 (×8) with pushed B♭. Chorus energy builds on each pass; "
            "final chorus peaks."
        ),
        "default_bpm": 82,
        "default_groove": "Ballad",
        "guitar_tabs": {
            "Bb": "x13331",
            "Bbsus4": "x13341",
            "Bbsus4/C": "x33341",
            "Eb": "x68886",
            "Gm": "355333",
            "F": "133211",
            "Cm": "x35543",
            "Eb7": "x68686",
            "Gm7": "353333",
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
