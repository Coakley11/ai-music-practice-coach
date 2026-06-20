"""Smoke checks for Custom Progression page UI source (no Streamlit runtime)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CPL_PAGE_UI = ROOT / "cpl_page_ui.py"


class TestCplPageUiSmoke(unittest.TestCase):
    def test_action_button_columns_are_defined_before_use(self) -> None:
        source = CPL_PAGE_UI.read_text(encoding="utf-8")
        columns_idx = source.index("n1, n2, n3 = st.columns(3)")
        with_n1_idx = source.index("with n1:")
        self.assertLess(
            columns_idx,
            with_n1_idx,
            "n1/n2/n3 columns must be created before `with n1:`",
        )

    def test_render_function_has_no_undefined_with_targets(self) -> None:
        tree = ast.parse(CPL_PAGE_UI.read_text(encoding="utf-8"))
        render_fn = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "render_custom_progression_lab_page"
        )
        assigned: set[str] = set()
        for node in ast.walk(render_fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.add(target.id)
                    elif isinstance(target, ast.Tuple):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name):
                                assigned.add(elt.id)
            elif isinstance(node, ast.With):
                for item in node.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Name) and ctx.id not in assigned:
                        self.fail(f"Undefined variable used in with-block: {ctx.id}")


if __name__ == "__main__":
    unittest.main()
