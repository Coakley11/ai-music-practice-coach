"""The exercise must sit in the register of the instrument actually chosen.

The Practice page's Instrument control offers families - 'Saxophone', not
'Alto saxophone (Eb)'. Written pitch is resolved upstream into the chart key, so that part
was already right, but instrument_register('Saxophone') answers with the alto range, so a
baritone player read exercises up to ten semitones above their horn and a soprano player
read below theirs. The app already resolves the specific type for the chart key; it now
passes the same value down for the register.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from chord_navigation_notation import instrument_register
from notation_exercise_patterns import build_exercise_midis

ROOT = Path(__file__).resolve().parents[1]
CHORDS = ["Am6", "C7", "B7", "Em6"]
SAXES = (
    "Alto saxophone (Eb)",
    "Tenor saxophone (Bb)",
    "Soprano saxophone (Bb)",
    "Baritone saxophone (Eb)",
)


def _span(register_instrument: str = "", family: str = "Saxophone"):
    bars, _ = build_exercise_midis(
        CHORDS, level="Intermediate", instrument=family, key_center="Am",
        register_instrument=register_instrument,
    )
    flat = [m for b in bars for m in b]
    return min(flat), max(flat)


class TheRealUiStringsResolveCorrectly(unittest.TestCase):
    """These are the values the Instrument selectbox actually offers."""

    def test_the_option_list_is_families_not_specific_horns(self):
        from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS

        self.assertIn("Saxophone", DEFAULT_INSTRUMENT_OPTIONS)
        self.assertNotIn("Alto Saxophone", DEFAULT_INSTRUMENT_OPTIONS)

    def test_each_family_resolves_to_the_right_written_key(self):
        from instrument_transposition import (
            SELECTED_TRANSPOSING_INSTRUMENT_KEY as KEY,
        )
        from instrument_transposition import selected_transposing_type, written_key_for_type

        cases = [
            ("Saxophone", "Alto saxophone (Eb)", "A"),
            ("Saxophone", "Tenor saxophone (Bb)", "D"),
            ("Saxophone", "Soprano saxophone (Bb)", "D"),
            ("Saxophone", "Baritone saxophone (Eb)", "A"),
            ("Trumpet", None, "D"),
            ("Clarinet", None, "D"),
        ]
        for family, chosen, expected in cases:
            with self.subTest(family=family, type=chosen):
                ss = {"instrument": family}
                if chosen:
                    ss[KEY] = chosen
                resolved = selected_transposing_type(ss, family)
                self.assertEqual(written_key_for_type("C", resolved), expected)

    def test_concert_instruments_are_not_transposed(self):
        from instrument_transposition import is_transposing_instrument

        for family in ("Piano", "Guitar", "Bass", "Flute", "Voice"):
            with self.subTest(family=family):
                self.assertFalse(is_transposing_instrument(family))

    def test_saxophone_without_a_chosen_type_does_not_fall_back_to_concert(self):
        """The specific worry: a missing (Eb) suffix must not mean concert pitch."""
        from instrument_transposition import selected_transposing_type, written_key_for_type

        resolved = selected_transposing_type({"instrument": "Saxophone"}, "Saxophone")
        self.assertTrue(resolved)
        self.assertEqual(written_key_for_type("C", resolved), "A")


class EachSaxophoneGetsItsOwnRegister(unittest.TestCase):
    def test_the_family_default_is_the_alto_range(self):
        self.assertEqual(_span(""), _span("Alto saxophone (Eb)"))

    def test_baritone_sits_below_alto(self):
        bari_lo, bari_hi = _span("Baritone saxophone (Eb)")
        alto_lo, alto_hi = _span("Alto saxophone (Eb)")
        self.assertLess(bari_lo, alto_lo)
        self.assertLess(bari_hi, alto_hi)

    def test_soprano_sits_above_alto(self):
        sop_lo, sop_hi = _span("Soprano saxophone (Bb)")
        alto_lo, alto_hi = _span("Alto saxophone (Eb)")
        self.assertGreater(sop_lo, alto_lo)
        self.assertGreater(sop_hi, alto_hi)

    def test_every_saxophone_stays_inside_its_own_playable_range(self):
        for horn in SAXES:
            lo, hi, _ = instrument_register(horn, "Intermediate")
            span_lo, span_hi = _span(horn)
            with self.subTest(horn=horn):
                self.assertGreaterEqual(span_lo, lo)
                self.assertLessEqual(span_hi, hi)

    def test_the_four_horns_do_not_all_produce_the_same_notes(self):
        spans = {h: _span(h) for h in SAXES}
        self.assertGreaterEqual(len(set(spans.values())), 3, spans)

    def test_an_unknown_register_instrument_falls_back_to_the_family(self):
        self.assertEqual(_span("Nonexistent horn"), _span(""))

    def test_concert_instruments_are_unaffected(self):
        for family in ("Flute", "Piano", "Bass"):
            with self.subTest(family=family):
                bars, _ = build_exercise_midis(
                    CHORDS, level="Intermediate", instrument=family, key_center="Am"
                )
                lo, hi, _ = instrument_register(family, "Intermediate")
                flat = [m for b in bars for m in b]
                self.assertGreaterEqual(min(flat), lo)
                self.assertLessEqual(max(flat), hi)


class ThePracticePagePassesTheResolvedType(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

    def test_the_generate_call_passes_a_register_instrument(self):
        self.assertIn("register_instrument=", self.src)

    def test_it_uses_the_type_the_app_already_resolved_for_the_chart_key(self):
        i = self.src.index("register_instrument=")
        self.assertIn("selected_saxophone_type", self.src[i : i + 300])

    def test_concert_instruments_pass_an_empty_value(self):
        i = self.src.index("register_instrument=")
        self.assertIn("is_transposing_instrument", self.src[i : i + 300])
