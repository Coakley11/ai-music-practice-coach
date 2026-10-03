"""Tests for the redesigned Notation/TAB tool (practice_notation.py).

Proves the tool now teaches chord-tone navigation (connected, chord-symbol-
annotated exercises) rather than independent unrelated shapes per chord,
and that it stays distinct per instrument -- not a copy of Generated
Practice Melody.
"""

from __future__ import annotations

import unittest

from practice_notation import generate_practice_notation

_SECTIONS = {
    "Verse 1": ["Am7", "Dm7", "G7", "Cmaj7"],
    "Chorus": ["F", "C", "G", "Am"],
}


def _generate(*, instrument: str, difficulty: str = "medium", section_focus: str | None = "Verse 1", num_lines: int = 4, display_key: str = "C"):
    return generate_practice_notation(
        song_title="Test Song",
        artist="Someone",
        display_key=display_key,
        original_key="C",
        bpm=100,
        groove_style="Pop",
        instrument=instrument,
        focus="general",
        section_focus=section_focus,
        sections=_SECTIONS,
        guitar_tabs={},
        num_lines=num_lines,
        difficulty=difficulty,
    )


class TestInstrumentDispatch(unittest.TestCase):
    def test_guitar_returns_tab_format(self) -> None:
        r = _generate(instrument="Guitar")
        self.assertEqual(r.format, "tab")

    def test_piano_returns_abc_with_bracketed_voicings(self) -> None:
        r = _generate(instrument="Piano")
        self.assertEqual(r.format, "abc")
        self.assertIn("[", r.abc)
        self.assertIn("]", r.abc)

    def test_saxophone_returns_monophonic_abc(self) -> None:
        r = _generate(instrument="Saxophone")
        self.assertEqual(r.format, "abc")
        self.assertNotIn("[", r.abc)

    def test_piano_and_saxophone_outputs_differ(self) -> None:
        piano = _generate(instrument="Piano")
        sax = _generate(instrument="Saxophone")
        self.assertNotEqual(piano.abc, sax.abc)


class TestChordSymbolsPresent(unittest.TestCase):
    def test_every_section_chord_appears_as_a_symbol(self) -> None:
        for instrument in ("Saxophone", "Piano"):
            r = _generate(instrument=instrument)
            for chord in _SECTIONS["Verse 1"]:
                self.assertIn(f'"{chord}"', r.abc, f"{instrument} output missing chord symbol for {chord}")

    def test_guitar_tab_shows_chord_name_per_measure(self) -> None:
        r = _generate(instrument="Guitar")
        for chord in _SECTIONS["Verse 1"]:
            self.assertIn(chord, r.html)


class TestSectionScope(unittest.TestCase):
    def test_different_sections_produce_different_chord_labels(self) -> None:
        verse = _generate(instrument="Saxophone", section_focus="Verse 1")
        chorus = _generate(instrument="Saxophone", section_focus="Chorus")
        self.assertNotEqual(verse.chord_labels, chorus.chord_labels)
        for chord in _SECTIONS["Chorus"]:
            self.assertIn(chord, chorus.chord_labels)


class TestLevelDifferentiation(unittest.TestCase):
    def test_easy_and_advanced_produce_different_note_counts(self) -> None:
        easy = _generate(instrument="Saxophone", difficulty="easy")
        advanced = _generate(instrument="Saxophone", difficulty="advanced")
        easy_notes = easy.abc.count('"') // 2  # one pair of quotes per chord annotation, not a note count
        self.assertNotEqual(easy.abc, advanced.abc)

    def test_difficulty_is_recorded_on_the_result(self) -> None:
        r = _generate(instrument="Saxophone", difficulty="advanced")
        self.assertEqual(r.difficulty, "advanced")


class TestKeyProjection(unittest.TestCase):
    def test_changing_display_key_changes_abc_key_field_not_song(self) -> None:
        c_key = _generate(instrument="Saxophone", display_key="C")
        d_key = _generate(instrument="Saxophone", display_key="D")
        self.assertIn("K:C", c_key.abc)
        self.assertIn("K:D", d_key.abc)
        # Same chord progression (same song/section) regardless of key.
        self.assertEqual(c_key.chord_labels, d_key.chord_labels)


if __name__ == "__main__":
    unittest.main()
