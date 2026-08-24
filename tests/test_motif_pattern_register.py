"""M1–M6: Motif pattern source preservation and register-aware sequencing."""

from __future__ import annotations

import unittest

from improvisation_motif import (
    build_motif_abc,
    build_motif_notation_abc,
    build_motif_pattern,
    generate_motif_for_chord,
    rebuild_motif_pattern,
    transform_motif,
)


class TestM1SourceMotifPreservation(unittest.TestCase):
    def test_first_cell_preserves_non_diatonic_exact(self) -> None:
        # F B Ab C — B is outside Fm diatonic; must not snap to Bb.
        motif = {
            "chord": "Fm",
            "notes": ["F", "B", "Ab", "C"],
            "midi": [65, 71, 68, 72],
        }
        pat = build_motif_pattern(
            motif,
            key_center="Fm",
            pattern_type="diatonic",
            direction="ascending",
            length=8,
        )
        self.assertEqual(pat["cells"][0], ["F", "B", "Ab", "C"])
        self.assertEqual(list(pat["midi"][:4]), [65, 71, 68, 72])
        self.assertNotEqual(pat["cells"][0], ["F", "Bb", "Ab", "C"])


class TestM2AscendingTrueRegister(unittest.TestCase):
    def test_ascending_cells_never_wrap_down(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["F", "Ab", "C", "Eb"],
            "midi": [65, 68, 72, 75],  # includes C5 / MIDI 72
        }
        pat = build_motif_pattern(
            motif,
            key_center="Fm",
            pattern_type="diatonic",
            direction="ascending",
            length=8,
        )
        midis = [int(m) for m in pat.get("midi") or []]
        self.assertEqual(midis[:4], [65, 68, 72, 75])
        # No isolated C5 → C4 wrap on an ascending pattern.
        self.assertNotIn(60, midis)
        cell_len = 4
        for i in range(1, 8):
            prev = midis[(i - 1) * cell_len : i * cell_len]
            cur = midis[i * cell_len : (i + 1) * cell_len]
            self.assertEqual(len(cur), cell_len)
            for a, b in zip(prev, cur):
                self.assertGreater(b, a, msg=f"cell {i}: {a} -> {b} must rise")


class TestM3DescendingTrueRegister(unittest.TestCase):
    def test_descending_cells_never_wrap_up(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["F", "Ab", "C", "Eb"],
            "midi": [65, 68, 72, 75],
        }
        pat = build_motif_pattern(
            motif,
            key_center="Fm",
            pattern_type="diatonic",
            direction="descending",
            length=8,
        )
        midis = [int(m) for m in pat.get("midi") or []]
        self.assertEqual(midis[:4], [65, 68, 72, 75])
        cell_len = 4
        for i in range(1, 8):
            prev = midis[(i - 1) * cell_len : i * cell_len]
            cur = midis[i * cell_len : (i + 1) * cell_len]
            for a, b in zip(prev, cur):
                self.assertLess(b, a, msg=f"cell {i}: {a} -> {b} must fall")


class TestM4PatternControls(unittest.TestCase):
    def test_type_length_direction_and_rhythm_preserve_pitches(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["F", "B", "Ab", "C"],
            "midi": [65, 71, 68, 72],
        }
        asc = build_motif_pattern(
            motif, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        self.assertEqual(asc["pattern_length"], 8)
        self.assertEqual(asc["cells"][0], ["F", "B", "Ab", "C"])

        long12 = rebuild_motif_pattern(
            asc, key_center="Fm", pattern_type="thirds", direction="ascending", length=12
        )
        self.assertEqual(long12["pattern_length"], 12)
        self.assertEqual(long12["pattern_type"], "thirds")
        self.assertEqual(long12["cells"][0], ["F", "B", "Ab", "C"])

        desc = rebuild_motif_pattern(
            long12, key_center="Fm", pattern_type="thirds", direction="descending", length=16
        )
        self.assertEqual(desc["pattern_length"], 16)
        self.assertEqual(desc["pattern_direction"], "descending")
        self.assertEqual(desc["cells"][0], ["F", "B", "Ab", "C"])

        pitches = list(desc["notes"])
        midis = list(desc["midi"])
        changed = transform_motif(desc, "change_rhythm", key_center="Fm")
        self.assertEqual(list(changed["notes"]), pitches)
        self.assertEqual(list(changed["midi"]), midis)
        self.assertNotEqual(changed.get("rhythm_key"), desc.get("rhythm_key"))

        up = transform_motif(desc, "sequence_up", key_center="Fm")
        self.assertEqual(len(up["notes"]), len(pitches))
        self.assertTrue(up.get("is_pattern"))
        self.assertNotEqual(up["notes"], pitches)


class TestM5SheetMusicRegister(unittest.TestCase):
    def test_abc_uses_full_pattern_and_register(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["F", "Ab", "C", "Eb"],
            "midi": [65, 68, 72, 75],
        }
        pat = build_motif_pattern(
            motif, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        abc = build_motif_abc(pat, key_center="Fm", bpm=100)
        # Full pattern — not a 4-note motif only.
        self.assertGreater(len(pat["notes"]), 4)
        # C5 (MIDI 72) and higher notes need ABC octave marks (').
        self.assertIn("'", abc)
        # Register-aware midis must survive into notation helper.
        abc2 = build_motif_notation_abc(pat, key_center="Fm", bpm=100)
        self.assertIn("X:", abc2)
        self.assertIn("'", abc2)


class TestM6ChordOwner(unittest.TestCase):
    def test_cshm_motif_and_pattern_owner(self) -> None:
        motif = generate_motif_for_chord("C#m", key_center="C# minor", level="Intermediate")
        self.assertEqual(motif.get("chord"), "C#m")
        self.assertNotEqual(list(motif.get("notes") or []), ["E", "F#", "G", "B"])
        pat = build_motif_pattern(motif, key_center="C# minor", length=8)
        self.assertEqual(pat.get("chord"), "C#m")
        self.assertEqual(pat["cells"][0], list(motif["notes"]))


if __name__ == "__main__":
    unittest.main()
