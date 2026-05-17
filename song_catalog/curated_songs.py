"""Hand-curated songs with practice-level harmony (priority accuracy for listed artists)."""

from __future__ import annotations

from typing import Any


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


def _core_chart_overrides() -> dict[tuple[str, str], dict[str, Any]]:
    """Explicit musician-practice charts for the trusted core library.

    One list item equals one bar. Repeated chords intentionally represent
    repeated measures so the chart renderer and backing track share the same
    harmonic rhythm.
    """

    def pack(key, beginner, intermediate, advanced=None, status="trusted"):
        return {
            "key": key,
            "sections": intermediate,
            "chart_versions": _levels(
                beginner=beginner,
                intermediate=intermediate,
                advanced=advanced or intermediate,
            ),
            "chart_status": status,
        }

    return {
        ("Say", "John Mayer"): pack("Bb",
            {
                "Intro": ["Bb", "F", "Gm", "Eb"],
                "Verse": ["Bb", "F", "Gm", "Eb", "Bb", "F", "Eb", "Eb"],
                "Pre-Chorus": ["Cm", "Eb", "Bb", "F"],
                "Chorus": ["Bb", "F", "Eb", "Bb", "Cm", "Eb", "F", "Bb"],
                "Bridge": ["Gm", "F", "Eb", "Bb", "Cm", "Eb", "F", "F"],
                "Outro": ["Bb", "F", "Eb", "Bb"],
            },
            {
                "Intro": ["Bb", "F/A", "Gm7", "Ebadd9"],
                "Verse": ["Bb", "F/A", "Gm7", "Ebadd9", "Bb", "F/A", "Ebadd9", "Ebadd9"],
                "Pre-Chorus": ["Cm7", "Eb", "Bb/D", "F"],
                "Chorus": ["Bb", "F/A", "Ebadd9", "Bb/D", "Cm7", "Eb", "F", "Bb"],
                "Bridge": ["Gm7", "F/A", "Ebadd9", "Bb/D", "Cm7", "Eb", "F", "F"],
                "Outro": ["Bb", "F/A", "Ebadd9", "Bb"],
            },
            {
                "Intro": ["Bbadd9", "F/A", "Gm9", "Ebmaj9"],
                "Verse": ["Bbadd9", "F/A", "Gm9", "Ebmaj9", "Bb/D", "F/A", "Ebmaj9", "Ebmaj9"],
                "Pre-Chorus": ["Cm9", "Ebmaj7", "Bb/D", "F13sus"],
                "Chorus": ["Bbadd9", "F/A", "Ebmaj9", "Bb/D", "Cm9", "Ebmaj7", "F13sus", "Bbadd9"],
                "Bridge": ["Gm9", "F/A", "Ebmaj9", "Bb/D", "Cm9", "Ebmaj7", "F13sus", "F13"],
                "Outro": ["Bbadd9", "F/A", "Ebmaj9", "Bbadd9"],
            },
        ),
        ("Gravity", "John Mayer"): pack("G",
            {
                "Intro / Verse Groove": ["G", "C", "G", "C"],
                "Verse": ["G", "C", "G", "C", "G", "C", "G", "C"],
                "Chorus": ["Em", "C", "G", "D", "Em", "C", "G", "D"],
                "Solo": ["G7", "C7", "G7", "G7", "C7", "C7", "G7", "D7"],
                "Outro": ["G", "C", "G", "C"],
            },
            {
                "Intro / Verse Groove": ["G", "C/G", "G", "C/G"],
                "Verse": ["G", "C/G", "G", "C/G", "G", "C/G", "G", "C/G"],
                "Chorus": ["Em7", "Cadd9", "G/D", "D", "Em7", "Cadd9", "G", "D"],
                "Solo": ["G7", "C7", "G7", "G7", "C7", "C7", "G7", "D7"],
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
        ("Shape of You", "Ed Sheeran"): pack("C#m",
            {
                "Main Loop": ["C#m", "F#m", "A", "B"],
                "Verse": ["C#m", "F#m", "A", "B", "C#m", "F#m", "A", "B"],
                "Pre-Chorus": ["C#m", "F#m", "A", "B", "C#m", "F#m", "A", "B"],
                "Chorus": ["C#m", "F#m", "A", "B", "C#m", "F#m", "A", "B"],
                "Bridge / Breakdown": ["C#m", "F#m", "A", "B"],
            },
            {
                "Main Loop": ["C#m7", "F#m7", "Aadd9", "B"],
                "Verse": ["C#m7", "F#m7", "Aadd9", "B", "C#m7", "F#m7", "Aadd9", "B"],
                "Pre-Chorus": ["C#m7", "F#m7", "Aadd9", "B", "C#m7", "F#m7", "Aadd9", "B"],
                "Chorus": ["C#m7", "F#m7", "Aadd9", "B", "C#m7", "F#m7", "Aadd9", "B"],
                "Bridge / Breakdown": ["C#m7", "F#m7", "Aadd9", "B"],
            },
            {
                "Main Loop": ["C#m9", "F#m9", "Amaj9", "B13sus"],
                "Verse": ["C#m9", "F#m9", "Amaj9", "B13sus", "C#m9", "F#m9", "Amaj9", "B13sus"],
                "Pre-Chorus": ["C#m9", "F#m9", "Amaj9", "B13sus", "C#m9", "F#m9", "Amaj9", "B13sus"],
                "Chorus": ["C#m9", "F#m9", "Amaj9", "B13sus", "C#m9", "F#m9", "Amaj9", "B13sus"],
                "Bridge / Breakdown": ["C#m9", "F#m9", "Amaj9", "B13sus"],
            },
        ),
        ("Perfect", "Ed Sheeran"): pack("G",
            {
                "Intro": ["G", "G", "Em", "C"],
                "Verse": ["G", "Em", "C", "D", "G", "Em", "C", "D"],
                "Pre-Chorus": ["Em", "C", "G", "D", "Em", "C", "G", "D"],
                "Chorus": ["G", "D", "Em", "C", "G", "D", "C", "D"],
                "Bridge": ["Em", "C", "G", "D", "Em", "C", "G", "D"],
                "Outro": ["G", "D", "Em", "C", "G"],
            },
            {
                "Intro": ["G", "G", "Em7", "Cadd9"],
                "Verse": ["G", "Em7", "Cadd9", "D", "G", "Em7", "Cadd9", "D"],
                "Pre-Chorus": ["Em7", "Cadd9", "G", "D/F#", "Em7", "Cadd9", "G", "D"],
                "Chorus": ["G", "D/F#", "Em7", "Cadd9", "G", "D/F#", "Cadd9", "D"],
                "Bridge": ["Em7", "Cadd9", "G", "D", "Em7", "Cadd9", "G", "D"],
                "Outro": ["G", "D/F#", "Em7", "Cadd9", "G"],
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
        ("Piano Man", "Billy Joel"): pack("C",
            {
                "Intro / Harmonica": ["C", "G", "Am", "F", "C", "G", "F", "G"],
                "Verse": ["C", "G", "Am", "F", "C", "G", "F", "G"],
                "Pre-Chorus": ["F", "C", "Dm", "G", "F", "C", "D", "G"],
                "Chorus": ["C", "G", "Am", "F", "C", "G", "C", "G"],
                "Solo": ["C", "G", "Am", "F", "C", "G", "F", "G"],
                "Outro": ["C", "F", "C", "G", "C", "F", "C", "G"],
            },
            {
                "Intro / Harmonica": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
                "Verse": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
                "Pre-Chorus": ["F", "C/E", "Dm7", "G7", "F", "C/E", "D7/F#", "G7"],
                "Chorus": ["C", "G/B", "Am7", "C/G", "F", "G7", "C", "G7"],
                "Solo": ["C", "G/B", "Am7", "C/G", "F", "C/E", "Dm7", "G7"],
                "Outro": ["C", "F", "C/E", "G7", "C", "F", "C/G", "G7"],
            },
            {
                "Intro / Harmonica": ["Cadd9", "G/B", "Am9", "C/G", "Fmaj9", "C/E", "Dm9", "G13"],
                "Verse": ["Cadd9", "G/B", "Am9", "C/G", "Fmaj9", "C/E", "Dm9", "G13"],
                "Pre-Chorus": ["Fmaj9", "C/E", "Dm9", "G13", "Fmaj9", "C/E", "D13/F#", "G13"],
                "Chorus": ["Cadd9", "G/B", "Am9", "C/G", "Fmaj9", "G13", "Cadd9", "G13"],
                "Solo": ["Cadd9", "G/B", "Am9", "C/G", "Fmaj9", "C/E", "Dm9", "G13"],
                "Outro": ["Cadd9", "Fmaj9", "C/E", "G13", "Cadd9", "Fmaj9", "C/G", "G13"],
            },
        ),
        ("Turn the Lights Back On", "Billy Joel"): pack("C",
            {
                "Intro": ["C", "Am", "F", "G"],
                "Verse": ["C", "Am", "F", "G", "C", "Am", "F", "G"],
                "Pre-Chorus": ["Dm", "G", "Em", "Am", "F", "G", "C", "G"],
                "Chorus": ["C", "Am", "F", "G", "C", "Am", "F", "G"],
                "Bridge": ["F", "G", "Em", "Am", "Dm", "G", "C", "G"],
            },
            {
                "Intro": ["C", "Am7", "Fmaj7", "G"],
                "Verse": ["C", "Am7", "Fmaj7", "G", "C/E", "Am7", "Fmaj7", "G"],
                "Pre-Chorus": ["Dm7", "G", "Em7", "Am7", "Fmaj7", "G", "C", "G"],
                "Chorus": ["C", "Am7", "Fmaj7", "G", "C/E", "Am7", "Fmaj7", "G"],
                "Bridge": ["Fmaj7", "G", "Em7", "Am7", "Dm7", "G", "C", "G"],
            },
            {
                "Intro": ["Cmaj9", "Am9", "Fmaj9", "G13sus"],
                "Verse": ["Cmaj9", "Am9", "Fmaj9", "G13sus", "C/E", "Am9", "Fmaj9", "G13sus"],
                "Pre-Chorus": ["Dm9", "G13", "Em9", "Am9", "Fmaj9", "G13sus", "Cmaj9", "G13"],
                "Chorus": ["Cmaj9", "Am9", "Fmaj9", "G13sus", "C/E", "Am9", "Fmaj9", "G13sus"],
                "Bridge": ["Fmaj9", "G13", "Em9", "Am9", "Dm9", "G13", "Cmaj9", "G13"],
            },
        ),
        ("Just the Way You Are", "Billy Joel"): pack("D",
            {
                "Intro": ["D", "Bm", "G", "A"],
                "Verse": ["D", "Bm", "G", "Gm", "D", "B7", "Em", "A"],
                "Chorus": ["G", "Gm", "D", "B7", "Em", "A", "D", "A"],
                "Bridge": ["Bb", "Eb", "Am", "D7", "G", "A", "D", "A"],
            },
            {
                "Intro": ["Dmaj7", "Bm7", "Gmaj7", "A7"],
                "Verse": ["Dmaj7", "Bm7", "Gmaj7", "Gm6", "D/F#", "B7", "Em7", "A7"],
                "Chorus": ["Gmaj7", "Gm6", "D/F#", "B7", "Em7", "A7", "Dmaj7", "A7"],
                "Bridge": ["Bbmaj7", "Eb13", "Am7", "D7", "Gmaj7", "A7", "Dmaj7", "A7"],
            },
            {
                "Intro": ["Dmaj9", "Bm9", "Gmaj9", "A13"],
                "Verse": ["Dmaj9", "Bm9", "Gmaj9", "Gm6", "D/F#", "B7b9", "Em9", "A13"],
                "Chorus": ["Gmaj9", "Gm6", "D/F#", "B7b9", "Em9", "A13", "Dmaj9", "A13"],
                "Bridge": ["Bbmaj9", "Eb13", "Am9", "D13", "Gmaj9", "A13", "Dmaj9", "A13"],
            },
        ),
        ("Vienna", "Billy Joel"): pack("Bb",
            {
                "Intro": ["Bb", "Bb", "Eb", "F"],
                "Verse": ["Bb", "Dm", "Gm", "Eb", "Bb", "F", "Bb", "F"],
                "Pre-Chorus": ["Eb", "F", "Dm", "Gm", "Cm", "F", "Bb", "F"],
                "Chorus": ["Eb", "F", "Dm", "Gm", "Cm", "F", "Bb", "F"],
                "Bridge": ["Gm", "Dm", "Eb", "Bb", "Cm", "F", "Bb", "F"],
            },
            {
                "Intro": ["Bb", "Bb/D", "Ebmaj7", "F7"],
                "Verse": ["Bb", "Dm7", "Gm7", "Ebmaj7", "Bb/F", "F7", "Bb", "F7"],
                "Pre-Chorus": ["Ebmaj7", "F/Eb", "Dm7", "Gm7", "Cm7", "F7", "Bb", "F7"],
                "Chorus": ["Ebmaj7", "F7", "Dm7", "Gm7", "Cm7", "F7", "Bb", "F7"],
                "Bridge": ["Gm7", "Dm7/F", "Ebmaj7", "Bb/D", "Cm7", "F7", "Bb", "F7"],
            },
            {
                "Intro": ["Bbmaj9", "Bb/D", "Ebmaj9", "F13"],
                "Verse": ["Bbmaj9", "Dm9", "Gm9", "Ebmaj9", "Bb/F", "F13", "Bbmaj9", "F13"],
                "Pre-Chorus": ["Ebmaj9", "F13/Eb", "Dm9", "Gm9", "Cm9", "F13", "Bbmaj9", "F13"],
                "Chorus": ["Ebmaj9", "F13", "Dm9", "Gm9", "Cm9", "F13", "Bbmaj9", "F13"],
                "Bridge": ["Gm9", "Dm9/F", "Ebmaj9", "Bb/D", "Cm9", "F13", "Bbmaj9", "F13"],
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
                "Pre-Chorus": ["Bb", "Bb", "F", "F", "C7", "C7", "F", "F"],
                "Chorus": ["F", "Eb", "Bb", "F", "F", "Eb", "Bb", "F"],
                "Outro Vamp": ["F", "Eb", "Bb", "F", "F", "Eb", "Bb", "F"],
            },
            {
                "Intro": ["F", "C/E", "C7", "F"],
                "Verse": ["F", "C/E", "C7", "F", "Bb", "F/A", "C7", "F"],
                "Pre-Chorus": ["Bb", "Bb", "F/A", "F", "C7", "C7", "F", "F"],
                "Chorus": ["F", "Eb", "Bb", "F/A", "F", "Eb", "Bb", "F"],
                "Outro Vamp": ["F", "Eb", "Bb", "F", "F", "Eb", "Bb", "F"],
            },
            {
                "Intro": ["Fadd9", "C/E", "C13", "Fadd9"],
                "Verse": ["Fadd9", "C/E", "C13", "Fadd9", "Bbmaj9", "F/A", "C13", "Fadd9"],
                "Pre-Chorus": ["Bbmaj9", "Bbmaj9", "F/A", "Fadd9", "C13", "C13", "Fadd9", "Fadd9"],
                "Chorus": ["Fadd9", "Ebadd9", "Bbmaj9", "F/A", "Fadd9", "Ebadd9", "Bbmaj9", "Fadd9"],
                "Outro Vamp": ["Fadd9", "Ebadd9", "Bbmaj9", "Fadd9", "Fadd9", "Ebadd9", "Bbmaj9", "Fadd9"],
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
                "A Section": ["F", "F", "G7", "G7", "Gm", "C7", "F", "F"],
                "B Section": ["Gb", "Gb", "B7", "B7", "F#m", "B7", "Gm", "C7"],
                "Final A / Outro": ["Gm", "C7", "F", "F"],
            },
            {
                "Intro": ["Gm7", "C7", "Gm7", "C7"],
                "A Section": ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "C7", "Fmaj7", "Fmaj7"],
                "B Section": ["Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "B7", "Gm7", "C7"],
                "Final A / Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
            },
            {
                "Intro": ["Gm9", "C13", "Gm9", "C13"],
                "A Section": ["Fmaj9", "Fmaj9", "G13", "G13", "Gm9", "C13", "Fmaj9", "Fmaj9"],
                "B Section": ["Gbmaj9", "Gbmaj9", "B13", "B13", "F#m9", "B13", "Gm9", "C13"],
                "Final A / Outro": ["Gm9", "C13", "Fmaj9", "F6add9"],
            },
        ),
        ("Wave", "Antonio Carlos Jobim"): pack("D",
            {
                "Intro": ["D", "D", "D", "D"],
                "A Section": ["D", "Bbdim7", "Am", "D7", "G", "Gm", "D", "A7"],
                "B Section": ["Em", "A7", "D", "D", "Fm", "Bb7", "Eb", "A7"],
                "Final A / Outro": ["D", "Bbdim7", "Am", "D7", "G", "Gm", "D", "A7"],
            },
            {
                "Intro": ["Dmaj7", "Dmaj7", "Dmaj7", "Dmaj7"],
                "A Section": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "F#m7", "B7b9"],
                "B Section": ["Em9", "A13", "Dmaj9", "Dmaj9", "Fm9", "Bb13", "Ebmaj9", "A7b13"],
                "Final A / Outro": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "Dmaj9", "A13"],
            },
            {
                "Intro": ["Dmaj9", "D6add9", "Dmaj9", "D6add9"],
                "A Section": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "F#m9", "B7b9"],
                "B Section": ["Em9", "A13", "Dmaj9", "D6add9", "Fm9", "Bb13", "Ebmaj9", "A7b13"],
                "Final A / Outro": ["Dmaj9", "Bbdim7", "Am9", "D13", "Gmaj9", "Gm6", "Dmaj9", "A13"],
            },
        ),
        ("Blue Bossa", "Kenny Dorham"): pack("Cm",
            {
                "A Section": ["Cm", "Fm", "Dm7b5", "G7", "Cm", "Cm"],
                "B Section": ["Ebm", "Ab7", "Db", "Db", "Dm7b5", "G7", "Cm", "G7"],
            },
            {
                "A Section": ["Cm7", "Fm7", "Dm7b5", "G7", "Cm7", "Cm7"],
                "B Section": ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "G7"],
            },
            {
                "A Section": ["Cm9", "Fm9", "Dm7b5", "G7b9", "Cm9", "Cm9"],
                "B Section": ["Ebm9", "Ab13", "Dbmaj9", "Dbmaj9", "Dm7b5", "G7b9", "Cm9", "G7b9"],
            },
        ),
        ("Autumn Leaves", "Jazz Standard"): pack("Gm",
            {
                "Intro": ["Am7b5", "D7", "Gm", "Gm"],
                "A Section": ["Cm", "F7", "Bb", "Eb", "Am7b5", "D7", "Gm", "Gm"],
                "B Section": ["Cm", "F7", "Bb", "Eb", "Am7b5", "D7", "Gm", "D7"],
            },
            {
                "Intro": ["Am7b5", "D7b9", "Gm7", "Gm7"],
                "A Section": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7b9", "Gm7", "Gm7"],
                "B Section": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7b9", "Gm7", "D7b9"],
            },
            {
                "Intro": ["Am7b5", "D7b9", "Gm9", "Gm9"],
                "A Section": ["Cm9", "F13", "Bbmaj9", "Ebmaj9", "Am7b5", "D7b9", "Gm9", "Gm9"],
                "B Section": ["Cm9", "F13", "Bbmaj9", "Ebmaj9", "Am7b5", "D7b9", "Gm9", "D7b9"],
            },
        ),
        ("Fly Me to the Moon", "Bart Howard"): pack("C",
            {
                "A Section": ["Am", "Dm", "G7", "C", "F", "Bm7b5", "E7", "Am"],
                "B Section": ["Dm", "G7", "C", "A7", "Dm", "G7", "C", "E7"],
                "Tag": ["Dm", "G7", "C", "C"],
            },
            {
                "A Section": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
                "B Section": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "E7"],
                "Tag": ["Dm7", "G7", "Cmaj7", "Cmaj7"],
            },
            {
                "A Section": ["Am9", "Dm9", "G13", "Cmaj9", "Fmaj9", "Bm7b5", "E7b9", "Am9"],
                "B Section": ["Dm9", "G13", "Cmaj9", "A7b9", "Dm9", "G13", "Cmaj9", "E7b9"],
                "Tag": ["Dm9", "G13", "Cmaj9", "C6add9"],
            },
        ),
    }


def _apply_core_chart_overrides(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overrides = _core_chart_overrides()
    out = []
    for row in records:
        patch = overrides.get((row["title"], row["artist"]))
        if patch:
            row = {**row, **patch}
        out.append(row)
    return out


def curated_song_records() -> list[dict[str, Any]]:
    records = [
        # --- John Mayer / Pop foundations ---
        _s("Say", "John Mayer", "Pop", "Bb", {
            "Intro": ["Bb", "F/A", "Gm7", "Ebadd9"],
            "Verse": ["Bb", "F/A", "Gm7", "Ebadd9", "Bb", "F/A", "Ebadd9", "Ebadd9"],
            "Pre-Chorus": ["Cm7", "Eb", "Bb/D", "F"],
            "Chorus": ["Bb", "F/A", "Ebadd9", "Bb/D", "Cm7", "Eb", "F", "Bb"],
            "Bridge": ["Gm7", "F/A", "Ebadd9", "Bb/D", "Cm7", "Eb", "F", "F"],
            "Outro / Final Chorus": ["Bb", "F/A", "Ebadd9", "Bb"],
        }, guitar_tabs={"Bb": "x13331", "F": "133211", "Gm": "355333", "Eb": "x68886", "Gm7": "353333"}),
        _s("Gravity", "John Mayer", "Pop", "G", {
            "Intro / Verse Groove": ["G", "C/G", "G", "C/G"],
            "Verse": ["G", "C/G", "G", "C/G", "G", "C/G", "G", "C/G"],
            "Chorus / Lift": ["Em7", "Cadd9", "G/D", "D", "Em7", "Cadd9", "G", "D"],
            "Solo Section": ["G7", "C7", "G7", "G7", "C7", "C7", "G7", "D7"],
            "Outro Vamp": ["G", "C/G", "G", "C/G"],
        }, guitar_tabs={"G": "320003", "C": "x32010", "Em": "022000", "D": "xx0232", "G7": "320001", "C7": "x32310", "D7": "xx0212"}),
        _s("Waiting on the World to Change", "John Mayer", "Pop", "D", {
            "Verse": ["D", "Bm", "G", "A"],
            "Chorus": ["D", "Bm", "G", "A"],
            "Bridge": ["Em", "G", "D", "A"],
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
        _s("Shape of You", "Ed Sheeran", "Pop", "C#m", {
            "Intro / Main Loop": ["C#m7", "F#m7", "A", "B"],
            "Verse": ["C#m7", "F#m7", "A", "B", "C#m7", "F#m7", "A", "B"],
            "Pre-Chorus": ["C#m7", "F#m7", "A", "B", "C#m7", "F#m7", "A", "B"],
            "Chorus": ["C#m7", "F#m7", "A", "B", "C#m7", "F#m7", "A", "B"],
            "Bridge": ["C#m7", "F#m7", "A", "B"],
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
        _s("Piano Man", "Billy Joel", "Pop", "C", {
            "Intro (Pickup / Band In)": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
            "Verse (Story)": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
            "Pre-Chorus (La-da Lift)": ["F", "C/E", "Dm7", "G7", "F", "C/E", "D7/F#", "G7"],
            "Chorus (Sing Us a Song)": ["C", "G/B", "Am7", "C/G", "F", "G7", "C", "G7"],
            "Instrumental / Harmonica Solo": ["C", "G/B", "Am7", "C/G", "F", "C/E", "Dm7", "G7"],
            "Final Chorus / Outro": ["C", "F", "C/E", "G7", "C", "F", "C/G", "G7"],
        }, composer="Billy Joel"),
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
        _s("Uptown Girl", "Billy Joel", "Pop", "E", {
            "Verse": ["E", "A", "E", "B", "E", "A", "E", "B"],
            "Chorus": ["E", "B", "A", "B", "E", "B", "A", "B"],
            "Bridge": ["C#m", "G#m", "A", "B", "E", "B", "A", "B"],
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
        _s("One Note Samba", "Antonio Carlos Jobim", "Jazz", "Bb", {
            "A Section": ["Bbmaj7", "Bdim7", "Cm7", "F7", "Cm7", "F7", "Bbmaj7", "F7"],
            "B Section": ["Dm7", "G7", "Cm7", "F7", "Dm7", "G7", "Cm7", "F7"],
            "Final A": ["Bbmaj7", "Bdim7", "Cm7", "F7", "Bbmaj7", "Bbmaj7"],
        }, composer="Antonio Carlos Jobim"),
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
        _s("Summer Samba", "Marcos Valle", "Jazz", "F", {
            "A Section": ["Fmaj7", "Gm7", "Am7", "Gm7", "Fmaj7", "Gm7", "Am7", "D7"],
            "B Section": ["Gm7", "C7", "Fmaj7", "Dm7", "Gm7", "C7", "Fmaj7", "C7"],
        }, composer="Marcos Valle"),

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
    return _apply_core_chart_overrides(records)
