"""We Are the Champions — Queen (Cm verse, F-centered chorus, 4/4)."""

from __future__ import annotations

from typing import Any

# One list item = one bar. Use ``|`` for in-bar splits (e.g. ``Bb|C7``).

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

CHAMPIONS_CHORUS_MAIN: list[str] = [
    "F",
    "Am",
    "Dm",
    "Bb|C7",
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
]

CHAMPIONS_ENDING_TAG: list[str] = [
    "Fm",
    "Gm7",
    "Fm",
    "Gm7/F",
    "Fm",
    "Gm7/C",
]

CHAMPIONS_SECTIONS: dict[str, list[str]] = {
    "Verse 1": list(CHAMPIONS_VERSE),
    "Chorus 1": list(CHAMPIONS_CHORUS_MAIN),
    "Ending Tag": list(CHAMPIONS_ENDING_TAG),
    "Verse 2": list(CHAMPIONS_VERSE),
    "Chorus 2": list(CHAMPIONS_CHORUS_MAIN),
    "Final Chorus": list(CHAMPIONS_CHORUS_MAIN),
    "Outro": list(CHAMPIONS_CHORUS_MAIN),
}

CHAMPIONS_BEGINNER: dict[str, list[str]] = {
    name: [
        c.replace("Bb|C7", "Bb")
        .replace("Ab/Eb", "Ab")
        .replace("Ab/Bb", "Ab")
        .replace("F#dim7", "F#dim")
        .replace("Bbm6/Db", "Bbm")
        .replace("Bbm6", "Bbm")
        .replace("Edim7", "Edim")
        .replace("Gdim7", "Gdim")
        .replace("Ebadd9/G", "Eb/G")
        .replace("Cm7add4", "Cm7")
        for c in chords
    ]
    for name, chords in CHAMPIONS_SECTIONS.items()
}

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
]

_CHAMPIONS_TAG_ROWS: list[dict[str, Any]] = [
    {"chords": ["Fm", "Gm7", "Fm", "Gm7/F", "Fm", "Gm7/C"]},
]

CHAMPIONS_LYRIC_CHART: list[dict[str, Any]] = [
    {"section": "Verse 1", "lines": list(_CHAMPIONS_VERSE_ROWS)},
    {"section": "Chorus 1", "lines": list(_CHAMPIONS_CHORUS_ROWS)},
    {"section": "Ending Tag", "lines": list(_CHAMPIONS_TAG_ROWS)},
    {"section": "Verse 2", "lines": list(_CHAMPIONS_VERSE_ROWS)},
    {"section": "Chorus 2", "lines": list(_CHAMPIONS_CHORUS_ROWS)},
    {"section": "Final Chorus", "lines": list(_CHAMPIONS_CHORUS_ROWS)},
    {"section": "Outro", "lines": list(_CHAMPIONS_CHORUS_ROWS)},
]

CHAMPIONS_ARRANGEMENT_NOTES = (
    "**C minor** verse / **F major**-centered chorus (**4/4**, ~65 BPM). "
    "Preserve Queen slash colors: **Gm7/C · Ab/Eb · Bb/D · Ab/Bb · "
    "Bbm7b5 · C7/G · Bbm6/Db · F#dim7 · Ebadd9/G · Cm7add4**. "
    "Chorus bar 4 uses **Bb|C7** (half-bar split). **Ending Tag** is "
    "**Fm–Gm7–Gm7/F–Gm7/C** after the first chorus lift. Backing: "
    "grand piano, bass, stadium drums, layered vocals, orchestral support — "
    "arena anthem dynamics, not acoustic or jazz trio. **Final Chorus** "
    "same harmony with biggest arrangement; **Outro** repeats the "
    "full chorus progression for singalong close."
)
