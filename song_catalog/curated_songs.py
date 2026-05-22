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
) -> dict[str, Any]:
    return {
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
        ("Shape of You", "Ed Sheeran"): pack(
            "Bm",
            {
                "Intro": ["Bm", "Em", "G", "A"],
                "Verse": ["Bm", "Em", "G", "A"],
                "Pre-Chorus": ["Bm", "Em", "G", "A"],
                "Chorus": ["Bm", "Em", "G", "A"],
                "Bridge": ["Bm", "Em", "G", "A"],
                "Outro": ["Bm", "Em", "G", "A"],
            },
            {
                "Intro": ["Bm", "Em", "G", "A"],
                "Verse": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
                "Pre-Chorus": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
                "Chorus": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
                "Bridge": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
                "Outro": ["Bm", "Em", "G", "A"],
            },
            {
                "Intro": ["Bm7", "Em7", "Gmaj7", "Asus2"],
                "Verse": ["Bm7", "Em7", "Gmaj7", "Asus2", "Bm7", "Em7", "Gmaj7", "Asus2"],
                "Pre-Chorus": ["Bm7", "Em7", "Gmaj7", "Asus2", "Bm7", "Em7", "Gmaj7", "Asus2"],
                "Chorus": ["Bm7", "Em7", "Gmaj7", "Aadd9", "Bm7", "Em7", "Gmaj7", "Aadd9"],
                "Bridge": ["Bm7", "Em7", "Gmaj7", "Aadd9", "N.C.", "N.C.", "Bm7", "Em7"],
                "Outro": ["Bm7", "Em7", "Gmaj7", "Aadd9"],
            },
            status="practice_level_verified",
            lyric_cues={
                "Intro": ["percussion / marimba loop enters"],
                "Verse": ["syncopated vocal pickup over loop"],
                "Pre-Chorus": ["lift before hook — keep groove steady"],
                "Chorus": ["title-hook rhythm — lock the loop"],
                "Bridge": ["breakdown / vocal-only bars then loop returns"],
                "Outro": ["fade on main loop vamp"],
            },
            extensions=_ext(
                arrangement_notes=(
                    "Radio-accurate **Bm–Em–G–A** loop (one chord per bar, 4/4). "
                    "Recording key is C#m; transpose with Display Key as needed. "
                    "Default groove: pop syncopation ~96 BPM — keep the loop even."
                ),
                default_bpm=96,
                default_groove="Pop groove",
            ),
        ),
        ("Perfect", "Ed Sheeran"): pack("Ab",
            {
                "Intro": ["Ab", "Ab", "Fm", "Db"],
                "Verse": ["Ab", "Fm", "Db", "Eb", "Ab", "Fm", "Db", "Eb"],
                "Pre-Chorus": ["Fm", "Db", "Ab", "Eb", "Fm", "Db", "Ab", "Eb"],
                "Chorus": ["Ab", "Eb", "Fm", "Db", "Ab", "Eb", "Db", "Eb"],
                "Bridge": ["Fm", "Db", "Ab", "Eb", "Fm", "Db", "Ab", "Eb"],
                "Outro": ["Ab", "Eb", "Fm", "Db", "Ab"],
            },
            {
                "Intro": ["Ab", "Ab", "Fm7", "Dbadd9"],
                "Verse": ["Ab", "Fm7", "Dbadd9", "Eb", "Ab", "Fm7", "Dbadd9", "Eb"],
                "Pre-Chorus": ["Fm7", "Dbadd9", "Ab", "Eb/G", "Fm7", "Dbadd9", "Ab", "Eb"],
                "Chorus": ["Ab", "Eb/G", "Fm7", "Dbadd9", "Ab", "Eb/G", "Dbadd9", "Eb"],
                "Bridge": ["Fm7", "Dbadd9", "Ab", "Eb", "Fm7", "Dbadd9", "Ab", "Eb"],
                "Outro": ["Ab", "Eb/G", "Fm7", "Dbadd9", "Ab"],
            },
            {
                "Intro": ["Gadd9", "Gadd9", "Em9", "Cmaj9"],
                "Verse": ["Gadd9", "Em9", "Cmaj9", "D13sus", "Gadd9", "Em9", "Cmaj9", "D13sus"],
                "Pre-Chorus": ["Em9", "Cmaj9", "G/B", "D/A", "Em9", "Cmaj9", "G", "D13sus"],
                "Chorus": ["Gadd9", "D/F#", "Em9", "Cmaj9", "G/B", "D/A", "Cmaj9", "D13sus"],
                "Bridge": ["Em9", "Cmaj9", "G/B", "D13sus", "Em9", "Cmaj9", "G", "D13sus"],
                "Outro": ["Gadd9", "D/F#", "Em9", "Cmaj9", "Gadd9"],
            },
        ),
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
        ("Piano Man", "Billy Joel"): pack(
            "C",
            {
                "Intro (Harmonica)": [
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G",
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G",
                    "C", "C/B", "Am", "C/G", "F", "G", "C",
                    "C", "F/C", "C", "G",
                    "C", "F/C", "C", "G",
                ],
                "Verse": [
                    "C", "G/B", "F/A", "C/G", "F", "C/E", "D7", "G",
                    "C", "G/B", "F/A", "C/G", "F", "G", "C",
                ],
                "Verse (Memory)": [
                    "C", "C/B", "Am", "C/G", "F", "C/E", "D7", "G",
                    "C", "Em/B", "Am", "C/G", "F", "G", "C",
                ],
                "Verse (Extended Tag)": [
                    "C", "G/B", "F/A", "C/G", "F", "G", "C",
                    "F/C", "C", "G",
                ],
                "Harmonica Interlude": [
                    "C", "C/B", "Am", "C/G", "F", "G", "C",
                    "C", "F/C", "C", "G",
                ],
                "Bridge": [
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "D7", "G", "G/F", "C/E", "G/D",
                ],
                "Chorus": [
                    "C", "G/B", "F/A", "C/G", "F", "C/E", "D7", "G",
                    "C", "G/B", "F/A", "C/G", "F", "G", "C",
                ],
                "Instrumental": [
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "F",
                    "Am", "Am/G", "D7/F#", "D7", "G", "G/F", "C/E", "G/D",
                ],
                "Outro": [
                    "C", "G/B", "F/A", "C/G", "F", "G", "C",
                    "C", "F/C", "C", "G",
                    "C", "F/C", "C", "G",
                    "G/F", "C/E", "G/D", "C",
                ],
            },
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
            {
                "Intro (Harmonica)": [
                    "C", "C/B", "Am7", "C/G", "Fmaj7", "C/E", "D7", "G7",
                    "C", "C/B", "Am7", "C/G", "Fmaj7", "C/E", "D7", "G7",
                    "C", "C/B", "Am7", "C/G", "Fmaj7", "G11", "Cmaj7",
                    "C", "F/C", "Cmaj7", "G11",
                    "C", "F/C", "Cmaj7", "G11",
                ],
                "Verse": [
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "C/E", "D7", "G7",
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "G11", "Cmaj7",
                ],
                "Verse (Memory)": [
                    "C", "C/B", "Am7", "C/G", "Fmaj7", "C/E", "D7", "G7",
                    "C", "Em/B", "Am7", "C/G", "Fmaj7", "G11", "Cmaj7",
                ],
                "Verse (Extended Tag)": [
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "G11", "Cmaj7",
                    "F/C", "Cmaj7", "G11",
                ],
                "Harmonica Interlude": [
                    "C", "Em/B", "Am7", "C/G", "Fmaj7", "G11", "Cmaj7",
                    "C", "F/C", "Cmaj7", "G11",
                ],
                "Bridge": [
                    "Am7", "Am7/G", "D7/F#", "Fmaj7",
                    "Am7", "Am7/G", "D7/F#", "D7", "G7", "G7/F", "C/E", "G7/D",
                ],
                "Chorus": [
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "C/E", "D7", "G7",
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "G11", "Cmaj7",
                ],
                "Instrumental": [
                    "Am7", "Am7/G", "D7/F#", "Fmaj7",
                    "Am7", "Am7/G", "D7/F#", "Fmaj7",
                    "Am7", "Am7/G", "D7/F#", "D7", "G7", "G7/F", "C/E", "G7/D",
                ],
                "Outro": [
                    "C", "G/B", "F/A", "C/G", "Fmaj7", "G11", "Cmaj7",
                    "C", "F/C", "Cmaj7", "G11",
                    "C", "F/C", "Cmaj7", "G11",
                    "G7/F", "C/E", "G7/D", "Cmaj7",
                ],
            },
            status="practice_needs_review",
        ),
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
        ("Don't Stop Believin'", "Journey"): pack("E",
            {
                "Intro / Piano Loop": ["E", "B", "C#m", "A"],
                "Verse": ["E", "B", "C#m", "A", "E", "B", "C#m", "A"],
                "Pre-Chorus": ["A", "E", "B", "C#m", "A", "E", "B", "B"],
                "Chorus": ["E", "B", "A", "E", "A", "E", "B", "B"],
                "Final Chorus": ["E", "B", "A", "E", "A", "E", "B", "E"],
            },
            {
                "Intro / Piano Loop": ["E", "B/D#", "C#m7", "Aadd9"],
                "Verse": ["E", "B/D#", "C#m7", "Aadd9", "E", "B/D#", "C#m7", "Aadd9"],
                "Pre-Chorus": ["Aadd9", "E/G#", "B", "C#m7", "Aadd9", "E/G#", "B", "B"],
                "Chorus": ["E", "B/D#", "Aadd9", "E/G#", "Aadd9", "E/G#", "B", "B"],
                "Final Chorus": ["E", "B/D#", "Aadd9", "E/G#", "Aadd9", "E/G#", "B", "E"],
            },
            {
                "Intro / Piano Loop": ["Eadd9", "B/D#", "C#m9", "Amaj9"],
                "Verse": ["Eadd9", "B/D#", "C#m9", "Amaj9", "Eadd9", "B/D#", "C#m9", "Amaj9"],
                "Pre-Chorus": ["Amaj9", "E/G#", "B13sus", "C#m9", "Amaj9", "E/G#", "B13sus", "B13"],
                "Chorus": ["Eadd9", "B/D#", "Amaj9", "E/G#", "Amaj9", "E/G#", "B13sus", "B13"],
                "Final Chorus": ["Eadd9", "B/D#", "Amaj9", "E/G#", "Amaj9", "E/G#", "B13sus", "Eadd9"],
            },
        ),
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
        ("Blue Bossa", "Kenny Dorham"): pack("Cm",
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
        row = v(
            title,
            artist,
            ref["genre"],
            ref["key"],
            beg,
            inter,
            advanced=inter,
            composer=composer,
            lyric_cues=lyric_cues_for_reference(title, artist),
            guitar_tabs=ref.get("guitar_tabs"),
            notes=ref.get("arrangement_notes"),
            chart_status=status,
        )
        if ref.get("default_bpm"):
            row["extensions"] = {
                **(row.get("extensions") or {}),
                "default_bpm": int(ref["default_bpm"]),
            }
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
        _s("Shape of You", "Ed Sheeran", "Pop", "Bm", {
            "Intro": ["Bm", "Em", "G", "A"],
            "Verse": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
            "Pre-Chorus": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
            "Chorus": ["Bm", "Em", "G", "A", "Bm", "Em", "G", "A"],
            "Bridge": ["Bm", "Em", "G", "A"],
            "Outro": ["Bm", "Em", "G", "A"],
        }),
        _s("Perfect", "Ed Sheeran", "Pop", "G", {
            "Intro": ["G", "G", "Em7", "Cadd9"],
            "Verse": ["G", "Em7", "Cadd9", "D", "G", "Em7", "Cadd9", "D"],
            "Pre-Chorus": ["Em7", "Cadd9", "G", "D/F#", "Em7", "Cadd9", "G", "D"],
            "Chorus": ["G", "D/F#", "Em7", "Cadd9", "G", "D/F#", "Cadd9", "D"],
            "Bridge": ["Em7", "Cadd9", "G", "D", "Em7", "Cadd9", "G", "D"],
        }),
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
        _s("Across the Universe", "The Beatles", "Rock", "D", {
            "Verse": ["D", "Bm", "F#m", "A"],
            "Chorus": ["G", "A", "D", "D"],
            "Bridge": ["G", "D", "A", "A"],
        }, composer="Lennon–McCartney"),
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
        _s("Don't Stop Believin'", "Journey", "Rock", "E", {
            "Intro / Piano Loop": ["E", "B/D#", "C#m7", "Aadd9"],
            "Verse": ["E", "B/D#", "C#m7", "Aadd9", "E", "B/D#", "C#m7", "Aadd9"],
            "Pre-Chorus": ["Aadd9", "E/G#", "B", "C#m7", "Aadd9", "E/G#", "B", "B"],
            "Chorus": ["E", "B/D#", "Aadd9", "E/G#", "Aadd9", "E/G#", "B", "B"],
            "Final Chorus": ["E", "B/D#", "Aadd9", "E/G#", "Aadd9", "E/G#", "B", "E"],
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
        _s("Ode to Joy", "Beethoven", "Classical", "D", {
            "Main Theme": ["D", "A", "D", "G", "D", "A", "D"],
            "Practice Variation": ["D", "G", "A", "D"],
        }, composer="Ludwig van Beethoven"),
    ]
    return _apply_requested_verified_records(_apply_core_chart_overrides(records))
