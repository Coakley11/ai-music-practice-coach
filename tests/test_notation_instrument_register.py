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


def _notes(register_instrument: str = "", family: str = "Saxophone"):
    bars, _ = build_exercise_midis(
        CHORDS, level="Intermediate", instrument=family, key_center="Am",
        register_instrument=register_instrument,
    )
    return [m for b in bars for m in b]


def _span(register_instrument: str = "", family: str = "Saxophone"):
    flat = _notes(register_instrument, family)
    return min(flat), max(flat)


def _centre(register_instrument: str = "", family: str = "Saxophone") -> float:
    """Where the exercise actually sits, which is what "emphasis" means.

    The old tests compared the lowest and highest generated note. The highest still
    distinguishes these horns; the lowest no longer can, and should not - see
    ``EachSaxophoneEmphasisesItsOwnPartOfOneSharedRange``.
    """
    flat = _notes(register_instrument, family)
    return sum(flat) / len(flat)


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
        """Emphasis, measured where the exercise sits and how high it reaches.

        This used to also require the baritone's *lowest* note to be below the alto's.
        It cannot be, and should not be: every saxophone reads the same written range,
        about Bb3-F6, because they share one fingering system. A baritone sounds much
        lower than an alto but *reads* the same notes, and the old expectation could
        only be met by writing it below its own lowest note - measured at ten semitones
        below written Bb3 at Beginner and sixteen at Advanced. The pedagogical intent
        behind the test is real and is kept: the baritone's exercise still sits lower
        and reaches less high than the alto's.
        """
        self.assertLess(_centre("Baritone saxophone (Eb)"),
                        _centre("Alto saxophone (Eb)"))
        self.assertLess(_span("Baritone saxophone (Eb)")[1],
                        _span("Alto saxophone (Eb)")[1])

    def test_soprano_sits_above_alto(self):
        """Same correction, the other way up - and here the floor is a real preference.

        The soprano's written floor (D4) is *above* the shared physical floor, so it is
        a choice rather than an impossibility, and it is preserved. What cannot be
        required is that its lowest generated note beats the alto's: both horns can
        reach written Bb3, and at this level both exercises happen to start on the same
        note. Emphasis is the thing that distinguishes them.
        """
        self.assertGreater(_centre("Soprano saxophone (Bb)"),
                           _centre("Alto saxophone (Eb)"))
        self.assertGreater(_span("Soprano saxophone (Bb)")[1],
                           _span("Alto saxophone (Eb)")[1])

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


class EachSaxophoneEmphasisesItsOwnPartOfOneSharedRange(unittest.TestCase):
    """The replacement for the two assertions this change had to retire.

    One fingering system, one written range: a soprano, alto, tenor and baritone all
    read about Bb3-F6. What differs is what they *sound*, and the app already models
    that separately as a key transposition. Treating a lower-sounding horn as if it
    read lower notes is the error that put a baritone exercise sixteen semitones below
    its lowest note.

    So the floor is shared and physical, and the emphasis - where inside that range the
    exercise actually sits - stays per horn. Both halves are asserted here, because
    either on its own can be satisfied by something wrong: a shared floor with no
    emphasis would make the four horns identical, and emphasis without a floor is what
    produced unplayable notes.
    """

    ORDER = (
        "Baritone saxophone (Eb)",
        "Tenor saxophone (Bb)",
        "Alto saxophone (Eb)",
        "Soprano saxophone (Bb)",
    )

    def test_every_saxophone_shares_one_physical_written_floor(self):
        from music_coach_ami.notation_profile import playable_written_range

        floors = {h: playable_written_range(h)[0] for h in SAXES}
        self.assertEqual(len(set(floors.values())), 1, floors)

    def test_no_saxophone_is_written_below_that_floor(self):
        from chord_navigation_notation import instrument_register
        from music_coach_ami.notation_profile import playable_written_range

        for horn in SAXES:
            floor = playable_written_range(horn)[0]
            for level in ("Beginner", "Intermediate", "Advanced"):
                bars, _ = build_exercise_midis(
                    CHORDS, level=level, instrument="Saxophone", key_center="Am",
                    register_instrument=horn,
                )
                flat = [m for b in bars for m in b]
                lo, _hi, _s = instrument_register(horn, level)
                with self.subTest(horn=horn, level=level):
                    self.assertGreaterEqual(lo, floor)
                    self.assertGreaterEqual(min(flat), floor)

    def test_the_four_horns_still_sit_in_a_sensible_order(self):
        centres = [(_centre(h), h) for h in self.ORDER]
        self.assertEqual([h for _c, h in sorted(centres)], list(self.ORDER),
                         f"emphasis order changed: {centres}")

    def test_the_order_holds_at_every_level(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            centres = []
            for horn in self.ORDER:
                bars, _ = build_exercise_midis(
                    CHORDS, level=level, instrument="Saxophone", key_center="Am",
                    register_instrument=horn,
                )
                flat = [m for b in bars for m in b]
                centres.append((sum(flat) / len(flat), horn))
            with self.subTest(level=level):
                self.assertEqual([h for _c, h in sorted(centres)], list(self.ORDER),
                                 f"{level}: {centres}")

    def test_a_preference_above_the_floor_is_left_alone(self):
        """The soprano reads from D4 by choice, not by limit, so nothing moves it."""
        from music_coach_ami.notation_profile import (
            notation_profile_for_instrument,
            playable_written_range,
        )

        profile = notation_profile_for_instrument("Soprano saxophone (Bb)")
        floor = playable_written_range("Soprano saxophone (Bb)")[0]
        self.assertGreater(profile.midi_low, floor)
        from chord_navigation_notation import instrument_register

        self.assertEqual(instrument_register("Soprano saxophone (Bb)", "Beginner")[0],
                         profile.midi_low)

    def test_difficulty_still_opens_up_more_of_the_range(self):
        from chord_navigation_notation import instrument_register

        for horn in SAXES:
            spans = [instrument_register(horn, lvl)[1] - instrument_register(horn, lvl)[0]
                     for lvl in ("Beginner", "Intermediate", "Advanced")]
            with self.subTest(horn=horn, spans=spans):
                self.assertLess(spans[0], spans[2])
