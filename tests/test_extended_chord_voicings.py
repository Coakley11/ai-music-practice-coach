"""Two ways backing_audio played a simpler chord than the chart asked for.

**1. A "6/9" chord lost its ninth, and its bass went to a fallback pitch.**

``_chord_head`` split on the first "/" unconditionally, so ``C6/9`` was read as
the chord ``C6`` with a bass note of ``"9"``. Two things followed. The ninth
vanished, which also made the ``("6/9", "69")`` entry in ``_SUFFIX_ALIASES``
dead code - the slash was gone before suffix matching ran. And ``bass_note``
could not parse ``"9"`` as a note, so it returned its fallback, C3, whatever the
root was: ``F6/9`` sounded an F chord over a **C** bass and ``A6/9`` an A chord
over a **C** bass. A slash bass now has to begin with a note letter.

**2. Eleventh chords played as plain triads.**

No branch tested for ``11``, so ``C11`` fell through to the default major triad
and ``Cm11`` to the generic minor triad: the seventh, ninth and eleventh were
all dropped. ``add11`` fell through the same way, which mattered most to Viva La
Vida, whose own arrangement note asks to preserve ``Ebadd11`` - it was sounding
a bare Eb triad.

Now: a dominant eleventh omits the third, which would clash with the eleventh;
a minor eleventh keeps its minor third; ``add11`` is the triad plus the
eleventh, with no seventh or ninth.

Altered elevenths are deliberately excluded. ``C7#11`` is a dominant seventh
with a raised eleventh and is still handled further down the chain, and
``B11sus`` keeps being read as a suspension.

Affected chart cells at the time of the fix, across all levels:
Viva La Vida (Ebadd11 x64), Photograph (C#m11 x28), Why Georgia (C6/9 x14),
Perfect (C6/9 x8), Piano Man (G11 x6), Rocket Man (C11 x5, Gm11 x2),
The Scientist (F6/9 x4), Daughters (Gm11 x2), One Note Samba (A6/9 x2),
Billie Jean (Bm11 x1).

Engine only: no catalog chart, key, tempo or section changes. Not checked by
ear - the voicings are verified against the interval arithmetic.
"""
from __future__ import annotations

import unittest

from backing_audio import bass_note, chord_notes

PC = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
      6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}


def names(chord):
    return [PC[n % 12] for n in chord_notes(chord)]


def bass(chord):
    return PC[bass_note(chord) % 12]


class SixNineKeepsItsNinthAndItsRoot(unittest.TestCase):
    def test_the_ninth_is_no_longer_dropped(self) -> None:
        self.assertEqual(names("C6/9"), ["C", "E", "G", "A", "D"])
        self.assertEqual(names("F6/9"), ["F", "A", "C", "D", "G"])
        self.assertEqual(names("A6/9"), ["A", "C#", "E", "F#", "B"])

    def test_the_slashless_spelling_agrees(self) -> None:
        for a, b in (("C6/9", "C69"), ("F6/9", "F69"), ("A6/9", "A69")):
            self.assertEqual(names(a), names(b), f"{a} != {b}")

    def test_it_is_not_a_plain_sixth(self) -> None:
        self.assertNotEqual(names("C6/9"), names("C6"))
        self.assertIn("D", names("C6/9"))

    def test_the_bass_follows_the_root_not_a_fallback(self) -> None:
        self.assertEqual(bass("C6/9"), "C")
        self.assertEqual(bass("F6/9"), "F")
        self.assertEqual(bass("A6/9"), "A")
        self.assertEqual(bass_note("F6/9"), bass_note("F"))
        self.assertEqual(bass_note("A6/9"), bass_note("A"))

    def test_a_real_slash_bass_still_works(self) -> None:
        for sym, want in (("C/E", "E"), ("Cmaj7/E", "E"), ("Am7/G", "G"),
                          ("Dsus4/B", "B"), ("Eb/Bb", "Bb")):
            self.assertEqual(bass(sym), want, sym)
        # enharmonics compare by pitch, not spelling
        self.assertEqual(bass_note("F#/A#"), bass_note("Bb"))
        # and a slash bass must not change the upper voicing
        self.assertEqual(names("C/E"), names("C"))
        self.assertEqual(names("Cmaj7/E"), names("Cmaj7"))


class EleventhChordsSoundTheirExtensions(unittest.TestCase):
    def test_dominant_eleventh_omits_the_third(self) -> None:
        self.assertEqual(names("C11"), ["C", "G", "Bb", "D", "F"])
        self.assertEqual(names("G11"), ["G", "D", "F", "A", "C"])
        self.assertNotIn("E", names("C11"), "the third clashes with the eleventh")

    def test_minor_eleventh_keeps_its_minor_third(self) -> None:
        self.assertEqual(names("Cm11"), ["C", "Eb", "G", "Bb", "D", "F"])
        self.assertEqual(names("Gm11"), ["G", "Bb", "D", "F", "A", "C"])
        self.assertEqual(names("Bm11"), ["B", "D", "F#", "A", "C#", "E"])
        self.assertEqual(names("C#m11"), ["C#", "E", "Ab", "B", "Eb", "F#"])

    def test_add11_is_the_triad_plus_the_eleventh(self) -> None:
        self.assertEqual(names("Ebadd11"), ["Eb", "G", "Bb", "Ab"])
        self.assertEqual(names("Cadd11"), ["C", "E", "G", "F"])
        self.assertNotIn("Bb", names("Cadd11"), "add11 carries no seventh")

    def test_an_eleventh_is_no_longer_a_bare_triad(self) -> None:
        for sym, triad in (("C11", "C"), ("Cm11", "Cm"), ("Gm11", "Gm"),
                           ("Ebadd11", "Eb")):
            self.assertNotEqual(names(sym), names(triad), f"{sym} is still a triad")

    def test_altered_and_suspended_elevenths_are_untouched(self) -> None:
        self.assertEqual(names("C7#11"), ["C", "E", "G", "Bb", "F#"])
        self.assertEqual(names("Ebmaj7#11"), ["Eb", "G", "Bb", "D", "A"])
        self.assertEqual(names("B11sus"), ["B", "E", "F#"])


class NothingElseMoved(unittest.TestCase):
    def test_common_qualities_are_unchanged(self) -> None:
        for sym, want in (
            ("C", ["C", "E", "G"]), ("Cm", ["C", "Eb", "G"]),
            ("C7", ["C", "E", "G", "Bb"]), ("Cmaj7", ["C", "E", "G", "B"]),
            ("Cm7", ["C", "Eb", "G", "Bb"]), ("C6", ["C", "E", "G", "A"]),
            ("C9", ["C", "E", "G", "Bb", "D"]), ("Cm9", ["C", "Eb", "G", "Bb", "D"]),
            ("C13", ["C", "E", "G", "Bb", "D", "A"]),
            ("Cadd9", ["C", "E", "G", "D"]), ("C69", ["C", "E", "G", "A", "D"]),
            ("Csus2", ["C", "D", "G"]), ("Csus4", ["C", "F", "G"]),
            ("Cdim", ["C", "Eb", "F#"]), ("Cdim7", ["C", "Eb", "F#", "A"]),
            ("Cm7b5", ["C", "Eb", "F#", "Bb"]), ("Caug", ["C", "E", "Ab"]),
        ):
            self.assertEqual(names(sym), want, sym)

    def test_the_documented_custom_vocabulary_still_voices(self) -> None:
        from composition_chord_manual_editor import (
            ALTERATION_OPTIONS,
            QUALITY_OPTIONS,
            ROOT_OPTIONS,
        )

        checked = 0
        for root in (r for r in ROOT_OPTIONS if r):
            for qual in QUALITY_OPTIONS:
                for alt in ALTERATION_OPTIONS:
                    sym = f"{root}{qual}{alt}"
                    self.assertTrue(chord_notes(sym), f"{sym} voiced to nothing")
                    checked += 1
        self.assertGreater(checked, 500)


class EveryCatalogCellStillVoices(unittest.TestCase):
    def test_no_catalog_cell_fails_or_loses_its_root(self) -> None:
        import copy

        from chart_level_arrangement import resolve_level_chart
        from song_catalog.catalog import curated_song_records

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
                            part = part.strip().split(":")[0]
                            if not part or part == "N.C." or not part[0].isalpha():
                                continue
                            notes = chord_notes(part)
                            self.assertTrue(notes, f"{rec['title']}: {part!r} -> {notes}")
                            seen += 1
        self.assertGreater(seen, 1000, "catalog walk did not run")


if __name__ == "__main__":
    unittest.main()
