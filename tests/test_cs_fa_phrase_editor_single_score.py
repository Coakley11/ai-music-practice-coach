"""Phrase editor shows ONE score: static staff until armed, then the synced player only."""
import unittest

import streamlit.components.v1 as _components


class TestPhraseEditorSingleScore(unittest.TestCase):
    def setUp(self) -> None:
        # The AppTest harness replaces components.html with a capture fake in-process; restore the
        # real function afterwards so later tests that count real iframes are not affected.
        self.addCleanup(setattr, _components, "html", _components.html)

    def _run(self, arm: bool):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("tests/_cs_fa_editor_harness.py", default_timeout=60)
        if arm:
            at.session_state["_arm"] = True
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at, list(at.session_state["_html_calls"])

    def test_unarmed_renders_exactly_one_static_score(self) -> None:
        _, calls = self._run(False)
        self.assertEqual(len(calls), 1)
        self.assertIn("ABCJS.renderAbc", calls[0])

    def test_armed_renders_exactly_one_synced_score(self) -> None:
        _, calls = self._run(True)
        self.assertEqual(len(calls), 1)
        self.assertIn("cplay", calls[0])


if __name__ == "__main__":
    unittest.main()
