"""Issue 69A/B: a chord in a cue line keeps one accidental, and moves with the key.

Reported from the phone. Practising *Say* with the Practice Key moved off the song's
original B-flat, the Karaoke Phrasing Guide showed its Intro as

    Instrumental - D#(flat) . G#(flat) . Bm . A

A root carrying a sharp *and* a flat is not a chord, and the two plain-letter chords
beside it had transposed correctly - which is the whole clue. ``_CHORD_IN_PROSE`` spelled
its accidentals ``(?:#|b)``, ASCII only, while the curated cue text is written with the
typographic signs. So the pattern matched the bare letter ``B``, moved *that* to ``D#``,
and the original flat stayed glued to the result.

Say's curated Intro is ``Instrumental - Bb . Eb . Gm . F`` - I, IV, vi, V of B-flat
major. In D major that is ``D . G . Bm . A``, and the broken output had reached the
right answer for exactly the two chords whose roots happened to need no accidental.

The tests use the typographic signs on purpose: writing them in ASCII is what hid this.
"""

from __future__ import annotations

import re
import unittest

from musician_coaching import transpose_lyric_cue, transpose_lyric_cues

FLAT = "♭"
SHARP = "♯"
DOT = "·"
DASH = "—"

#: Say's curated Intro cue, exactly as the catalog writes it.
SAY_INTRO = f"Instrumental {DASH} B{FLAT} {DOT} E{FLAT} {DOT} Gm {DOT} F"

#: Any root carrying two accidentals, in either order and either alphabet.
DOUBLE_ACCIDENTAL = re.compile(f"[A-G](?:#|b|{SHARP}|{FLAT})(?:#|b|{SHARP}|{FLAT})")


class TheReportedCase(unittest.TestCase):
    def test_say_intro_from_b_flat_to_d(self):
        got = transpose_lyric_cue(SAY_INTRO, catalog_key="Bb", practice_key="D")
        self.assertEqual(got, f"Instrumental {DASH} D {DOT} G {DOT} Bm {DOT} A")

    def test_the_typographic_and_ascii_spellings_agree(self):
        """They described the same four chords and transposed to different answers."""
        ascii_cue = f"Instrumental {DASH} Bb {DOT} Eb {DOT} Gm {DOT} F"
        self.assertEqual(
            transpose_lyric_cue(SAY_INTRO, catalog_key="Bb", practice_key="D"),
            transpose_lyric_cue(ascii_cue, catalog_key="Bb", practice_key="D"),
        )

    def test_the_flat_rooted_chords_actually_move(self):
        got = transpose_lyric_cue(SAY_INTRO, catalog_key="Bb", practice_key="D")
        self.assertNotIn(f"B{FLAT}", got)
        self.assertNotIn(f"E{FLAT}", got)


class NoChordEverCarriesTwoAccidentals(unittest.TestCase):
    """The defect's visible signature, swept across keys and chord shapes."""

    CUES = (
        SAY_INTRO,
        f"Intro {DASH} D/F{SHARP} {DOT} Csus4/D {DOT} C{SHARP}m7",
        f"Verse {DASH} Bb {DOT} Eb {DOT} F#m7b5 {DOT} A/C#",
        f"Bridge {DASH} A{FLAT}maj7 {DOT} D{FLAT} {DOT} G{FLAT} {DOT} B{FLAT}m",
        f"Turnaround {DASH} F{SHARP}m {DOT} B {DOT} E {DOT} C{SHARP}7",
    )
    PAIRS = (
        ("Bb", "D"), ("Bb", "C"), ("C", "D"), ("C", "Eb"), ("D", "F#"),
        ("Eb", "A"), ("F#", "Bb"), ("Ab", "E"), ("G", "Bb"),
    )

    def test_no_double_accidental_in_any_pairing(self):
        for catalog, practice in self.PAIRS:
            for cue in self.CUES:
                out = transpose_lyric_cue(cue, catalog_key=catalog,
                                          practice_key=practice)
                with self.subTest(catalog=catalog, practice=practice, cue=cue):
                    found = DOUBLE_ACCIDENTAL.search(out)
                    self.assertIsNone(
                        found,
                        f"{catalog}->{practice}: {cue!r} produced {out!r}",
                    )

    def test_a_cue_with_no_key_change_is_returned_unchanged(self):
        for cue in self.CUES:
            with self.subTest(cue=cue):
                self.assertEqual(
                    transpose_lyric_cue(cue, catalog_key="Bb", practice_key="Bb"), cue)


class WhatMustNotBeTouched(unittest.TestCase):
    """The pattern sits in prose, so it has to leave prose alone."""

    def test_ordinary_words_survive(self):
        for text in (
            "Breathe at the end of each phrase.",
            "Add a crescendo before the Bridge.",
            "Count the bar in and come in on beat two.",
            "Feel the backbeat; do not rush the Fill.",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    transpose_lyric_cue(text, catalog_key="Bb", practice_key="D"), text)

    def test_a_letter_inside_a_word_is_not_a_chord(self):
        text = "Fade on the Dm chord, Gently"
        out = transpose_lyric_cue(text, catalog_key="C", practice_key="D")
        self.assertIn("Gently", out)
        self.assertIn("Em", out)          # the real chord moved
        self.assertIn("Fade", out)

    def test_slash_chords_move_root_and_bass_together(self):
        """Both notes move. The output spells accidentals in ASCII, which is the
        existing convention here - a display layer prettifies them later - so the
        comparison normalises rather than pinning one alphabet."""
        out = transpose_lyric_cue(f"Intro {DASH} D/F{SHARP}", catalog_key="D",
                                  practice_key="E")
        self.assertEqual(out.replace(SHARP, "#"), f"Intro {DASH} E/G#")

    def test_a_suspended_slash_chord_moves_whole(self):
        out = transpose_lyric_cue(f"Pre {DASH} Csus4/D", catalog_key="C",
                                  practice_key="D")
        self.assertEqual(out, f"Pre {DASH} Dsus4/E")


class TheWholeCueMappingMoves(unittest.TestCase):
    def test_every_section_is_transposed(self):
        cues = {
            "Intro": [SAY_INTRO],
            "Verse": [f"Keep it soft {DASH} B{FLAT} {DOT} F"],
            "Chorus": ["Lift the dynamic here"],
        }
        out = transpose_lyric_cues(cues, catalog_key="Bb", practice_key="D")
        self.assertEqual(out["Intro"], [f"Instrumental {DASH} D {DOT} G {DOT} Bm {DOT} A"])
        self.assertEqual(out["Verse"], [f"Keep it soft {DASH} D {DOT} A"])
        self.assertEqual(out["Chorus"], ["Lift the dynamic here"])

    def test_the_original_mapping_is_not_mutated(self):
        cues = {"Intro": [SAY_INTRO]}
        transpose_lyric_cues(cues, catalog_key="Bb", practice_key="D")
        self.assertEqual(cues, {"Intro": [SAY_INTRO]})


if __name__ == "__main__":
    unittest.main()
