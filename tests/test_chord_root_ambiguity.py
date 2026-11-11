"""Two separate causes of a lost chord root in Custom / Composition charts.

**1. Enharmonic roots did not resolve.**

``E#``, ``B#``, ``Fb`` and ``Cb`` are legitimate spellings - E# is the leading
note of F# minor, Cb the fourth of Gb - but none of them is a key in
``backing_audio.NOTE_TO_MIDI``, and ``music_theory.normalize_root`` passed them
through unchanged. Every pitch lookup therefore fell back to its default, so
``E#11`` sounded a **C** chord and ``Cbmaj7`` sounded a C major seventh.
``normalize_root`` now folds each to the note it sounds, so ``E#11`` is an F
eleventh, which is what the symbol literally says.

**2. The editor built symbols whose root was ambiguous.**

``build_chord_symbol`` concatenated root + quality + alteration, so root ``C``
with alteration ``#5`` became ``C#5`` - indistinguishable from the root C# with
a stray 5, and that is how the parser read it. 36 of the documented
root x quality x alteration combinations lost their root this way.

The fix is a representation change, not a reinterpretation. When the quality is
empty and the alteration begins with an accidental, a one-letter root gets a
spelling that cannot absorb it:

* ``#5`` becomes ``C+``. A raised fifth over a plain triad is an augmented
  chord and ``+`` is its conventional symbol, so this - the likeliest
  alteration on a bare triad - needs no invented spelling at all. It parses
  unambiguously because ``+`` is not a note letter.
* the other five alterations have no short conventional symbol over a plain
  triad, so the major quality is named explicitly: ``Cmajb9``. Verbose, but it
  reads correctly, where ``Cb9`` would read as C-flat.

``parse_chord_parts`` maps both back to an empty quality plus the alteration, so
the editor's dropdowns round-trip. The ``maj`` strip has to happen before the
quality scan, or the one-character ``m`` option claims its first letter and
leaves ``aj#5`` behind.

``C(#5)`` was considered and rejected: ``_chord_head`` strips parentheses before
the root is read, so it parses as the root C# with a stray 5 - exactly the bug
being fixed.

**Known residual.** 35 symbols - the five unusual alterations over a bare triad,
at all seven one-letter roots - still render as ``Xmaj<alt>`` in the lead sheet
and the chart grid, because those surfaces print the stored token and there is
no single label chokepoint to normalise. It is verbose rather than wrong, and a
strict improvement on today, where the same selections produce an audibly wrong
chord. Narrowing it further would mean a display-layer mapping across several
label surfaces, which is deliberately not attempted here.

**Deliberate non-goals.** A hand-written ``C#5`` keeps its current reading as a
C# chord - it is genuinely ambiguous and only its author knows which was meant.
No saved chart is rewritten: this changes what new edits *produce*, never what
stored symbols *mean*. And no rule assumes a two-character prefix is a root;
the ambiguity is removed at the point the symbol is built.

No catalog chart is affected. The eight symbols of this shape that catalog songs
do use - Bb9, Eb9, Eb13, Ab13, Bb13, Gb13, F#9, C#9 - are ordinary chords whose
roots were always parsed correctly, and no catalog chart uses an enharmonic root.
"""
from __future__ import annotations

import unittest

from backing_audio import NOTE_TO_MIDI, chord_notes, split_chord
from composition_chord_manual_editor import (
    ALTERATION_OPTIONS,
    QUALITY_OPTIONS,
    ROOT_OPTIONS,
    build_chord_symbol,
    parse_chord_parts,
)
from music_theory import normalize_root

PC = {0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
      6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"}
NAME_TO_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
              "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10,
              "Bb": 10, "B": 11}


def names(sym):
    return [PC[n % 12] for n in chord_notes(sym)]


class EnharmonicRootsResolve(unittest.TestCase):
    def test_each_folds_to_the_note_it_sounds(self) -> None:
        for spelled, sounding in (("E#", "F"), ("B#", "C"), ("Fb", "E"), ("Cb", "B")):
            self.assertEqual(normalize_root(spelled), sounding, spelled)
            self.assertIn(normalize_root(spelled), NOTE_TO_MIDI, spelled)

    def test_a_chord_on_an_enharmonic_root_sounds_that_root(self) -> None:
        for spelled, sounding in (("E#", "F"), ("B#", "C"), ("Fb", "E"), ("Cb", "B")):
            for quality in ("", "m", "7", "maj7", "m7"):
                sym = f"{spelled}{quality}"
                self.assertEqual(
                    names(sym), names(f"{sounding}{quality}"),
                    f"{sym} does not sound like {sounding}{quality}",
                )

    def test_the_old_fallback_to_c_is_gone(self) -> None:
        # E#11 used to voice a C chord; it is an F eleventh
        self.assertEqual(names("E#11"), names("F11"))
        self.assertNotEqual(names("E#11"), names("C11"))
        self.assertEqual(names("Cbmaj7"), names("Bmaj7"))
        self.assertNotEqual(names("Cbmaj7"), names("Cmaj7"))

    def test_ordinary_spellings_are_untouched(self) -> None:
        for r in ("C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb",
                  "G", "G#", "Ab", "A", "A#", "Bb", "B"):
            self.assertIn(normalize_root(r), NOTE_TO_MIDI, r)
            self.assertEqual(
                {n % 12 for n in chord_notes(r)},
                {(NAME_TO_PC[r] + i) % 12 for i in (0, 4, 7)}, r,
            )


class EditorSymbolsAreUnambiguous(unittest.TestCase):
    def test_every_documented_combination_keeps_its_root(self) -> None:
        bad = []
        for root in (x for x in ROOT_OPTIONS if x):
            for qual in QUALITY_OPTIONS:
                for alt in ALTERATION_OPTIONS:
                    sym = build_chord_symbol(root=root, quality=qual, alteration=alt)
                    parsed = parse_chord_parts(sym)
                    if parsed["root"] != normalize_root(root):
                        bad.append((root, qual, alt, sym, parsed["root"]))
        self.assertEqual(bad, [], f"{len(bad)} symbols lose their root, e.g. {bad[:5]}")

    def test_a_one_letter_root_with_an_accidental_gets_an_explicit_maj(self) -> None:
        for root, alt, want in (("C", "b9", "Cmajb9"),
                                ("D", "b5", "Dmajb5"), ("E", "#11", "Emaj#11"),
                                ("A", "b13", "Amajb13"),
                                ("B", "b9", "Bmajb9"), ("F", "#9", "Fmaj#9")):
            self.assertEqual(build_chord_symbol(root=root, alteration=alt), want)

    def test_those_symbols_voice_the_chord_they_name(self) -> None:
        for sym, want in (("C+", ["C", "E", "Ab"]),
                          ("Cmajb5", ["C", "E", "F#"]),
                          ("Cmaj#9", ["C", "E", "G", "Eb"]),
                          ("Cmajb9", ["C", "E", "G", "C#"]),
                          ("Cmaj#11", ["C", "E", "G", "F#"]),
                          ("Cmajb13", ["C", "E", "G", "Ab"]),
                          ("Emaj#11", ["E", "Ab", "B", "Bb"])):
            self.assertEqual(names(sym), want, sym)

    def test_a_two_character_root_needs_no_help(self) -> None:
        for root, alt in (("C#", "b9"), ("Eb", "#9"), ("Bb", "b5"), ("F#", "#11")):
            sym = build_chord_symbol(root=root, alteration=alt)
            self.assertNotIn("maj", sym, sym)
            self.assertEqual(parse_chord_parts(sym)["root"], normalize_root(root))

    def test_a_named_quality_needs_no_help(self) -> None:
        for root, qual, alt in (("C", "m7", "b5"), ("C", "9", "#11"),
                                ("C", "maj7", "#11"), ("C", "7", "b9")):
            sym = build_chord_symbol(root=root, quality=qual, alteration=alt)
            self.assertNotIn("maj#", sym)
            self.assertEqual(parse_chord_parts(sym)["root"], "C")

    def test_the_round_trip_preserves_the_alteration(self) -> None:
        for root in (x for x in ROOT_OPTIONS if x):
            for alt in (a for a in ALTERATION_OPTIONS if a):
                sym = build_chord_symbol(root=root, alteration=alt)
                self.assertEqual(parse_chord_parts(sym)["alteration"], alt,
                                 f"{root}+{alt} -> {sym}")

    def test_maj7_and_maj9_qualities_survive_the_maj_strip(self) -> None:
        for sym, qual in (("Cmaj7", "maj7"), ("Cmaj9", "maj9")):
            self.assertEqual(parse_chord_parts(sym)["quality"], qual, sym)
        self.assertEqual(names("Cmaj7"), ["C", "E", "G", "B"])
        self.assertEqual(names("Cmaj9"), ["C", "E", "G", "B", "D"])

    def test_a_slash_bass_still_round_trips(self) -> None:
        sym = build_chord_symbol(root="C", alteration="b9", bass="G")
        self.assertEqual(sym, "Cmajb9/G")
        parsed = parse_chord_parts(sym)
        self.assertEqual((parsed["root"], parsed["alteration"], parsed["bass"]),
                         ("C", "b9", "G"))


class NonGoalsHold(unittest.TestCase):
    """What this change must NOT do."""

    def test_a_hand_written_c_sharp_5_is_not_reinterpreted(self) -> None:
        self.assertEqual(split_chord("C#5")[0], "C#")
        self.assertEqual(names("C#5"), names("C#"))

    def test_the_catalog_symbols_of_this_shape_are_unchanged(self) -> None:
        for sym, root in (("Bb9", "Bb"), ("Eb9", "Eb"), ("Eb13", "Eb"),
                          ("Ab13", "Ab"), ("Bb13", "Bb"), ("Gb13", "Gb"),
                          ("F#9", "F#"), ("C#9", "C#")):
            self.assertIn(NAME_TO_PC[root] % 12, {n % 12 for n in chord_notes(sym)}, sym)

    def test_no_catalog_chart_is_affected(self) -> None:
        import copy

        from chart_level_arrangement import resolve_level_chart
        from song_catalog.catalog import curated_song_records

        enh = {"E#", "B#", "Fb", "Cb"}
        hits, seen = [], 0
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
                            if not part or not part[:1].isalpha():
                                continue
                            seen += 1
                            if part[:2] in enh:
                                hits.append((rec["title"], part))
        self.assertEqual(hits, [], f"catalog uses an enharmonic root: {hits[:5]}")
        self.assertGreater(seen, 1000)


class AugmentedUsesTheConventionalSymbol(unittest.TestCase):
    """A raised fifth over a plain triad needs no invented spelling."""

    ROOTS = ["C", "D", "E", "F", "G", "A", "B"]

    def test_a_sharp_five_builds_as_plus(self) -> None:
        for r in self.ROOTS:
            self.assertEqual(build_chord_symbol(root=r, alteration="#5"), f"{r}+")

    def test_plus_sounds_the_augmented_triad(self) -> None:
        for r in self.ROOTS:
            base = NAME_TO_PC[r]
            self.assertEqual({n % 12 for n in chord_notes(f"{r}+")},
                             {(base + i) % 12 for i in (0, 4, 8)}, f"{r}+")

    def test_plus_round_trips_into_the_dropdowns(self) -> None:
        for r in self.ROOTS:
            parsed = parse_chord_parts(f"{r}+")
            self.assertEqual(parsed["root"], normalize_root(r))
            self.assertEqual(parsed["quality"], "")
            self.assertEqual(parsed["alteration"], "#5")

    def test_plus_takes_a_slash_bass(self) -> None:
        sym = build_chord_symbol(root="C", alteration="#5", bass="G")
        self.assertEqual(sym, "C+/G")
        parsed = parse_chord_parts(sym)
        self.assertEqual((parsed["root"], parsed["alteration"], parsed["bass"]),
                         ("C", "#5", "G"))

    def test_plus_is_never_an_invented_spelling_on_screen(self) -> None:
        from songs.sheet_format import chord_display_cell

        for r in self.ROOTS:
            shown = chord_display_cell(f"{r}+", None)
            self.assertEqual(shown, f"{r}+")
            self.assertNotIn("maj", shown)


class TheParenthesisedFormWasRejected(unittest.TestCase):
    """Why C(#5) is not the stored spelling, so nobody retries it."""

    def test_parentheses_are_stripped_before_the_root_is_read(self) -> None:
        from backing_audio import _chord_head, split_chord

        # split_chord alone reads the root correctly, because "(" is not an
        # accidental - but chord_notes runs _chord_head first, and that strips
        # the parentheses, which puts the accidental back against the root.
        self.assertEqual(split_chord("C(#5)")[0], "C")
        self.assertEqual(_chord_head("C(#5)"), "C#5")
        self.assertEqual(split_chord(_chord_head("C(#5)"))[0], "C#")
        self.assertNotEqual({n % 12 for n in chord_notes("C(#5)")},
                            {n % 12 for n in chord_notes("C+")})


class ResidualDisplayLeakIsBounded(unittest.TestCase):
    """The maj spelling that does still reach the screen, counted and pinned."""

    def test_only_the_five_unusual_alterations_show_maj(self) -> None:
        leaked = set()
        for root in (x for x in ROOT_OPTIONS if x):
            for alt in (a for a in ALTERATION_OPTIONS if a):
                sym = build_chord_symbol(root=root, alteration=alt)
                if "maj" in sym:
                    leaked.add(sym)
        self.assertEqual(len(leaked), 35, sorted(leaked)[:8])
        for sym in leaked:
            self.assertNotIn("#5", sym, f"{sym}: #5 should use + instead")
            # and each still voices the chord it names, which is the point
            self.assertTrue(chord_notes(sym))

    def test_the_leaked_form_still_renders_and_parses(self) -> None:
        from songs.sheet_format import chord_display_cell

        for sym in ("Cmajb9", "Cmaj#9", "Cmaj#11", "Cmajb13", "Cmajb5"):
            self.assertEqual(chord_display_cell(sym, None), sym)
            self.assertEqual(parse_chord_parts(sym)["root"], "C")


if __name__ == "__main__":
    unittest.main()
