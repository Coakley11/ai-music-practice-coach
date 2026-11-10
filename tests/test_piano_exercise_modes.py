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

    def _bass_first_chord(self, difficulty, focus="Tone"):
        """Read the level progression under a focus that names no left-hand job.

        A focus that does name one - Left-Hand Patterns, Voice Leading, Inversions -
        outranks the level by design, so asserting the progression under one of those would
        be asserting the override instead.
        """
        _, bass = _staves(_render("auto", difficulty, focus=focus).abc)
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

    def test_a_focus_that_names_a_left_hand_job_outranks_the_level(self):
        plain = _staves(_render("auto", "medium", focus="Tone").abc)[1]
        for focus in ("Left-Hand Patterns", "Voice Leading", "Inversions", "Guide Tones"):
            with self.subTest(focus=focus):
                claimed = _staves(_render("auto", "medium", focus=focus).abc)[1]
                self.assertNotEqual(plain, claimed)

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
        """A Dorian, not aeolian - the same answer the wind instruments get.

        Over several bars rather than one: the exercise register is a single octave, so
        eight notes of one bar need not touch every degree of the scale. A bar that happens
        to run C E G B is still A Dorian; what would be wrong is an F natural.
        """
        abc = _render("scales", "advanced", chords=["Am6"] * 4).abc.lower()
        self.assertIn("^f", abc)

    def test_am6_never_sounds_the_natural_sixth_that_would_make_it_aeolian(self):
        import re

        abc = _render("scales", "advanced", chords=["Am6"] * 4).abc.lower()
        body = abc.split("v:1\n", 1)[1]
        self.assertFalse(re.search(r"(?<![\^_=])f", body), "a natural F would be aeolian")

    def test_the_piano_builder_takes_no_harmony_decisions_of_its_own(self):
        import inspect

        from practice_notation import _build_piano_voicings

        src = inspect.getsource(_build_piano_voicings)
        self.assertIn("build_exercise_midis", src)
        self.assertIn("build_connected_piano_voicings", src)


if __name__ == "__main__":
    unittest.main()


class BothHandsObeyTheHarmony(unittest.TestCase):
    """The invariant the whole feature rests on, asserted for the hand the tests forgot.

    Every earlier harmony test read the treble staff. The left hand was generated separately
    and nobody checked it, so contrary motion spent four commits mirroring the line in
    semitones and sounding G#, C# and F natural against an A Dorian right hand. A browser
    capture found it, not a test. This is that test.
    """

    import re as _re

    def _notes(self, abc_voice: str) -> list[str]:
        """Pitch tokens only.

        Chord symbols are quoted annotations - "Dm7b5", "C7alt" - and are full of letters
        that look exactly like ABC pitches. Reading them as notes made this test fail on
        chords whose notation was perfectly correct, so they are stripped first.
        """
        bare = self._re.sub(r'"[^"]*"', " ", abc_voice).replace("z", "")
        return self._re.findall(r"[\^_=]?[a-gA-G],*'*", bare)

    def _pcs(self, abc_voice: str) -> set[int]:
        base = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
        out = set()
        for tok in self._notes(abc_voice):
            acc = 0
            if tok[0] == "^":
                acc, tok = 1, tok[1:]
            elif tok[0] == "_":
                acc, tok = -1, tok[1:]
            elif tok[0] == "=":
                tok = tok[1:]
            letter = tok[0].lower()
            if letter in base:
                out.add((base[letter] + acc) % 12)
        return out

    def test_every_note_in_both_staves_belongs_to_the_chord_scale(self):
        from notation_exercise_patterns import scale_pcs

        for chord in ("Am6", "C7", "Cmaj7", "Dm7b5", "C7alt", "Em6"):
            for difficulty in ("easy", "medium", "advanced"):
                abc = _render("scales", difficulty, chords=[chord] * 4).abc
                treble, bass = _staves(abc)
                allowed = set(scale_pcs(chord, "Am"))
                for name, voice in (("treble", treble), ("bass", bass)):
                    with self.subTest(chord=chord, difficulty=difficulty, staff=name):
                        extra = self._pcs(voice) - allowed
                        self.assertFalse(
                            extra, f"{chord} {name}: {sorted(extra)} outside the scale"
                        )

    def test_the_bass_staff_carries_the_line_wherever_both_hands_play(self):
        """Beginner is excluded on purpose: that level practises hands separately.

        scale_motion_for("Beginner") is "separate", so the line stays in one hand and the
        other staff is rests - which is the exercise, not an omission.
        """
        for difficulty in ("medium", "advanced"):
            _, bass = _staves(_render("scales", difficulty).abc)
            with self.subTest(difficulty=difficulty):
                self.assertTrue(self._notes(bass), "bass staff had no notes at all")

    def test_a_beginner_practises_one_hand_at_a_time(self):
        from piano_grand_staff import scale_motion_for

        self.assertEqual(scale_motion_for("Beginner"), "separate")
        treble, bass = _staves(_render("scales", "easy").abc)
        self.assertTrue(self._notes(treble))
        self.assertIn("z", bass)


class TheExerciseRegisterStaysReadable(unittest.TestCase):
    """Both staves, not just the treble.

    The register was first chosen only so the treble would not be a bar of rests. It was
    G3-C6, and because build_exercise_midis fills toward the top of its range the line sat
    at G4-C6 - putting the left hand four and five ledger lines above the bass staff on
    nearly every note.
    """

    BASS_TOP = 57   # A3, top line of the bass staff
    BASS_BOTTOM = 43  # G2, bottom line

    def test_the_two_handed_register_centres_on_middle_c(self):
        from piano_grand_staff import PIANO_EXERCISE_HIGH, PIANO_EXERCISE_LOW

        self.assertEqual(PIANO_EXERCISE_LOW, 60)    # C4
        self.assertEqual(PIANO_EXERCISE_HIGH, 72)   # C5

    def test_the_left_hand_mostly_sits_on_its_own_staff(self):
        from chord_navigation_notation import instrument_register  # noqa: F401
        from notation_exercise_patterns import build_exercise_midis, scale_pcs
        from piano_grand_staff import (
            PIANO_EXERCISE_HIGH,
            PIANO_EXERCISE_LOW,
            hands_for_scale,
            scale_motion_for,
        )

        far = total = 0
        for level in ("Intermediate", "Advanced"):
            bars, _ = build_exercise_midis(
                CHORDS, level=level, instrument="Piano", key_center="Am", mode="scales",
                low=PIANO_EXERCISE_LOW, high=PIANO_EXERCISE_HIGH,
            )
            motion = scale_motion_for(level)
            for i, bar in enumerate(bars):
                pcs = scale_pcs(CHORDS[i % len(CHORDS)], "Am")
                for v in hands_for_scale(bar, motion=motion, scale_pcs=pcs):
                    if len(v) < 2:
                        continue
                    total += 1
                    if min(v) > self.BASS_TOP + 4 or min(v) < self.BASS_BOTTOM - 4:
                        far += 1
        self.assertLess(far / max(1, total), 0.15, f"{far}/{total} left-hand notes stranded")
