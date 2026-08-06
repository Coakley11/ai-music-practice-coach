"""AppTest proofs against streamlit_generated_key_harness.py — real widget lifecycle."""

from __future__ import annotations

import unittest
from typing import Any

STYLE_SID = "Pop groove"
GEN_SID = "jam-harness-1"


def _ss(at: Any) -> Any:
    return at.session_state


class _SessionAdapter:
    """Minimal dict-like view for workflow store helpers over AppTest session_state."""

    def __init__(self, ss: Any) -> None:
        self._ss = ss

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._ss[key]
        except (KeyError, TypeError):
            return default

    def __getitem__(self, key: str) -> Any:
        return self._ss[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._ss[key] = value

    def __contains__(self, key: object) -> bool:
        try:
            self._ss[str(key)]  # type: ignore[index]
            return True
        except (KeyError, TypeError):
            return False


def _adapt(at: Any) -> _SessionAdapter:
    return _SessionAdapter(_ss(at))


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestStreamlitGeneratedKeyHarnessAppTest(unittest.TestCase):
    HARNESS = "streamlit_generated_key_harness.py"

    def _run_harness(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.HARNESS, default_timeout=90)
        at.run(timeout=120)
        return at

    def test_style_jam_c_to_d_via_selectbox_and_rerun(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run_harness()
        at.selectbox(key="improv_style_key").set_value("D").run()
        self.assertEqual(_ss(at)["improv_style_key"], "D")
        blob = get_workflow_blob(_adapt(at), "style_jam", STYLE_SID)
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "D")
        prog = blob.section_map.get("Head (Pop)") or []
        self.assertTrue(prog)
        self.assertNotEqual(prog[0], "C")
        self.assertNotIn("_music_projection_block_last", _adapt(at))

    def test_generator_c_to_a_via_selectbox_and_rerun(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run_harness()
        at.selectbox(key="improv_jam_key").set_value("A").run()
        self.assertEqual(_ss(at)["improv_jam_key"], "A")
        blob = get_workflow_blob(_adapt(at), "jam_session_generator", GEN_SID)
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "A")

    def test_independent_keys_after_second_style_change(self) -> None:
        """Dual-widget sequencing in one AppTest session — known gap; see isolated tests."""
        from music_workflow_state_store import get_workflow_blob

        at = self._run_harness()
        at.selectbox(key="improv_style_key").set_value("D").run()
        at.run(timeout=120)
        at.selectbox(key="improv_jam_key").set_value("A").run()
        at.run(timeout=120)
        sb = get_workflow_blob(_adapt(at), "style_jam", STYLE_SID)
        gb = get_workflow_blob(_adapt(at), "jam_session_generator", GEN_SID)
        self.assertIsNotNone(sb)
        self.assertIsNotNone(gb)
        self.assertEqual(sb.keys.practice_tonic, "D")
        self.assertEqual(gb.keys.practice_tonic, "A")

    def test_bootstrap_runs_before_widgets_each_run(self) -> None:
        at = self._run_harness()
        self.assertTrue(_ss(at)["_music_pre_widget_bootstrap_ran_this_run"])
        at.selectbox(key="improv_style_key").set_value("D").run()
        self.assertTrue(_ss(at)["_music_pre_widget_bootstrap_ran_this_run"])

    def test_hevenu_identity_dm_in_harness_tab(self) -> None:
        from sidebar_key_identity import resolve_sidebar_key_identity

        at = self._run_harness()
        hevenu: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
            "selected_song": {"pick_key": "Jewish|Hevenu Shalom Aleichem", "key": "Dm"},
            "display_key": "D#",
            "concert_key": "D#",
        }
        ident = resolve_sidebar_key_identity(hevenu)
        self.assertEqual(ident.practice_tonic, "D")
        self.assertEqual(ident.practice_mode, "minor")
        self.assertIn(ident.label, {"Dm", "D minor"})


if __name__ == "__main__":
    unittest.main()
