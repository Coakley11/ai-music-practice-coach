"""Level arrangement defects: Beginner chord names and Beginner forms.

- Beginner turned a dominant seventh into its root twice ("G7" -> "GG").
- A jazz head form (Section A / Section B / Head) kept only its Outro.
- Shallow's Refrains counted as its choruses, so Beginner never reached a Chorus.
"""
from __future__ import annotations

import pytest

from beginner_arrangement import select_beginner_section_names
from chart_level_arrangement import resolve_level_chart, simplify_chord_for_beginner
from song_catalog.catalog import load_song_catalog


def _song(title: str) -> dict:
    _lib, picker, _g, _r = load_song_catalog()
    for _genre, songs in picker.items():
        for label, data in songs.items():
            if label.startswith(title + " "):
                return data
    raise AssertionError(title)


@pytest.mark.parametrize(
    "chord,want",
    [("G7", "G"), ("Bb7", "Bb"), ("D7/F#", "D"), ("Cmaj7", "C"), ("Am7", "Am"), ("F#m7b5", "F#m"), ("Esus4", "E")],
)
def test_beginner_chords_are_triads(chord: str, want: str) -> None:
    assert simplify_chord_for_beginner(chord, genre="Pop") == want


def test_beginner_blues_keeps_the_dominant_seventh() -> None:
    assert simplify_chord_for_beginner("G7", genre="Blues") == "G7"


def test_jazz_head_form_keeps_the_head() -> None:
    names = ["Section A", "Section B", "Head", "Solo", "Outro"]
    assert select_beginner_section_names(names) == ["Section A", "Section B", "Outro"]
    sd, _ = resolve_level_chart(_song("Blue Bossa"), "Beginner")
    assert sd["section_order"] == ["Section A", "Section B", "Outro"]


def test_refrains_follow_their_verses_when_real_choruses_exist() -> None:
    names = ["Intro", "Verse 1", "Refrain 1", "Verse 2", "Refrain 2", "Chorus 1", "Bridge",
             "Gaga build-up", "Chorus 2", "Outro"]
    assert select_beginner_section_names(names) == [
        "Intro", "Verse 1", "Refrain 1", "Chorus 1", "Verse 2", "Refrain 2", "Chorus 2", "Outro",
    ]


def test_refrain_still_counts_as_the_chorus_when_there_is_none() -> None:
    names = ["Verse 1", "Refrain", "Verse 2", "Refrain 2"]
    assert select_beginner_section_names(names) == ["Verse 1", "Refrain", "Verse 2", "Refrain 2"]


def test_pop_forms_unchanged() -> None:
    names = ["Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Pre-Chorus 2", "Chorus 2", "Bridge", "Final Chorus"]
    assert select_beginner_section_names(names) == ["Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Chorus 2"]

