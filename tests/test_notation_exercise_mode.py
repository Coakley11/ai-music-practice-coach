"""Practice Notation — an explicit Scales / Arpeggios choice, and the drills it adds.

The exercise engine and the harmony-aware chord-scale selection already existed. What was
missing was the musician being able to *ask* for scales or arpeggios: patterns were chosen
for them by level and Practice Focus, with no control in the Notation tab. These tests pin
the mode, the three drills added to serve it, and that "auto" leaves the old behaviour
exactly as it was.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from notation_exercise_patterns import (
    EXERCISE_MODES,
    EXERCISE_PATTERNS,
    MODE_LABELS,
    build_exercise_events,
    exercise_measure_midis,
    normalize_exercise_mode,
    pattern_plan,
)

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("Beginner", "Intermediate", "Advanced")


class ModeSelection(unittest.TestCase):
    def test_the_three_modes_exist_and_are_labelled(self):
        self.assertEqual(set(EXERCISE_MODES), {"auto", "arpeggios", "scales"})
        for mode in EXERCISE_MODES:
            self.assertTrue(MODE_LABELS.get(mode))

    def test_auto_is_unchanged_from_the_level_plan(self):
        from notation_exercise_patterns import _LEVEL_PLANS

        for level in LEVELS:
            with self.subTest(level=level):
                self.assertEqual(
                    pattern_plan(level, 4, mode="auto"),
                    [_LEVEL_PLANS[level][i % len(_LEVEL_PLANS[level])] for i in range(4)],
                )

    def test_no_mode_argument_behaves_like_auto(self):
        for level in LEVELS:
            with self.subTest(level=level):
                self.assertEqual(pattern_plan(level, 5), pattern_plan(level, 5, mode="auto"))

    def test_arpeggios_mode_drills_only_chord_tone_patterns(self):
        for level in LEVELS:
            with self.subTest(level=level):
                for pat in pattern_plan(level, 6, mode="arpeggios"):
                    self.assertTrue(
                        pat.startswith("arpeggio") or pat == "voice_leading",
                        f"{level}: {pat} is not an arpeggio drill",
                    )

    def test_scales_mode_drills_only_scalar_patterns(self):
        for level in LEVELS:
            with self.subTest(level=level):
                for pat in pattern_plan(level, 6, mode="scales"):
                    self.assertFalse(
                        pat.startswith("arpeggio"), f"{level}: {pat} is not a scale drill"
                    )

    def test_an_explicit_mode_outranks_the_practice_focus(self):
        """The musician asking directly beats a guess made from their Focus."""
        focused = pattern_plan("Advanced", 4, focus="Arpeggios")
        asked = pattern_plan("Advanced", 4, focus="Arpeggios", mode="scales")
        self.assertNotEqual(focused, asked)
        for pat in asked:
            self.assertFalse(pat.startswith("arpeggio"))

    def test_auto_still_follows_the_practice_focus(self):
        self.assertNotEqual(
            pattern_plan("Advanced", 4, focus="Scales", mode="auto"),
            pattern_plan("Advanced", 4, mode="auto"),
        )

    def test_an_unknown_mode_falls_back_to_auto(self):
        self.assertEqual(normalize_exercise_mode("nonsense"), "auto")
        self.assertEqual(normalize_exercise_mode(""), "auto")
        self.assertEqual(normalize_exercise_mode(None), "auto")
        self.assertEqual(pattern_plan("Advanced", 4, mode="nonsense"), pattern_plan("Advanced", 4))

    def test_mode_names_are_case_insensitive(self):
        self.assertEqual(normalize_exercise_mode("Scales"), "scales")
        self.assertEqual(normalize_exercise_mode("  ARPEGGIOS "), "arpeggios")


class LevelsStillDifferInsideAMode(unittest.TestCase):
    """Choosing a mode must not flatten the difficulty progression."""

    def test_arpeggio_levels_differ(self):
        plans = [tuple(pattern_plan(lv, 8, mode="arpeggios")) for lv in LEVELS]
        self.assertNotEqual(plans[0], plans[1])
        self.assertNotEqual(plans[1], plans[2])

    def test_scale_levels_differ(self):
        plans = [tuple(pattern_plan(lv, 8, mode="scales")) for lv in LEVELS]
        self.assertNotEqual(plans[0], plans[1])
        self.assertNotEqual(plans[1], plans[2])

    def test_beginner_is_not_given_the_hardest_drills(self):
        beginner = set(pattern_plan("Beginner", 8, mode="scales"))
        self.assertNotIn("four_note_sequence", beginner)
        self.assertNotIn("fourths", beginner)
        self.assertNotIn("arpeggio_inversions", set(pattern_plan("Beginner", 8, mode="arpeggios")))

    def test_advanced_gets_the_sequence_drills(self):
        advanced = set(pattern_plan("Advanced", 8, mode="scales"))
        self.assertIn("triplet_sequence", advanced)
        self.assertIn("four_note_sequence", advanced)
        self.assertIn("arpeggio_inversions", set(pattern_plan("Advanced", 8, mode="arpeggios")))


class TheDrillsAddedToServeTheModes(unittest.TestCase):
    def test_the_new_patterns_are_registered_with_descriptions(self):
        for pat in ("arpeggio_inversions", "triplet_sequence", "four_note_sequence"):
            with self.subTest(pattern=pat):
                self.assertTrue(EXERCISE_PATTERNS.get(pat))

    def _bar(self, pattern, chord="Am6", count=8):
        return exercise_measure_midis(
            chord, pattern=pattern, key_center="C", low=60, high=84, start_midi=67, count=count
        )

    def test_every_pattern_fills_the_bar(self):
        for pat in EXERCISE_PATTERNS:
            with self.subTest(pattern=pat):
                self.assertEqual(len(self._bar(pat)), 8)

    def test_every_pattern_stays_inside_the_register(self):
        for pat in EXERCISE_PATTERNS:
            with self.subTest(pattern=pat):
                for midi in self._bar(pat):
                    self.assertGreaterEqual(midi, 60)
                    self.assertLessEqual(midi, 84)

    def test_inversions_start_each_group_one_chord_tone_higher(self):
        bar = self._bar("arpeggio_inversions", count=9)
        groups = [bar[i : i + 3] for i in range(0, 9, 3)]
        for earlier, later in zip(groups, groups[1:]):
            self.assertGreater(later[0], earlier[0], "a group did not step up a chord tone")

    def test_inversions_use_chord_tones_only(self):
        from notation_exercise_patterns import chord_tone_pcs

        tones = set(chord_tone_pcs("Am6"))
        for midi in self._bar("arpeggio_inversions"):
            self.assertIn(midi % 12, tones)

    def test_sequences_overlap_rather_than_running_straight(self):
        """0 1 2 / 1 2 3 — the second group restarts below where the first ended."""
        bar = self._bar("triplet_sequence", count=6)
        self.assertLess(bar[3], bar[2])

    def test_four_note_groups_overlap_too(self):
        bar = self._bar("four_note_sequence", count=8)
        self.assertLess(bar[4], bar[3])

    def test_sequences_use_the_chord_scale_not_just_chord_tones(self):
        """Am6's scale has F#; a sequence should be able to use scale degrees."""
        from notation_exercise_patterns import chord_tone_pcs

        tones = set(chord_tone_pcs("Am6"))
        used = {m % 12 for m in self._bar("triplet_sequence", count=8)}
        self.assertTrue(used - tones, "sequence used only chord tones, not the scale")

    def test_a_one_note_ladder_does_not_spin(self):
        """Degenerate input must terminate rather than loop."""
        out = exercise_measure_midis(
            "C", pattern="triplet_sequence", key_center="C", low=60, high=60, count=8
        )
        self.assertEqual(len(out), 8)


class TheWholePipelineHonoursTheMode(unittest.TestCase):
    CHORDS = ["Am6", "C7", "B7", "Em6"]

    def test_events_are_produced_for_every_mode(self):
        for mode in EXERCISE_MODES:
            with self.subTest(mode=mode):
                events, plan = build_exercise_events(
                    self.CHORDS, level="Advanced", instrument="Flute",
                    key_center="Am", mode=mode,
                )
                self.assertTrue(events)
                self.assertEqual(len(plan), len(self.CHORDS))

    def test_scales_and_arpeggios_produce_different_plans(self):
        _, scales = build_exercise_events(
            self.CHORDS, level="Advanced", instrument="Flute", key_center="Am", mode="scales"
        )
        _, arps = build_exercise_events(
            self.CHORDS, level="Advanced", instrument="Flute", key_center="Am", mode="arpeggios"
        )
        self.assertNotEqual(scales, arps)

    def test_the_notation_generator_accepts_and_forwards_the_mode(self):
        from practice_notation import generate_practice_notation

        out = {}
        for mode in ("arpeggios", "scales"):
            out[mode] = generate_practice_notation(
                song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
                groove_style="Jazz swing", instrument="Flute", focus="Improvisation",
                section_focus=None, sections={"A": self.CHORDS}, difficulty="advanced",
                exercise_mode=mode,
            )
        self.assertNotEqual(out["arpeggios"].abc, out["scales"].abc)

    def test_the_default_still_works_without_the_argument(self):
        from practice_notation import generate_practice_notation

        res = generate_practice_notation(
            song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
            groove_style="Jazz swing", instrument="Flute", focus="Improvisation",
            section_focus=None, sections={"A": self.CHORDS}, difficulty="advanced",
        )
        self.assertTrue(res.abc)

    def test_scales_mode_respects_the_chord_scale_not_the_key_signature(self):
        """Am6 in A minor must still show F#, which aeolian would not supply."""
        from practice_notation import generate_practice_notation

        res = generate_practice_notation(
            song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
            groove_style="Jazz swing", instrument="Flute", focus="Improvisation",
            section_focus=None, sections={"A": ["Am6"]}, difficulty="advanced",
            exercise_mode="scales",
        )
        self.assertIn("^f", (res.abc or "").lower())


class TheSelectorIsWiredIntoThePracticePage(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

    def test_the_notation_tab_offers_the_choice(self):
        self.assertIn('key="practice_notation_exercise_mode"', self.src)

    def test_the_choice_reaches_the_generator(self):
        self.assertIn("exercise_mode=_notation_exercise_mode", self.src)

    def test_it_uses_the_shared_mode_list_rather_than_hard_coded_strings(self):
        self.assertIn("from notation_exercise_patterns import", self.src)
        self.assertIn("EXERCISE_MODES", self.src)

    def test_changing_it_invalidates_the_cached_notation(self):
        """Otherwise the tab would keep showing the previous mode's exercise."""
        self.assertIn(
            "on_change=_on_practice_filter_change",
            self.src[self.src.index('key="practice_notation_exercise_mode"') - 400 :][:600],
        )


if __name__ == "__main__":
    unittest.main()


class StaleNotationIsInvalidated(unittest.TestCase):
    """Changing the exercise or the difficulty must drop the cached result.

    _notation_sig decides when practice_notation_result is cleared. It listed song,
    section, instrument, focus, chart key, bpm, groove, sax type and capo - but neither
    the exercise mode nor the difficulty, so switching either left the previous
    exercise on screen describing a choice the musician had already changed.
    """

    def setUp(self):
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        start = src.index("_notation_sig = (")
        end = src.index('if st.session_state.get("practice_notation_sig")', start)
        self.sig = src[start:end]

    def test_the_exercise_mode_is_part_of_the_signature(self):
        self.assertIn("practice_notation_exercise_mode", self.sig)

    def test_the_difficulty_is_part_of_the_signature(self):
        self.assertIn("practice_notation_difficulty", self.sig)

    def test_the_existing_inputs_are_still_there(self):
        for token in ("song", "instrument", "focus", "_practice_chart_key", "_practice_bpm"):
            with self.subTest(token=token):
                self.assertIn(token, self.sig)

    def test_the_cache_is_cleared_when_the_signature_moves(self):
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn(
            'if st.session_state.get("practice_notation_sig") != _notation_sig:', src
        )
