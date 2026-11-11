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

**3. add4 / add11 are added notes, not replacements.**

``add4`` had no branch at all, so Why Georgia's ``Dadd4`` sounded a plain D
triad. ``add11`` had one, but it rebuilt the whole chord as ``[0,4,7,17]``,
which hardcoded a MAJOR third (so ``Cmadd11`` came out major) and would have
dropped the seventh from ``Cm7add4``. Both now append the fourth/eleventh to
whatever quality the rest of the symbol gives.

That keeps the third, which is the whole difference between an added fourth and
a suspended one: ``Dadd4`` is D-F#-A-G, while ``Dsus4`` replaces the F# with the
G. Worth stating, because Why Georgia's printed fingering for ``Dadd4`` is
``xx0233``, which sounds D-A-D-G with **no F#** - a Dsus4 voicing, not a
complete Dadd4. The chart symbol and the fingering therefore still disagree.
Neither is changed here; it is recorded as a separate audit item.

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


class AddedFourthKeepsTheThird(unittest.TestCase):
    """add4 / add11 add a note; sus4 replaces one. Checked at all twelve roots."""

    ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    PCS = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5,
           "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}

    def pcs(self, sym):
        return {n % 12 for n in chord_notes(sym)}

    def test_major_add4_is_triad_plus_fourth_every_root(self) -> None:
        for r in self.ROOTS:
            b = self.PCS[r]
            self.assertEqual(self.pcs(f"{r}add4"),
                             {(b + i) % 12 for i in (0, 4, 7, 5)}, f"{r}add4")
            self.assertIn((b + 4) % 12, self.pcs(f"{r}add4"), f"{r}add4 lost its third")
            self.assertIn((b + 5) % 12, self.pcs(f"{r}add4"), f"{r}add4 lost its fourth")

    def test_minor_add4_keeps_the_minor_third_every_root(self) -> None:
        for r in self.ROOTS:
            b = self.PCS[r]
            self.assertEqual(self.pcs(f"{r}madd4"),
                             {(b + i) % 12 for i in (0, 3, 7, 5)}, f"{r}madd4")
            self.assertNotIn((b + 4) % 12, self.pcs(f"{r}madd4"),
                             f"{r}madd4 has a major third")

    def test_add11_names_the_same_added_note_as_add4(self) -> None:
        for r in self.ROOTS:
            self.assertEqual(self.pcs(f"{r}add11"), self.pcs(f"{r}add4"), r)
            self.assertEqual(self.pcs(f"{r}madd11"), self.pcs(f"{r}madd4"), r)

    def test_add4_differs_from_sus4_by_exactly_the_third(self) -> None:
        for r in self.ROOTS:
            self.assertNotEqual(self.pcs(f"{r}add4"), self.pcs(f"{r}sus4"),
                                f"{r}add4 == {r}sus4")
            self.assertEqual(self.pcs(f"{r}add4") - self.pcs(f"{r}sus4"),
                             {(self.PCS[r] + 4) % 12}, r)

    def test_an_added_fourth_composes_with_a_seventh(self) -> None:
        self.assertEqual(names("Cm7add4"), ["C", "Eb", "G", "Bb", "F"])
        self.assertEqual(names("Cmaj7add4"), ["C", "E", "G", "B", "F"])
        self.assertEqual(names("C7add4"), ["C", "E", "G", "Bb", "F"])

    def test_dadd4_specifically(self) -> None:
        self.assertEqual(names("Dadd4"), ["D", "F#", "A", "G"])
        self.assertEqual(names("Dsus4"), ["D", "G", "A"])
        self.assertIn("F#", names("Dadd4"))
        self.assertNotIn("F#", names("Dsus4"))

    def test_why_georgias_dadd4_fingering_is_a_sus4_voicing(self) -> None:
        """A documented discrepancy, deliberately NOT reconciled here.

        The chart cell says Dadd4, which keeps the F#. The printed fingering
        xx0233 sounds D-A-D-G, with no F#, so it is a Dsus4 voicing. Neither the
        symbol nor the fingering is changed; this pins the gap so it stays visible.
        """
        import copy

        from song_catalog.catalog import curated_song_records

        rec = copy.deepcopy(
            next(x for x in curated_song_records() if x["title"] == "Why Georgia")
        )
        tabs = rec.get("guitar_tabs") or {}
        self.assertEqual(tabs.get("Dadd4"), "xx0233")
        open_pc = {"E": 4, "A": 9, "D": 2, "G": 7, "B": 11, "e": 4}
        sounded = {PC[(open_pc[st] + int(c)) % 12]
                   for st, c in zip(["E", "A", "D", "G", "B", "e"], "xx0233") if c != "x"}
        self.assertEqual(sorted(sounded), ["A", "D", "G"])
        self.assertNotIn("F#", sounded, "the fingering omits the third the symbol keeps")
        self.assertIn("F#", names("Dadd4"), "the symbol keeps its third")


class RootLossIsPreExistingAndDocumented(unittest.TestCase):
    """E#11 sounds different under this branch, and both renderings are wrong.

    split_chord("E#11") yields the root "E#", which is absent from NOTE_TO_MIDI
    and which normalize_root does not fold to F, so the root falls back to C.
    Before this change E#11 voiced C-E-G; now it voices C-G-Bb-D-F. Neither is an
    E or an F chord, so this is a behaviour change without being a regression:
    the old pitch set merely happened to contain an E, which masked the fault.

    The same fallback affects B#, Fb and Cb. No catalog chart uses any of them -
    they are reachable only by the Composition editor concatenating a root with
    an alteration. Tracked separately; not fixed here.
    """

    def test_unresolvable_roots_still_fall_back(self) -> None:
        from backing_audio import NOTE_TO_MIDI, normalize_root, split_chord

        for sym in ("E#11", "B#11", "Fb9", "Cb9"):
            root = split_chord(sym)[0]
            self.assertNotIn(root, NOTE_TO_MIDI, f"{root} unexpectedly resolvable")
            self.assertNotIn(normalize_root(root), NOTE_TO_MIDI,
                             f"{root} is folded now - update this test and the note")

    def test_e_sharp_eleven_is_voiced_as_a_c_chord(self) -> None:
        self.assertEqual(names("E#11"), names("C11"))
        self.assertNotIn("E", names("E#11"), "not an E chord")
        self.assertEqual(names("E#11")[0], "C", "the root fell back to C")

    def test_no_catalog_chart_uses_an_unresolvable_root(self) -> None:
        import copy

        from chart_level_arrangement import resolve_level_chart
        from song_catalog.catalog import curated_song_records

        bad = {"E#", "B#", "Fb", "Cb"}
        hits = []
        for rec in curated_song_records():
            for lv in ("Beginner", "Intermediate", "Advanced"):
                try:
                    _v, secs = resolve_level_chart(copy.deepcopy(rec), lv)
                except Exception:
                    continue
                for chords in (secs or {}).values():
                    for tok in chords:
                        for part in str(tok).split("|"):
                            part = part.strip().split(":")[0]
                            if part[:2] in bad:
                                hits.append((rec["title"], part))
        self.assertEqual(hits, [], f"catalog now uses an unresolvable root: {hits[:5]}")


if __name__ == "__main__":
    unittest.main()
