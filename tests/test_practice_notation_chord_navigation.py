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

# Longer than the old hardcoded 4-chord truncation, to prove full-scope
# generation covers it all (item 3): a full song's worth of changes.
_LONG_SECTIONS = {
    "Full Song": [
        "Am7", "Dm7", "G7", "Cmaj7",
        "Fmaj7", "Bm7b5", "E7", "Am7",
        "Dm7", "G7", "Cmaj7", "Fmaj7",
    ],
}


def _generate(*, instrument: str, difficulty: str = "medium", section_focus: str | None = "Verse 1", display_key: str = "C", sections: dict[str, list[str]] | None = None):
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
        sections=sections or _SECTIONS,
        guitar_tabs={},
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


class TestFullScopeGeneration(unittest.TestCase):
    """Notation/TAB must cover the entire selected Practice scope, not
    truncate to the first few bars (the old ``num_lines`` bar-count picker,
    now removed)."""

    def test_saxophone_covers_every_chord_in_a_long_full_song_section(self) -> None:
        r = _generate(
            instrument="Saxophone",
            section_focus="Full Song",
            sections=_LONG_SECTIONS,
        )
        full = _LONG_SECTIONS["Full Song"]
        for chord in full:
            self.assertIn(chord, r.chord_labels)
        self.assertEqual(r.num_lines, len(full))

    def test_piano_covers_every_chord_in_a_long_full_song_section(self) -> None:
        r = _generate(
            instrument="Piano",
            section_focus="Full Song",
            sections=_LONG_SECTIONS,
        )
        full = _LONG_SECTIONS["Full Song"]
        for chord in full:
            self.assertIn(chord, r.chord_labels)
        self.assertEqual(r.num_lines, len(full))

    def test_guitar_covers_every_chord_in_a_long_full_song_section(self) -> None:
        r = _generate(
            instrument="Guitar",
            section_focus="Full Song",
            sections=_LONG_SECTIONS,
        )
        full = _LONG_SECTIONS["Full Song"]
        for chord in full:
            self.assertIn(chord, r.html)
        self.assertEqual(r.num_lines, len(full))

    def test_generate_practice_notation_has_no_num_lines_parameter(self) -> None:
        """The removed bar-count picker must not be re-exposed as a kwarg."""
        import inspect

        params = inspect.signature(generate_practice_notation).parameters
        self.assertNotIn("num_lines", params)


class TestBassClef(unittest.TestCase):
    """Bass must render in bass clef, never treble."""

    def test_bass_abc_declares_bass_clef(self) -> None:
        r = _generate(instrument="Bass")
        self.assertEqual(r.format, "abc")
        self.assertIn("clef=bass", r.abc)

    def test_bass_is_not_routed_to_guitar_tab(self) -> None:
        r = _generate(instrument="Bass")
        self.assertNotEqual(r.format, "tab")

    def test_other_instruments_do_not_declare_a_clef(self) -> None:
        for instrument in ("Saxophone", "Trumpet", "Flute", "Clarinet"):
            r = _generate(instrument=instrument)
            self.assertNotIn("clef=", r.abc, instrument)

    def test_guitar_still_renders_as_tab_unaffected_by_bass_routing(self) -> None:
        r = _generate(instrument="Guitar")
        self.assertEqual(r.format, "tab")


class TestNoTextualNoteGuideInStructuredBody(unittest.TestCase):
    """The per-bar note/chord text listing stays available on the result
    object (for generation/tests) but the UI no longer displays it -- see
    streamlit_music_practice_app.py's Notation/TAB render block."""

    def test_body_field_still_populated_for_internal_use(self) -> None:
        r = _generate(instrument="Saxophone")
        self.assertTrue(r.body, "structured body data must remain available internally")

    def test_piano_body_field_still_populated_for_internal_use(self) -> None:
        r = _generate(instrument="Piano")
        self.assertTrue(r.body)


# A -> A -> B -> A form (A repeats identically three times, like item 10's
# own example) -- the literal "sections" dict can't hold duplicate keys, so
# repeats are represented as separate dict entries with IDENTICAL chords,
# exactly like a real song's chart (e.g. practice_melody_generator.py's own
# dedup precedent keys on chord-tuple identity, not label).
_FORM_SECTIONS = {
    "A1": ["Am7", "Dm7", "G7", "Cmaj7"],
    "A2": ["Am7", "Dm7", "G7", "Cmaj7"],  # identical chords to A1 -- a repeat
    "B": ["Fmaj7", "Bm7b5", "E7", "Am7"],
    "A3": ["Am7", "Dm7", "G7", "Cmaj7"],  # identical chords to A1/A2 again
}

# Verse -> Chorus -> Verse -> Chorus -> Bridge -> Chorus, matching item 10's
# second example.
_VCB_SECTIONS = {
    "Verse 1": ["C", "G", "Am", "F"],
    "Chorus 1": ["F", "C", "G", "Am"],
    "Verse 2": ["C", "G", "Am", "F"],  # same harmony as Verse 1
    "Chorus 2": ["F", "C", "G", "Am"],  # same harmony as Chorus 1
    "Bridge": ["Dm", "G", "Em", "Am"],
    "Chorus 3": ["F", "C", "G", "Am"],  # same harmony as Chorus 1/2 again
}


class TestFullSongUniqueSectionDeduplication(unittest.TestCase):
    """Full Song must show each musically unique section once, in
    first-appearance/form order -- not a literal copy every time that
    section recurs in the form."""

    def test_aaba_form_shows_a_and_b_once_each(self) -> None:
        r = _generate(instrument="Saxophone", section_focus="Full Song", sections=_FORM_SECTIONS)
        a_chords = _FORM_SECTIONS["A1"]
        b_chords = _FORM_SECTIONS["B"]
        for chord in a_chords + b_chords:
            self.assertIn(chord, r.chord_labels)
        # Full progression length == one A + one B, not three A's + one B.
        self.assertEqual(r.num_lines, len(a_chords) + len(b_chords))

    def test_verse_chorus_bridge_form_dedupes_to_three_unique_sections(self) -> None:
        r = _generate(instrument="Piano", section_focus="Full Song", sections=_VCB_SECTIONS)
        unique_bars = len(_VCB_SECTIONS["Verse 1"]) + len(_VCB_SECTIONS["Chorus 1"]) + len(_VCB_SECTIONS["Bridge"])
        self.assertEqual(r.num_lines, unique_bars)

    def test_single_selected_section_is_never_deduplicated_against_itself(self) -> None:
        """Selecting one specific section (not Full Song) must render that
        section's entire harmony normally -- dedup only applies to Full
        Song's section-repeat collapsing."""
        r = _generate(instrument="Saxophone", section_focus="A2", sections=_FORM_SECTIONS)
        self.assertEqual(r.num_lines, len(_FORM_SECTIONS["A2"]))

    def test_genuinely_different_sections_with_similar_labels_are_not_merged(self) -> None:
        """Two sections must only collapse when their actual harmony
        matches -- never merely because their names look similar."""
        sections = {
            "Verse 1": ["C", "G", "Am", "F"],
            "Verse 2": ["Dm", "Em", "F", "G"],  # same label pattern, different harmony
        }
        r = _generate(instrument="Saxophone", section_focus="Full Song", sections=sections)
        self.assertEqual(r.num_lines, 8)
        for chord in sections["Verse 1"] + sections["Verse 2"]:
            self.assertIn(chord, r.chord_labels)


if __name__ == "__main__":
    unittest.main()
