"""Mobile M3 — ordered musical content helpers (row-major; no i % n)."""

from __future__ import annotations

import inspect
import unittest


class TestMobileM3IterUiRows(unittest.TestCase):
    def test_chunks_are_row_major(self) -> None:
        from responsive_layout import iter_ui_rows

        items = list("ABCDEFGHI")
        rows = list(iter_ui_rows(items, cols_per_row=4))
        self.assertEqual(rows, [["A", "B", "C", "D"], ["E", "F", "G", "H"], ["I"]])
        # Flatten preserves original order
        self.assertEqual([x for row in rows for x in row], items)

    def test_empty_and_single(self) -> None:
        from responsive_layout import iter_ui_rows

        self.assertEqual(list(iter_ui_rows([], 4)), [])
        self.assertEqual(list(iter_ui_rows(["only"], 4)), [["only"]])


class TestMobileM3CallSitesAvoidModulo(unittest.TestCase):
    def test_composition_structure_uses_ordered_rows(self) -> None:
        import composition_studio_page as csp

        src = inspect.getsource(csp._render_phase_structure)
        self.assertIn("render_ordered_column_rows", src)
        self.assertNotIn("i % len(strip_cols)", src)
        self.assertNotIn("strip_cols[i %", src)

    def test_composition_workflow_strip_uses_ordered_rows(self) -> None:
        import composition_studio_page as csp

        src = inspect.getsource(csp._render_workflow_section_strip)
        self.assertIn("render_ordered_column_rows", src)
        self.assertNotIn("i % len(cols)", src)

    def test_harmony_map_uses_row_chunks(self) -> None:
        import improvisation_intelligence_ui as ii

        src = inspect.getsource(ii._tab_harmony_map)
        self.assertIn("row_start", src)
        self.assertIn("cols_per_row", src)
        self.assertNotIn("i % len(cols)", src)

    def test_dha_section_picker_uses_ordered_rows(self) -> None:
        from pathlib import Path

        src = Path("deep_harmonic_analyzer_ui.py").read_text(encoding="utf-8")
        self.assertIn("render_ordered_column_rows", src)
        self.assertNotIn("cols[j % len(cols)]", src)


class TestMobileM3RenderHelperContract(unittest.TestCase):
    def test_helper_exported_from_app_ui(self) -> None:
        from app_ui import render_ordered_column_rows
        from responsive_layout import iter_ui_rows

        src = inspect.getsource(render_ordered_column_rows)
        self.assertIn("iter_ui_rows", src)
        self.assertIn("st.columns", src)
        # Sanity: helper uses shared chunker
        self.assertTrue(callable(iter_ui_rows))


if __name__ == "__main__":
    unittest.main()
