"""G major pentatonic collection + Change Rhythm one-measure contract."""

from __future__ import annotations

import unittest

from improvisation_motif import (
    _beats_per_bar,
    _measure_rhythm_candidates,
    _rhythm_symbol_beats,
    abc_body_measures,
    abc_measure_beats,
    build_motif_abc,
    build_motif_pattern,
    cycle_motif_rhythm,
    transform_motif,
)

G_MAJOR_PENT = {"G", "A", "B", "D", "E"}
FORBIDDEN_G_PENT = {"A#", "Bb", "C", "C#", "Db", "F", "F#", "Gb"}


def _note_letter(note: str) -> str:
    text = str(note or "").strip()
    if text.endswith("#") or text.endswith("b"):
        return text[:2] if len(text) >= 2 and text[1] in {"#", "b"} else text[0]
    return text[0].upper() if text else ""


class TestGMajorPentatonicCollection(unittest.TestCase):
    def test_all_cells_stay_in_g_a_b_d_e(self) -> None:
        motif = {
            "chord": "G",
            "notes": ["A#", "B", "D", "C"],
            "midi": [70, 71, 74, 72],
        }
        pat = build_motif_pattern(
            motif,
            key_center="G",
            pattern_type="pentatonic",
            direction="ascending",
            length=8,
        )
        self.assertEqual(pat["pattern_type"], "pentatonic")
        first = [str(n) for n in pat["cells"][0]]
        self.assertEqual(first[0], "A", first)
        self.assertNotIn("A#", first)
        self.assertNotIn("C", first)
        for cell in pat["cells"]:
            letters = [_note_letter(n) for n in cell]
            for letter in letters:
                self.assertIn(letter, G_MAJOR_PENT, cell)
                self.assertNotIn(letter, FORBIDDEN_G_PENT)
        for note in pat["notes"]:
            self.assertIn(_note_letter(note), G_MAJOR_PENT)

    def test_sequence_up_down_move_one_pentatonic_degree(self) -> None:
        motif = {
            "chord": "G",
            "notes": ["G", "A", "B", "D"],
            "midi": [67, 69, 71, 74],
            "is_pattern": True,
            "pattern_type": "pentatonic",
            "pattern_direction": "ascending",
            "pattern_length": 4,
            "base_motif_notes": ["G", "A", "B", "D"],
            "cells": [["G", "A", "B", "D"]],
        }
        up = transform_motif(motif, "sequence_up", key_center="G")
        self.assertEqual([_note_letter(n) for n in up["notes"][:4]], ["A", "B", "D", "E"])
        down = transform_motif(up, "sequence_down", key_center="G")
        self.assertEqual([_note_letter(n) for n in down["notes"][:4]], ["G", "A", "B", "D"])
        for note in list(up["notes"]) + list(down["notes"]):
            self.assertIn(_note_letter(note), G_MAJOR_PENT)

    def test_each_cell_is_one_measure(self) -> None:
        motif = {
            "chord": "G",
            "notes": ["G", "A", "B", "D"],
            "midi": [67, 69, 71, 74],
            "meter": "4/4",
        }
        pat = build_motif_pattern(
            motif,
            key_center="G",
            pattern_type="pentatonic",
            direction="ascending",
            length=8,
        )
        abc = build_motif_abc(pat, key_center="G")
        measures = abc_body_measures(abc)
        self.assertEqual(len(measures), 8)
        for measure in measures:
            self.assertAlmostEqual(abc_measure_beats(measure), 4.0, places=2)


class TestChangeRhythmInjectable(unittest.TestCase):
    def test_injected_choice_is_demonstrably_different(self) -> None:
        motif = {
            "chord": "G",
            "notes": ["G", "A", "B", "D"] * 8,
            "cells": [["G", "A", "B", "D"]] * 8,
            "is_pattern": True,
            "pattern_type": "pentatonic",
            "base_motif_notes": ["G", "A", "B", "D"],
            "midi": [67, 69, 71, 74] * 8,
            "meter": "4/4",
            "cell_rhythm_symbols": ["♩", "♩", "♩", "♩"],
            "rhythm_symbols": ["♩"] * 32,
            "rhythm": "♩ ♩ ♩ ♩",
        }
        before = list(motif["cell_rhythm_symbols"])
        cands = _measure_rhythm_candidates(4, 4.0)
        alt = next(c for c in cands if tuple(c) != tuple(before))

        def _pick(_cands, _current):
            return list(alt)

        out = cycle_motif_rhythm(motif, meter="4/4", choose_rhythm=_pick)
        self.assertEqual(out["notes"], motif["notes"])
        self.assertEqual(out["pattern_type"], "pentatonic")
        self.assertNotEqual(list(out["cell_rhythm_symbols"]), before)
        self.assertEqual(list(out["cell_rhythm_symbols"]), list(alt))
        self.assertAlmostEqual(_rhythm_symbol_beats(out["cell_rhythm_symbols"]), _beats_per_bar("4/4"), places=2)
        cell_len = 4
        for i in range(8):
            self.assertEqual(
                out["rhythm_symbols"][i * cell_len : (i + 1) * cell_len],
                list(alt),
            )
        abc = build_motif_abc(out, key_center="G")
        measures = abc_body_measures(abc)
        self.assertEqual(len(measures), 8)
        for measure in measures:
            self.assertAlmostEqual(abc_measure_beats(measure), 4.0, places=2)

    def test_default_change_rhythm_is_not_a_no_op(self) -> None:
        motif = {
            "chord": "G",
            "notes": ["G", "A", "B", "D"] * 4,
            "cells": [["G", "A", "B", "D"]] * 4,
            "is_pattern": True,
            "meter": "4/4",
        }
        out = cycle_motif_rhythm(motif, meter="4/4")
        self.assertNotEqual(
            str(out.get("rhythm") or ""),
            "♩ ♩ ♩ ♩",
        )
        self.assertAlmostEqual(
            _rhythm_symbol_beats(list(out.get("cell_rhythm_symbols") or [])),
            4.0,
            places=2,
        )

    def test_change_rhythm_runs_when_notes_missing_but_cells_exist(self) -> None:
        from improvisation_motif import transform_motif

        motif = {
            "chord": "G",
            "notes": [],
            "cells": [["G", "A", "B", "D"]] * 4,
            "is_pattern": True,
            "meter": "4/4",
            "cell_rhythm_symbols": ["♩", "♩", "♩", "♩"],
            "last_transform": "build_pattern",
        }
        out = transform_motif(motif, "change_rhythm", key_center="G")
        self.assertEqual(out.get("last_transform"), "change_rhythm")
        self.assertNotEqual(str(out.get("rhythm") or ""), "♩ ♩ ♩ ♩")

    def test_rebuild_preserves_change_rhythm(self) -> None:
        from improvisation_motif import rebuild_motif_pattern

        motif = {
            "chord": "G",
            "notes": ["G", "A", "B", "D"] * 4,
            "cells": [["G", "A", "B", "D"]] * 4,
            "is_pattern": True,
            "pattern_type": "pentatonic",
            "pattern_direction": "ascending",
            "pattern_length": 4,
            "base_motif_notes": ["G", "A", "B", "D"],
            "midi": [67, 69, 71, 74] * 4,
            "meter": "4/4",
            "cell_rhythm_symbols": ["♩", "♩", "♩", "♩"],
            "last_transform": "build_pattern",
        }
        changed = cycle_motif_rhythm(motif, meter="4/4")
        self.assertEqual(changed.get("last_transform"), "change_rhythm")
        rhythm = list(changed.get("cell_rhythm_symbols") or [])
        rebuilt = rebuild_motif_pattern(
            changed,
            key_center="G",
            pattern_type="pentatonic",
            direction="ascending",
            length=4,
        )
        self.assertEqual(rebuilt.get("last_transform"), "change_rhythm")
        self.assertEqual(list(rebuilt.get("cell_rhythm_symbols") or []), rhythm)


if __name__ == "__main__":
    unittest.main()
