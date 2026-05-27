"""Hand-curated songs with practice-level harmony (priority accuracy for listed artists)."""

from __future__ import annotations

from typing import Any

from .verified_core_refs import (
    chart_versions_for_reference,
    lyric_cues_for_reference,
    reference_for,
)


def _ext(**kwargs) -> dict[str, Any]:
    """Reserved slots for MIDI / MusicXML / analysis / improvisation metadata."""
    base = {
        "midi_path": None,
        "musicxml_path": None,
        "harmonic_analysis": None,
        "arrangement_notes": None,
    }
    base.update({k: v for k, v in kwargs.items() if v is not None})
    return base


def _s(
    title: str,
    artist: str,
    genre: str,
    key: str,
    sections: dict[str, list[str]],
    *,
    guitar_tabs: dict[str, str] | None = None,
    composer: str | None = None,
    lyric_cues: dict[str, list[str]] | None = None,
    extensions: dict[str, Any] | None = None,
    chart_status: str = "practice_simplified",
    chart_versions: dict[str, dict[str, list[str]]] | None = None,
    section_order: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "title": title,
        "artist": artist,
        "genre": genre,
        "key": key,
        "sections": sections,
        "chart_versions": chart_versions or {},
        "chart_status": chart_status,
        "guitar_tabs": guitar_tabs or {},
        "composer": composer,
        "lyric_cues": lyric_cues or {},
        "extensions": extensions or _ext(),
    }
    if section_order:
        row["section_order"] = list(section_order)
    return row


def _levels(
    *,
    beginner: dict[str, list[str]],
    intermediate: dict[str, list[str]],
    advanced: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, list[str]]]:
    return {
        "Beginner": beginner,
        "Intermediate": intermediate,
        "Advanced": advanced or intermediate,
    }


def _perfect_chart_pack() -> dict[str, Any]:
    """Perfect — Ed Sheeran (G major, acoustic pop ballad)."""
    walk = ["G", "D/F#", "Em7", "D", "Cadd9", "D", "G"]
    chorus = ["Em7", "Cadd9", "G", "D/F#", "Em7", "Cadd9", "G", "D/F#"]

    def _hold_two_bars(chords: list[str]) -> list[str]:
        out: list[str] = []
        for ch in chords:
            out.extend([ch, ch])
        return out

    def _verse_bars(cycle: list[str]) -> list[str]:
        return _hold_two_bars(cycle) * 2

    verse_cycle = ["G", "Em7", "Cadd9", "D/F#"]
    verse = _verse_bars(verse_cycle)
    base = {
        "Intro": list(walk),
        "Verse 1": list(verse),
        "Verse 2": list(verse),
        "Chorus 1": list(chorus),
        "Verse 3": list(verse),
        "Verse 4": list(verse),
        "Chorus 2": list(chorus),
        "Chorus 3": list(chorus),
        "Outro": list(walk),
    }
    intermediate = dict(base)
    verse_adv_cycle = ["G6", "Em9", "Cmaj9", "D13sus4"]
    chorus_adv = ["Em9", "C6/9", "Gmaj9/B", "D13sus4"] * 2
    advanced = {
        "Intro": ["Gmaj9", "D/F#", "Em9", "D13sus4", "C6/9", "Dadd9", "Gmaj9"],
        "Verse 1": _verse_bars(verse_adv_cycle),
        "Verse 2": _verse_bars(verse_adv_cycle),
        "Chorus 1": list(chorus_adv),
        "Verse 3": _verse_bars(verse_adv_cycle),
        "Verse 4": _verse_bars(verse_adv_cycle),
        "Chorus 2": list(chorus_adv),
        "Chorus 3": list(chorus_adv),
        "Outro": ["Gmaj9", "D/F#", "Em9", "D13sus4", "C6/9", "Dadd9", "Gmaj9"],
    }
    section_order = [
        "Intro",
        "Verse 1",
        "Verse 2",
        "Chorus 1",
        "Verse 3",
        "Verse 4",
        "Chorus 2",
        "Chorus 3",
        "Outro",
    ]
    return {
        "key": "G",
        "sections": intermediate,
        "chart_versions": _levels(beginner=base, intermediate=intermediate, advanced=advanced),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": {
            "Intro": ["Instrumental — G · D/F# · Em7 · D · Cadd9 · D · G"],
            "Verse 1": ["I found a love for me…", "Darling just dive right in…"],
            "Verse 2": ["Well I found a girl, beautiful and sweet…"],
            "Chorus 1": ["Baby, I'm dancing in the dark…"],
            "Verse 3": ["Cause we were just kids when we fell in love…"],
            "Verse 4": ["Barefoot on the grass, listening to our favourite song…"],
            "Chorus 2": ["Baby, I'm dancing in the dark…"],
            "Chorus 3": ["Final chorus — same lift as Chorus 2"],
            "Outro": ["Tag — walkdown G · D/F# · Em7 · D · Cadd9 · D · G"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**G major** acoustic ballad (~95 BPM, **6/8**). Intro/Outro walk: "
                "**G–D/F#–Em7–D–Cadd9–D–G**. Verses hold each chord **two full 6/8 bars** "
                "(**G–Em7–Cadd9–D/F#**, twice per verse). Choruses **Em7–Cadd9–G–D/F#** "
                "one bar each (×2 per chorus). Form adds **Chorus 3** before the outro. "
                "Advanced adds maj9, 6/9, and sus extensions."
            ),
            default_bpm=95,
            default_groove="Ballad",
            time_signature="6/8",
        ),
    }


def _champions_chart_pack() -> dict[str, Any]:
    from song_catalog.we_are_the_champions import (
        CHAMPIONS_ARRANGEMENT_NOTES,
        CHAMPIONS_BEGINNER,
        CHAMPIONS_GUITAR_TABS,
        CHAMPIONS_LYRIC_CHART,
        CHAMPIONS_SECTIONS,
    )

    inter = dict(CHAMPIONS_SECTIONS)
    beg = dict(CHAMPIONS_BEGINNER)
    return {
        "key": "Cm",
        "sections": inter,
        "chart_versions": _levels(beginner=beg, intermediate=inter, advanced=inter),
        "chart_status": "practice_level_verified",
        "guitar_tabs": CHAMPIONS_GUITAR_TABS,
        "extensions": _ext(
            arrangement_notes=CHAMPIONS_ARRANGEMENT_NOTES,
            default_bpm=107,
            default_groove="Rock groove",
            lyric_chord_chart=CHAMPIONS_LYRIC_CHART,
        ),
    }


def _piano_man_chart_pack() -> dict[str, Any]:
    """Piano Man — Billy Joel (C major, 3/4 waltz feel).

    Section-by-section chart. One list item = one bar.

    Where the original chart had a single bar of **G11**, the harmonica
    passages substitute the passing motion **Fmaj7 -> Am7 -> C/D** *inside the
    same one bar*. This is encoded as the subdivided-bar token
    ``"Fmaj7|Am7|C/D"`` (see :mod:`chord_subdivisions`):

    * Backing audio plays Fmaj7 / Am7 / C/D on consecutive beats inside the
      same measure (one chord per beat in 3/4).
    * Chord-follow highlighting moves beat-by-beat across the three sub-chords
      while the cell stays lit as one bar.
    * The lead sheet renders the cell as a single bar with three sub-chord
      pills - the quick walk-up turnaround the chart calls for.
    """

    # --- Shared building blocks (intermediate level / canonical) ---
    HARM_INTRO_LINE_1 = ["C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G"]
    # Subdivided passing bar: three chords inside one measure.
    PASSING_BAR = "Fmaj7|Am7|C/D"

    VERSE_LINE_1 = ["C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G"]
    VERSE_LINE_2_BASE = ["C", "C/B", "Am", "C/G", "F", "G11"]  # 6 bars, then ending
    VERSE_MEMORY_LINE_2_BASE = ["C", "Em/B", "Am", "C/G", "F", "G11"]
    CHORUS_LINE_1 = ["C", "Em/B", "Am", "C/G", "F", "C/E", "D7", "G"]
    CHORUS_LINE_2_BASE = ["C", "Em/B", "Am", "C/G", "F", "G11"]

    BRIDGE = (
        ["Am", "Am/G", "D7/F#", "F"]
        + ["Am", "Am/G", "D7/F#", "D7"]
        + ["G", "G/F", "C/E", "G7/D"]
    )  # 12 bars - single G7/D resolution, no extra held bar

    INSTRUMENTAL = (
        ["Am", "Am/G", "D7/F#", "F"]
        + ["Am", "Am/G", "D7/F#", "F"]
        + ["Am", "Am/G", "D7/F#", "D7"]
        + ["G", "G/F", "C/E", "G/D"]
    )  # 16 bars

    # Section assemblers (each PASSING_BAR is ONE bar containing 3 sub-chords).
    harmonica_intro = (
        list(HARM_INTRO_LINE_1)                                   # 8 bars
        + ["C", "C/B", "Am", "C/G", "F", PASSING_BAR]             # 6 bars
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                      # 4 bars
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                      # 4 bars
    )  # 22 bars total

    verse_1 = list(VERSE_LINE_1) + list(VERSE_LINE_2_BASE) + ["C", "C"]
    # 8 + 6 + 2 = 16 bars

    harmonica_turnaround = (
        ["C", "C/B", "Am", "C/G", "F", "G11", "C", "F/C"]
    )  # 8 bars

    verse_2 = list(VERSE_LINE_1) + list(VERSE_MEMORY_LINE_2_BASE) + ["C", "C"]
    # 8 + 6 + 2 = 16 bars (Verse 2 uses Em/B walk-down in line 2)

    chorus_1 = list(CHORUS_LINE_1) + list(CHORUS_LINE_2_BASE) + ["C", "C"]
    # 8 + 6 + 2 = 16 bars (Bar 16 holds C - matches Chorus 2/3 resolution)
    chorus_2 = list(CHORUS_LINE_1) + list(CHORUS_LINE_2_BASE) + ["C", "C"]
    chorus_3 = list(chorus_2)
    # All three choruses now end on two bars of C => 16 bars each

    harmonica_2 = (
        ["C", "Em/B", "Am", "C/G", "F", PASSING_BAR]              # 6 bars
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                      # 4 bars
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                      # 4 bars
    )  # 14 bars total

    # Verse 3A ends with C | F/C (different tag)
    verse_3a = list(VERSE_LINE_1) + list(VERSE_LINE_2_BASE) + ["C", "F/C"]
    # 8 + 6 + 2 = 16 bars
    verse_3b = list(verse_1)  # ends with C C
    verse_4 = list(verse_1)   # standard
    verse_5 = list(verse_1)   # standard

    harmonica_3 = (
        ["C", "Em/B", "Am", "C/G", "F", PASSING_BAR]              # 6 bars
        + ["C", "F/C"]                                            # 2 bars
    )  # 8 bars total

    harmonica_4 = (
        ["C", "C/B", "Am", "C/G", "F", "G11", "C", "F/C"]      # bars 1-8
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                    # bars 9-12 (Bar 12 = Fmaj7 -> Am7 -> C/D inside ONE bar)
    )  # 12 bars total

    verse_6a = list(verse_3a)  # ends C F/C
    verse_6b = list(verse_1)   # ends C C

    final_outro = (
        ["C", "C/B", "Am", "C/G", "F", PASSING_BAR]               # 6 bars
        + ["C", "F/C", "Cmaj7", PASSING_BAR]                      # 4 bars
        + ["G/F", "C/E", "G/D", "C"]                              # 4 bars (final C = 1 bar)
    )  # 14 bars total

    intermediate: dict[str, list[str]] = {
        "Harmonica Intro": harmonica_intro,
        "Verse 1": verse_1,
        "Harmonica Turnaround": harmonica_turnaround,
        "Verse 2": verse_2,
        "Bridge 1": list(BRIDGE),
        "Chorus 1": chorus_1,
        "Harmonica Section 2": harmonica_2,
        "Verse 3A": verse_3a,
        "Verse 3B": verse_3b,
        "Bridge 2": list(BRIDGE),
        "Verse 4": verse_4,
        "Harmonica Section 3": harmonica_3,
        "Verse 5": verse_5,
        "Instrumental": list(INSTRUMENTAL),
        "Chorus 2": chorus_2,
        "Harmonica Section 4": harmonica_4,
        "Verse 6A": verse_6a,
        "Verse 6B": verse_6b,
        "Bridge 3": list(BRIDGE),
        "Chorus 3": chorus_3,
        "Final Harmonica Outro": final_outro,
    }

    section_order: list[str] = [
        "Harmonica Intro",
        "Verse 1",
        "Harmonica Turnaround",
        "Verse 2",
        "Bridge 1",
        "Chorus 1",
        "Harmonica Section 2",
        "Verse 3A",
        "Verse 3B",
        "Bridge 2",
        "Verse 4",
        "Harmonica Section 3",
        "Verse 5",
        "Instrumental",
        "Chorus 2",
        "Harmonica Section 4",
        "Verse 6A",
        "Verse 6B",
        "Bridge 3",
        "Chorus 3",
        "Final Harmonica Outro",
    ]

    def _map_subdivided(token: str, mapper) -> str:
        """Apply ``mapper`` to each sub-chord inside a subdivided bar; preserve the ``|`` form."""
        if "|" not in token:
            return mapper(token)
        parts = [p.strip() for p in token.split("|") if p.strip()]
        return "|".join(mapper(p) for p in parts)

    # --- Beginner: simpler open voicings, no jazz extensions ---
    def _simplify_single(chord: str) -> str:
        mapping = {
            "Cmaj7": "C",
            "Fmaj7": "F",
            "Am7": "Am",
            "Am/G": "Am",
            "G7/D": "G",
            "G7/F": "G",
            "G11": "G",
            "C/D": "G",  # closest beginner-friendly substitution
        }
        return mapping.get(chord, chord)

    def _simplify(chord: str) -> str:
        return _map_subdivided(chord, _simplify_single)

    beginner: dict[str, list[str]] = {
        name: [_simplify(c) for c in chords]
        for name, chords in intermediate.items()
    }

    # --- Advanced: tasteful extensions, richer voice leading ---
    def _enrich_single(chord: str) -> str:
        mapping = {
            "C": "Cmaj7",
            "F": "Fmaj7",
            "Am": "Am7",
            "Am/G": "Am7/G",
            "G": "G7",
            "G7/D": "G13/D",
            "G7/F": "G13/F",
            "G11": "G13sus",
            "D7": "D9",
            "D7/F#": "D9/F#",
            "C/B": "Cmaj7/B",
            "C/G": "Cmaj7/G",
            "C/E": "Cmaj7/E",
            "F/C": "Fmaj7/C",
            "F/A": "Fmaj7/A",
            "Em/B": "Em9/B",
        }
        return mapping.get(chord, chord)

    def _enrich(chord: str) -> str:
        return _map_subdivided(chord, _enrich_single)

    advanced: dict[str, list[str]] = {
        name: [_enrich(c) for c in chords]
        for name, chords in intermediate.items()
    }

    lyric_cues: dict[str, list[str]] = {
        "Harmonica Intro": [
            "Solo harmonica establishes the C major waltz",
            "Descending bass walk: C → B → A → G → F → E → D → G",
            "Setup of the rolling 3/4 piano-ballad groove",
        ],
        "Verse 1": [
            "Story setup — 'It's nine o'clock on a Saturday'",
            "Voice enters on the same descending walk",
            "Resolves to C with G11 → C cadence",
        ],
        "Harmonica Turnaround": [
            "Short harmonica fill bridging Verse 1 → Verse 2",
            "Same C → C/B → Am → C/G walk-down",
        ],
        "Verse 2": [
            "Second verse — 'He says, son can you play me a memory?'",
            "Line 2 uses Em/B for darker color over the walk-down",
        ],
        "Bridge 1": [
            "Am → Am/G → D7/F# → F descending phrase",
            "Repeats then lifts via G → G/F → C/E → G7/D (single G7/D resolution)",
            "Sets up the title-hook chorus",
        ],
        "Chorus 1": [
            "Title hook — 'Sing us a song you're the piano man'",
            "Em/B walk-down through the chorus phrase",
            "Resolves with two bars of C before the harmonica break",
        ],
        "Harmonica Section 2": [
            "Featured harmonica solo over the Em/B walk-down",
            "Passing motion Fmaj7 → Am7 → C/D in place of G11",
        ],
        "Verse 3A": [
            "Third verse part A — 'Now John at the bar is a friend of mine'",
            "Ends with C → F/C tag heading into Verse 3B",
        ],
        "Verse 3B": [
            "Third verse part B — completes the John portrait",
            "Standard verse ending: two bars of C",
        ],
        "Bridge 2": [
            "Same harmonic arc as Bridge 1 — Am descent + lift",
        ],
        "Verse 4": [
            "Fourth verse — 'Now Paul is a real estate novelist'",
            "Standard verse ending: two bars of C",
        ],
        "Harmonica Section 3": [
            "Short harmonica interlude before Verse 5",
            "Em/B walk-down + Fmaj7 → Am7 → C/D passing",
        ],
        "Verse 5": [
            "Fifth verse — 'It's a pretty good crowd for a Saturday'",
        ],
        "Instrumental": [
            "Full-band instrumental on the bridge progression",
            "Two passes of Am → Am/G → D7/F# descents",
        ],
        "Chorus 2": [
            "Title-hook chorus returns",
            "Ends with two bars of C",
        ],
        "Harmonica Section 4": [
            "Harmonica feature reinforces the rolling groove",
            "Bar 12 ends on the passing motion Fmaj7 -> Am7 -> C/D (one bar, one chord per beat)",
        ],
        "Verse 6A": [
            "Sixth verse part A — 'And the piano sounds like a carnival'",
            "Ends with C → F/C tag",
        ],
        "Verse 6B": [
            "Sixth verse part B — 'And the microphone smells like a beer'",
            "Standard verse ending: two bars of C",
        ],
        "Bridge 3": [
            "Final bridge — same Am descent + lift",
        ],
        "Chorus 3": [
            "Final chorus — full title hook",
            "Ends with two bars of C heading into the outro",
        ],
        "Final Harmonica Outro": [
            "Final harmonica statement over the walk-down",
            "Two passes of Fmaj7 → Am7 → C/D passing motion",
            "Coda cadence: G/F → C/E → G/D → C (final C = 1 bar)",
        ],
    }

    arrangement_notes = (
        "**C major, 3/4 waltz (~88 BPM).** Piano-ballad with rolling left-hand "
        "arpeggios and a descending bass walk: **C → C/B → Am → C/G → F → C/E "
        "→ D7 → G**. Form (21 sections): Harmonica Intro → Verse 1 → Harmonica "
        "Turnaround → Verse 2 → Bridge 1 → Chorus 1 → Harmonica Section 2 → "
        "Verse 3A → Verse 3B → Bridge 2 → Verse 4 → Harmonica Section 3 → Verse "
        "5 → Instrumental → Chorus 2 → Harmonica Section 4 → Verse 6A → Verse "
        "6B → Bridge 3 → Chorus 3 → Final Harmonica Outro. "
        "Most G11 bars in the harmonica sections are replaced with the passing "
        "motion **Fmaj7 → Am7 → C/D** — three chords played **inside one single "
        "bar** (one per beat in 3/4). The chart, backing audio, and chord-follow "
        "all treat this as one measure with three quick sub-chords, not three "
        "separate bars: the lead-sheet cell shows the trio of pills side-by-side "
        "and the highlight moves beat-by-beat across them as the bar plays. "
        "Bridges share an identical 12-bar form (Am → Am/G → D7/F# → F twice, "
        "then G → G/F → C/E → G7/D - single resolution, no extra held bar). "
        "Verse 2 swaps Em/B for C/B in line 2 for the darker memory color. "
        "All three choruses end with two bars of C (16 bars each). "
        "Harmonica Section 4 closes Bar 12 on the Fmaj7 -> Am7 -> C/D passing "
        "bar instead of the held G11. Final Outro coda: "
        "**G/F → C/E → G/D → C** (final C = 1 bar). "
        "Beginner replaces extensions with open triads; Advanced enriches with "
        "maj7 / 9 / 13sus colors and slash-chord voice leading. One chart bar "
        "= one playback bar."
    )

    return {
        "key": "C",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": lyric_cues,
        "extensions": _ext(
            arrangement_notes=arrangement_notes,
            default_bpm=88,
            default_groove="Ballad",
            time_signature="3/4",
        ),
    }


def _shallow_chart_pack() -> dict[str, Any]:
    """Shallow - Lady Gaga / Bradley Cooper (G major, 4/4 cinematic ballad).

    Section-by-section chart. **One list item = one bar.**

    Chords in the user's reference are already in the song's actual key (G
    major), so no transposition is needed. Bar counts mix 1-, 2-, and 4-bar
    holds to match the song's intimate verse pacing -> sustained chorus
    anthem build.
    """

    def _hold(chord: str, bars: int) -> list[str]:
        return [chord] * bars

    # --- INTRO (13 bars) ---
    intro = (
        _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G", 2)        # 4
        + _hold("C", 2) + _hold("G", 1) + _hold("D/F#", 2)        # 5
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G", 2)      # 4
    )

    # --- VERSE 1 / VERSE 2 (18 bars each) ---
    verse = (
        _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)       # 4
        + _hold("C", 2) + _hold("G", 1)                            # 3
        + _hold("D9", 1) + _hold("D", 1)                           # 2
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)      # 4
        + _hold("C", 2) + _hold("G", 1) + _hold("D/F#", 2)         # 5
    )

    # --- REFRAIN 1 (26 bars) ---
    refrain_1 = (
        _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)       # 4
        + _hold("C", 2) + _hold("G", 1)                            # 3
        + _hold("D9", 2)                                            # 2
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)      # 4
        + _hold("C", 2) + _hold("G", 1) + _hold("D/F#", 2)         # 5
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G", 2)       # 4
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G", 2)       # 4
    )

    # --- REFRAIN 2 (18 bars) ---
    refrain_2 = (
        _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)       # 4
        + _hold("C", 2) + _hold("G", 1) + _hold("D/F#", 2)         # 5
        + _hold("Em7", 1) + _hold("D/F#", 1) + _hold("G6", 2)      # 4
        + _hold("C", 2) + _hold("G", 1) + _hold("D/F#", 2)         # 5
    )

    # --- CHORUS / FINAL CHORUS (16 bars) ---
    chorus = (
        _hold("Am", 2) + _hold("D/F#", 2)                          # 4
        + _hold("G", 1) + _hold("D", 1)                            # 2
        + _hold("Em", 2)                                            # 2
        + _hold("Am", 2) + _hold("D/F#", 2)                        # 4
        + _hold("G", 1) + _hold("D", 1)                            # 2
        + _hold("Em", 2)                                            # 2
    )

    # --- BRIDGE 1 (16 bars) - first half has plain D (no inversion) ---
    bridge_1 = (
        _hold("Am", 2) + _hold("D", 2)                             # 4
        + _hold("G", 1) + _hold("D", 1)                            # 2
        + _hold("Em", 2)                                            # 2
        + _hold("Am", 2) + _hold("D/F#", 2)                        # 4
        + _hold("G", 1) + _hold("D", 1)                            # 2
        + _hold("Em", 2)                                            # 2
    )

    # --- BRIDGE 2 (16 bars) - modal lift through Bm / A / E ---
    bridge_2 = (
        _hold("Bm", 2) + _hold("D", 2)                             # 4
        + _hold("A", 2) + _hold("E", 2)                            # 4
        + _hold("Bm", 2) + _hold("D", 2)                            # 4
        + _hold("A", 4)                                             # 4
    )

    # --- OUTRO (16 bars) - chorus shape with D (no inversion) at the second turnaround ---
    outro = (
        _hold("Am", 2) + _hold("D/F#", 2)                          # 4
        + _hold("G", 1) + _hold("D", 1)                            # 2
        + _hold("Em", 2)                                            # 2
        + _hold("Am", 2) + _hold("D", 2)                            # 4 (plain D)
        + _hold("G", 1) + _hold("D", 1)                             # 2
        + _hold("Em", 2)                                             # 2
    )

    base_sections: dict[str, list[str]] = {
        "Intro": intro,
        "Verse 1": list(verse),
        "Refrain 1": refrain_1,
        "Verse 2": list(verse),
        "Refrain 2": refrain_2,
        "Chorus": list(chorus),
        "Bridge 1": bridge_1,
        "Bridge 2": bridge_2,
        "Final Chorus": list(chorus),
        "Outro": outro,
    }

    section_order: list[str] = [
        "Intro",
        "Verse 1",
        "Refrain 1",
        "Verse 2",
        "Refrain 2",
        "Chorus",
        "Bridge 1",
        "Bridge 2",
        "Final Chorus",
        "Outro",
    ]

    # --- Beginner: simplified open voicings; preserve every slash chord exactly. ---
    def _simplify(chord: str) -> str:
        mapping = {
            "Em7": "Em",
            "G6": "G",
            "D9": "D",
        }
        return mapping.get(chord, chord)  # slash chords pass through untouched

    beginner = {name: [_simplify(c) for c in chords] for name, chords in base_sections.items()}

    # --- Intermediate: the canonical chart as the user wrote it. ---
    intermediate = {name: list(chords) for name, chords in base_sections.items()}

    # --- Advanced: tasteful add9 / maj9 extensions while preserving Em7, G6,
    #     D9, and every slash chord exactly as the user required.
    def _enrich(chord: str) -> str:
        mapping = {
            "Em7": "Em9",       # preserve Em7 family color, add 9
            "G6": "G6add9",     # keep the 6 color, add 9 - non-slash, parser-safe
            "D9": "D9",         # preserve exactly
            "G": "Gadd9",
            "C": "Cmaj9",
            "Am": "Am9",
            "Em": "Em9",
            "Bm": "Bm9",
            "A": "Aadd9",
            "E": "Esus4",       # tasteful upper lift for the bridge climb
            "D": "Dsus4",       # add motion under the bridge / chorus turnarounds
        }
        # Slash chords (D/F#) are preserved exactly.
        if "/" in chord:
            return chord
        return mapping.get(chord, chord)

    advanced = {name: [_enrich(c) for c in chords] for name, chords in base_sections.items()}

    lyric_cues: dict[str, list[str]] = {
        "Intro": [
            "Quiet fingerpicked guitar opens the cinematic ballad",
            "Em7 -> D/F# -> G walk-down establishes the emotional center",
            "Sparse and intimate before any vocal",
        ],
        "Verse 1": [
            "First vocal entry - 'Tell me something, girl...'",
            "Hold each chord 1-2 bars; let the lyric breathe",
            "D9 -> D color shift cues the dynamic build mid-verse",
        ],
        "Refrain 1": [
            "Pre-chorus lift building toward the chorus",
            "Sustained D9 holds the tension before the descending tag",
            "Closing Em7 -> D/F# -> G pair sets up the chorus arrival",
        ],
        "Verse 2": [
            "Second vocal entry - 'Tell me something, boy...'",
            "Same intimate pacing as Verse 1",
        ],
        "Refrain 2": [
            "Shortened refrain lifts back into the second chorus",
            "Em7 -> D/F# -> G6 phrase repeats twice",
        ],
        "Chorus": [
            "Title hook - 'In the shallow, shallow...'",
            "Am -> D/F# pair holds the emotional core",
            "G/D turnaround lifts into the Em arrival on each cycle",
        ],
        "Bridge 1": [
            "First bridge half uses plain D (no inversion) for a darker lift",
            "Second half restores D/F# bass walk for the resolving Em",
            "Pre-climax: dynamics swell into Bridge 2",
        ],
        "Bridge 2": [
            "Climax modulation - Bm / A / E modal lift to the top of the form",
            "Final A(4) is the held vocal climb 'Ahh ahh ahh AHHHH!'",
            "Sets up the final chorus arrival on Am",
        ],
        "Final Chorus": [
            "Full anthem chorus - same shape as the first chorus",
            "Biggest dynamic moment of the form",
        ],
        "Outro": [
            "Quiet wind-down using the chorus pattern",
            "Plain D at the second turnaround signals the closing exhale",
            "Lands on the held Em - intimate to match the intro",
        ],
    }

    arrangement_notes = (
        "**G major, 4/4 cinematic pop ballad / acoustic anthem (~96 BPM).** "
        "All chords are written in the song's actual key. The chart honors "
        "the **exact bar durations** (mix of 1-, 2-, and 4-bar holds) and "
        "**preserves every slash chord** (D/F#) and characteristic color "
        "(Em7, G6, D9) so the descending bass walk under the verses and the "
        "lifting Am -> D/F# -> G/D -> Em chorus arc remain audible. "
        "Form (10 sections): Intro -> Verse 1 -> Refrain 1 -> Verse 2 -> "
        "Refrain 2 -> Chorus -> Bridge 1 -> Bridge 2 -> Final Chorus -> Outro. "
        "**Bridge 2** lifts modally through **Bm / D / A / E** before the "
        "held **A(4)** vocal climb cues the climactic final chorus. "
        "**Outro** mirrors the chorus shape but swaps plain D for D/F# at "
        "the second turnaround for the intimate closing exhale. "
        "Beginner simplifies Em7 / G6 / D9 to Em / G / D but **keeps every "
        "slash chord exactly**. Intermediate is the canonical chart. "
        "Advanced layers Em9 / Cmaj9 / Am9 / Bm9 / Aadd9 / Gadd9 / sus4 "
        "colors while **preserving Em7, G6, D9, and the D/F# slash chords**. "
        "**One chart bar = one playback bar** - the long sustains are honest, "
        "not a display convention."
    )

    return {
        "key": "G",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": lyric_cues,
        "extensions": _ext(
            arrangement_notes=arrangement_notes,
            default_bpm=96,
            default_groove="Ballad",
            time_signature="4/4",
        ),
    }


def _hotel_california_chart_pack() -> dict[str, Any]:
    """Hotel California - Eagles (B minor, 4/4 laid-back rock).

    The user-supplied reference is in A minor; the chart below is the
    transposition into the song's actual recorded key (B minor):

        Am -> Bm      E7 -> F#7
        G  -> A       D  -> E
        F  -> G       C  -> D
        Dm -> Em

    Harmonic rhythm is **slow and spacious**: every chord is held for
    **four full bars**. One list item = one bar, so a 4-bar chord appears
    as four consecutive identical cells; the chord-follow highlighter and
    backing track honor the long sustain honestly.
    """

    def _hold(chord: str, bars: int) -> list[str]:
        return [chord] * bars

    # The iconic 8-chord descending Hotel California cycle (one chord = 4 bars).
    VERSE_CYCLE = (
        _hold("Bm", 4) + _hold("F#7", 4) + _hold("A", 4) + _hold("E", 4)
        + _hold("G", 4) + _hold("D", 4) + _hold("Em", 4) + _hold("F#7", 4)
    )  # 32 bars

    # Chorus has the same harmonic palette but its own 8-bar voice-leading
    # phrase: G -> D -> F#7 -> Bm, then G -> D -> Em -> F#7 to set up the next
    # verse.
    CHORUS_CYCLE = (
        _hold("G", 4) + _hold("D", 4) + _hold("F#7", 4) + _hold("Bm", 4)
        + _hold("G", 4) + _hold("D", 4) + _hold("Em", 4) + _hold("F#7", 4)
    )  # 32 bars

    # Outro Solo = the iconic Hotel California guitar-solo jam over the same
    # descending 8-chord cycle as the Intro / Verses, repeated FIVE TIMES
    # TOTAL (5 x 32 bars = 160 bars). This is the long extended outro.
    OUTRO_SOLO = (
        list(VERSE_CYCLE)  # cycle 1
        + list(VERSE_CYCLE)  # cycle 2
        + list(VERSE_CYCLE)  # cycle 3
        + list(VERSE_CYCLE)  # cycle 4
        + list(VERSE_CYCLE)  # cycle 5
    )  # 160 bars

    base_sections: dict[str, list[str]] = {
        "Intro": list(VERSE_CYCLE) + list(VERSE_CYCLE),  # 64 bars - two cycles
        "Verse 1A": list(VERSE_CYCLE),                   # 32 bars
        "Verse 1B": list(VERSE_CYCLE),                   # 32 bars
        "Chorus 1": list(CHORUS_CYCLE),                  # 32 bars
        "Verse 2A": list(VERSE_CYCLE),                   # 32 bars
        "Verse 2B": list(VERSE_CYCLE),                   # 32 bars
        "Chorus 2": list(CHORUS_CYCLE),                  # 32 bars
        "Verse 3A": list(VERSE_CYCLE),                   # 32 bars
        "Verse 3B": list(VERSE_CYCLE),                   # 32 bars
        "Outro Solo": list(OUTRO_SOLO),                  # 160 bars - 5 cycles
    }

    section_order: list[str] = [
        "Intro",
        "Verse 1A",
        "Verse 1B",
        "Chorus 1",
        "Verse 2A",
        "Verse 2B",
        "Chorus 2",
        "Verse 3A",
        "Verse 3B",
        "Outro Solo",
    ]

    def _retune(source: dict[str, list[str]], mapper) -> dict[str, list[str]]:
        return {name: [mapper(c) for c in chords] for name, chords in source.items()}

    beginner = {name: list(chords) for name, chords in base_sections.items()}

    # Intermediate: classic Eagles voicings - bass inversions over the
    # descending walk so the line is audible under the long sustains.
    inter_map = {
        "Bm": "Bm",
        "F#7": "F#7/A#",
        "A": "A",
        "E": "E/G#",
        "G": "G",
        "D": "D/F#",
        "Em": "Em",
    }
    intermediate = _retune(base_sections, lambda c: inter_map.get(c, c))
    # The F#7 cadential cell at the end of every verse cycle should resolve
    # straight to Bm - keep it as a plain F#7 (root in the bass) so the V-i
    # punch is audible. Only the descending walk F#7 cells inside the cycle
    # use the F#7/A# inversion.
    for sec_name, chords in intermediate.items():
        # Last 4-bar chord of each 32-bar cycle is the cadential F#7 -
        # restore it to plain F#7 (the inversion is only useful when
        # descending from Bm into A, not when resolving back to Bm/G).
        for cycle_start in range(0, len(chords), 32):
            tail_start = cycle_start + 28
            if tail_start + 4 <= len(chords):
                tail = chords[tail_start:tail_start + 4]
                if all(c == "F#7/A#" for c in tail):
                    for i in range(4):
                        chords[tail_start + i] = "F#7"

    # Advanced: maj9 / m9 / 7b9 colors on top of the same Eagles inversions.
    adv_map = {
        "Bm": "Bm9",
        "F#7": "F#7/A#",
        "A": "Aadd9",
        "E": "E/G#",
        "G": "Gmaj9",
        "D": "D/F#",
        "Em": "Em9",
    }
    advanced = _retune(base_sections, lambda c: adv_map.get(c, c))
    # Same cadential treatment - the resolving F#7 at the end of each cycle
    # gets the b9 tension (the iconic Hotel California "altered V" sound).
    for sec_name, chords in advanced.items():
        for cycle_start in range(0, len(chords), 32):
            tail_start = cycle_start + 28
            if tail_start + 4 <= len(chords):
                tail = chords[tail_start:tail_start + 4]
                if all(c == "F#7/A#" for c in tail):
                    for i in range(4):
                        chords[tail_start + i] = "F#7b9"

    lyric_cues: dict[str, list[str]] = {
        "Intro": [
            "Solo nylon-string guitar arpeggio over the full 8-chord cycle",
            "Twice through the cycle - long, spacious harmonic rhythm",
            "Bass walks Bm -> F#/A# -> A -> E/G# -> G -> D/F# -> Em -> F#",
        ],
        "Verse 1A": [
            "'On a dark desert highway...' - narrative entry",
            "Voice rides the same descending 8-chord arc",
            "Each chord rings for 4 full bars - keep the storytelling spacious",
        ],
        "Verse 1B": [
            "'There she stood in the doorway...' - second half of verse 1",
            "Same descending cycle, builds toward the chorus",
        ],
        "Chorus 1": [
            "Title hook - 'Welcome to the Hotel California'",
            "Phrase 1 lands on Bm (the 'such a lovely place' settling)",
            "Phrase 2 lifts back to F#7 to launch verse 2",
        ],
        "Verse 2A": [
            "'Her mind is Tiffany twisted...' - third verse part A",
            "Returns to the spacious 8-chord cycle",
        ],
        "Verse 2B": [
            "'So I called up the captain...' - third verse part B",
            "Same form; sets up the second chorus / solo section that follows",
        ],
        "Chorus 2": [
            "Second title-hook chorus - 'Welcome to the Hotel California'",
            "Same G -> D -> F#7 -> Bm voice-leading as Chorus 1",
            "Lifts back to F#7 to launch the final verses",
        ],
        "Verse 3A": [
            "'Mirrors on the ceiling...' - final verse part A",
            "Returns to the spacious descending 8-chord cycle",
        ],
        "Verse 3B": [
            "'Last thing I remember...' - final verse part B",
            "Closing lyrical phrase - sustained build into the extended solo",
        ],
        "Outro Solo": [
            "The iconic dual-guitar solo - twin harmonized leads",
            "Cycles the descending Bm -> F#7 -> A -> E -> G -> D -> Em -> F#7 progression FIVE times",
            "Long-form solo territory: tension/release over sustained harmony",
            "Improvise with B natural minor / B harmonic minor (F# major over the F#7 cadences)",
            "Melodic-minor color on the F#7b9 cadential bars (Advanced tier)",
        ],
    }

    arrangement_notes = (
        "**B minor, 4/4 laid-back rock (~75 BPM).** Transposed from the "
        "A-minor reference: **Am->Bm, E7->F#7, G->A, D->E, F->G, C->D, Dm->Em**. "
        "The iconic descending 8-chord verse cycle holds **each chord for 4 "
        "full bars**: Bm -> F#7 -> A -> E -> G -> D -> Em -> F#7 (32 bars). "
        "The chorus uses the same palette in a new voice-leading shape: "
        "G -> D -> F#7 -> Bm -> G -> D -> Em -> F#7 (also 32 bars / 4 bars per "
        "chord). Full form (10 sections): Intro -> Verse 1A -> Verse 1B -> "
        "Chorus 1 -> Verse 2A -> Verse 2B -> Chorus 2 -> Verse 3A -> Verse 3B "
        "-> Outro Solo. The Intro plays the verse cycle **twice** (64 bars of "
        "nylon-guitar arpeggios) before the vocal enters. The **Outro Solo** "
        "repeats the same descending 8-chord cycle **five times total** (160 "
        "bars) - the famous dual-guitar harmonized lead section. Beginner "
        "uses pure triads / dominant sevenths (Bm / F#7 / A / E / G / D / "
        "Em). Intermediate adds the Eagles bass-inversion voice leading - "
        "F#7/A#, E/G#, D/F# - keeping a plain F#7 at the cadential "
        "resolution bars (V -> i / V -> IV). Advanced layers maj9 / m9 "
        "colors and the **F#7b9** altered V for the iconic Hotel California "
        "modal-minor sound. Solo territory: B natural minor + B harmonic "
        "minor (F# major over the F#7 cadences); the Advanced F#7b9 bars "
        "invite F# Phrygian-dominant / melodic-minor lines for the long "
        "outro jam. **One chart bar = one playback bar** so the long "
        "sustained pacing is honest; chord-follow holds each cell for the "
        "full 4-bar window before advancing."
    )

    return {
        "key": "Bm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": lyric_cues,
        "extensions": _ext(
            arrangement_notes=arrangement_notes,
            default_bpm=75,
            default_groove="Rock groove",
            time_signature="4/4",
        ),
    }


def _journey_believin_chart_pack() -> dict[str, Any]:
    """Don't Stop Believin' - Journey (E major, 4/4 arena rock).

    Section-by-section chart. **One list item = one bar.**

    Most chords hold for **2 bars**; the long-sustain choruses hold for
    **4 bars** per chord, with the climactic tag using 1-bar / 3-bar mixes.
    The classic Journey 8-bar piano pattern is built from two cycles:

        E(2) -> B(2) -> C#m(2) -> A(2)        (the iconic first half)
        E(2) -> B(2) -> G#m(2) -> A(2)        (the iconic second half)

    Verses, Interlude 1, Verse 3, Guitar Solo and the Outro all use this
    16-bar engine; the choruses break out into the sustained A/E pedal
    cycle that defines the anthem.
    """

    def _hold(chord: str, bars: int) -> list[str]:
        return [chord] * bars

    # --- Shared engines ---
    JOURNEY_HALF_A = (
        _hold("E", 2) + _hold("B", 2) + _hold("C#m", 2) + _hold("A", 2)
    )  # 8 bars - the iconic first half
    JOURNEY_HALF_B = (
        _hold("E", 2) + _hold("B", 2) + _hold("G#m", 2) + _hold("A", 2)
    )  # 8 bars - second half swaps G#m for C#m
    JOURNEY_CYCLE = list(JOURNEY_HALF_A) + list(JOURNEY_HALF_B)  # 16 bars

    # --- Sections ---
    intro = list(JOURNEY_CYCLE)                            # 16 bars
    verse_1 = list(JOURNEY_CYCLE) + list(JOURNEY_CYCLE)    # 32 bars (2x)
    interlude_1 = list(JOURNEY_CYCLE)                      # 16 bars
    verse_2 = list(JOURNEY_CYCLE)                          # 16 bars

    # Chorus 1 - long-sustain A/E pedal anthem ending with a 6-bar tag
    chorus_1 = (
        _hold("A", 4) + _hold("E", 4)                       # 8
        + _hold("A", 4) + _hold("E", 4)                     # 8
        + _hold("A", 4) + _hold("E", 4)                     # 8
        + _hold("A", 4)                                     # 4
        + _hold("B", 1) + _hold("E", 1) + _hold("B", 1) + _hold("A", 3)  # 6
    )  # 34 bars

    interlude_2 = list(JOURNEY_HALF_A)                     # 8 bars (single half)
    verse_3 = list(JOURNEY_CYCLE) + list(JOURNEY_CYCLE)    # 32 bars (2x)

    # Chorus 2 - same anthem body, ends on a 5-bar tag that sets up the solo
    chorus_2 = (
        _hold("A", 4) + _hold("E", 4)                       # 8
        + _hold("A", 4) + _hold("E", 4)                     # 8
        + _hold("A", 4) + _hold("E", 4)                     # 8
        + _hold("A", 4)                                     # 4
        + _hold("B", 1) + _hold("E", 1) + _hold("B", 3)     # 5
    )  # 33 bars

    guitar_solo = list(JOURNEY_CYCLE)                      # 16 bars (1 cycle)

    outro = (
        list(JOURNEY_CYCLE)                                 # 16
        + list(JOURNEY_CYCLE)                               # 16
        + _hold("E", 2) + _hold("B", 2)                     # 4 (final tag)
    )  # 36 bars

    # Beginner = pure open triads (E, B, C#m, A, G#m) - the user's reference.
    base_sections: dict[str, list[str]] = {
        "Intro": intro,
        "Verse 1": verse_1,
        "Interlude 1": interlude_1,
        "Verse 2": verse_2,
        "Chorus 1": chorus_1,
        "Interlude 2": interlude_2,
        "Verse 3": verse_3,
        "Chorus 2": chorus_2,
        "Guitar Solo / Interlude": guitar_solo,
        "Outro": outro,
    }

    section_order: list[str] = [
        "Intro",
        "Verse 1",
        "Interlude 1",
        "Verse 2",
        "Chorus 1",
        "Interlude 2",
        "Verse 3",
        "Chorus 2",
        "Guitar Solo / Interlude",
        "Outro",
    ]

    def _retune(source: dict[str, list[str]], mapper) -> dict[str, list[str]]:
        return {name: [mapper(c) for c in chords] for name, chords in source.items()}

    beginner = {name: list(chords) for name, chords in base_sections.items()}

    # Intermediate canonical Journey voicings: arena open shapes with bass
    # inversions on B (B/D#) and E (E/G#) that give the rolling piano feel.
    inter_map = {
        "E": "E",
        "B": "B/D#",
        "C#m": "C#m7",
        "A": "Aadd9",
        "G#m": "G#m7",
    }
    intermediate = _retune(base_sections, lambda c: inter_map.get(c, c))
    # The 1-bar B cadential tag bars should punch as a plain B (not the
    # inversion). Restore them to the pure triad after the map pass.
    for chorus_name in ("Chorus 1", "Chorus 2"):
        seq = intermediate[chorus_name]
        for i, ch in enumerate(seq):
            if i >= 28 and ch == "B/D#":
                seq[i] = "B"

    # Advanced: extension-rich anthem voicings - mapped from the pure triads.
    adv_map = {
        "E": "Eadd9",
        "B": "B/D#",
        "C#m": "C#m9",
        "A": "Amaj9",
        "G#m": "G#m9",
    }
    advanced = _retune(base_sections, lambda c: adv_map.get(c, c))
    # Cadential tag uses B13sus for the big anthem lift.
    for chorus_name in ("Chorus 1", "Chorus 2"):
        seq = advanced[chorus_name]
        for i, ch in enumerate(seq):
            if i >= 28 and ch == "B/D#":
                seq[i] = "B13sus"

    lyric_cues: dict[str, list[str]] = {
        "Intro": [
            "Iconic piano intro - 16 bars on the Journey cycle",
            "Bass walks E -> B (D#) -> C#m -> A under the right-hand chord pattern",
        ],
        "Verse 1": [
            "'Just a small-town girl, livin' in a lonely world...'",
            "Vocals enter on the same 16-bar cycle, then repeat the cycle once more",
        ],
        "Interlude 1": [
            "Instrumental link - bass and piano hold the groove for one cycle",
        ],
        "Verse 2": [
            "'A singer in a smoky room...'",
            "Single 16-bar cycle this time; tension builds toward the chorus",
        ],
        "Chorus 1": [
            "Long-sustain anthem - 'Don't stop believin'...'",
            "A/E pedal pattern with 4-bar holds; lift on the final B / E / B / A tag",
        ],
        "Interlude 2": [
            "Short 8-bar interlude - just the first half of the Journey cycle",
            "Resets the groove before the big finish builds",
        ],
        "Verse 3": [
            "'Working hard to get my fill...' - two full cycles",
            "Crowd-singalong territory: keep the dynamics broad",
        ],
        "Chorus 2": [
            "Second long-sustain anthem chorus",
            "Tag ends on B (1) / E (1) / B (3) to launch the guitar solo",
        ],
        "Guitar Solo / Interlude": [
            "Neal Schon-style arena solo over one 16-bar cycle",
            "Stay on E mixolydian / E major pentatonic; phrase across the long holds",
        ],
        "Outro": [
            "Final repeated chorus tag - two full Journey cycles",
            "Tag fade on E (2) / B (2) - the song never truly cadences",
        ],
    }

    arrangement_notes = (
        "**E major, 4/4 arena rock (~119 BPM).** Driving piano + drums groove "
        "built on the classic Journey 16-bar cycle: E(2) -> B(2) -> C#m(2) -> "
        "A(2) || E(2) -> B(2) -> G#m(2) -> A(2). Most chords hold for **2 "
        "bars**; the choruses break into the sustained **A/E pedal anthem** "
        "with **4-bar holds** plus a climactic tag. "
        "Form (10 sections): Intro -> Verse 1 -> Interlude 1 -> Verse 2 -> "
        "Chorus 1 -> Interlude 2 -> Verse 3 -> Chorus 2 -> Guitar Solo / "
        "Interlude -> Outro. **Chorus 1** ends with B(1) / E(1) / B(1) / A(3); "
        "**Chorus 2** ends with B(1) / E(1) / B(3) to set up the solo. The "
        "**Outro** is two full Journey cycles plus an E(2) / B(2) fade tag - "
        "the song never truly resolves, which is part of why it works. "
        "Beginner uses pure open triads (E / B / C#m / A / G#m). Intermediate "
        "adds the canonical arena voicings: B/D# bass inversion, C#m7, Aadd9, "
        "G#m7 - with plain B for the cadential 1-bar tags. Advanced opens up "
        "to maj9 / m9 colors (Eadd9, C#m9, Amaj9, G#m9) and B13sus on the "
        "chorus tag for the big anthem lift. **One chart bar = one playback "
        "bar** - the long sustains are honest, not a display convention."
    )

    return {
        "key": "E",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": lyric_cues,
        "extensions": _ext(
            arrangement_notes=arrangement_notes,
            default_bpm=119,
            default_groove="Rock groove",
            time_signature="4/4",
        ),
    }


def _photograph_chart_pack() -> dict[str, Any]:
    """Photograph — Ed Sheeran (E major, 4/4 modern acoustic pop ballad).

    Transposed from the C-major reference: **C → E, Am → C#m, G → B, F → A**.

    Harmonic rhythm is **slow and sustained**:
      * Intro / Verse / Chorus / Bridge / Outro: each chord = **4 bars**.
      * Pre-Chorus: each chord = **2 bars**.

    One list item = one bar, so a 4-bar chord appears as four consecutive
    identical cells. This keeps backing-track timing and chord-follow
    highlighting honest about the long sustained pacing the song asks for.
    """

    def _hold(chord: str, bars: int) -> list[str]:
        return [chord] * bars

    def _build(tonic: str, sub_med: str, dom: str, sub: str) -> dict[str, list[str]]:
        """Assemble all sections from the four functional roles.

        Roles (E major):
            tonic   = E  (I)
            sub_med = C#m (vi)
            dom     = B  (V)
            sub     = A  (IV)
        """
        intro = (
            _hold(tonic, 4) + _hold(sub_med, 4) + _hold(dom, 4) + _hold(sub, 4)
        )  # 16 bars

        verse_line = (
            _hold(tonic, 4) + _hold(sub_med, 4) + _hold(dom, 4) + _hold(sub, 4)
        )
        verse = verse_line * 2  # 32 bars

        pre_chorus_line = (
            _hold(sub_med, 2) + _hold(sub, 2) + _hold(tonic, 2) + _hold(dom, 2)
        )
        pre_chorus = pre_chorus_line * 2  # 16 bars

        chorus_line = (
            _hold(tonic, 4) + _hold(dom, 4) + _hold(sub_med, 4) + _hold(sub, 4)
        )
        chorus_1 = chorus_line + _hold(tonic, 4)  # 20 bars (single tag)
        chorus_2 = chorus_line * 2  # 32 bars
        chorus_3 = chorus_line * 3  # 48 bars

        bridge = (
            _hold(sub_med, 4) + _hold(sub, 4) + _hold(tonic, 4) + _hold(dom, 4)
        )  # 16 bars

        outro = _hold(tonic, 4)  # 4 bars

        return {
            "Intro": intro,
            "Verse 1": list(verse),
            "Pre-Chorus 1": list(pre_chorus),
            "Chorus 1": list(chorus_1),
            "Verse 2": list(verse),
            "Pre-Chorus 2": list(pre_chorus),
            "Chorus 2": list(chorus_2),
            "Bridge": bridge,
            "Chorus 3": list(chorus_3),
            "Outro": outro,
        }

    # Three tiers — same shape, different voicings.
    beginner = _build("E", "C#m", "B", "A")
    intermediate = _build("Eadd9", "C#m7", "Bsus4", "Aadd9")
    advanced = _build("Emaj9", "C#m11", "B11sus", "Amaj9")

    section_order = [
        "Intro",
        "Verse 1",
        "Pre-Chorus 1",
        "Chorus 1",
        "Verse 2",
        "Pre-Chorus 2",
        "Chorus 2",
        "Bridge",
        "Chorus 3",
        "Outro",
    ]

    lyric_cues: dict[str, list[str]] = {
        "Intro": [
            "Instrumental — solo acoustic + percussion swell",
            "Establish the E → C#m → B → A loop with long sustained chords",
        ],
        "Verse 1": [
            "Story opener — 'Loving can hurt…'",
            "Each chord rings for 4 full bars; let the lyric breathe",
        ],
        "Pre-Chorus 1": [
            "Tension lift — 'So you can keep me…'",
            "Faster harmonic rhythm (2-bar holds) builds toward the chorus",
        ],
        "Chorus 1": [
            "Title hook — 'We keep this love in a photograph'",
            "First chorus ends on a single 4-bar tonic to settle",
        ],
        "Verse 2": [
            "Reflective verse — 'Loving can heal…'",
            "Same 4-bar sustain pattern as Verse 1",
        ],
        "Pre-Chorus 2": [
            "Second tension lift — pre-chorus mirrors the first",
            "Builds into a longer, more emotional Chorus 2",
        ],
        "Chorus 2": [
            "Repeated title hook with a full second pass — no early tag",
        ],
        "Bridge": [
            "Quiet pull-back — 'And if you hurt me…'",
            "Starts on C#m for emotional darkness, lifts through A → E → B",
        ],
        "Chorus 3": [
            "Final triple chorus — biggest emotional peak",
            "Three full passes of the E → B → C#m → A cycle",
        ],
        "Outro": [
            "Single sustained E to close — 'When I'm away, I will remember…'",
        ],
    }

    arrangement_notes = (
        "**E major, 4/4 modern acoustic pop ballad (~108 BPM).** Transposed "
        "from the C-major reference: **C → E, Am → C#m, G → B, F → A**. "
        "Slow, sustained harmonic rhythm: every chord rings for **4 bars** in "
        "Intro / Verses / Choruses / Bridge / Outro; only the **Pre-Choruses** "
        "use **2-bar** holds to lift the energy. Form (10 sections): Intro → "
        "Verse 1 → Pre-Chorus 1 → Chorus 1 → Verse 2 → Pre-Chorus 2 → Chorus 2 "
        "→ Bridge → Chorus 3 → Outro. Chorus 1 ends on a single 4-bar tonic "
        "(20 bars total); Chorus 2 is a full double pass (32 bars); Chorus 3 "
        "is a triple-chorus climax (48 bars). Bridge starts on the vi (C#m) "
        "for emotional darkness before returning to the tonic. "
        "Beginner uses open triads (E / C#m / B / A); Intermediate adds the "
        "Ed Sheeran signature add9 / sus / m7 colors (Eadd9, C#m7, Bsus4, "
        "Aadd9); Advanced opens up to maj9 / m11 / 11sus for sustained-pad "
        "voicings. Guitar players should think strum-and-let-ring; piano "
        "should sustain LH voicings beneath floating RH dyads; horns work "
        "best with long vocal-style phrases that float across the bar lines."
    )

    return {
        "key": "E",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "lyric_cues": lyric_cues,
        "extensions": _ext(
            arrangement_notes=arrangement_notes,
            default_bpm=108,
            default_groove="Modern Acoustic Pop Ballad",
            time_signature="4/4",
        ),
    }


def _say_waiting_lyric_pack(title: str) -> dict[str, Any]:
    """UG-style lyric charts for John Mayer Say / Waiting (main catalog versions)."""
    from song_catalog.lyric_chord_charts import LYRIC_CHORD_CHARTS

    row = LYRIC_CHORD_CHARTS.get((title, "John Mayer"))
    if not row:
        raise ValueError(f"Missing lyric chord chart: {title}")
    inter = dict(row["sections"])
    beg = {k: [c.replace("Em7", "Em").replace("Dm7", "Dm") for c in v] for k, v in inter.items()}
    return {
        "key": row["key"],
        "sections": inter,
        "chart_versions": _levels(beginner=beg, intermediate=inter, advanced=inter),
        "chart_status": "practice_level_verified",
        "guitar_tabs": row.get("guitar_tabs"),
        "extensions": _ext(
            arrangement_notes=row.get("arrangement_notes"),
            default_bpm=row.get("default_bpm"),
            default_groove=row.get("default_groove"),
            lyric_chord_chart=row["chart"],
        ),
    }


def _core_chart_overrides() -> dict[tuple[str, str], dict[str, Any]]:
    """Explicit musician-practice charts for the trusted core library.

    One list item equals one bar. Repeated chords intentionally represent
    repeated measures so the chart renderer and backing track share the same
    harmonic rhythm.
    """

    def pack(
        key,
        beginner,
        intermediate,
        advanced=None,
        status="practice_simplified",
        *,
        lyric_cues: dict[str, list[str]] | None = None,
        extensions: dict[str, Any] | None = None,
        section_order: list[str] | None = None,
    ):
        row = {
            "key": key,
            "sections": intermediate,
            "chart_versions": _levels(
                beginner=beginner,
                intermediate=intermediate,
                advanced=advanced or intermediate,
            ),
            "chart_status": status,
        }
        if lyric_cues:
            row["lyric_cues"] = lyric_cues
        if extensions:
            row["extensions"] = extensions
        if section_order:
            row["section_order"] = list(section_order)
        return row

    return {
        ("Say", "John Mayer"): _say_waiting_lyric_pack("Say"),
        ("Waiting on the World to Change", "John Mayer"): _say_waiting_lyric_pack(
            "Waiting on the World to Change"
        ),
        ("We Are the Champions", "Queen"): _champions_chart_pack(),
        ("Gravity", "John Mayer"): pack("G",
            {
                "Intro / Verse Groove": ["G", "C", "G", "C"],
                "Verse": ["G", "C", "G", "C", "G", "C", "G", "C"],
                "Lift / Turnaround": ["Am", "D7", "Gm/Bb", "Eb", "Am", "D7", "G", "C"],
                "Solo": ["G", "C", "G", "C", "G", "C", "G", "C"],
                "Outro": ["G", "C", "G", "C"],
            },
            {
                "Intro / Verse Groove": ["G", "C/G", "G", "C/G"],
                "Verse": ["G", "C/G", "G", "C/G", "G", "C/G", "G", "C/G"],
                "Lift / Turnaround": ["Am7", "D7", "Gm/Bb", "Ebmaj7", "Am7", "D7", "G", "C/G"],
                "Solo": ["G", "C/G", "G", "C/G", "G", "C/G", "G", "C/G"],
                "Outro": ["G", "C/G", "G", "C/G"],
            },
            {
                "Intro / Verse Groove": ["G6", "Cmaj9/G", "G6", "Cmaj9/G"],
                "Verse": ["G6", "Cmaj9/G", "G6", "Cmaj9/G", "G6", "Cmaj9/G", "G6", "Cmaj9/G"],
                "Chorus": ["Em9", "Cmaj9", "G/D", "D13sus", "Em9", "Cmaj9", "G6", "D13"],
                "Solo": ["G13", "C13", "G13", "G13", "C13", "C13", "G13", "D13"],
                "Outro": ["G6", "Cmaj9/G", "G6", "Cmaj9/G"],
            },
        ),
        # ``Shape of You`` — Ed Sheeran. Form (one chord = one bar in 4/4):
        #   Verse x4 -> Pre-Chorus x4 -> Chorus x8 -> Verse x4 ->
        #   Pre-Chorus x4 -> Chorus x8 -> Bridge (16 bars N.C. breakdown
        #   + 2 loops) -> Final Chorus x8.
        # Repeats are written out so the karaoke cue clock, backing
        # bar timeline, and section-focus practice loop all see the
        # exact bar count without inferring repeats. The 16-bar
        # ``N.C.`` block in the bridge tells the backing engine to
        # drop harmony instruments (bass + comp lay out) so only
        # drums/percussion carry the breakdown.
        ("Shape of You", "Ed Sheeran"): pack(
            "Bm",
            # --- Beginner: one main-loop pass per section so newcomers
            # can lock the groove without losing their place in the
            # form. The bridge keeps the tacet bars so the breakdown
            # cue still surfaces in Karaoke/Practice. ---
            {
                "Verse 1": ["Bm", "Em", "G", "A"],
                "Pre-Chorus 1": ["Bm", "Em", "G", "A"],
                "Chorus 1": ["Bm", "Em", "G", "A"],
                "Verse 2": ["Bm", "Em", "G", "A"],
                "Pre-Chorus 2": ["Bm", "Em", "G", "A"],
                "Chorus 2": ["Bm", "Em", "G", "A"],
                "Bridge": ["N.C."] * 4 + ["Bm", "Em", "G", "A"],
                "Final Chorus": ["Bm", "Em", "G", "A"],
            },
            # --- Intermediate / Authoritative: full per-bar form. ---
            {
                "Verse 1": ["Bm", "Em", "G", "A"] * 4,
                "Pre-Chorus 1": ["Bm", "Em", "G", "A"] * 4,
                "Chorus 1": ["Bm", "Em", "G", "A"] * 8,
                "Verse 2": ["Bm", "Em", "G", "A"] * 4,
                "Pre-Chorus 2": ["Bm", "Em", "G", "A"] * 4,
                "Chorus 2": ["Bm", "Em", "G", "A"] * 8,
                "Bridge": ["N.C."] * 16 + ["Bm", "Em", "G", "A"] * 2,
                "Final Chorus": ["Bm", "Em", "G", "A"] * 8,
            },
            # --- Advanced: extension-rich voicings over the same form
            # (Bm7 / Em7 / Gmaj7 / Aadd9) so the per-bar timing is
            # identical to Intermediate but the comping is jazzier. ---
            {
                "Verse 1": ["Bm7", "Em7", "Gmaj7", "Asus2"] * 4,
                "Pre-Chorus 1": ["Bm7", "Em7", "Gmaj7", "Asus2"] * 4,
                "Chorus 1": ["Bm7", "Em7", "Gmaj7", "Aadd9"] * 8,
                "Verse 2": ["Bm7", "Em7", "Gmaj7", "Asus2"] * 4,
                "Pre-Chorus 2": ["Bm7", "Em7", "Gmaj7", "Asus2"] * 4,
                "Chorus 2": ["Bm7", "Em7", "Gmaj7", "Aadd9"] * 8,
                "Bridge": ["N.C."] * 16 + ["Bm7", "Em7", "Gmaj7", "Aadd9"] * 2,
                "Final Chorus": ["Bm7", "Em7", "Gmaj7", "Aadd9"] * 8,
            },
            status="practice_level_verified",
            lyric_cues={
                "Verse 1": [
                    "The club isn't the best place to find a lover…",
                    "syncopated pickup over the Bm–Em–G–A loop",
                ],
                "Pre-Chorus 1": [
                    "Girl, you know I want your love…",
                    "lift before the hook — hold the A into the chorus",
                ],
                "Chorus 1": [
                    "I'm in love with the shape of you…",
                    "title-hook rhythm — lock the loop for 8 cycles",
                ],
                "Verse 2": [
                    "One week in, we let the story begin…",
                    "same loop, fuller percussion underneath",
                ],
                "Pre-Chorus 2": [
                    "Come on, be my baby, come on…",
                    "second lift — match Pre-Chorus 1 exactly",
                ],
                "Chorus 2": [
                    "I'm in love with the shape of you…",
                    "second chorus — same 8-cycle loop",
                ],
                "Bridge": [
                    "Come on, be my baby, come on… (vocal over N.C.)",
                    "16 bars tacet — drums/percussion only, no chords",
                    "loop returns: Bm–Em–G–A x2 lifts back into the final chorus",
                ],
                "Final Chorus": [
                    "I'm in love with the shape of you…",
                    "final 8-cycle hook — fade on the loop",
                ],
            },
            extensions=_ext(
                arrangement_notes=(
                    "Radio-accurate **Bm–Em–G–A** loop (one chord per bar, 4/4). "
                    "Form: Verse x4 -> Pre-Chorus x4 -> Chorus x8, twice, then a "
                    "bridge that opens with **16 bars of N.C.** (drums/percussion "
                    "only — harmony lays out) before the loop returns x2 and the "
                    "Final Chorus rides x8. Recording key is C#m; transpose with "
                    "Display Key as needed. Default groove: pop syncopation ~96 BPM."
                ),
                default_bpm=96,
                default_groove="Pop groove",
            ),
            section_order=[
                "Verse 1",
                "Pre-Chorus 1",
                "Chorus 1",
                "Verse 2",
                "Pre-Chorus 2",
                "Chorus 2",
                "Bridge",
                "Final Chorus",
            ],
        ),
        ("Perfect", "Ed Sheeran"): _perfect_chart_pack(),
        ("Thinking Out Loud", "Ed Sheeran"): pack("D",
            {
                "Intro": ["D", "D/F#", "G", "A"],
                "Verse": ["D", "D/F#", "G", "A", "D", "D/F#", "G", "A"],
                "Pre-Chorus": ["Em", "A", "D", "Bm", "Em", "A", "D", "A"],
                "Chorus": ["D", "D/F#", "G", "A", "D", "D/F#", "G", "A"],
                "Bridge": ["Bm", "A", "G", "D/F#", "Em", "A", "D", "A"],
            },
            {
                "Intro": ["D", "D/F#", "G", "A7"],
                "Verse": ["D", "D/F#", "G", "A7", "D", "D/F#", "G", "A7"],
                "Pre-Chorus": ["Em7", "A7", "D", "Bm7", "Em7", "A7", "D", "A7"],
                "Chorus": ["D", "D/F#", "G", "A7", "D", "D/F#", "G", "A7"],
                "Bridge": ["Bm7", "A", "G", "D/F#", "Em7", "A7", "D", "A7"],
            },
            {
                "Intro": ["Dmaj9", "D/F#", "Gmaj9", "A13"],
                "Verse": ["Dmaj9", "D/F#", "Gmaj9", "A13", "Dmaj9", "D/F#", "Gmaj9", "A13"],
                "Pre-Chorus": ["Em9", "A13", "Dmaj9", "Bm9", "Em9", "A13", "Dmaj9", "A13"],
                "Chorus": ["Dmaj9", "D/F#", "Gmaj9", "A13", "Dmaj9", "D/F#", "Gmaj9", "A13"],
                "Bridge": ["Bm9", "A13", "Gmaj9", "D/F#", "Em9", "A13", "Dmaj9", "A13"],
            },
        ),
        ("Viva La Vida", "Coldplay"): pack("Ab",
            {
                "Intro": ["Db", "Eb", "Ab", "Fm"],
                "Verse": ["Db", "Eb", "Ab", "Fm", "Db", "Eb", "Ab", "Fm"],
                "Chorus": ["Db", "Eb", "Ab", "Fm", "Db", "Eb", "Ab", "Fm"],
                "Bridge": ["Db", "Eb", "Ab", "Ab", "Db", "Eb", "Ab", "Fm"],
                "Outro": ["Db", "Eb", "Ab", "Fm"],
            },
            {
                "Intro": ["Db", "Eb", "Ab/C", "Fm"],
                "Verse": ["Db", "Eb", "Ab/C", "Fm", "Db", "Eb", "Ab/C", "Fm"],
                "Chorus": ["Db", "Eb", "Ab/C", "Fm", "Db", "Eb", "Ab/C", "Fm"],
                "Bridge": ["Db", "Eb", "Ab", "Ab", "Db", "Eb", "Ab/C", "Fm"],
                "Outro": ["Db", "Eb", "Ab/C", "Fm"],
            },
            {
                "Intro": ["Dbmaj9", "Eb13sus", "Ab/C", "Fm9"],
                "Verse": ["Dbmaj9", "Eb13sus", "Ab/C", "Fm9", "Dbmaj9", "Eb13sus", "Ab/C", "Fm9"],
                "Chorus": ["Dbmaj9", "Eb13sus", "Ab/C", "Fm9", "Dbmaj9", "Eb13sus", "Ab/C", "Fm9"],
                "Bridge": ["Dbmaj9", "Eb13sus", "Abadd9", "Abadd9", "Dbmaj9", "Eb13sus", "Ab/C", "Fm9"],
                "Outro": ["Dbmaj9", "Eb13sus", "Ab/C", "Fm9"],
            },
        ),
        ("Piano Man", "Billy Joel"): _piano_man_chart_pack(),
        ("Photograph", "Ed Sheeran"): _photograph_chart_pack(),
        ("Turn the Lights Back On", "Billy Joel"): pack("C",
            {
                "Intro": ["C", "F/C", "C", "F/C"],
                "Verse": ["C", "F/C", "C", "E7", "Am", "D/F#", "F", "G"],
                "Pre-Chorus": ["F", "G", "Em", "Am", "D/F#", "D7", "G", "G"],
                "Chorus": ["C", "E7", "Am", "D/F#", "F", "G", "C", "G"],
                "Bridge": ["F", "G", "E7/G#", "Am", "D/F#", "D7", "G", "G7"],
            },
            {
                "Intro": ["C", "F/C", "C", "F/C"],
                "Verse": ["C", "F/C", "C", "E7", "Am7", "D/F#", "Fmaj7", "G"],
                "Pre-Chorus": ["Fmaj7", "G", "Em7", "Am7", "D/F#", "D7", "G", "G7"],
                "Chorus": ["C", "E7/G#", "Am7", "D/F#", "Fmaj7", "G", "C", "G"],
                "Bridge": ["Fmaj7", "G", "E7/G#", "Am7", "D/F#", "D7", "G", "G7"],
            },
            {
                "Intro": ["Cmaj9", "Fmaj9/C", "Cmaj9", "Fmaj9/C"],
                "Verse": ["Cmaj9", "Fmaj9/C", "Cmaj9", "E7b9", "Am9", "D13/F#", "Fmaj9", "G13sus"],
                "Pre-Chorus": ["Fmaj9", "G13sus", "Em9", "Am9", "D13/F#", "D13", "G13sus", "G13"],
                "Chorus": ["Cmaj9", "E7b9/G#", "Am9", "D13/F#", "Fmaj9", "G13sus", "Cmaj9", "G13"],
                "Bridge": ["Fmaj9", "G13sus", "E7b9/G#", "Am9", "D13/F#", "D13", "G13sus", "G13"],
            },
        ),
        ("Just the Way You Are", "Billy Joel"): pack("D",
            {
                "Intro": ["D", "Gm/D", "D", "Gm/D"],
                "Verse": ["D", "Bm", "G", "Gm", "D/F#", "B7", "Em", "A"],
                "Chorus": ["G", "A", "F#m", "B7", "Em", "A", "D", "Gm/D"],
                "Bridge": ["Am", "D7", "G", "Gm", "D/F#", "B7", "Em", "A"],
            },
            {
                "Intro": ["Dmaj7", "Gm6/D", "Dmaj7", "Gm6/D"],
                "Verse": ["Dmaj7", "Bm7", "Gmaj7", "Gm6", "D/F#", "B7b9", "Em7", "A7sus4"],
                "Chorus": ["Gmaj7", "A6", "F#m7", "B7b9", "Em7", "A7sus4", "Dmaj7", "Gm6/D"],
                "Bridge": ["Am7", "D9", "Gmaj7", "Gm6", "F#m7", "B7b9", "Em7", "A7sus4"],
            },
            {
                "Intro": ["Dmaj9", "Gm6/D", "Dmaj9", "Gm6/D"],
                "Verse": ["Dmaj9", "Bm9", "Gmaj9", "Gm6", "D/F#", "B7b9", "Em9", "A13"],
                "Chorus": ["Gmaj9", "A13", "F#m9", "B7b9", "Em9", "A13sus", "Dmaj9", "Gm6/D"],
                "Bridge": ["Am9", "D13", "Gmaj9", "Gm6", "F#m9", "B7b9", "Em9", "A13sus"],
            },
        ),
        ("Vienna", "Billy Joel"): pack("Gm",
            {
                "Intro": ["Gm", "Bb", "F", "Ab", "Eb", "Bb", "C", "D"],
                "Verse": ["Gm", "Bb", "F", "Ab", "Eb", "Bb", "C", "D"],
                "Pre-Chorus": ["Eb", "Bb/D", "Cm", "D", "Gm", "F", "Eb", "D"],
                "Chorus": ["Gm", "D/F#", "Gm/F", "C/E", "Eb", "Bb/D", "Cm", "D"],
                "Bridge": ["Am7b5", "D7", "Gm", "C7", "Cm", "F7", "Bb", "D7"],
                "Outro": ["Gm", "Bb", "F", "Ab", "Eb", "D", "Gm", "Gm"],
            },
            {
                "Intro": ["Gm7", "Bb/F", "F", "Abmaj7", "Ebmaj7", "Bb/D", "C7", "D7sus4"],
                "Verse": ["Gm7", "Bb/F", "F", "Abmaj7", "Ebmaj7", "Bb/D", "C7", "D7"],
                "Pre-Chorus": ["Ebmaj7", "Bb/D", "Cm7", "D7", "Gm7", "F", "Ebmaj7", "D7"],
                "Chorus": ["Gm7", "D/F#", "Gm/F", "C/E", "Ebmaj7", "Bb/D", "Cm7", "D7"],
                "Bridge": ["Am7b5", "D7b9", "Gm7", "C7", "Cm7", "F7", "Bbmaj7", "D7b9"],
                "Outro": ["Gm7", "Bb/F", "F", "Abmaj7", "Ebmaj7", "D7", "Gm7", "Gm7"],
            },
            {
                "Intro": ["Gm9", "Bb/F", "F13", "Abmaj9", "Ebmaj9", "Bb/D", "C13", "D7sus4"],
                "Verse": ["Gm9", "Bb/F", "F13", "Abmaj9", "Ebmaj9", "Bb/D", "C13", "D7b9"],
                "Pre-Chorus": ["Ebmaj9", "Bb/D", "Cm9", "D7b9", "Gm9", "F13", "Ebmaj9", "D7b9"],
                "Chorus": ["Gm9", "D7/F#", "Gm9/F", "C13/E", "Ebmaj9", "Bb/D", "Cm9", "D7b9"],
                "Bridge": ["Am7b5", "D7b9", "Gm9", "C13", "Cm9", "F13", "Bbmaj9", "D7b9"],
                "Outro": ["Gm9", "Bb/F", "F13", "Abmaj9", "Ebmaj9", "D7b9", "Gm9", "Gm9"],
            },
        ),
        ("Let It Be", "The Beatles"): pack("C",
            {
                "Intro": ["C", "G", "Am", "F"],
                "Verse": ["C", "G", "Am", "F", "C", "G", "F", "C"],
                "Chorus": ["Am", "G", "F", "C", "C", "G", "F", "C"],
                "Solo": ["C", "G", "Am", "F", "C", "G", "F", "C"],
                "Outro": ["C", "G", "F", "C", "F", "C", "G", "C"],
            },
            {
                "Intro": ["C", "G/B", "Am7", "Fmaj7"],
                "Verse": ["C", "G/B", "Am7", "Fmaj7", "C/G", "G", "F", "C/E"],
                "Chorus": ["Am7", "G", "F", "C/E", "C", "G", "F", "C"],
                "Solo": ["C", "G/B", "Am7", "Fmaj7", "C/G", "G", "F", "C/E"],
                "Outro": ["C", "G", "F", "C", "F", "C/E", "G", "C"],
            },
            {
                "Intro": ["Cadd9", "G/B", "Am9", "Fmaj9"],
                "Verse": ["Cadd9", "G/B", "Am9", "Fmaj9", "C/G", "G13sus", "Fmaj9", "C/E"],
                "Chorus": ["Am9", "G13sus", "Fmaj9", "C/E", "Cadd9", "G13sus", "Fmaj9", "Cadd9"],
                "Solo": ["Cadd9", "G/B", "Am9", "Fmaj9", "C/G", "G13sus", "Fmaj9", "C/E"],
                "Outro": ["Cadd9", "G13sus", "Fmaj9", "Cadd9", "Fmaj9", "C/E", "G13sus", "Cadd9"],
            },
        ),
        ("Hey Jude", "The Beatles"): pack("F",
            {
                "Intro": ["F", "C", "C7", "F"],
                "Verse": ["F", "C", "C7", "F", "Bb", "F", "C", "F"],
                "Bridge / Build": ["F7", "Bb", "Bb/A", "Bb/G", "Bb/F", "C7", "F", "F"],
                "Outro Vamp": ["F", "F7", "Eb", "Bb", "F", "F7", "Eb", "Bb"],
            },
            {
                "Intro": ["F", "C/E", "C7", "F"],
                "Verse": ["F", "C/E", "C7", "F", "Bb", "F/A", "C7", "F"],
                "Bridge / Build": ["F7", "Bb", "Bb/A", "Bb/G", "Bb/F", "C7", "F", "F"],
                "Outro Vamp": ["F6", "F7", "Eb", "Bb", "F6", "F7", "Eb", "Bb"],
            },
            {
                "Intro": ["F", "C/E", "C7", "F"],
                "Verse": ["F", "C/E", "C7", "F", "Bb", "F/A", "C7", "F"],
                "Bridge / Build": ["F7", "Bb", "Bb/A", "Bb/G", "Bb/F", "C7", "F", "F"],
                "Outro Vamp": ["F6", "F7", "Eb", "Bb", "F6", "F7", "Eb", "Bb"],
            },
        ),
        ("Yesterday", "The Beatles"): pack("F",
            {
                "Intro": ["F", "F"],
                "Verse": ["F", "Em", "A7", "Dm", "Dm", "Bb", "C7", "F"],
                "Middle Eight": ["Bb", "C7", "F", "Dm", "Gm", "C7", "F", "F"],
                "Return / Tag": ["F", "Em", "A7", "Dm", "Gm", "C7", "F", "F"],
            },
            {
                "Intro": ["Fmaj7", "F6"],
                "Verse": ["F", "Em7", "A7", "Dm", "Dm/C", "Bbmaj7", "C7", "F"],
                "Middle Eight": ["Bbmaj7", "C7", "F/A", "Dm7", "Gm7", "C7", "Fmaj7", "F6"],
                "Return / Tag": ["F", "Em7", "A7", "Dm", "Gm7", "C7", "Fmaj7", "F6"],
            },
            {
                "Intro": ["Fmaj9", "F6add9"],
                "Verse": ["Fmaj9", "Em7b5", "A7b9", "Dm9", "Dm9/C", "Bbmaj9", "C13", "Fmaj9"],
                "Middle Eight": ["Bbmaj9", "C13", "F/A", "Dm9", "Gm9", "C13", "Fmaj9", "F6add9"],
                "Return / Tag": ["Fmaj9", "Em7b5", "A7b9", "Dm9", "Gm9", "C13", "Fmaj9", "F6add9"],
            },
        ),
        ("Here Comes the Sun", "The Beatles"): pack("A",
            {
                "Intro": ["A", "D", "E7", "A"],
                "Verse": ["A", "D", "E7", "A", "A", "D", "E7", "A"],
                "Chorus": ["D", "B7", "E7", "A", "D", "B7", "E7", "A"],
                "Bridge": ["C", "G", "D", "A", "C", "G", "D", "E7"],
                "Outro": ["A", "D", "E7", "A"],
            },
            {
                "Intro": ["A", "D/A", "E7/A", "A"],
                "Verse": ["A", "D/F#", "E7", "A", "A", "D/F#", "E7", "A"],
                "Chorus": ["Dmaj7", "B7", "E7", "A", "Dmaj7", "B7", "E7", "A"],
                "Bridge": ["C", "G/B", "D", "A", "C", "G/B", "D", "E7"],
                "Outro": ["A", "D/F#", "E7", "A"],
            },
            {
                "Intro": ["Aadd9", "Dmaj9/A", "E13/A", "Aadd9"],
                "Verse": ["Aadd9", "Dmaj9/F#", "E13", "Aadd9", "Aadd9", "Dmaj9/F#", "E13", "Aadd9"],
                "Chorus": ["Dmaj9", "B13", "E13", "Aadd9", "Dmaj9", "B13", "E13", "Aadd9"],
                "Bridge": ["Cadd9", "G/B", "Dadd9", "Aadd9", "Cadd9", "G/B", "Dadd9", "E13"],
                "Outro": ["Aadd9", "Dmaj9/F#", "E13", "Aadd9"],
            },
        ),
        ("Don't Stop Believin'", "Journey"): _journey_believin_chart_pack(),
        ("Hotel California", "Eagles"): _hotel_california_chart_pack(),
        ("Shallow", "Lady Gaga / Bradley Cooper"): _shallow_chart_pack(),
        ("The Girl from Ipanema", "Antonio Carlos Jobim"): pack("F",
            {
                "Intro": ["Gm", "C7", "Gm", "C7"],
                "A Section": ["F", "F", "G7", "G7", "Gm", "Gb7", "F", "Gb7"],
                "B Section": ["Gb", "Gb", "B7", "B7", "F#m", "B7", "Gm", "C7"],
                "Final A / Outro": ["Gm", "C7", "F", "F"],
            },
            {
                "Intro": ["Gm7", "C7", "Gm7", "C7"],
                "A Section": ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"],
                "B Section": ["Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "B7", "Gm7", "C7"],
                "Final A / Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
            },
            {
                "Intro": ["Gm9", "C13", "Gm9", "C13"],
                "A Section": ["Fmaj9", "Fmaj9", "G13", "G13", "Gm9", "Gb13", "Fmaj9", "Gb13"],
                "B Section": ["Gbmaj9", "Gbmaj9", "B13", "B13", "F#m9", "B13", "Gm9", "C13"],
                "Final A / Outro": ["Gm9", "C13", "Fmaj9", "F6add9"],
            },
        ),
        ("Wave", "Antonio Carlos Jobim"): pack("D",
            {
                "Intro": ["D", "D", "D", "D"],
                "A Section": ["D", "Bbdim7", "Am", "D7", "G", "Gm", "F#7", "B7"],
                "B Section": ["Em", "A7", "D", "D", "Fm", "Bb7", "Eb", "A7"],
                "Final A / Outro": ["D", "Bbdim7", "Am", "D7", "G", "Gm", "D", "A7"],
            },
            {
                "Intro": ["Dmaj7", "Dmaj7", "Dmaj7", "Dmaj7"],
                "A Section": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "F#7", "B7b9"],
                "B Section": ["Em9", "A13", "Dmaj9", "Dmaj9", "Fm9", "Bb13", "Ebmaj9", "A7b13"],
                "Final A / Outro": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "Dmaj9", "A13"],
            },
            {
                "Intro": ["Dmaj9", "D6add9", "Dmaj9", "D6add9"],
                "A Section": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "F#13", "B7b9"],
                "B Section": ["Em9", "A13", "Dmaj9", "D6add9", "Fm9", "Bb13", "Ebmaj9", "A7b13"],
                "Final A / Outro": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "Dmaj9", "A13"],
            },
        ),
        ("Blue Bossa", "Kenny Dorham"): pack(
            "Cm",
            {
                "A Section": ["Cm", "Cm", "Fm", "Fm", "Dm7b5", "G7", "Cm", "Cm"],
                "B Section": ["Ebm", "Ab7", "Db", "Db", "Dm7b5", "G7", "Cm", "G7"],
            },
            {
                "A Section": ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7", "Cm7", "Cm7"],
                "B Section": ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "G7"],
            },
            {
                "A Section": ["Cm9", "Cm9", "Fm9", "Fm9", "Dm7b5", "G7b9", "Cm9", "Cm9"],
                "B Section": ["Ebm9", "Ab13", "Dbmaj9", "Dbmaj9", "Dm7b5", "G7b9", "Cm9", "G7b9"],
            },
            extensions=_ext(
                default_bpm=100,
                default_groove="Bossa nova",
                arrangement_notes="Latin jazz bossa — ~100 BPM; A/B sections, one chord per bar.",
            ),
        ),
        ("Autumn Leaves", "Jazz Standard"): pack("Gm",
            {
                "Intro": ["Am7b5", "D7", "Gm", "Gm"],
                "A Section": ["Cm", "F7", "Bb", "Eb", "Am7b5", "D7", "Gm", "Gm"],
                "B Section": ["Am7b5", "D7", "Gm", "Gm", "Cm", "F7", "Bb", "Eb"],
                "Final A": ["Am7b5", "D7", "Gm", "C7", "Fm", "Bb7", "Eb", "D7"],
            },
            {
                "Intro": ["Am7b5", "D7b9", "Gm7", "Gm7"],
                "A Section": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7b9", "Gm7", "Gm7"],
                "B Section": ["Am7b5", "D7b9", "Gm7", "Gm7", "Cm7", "F7", "Bbmaj7", "Ebmaj7"],
                "Final A": ["Am7b5", "D7b9", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7", "D7b9"],
            },
            {
                "Intro": ["Am7b5", "D7b9", "Gm9", "Gm9"],
                "A Section": ["Cm9", "F13", "Bbmaj9", "Ebmaj9", "Am7b5", "D7b9", "Gm9", "Gm9"],
                "B Section": ["Am7b5", "D7b9", "Gm9", "Gm9", "Cm9", "F13", "Bbmaj9", "Ebmaj9"],
                "Final A": ["Am7b5", "D7b9", "Gm9", "C13", "Fm9", "Bb13", "Ebmaj9", "D7b9"],
            },
        ),
        ("Fly Me to the Moon", "Bart Howard"): pack("C",
            {
                "A1": ["Am", "Dm", "G7", "C", "F", "Bm7b5", "E7", "Am"],
                "A2": ["A7", "Dm", "G7", "C", "E7", "Am", "A7", "Dm"],
                "Bridge": ["Dm", "G7", "C", "Am", "Dm", "G7", "C", "E7"],
                "Final A / Tag": ["Am", "Dm", "G7", "C", "F", "Bm7b5", "E7", "Am"],
            },
            {
                "A1": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
                "A2": ["A7", "Dm7", "G7", "Cmaj7", "E7", "Am7", "A7", "Dm7"],
                "Bridge": ["Dm7", "G7", "Cmaj7", "Am7", "Dm7", "G7", "Cmaj7", "E7"],
                "Final A / Tag": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
            },
            {
                "A1": ["Am9", "Dm9", "G13", "Cmaj9", "Fmaj9", "Bm7b5", "E7b9", "Am9"],
                "A2": ["A7b9", "Dm9", "G13", "Cmaj9", "E7b9", "Am9", "A7b9", "Dm9"],
                "Bridge": ["Dm9", "G13", "Cmaj9", "Am9", "Dm9", "G13", "Cmaj9", "E7b9"],
                "Final A / Tag": ["Am9", "Dm9", "G13", "Cmaj9", "Fmaj9", "Bm7b5", "E7b9", "Am9"],
            },
        ),
        ("So Nice (Summer Samba)", "Marcos Valle"): pack(
            "F",
            {
                "Intro": ["F", "F", "F", "F", "F", "F", "F", "F"],
                "Verse": [
                    "F", "F", "F", "F",
                    "Bm", "E7", "Bm", "E7",
                    "Bb", "Bb", "Bb", "Bb",
                    "Bbm", "Bbm", "Bbm", "Bbm",
                ],
                "Chorus": [
                    "Am", "D7", "Gm", "C7",
                    "Em", "A7", "Dm",
                    "G7", "Gm", "C7", "C7",
                ],
                "Chorus (alternate)": [
                    "Am", "D7", "Gm", "C7",
                    "F", "Bb", "F",
                ],
            },
            {
                "Intro": ["Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6"],
                "Verse": [
                    "Fmaj7", "F6", "Fmaj7", "F6",
                    "Bm7", "E9", "Bm7", "E9",
                    "Bbmaj7", "Bb6", "Bbmaj7", "Bb6",
                    "Bbm7", "Bbm6", "Bbm7", "Bbm6",
                ],
                "Chorus": [
                    "Am7", "D7b9", "Gm7", "C7b9",
                    "Em7b5", "A7#5", "Dm9",
                    "G13", "Gm7", "C#9", "C9",
                ],
                "Chorus (alternate)": [
                    "Am7", "D7b9", "Gm7", "C7b9",
                    "Fmaj7", "Bb7", "Fmaj7",
                ],
            },
            status="practice_level_verified",
            lyric_cues={
                "Intro": ["samba pickup — keep Fmaj7/F6 bounce light"],
                "Verse": ["lyric entrance over I–VI–bVII–iv color"],
                "Chorus": ["lift into ii–V–I minor then back to F"],
                "Chorus (alternate)": ["shorter tag — resolve on Fmaj7"],
            },
            extensions=_ext(
                default_bpm=135,
                default_groove="Bossa nova",
                arrangement_notes=(
                    "Bossa/samba form in **F** — one chord per bar. "
                    "Use **Chorus (alternate)** for later passes; default groove ~135 BPM."
                ),
            ),
        ),
        ("One Note Samba", "Antonio Carlos Jobim"): pack(
            "Db",
            {
                "Verse": [
                    "Dbm", "C7", "B7", "Bb7",
                    "Dbm", "C7", "B7", "Bb7",
                    "Em", "A7", "D", "Dm", "G7",
                    "Dbm", "C7", "B7", "Bb7", "A",
                ],
                "Chorus": [
                    "Dm", "G7", "C",
                    "Cm", "F7", "Bb",
                    "Bdim", "Bb7",
                ],
                "Ending / Tag": [
                    "Dbm", "C7", "B7", "Bb7",
                    "Dbm", "C7", "B7", "Bb7",
                    "Em", "A7", "D", "Dm", "G7",
                    "C6", "B7", "Bb", "A7",
                ],
            },
            {
                "Verse": [
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                    "Dbm7", "C7", "B7sus4", "Bb7b5", "A6/9",
                ],
                "Chorus": [
                    "Dm7", "G7", "Cmaj7",
                    "Cm7", "F7", "Bbmaj7",
                    "Bdim", "Bb7b5",
                ],
                "Ending / Tag": [
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                    "C6", "B7", "Bbmaj7", "A7",
                ],
            },
            status="practice_level_verified",
            lyric_cues={
                "Verse": ["single-note melody over shifting dominants"],
                "Chorus": ["opens in C major — sing the guide tone through Dm7–G7–Cmaj7"],
                "Ending / Tag": ["repeat verse colors then tag on C6–B7–Bbmaj7–A7"],
            },
            extensions=_ext(
                default_bpm=130,
                default_groove="Bossa nova",
                arrangement_notes=(
                    "Classic Jobim bossa — verse in **Db** minor area, chorus in **C** major. "
                    "One chord cell = one bar for backing and section practice."
                ),
            ),
        ),
    }


def _requested_verified_song_records() -> list[dict[str, Any]]:
    """Practice-level verified additions requested for the core picker.

    Charts use one list item per bar so chart display, section bar counts,
    and synthesized backing tracks share the same harmonic timeline.
    """

    status = "practice_level_verified"

    def note(text: str) -> dict[str, Any]:
        return _ext(arrangement_notes=text)

    def v(
        title: str,
        artist: str,
        genre: str,
        key: str,
        beginner: dict[str, list[str]],
        intermediate: dict[str, list[str]],
        *,
        advanced: dict[str, list[str]] | None = None,
        composer: str | None = None,
        lyric_cues: dict[str, list[str]] | None = None,
        guitar_tabs: dict[str, str] | None = None,
        notes: str | None = None,
        chart_status: str | None = None,
        default_bpm: int | None = None,
        default_groove: str | None = None,
    ) -> dict[str, Any]:
        ext = note(notes or "Practice-level verified form; one chord cell equals one bar.")
        if default_bpm:
            ext["default_bpm"] = int(default_bpm)
        if default_groove:
            ext["default_groove"] = default_groove
        return _s(
            title,
            artist,
            genre,
            key,
            intermediate,
            composer=composer,
            lyric_cues=lyric_cues,
            guitar_tabs=guitar_tabs,
            chart_status=chart_status or status,
            chart_versions=_levels(
                beginner=beginner,
                intermediate=intermediate,
                advanced=advanced or intermediate,
            ),
            extensions=ext,
        )

    def core_ref(
        title: str,
        artist: str,
        *,
        composer: str | None = None,
    ) -> dict[str, Any]:
        ref = reference_for(title, artist)
        if not ref:
            raise ValueError(f"Missing verified core reference: {title} — {artist}")
        inter = ref["sections"]
        beg = ref.get("beginner") or inter
        adv = ref.get("advanced") or inter
        row = v(
            title,
            artist,
            ref["genre"],
            ref["key"],
            beg,
            inter,
            advanced=adv,
            composer=composer,
            lyric_cues=lyric_cues_for_reference(title, artist),
            guitar_tabs=ref.get("guitar_tabs"),
            notes=ref.get("arrangement_notes"),
            chart_status=status,
        )
        ext_patch: dict[str, Any] = dict(row.get("extensions") or {})
        if ref.get("default_bpm"):
            ext_patch["default_bpm"] = int(ref["default_bpm"])
        if ref.get("default_groove"):
            ext_patch["default_groove"] = str(ref["default_groove"])
        if ref.get("time_signature"):
            ext_patch["time_signature"] = str(ref["time_signature"])
        if ext_patch:
            row["extensions"] = ext_patch
        if ref.get("section_order"):
            row["section_order"] = list(ref["section_order"])
        return row

    return [
        v(
            "Shallow",
            "Lady Gaga / Bradley Cooper",
            "Pop",
            "G",
            {
                "Intro (6/8)": ["Em", "D/F#", "G", "C"],
                "Verse": ["Em", "D/F#", "G", "C", "Em", "D/F#", "G", "C"],
                "Pre-Chorus": ["Am", "D", "G", "C", "Am", "D", "G", "D"],
                "Chorus": ["G", "D/F#", "Em", "D", "C", "G/B", "Am", "D"],
                "Bridge / Vocal Climb": ["Em", "D/F#", "G", "C", "Am", "D", "G", "D"],
                "Final Chorus / Outro": ["G", "D/F#", "Em", "D", "C", "G/B", "Am", "D", "G", "G"],
            },
            {
                "Intro (6/8)": ["Em7", "D/F#", "G", "Cadd9"],
                "Verse": ["Em7", "D/F#", "G", "Cadd9", "Em7", "D/F#", "G", "Cadd9"],
                "Pre-Chorus": ["Am7", "D", "G/B", "Cadd9", "Am7", "D", "G", "D/F#"],
                "Chorus": ["G", "D/F#", "Em7", "D", "Cadd9", "G/B", "Am7", "D"],
                "Bridge / Vocal Climb": ["Em7", "D/F#", "G", "Cadd9", "Am7", "D", "G", "D"],
                "Final Chorus / Outro": ["G", "D/F#", "Em7", "D", "Cadd9", "G/B", "Am7", "D", "G", "G"],
            },
            advanced={
                "Intro (6/8)": ["Em9", "D/F#", "Gadd9", "Cmaj9"],
                "Verse": ["Em9", "D/F#", "Gadd9", "Cmaj9", "Em9", "D/F#", "Gadd9", "Cmaj9"],
                "Pre-Chorus": ["Am9", "D13sus", "G/B", "Cmaj9", "Am9", "D13sus", "Gadd9", "D/F#"],
                "Chorus": ["Gadd9", "D/F#", "Em9", "D", "Cmaj9", "G/B", "Am9", "D13sus"],
                "Bridge / Vocal Climb": ["Em9", "D/F#", "Gadd9", "Cmaj9", "Am9", "D13sus", "Gadd9", "D13sus"],
                "Final Chorus / Outro": ["Gadd9", "D/F#", "Em9", "D", "Cmaj9", "G/B", "Am9", "D13sus", "Gadd9", "Gadd9"],
            },
            composer="Lady Gaga, Mark Ronson, Anthony Rossomando & Andrew Wyatt",
            lyric_cues={
                "Verse": ["quiet character setup", "question-answer duet entrance"],
                "Chorus": ["title-hook lift", "open vowel sustain"],
                "Bridge / Vocal Climb": ["build toward the high register", "keep breath low before the peak"],
            },
            guitar_tabs={"G": "320003", "D/F#": "2x0232", "Em7": "022030", "Cadd9": "x32030", "Am7": "x02010"},
            notes="Original-feel 6/8 ballad chart; chorus includes the G/B-Am-D lift before each resolution.",
        ),
        v(
            "All of Me",
            "John Legend",
            "Pop",
            "Ab",
            {
                "Intro / Verse": ["Fm", "Db", "Ab", "Eb"] * 2,
                "Pre-Chorus": ["Db", "Ab", "Eb", "Fm", "Db", "Ab", "Eb", "Eb"],
                "Chorus": ["Ab", "Fm", "Db", "Eb", "Ab", "Fm", "Db", "Eb"],
                "Bridge": ["Fm", "Db", "Ab", "Eb", "Fm", "Db", "Ab", "Eb"],
                "Outro": ["Ab", "Fm", "Db", "Eb", "Ab", "Ab"],
            },
            {
                "Intro / Verse": ["Fm7", "Dbadd9", "Ab", "Eb/G"] * 2,
                "Pre-Chorus": ["Dbadd9", "Ab/C", "Eb", "Fm7", "Dbadd9", "Ab/C", "Eb", "Eb"],
                "Chorus": ["Ab", "Fm7", "Dbadd9", "Eb", "Ab", "Fm7", "Dbadd9", "Eb"],
                "Bridge": ["Fm7", "Dbadd9", "Ab", "Eb/G", "Fm7", "Dbadd9", "Ab", "Eb"],
                "Outro": ["Ab", "Fm7", "Dbadd9", "Eb", "Ab", "Ab"],
            },
            advanced={
                "Intro / Verse": ["Fm9", "Dbmaj9", "Abadd9", "Eb/G"] * 2,
                "Pre-Chorus": ["Dbmaj9", "Ab/C", "Eb13sus", "Fm9", "Dbmaj9", "Ab/C", "Eb13sus", "Eb13"],
                "Chorus": ["Abadd9", "Fm9", "Dbmaj9", "Eb13sus", "Abadd9", "Fm9", "Dbmaj9", "Eb13sus"],
                "Bridge": ["Fm9", "Dbmaj9", "Abadd9", "Eb/G", "Fm9", "Dbmaj9", "Abadd9", "Eb13sus"],
                "Outro": ["Abadd9", "Fm9", "Dbmaj9", "Eb13sus", "Abadd9", "Abadd9"],
            },
            composer="John Legend & Toby Gad",
            lyric_cues={"Intro / Verse": ["intimate piano entry"], "Chorus": ["title-hook declaration"], "Bridge": ["vow-like build"]},
            notes="Piano ballad in Ab; slash bass keeps the verse descent clear while preserving one bar per cell.",
        ),
        v(
            "Attention",
            "Charlie Puth",
            "Pop",
            "Ebm",
            {
                "Bass Intro / Verse": ["Ebm", "Db", "Bbm", "B"] * 2,
                "Pre-Chorus": ["Ebm", "Db", "Bbm", "B", "Ebm", "Db", "Bbm", "B"],
                "Chorus": ["Ebm", "Db", "Bbm", "B"] * 2,
                "Bridge / Breakdown": ["B", "Db", "Ebm", "Bbm", "B", "Db", "Ebm", "Ebm"],
                "Outro Vamp": ["Ebm", "Db", "Bbm", "B"],
            },
            {
                "Bass Intro / Verse": ["Ebm7", "Db", "Bbm7", "Bmaj7"] * 2,
                "Pre-Chorus": ["Ebm7", "Db", "Bbm7", "Bmaj7", "Ebm7", "Db", "Bbm7", "Bmaj7"],
                "Chorus": ["Ebm7", "Db", "Bbm7", "Bmaj7"] * 2,
                "Bridge / Breakdown": ["Bmaj7", "Db", "Ebm7", "Bbm7", "Bmaj7", "Db", "Ebm7", "Ebm7"],
                "Outro Vamp": ["Ebm7", "Db", "Bbm7", "Bmaj7"],
            },
            advanced={
                "Bass Intro / Verse": ["Ebm9", "Dbadd9", "Bbm9", "Bmaj9"] * 2,
                "Pre-Chorus": ["Ebm9", "Dbadd9", "Bbm9", "Bmaj9", "Ebm9", "Dbadd9", "Bbm9", "Bmaj9"],
                "Chorus": ["Ebm9", "Dbadd9", "Bbm9", "Bmaj9"] * 2,
                "Bridge / Breakdown": ["Bmaj9", "Dbadd9", "Ebm9", "Bbm9", "Bmaj9", "Dbadd9", "Ebm9", "Ebm9"],
                "Outro Vamp": ["Ebm9", "Dbadd9", "Bbm9", "Bmaj9"],
            },
            composer="Charlie Puth & Jacob Kasher",
            lyric_cues={"Bass Intro / Verse": ["tight bass-pocket entry"], "Pre-Chorus": ["lift before hook"], "Chorus": ["syncopated title hook"]},
            notes="Funk-pop loop chart in Eb minor; backing track follows the bass-harmony cycle section by section.",
        ),
        v(
            "Hotel California",
            "Eagles",
            "Rock",
            "Bm",
            {
                "Intro / Verse": ["Bm", "F#", "A", "E", "G", "D", "Em", "F#"] * 2,
                "Chorus": ["G", "D", "F#", "Bm", "G", "D", "Em", "F#"],
                "Guitar Solo": ["Bm", "F#", "A", "E", "G", "D", "Em", "F#"] * 2,
                "Outro Solo Vamp": ["Bm", "F#", "A", "E", "G", "D", "Em", "F#"],
            },
            {
                "Intro / Verse": ["Bm", "F#7/A#", "A", "E/G#", "G", "D/F#", "Em", "F#7"] * 2,
                "Chorus": ["G", "D/F#", "F#7", "Bm", "G", "D/F#", "Em", "F#7"],
                "Guitar Solo": ["Bm", "F#7/A#", "A", "E/G#", "G", "D/F#", "Em", "F#7"] * 2,
                "Outro Solo Vamp": ["Bm", "F#7/A#", "A", "E/G#", "G", "D/F#", "Em", "F#7"],
            },
            advanced={
                "Intro / Verse": ["Bm9", "F#7/A#", "Aadd9", "E/G#", "Gmaj9", "D/F#", "Em9", "F#7b9"] * 2,
                "Chorus": ["Gmaj9", "D/F#", "F#7b9", "Bm9", "Gmaj9", "D/F#", "Em9", "F#7b9"],
                "Guitar Solo": ["Bm9", "F#7/A#", "Aadd9", "E/G#", "Gmaj9", "D/F#", "Em9", "F#7b9"] * 2,
                "Outro Solo Vamp": ["Bm9", "F#7/A#", "Aadd9", "E/G#", "Gmaj9", "D/F#", "Em9", "F#7b9"],
            },
            composer="Don Felder, Don Henley & Glenn Frey",
            lyric_cues={"Intro / Verse": ["narrative desert arrival"], "Chorus": ["title-hotel refrain"], "Guitar Solo": ["dual-guitar lead form"]},
            guitar_tabs={"Bm": "x24432", "F#7": "242322", "A": "x02220", "E/G#": "4x245x", "G": "320003", "D/F#": "2x0232", "Em": "022000"},
            notes="Classic 8-bar descending verse cycle; solo uses the same harmonic form for accurate practice looping.",
        ),
        v(
            "Californication",
            "Red Hot Chili Peppers",
            "Rock",
            "Am",
            {
                "Intro / Verse Riff": ["Am", "F", "Am", "F", "Am", "F", "Am", "F"],
                "Pre-Chorus": ["C", "G", "F", "Dm", "C", "G", "F", "Dm"],
                "Chorus": ["Am", "F", "C", "G", "Am", "F", "C", "G"],
                "Guitar Solo": ["F#m", "D", "F#m", "D", "Bm", "D", "A", "E"],
                "Outro": ["Am", "F", "C", "G"],
            },
            {
                "Intro / Verse Riff": ["Am", "Fmaj7", "Am", "Fmaj7", "Am", "Fmaj7", "Am", "Fmaj7"],
                "Pre-Chorus": ["C", "G", "Fmaj7", "Dm", "C", "G", "Fmaj7", "Dm"],
                "Chorus": ["Am", "Fmaj7", "C", "G", "Am", "Fmaj7", "C", "G"],
                "Guitar Solo": ["F#m", "D", "F#m", "D", "Bm", "D", "A", "E"],
                "Outro": ["Am", "Fmaj7", "C", "G"],
            },
            composer="Red Hot Chili Peppers",
            lyric_cues={"Intro / Verse Riff": ["low conversational riff entry"], "Chorus": ["wide melodic hook"], "Guitar Solo": ["relative minor solo color"]},
            guitar_tabs={"Am": "x02210", "Fmaj7": "1x2210", "C": "x32010", "G": "320003", "Dm": "xx0231"},
        ),
        v(
            "Iris",
            "Goo Goo Dolls",
            "Rock",
            "Bm",
            {
                "Intro": ["Bm", "G", "D", "A"] * 2,
                "Verse": ["Bm", "G", "D", "A", "Bm", "G", "D", "A"],
                "Pre-Chorus": ["Em", "G", "Bm", "A", "Em", "G", "A", "A"],
                "Chorus": ["D", "A", "Em", "G", "D", "A", "G", "G"],
                "Bridge": ["Bm", "A", "G", "G", "Bm", "A", "G", "A"],
                "Outro": ["D", "A", "Em", "G", "D", "D"],
            },
            {
                "Intro": ["Bm7", "Gadd9", "D", "Asus4"] * 2,
                "Verse": ["Bm7", "Gadd9", "D", "Asus4", "Bm7", "Gadd9", "D", "Asus4"],
                "Pre-Chorus": ["Em7", "Gadd9", "Bm7", "A", "Em7", "Gadd9", "Asus4", "A"],
                "Chorus": ["D", "A/C#", "Em7", "Gadd9", "D", "A/C#", "Gadd9", "Gadd9"],
                "Bridge": ["Bm7", "A", "Gadd9", "Gadd9", "Bm7", "A", "Gadd9", "A"],
                "Outro": ["D", "A/C#", "Em7", "Gadd9", "D", "D"],
            },
            composer="John Rzeznik",
            lyric_cues={"Verse": ["introspective low entry"], "Pre-Chorus": ["confessional lift"], "Chorus": ["big open hook"]},
            notes="Practice chart in concert B minor; original guitar uses altered tuning, so voicings are normalized for app playback.",
        ),
        v(
            "Take Me Home, Country Roads",
            "John Denver",
            "Country",
            "A",
            {
                "Intro": ["A", "A", "F#m", "F#m", "E", "E", "D", "A"],
                "Verse": ["A", "F#m", "E", "D", "A", "A", "E", "E"],
                "Chorus": ["A", "E", "F#m", "D", "A", "E", "D", "A"],
                "Bridge": ["F#m", "E/G#", "A", "D", "A", "E", "D", "A"],
                "Outro": ["A", "E", "D", "A"],
            },
            {
                "Intro": ["A", "A", "F#m7", "F#m7", "E", "E", "D", "A"],
                "Verse": ["A", "F#m7", "E", "D", "A", "A", "E", "E"],
                "Chorus": ["A", "E/G#", "F#m7", "D", "A", "E", "D", "A"],
                "Bridge": ["F#m7", "E/G#", "A", "D", "A", "E", "D", "A"],
                "Outro": ["A", "E/G#", "D", "A"],
            },
            composer="John Denver, Bill Danoff & Taffy Nivert",
            lyric_cues={"Intro": ["acoustic pickup / establish tempo"], "Verse": ["place-name storytelling"], "Chorus": ["homeward title hook"], "Bridge": ["memory swell before final chorus"], "Outro": ["final home cadence"]},
            guitar_tabs={"A": "x02220", "F#m7": "242222", "E/G#": "4x2400", "D": "xx0232", "E": "022100"},
            notes="Original-key country chart in A; chorus keeps E/G# bass motion for the stepwise lift into F#m.",
        ),
        v(
            "How Deep Is Your Love",
            "Bee Gees",
            "Pop",
            "Eb",
            {
                "Intro": ["Eb", "Gm", "Fm", "Bb"] * 2,
                "Verse": ["Eb", "Gm", "Fm", "Bb", "Eb", "Gm", "Ab", "Bb"],
                "Pre-Chorus": ["Ab", "Gm", "Fm", "Eb", "Ab", "Gm", "Fm", "Bb"],
                "Chorus": ["Eb", "Gm", "Ab", "Bb", "Eb", "Gm", "Ab", "Bb"],
                "Bridge": ["Cm", "Gm", "Ab", "Eb", "Fm", "Gm", "Ab", "Bb"],
                "Outro": ["Eb", "Gm", "Ab", "Bb", "Eb", "Eb"],
            },
            {
                "Intro": ["Ebmaj7", "Gm7", "Fm7", "Bb7"] * 2,
                "Verse": ["Ebmaj7", "Gm7", "Fm7", "Bb7", "Ebmaj7", "Gm7", "Abmaj7", "Bb7"],
                "Pre-Chorus": ["Abmaj7", "Gm7", "Fm7", "Eb/G", "Abmaj7", "Gm7", "Fm7", "Bb7"],
                "Chorus": ["Ebmaj7", "Gm7", "Abmaj7", "Bb7", "Ebmaj7", "Gm7", "Abmaj7", "Bb7"],
                "Bridge": ["Cm7", "Gm7", "Abmaj7", "Eb/G", "Fm7", "Gm7", "Abmaj7", "Bb7"],
                "Outro": ["Ebmaj7", "Gm7", "Abmaj7", "Bb7", "Ebmaj7", "Ebmaj7"],
            },
            advanced={
                "Intro": ["Ebmaj9", "Gm9", "Fm9", "Bb13"] * 2,
                "Verse": ["Ebmaj9", "Gm9", "Fm9", "Bb13", "Ebmaj9", "Gm9", "Abmaj9", "Bb13"],
                "Pre-Chorus": ["Abmaj9", "Gm9", "Fm9", "Eb/G", "Abmaj9", "Gm9", "Fm9", "Bb13"],
                "Chorus": ["Ebmaj9", "Gm9", "Abmaj9", "Bb13", "Ebmaj9", "Gm9", "Abmaj9", "Bb13"],
                "Bridge": ["Cm9", "Gm9", "Abmaj9", "Eb/G", "Fm9", "Gm9", "Abmaj9", "Bb13"],
                "Outro": ["Ebmaj9", "Gm9", "Abmaj9", "Bb13", "Ebmaj9", "Ebmaj9"],
            },
            composer="Barry Gibb, Robin Gibb & Maurice Gibb",
            lyric_cues={"Intro": ["soft electric-piano color"], "Verse": ["soft falsetto setup"], "Pre-Chorus": ["gentle lift into question hook"], "Chorus": ["question-hook phrase"], "Bridge": ["tender dynamic dip"], "Outro": ["fade with warm maj7 color"]},
            notes="Practice-level Bee Gees ballad chart in Eb; maj7 and slash-bass colors preserve the soft harmonic motion.",
        ),
        v(
            "Isn't She Lovely",
            "Stevie Wonder",
            "Funk",
            "E",
            {
                "Intro / Harmonica Vamp": ["C#m", "F#7", "B", "E"] * 2,
                "Verse": ["C#m", "F#7", "B", "E", "A", "G#7", "C#m", "F#7"],
                "Chorus": ["B", "E", "A", "G#7", "C#m", "F#7", "B", "E"],
                "Solo Vamp": ["C#m", "F#7", "B", "E"] * 2,
                "Outro": ["C#m", "F#7", "B", "E"],
            },
            {
                "Intro / Harmonica Vamp": ["C#m7", "F#9", "B13", "Emaj7"] * 2,
                "Verse": ["C#m7", "F#9", "B13", "Emaj7", "Amaj7", "G#7", "C#m7", "F#9"],
                "Chorus": ["B13", "Emaj7", "Amaj7", "G#7", "C#m7", "F#9", "B13", "Emaj7"],
                "Solo Vamp": ["C#m7", "F#9", "B13", "Emaj7"] * 2,
                "Outro": ["C#m7", "F#9", "B13", "Emaj7"],
            },
            advanced={
                "Intro / Harmonica Vamp": ["C#m9", "F#13", "B13", "Emaj9"] * 2,
                "Verse": ["C#m9", "F#13", "B13", "Emaj9", "Amaj9", "G#7b9", "C#m9", "F#13"],
                "Chorus": ["B13", "Emaj9", "Amaj9", "G#7b9", "C#m9", "F#13", "B13", "Emaj9"],
                "Solo Vamp": ["C#m9", "F#13", "B13", "Emaj9"] * 2,
                "Outro": ["C#m9", "F#13", "B13", "Emaj9"],
            },
            composer="Stevie Wonder",
            lyric_cues={"Intro / Harmonica Vamp": ["harmonica pickup over main cycle"], "Verse": ["joyful newborn celebration"], "Chorus": ["title-hook smile"], "Solo Vamp": ["harmonica / vocal ad-lib space"], "Outro": ["repeat groove with ad-lib feel"]},
            notes="Soul-funk cycle with ii-V motion into E; advanced chart keeps dominant colors for comping.",
        ),
        v(
            "Just the Two of Us",
            "Grover Washington Jr. / Bill Withers",
            "Soul",
            "Db",
            {
                "Intro / Groove": ["Db", "C7", "Fm", "Ebm", "Ab7", "Db", "C7", "Fm"],
                "Verse": ["Db", "C7", "Fm", "Ebm", "Ab7", "Db", "C7", "Fm"],
                "Chorus": ["Db", "C7", "Fm", "Ebm", "Ab7", "Db", "C7", "Fm"],
                "Bridge": ["Bbm", "Eb7", "Ab", "Db", "Gb", "C7", "Fm", "Ab7"],
                "Solo": ["Db", "C7", "Fm", "Ebm", "Ab7", "Db", "C7", "Fm"],
                "Outro": ["Db", "C7", "Fm", "Ebm", "Ab7", "Db", "Db"],
            },
            {
                "Intro / Groove": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
                "Verse": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
                "Chorus": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
                "Bridge": ["Bbm7", "Eb9", "Abmaj7", "Dbmaj7", "Gbmaj7", "C7", "Fm7", "Ab7"],
                "Solo": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
                "Outro": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "Dbmaj7"],
            },
            advanced={
                "Intro / Groove": ["Dbmaj9", "C7b9", "Fm9", "Ebm9", "Ab13", "Dbmaj9", "C7b9", "Fm9"],
                "Verse": ["Dbmaj9", "C7b9", "Fm9", "Ebm9", "Ab13", "Dbmaj9", "C7b9", "Fm9"],
                "Chorus": ["Dbmaj9", "C7b9", "Fm9", "Ebm9", "Ab13", "Dbmaj9", "C7b9", "Fm9"],
                "Bridge": ["Bbm9", "Eb13", "Abmaj9", "Dbmaj9", "Gbmaj9", "C7b9", "Fm9", "Ab13"],
                "Solo": ["Dbmaj9", "C7b9", "Fm9", "Ebm9", "Ab13", "Dbmaj9", "C7b9", "Fm9"],
                "Outro": ["Dbmaj9", "C7b9", "Fm9", "Ebm9", "Ab13", "Dbmaj9", "Dbmaj9"],
            },
            composer="Bill Withers, William Salter & Ralph MacDonald",
            lyric_cues={"Intro / Groove": ["electric piano and sax texture"], "Verse": ["smooth conversational phrase"], "Chorus": ["two-person hook"], "Bridge": ["brighter harmonic lift"], "Solo": ["sax lead over main groove"], "Outro": ["fade on main groove"]},
            notes="Soul-jazz practice chart in Db; keeps the Dbmaj7-C7-Fm7 color and ii-V movement into Db.",
        ),
        v(
            "Rocket Man",
            "Elton John",
            "Pop",
            "Bb",
            {
                "Intro": ["Gm", "C", "F", "Bb"] * 2,
                "Verse": [
                    "Gm", "C", "Gm", "C",
                    "Eb", "Bb/D", "Cm", "Cm/Bb", "F/A", "F/C", "F",
                ],
                "Chorus": [
                    "Bb", "Eb", "Bb", "Eb", "Bb/D", "C", "Eb", "Bb", "Eb",
                ],
                "Verse 2": [
                    "Gm", "C11", "Gm", "C11",
                    "Eb", "Bb/D", "Cm", "Cm/Bb", "F/A", "F/C", "F",
                ],
                "Outro": ["Eb", "Bb", "Eb", "Bb", "Eb", "Bb", "Eb", "Bb"],
            },
            {
                "Intro": ["Gm7", "C9", "F", "Bb"] * 2,
                "Verse": [
                    "Gm7", "C9", "Gm7", "C9",
                    "Eb", "Bb/D", "Cm7", "Cm7/Bb", "F/A", "F/C", "F",
                ],
                "Chorus": [
                    "Bb", "Eb", "Bb", "Eb", "Bb/D", "C9", "Eb", "Bb", "Eb",
                ],
                "Verse 2": [
                    "Gm7", "C11", "Gm7", "C11",
                    "Eb", "Bb/D", "Cm7", "Cm7/Bb", "F/A", "F/C", "F",
                ],
                "Outro": ["Eb", "Bb", "Eb", "Bb", "Eb", "Bb", "Eb", "Bb"],
            },
            advanced={
                "Intro": ["Gm9", "C13sus4", "Fadd9", "Bbmaj7"] * 2,
                "Verse": [
                    "Gm9", "C13sus4", "Gm11", "C9",
                    "Ebmaj7", "Bb/D", "Cm9", "Cm7/Bb", "F/A", "F/C", "Fmaj7",
                ],
                "Chorus": [
                    "Bbmaj7", "Ebmaj9", "Bb6", "Ebadd9",
                    "Bb/D", "C13sus4", "C9", "Ebmaj9", "Bbadd9",
                ],
                "Verse 2": [
                    "Gm9", "C11", "Gm11", "C9",
                    "Ebmaj7", "Bb/D", "Cm9", "Cm7/Bb", "F/A", "F/C", "F6",
                ],
                "Outro": ["Ebmaj9", "Bbadd9", "Eb6", "Bbmaj7", "Ebmaj9", "Bbadd9", "Ebmaj9", "Bbmaj7"],
            },
            composer="Elton John & Bernie Taupin",
            lyric_cues={
                "Intro": ["piano intro — no vocal"],
                "Verse": [
                    "She packed my bags last night pre-flight",
                    "Gm7–C9 then Eb–Bb/D–Cm–Cm/Bb–F/A–F/C–F walkdown",
                ],
                "Chorus": [
                    "And I think it's gonna be a long long time",
                    "Till touchdown brings me 'round again to find",
                    "I'm not the man they think I am at home",
                    "Oh no no no I'm a rocket man",
                    "Rocket man burnin' out his fuse up here alone",
                ],
                "Verse 2": [
                    "Mars ain't the kind of place to raise your kids",
                    "same verse shape — C11 color on second Gm–C pass",
                ],
                "Outro": ["fade — Eb and Bb alternating"],
            },
            notes=(
                "Key Bb (concert). Reference chart: verse opens Gm7–C9 twice, then "
                "Eb–Bb/D–Cm–Cm/Bb–F/A–F/C–F bass walkdown (slash chords retained). "
                "Chorus: Bb↔Eb with Bb/D–C9 tag. Advanced adds 9/11/13 colors and "
                "C13sus4→C9 while keeping all slash bass motion. Not AI-verified."
            ),
            chart_status="user_corrected_reference",
        ),
        v(
            "In My Life",
            "The Beatles",
            "Rock",
            "A",
            {
                "Intro": ["A", "E", "A", "E"],
                "Verse": ["A", "E", "F#m", "A7", "D", "Dm", "A", "A"],
                "Chorus": ["F#m", "D", "G", "A", "F#m", "B7", "E", "E"],
                "Piano Solo": ["A", "E", "F#m", "A7", "D", "Dm", "A", "A"],
                "Outro": ["A", "E", "A", "A"],
            },
            {
                "Intro": ["A", "E/G#", "A", "E/G#"],
                "Verse": ["A", "E/G#", "F#m7", "A7", "D", "Dm6", "A/E", "A"],
                "Chorus": ["F#m7", "D", "G", "A", "F#m7", "B7", "E", "E7"],
                "Piano Solo": ["A", "E/G#", "F#m7", "A7", "D", "Dm6", "A/E", "A"],
                "Outro": ["A", "E/G#", "A", "A"],
            },
            composer="Lennon-McCartney",
            lyric_cues={"Intro": ["guitar arpeggio setup"], "Verse": ["memory list phrase"], "Chorus": ["affection reflection"], "Piano Solo": ["baroque keyboard break"], "Outro": ["gentle final cadence"]},
            notes="Beatles practice chart in A; verse keeps the A7-to-D and Dm6 modal-mixture color before resolving.",
        ),
        core_ref(
            "Across the Universe",
            "The Beatles",
            composer="Lennon-McCartney",
        ),
        core_ref(
            "Uptown Girl",
            "Billy Joel",
            composer="Billy Joel",
        ),
        core_ref(
            "Kiss Me",
            "Sixpence None the Richer",
            composer="Matt Slocum",
        ),
        v(
            "Girls Just Want to Have Fun",
            "Cyndi Lauper",
            "Pop",
            "F#",
            {
                "Intro": ["F#", "C#", "D#m", "B"] * 2,
                "Verse": ["F#", "C#", "D#m", "B", "F#", "C#", "D#m", "B"],
                "Pre-Chorus": ["B", "C#", "F#", "D#m", "B", "C#", "F#", "F#"],
                "Chorus": ["F#", "C#", "D#m", "B", "F#", "C#", "B", "B"],
                "Bridge": ["D#m", "B", "F#", "C#", "D#m", "B", "C#", "C#"],
                "Outro": ["F#", "C#", "D#m", "B"],
            },
            {
                "Intro": ["F#add9", "C#", "D#m7", "Badd9"] * 2,
                "Verse": ["F#add9", "C#", "D#m7", "Badd9", "F#add9", "C#", "D#m7", "Badd9"],
                "Pre-Chorus": ["Badd9", "C#", "F#/A#", "D#m7", "Badd9", "C#", "F#add9", "F#add9"],
                "Chorus": ["F#add9", "C#", "D#m7", "Badd9", "F#add9", "C#", "Badd9", "Badd9"],
                "Bridge": ["D#m7", "Badd9", "F#add9", "C#", "D#m7", "Badd9", "C#", "C#"],
                "Outro": ["F#add9", "C#", "D#m7", "Badd9"],
            },
            composer="Robert Hazard",
            lyric_cues={"Intro": ["bright synth/guitar pickup"], "Verse": ["phone-call story setup"], "Pre-Chorus": ["parent-response lift"], "Chorus": ["big title hook"], "Bridge": ["dance-break contrast"], "Outro": ["repeat hook vamp"]},
            notes="Synth-pop chart in F#; add9 colors and F#/A# slash bass keep the bright chorus lift playable.",
        ),
        v(
            "Every Breath You Take",
            "The Police",
            "Rock",
            "Ab",
            {
                "Intro / Verse Arpeggio": ["Ab", "Ab", "Fm", "Fm", "Db", "Eb", "Ab", "Ab"],
                "Pre-Chorus": ["Db", "Db", "Ab", "Ab", "Bb", "Bb", "Eb", "Eb"],
                "Chorus": ["Ab", "Fm", "Db", "Eb", "Ab", "Ab"],
                "Bridge": ["Gb", "Gb", "Ab", "Ab", "Gb", "Gb", "Eb", "Eb"],
                "Outro Vamp": ["Ab", "Fm", "Db", "Eb"],
            },
            {
                "Intro / Verse Arpeggio": ["Abadd9", "Abadd9", "Fmadd9", "Fmadd9", "Dbadd9", "Ebadd9", "Abadd9", "Abadd9"],
                "Pre-Chorus": ["Dbadd9", "Dbadd9", "Abadd9", "Abadd9", "Bbadd9", "Bbadd9", "Ebadd9", "Ebadd9"],
                "Chorus": ["Abadd9", "Fmadd9", "Dbadd9", "Ebadd9", "Abadd9", "Abadd9"],
                "Bridge": ["Gbadd9", "Gbadd9", "Abadd9", "Abadd9", "Gbadd9", "Gbadd9", "Ebadd9", "Ebadd9"],
                "Outro Vamp": ["Abadd9", "Fmadd9", "Dbadd9", "Ebadd9"],
            },
            composer="Sting",
            lyric_cues={"Intro / Verse Arpeggio": ["fingerpicked/arpeggio entry"], "Pre-Chorus": ["minor-to-major tension"], "Chorus": ["title observation hook"], "Bridge": ["darker harmonic contrast"], "Outro Vamp": ["repeat arpeggio fade"]},
            notes="Arpeggio song reduced to harmonic bars; add9 colors preserve the recorded guitar texture.",
        ),
        v(
            "Careless Whisper",
            "George Michael",
            "Pop",
            "Dm",
            {
                "Sax Intro": ["Dm", "Gm", "Bb", "A"] * 2,
                "Verse": ["Dm", "Gm", "Bb", "A", "Dm", "Gm", "Bb", "A"],
                "Pre-Chorus": ["Gm", "A", "Dm", "Dm", "Gm", "A", "Dm", "A"],
                "Chorus": ["Dm", "Gm", "Bb", "A", "Dm", "Gm", "Bb", "A"],
                "Bridge": ["Bb", "C", "Dm", "Dm", "Bb", "C", "A", "A"],
                "Outro Sax": ["Dm", "Gm", "Bb", "A"],
            },
            {
                "Sax Intro": ["Dm7", "Gm7", "Bbmaj7", "A7"] * 2,
                "Verse": ["Dm7", "Gm7", "Bbmaj7", "A7", "Dm7", "Gm7", "Bbmaj7", "A7"],
                "Pre-Chorus": ["Gm7", "A7", "Dm7", "Dm7", "Gm7", "A7", "Dm7", "A7"],
                "Chorus": ["Dm7", "Gm7", "Bbmaj7", "A7", "Dm7", "Gm7", "Bbmaj7", "A7"],
                "Bridge": ["Bbmaj7", "C", "Dm7", "Dm7", "Bbmaj7", "C", "A7", "A7"],
                "Outro Sax": ["Dm7", "Gm7", "Bbmaj7", "A7"],
            },
            advanced={
                "Sax Intro": ["Dm9", "Gm9", "Bbmaj9", "A7b9"] * 2,
                "Verse": ["Dm9", "Gm9", "Bbmaj9", "A7b9", "Dm9", "Gm9", "Bbmaj9", "A7b9"],
                "Pre-Chorus": ["Gm9", "A7b9", "Dm9", "Dm9", "Gm9", "A7b9", "Dm9", "A7b9"],
                "Chorus": ["Dm9", "Gm9", "Bbmaj9", "A7b9", "Dm9", "Gm9", "Bbmaj9", "A7b9"],
                "Bridge": ["Bbmaj9", "C13sus", "Dm9", "Dm9", "Bbmaj9", "C13sus", "A7b9", "A7b9"],
                "Outro Sax": ["Dm9", "Gm9", "Bbmaj9", "A7b9"],
            },
            composer="George Michael & Andrew Ridgeley",
            lyric_cues={"Sax Intro": ["signature sax pickup"], "Verse": ["regretful low vocal"], "Pre-Chorus": ["dominant pull back to Dm"], "Chorus": ["dance-floor hook"], "Bridge": ["brief lift before sax return"], "Outro Sax": ["repeat sax color"]},
            notes="D minor pop-sax chart; keeps Bbmaj7 and A7 dominant tension for the signature loop.",
        ),
        v(
            "Take On Me",
            "a-ha",
            "Pop",
            "A",
            {
                "Synth Intro": ["A", "E/G#", "F#m", "D"] * 2,
                "Verse": ["Bm", "E", "A", "D", "C#m", "F#m", "E", "E"],
                "Pre-Chorus": ["D", "E", "F#m", "D", "D", "E", "F#m", "E"],
                "Chorus": ["A", "E/G#", "F#m", "D", "A", "E/G#", "D", "E"],
                "Bridge": ["F#m", "D", "A", "E", "F#m", "D", "E", "E"],
                "Outro": ["A", "E/G#", "F#m", "D"],
            },
            {
                "Synth Intro": ["Aadd9", "E/G#", "F#m7", "Dadd9"] * 2,
                "Verse": ["Bm7", "E", "Aadd9", "Dadd9", "C#m7", "F#m7", "E", "E"],
                "Pre-Chorus": ["Dadd9", "E", "F#m7", "Dadd9", "Dadd9", "E", "F#m7", "E"],
                "Chorus": ["Aadd9", "E/G#", "F#m7", "Dadd9", "Aadd9", "E/G#", "Dadd9", "E"],
                "Bridge": ["F#m7", "Dadd9", "Aadd9", "E", "F#m7", "Dadd9", "E", "E"],
                "Outro": ["Aadd9", "E/G#", "F#m7", "Dadd9"],
            },
            composer="Magne Furuholmen, Morten Harket & Pal Waaktaar",
            lyric_cues={"Synth Intro": ["iconic synth-riff entry"], "Verse": ["quick synth-pop verse"], "Pre-Chorus": ["rising pickup"], "Chorus": ["high title hook"], "Bridge": ["brief breakdown before return"], "Outro": ["riff tag"]},
            notes="Original-key A synth-pop chart; slash bass and add9 colors support the bright keyboard riff movement.",
        ),
        v(
            "Billie Jean",
            "Michael Jackson",
            "Funk",
            "F#m",
            {
                "Intro": ["F#m", "G#m", "A", "G#m"] * 2,
                "Verse": [
                    "F#m", "G#m", "A", "G#m",
                    "F#m", "G#m", "A", "G#m", "Bm",
                    "Bm", "F#m", "G#m", "A", "G#m", "Bm",
                    "Bm", "F#m", "G#m", "A", "G#m",
                ],
                "Bridge": ["D", "F#m", "D", "F#m", "D", "F#m", "D", "C#"],
                "Chorus": [
                    "F#m", "G#m", "A", "G#m", "F#m", "G#m", "A", "G#m", "B5",
                    "B5", "F#m", "G#m", "A", "G#m",
                ],
                "Chorus (Extension)": ["Bm", "Bm", "F#m", "G#m", "A", "G#m"],
                "Instrumental": ["F#m", "G#m", "A", "G#m"] * 4
                + ["Bm", "Bm", "F#m", "G#m", "A", "G#m"],
                "Outro": ["F#m", "G#m", "A", "G#m"] * 2,
            },
            {
                "Intro": ["F#m7", "G#m7", "A", "G#m7"] * 2,
                "Verse": [
                    "F#m7", "G#m7", "A", "G#m7",
                    "F#m7", "G#m7", "A", "G#m7", "Bm7",
                    "Bm7", "F#m7", "G#m7", "A", "G#m7", "Bm7",
                    "Bm7", "F#m7", "G#m7", "A", "G#m7",
                ],
                "Bridge": ["D", "F#m7", "D", "F#m7", "D", "F#m7", "D", "C#7"],
                "Chorus": [
                    "F#m7", "G#m7", "A", "G#m7", "F#m7", "G#m7", "A", "G#m7", "B5",
                    "B5", "F#m7", "G#m7", "A", "G#m7",
                ],
                "Chorus (Extension)": ["Bm7", "Bm7", "F#m7", "G#m7", "A", "G#m7"],
                "Instrumental": ["F#m7", "G#m7", "A", "G#m7"] * 4
                + ["Bm7", "Bm7", "F#m7", "G#m7", "A", "G#m7"],
                "Outro": ["F#m7", "G#m7", "A", "G#m7"] * 2,
            },
            advanced={
                "Intro": ["F#m9", "G#m7", "Amaj7", "G#m7"] * 2,
                "Verse": [
                    "F#m9", "G#m7", "Amaj7", "G#m7",
                    "F#m9", "G#m7", "Amaj7", "G#m7", "Bm9",
                    "Bm9", "F#m9", "G#m7", "Amaj7", "G#m7", "Bm9",
                    "Bm9", "F#m9", "G#m7", "A6", "G#m7",
                ],
                "Bridge": ["Dmaj9", "F#m9", "D6", "F#m9", "Dmaj7", "F#m9", "Dmaj9", "C#9"],
                "Chorus": [
                    "F#m9", "G#m7", "Amaj7", "G#m7", "F#m9", "G#m7", "A6", "G#m7", "B5",
                    "B5", "F#m9", "G#m7", "Amaj7", "G#m7",
                ],
                "Chorus (Extension)": ["Bm9", "Bm11", "F#m9", "G#m7", "Amaj7", "G#m7"],
                "Instrumental": ["F#m9", "G#m7", "Amaj7", "G#m7"] * 4
                + ["Bm9", "Bm9", "F#m9", "G#m7", "Amaj7", "G#m7"],
                "Outro": ["F#m9", "G#m7", "Amaj7", "G#m7"] * 2,
            },
            composer="Michael Jackson",
            lyric_cues={
                "Intro": ["bass riff — ||: F#m G#m | A G#m :|| groove (no vocal)"],
                "Verse": [
                    "She was more like a beauty queen from a movie scene",
                    "verse cells: F#m G#m | A G#m, then Bm turns — not a flat F#m loop",
                ],
                "Bridge": [
                    "People always told me be careful of what you do",
                    "||: D | F#m :|| then D | C#7",
                ],
                "Chorus": [
                    "Billie Jean is not my lover",
                    "F#m G#m | A G#m … B5 power — She's just a girl who claims that I am the one",
                ],
                "Chorus (Extension)": ["Bm | Bm | F#m G#m | A G#m — later chorus tag"],
                "Instrumental": [
                    "dance break — F#m G#m | A G#m ×4, then Bm | Bm | F#m G#m | A G#m",
                ],
                "Outro": ["fade on main groove vamp"],
            },
            notes=(
                "Key F#m; 4/4 groove — one chord = one bar. F#m→G#m→A→G#m vamp is the "
                "core feel. Verse uses phased Bm bars; chorus adds B5. Advanced uses "
                "F#m9/G#m7/Amaj7/Bm9 colors without changing the tight loop. Not AI-verified."
            ),
            chart_status="user_corrected_reference",
        ),
        v(
            "Love Story",
            "Taylor Swift",
            "Country",
            "C",
            {
                "Intro": ["C", "F", "Am", "F"],
                "Verse": ["C", "F", "Am", "F", "C", "F", "Am", "G"],
                "Pre-Chorus": ["F", "G", "Am", "G", "F", "G", "Am", "C"],
                "Chorus": ["C", "G", "Am", "F", "C", "G", "Am", "F"],
                "Bridge": ["Am", "F", "C", "G", "Am", "F", "C", "G"],
                "Final Chorus (Key Change)": ["D", "A", "Bm", "G", "D", "A", "Bm", "G"],
                "Outro": ["D", "A", "Bm", "G", "D", "A", "G", "D"],
            },
            {
                "Intro": ["Cadd9", "Fadd9", "Am7", "Fadd9"],
                "Verse": ["Cadd9", "Fadd9", "Am7", "Fadd9", "Cadd9", "Fadd9", "Am7", "G"],
                "Pre-Chorus": ["Fadd9", "G", "Am7", "G", "Fadd9", "G", "Am7", "Cadd9"],
                "Chorus": ["Cadd9", "G", "Am7", "Fadd9", "Cadd9", "G", "Am7", "Fadd9"],
                "Bridge": ["Am7", "Fadd9", "Cadd9", "G", "Am7", "Fadd9", "Cadd9", "G"],
                "Final Chorus (Key Change)": ["Dadd9", "A", "Bm7", "Gadd9", "Dadd9", "A", "Bm7", "Gadd9"],
                "Outro": ["Dadd9", "A", "Bm7", "Gadd9", "Dadd9", "A", "Gadd9", "Dadd9"],
            },
            advanced={
                "Intro": ["Cadd9", "Fadd9", "Am7", "Fadd9"],
                "Verse": ["Cadd9", "Fadd9", "Am7", "Fadd9", "Cadd9", "Fadd9", "Am7", "Gsus4"],
                "Pre-Chorus": ["Fadd9", "Gsus4", "Am7", "G", "Fadd9", "Gsus4", "Am7", "Cadd9"],
                "Chorus": ["Cadd9", "G/B", "Am7", "Fadd9", "Cadd9", "G/B", "Am7", "Fadd9"],
                "Bridge": ["Am7", "Fadd9", "Cadd9", "G", "Am7", "Fadd9", "Cadd9", "Gsus4"],
                "Final Chorus (Key Change)": ["Dadd9", "A/C#", "Bm7", "Gadd9", "Dadd9", "A/C#", "Bm7", "Gadd9"],
                "Outro": ["Dadd9", "A/C#", "Bm7", "Gadd9", "Dadd9", "A", "Gadd9", "Dadd9"],
            },
            composer="Taylor Swift",
            lyric_cues={"Intro": ["mandolin/guitar storybook pickup"], "Verse": ["storybook scene setup"], "Pre-Chorus": ["tension climbs toward the hook"], "Chorus": ["proposal/title hook"], "Bridge": ["quiet plea before final lift"], "Final Chorus (Key Change)": ["whole-step final lift"], "Outro": ["tag after key change"]},
            guitar_tabs={"Cadd9": "x32030", "Fadd9": "xx3213", "Am7": "x02010", "G": "320003", "Gsus4": "320013", "Dadd9": "xx0230", "A": "x02220", "Bm7": "x24232", "Gadd9": "320203"},
            notes="Capo-shape practice chart centered on C-F-Am-G movement; capo 2 sounds in D for the main body, with the final chorus shape lift to D-A-Bm-G sounding in E.",
        ),
        v(
            "You've Got a Friend in Me",
            "Randy Newman",
            "Jazz",
            "C",
            {
                "Intro": ["C", "E7", "Am", "C7", "F", "F#dim7", "C/G", "G7"],
                "Verse": ["C", "E7", "Am", "C7", "F", "F#dim7", "C/G", "A7"],
                "Chorus": ["Dm", "G7", "C", "A7", "Dm", "G7", "C", "G7"],
                "Bridge": ["F", "F#dim7", "C/G", "A7", "D7", "D7", "G7", "G7"],
                "Final Tag": ["C", "E7", "Am", "C7", "F", "G7", "C", "C"],
            },
            {
                "Intro": ["C6", "E7", "Am7", "C7", "F6", "F#dim7", "C/G", "G7"],
                "Verse": ["C6", "E7", "Am7", "C7", "F6", "F#dim7", "C/G", "A7"],
                "Chorus": ["Dm7", "G7", "C6", "A7", "Dm7", "G7", "C6", "G7"],
                "Bridge": ["F6", "F#dim7", "C/G", "A7", "D7", "D7", "G7", "G7"],
                "Final Tag": ["C6", "E7", "Am7", "C7", "F6", "G7", "C6", "C6"],
            },
            advanced={
                "Intro": ["Cmaj9", "E7b9", "Am9", "C13", "Fmaj9", "F#dim7", "C/G", "G13"],
                "Verse": ["Cmaj9", "E7b9", "Am9", "C13", "Fmaj9", "F#dim7", "C/G", "A7b9"],
                "Chorus": ["Dm9", "G13", "Cmaj9", "A7b9", "Dm9", "G13", "Cmaj9", "G13"],
                "Bridge": ["Fmaj9", "F#dim7", "C/G", "A7b9", "D13", "D13", "G13", "G13"],
                "Final Tag": ["Cmaj9", "E7b9", "Am9", "C13", "Fmaj9", "G13", "Cmaj9", "Cmaj9"],
            },
            composer="Randy Newman",
            lyric_cues={"Verse": ["friendly conversational entry"], "Chorus": ["loyalty hook"], "Bridge": ["ragtime-style contrast"]},
            guitar_tabs={"C": "x32010", "E7": "020100", "Am7": "x02010", "C7": "x32310", "F": "133211", "G7": "320001", "Dm7": "xx0211"},
            notes="Swing-pop/jazz practice chart with secondary dominants and diminished passing harmony retained.",
        ),
        v(
            "So Nice (Summer Samba)",
            "Marcos Valle",
            "Jazz",
            "F",
            {
                "Intro": ["F", "F", "F", "F", "F", "F", "F", "F"],
                "Verse": [
                    "F", "F", "F", "F",
                    "Bm", "E7", "Bm", "E7",
                    "Bb", "Bb", "Bb", "Bb",
                    "Bbm", "Bbm", "Bbm", "Bbm",
                ],
                "Chorus": [
                    "Am", "D7", "Gm", "C7",
                    "Em", "A7", "Dm",
                    "G7", "Gm", "C7", "C7",
                ],
                "Chorus (alternate)": [
                    "Am", "D7", "Gm", "C7",
                    "F", "Bb", "F",
                ],
            },
            {
                "Intro": ["Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6"],
                "Verse": [
                    "Fmaj7", "F6", "Fmaj7", "F6",
                    "Bm7", "E9", "Bm7", "E9",
                    "Bbmaj7", "Bb6", "Bbmaj7", "Bb6",
                    "Bbm7", "Bbm6", "Bbm7", "Bbm6",
                ],
                "Chorus": [
                    "Am7", "D7b9", "Gm7", "C7b9",
                    "Em7b5", "A7#5", "Dm9",
                    "G13", "Gm7", "C#9", "C9",
                ],
                "Chorus (alternate)": [
                    "Am7", "D7b9", "Gm7", "C7b9",
                    "Fmaj7", "Bb7", "Fmaj7",
                ],
            },
            composer="Marcos Valle · Norman Gimbel",
            lyric_cues={
                "Intro": ["samba bounce on Fmaj7/F6"],
                "Verse": ["Brazilian pop-jazz verse — watch Bbm6 color"],
                "Chorus": ["full turnarounds — build energy on G13–C9"],
                "Chorus (alternate)": ["shorter ending chorus on Fmaj7"],
            },
            notes="So Nice (Summer Samba) — F major bossa/samba; alternate chorus for later form.",
            chart_status=status,
            default_bpm=135,
            default_groove="Bossa nova",
        ),
        v(
            "One Note Samba",
            "Antonio Carlos Jobim",
            "Jazz",
            "Db",
            {
                "Verse": [
                    "Dbm", "C7", "B7", "Bb7",
                    "Dbm", "C7", "B7", "Bb7",
                    "Em", "A7", "D", "Dm", "G7",
                    "Dbm", "C7", "B7", "Bb7", "A",
                ],
                "Chorus": [
                    "Dm", "G7", "C",
                    "Cm", "F7", "Bb",
                    "Bdim", "Bb7",
                ],
                "Ending / Tag": [
                    "Dbm", "C7", "B7", "Bb7",
                    "Dbm", "C7", "B7", "Bb7",
                    "Em", "A7", "D", "Dm", "G7",
                    "C6", "B7", "Bb", "A7",
                ],
            },
            {
                "Verse": [
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                    "Dbm7", "C7", "B7sus4", "Bb7b5", "A6/9",
                ],
                "Chorus": [
                    "Dm7", "G7", "Cmaj7",
                    "Cm7", "F7", "Bbmaj7",
                    "Bdim", "Bb7b5",
                ],
                "Ending / Tag": [
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Dbm7", "C7", "B7sus4", "Bb7b5",
                    "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                    "C6", "B7", "Bbmaj7", "A7",
                ],
            },
            composer="Antonio Carlos Jobim · Newton Mendonça",
            lyric_cues={
                "Verse": ["melodic focus on one pitch — hear the bass roots move"],
                "Chorus": ["modulates to C major center"],
                "Ending / Tag": ["full reprise then C6–B7–Bbmaj7–A7 tag"],
            },
            notes="One Note Samba — advanced bossa harmony; Db verse area resolving through C major chorus.",
            chart_status=status,
            default_bpm=130,
            default_groove="Bossa nova",
        ),
    ]


def _apply_requested_verified_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requested = _requested_verified_song_records()
    requested_by_key = {(row["title"], row["artist"]): row for row in requested}
    out: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()

    for row in records:
        key = (row["title"], row["artist"])
        if key in requested_by_key:
            out.append(requested_by_key[key])
            used.add(key)
        else:
            out.append(row)

    out.extend(row for row in requested if (row["title"], row["artist"]) not in used)
    return out


def _apply_core_chart_overrides(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overrides = _core_chart_overrides()
    out = []
    for row in records:
        patch = overrides.get((row["title"], row["artist"]))
        if patch:
            row = {**row, **patch}
            if row.get("genre") in ["Pop", "Rock"]:
                versions = dict(row.get("chart_versions") or {})
                inter = versions.get("Intermediate") or {}
                adv = versions.get("Advanced") or {}
                # Keep explicit three-tier charts (e.g. Piano Man); only fill Advanced when missing.
                if inter and (not adv or adv == inter):
                    versions["Advanced"] = inter
                    row["chart_versions"] = versions
        out.append(row)
    return out


def _jewish_catalog_songs() -> list[dict[str, Any]]:
    """Traditional Jewish repertoire — hora/klezmer dance tunes and prayer ballads."""

    def _j(
        title: str,
        key: str,
        sections: dict[str, list[str]],
        *,
        bpm: int,
        groove: str,
        meter: str = "4/4",
        lyric_cues: dict[str, list[str]] | None = None,
        section_order: list[str] | None = None,
        guitar_tabs: dict[str, str] | None = None,
        beginner: dict[str, list[str]] | None = None,
        advanced: dict[str, list[str]] | None = None,
        composer: str | None = None,
        artist: str = "Traditional",
    ) -> dict[str, Any]:
        inter = sections
        beg = beginner or sections
        adv = advanced or sections
        ext = _ext(
            default_bpm=bpm,
            default_groove=groove,
            time_signature=meter,
            arrangement_notes=(
                f"{title}: practice-level Jewish folk chart; one chord cell = one bar."
            ),
        )
        row = _s(
            title,
            artist,
            "Jewish",
            key,
            inter,
            composer=composer,
            lyric_cues=lyric_cues or {},
            guitar_tabs=guitar_tabs or {},
            chart_status="practice_simplified",
            chart_versions=_levels(beginner=beg, intermediate=inter, advanced=adv),
            extensions=ext,
        )
        row["section_order"] = section_order or list(sections.keys())
        return row

    _em_tabs = {"Em": "022000", "B7": "x21202", "C": "x32010", "G": "320003", "Am": "x02210"}
    _dm_tabs = {"Dm": "xx0231", "Gm": "355333", "A7": "x02020", "Bb": "x13331"}
    _am_tabs = {"Am": "x02210", "G": "320003", "F": "133211", "E7": "020100", "C": "x32010"}
    _d_tabs = {"D": "xx0232", "G": "320003", "A": "x02220", "Bm": "x24432"}
    _f_tabs = {"F": "133211", "Bb": "x13331", "C": "x32010", "Dm": "xx0231", "Gm": "355333"}

    _hora_8 = ["Em", "B7", "Em", "B7", "Em", "C", "B7", "Em"]
    _hora_beg = ["Em", "Em", "Em", "B7", "Em", "Em", "B7", "Em"]

    return [
        _j(
            "Hava Nagila",
            "Em",
            {
                "Hora A": list(_hora_8),
                "Hora B (lift)": list(_hora_8),
                "Outro": ["Em", "B7", "Em", "Em", "B7", "Em", "Em", "Em"],
            },
            bpm=120,
            groove="Jewish groove",
            meter="6/8",
            beginner={"Hora A": _hora_beg, "Hora B (lift)": _hora_beg, "Outro": _hora_beg},
            advanced={
                "Hora A": ["Em", "B7", "Em7", "B7", "Em", "Cmaj7", "B7", "Em"],
                "Hora B (lift)": ["Em", "B7", "Em7", "B7", "Em", "Cmaj7", "B7", "Em"],
                "Outro": ["Em", "B7", "Em7", "Em", "B7", "Em", "Em", "Em"],
            },
            lyric_cues={
                "Hora A": ["hora circle entrance", "build the dance pulse"],
                "Hora B (lift)": ["acceleration — brighter energy", "hands up on the lift"],
                "Outro": ["final hora pass", "hold the last Em"],
            },
            guitar_tabs=_em_tabs,
            section_order=["Hora A", "Hora B (lift)", "Outro"],
        ),
        _j(
            "Hevenu Shalom Aleichem",
            "Dm",
            {
                "Melody A": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
                "Melody B": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
            },
            bpm=72,
            groove="Ballad",
            lyric_cues={
                "Melody A": ["gentle welcome phrase", "soft consonants on A7"],
                "Melody B": ["repeat with warmth", "let the final Dm ring"],
            },
            guitar_tabs=_dm_tabs,
            beginner={
                "Melody A": ["Dm", "Dm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
                "Melody B": ["Dm", "Dm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
            },
        ),
        _j(
            "Oseh Shalom",
            "Am",
            {
                "Prayer": ["Am", "G", "F", "E7", "Am", "G", "F", "E7"],
                "Refrain": ["Am", "G", "F", "E7", "Am", "G", "F", "E7"],
            },
            bpm=80,
            groove="Ballad",
            lyric_cues={
                "Prayer": ["calm prayer tone", "smooth vowels through E7"],
                "Refrain": ["peace refrain lift", "sustain on the final Am"],
            },
            guitar_tabs=_am_tabs,
            beginner={
                "Prayer": ["Am", "Am", "F", "E7", "Am", "Am", "F", "E7"],
                "Refrain": ["Am", "Am", "F", "E7", "Am", "Am", "F", "E7"],
            },
        ),
        _j(
            "Am Yisrael Chai",
            "Am",
            {
                "Chorus": ["Am", "F", "G", "Am", "C", "G", "Am", "Am"],
                "Refrain": ["Am", "F", "G", "Am", "C", "G", "Am", "Am"],
            },
            bpm=118,
            groove="Jewish groove",
            lyric_cues={
                "Chorus": ["anthem entrance — strong downbeat", "build through G to Am"],
                "Refrain": ["repeat with more energy", "celebratory lift on final Am"],
            },
            guitar_tabs={**_am_tabs, "F": "133211"},
            beginner={
                "Chorus": ["Am", "Am", "G", "Am", "C", "G", "Am", "Am"],
                "Refrain": ["Am", "Am", "G", "Am", "C", "G", "Am", "Am"],
            },
        ),
        _j(
            "Siman Tov U'Mazal Tov",
            "D",
            {
                "Hora A": ["D", "G", "A", "D", "D", "G", "A", "D"],
                "Hora B": ["D", "G", "A", "D", "D", "G", "A", "D"],
            },
            bpm=130,
            groove="Jewish groove",
            meter="6/8",
            lyric_cues={
                "Hora A": ["wedding hora — bright pulse", "short punchy chord changes"],
                "Hora B": ["repeat with more drive", "keep the triple lilt steady"],
            },
            guitar_tabs=_d_tabs,
            beginner={
                "Hora A": ["D", "D", "A", "D", "D", "D", "A", "D"],
                "Hora B": ["D", "D", "A", "D", "D", "D", "A", "D"],
            },
        ),
        _j(
            "Yerushalayim Shel Zahav",
            "Am",
            {
                "Verse 1": ["Am", "Em", "Am", "Em", "F", "C", "G", "Am"],
                "Verse 2": ["Am", "Em", "Am", "Em", "F", "C", "G", "Am"],
                "Bridge": ["F", "C", "G", "Am", "F", "C", "G", "Am"],
            },
            bpm=76,
            groove="Ballad",
            composer="Naomi Shemer",
            lyric_cues={
                "Verse 1": ["tender opening — golden city imagery", "soft pick or arpeggio"],
                "Verse 2": ["deepen the lyric line", "gentle swell into F"],
                "Bridge": ["emotional peak", "sustain through G to Am"],
            },
            guitar_tabs={**_am_tabs, "Em": "022000"},
            beginner={
                "Verse 1": ["Am", "Am", "Am", "Em", "F", "C", "G", "Am"],
                "Verse 2": ["Am", "Am", "Am", "Em", "F", "C", "G", "Am"],
                "Bridge": ["F", "C", "G", "Am", "F", "C", "G", "Am"],
            },
        ),
        _j(
            "Hinei Ma Tov",
            "D",
            {
                "Round A": ["D", "G", "A", "D", "Bm", "G", "A", "D"],
                "Round B": ["D", "G", "A", "D", "Bm", "G", "A", "D"],
            },
            bpm=88,
            groove="Jewish groove",
            lyric_cues={
                "Round A": ["freylekh entrance", "brotherhood / unity phrase"],
                "Round B": ["repeat — keep the bounce", "clean landing on D"],
            },
            guitar_tabs=_d_tabs,
            beginner={
                "Round A": ["D", "D", "A", "D", "Bm", "G", "A", "D"],
                "Round B": ["D", "D", "A", "D", "Bm", "G", "A", "D"],
            },
        ),
        _j(
            "Shalom Aleichem",
            "Dm",
            {
                "Verse (Peace unto you)": ["Dm", "Gm", "A7", "Dm"] * 2,
                "Verse (Return in peace)": ["Dm", "Gm", "A7", "Dm"] * 2,
            },
            bpm=70,
            groove="Ballad",
            lyric_cues={
                "Verse (Peace unto you)": ["Shabbat welcome — very soft", "four-bar phrase breathing"],
                "Verse (Return in peace)": ["answer phrase", "gentle A7 resolution"],
            },
            guitar_tabs=_dm_tabs,
            beginner={
                "Verse (Peace unto you)": ["Dm", "Dm", "A7", "Dm", "Dm", "Dm", "A7", "Dm"],
                "Verse (Return in peace)": ["Dm", "Dm", "A7", "Dm", "Dm", "Dm", "A7", "Dm"],
            },
        ),
        _j(
            "Adon Olam",
            "F",
            {
                "Strophe A": ["F", "Bb", "C", "F", "Dm", "Gm", "C", "F"],
                "Strophe B": ["Bb", "F", "C", "F", "Dm", "Gm", "C", "F"],
            },
            bpm=88,
            groove="Ballad",
            lyric_cues={
                "Strophe A": ["stately prayer march", "clear downbeats on F and C"],
                "Strophe B": ["second strophe — steady confidence", "hold the final F"],
            },
            guitar_tabs=_f_tabs,
            beginner={
                "Strophe A": ["F", "Bb", "C", "F", "Dm", "Dm", "C", "F"],
                "Strophe B": ["Bb", "F", "C", "F", "Dm", "Dm", "C", "F"],
            },
            advanced={
                "Strophe A": ["F", "Bb", "C7", "F", "Dm7", "Gm7", "C7", "F"],
                "Strophe B": ["Bb", "F/A", "C7", "F", "Dm7", "Gm7", "C7", "F"],
            },
        ),
    ]


def curated_song_records() -> list[dict[str, Any]]:
    records = [
        # --- John Mayer / Pop foundations ---
        _s("Say", "John Mayer", "Pop", "G", {
            "Verse": ["G", "C", "Em", "D"] * 4,
            "Chorus": ["G", "C", "Em", "D", "G", "C", "Em", "D"],
            "Bridge": ["Am", "C", "D"] * 4,
            "Final Chorus": ["Em", "G", "C7", "C7", "Em", "G", "C7", "C7"],
        }, guitar_tabs={"G": "320003", "C": "x32010", "Em": "022000", "D": "xx0232", "Am": "x02210", "C7": "x32310"}),
        _s("Gravity", "John Mayer", "Pop", "G", {
            "Intro / Verse Groove": ["G", "C/G", "G", "C/G"],
            "Verse": ["G", "C/G", "G", "C/G", "G", "C/G", "G", "C/G"],
            "Chorus / Lift": ["Em7", "Cadd9", "G/D", "D", "Em7", "Cadd9", "G", "D"],
            "Solo Section": ["G7", "C7", "G7", "G7", "C7", "C7", "G7", "D7"],
            "Outro Vamp": ["G", "C/G", "G", "C/G"],
        }, guitar_tabs={"G": "320003", "C": "x32010", "Em": "022000", "D": "xx0232", "G7": "320001", "C7": "x32310", "D7": "xx0212"}),
        _s("Waiting on the World to Change", "John Mayer", "Pop", "D", {
            "Verse 1": ["D", "Bm", "G", "D", "A", "Bm", "G", "D"] * 4,
            "Chorus": ["D", "Bm", "G", "D", "A", "Bm", "G", "D", "D", "Em", "Bm", "Em7", "A", "Bm", "G", "D"],
            "Verse 2": ["D", "Bm", "G", "D", "A", "Bm", "G", "D"] * 4,
            "Bridge": ["Dm7"] * 4 + ["D", "Bm", "G", "D", "A", "Bm", "G", "D"],
            "Final Chorus": ["D", "Bm", "G", "D", "A", "Bm", "G", "D", "D", "Em", "Bm", "Em7", "A", "Bm", "G", "D"],
        }),
        _s("Daughters", "John Mayer", "Pop", "D", {
            "Verse": ["D", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
            "Bridge": ["Em", "G", "D", "A"],
        }),
        _s("Slow Dancing in a Burning Room", "John Mayer", "Pop", "C#m", {
            "Verse": ["C#m", "A", "E", "B"],
            "Chorus": ["A", "E", "B", "C#m"],
            "Solo": ["C#m", "A", "E", "B"],
        }),

        # --- Ed Sheeran ---
        _s(
            "Perfect",
            "Ed Sheeran",
            "Pop",
            "G",
            {
                "Intro": ["G", "D/F#", "Em7", "D", "Cadd9", "D", "G"],
                "Verse 1": ["G", "G", "Em7", "Em7", "Cadd9", "Cadd9", "D/F#", "D/F#"] * 2,
                "Verse 2": ["G", "G", "Em7", "Em7", "Cadd9", "Cadd9", "D/F#", "D/F#"] * 2,
                "Chorus 1": ["Em7", "Cadd9", "G", "D/F#"] * 2,
                "Verse 3": ["G", "G", "Em7", "Em7", "Cadd9", "Cadd9", "D/F#", "D/F#"] * 2,
                "Verse 4": ["G", "G", "Em7", "Em7", "Cadd9", "Cadd9", "D/F#", "D/F#"] * 2,
                "Chorus 2": ["Em7", "Cadd9", "G", "D/F#"] * 2,
                "Chorus 3": ["Em7", "Cadd9", "G", "D/F#"] * 2,
                "Outro": ["G", "D/F#", "Em7", "D", "Cadd9", "D", "G"],
            },
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Verse 2",
                "Chorus 1",
                "Verse 3",
                "Verse 4",
                "Chorus 2",
                "Chorus 3",
                "Outro",
            ],
        ),
        # Shape of You — Ed Sheeran. Authoritative form mirrors the
        # ``_core_chart_overrides`` entry above so Practice / Karaoke /
        # Backing all see the same per-bar structure (one chord = one
        # 4/4 bar). The bridge opens with 16 bars of ``N.C.``
        # (percussion-only breakdown) before the loop returns.
        _s(
            "Shape of You",
            "Ed Sheeran",
            "Pop",
            "Bm",
            {
                # Verse 1 — main loop x4 (16 bars).
                "Verse 1": ["Bm", "Em", "G", "A"] * 4,
                # Pre-Chorus 1 — main loop x4 (16 bars), holds A into the chorus.
                "Pre-Chorus 1": ["Bm", "Em", "G", "A"] * 4,
                # Chorus 1 — main loop x8 (32 bars).
                "Chorus 1": ["Bm", "Em", "G", "A"] * 8,
                # Verse 2 — same shape as Verse 1.
                "Verse 2": ["Bm", "Em", "G", "A"] * 4,
                # Pre-Chorus 2 — same shape as Pre-Chorus 1.
                "Pre-Chorus 2": ["Bm", "Em", "G", "A"] * 4,
                # Chorus 2 — same shape as Chorus 1.
                "Chorus 2": ["Bm", "Em", "G", "A"] * 8,
                # Bridge — 16 bars tacet (N.C.) breakdown, then 8 bars
                # of the main loop x2 to lift back into the final chorus.
                "Bridge": ["N.C."] * 16 + ["Bm", "Em", "G", "A"] * 2,
                # Final Chorus — same shape as the prior choruses.
                "Final Chorus": ["Bm", "Em", "G", "A"] * 8,
            },
            section_order=[
                "Verse 1",
                "Pre-Chorus 1",
                "Chorus 1",
                "Verse 2",
                "Pre-Chorus 2",
                "Chorus 2",
                "Bridge",
                "Final Chorus",
            ],
        ),
        _s("Thinking Out Loud", "Ed Sheeran", "Pop", "D", {
            "Intro": ["D", "D/F#", "G", "A7"],
            "Verse": ["D", "D/F#", "G", "A7", "D", "D/F#", "G", "A7"],
            "Pre-Chorus": ["Em7", "A7", "D", "Bm7", "Em7", "A7", "D", "A7"],
            "Chorus": ["D", "D/F#", "G", "A7", "D", "D/F#", "G", "A7"],
            "Bridge": ["Bm7", "A", "G", "D/F#", "Em7", "A7", "D", "A7"],
        }),
        _s("Photograph", "Ed Sheeran", "Pop", "E", {
            "Verse": ["E", "C#m", "B", "A"],
            "Chorus": ["E", "B", "C#m", "A"],
            "Bridge": ["C#m", "A", "E", "B"],
        }),
        _s("Bad Habits", "Ed Sheeran", "Pop", "Bm", {
            "Verse": ["Bm", "G", "D", "A"],
            "Pre-Chorus": ["Bm", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
            "Bridge": ["G", "A", "Bm", "D"],
        }),
        _s("Castle on the Hill", "Ed Sheeran", "Pop", "D", {
            "Verse": ["D", "G", "Bm", "A"],
            "Pre-Chorus": ["G", "A", "Bm", "D"],
            "Chorus": ["D", "G", "Bm", "A"],
            "Bridge": ["G", "D", "A", "Bm"],
        }),
        _s("Shivers", "Ed Sheeran", "Pop", "Bm", {
            "Verse": ["Bm", "G", "D", "A"],
            "Pre-Chorus": ["Bm", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
        }),
        _s("The A Team", "Ed Sheeran", "Pop", "A", {
            "Verse": ["A", "E", "F#m", "D"],
            "Chorus": ["A", "E", "F#m", "D"],
            "Bridge": ["D", "A", "E", "E"],
        }),

        # --- Coldplay (guitar-friendly, rehearsal-level form) ---
        _s("Viva La Vida", "Coldplay", "Pop", "Ab", {
            "Intro (Strings Figure)": ["Ab", "Fm", "Db", "Eb"],
            "Verse": ["Db", "Eb", "Ab/C", "Fm"],
            "Pre-Chorus (Lift)": ["Db", "Ab/C", "Eb", "Fm"],
            "Chorus": ["Db", "Eb", "Ab/C", "Fm"],
            "Bridge (Breakdown)": ["Db", "Eb", "Ab", "Ab"],
            "Final Chorus / Outro": ["Db", "Eb", "Ab/C", "Fm"],
        }),
        _s("Yellow", "Coldplay", "Pop", "B", {
            "Intro": ["B", "B", "F#", "E"],
            "Verse": ["B", "F#/A#", "E", "B"],
            "Pre-Chorus": ["E", "G#m7", "F#sus4", "F#"],
            "Chorus": ["E", "B", "F#sus4", "F#", "E", "B", "F#", "E"],
            "Bridge": ["G#m7", "F#/A#", "E", "B"],
            "Outro": ["E", "B", "F#sus4", "B"],
        }),
        _s("Fix You", "Coldplay", "Pop", "Eb", {
            "Intro (Organ)": ["Eb", "Gm", "Cm", "Bb"],
            "Verse": ["Eb", "Gm", "Cm", "Bb"],
            "Pre-Chorus": ["Ab", "Bb", "Gm", "Cm"],
            "Chorus": ["Ab", "Eb", "Bb", "Cm"],
            "Bridge (Build)": ["Ab", "Eb", "Bb", "Cm"],
            "Outro / Resolution": ["Ab", "Eb", "Bb", "Eb"],
        }),
        _s("The Scientist", "Coldplay", "Pop", "F", {
            "Intro": ["Dm", "Bb", "F", "F"],
            "Verse": ["Dm7", "Bbadd9", "F", "F"],
            "Pre-Chorus": ["Gm7", "Bbadd9", "F/A", "F"],
            "Chorus": ["Bbadd9", "F/A", "C", "Dm7"],
            "Bridge": ["Bbadd9", "F/A", "C", "Dm7"],
            "Outro": ["Dm7", "Bbadd9", "F", "F"],
        }),
        _s("Clocks", "Coldplay", "Pop", "Eb", {
            "Intro / Piano Riff": ["Eb", "Bbm", "Fm", "Fm"],
            "Verse (Riff)": ["Eb", "Bbm", "Fm", "Fm"],
            "Chorus": ["Ab", "Eb", "Bbm", "Fm"],
            "Bridge": ["Db", "Ab", "Eb", "Bbm"],
            "Solo / Outro Riff": ["Eb", "Bbm", "Fm", "Fm"],
        }),
        _s("A Sky Full of Stars", "Coldplay", "Pop", "F", {
            "Intro": ["F", "Am", "Dm", "Bb"],
            "Verse": ["F", "Am", "Dm", "Bb"],
            "Pre-Chorus": ["Bb", "C", "Dm", "Am"],
            "Chorus": ["F", "Am", "Dm", "Bb"],
            "Bridge": ["Bb", "C", "Dm", "F"],
            "Outro": ["F", "Am", "Dm", "Bb"],
        }),
        _s("Paradise", "Coldplay", "Pop", "F", {
            "Intro (Synth Theme)": ["F", "Gm", "Bb", "Dm"],
            "Verse": ["F", "Gm", "Bb", "Dm"],
            "Pre-Chorus": ["Gm", "Bb", "F", "C"],
            "Chorus": ["Bb", "F", "C", "Dm"],
            "Bridge": ["Gm", "Bb", "F", "C"],
            "Outro": ["Bb", "F", "C", "Dm"],
        }),

        # --- Billy Joel (composer = self where applicable) ---
        _s(
            "Piano Man",
            "Billy Joel",
            "Pop",
            "C",
            {
                "Intro (Harmonica)": [
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G7",
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G7",
                    "C", "C/B", "Am", "C/G", "F", "G11", "C",
                    "C", "F/C", "Cmaj7", "G11",
                    "C", "F/C", "Cmaj7", "G11",
                ],
                "Verse": [
                    "C", "G/B", "F/A", "C/G", "F", "C/E", "D7", "G7",
                    "C", "G/B", "F/A", "C/G", "F", "G11", "C",
                ],
                "Verse (Memory)": [
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G7",
                    "C", "Em/B", "Am", "C/G", "F", "G11", "C",
                ],
                "Verse (Extended Tag)": [
                    "C", "G/B", "F/A", "C/G", "F", "G11", "C",
                    "F/C", "Cmaj7", "G11",
                ],
                "Harmonica Interlude": [
                    "C", "Em/B", "Am", "C/G", "F", "G11", "C",
                    "C", "F/C", "Cmaj7", "G11",
                ],
                "Bridge": [
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "D7", "G", "G/F", "C/E", "G7/D",
                ],
                "Chorus": [
                    "C", "G/B", "F/A", "C/G", "F", "C/E", "D7", "G7",
                    "C", "G/B", "F/A", "C/G", "F", "G11", "C",
                ],
                "Instrumental": [
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "D7", "G", "G/F", "C/E", "G/D",
                ],
                "Outro": [
                    "C", "G/B", "F/A", "C/G", "F", "G11", "C",
                    "C", "F/C", "Cmaj7", "G11",
                    "C", "F/C", "Cmaj7", "G11",
                    "G/F", "C/E", "G/D", "C",
                ],
            },
            composer="Billy Joel",
            chart_status="practice_needs_review",
            lyric_cues={
                "Intro (Harmonica)": [
                    "harmonica pickup (no vocal) — C C/B Am C/G; played twice, then G11 tag",
                ],
                "Verse": [
                    "It's nine o'clock on a Saturday / The regular crowd shuffles in",
                    "line 2 ends F → G11 → C (not a full D7–G turnaround)",
                ],
                "Verse (Memory)": [
                    "He says, Son, can you play me a memory — uses Am (not F/A) on bar 3",
                    "second line: Em/B Am C/G → F → G11 → C",
                ],
                "Verse (Extended Tag)": [
                    "used after verses like John at the bar — adds F/C Cmaj7 G11 tag",
                ],
                "Harmonica Interlude": [
                    "between vocal sections — often Em/B Am C/G then F/C Cmaj7 G11",
                ],
                "Bridge": [
                    "la la, di dee da / la la, di dee da, da dum",
                    "12-bar walkdown: Am → … → G7/D",
                ],
                "Chorus": [
                    "Sing us a song, you're the piano man / Sing us a song tonight",
                    "We're all in the mood for a melody … feeling alright",
                ],
                "Instrumental": [
                    "harmonica solo — bridge figure twice, then D7 G walkdown to G/D",
                ],
                "Outro": [
                    "final harmonica reprise + F/C Cmaj7 G11 tags + G/F C/E G/D → C",
                ],
            },
            extensions=_ext(
                arrangement_notes=(
                    "Key C, 3/4 waltz; one chord = one bar. Manually checked against "
                    "pianochordcharts.net (2020). Status: practice approximation — needs review. "
                    "Standard verse/chorus: 8-bar walkdown (C G/B F/A C/G F C/E D7 G) + "
                    "7-bar lyric close (… F G11 C). Memory verse swaps F/A for Am and uses Em/B."
                ),
            ),
        ),
        _s("Turn the Lights Back On", "Billy Joel", "Pop", "C", {
            "Intro": ["C", "Am7", "Fmaj7", "G"],
            "Verse": ["C", "Am7", "Fmaj7", "G", "C/E", "Am7", "Fmaj7", "G"],
            "Pre-Chorus": ["Dm7", "G", "Em7", "Am7", "Fmaj7", "G", "C", "G"],
            "Chorus": ["C", "Am7", "Fmaj7", "G", "C/E", "Am7", "Fmaj7", "G"],
            "Bridge": ["Fmaj7", "G", "Em7", "Am7", "Dm7", "G", "C", "G"],
        }, composer="Billy Joel"),
        _s("Just the Way You Are", "Billy Joel", "Pop", "D", {
            "Verse": ["Dmaj7", "Bm7", "Gmaj7", "A7", "F#m7", "B7", "Em7", "A7"],
            "Chorus": ["Gmaj7", "Gm6", "D/F#", "B7", "Em7", "A7", "Dmaj7", "A7"],
            "Bridge": ["Bbmaj7", "Eb", "Am7", "D7", "Gmaj7", "A7", "Dmaj7", "A7"],
        }, composer="Billy Joel"),
        _s("Vienna", "Billy Joel", "Pop", "Bb", {
            "Intro": ["Bb", "Bb/D", "Ebmaj7", "F7"],
            "Verse": ["Bb", "Dm7", "Gm7", "Ebmaj7", "Bb/F", "F7", "Bb", "F7"],
            "Pre-Chorus": ["Ebmaj7", "F/Eb", "Dm7", "Gm7", "Cm7", "F7", "Bb", "F7"],
            "Chorus": ["Ebmaj7", "F7", "Dm7", "Gm7", "Cm7", "F7", "Bb", "F7"],
            "Bridge": ["Gm7", "Dm7/F", "Ebmaj7", "Bb/D", "Cm7", "F7", "Bb", "F7"],
        }, composer="Billy Joel"),
        _s("New York State of Mind", "Billy Joel", "Jazz", "C", {
            "Intro": ["Cmaj9", "A7b9", "Dm9", "G13"],
            "Verse": ["Cmaj9", "B7#9", "Em9", "A13", "Dm9", "G13", "Cmaj9", "G13"],
            "Chorus": ["Fmaj9", "Fm9", "Em7", "A7b9", "Dm9", "G13", "Cmaj9", "G13"],
            "Bridge": ["Abmaj9", "Db13", "Cmaj9", "A7b9", "Dm9", "G13", "Cmaj9", "G13"],
        }, composer="Billy Joel"),
        _s("Scenes from an Italian Restaurant", "Billy Joel", "Rock", "F", {
            "Ballad Intro": ["F", "Dm7", "Bb", "C", "F", "Dm7", "Gm7", "C7"],
            "Groove Section": ["F7", "Bb7", "Eb7", "Ab7"],
            "Outro Vamp": ["F", "Bb", "F", "C7"],
        }, composer="Billy Joel"),
        _s("Uptown Girl", "Billy Joel", "Pop", "D", {
            "Intro": ["D", "Em", "D/F#", "G", "A"],
            "Verse": ["D", "Em", "D/F#", "G", "A", "D", "Em", "D/F#", "G", "A"],
            "Chorus": ["D", "Em", "D/F#", "G", "A", "D", "Em", "D/F#", "G", "A"],
            "Interlude": ["F", "G", "E", "Am", "G"],
            "Bridge": ["Bb", "Gm", "Cm", "F", "Bb", "Gm", "Am7b5", "D7", "G", "Em", "Am", "A"],
            "Outro": ["D", "Em", "D/F#", "G", "A", "D"],
        }, composer="Billy Joel"),
        _s("She's Always a Woman", "Billy Joel", "Pop", "Eb", {
            "Verse": ["Eb", "Gm7", "Cm7", "Ab", "Eb", "Gm7", "Cm7", "Bb"],
            "Chorus": ["Ab", "Bb", "Gm7", "Cm7", "Ab", "Bb", "Eb", "Bb"],
        }, composer="Billy Joel"),

        # --- The Beatles ---
        _s("Let It Be", "The Beatles", "Rock", "C", {
            "Intro": ["C", "G/B", "Am7", "Fmaj7"],
            "Verse": ["C", "G/B", "Am7", "Fmaj7", "C/G", "G", "F", "C/E"],
            "Chorus": ["Am7", "G", "F", "C/E", "C", "G", "F", "C"],
            "Bridge": ["F", "C/E", "Dm7", "C", "Bb", "F/A", "G", "G7"],
            "Guitar Solo (Over Verse)": ["C", "G/B", "Am7", "Fmaj7", "C/G", "G", "F", "C/E"],
            "Final Chorus / Outro": ["C", "G", "F", "C", "F", "C/E", "Dm7", "C"],
        }, composer="John Lennon & Paul McCartney"),
        _s("Hey Jude", "The Beatles", "Rock", "F", {
            "Intro": ["F", "C", "C7", "F"],
            "Verse": ["F", "C", "C7", "F"],
            "Pre-Chorus (Build)": ["Bb", "Bb", "F", "F"],
            "Chorus (Take a Sad Song)": ["Bb", "F", "C", "F"],
            "Bridge / Middle (Instrumental)": ["Bb", "F", "C", "F"],
            "Outro Vamp (Na-Na)": ["F", "Eb", "Bb", "F", "C", "F", "C", "F"],
        }, composer="Lennon–McCartney"),
        _s("Yesterday", "The Beatles", "Rock", "F", {
            "Intro": ["F", "F", "F", "F"],
            "Verse": ["F", "Em7", "A7", "Dm"],
            "Middle Eight": ["Bb", "C7", "F", "Dm7"],
            "Return / Tag": ["Gm7", "C7", "Fmaj7", "F6"],
        }, composer="Lennon–McCartney"),
        _s("Here Comes the Sun", "The Beatles", "Rock", "A", {
            "Intro": ["A", "D/A", "E7/A", "A"],
            "Verse": ["A", "D/F#", "E7", "A", "A", "D/F#", "E7", "A"],
            "Chorus": ["Dmaj7", "B7", "E7", "A", "Dmaj7", "B7", "E7", "A"],
            "Bridge (Sun Sun Sun)": ["C", "G/B", "D", "A", "C", "G/B", "D", "E7"],
        }, composer="George Harrison"),
        _s("Something", "The Beatles", "Rock", "F", {
            "Intro": ["F", "Eb", "G", "C"],
            "Verse": ["F", "Eb", "G", "C", "F", "G", "F", "Eb"],
            "Bridge (I Don't Want to Leave)": ["A", "A/G", "F#m7", "F", "D", "G", "C", "C"],
            "Guitar Solo (Verse Form)": ["F", "Eb", "G", "C"],
            "Final Verse / Outro": ["F", "Eb", "G", "C"],
        }, composer="George Harrison"),
        _s("Blackbird", "The Beatles", "Rock", "G", {
            "Intro / Verse": ["G", "Am7", "G/B", "C", "G", "Am7", "G/B", "C"],
            "Middle": ["C", "Cm/Eb", "G/D", "A7/C#"],
            "Return": ["G", "Am7", "G/B", "C", "G/D", "D7", "G", "G"],
        }, composer="Lennon–McCartney"),
        _s("In My Life", "The Beatles", "Rock", "A", {
            "Verse": ["A", "E", "F#m", "A7", "D", "Dm", "A", "A"],
            "Chorus": ["F#m", "D", "E", "A", "F#m", "B7", "E", "E"],
        }, composer="Lennon–McCartney"),
        _s("We Are the Champions", "Queen", "Rock", "Cm", {
            "Verse": [
                "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C",
                "Eb", "Ab/Eb", "Eb", "Ab/Eb", "Eb", "Bb/D", "Cm", "F7", "Bb",
                "Ab/Bb", "Bbm7b5", "Bb7", "C7",
            ],
            "Chorus": [
                "F", "Am", "Dm", "Bb", "C7", "F", "Am", "Bb", "F#dim7",
                "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                "Fm", "Gm7", "Fm", "Gm7/F", "Fm", "Gm7/C",
            ],
            "Outro": [
                "F", "Am", "Dm", "Bb", "C7", "F", "Am", "Bb", "F#dim7",
                "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                "Fm", "Gm7", "Fm", "Gm7/F", "Fm", "Gm7/C",
                "Cm", "Gm7/C", "Cm", "Gm7/C",
            ],
        }, composer="Freddie Mercury", guitar_tabs={
            "Cm": "x35543", "Gm7/C": "x30303", "F": "133211", "Bb": "x13331",
        }),
        _s("Come Together", "The Beatles", "Rock", "Dm", {
            "Verse Vamp": ["Dm7", "Dm7", "Dm7", "Dm7"],
            "Chorus": ["A7", "G7", "D7", "A7"],
            "Bridge": ["Bm", "G", "A", "A"],
        }, composer="Lennon–McCartney"),
        _s("While My Guitar Gently Weeps", "The Beatles", "Rock", "Am", {
            "Verse": ["Am", "Am/G", "D/F#", "F", "Am", "G", "D", "E"],
            "Chorus": ["A", "C#m", "F#m", "C#m", "Bm", "E", "A", "E"],
            "Bridge": ["Am", "G", "D", "E"],
        }, composer="George Harrison"),
        _s("Eleanor Rigby", "The Beatles", "Rock", "Em", {
            "Verse": ["Em", "Em", "C", "Em"],
            "Chorus": ["Em", "C", "Em", "C"],
            "Bridge": ["Am", "Em", "C", "Em"],
        }, composer="Lennon–McCartney"),
        _s("Twist and Shout", "The Beatles", "Rock", "D", {
            "Verse": ["D", "G", "A", "G"],
            "Chorus": ["D", "G", "A", "G"],
            "Break": ["D", "D", "A", "A"],
        }, composer="Bert Russell & Phil Medley"),
        _s("A Day in the Life", "The Beatles", "Rock", "G", {
            "Verse": ["G", "Bm", "Em", "Em7"],
            "Orchestral Bridge": ["E", "E", "E", "E"],
            "Final": ["G", "Bm", "Em", "C"],
        }, composer="Lennon–McCartney"),
        _s("Help!", "The Beatles", "Rock", "A", {
            "Verse": ["A", "C#m", "F#m", "D"],
            "Chorus": ["E", "A", "D", "D"],
            "Bridge": ["Bm", "G", "A", "A"],
        }, composer="Lennon–McCartney"),
        _s("All You Need Is Love", "The Beatles", "Rock", "G", {
            "Verse": ["G", "D", "Em", "D"],
            "Chorus": ["C", "D", "G", "G"],
            "Bridge": ["Em", "A7", "D", "D"],
        }, composer="Lennon–McCartney"),

        # --- Jobim & bossa ---
        _s("The Girl from Ipanema", "Antonio Carlos Jobim", "Jazz", "F", {
            "Intro (Turnaround)": ["Gm7", "C7", "Gm7", "C7"],
            "Verse / A Section": ["Fmaj7", "G7", "Gm7", "C7", "Fmaj7", "G7", "Gm7", "C7"],
            "Bridge / B Section": ["Dbmaj7", "B7", "F#m7", "B7", "Gm7", "Eb7", "Am7", "D7"],
            "Last A (Recap)": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Wave", "Antonio Carlos Jobim", "Jazz", "D", {
            "Intro": ["Dmaj7", "Dmaj7", "Dmaj7", "Dmaj7"],
            "Verse / A Section": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "F#m7", "B7b9"],
            "Bridge / B Section": ["Em9", "A13", "Dmaj9", "Dmaj9", "Fm9", "Bb13", "Ebmaj9", "A7b13"],
            "Final A / Outro": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "Dmaj9", "A13"],
        }, composer="Antonio Carlos Jobim"),
        _s("One Note Samba", "Antonio Carlos Jobim", "Jazz", "Db", {
            "Verse": [
                "Dbm7", "C7", "B7sus4", "Bb7b5",
                "Dbm7", "C7", "B7sus4", "Bb7b5",
                "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                "Dbm7", "C7", "B7sus4", "Bb7b5", "A6/9",
            ],
            "Chorus": [
                "Dm7", "G7", "Cmaj7",
                "Cm7", "F7", "Bbmaj7",
                "Bdim", "Bb7b5",
            ],
            "Ending / Tag": [
                "Dbm7", "C7", "B7sus4", "Bb7b5",
                "Dbm7", "C7", "B7sus4", "Bb7b5",
                "Em9", "A7#5", "Dmaj7", "Dm7", "G7",
                "C6", "B7", "Bbmaj7", "A7",
            ],
        }, composer="Antonio Carlos Jobim · Newton Mendonça",
          extensions=_ext(default_bpm=130, default_groove="Bossa nova"),
          chart_status="practice_level_verified"),
        _s("Desafinado", "Antonio Carlos Jobim", "Jazz", "F", {
            "A Section": ["Fmaj7", "G7", "Gm7", "C7", "Am7", "D7", "Gm7", "C7"],
            "B Section": ["Fmaj7", "F#dim7", "Gm7", "C7", "Fmaj7", "D7", "Gm7", "C7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Corcovado", "Antonio Carlos Jobim", "Jazz", "C", {
            "Intro": ["Cmaj9", "D9", "Dm9", "G13"],
            "A Section": ["Cmaj9", "D9", "Dm9", "G13", "Cmaj9", "D9", "Dm9", "G13"],
            "B Section": ["Em9", "A7b9", "Dm9", "G13", "Cmaj9", "Cmaj9"],
        }, composer="Antonio Carlos Jobim"),
        _s("Meditation", "Antonio Carlos Jobim", "Jazz", "C", {
            "A Section": ["Cmaj7", "Cmaj7", "Bm7b5", "E7", "Am7", "D7", "Dm7", "G7"],
            "B Section": ["Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Agua de Beber", "Antonio Carlos Jobim", "Jazz", "Am", {
            "A Section": ["Am7", "D7", "Am7", "D7", "Am7", "D7", "Gmaj7", "Gmaj7"],
            "B Section": ["Bm7b5", "E7", "Am7", "Am7", "Dm7", "G7", "Cmaj7", "E7"],
        }, composer="Antonio Carlos Jobim"),
        _s("How Insensitive", "Antonio Carlos Jobim", "Jazz", "Dm", {
            "A Section": ["Dm9", "Dm9/C", "Bdim7", "Bbmaj7", "A7", "A7", "Dm", "Dm"],
            "B Section": ["Gm7", "C7", "Fmaj7", "Bbmaj7", "Em7b5", "A7", "Dm", "A7"],
        }, composer="Antonio Carlos Jobim"),
        _s("So Nice (Summer Samba)", "Marcos Valle", "Jazz", "F", {
            "Intro": ["Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6", "Fmaj7", "F6"],
            "Verse": [
                "Fmaj7", "F6", "Fmaj7", "F6",
                "Bm7", "E9", "Bm7", "E9",
                "Bbmaj7", "Bb6", "Bbmaj7", "Bb6",
                "Bbm7", "Bbm6", "Bbm7", "Bbm6",
            ],
            "Chorus": [
                "Am7", "D7b9", "Gm7", "C7b9",
                "Em7b5", "A7#5", "Dm9",
                "G13", "Gm7", "C#9", "C9",
            ],
            "Chorus (alternate)": [
                "Am7", "D7b9", "Gm7", "C7b9",
                "Fmaj7", "Bb7", "Fmaj7",
            ],
        }, composer="Marcos Valle · Norman Gimbel",
          extensions=_ext(default_bpm=135, default_groove="Bossa nova"),
          chart_status="practice_level_verified"),

        # --- Jazz standards (practice forms) ---
        _s("Autumn Leaves", "Jazz Standard", "Jazz", "Gm", {
            "Intro (Minor ii–V)": ["Am7b5", "D7b9", "Gm9", "Gm9"],
            "Verse / A": ["Cm9", "F13", "Bbmaj9", "Ebmaj9", "Am7b5", "D7b9", "Gm9", "Gm9"],
            "Bridge / B": ["Cm9", "F13", "Bbmaj9", "Ebmaj9", "Am7b5", "D7b9", "Gm9", "D7b9"],
        }, composer="Joseph Kosma"),
        _s("Blue Bossa", "Kenny Dorham", "Jazz", "Cm", {
            "A Section": ["Cm9", "Fm9", "Dm7b5", "G7b9", "Cm9", "Cm9"],
            "B Section": ["Ebm9", "Ab13", "Dbmaj9", "Dbmaj9", "Dm7b5", "G7b9", "Cm9", "G7b9"],
        }, composer="Kenny Dorham"),
        _s("All of Me", "Jazz Standard", "Jazz", "C", {
            "A Section": ["Cmaj7", "E7", "A7", "Dm7", "E7", "Am7", "D7", "G7"],
            "B Section": ["Cmaj7", "E7", "A7", "Dm7", "Fmaj7", "Fm7", "Cmaj7", "A7"],
            "Turnaround": ["Dm7", "G7", "Cmaj7", "G7"],
        }, composer="Gerald Marks & Seymour Simons"),
        _s("Fly Me to the Moon", "Bart Howard", "Jazz", "C", {
            "A Section": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
            "B Section": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "E7"],
        }, composer="Bart Howard"),
        _s("So What", "Miles Davis", "Jazz", "Dm", {
            "A Section": ["Dm7"] * 8,
            "Bridge": ["Ebm7"] * 8,
            "Final A": ["Dm7"] * 8,
        }, composer="Miles Davis"),
        _s("Take the A Train", "Duke Ellington", "Jazz", "C", {
            "A Section": ["Cmaj7", "Cmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
            "B Section": ["Fmaj7", "Fmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
        }, composer="Billy Strayhorn"),
        _s("There Will Never Be Another You", "Harry Warren", "Jazz", "Eb", {
            "A Section": ["Ebmaj7", "Cm7", "Fm7", "Bb7", "Gm7", "C7", "Fm7", "Bb7"],
            "B Section": ["Ebmaj7", "Abmaj7", "Dm7b5", "G7", "Cm7", "F7", "Fm7", "Bb7"],
        }, composer="Harry Warren"),
        _s("All the Things You Are", "Jerome Kern", "Jazz", "Ab", {
            "A Section": ["Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "G7", "Cmaj7", "Cmaj7"],
            "B Section": ["Cm7", "Fm7", "Bb7", "Ebmaj7", "Abmaj7", "D7", "Gmaj7", "Gmaj7"],
        }, composer="Jerome Kern"),
        _s("Body and Soul", "Jazz Standard", "Jazz", "Db", {
            "A Section": ["Dbmaj7", "Ebm7", "E7", "Amaj7", "Abm7", "Db7", "Gbmaj7", "Gbmaj7"],
            "B Section": ["Fm7", "Bb7", "Ebmaj7", "Gm7b5", "C7", "Fm7", "Bb7", "Eb7"],
        }, composer="Johnny Green"),
        _s("Misty", "Erroll Garner", "Jazz", "Eb", {
            "A Section": ["Ebmaj7", "Bbm7", "Ebmaj7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7"],
            "B Section": ["Am7b5", "D7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
        }, composer="Erroll Garner"),
        _s("Satin Doll", "Duke Ellington", "Jazz", "C", {
            "A Section": ["D7", "D7", "Dm7", "G7", "Cmaj7", "Cmaj7", "Am7", "D7"],
            "B Section": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        }, composer="Duke Ellington"),
        _s("Blue in Green", "Miles Davis", "Jazz", "Gm", {
            "A Section": ["Gm7", "Gm7", "A7#9", "A7#9", "Gm7", "Gm7", "Gm7", "Gm7"],
        }, composer="Miles Davis / Bill Evans"),

        # --- Rock / Funk / Blues anchors ---
        # Minimal shell - the real 10-section arena-rock chart is supplied by
        # _journey_believin_chart_pack() via _core_chart_overrides(). This
        # placeholder only exists so the override has a (title, artist) row
        # to patch; every chart-related field below is fully replaced.
        _s("Don't Stop Believin'", "Journey", "Rock", "E", {
            "Placeholder": ["E"],
        }),
        _s("Superstition", "Stevie Wonder", "Funk", "Eb", {
            "Main Groove": ["Ebm7", "Ebm7", "Ebm7", "Ebm7"],
            "Chorus": ["Ab7", "Gb7", "Ebm7", "Ebm7"],
            "Final Groove": ["Ebm7", "Ebm7", "Ebm7", "Ebm7"],
        }),
        _s("Cissy Strut", "The Meters", "Funk", "C", {
            "Main Funk Vamp": ["C7", "C7", "C7", "C7"],
            "Turnaround": ["F7", "Eb7", "C7", "C7"],
        }),
        _s("12-Bar Blues in F", "Traditional", "Blues", "F", {
            "Bars 1-4": ["F7", "Bb7", "F7", "F7"],
            "Bars 5-8": ["Bb7", "Bb7", "F7", "F7"],
            "Bars 9-12": ["C7", "Bb7", "F7", "C7"],
        }),
        *_jewish_catalog_songs(),
        _s("Ode to Joy", "Beethoven", "Classical", "D", {
            "Main Theme": ["D", "A", "D", "G", "D", "A", "D"],
            "Practice Variation": ["D", "G", "A", "D"],
        }, composer="Ludwig van Beethoven"),
    ]
    # Apply verified-record replacements FIRST, then core chart overrides LAST so
    # the override always wins. Previously the order was reversed, which caused
    # _apply_requested_verified_records() to silently clobber freshly-overridden
    # rows (e.g. Shallow) with their older verified-record snapshots.
    return _apply_core_chart_overrides(_apply_requested_verified_records(records))
