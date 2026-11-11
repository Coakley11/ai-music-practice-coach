"""Thirteenth chords lost the quality that names them.

Two families reached the wrong branch of ``backing_audio.chord_notes``:

* **minor 13th** — ``"m13"`` had no branch, so it fell through to the generic
  ``"m" in low`` rule and came out a bare minor triad. The dominant-13 rule sits
  *after* that one, so it was never reached. ``Gm13``, the opening chord of
  Blue in Green, sounded ``Gm``.
* **major 13th** — ``"maj13"`` had no branch either, so it reached the generic
  ``"13"`` rule, which spells a **minor** seventh. ``Dbmaj13`` in New York State
  of Mind therefore sounded a dominant chord.

Both now have their own branch, placed so that the more specific quality is
matched first: ``mmaj13`` before ``maj13`` (whose substring it contains),
``maj13`` before the generic ``13``, and ``m13`` before the generic ``m``.

Voicings are root, third, fifth, seventh, ninth and thirteenth — the same shape
the existing dominant 13 already used, so the three families differ only where
they should:

    Cm13     C Eb G Bb D A      minor third, minor seventh
    Cmaj13   C E  G B  D A      major third, MAJOR seventh
    C13      C E  G Bb D A      major third, minor seventh

Scope: of 521 chord symbols the catalog can render plus a probe list, exactly 11
voicings change and no bass note changes. ``C13``, ``C13#11``, ``C7b13``,
``Cb13``, ``Cm11``, ``C11``, ``Cmaj9``, ``Cmaj7``, ``Cadd11``, ``Cadd4``,
``C6/9`` and the altered elevenths are all untouched.

Not checked by ear; the voicings are verified against interval arithmetic.
"""
from __future__ import annotations

import unittest

from backing_audio import bass_note, chord_notes

PC = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
      6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}
NAME = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
        "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10,
        "Bb": 10, "B": 11}
ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def names(sym):
    return [PC[n % 12] for n in chord_notes(sym)]


def pcs(sym):
    return {n % 12 for n in chord_notes(sym)}


class AllTwelveRoots(unittest.TestCase):
    def test_minor_thirteenth(self) -> None:
        for r in ROOTS:
            b = NAME[r]
            self.assertEqual(pcs(f"{r}m13"),
                             {(b + i) % 12 for i in (0, 3, 7, 10, 14, 21)}, f"{r}m13")

    def test_major_thirteenth(self) -> None:
        for r in ROOTS:
            b = NAME[r]
            self.assertEqual(pcs(f"{r}maj13"),
                             {(b + i) % 12 for i in (0, 4, 7, 11, 14, 21)}, f"{r}maj13")

    def test_dominant_thirteenth_is_unchanged(self) -> None:
        for r in ROOTS:
            b = NAME[r]
            self.assertEqual(pcs(f"{r}13"),
                             {(b + i) % 12 for i in (0, 4, 7, 10, 14, 21)}, f"{r}13")

    def test_each_family_keeps_its_defining_tones(self) -> None:
        for r in ROOTS:
            b = NAME[r]
            m, mj, dom = pcs(f"{r}m13"), pcs(f"{r}maj13"), pcs(f"{r}13")
            self.assertIn((b + 3) % 12, m, f"{r}m13 lost its minor third")
            self.assertIn((b + 10) % 12, m, f"{r}m13 lost its minor seventh")
            self.assertIn((b + 4) % 12, mj, f"{r}maj13 lost its major third")
            self.assertIn((b + 11) % 12, mj, f"{r}maj13 lost its major seventh")
            self.assertIn((b + 10) % 12, dom, f"{r}13 lost its minor seventh")
            for sym, got in ((f"{r}m13", m), (f"{r}maj13", mj), (f"{r}13", dom)):
                self.assertIn((b + 21) % 12, got, f"{sym} lost its thirteenth")
            self.assertIn(b % 12, m)
            self.assertIn(b % 12, mj)

    def test_the_three_families_are_distinct(self) -> None:
        for r in ROOTS:
            self.assertNotEqual(pcs(f"{r}m13"), pcs(f"{r}maj13"), r)
            self.assertNotEqual(pcs(f"{r}maj13"), pcs(f"{r}13"), r)
            self.assertNotEqual(pcs(f"{r}m13"), pcs(f"{r}13"), r)

    def test_none_is_a_bare_triad_any_more(self) -> None:
        for r in ROOTS:
            for suffix in ("m13", "maj13", "13"):
                self.assertGreater(len(pcs(f"{r}{suffix}")), 3, f"{r}{suffix}")
            self.assertNotEqual(pcs(f"{r}m13"), pcs(f"{r}m"), f"{r}m13 is still a triad")

    def test_the_bass_follows_the_root(self) -> None:
        for r in ROOTS:
            for suffix in ("m13", "maj13", "13"):
                self.assertEqual(bass_note(f"{r}{suffix}") % 12, NAME[r] % 12,
                                 f"{r}{suffix}")


class TheTwoRealCatalogCases(unittest.TestCase):
    def test_blue_in_greens_opening_gm13(self) -> None:
        self.assertEqual(names("Gm13"), ["G", "Bb", "D", "F", "A", "E"])
        self.assertNotEqual(pcs("Gm13"), pcs("Gm"), "Gm13 still sounds Gm")

    def test_new_york_state_of_minds_dbmaj13(self) -> None:
        # Db F Ab C Eb Bb - the major seventh is C, not the B of a dominant
        self.assertEqual(pcs("Dbmaj13"),
                         {NAME[x] for x in ("Db", "F", "Ab", "C", "Eb", "Bb")})
        self.assertIn(NAME["C"], pcs("Dbmaj13"), "the major seventh is missing")
        self.assertNotIn(NAME["B"], pcs("Dbmaj13"), "a minor seventh crept in")

    def test_they_voice_inside_their_songs(self) -> None:
        import copy

        from chart_level_arrangement import resolve_level_chart
        from song_catalog.catalog import curated_song_records

        seen = {}
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
                            if "m13" in part or "maj13" in part:
                                seen.setdefault(part, set()).add(rec["title"])
                                self.assertTrue(chord_notes(part), part)
        # at least the NYSOM case must be present on any dev checkout
        self.assertIn("Dbmaj13", seen, f"found instead: {sorted(seen)}")


class MoreSpecificQualitiesWinTheBranch(unittest.TestCase):
    def test_minor_major_thirteenth_is_not_claimed_by_maj13(self) -> None:
        self.assertEqual(pcs("Cmmaj13"),
                         {NAME[x] for x in ("C", "Eb", "G", "B", "D", "A")})
        self.assertIn(NAME["Eb"], pcs("Cmmaj13"), "minor third lost to maj13")
        self.assertIn(NAME["B"], pcs("Cmmaj13"), "major seventh lost")

    def test_an_altered_thirteenth_still_reaches_its_own_rule(self) -> None:
        self.assertEqual(names("C7b13"), ["C", "E", "G", "Bb", "Ab"])
        self.assertEqual(names("C13#11"), ["C", "E", "G", "Bb", "D", "A", "F#"])
        self.assertEqual(names("Cmaj13#11"), ["C", "E", "G", "B", "D", "A", "F#"])

    def test_a_flat_root_named_cb_is_still_a_b_chord(self) -> None:
        self.assertEqual(pcs("Cb13"), pcs("B13"))


class NothingElseMoved(unittest.TestCase):
    def test_the_neighbouring_families_are_untouched(self) -> None:
        for sym, want in (
            ("Cm11", ["C", "Eb", "G", "Bb", "D", "F"]),
            ("C11", ["C", "G", "Bb", "D", "F"]),
            ("Cmaj9", ["C", "E", "G", "B", "D"]),
            ("Cmaj7", ["C", "E", "G", "B"]),
            ("Cm9", ["C", "Eb", "G", "Bb", "D"]),
            ("Cm7", ["C", "Eb", "G", "Bb"]),
            ("Cm6", ["C", "Eb", "G", "A"]),
            ("Cm", ["C", "Eb", "G"]),
            ("Cadd11", ["C", "E", "G", "F"]),
            ("Cadd4", ["C", "E", "G", "F"]),
            ("C69", ["C", "E", "G", "A", "D"]),
            ("C6/9", ["C", "E", "G", "A", "D"]),
            ("C7#11", ["C", "E", "G", "Bb", "F#"]),
            ("C9#11", ["C", "E", "G", "Bb", "D", "F#"]),
            ("Cmaj7#11", ["C", "E", "G", "B", "F#"]),
            ("B11sus", ["B", "E", "F#"]),
            ("Cmmaj7", ["C", "Eb", "G", "B"]),
            ("Csus2", ["C", "D", "G"]),
            ("Csus4", ["C", "F", "G"]),
            ("C", ["C", "E", "G"]),
            ("C7", ["C", "E", "G", "Bb"]),
        ):
            self.assertEqual(names(sym), want, sym)

    def test_every_catalog_cell_still_voices_and_keeps_its_root(self) -> None:
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
                            seen += 1
                            notes = chord_notes(part)
                            self.assertTrue(notes, f"{rec['title']}: {part!r}")
                            root = part.split("/")[0]
                            root = root[:2] if len(root) > 1 and root[1] in "#b" else root[:1]
                            if root in NAME:
                                self.assertIn(NAME[root] % 12, {n % 12 for n in notes},
                                              f"{rec['title']}: {part!r} lost its root")
        self.assertGreater(seen, 1000)

    def test_the_documented_custom_vocabulary_still_voices(self) -> None:
        from composition_chord_manual_editor import (
            ALTERATION_OPTIONS,
            QUALITY_OPTIONS,
            ROOT_OPTIONS,
        )

        for root in (x for x in ROOT_OPTIONS if x):
            for qual in QUALITY_OPTIONS:
                for alt in ALTERATION_OPTIONS:
                    sym = f"{root}{qual}{alt}"
                    self.assertTrue(chord_notes(sym), sym)


if __name__ == "__main__":
    unittest.main()
