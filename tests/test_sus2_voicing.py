"""backing_audio voiced every sus2 chord as a sus4.

``chord_notes`` had a single branch for every suspension::

    elif "sus" in low:
        intervals = [0,5,7,10] if "7" in low else [0,5,7]

Interval 5 is the perfect fourth, so ``Csus2`` came out C-F-G, note for note the
same chord as ``Csus4``, and the backing played a fourth everywhere a chart asked
for a second. That is a wrong note, not a voicing preference: the codebase's own
other implementation, ``music_theory.guide_tones_for_chord``, already returns
('C', 'D') for Csus2 against ('C', 'F') for Csus4.

``sus2`` now spells [0,2,7] (and [0,2,7,10] with a seventh), and ``add2`` spells
[0,2,4,7], keeping the third. ``sus4``, ``7sus4`` and every other quality are
untouched.

Affected catalog songs at the time of the fix (chart cells, all levels):
Man in the Mirror (Csus2 x60), Why Georgia (Gsus2 x40, Fsus2 x14, Bbsus2 x8,
Csus2 x4, Dsus2 x2), The Scientist (Dsus2 x23, Dsus2/C# x2), Shape of You
(Asus2 x16), Kiss Me (Asus2 x14), Iris (Bsus2 x12), Love Story (Asus2 x3),
Daughters (Dsus2 x2), I'm Yours (Dsus2 x2).

**Bare numeric suffixes are deliberately NOT reinterpreted.** An earlier draft
aliased a bare degree to a suspension, so ``D4`` would sound D-G-A rather than
the plain D-F#-A it sounds today. That was withdrawn: ``sus2``/``sus4`` are the
documented input vocabulary (``composition_chord_manual_editor.QUALITY_OPTIONS``)
and a bare degree is not, so teaching the shared parser an undocumented
shorthand would widen the contract without a tested convention behind it. The
one catalog chart that relies on it, Man in the Mirror's ``D4``, is being
respelled as ``Dsus4`` in the chart instead. The guard below pins that decision
so the aliases are not reintroduced by accident.

Engine only: no catalog chart, key, tempo or section changes. Not checked by
ear - the voicings are verified against the interval arithmetic and against
guide_tones_for_chord, so listening confirmation is still wanted.
"""
from __future__ import annotations

import unittest

from backing_audio import bass_note, chord_notes

PC = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
      6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}


def names(chord):
    return [PC[n % 12] for n in chord_notes(chord)]


class Sus2SuspendsTheSecond(unittest.TestCase):
    def test_sus2_is_root_second_fifth(self) -> None:
        self.assertEqual(names("Csus2"), ["C", "D", "G"])
        self.assertEqual(names("Dsus2"), ["D", "E", "A"])
        self.assertEqual(names("Fsus2"), ["F", "G", "C"])
        self.assertEqual(names("Gsus2"), ["G", "A", "D"])
        self.assertEqual(names("Asus2"), ["A", "B", "E"])
        self.assertEqual(names("Bsus2"), ["B", "C#", "F#"])
        self.assertEqual(names("Bbsus2"), ["Bb", "C", "F"])
        self.assertEqual(names("Ebsus2"), ["Eb", "F", "Bb"])

    def test_sus2_is_no_longer_the_same_chord_as_sus4(self) -> None:
        for root in ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"):
            self.assertNotEqual(
                names(f"{root}sus2"), names(f"{root}sus4"),
                f"{root}sus2 and {root}sus4 voiced identically",
            )

    def test_sus2_agrees_with_the_guide_tone_implementation(self) -> None:
        from music_theory import guide_tones_for_chord

        for sym, degree in (("Csus2", "D"), ("Fsus2", "G"), ("Gsus2", "A"), ("Csus4", "F")):
            self.assertIn(degree, names(sym))
            self.assertEqual(guide_tones_for_chord(sym)[1], degree)

    def test_suspension_with_a_seventh(self) -> None:
        self.assertEqual(names("C7sus2"), ["C", "D", "G", "Bb"])
        self.assertEqual(names("C7sus4"), ["C", "F", "G", "Bb"])
        self.assertEqual(names("A7sus4"), ["A", "D", "E", "G"])

    def test_add2_keeps_the_third(self) -> None:
        self.assertEqual(names("Cadd2"), ["C", "D", "E", "G"])
        self.assertEqual(names("Cadd9"), ["C", "E", "G", "D"])

    def test_a_slash_bass_changes_the_bass_not_the_voicing(self) -> None:
        for sym, plain in (("Dsus2/C#", "Dsus2"), ("Csus2/G", "Csus2"),
                           ("Dsus4/B", "Dsus4")):
            self.assertEqual(names(sym), names(plain))
        self.assertEqual(bass_note("Dsus2/C#"), bass_note("C#"))
        self.assertEqual(bass_note("Csus2/G"), bass_note("G"))


class BareDegreesAreNotReinterpreted(unittest.TestCase):
    """A bare numeral is not a documented input, so the parser leaves it alone."""

    def test_bare_degree_still_voices_as_a_plain_triad(self) -> None:
        for bare, plain in (("D4", "D"), ("C4", "C"), ("C2", "C"), ("D2", "D"),
                            ("Eb4", "Eb")):
            self.assertEqual(names(bare), names(plain),
                             f"{bare} must behave as it always has")

    def test_bare_degree_is_not_silently_a_suspension(self) -> None:
        self.assertNotEqual(names("D4"), names("Dsus4"))
        self.assertNotEqual(names("C2"), names("Csus2"))

    def test_no_bare_degree_alias_was_added_to_the_suffix_table(self) -> None:
        from backing_audio import _SUFFIX_ALIASES

        for alias, _canon in _SUFFIX_ALIASES:
            self.assertFalse(
                alias.isdigit(),
                f"bare-degree alias {alias!r} reintroduced into _SUFFIX_ALIASES",
            )


class NothingElseMoved(unittest.TestCase):
    def test_common_qualities_are_unchanged(self) -> None:
        self.assertEqual(names("C"), ["C", "E", "G"])
        self.assertEqual(names("Cm"), ["C", "Eb", "G"])
        self.assertEqual(names("Cmaj7"), ["C", "E", "G", "B"])
        self.assertEqual(names("Am7"), ["A", "C", "E", "G"])
        self.assertEqual(names("C7"), ["C", "E", "G", "Bb"])
        self.assertEqual(names("Cdim"), ["C", "Eb", "F#"])
        self.assertEqual(names("Cdim7"), ["C", "Eb", "F#", "A"])
        self.assertEqual(names("Cm7b5"), ["C", "Eb", "F#", "Bb"])
        self.assertEqual(names("C6"), ["C", "E", "G", "A"])
        self.assertEqual(names("C69"), ["C", "E", "G", "A", "D"])
        self.assertEqual(names("Caug"), ["C", "E", "Ab"])
        self.assertEqual(names("Csus4"), ["C", "F", "G"])

    def test_the_whole_documented_custom_vocabulary_still_voices(self) -> None:
        """Every chord a saved Custom or Composition chart can hold.

        composition_chord_manual_editor is the app's documented input vocabulary,
        so every root x quality x alteration it can produce must voice without
        raising, and sus2 must differ from sus4 throughout.
        """
        from composition_chord_manual_editor import (
            ALTERATION_OPTIONS,
            QUALITY_OPTIONS,
            ROOT_OPTIONS,
        )

        self.assertIn("sus2", QUALITY_OPTIONS)
        self.assertIn("sus4", QUALITY_OPTIONS)
        checked = 0
        for root in ROOT_OPTIONS:
            if not root:
                continue
            for qual in QUALITY_OPTIONS:
                for alt in ALTERATION_OPTIONS:
                    sym = f"{root}{qual}{alt}"
                    notes = chord_notes(sym)
                    self.assertTrue(notes, f"{sym} voiced to nothing")
                    self.assertTrue(
                        all(isinstance(n, int) for n in notes), f"{sym} -> {notes}"
                    )
                    checked += 1
            self.assertNotEqual(
                names(f"{root}sus2"), names(f"{root}sus4"), f"{root}: sus2 == sus4"
            )
        self.assertGreater(checked, 500, "vocabulary sweep did not run")

    def test_slash_voicings_over_the_custom_vocabulary_keep_their_bass(self) -> None:
        from composition_chord_manual_editor import QUALITY_OPTIONS, ROOT_OPTIONS

        for root in [r for r in ROOT_OPTIONS if r][:6]:
            for qual in QUALITY_OPTIONS:
                for bass in ("E", "G", "Bb"):
                    sym = f"{root}{qual}/{bass}"
                    self.assertEqual(names(sym), names(f"{root}{qual}"), sym)
                    self.assertEqual(bass_note(sym), bass_note(bass), sym)


class EveryCatalogSusTokenVoicesItsOwnDegree(unittest.TestCase):
    """Walk the live catalog: no sus2 cell may sound a fourth."""

    def test_no_sus2_cell_in_the_catalog_sounds_a_fourth(self) -> None:
        import copy
        import re

        from chart_level_arrangement import resolve_level_chart
        from song_catalog.catalog import curated_song_records

        sus2 = re.compile(r"^([A-G][#b]?)sus2", re.I)
        seen = 0
        for rec in curated_song_records():
            for level in ("Beginner", "Intermediate", "Advanced"):
                try:
                    _v, secs = resolve_level_chart(copy.deepcopy(rec), level)
                except Exception:
                    continue
                for chords in (secs or {}).values():
                    for tok in chords:
                        for part in str(tok).split("|"):
                            m = sus2.match(part.strip())
                            if not m:
                                continue
                            seen += 1
                            self.assertNotEqual(
                                names(part.strip()), names(f"{m.group(1)}sus4"),
                                f"{rec['title']} {level}: {part!r} sounds as sus4",
                            )
        self.assertGreater(seen, 0, "no sus2 cells found - has the catalog changed?")


if __name__ == "__main__":
    unittest.main()
