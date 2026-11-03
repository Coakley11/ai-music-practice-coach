"""The Notation tab writes technical exercises, not a second Practice Melody.

Arpeggios and scales run up and down, thirds and fourths sequence through the chord's own scale, and
voice leading starts on the nearest chord tone - all inside the instrument's comfortable register.
"""
import unittest

from notation_exercise_patterns import (
    EXERCISE_PATTERNS,
    NOTES_PER_BAR,
    build_exercise_events,
    build_exercise_midis,
    chord_tone_pcs,
    exercise_measure_midis,
    exercise_summary,
    pattern_plan,
    scale_pcs,
)

PROG = ["Dm7", "G7", "Cmaj7", "A7"]
WINDS = ["Flute", "Alto saxophone (Eb)", "Tenor saxophone (Bb)", "Baritone saxophone (Eb)", "Bb Clarinet"]


def _dirs(midis):
    return [b - a for a, b in zip(midis, midis[1:])]


class TestPatternShapes(unittest.TestCase):
    KW = dict(key_center="C", low=55, high=84, start_midi=67, count=6)

    def test_ascending_patterns_only_go_up(self):
        for pattern in ("arpeggio_up", "scale_up", "thirds", "fourths"):
            with self.subTest(pattern=pattern):
                out = exercise_measure_midis("Dm7", pattern=pattern, **self.KW)
                self.assertEqual(len(out), 6)
                self.assertTrue(all(d > 0 for d in _dirs(out)), out)

    def test_descending_patterns_only_go_down(self):
        for pattern in ("arpeggio_down", "scale_down"):
            with self.subTest(pattern=pattern):
                out = exercise_measure_midis("Dm7", pattern=pattern, **self.KW)
                self.assertTrue(all(d < 0 for d in _dirs(out)), out)

    def test_up_down_patterns_turn_around_once(self):
        for pattern in ("arpeggio_up_down", "scale_up_down"):
            with self.subTest(pattern=pattern):
                out = exercise_measure_midis("Dm7", pattern=pattern, **self.KW)
                turns = sum(1 for a, b in zip(_dirs(out), _dirs(out)[1:]) if a > 0 >= b or a < 0 <= b)
                self.assertGreaterEqual(turns, 1, out)
                self.assertLessEqual(turns, 2, out)

    def test_thirds_and_fourths_step_wider_than_a_scale(self):
        scale = exercise_measure_midis("Cmaj7", pattern="scale_up", **self.KW)
        thirds = exercise_measure_midis("Cmaj7", pattern="thirds", **self.KW)
        fourths = exercise_measure_midis("Cmaj7", pattern="fourths", **self.KW)
        avg = lambda xs: sum(abs(d) for d in _dirs(xs)) / len(_dirs(xs))
        self.assertLess(avg(scale), avg(thirds))
        self.assertLess(avg(thirds), avg(fourths))

    def test_arpeggios_use_only_chord_tones(self):
        for chord in PROG:
            with self.subTest(chord=chord):
                allowed = set(chord_tone_pcs(chord))
                for pattern in ("arpeggio_up", "arpeggio_down", "arpeggio_up_down", "voice_leading"):
                    out = exercise_measure_midis(chord, pattern=pattern, **self.KW)
                    self.assertTrue({m % 12 for m in out} <= allowed, (chord, pattern, out))

    def test_scalar_patterns_use_the_chords_own_scale(self):
        for chord in PROG:
            with self.subTest(chord=chord):
                allowed = set(scale_pcs(chord, "C"))
                for pattern in ("scale_up", "scale_down", "thirds", "fourths"):
                    out = exercise_measure_midis(chord, pattern=pattern, **self.KW)
                    self.assertTrue({m % 12 for m in out} <= allowed, (chord, pattern, out))

    def test_voice_leading_starts_next_to_the_previous_note(self):
        out = exercise_measure_midis("G7", pattern="voice_leading", key_center="C",
                                     low=55, high=84, start_midi=67, count=4)
        self.assertLessEqual(abs(out[0] - 67), 3)

    def test_the_am6_bar_uses_its_dorian_sixth_not_a_flat_sixth(self):
        pcs = set(scale_pcs("Am6", "Am"))
        self.assertIn(6, pcs)         # F# - Dorian
        self.assertNotIn(5, pcs)      # not F natural

    def test_every_advertised_pattern_produces_notes(self):
        for pattern in EXERCISE_PATTERNS:
            with self.subTest(pattern=pattern):
                out = exercise_measure_midis("G7", pattern=pattern, **self.KW)
                self.assertEqual(len(out), 6)


class TestWholeExercise(unittest.TestCase):
    def test_every_level_cycles_through_its_own_drills(self):
        for level, want in (("Beginner", 2), ("Intermediate", 4), ("Advanced", 5)):
            with self.subTest(level=level):
                plan = pattern_plan(level, 8)
                self.assertEqual(len(plan), 8)
                self.assertEqual(len(set(plan)), want)

    def test_levels_differ_in_density(self):
        counts = []
        for level in ("Beginner", "Intermediate", "Advanced"):
            bars, _plan = build_exercise_midis(PROG, level=level, instrument="Flute", key_center="C")
            counts.append(len(bars[0]))
            self.assertEqual(len(bars[0]), NOTES_PER_BAR[level])
        self.assertEqual(counts, sorted(counts))

    def test_bars_connect_to_each_other(self):
        bars, _plan = build_exercise_midis(PROG, level="Intermediate", instrument="Flute", key_center="C")
        for a, b in zip(bars, bars[1:]):
            self.assertLessEqual(abs(b[0] - a[-1]), 12, (a[-1], b[0]))

    def test_it_stays_in_a_playable_register_for_every_wind(self):
        from instrument_register_fit import comfortable_written_range

        for inst in WINDS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                with self.subTest(inst=inst, level=level):
                    bars, _plan = build_exercise_midis(PROG, level=level, instrument=inst, key_center="C")
                    flat = [m for bar in bars for m in bar]
                    lo, hi = comfortable_written_range(inst, level)
                    self.assertGreaterEqual(min(flat), lo)
                    self.assertLessEqual(max(flat), hi)

    def test_an_advanced_flute_study_is_not_shrieking(self):
        bars, _plan = build_exercise_midis(PROG, level="Advanced", instrument="Flute", key_center="C")
        self.assertLessEqual(max(m for bar in bars for m in bar), 88)

    def test_practice_focus_steers_the_drills(self):
        _b, scales = build_exercise_midis(PROG, level="Advanced", instrument="Flute", focus="Scales")
        _b, guides = build_exercise_midis(PROG, level="Advanced", instrument="Flute", focus="Guide Tones")
        self.assertNotEqual(scales, guides)
        self.assertTrue(all("scale" in p or p in ("thirds", "fourths") for p in scales), scales)
        self.assertIn("voice_leading", guides)

    def test_the_summary_names_what_is_drilled(self):
        _bars, plan = build_exercise_midis(PROG, level="Advanced", instrument="Flute")
        summary = exercise_summary(plan)
        for pattern in set(plan):
            self.assertIn(EXERCISE_PATTERNS[pattern], summary)


class TestRenderableEvents(unittest.TestCase):
    def test_bars_are_exactly_full(self):
        events, _plan = build_exercise_events(PROG, level="Advanced", instrument="Flute",
                                              key_center="C", beats_per_measure=4)
        per_bar = {}
        for e in events:
            per_bar[e.measure] = per_bar.get(e.measure, 0) + e.duration_beats
        self.assertEqual(set(per_bar), set(range(len(PROG))))
        for measure, beats in per_bar.items():
            self.assertAlmostEqual(beats, 4.0, places=6, msg=f"bar {measure}")

    def test_events_carry_pitch_and_chord_and_no_rests(self):
        events, _plan = build_exercise_events(PROG, level="Intermediate", instrument="Alto saxophone (Eb)")
        self.assertTrue(events)
        for e in events:
            self.assertFalse(e.is_rest)
            self.assertTrue(e.pitch)
            self.assertIn(e.chord, PROG)

    def test_articulation_grows_with_the_level(self):
        marks = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            events, _plan = build_exercise_events(PROG, level=level, instrument="Flute")
            marks[level] = sum(1 for e in events if e.articulation)
        self.assertEqual(marks["Beginner"], 0)
        self.assertLess(marks["Intermediate"], marks["Advanced"])

    def test_it_renders_through_the_shared_abc_pipeline(self):
        from chord_navigation_notation import arpeggio_events_to_melody_dicts
        from composition_melody_notation import build_abc_from_melody_events

        events, _plan = build_exercise_events(PROG, level="Intermediate", instrument="Flute", key_center="C")
        abc = build_abc_from_melody_events(
            arpeggio_events_to_melody_dicts(events), key="C", meter="4/4", bpm=100,
            title="Exercise", chords=PROG, clef="treble",
        )
        self.assertIn("K:C", abc)
        self.assertIn("Dm7", abc)


if __name__ == "__main__":
    unittest.main()
