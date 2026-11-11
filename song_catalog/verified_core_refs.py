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

# --- Kiss Me (Sixpence None the Richer) — concert key Eb major ---
# Folk-pop ballad in 4/4. One list item = one bar so chart, backing, and
# practice timelines share the same harmonic rhythm.
#
# BAR GRID CORRECTED (W21). The cells used to be written at HALF-bar
# granularity while the record is one chord per bar in the intro/verse cycle
# and TWO chords per bar in the chorus and the instrumental. That made every
# section twice as long as it is played: Advanced ran 176 bars = 7:02 at
# 100 BPM against a 3:30 album version. The grid is now the recording's:
# 88 bars = 3:31. No chord was deleted to shorten anything — the repeated
# pairs in the cycle collapsed into one bar each, and the differing pairs in
# the chorus became within-bar changes ("Em|A"), which is what the source
# prints.
#
# Reference, named and kept consistent: the bar-formatted chord chart at
# bellandcomusic.com/kiss-me.html, which gives the intro as four bars of one
# chord each inside repeat signs (C | Cmaj7 | C7 | Cmaj7 in its capo-3 C
# shapes) and the instrumental as its eight chorus chords in FOUR bars, i.e.
# two chords to a bar. Its chorus and ours differ on a few chord identities
# (it prints Em/Am7-G where we hold D/C#-D/A); those are left alone here,
# because this correction is to the bar grid only.
#
# The cells below are written in the open D shapes every tab site prints,
# then transposed up a semitone to the key the record actually sounds in.
# Wikipedia and the Musicnotes listing both give Eb major, and an
# AcousticBrainz estimate for the track says D# major (the same pitch), so
# the D shapes are a capo-1 reading, not the sounding key.

# One chord per bar, exactly as the reference prints the intro.
_KISS_INTRO_CYCLE = (
    _hold("D", 1)
    + _hold("Dmaj7", 1)
    + _hold("D7", 1)
    + _hold("Dmaj7", 1)
)  # 4 bars
_KISS_INTRO = list(_KISS_INTRO_CYCLE) * 2  # 8 bars

_KISS_VERSE = (
    _hold("D", 1)
    + _hold("Dmaj7", 1)
    + _hold("D7", 1)
    + _hold("Dmaj7", 1)
    + _hold("D", 1)
    + _hold("Dmaj7", 1)
    + _hold("D7", 1)
    + _hold("G", 1)
)  # 8 bars

# Two chords to a bar, as the reference's instrumental staves show. Each cell
# below is one bar; "Em|A" means both chords inside it, two beats each.
_KISS_CHORUS = [
    "Em|A", "D|Bm",
    "Em|A", "D|D7",
    "Em|A", "D|D/C#",
    "Bm7|D/A",
    "Gmaj7",            # the one whole-bar chord in the chorus
    "Asus4|A",
]  # 9 bars

_KISS_INTERLUDE = list(_KISS_INTRO_CYCLE) * 2  # 8 bars
_KISS_HARMONICA = list(_KISS_INTRO_CYCLE) * 2  # 8 bars

# The reference prints exactly these eight chords across FOUR bars.
_KISS_GUITAR_SECTION = ["Em|A", "D|Bm", "Em|A", "D|D7"]  # 4 bars

_KISS_OUTRO = (
    list(_KISS_INTRO_CYCLE) * 4  # 16 bars
    + _hold("D", 1)               # 1 final bar
)  # 17 bars

_KISS_SECTION_ORDER: list[str] = [
    "Intro",
    "Verse 1",
    "Chorus 1",
    "Interlude",
    "Verse 2",
    "Chorus 2",
    "Harmonica / Accordion",
    "Guitar Section",
    "Chorus 3",
    "Outro",
]

_KISS_SECTIONS: dict[str, list[str]] = {
    "Intro": list(_KISS_INTRO),
    "Verse 1": list(_KISS_VERSE),
    "Chorus 1": list(_KISS_CHORUS),
    "Interlude": list(_KISS_INTERLUDE),
    "Verse 2": list(_KISS_VERSE),
    "Chorus 2": list(_KISS_CHORUS),
    "Harmonica / Accordion": list(_KISS_HARMONICA),
    "Guitar Section": list(_KISS_GUITAR_SECTION),
    "Chorus 3": list(_KISS_CHORUS),
    "Outro": list(_KISS_OUTRO),
}

# Beginner: simpler open voicings, identical bar counts so backing timing
# and chord-follow displays stay in sync with the intermediate/advanced charts.
def _kiss_beginner_chord(chord: str) -> str:
    """Map richer Kiss Me chords to simpler open voicings for beginners."""
    simple_map = {
        "Dmaj7": "D",
        "D7": "D",
        "D/C#": "D",
        "D/A": "D",
        "Bm7": "Bm",
        "Gmaj7": "G",
        "Asus4": "A",
    }
    return simple_map.get(chord, chord)


def _kiss_map_cell(cell: str, fn) -> str:
    """Apply a per-chord level map inside a possibly split bar ("Em|A")."""
    return "|".join(fn(part) for part in str(cell).split("|"))


_KISS_BEGINNER: dict[str, list[str]] = {
    name: [_kiss_map_cell(c, _kiss_beginner_chord) for c in chords]
    for name, chords in _KISS_SECTIONS.items()
}

# Advanced: tasteful extensions — Dmaj9, add9 colors, sus2/sus4 textures,
# richer voice leading. Bar counts unchanged.
def _kiss_advanced_chord(chord: str) -> str:
    """Map Kiss Me chords to richer voicings for the advanced tier."""
    advanced_map = {
        "D": "Dadd9",
        "Dmaj7": "Dmaj9",
        "D7": "D9",
        "Dmaj7/C#": "Dmaj9/C#",
        "D/C#": "Dmaj7/C#",
        "D/A": "Dadd9/A",
        "G": "Gadd9",
        "Gmaj7": "Gmaj9",
        "Em": "Em9",
        "Bm": "Bm9",
        "Bm7": "Bm9",
        "A": "Asus2",
        "Asus4": "A7sus4",
    }
    return advanced_map.get(chord, chord)


_KISS_ADVANCED: dict[str, list[str]] = {
    name: [_kiss_map_cell(c, _kiss_advanced_chord) for c in chords]
    for name, chords in _KISS_SECTIONS.items()
}


def _kiss_to_concert(charts: dict[str, list[str]]) -> dict[str, list[str]]:
    """D shapes (capo 1) -> the sounding key, Eb major."""
    from music_theory import transpose_sections_dict

    return transpose_sections_dict(charts, "D", "Eb")


# The level maps above are keyed on the D-shape names, so transposition happens
# once, after all three tiers are built.
_KISS_SECTIONS = _kiss_to_concert(_KISS_SECTIONS)
_KISS_BEGINNER = _kiss_to_concert(_KISS_BEGINNER)
_KISS_ADVANCED = _kiss_to_concert(_KISS_ADVANCED)

# Lyric cues — short paraphrases of the section feel (no copyrighted lines).
_KISS_LYRIC_CUES: dict[str, list[str]] = {
    "Intro": [
        "Soft acoustic strum setup",
        "Open-string Dmaj7 → D7 arc — establish the dreamy folk-pop feel",
    ],
    "Verse 1": [
        "Imagery setup — moonlit, swaying outdoors",
        "Vocal sits inside the D · Dmaj7 · D7 · Dmaj7 cycle",
        "Lift into G at the phrase resolution",
    ],
    "Chorus 1": [
        "Title hook — 'Kiss me' on Em → A → D",
        "Subtle bass descent: D → D/C# → Bm7 → D/A",
        "Gmaj7 lift, Asus4 → A release back to the verse",
    ],
    "Interlude": [
        "Wordless / instrumental D · Dmaj7 · D7 · Dmaj7 cycle",
        "Same harmonic feel as the intro",
    ],
    "Verse 2": [
        "Second-verse imagery — string-light, slow-dance setting",
        "Same harmonic rhythm as Verse 1",
    ],
    "Chorus 2": [
        "Title hook returns — same chord arc as Chorus 1",
        "Push slightly in dynamics toward the harmonica break",
    ],
    "Harmonica / Accordion": [
        "Featured harmonica / accordion melody over the intro cycle",
        "Phrase across D → Dmaj7 → D7 → Dmaj7, repeated",
    ],
    "Guitar Section": [
        "Guitar feature over the chorus chord skeleton",
        "Em → A → D → Bm, then Em → A → D → D7",
    ],
    "Chorus 3": [
        "Final chorus — sing out the title hook",
        "Same chord arc, slightly stronger groove",
    ],
    "Outro": [
        "Wordless extended D · Dmaj7 · D7 · Dmaj7 cycle, four times",
        "Soft 'kiss me' tag fragments allowed over the cycle",
        "Settle and finish on a final bar of D major",
    ],
}

VERIFIED_CORE_REFERENCE_KEYS: frozenset[tuple[str, str]] = frozenset(
    {
        ("Across the Universe", "The Beatles"),
        ("Uptown Girl", "Billy Joel"),
        ("Kiss Me", "Sixpence None the Richer"),
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
        "default_bpm": 128,
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
    ("Kiss Me", "Sixpence None the Richer"): {
        "key": "Eb",
        "concert_key": "Eb",
        "guitar_friendly_key": "D",
        "capo_note": "Capo 1 (open D shapes) · concert key Eb major",
        "genre": "Pop",
        "default_bpm": 100,
        "default_groove": "Folk Pop",
        "time_signature": "4/4",
        "sections": _KISS_SECTIONS,
        "section_order": list(_KISS_SECTION_ORDER),
        "beginner": _KISS_BEGINNER,
        "advanced": _KISS_ADVANCED,
        "lyric_cues": _KISS_LYRIC_CUES,
        # Concert-pitch fingerings, as the other capo-corrected songs carry.
        # Every shape here is one this repo already uses for that chord name;
        # the Advanced extensions (Ebadd9, Ebmaj9, Eb9, Abadd9, Abmaj9, Fm9,
        # Bb7sus4) and the slash voicings are omitted rather than invented,
        # since no verified fingering for them exists here yet.
        "guitar_tabs": {
            "Eb": "x68886",
            "Ebmaj7": "x6533x",
            "Eb7": "x68686",
            "Ab": "466544",
            "Abmaj7": "465544",
            "Fm": "133111",
            "Bb": "x13331",
            "Bbsus4": "x13341",
            "Bbsus2": "x13311",
            "Cm": "x35543",
            "Cm7": "x35343",
            "Cm9": "x3133x",
        },
        "arrangement_notes": (
            "Folk-pop ballad in **Eb major** (the recording's key), ~100 BPM, 4/4. "
            "Guitarists read it in open **D shapes with a capo on fret 1**; the chart "
            "stores the sounding chords. Form: "
            "**Intro → Verse 1 → Chorus 1 → Interlude → Verse 2 → Chorus 2 "
            "→ Harmonica / Accordion → Guitar Section → Chorus 3 → Outro**. "
            "Intro / Interlude / Harmonica all share the same 4-chord cycle, "
            "**one chord per bar**: **Eb · Ebmaj7 · Eb7 · Ebmaj7** (×2 = 8 bars each). "
            "Verse: same cycle then **Eb · Ebmaj7 · Eb7 · Ab** (8 bars). "
            "Chorus (9 bars, **two chords per bar**): "
            "**Fm|Bb · Eb|Cm · Fm|Bb · Eb|Eb7 · Fm|Bb · Eb|Eb/D · Cm7|Eb/Bb · "
            "Abmaj7 · Bbsus4|Bb**. "
            "Guitar Section: **Fm|Bb · Eb|Cm · Fm|Bb · Eb|Eb7** (4 bars). "
            "Outro: intro cycle ×4 (16 bars), then a final **Eb** bar (17 bars). "
            "One chart bar = one playback bar. "
            "FORM CORRECTED (W21): the chart was previously written at half-bar "
            "granularity, which made every section twice as long as it is played "
            "(176 Advanced bars = 7:02 at 100 BPM against a 3:30 album version). "
            "The bar-formatted chart at bellandcomusic.com/kiss-me.html prints the "
            "intro as four one-chord bars inside repeat signs and the instrumental's "
            "eight chords across four bars, i.e. two to a bar. Regridded to match: "
            "88 Advanced bars = 3:31. No chord was removed — repeated pairs became "
            "one bar, differing pairs became within-bar changes."
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
    adv = ref.get("advanced") or inter
    return {
        "Beginner": beg,
        "Intermediate": inter,
        "Advanced": adv,
    }


def lyric_cues_for_reference(title: str, artist: str) -> dict[str, list[str]]:
    ref = reference_for(title, artist)
    if not ref:
        return {}
    return dict(ref.get("lyric_cues") or {})
