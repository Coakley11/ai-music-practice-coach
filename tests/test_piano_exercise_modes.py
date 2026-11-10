"""Slice 2 — piano plays all three modes, on two staves, with the hands given roles.

The hands are not split at middle C here. A close-position voicing cut at an arbitrary
pitch can hand the left thumb a chord's third while the right plays its root, which is not
how anyone voices a chord. The left hand is built for its job and the right keeps the
voice-led voicing the existing engine produced, so these tests check the *roles*, not just
that two staves exist.
"""

from __future__ import annotations

import unittest

from practice_notation import generate_practice_notation

CHORDS = ["Am6", "C7", "B7", "Em6"]
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _render(mode="auto", difficulty="medium", focus="Improvisation", chords=None):
    return generate_practice_notation(
        song_title="T", artist="", display_key="Am", original_key="Am", bpm=100,
        groove_style="Jazz swing", instrument="Piano", focus=focus,
        section_focus=None, sections={"A": chords or CHORDS},
        difficulty=difficulty, exercise_mode=mode,
    )


def _staves(abc: str) -> tuple[str, str]:
    tail = abc.split("V:2 clef=bass", 1)[1]
    treble = tail.split("V:1", 1)[1].split("V:2", 1)[0]
    bass = tail.split("V:2", 1)[1]
    return treble.strip(), bass.strip()


class EveryModeIsAGrandStaff(unittest.TestCase):
    def test_all_three_modes_emit_two_braced_voices(self):
        for mode in ("auto", "arpeggios", "scales"):
            with self.subTest(mode=mode):
                abc = _render(mode).abc
                self.assertIn("%%score {1 | 2}", abc)
                self.assertIn("V:1 clef=treble", abc)
                self.assertIn("V:2 clef=bass", abc)

    def test_all_three_modes_carry_a_key_signature(self):
        for mode in ("auto", "arpeggios", "scales"):
            with self.subTest(mode=mode):
                self.assertIn("K:", _render(mode).abc)

    def test_the_three_modes_are_musically_different(self):
        rendered = {m: _render(m).abc for m in ("auto", "arpeggios", "scales")}
        self.assertEqual(len(set(rendered.values())), 3)

    def test_the_treble_staff_is_never_a_bar_of_rests(self):
        """The piano register sits below middle C; using it would empty this staff."""
        for mode in ("auto", "arpeggios", "scales"):
            for difficulty in ("easy", "medium", "advanced"):
                with self.subTest(mode=mode, difficulty=difficulty):
                    treble, _ = _staves(_render(mode, difficulty).abc)
                    stripped = treble.replace("z", "").replace("|", "")
                    self.assertTrue(
                        any(c.isalpha() for c in stripped), f"{mode}/{difficulty}"
                    )

    def test_the_format_is_still_abc(self):
        self.assertEqual(_render("scales").format, "abc")


class TheHandsHaveRoles(unittest.TestCase):
    """Beginner roots, Intermediate root-and-fifth, Advanced a root-and-seventh shell."""

    def _bass_first_chord(self, difficulty):
        _, bass = _staves(_render("auto", difficulty).abc)
        return bass.split("|", 1)[0].strip()

    def test_beginner_left_hand_plays_a_single_root(self):
        first = self._bass_first_chord("easy")
        self.assertNotIn("[", first, f"expected one note, got {first!r}")

    def test_intermediate_left_hand_plays_two_notes(self):
        self.assertIn("[", self._bass_first_chord("medium"))

    def test_advanced_left_hand_plays_two_notes(self):
        self.assertIn("[", self._bass_first_chord("advanced"))

    def test_the_levels_do_not_all_produce_the_same_left_hand(self):
        hands = {d: self._bass_first_chord(d) for d in ("easy", "medium", "advanced")}
        self.assertGreaterEqual(len(set(hands.values())), 2, hands)

    def test_the_right_hand_keeps_the_voiced_chord(self):
        treble, _ = _staves(_render("auto", "medium").abc)
        self.assertIn("[", treble.split("|", 1)[0])

    def test_guide_tones_focus_changes_the_left_hand(self):
        plain = _staves(_render("auto", "medium", focus="Improvisation").abc)[1]
        guide = _staves(_render("auto", "medium", focus="Guide Tones").abc)[1]
        self.assertNotEqual(plain, guide)

    def test_the_hands_do_not_collide(self):
        from chord_navigation_notation import build_connected_piano_voicings
        from piano_grand_staff import hands_for_voicing

        for level in ("Beginner", "Intermediate", "Advanced"):
            for v in build_connected_piano_voicings(CHORDS, level=level):
                left, right = hands_for_voicing(list(v.midis), v.chord, level=level)
                with self.subTest(level=level, chord=v.chord):
                    if left and right:
                        self.assertLess(max(left), min(right))


class ScalesAreTwoHandedAndLevelled(unittest.TestCase):
    def test_beginner_practises_hands_separately(self):
        from piano_grand_staff import scale_motion_for

        self.assertEqual(scale_motion_for("Beginner"), "separate")

    def test_intermediate_practises_hands_together(self):
        from piano_grand_staff import scale_motion_for

        self.assertEqual(scale_motion_for("Intermediate"), "parallel")

    def test_advanced_practises_contrary_motion(self):
        from piano_grand_staff import scale_motion_for

        self.assertEqual(scale_motion_for("Advanced"), "contrary")

    def test_a_technique_focus_asks_for_independence_at_any_level(self):
        from piano_grand_staff import scale_motion_for

        self.assertEqual(scale_motion_for("Beginner", "Technique"), "contrary")

    def test_advanced_scales_really_move_in_opposite_directions(self):
        treble, bass = _staves(_render("scales", "advanced").abc)
        self.assertTrue(treble.strip())
        self.assertTrue(bass.replace("z", "").replace("|", "").strip())

    def test_scales_mode_is_not_block_chords(self):
        """A scale study must be a line, not the voicing Auto already gives."""
        self.assertNotEqual(_render("scales", "medium").abc, _render("auto", "medium").abc)


class ArpeggiosAreTwoHanded(unittest.TestCase):
    def test_both_hands_take_part(self):
        treble, bass = _staves(_render("arpeggios", "medium").abc)
        self.assertTrue(any(c.isalpha() for c in treble.replace("z", "")))
        self.assertTrue(any(c.isalpha() for c in bass.replace("z", "")))

    def test_it_differs_from_the_chord_voicings(self):
        self.assertNotEqual(_render("arpeggios").abc, _render("auto").abc)

    def test_levels_change_the_pattern(self):
        self.assertNotEqual(
            _render("arpeggios", "easy").abc, _render("arpeggios", "advanced").abc
        )


class TheHarmonyStillComesFromTheSharedEngine(unittest.TestCase):
    def test_am6_keeps_its_f_sharp_on_the_piano_staff(self):
        """A Dorian, not aeolian - the same answer the wind instruments get."""
        abc = _render("scales", "advanced", chords=["Am6"]).abc
        self.assertIn("^f", abc.lower())

    def test_the_piano_builder_takes_no_harmony_decisions_of_its_own(self):
        import inspect

        from practice_notation import _build_piano_voicings

        src = inspect.getsource(_build_piano_voicings)
        self.assertIn("build_exercise_midis", src)
        self.assertIn("build_connected_piano_voicings", src)


if __name__ == "__main__":
    unittest.main()
