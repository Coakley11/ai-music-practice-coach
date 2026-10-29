"""Key Cycling keeps authoritative chord spelling (C#m never reads Dbm).

The Spelling setting names the cycling key. It used to respell every chord
root and bass by pitch class as well, so C#m showed as Dbm and E/G# as E/Ab on
Current / Next Chord and the cycle Lead Sheet, even with nothing transposed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backing_key_cycle import (
    apply_spelling_prefs_to_key,
    cycle_concert_practice_key,
    default_spelling_prefs,
    project_cycle_display_chord,
    project_follow_timeline_for_display,
    spell_key_tonic,
)
from backing_key_cycle_handoff import build_cycle_lead_sheet_html

SRC = (Path(__file__).resolve().parents[1] / "backing_key_cycle.py").read_text(encoding="utf-8")


def _session(**extra):
    s = {"instrument": "Piano", "backing_key_spelling_prefs": default_spelling_prefs()}
    s.update(extra)
    return s


def _tenor(**extra):
    return _session(
        instrument="Saxophone",
        selected_transposing_instrument="Tenor saxophone (Bb)",
        show_chart_in_instrument_key=True,
        **extra,
    )


@pytest.mark.parametrize(
    "pc,want",
    [(1, "C#"), (3, "Eb"), (6, "F#"), (8, "G#"), (10, "Bb"), (0, "C"), (9, "A")],
)
def test_minor_key_tonic_default_names(pc: int, want: str) -> None:
    assert spell_key_tonic(pc, "minor", default_spelling_prefs()) == want


def test_minor_keys_with_one_real_name_ignore_the_flat_preference() -> None:
    prefs = dict(default_spelling_prefs(), **{"C#/Db": "Db", "F#/Gb": "Gb", "G#/Ab": "Ab"})
    assert [spell_key_tonic(pc, "minor", prefs) for pc in (1, 6, 8)] == ["C#", "F#", "G#"]
    assert [spell_key_tonic(pc, "major", prefs) for pc in (1, 6, 8)] == ["Db", "Gb", "Ab"]


def test_genuine_minor_choices_follow_their_own_pair() -> None:
    prefs = dict(default_spelling_prefs(), **{"D#/Eb": "D#", "A#/Bb": "A#"})
    assert spell_key_tonic(3, "minor", prefs) == "D#"
    assert spell_key_tonic(10, "minor", prefs) == "A#"


def test_twelve_minor_cycle_keys_are_conventional() -> None:
    seq = [cycle_concert_practice_key("Am", semitones=i) for i in range(12)]
    assert seq == ["Am", "Bbm", "Bm", "Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m"]


def test_key_names_respelled_by_mode() -> None:
    prefs = default_spelling_prefs()
    assert apply_spelling_prefs_to_key("Dbm", prefs) == "C#m"
    assert apply_spelling_prefs_to_key("C#", prefs) == "Db"
    assert apply_spelling_prefs_to_key("A#m", prefs) == "Bbm"
    assert apply_spelling_prefs_to_key("G#m", prefs) == "G#m"


@pytest.mark.parametrize("chord", ["C#m", "C#m7", "E/G#", "G#m7b5", "A#dim7", "F#7#9", "Dbmaj7", "Bb7/D"])
def test_concert_chords_keep_their_spelling(chord: str) -> None:
    s = _session(_kc_temporary_playback_key="A")
    assert project_cycle_display_chord(s, chord, sounding_key="A") == chord
    tl = project_follow_timeline_for_display(s, [{"chord": chord, "start_time": 0, "end_time": 1}], sounding_key="A")
    assert tl[0]["chord"] == chord


def test_written_projection_spells_in_the_reading_key() -> None:
    s = _tenor()
    # Concert A major: C#m (iii) and E/G# read as D#m and F#/A# for tenor in B.
    assert project_cycle_display_chord(s, "C#m", sounding_key="A") == "D#m"
    assert project_cycle_display_chord(s, "E/G#", sounding_key="A") == "F#/A#"
    # Concert Am reads Bm, never C#m.
    assert project_cycle_display_chord(s, "Am7", sounding_key="Am") == "Bm7"


def test_cycle_sheet_reading_key_and_chords_agree() -> None:
    s = _tenor()
    html = build_cycle_lead_sheet_html(
        sounding_key="Am",
        sections={"A": ["Am7", "Dm7", "Bm7b5", "E7#5"]},
        song_name="Blue Bossa",
        session=s,
        chart_display_key="Bm",
    )
    assert "Reading Bm" in html and "Sounding Am" in html
    assert "C#m7" not in html.split("Reading")[1][:40]
    for chord in ("Bm7", "Em7", "C#m7b5", "F#7#5"):
        assert chord in html


def test_browser_never_respells_chords_by_pitch_class() -> None:
    assert "__kcApplySpellingPrefs" not in SRC
    js = SRC[SRC.index("parentWin.__kcTransposeChordToken = function"):][:2600]
    assert "family === 'sharp'" in js
    assert "const sharpSide = minor ? ['A', 'E', 'B'] : ['G', 'D', 'A', 'E', 'B'];" in js
