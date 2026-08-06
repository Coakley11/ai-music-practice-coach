"""AppTest proofs for streamlit_creative_full_production_harness.py."""

from __future__ import annotations

import inspect
import unittest
from typing import Any

STYLE_SID = "Bossa Nova"
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

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        self[key] = default
        return default


def _adapt(at: Any) -> _SessionAdapter:
    return _SessionAdapter(at.session_state)


def _gen_session_id(session: _SessionAdapter) -> str:
    from music_workflow_compatibility import legacy_session_id_for_owner

    return str(legacy_session_id_for_owner(session, "jam_session_generator") or GEN_SID)


def _style_session_id(session: _SessionAdapter) -> str:
    from music_workflow_compatibility import legacy_session_id_for_owner

    return str(legacy_session_id_for_owner(session, "style_jam") or STYLE_SID)


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

    def test_entry_mode_switch_does_not_queue_unarmed_backing(self) -> None:
        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        session = _adapt(at)
        self.assertEqual(
            str(session.get("improv_entry_mode") or ""),
            "Jam Session Generator",
        )
        self.assertEqual(_mission_trace_queued(session), [])
        at.radio(key="improv_entry_mode").set_value("Style Jam Mode").run()
        self.assertEqual(_mission_trace_queued(_adapt(at)), [])
        queued_seqs = [q.get("request_seq") for q in _mission_trace_queued(_adapt(at))]
        self.assertEqual(queued_seqs, [])

    def test_style_jam_c_to_d(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.selectbox(key="improv_style_key").set_value("D").run()
        session = _adapt(at)
        blob = get_workflow_blob(session, "style_jam", _style_session_id(session))
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "D")
        prog = blob.section_map.get("Head (Pop)") or []
        if prog and str(prog[0]).strip().upper().startswith("C"):
            last = session.get("_music_workflow_mutation_last") or {}
            self.assertGreater(int(last.get("transpose_applications") or 0), 0)

    def test_generator_c_to_a_after_entry_switch(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        at.selectbox(key="improv_jam_key").set_value("A").run()
        at.run(timeout=180)
        blob = get_workflow_blob(_adapt(at), "jam_session_generator", _gen_session_id(_adapt(at)))
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "A")

    def test_dual_entry_keys_in_one_session(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        at.selectbox(key="improv_jam_key").set_value("A").run()
        at.run(timeout=180)
        session = _adapt(at)
        gb = get_workflow_blob(session, "jam_session_generator", _gen_session_id(session))
        self.assertIsNotNone(gb)
        self.assertEqual(gb.keys.practice_tonic, "A")

        at.radio(key="improv_entry_mode").set_value("Style Jam Mode").run()
        at.run(timeout=180)
        at.selectbox(key="improv_style_key").set_value("D").run()
        at.run(timeout=180)
        session = _adapt(at)
        sb = get_workflow_blob(session, "style_jam", _style_session_id(session))
        gb_final = get_workflow_blob(session, "jam_session_generator", _gen_session_id(session))
        self.assertIsNotNone(sb)
        self.assertIsNotNone(gb_final)
        self.assertEqual(sb.keys.practice_tonic, "D")
        self.assertEqual(gb_final.keys.practice_tonic, "A")

    def test_hevenu_sidebar_identity_dm(self) -> None:
        from sidebar_key_identity import resolve_sidebar_key_identity

        at = self._run()
        at.radio(key="improv_entry_mode").set_value("Jam Session Generator").run()
        at.selectbox(key="improv_jam_key").set_value("A").run()
        at.run(timeout=180)
        base = _adapt(at)
        hevenu = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
            "selected_song": {"pick_key": "Jewish|Hevenu Shalom Aleichem", "key": "Dm"},
            "display_key": "D#",
            "concert_key": "D#",
            "_suite_active_workspace_id": base.get("_suite_active_workspace_id"),
            "_suite_account_id": base.get("_suite_account_id"),
        }
        ident = resolve_sidebar_key_identity(hevenu)
        self.assertEqual(ident.practice_tonic, "D")
        self.assertEqual(ident.practice_mode, "minor")
        token = str(ident.selector_token or "").strip()
        self.assertIn(token.lower(), {"dm", "d"})

    def test_late_entry_activation_queues_not_projects(self) -> None:
        from music_workflow_activation import activate_workflow_for_entry_mode
        from music_workflow_pending_activation import peek_pending_workflow_activation
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff
        from music_workflow_state_store import MUSIC_WORKFLOW_STATE_STORE_KEY

        at = self._run()
        base = _adapt(at)
        session_dict: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "_streamlit_widgets_locked_this_run": True,
            "_suite_active_workspace_id": str(base.get("_suite_active_workspace_id") or "harness-fp"),
            "_suite_account_id": str(base.get("_suite_account_id") or "harness-fp-acct"),
            MUSIC_WORKFLOW_STATE_STORE_KEY: base.get(MUSIC_WORKFLOW_STATE_STORE_KEY),
        }
        result = activate_workflow_for_entry_mode(session_dict)
        self.assertIsNotNone(result)
        self.assertTrue(result.skipped or result.ok)
        self.assertIsNotNone(peek_pending_workflow_activation(session_dict))
        self.assertIsNone(peek_pending_backing_workflow_handoff(session_dict))
        self.assertNotEqual(
            (session_dict.get("_music_workflow_mutation_last") or {}).get("error_code"),
            "REQUIRES_PRE_WIDGET_ACTIVATION",
        )

    def test_tab_entry_modes_direct_st_rerun_only_on_generate_buttons(self) -> None:
        from improvisation_intelligence_ui import _tab_entry_modes

        src = inspect.getsource(_tab_entry_modes)
        self.assertEqual(src.count("st.rerun()"), 2)
        self.assertIn('key="improv_gen_style"', src)
        self.assertIn('key="improv_gen_jam"', src)

    def test_explicit_open_backing_queues_with_arm(self) -> None:
        at = self._run()
        btn = at.button(key="improv_to_backing_jam")
        if btn is None:
            self.skipTest("Open in Backing Studio button not rendered")
        btn.click().run()
        session = _adapt(at)
        self.assertEqual(int(session.get("_harness_fp_mission_backing_clicks") or 0), 1)
        trace = session.get("_music_mission_backing_handoff_trace") or []
        phases = [t.get("phase") for t in trace if isinstance(t, dict)]
        self.assertIn("queued", phases)
        self.assertTrue(
            "consume_applied" in phases or session.get("studio_page") == "backing",
        )

    def test_generate_progression_after_key_edit_no_unarmed_backing(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        at = self._run()
        at.selectbox(key="improv_style_key").set_value("D").run()
        at.run(timeout=180)
        before = _mission_trace_queued(_adapt(at))
        gen_btn = at.button(key="improv_gen_style")
        if gen_btn is not None:
            gen_btn.click().run()
            at.run(timeout=180)
        session = _adapt(at)
        after = _mission_trace_queued(session)
        self.assertEqual(len(after), len(before))
        blob = get_workflow_blob(session, "style_jam", STYLE_SID)
        self.assertIsNotNone(blob)
        self.assertEqual(blob.keys.practice_tonic, "D")


if __name__ == "__main__":
    unittest.main()
