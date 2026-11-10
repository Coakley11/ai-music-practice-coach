"""Every exercise the app generates must be playable on the instrument it is for.

``instrument_register`` widens the AMI comfortable-middle register by three semitones a
level, and claimed in its docstring to stay "bounded by real instrument limits". It was
not: a comfortable register is not a limit, and the widening ran off the bottom. Measured
over nine instruments and three levels, seventeen combinations generated notes that do
not exist on the instrument - worst a baritone saxophone sixteen semitones below its
lowest note, and a guitar below the open low E.

Every failure was at the bottom, never the top, because these registers sit low in the
instrument's compass. So the fix clamps to a real playable range and gives width the
floor cannot absorb to the ceiling instead - Advanced still means a wider register than
Beginner, which is the whole point of the level.
"""

from __future__ import annotations

import unittest

from chord_navigation_notation import instrument_register
from music_coach_ami.notation_profile import playable_written_range
from notation_exercise_patterns import build_exercise_midis

INSTRUMENTS = [
    "Flute", "Alto Sax (Eb)", "Tenor Sax (Bb)", "Soprano Sax (Bb)", "Bari Sax (Eb)",
    "Bb Clarinet", "Bb Trumpet", "Bass", "Voice", "Piano", "Guitar",
]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
CHORDS = ["Am7", "D7", "Gmaj7", "Cmaj7", "F#m7b5", "B7", "Em7", "A7"]
KEYS = ["C", "G", "Bb", "Am", "Eb", "F#", "D", "Ab"]
MODES = ["auto", "scales", "arpeggios"]


class TheRegisterStaysOnTheInstrument(unittest.TestCase):
    def test_the_declared_register_is_inside_the_playable_range(self):
        for name in INSTRUMENTS:
            floor, ceiling = playable_written_range(name)
            for level in LEVELS:
                lo, hi, start = instrument_register(name, level)
                with self.subTest(instrument=name, level=level):
                    self.assertGreaterEqual(lo, floor)
                    self.assertLessEqual(hi, ceiling)
                    self.assertLessEqual(lo, start)
                    self.assertLessEqual(start, hi)

    def test_no_generated_note_is_unplayable(self):
        """The one that matters: the notes themselves, not the declared bounds."""
        for name in INSTRUMENTS:
            floor, ceiling = playable_written_range(name)
            for level in LEVELS:
                notes = []
                for key in KEYS:
                    for mode in MODES:
                        per_bar, _plan = build_exercise_midis(
                            CHORDS, level=level, instrument=name, key_center=key,
                            seed=7, focus="Improvisation", mode=mode,
                            register_instrument=name,
                        )
                        notes += [m for bar in per_bar for m in bar]
                with self.subTest(instrument=name, level=level):
                    self.assertTrue(notes)
                    self.assertGreaterEqual(min(notes), floor)
                    self.assertLessEqual(max(notes), ceiling)


class ALevelStillMeansMoreRange(unittest.TestCase):
    """Clamping must not flatten the progression into one register for every level."""

    def test_each_level_spans_at_least_as_much_as_the_one_below(self):
        for name in INSTRUMENTS:
            spans = []
            for level in LEVELS:
                lo, hi, _start = instrument_register(name, level)
                spans.append(hi - lo)
            with self.subTest(instrument=name, spans=spans):
                self.assertLessEqual(spans[0], spans[1])
                self.assertLessEqual(spans[1], spans[2])

    def test_advanced_is_strictly_wider_than_beginner_where_there_is_room(self):
        for name in INSTRUMENTS:
            floor, ceiling = playable_written_range(name)
            b_lo, b_hi, _ = instrument_register(name, "Beginner")
            a_lo, a_hi, _ = instrument_register(name, "Advanced")
            room = (b_lo - floor) + (ceiling - b_hi)
            if room <= 0:
                continue
            with self.subTest(instrument=name):
                self.assertGreater(a_hi - a_lo, b_hi - b_lo)


class TheSaxophonesShareOneWrittenRange(unittest.TestCase):
    """One fingering system, one written range - different sounding pitch.

    The profile table gave each saxophone a different written register, which is how
    bari ended up generating ten semitones below its lowest note at Beginner.
    """

    def test_every_saxophone_has_the_same_playable_written_range(self):
        ranges = {
            name: playable_written_range(name)
            for name in ("Alto Sax (Eb)", "Tenor Sax (Bb)",
                         "Soprano Sax (Bb)", "Bari Sax (Eb)")
        }
        self.assertEqual(len(set(ranges.values())), 1, ranges)

    def test_the_longest_name_wins_the_lookup(self):
        self.assertEqual(playable_written_range("Tenor Sax (Bb)"),
                         playable_written_range("sax"))

    def test_an_unknown_instrument_is_not_clamped_to_nothing(self):
        lo, hi = playable_written_range("Theremin")
        self.assertLess(lo, hi)
        self.assertLessEqual(hi - lo, 108)


class TheBeginnerRegisterIsUnchangedWhereItWasAlreadyPlayable(unittest.TestCase):
    """A clamp should move only what was wrong, so known-good output stays identical."""

    def test_instruments_that_were_in_range_keep_their_beginner_register(self):
        for name, expected in (
            ("Flute", (60, 96)),          # profile 60-96, already at its limits
            ("Alto Sax (Eb)", (58, 77)),
            ("Bb Clarinet", (60, 79)),
            ("Bb Trumpet", (58, 77)),
            ("Bass", (40, 55)),
            ("Guitar", (52, 67)),
            ("Piano", (36, 55)),
        ):
            with self.subTest(instrument=name):
                lo, hi, _start = instrument_register(name, "Beginner")
                self.assertEqual((lo, hi), expected)


if __name__ == "__main__":
    unittest.main()


class TheGuitarStaysOnTheFretboardTheBuilderUses(unittest.TestCase):
    """A clamp that widens the register must not outrun the fretboard.

    ``guitar_exercise_tab`` places notes on strings tuned (40, 45, 50, 55, 59, 64) with
    ``EXERCISE_MAX_FRET`` of 12, so the highest note it can reach is 76. It does not
    complain about one it cannot place - it leaves it out. Raising the guitar ceiling to
    a theoretical E6 turned a 32-note Advanced exercise into 21 printed notes, silently.
    """

    CHORDS = ["Am7", "D7", "Gmaj7", "Cmaj7"]

    def test_the_ceiling_matches_what_twelve_frets_can_reach(self):
        from backing_rock_guitar import OPEN_STRINGS
        from guitar_exercise_tab import EXERCISE_MAX_FRET

        _floor, ceiling = playable_written_range("Guitar")
        self.assertEqual(ceiling, max(OPEN_STRINGS) + EXERCISE_MAX_FRET)

    def test_the_floor_is_the_open_low_string(self):
        from backing_rock_guitar import OPEN_STRINGS
        from music_coach_ami.notation_profile import notation_profile_for_instrument

        floor, _ceiling = playable_written_range("Guitar")
        shift = notation_profile_for_instrument("Guitar").sounding_to_written_shift
        self.assertEqual(floor, min(OPEN_STRINGS) + 12 * shift)

    def test_every_generated_note_reaches_the_tab(self):
        from guitar_exercise_tab import build_guitar_exercise_measures

        for level, mode in [(l, m) for l in LEVELS
                            for m in ("auto", "scales", "arpeggios")]:
            for key in ("C", "G", "Bb", "Eb"):
                with self.subTest(level=level, mode=mode, key=key):
                    per_bar, _ = build_exercise_midis(
                        self.CHORDS, level=level, instrument="Guitar",
                        key_center=key, seed=7, focus="Improvisation", mode=mode)
                    wanted = sum(len(b) for b in per_bar)
                    measures = build_guitar_exercise_measures(
                        self.CHORDS, level=level, mode=mode,
                        focus="Improvisation", key_center=key)
                    self.assertEqual(sum(len(m) for m in measures), wanted,
                                     "the TAB dropped notes it could not place")


class EveryRegisterSpansAtLeastAnOctave(unittest.TestCase):
    """``_nearest_octave_in_range`` says so, and a narrower one breaks the generator.

    Clamping the baritone saxophone's floor up to its real low Bb left its Beginner
    register nine semitones wide, and the connected-line generator then emitted a pitch
    outside its own bounds - a real failure in
    ``test_chord_navigation_notation.TestRegisterAcrossAllNamedInstruments``, not a
    hypothetical one.
    """

    def test_no_instrument_or_level_is_narrower_than_twelve_semitones(self):
        for name in INSTRUMENTS + ["Trombone", "Tuba", "Theremin", ""]:
            for level in LEVELS:
                lo, hi, _start = instrument_register(name, level)
                with self.subTest(instrument=name, level=level, span=hi - lo):
                    self.assertGreaterEqual(hi - lo, 12)

    def test_the_narrowest_case_is_the_one_that_caught_it(self):
        lo, hi, _ = instrument_register("Bari Sax (Eb)", "Beginner")
        floor, _ceiling = playable_written_range("Bari Sax (Eb)")
        self.assertEqual(lo, floor)
        self.assertEqual(hi - lo, 12)

    def test_the_generator_stays_inside_its_own_bounds(self):
        from chord_navigation_notation import build_connected_arpeggio_line

        for name in INSTRUMENTS:
            for level in LEVELS:
                lo, hi, _ = instrument_register(name, level)
                with self.subTest(instrument=name, level=level):
                    events = build_connected_arpeggio_line(
                        ["Fm7", "Bb7", "Ebmaj7", "Abmaj7", "Dm7b5", "G7", "Cm7", "Cm7"],
                        level=level, instrument=name)
                    for ev in events:
                        if not ev.is_rest and ev.midi is not None:
                            self.assertTrue(lo <= int(ev.midi) <= hi)


class OnlyTheOutOfRangeRegistersMoved(unittest.TestCase):
    """What was already playable must come out byte for byte as before.

    These are the registers the pre-clamp code produced for the instrument/level pairs
    that were already inside the instrument. If one of these changes, the clamp has
    reached past what it was for.
    """

    UNCHANGED = {
        ("Flute", "Beginner"): (60, 96),
        ("Alto Sax (Eb)", "Beginner"): (58, 77),
        ("Soprano Sax (Bb)", "Beginner"): (62, 81),
        ("Soprano Sax (Bb)", "Intermediate"): (59, 84),
        ("Bb Clarinet", "Beginner"): (60, 79),
        ("Bb Clarinet", "Intermediate"): (57, 82),
        ("Bb Clarinet", "Advanced"): (54, 85),
        ("Bb Trumpet", "Beginner"): (58, 77),
        ("Bb Trumpet", "Intermediate"): (55, 80),
        ("Bass", "Beginner"): (40, 55),
        ("Guitar", "Beginner"): (52, 67),
        ("Piano", "Beginner"): (36, 55),
        ("Piano", "Intermediate"): (33, 58),
        ("Piano", "Advanced"): (30, 61),
    }

    def test_registers_that_were_in_range_are_untouched(self):
        for (name, level), expected in self.UNCHANGED.items():
            with self.subTest(instrument=name, level=level):
                lo, hi, _start = instrument_register(name, level)
                self.assertEqual((lo, hi), expected)
