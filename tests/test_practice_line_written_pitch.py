"""Issue 65: the single-line Practice staff must show the pitch the exercise engine chose.

Three different numbers get confused in this area, so they are named once here and kept
apart for the rest of the file.

**Engine pitch.** What ``build_exercise_events`` decides. It comes from
``chord_navigation_notation.instrument_register``, which is documented as - and is
literally built from - the AMI *written*-register table
(``music_coach_ami.notation_profile``). So the engine already works in written pitch, for
every instrument including bass.

**Written pitch.** What the player reads off the staff. It must equal the engine pitch:
the exercise was generated in the instrument's written register, so drawing it anywhere
else makes the printed exercise a different one.

**Sounding (concert) pitch.** What comes out of the instrument. It is *not* the written
pitch for a transposing instrument, and the difference is not one rule: an alto sax
sounds a major sixth below written, a tenor sax a major ninth, a bari sax an octave and a
major sixth, and a bass guitar an octave. Nothing in this file forces the staff to show
sounding pitch - that would be wrong for six of the nine instruments the Practice page
offers - and ``WrittenIsNotSounding`` exists to keep that distinction written down.

The reader is ``tests.test_abc_bar_accidentals.read_abc``, already in this repo and
already used to prove the coach's notation. It follows the ABC rules the drawing library
follows: accidentals are absolute and last to the bar line for the same letter *and*
octave. Reusing it is the point - a second spelling implementation would only test
itself.
"""

from __future__ import annotations

import unittest

from chord_navigation_notation import (
    arpeggio_events_to_melody_dicts,
    build_connected_arpeggio_line,
    instrument_register,
)
from composition_melody_notation import build_abc_from_melody_events
from music_coach_ami.notation_profile import notation_profile_for_instrument
from notation_exercise_patterns import build_exercise_events
from practice_notation import NOTATION_METER, PRACTICE_ABC_OCTAVE_SHIFT
from tests.test_abc_bar_accidentals import read_abc

CHORDS = ["Am7", "D7", "Gmaj7", "Cmaj7"]
KEYS = ["C", "G", "Bb", "Am", "Eb", "F#"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
MODES = ["auto", "scales", "arpeggios"]

# (page instrument, specific horn passed as register_instrument)
INSTRUMENTS = [
    ("Flute", ""),
    ("Saxophone", "Alto Sax (Eb)"),
    ("Saxophone", "Tenor Sax (Bb)"),
    ("Saxophone", "Soprano Sax (Bb)"),
    ("Saxophone", "Bari Sax (Eb)"),
    ("Clarinet", "Bb Clarinet"),
    ("Trumpet", "Bb Trumpet"),
    ("Bass", ""),
    ("Voice", ""),
]


def line_events(instrument, register_instrument, level, key, mode):
    """Exactly what practice_notation._build_line_notation renders."""
    try:
        events, _plan = build_exercise_events(
            CHORDS, level=level, instrument=instrument, key_center=key,
            focus="Improvisation", mode=mode, register_instrument=register_instrument,
        )
    except Exception:
        events = []
    if not events:
        events = build_connected_arpeggio_line(
            CHORDS, level=level, instrument=register_instrument or instrument,
            focus="Improvisation", groove_style="Jazz swing",
        )
    return events


def line_abc(events, key, clef="treble"):
    return build_abc_from_melody_events(
        arpeggio_events_to_melody_dicts(events), key=key, meter=NOTATION_METER,
        bpm=100, title="t", chords=CHORDS, clef=clef,
        octave_shift=PRACTICE_ABC_OCTAVE_SHIFT, musical_spelling=True,
    )


def readable(abc: str) -> str:
    """Drop slur parentheses before handing the tune to ``read_abc``.

    A phrasing slur carries no pitch, but it sits between the chord annotation and the
    first note of the bar - ``"Am7"(!>!G`` - and the reader's note pattern expects the
    annotation to be followed directly by the note it decorates. Without this it falls
    back to matching the ``A`` inside ``"Am7"`` and reports a note nobody wrote. The
    coach's own ABC has no slurs, which is why the reader has not needed it before.
    """
    return abc.replace("(", "").replace(")", "")


class TheStaffShowsTheEnginesWrittenPitch(unittest.TestCase):
    """The regression itself: read the staff back and compare, note for note.

    Measured before the fix: 0 of 9720 notes matched - 9513 drawn an octave high and 207
    drawn a semitone below even that, because a bare note after an explicit accidental in
    the same bar kept the accidental.
    """

    def test_every_instrument_level_mode_and_key(self):
        for instrument, horn in INSTRUMENTS:
            clef = "bass" if instrument == "Bass" else "treble"
            for level in LEVELS:
                for mode in MODES:
                    for key in KEYS:
                        with self.subTest(instrument=horn or instrument, level=level,
                                          mode=mode, key=key):
                            events = line_events(instrument, horn, level, key, mode)
                            want = [int(e.midi) for e in events
                                    if not e.is_rest and e.midi]
                            self.assertTrue(want, "no sounding notes generated")
                            got = read_abc(readable(line_abc(events, key, clef)))
                            self.assertEqual(got, want)

    def test_the_bass_staff_is_not_an_exception(self):
        """Bass earns its own test because its convention invites a wrong answer.

        A bass part is written an octave above sounding - but the engine is already
        working in written pitch, so the staff still shows the engine's number. The
        octave lives between written and *sounding*, not between the engine and the page.
        """
        events = line_events("Bass", "", "Intermediate", "C", "scales")
        want = [int(e.midi) for e in events if not e.is_rest and e.midi]
        self.assertEqual(read_abc(readable(line_abc(events, "C", "bass"))), want)


class AccidentalsFollowTheBarRule(unittest.TestCase):
    """An accidental lasts to the bar line; a later natural has to be written.

    This is the defect that an octave correction alone would have left in place: 207
    notes drawn a semitone flat, always a bare "g" after a "_g" earlier in the same bar
    and octave - the engine's G natural read as G flat, against a D7.
    """

    def abc_for(self, pitches, key="C"):
        events = [{"pitch": p, "is_rest": False, "duration_beats": 1.0} for p in pitches]
        return build_abc_from_melody_events(
            events, key=key, meter=NOTATION_METER, bpm=100, title="t",
            octave_shift=PRACTICE_ABC_OCTAVE_SHIFT, musical_spelling=True,
        )

    def test_a_natural_after_a_flat_in_the_same_bar_is_restored(self):
        from music_theory import NOTE_TO_MIDI  # noqa: F401  (import guard only)

        abc = self.abc_for(["Gb4", "G4", "Gb4", "G4"])
        self.assertEqual(read_abc(abc), [66, 67, 66, 67])

    def test_a_natural_after_a_sharp_in_the_same_bar_is_restored(self):
        self.assertEqual(read_abc(self.abc_for(["F#4", "F4", "F#4", "F4"])),
                         [66, 65, 66, 65])

    def test_the_rule_is_per_octave(self):
        self.assertEqual(read_abc(self.abc_for(["Gb4", "G5", "G4"])), [66, 79, 67])

    def test_a_new_bar_restores_the_key_signature(self):
        # Four beats a bar, so the fifth note starts a new bar and G is natural again.
        abc = self.abc_for(["Gb4", "G4", "G4", "G4", "G4"])
        self.assertEqual(read_abc(abc), [66, 67, 67, 67, 67])

    def test_a_flat_key_signature_still_reads_back_exactly(self):
        self.assertEqual(read_abc(self.abc_for(["Bb4", "B4", "Bb4"], key="Bb")),
                         [70, 71, 70])


class WrittenIsNotSounding(unittest.TestCase):
    """What each instrument sounds, given what it reads. Documentation with teeth.

    The app models the two halves of a transposition in two different places, and only
    one of them is a pitch class:

    * ``instrument_transposition.TRANSPOSING_SEMITONE_STEPS`` carries the *interval*
      used to transpose a key - pitch class only, which is all a key signature needs.
    * ``notation_profile.sounding_to_written_shift`` carries the *octave*, and is set
      only for bass and guitar.

    For the saxophones the octave half is not modelled at all: a tenor sounds a major
    ninth below written, not a major second, and a bari an octave and a major sixth, not
    a major sixth. That costs nothing today because nothing converts a wind exercise to
    concert MIDI - but it is exactly the assumption that would make a blanket octave
    shift look reasonable, so it is written down here rather than left to be rediscovered.
    """

    # instrument -> (true written-to-sounding semitones, app's pitch-class step)
    TRUE_SOUNDING_OFFSET = {
        "Flute": (0, 0),
        "Alto Sax (Eb)": (-9, -3),
        "Tenor Sax (Bb)": (-14, 2),
        "Soprano Sax (Bb)": (-2, 2),
        "Bari Sax (Eb)": (-21, -3),
        "Bb Clarinet": (-2, 2),
        "Bb Trumpet": (-2, 2),
        "Bass": (-12, 0),
        "Voice": (0, 0),
    }

    def test_the_apps_step_is_the_true_interval_as_a_pitch_class(self):
        from instrument_transposition import TRANSPOSING_SEMITONE_STEPS

        for name, (true_offset, app_step) in self.TRUE_SOUNDING_OFFSET.items():
            with self.subTest(instrument=name):
                self.assertEqual(TRANSPOSING_SEMITONE_STEPS.get(name, 0), app_step)
                # written + step and written + true offset are the same note name.
                self.assertEqual((-true_offset) % 12, app_step % 12)

    def test_only_bass_carries_an_octave_in_its_notation_profile(self):
        for name, (_true, _step) in self.TRUE_SOUNDING_OFFSET.items():
            with self.subTest(instrument=name):
                shift = notation_profile_for_instrument(name).sounding_to_written_shift
                self.assertEqual(shift, 1 if name == "Bass" else 0)

    def test_the_saxophone_octave_displacement_is_not_modelled(self):
        """Recorded, not asserted as correct: tenor and bari are an octave out.

        If anything ever needs a wind exercise in concert pitch, this is the gap to
        close first - and closing it must not touch the written staff, which is right.
        """
        for name in ("Tenor Sax (Bb)", "Bari Sax (Eb)"):
            true_offset, app_step = self.TRUE_SOUNDING_OFFSET[name]
            with self.subTest(instrument=name):
                modelled = -app_step - 12 * notation_profile_for_instrument(
                    name).sounding_to_written_shift
                self.assertNotEqual(modelled, -true_offset,
                                    "if this now matches, the gap was closed - "
                                    "update this test and the Issue 65 notes")

    def test_the_engine_register_is_the_written_register(self):
        """instrument_register is the AMI written table widened by level, not a second one."""
        for name, _ in self.TRUE_SOUNDING_OFFSET.items():
            with self.subTest(instrument=name):
                profile = notation_profile_for_instrument(name)
                lo, hi, _start = instrument_register(name, "Beginner")
                self.assertEqual((lo, hi), (profile.midi_low, profile.midi_high))


if __name__ == "__main__":
    unittest.main()


class TheCallSitesActuallyPassTheFlags(unittest.TestCase):
    """Everything above builds its own ABC, so it would pass even if the app did not.

    These check the two real call sites in ``practice_notation`` - the wind/line builder
    and the bass builder - so the product cannot drift back while the tests stay green.
    """

    def setUp(self):
        from pathlib import Path

        import practice_notation

        self.src = Path(practice_notation.__file__).read_text(encoding="utf-8")

    def test_the_shift_is_minus_one(self):
        self.assertEqual(PRACTICE_ABC_OCTAVE_SHIFT, -1)

    def test_both_builders_pass_the_octave_shift_and_musical_spelling(self):
        calls = self.src.count("build_abc_from_melody_events(")
        self.assertEqual(calls, 2, "a third call site needs the same two arguments")
        self.assertEqual(self.src.count("octave_shift=PRACTICE_ABC_OCTAVE_SHIFT"), 2)
        self.assertEqual(self.src.count("musical_spelling=True"), 2)

    def test_the_rendered_result_matches_the_engine_end_to_end(self):
        """Through generate_practice_notation itself, not through the helper above."""
        from practice_notation import generate_practice_notation

        for instrument in ("Saxophone", "Flute", "Trumpet", "Clarinet", "Bass", "Voice"):
            for key in ("C", "Bb", "Eb", "G"):
                with self.subTest(instrument=instrument, key=key):
                    res = generate_practice_notation(
                        song_title="S", artist="", display_key=key, original_key=key,
                        bpm=100, groove_style="Jazz swing", instrument=instrument,
                        focus="Improvisation", section_focus=None,
                        sections={"A": CHORDS}, difficulty="medium",
                        exercise_mode="scales",
                    )
                    # Bass never reaches the exercise builder: Scales and Arpeggios
                    # are still deferred for it, so the page always renders its
                    # walking line. Compare against whichever builder the app used.
                    if instrument == "Bass":
                        from chord_navigation_notation import build_bass_line

                        events = build_bass_line(
                            CHORDS, level="Intermediate",
                            groove_style="Jazz swing", focus="Improvisation",
                        )
                    else:
                        events = line_events(instrument, "", "Intermediate", key, "scales")
                    want = [int(e.midi) for e in events if not e.is_rest and e.midi]
                    self.assertEqual(read_abc(readable(res.abc or "")), want)
