"""M1–M6: Motif pattern source preservation and register-aware sequencing."""

from __future__ import annotations

import unittest

from improvisation_motif import (
    _max_leap,
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
        # Named-direction realization keeps pitch classes and note order. Intra-cell
        # octaves may move so every adjacent MIDI continues ascending (B→Ab no
        # longer drops). B must not snap to Bb.
        cell0 = [int(m) for m in pat["midi"][:4]]
        self.assertEqual([int(m) % 12 for m in cell0], [5, 11, 8, 0])
        for i in range(1, 4):
            self.assertGreaterEqual(cell0[i], cell0[i - 1])
        self.assertLessEqual(_max_leap(cell0), 12)
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
        cell_len = 4
        # First cell is a rigid register shift of the source contour — no C5→C4 wrap.
        self.assertEqual(len(midis[:4]), 4)
        self.assertNotIn(60, midis[:4])  # isolated C4 wrap of a C5 source is forbidden
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


class TestM7CompactBaseMotif(unittest.TestCase):
    def test_b_a_g_a_stays_nearby(self) -> None:
        from improvisation_motif import _compact_midis_from_notes

        midis = _compact_midis_from_notes(["B", "A", "G", "A"])
        self.assertEqual(midis, [71, 69, 67, 69])
        self.assertLessEqual(_max_leap(midis), 2)
        # Reject octave zigzag B4 A5 G4 A5
        self.assertNotEqual(midis, [71, 81, 67, 81])

    def test_generated_motifs_are_compact(self) -> None:
        for chord, key in (("Bb", "Eb"), ("G", "C"), ("Cm", "Eb"), ("F#m", "A")):
            motif = generate_motif_for_chord(chord, key_center=key, level="Intermediate")
            midis = [int(m) for m in motif.get("midi") or []]
            self.assertEqual(len(midis), len(motif.get("notes") or []))
            self.assertLessEqual(_max_leap(midis), 12, msg=(chord, motif.get("notes"), midis))


class TestM8Ascending16NoMidWrap(unittest.TestCase):
    def test_ab_g_f_g_sixteen_cells_climb(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["Ab", "G", "F", "G"],
            "midi": [68, 67, 65, 67],
        }
        pat = build_motif_pattern(
            motif, key_center="Fm", pattern_type="diatonic", direction="ascending", length=16
        )
        self.assertEqual(pat["cells"][0], ["Ab", "G", "F", "G"])
        midis = [int(m) for m in pat["midi"]]
        cell_len = 4
        # No cell-mean drop (would indicate mid-pattern octave reset).
        means = [
            sum(midis[i * cell_len : (i + 1) * cell_len]) / cell_len for i in range(16)
        ]
        for i in range(1, 16):
            self.assertGreater(means[i], means[i - 1] - 0.01, msg=f"mean drop at cell {i}")
        for i in range(1, 16):
            for a, b in zip(
                midis[(i - 1) * cell_len : i * cell_len],
                midis[i * cell_len : (i + 1) * cell_len],
            ):
                self.assertGreater(b, a)


class TestM9Descending16NoMidWrap(unittest.TestCase):
    def test_ab_g_f_g_sixteen_cells_fall(self) -> None:
        motif = {
            "chord": "Fm",
            "notes": ["Ab", "G", "F", "G"],
            "midi": [68, 67, 65, 67],
        }
        pat = build_motif_pattern(
            motif, key_center="Fm", pattern_type="diatonic", direction="descending", length=16
        )
        midis = [int(m) for m in pat["midi"]]
        cell_len = 4
        means = [
            sum(midis[i * cell_len : (i + 1) * cell_len]) / cell_len for i in range(16)
        ]
        for i in range(1, 16):
            self.assertLess(means[i], means[i - 1] + 0.01, msg=f"mean rise at cell {i}")
        for i in range(1, 16):
            for a, b in zip(
                midis[(i - 1) * cell_len : i * cell_len],
                midis[i * cell_len : (i + 1) * cell_len],
            ):
                self.assertLess(b, a)


class TestM10CellContinuity(unittest.TestCase):
    def test_cell_boundary_leaps_bounded(self) -> None:
        motif = {"chord": "Fm", "notes": ["Ab", "G", "F", "G"], "midi": [68, 67, 65, 67]}
        for direction in ("ascending", "descending"):
            pat = build_motif_pattern(
                motif, key_center="Fm", pattern_type="diatonic", direction=direction, length=8
            )
            midis = [int(m) for m in pat["midi"]]
            cell_len = 4
            for i in range(1, 8):
                prev_last = midis[i * cell_len - 1]
                next_first = midis[i * cell_len]
                self.assertLessEqual(
                    abs(next_first - prev_last),
                    16,
                    msg=f"{direction} boundary cell {i}: {prev_last}->{next_first}",
                )


class TestM11SheetMusicRegister(unittest.TestCase):
    def test_abc_follows_planned_midis_not_octave4(self) -> None:
        motif = {"chord": "Fm", "notes": ["Ab", "G", "F", "G"], "midi": [56, 55, 53, 55]}
        pat = build_motif_pattern(
            motif, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        abc = build_motif_abc(pat, key_center="Fm", bpm=100)
        # Low starting register uses ABC comma octave marks, not all mid-staff.
        self.assertTrue("," in abc or "'" in abc)
        self.assertGreater(len(pat["notes"]), 4)


if __name__ == "__main__":
    unittest.main()
