"""Streamlit runtime smoke — pre-widget bootstrap runs on first script pass."""

from __future__ import annotations

import unittest
from pathlib import Path


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestStreamlitPreWidgetBootstrapSmoke(unittest.TestCase):
    def test_app_run_sets_bootstrap_ran_flag(self) -> None:
        from streamlit.testing.v1 import AppTest

        root = Path(__file__).resolve().parents[1]
        app_path = root / "streamlit_music_practice_app.py"
        at = AppTest.from_file(str(app_path), default_timeout=120)
        at.run(timeout=180)
        self.assertTrue(at.session_state["_music_pre_widget_bootstrap_ran_this_run"])
        last = at.session_state["_music_pre_widget_bootstrap_last"]
        self.assertIsInstance(last, dict)


if __name__ == "__main__":
    unittest.main()
