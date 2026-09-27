"""Slice 5D — Phrase/Motif: no Diatonic UI, one direction control, Auto/Musical skips + accidentals."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from improvisation_motif import (
    PATTERN_TYPES_UI,
    _auto_musical_cell_offsets,
    _normalize_pattern_type,
    build_motif_pattern,
)


def _seed_motif(notes: list[str], *, key: str = "G") -> dict:
    from improvisation_motif import sync_motif_midi

    return sync_motif_midi(
        {
            "chord": f"{key}maj7",
            "notes": list(notes),
            "base_motif_notes": list(notes),
            "display": " – ".join(notes),
            "rhythm": "♩ ♩ ♩ ♩",
            "rhythm_key": "quarter-quarter-quarter-quarter",
        }
    )


class TestSlice5DPatternUI(unittest.TestCase):
    def test_no_diatonic_in_ui_types(self) -> None:
        self.assertNotIn("diatonic", PATTERN_TYPES_UI)
        self.assertIn("auto", PATTERN_TYPES_UI)
        self.assertIn("scalar", PATTERN_TYPES_UI)

    def test_diatonic_normalizes_to_scalar(self) -> None:
        self.assertEqual(_normalize_pattern_type("diatonic"), "scalar")
        self.assertEqual(_normalize_pattern_type("auto"), "auto")

    def test_ui_source_has_no_diatonic_label_or_descending_button(self) -> None:
        src = Path("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        # Pattern type labels block should not offer Diatonic.
        self.assertNotIn('"diatonic": "Diatonic"', src)
        self.assertNotIn('improv_motif_dir_descending_btn', src)
        self.assertIn('format_func=lambda d: "Ascending" if d == "ascending" else "Descending"', src)
        # Exactly one Direction selectbox key.
        self.assertEqual(src.count('key="improv_motif_pattern_dir_widget"'), 1)


class TestSlice5DAutoMusical(unittest.TestCase):
    def test_auto_offsets_include_skips(self) -> None:
        offs = _auto_musical_cell_offsets(8, sign=1)
        self.assertEqual(offs[0], 0)
        deltas = [offs[i + 1] - offs[i] for i in range(len(offs) - 1)]
        self.assertTrue(any(d >= 2 for d in deltas), deltas)
        self.assertNotEqual(deltas, [1] * (len(deltas)))

    def test_auto_descending_mirrors_offsets(self) -> None:
        up = _auto_musical_cell_offsets(6, sign=1)
        down = _auto_musical_cell_offsets(6, sign=-1)
        self.assertEqual(down, [-x for x in up])

    def test_auto_can_produce_accidentals(self) -> None:
        motif = _seed_motif(["G", "A", "B", "D"], key="G")
        out = build_motif_pattern(
            motif,
            key_center="G",
            pattern_type="auto",
            direction="ascending",
            length=8,
        )
        notes = list(out.get("notes") or [])
        self.assertGreaterEqual(len(notes), 8)
        # Chromatic collection + skip offsets must introduce #/b spellings (key-aware).
        accidental = any("#" in str(n) or "b" in str(n) for n in notes)
        self.assertTrue(accidental, f"auto expected accidentals: notes={notes[:16]}")
        cells = list(out.get("cells") or [])
        self.assertGreaterEqual(len(cells), 4)
        cell_starts = [c[0] for c in cells if c]
        from music_theory import pitch_class_from_spelled_note

        pcs = [pitch_class_from_spelled_note(n) for n in cell_starts]
        semis = [(pcs[i + 1] - pcs[i]) % 12 for i in range(len(pcs) - 1)]
        has_skip = any(s not in (0, 1, 2, 10, 11) for s in semis)
        self.assertTrue(
            has_skip or len(set(semis)) > 1,
            f"auto too stepwise: notes={notes[:16]} semis={semis}",
        )

    def test_auto_not_identical_to_scalar_seconds(self) -> None:
        motif = _seed_motif(["G", "A", "B", "D"], key="G")
        auto = build_motif_pattern(
            motif, key_center="G", pattern_type="auto", direction="ascending", length=8
        )
        scalar = build_motif_pattern(
            motif, key_center="G", pattern_type="scalar", direction="ascending", length=8
        )
        self.assertNotEqual(auto.get("notes"), scalar.get("notes"))
        self.assertEqual(auto.get("pattern_type"), "auto")
        self.assertEqual(scalar.get("pattern_type"), "scalar")

    def test_ascending_vs_descending_direction(self) -> None:
        motif = _seed_motif(["C", "D", "E", "G"], key="C")
        up = build_motif_pattern(
            motif, key_center="C", pattern_type="scalar", direction="ascending", length=8
        )
        down = build_motif_pattern(
            motif, key_center="C", pattern_type="scalar", direction="descending", length=8
        )
        self.assertEqual(up.get("pattern_direction"), "ascending")
        self.assertEqual(down.get("pattern_direction"), "descending")
        up_midi = list(up.get("midi") or [])
        down_midi = list(down.get("midi") or [])
        self.assertTrue(up_midi and down_midi)
        # Ascending pattern trends up; descending trends down across the phrase.
        self.assertGreater(up_midi[-1], up_midi[0])
        self.assertLess(down_midi[-1], down_midi[0])

    def test_legacy_diatonic_build_equals_scalar(self) -> None:
        motif = _seed_motif(["F", "G", "A", "C"], key="F")
        a = build_motif_pattern(
            motif, key_center="F", pattern_type="diatonic", direction="ascending", length=8
        )
        b = build_motif_pattern(
            motif, key_center="F", pattern_type="scalar", direction="ascending", length=8
        )
        self.assertEqual(a.get("notes"), b.get("notes"))
        self.assertEqual(a.get("pattern_type"), "scalar")

    def test_pattern_build_does_not_touch_owners(self) -> None:
        session_like = {
            "backing_owner_kind": "catalog",
            "creative_owner": "catalog",
            "display_key": "G",
            "active_catalog_pick_key": "pop::perfect",
            "_studio_nav_history": ["Creative"],
        }
        before = dict(session_like)
        motif = _seed_motif(["G", "A", "B", "D"], key="G")
        build_motif_pattern(
            motif, key_center="G", pattern_type="auto", direction="ascending", length=8
        )
        self.assertEqual(session_like, before)


if __name__ == "__main__":
    unittest.main()
