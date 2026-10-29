"""Karaoke display lyrics returns proper cues for Composition songs."""

from __future__ import annotations

import unittest

import karaoke_mode as km
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_lyrics_alignment import align_lyrics_to_melody, set_alignment
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import composition_pick_key_for

SHALLOW = "Pop\x1fShallow — Lady Gaga"


def _doc_with_lyrics() -> dict:
    """Composition with chords and lyrics on Verse."""
    doc = bootstrap_from_vision(
        genre="Pop", song_idea="Test Song", title="Test Song", key="C", bpm=120
    )
    apply_structure_template(doc, "simple")
    secs = ordered_sections(doc)
    apply_section_chords(doc, str(secs[0]["id"]), parse_chord_paste("C G Am F"))
    secs[0]["lyrics"] = {
        "intent": {},
        "lines": ["Hello world", "This is a test"],
        "raw_text": "Hello world\nThis is a test",
    }
    return doc


def _doc_with_alignment() -> dict:
    """Composition with lyrics AND a provisional alignment."""
    doc = _doc_with_lyrics()
    secs = ordered_sections(doc)
    sec = secs[0]
    events = [
        {"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1},
        {"pitch": "D4", "duration_beats": 1.0, "beat": 1, "measure": 1},
        {"pitch": "E4", "duration_beats": 1.0, "beat": 2, "measure": 1},
        {"pitch": "F4", "duration_beats": 1.0, "beat": 3, "measure": 1},
        {"pitch": "G4", "duration_beats": 1.0, "beat": 0, "measure": 2},
        {"pitch": "A4", "duration_beats": 1.0, "beat": 1, "measure": 2},
    ]
    sec.setdefault("melody", {})["events"] = events
    alignment = align_lyrics_to_melody("Hello world\nThis is a test", events)
    set_alignment(sec, alignment)
    return doc


def _karaoke_session(doc: dict) -> dict:
    pick = composition_pick_key_for(doc)
    ss: dict = {
        "instrument": "Voice",
        "studio_page": "backing",
        "karaoke_queue": [],
        COMPOSER_LIBRARY_KEY: {},
        "practice_key_by_source": {},
        "display_key": "C",
        "concert_key": "C",
    }
    save_document_to_library(ss, doc)
    km.add_to_queue(ss, pick, title="Test Song", artist="Composition", practice_key="C", bpm=120)
    km.start_session(ss, starting_pick_key=pick)
    return ss


class TestCompositionKaraokeLyrics(unittest.TestCase):
    def test_returns_section_lyrics_text(self) -> None:
        doc = _doc_with_lyrics()
        ss = _karaoke_session(doc)
        section_lyrics, _cues = km.karaoke_display_lyrics(ss)
        self.assertIn("Verse", section_lyrics)
        self.assertIn("Hello world", section_lyrics["Verse"])

    def test_returns_cues_from_lyrics_text(self) -> None:
        doc = _doc_with_lyrics()
        ss = _karaoke_session(doc)
        _lyrics, cues = km.karaoke_display_lyrics(ss)
        self.assertIn("Verse", cues)
        self.assertEqual(cues["Verse"], ["Hello world", "This is a test"])

    def test_returns_cues_from_alignment_when_available(self) -> None:
        doc = _doc_with_alignment()
        ss = _karaoke_session(doc)
        _lyrics, cues = km.karaoke_display_lyrics(ss)
        self.assertIn("Verse", cues)
        self.assertTrue(len(cues["Verse"]) >= 1)

    def test_empty_when_no_composition_found(self) -> None:
        ss: dict = {
            "instrument": "Voice",
            "studio_page": "backing",
            "karaoke_queue": [],
            COMPOSER_LIBRARY_KEY: {},
            "practice_key_by_source": {},
            "display_key": "C",
            "concert_key": "C",
        }
        km.add_to_queue(
            ss, "composition::nonexistent", title="Gone", artist="Composition",
            practice_key="C", bpm=120,
        )
        km.start_session(ss, starting_pick_key="composition::nonexistent")
        section_lyrics, cues = km.karaoke_display_lyrics(ss)
        self.assertEqual(section_lyrics, {})
        self.assertEqual(cues, {})


if __name__ == "__main__":
    unittest.main()
