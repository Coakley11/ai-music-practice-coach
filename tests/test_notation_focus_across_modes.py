"""Slice 4 — the Practice Focus has to mean something in every mode, on every instrument.

Two things were wrong before this. ``pattern_plan`` dropped the focus entirely as soon as a
mode was chosen explicitly, so picking Scales threw away the focus the musician had also
chosen. And the piano ignored its own focus vocabulary completely: the canonical
``generation_focus_key`` recognises six keys, and none of Voicings, Left-Hand Patterns,
Comping, Voice Leading, Inversions or Reharmonization maps to any of them, so all seventeen
piano foci produced one identical exercise.

The rule these tests hold the code to is that the mode decides *which* study runs and the
focus decides *how* it is practised. A Guide Tones focus must not turn a scale study into an
arpeggio study, and a focus must not pull an Advanced drill down to a Beginner.

Where a focus genuinely has no opinion - Tone, Timing - it is expected to change nothing.
That is the honest answer, not a gap, so it is asserted as a property of a *set* of foci
rather than demanded of each one.
"""

from __future__ import annotations

import unittest

from notation_exercise_patterns import (
    EXERCISE_PATTERNS,
    mode_plan_for_focus,
    pattern_plan,
)
from practice_notation import generate_practice_notation
from practice_setup_controls import focus_options_for_instrument

CHORDS = ["Am6", "C7", "B7", "Em6"]
ARPEGGIO_FAMILY = {"arpeggio_up", "arpeggio_down", "arpeggio_up_down",
                   "arpeggio_inversions", "voice_leading"}
SCALE_FAMILY = {"scale_up", "scale_down", "scale_up_down", "thirds", "fourths",
                "triplet_sequence", "four_note_sequence"}


def _render(instrument, mode, focus, difficulty="medium"):
    res = generate_practice_notation(
        song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
        groove_style="Jazz swing", instrument=instrument, focus=focus,
        section_focus=None, sections={"A": CHORDS},
        difficulty=difficulty, exercise_mode=mode,
    )
    return (res.abc, res.body, res.html)


def _distinct(instrument, mode, difficulty="medium"):
    foci = focus_options_for_instrument(instrument)
    return len({_render(instrument, mode, f, difficulty) for f in foci}), len(foci)


class TheModeStaysAuthoritative(unittest.TestCase):
    """The focus colours the study; it never changes which study it is."""

    def test_a_scales_mode_only_ever_plans_scale_patterns(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            for focus in focus_options_for_instrument("Saxophone"):
                with self.subTest(level=level, focus=focus):
                    self.assertTrue(
                        set(mode_plan_for_focus("scales", level, focus)) <= SCALE_FAMILY
                    )

    def test_an_arpeggios_mode_only_ever_plans_arpeggio_patterns(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            for focus in focus_options_for_instrument("Piano"):
                with self.subTest(level=level, focus=focus):
                    self.assertTrue(
                        set(mode_plan_for_focus("arpeggios", level, focus))
                        <= ARPEGGIO_FAMILY
                    )

    def test_a_guide_tones_focus_does_not_smuggle_arpeggios_into_a_scale_study(self):
        plan = mode_plan_for_focus("scales", "Advanced", "Guide Tones")
        self.assertFalse(set(plan) & ARPEGGIO_FAMILY)

    def test_a_focus_cannot_pull_an_advanced_drill_down_to_a_beginner(self):
        """Otherwise a Technique focus would hand a beginner four-note sequences."""
        beginner = set(mode_plan_for_focus("scales", "Beginner", "Technique"))
        self.assertFalse(beginner & {"triplet_sequence", "four_note_sequence", "fourths"})

    def test_every_planned_pattern_is_a_real_pattern(self):
        for mode in ("scales", "arpeggios"):
            for level in ("Beginner", "Intermediate", "Advanced"):
                for focus in ("", "Technique", "Guide Tones", "Inversions", "Bebop Phrasing"):
                    with self.subTest(mode=mode, level=level, focus=focus):
                        for p in mode_plan_for_focus(mode, level, focus):
                            self.assertIn(p, EXERCISE_PATTERNS)

    def test_a_focus_with_no_opinion_leaves_the_plan_alone(self):
        for focus in ("Tone", "Timing", "Dynamics", "Breath Support"):
            with self.subTest(focus=focus):
                self.assertEqual(
                    mode_plan_for_focus("scales", "Advanced", focus),
                    mode_plan_for_focus("scales", "Advanced", ""),
                )

    def test_a_focus_that_does_have_an_opinion_reorders_the_plan(self):
        self.assertNotEqual(
            mode_plan_for_focus("scales", "Advanced", "Technique"),
            mode_plan_for_focus("scales", "Advanced", ""),
        )

    def test_the_plan_still_reaches_pattern_plan(self):
        self.assertNotEqual(
            pattern_plan("Advanced", 4, mode="scales", focus="Technique"),
            pattern_plan("Advanced", 4, mode="scales", focus=""),
        )

    def test_an_unknown_mode_is_still_auto(self):
        self.assertEqual(
            pattern_plan("Advanced", 4, mode="sideways", focus="Technique"),
            pattern_plan("Advanced", 4, mode="auto", focus="Technique"),
        )


class TheFocusReachesEveryModeOnEveryInstrument(unittest.TestCase):
    """The regression this slice exists to prevent: a mode swallowing the focus."""

    def test_explicit_modes_are_focus_sensitive_for_line_instruments(self):
        for mode in ("scales", "arpeggios"):
            with self.subTest(mode=mode):
                n, total = _distinct("Saxophone", mode, "advanced")
                self.assertGreater(n, 1, f"all {total} foci gave one exercise")

    def test_explicit_modes_are_focus_sensitive_for_the_piano(self):
        for mode in ("scales", "arpeggios"):
            with self.subTest(mode=mode):
                n, _ = _distinct("Piano", mode, "advanced")
                self.assertGreater(n, 1)

    def test_explicit_modes_are_focus_sensitive_for_the_guitar(self):
        for mode in ("scales", "arpeggios"):
            with self.subTest(mode=mode):
                n, _ = _distinct("Guitar", mode, "advanced")
                self.assertGreater(n, 1)

    def test_the_piano_now_answers_to_its_own_focus_vocabulary(self):
        """All seventeen piano foci used to produce one identical exercise in Auto."""
        for difficulty in ("easy", "medium", "advanced"):
            with self.subTest(difficulty=difficulty):
                n, _ = _distinct("Piano", "auto", difficulty)
                self.assertGreater(n, 1)

    def test_auto_stays_focus_sensitive_everywhere_it_already_was(self):
        for inst in ("Saxophone", "Guitar", "Piano"):
            with self.subTest(instrument=inst):
                n, _ = _distinct(inst, "auto")
                self.assertGreater(n, 1)

    def test_a_beginner_explicit_mode_is_allowed_to_be_insensitive(self):
        """Documented, not hidden: at Beginner a mode has exactly two drills.

        The level ceiling deliberately stops a focus reaching for the Advanced sequences, so
        there is nothing left for it to reorder. The focus still shows up elsewhere at that
        level - the piano's hand roles, the guitar's position, the practice cues.
        """
        self.assertEqual(len(mode_plan_for_focus("scales", "Beginner", "")), 2)
        n, _ = _distinct("Piano", "auto", "easy")
        self.assertGreater(n, 1, "the focus must still reach the beginner somewhere")


class ThePianoLeftHandHasAJob(unittest.TestCase):
    def test_each_focus_that_names_a_left_hand_job_gets_that_role(self):
        from piano_grand_staff import (
            LH_OCTAVE,
            LH_ROOT_SEVENTH,
            LH_SHELL_3_7,
            LH_THIRD_ROOT,
            left_hand_role,
        )

        self.assertEqual(left_hand_role("Intermediate", "Left-Hand Patterns"), LH_OCTAVE)
        self.assertEqual(left_hand_role("Intermediate", "Voice Leading"), LH_ROOT_SEVENTH)
        self.assertEqual(left_hand_role("Intermediate", "Inversions"), LH_THIRD_ROOT)
        self.assertEqual(left_hand_role("Intermediate", "Reharmonization"), LH_SHELL_3_7)

    def test_a_focus_about_the_right_hand_line_claims_no_left_hand_role(self):
        """Improvisation and Melody say nothing about the left hand, so the level decides."""
        from piano_grand_staff import LH_ROOT_FIFTH, left_hand_role

        for focus in ("Improvisation", "Melody", "Harmony", "Phrasing", "Rhythm"):
            with self.subTest(focus=focus):
                self.assertEqual(left_hand_role("Intermediate", focus), LH_ROOT_FIFTH)

    def test_a_focus_that_names_one_outranks_the_level(self):
        from piano_grand_staff import LH_OCTAVE, left_hand_role

        for level in ("Beginner", "Intermediate", "Advanced"):
            with self.subTest(level=level):
                self.assertEqual(left_hand_role(level, "Left-Hand Patterns"), LH_OCTAVE)

    def test_the_level_progression_survives_where_no_focus_claims_it(self):
        from piano_grand_staff import (
            LH_ROOT,
            LH_ROOT_FIFTH,
            LH_ROOT_SEVENTH,
            left_hand_role,
        )

        self.assertEqual(left_hand_role("Beginner", "Tone"), LH_ROOT)
        self.assertEqual(left_hand_role("Intermediate", "Tone"), LH_ROOT_FIFTH)
        self.assertEqual(left_hand_role("Advanced", "Tone"), LH_ROOT_SEVENTH)

    def test_a_role_needing_a_seventh_falls_back_on_a_triad(self):
        """Rather than borrowing a note the chord does not contain."""
        from piano_grand_staff import hands_for_voicing

        left, _right = hands_for_voicing([60, 64, 67], "C", focus="Voice Leading")
        self.assertTrue(left)
        self.assertTrue(set(m % 12 for m in left) <= {0, 4, 7})

    def test_the_octave_role_really_doubles_the_root(self):
        """And doubles it downwards, where a left-hand foundation lives."""
        from piano_grand_staff import MIDDLE_C, hands_for_voicing

        left, _ = hands_for_voicing([60, 64, 67, 71], "Cmaj7", focus="Left-Hand Patterns")
        self.assertEqual(len(left), 2)
        self.assertEqual(len({m % 12 for m in left}), 1)   # one pitch class, two octaves
        self.assertEqual(max(left) - min(left), 12)
        self.assertLess(max(left), MIDDLE_C)

    def test_the_hands_never_collide_whatever_the_focus(self):
        from chord_navigation_notation import build_connected_piano_voicings
        from piano_grand_staff import hands_for_voicing

        for focus in focus_options_for_instrument("Piano"):
            for level in ("Beginner", "Intermediate", "Advanced"):
                for v in build_connected_piano_voicings(CHORDS, level=level):
                    left, right = hands_for_voicing(
                        list(v.midis), v.chord, level=level, focus=focus
                    )
                    with self.subTest(focus=focus, level=level, chord=v.chord):
                        if left and right:
                            self.assertLess(max(left), min(right))

    def test_the_left_hand_stays_on_the_keyboard(self):
        from piano_grand_staff import PIANO_HIGH, PIANO_LOW, hands_for_voicing

        for focus in focus_options_for_instrument("Piano"):
            left, right = hands_for_voicing([60, 64, 67, 71], "Cmaj7", focus=focus)
            for m in left + right:
                with self.subTest(focus=focus, midi=m):
                    self.assertTrue(PIANO_LOW <= m <= PIANO_HIGH)

    def test_one_focus_means_one_thing_across_the_pianos_modes(self):
        """The arpeggio left hand uses the same roles the Auto voicings do."""
        import inspect

        from practice_notation import _build_piano_voicings

        src = inspect.getsource(_build_piano_voicings)
        self.assertIn("left_hand_role", src)


class NoNewFocusVocabularyWasInvented(unittest.TestCase):
    """The canonical focus list stays the only list of foci."""

    def test_every_focus_key_matches_something_the_page_offers(self):
        from notation_exercise_patterns import _FOCUS_EMPHASIS
        from piano_grand_staff import LH_ROLE_FOR_FOCUS

        offered = {
            f.lower()
            for inst in ("Piano", "Guitar", "Bass", "Saxophone")
            for f in focus_options_for_instrument(inst)
        }
        for needle in list(_FOCUS_EMPHASIS) + list(LH_ROLE_FOR_FOCUS):
            with self.subTest(needle=needle):
                self.assertTrue(
                    any(needle in f for f in offered),
                    f"{needle!r} matches no Practice Focus the app offers",
                )


if __name__ == "__main__":
    unittest.main()
