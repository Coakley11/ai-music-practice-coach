"""AppTest proofs for streamlit_creative_full_production_harness.py."""

from __future__ import annotations

import inspect
import unittest
from typing import Any

STYLE_SID = "Pop groove"
GEN_SID = "jam-harness-fp-1"
HARNESS = "streamlit_creative_full_production_harness.py"


class _SessionAdapter:
    def __init__(self, ss: Any) -> None:
        self._ss = ss

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._ss[key]
        except (KeyError, TypeError, AttributeError):
            return default

    def __getitem__(self, key: str) -> Any:
        return self._ss[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._ss[key] = value

    def __contains__(self, key: object) -> bool:
        try:
            self._ss[str(key)]  # type: ignore[index]
            return True
        except (KeyError, TypeError, AttributeError):
            return False


def _adapt(at: Any) -> _SessionAdapter:
    return _SessionAdapter(at.session_state)


def _mission_trace_queued(session: _SessionAdapter) -> list[dict[str, Any]]:
    trace = session.get("_music_mission_backing_handoff_trace")
    if not isinstance(trace, list):
        return []
    return [t for t in trace if isinstance(t, dict) and t.get("phase") == "queued"]


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCreativeFullProductionHarness(unittest.TestCase):
    def _run(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(HARNESS, default_timeout=120)
        at.run(timeout=180)
        return at

    def test_initial_render_does_not_queue_mission_backing(self) -> None:
        at = self._run()
        session = _adapt(at)
        self.assertEqual(_mission_trace_queued(session), [])
        self.assertIsNone(session.get("_music_pending_backing_workflow_handoff"))

    def test_repro_entry_mode_switch_queues_unarmed_backing(self) -> None:
        """Matches FAILED_LIVE Cloud sequence (seq=1, full rollback, not consume_armed)."""
        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        session = _adapt(at)
        self.assertEqual(
            str(session.get("improv_entry_mode") or ""),
            "Jam Session Generator",
        )
        queued = _mission_trace_queued(session)
        self.assertGreaterEqual(len(queued), 1)
        self.assertEqual(queued[-1].get("request_seq"), 1)
        self.assertFalse(queued[-1].get("with_practice_lick"))
        diag = session.get("_music_workflow_mutation_last") or {}
        if isinstance(diag, dict):
            self.assertEqual(diag.get("error_code"), "REQUIRES_PRE_WIDGET_ACTIVATION")

    @unittest.expectedFailure
    def test_gate_entry_mode_switch_must_not_queue_backing(self) -> None:
        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        self.assertEqual(_mission_trace_queued(_adapt(at)), [])

    @unittest.expectedFailure
    def test_style_jam_c_to_d(self) -> None:
        """Style Jam canonical consume under full shell — matches FAILED_LIVE gap."""
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.selectbox(key="improv_style_key").set_value("D").run()
        at.run(timeout=180)
        blob = get_workflow_blob(_adapt(at), "style_jam", STYLE_SID)
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "D")

    def test_generator_c_to_a_after_entry_switch(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        at.selectbox(key="improv_jam_key").set_value("A").run()
        blob = get_workflow_blob(_adapt(at), "jam_session_generator", GEN_SID)
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "A")

    def test_hevenu_sidebar_identity_dm(self) -> None:
        from sidebar_key_identity import resolve_sidebar_key_identity

        at = self._run()
        base = {k: _adapt(at).get(k) for k in ("studio_page", "display_key", "concert_key")}
        hevenu = {
            **base,
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

    def test_tab_entry_modes_direct_st_rerun_only_on_generate_buttons(self) -> None:
        from improvisation_intelligence_ui import _tab_entry_modes

        src = inspect.getsource(_tab_entry_modes)
        rerun_count = src.count("st.rerun()")
        self.assertEqual(
            rerun_count,
            2,
            msg="_tab_entry_modes must expose exactly two direct st.rerun() calls (both Generate buttons)",
        )
        self.assertIn('key="improv_gen_style"', src)
        self.assertIn('key="improv_gen_jam"', src)

    def test_explicit_open_backing_queues_with_arm(self) -> None:
        at = self._run()
        btn = at.button(key="improv_to_backing_jam")
        if btn is None:
            self.skipTest("Open in Backing Studio button not rendered (generate a jam first)")
        btn.click().run()
        session = _adapt(at)
        self.assertEqual(int(session.get("_harness_fp_mission_backing_clicks") or 0), 1)
        trace = session.get("_music_mission_backing_handoff_trace") or []
        phases = [t.get("phase") for t in trace if isinstance(t, dict)]
        self.assertIn("queued", phases)
        self.assertTrue(
            "consume_applied" in phases or session.get("studio_page") == "backing",
            msg=f"Armed handoff should consume on next run; phases={phases}",
        )

    @unittest.expectedFailure
    def test_gate_late_entry_activation_must_not_queue_backing(self) -> None:
        from music_workflow_activation import activate_workflow_for_entry_mode
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

        at = self._run()
        session = dict(_adapt(at))
        session["_streamlit_widgets_locked_this_run"] = True
        activate_workflow_for_entry_mode(session)
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))


if __name__ == "__main__":
    unittest.main()
