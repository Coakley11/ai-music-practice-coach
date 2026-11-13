"""Cluster B / P5: context-aware Roman numerals, generated explanations, distinct suggestions."""

from __future__ import annotations

import re
import unittest

from composition_chord_suggestions import suggest_progressions
from composition_document import (
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
)
from composition_harmony_explain import (
    explain_progression,
    harmonic_identity,
    infer_key,
)
from composition_song_intent import describe_harmony_from_events
from roman_numeral_analysis import analyze_progression, analyze_progression_detailed

FLAT = "♭"
DIM = "°"
HALF = "ø"

# (key, chords, exact expected Roman labels)
EXPECTED_LABELS = [
    # The three jazz cards from the product-owner report (C major).
    ("C", "Cmaj7 Em7 D7 G7", "Imaj7 iii7 V7/V V7"),
    ("C", "Cmaj7 Fmaj7 D7 G7", "Imaj7 IVmaj7 V7/V V7"),
    ("C", "Cmaj7 A7 D7 G7", "Imaj7 V7/ii V7/V V7"),
    # Diatonic jazz / bossa
    ("C", "Dm7 G7 Cmaj7 A7", "ii7 V7 Imaj7 V7/ii"),
    ("C", "Cmaj7 Fmaj7 Dm7 G7", "Imaj7 IVmaj7 ii7 V7"),
    ("C", "Cmaj7 Am7 Dm7 G7", "Imaj7 vi7 ii7 V7"),
    ("C", "C6 Am7 Dm7 G9", "I6 vi7 ii7 V9"),
    # Secondary dominants and chains
    ("C", "Em7 A7 Dm7 G7", "iii7 V7/ii ii7 V7"),
    ("C", "Cmaj7 B7 Em7 A7", "Imaj7 V7/iii iii7 V7/ii"),
    ("C", "C D7 G7 C", "I V7/V V7 I"),
    ("C", "C E Am F", f"I V/vi vi IV"),
    ("C", "Bm7b5 E7 Am7", f"vii{HALF}7 V7/vi vi7"),
    ("G", "Gmaj7 E7 Am7 D7", "Imaj7 V7/ii ii7 V7"),
    ("Bb", "Bbmaj7 G7 Cm7 F7", "Imaj7 V7/ii ii7 V7"),
    # Tritone substitutions
    ("C", "Dm7 Db7 Cmaj7", f"ii7 {FLAT}II7 Imaj7"),
    ("C", "Cmaj7 Eb7 Dm7 G7", "Imaj7 subV7/ii ii7 V7"),
    # Passing / leading-tone diminished, slash chords
    ("C", "Fmaj7 F#dim7 Cmaj7/G G7", f"IVmaj7 vii{DIM}7/V Imaj7/V V7"),
    ("C", "Bdim7 Cmaj7", f"vii{DIM}7 Imaj7"),
    ("C", "C C/E F G", "I I/III IV V"),
    # Pop / rock / blues
    ("C", "C G Am F", "I V vi IV"),
    ("C", "C Em Am F", "I iii vi IV"),
    ("C", "C Bb F C", f"I {FLAT}VII IV I"),
    ("C", "C Fm C", "I iv I"),
    ("C", "C7 F7 C7 G7", "I7 IV7 I7 V7"),
    ("C", "C Gsus4 G7 C", "I Vsus4 V7 I"),
    ("C", "Cmaj7 C7 Fmaj7 Fm7", "Imaj7 I7 IVmaj7 iv7"),
    # Minor keys
    ("Am", "Am Dm E Am", "i iv V i"),
    ("Am", "Am G F E", "i VII VI V"),
    ("Am", "Am Dm7 G7 Cmaj7", "i iv7 V7/III IIImaj7"),
    ("Am", "Bm7b5 E7 Am", f"ii{HALF}7 V7 i"),
    ("Am", "Am D G C", "i V/VII VII III"),
    ("Cm", "Cm Fm G7 Cm", "i iv V7 i"),
    ("Cm", "Cm Ab Bb Cm", "i VI VII i"),
    ("Em", "Em Am B7 Em", "i iv V7 i"),
]


class TestContextAwareRomanLabels(unittest.TestCase):
    def test_exact_labels(self) -> None:
        for key, chords, expected in EXPECTED_LABELS:
            with self.subTest(key=key, chords=chords):
                self.assertEqual(" ".join(analyze_progression(chords.split(), key)), expected)

    def test_major_quality_dominant_on_ii_is_never_a_ii_chord(self) -> None:
        for prog in ("Cmaj7 Em7 D7 G7", "Cmaj7 Fmaj7 D7 G7", "Cmaj7 A7 D7 G7", "D7", "D7 Gmaj7"):
            chords = prog.split()
            d7 = analyze_progression(chords, "C")[chords.index("D7")]
            self.assertEqual(d7, "V7/V", (prog, d7))

    def test_context_free_single_chord_unchanged(self) -> None:
        # chord_to_roman is deliberately context-free (used by the Custom Progression Lab).
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("A7", "C"), "VI7")
        self.assertEqual(chord_to_roman("D7", "C"), "II7")

    def test_quality_spellings(self) -> None:
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("CΔ7", "C"), "Imaj7")
        self.assertEqual(chord_to_roman("Cdom7", "C"), "I7")
        self.assertEqual(chord_to_roman("Cadd9", "C"), "Iadd9")
        self.assertEqual(chord_to_roman("Cmmaj7", "C"), "i(maj7)")
        self.assertEqual(chord_to_roman("G7b9", "C"), "V7♭9")

    def test_roles_and_targets(self) -> None:
        rows = analyze_progression_detailed("Cmaj7 A7 D7 G7".split(), "C")
        self.assertEqual([r["role"] for r in rows], ["diatonic", "secondary_dominant", "secondary_dominant", "dominant"])
        self.assertEqual(rows[1]["target_index"], 2)
        self.assertEqual(rows[2]["target_index"], 3)
        rows = analyze_progression_detailed(["Dm7", "Db7", "Cmaj7"], "C")
        self.assertEqual(rows[1]["role"], "tritone_sub")

    def test_nc_and_empty_are_blank(self) -> None:
        self.assertEqual(analyze_progression(["N.C.", "C"], "C"), ["", "I"])


class TestGeneratedExplanations(unittest.TestCase):
    def test_reported_jazz_cards(self) -> None:
        a = explain_progression("Cmaj7 Em7 D7 G7".split(), "C")
        self.assertIn("iii7", a)
        self.assertIn("tonic-family", a)
        self.assertIn("D7 is V7/V", a)
        self.assertIn("secondary dominant", a)
        self.assertIn("not the diatonic ii7", a)
        self.assertNotIn("ii–V", a)  # D7-G7 is NOT a diatonic minor ii-V in C
        b = explain_progression("Cmaj7 Fmaj7 D7 G7".split(), "C")
        self.assertIn("IVmaj7", b)
        self.assertIn("subdominant", b)
        self.assertNotIn("ii–V", b)
        c = explain_progression("Cmaj7 A7 D7 G7".split(), "C")
        self.assertIn("chain of dominants", c)
        self.assertIn("V7/ii → V7/V → V7", c)
        self.assertNotIn("shaped for a", a + b + c)
        self.assertNotIn("uses dominant seventh color", a + b + c)

    def test_diatonic_ii_v_is_still_named(self) -> None:
        why = explain_progression("Dm7 G7 Cmaj7".split(), "C")
        self.assertIn("ii–V", why)
        self.assertIn("Lands home", why)

    def test_secondary_ii_v(self) -> None:
        why = explain_progression("Em7 A7 Dm7 G7".split(), "C")
        self.assertIn("Em7 → A7 is a ii–V that briefly tonicizes ii", why)

    def test_tritone_and_passing_dim(self) -> None:
        self.assertIn("tritone substitute", explain_progression("Dm7 Db7 Cmaj7".split(), "C"))
        why = explain_progression("Fmaj7 F#dim7 Cmaj7/G G7".split(), "C")
        self.assertIn("diminished passing chord", why)
        self.assertIn("vii°7/V", why)

    def test_borrowed_chords(self) -> None:
        self.assertIn("borrowed from the parallel minor", explain_progression("C Bb F C".split(), "C"))
        self.assertIn("minor iv borrowed", explain_progression("C Fm C".split(), "C"))

    def test_minor_key_dominant(self) -> None:
        why = explain_progression("Am Dm E Am".split(), "Am")
        self.assertIn("A minor", why)
        self.assertIn("Dm", why)

    def test_wraparound_resolution(self) -> None:
        why = explain_progression("Dm7 G7 Cmaj7 A7".split(), "C")
        self.assertIn("resolves back down a fifth into the opening Dm7", why)

    def test_key_inference(self) -> None:
        self.assertEqual(infer_key("Dm7 G7 Cmaj7".split()), "C")
        self.assertEqual(infer_key("Am Dm E Am".split()), "Am")

    def test_describe_hook_uses_profile_key(self) -> None:
        why = describe_harmony_from_events(
            [{"chord": "A7"}, {"chord": "D7"}, {"chord": "Gmaj7"}],
            profile={"key_center": "G", "style_family": "jazz"},
        )
        self.assertIn("G major", why)
        self.assertIn("V7/V", why)  # A7 is V7/V in G
        self.assertIn("V7", why)

    def test_every_cited_numeral_and_chord_is_in_the_progression(self) -> None:
        """The explanation can only cite chords/numerals that the analysis really produced."""
        chord_re = re.compile(r"\b([A-G][b#]?(?:maj7|m7b5|m7|dim7|dim|sus4|m|7|9|6)?(?:/[A-G][b#]?)?)\b")
        for key, chords, _ in EXPECTED_LABELS:
            syms = chords.split()
            why = explain_progression(syms, key)
            labels = set(analyze_progression(syms, key)) | {
                r["plain_roman"] for r in analyze_progression_detailed(syms, key)
            }
            body = why.split(",", 1)[1] if why.startswith("In ") else why
            for tok in re.findall(r"\(([^()\s]+)\)", why):
                self.assertIn(tok, labels | {"V", "ii"}, (chords, tok, why))
            for tok in chord_re.findall(body):
                if tok in {"A", "I", "V"}:
                    continue
                self.assertIn(tok, set(syms) | labels, (chords, tok, why))


def _doc(genre: str, key: str = "C", *, bpm: int = 100):
    doc = bootstrap_from_vision(genre=genre, song_idea="A song.", key=f"{key} major", bpm=bpm, meter="4/4")
    doc["global"]["original_key_center"] = key
    apply_structure_template(doc, "simple")
    return doc, ordered_sections(doc)


class TestSuggestionSetDistinct(unittest.TestCase):
    GENRES = ("Pop", "Jazz", "Rock", "Blues", "Bossa", "Folk")
    FEELINGS = ("stable", "tense", "uplifting", "reflective", "energetic", "melancholy")

    def test_no_identical_chord_sequences_and_ids_unique(self) -> None:
        for genre in self.GENRES:
            for key in ("C", "G", "Eb"):
                doc, secs = _doc(genre, key)
                for sec in secs[:3]:
                    for feel in self.FEELINGS:
                        ideas = suggest_progressions(doc, sec, feel, limit=3)
                        seqs = [tuple(c["chord"] for c in i["chords"]) for i in ideas]
                        with self.subTest(genre=genre, key=key, section=sec.get("label"), feeling=feel):
                            self.assertEqual(len(seqs), len(set(seqs)), seqs)
                            ids = [i["id"] for i in ideas]
                            self.assertEqual(len(ids), len(set(ids)))
                            idents = [harmonic_identity(list(s), key) for s in seqs]
                            self.assertEqual(len(idents), len(set(idents)))

    def test_candidates_differ_by_more_than_one_chord_when_possible(self) -> None:
        doc, secs = _doc("Jazz")
        ideas = suggest_progressions(doc, secs[0], "tense", limit=3)
        seqs = [[c["chord"] for c in i["chords"]] for i in ideas]
        self.assertEqual(len(seqs), 3)
        for i in range(len(seqs)):
            for j in range(i + 1, len(seqs)):
                if len(seqs[i]) == len(seqs[j]):
                    diff = sum(1 for a, b in zip(seqs[i], seqs[j]) if a != b)
                    self.assertGreaterEqual(diff, 2, (seqs[i], seqs[j]))

    def test_explanations_unique_within_set_and_match_chords(self) -> None:
        for genre in ("Jazz", "Pop", "Bossa", "Blues", "Rock"):
            doc, secs = _doc(genre)
            for feel in ("stable", "tense", "uplifting"):
                ideas = suggest_progressions(doc, secs[0], feel, limit=3)
                whys = [i["why"] for i in ideas]
                with self.subTest(genre=genre, feeling=feel):
                    self.assertEqual(len(whys), len(set(whys)))
                    for idea in ideas:
                        syms = [c["chord"] for c in idea["chords"]]
                        # The stored explanation IS the generated one for these chords + key.
                        self.assertEqual(idea["why"], explain_progression(syms, "C"))
                        self.assertIn(syms[0], idea["why"])
                        self.assertNotIn("shaped for a", idea["why"])


if __name__ == "__main__":
    unittest.main()
