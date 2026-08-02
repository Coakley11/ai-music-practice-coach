"""Creative selector save durability trace (Supabase upsert + forced network refetch)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_selector_save_durability_trace import (
    CREATIVE_SELECTOR_SAVE_ACTIVE_KEY,
    VIOLATION_FALSE_AUTHORITATIVE,
    VIOLATION_UPSERT_NOT_ATTEMPTED,
    begin_selector_save_durability,
    finalize_selector_save_confirmation,
    record_force_save_path,
    record_payload_before_upsert,
    record_supabase_result,
)
from creative_tab_tool_persistence import (
    CREATIVE_SELECTOR_LAST_TX_KEY,
    CREATIVE_TAB_USER_EVENT_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    SAVE_REASON_TAB,
    default_creative_workspace_state,
    record_creative_tab_save_outcome,
)
from creative_workspace_state_persistence import default_creative_workspace_state as dws


def _missions_payload(rev: int) -> dict:
    cws = {**dws(), "improv_intelligence_tab": "Missions"}
    return {
        "workspace_revision": rev,
        "creative_workspace_state": cws,
        "session": {"improv_intelligence_tab": "Missions"},
        "music_workspace_state": {"workspace_revision": rev, "creative_workspace_state": cws},
    }


class TestSelectorSaveDurabilityFinalize(unittest.TestCase):
    def test_full_pipeline_confirms_from_network_refetch(self) -> None:
        ss: dict = {
            "_script_run_seq": 10,
            "_suite_active_workspace": "daniel",
            "_suite_cloud_workspace_key": "workspaces/daniel",
            "_suite_applied_workspace_revision": 193,
            "_music_last_cloud_fetch_source": "network",
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_intelligence_tab": "Missions",
            },
            CREATIVE_TAB_USER_EVENT_KEY: {
                "field": "improv_intelligence_tab",
                "value": "Missions",
                "old_value": "Entry & Jam",
                "run_seq": 10,
            },
        }
        begin_selector_save_durability(
            ss,
            field="improv_intelligence_tab",
            old_value="Entry & Jam",
            selected_value="Missions",
            widget_key="improv_intelligence_tab",
            save_reason=SAVE_REASON_TAB,
        )
        record_force_save_path(
            ss,
            save_reason=SAVE_REASON_TAB,
            force_save_entered=True,
            allowed=True,
            canonical_revision_before=193,
            reserved_revision=194,
        )
        upsert_state = _missions_payload(194)
        record_payload_before_upsert(ss, upsert_state, write_path="force_music_workspace_save")
        record_supabase_result(
            ss,
            diag={
                "cloud_upsert_attempted": True,
                "cloud_upsert_succeeded": True,
                "cloud_payload_revision": 194,
            },
            saved=True,
        )
        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(_missions_payload(194), 0.0),
        ):
            from creative_selector_save_durability_trace import perform_authoritative_selector_refetch

            perform_authoritative_selector_refetch(ss)
        result = finalize_selector_save_confirmation(ss, force_save_ok=True)
        self.assertEqual(result.get("confirmation_status"), "confirmed")
        self.assertEqual(result.get("reserved_revision"), 194)
        self.assertEqual(result.get("confirmed_revision"), 194)
        self.assertEqual(result.get("authoritative_refetched_value"), "Missions")
        self.assertNotIn(CREATIVE_SELECTOR_SAVE_ACTIVE_KEY, ss)

    def test_false_confirmation_when_refetch_revision_stale(self) -> None:
        ss: dict = {
            "_script_run_seq": 11,
            "_suite_applied_workspace_revision": 193,
            "_music_last_cloud_fetch_source": "network",
        }
        begin_selector_save_durability(
            ss,
            field="improv_intelligence_tab",
            old_value="Entry & Jam",
            selected_value="Missions",
            widget_key="improv_intelligence_tab",
            save_reason=SAVE_REASON_TAB,
        )
        record_force_save_path(
            ss,
            save_reason=SAVE_REASON_TAB,
            force_save_entered=True,
            allowed=True,
            reserved_revision=199,
        )
        record_payload_before_upsert(ss, _missions_payload(199))
        record_supabase_result(
            ss,
            diag={"cloud_upsert_attempted": True, "cloud_upsert_succeeded": True, "cloud_payload_revision": 199},
            saved=True,
        )
        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=({"workspace_revision": 193}, 0.0),
        ):
            from creative_selector_save_durability_trace import perform_authoritative_selector_refetch

            perform_authoritative_selector_refetch(ss)
        result = finalize_selector_save_confirmation(ss, force_save_ok=True)
        self.assertEqual(result.get("confirmation_status"), "unconfirmed")
        violations = (ss.get("_creative_tab_tool_diag") or {}).get("violations") or []
        codes = {v.get("code") for v in violations}
        self.assertIn(VIOLATION_FALSE_AUTHORITATIVE, codes)


class TestRecordCreativeTabSaveOutcome(unittest.TestCase):
    def test_record_outcome_requires_authoritative_refetch(self) -> None:
        ss: dict = {
            "_script_run_seq": 10,
            "_suite_applied_workspace_revision": 193,
            "_music_last_cloud_fetch_source": "network",
            CREATIVE_TAB_USER_EVENT_KEY: {
                "field": "improv_intelligence_tab",
                "value": "Missions",
                "run_seq": 10,
            },
        }
        begin_selector_save_durability(
            ss,
            field="improv_intelligence_tab",
            old_value="",
            selected_value="Missions",
            widget_key="improv_intelligence_tab",
            save_reason=SAVE_REASON_TAB,
        )
        record_force_save_path(ss, save_reason=SAVE_REASON_TAB, force_save_entered=True, reserved_revision=194)
        record_payload_before_upsert(ss, _missions_payload(194))
        record_supabase_result(
            ss,
            diag={"cloud_upsert_attempted": True, "cloud_upsert_succeeded": True, "cloud_payload_revision": 194},
            saved=True,
        )
        ss[CREATIVE_SELECTOR_SAVE_ACTIVE_KEY]["B_force_save_path"] = ss[CREATIVE_SELECTOR_SAVE_ACTIVE_KEY].get(
            "B_force_save_path"
        ) or {"reserved_revision": 194}

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(_missions_payload(194), 0.0),
        ):
            record_creative_tab_save_outcome(ss, save_reason=SAVE_REASON_TAB, ok=True)
        last = ss.get(CREATIVE_SELECTOR_LAST_TX_KEY)
        self.assertEqual((last or {}).get("confirmation_status"), "confirmed")

    def test_no_upsert_emits_violation(self) -> None:
        ss: dict = {
            CREATIVE_TAB_USER_EVENT_KEY: {"field": "improv_intelligence_tab", "value": "Missions", "run_seq": 1},
            "_music_last_cloud_fetch_source": "network",
        }
        begin_selector_save_durability(
            ss,
            field="improv_intelligence_tab",
            old_value="",
            selected_value="Missions",
            widget_key="improv_intelligence_tab",
            save_reason=SAVE_REASON_TAB,
        )
        record_supabase_result(ss, diag={}, saved=False)
        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=({"workspace_revision": 193}, 0.0),
        ):
            record_creative_tab_save_outcome(ss, save_reason=SAVE_REASON_TAB, ok=False)
        codes = {v.get("code") for v in (ss.get("_creative_tab_tool_diag") or {}).get("violations") or []}
        self.assertIn(VIOLATION_UPSERT_NOT_ATTEMPTED, codes)


if __name__ == "__main__":
    unittest.main()
