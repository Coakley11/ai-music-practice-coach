"""We Are the Champions — Queen (Cm). Screenshot-aligned practice chart."""

from __future__ import annotations

from typing import Any

# One list item = one bar (backing track + block chart).

CHAMPIONS_VERSE: list[str] = [
    "Cm",
    "Gm7/C",
    "Cm",
    "Gm7/C",
    "Cm",
    "Gm7/C",
    "Cm",
    "Gm7/C",
    "Eb",
    "Ab/Eb",
    "Eb",
    "Ab/Eb",
    "Eb",
    "Bb/D",
    "Cm",
    "F7",
    "Bb",
    "Ab/Bb",
    "Bbm7b5",
    "Bb7",
    "C7",
]

CHAMPIONS_CHORUS: list[str] = [
    "F",
    "Am",
    "Dm",
    "Bb",
    "C7",
    "F",
    "Am",
    "Bb",
    "F#dim7",
    "Gm7",
    "C7/G",
    "Bbm6",
    "Bbm6/Db",
    "Edim7",
    "Gdim7",
    "F",
    "Ebadd9/G",
    "Ab6",
    "Bb",
    "Cm7add4",
    "Fm",
    "Gm7",
    "Fm",
    "Gm7/F",
    "Fm",
    "Gm7/C",
]

CHAMPIONS_OUTRO: list[str] = list(CHAMPIONS_CHORUS) + [
    "Cm",
    "Gm7/C",
    "Cm",
    "Gm7/C",
]

CHAMPIONS_SECTIONS: dict[str, list[str]] = {
    "Verse": list(CHAMPIONS_VERSE),
    "Chorus": list(CHAMPIONS_CHORUS),
    "Outro": list(CHAMPIONS_OUTRO),
}

CHAMPIONS_BEGINNER: dict[str, list[str]] = {
    "Verse": [
        "Cm",
        "Gm7/C",
        "Cm",
        "Gm7/C",
        "Cm",
        "Gm7/C",
        "Cm",
        "Gm7/C",
        "Eb",
        "Ab",
        "Eb",
        "Ab",
        "Eb",
        "Bb/D",
        "Cm",
        "F7",
        "Bb",
        "Ab",
        "Bbm7b5",
        "Bb7",
        "C7",
    ],
    "Chorus": [
        "F",
        "Am",
        "Dm",
        "Bb",
        "C7",
        "F",
        "Am",
        "Bb",
        "F#dim",
        "Gm7",
        "C7/G",
        "Bbm",
        "Bbm/Db",
        "Edim",
        "Gdim",
        "F",
        "Eb/G",
        "Ab",
        "Bb",
        "Cm7",
        "Fm",
        "Gm7",
        "Fm",
        "Gm7/F",
        "Fm",
        "Gm7/C",
    ],
}

CHAMPIONS_BEGINNER["Outro"] = list(CHAMPIONS_BEGINNER["Chorus"]) + [
    "Cm",
    "Gm7/C",
    "Cm",
    "Gm7/C",
]

CHAMPIONS_GUITAR_TABS: dict[str, str] = {
    "Cm": "x35543",
    "Gm7/C": "x30303",
    "Eb": "x68886",
    "Ab/Eb": "x69886",
    "Bb/D": "x5333x",
    "F7": "131211",
    "Bb": "x13331",
    "Ab/Bb": "x11341",
    "Bbm7b5": "x12021",
    "Bb7": "x13131",
    "C7": "x35353",
    "F": "133211",
    "Am": "x02210",
    "Dm": "xx0231",
    "C7": "x35353",
    "F#dim7": "2x120x",
    "Gm7": "353333",
    "C7/G": "332010",
    "Bbm6": "x13021",
    "Bbm6/Db": "x4332x",
    "Edim7": "xx2323",
    "Gdim7": "xx0101",
    "Ebadd9/G": "x6534x",
    "Ab6": "x1114x",
    "Cm7add4": "x35343",
    "Fm": "133111",
    "Gm7/F": "1x0033",
}

# Lyric/chord sheet (practice only) — chord pills; no auto lyric dump in backing.
_CHAMPIONS_VERSE_ROWS: list[dict[str, Any]] = [
    {"chords": ["Cm", "Gm7/C"]},
    {"chords": ["Cm", "Gm7/C"]},
    {"chords": ["Cm", "Gm7/C"]},
    {"chords": ["Cm", "Gm7/C"]},
    {"chords": ["Eb", "Ab/Eb"]},
    {"chords": ["Eb", "Ab/Eb"]},
    {"chords": ["Eb", "Bb/D", "Cm"]},
    {"chords": ["F7", "Bb"]},
    {"chords": ["Ab/Bb", "Bbm7b5", "Bb7", "C7"]},
]

_CHAMPIONS_CHORUS_ROWS: list[dict[str, Any]] = [
    {"chords": ["F", "Am"]},
    {"chords": ["Dm", "Bb", "C7"]},
    {"chords": ["F", "Am", "Bb", "F#dim7"]},
    {"chords": ["Gm7", "C7/G", "Bbm6", "Bbm6/Db"]},
    {"chords": ["Edim7", "Gdim7"]},
    {"chords": ["F", "Ebadd9/G", "Ab6"]},
    {"chords": ["Bb", "Cm7add4"]},
    {"chords": ["Fm", "Gm7", "Fm", "Gm7/F", "Fm"]},
    {"chords": ["Gm7/C"]},
]

CHAMPIONS_LYRIC_CHART: list[dict[str, Any]] = [
    {"section": "Verse", "lines": list(_CHAMPIONS_VERSE_ROWS)},
    {"section": "Chorus", "lines": list(_CHAMPIONS_CHORUS_ROWS)},
    {"section": "Outro", "lines": list(_CHAMPIONS_CHORUS_ROWS) + [{"chords": ["Cm", "Gm7/C"]}, {"chords": ["Cm", "Gm7/C"]}]},
]

CHAMPIONS_ARRANGEMENT_NOTES = (
    "Original key Cm (6/8 ballad feel ~107 BPM). Verse: Cm–Gm7/C vamp, Eb–Ab/Eb, "
    "Bb/D–Cm, F7–Bb turnaround, Ab/Bb–Bbm7b5–Bb7–C7 cadence. Chorus in F: "
    "F–Am–Dm–Bb–C7, F#dim7 passing, Gm7–C7/G–Bbm6–Edim7–Gdim7 color, "
    "Ebadd9/G–Ab6, then Fm–Gm7 tag and Gm7/C return."
)
