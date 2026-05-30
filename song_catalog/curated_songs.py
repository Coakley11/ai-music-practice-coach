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
    section_order = list(inter.keys())
    scale_hints = {
        "Cm": ["C Natural Minor", "C Minor Pentatonic"],
        "F7": ["F Mixolydian"],
        "Bb7": ["Bb Mixolydian"],
        "C7": ["C Mixolydian"],
        "Dm": ["D Dorian"],
        "Ab6": ["Ab Major"],
    }
    return {
        "key": "Cm",
        "sections": inter,
        "chart_versions": _levels(beginner=beg, intermediate=inter, advanced=inter),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "guitar_tabs": CHAMPIONS_GUITAR_TABS,
        "composer": "Freddie Mercury",
        "lyric_cues": {
            "Verse 1": ["Piano-driven verse — Cm · Gm7/C vamp"],
            "Chorus 1": ["Anthem lift — F major center, Bb|C7 push"],
            "Ending Tag": ["Fm · Gm7 tag before verse 2"],
            "Verse 2": ["Second verse — same Cm harmony"],
            "Chorus 2": ["Chorus return — layered vocals"],
            "Final Chorus": ["Biggest stadium singalong chorus"],
            "Outro": ["Sustained anthem outro — full chorus harmony"],
        },
        "extensions": _ext(
            arrangement_notes=CHAMPIONS_ARRANGEMENT_NOTES,
            default_bpm=65,
            default_groove="Rock groove",
            time_signature="4/4",
            vocal_showcase=True,
            queen_arena_anthem=True,
            repertoire_tags=[
                "Queen",
                "Freddie Mercury",
                "Arena Rock",
                "Power Ballad",
                "Anthem",
                "Karaoke Friendly",
                "Vocal Showcase",
            ],
            harmonic_analysis={
                "progression_summary": (
                    "Cm verse with slash bass motion; F-centered chorus "
                    "with diminished passing chords and Fm tag"
                ),
                "scale_suggestions": scale_hints,
            },
            lyric_chord_chart=CHAMPIONS_LYRIC_CHART,
        ),
    }


def _thinking_out_loud_chart_pack() -> dict[str, Any]:
    """Thinking Out Loud — Ed Sheeran (C guitar chart · D concert, 4/4)."""
    verse = ["C", "C/E", "F", "G"] * 4
    turnaround = ["C", "C/E", "F", "G", "C", "C/E", "F", "G"]
    pre_chorus = (
        ["Dm", "G", "C"]
        + ["Dm", "G"]
        + ["Dm", "G", "Am"]
        + ["Dm", "G"]
        + ["C", "C/E"]
    )
    chorus = ["F", "G", "C", "C/E"] * 3 + ["F", "G"]
    ending_tag = ["Am", "G", "F", "C/E", "Dm", "G", "C"]

    intermediate = {
        "Verse 1": list(verse),
        "Turnaround": list(turnaround),
        "Pre-Chorus 1": list(pre_chorus),
        "Chorus 1": list(chorus),
        "Ending Tag": list(ending_tag),
        "Verse 2": list(verse),
        "Pre-Chorus 2": list(pre_chorus),
        "Chorus 2": list(chorus),
        "Instrumental": list(verse),
        "Final Chorus": list(chorus),
        "Outro": list(ending_tag) * 2,
    }

    def _beg(ch: str) -> str:
        return ch.replace("C/E", "C").replace("Dm", "Dm").replace("Am", "Am")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = dict(intermediate)
    section_order = list(intermediate.keys())
    scale_hints = {
        "C": ["C Major", "C Pentatonic"],
        "C/E": ["C Major"],
        "F": ["F Lydian", "F Major Pentatonic"],
        "G": ["G Mixolydian"],
        "Dm": ["D Dorian"],
        "Am": ["A Aeolian", "A Minor Pentatonic"],
    }
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
        "composer": "Ed Sheeran",
        "lyric_cues": {
            "Verse 1": ["Intimate acoustic — C · C/E · F · G"],
            "Turnaround": ["Turnaround — hold the C/E bass line"],
            "Pre-Chorus 1": ["Gradual build into chorus"],
            "Chorus 1": ["Romantic lift — F · G · C · C/E"],
            "Ending Tag": ["Tag — Am · G · F · C/E · Dm · G · C"],
            "Verse 2": ["Second verse — same loop"],
            "Pre-Chorus 2": ["Pre-chorus 2 — fuller feel"],
            "Chorus 2": ["Chorus return"],
            "Instrumental": ["Instrumental — maintain groove"],
            "Final Chorus": ["Final chorus — warmest dynamics"],
            "Outro": ["Outro — let chords breathe"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C-shape guitar chart** (concert/recording **D major**, "
                "capo-friendly). **4/4**, ~75 BPM soul-pop ballad. Preserve "
                "**C/E** for smooth bass movement — do not drop the slash. "
                "Verse: intimate acoustic; pre-chorus: gradual build; chorus: "
                "fuller rhythm. Backing: acoustic guitar, light percussion, "
                "bass, subtle electric piano, warm pads — no heavy rock or "
                "jazz reharm. Wedding / singer-songwriter practice friendly."
            ),
            default_bpm=75,
            default_groove="Ballad",
            time_signature="4/4",
            vocal_showcase=True,
            ed_sheeran_acoustic=True,
            repertoire_tags=[
                "Ed Sheeran",
                "Acoustic Pop",
                "Wedding Song",
                "Romantic Ballad",
                "Karaoke Friendly",
                "Guitar/Vocal Performance",
            ],
            harmonic_analysis={
                "progression_summary": "I–I/3–IV–V verse; Dm–G–C pre-chorus; F–G–I chorus",
                "scale_suggestions": scale_hints,
                "concert_key": "D",
            },
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


def _say_chart_pack() -> dict[str, Any]:
    """Say — John Mayer (G major, pop ballad, 4/4).

    One list item = one bar. Main loop **G–C–Em–D**; bridge **Am–C–D**
    then **C–D**; final chorus **Em–G / C7** hold. No pushes, split
    bars, N.C., or stop-time hits — straight pop-ballad backing.
    """
    from song_catalog.lyric_chord_charts import SAY_CHART

    main4 = ["G", "C", "Em", "D"]
    turnaround = list(main4)
    verse16 = main4 * 4
    chorus16 = main4 * 4
    bridge = ["Am", "C", "D", "Am", "C", "D", "C", "D"]
    final_chorus = ["Em", "G", "C7", "C7", "Em", "G", "C7", "C7"]

    intermediate = {
        "Intro": list(main4),
        "Verse 1": list(verse16),
        "Chorus 1": list(chorus16),
        "Turnaround 1": list(turnaround),
        "Verse 2": list(verse16),
        "Chorus 2": list(chorus16),
        "Turnaround 2": list(turnaround),
        "Bridge": list(bridge),
        "Turnaround 3": list(turnaround),
        "Verse 3": list(verse16),
        "Final Chorus": list(final_chorus),
    }
    beginner = {
        "Intro": list(main4),
        "Verse 1": list(main4),
        "Chorus 1": list(main4),
        "Turnaround 1": list(main4),
        "Verse 2": list(main4),
        "Chorus 2": list(main4),
        "Turnaround 2": list(main4),
        "Bridge": ["Am", "C", "D", "C"],
        "Turnaround 3": list(main4),
        "Verse 3": list(main4),
        "Final Chorus": ["Em", "G", "C7", "C7"],
    }
    section_order = list(intermediate.keys())
    guitar_tabs = {
        "G": "320003",
        "C": "x32010",
        "Em": "022000",
        "D": "xx0232",
        "Am": "x02210",
        "C7": "x32310",
    }
    return {
        "key": "G",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "guitar_tabs": guitar_tabs,
        "lyric_cues": {
            "Intro": ["Instrumental — G · C · Em · D"],
            "Verse 1": [
                "Take all of your wasted honor",
                "Every little past frustration",
                "Take all of your so-called problems",
                "Better put 'em in quotations",
            ],
            "Chorus 1": [
                "Even if your hands are shaking",
                "And your faith is broken",
                "Even if your eyes are closing",
                "Say it anyway",
            ],
            "Verse 2": ["Second verse — same G · C · Em · D loop"],
            "Chorus 2": ["Chorus lift — same loop, more energy"],
            "Bridge": [
                "Walking like a one man army",
                "Fighting with the shadows in your head",
                "Living out the same old moment",
                "Knowing that it's all a waste of time",
            ],
            "Verse 3": ["Third verse — return to main loop"],
            "Final Chorus": ["Say what you need to say — Em · G · C7 hold"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**G major** pop ballad (**4/4**, mid-tempo, straight 8ths). "
                "Main loop **G–C–Em–D** (one chord per bar). Form: **Intro** → "
                "**Verse 1** → **Chorus 1** → **Turnaround** → **Verse 2** → "
                "**Chorus 2** → **Turnaround** → **Bridge** (**Am–C–D**, then "
                "**C–D**) → **Turnaround** → **Verse 3** → **Final Chorus** "
                "(**Em–G / C7**). No pushes, anticipations, split bars, or "
                "N.C. hits. Backing intensity builds on successive choruses; "
                "final chorus is the peak."
            ),
            default_bpm=82,
            default_groove="Ballad",
            time_signature="4/4",
            lyric_chord_chart=SAY_CHART,
        ),
    }


def _scientist_chart_pack() -> dict[str, Any]:
    """The Scientist — Coldplay (D minor concert, piano ballad, 4/4).

    One list item = one bar unless token uses ``|`` for an in-bar split
    (e.g. ``D|Dmaj7`` = two beats each). **N.C.** bars are true tacet.
    Preserve slash colors: **A/D · D6/9 · A/E · Asus4 · Dsus2/C#**.
    """
    verse_loop = ["Bm7", "G", "D", "Dsus2"]
    chorus = [
        "G",
        "D",
        "Dsus2",
        "A/D",
        "D6/9",
        "A/E",
        "Asus4",
        "A",
    ]
    ending_loop = ["Bm7", "G", "D", "D"]

    intermediate = {
        "Intro": verse_loop * 2,
        "Verse 1": verse_loop * 4,
        "Chorus 1": list(chorus),
        "N.C. 1": ["N.C."],
        "Instrumental 1": [
            "D",
            "G",
            "D",
            "D|Dmaj7",
            "Bm7",
            "G",
            "D",
            "Dsus2",
        ],
        "Verse 2": verse_loop * 3 + ["Bm7", "G", "D", "Dsus2/C#"],
        "Chorus 2": list(chorus),
        "N.C. 2": ["N.C."],
        "Instrumental 2": ["D", "G", "D", "D"],
        "Ending": ending_loop * 4,
        "Final Tag": ["Bm7", "G", "D"],
    }

    def _beg(ch: str) -> str:
        return (
            ch.replace("Dsus2/C#", "Dsus2")
            .replace("D6/9", "D")
            .replace("Dsus2", "D")
            .replace("A/D", "A")
            .replace("A/E", "A")
            .replace("Asus4", "A")
            .replace("D|Dmaj7", "D")
            .replace("Bm7", "Bm")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    section_order = list(intermediate.keys())
    scale_hints = {
        "Bm7": ["B Dorian", "B Minor Pentatonic"],
        "G": ["G Major"],
        "D": ["D Major"],
        "Dsus2": ["D Major"],
        "Dsus2/C#": ["D Major"],
        "A/D": ["A Mixolydian"],
        "D6/9": ["D Major"],
        "A/E": ["A Mixolydian"],
        "Asus4": ["A Mixolydian"],
        "A": ["A Mixolydian"],
        "Dmaj7": ["D Ionian", "D Lydian"],
    }
    return {
        "key": "Dm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Coldplay",
        "lyric_cues": {
            "Intro": ["Piano intro — Bm7 · G · D · Dsus2"],
            "Verse 1": ["Come up to meet you, tell you I'm sorry…"],
            "Chorus 1": ["Nobody said it was easy…"],
            "N.C. 1": ['N.C. — "Take me back to the start"'],
            "Instrumental 1": ["Instrumental — D · G · D · D/Dmaj7"],
            "Verse 2": ["Second verse — walk down to Dsus2/C#"],
            "Chorus 2": ["Chorus lift — wider strings, gentle drums"],
            "N.C. 2": ['N.C. — "I\'m going back to the start"'],
            "Instrumental 2": ["Short instrumental — emotional piano focus"],
            "Ending": ["Outro loop — gradually thin instrumentation"],
            "Final Tag": ["Final Bm7 · G · D — let the chord ring"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D minor** (concert) piano ballad (**4/4**, ~73 BPM). "
                "Common guitar reading uses capo + open-position shapes; "
                "preserve **Bm7 · G · D · Dsus2 · A/D · D6/9 · A/E · Asus4 · "
                "A · Dmaj7 · Dsus2/C#** — do not simplify slash colors. "
                "Verse: sparse piano; chorus: gentle lift with soft strings; "
                "ending fades to **Bm7–G–D** tag. Backing: piano primary, "
                "soft strings, bass, light brushes, ambient pads — avoid "
                "heavy rock guitars. Karaoke- and lyric-focused practice "
                "friendly; emotional dynamic shaping for performance mode."
            ),
            default_bpm=73,
            default_groove="Ballad",
            time_signature="4/4",
            vocal_showcase=True,
            coldplay_piano_ballad=True,
            repertoire_tags=[
                "Coldplay",
                "Piano Ballad",
                "Alternative Rock",
                "Emotional Ballad",
                "Karaoke Friendly",
                "Vocal Showcase",
            ],
            harmonic_analysis={
                "progression_summary": (
                    "Bm7–G–D–Dsus2 verse loop; chorus slash walk "
                    "A/D → D6/9 → A/E → Asus4 → A"
                ),
                "scale_suggestions": scale_hints,
            },
        ),
    }


def _blue_bossa_chart_pack() -> dict[str, Any]:
    """Blue Bossa — Kenny Dorham (C minor, bossa nova, 4/4, 16-bar).

    Classic A/B: **Cm7–Fm7–Dm7b5–G7(♯5)–Cm7** then
    **Ebm7–Ab7–Dbmaj7–Dm7b5–G7–Cm7**. One list item = one bar.
    """
    section_a = ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]
    section_b = ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "Cm7"]
    head = list(section_a) + list(section_b)

    intermediate = {
        "Section A": list(section_a),
        "Section B": list(section_b),
        "Head": list(head),
        "Solo": list(head) * 2,
        "Outro": ["Dm7b5", "G7", "Cm7", "Cm7"],
    }

    def _beg(ch: str) -> str:
        return (
            ch.replace("G7#5", "G7")
            .replace("Dm7b5", "Dm")
            .replace("Dbmaj7", "Db")
            .replace("Ebm7", "Ebm")
            .replace("Fm7", "Fm")
            .replace("Cm7", "Cm")
            .replace("Ab7", "Ab")
        )

    beginner = {name: [_beg(c) for c in chords] for name, chords in intermediate.items()}

    def _adv(ch: str) -> str:
        mapping = {
            "Cm7": "Cm9",
            "Fm7": "Fm9",
            "Dm7b5": "Dm7b5",
            "G7#5": "G7#5",
            "G7": "G7b9",
            "Ebm7": "Ebm9",
            "Ab7": "Ab13",
            "Dbmaj7": "Dbmaj9",
        }
        return mapping.get(ch, ch)

    advanced = {name: [_adv(c) for c in chords] for name, chords in intermediate.items()}
    section_order = list(intermediate.keys())
    scale_hints = {
        "Cm7": ["C Dorian", "C Minor Pentatonic", "C Blues Scale"],
        "Fm7": ["F Dorian"],
        "Dm7b5": ["D Locrian", "D Locrian ♮2"],
        "G7#5": ["G Whole Tone", "G Altered"],
        "G7": ["G Mixolydian", "G Altered", "G Half-Whole Diminished"],
        "Ebm7": ["Eb Dorian"],
        "Ab7": ["Ab Mixolydian"],
        "Dbmaj7": ["Db Ionian", "Db Lydian"],
    }
    return {
        "key": "Cm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Kenny Dorham",
        "lyric_cues": {
            "Section A": ["Head — lighter comping, melody space"],
            "Section B": ["Bridge — major ii–V–I to Dbmaj7"],
            "Head": ["Full 16-bar head — bossa ~135 BPM"],
            "Solo": ["Solo — stronger rhythm section, active bass"],
            "Outro": ["ii–V–i turnaround tag on Cm7"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C minor** jazz standard (**4/4**). Bossa feel **130–140 BPM** "
                "(default **135**); **Jazz swing** groove for **160–180** readings. "
                "Preserve **Cm7 · Dm7b5 · G7 · G7#5 · Fm7 · Ebm7 · Ab7 · Dbmaj7**. "
                "Recognize **Dm7b5–G7–Cm7** as minor **ii–V–i** and "
                "**Ebm7–Ab7–Dbmaj7** as major **ii–V–I**. Backing styles: "
                "bossa (nylon guitar, shaker, piano comp), jazz trio, or "
                "Latin combo. Core repertoire alongside Autumn Leaves, "
                "Satin Doll, ATTYA, Fly Me to the Moon, Take the A Train."
            ),
            default_bpm=135,
            default_groove="Bossa nova",
            time_signature="4/4",
            form="16-bar AABA-style (8 + 8)",
            jazz_standard_flagship=True,
            repertoire_tags=[
                "Jazz Standard",
                "Bossa Nova",
                "Latin Jazz",
                "Saxophone Friendly",
                "Piano Friendly",
                "Guitar Friendly",
                "Improvisation Study",
                "Essential Jazz Repertoire",
            ],
            harmonic_analysis={
                "progression_summary": (
                    "Minor ii–V–i (Dm7b5–G7–Cm7); major ii–V–I "
                    "(Ebm7–Ab7–Dbmaj7)"
                ),
                "scale_suggestions": scale_hints,
                "turnarounds": ["Dm7b5–G7–Cm7", "Ebm7–Ab7–Dbmaj7"],
            },
        ),
    }


def _nysom_chart_pack() -> dict[str, Any]:
    """New York State of Mind — Billy Joel (C major, jazz piano ballad, 4/4).

    One list item = one bar. Tokens with ``|`` (e.g. ``Gm7|C7``) are in-bar
    half-bar splits (two beats each in 4/4).
    """
    intro_head = ["Dm9", "Abmaj7/Bb", "Dm9", "Em7", "F", "Dm9", "F/G"]
    intro_tail = [
        "C",
        "E7",
        "Am7",
        "Gm7|C7",
        "F",
        "A7",
        "Dm",
        "Bb9",
        "C",
        "E7/B",
        "Am7",
        "C/G",
        "F",
        "C/E",
        "D9",
        "C/F",
        "F/G",
        "Am7",
        "D9",
        "Am",
        "G",
        "F/G",
    ]
    verse1 = [
        "C",
        "E7",
        "Am7",
        "Gm7|C7",
        "F",
        "A7",
        "Dm",
        "Bb9",
        "C",
        "E7/B",
        "Am7",
        "C/G",
        "F",
        "C/E",
        "D7",
        "C/F",
        "F/G",
        "Am",
        "D7",
        "Am",
        "G",
        "F/G",
    ]
    verse2 = [
        "C",
        "E7",
        "Am7",
        "Gm7|C7",
        "F",
        "A7",
        "Dm",
        "Bb9",
        "C",
        "E7/B",
        "Am7",
        "C/G",
        "F",
        "C/E",
        "D7",
        "C/F",
        "F/G",
        "Am",
        "D9",
        "Am",
        "G",
        "E7",
    ]
    chorus = [
        "Am7",
        "D7",
        "Gmaj7",
        "G",
        "Gm7",
        "C7",
        "Fmaj7",
        "Bm7",
        "E7",
        "Amaj7",
        "Am7",
        "D7",
        "Gmaj7",
        "Dm7",
        "F/G|G7",
    ]
    verse4 = list(verse1) + [
        "C",
        "E7",
        "Am7",
        "C/G",
        "F",
        "C/E",
        "D7",
        "C/F",
        "F/G",
        "C",
        "E7",
        "Am7",
        "Bb9",
    ]
    solo = [
        "C",
        "E7",
        "Am7",
        "Gm7|C7",
        "F",
        "A7",
        "Dm",
        "Bb9",
        "C",
        "E7/B",
        "Am7",
        "C/G",
        "F",
        "C/E",
        "D9",
        "C/F",
        "F/G",
        "Am",
        "D7",
        "Am",
        "G",
        "E7",
    ]
    outro = ["Eb6", "Ab", "Dm7", "Dbmaj13", "Cmaj9"]

    intermediate = {
        "Intro": intro_head + intro_tail,
        "Verse 1": list(verse1),
        "Verse 2": list(verse2),
        "Chorus 1": list(chorus),
        "Verse 3": list(verse1),
        "Solo": list(solo),
        "Chorus 2": list(chorus),
        "Verse 4 (Extended)": list(verse4),
        "Outro": list(outro),
    }

    def _beg_token(ch: str) -> str:
        if "|" in ch:
            return "|".join(_beg_token(p.strip()) for p in ch.split("|") if p.strip())
        head = ch.split("/")[0].strip()
        repl = (
            ("Abmaj7", "Ab"),
            ("Dbmaj13", "Db"),
            ("Cmaj9", "C"),
            ("Gmaj7", "G"),
            ("Fmaj7", "F"),
            ("Amaj7", "A"),
            ("Bb9", "Bb"),
            ("Dm9", "Dm"),
            ("Eb6", "Eb"),
            ("Em7", "Em"),
            ("Am7", "Am"),
            ("Gm7", "Gm"),
            ("Bm7", "Bm"),
            ("Dm7", "Dm"),
            ("C7", "C"),
            ("D9", "D"),
            ("D7", "D"),
            ("E7", "E"),
            ("A7", "A"),
            ("G7", "G"),
        )
        for old, new in repl:
            head = head.replace(old, new)
        if "/" in ch:
            bass = ch.split("/", 1)[1].strip()
            bass_root = bass[0] if bass and bass[0].isalpha() else ""
            if bass_root and bass_root not in head:
                return f"{head}/{bass}"
        return head

    beginner = {
        name: [_beg_token(c) for c in chords]
        for name, chords in intermediate.items()
    }
    section_order = list(intermediate.keys())
    return {
        "key": "C",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Billy Joel",
        "lyric_cues": {
            "Intro": ["Piano intro — Dm9 · Abmaj7/Bb · jazz turnaround"],
            "Verse 1": ["Some folks like to get away…"],
            "Verse 2": ["Second verse — same changes, tag to E7"],
            "Chorus 1": ["New York State of Mind — chorus lift"],
            "Verse 3": ["Third verse"],
            "Solo": ["Sax-style solo section — verse changes with D9"],
            "Chorus 2": ["Chorus return — fuller lounge band"],
            "Verse 4 (Extended)": ["Extended ending verse — final cadence setup"],
            "Outro": ["Outro: Eb6 · Ab · Dm7 · Dbmaj13 · Cmaj9"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C major** jazz piano ballad (**4/4**, ~74 BPM, straight 8ths). "
                "Preserve slash chords (**Abmaj7/Bb**, **F/G**, **E7/B**, **C/G**, "
                "**C/E**, **C/F**) and color tones (**Dm9**, **Bb9**, **D9**, "
                "**Gmaj7**, **Fmaj7**, **Amaj7**, **Dbmaj13**, **Cmaj9**). "
                "Half-bar splits: **Gm7|C7**, **F/G|G7**. Piano-led lounge "
                "feel; brushed drums; walking bass; solo section suits sax lead; "
                "outro is a final jazz cadence. **Advanced** chart tier."
            ),
            default_bpm=74,
            default_groove="Ballad",
            time_signature="4/4",
        ),
    }


def _jtway_chart_pack() -> dict[str, Any]:
    """Just the Way You Are — Billy Joel (D major, smooth pop/jazz ballad, 4/4).

    One list item = one bar. ``|`` marks in-bar half-bar splits (e.g. ``Bm|D7``).
    """
    turn = ["Gm6/D", "G/D", "Dsus4"]
    intro = turn * 2

    verse1 = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D7",
        "Gmaj7",
        "Gm7",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm7",
        "D/F#",
        "Bm7",
        "E9sus4",
        "E9",
        "G/A",
    ]
    refrain1 = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D9",
        "Gmaj7",
        "Gm7",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "Em7",
        "G/A",
        *turn,
        *turn,
    ]
    verse2 = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D9",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "E9sus4",
        "E9",
        "G/A",
    ]
    refrain2 = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D9",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "Em7",
        "G/A",
        *turn,
        "Gm6/D",
        "G/D",
        "Dmaj7",
        "D7",
    ]
    bridge = [
        "Gmaj7",
        "A6",
        "F#m7",
        "B7",
        "Em7",
        "A7sus",
        "D",
        "D/C",
        "Bb",
        "C",
        "Am7",
        "D9",
        "Gm",
        "C/G",
        "G/A",
    ]
    sax_solo = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "E9sus4",
        "E9",
        "G/A",
    ]
    refrain4 = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D9",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "Em",
        "A7sus4",
        "Bb",
        "C",
        "Am7",
        "D9",
        "Gm",
        "A7sus4|A7",
    ]
    outro = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Bm7",
        "E9sus4",
        "E9",
        "G/A",
    ]
    outro_fade = [
        "D",
        "Bm6",
        "Gmaj7",
        "Bm|D7",
        "Gmaj7",
        "Gm",
        "D/F#",
        "Am7|D7",
    ]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": list(verse1),
        "Refrain 1": list(refrain1),
        "Verse 2": list(verse2),
        "Refrain 2": list(refrain2),
        "Bridge": list(bridge),
        "Refrain 3": list(refrain1),
        "Sax Solo": list(sax_solo),
        "Refrain 4": list(refrain4),
        "Outro": list(outro),
        "Outro (Fade)": list(outro_fade),
    }

    def _beg_token(ch: str) -> str:
        if "|" in ch:
            return "|".join(_beg_token(p.strip()) for p in ch.split("|") if p.strip())
        head = ch.split("/")[0].strip()
        repl = (
            ("E9sus4", "E"),
            ("A7sus4", "A"),
            ("A7sus", "A"),
            ("Gmaj7", "G"),
            ("Bm6", "Bm"),
            ("Gm6", "Gm"),
            ("Dsus4", "D"),
            ("Dmaj7", "D"),
            ("F#m7", "F#m"),
            ("Em7", "Em"),
            ("Am7", "Am"),
            ("Bm7", "Bm"),
            ("Gm7", "Gm"),
            ("D9", "D"),
            ("D7", "D"),
            ("B7", "B"),
            ("A6", "A"),
        )
        for old, new in repl:
            head = head.replace(old, new)
        if "/" in ch:
            return ch.split("/")[0].replace("maj7", "").replace("m7", "m") or head
        return head

    beginner = {
        name: [_beg_token(c) for c in chords]
        for name, chords in intermediate.items()
    }
    section_order = list(intermediate.keys())
    return {
        "key": "D",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Billy Joel",
        "lyric_cues": {
            "Intro": ["Electric piano — Gm6/D · G/D · Dsus4 turnaround"],
            "Verse 1": ["Don't go changing…"],
            "Refrain 1": ["I love you just the way you are"],
            "Verse 2": ["Second verse — Gm color on line 2"],
            "Refrain 2": ["Refrain — tag Dmaj7 · D7 before bridge"],
            "Bridge": ["Bridge lift — Bb · C · Am7 · D9"],
            "Refrain 3": ["Refrain return"],
            "Sax Solo": ["Sax / solo — verse-style changes"],
            "Refrain 4": ["Final refrain — extended tag"],
            "Outro": ["Outro vamp"],
            "Outro (Fade)": ["Fade on refrain changes"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D major** smooth pop/jazz ballad (**4/4**, ~76 BPM). Preserve "
                "slash chords (**Gm6/D**, **G/D**, **D/F#**, **G/A**, **D/C**, "
                "**C/G**) and color tones (**Bm6**, **Gmaj7**, **D9**, **E9sus4**, "
                "**A6**, **A7sus**, **A7sus4**). Half-bar splits: **Bm|D7**, "
                "**Am7|D7**, **Bm|D9**, **A7sus4|A7**. Piano/Rhodes-led; bass "
                "follows slash basses; refrains warmer than verses; sax solo "
                "section; outro supports fade. **Advanced** tier."
            ),
            default_bpm=76,
            default_groove="Ballad",
            time_signature="4/4",
        ),
    }


def _come_together_chart_pack() -> dict[str, Any]:
    """Come Together — The Beatles (D minor, blues-rock / swamp groove, 4/4).

    Riff-driven form: intro/instrumental **Dm7** vamp, verses with **N.C.**
  stop-time bars, chorus lift on **Bm** / **Bm/A**.
    """
    riff4 = ["Dm7"] * 4
    riff2 = ["Dm7"] * 2
    verse = ["Dm", "Dm", "A", "G", "N.C."]
    chorus = ["Bm", "Bm/A", "G", "A", "N.C."]
    solo = ["Dm"] * 4 + ["A"] * 4
    outro_fade = ["Dm"] * 4

    intermediate = {
        "Intro": list(riff4),
        "Verse 1": list(verse),
        "Verse 2": list(verse),
        "Chorus 1": list(chorus),
        "Instrumental 1": list(riff4),
        "Verse 3": list(verse),
        "Chorus 2": list(chorus),
        "Instrumental 2": list(riff2),
        "Solo": list(solo),
        "Instrumental 3": list(riff2),
        "Verse 4": list(verse),
        "Final Chorus": list(chorus),
        "Outro (Fade)": list(outro_fade),
    }

    def _beg(ch: str) -> str:
        if ch == "N.C.":
            return "N.C."
        head = ch.split("/")[0].strip()
        return (
            head.replace("Dm7", "Dm")
            .replace("Bm/A", "Bm")
            .replace("maj7", "")
            .replace("m7", "m")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    section_order = list(intermediate.keys())
    return {
        "key": "Dm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Lennon–McCartney",
        "lyric_cues": {
            "Intro": ["Iconic Dm7 riff — bass and guitar groove"],
            "Verse 1": ["Here come old flat-top…"],
            "Chorus 1": ["Come together, right now, over me"],
            "Instrumental 1": ["Intro riff ×4"],
            "Solo": ["Lead-guitar solo — Dm then A vamp"],
            "Final Chorus": ["Final chorus lift"],
            "Outro (Fade)": ["Fade on Dm riff"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D minor** blues-rock / swamp groove (**4/4**, ~82 BPM). "
                "**Riff-driven** — bass riff and guitar riff carry the feel; "
                "avoid piano-ballad comping. **N.C.** bars are intentional "
                "stop-time pockets. Intro/instrumentals vamp **Dm7**; verses "
                "**Dm–Dm–A–G–N.C.**; chorus **Bm–Bm/A–G–A–N.C.** Brushed "
                "drums, prominent bass, chorus slightly fuller than verses."
            ),
            default_bpm=82,
            default_groove="Rock groove",
            time_signature="4/4",
            riff_driven=True,
            backing_character="blues_rock_riff",
        ),
    }


def _day_tripper_chart_pack() -> dict[str, Any]:
    """Day Tripper — The Beatles (E major, driving blues-rock, 4/4).

    Riff-driven British Invasion rock: preserve **E7 · A7 · F# · G# · C# · B**
    dominant colors; main riff sections dominate the arrangement.
    """
    riff_cell = ["E7", "E", "E7", "E"]
    verse_stanza = ["E7", "E", "E7", "A7", "E", "E7"]
    pre_chorus = ["F#", "A", "G#", "C#", "B"]
    outro = ["E7", "E", "E7", "E", "E7", "E", "E7"]

    intermediate = {
        "Intro Riff": riff_cell * 5,
        "Verse 1": verse_stanza * 4,
        "Pre-Chorus": list(pre_chorus),
        "Riff Return": riff_cell * 2,
        "Verse 2": verse_stanza * 4,
        "Pre-Chorus 2": list(pre_chorus),
        "Vocal Break": ["B"],
        "Guitar Break": riff_cell * 3,
        "Riff Return 2": riff_cell * 2,
        "Verse 3": verse_stanza * 4,
        "Pre-Chorus 3": list(pre_chorus),
        "Riff Return 3": riff_cell * 4,
        "Outro": list(outro),
    }

    _signature = {"E7", "A7", "F#", "G#", "C#", "B", "E"}

    def _beg(ch: str) -> str:
        if ch in _signature:
            return ch
        return ch.replace("7", "").replace("m7", "m")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    section_order = list(intermediate.keys())
    scale_hints = {
        "E7": ["E Mixolydian", "E Blues Scale"],
        "A7": ["A Mixolydian"],
        "F#": ["F# Major Pentatonic"],
        "G#": ["G# Major Pentatonic"],
        "C#": ["C# Major Pentatonic"],
        "B": ["B Mixolydian"],
        "E": ["E Major"],
    }

    return {
        "key": "E",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=intermediate,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Lennon–McCartney",
        "guitar_tabs": {
            "E7": "020100",
            "E": "022100",
            "A7": "x02020",
            "F#": "244322",
            "A": "x02220",
            "G#": "466544",
            "C#": "x46664",
            "B": "x24442",
        },
        "lyric_cues": {
            "Intro Riff": [
                "Iconic Day Tripper riff — guitar hook ×5 before vocal",
                "Drums lock to the riff; bass doubles the figure",
            ],
            "Verse 1": [
                "'Got a good reason…' — driving verse on E7 colors",
                "Keep the riff energy under the vocal",
            ],
            "Pre-Chorus": [
                "Rising tension — F# · A · G# · C# · B",
                "Build into the next riff return",
            ],
            "Riff Return": ["Main riff ×2 — instrumental hook"],
            "Guitar Break": ["Secondary guitar riff ×3 — solo break"],
            "Outro": ["Classic Beatles fade on E7 · E riff"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**E major** driving blues-rock / British Invasion (**4/4**, ~138 BPM). "
                "**Riff-driven** — the famous Day Tripper guitar riff is the core hook; "
                "preserve **E7 · A7 · F# · G# · C# · B** exactly. Verse: strong riff + "
                "punchy rhythm section; pre-chorus: rising harmony; riff sections dominate; "
                "outro fades on the riff. Electric guitar, bass, rock drums — **not** "
                "acoustic campfire or jazz reharmonization. Supports riff practice mode, "
                "isolated riff looping, and guitar/bass/full-band backing."
            ),
            default_bpm=138,
            default_groove="Rock groove",
            time_signature="4/4",
            riff_driven=True,
            riff_practice_mode=True,
            loop_riff_mode=True,
            backing_character="blues_rock_riff",
            repertoire_tags=[
                "The Beatles",
                "British Invasion",
                "Classic Rock",
                "Guitar Riff Song",
                "Karaoke Friendly",
            ],
            guitar_showcase=True,
            harmonic_analysis={
                "progression_summary": (
                    "E major riff rock; E7–A7 verse colors; pre-chorus F#–A–G#–C#–B lift"
                ),
                "improvisation_notes": (
                    "E Mixolydian / blues over E7; A Mixolydian on A7; pentatonics on "
                    "F#, G#, C#; sparse fills in riff gaps."
                ),
                "scale_suggestions": scale_hints,
            },
        ),
    }


def _autumn_leaves_chart_pack() -> dict[str, Any]:
    """Autumn Leaves — jazz standard in B minor (4/4).

    Classic **ii–V–I–IV** (Em7–A7–Dmaj7–Gmaj7) then **iiø–V7–i**
    (C#m7b5–F#7–Bm). Matches the common Eric Clapton / jazz-ballad
    reading; one list item = one bar in 4/4.
    """
    cycle = ["Em7", "A7", "Dmaj7", "Gmaj7", "C#m7b5", "F#7", "Bm", "Bm"]
    pre_chorus = [
        "C#m7b5",
        "F#7",
        "Bm",
        "Bm",
        "Em7",
        "A7",
        "Dmaj7",
        "Dmaj7",
    ]
    chorus = [
        "C#m7b5",
        "F#7",
        "Bm",
        "Bm",
        "C#m7b5",
        "F#7",
        "Bm",
        "Bm",
    ]

    intermediate = {
        "Intro": ["Bm", "Bm"],
        "Verse 1": list(cycle),
        "Verse 2": list(cycle),
        "Pre-Chorus": list(pre_chorus),
        "Chorus": list(chorus),
        "Instrumental": list(cycle) * 2,
        "Pre-Chorus 2": list(pre_chorus),
        "Chorus 2": list(chorus),
        "Final Chorus": list(chorus),
        "Outro Solo": list(cycle) * 4,
    }

    def _beg(ch: str) -> str:
        return (
            ch.replace("C#m7b5", "C#dim")
            .replace("Dmaj7", "D")
            .replace("Gmaj7", "G")
            .replace("Em7", "Em")
            .replace("m7b5", "dim")
            .replace("maj7", "")
            .replace("m7", "m")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }

    def _adv(ch: str) -> str:
        mapping = {
            "Em7": "Em9",
            "A7": "A13",
            "Dmaj7": "Dmaj9",
            "Gmaj7": "Gmaj9",
            "C#m7b5": "C#m7b5",
            "F#7": "F#7b9",
            "Bm": "Bm9",
        }
        return mapping.get(ch, ch)

    advanced = {
        name: [_adv(c) for c in chords]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "Em7": ["E Dorian"],
        "A7": ["A Mixolydian", "A altered (advanced)"],
        "Dmaj7": ["D Ionian"],
        "Gmaj7": ["G Lydian"],
        "C#m7b5": ["C# Locrian"],
        "F#7": ["F# Mixolydian", "F# altered (advanced)"],
        "Bm": ["B melodic minor", "B natural minor"],
    }
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
        "composer": "Joseph Kosma · Johnny Mercer",
        "lyric_cues": {
            "Intro": ["Piano intro — Bm vamp"],
            "Verse 1": ["The falling leaves drift by the window…"],
            "Verse 2": ["Second verse — same A section harmony"],
            "Pre-Chorus": ["Bridge into tonic — C#ø · F#7 · Bm"],
            "Chorus": ["Chorus turnaround — iiø–V7–i twice"],
            "Instrumental": ["Head / instrumental — full 8-bar cycle ×2"],
            "Pre-Chorus 2": ["Second bridge"],
            "Chorus 2": ["Second chorus"],
            "Final Chorus": ["Final chorus — hold on Bm"],
            "Outro Solo": [
                "Outro solo — repeat Em7–A7–Dmaj7–Gmaj7 · C#ø–F#7–Bm"
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**B minor** jazz ballad (**4/4**, ~80–85 BPM). Default feel is "
                "a straight **jazz ballad** (even eighths); **Jazz swing** is "
                "available in the groove picker for a light swing. Preserve "
                "qualities: **Em7 · A7 · Dmaj7 · Gmaj7 · C#m7b5 · F#7 · Bm**. "
                "Core motion: **ii–V–I–IV** then **iiø–V7–i**. Backing: piano, "
                "upright bass, brushed drums; optional jazz-guitar comping. "
                "**Advanced** tier adds rootless extensions and **F#7b9**. "
                "Tags: Jazz Standard · Improvisation Standard · Essential Jazz "
                "Repertoire."
            ),
            default_bpm=82,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Jazz Standard",
                "Improvisation Standard",
                "Essential Jazz Repertoire",
            ],
            harmonic_analysis={
                "progression_summary": (
                    "ii–V–I–IV (Em7–A7–Dmaj7–Gmaj7) then "
                    "iiø–V7–i (C#m7b5–F#7–Bm)"
                ),
                "scale_suggestions": scale_hints,
            },
            jazz_ballad=True,
        ),
    }


def _attention_chart_pack() -> dict[str, Any]:
    """Attention — Charlie Puth (D minor, pop-funk, 4/4).

    The entire song rides the **Dm · C · Am · Bb** loop (one chord per bar).
    Groove-driven production — not singer-songwriter strumming.
    """
    loop = ["Dm", "C", "Am", "Bb"]

    intermediate = {
        "Intro": list(loop),
        "Verse 1": list(loop) * 2,
        "Pre-Chorus": list(loop) * 2,
        "Chorus": list(loop) * 2,
        "Verse 2": list(loop) * 2,
        "Pre-Chorus 2": list(loop) * 2,
        "Chorus 2": list(loop) * 2,
        "Bridge": list(loop) * 2,
        "Pre-Chorus 3": list(loop) * 2,
        "Final Chorus": list(loop) * 3,
        "Outro": list(loop) * 2,
    }

    beginner = dict(intermediate)
    advanced = {
        name: [
            c.replace("Dm", "Dm7")
            .replace("Am", "Am7")
            .replace("Bb", "Bbmaj7")
            .replace("C", "Cmaj7")
            for c in chords
        ]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "Dm": ["D natural minor", "D minor pentatonic"],
        "C": ["C major"],
        "Am": ["A minor pentatonic"],
        "Bb": ["Bb major"],
    }
    return {
        "key": "Dm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Charlie Puth & Jacob Kasher",
        "lyric_cues": {
            "Intro": ["Tight bass-pocket intro — Dm · C · Am · Bb"],
            "Verse 1": ["You've been runnin' round…"],
            "Pre-Chorus": ["Lift before the hook — groove builds"],
            "Chorus": ["'Cause you know that I need that attention"],
            "Bridge": ["Bridge — slight breakdown, same loop"],
            "Final Chorus": ["Final chorus — highest energy"],
            "Outro": ["Outro vamp — fade on the loop"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D minor** pop-funk (**4/4**, ~100 BPM). The whole tune is "
                "**Dm · C · Am · Bb** (one chord per bar). **Not** campfire "
                "strumming — bass-led, syncopated guitar, crisp drums. Verse: "
                "lighter; pre-chorus: builds; chorus: full pocket; bridge: "
                "slight breakdown; final chorus: peak energy. Keys stay light "
                "in the mix. Tags: Pop · Funk · Modern Pop · Groove-Based · "
                "Bass Driven."
            ),
            default_bpm=100,
            default_groove="Funk groove",
            time_signature="4/4",
            repertoire_tags=[
                "Pop",
                "Funk",
                "Modern Pop",
                "Charlie Puth",
                "Groove-Based",
                "Bass Driven",
            ],
            harmonic_analysis={
                "progression_summary": "Dm · C · Am · Bb (repeating pop-funk loop)",
                "scale_suggestions": scale_hints,
            },
            groove_based=True,
            backing_character="pop_funk",
        ),
    }


def _dance_monkey_chart_pack() -> dict[str, Any]:
    """Dance Monkey — Tones and I (F# minor, dance/electro-pop, 4/4).

    Main loop **F#m · D · E · C#m** (one chord per bar). Production groove —
    not campfire strumming. Preserve **N.C.** stops and **E.hit** in Verse 1.
    """
    loop = ["F#m", "D", "E", "C#m"]
    pre_chorus_tail = ["F#m", "D", "E", "N.C."]

    intermediate = {
        "Intro": list(loop),
        "Verse 1": list(loop) + ["F#m", "D", "E.hit", "C#m"],
        "Pre-Chorus 1": list(loop) + list(pre_chorus_tail),
        "Chorus 1": list(loop) * 2,
        "Verse 2": list(loop) * 2,
        "Pre-Chorus 2": list(loop) + list(pre_chorus_tail),
        "Chorus 2": list(loop) * 2,
        "Chorus 3": list(loop) * 2,
        "Bridge": list(loop) + list(pre_chorus_tail),
        "Final Chorus": list(loop) * 2,
        "Final Chorus Repeat": list(loop) * 2,
        "Outro": ["N.C."],
    }

    beginner = {
        "Intro": list(loop),
        "Verse 1": list(loop) + ["F#m", "D", "E.hit", "C#m"],
        "Pre-Chorus 1": list(loop) + ["N.C."],
        "Chorus 1": list(loop),
        "Verse 2": list(loop),
        "Pre-Chorus 2": list(loop) + ["N.C."],
        "Chorus 2": list(loop),
        "Chorus 3": list(loop),
        "Bridge": list(loop) + ["N.C."],
        "Final Chorus": list(loop),
        "Final Chorus Repeat": list(loop),
        "Outro": ["N.C."],
    }

    advanced = {
        name: [
            c.replace("F#m", "F#m7")
            .replace("C#m", "C#m7")
            .replace("D", "Dmaj7")
            .replace("E.hit", "Emaj7.hit")
            .replace("E", "Emaj7")
            for c in chords
        ]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "F#m": ["F# natural minor", "F# minor pentatonic"],
        "D": ["D major"],
        "E": ["E major / Mixolydian color"],
        "C#m": ["C# natural minor"],
    }
    return {
        "key": "F#m",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Toni Watson",
        "lyric_cues": {
            "Intro": ["Synth hook — F#m · D · E · C#m pocket"],
            "Verse 1": ["They say oh my god I see the way you shine…", "E.hit = single strum on E"],
            "Pre-Chorus 1": ["Build — last bar N.C. stop before chorus"],
            "Chorus 1": ["Dance for me, dance for me…", "full dance-pop groove"],
            "Verse 2": ["Second verse — same loop, fuller percussion"],
            "Pre-Chorus 2": ["Second lift — N.C. break into chorus"],
            "Chorus 2": ["Second chorus — lock the loop"],
            "Chorus 3": ["Third chorus pass"],
            "Bridge": ["Breakdown — N.C. before final chorus"],
            "Final Chorus": ["Biggest energy — full bass pulse"],
            "Final Chorus Repeat": ["Repeat/fade on the loop"],
            "Outro": ["N.C. — tacet outro"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**F# minor**, **4/4**. Main loop **F#m · D · E · C#m** (one chord/bar). "
                "~98 BPM half-time (~196 double-time). Dance/electro-pop production — "
                "electronic drums, synth bass, claps, rhythmic keys; **not** campfire or "
                "piano ballad. Verse: lighter; pre-chorus/bridge: **N.C.** dramatic stops; "
                "chorus: full pulse. **E.hit** = hold/single strum on E in Verse 1."
            ),
            default_bpm=98,
            default_groove="Pop groove",
            time_signature="4/4",
            repertoire_tags=[
                "Pop",
                "Dance Pop",
                "Electro Pop",
                "Groove-Based",
                "Karaoke Friendly",
                "Vocal Style Practice",
                "Tones and I",
            ],
            harmonic_analysis={
                "progression_summary": "F#m · D · E · C#m (i–VI–VII–iv in F# minor)",
                "scale_suggestions": scale_hints,
            },
            groove_based=True,
            backing_character="pop_funk",
        ),
    }


def _im_yours_chart_pack() -> dict[str, Any]:
    """I'm Yours — Jason Mraz (G shapes / capo 4, concert B major, reggae-pop, 4/4).

    Chart in **G–D–Em–C** with **Dsus4**, **D/F#**, **A7**, half-bar splits, and
    **N.C.** outro pickup. Acoustic island groove — not rock or piano ballad.
    """
    loop = ["G", "D", "Em", "C"]
    verse = list(loop) * 2

    intermediate = {
        "Intro": list(loop),
        "Verse 1": list(verse),
        "Chorus 1": list(loop) * 2,
        "Verse 2": list(loop) + ["G", "D", "Em", "C", "A7"],
        "Chorus 2": ["G", "D|Dsus4", "Em", "C", "G", "D", "Em", "C"],
        "Bridge": [
            "G",
            "D",
            "Em",
            "D",
            "C",
            "A7",
            "G|D/F#",
            "Em|D",
            "C",
            "A7",
        ],
        "Verse 3": list(verse),
        "Final Chorus / Outro Build": [
            "G",
            "D|Dsus4",
            "Em",
            "C",
            "G",
            "D",
            "Em",
            "C",
            "A7",
        ],
        "Outro": ["N.C."] + list(loop) * 2,
    }

    beginner = {
        "Intro": list(loop),
        "Verse 1": list(loop),
        "Chorus 1": list(loop),
        "Verse 2": list(loop) + ["A7"],
        "Chorus 2": ["G", "D|Dsus4", "Em", "C"],
        "Bridge": ["G", "D", "Em", "C", "A7", "G|D/F#", "Em|D", "C", "A7"],
        "Verse 3": list(loop),
        "Final Chorus / Outro Build": ["G", "D|Dsus4", "Em", "C", "A7"],
        "Outro": ["N.C."] + list(loop),
    }

    advanced = {
        name: [
            c.replace("G|", "Gmaj7|")
            .replace("|Dsus4", "|Dsus2")
            .replace("Em|D", "Em7|D")
            .replace("G", "Gmaj7")
            .replace("Em", "Em7")
            .replace("C", "Cadd9")
            .replace("A7", "A7sus4")
            for c in chords
        ]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "G": ["G major", "G major pentatonic"],
        "D": ["D major"],
        "Em": ["E natural minor / relative minor"],
        "C": ["C major"],
        "A7": ["A mixolydian / blues pentatonic over V"],
    }
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
        "composer": "Jason Mraz",
        "guitar_tabs": {
            "G": "320003",
            "D": "xx0232",
            "Dsus4": "xx0233",
            "D/F#": "2x0232",
            "Em": "022000",
            "C": "x32010",
            "A7": "x02020",
        },
        "lyric_cues": {
            "Intro": ["Acoustic island vamp — G · D · Em · C"],
            "Verse 1": ["Well you done done me and you bet I felt it…"],
            "Chorus 1": ["But I won't hesitate no more, no more…"],
            "Verse 2": ["Come on and open up your plans…", "A7 lift into chorus 2"],
            "Chorus 2": ["Open up your plans and damn you're free…", "D|Dsus4 color"],
            "Bridge": ["And it's our God-forsaken right to be loved…", "G|D/F# walkdown"],
            "Verse 3": ["Third verse — same relaxed groove"],
            "Final Chorus / Outro Build": ["I've been spendin' way too long…", "A7 turn"],
            "Outro": ["N.C. pickup — fade on G · D · Em · C"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**B major** concert; chart in **G shapes** (capo **4**). **4/4**, ~75 BPM. "
                "Reggae-pop / island groove — acoustic guitar, light hand percussion, soft "
                "bass, relaxed drums. **Not** rock kit or piano ballad. Preserve **Dsus4**, "
                "**D/F#**, **A7**, half-bar splits (**D|Dsus4**, **G|D/F#**, **Em|D**), "
                "and **N.C.** outro pickup."
            ),
            default_bpm=75,
            default_groove="Pop groove",
            time_signature="4/4",
            capo_note="Capo 4 (G-shape chart) · concert key B major",
            repertoire_tags=[
                "Reggae Pop",
                "Acoustic Pop",
                "Island Groove",
                "Singer-Songwriter",
                "Karaoke Friendly",
                "Jason Mraz",
            ],
            harmonic_analysis={
                "progression_summary": "G–D–Em–C (I–V–vi–IV); A7 dominant color; bridge walkdown",
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="mtv_unplugged_acoustic",
        ),
    }


def _take_on_me_unplugged_chart_pack() -> dict[str, Any]:
    """Take On Me (MTV Unplugged) — a-ha (G major center, acoustic, 4/4).

    MTV Unplugged Summer Solstice 2017 arrangement. One list item = one bar;
    ``|`` marks in-bar half-bar splits (e.g. ``C|G/B``). **Not** the 1980s
    synth-pop production — acoustic guitar, light piano, soft percussion.
    """
    intro = [
        "Am",
        "D/F#",
        "G",
        "C|G/B",
        "Am",
        "D/F#",
        "G",
        "C|Gmaj7/B",
    ]

    def _verse() -> list[str]:
        return [
            "Am",
            "D/F#",
            "Em",
            "Am",
            "D/F#",
            "Em",
            "Am",
            "D/F#",
            "Em",
            "C",
        ]

    def _chorus(*, final: bool = False) -> list[str]:
        tail = ["G", "Bm", "Em", "C"] if final else ["G", "D/F#", "C", "D"]
        return [
            "G",
            "D",
            "Em",
            "D/F#",
            "G",
            "Bm",
            "Em",
            "C",
            "G",
            "B7",
            "Em",
            "C",
            *tail,
        ]

    bridge = [
        "Am",
        "D",
        "G",
        "C|G/B",
        "Am",
        "D",
        "G",
        "C|Gmaj7/B",
        "Am",
        "D",
        "Am",
        "D",
    ]

    outro = [
        "G",
        "B7",
        "Em",
        "C",
        "G",
        "D/F#",
        "Em",
        "C",
        "G",
        "D/F#",
        "C",
    ]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse(),
        "Chorus": _chorus(),
        "Verse 2": _verse(),
        "Chorus 2": _chorus(),
        "Bridge": list(bridge),
        "Verse 3": _verse(),
        "Final Chorus": _chorus(final=True),
        "Outro": list(outro),
    }

    def _beg(ch: str) -> str:
        if "|" in ch:
            return "|".join(_beg(p.strip()) for p in ch.split("|") if p.strip())
        head = ch.split("/")[0].strip()
        return (
            head.replace("Gmaj7", "G")
            .replace("maj7", "")
            .replace("m7", "m")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }

    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
    scale_hints = {
        "Am": ["A natural minor", "A minor pentatonic"],
        "D/F#": ["D major"],
        "G": ["G major"],
        "Em": ["E natural minor"],
        "C": ["C major"],
        "Bm": ["B natural minor"],
        "B7": ["B mixolydian", "B harmonic minor (dominant color)"],
        "C|G/B": ["G major"],
        "C|Gmaj7/B": ["G major", "G lydian"],
    }
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
        "composer": "Magne Furuholmen, Morten Harket & Pål Waaktaar",
        "lyric_cues": {
            "Intro": ["Acoustic fingerpicked intro — Am · D/F# · G · C|G/B"],
            "Verse 1": ["Talking away…"],
            "Chorus": ["Take on me — fuller acoustic strum + piano"],
            "Bridge": ["Dynamic lift — wider acoustic texture"],
            "Final Chorus": ["Biggest unplugged chorus — peak vocal support"],
            "Outro": ["Gradual thinning — fade on G · D/F# · C"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**MTV Unplugged Summer Solstice 2017** (a-ha). **G major** "
                "center with **Am** verse color (**4/4**, ~64 BPM). **Acoustic "
                "pop ballad** — **not** the synth-pop record: use acoustic "
                "guitar, light piano, soft percussion, warm bass. Preserve "
                "slashes **D/F#**, **G/B**, **Gmaj7/B** and colors **B7**, "
                "**Bm**, **Em**. Half-bar splits: **C|G/B**, **C|Gmaj7/B**. "
                "Verse: sparse guitar; chorus: fuller strum; bridge: lift; "
                "outro: reduce instrumentation. Tags: Acoustic · MTV "
                "Unplugged · Pop · Ballad · Folk Pop · Vocal Performance."
            ),
            default_bpm=64,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Acoustic",
                "MTV Unplugged",
                "Pop",
                "Ballad",
                "Folk Pop",
                "Vocal Performance",
                "Singer-Songwriter",
            ],
            harmonic_analysis={
                "progression_summary": (
                    "Am–D/F#–G–C (G major); chorus on G with Bm and B7 color"
                ),
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="mtv_unplugged_acoustic",
        ),
    }


def _iwantit_chart_pack() -> dict[str, Any]:
    """I Want It That Way — Backstreet Boys (Em → F#m, 90s pop ballad, 4/4).

    One list item = one bar. Signature **modulation** to **F# minor** at the
    final chorus; preserve slash **G/D**. Vocal-harmony ballad — backing stays
    light for singers.
    """
    intro = ["Em", "C", "G"] * 2

    def _verse() -> list[str]:
        return ["Em", "C", "G"] * 3 + ["Em", "D", "G"]

    def _chorus(*, tag_end: str = "G") -> list[str]:
        tail = ["Em", "D", tag_end] if tag_end == "G" else ["Em", tag_end]
        return [
            "C",
            "D",
            "Em",
            "C",
            "D",
            "Em",
            "C",
            "D",
            "G",
            *tail,
        ]

    bridge = [
        "Em",
        "G/D",
        "C",
        "Am",
        "D",
        "Em",
        "G/D",
        "C",
        "D",
    ]

    pre_final = [
        "C",
        "D",
        "Em",
        "C",
        "D",
        "Em",
        "C",
        "D",
        "G",
        "Em",
        "D",
    ]

    def _final_chorus() -> list[str]:
        return [
            "D",
            "E",
            "F#m",
            "D",
            "E",
            "F#m",
            "D",
            "E",
            "A",
            "F#m",
            "E",
            "A",
        ]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse(),
        "Chorus 1": _chorus(),
        "Verse 2": _verse(),
        "Chorus 2": _chorus(tag_end="B"),
        "Bridge": list(bridge),
        "Verse 3": _verse(),
        "Pre-Final Chorus": list(pre_final),
        "Key Change": ["N.C."],
        "Final Chorus": _final_chorus(),
        "Final Chorus Repeat": _final_chorus(),
        "Outro": _final_chorus(),
    }

    beginner = dict(intermediate)

    def _adv(ch: str) -> str:
        if ch in ("N.C.", "G/D"):
            return ch
        return {
            "Em": "Em7",
            "C": "Cmaj7",
            "G": "Gmaj7",
            "D": "Dmaj7",
            "B": "B7",
            "E": "E7",
            "F#m": "F#m7",
            "A": "Amaj7",
            "Am": "Am7",
        }.get(ch, ch)

    advanced = {
        name: [_adv(c) for c in chords] for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    return {
        "key": "Em",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Max Martin & Andreas Carlsson",
        "lyric_cues": {
            "Intro": ["Soft pad + guitar — (breath) before verse entrance"],
            "Verse 1": [
                "You are my fire — (breath)",
                "The one desire — (breath)",
                "Believe when I say — (breath)",
                "I want it that way",
            ],
            "Chorus 1": [
                "Tell me why… — (breath before lift)",
                "Ain't nothin' but a heartache — harmony stack",
                "I want it that way — (breath) title hook",
            ],
            "Verse 2": ["Second verse — same breath map as Verse 1"],
            "Chorus 2": ["Chorus 2 — land **B** major color on last bar"],
            "Bridge": [
                "Emotional build — (breath) low support",
                "G/D bass line — widen tone toward pre-chorus",
            ],
            "Verse 3": ["Third verse — conserve energy for final lift"],
            "Pre-Final Chorus": [
                "Rise into modulation — (breath) before key change",
                "Stronger support each pass",
            ],
            "Key Change": [
                "★ Modulate to F# minor — energy step up",
                "(breath) then attack Final Chorus downbeat",
            ],
            "Final Chorus": [
                "F#m chorus — biggest drums & pads",
                "Harmony on 'that way' — (breath) between phrases",
            ],
            "Final Chorus Repeat": ["Hold blend — sustain through repeat"],
            "Outro": ["Gradual release — (breath) on last 'that way'"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**E minor** 90s pop ballad (**4/4**, ~99 BPM) modulating to "
                "**F# minor** at the final chorus (signature moment). Preserve "
                "**G/D** slash. **Vocal harmony ballad** — not a busy "
                "instrumental track: light verse, fuller chorus, bridge build, "
                "noticeable lift at key change. Tags: Vocal Showcase · Harmony "
                "Singing · 90s Pop · Boy Band · Ballad."
            ),
            default_bpm=99,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Vocal Showcase",
                "Harmony Singing",
                "90s Pop",
                "Boy Band",
                "Ballad",
            ],
            vocal_showcase=True,
            modulation={
                "from_key": "Em",
                "to_key": "F#m",
                "section": "Key Change",
            },
            vocal_harmony_hints={
                "Chorus": "Boy-band stacks: melody + upper harmony on title hook.",
                "Final Chorus": "Same stacks a whole step up in F#m — brighter, more open vowels.",
            },
            harmonic_analysis={
                "progression_summary": "Em–C–G verse; chorus C–D–Em; modulates to F#m",
                "scale_suggestions": {
                    "Em": ["E natural minor", "E minor pentatonic"],
                    "C": ["C major"],
                    "G": ["G major"],
                    "D": ["D major"],
                    "F#m": ["F# natural minor", "F# minor pentatonic"],
                },
            },
            backing_character="vocal_ballad_90s",
        ),
    }


def _iwont_say_in_love_chart_pack() -> dict[str, Any]:
    """I Won't Say (I'm in Love) — Disney's Hercules (C, Broadway/gospel, 4/4).

    Susan Egan & the Muses. Slash harmony drives the Broadway sound — preserve
    **C/G**, **G/C**, **G/B**, **G/A**, **Am/G**, **C/E**, **C/D**, **Fmaj7/G**,
    etc. Vocal call-and-response; piano/gospel backing, not guitar strumming.
    """
    verse1 = [
        "C/G",
        "Fmaj7/G",
        "F6/G",
        "C/G",
        "F/G",
        "G7",
        "Am",
        "C/D",
        "D7",
        "G",
        "F/G",
        "G",
        "F/G",
        "G",
    ]

    pre1 = [
        "C",
        "F",
        "G",
        "C",
        "Am",
        "Am/G",
        "F",
        "C/E",
        "Dm7",
        "Gsus",
        "G",
    ]

    chorus1 = [
        "C",
        "G/C",
        "C",
        "G/B",
        "Am",
        "G/A",
        "Am",
        "Am/G",
        "Fmaj7",
        "G/F",
        "Fmaj7/G",
        "G",
        "C",
    ]

    verse2 = [
        "C",
        "Fmaj7/G",
        "F6",
        "C/E",
        "G7",
        "Am",
        "C/D",
        "D",
        "G",
        "F/G",
        "G",
        "F/G",
        "G",
    ]

    pre2 = [
        "C",
        "F",
        "G",
        "C",
        "Am",
        "F",
        "C/E",
        "Dm7",
        "F/G",
    ]

    chorus2 = [
        "C",
        "G/C",
        "C",
        "G/B",
        "Am",
        "G/A",
        "Am/G",
        "Fmaj7",
        "G/F",
        "Fmaj7",
        "F/G",
    ]

    ensemble = [
        "G",
        "Fmaj7/G",
        "G",
        "C",
        "G/C",
        "C",
        "G/B",
        "Am",
        "G/A",
        "Am",
        "Am/G",
        "Fmaj7",
        "G/F",
        "Fmaj7",
        "G",
        "C",
    ]

    tag = ["Am", "F", "G/F", "Fmaj7/G", "G", "C"]

    intermediate = {
        "Verse 1": list(verse1),
        "Pre-Chorus 1": list(pre1),
        "Chorus 1": list(chorus1),
        "Verse 2": list(verse2),
        "Pre-Chorus 2": list(pre2),
        "Chorus 2": list(chorus2),
        "Ensemble Chorus": list(ensemble),
        "Tag": list(tag),
    }

    def _beg(ch: str) -> str:
        head = ch.split("/")[0].strip()
        return (
            head.replace("Fmaj7", "F")
            .replace("F6", "F")
            .replace("Dm7", "Dm")
            .replace("Gsus", "G")
            .replace("G7", "G")
            .replace("D7", "D")
            .replace("maj7", "")
            .replace("sus", "")
            .replace("m7", "m")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
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
        "composer": "Alan Menken & David Zippel",
        "lyric_cues": {
            "Verse 1": [
                "Meg — conversational storytelling; (breath) before Muses enter",
                "If there's a prize — light, not belting yet",
            ],
            "Pre-Chorus 1": [
                "(Call) Muses: 'Honey, you mean the ones who…'",
                "(Response) gospel push on **Gsus → G**",
            ],
            "Chorus 1": [
                "Title hook — 'I won't say I'm in love' (breath)",
                "Slash bass walk **G/B · G/A · Am/G** — keep vowels forward",
            ],
            "Verse 2": ["Second verse — same intimacy as Verse 1"],
            "Pre-Chorus 2": ["Muses tighter — answer phrases shorter"],
            "Chorus 2": ["Chorus lift — brighter, still controlled"],
            "Ensemble Chorus": [
                "(Call-and-response) full Muses gospel stack",
                "Biggest energy — Broadway finale; blend over volume",
                "Shout responses on **G** pickups",
            ],
            "Tag": ["Final tag — (breath) resolve on **C**"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**Disney's Hercules** — Meg & the Muses (**C major**, **4/4**, "
                "~92 BPM). **Broadway / gospel pop** ballad: preserve slash "
                "voicings (**C/G**, **G/C**, **G/B**, **G/A**, **Am/G**, "
                "**C/E**, **C/D**, **Fmaj7/G**, **F6/G**, **F/G**, **Gsus**). "
                "Vocal phrasing, call-and-response, and ensemble harmony drive "
                "the chart — backing uses piano/gospel pads, brushed drums, "
                "light bass (not rock guitar strumming). Verse sparse; "
                "pre-chorus tension; chorus fuller; **Ensemble Chorus** = finale. "
                "Tags: Disney · Broadway · Musical Theatre · Female Vocal "
                "Showcase · Ensemble Vocal · Gospel Pop."
            ),
            default_bpm=92,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Disney",
                "Broadway",
                "Musical Theatre",
                "Female Vocal Showcase",
                "Ensemble Vocal",
                "Gospel Pop",
            ],
            vocal_showcase=True,
            broadway_disney=True,
            call_and_response={
                "Pre-Chorus 1": "Muses interrupt Meg — short call phrases, gospel answers.",
                "Pre-Chorus 2": "Tighter banter — leave space for ensemble punches.",
                "Ensemble Chorus": "Full Muses choir — call-and-response gospel stack.",
            },
            vocal_harmony_hints={
                "Chorus 1": "Gospel-tinged thirds above melody on slash walks.",
                "Ensemble Chorus": "Ensemble stacks + shout responses on G pickups.",
            },
            harmonic_analysis={
                "progression_summary": "C major Broadway slashes; gospel sus + maj7 color",
                "scale_suggestions": {
                    "C": ["C major", "C mixolydian (gospel color)"],
                    "Am": ["A natural minor", "A minor pentatonic"],
                    "Fmaj7": ["F major", "F lydian"],
                    "G7": ["G mixolydian"],
                    "D7": ["D mixolydian"],
                },
            },
            backing_character="broadway_gospel",
        ),
    }


def _how_far_ill_go_chart_pack() -> dict[str, Any]:
    """How Far I'll Go — Disney's Moana (E → F, inspirational ballad, 4/4).

    Auli'i Cravalho. Preserve slash bass **B/D#**, **E/G#**, **Dm/C**, **Ab/G**,
    **Dm7b5** and the full **Ending Descent**. Piano/strings Disney soundtrack
    feel — not rock guitar strumming.
    """
    verse = ["E", "F#m", "C#m", "A"] * 2

    def _pre() -> list[str]:
        return ["C#m", "B/D#", "E", "Am"]

    chorus_a = [
        "E",
        "B",
        "C#m",
        "A",
        "E",
        "B",
        "C#m",
        "Am",
        "E",
    ]

    verse2 = ["E", "F#m", "C#m", "A", "E", "F#m", "C#m", "A", "E/G#"]

    chorus_b = [
        "E",
        "B",
        "C#m",
        "A",
        "E",
        "B",
        "C#m",
        "A",
    ]

    final_chorus = [
        "F",
        "C",
        "Dm",
        "Bb",
        "F",
        "C",
        "Dm",
        "Dm/C",
    ]

    ending_descent = ["Ab", "Ab/G", "Fm", "Dm7b5", "C"]

    intermediate = {
        "Verse 1": list(verse),
        "Pre-Chorus 1": _pre(),
        "Chorus A": list(chorus_a),
        "Verse 2": list(verse2),
        "Pre-Chorus 2": _pre(),
        "Chorus B": list(chorus_b),
        "Key Change": ["N.C."],
        "Final Chorus": list(final_chorus),
        "Ending Descent": list(ending_descent),
    }

    def _beg(ch: str) -> str:
        if ch == "N.C.":
            return "N.C."
        head = ch.split("/")[0].strip()
        return (
            head.replace("F#m", "F#")
            .replace("C#m", "C#")
            .replace("Dm7b5", "Ddim")
            .replace("m7b5", "dim")
            .replace("m", "")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
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
        "composer": "Lin-Manuel Miranda & Mark Mancina",
        "lyric_cues": {
            "Verse 1": [
                "Moana — intimate storytelling; (breath) on 'I've been staring at the edge'",
                "Piano-led — keep vowels warm, not pushed",
            ],
            "Pre-Chorus 1": [
                "Build — 'I know everybody has a calling' (breath)",
                "B/D# bass walk lifts into chorus",
            ],
            "Chorus A": [
                "Title — 'How far I'll go' (breath) emotional peak",
                "See the line where the sky meets the sea — open vowels",
            ],
            "Verse 2": [
                "Second verse — E/G# color on last bar",
                "Deeper commitment in delivery",
            ],
            "Pre-Chorus 2": ["Stronger arc than Pre-Chorus 1"],
            "Chorus B": ["Chorus lift — fuller strings, same heart"],
            "Key Change": [
                "★ Modulate **E major → F major** — energy step up",
                "(breath) then Final Chorus downbeat",
            ],
            "Final Chorus": [
                "F major — biggest orchestral support",
                "Dm/C bass descent — don't rush the slash",
            ],
            "Ending Descent": [
                "Dramatic Disney resolution — Ab · Ab/G · Fm · Dm7b5 · C",
                "Hold each change; (breath) before final C",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**Disney's Moana** — How Far I'll Go (**E major** → **F major**, "
                "**4/4**, ~84 BPM). Inspirational Disney ballad: preserve "
                "**B/D#**, **E/G#**, **Dm/C**, **Ab/G**, **Dm7b5** and the full "
                "**Ending Descent** (do not simplify). Piano/strings/cinematic "
                "pads — not rock guitar. Verse sparse; pre-chorus build; chorus "
                "wider; key change lifts energy; final chorus + ending = emotional "
                "payoff. Tags: Disney · Musical Theatre · Female Vocal Showcase · "
                "Broadway · Inspirational Ballad · Karaoke Friendly."
            ),
            default_bpm=84,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Disney",
                "Musical Theatre",
                "Female Vocal Showcase",
                "Broadway",
                "Inspirational Ballad",
                "Karaoke Friendly",
            ],
            vocal_showcase=True,
            broadway_disney=True,
            disney_ballad=True,
            modulation={
                "from_key": "E",
                "to_key": "F",
                "section": "Key Change",
            },
            vocal_harmony_hints={
                "Chorus A": "Melody forward — strings pad; save biggest tone for Final Chorus.",
                "Final Chorus": "Brighter vowels in F; let Dm/C bass lead the line down.",
                "Ending Descent": "Storytelling resolution — each slash is a new emotional color.",
            },
            harmonic_analysis={
                "progression_summary": "E major verse/chorus; modulates to F; dramatic ending descent",
                "scale_suggestions": {
                    "E": ["E major", "E major pentatonic"],
                    "F#m": ["F# natural minor"],
                    "C#m": ["C# natural minor"],
                    "A": ["A major"],
                    "F": ["F major"],
                    "Dm": ["D natural minor"],
                },
            },
            backing_character="disney_cinematic",
        ),
    }


def _viva_la_vida_chart_pack() -> dict[str, Any]:
    """Viva La Vida — Coldplay (C guitar-friendly chart · Ab concert, 4/4, ~138 BPM).

    Main loop **C · Dadd11 · G · Em** — preserve **Dadd11** (do not simplify to D
    except beginner charts). Orchestral arena-pop backing — strings ostinato,
    cinematic percussion, not acoustic strumming.
    """

    def _four() -> list[str]:
        return ["C", "Dadd11", "G", "Em"]

    def _chorus_with_bm() -> list[str]:
        return _four() * 3 + ["C", "Dadd11", "Bm", "Em"]

    oh_section = (
        ["C", "Em", "C", "Em", "C", "Em", "Dadd11", "Dadd11"]
        + _four()
        + _four()
    )

    intermediate = {
        "Intro": _four() + _four(),
        "Verse 1": _four() + _four(),
        "Interlude": _four() + _four(),
        "Verse 2": _four() * 4,
        "Chorus 1": _chorus_with_bm(),
        "Interlude 2": _four() + _four(),
        "Verse 3": _four() * 4,
        "Chorus 2": _chorus_with_bm(),
        "Bridge / Oh Section": oh_section,
        "Final Chorus": _chorus_with_bm(),
        "Outro": ["C", "Dadd11", "Bm", "Em"] * 2,
    }

    def _beg_line(chords: list[str]) -> list[str]:
        return [c.replace("Dadd11", "D") for c in chords]

    beginner = {name: _beg_line(chords) for name, chords in intermediate.items()}
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
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
        "composer": "Coldplay",
        "lyric_cues": {
            "Intro": [
                "Strings establish the pulse — (breath) before the vocal enters",
                "Orchestral pop — keep time with the ostinato, not a folk strum",
            ],
            "Verse 1": [
                "I used to rule the world — narrative, restrained drums",
                "Steady string movement under the vocal",
            ],
            "Chorus 1": [
                "Arena lift — fuller percussion and bigger strings",
                "Bm → Em tag at the end — don't rush the handoff",
            ],
            "Bridge / Oh Section": [
                "Dynamic contrast — expansive 'oh' moment",
                "Dadd11 hold bars — let the harmony ring",
            ],
            "Final Chorus": [
                "Biggest arrangement — anthem climax",
                "Open vowels; ride the orchestral build",
            ],
            "Outro": [
                "Resolve with anthem feel — gradual release",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**Viva La Vida** — Coldplay (**Ab major** concert · **C** guitar-friendly "
                "shapes, **4/4**, ~**138 BPM**). Core loop: **C · Dadd11 · G · Em** "
                "(preserve **Dadd11** on intermediate/advanced). **Bm** appears at "
                "chorus/outro tags. Backing: orchestral strings, pizzicato/driving "
                "ostinato, cinematic percussion, bass, light piano, arena drums — "
                "not plain acoustic strumming or jazz reharm. Intro sets pulse; "
                "verses restrained; choruses widen; bridge/oh expands; final chorus "
                "is the climax. Tags: Coldplay · Orchestral Pop · Arena Pop · "
                "Britpop · Karaoke Friendly · Vocal Showcase."
            ),
            default_bpm=138,
            default_groove="Pop groove",
            time_signature="4/4",
            repertoire_tags=[
                "Coldplay",
                "Orchestral Pop",
                "Baroque Pop",
                "Arena Pop",
                "Britpop",
                "Karaoke Friendly",
                "Vocal Showcase",
            ],
            vocal_showcase=True,
            concert_key="Ab",
            guitar_friendly_key="C",
            vocal_harmony_hints={
                "Verse 1": "Storytelling tone — let strings carry momentum; stay inside the pulse.",
                "Chorus 1": "Brighter, declarative — save peak energy for Final Chorus.",
                "Bridge / Oh Section": "Widest dynamic — long vowels on the 'oh' lifts.",
                "Final Chorus": "Full arena delivery — commit to the Bm → Em cadence.",
            },
            harmonic_analysis={
                "progression_summary": "C major loop C–Dadd11–G–Em with Bm color in chorus tags",
                "scale_suggestions": {
                    "C": ["C major", "C major pentatonic"],
                    "Dadd11": ["D mixolydian", "G major"],
                    "G": ["G major"],
                    "Em": ["E natural minor", "G major"],
                    "Bm": ["B natural minor"],
                },
            },
            backing_character="disney_cinematic",
        ),
    }


def _vienna_chart_pack() -> dict[str, Any]:
    """Vienna — Billy Joel (G major, piano ballad, 4/4).

    Capo-3 guitar chart reads in **G**; preserve Joel color tones (**G6**,
    **Faug**, **B9sus**, **Eb7**, **B5/F#**, slash walks). Piano-centric
    arrangement — not guitar-strumming logic.
    """
    intro = [
        "G6",
        "Faug",
        "F7",
        "B7sus4",
        "C/G",
        "Am7b5",
        "Bm7",
        "G",
    ]

    def _verse_a() -> list[str]:
        return ["Em", "G", "D", "F", "C", "G", "A", "B9sus", "B"]

    def _verse_b() -> list[str]:
        return ["Em", "G", "D", "F", "C", "G", "F#m", "B9sus", "B"]

    def _chorus(*, with_b5: bool = False) -> list[str]:
        tail = ["D", "G", "B5/F#"] if with_b5 else ["D", "G"]
        return [
            "C",
            "D",
            "G",
            "D/F#",
            "Em",
            "G/D",
            "C",
            "F#m",
            "B7",
            "Em7",
            "A7",
            "Eb7",
            *tail,
        ]

    instrumental = ["Em", "G", "D", "F", "C", "G", "F#m", "B9sus", "B"]

    outro = ["E7", "A7", "N.C.", "D", "G"]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse_a() + _verse_b(),
        "Chorus 1": _chorus(with_b5=True),
        "Verse 2": _verse_a() + _verse_b(),
        "Chorus 2": _chorus(),
        "Instrumental": list(instrumental),
        "Chorus 3": _chorus(),
        "Final Chorus": _chorus(),
        "Outro": list(outro),
    }

    def _beg(ch: str) -> str:
        if ch == "N.C.":
            return "N.C."
        head = ch.split("/")[0].strip()
        return (
            head.replace("G6", "G")
            .replace("Faug", "F")
            .replace("B7sus4", "B7")
            .replace("B9sus", "B7")
            .replace("Am7b5", "Am")
            .replace("Bm7", "Bm")
            .replace("Em7", "Em")
            .replace("Eb7", "Eb")
            .replace("B5", "B")
            .replace("aug", "")
            .replace("sus4", "")
            .replace("sus", "")
            .replace("m7b5", "dim")
            .replace("maj7", "")
            .replace("m7", "m")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
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
        "composer": "Billy Joel",
        "lyric_cues": {
            "Intro": ["Iconic Joel intro — G6 · Faug · chromatic color"],
            "Verse 1": [
                "Slow down, you crazy child — (breath) storytelling",
                "Intimate piano; let lyrics lead",
            ],
            "Chorus 1": [
                "Vienna waits for you — (breath) emotional lift",
                "Eb7 borrowed color — don't rush the slash walks",
            ],
            "Verse 2": ["Second verse — deepen the narrative"],
            "Instrumental": ["Melodic piano fill — same harmony as verse tail"],
            "Final Chorus": ["Biggest peak — richest voicings, still reflective"],
            "Outro": ["E7 · A7 · N.C. — gradual release into D · G"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**G major** piano ballad (**4/4**, ~63 BPM). Guitar chart "
                "often played with **capo 3** (Em shapes). Preserve Joel "
                "colors: **G6**, **Faug**, **F7**, **B7sus4**, **C/G**, "
                "**Am7b5**, **B9sus**, **D/F#**, **G/D**, **Em7**, **Eb7**, "
                "**B5/F#**. Piano-centric — not rock guitar strumming. Verse "
                "intimate; chorus fuller; instrumental piano fills; final "
                "chorus = emotional peak; outro relaxes. Advanced study: "
                "secondary dominants & modal interchange. Tags: Billy Joel · "
                "Piano Ballad · Singer-Songwriter · Storytelling · Vocal "
                "Showcase."
            ),
            default_bpm=63,
            default_groove="Ballad",
            time_signature="4/4",
            capo_note="Capo 3 (Em-shape chart) · sounding key G major",
            repertoire_tags=[
                "Billy Joel",
                "Piano Ballad",
                "Singer-Songwriter",
                "Storytelling Song",
                "Vocal Showcase",
            ],
            vocal_showcase=True,
            piano_centric=True,
            harmonic_analysis={
                "progression_summary": (
                    "G major with chromatic passing (Faug, Eb7) and "
                    "secondary dominants (A7, E7); slash bass voice-leading"
                ),
                "scale_suggestions": {
                    "G": ["G major", "G mixolydian (passing F7)"],
                    "Em": ["E natural minor", "E dorian (Em7–A7)"],
                    "Eb7": ["Ab major / borrowed bVII color (modal interchange)"],
                    "F#m": ["F# natural minor (ii in G)"],
                },
                "study_topics": [
                    "Secondary dominant analysis",
                    "Modal interchange awareness",
                    "Slash-chord voice leading",
                ],
            },
            backing_character="piano_ballad_joel",
        ),
    }


def _attya_chart_pack() -> dict[str, Any]:
    """All the Things You Are — Jerome Kern (AABA, 36 bars, 4/4).

    Flagship jazz standard: **Ab** opening, modulations through **Db**, **C**,
    **B**, **E**, **G**, return to **C**. One list item = one bar; preserve
    **maj7**, **m7**, **dim7**, and dominant **7** qualities exactly.
    """
    section_a = [
        "Fm7",
        "Bbm7",
        "Eb7",
        "Abmaj7",
        "Dbmaj7",
        "G7",
        "Cmaj7",
        "Cmaj7",
    ]
    section_b = [
        "Fm7",
        "Bbm7",
        "Eb7",
        "Abmaj7",
        "Dbmaj7",
        "Bdim7",
        "Ebm7",
        "Ab7",
    ]
    section_a2 = [
        "Dbm7",
        "Gb7",
        "Bmaj7",
        "Emaj7",
        "Am7",
        "D7",
        "Gmaj7",
        "C7",
    ]
    # Bars 25–36: turnaround in C plus standard 4-bar tag to complete 36-bar form.
    section_c = [
        "Fm7",
        "Dm7",
        "G7",
        "Cmaj7",
        "Am7",
        "Dm7",
        "G7",
        "Cmaj7",
        "Am7",
        "D7",
        "Gmaj7",
        "Cmaj7",
    ]

    intermediate = {
        "A": list(section_a),
        "B": list(section_b),
        "A2": list(section_a2),
        "C": list(section_c),
    }

    def _beg(ch: str) -> str:
        head = ch.split("/")[0].strip()
        return (
            head.replace("maj7", "")
            .replace("m7b5", "dim")
            .replace("dim7", "dim")
            .replace("m7", "m")
            .replace("b5", "")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    scale_hints = {
        "Fm7": ["F Dorian"],
        "Bbm7": ["Bb Dorian"],
        "Eb7": ["Eb Mixolydian"],
        "Abmaj7": ["Ab Ionian"],
        "Dbmaj7": ["Db Lydian"],
        "G7": ["G Mixolydian", "G altered (advanced)"],
        "Cmaj7": ["C Ionian"],
        "Bdim7": ["Whole-half diminished"],
        "Ebm7": ["Eb Dorian"],
        "Ab7": ["Ab Mixolydian"],
        "Dbm7": ["Db Dorian"],
        "Gb7": ["Gb Mixolydian"],
        "Bmaj7": ["B Ionian"],
        "Emaj7": ["E Ionian"],
        "Am7": ["A Dorian"],
        "D7": ["D Mixolydian", "D altered (advanced)"],
        "Gmaj7": ["G Ionian"],
        "Dm7": ["D Dorian"],
        "C7": ["C Mixolydian", "C altered (advanced)"],
    }

    section_order = list(intermediate.keys())
    return {
        "key": "Ab",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Jerome Kern · Oscar Hammerstein II",
        "lyric_cues": {
            "A": ["Ab major — ii–V–I opening (Fm7 · Bbm7 · Eb7 · Abmaj7)"],
            "B": ["Return to Ab; Bdim7 chromatic approach to Ebm7"],
            "A2": ["Modulation chain: Db → B → E → G major areas"],
            "C": ["Final turnaround in C; tag Am7 · D7 · Gmaj7 · Cmaj7"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**AABA** (36 bars, **4/4**). Opens in **Ab major** (~72 BPM "
                "ballad default; **medium swing** or **bossa** in groove "
                "picker). Preserve all qualities: **maj7**, **m7**, **dim7**, "
                "dominant **7** — do not simplify. Section **C** (bars 25–36) "
                "uses the Dm7–G7 turnaround in C plus a 4-bar tag. Flagship "
                "chart for ii–V–I, modulations, and bebop vocabulary. Tags: "
                "Jazz Standard · Essential Repertoire · Improvisation · Bebop."
            ),
            default_bpm=72,
            default_groove="Ballad",
            time_signature="4/4",
            form="AABA (36 bars)",
            repertoire_tags=[
                "Jazz Standard",
                "Essential Repertoire",
                "Improvisation",
                "Bebop",
                "ii-V-I Progressions",
                "Advanced Harmony",
                "Great American Songbook",
            ],
            jazz_standard_flagship=True,
            harmonic_analysis={
                "progression_summary": (
                    "Modulating AABA through Ab, Db, C, B, E, G, and back to C"
                ),
                "key_centers": [
                    {
                        "section": "A (bars 1–8)",
                        "center": "Ab major",
                        "progression": "Fm7 → Bbm7 → Eb7 → Abmaj7 → Dbmaj7 → G7 → Cmaj7",
                    },
                    {
                        "section": "B (bars 9–16)",
                        "center": "Ab major → Eb minor",
                        "progression": "Fm7 → Bbm7 → Eb7 → Abmaj7 → Dbmaj7 → Bdim7 → Ebm7 → Ab7",
                    },
                    {
                        "section": "A2 (bars 17–24)",
                        "center": "B major → E major → G major",
                        "progression": "Dbm7 → Gb7 → Bmaj7 → Emaj7 → Am7 → D7 → Gmaj7 → C7",
                    },
                    {
                        "section": "C (bars 25–36)",
                        "center": "C major",
                        "progression": "Fm7 → Dm7 → G7 → Cmaj7 → Am7 → D7 → Gmaj7 → Cmaj7",
                    },
                ],
                "ii_v_i_groupings": [
                    "Bars 1–3: Fm7–Bbm7–Eb7 (ii–V–I in Ab)",
                    "Bars 5–7: Dbmaj7–G7–Cmaj7 (ii–V–I in C)",
                    "Bars 9–11: Fm7–Bbm7–Eb7 (ii–V–I in Ab)",
                    "Bars 17–18: Dbm7–Gb7 (ii–V in B)",
                    "Bars 21–22: Am7–D7 (ii–V in G)",
                    "Bars 26–27 & 30–31: Dm7–G7 (ii–V in C)",
                    "Bars 33–34: Am7–D7 (ii–V in G)",
                ],
                "guide_tone_notes": (
                    "Follow 3rds/7ths through each ii–V: e.g. Abmaj7 3rd→7th "
                    "voice-leading into Dbmaj7; G7 tritone resolves to Cmaj7."
                ),
                "improvisation_notes": (
                    "Outline guide tones on changes, then use mode per chord "
                    "from scale_suggestions; target chord tones on beats 1 "
                    "and 3 in swing. Reharmonization-friendly on every ii–V."
                ),
                "scale_suggestions": scale_hints,
            },
            jazz_ballad=True,
            backing_character="jazz_standard_flagship",
        ),
    }


def _satin_doll_chart_pack() -> dict[str, Any]:
    """Satin Doll — Duke Ellington / Strayhorn (AABA + turnaround, 4/4).

    **C major** swing standard. Each **ii–V** cell is one bar with in-bar
  splits (``Dm7|G7``). AABA = 32 bars; optional 4-bar **Turnaround** tag.
    """
    def _a_tail(*, hold_c: bool = False) -> list[str]:
        tail = ["Cmaj7", "Cmaj7"] if hold_c else ["Cmaj7|B7", "Bb7|A7"]
        return [
            "Dm7|G7",
            "Dm7|G7",
            "Em7|A7",
            "Em7|A7",
            "Am7|D7",
            "Am7|D7",
            *tail,
        ]

    section_b = [
        "Gm7|C7",
        "Gm7|C7",
        "Fmaj7",
        "Fmaj7",
        "Fm7|Bb7",
        "Em7|A7",
        "Am7|D7",
        "Dm7|G7",
    ]

    turnaround = ["Dm7|G7", "Em7|A7", "Am7|D7", "G7"]

    intermediate = {
        "A": _a_tail(),
        "A2": _a_tail(hold_c=True),
        "B (Bridge)": list(section_b),
        "A3": _a_tail(),
        "Turnaround": list(turnaround),
    }

    def _beg(ch: str) -> str:
        if "|" in ch:
            return "|".join(_beg(p.strip()) for p in ch.split("|") if p.strip())
        head = ch.split("/")[0].strip()
        return head.replace("maj7", "").replace("m7", "m").replace("7", "")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    scale_hints = {
        "Dm7": ["D Dorian"],
        "G7": ["G Mixolydian", "G altered (advanced)"],
        "Em7": ["E Dorian"],
        "A7": ["A Mixolydian", "A altered (advanced)"],
        "Am7": ["A Dorian"],
        "D7": ["D Mixolydian", "D altered (advanced)"],
        "Cmaj7": ["C Ionian"],
        "B7": ["B Mixolydian", "B altered (advanced)"],
        "Bb7": ["Bb Mixolydian"],
        "Gm7": ["G Dorian"],
        "C7": ["C Mixolydian", "C altered (advanced)"],
        "Fmaj7": ["F Ionian", "F Lydian"],
        "Fm7": ["F Dorian"],
    }

    section_order = list(intermediate.keys())
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
        "composer": "Duke Ellington · Billy Strayhorn · Johnny Mercer",
        "lyric_cues": {
            "A": ["Chain of ii–V's in C — Dm7|G7 pickup feel"],
            "A2": ["Second A — hold on Cmaj7 (no chromatic B7/Bb7)"],
            "B (Bridge)": ["Bridge to F — Gm7|C7 · Fmaj7 · Fm7|Bb7"],
            "A3": ["Return of A — same as first A"],
            "Turnaround": ["Tag: Dm7|G7 · Em7|A7 · Am7|D7 · G7 back to top"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C major** AABA swing standard (**4/4**, ~128 BPM medium "
                "swing; **110–130** bossa in groove picker). **32-bar** head "
                "(A–A2–B–A3) plus optional **4-bar turnaround**. Preserve "
                "**m7**, **maj7**, and dominant **7** — use **Dm7|G7** "
                "half-bar splits for each ii–V bar. Core jazz repertoire "
                "alongside Autumn Leaves, ATTYA, Blue Bossa. Piano: shell "
                "voicings on 2 and 4; guitar: Freddie Green-style comp; bass: "
                "walking quarter notes in swing. Tags: Jazz Standard · Swing · "
                "Duke Ellington · Big Band · ii-V-I · Essential Standards."
            ),
            default_bpm=128,
            default_groove="Jazz swing",
            time_signature="4/4",
            form="AABA (32 bars) + Turnaround (4 bars)",
            repertoire_tags=[
                "Jazz Standard",
                "Swing",
                "Duke Ellington",
                "Big Band",
                "Jazz Repertoire",
                "ii-V-I Progressions",
                "Improvisation",
                "Essential Standards",
            ],
            jazz_standard_flagship=True,
            harmonic_analysis={
                "progression_summary": "Chain of ii–V progressions in C and brief F major bridge",
                "key_centers": [
                    {
                        "section": "A / A3",
                        "center": "C major",
                        "progression": "Dm7|G7 · Em7|A7 · Am7|D7 · Cmaj7|B7|Bb7|A7",
                    },
                    {
                        "section": "A2",
                        "center": "C major",
                        "progression": "Same chain; resolves to Cmaj7",
                    },
                    {
                        "section": "B (Bridge)",
                        "center": "F major",
                        "progression": "Gm7|C7 · Fmaj7 · Fm7|Bb7 · return to C via ii–V chain",
                    },
                ],
                "ii_v_i_groupings": [
                    "Dm7|G7 (ii–V in C)",
                    "Em7|A7 (ii–V in D / secondary)",
                    "Am7|D7 (ii–V in G / secondary)",
                    "Gm7|C7 (ii–V in F)",
                    "Fm7|Bb7 (ii–V in Eb)",
                    "Turnaround: Dm7|G7 · Em7|A7 · Am7|D7 · G7",
                ],
                "guide_tone_notes": (
                    "Connect 3rds and 7ths across each ii–V: e.g. Dm7 (F,C) → G7 (B,F) "
                    "→ Cmaj7; keep guide tones on beats 1 and 3 when walking or comping."
                ),
                "improvisation_notes": (
                    "Use Dorian on minors, Mixolydian or altered on dominants; "
                    "target chord tones through each ii–V in swing eighths."
                ),
                "comping_notes": {
                    "Piano": "Shell voicings (rootless 3–7) on beats 2 and 4; Charleston rhythm optional.",
                    "Guitar": "Muted quarter-note Freddie Green comp; highlight ii–V pairs.",
                    "Bass": "Walking quarters: root–chord tone–scale–approach on each bar.",
                },
                "scale_suggestions": scale_hints,
            },
            jazz_ballad=False,
            backing_character="jazz_swing_standard",
        ),
    }


def _wave_chart_pack() -> dict[str, Any]:
    """Wave — Antônio Carlos Jobim (D major, bossa nova, 4/4).

    Full Jobim form with **Dm7 · G13** intro/outro turnaround, three verses,
    two bridge passes, instrumental solo section, and gentle fade. Preserve
    **Dmaj9**, **Bbdim7**, **D7b9**, **Gm6**, **F#7**, **B7b9**, **G13**,
    **Am6**, **Ab6**, **Bb7b9**, and **A7#5** — do not simplify.
    """
    intro_outro = ["Dm7", "G13"] * 4

    verse = [
        "Dmaj9",
        "Bbdim7",
        "Am7",
        "D7b9",
        "Gmaj7",
        "Gm6",
        "F#7",
        "B7b9",
        "Bm7",
        "E7",
        "Bb7",
        "A7",
        "Dm7",
        "G7",
        "Dm7",
        "G7",
    ]

    bridge = [
        "Gm7",
        "C7",
        "Am7",
        "Am6",
        "Ab6",
        "Bb7b9",
        "Gm7",
        "A7#5",
    ]

    instrumental = [
        "Dmaj7",
        "Bbdim7",
        "Am7",
        "D7b9",
        "Gmaj7",
        "Gm6",
        "F#7",
        "B7b9",
        "Bm7",
        "E7",
        "Bb7",
        "A7",
        "Dm7",
        "G7",
        "Dm7",
        "G13",
    ]

    intermediate = {
        "Intro": list(intro_outro),
        "Verse 1": list(verse),
        "Verse 2": list(verse),
        "Bridge": list(bridge),
        "Verse 3": list(verse),
        "Instrumental": list(instrumental),
        "Bridge 2": list(bridge),
        "Final Verse": list(verse),
        "Outro": list(intro_outro),
    }

    def _beg(ch: str) -> str:
        head = ch.split("/")[0].strip()
        return (
            head.replace("maj9", "")
            .replace("maj7", "")
            .replace("dim7", "dim")
            .replace("m7", "m")
            .replace("m6", "m")
            .replace("b9", "")
            .replace("b5", "")
            .replace("#5", "")
            .replace("13", "7")
            .replace("6", "")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    scale_hints = {
        "Dm7": ["D Dorian"],
        "G13": ["G Mixolydian"],
        "Dmaj9": ["D Ionian", "D Lydian"],
        "Dmaj7": ["D Ionian", "D Lydian"],
        "Bbdim7": ["Whole-Half Diminished"],
        "Am7": ["A Dorian"],
        "D7b9": ["D Half-Whole Diminished", "D Altered"],
        "Gmaj7": ["G Ionian", "G Lydian"],
        "Gm6": ["G Melodic Minor"],
        "F#7": ["F# Mixolydian", "F# Altered"],
        "B7b9": ["B Phrygian Dominant", "B Half-Whole Diminished"],
        "Bm7": ["B Dorian"],
        "E7": ["E Mixolydian"],
        "Bb7": ["Bb Mixolydian"],
        "A7": ["A Mixolydian", "A Altered"],
        "A7#5": ["A Whole Tone", "A Altered"],
        "Gm7": ["G Dorian"],
        "C7": ["C Mixolydian", "C Altered"],
        "Am6": ["A Dorian", "A Melodic Minor"],
        "Ab6": ["Ab Lydian", "Ab Ionian"],
        "Bb7b9": ["Bb Phrygian Dominant", "Bb Half-Whole Diminished"],
        "G7": ["G Mixolydian", "G Altered"],
    }

    section_order = list(intermediate.keys())
    return {
        "key": "D",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Antônio Carlos Jobim",
        "lyric_cues": {
            "Intro": ["Bossa turnaround — Dm7 · G13 vamp (nylon guitar + brushes)"],
            "Verse 1": ["So close your eyes for that's a lovely way to be…"],
            "Verse 2": ["Second verse — same harmonic story, fuller bass movement"],
            "Bridge": ["Richer harmony — Am6 · Ab6 · Bb7b9 tension"],
            "Verse 3": ["Third verse before instrumental"],
            "Instrumental": ["Solo section — ideal for jazz improvisation over the form"],
            "Bridge 2": ["Second bridge — A7#5 lift back toward D"],
            "Final Verse": ["Last vocal pass — gentle dynamic peak"],
            "Outro": ["Dm7 · G13 fade — classic bossa ending"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D major** bossa nova standard (**4/4**, ~120 BPM bossa default; "
                "**Ballad** or **Jazz swing** in groove picker for alternate feel). "
                "Authentic Jobim production: nylon-string guitar, acoustic bass, "
                "brushes, light percussion, piano, soft strings — **not** rock drums "
                "or heavy strumming. Verse: light bossa groove; bridge: richer "
                "harmony and tension; instrumental: solo-friendly; outro: gentle "
                "fade on **Dm7 · G13**. Preserve all listed chord colors exactly. "
                "Core Brazilian jazz repertoire alongside Girl from Ipanema, "
                "Corcovado, One Note Samba, Desafinado."
            ),
            default_bpm=120,
            default_groove="Bossa nova",
            time_signature="4/4",
            form="Intro · Verse ×3 · Bridge ×2 · Instrumental · Outro",
            repertoire_tags=[
                "Jazz Standard",
                "Bossa Nova",
                "Antônio Carlos Jobim",
                "Brazilian Jazz",
                "Advanced Harmony",
                "Improvisation",
                "Essential Repertoire",
            ],
            jazz_standard_flagship=True,
            harmonic_analysis={
                "progression_summary": (
                    "D major bossa with chromatic diminished approach, "
                    "Gm6/F#7 color, and Dm7–G13 turnaround bookends"
                ),
                "key_centers": [
                    {
                        "section": "Intro / Outro",
                        "center": "D major (turnaround)",
                        "progression": "Dm7 → G13 (ii–V in D)",
                    },
                    {
                        "section": "Verse",
                        "center": "D major → G major",
                        "progression": (
                            "Dmaj9 → Bbdim7 → Am7 → D7b9 → Gmaj7 → Gm6 → F#7 → "
                            "B7b9 → Bm7 → E7 → Bb7 → A7 → Dm7 → G7"
                        ),
                    },
                    {
                        "section": "Bridge",
                        "center": "F / D major approach",
                        "progression": "Gm7 → C7 → Am7 → Am6 → Ab6 → Bb7b9 → Gm7 → A7#5",
                    },
                    {
                        "section": "Instrumental",
                        "center": "D major (solo form)",
                        "progression": "Same verse changes; ends on G13 pickup to outro",
                    },
                ],
                "ii_v_i_groupings": [
                    "Intro/Outro: Dm7 → G13 (ii–V in D)",
                    "Verse bars 3–4: Am7 → D7b9 → Gmaj7 (ii–V–I in G)",
                    "Verse bars 13–14: Dm7 → G7 (ii–V in D)",
                    "Bridge bars 1–2: Gm7 → C7 (ii–V in F)",
                    "Bridge bars 7–8: Gm7 → A7#5 (ii–V toward D)",
                ],
                "substitute_dominants": [
                    "D7b9: altered dominant resolving to Gmaj7",
                    "Bb7: tritone-sub color approaching A7 / D area",
                    "B7b9: Phrygian-dominant tension before Bm7",
                    "A7#5: altered dominant with #5 color into final verse/outro",
                    "G13: extended dominant in turnaround and instrumental tag",
                ],
                "guide_tone_notes": (
                    "Follow 3rds and 7ths through each Jobim change — e.g. "
                    "Am7 (C,G) → D7b9 (F#,C) → Gmaj7 (B,F#); keep voice-leading "
                    "smooth on nylon comp and walking bass."
                ),
                "improvisation_notes": (
                    "Instrumental section is the primary solo canvas — outline "
                    "guide tones, then use scale_suggestions per chord. Bossa "
                    "eighths stay relaxed; save peak intensity for bridge A7#5 "
                    "and final verse. Section-focus practice loops any verse or "
                    "bridge for isolated improvisation work."
                ),
                "comping_notes": {
                    "Guitar": "Nylon-string bossa comp — thumb bass notes, finger syncopation.",
                    "Piano": "Shell voicings and rootless clusters; light left-hand bass.",
                    "Bass": "Acoustic walking/quarter-note movement — light in verse, fuller in bridge.",
                },
                "scale_suggestions": scale_hints,
            },
            jazz_ballad=True,
            backing_character="bossa_nova_jobim",
        ),
    }


def _iris_chart_pack() -> dict[str, Any]:
    """Iris — Goo Goo Dolls (B minor, alt-rock ballad, 4/4).

    Soaring 90s pop-rock ballad with gradual build. Preserve **Bsus2**,
    **Gmaj7**, **Bm/A**, **F#m**; one list item = one bar.
    """
    intro = ["Bm", "Bsus2", "G", "Gmaj7", "G"]

    def _verse() -> list[str]:
        return ["D", "Em", "G", "Bm", "A", "G"] * 2

    chorus = ["Bm", "A", "G"] * 4

    instrumental_head = (
        ["Bm", "Bm/A", "D", "D", "Bm", "Bm/A", "G", "G"] * 2
        + ["Bm", "Bsus2", "G", "G"] * 3
        + ["Bm", "Bsus2"]
    )

    build = (
        ["G", "F#m", "G", "Bm"]
        + ["G", "F#m", "Bm", "Bm"]
        + ["G", "F#m", "Bm", "Bm"]
    )

    ending_build = ["Bm", "Bm/A", "G", "G"] * 4

    outro = ["Bm", "A", "G"] * 2 + ["Bm", "A", "Bm"]

    coda = ["Bm", "Bm/A", "G", "G"] * 4

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse(),
        "Verse 2": _verse(),
        "Chorus 1": list(chorus),
        "Interlude": list(intro),
        "Verse 3": _verse(),
        "Chorus 2": list(chorus),
        "Instrumental": list(instrumental_head),
        "Build": list(build),
        "Ending Build": list(ending_build),
        "Final Chorus": list(chorus) * 2,
        "Outro": list(outro),
        "Coda": list(coda),
    }

    def _beg(ch: str) -> str:
        head = ch.split("/")[0].strip()
        return (
            head.replace("Bsus2", "Bm")
            .replace("Gmaj7", "G")
            .replace("F#m", "F#")
            .replace("m7", "m")
            .replace("sus2", "")
            .replace("maj7", "")
        )

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
    scale_hints = {
        "Bm": ["B natural minor", "B minor pentatonic"],
        "A": ["A major"],
        "G": ["G major"],
        "Em": ["E natural minor"],
        "D": ["D major"],
        "F#m": ["F# Dorian", "F# natural minor"],
    }
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
        "composer": "John Rzeznik",
        "lyric_cues": {
            "Intro": ["Atmospheric Bm · Bsus2 · G — (breath) before vocal"],
            "Verse 1": ["And I'd give up forever… — intimate, conversational"],
            "Chorus 1": ["I don't want the world to see me — (breath) open vowels"],
            "Interlude": ["Guitar interlude — same as intro colors"],
            "Instrumental": ["Dynamic lift — Bm/A slash bass movement"],
            "Build": ["F#m color — push energy toward climax"],
            "Final Chorus": ["Fullest arrangement — repeat for impact"],
            "Outro": ["And I just want you to know who I am — release"],
            "Coda": ["Fade on Bm/A · G vamp"],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**B minor** alt-rock ballad (**4/4**, ~154 BPM). **Not** "
                "piano-ballad or jazz comping — layered acoustic/electric "
                "guitars, pads, rock drums, melodic bass. Preserve **Bsus2**, "
                "**Gmaj7**, **Bm/A**, **F#m**. Verse: lighter acoustic; chorus: "
                "bigger drums/guitars; instrumental/build: gradual emotional "
                "swell; final chorus: peak. Karaoke-friendly vocal showcase."
            ),
            default_bpm=154,
            default_groove="Rock groove",
            time_signature="4/4",
            repertoire_tags=[
                "90s Rock",
                "Alternative Rock",
                "Pop Rock Ballad",
                "Vocal Showcase",
                "Acoustic Rock",
            ],
            vocal_showcase=True,
            vocal_range_notes=(
                "Melody mostly mid–high chest in verses; chorus soars to "
                "head-mix on 'I don't want the world to see me'. Plan breaths "
                "before each chorus entrance and the final chorus repeat."
            ),
            harmonic_analysis={
                "progression_summary": "Bm-centric with G major and D major verse color",
                "scale_suggestions": scale_hints,
            },
            alt_rock_ballad=True,
            backing_character="alt_rock_ballad",
        ),
    }


def _shalom_aleichem_chart_pack() -> dict[str, Any]:
    """Shalom Aleichem — Traditional Jewish Sabbath Song (Dm, 4/4).

    Warm Friday-night Shabbat welcome; one list item = one bar.
    Simple Dm · Gm · A · F · C harmony — no jazz reharmonization.
    """
    def _verse_full() -> list[str]:
        return (
            ["Dm", "A", "Dm", "A"]
            + ["Dm", "A", "Gm", "A"]
            + ["Dm", "F", "C", "Dm", "A"]
            + ["Gm", "A", "Dm", "A", "Dm"]
        )

    def _verse_short() -> list[str]:
        return ["Dm", "A", "Dm", "A"] + ["Dm", "A", "Gm", "A"]

    instrumental = [
        "Dm",
        "F",
        "C",
        "C",
        "Dm",
        "Dm",
        "A",
        "A",
        "Gm",
        "Gm",
        "A",
        "Dm",
        "Dm",
        "A",
        "Dm",
        "Dm",
    ]

    intermediate = {
        "Verse 1": _verse_full(),
        "Verse 2": _verse_full(),
        "Verse 3": _verse_short(),
        "Instrumental": instrumental,
        "Verse 4": _verse_full(),
        "Outro": ["Dm", "A", "Dm"],
    }
    beginner = {name: list(chords) for name, chords in intermediate.items()}
    advanced = {name: list(chords) for name, chords in intermediate.items()}
    section_order = list(intermediate.keys())

    hebrew_lyrics = {
        "Verse 1": "שלום עליכם מלאכי השלום",
        "Verse 2": "באוכם לשלום מלאכי השלום",
        "Verse 3": "ברכוני לשלום מלאכי השלום",
        "Verse 4": "צאתכם לשלום מלאכי השלום",
    }
    transliteration = {
        "Verse 1": "Shalom aleichem, mal'achei hashalom",
        "Verse 2": "Bo'achem leshalom, mal'achei hashalom",
        "Verse 3": "Barchuni leshalom, mal'achei hashalom",
        "Verse 4": "Tzeitchem leshalom, mal'achei hashalom",
    }
    scale_hints = {
        "Dm": ["D natural minor", "D minor pentatonic"],
        "Gm": ["G natural minor"],
        "A": ["A major", "A Mixolydian"],
        "F": ["F major"],
        "C": ["C major"],
    }

    return {
        "key": "Dm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "guitar_tabs": {
            "Dm": "xx0231",
            "Gm": "355333",
            "A": "x02220",
            "F": "133211",
            "C": "x32010",
        },
        "lyric_cues": {
            "Verse 1": [
                "Shalom aleichem — soft congregational welcome",
                "breath before each four-bar phrase",
            ],
            "Verse 2": [
                "Bo'achem leshalom — answer phrase, same warmth",
                "keep vowels open and unhurried",
            ],
            "Verse 3": [
                "Barchuni leshalom — shorter verse before interlude",
                "gentle lift into instrumental",
            ],
            "Instrumental": [
                "simple melodic interlude — let the Dm cadence breathe",
                "strings / clarinet color optional",
            ],
            "Verse 4": [
                "Tzeitchem leshalom — slightly fuller than earlier verses",
                "farewell blessing tone",
            ],
            "Outro": [
                "gentle cadence on Dm — let the final minor chord ring",
                "Shabbat-table hush on the last Dm",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D minor** Shabbat welcome (**4/4**, slow congregational pulse). "
                "Warm Friday-night table or synagogue singalong — acoustic guitar, "
                "piano, strings pad, light percussion; optional clarinet and violin. "
                "**Not** heavy drums, rock guitar, jazz reharmonization, or pop "
                "production. Verse: soft accompaniment; instrumental: simple "
                "melodic interlude; Verse 4: slightly fuller; outro: gentle Dm cadence."
            ),
            default_bpm=72,
            default_groove="Jewish ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Jewish",
                "Shabbat",
                "Hebrew",
                "Traditional",
                "Congregational",
                "Family Singing",
            ],
            hebrew_lyrics=hebrew_lyrics,
            transliteration=transliteration,
            jewish_traditional=True,
            backing_character="jewish_traditional_congregational",
            harmonic_analysis={
                "progression_summary": "Dm-centered Shabbat welcome — Gm subdominant, A major dominant",
                "scale_suggestions": scale_hints,
            },
        ),
    }


def _all_of_me_chart_pack() -> dict[str, Any]:
    """All of Me — John Legend (Em capo chart, piano ballad, 4/4).

    Contemporary wedding/love ballad. Preserve **C/D** (do not replace with plain D);
  one list item = one bar.
    """
    intro = ["Em", "C", "G", "D"] * 2

    def _verse() -> list[str]:
        return (
            ["Em", "C", "G", "D"] * 2
            + ["Em", "C", "G", "D", "Em"]
            + ["C", "G", "D", "Am"]
        )

    def _pre_chorus() -> list[str]:
        return ["Am", "G", "D", "Am", "Am", "G", "D"]

    def _chorus_core() -> list[str]:
        return ["G", "Em", "Am", "C/D", "D", "G", "Em", "Am", "C/D", "D"]

    def _chorus() -> list[str]:
        return _chorus_core() + ["Em", "C", "G", "D"] * 2

    bridge = ["Am", "Am", "G", "D", "Am", "Am", "G", "D"]

    final_chorus = _chorus_core() + ["Em", "C", "G", "D"] * 4

    outro = ["Em", "C", "G", "D"] * 4

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse(),
        "Pre-Chorus": _pre_chorus(),
        "Chorus 1": _chorus(),
        "Verse 2": _verse(),
        "Pre-Chorus 2": _pre_chorus(),
        "Chorus 2": _chorus(),
        "Bridge": list(bridge),
        "Final Chorus": list(final_chorus),
        "Outro": list(outro),
    }

    def _beg(ch: str) -> str:
        head = ch.split("/")[0].strip()
        if ch == "C/D":
            return "C/D"
        return head.replace("maj7", "").replace("m7", "m")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }

    def _adv(ch: str) -> str:
        if ch == "C/D":
            return "C/D"
        return {
            "Em": "Em7",
            "C": "Cmaj7",
            "G": "Gmaj7",
            "D": "Dmaj7",
            "Am": "Am7",
        }.get(ch, ch)

    advanced = {name: [_adv(c) for c in chords] for name, chords in intermediate.items()}
    section_order = list(intermediate.keys())
    scale_hints = {
        "Em": ["E natural minor", "E minor pentatonic"],
        "C": ["C major"],
        "G": ["G major"],
        "D": ["D major"],
        "Am": ["A natural minor"],
    }

    return {
        "key": "Em",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "John Legend & Toby Gad",
        "guitar_tabs": {
            "Em": "022000",
            "C": "x32010",
            "G": "320003",
            "D": "xx0232",
            "Am": "x02210",
            "C/D": "x3023x",
        },
        "lyric_cues": {
            "Intro": ["Piano vamp — (breath) before 'What would I do without your smart mouth'"],
            "Verse 1": [
                "Intimate verse — (breath) conversational tone",
                "Smart mouth / crazy — light, playful delivery",
                "Land Am color on last line before pre-chorus",
            ],
            "Pre-Chorus": [
                "Gentle build — (breath) before chorus lift",
                "Love your curves and all your edges — open vowels",
            ],
            "Chorus 1": [
                "'Cause all of me loves all of you — (breath) title hook",
                "Preserve **C/D** → D resolution — don't rush the dominant",
                "Fuller piano + bass — wedding-song declaration",
            ],
            "Verse 2": ["Second verse — same breath map; deepen intimacy"],
            "Pre-Chorus 2": ["Build again — save energy for bridge lift"],
            "Chorus 2": ["Repeat chorus energy — blend on sustained vowels"],
            "Bridge": [
                "Emotional lift — (breath) 'How many times do I have to tell you'",
                "Strongest story moment before final chorus",
            ],
            "Final Chorus": [
                "Biggest dynamic peak — fullest piano and vocal support",
                "Extra Em–C–G–D passes — sustain through the climax",
            ],
            "Outro": [
                "Vamp Em–C–G–D — gradually release; let final Em ring",
                "(breath) between passes as instrumentation thins",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**E minor** capo guitar chart (**4/4**, ~126 BPM). Original "
                "recordings vary in sounding key — this chart follows the common "
                "**Em-shape** arrangement. **Piano-led** love ballad: preserve "
                "**C/D** (suspended dominant — do not simplify to plain D). "
                "Verse intimate; pre-chorus gentle build; chorus fuller piano/"
                "bass; bridge emotional lift; final chorus = peak; outro fades. "
                "**Not** rock drums or distorted guitar. Core vocal-showcase "
                "wedding repertoire."
            ),
            default_bpm=126,
            default_groove="Ballad",
            time_signature="4/4",
            capo_note=(
                "Em-shape capo chart · sounding key varies by vocalist; "
                "studio take often sits higher than this shape"
            ),
            repertoire_tags=[
                "Wedding Song",
                "Love Song",
                "Piano Ballad",
                "Vocal Showcase",
                "Contemporary Pop",
                "Karaoke Friendly",
            ],
            vocal_showcase=True,
            piano_centric=True,
            vocal_range_notes=(
                "Verse sits in comfortable mid chest; pre-chorus and chorus "
                "ask for mixed voice on sustained vowels ('all of me'). Plan "
                "breaths before each chorus and the bridge; final chorus is the "
                "highest sustained belt — warm up the top mix beforehand."
            ),
            vocal_harmony_hints=(
                "Piano ballad: let the lyric lead; soften consonants in verses "
                "and open the chorus on 'all of me'. C/D → D is the emotional "
                "punctuation — don't clip the dominant."
            ),
            harmonic_analysis={
                "progression_summary": "Em-centric pop ballad with Am pre-chorus and C/D dominant color",
                "scale_suggestions": scale_hints,
            },
            backing_character="piano_vocal_ballad_wedding",
        ),
    }


def _love_story_chart_pack() -> dict[str, Any]:
    """Love Story — Taylor Swift (C guitar shapes / capo 2, D concert, 4/4).

    Country-pop ballad built on **C · G · Am · F** with a signature whole-step
    key change to **D · A · Bm · G** at the final chorus. One list item = one bar.
    Preserve **Am**, **Bm**, **F**, and **G** exactly.
    """
    intro = ["C", "G", "Am", "F"]

    verse_1 = ["C", "F", "Am", "F", "C", "F", "Am", "G"]
    verse_2 = ["C", "F", "Am", "G"]

    def _pre_chorus() -> list[str]:
        return ["F", "G", "Am", "C", "F", "G", "Am", "F", "G"]

    chorus = ["C", "G", "Am", "F", "G", "C"]
    chorus_2 = ["C", "G", "Am", "F", "G", "C", "G", "Am", "F", "G"]

    solo = ["C", "C", "G", "G", "Am", "Am", "F", "G"]
    bridge = ["Am", "F", "C", "G", "Am", "F", "C", "G"]

    final_chorus = ["D", "A", "Bm", "G", "A", "D"]
    outro = ["A", "Bm", "G", "D"]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": list(verse_1),
        "Pre-Chorus": _pre_chorus(),
        "Chorus": list(chorus),
        "Verse 2": list(verse_2),
        "Pre-Chorus 2": _pre_chorus(),
        "Chorus 2": list(chorus_2),
        "Solo": list(solo),
        "Bridge": list(bridge),
        "Final Chorus (Key Change)": list(final_chorus),
        "Outro": list(outro),
    }

    beginner = {name: list(chords) for name, chords in intermediate.items()}

    def _adv(ch: str) -> str:
        if ch in {"Am", "Bm", "F", "G"}:
            return ch
        return {"C": "Cadd9", "D": "Dadd9", "A": "Asus2"}.get(ch, ch)

    advanced = {
        name: [_adv(c) for c in chords]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "C": ["C Major", "C Major Pentatonic"],
        "G": ["G Major"],
        "Am": ["A Natural Minor", "A Minor Pentatonic"],
        "F": ["F Major"],
        "D": ["D Major"],
        "A": ["A Major"],
        "Bm": ["B Natural Minor"],
    }

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
        "composer": "Taylor Swift",
        "guitar_tabs": {
            "C": "x32010",
            "G": "320003",
            "Am": "x02210",
            "F": "133211",
            "D": "xx0232",
            "A": "x02220",
            "Bm": "x24432",
        },
        "lyric_cues": {
            "Intro": [
                "Acoustic storybook pickup — (breath) before 'We were both young…'",
                "C · G · Am · F sets the fairytale frame",
            ],
            "Verse 1": [
                "Intimate verse — conversational, light country-pop tone",
                "(breath) after long lines; let the guitar carry the rhythm",
            ],
            "Pre-Chorus": [
                "Gradual build — (breath) before 'That you were Romeo…'",
                "Tension climbs on F · G · Am · C",
            ],
            "Chorus": [
                "Title hook — 'Love Story' — open vowels, fuller drums enter",
                "(breath) before 'Romeo take me somewhere we can be alone'",
                "Land the F · G · C tag cleanly",
            ],
            "Verse 2": [
                "Shorter second verse — stay intimate, don't rush to pre-chorus",
            ],
            "Pre-Chorus 2": [
                "Same lift as first pre-chorus — save energy for double chorus",
            ],
            "Chorus 2": [
                "Double chorus pass — stronger bass and wider arrangement",
                "Second half repeats the hook with full band energy",
            ],
            "Solo": [
                "Fiddle/guitar solo section — support improvisation over C · G · Am · F",
            ],
            "Bridge": [
                "Emotional lift — (breath) 'Marry me, Juliet…'",
                "Quiet plea before the famous key change",
            ],
            "Final Chorus (Key Change)": [
                "Whole-step lift C → D — biggest energy of the song",
                "(breath) then commit to the brighter D · A · Bm · G hook",
                "Open up tone for the proposal moment",
            ],
            "Outro": [
                "Warm fade — reduce instrumentation on A · Bm · G · D",
                "Let the final D ring; soft ending",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D major** concert; chart in **C shapes** (capo **2**). **4/4**, "
                "~119 BPM country-pop / acoustic ballad. Core loop **C · G · Am · F** "
                "with pre-chorus build and double chorus before solo/bridge. "
                "Signature **modulation to D · A · Bm · G** at the final chorus — "
                "do not flatten the key change. Backing: acoustic guitar, light "
                "drums, bass, optional fiddle, piano support — **not** rock/EDM/jazz "
                "reharm. Verse intimate; pre-chorus builds; chorus fullest; bridge "
                "lifts; final chorus = peak; outro thins warmly. Core beginner "
                "vocal-showcase repertoire alongside All of Me, Shallow, Friend in Me."
            ),
            default_bpm=119,
            default_groove="Ballad",
            time_signature="4/4",
            capo_note="Capo 2 (C-shape chart) · concert key D major",
            repertoire_tags=[
                "Taylor Swift",
                "Country Pop",
                "Pop Ballad",
                "Love Song",
                "Karaoke Friendly",
                "Vocal Showcase",
                "Beginner Friendly",
            ],
            vocal_showcase=True,
            modulation={
                "from_key": "C",
                "to_key": "D",
                "section": "Final Chorus (Key Change)",
            },
            vocal_range_notes=(
                "Verse and pre-chorus sit in comfortable chest/mix; chorus opens "
                "slightly. Plan breaths before each chorus and the bridge plea. "
                "Final chorus (key change up a whole step) is the highest sustained "
                "moment — warm up mix voice before the D-major lift."
            ),
            vocal_harmony_hints=(
                "Country-pop storytelling: soften consonants in verses, open the "
                "title hook on 'Love Story', and breathe before the pre-chorus "
                "lift. The C → D key change is the emotional peak — brighten tone "
                "and don't rush the Bm · G landing."
            ),
            harmonic_analysis={
                "progression_summary": "I–V–vi–IV in C; whole-step modulation to D for final chorus",
                "key_centers": [
                    {
                        "section": "Intro through Bridge",
                        "center": "C major",
                        "progression": "C · G · Am · F with pre-chorus F · G · Am · C",
                    },
                    {
                        "section": "Final Chorus / Outro",
                        "center": "D major",
                        "progression": "D · A · Bm · G · A · D (modulation up whole step)",
                    },
                ],
                "improvisation_notes": (
                    "Solo section repeats C · G · Am · F pairs — use major pentatonic "
                    "on C and A minor pentatonic on Am for beginner-friendly fills."
                ),
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="country_pop_acoustic_vocal",
        ),
    }


def _imagine_chart_pack() -> dict[str, Any]:
    """Imagine — John Lennon (C major, piano ballad, 4/4).

    Piano-centric ballad with **C · Cmaj7 · F** verses, descending-bass
    bridges (**Am/E · Dm7 · F/C · C/G**), and anthem chorus with **E7**.
    Preserve all slash chords and color tones exactly.
    """
    intro = ["C", "Cmaj7", "F", "C", "Cmaj7", "F"]

    def _verse() -> list[str]:
        return ["C", "Cmaj7", "F"] * 4

    def _bridge() -> list[str]:
        return ["F", "Am/E", "Dm7", "F/C", "G", "C/G", "G7"]

    def _chorus() -> list[str]:
        return (
            ["F", "G"]
            + ["C", "Cmaj7", "E", "E7"]
            + ["F", "G"]
            + ["C", "Cmaj7", "E", "E7"]
            + ["F", "G"]
            + ["C", "Cmaj7", "E", "E7"]
            + ["F", "G"]
            + ["C"]
        )

    outro = ["C", "Cmaj7", "F", "C"]

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse(),
        "Bridge 1": _bridge(),
        "Verse 2": _verse(),
        "Bridge 2": _bridge(),
        "Chorus": _chorus(),
        "Verse 3": _verse(),
        "Bridge 3": _bridge(),
        "Final Chorus": _chorus(),
        "Outro": list(outro),
    }

    _preserve = {"Cmaj7", "Am/E", "Dm7", "F/C", "C/G", "G7", "E7"}

    def _beg(ch: str) -> str:
        if ch in _preserve or "/" in ch:
            return ch
        return ch.replace("maj7", "").replace("m7", "m")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }

    def _adv(ch: str) -> str:
        if ch in _preserve or "/" in ch or ch in {"E", "F", "G"}:
            return ch
        if ch == "C":
            return "Cadd9"
        return ch

    advanced = {
        name: [_adv(c) for c in chords]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "C": ["C Major", "C Major Pentatonic"],
        "Cmaj7": ["C Ionian", "C Lydian"],
        "Cadd9": ["C Major", "C Major Pentatonic"],
        "F": ["F Major"],
        "G": ["G Mixolydian"],
        "Am/E": ["A Natural Minor"],
        "Dm7": ["D Dorian"],
        "F/C": ["F Major"],
        "C/G": ["C Major"],
        "G7": ["G Mixolydian", "G Altered (advanced)"],
        "E": ["E Mixolydian"],
        "E7": ["E Mixolydian", "E Altered (advanced)"],
    }

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
        "composer": "John Lennon",
        "guitar_tabs": {
            "C": "x32010",
            "Cadd9": "x32030",
            "Cmaj7": "x32000",
            "F": "133211",
            "G": "320003",
            "Am/E": "002210",
            "Dm7": "xx0211",
            "F/C": "x33211",
            "C/G": "332010",
            "G7": "320001",
            "E": "022100",
            "E7": "020100",
        },
        "lyric_cues": {
            "Intro": [
                "Intimate piano — (breath) before 'Imagine there's no heaven…'",
                "C · Cmaj7 · F sets the reflective tone",
            ],
            "Verse 1": [
                "Sparse verse — let each C · Cmaj7 · F cell breathe",
                "(breath) between phrases; conversational delivery",
            ],
            "Bridge 1": [
                "Gradual build — follow descending bass F → Am/E → Dm7 → F/C",
                "Land C/G · G7 turnaround cleanly",
            ],
            "Verse 2": ["Second verse — same intimate pacing as Verse 1"],
            "Bridge 2": ["Second bridge lift — slightly fuller than Bridge 1"],
            "Chorus": [
                "'Imagine all the people…' — open vowels, gentle dynamic lift",
                "(breath) before each F · G pickup",
                "E · E7 color is the emotional punctuation — don't rush it",
            ],
            "Verse 3": ["Third verse — stay intimate before final bridge"],
            "Bridge 3": ["Last bridge — build toward richest final chorus"],
            "Final Chorus": [
                "Emotional peak — widest arrangement, warmest vocal tone",
                "Same harmony as chorus; save your fullest sound here",
            ],
            "Outro": [
                "Reduce instrumentation — let final C ring",
                "Gentle fade on C · Cmaj7 · F · C",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C major** piano ballad (**4/4**, ~76 BPM). **Piano-led** "
                "singer-songwriter arrangement — intimate verses on **C · Cmaj7 · F**, "
                "bridges with descending bass (**Am/E · Dm7 · F/C · C/G · G7**), "
                "chorus lift on **F · G · C · Cmaj7 · E · E7**. Preserve **Cadd9** "
                "(optional voicing on open C bars), **Cmaj7**, all slash chords, "
                "**Dm7**, **G7**, and **E7** — do not simplify. Backing: piano primary, "
                "light bass, subtle strings, soft brushes — **not** rock drums or "
                "distorted guitar. Verse sparse; bridge builds; chorus wider; final "
                "chorus = peak; outro thins to ringing C."
            ),
            default_bpm=76,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "John Lennon",
                "Piano Ballad",
                "Singer-Songwriter",
                "Classic Rock",
                "Karaoke Friendly",
                "Vocal Showcase",
            ],
            vocal_showcase=True,
            piano_centric=True,
            optional_voicings={"C": "Cadd9"},
            vocal_range_notes=(
                "Verse sits in comfortable mid chest; chorus asks for a gentle mix "
                "lift without forcing. Plan breaths before each chorus entrance and "
                "the E · E7 lifts; final chorus is the warmest sustained peak."
            ),
            vocal_harmony_hints=(
                "Reflective piano ballad: soften consonants in verses, open vowels on "
                "'Imagine', and breathe before each bridge descent. Follow the "
                "descending bass in the bridges with your phrasing — don't rush "
                "Am/E → Dm7 → F/C."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "C major piano ballad; verse I–maj7–IV; bridge descending bass "
                    "to V; chorus F–G–I with E/E7 color"
                ),
                "descending_bass_line": (
                    "Bridge signature: F → Am/E → Dm7 → F/C → G → C/G → G7"
                ),
                "voice_leading_notes": (
                    "Piano comping follows slash basses: Am/E keeps E in the bass "
                    "under A minor color; F/C and C/G maintain stepwise descent; "
                    "E7 resolves toward Am in the next verse cycle."
                ),
                "piano_voicing_notes": (
                    "Use rootless left-hand shells on slashes; optional **Cadd9** "
                    "right-hand color on open C bars in intro/verse/outro."
                ),
                "improvisation_notes": (
                    "C major pentatonic over verses; Dorian on Dm7 in bridges; "
                    "Mixolydian or altered on E7 at chorus peaks."
                ),
                "scale_suggestions": scale_hints,
            },
            backing_character="piano_ballad_lennon",
        ),
    }


def _wonderwall_chart_pack() -> dict[str, Any]:
    """Wonderwall — Oasis (Em shapes / capo 2, F# minor concert, 4/4).

    Britpop acoustic anthem on **Em7 · G · Dsus4 · A7sus4** with **Cadd9**
    and **G/F#** in bridge/chorus. Preserve all sus/add9 voicings exactly.
    """
    loop = ["Em7", "G", "Dsus4", "A7sus4"]
    intro = list(loop) * 4

    def _verse_12() -> list[str]:
        return list(loop) * 3 + ["Cadd9", "Dsus4", "A7sus4"]

    verse_3 = list(loop) * 4

    def _bridge() -> list[str]:
        return [
            "Cadd9",
            "Dsus4",
            "Em7",
            "Cadd9",
            "Dsus4",
            "Em7",
            "Cadd9",
            "Dsus4",
            "G",
            "G/F#",
            "Em7",
            "G",
            "A7sus4",
        ]

    def _chorus() -> list[str]:
        return (
            ["Cadd9", "Em7", "G"]
            + ["Em7", "Cadd9", "Em7", "G"]
            + ["Em7", "Cadd9", "Em7", "G"]
            + ["Em7"]
        )

    outro = ["Cadd9", "Em7", "G", "Em7"] * 4

    intermediate = {
        "Intro": list(intro),
        "Verse 1": _verse_12(),
        "Verse 2": _verse_12(),
        "Chorus Prep / Bridge": _bridge(),
        "Chorus": _chorus(),
        "Verse 3": list(verse_3),
        "Bridge 2": _bridge(),
        "Final Chorus": _chorus(),
        "Outro": list(outro),
    }

    beginner = {name: list(chords) for name, chords in intermediate.items()}
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
    scale_hints = {
        "Em7": ["E Minor Pentatonic", "E Natural Minor"],
        "G": ["G Major"],
        "Dsus4": ["D Major"],
        "A7sus4": ["A Mixolydian"],
        "Cadd9": ["C Major"],
        "G/F#": ["G Major"],
    }

    return {
        "key": "Em",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Noel Gallagher",
        "guitar_tabs": {
            "Em7": "022030",
            "G": "320003",
            "Dsus4": "xx0233",
            "A7sus4": "x02030",
            "Cadd9": "x32030",
            "G/F#": "2x0033",
        },
        "lyric_cues": {
            "Intro": [
                "Iconic Em7 · G · Dsus4 · A7sus4 vamp — let chords ring",
                "(breath) before 'Today is gonna be the day…'",
            ],
            "Verse 1": [
                "Steady acoustic strumming — intimate, singalong delivery",
                "Land Cadd9 · Dsus4 · A7sus4 tag at end of verse",
            ],
            "Verse 2": ["Second verse — same groove, slightly fuller feel"],
            "Chorus Prep / Bridge": [
                "Gradual build — Cadd9 · Dsus4 · Em7 lifts",
                "G · G/F# · Em7 walkdown is the signature Oasis moment",
            ],
            "Chorus": [
                "'Maybe you're gonna be the one…' — open vowels, full strum",
                "(breath) before title hook 'Wonderwall'",
                "Fuller drums and wider guitars",
            ],
            "Verse 3": ["Third verse — four full loops, no Cadd9 tag"],
            "Bridge 2": ["Second bridge — stronger bass, build to final chorus"],
            "Final Chorus": [
                "Biggest energy — strongest singalong pass",
                "Repeat feel; belt the title hook with ringing open chords",
            ],
            "Outro": [
                "Cadd9 · Em7 · G · Em7 repeat and fade",
                "Gradually release strumming intensity",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**F# minor** concert; chart in **Em shapes** (capo **2**). "
                "**4/4**, ~88 BPM britpop / acoustic rock. Core vamp "
                "**Em7 · G · Dsus4 · A7sus4** — preserve **Em7**, **Dsus4**, "
                "**A7sus4**, **Cadd9**, and **G/F#** exactly (no plain D or A7 "
                "substitutions). Verse: steady acoustic strum; bridge: gradual "
                "build with G/F# bass; chorus: fuller drums and guitars; outro "
                "repeats and fades. **Not** piano ballad or jazz reharm. "
                "Classic singalong karaoke repertoire."
            ),
            default_bpm=88,
            default_groove="Pop groove",
            time_signature="4/4",
            capo_note="Capo 2 (Em-shape chart) · concert key F# minor",
            strumming_pattern=(
                "Typical feel: down-strokes on beats 1–3, lighter ups on 2 & 4; "
                "or D · DU · UDU per bar — keep open strings ringing."
            ),
            repertoire_tags=[
                "Britpop",
                "Oasis",
                "Acoustic Rock",
                "90s Rock",
                "Karaoke Friendly",
                "Vocal Showcase",
            ],
            vocal_showcase=True,
            vocal_range_notes=(
                "Verse sits in comfortable chest/mix; chorus opens slightly on "
                "the title hook. Plan breaths before each chorus and the bridge "
                "G/F# walk — don't rush the suspended chords."
            ),
            vocal_harmony_hints=(
                "Britpop singalong: conversational verses, open vowels on "
                "'Wonderwall', and let Dsus4 · A7sus4 ring between phrases."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "Em-centric britpop loop with sus/add9 colors; bridge "
                    "Cadd9–Dsus4–Em7 and G/F# bass walk"
                ),
                "improvisation_notes": (
                    "E minor pentatonic over the main loop; C major over "
                    "Cadd9 bridge figures; keep fills sparse and ringing."
                ),
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="britpop_acoustic_oasis",
        ),
    }


def _why_georgia_chart_pack() -> dict[str, Any]:
    """Why Georgia — John Mayer (G major, acoustic rock, 4/4).

    Fingerstyle acoustic showcase: **Gsus2 · D · Dsus · D** riff, **C6/9**
    holds, Mayer color pre-chorus (**Em7 · D/F# · Cadd9 · A7sus**), atmospheric
    bridge (**Bbsus2 · Csus2 · Gm/C**). Preserve all sus/add9 voicings exactly.
    """
    def _riff(bars: int = 1) -> list[str]:
        cell = ["Gsus2", "D", "Dsus", "D"]
        return cell * bars

    def _verse() -> list[str]:
        return _riff(2) + ["C6/9", "C6/9"] + _riff(1)

    def _pre_chorus() -> list[str]:
        return ["Em7", "D/F#", "G", "Cadd9", "Em7", "D/F#", "G", "A7sus"]

    def _chorus() -> list[str]:
        return ["D", "A", "G", "D", "A", "Em7", "D", "A", "G", "Fsus2", "Cadd9"]

    def _bridge() -> list[str]:
        return (
            ["Fsus2", "Bbsus2", "Csus2", "Bbsus2"] * 2
            + ["G", "Cadd9", "Dadd4", "Cadd9"] * 2
            + ["Em7", "Dsus2", "Gm/C", "Fsus2"]
        )

    intermediate = {
        "Intro": _riff(4),
        "Verse 1": _verse(),
        "Verse Build": _pre_chorus(),
        "Chorus": _chorus(),
        "Intro Riff Return": _riff(1),
        "Verse 2": _verse(),
        "Pre-Chorus": _pre_chorus(),
        "Chorus 2": _chorus() + ["G", "Gmaj7"],
        "Bridge": _bridge(),
        "Verse 3": _verse(),
        "Final Build": ["Em7", "D/F#", "G", "A7sus"],
        "Final Chorus": _chorus() + ["G"],
        "Outro": _riff(2),
    }

    _signature = {
        "Gsus2",
        "Dsus",
        "C6/9",
        "Em7",
        "D/F#",
        "Cadd9",
        "A7sus",
        "Fsus2",
        "Gmaj7",
        "Bbsus2",
        "Csus2",
        "Dsus2",
        "Gm/C",
        "Dadd4",
    }

    def _beg(ch: str) -> str:
        if ch in _signature or "/" in ch or "sus" in ch or "6/9" in ch:
            return ch
        return ch.replace("maj7", "").replace("m7", "m")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
    scale_hints = {
        "G": ["G Major", "G Major Pentatonic"],
        "Gsus2": ["G Major", "G Major Pentatonic"],
        "Em7": ["E Dorian", "E Minor Pentatonic"],
        "A7sus": ["A Mixolydian"],
        "Cadd9": ["C Major"],
        "D/F#": ["D Major"],
        "Gm/C": ["C Mixolydian", "modal color"],
        "C6/9": ["C Major"],
        "Fsus2": ["F Major"],
    }

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
        "composer": "John Mayer",
        "guitar_tabs": {
            "Gsus2": "300033",
            "D": "xx0232",
            "Dsus": "xx0230",
            "C6/9": "x32030",
            "Em7": "022030",
            "D/F#": "2x0232",
            "G": "320003",
            "Cadd9": "x32030",
            "A7sus": "x02030",
            "A": "x02220",
            "Fsus2": "133011",
            "Gmaj7": "3x443x",
            "Bbsus2": "x13311",
            "Csus2": "x35533",
            "Dadd4": "xx0233",
            "Dsus2": "xx0230",
            "Gm/C": "x30333",
        },
        "lyric_cues": {
            "Intro": [
                "Fingerpicked Gsus2 · D · Dsus · D — (breath) before vocal",
                "Let each sus chord ring; thumb on bass notes",
            ],
            "Verse 1": [
                "'I am driving up 85…' — intimate, conversational",
                "Hold C6/9 for two bars; don't rush the return riff",
            ],
            "Verse Build": [
                "Gradual lift — Em7 · D/F# bass walk",
                "Land A7sus cleanly before chorus",
            ],
            "Chorus": [
                "'I am living in the eye of the hurricane…' — open vowels",
                "Fuller band enters; Fsus2 · Cadd9 tags each chorus",
            ],
            "Intro Riff Return": ["Instrumental riff — reset before Verse 2"],
            "Verse 2": ["Second verse — same fingerstyle feel as Verse 1"],
            "Pre-Chorus": ["Build again — save peak for Chorus 2 tag"],
            "Chorus 2": [
                "Chorus + G · Gmaj7 lift — widest verse-chorus energy so far",
            ],
            "Bridge": [
                "Atmospheric Bbsus2 · Csus2 tension",
                "Gm/C modal color — emotional bridge peak",
            ],
            "Verse 3": ["Third verse — pull back to intimate riff"],
            "Final Build": [
                "Single-bar build Em7 → D/F# → G → A7sus — (breath) before final chorus",
            ],
            "Final Chorus": [
                "Biggest dynamic peak — fullest drums and guitars",
                "Land on ringing G",
            ],
            "Outro": [
                "Return to Gsus2 · D · Dsus · D — fade out reflectively",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**G major** acoustic rock / singer-songwriter (**4/4**, ~84 BPM). "
                "Signature Mayer fingerstyle riff **Gsus2 · D · Dsus · D**; preserve "
                "all sus/add9/slash colors exactly (**C6/9**, **A7sus**, **Fsus2**, "
                "**Bbsus2**, **Csus2**, **Dsus2**, **Gm/C**, **Gmaj7**). Verse: "
                "intimate fingerpick; pre-chorus builds; chorus fuller band; bridge "
                "atmospheric; final chorus = peak; outro fades on intro riff. "
                "**Not** heavy distortion, EDM, or piano ballad. Advanced acoustic "
                "guitar showcase — character comes from voicings and rhythm."
            ),
            default_bpm=84,
            default_groove="Ballad",
            time_signature="4/4",
            fingerstyle_notes=(
                "Thumb–finger pattern on Gsus2–D–Dsus–D: bass note on beat 1, "
                "syncopated pluck on 2 and 4; let sus chords ring. Pre-chorus "
                "Em7–D/F#: walk bass under arpeggios."
            ),
            rhythm_guitar_notes=(
                "Chorus: light strum or arpeggiated A and D triads; keep Fsus2 "
                "and Cadd9 as open ringing voicings, not power chords."
            ),
            repertoire_tags=[
                "John Mayer",
                "Acoustic Rock",
                "Singer-Songwriter",
                "Reflective",
                "Guitar Showcase",
                "Karaoke Friendly",
            ],
            vocal_showcase=True,
            guitar_showcase=True,
            vocal_range_notes=(
                "Verse in comfortable chest; chorus opens into mix without forcing. "
                "Plan breaths before each chorus and the final build; bridge is "
                "the most atmospheric vocal moment."
            ),
            vocal_harmony_hints=(
                "Reflective Mayer delivery: conversational verses, slightly brighter "
                "tone on chorus hooks, and let the guitar voicings breathe between "
                "lines — don't compete with the sus chord ringing."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "G major riff-based song; pre-chorus Em7–D/F#–Cadd9; "
                    "chorus D–A–G with Fsus2 color; modal bridge"
                ),
                "improvisation_notes": (
                    "G major pentatonic over riff; E Dorian on Em7; sparse "
                    "fills in gaps — the voicings carry the song."
                ),
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="mayer_acoustic_guitar_showcase",
        ),
    }


def _daughters_chart_pack() -> dict[str, Any]:
    """Daughters — John Mayer (D major, acoustic ballad, 4/4).

    Fingerpicked Mayer ballad: preserve **Bm7 · Em7 · A7sus4 · D** cycle,
    chorus **E7** lift, and bridge colors (**D9 · Gm/D · Dmaj7 · Dsus2 ·
    Gm11 · D/F#**) exactly — no simplification of sus/add9/slash voicings.
    """
    intro_cell = ["Bm7", "Em7", "A7sus4", "D"]

    def _verse() -> list[str]:
        stanza = ["Bm7", "Em7", "A7sus4", "D"]
        return stanza * 4

    def _chorus() -> list[str]:
        stanza = ["Bm7", "E7", "A7sus4", "D"]
        return stanza * 4

    def _bridge() -> list[str]:
        return [
            "D9",
            "Gm/D",
            "D",
            "Dmaj7",
            "Dsus2",
            "Bm7",
            "Em7",
            "D/F#",
            "Gm11",
            "A7sus4",
            "Bm7",
        ]

    def _instrumental_tag() -> list[str]:
        return ["Bm7", "E7", "A7sus4", "D", "Bm7", "E7", "A7sus4"]

    def _interlude() -> list[str]:
        return [
            "D",
            "Bm7",
            "E7",
            "A7sus4",
            "D",
            "Bm7",
            "E7",
            "A7sus4",
            "D",
        ]

    intermediate = {
        "Intro": intro_cell * 2,
        "Verse 1": _verse(),
        "Chorus": _chorus(),
        "Instrumental": intro_cell * 2,
        "Verse 2": _verse(),
        "Chorus 2": _chorus(),
        "Bridge": _bridge(),
        "Instrumental Tag": _instrumental_tag(),
        "Interlude": _interlude(),
        "Final Chorus": _chorus(),
        "Outro": _chorus()[:4],
    }

    _signature = {
        "Bm7",
        "Em7",
        "A7sus4",
        "D9",
        "Gm/D",
        "Dmaj7",
        "Dsus2",
        "D/F#",
        "Gm11",
        "E7",
    }

    def _beg(ch: str) -> str:
        if ch in _signature or "/" in ch or "sus" in ch or "11" in ch:
            return ch
        return ch.replace("maj7", "").replace("m7", "m")

    beginner = {
        name: [_beg(c) for c in chords]
        for name, chords in intermediate.items()
    }
    advanced = {name: list(chords) for name, chords in intermediate.items()}

    section_order = list(intermediate.keys())
    scale_hints = {
        "Bm7": ["B Dorian", "B Minor Pentatonic"],
        "Em7": ["E Dorian"],
        "A7sus4": ["A Mixolydian"],
        "D": ["D Major"],
        "E7": ["E Mixolydian", "E Altered (advanced)"],
        "Dmaj7": ["D Ionian", "D Lydian"],
        "Gm11": ["G Dorian"],
        "D9": ["D Major"],
        "Gm/D": ["D Major", "modal color"],
        "Dsus2": ["D Major"],
        "D/F#": ["D Major"],
    }

    return {
        "key": "D",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "John Mayer",
        "guitar_tabs": {
            "Bm7": "x24232",
            "Em7": "022030",
            "A7sus4": "x02030",
            "D": "xx0232",
            "E7": "020100",
            "D9": "x54530",
            "Gm/D": "xx0331",
            "Dmaj7": "xx0222",
            "Dsus2": "xx0230",
            "D/F#": "2x0232",
            "Gm11": "353533",
        },
        "lyric_cues": {
            "Intro": [
                "Bm7 · Em7 · A7sus4 · D — fingerpicked intro, (breath) before vocal",
                "Intimate acoustic; let each sus voicing ring",
            ],
            "Verse 1": [
                "'Fathers be good to your daughters…' — conversational, reflective",
                "Hold the A7sus4 → D resolution; don't rush the cycle",
            ],
            "Chorus": [
                "Slightly fuller — E7 lift before A7sus4 · D",
                "Open vowels; stronger bass under the chorus",
            ],
            "Instrumental": [
                "Same intro cycle — reset energy before Verse 2",
            ],
            "Verse 2": [
                "Second verse — same intimate fingerstyle as Verse 1",
            ],
            "Chorus 2": [
                "Chorus again — maintain Mayer phrasing, not pushed",
            ],
            "Bridge": [
                "Emotional peak — D9 · Gm/D · Dmaj7 colors",
                "Gm11 · A7sus4 · Bm7 — richest harmony in the song",
            ],
            "Instrumental Tag": [
                "Short tag — hang on final A7sus4",
            ],
            "Interlude": [
                "D · Bm7 · E7 · A7sus4 turnaround — (breath) before final chorus",
            ],
            "Final Chorus": [
                "Widest dynamic — fullest arrangement, still acoustic",
            ],
            "Outro": [
                "Pull instrumentation back — let chords breathe and fade",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D major** singer-songwriter acoustic ballad (**4/4**, ~125 BPM). "
                "Preserve Mayer color voicings exactly: **Bm7 · Em7 · A7sus4 · D** "
                "verse cycle; chorus **E7** lift; bridge **D9 · Gm/D · Dmaj7 · "
                "**Dsus2 · Gm11 · D/F#**. Verse: intimate fingerpick; chorus slightly "
                "fuller with stronger bass; bridge = emotional peak; outro pulls back. "
                "Backing: acoustic fingerpicked guitar, light percussion, bass, subtle "
                "electric texture — **not** heavy drums or rock distortion. Group with "
                "core Mayer repertoire (Why Georgia, Gravity, Slow Dancing, Stop This "
                "Train)."
            ),
            default_bpm=125,
            default_groove="Ballad",
            time_signature="4/4",
            fingerstyle_notes=(
                "Thumb–finger arpeggio on Bm7–Em7–A7sus4–D: bass on 1, syncopated "
                "pluck on 2 and 4; let sus chords ring through the bar."
            ),
            rhythm_guitar_notes=(
                "Chorus: light strum or arpeggiated D and A triads; keep A7sus4 and "
                "E7 as open ringing voicings. Bridge: richer voicings — no power chords."
            ),
            repertoire_tags=[
                "John Mayer",
                "Acoustic Ballad",
                "Singer-Songwriter",
                "Reflective",
                "Guitar Showcase",
                "Karaoke Friendly",
            ],
            vocal_showcase=True,
            guitar_showcase=True,
            vocal_range_notes=(
                "Comfortable chest voice in verses; chorus opens slightly without "
                "forcing. Plan breaths before each chorus and the bridge peak."
            ),
            vocal_harmony_hints=(
                "Reflective Mayer delivery: intimate verses, warm tone on chorus hooks, "
                "and let fingerpicked voicings breathe between lines."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "D major ballad; Bm7–Em7–A7sus4–D verse; chorus E7 color; "
                    "bridge with D9, Gm/D, Dmaj7, Gm11 peak"
                ),
                "improvisation_notes": (
                    "B Dorian / B minor pentatonic over Bm7; E Dorian on Em7; "
                    "A Mixolydian on A7sus4; sparse fills — voicings carry the song."
                ),
                "scale_suggestions": scale_hints,
            },
            acoustic_unplugged=True,
            backing_character="mayer_acoustic_guitar_showcase",
        ),
    }


def _breakaway_chart_pack() -> dict[str, Any]:
    """Breakaway — Kelly Clarkson (C major, inspirational pop ballad, 4/4).

    Uplifting **Am · G · C · F** loop with **D** in build sections. One list
    item = one bar. Preserve **Am**, **G**, **C**, **F**, and **D** exactly.
    """
    loop = ["Am", "G", "C", "F"]
    intro_cell = list(loop) + ["Am", "G", "F"]

    def _verse_stanza() -> list[str]:
        return ["Am", "G", "C", "F", "Am", "G", "F"]

    def _build_tail() -> list[str]:
        return ["Am", "G", "D", "F", "G"]

    def _chorus() -> list[str]:
        half = ["C", "G", "Am", "F", "C", "G", "Am", "G", "F"]
        return half * 2

    def _bridge() -> list[str]:
        return ["G", "C", "F", "G", "C", "F", "G", "C", "F", "D", "F", "G"]

    intermediate = {
        "Intro": intro_cell * 2,
        "Verse 1": _verse_stanza() * 3 + _build_tail(),
        "Chorus": _chorus(),
        "Instrumental": list(intro_cell),
        "Verse 2": _verse_stanza() * 2 + _build_tail(),
        "Chorus 2": _chorus(),
        "Bridge": _bridge(),
        "Final Chorus": _chorus(),
        "Ending": ["Am", "G", "F", "Am", "G", "F"],
        "Outro": ["C"],
    }

    beginner = {name: list(chords) for name, chords in intermediate.items()}

    def _adv(ch: str) -> str:
        if ch in {"Am", "G", "C", "F", "D"}:
            return ch
        return ch

    advanced = {
        name: [_adv(c) for c in chords]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "Am": ["A Natural Minor", "A Minor Pentatonic"],
        "G": ["G Major"],
        "C": ["C Major"],
        "F": ["F Major"],
        "D": ["D Major"],
    }

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
        "composer": "Avril Lavigne · Kara DioGuardi · Matthew Gerrard",
        "guitar_tabs": {
            "Am": "x02210",
            "G": "320003",
            "C": "x32010",
            "F": "133211",
            "D": "xx0232",
        },
        "lyric_cues": {
            "Intro": [
                "Am · G · C · F pickup — (breath) before 'Grew up in a small town…'",
                "Lighter instrumentation; set the inspirational story",
            ],
            "Verse 1": [
                "Intimate storytelling — conversational delivery",
                "(breath) between phrases; land **D** on the fourth stanza build",
            ],
            "Chorus": [
                "'Breakaway' title hook — open vowels, fuller drums and piano",
                "(breath) before 'I'll spread my wings and I'll learn how to fly'",
                "Uplifting anthem energy",
            ],
            "Instrumental": ["Short instrumental — same Am · G · C · F feel"],
            "Verse 2": [
                "Second verse — deepen the journey narrative",
                "D major lift on final stanza before Chorus 2",
            ],
            "Chorus 2": ["Repeat chorus lift — stronger band support"],
            "Bridge": [
                "Strongest build — (breath) 'Out of the darkness and into the sun'",
                "Three G · C · F climbs then **D** · F · G peak",
            ],
            "Final Chorus": [
                "Biggest emotional peak — graduation-anthem delivery",
                "Fullest strings and drums; sustain through both halves",
            ],
            "Ending": [
                "Wind down on Am · G · F — release intensity gradually",
            ],
            "Outro": [
                "Single **C** — warm landing; let the chord ring",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**C major** inspirational pop ballad (**4/4**, ~160 BPM). "
                "Core loop **Am · G · C · F** drives verses; preserve **D** in "
                "build/transition stanzas (Verse 1 tail, Verse 2 tail, Bridge). "
                "Chorus: **C · G · Am · F** with extended **G · Am · G · F** tags. "
                "Verse intimate; chorus bigger drums and piano; bridge strongest "
                "build; final chorus = emotional peak; outro thins to **C**. "
                "**Not** rock distortion, jazz reharm, or EDM. Graduation / "
                "empowerment karaoke repertoire."
            ),
            default_bpm=160,
            default_groove="Ballad",
            time_signature="4/4",
            repertoire_tags=[
                "Kelly Clarkson",
                "Inspirational Pop",
                "Pop Ballad",
                "Female Vocal Showcase",
                "Karaoke Friendly",
                "Graduation Song",
                "Inspirational",
                "Empowerment",
                "Life Journey",
                "Vocal Showcase",
            ],
            vocal_showcase=True,
            inspirational_ballad=True,
            vocal_range_notes=(
                "Verse in comfortable chest; chorus opens into mix on the title "
                "hook and high notes on 'fly'. Plan breaths before each chorus "
                "and the bridge; final chorus is the sustained peak."
            ),
            vocal_harmony_hints=(
                "Inspirational delivery: tell the story in verses, then open up "
                "on 'Breakaway' — don't rush the **D** build bars; let the "
                "emotion climb through the bridge into the final chorus."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "Am–G–C–F verse loop (vi–V–I–IV in C); D major in builds; "
                    "chorus I–V–vi–IV anthem"
                ),
                "improvisation_notes": (
                    "A minor pentatonic over verse loop; C major over chorus; "
                    "keep fills sparse and uplifting."
                ),
                "scale_suggestions": scale_hints,
            },
            backing_character="inspirational_pop_anthem",
        ),
    }


def _complicated_chart_pack() -> dict[str, Any]:
    """Complicated — Avril Lavigne (D minor, pop-rock, 4/4).

    Early-2000s hook **Dm · Bb · F · C** with **Gm** color in the chorus tail.
    One list item = one bar. Preserve **Gm** — do not substitute G major.
    """
    hook = ["Dm", "Bb", "F", "C"]

    def _verse() -> list[str]:
        return ["F", "Dm", "Bb", "C"] * 2

    def _pre_chorus() -> list[str]:
        return ["Bb", "Dm", "Bb", "C"]

    def _chorus() -> list[str]:
        return (
            list(hook) * 2
            + ["Dm", "Bb", "F", "C", "Gm", "Bb", "F"]
        )

    intermediate = {
        "Intro": list(hook) * 4,
        "Verse 1": _verse(),
        "Pre-Chorus": _pre_chorus(),
        "Chorus": _chorus(),
        "Verse 2": _verse(),
        "Pre-Chorus 2": _pre_chorus(),
        "Chorus 2": _chorus(),
        "Interlude": ["F", "Dm", "Bb", "C"],
        "Verse 3": _verse()[:4],
        "Pre-Chorus 3": _pre_chorus(),
        "Final Chorus": _chorus(),
        "Repeat Final Chorus": _chorus(),
        "Outro": list(hook) * 2,
    }

    beginner = {name: list(chords) for name, chords in intermediate.items()}

    def _adv(ch: str) -> str:
        if ch in {"Dm", "Bb", "F", "C", "Gm"}:
            return ch
        return ch

    advanced = {
        name: [_adv(c) for c in chords]
        for name, chords in intermediate.items()
    }

    section_order = list(intermediate.keys())
    scale_hints = {
        "Dm": ["D Natural Minor", "D Minor Pentatonic"],
        "Bb": ["Bb Major"],
        "F": ["F Major"],
        "C": ["C Major"],
        "Gm": ["G Dorian", "G Natural Minor"],
    }

    return {
        "key": "Dm",
        "sections": intermediate,
        "chart_versions": _levels(
            beginner=beginner,
            intermediate=intermediate,
            advanced=advanced,
        ),
        "chart_status": "practice_level_verified",
        "section_order": section_order,
        "composer": "Avril Lavigne · The Matrix (Lauren Christy · Scott Spock · Graham Edwards)",
        "guitar_tabs": {
            "Dm": "xx0231",
            "Bb": "x13331",
            "F": "133211",
            "C": "x32010",
            "Gm": "355333",
        },
        "lyric_cues": {
            "Intro": [
                "Dm · Bb · F · C hook — (breath) before 'Uh huh, life's like this…'",
                "Acoustic strum driving the early-2000s feel",
            ],
            "Verse 1": [
                "Verse: F · Dm · Bb · C — conversational, vocal-focused",
                "(breath) between lines; lighter drums",
            ],
            "Pre-Chorus": [
                "Build energy — Bb · Dm · Bb · C lift into chorus",
            ],
            "Chorus": [
                "'Why'd you have to go and make things complicated?' — title hook",
                "Full pop-rock band; land **Gm** color — not G major",
                "Open vowels on the chorus peak",
            ],
            "Verse 2": ["Second verse — same F · Dm · Bb · C pattern"],
            "Pre-Chorus 2": ["Second build — push into Chorus 2"],
            "Chorus 2": ["Repeat chorus energy — wider guitars"],
            "Interlude": ["Instrumental F · Dm · Bb · C breather"],
            "Verse 3": ["Third verse — one pass before final lifts"],
            "Pre-Chorus 3": ["Last pre-chorus — save peak for final choruses"],
            "Final Chorus": [
                "Biggest energy — fullest drums and backing vocals",
            ],
            "Repeat Final Chorus": [
                "Second final pass — anthem singalong; repeat hook",
            ],
            "Outro": [
                "Dm · Bb · F · C fade — natural hook outro",
            ],
        },
        "extensions": _ext(
            arrangement_notes=(
                "**D minor** early-2000s pop-rock (**4/4**, ~78 BPM). Primary hook "
                "**Dm · Bb · F · C** (vi–IV–I–V in F major / D minor feel). "
                "Preserve **Gm** in chorus tail — **not** G major. Verse lighter "
                "and vocal-focused; pre-chorus builds; chorus full band; final "
                "chorus ×2 = peak. **Acoustic** default: guitar-driven strum; "
                "switch groove to **Rock groove** in picker for full-band feel. "
                "**Not** jazz reharm, piano ballad, or metal. Beginner-friendly "
                "open-chord strumming alongside Sk8er Boi / I'm With You category."
            ),
            default_bpm=78,
            default_groove="Pop groove",
            time_signature="4/4",
            strumming_pattern=(
                "Verse: down-strum on beats 1 and 3, light ups on 2 and 4. "
                "Chorus: fuller eighth-note strum on Dm · Bb · F · C."
            ),
            repertoire_tags=[
                "Avril Lavigne",
                "Pop Rock",
                "Pop Punk",
                "2000s Pop",
                "Female Vocal Showcase",
                "Karaoke Friendly",
                "Acoustic Pop Rock",
            ],
            vocal_showcase=True,
            acoustic_unplugged=True,
            vocal_range_notes=(
                "Verse in mid chest; chorus opens with attitude on the title "
                "line. Plan breaths before each chorus; final chorus passes "
                "are the loudest sustained belts."
            ),
            vocal_harmony_hints=(
                "Pop-punk attitude: bite the consonants lightly in verses, "
                "then lean into the 'complicated' hook. The **Gm** bar is the "
                "emotional color — don't flatten it to G major."
            ),
            harmonic_analysis={
                "progression_summary": (
                    "Dm–Bb–F–C main hook; verse F–Dm–Bb–C; chorus Gm color tag"
                ),
                "improvisation_notes": (
                    "D minor pentatonic over hook; sparse fills in verse gaps."
                ),
                "scale_suggestions": scale_hints,
            },
            backing_character="pop_punk_acoustic_2000s",
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
        ("Say", "John Mayer"): _say_chart_pack(),
        ("Why Georgia", "John Mayer"): _why_georgia_chart_pack(),
        ("Daughters", "John Mayer"): _daughters_chart_pack(),
        ("The Scientist", "Coldplay"): _scientist_chart_pack(),
        ("New York State of Mind", "Billy Joel"): _nysom_chart_pack(),
        ("Just the Way You Are", "Billy Joel"): _jtway_chart_pack(),
        ("Come Together", "The Beatles"): _come_together_chart_pack(),
        ("Day Tripper", "The Beatles"): _day_tripper_chart_pack(),
        ("Autumn Leaves", "Jazz Standard"): _autumn_leaves_chart_pack(),
        ("Autumn Leaves", "Eric Clapton"): _autumn_leaves_chart_pack(),
        ("Attention", "Charlie Puth"): _attention_chart_pack(),
        ("Dance Monkey", "Tones and I"): _dance_monkey_chart_pack(),
        ("I'm Yours", "Jason Mraz"): _im_yours_chart_pack(),
        ("Take On Me (MTV Unplugged Version)", "a-ha"): _take_on_me_unplugged_chart_pack(),
        ("I Want It That Way", "Backstreet Boys"): _iwantit_chart_pack(),
        (
            "I Won't Say (I'm in Love)",
            "Disney · Hercules",
        ): _iwont_say_in_love_chart_pack(),
        ("How Far I'll Go", "Disney · Moana"): _how_far_ill_go_chart_pack(),
        ("Vienna", "Billy Joel"): _vienna_chart_pack(),
        ("All the Things You Are", "Jazz Standard"): _attya_chart_pack(),
        ("All the Things You Are", "Jerome Kern"): _attya_chart_pack(),
        ("Satin Doll", "Duke Ellington"): _satin_doll_chart_pack(),
        ("Iris", "Goo Goo Dolls"): _iris_chart_pack(),
        ("All of Me", "John Legend"): _all_of_me_chart_pack(),
        ("Love Story", "Taylor Swift"): _love_story_chart_pack(),
        ("Imagine", "John Lennon"): _imagine_chart_pack(),
        ("Wonderwall", "Oasis"): _wonderwall_chart_pack(),
        ("Breakaway", "Kelly Clarkson"): _breakaway_chart_pack(),
        ("Complicated", "Avril Lavigne"): _complicated_chart_pack(),
        (
            "Shalom Aleichem",
            "Traditional Jewish Sabbath Song",
        ): _shalom_aleichem_chart_pack(),
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
        ("Thinking Out Loud", "Ed Sheeran"): _thinking_out_loud_chart_pack(),
        ("Viva La Vida", "Coldplay"): _viva_la_vida_chart_pack(),
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
        ("Wave", "Antonio Carlos Jobim"): _wave_chart_pack(),
        ("Blue Bossa", "Kenny Dorham"): _blue_bossa_chart_pack(),
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
            "Em",
            {
                "Intro": ["Em", "C", "G", "D"] * 2,
                "Verse": ["Em", "C", "G", "D"] * 4,
                "Chorus": ["G", "Em", "Am", "C/D", "D", "Em", "C", "G", "D"],
            },
            {
                "Intro": ["Em7", "Cmaj7", "G", "D"] * 2,
                "Verse": ["Em7", "Cmaj7", "G", "D"] * 4,
                "Chorus": ["G", "Em7", "Am7", "C/D", "D", "Em7", "Cmaj7", "G", "D"],
            },
            composer="John Legend & Toby Gad",
            lyric_cues={
                "Intro": ["piano vamp — full chart in override"],
                "Chorus": ["title hook — preserve C/D color"],
            },
            notes="Em capo chart (~126 BPM); full form with C/D in chart override.",
            default_bpm=126,
            default_groove="Ballad",
        ),
        v(
            "Attention",
            "Charlie Puth",
            "Pop",
            "Dm",
            {
                "Intro": ["Dm", "C", "Am", "Bb"],
                "Verse 1": ["Dm", "C", "Am", "Bb"] * 2,
            },
            {
                "Intro": ["Dm", "C", "Am", "Bb"],
                "Verse 1": ["Dm", "C", "Am", "Bb"] * 2,
            },
            composer="Charlie Puth & Jacob Kasher",
            lyric_cues={"Intro": ["Dm · C · Am · Bb pocket"]},
            notes="D minor pop-funk loop; full form in chart override.",
            default_bpm=100,
            default_groove="Funk groove",
        ),
        v(
            "Dance Monkey",
            "Tones and I",
            "Pop",
            "F#m",
            {
                "Intro": ["F#m", "D", "E", "C#m"],
                "Verse 1": ["F#m", "D", "E", "C#m"],
            },
            {
                "Intro": ["F#m", "D", "E", "C#m"],
                "Verse 1": ["F#m", "D", "E", "C#m"],
            },
            composer="Toni Watson",
            lyric_cues={"Intro": ["F#m · D · E · C#m dance-pop loop"]},
            notes="F# minor electro-pop loop; full form in chart override.",
            default_bpm=98,
            default_groove="Pop groove",
        ),
        v(
            "I'm Yours",
            "Jason Mraz",
            "Pop",
            "G",
            {
                "Intro": ["G", "D", "Em", "C"],
                "Verse 1": ["G", "D", "Em", "C"],
            },
            {
                "Intro": ["G", "D", "Em", "C"],
                "Verse 1": ["G", "D", "Em", "C"],
            },
            composer="Jason Mraz",
            lyric_cues={"Intro": ["G · D · Em · C island groove"]},
            notes="G-shape chart (capo 4 = B concert); full form in chart override.",
            default_bpm=75,
            default_groove="Pop groove",
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
            notes="Practice chart in B minor; full form in chart override.",
            default_bpm=154,
            default_groove="Rock groove",
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
            "Take On Me (MTV Unplugged Version)",
            "a-ha",
            "Pop",
            "G",
            {
                "Intro": ["Am", "D/F#", "G", "C|G/B"],
                "Verse 1": ["Am", "D/F#", "Em"],
            },
            {
                "Intro": ["Am", "D/F#", "G", "C|G/B"],
                "Verse 1": ["Am", "D/F#", "Em"],
            },
            composer="Magne Furuholmen, Morten Harket & Pål Waaktaar",
            lyric_cues={"Intro": ["Acoustic unplugged — not synth-pop"]},
            notes="MTV Unplugged 2017; full chart in override.",
            default_bpm=64,
            default_groove="Ballad",
        ),
        v(
            "I Want It That Way",
            "Backstreet Boys",
            "Pop",
            "Em",
            {
                "Intro": ["Em", "C", "G"],
                "Verse 1": ["Em", "C", "G"],
            },
            {
                "Intro": ["Em", "C", "G"],
                "Verse 1": ["Em", "C", "G"],
            },
            composer="Max Martin & Andreas Carlsson",
            lyric_cues={"Intro": ["90s ballad — vocal-forward"]},
            notes="Em → F#m modulation; full chart in override.",
            default_bpm=99,
            default_groove="Ballad",
        ),
        v(
            "I Won't Say (I'm in Love)",
            "Disney · Hercules",
            "Pop",
            "C",
            {
                "Verse 1": ["C/G", "Fmaj7/G", "F6/G"],
                "Chorus 1": ["C", "G/C", "C"],
            },
            {
                "Verse 1": ["C/G", "Fmaj7/G", "F6/G"],
                "Chorus 1": ["C", "G/C", "C"],
            },
            composer="Alan Menken & David Zippel",
            lyric_cues={"Verse 1": ["Meg — Broadway storytelling"]},
            notes="Hercules Muses chart; full slashes in override.",
            default_bpm=92,
            default_groove="Ballad",
        ),
        v(
            "How Far I'll Go",
            "Disney · Moana",
            "Pop",
            "E",
            {
                "Verse 1": ["E", "F#m", "C#m", "A"],
                "Chorus A": ["E", "B", "C#m", "A"],
            },
            {
                "Verse 1": ["E", "F#m", "C#m", "A"],
                "Chorus A": ["E", "B", "C#m", "A"],
            },
            composer="Lin-Manuel Miranda & Mark Mancina",
            lyric_cues={"Verse 1": ["Moana — storytelling ballad"]},
            notes="E→F modulation; full ending descent in override.",
            default_bpm=84,
            default_groove="Ballad",
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
            "Complicated",
            "Avril Lavigne",
            "Pop",
            "Dm",
            {
                "Intro": ["Dm", "Bb", "F", "C"],
                "Verse 1": ["F", "Dm", "Bb", "C"],
            },
            {
                "Intro": ["Dm", "Bb", "F", "C"],
                "Verse 1": ["F", "Dm", "Bb", "C"],
            },
            composer="Avril Lavigne · The Matrix",
            lyric_cues={"Intro": ["Dm · Bb · F · C pop-rock hook"]},
            notes="D minor hook progression; full form with Gm chorus color in override.",
            chart_status=status,
            default_bpm=78,
            default_groove="Pop groove",
        ),
        v(
            "Breakaway",
            "Kelly Clarkson",
            "Pop",
            "C",
            {
                "Intro": ["Am", "G", "C", "F"],
                "Verse 1": ["Am", "G", "C", "F"],
            },
            {
                "Intro": ["Am", "G", "C", "F"],
                "Verse 1": ["Am", "G", "C", "F"],
            },
            composer="Avril Lavigne · Kara DioGuardi · Matthew Gerrard",
            lyric_cues={"Intro": ["Am · G · C · F inspirational pickup"]},
            notes="C major pop ballad; full form with D builds in override.",
            chart_status=status,
            default_bpm=160,
            default_groove="Ballad",
        ),
        v(
            "Why Georgia",
            "John Mayer",
            "Pop",
            "G",
            {
                "Intro": ["Gsus2", "D", "Dsus", "D"],
                "Verse 1": ["Gsus2", "D", "Dsus", "D"],
            },
            {
                "Intro": ["Gsus2", "D", "Dsus", "D"],
                "Verse 1": ["Gsus2", "D", "Dsus", "D"],
            },
            composer="John Mayer",
            lyric_cues={"Intro": ["Gsus2 · D · Dsus · D fingerpick riff"]},
            notes="G major Mayer acoustic showcase; full form in chart override.",
            chart_status=status,
            default_bpm=84,
            default_groove="Ballad",
        ),
        v(
            "Daughters",
            "John Mayer",
            "Pop",
            "D",
            {
                "Intro": ["Bm7", "Em7", "A7sus4", "D"],
                "Verse 1": ["Bm7", "Em7", "A7sus4", "D"],
            },
            {
                "Intro": ["Bm7", "Em7", "A7sus4", "D", "Bm7", "Em7", "A7sus4", "D"],
                "Verse 1": ["Bm7", "Em7", "A7sus4", "D"] * 4,
            },
            composer="John Mayer",
            lyric_cues={"Intro": ["Bm7 · Em7 · A7sus4 · D fingerpicked intro"]},
            notes=(
                "D major Mayer acoustic ballad; preserve Bm7, Em7, A7sus4, D9, "
                "Gm/D, Dmaj7, Dsus2, D/F#, Gm11, E7 — full form in chart override."
            ),
            chart_status=status,
            default_bpm=125,
            default_groove="Ballad",
        ),
        v(
            "Love Story",
            "Taylor Swift",
            "Country",
            "C",
            {
                "Intro": ["C", "G", "Am", "F"],
                "Verse 1": ["C", "F", "Am", "F"],
            },
            {
                "Intro": ["C", "G", "Am", "F"],
                "Verse 1": ["C", "F", "Am", "F"],
            },
            composer="Taylor Swift",
            lyric_cues={"Intro": ["C · G · Am · F storybook pickup"]},
            notes="C-shape chart (capo 2 = D concert); full form with key change in override.",
            chart_status=status,
            default_bpm=119,
            default_groove="Ballad",
        ),
        v(
            "Imagine",
            "John Lennon",
            "Rock",
            "C",
            {
                "Intro": ["C", "Cmaj7", "F"],
                "Verse 1": ["C", "Cmaj7", "F"],
            },
            {
                "Intro": ["C", "Cmaj7", "F"],
                "Verse 1": ["C", "Cmaj7", "F"],
            },
            composer="John Lennon",
            lyric_cues={"Intro": ["C · Cmaj7 · F piano pickup"]},
            notes="C major piano ballad; full form with slash-bridge in override.",
            chart_status=status,
            default_bpm=76,
            default_groove="Ballad",
        ),
        v(
            "Wonderwall",
            "Oasis",
            "Rock",
            "Em",
            {
                "Intro": ["Em7", "G", "Dsus4", "A7sus4"],
                "Verse 1": ["Em7", "G", "Dsus4", "A7sus4"],
            },
            {
                "Intro": ["Em7", "G", "Dsus4", "A7sus4"],
                "Verse 1": ["Em7", "G", "Dsus4", "A7sus4"],
            },
            composer="Noel Gallagher",
            lyric_cues={"Intro": ["Em7 · G · Dsus4 · A7sus4 britpop vamp"]},
            notes="Em-shape chart (capo 2 = F#m concert); full form in override.",
            chart_status=status,
            default_bpm=88,
            default_groove="Pop groove",
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


def _jewish_traditional_catalog_songs() -> list[dict[str, Any]]:
    """Shabbat / congregational Jewish repertoire — warm acoustic singalong."""

    def _jt(
        title: str,
        key: str,
        sections: dict[str, list[str]],
        *,
        bpm: int,
        groove: str = "Jewish ballad",
        meter: str = "4/4",
        lyric_cues: dict[str, list[str]] | None = None,
        section_order: list[str] | None = None,
        guitar_tabs: dict[str, str] | None = None,
        beginner: dict[str, list[str]] | None = None,
        advanced: dict[str, list[str]] | None = None,
        artist: str = "Traditional Jewish Sabbath Song",
        hebrew_lyrics: dict[str, str] | None = None,
        transliteration: dict[str, str] | None = None,
        repertoire_tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        inter = sections
        beg = beginner or sections
        adv = advanced or sections
        tags = repertoire_tags or [
            "Jewish",
            "Shabbat",
            "Hebrew",
            "Traditional",
            "Congregational",
        ]
        ext = _ext(
            default_bpm=bpm,
            default_groove=groove,
            time_signature=meter,
            arrangement_notes=notes
            or (
                f"{title}: Jewish Traditional Shabbat chart; Hebrew + transliteration "
                "supported; congregational acoustic backing."
            ),
            repertoire_tags=tags,
            hebrew_lyrics=hebrew_lyrics,
            transliteration=transliteration,
            jewish_traditional=True,
            backing_character="jewish_traditional_congregational",
        )
        row = _s(
            title,
            artist,
            "Jewish Traditional",
            key,
            inter,
            lyric_cues=lyric_cues or {},
            guitar_tabs=guitar_tabs or {},
            chart_status="practice_level_verified",
            chart_versions=_levels(beginner=beg, intermediate=inter, advanced=adv),
            extensions=ext,
        )
        row["section_order"] = section_order or list(sections.keys())
        return row

    _dm_tabs = {"Dm": "xx0231", "Gm": "355333", "A": "x02220", "F": "133211", "C": "x32010"}

    return [
        _jt(
            "Shalom Aleichem",
            "Dm",
            {
                "Verse 1": ["Dm", "A", "Dm", "A"],
                "Verse 2": ["Dm", "A", "Dm", "A"],
            },
            bpm=72,
            lyric_cues={
                "Verse 1": ["Shabbat welcome — full chart in override"],
                "Verse 2": ["congregational answer phrase"],
            },
            guitar_tabs=_dm_tabs,
            notes="Full Shabbat form (Verses 1–4, instrumental, outro) in chart override.",
        ),
    ]


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
            chart_status="practice_level_verified",
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
            groove="Jewish hora",
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
            groove="Jewish ballad",
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
            groove="Jewish ballad",
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
            groove="Klezmer groove",
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
            groove="Jewish hora",
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
            groove="Jewish ballad",
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
            groove="Klezmer groove",
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
            "Adon Olam",
            "F",
            {
                "Strophe A": ["F", "Bb", "C", "F", "Dm", "Gm", "C", "F"],
                "Strophe B": ["Bb", "F", "C", "F", "Dm", "Gm", "C", "F"],
            },
            bpm=88,
            groove="Jewish ballad",
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
        _s(
            "Say",
            "John Mayer",
            "Pop",
            "G",
            {
                "Intro": ["G", "C", "Em", "D"],
                "Verse 1": ["G", "C", "Em", "D"] * 4,
                "Chorus 1": ["G", "C", "Em", "D"] * 4,
                "Turnaround 1": ["G", "C", "Em", "D"],
                "Verse 2": ["G", "C", "Em", "D"] * 4,
                "Chorus 2": ["G", "C", "Em", "D"] * 4,
                "Bridge": ["Am", "C", "D", "Am", "C", "D", "C", "D"],
                "Final Chorus": ["Em", "G", "C7", "C7", "Em", "G", "C7", "C7"],
            },
            guitar_tabs={
                "G": "320003",
                "C": "x32010",
                "Em": "022000",
                "D": "xx0232",
                "Am": "x02210",
                "C7": "x32310",
            },
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Chorus 1",
                "Turnaround 1",
                "Verse 2",
                "Chorus 2",
                "Turnaround 2",
                "Bridge",
                "Turnaround 3",
                "Verse 3",
                "Final Chorus",
            ],
            extensions=_ext(default_bpm=82, default_groove="Ballad", time_signature="4/4"),
        ),
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
            "Intro": ["Bm7", "Em7", "A7sus4", "D"],
            "Verse 1": ["Bm7", "Em7", "A7sus4", "D"],
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
        _s(
            "Thinking Out Loud",
            "Ed Sheeran",
            "Pop",
            "C",
            {
                "Verse 1": ["C", "C/E", "F", "G"] * 4,
                "Turnaround": ["C", "C/E", "F", "G", "C", "C/E", "F", "G"],
                "Pre-Chorus 1": ["Dm", "G", "C", "Dm", "G", "Dm", "G", "Am", "Dm", "G", "C", "C/E"],
                "Chorus 1": ["F", "G", "C", "C/E"] * 3 + ["F", "G"],
                "Verse 2": ["C", "C/E", "F", "G"] * 4,
                "Chorus 2": ["F", "G", "C", "C/E"] * 3 + ["F", "G"],
                "Outro": ["Am", "G", "F", "C/E", "Dm", "G", "C"],
            },
            extensions=_ext(
                default_bpm=75,
                default_groove="Ballad",
                time_signature="4/4",
                vocal_showcase=True,
                ed_sheeran_acoustic=True,
                repertoire_tags=[
                    "Ed Sheeran",
                    "Acoustic Pop",
                    "Wedding Song",
                    "Romantic Ballad",
                    "Karaoke Friendly",
                ],
            ),
            chart_status="practice_level_verified",
        ),
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
        _s("Viva La Vida", "Coldplay", "Pop", "C", {
            "Placeholder": ["C"],
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
        _s(
            "The Scientist",
            "Coldplay",
            "Pop",
            "Dm",
            {
                "Intro": ["Bm7", "G", "D", "Dsus2"] * 2,
                "Verse 1": ["Bm7", "G", "D", "Dsus2"] * 4,
                "Chorus 1": [
                    "G",
                    "D",
                    "Dsus2",
                    "A/D",
                    "D6/9",
                    "A/E",
                    "Asus4",
                    "A",
                ],
                "N.C. 1": ["N.C."],
                "Instrumental 1": [
                    "D",
                    "G",
                    "D",
                    "D|Dmaj7",
                    "Bm7",
                    "G",
                    "D",
                    "Dsus2",
                ],
                "Verse 2": ["Bm7", "G", "D", "Dsus2"] * 3
                + ["Bm7", "G", "D", "Dsus2/C#"],
                "Chorus 2": [
                    "G",
                    "D",
                    "Dsus2",
                    "A/D",
                    "D6/9",
                    "A/E",
                    "Asus4",
                    "A",
                ],
                "N.C. 2": ["N.C."],
                "Instrumental 2": ["D", "G", "D", "D"],
                "Ending": ["Bm7", "G", "D", "D"] * 4,
                "Final Tag": ["Bm7", "G", "D"],
            },
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Chorus 1",
                "N.C. 1",
                "Instrumental 1",
                "Verse 2",
                "Chorus 2",
                "N.C. 2",
                "Instrumental 2",
                "Ending",
                "Final Tag",
            ],
            extensions=_ext(
                default_bpm=73,
                default_groove="Ballad",
                time_signature="4/4",
                vocal_showcase=True,
                coldplay_piano_ballad=True,
                repertoire_tags=[
                    "Coldplay",
                    "Piano Ballad",
                    "Alternative Rock",
                    "Emotional Ballad",
                    "Karaoke Friendly",
                    "Vocal Showcase",
                ],
            ),
        ),
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
        _s(
            "Just the Way You Are",
            "Billy Joel",
            "Pop",
            "D",
            {
                "Intro": ["Gm6/D", "G/D", "Dsus4"] * 2,
                "Verse 1": ["D", "Bm6", "Gmaj7", "Bm|D7", "Gmaj7", "Gm7", "D/F#"],
                "Refrain 1": ["D", "Bm6", "Gmaj7", "Bm|D9", "Gmaj7", "Gm7", "D/F#"],
                "Bridge": ["Gmaj7", "A6", "F#m7", "B7", "Em7", "A7sus", "D", "D/C"],
                "Outro": ["D", "Bm6", "Gmaj7", "Bm|D7", "Gmaj7", "Gm", "D/F#"],
            },
            composer="Billy Joel",
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Refrain 1",
                "Verse 2",
                "Refrain 2",
                "Bridge",
                "Refrain 3",
                "Sax Solo",
                "Refrain 4",
                "Outro",
                "Outro (Fade)",
            ],
            extensions=_ext(default_bpm=76, default_groove="Ballad", time_signature="4/4"),
        ),
        _s("Vienna", "Billy Joel", "Pop", "G", {
            "Intro": ["G6", "Faug", "F7", "B7sus4"],
            "Verse 1": ["Em", "G", "D", "F"],
            "Chorus 1": ["C", "D", "G", "D/F#"],
        }, composer="Billy Joel",
          extensions=_ext(
              default_bpm=63,
              default_groove="Ballad",
              piano_centric=True,
              vocal_showcase=True,
              capo_note="Capo 3 (Em-shape chart)",
              repertoire_tags=["Billy Joel", "Piano Ballad", "Vocal Showcase"],
          ),
          chart_status="practice_level_verified"),
        _s(
            "New York State of Mind",
            "Billy Joel",
            "Jazz",
            "C",
            {
                "Intro": [
                    "Dm9",
                    "Abmaj7/Bb",
                    "Dm9",
                    "Em7",
                    "F",
                    "Dm9",
                    "F/G",
                    "C",
                    "E7",
                    "Am7",
                    "Gm7|C7",
                    "F",
                    "A7",
                    "Dm",
                    "Bb9",
                ],
                "Verse 1": ["C", "E7", "Am7", "Gm7|C7", "F", "A7", "Dm", "Bb9"],
                "Chorus 1": ["Am7", "D7", "Gmaj7", "G", "Gm7", "C7", "Fmaj7"],
                "Outro": ["Eb6", "Ab", "Dm7", "Dbmaj13", "Cmaj9"],
            },
            composer="Billy Joel",
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Verse 2",
                "Chorus 1",
                "Verse 3",
                "Solo",
                "Chorus 2",
                "Verse 4 (Extended)",
                "Outro",
            ],
            extensions=_ext(default_bpm=74, default_groove="Ballad", time_signature="4/4"),
        ),
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
        _s(
            "We Are the Champions",
            "Queen",
            "Rock",
            "Cm",
            {
                "Verse 1": [
                    "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C",
                    "Eb", "Ab/Eb", "Eb", "Ab/Eb", "Eb", "Bb/D", "Cm", "F7", "Bb",
                    "Ab/Bb", "Bbm7b5", "Bb7", "C7",
                ],
                "Chorus 1": [
                    "F", "Am", "Dm", "Bb|C7", "F", "Am", "Bb", "F#dim7",
                    "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                    "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                ],
                "Ending Tag": ["Fm", "Gm7", "Fm", "Gm7/F", "Fm", "Gm7/C"],
                "Verse 2": [
                    "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C", "Cm", "Gm7/C",
                    "Eb", "Ab/Eb", "Eb", "Ab/Eb", "Eb", "Bb/D", "Cm", "F7", "Bb",
                    "Ab/Bb", "Bbm7b5", "Bb7", "C7",
                ],
                "Chorus 2": [
                    "F", "Am", "Dm", "Bb|C7", "F", "Am", "Bb", "F#dim7",
                    "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                    "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                ],
                "Final Chorus": [
                    "F", "Am", "Dm", "Bb|C7", "F", "Am", "Bb", "F#dim7",
                    "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                    "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                ],
                "Outro": [
                    "F", "Am", "Dm", "Bb|C7", "F", "Am", "Bb", "F#dim7",
                    "Gm7", "C7/G", "Bbm6", "Bbm6/Db", "Edim7", "Gdim7",
                    "F", "Ebadd9/G", "Ab6", "Bb", "Cm7add4",
                ],
            },
            composer="Freddie Mercury",
            chart_status="practice_level_verified",
            section_order=[
                "Verse 1",
                "Chorus 1",
                "Ending Tag",
                "Verse 2",
                "Chorus 2",
                "Final Chorus",
                "Outro",
            ],
            extensions=_ext(
                default_bpm=65,
                default_groove="Rock groove",
                time_signature="4/4",
                vocal_showcase=True,
                queen_arena_anthem=True,
                repertoire_tags=[
                    "Queen",
                    "Freddie Mercury",
                    "Arena Rock",
                    "Power Ballad",
                    "Anthem",
                    "Karaoke Friendly",
                    "Vocal Showcase",
                ],
            ),
        ),
        _s(
            "Come Together",
            "The Beatles",
            "Rock",
            "Dm",
            {
                "Intro": ["Dm7"] * 4,
                "Verse 1": ["Dm", "Dm", "A", "G", "N.C."],
                "Chorus 1": ["Bm", "Bm/A", "G", "A", "N.C."],
                "Instrumental 1": ["Dm7"] * 4,
                "Solo": ["Dm"] * 4 + ["A"] * 4,
                "Outro (Fade)": ["Dm"] * 4,
            },
            composer="Lennon–McCartney",
            chart_status="practice_level_verified",
            section_order=[
                "Intro",
                "Verse 1",
                "Verse 2",
                "Chorus 1",
                "Instrumental 1",
                "Verse 3",
                "Chorus 2",
                "Instrumental 2",
                "Solo",
                "Instrumental 3",
                "Verse 4",
                "Final Chorus",
                "Outro (Fade)",
            ],
            extensions=_ext(
                default_bpm=82,
                default_groove="Rock groove",
                time_signature="4/4",
                riff_driven=True,
            ),
        ),
        _s(
            "Day Tripper",
            "The Beatles",
            "Rock",
            "E",
            {
                "Intro Riff": ["E7", "E", "E7", "E"],
                "Verse 1": ["E7", "E", "E7", "A7", "E", "E7"],
                "Pre-Chorus": ["F#", "A", "G#", "C#", "B"],
            },
            composer="Lennon–McCartney",
            chart_status="practice_level_verified",
            section_order=["Intro Riff", "Verse 1", "Pre-Chorus"],
            extensions=_ext(
                default_bpm=138,
                default_groove="Rock groove",
                time_signature="4/4",
                riff_driven=True,
            ),
        ),
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
            "Intro": ["Dm7", "G13", "Dm7", "G13"],
            "Verse 1": ["Dmaj9", "Bbdim7", "Am7", "D7b9"],
        }, composer="Antônio Carlos Jobim",
          extensions=_ext(
              default_bpm=120,
              default_groove="Bossa nova",
              jazz_standard_flagship=True,
              repertoire_tags=[
                  "Jazz Standard",
                  "Bossa Nova",
                  "Antônio Carlos Jobim",
                  "Brazilian Jazz",
                  "Improvisation",
                  "Essential Repertoire",
              ],
          ),
          chart_status="practice_level_verified"),
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
        _s("Autumn Leaves", "Jazz Standard", "Jazz", "Bm", {
            "Intro": ["Bm", "Bm"],
            "Verse 1": ["Em7", "A7", "Dmaj7", "Gmaj7", "C#m7b5", "F#7", "Bm", "Bm"],
        }, composer="Joseph Kosma · Johnny Mercer",
          extensions=_ext(
              default_bpm=82,
              default_groove="Ballad",
              repertoire_tags=[
                  "Jazz Standard",
                  "Improvisation Standard",
                  "Essential Jazz Repertoire",
              ],
          ),
          chart_status="practice_level_verified"),
        _s("Autumn Leaves", "Eric Clapton", "Jazz", "Bm", {
            "Intro": ["Bm", "Bm"],
            "Verse 1": ["Em7", "A7", "Dmaj7", "Gmaj7", "C#m7b5", "F#7", "Bm", "Bm"],
        }, composer="Joseph Kosma · Johnny Mercer",
          extensions=_ext(
              default_bpm=82,
              default_groove="Ballad",
              arrangement_notes="Eric Clapton jazz-ballad reading in B minor.",
              repertoire_tags=[
                  "Jazz Standard",
                  "Improvisation Standard",
                  "Essential Jazz Repertoire",
              ],
          ),
            chart_status="practice_level_verified"),
        _s(
            "Take On Me (MTV Unplugged Version)",
            "a-ha",
            "Pop",
            "G",
            {
                "Intro": ["Am", "D/F#", "G", "C|G/B"],
                "Verse 1": ["Am", "D/F#", "Em"],
                "Chorus": ["G", "D", "Em", "D/F#"],
            },
            composer="Magne Furuholmen, Morten Harket & Pål Waaktaar",
            extensions=_ext(
                default_bpm=64,
                default_groove="Ballad",
                repertoire_tags=[
                    "Acoustic",
                    "MTV Unplugged",
                    "Pop",
                    "Ballad",
                    "Folk Pop",
                ],
                acoustic_unplugged=True,
            ),
            chart_status="practice_level_verified",
        ),
        _s(
            "I Want It That Way",
            "Backstreet Boys",
            "Pop",
            "Em",
            {
                "Intro": ["Em", "C", "G"],
                "Verse 1": ["Em", "C", "G"],
                "Chorus 1": ["C", "D", "Em"],
            },
            composer="Max Martin & Andreas Carlsson",
            extensions=_ext(
                default_bpm=99,
                default_groove="Ballad",
                vocal_showcase=True,
                repertoire_tags=["Vocal Showcase", "Boy Band", "90s Pop"],
            ),
            chart_status="practice_level_verified",
        ),
        _s(
            "I Won't Say (I'm in Love)",
            "Disney · Hercules",
            "Pop",
            "C",
            {
                "Verse 1": ["C/G", "Fmaj7/G", "F6/G"],
                "Chorus 1": ["C", "G/C", "C"],
            },
            composer="Alan Menken & David Zippel",
            extensions=_ext(
                default_bpm=92,
                default_groove="Ballad",
                vocal_showcase=True,
                broadway_disney=True,
                repertoire_tags=["Disney", "Broadway", "Musical Theatre"],
            ),
            chart_status="practice_level_verified",
        ),
        _s(
            "How Far I'll Go",
            "Disney · Moana",
            "Pop",
            "E",
            {
                "Verse 1": ["E", "F#m", "C#m", "A"],
                "Chorus A": ["E", "B", "C#m", "A"],
            },
            composer="Lin-Manuel Miranda & Mark Mancina",
            extensions=_ext(
                default_bpm=84,
                default_groove="Ballad",
                vocal_showcase=True,
                broadway_disney=True,
                disney_ballad=True,
                repertoire_tags=["Disney", "Musical Theatre", "Inspirational Ballad"],
            ),
            chart_status="practice_level_verified",
        ),
        _s(
            "Blue Bossa",
            "Kenny Dorham",
            "Jazz",
            "Cm",
            {
                "Section A": ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"],
                "Section B": ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "Cm7"],
            },
            composer="Kenny Dorham",
            extensions=_ext(
                default_bpm=135,
                default_groove="Bossa nova",
                jazz_standard_flagship=True,
                repertoire_tags=[
                    "Jazz Standard",
                    "Bossa Nova",
                    "Latin Jazz",
                    "Improvisation Study",
                    "Essential Jazz Repertoire",
                ],
            ),
            chart_status="practice_level_verified",
        ),
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
        _s("All the Things You Are", "Jazz Standard", "Jazz", "Ab", {
            "A": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
            "B": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
            "A2": ["Dbm7", "Gb7", "Bmaj7", "Emaj7"],
            "C": ["Fm7", "Dm7", "G7", "Cmaj7"],
        }, composer="Jerome Kern · Oscar Hammerstein II",
          extensions=_ext(
              default_bpm=72,
              default_groove="Ballad",
              jazz_standard_flagship=True,
              repertoire_tags=[
                  "Jazz Standard",
                  "Essential Repertoire",
                  "Improvisation",
                  "Bebop",
              ],
          ),
          chart_status="practice_level_verified"),
        _s("All the Things You Are", "Jerome Kern", "Jazz", "Ab", {
            "A": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
            "C": ["Fm7", "Dm7", "G7", "Cmaj7"],
        }, composer="Jerome Kern · Oscar Hammerstein II",
          chart_status="practice_level_verified"),
        _s("Body and Soul", "Jazz Standard", "Jazz", "Db", {
            "A Section": ["Dbmaj7", "Ebm7", "E7", "Amaj7", "Abm7", "Db7", "Gbmaj7", "Gbmaj7"],
            "B Section": ["Fm7", "Bb7", "Ebmaj7", "Gm7b5", "C7", "Fm7", "Bb7", "Eb7"],
        }, composer="Johnny Green"),
        _s("Misty", "Erroll Garner", "Jazz", "Eb", {
            "A Section": ["Ebmaj7", "Bbm7", "Ebmaj7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7"],
            "B Section": ["Am7b5", "D7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
        }, composer="Erroll Garner"),
        _s("Satin Doll", "Duke Ellington", "Jazz", "C", {
            "A": ["Dm7|G7", "Dm7|G7", "Em7|A7", "Em7|A7"],
            "B (Bridge)": ["Gm7|C7", "Gm7|C7", "Fmaj7", "Fmaj7"],
            "Turnaround": ["Dm7|G7", "Em7|A7", "Am7|D7", "G7"],
        }, composer="Duke Ellington · Billy Strayhorn · Johnny Mercer",
          extensions=_ext(
              default_bpm=128,
              default_groove="Jazz swing",
              jazz_standard_flagship=True,
              repertoire_tags=["Jazz Standard", "Swing", "Duke Ellington", "Essential Standards"],
          ),
          chart_status="practice_level_verified"),
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
        *_jewish_traditional_catalog_songs(),
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
