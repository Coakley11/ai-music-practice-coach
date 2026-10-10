"""ACC1-ACC6 — reordering a motif (reverse/invert/sequence) must preserve the
exact intended pitch of every source note, and the rebuilt notation must show
whatever accidental is necessary to reproduce that pitch against the active
key signature and in-bar accidental state - never a blind copy of the
original glyph, and never a generic respell that discards a deliberately
chosen collection spelling (Blues/Pentatonic).
"""

from __future__ import annotations

import logging
import re
import unittest

from improvisation_motif import _midi_from_note, build_motif_abc, transform_motif
from tests.abc_pitch_decoder import body_tokens, decode_abc_midis

logging.disable(logging.CRITICAL)


def _motif(notes: list[str], *, chord: str = "", relationship: str = "", meter: str = "4/4") -> dict:
    midis = [_midi_from_note(n, 4) for n in notes]
    m = {
        "chord": chord,
        "notes": list(notes),
        "midi": midis,
        "rhythm_symbols": ["quarter"] * len(notes),
        "meter": meter,
    }
    if relationship:
        m["pentatonic_relationship"] = relationship
    return m


def _tokens_no_len(abc: str) -> list[str]:
    return [re.sub(r"[\d/]+$", "", t) for t in body_tokens(abc)]


class TestACC1DMajorReversal(unittest.TestCase):
    """ACC1 — D major: C# C-natural D, reversed -> D C-natural C#."""

    def test_reversal_preserves_pitch_and_shows_explicit_natural(self) -> None:
        motif = _motif(["C#", "C", "D"], chord="D")
        before_midis = list(motif["midi"])
        out = transform_motif(motif, "invert", key_center="D")

        # MIDI/pitch identities are exactly reversed.
        self.assertEqual(out["midi"], list(reversed(before_midis)))
        self.assertEqual(out["notes"], ["D", "C", "C#"])

        abc = build_motif_abc(out, key_center="D")
        tokens = _tokens_no_len(abc)
        # Middle note stays natural, with an explicit natural sign (D major's
        # signature implies C#); the final note resolves back to sharp.
        self.assertEqual(tokens[:3], ["D", "=C", "^C"])
        self.assertEqual(decode_abc_midis(abc)[:3], out["midi"])


class TestACC2FlatKeyEquivalent(unittest.TestCase):
    """ACC2 — a flat key where a note explicitly cancels a key-signature flat."""

    def test_reversal_preserves_natural_cancelling_a_flat(self) -> None:
        # Eb major signature flats B/E/A; "E" here is an explicit natural.
        motif = _motif(["Eb", "E", "F"], chord="Eb")
        out = transform_motif(motif, "invert", key_center="Eb")
        self.assertEqual(out["notes"], ["F", "E", "Eb"])

        abc = build_motif_abc(out, key_center="Eb")
        tokens = _tokens_no_len(abc)
        self.assertEqual(tokens[:3], ["F", "=E", "_E"])
        self.assertEqual(decode_abc_midis(abc)[:3], out["midi"])


class TestACC3AccidentalCarryWithinMeasure(unittest.TestCase):
    """ACC3 — repeated same-letter notes where an earlier accidental in the
    transformed measure changes what must be written later."""

    def test_alternating_natural_and_sharp_within_one_bar(self) -> None:
        motif = _motif(["C#", "C", "C#", "C"], chord="D")
        before_midis = list(motif["midi"])
        out = transform_motif(motif, "invert", key_center="D")
        self.assertEqual(out["midi"], list(reversed(before_midis)))
        self.assertEqual(out["notes"], ["C", "C#", "C", "C#"])

        abc = build_motif_abc(out, key_center="D")
        tokens = _tokens_no_len(abc)
        self.assertEqual(tokens[:4], ["=C", "^C", "=C", "^C"])
        self.assertEqual(decode_abc_midis(abc)[:4], out["midi"])


class TestACC4BarLine(unittest.TestCase):
    """ACC4 — transformed notes cross a bar line: accidental state resets
    and the key signature becomes authoritative again."""

    def test_accidental_state_resets_at_the_barline(self) -> None:
        motif = _motif(["C#", "C", "D", "C#", "C", "D"], chord="D")
        before_midis = list(motif["midi"])
        out = transform_motif(motif, "invert", key_center="D")
        self.assertEqual(out["midi"], list(reversed(before_midis)))
        self.assertEqual(out["notes"], ["D", "C", "C#", "D", "C", "C#"])

        abc = build_motif_abc(out, key_center="D")
        tokens = _tokens_no_len(abc)
        # Bar 1: D =C ^C D | Bar 2 (fresh state): =C ^C (rest)
        self.assertEqual(tokens[:4], ["D", "=C", "^C", "D"])
        self.assertIn("|", abc)
        bar2 = tokens[4:6]
        self.assertEqual(bar2, ["=C", "^C"])
        self.assertEqual(decode_abc_midis(abc)[:6], out["midi"])


class TestACC5SharpNaturalSharp(unittest.TestCase):
    """ACC5 — explicit C# -> C-natural -> C# pattern, and its reversal."""

    def test_pattern_and_its_reversal(self) -> None:
        for notes in (["C#", "C", "C#"], ["C#", "C", "D", "C#"]):
            motif = _motif(notes, chord="D")
            before_midis = list(motif["midi"])
            out = transform_motif(motif, "invert", key_center="D")
            self.assertEqual(out["midi"], list(reversed(before_midis)), notes)
            abc = build_motif_abc(out, key_center="D")
            self.assertEqual(decode_abc_midis(abc), out["midi"], notes)


class TestACC6NotationMidiAgreement(unittest.TestCase):
    """ACC6 — displayed notation pitch, note names, and MIDI must agree for
    every transformed example, across sequence_up/sequence_down/invert."""

    def test_agreement_across_operations_and_keys(self) -> None:
        cases = [
            (["C#", "C", "D"], "D", "D"),
            (["Eb", "E", "F", "G"], "Eb", "Eb"),
            (["F#", "G", "A", "F#", "G"], "G", "G"),
            (["Bb", "B", "C", "Bb"], "F", "F"),
        ]
        for notes, chord, key in cases:
            for op in ("invert", "sequence_up", "sequence_down"):
                motif = _motif(notes, chord=chord)
                out = transform_motif(motif, op, key_center=key)
                abc = build_motif_abc(out, key_center=key)
                self.assertEqual(
                    decode_abc_midis(abc), [int(m) for m in out["midi"]], (notes, chord, key, op)
                )
                self.assertEqual(out["display"], " – ".join(out["notes"]))


class TestBluesPentatonicCollectionSpellingSurvivesTransform(unittest.TestCase):
    """The deliberately-chosen Blues/Pentatonic collection spelling (e.g. D
    Blues's "Ab") must survive reordering, not get silently respelled to the
    generic key-family equivalent ("G#") - reversing note-name letters and
    letting the destination key reinterpret them is exactly what must not
    happen, whether the note is a plain natural or a collection member."""

    def test_blues_ab_survives_invert_in_a_sharp_key(self) -> None:
        motif = _motif(["D", "Ab", "F", "D"], chord="D7", relationship="root_minor_blues")
        before_midis = list(motif["midi"])
        out = transform_motif(motif, "invert", key_center="D")
        self.assertEqual(out["midi"], list(reversed(before_midis)))
        self.assertEqual(out["notes"], ["D", "F", "Ab", "D"])
        self.assertNotIn("G#", out["notes"])
        self.assertEqual(out.get("pentatonic_relationship"), "root_minor_blues")

    def test_pentatonic_relationship_tag_survives_sequence_transforms(self) -> None:
        for op in ("sequence_up", "sequence_down", "invert"):
            motif = _motif(["D", "G", "C", "F", "A", "D"], chord="D7", relationship="root_minor")
            out = transform_motif(motif, op, key_center="D")
            self.assertEqual(out.get("pentatonic_relationship"), "root_minor", op)


if __name__ == "__main__":
    unittest.main()
