"""Altered dominants: the arpeggio must not sound a fifth the symbol denies.

``music_theory.spell_chord_tones`` answers with the plain seventh-chord skeleton for every
altered dominant - C7b5, C7#5, C7alt and C7b9 all come back as C E G Bb. The scale side
already reads the symbol (C7b5 runs altered), so before this fix the two halves of the same
exercise disagreed: the scale avoided the natural fifth and the arpeggio played it.

The correction lives in notation_exercise_patterns.chord_tone_pcs, reading the symbol via
the alteration parser that chord_scale_selection already uses. The shared speller is left
alone deliberately - changing it would touch every caller in the app and needs its own
evidence.
"""

from __future__ import annotations

import unittest

from notation_exercise_patterns import chord_tone_pcs, exercise_measure_midis, scale_pcs

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _pcs(chord: str) -> set[int]:
    return set(chord_tone_pcs(chord))


class TheSharedSpellerStillIgnoresAlterations(unittest.TestCase):
    """Documents why the correction is needed, so it is not mistaken for dead code."""

    def test_spell_chord_tones_returns_the_same_shell_for_every_altered_symbol(self):
        from music_theory import spell_chord_tones

        shell = spell_chord_tones("C7")
        for chord in ("C7alt", "C7b5", "C7#5", "C7b9", "C7#9"):
            with self.subTest(chord=chord):
                self.assertEqual(spell_chord_tones(chord), shell)


class TheFifthFollowsTheSymbol(unittest.TestCase):
    def test_b5_lowers_the_fifth(self):
        self.assertIn(NAMES.index("F#"), _pcs("C7b5"))
        self.assertNotIn(NAMES.index("G"), _pcs("C7b5"))

    def test_sharp5_raises_the_fifth(self):
        self.assertIn(NAMES.index("G#"), _pcs("C7#5"))
        self.assertNotIn(NAMES.index("G"), _pcs("C7#5"))

    def test_a_bare_alt_drops_the_fifth_rather_than_inventing_one(self):
        """"alt" does not say which fifth, so none is guessed."""
        tones = _pcs("C7alt")
        self.assertNotIn(NAMES.index("G"), tones)
        self.assertNotIn(NAMES.index("F#"), tones)
        self.assertNotIn(NAMES.index("G#"), tones)
        self.assertEqual(tones, {NAMES.index(n) for n in ("C", "E", "A#")})

    def test_an_altered_ninth_leaves_the_fifth_alone(self):
        """b9 alters the ninth, not the fifth."""
        self.assertIn(NAMES.index("G"), _pcs("C7b9"))

    def test_unaltered_chords_are_untouched(self):
        for chord, expected in (
            ("C7", ("C", "E", "G", "A#")),
            ("Cmaj7", ("C", "E", "G", "B")),
            ("Am6", ("A", "C", "E", "F#")),
            ("Cm7", ("C", "D#", "G", "A#")),
        ):
            with self.subTest(chord=chord):
                self.assertEqual(_pcs(chord), {NAMES.index(n) for n in expected})

    def test_the_correction_applies_on_any_root(self):
        self.assertIn(NAMES.index("C#"), _pcs("G7b5"))   # Db is G's b5
        self.assertNotIn(NAMES.index("D"), _pcs("G7b5"))

    def test_a_chord_with_no_fifth_at_all_is_safe(self):
        self.assertTrue(chord_tone_pcs("C5alt"))


class TheArpeggioExerciseSoundsTheRightFifth(unittest.TestCase):
    def _arp(self, chord):
        midis = exercise_measure_midis(
            chord, pattern="arpeggio_up", key_center="C", low=60, high=84,
            start_midi=67, count=4,
        )
        return {m % 12 for m in midis}

    def test_a_flat_five_chord_no_longer_plays_a_natural_fifth(self):
        self.assertNotIn(NAMES.index("G"), self._arp("C7b5"))

    def test_a_sharp_five_chord_no_longer_plays_a_natural_fifth(self):
        self.assertNotIn(NAMES.index("G"), self._arp("C7#5"))

    def test_an_altered_chord_no_longer_plays_a_natural_fifth(self):
        self.assertNotIn(NAMES.index("G"), self._arp("C7alt"))

    def test_the_altered_symbols_no_longer_all_sound_identical(self):
        """Before the fix C7, C7alt, C7b5 and C7#5 produced the same four notes."""
        shapes = {c: tuple(sorted(self._arp(c))) for c in ("C7", "C7alt", "C7b5", "C7#5")}
        self.assertEqual(len(set(shapes.values())), 4, shapes)

    def test_the_inversion_drill_inherits_the_corrected_fifth(self):
        midis = exercise_measure_midis(
            "C7b5", pattern="arpeggio_inversions", key_center="C", low=60, high=84,
            start_midi=67, count=9,
        )
        self.assertNotIn(NAMES.index("G"), {m % 12 for m in midis})


class ArpeggioAndScaleNoLongerContradict(unittest.TestCase):
    """The two halves of one exercise must not disagree about the same chord."""

    FIFTH_ALTERED = ("C7alt", "C7b5", "C7#5", "G7alt", "F7b5")

    def test_fifth_altered_chords_are_consistent_in_every_key(self):
        for chord in self.FIFTH_ALTERED:
            for key in ("C", "Am", "G", "F", "Bb"):
                with self.subTest(chord=chord, key=key):
                    self.assertTrue(
                        _pcs(chord).issubset(set(scale_pcs(chord, key))),
                        f"{chord} in {key}: {sorted(_pcs(chord) - set(scale_pcs(chord, key)))}",
                    )

    def test_ordinary_harmony_is_consistent_too(self):
        for chord in ("C7", "Cmaj7", "Am6", "Em6", "AmMaj7", "Am7", "Dm7b5", "Cm9", "Csus4"):
            for key in ("C", "Am", "G", "F"):
                with self.subTest(chord=chord, key=key):
                    self.assertTrue(_pcs(chord).issubset(set(scale_pcs(chord, key))))

    @unittest.expectedFailure
    def test_known_open_defect_b9_and_b13_still_disagree(self):
        """C7b9 keeps its natural fifth (right: b9 alters the ninth), but
        chord_scale_selection gives it the altered scale, which has none.

        The textbook scale for a plain 7b9 is half-whole diminished, which does contain
        the natural fifth. Left unfixed on purpose: that is a change to the shared scale
        selector and needs its own evidence and regression run, not a quiet edit here.
        This test is expected to fail and will start passing when that is addressed.
        """
        for chord in ("C7b9", "C7b13"):
            self.assertTrue(_pcs(chord).issubset(set(scale_pcs(chord, "C"))), chord)


if __name__ == "__main__":
    unittest.main()
