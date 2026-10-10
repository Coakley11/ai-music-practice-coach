"""Runtime smoke test: actually execute the app script.

HTTP 200 on the Streamlit port and a healthy /_stcore/health endpoint prove
only that the server process is listening. Streamlit runs the app script when a
browser session connects, so a NameError in the script surfaces to the user and
not to either check -- that is exactly how an undefined
``_karaoke_hide_chart`` reached the browser.

AppTest executes the script the same way a session does, so an exception fails
the test instead of the page.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

APP = str(Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py")


def _apptest(timeout: int = 240):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(APP, default_timeout=timeout)


class TestKaraokeAppRuntimeSmoke(unittest.TestCase):
    """The app script must execute without raising, on the paths we changed."""

    @classmethod
    def setUpClass(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:                             # pragma: no cover
            raise unittest.SkipTest("streamlit AppTest unavailable")
        # Keep diagnostics out of the real runtime data dir.
        os.environ.setdefault("MUSIC_APP_DATA_DIR", str(Path(APP).parent / "_runtime_apptest_smoke"))

    def _assert_clean(self, at, where: str):
        """Fail with the actual exception text rather than a bare boolean."""
        if at.exception:
            msgs = []
            for exc in at.exception:
                msgs.append(str(getattr(exc, "value", exc)))
            self.fail(f"{where}: app script raised:\n  " + "\n  ".join(msgs))

    def test_app_script_runs_on_first_load(self):
        at = _apptest()
        at.run()
        self._assert_clean(at, "first load")

    def test_app_script_runs_on_backing_page(self):
        """The page carrying every karaoke render path we touched."""
        at = _apptest()
        at.session_state["studio_page"] = "backing"
        at.run()
        self._assert_clean(at, "backing page")

    def test_app_script_runs_with_karaoke_session_active(self):
        """Voice karaoke on Backing: the full performance render path."""
        at = _apptest()
        at.session_state["studio_page"] = "backing"
        at.session_state["instrument"] = "Voice"
        at.session_state["karaoke_mode_instrument"] = "Voice"
        at.session_state["karaoke_session_active"] = True
        at.session_state["karaoke_session_index"] = 0
        at.run()
        self._assert_clean(at, "karaoke active on backing")

    def test_app_script_runs_with_show_chords_off(self):
        """Show Chords OFF took a different branch through hide_chart/labels."""
        at = _apptest()
        at.session_state["studio_page"] = "backing"
        at.session_state["instrument"] = "Voice"
        at.session_state["karaoke_mode_instrument"] = "Voice"
        at.session_state["karaoke_session_active"] = True
        at.session_state["karaoke_show_chords"] = False
        at.run()
        self._assert_clean(at, "karaoke with Show Chords OFF")

    def test_app_script_runs_with_show_chords_on(self):
        at = _apptest()
        at.session_state["studio_page"] = "backing"
        at.session_state["instrument"] = "Voice"
        at.session_state["karaoke_mode_instrument"] = "Voice"
        at.session_state["karaoke_session_active"] = True
        at.session_state["karaoke_show_chords"] = True
        at.run()
        self._assert_clean(at, "karaoke with Show Chords ON")

    def test_app_script_runs_on_songs_page(self):
        """The picker page carries the sidebar identity reads."""
        at = _apptest()
        at.session_state["studio_page"] = "picker"
        at.run()
        self._assert_clean(at, "songs page")



class TestModuleLevelUseBeforeAssignment(unittest.TestCase):
    """Static guard for the bug class that reached the browser.

    The AppTest cases above execute the script, but the karaoke performance
    block sits behind conditions a synthetic session does not reach, so they
    passed even with the defect present (verified by reintroducing it). This
    check does catch it: it compares, at module scope, the first binding line
    of every name a diagnostic call loads against the call's own line.
    """

    def _module_scope_report(self) -> list[str]:
        import ast

        src = Path(APP).read_text(encoding="utf-8")
        tree = ast.parse(src)

        nested: list[tuple[int, int]] = []

        def walk(node):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nested.append((ch.lineno, ch.end_lineno or ch.lineno))
                    walk(ch)
                else:
                    walk(ch)

        walk(tree)

        def at_module_scope(line: int) -> bool:
            return not any(s <= line <= e for s, e in nested)

        first_bind: dict[str, int] = {}
        for node in ast.walk(tree):
            if not at_module_scope(getattr(node, "lineno", 10**9)):
                continue
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.For):
                targets = [node.target]
            for t in targets:
                names = []
                if isinstance(t, ast.Name):
                    names = [t.id]
                elif isinstance(t, (ast.Tuple, ast.List)):
                    names = [e.id for e in t.elts if isinstance(e, ast.Name)]
                for nm in names:
                    first_bind[nm] = min(first_bind.get(nm, node.lineno), node.lineno)

        problems: list[str] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"_karaoke_identity_trace", "_kr_audit"}
                and at_module_scope(node.lineno)
            ):
                continue
            label = ""
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    label = a.value
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    bound = first_bind.get(sub.id)
                    if bound is not None and bound > node.lineno:
                        problems.append(
                            f"L{node.lineno} [{label}] reads {sub.id!r} "
                            f"first bound at L{bound}"
                        )
        return problems

    def test_no_diagnostic_reads_a_name_bound_later(self):
        problems = self._module_scope_report()
        self.assertEqual(
            problems, [],
            "a diagnostic call reads a module-level name before it is bound; "
            "this raises NameError only on the render path that reaches it:\n  "
            + "\n  ".join(problems),
        )

if __name__ == "__main__":
    unittest.main()
