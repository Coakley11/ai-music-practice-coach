"""Authoritative confirmation tests for sidebar display_key_change."""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from display_key_sidebar_cloud_confirmation import (
    DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH,
    DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED,
    attempt_explicit_display_key_authoritative_confirmation,
    record_display_key_supabase_result,
)
from display_key_sidebar_persistence_trace import (
    DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY,
    arm_explicit_sidebar_display_key_save,
    begin_display_key_sidebar_transaction,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY


class TestDisplayKeySidebarCloudConfirmation(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_no_upsert_attempt_reports_not_attempted(self) -> None:
        ss: dict[str, Any] = {
            "developer_mode": True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            "_music_workspace_save_transaction": {"cloud_write_attempted": False},
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="test")
        arm_explicit_sidebar_display_key_save(ss, transaction_id=tx, selected_display_key="Cm")
        ok, forensic = attempt_explicit_display_key_authoritative_confirmation(
            ss,
            save_reason="display_key_change",
            expected_display_key="Cm",
        )
        self.assertFalse(ok)
        self.assertEqual(forensic.get("failure_code"), DISPLAY_KEY_CLOUD_WRITE_NOT_ATTEMPTED)

    def test_confirms_cm_from_network_refetch(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss: dict[str, Any] = {
            "developer_mode": True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            "_suite_cloud_workspace_key": "daniel",
            "_music_startup_revision_loaded": 10,
            "_music_workspace_save_transaction": {
                "cloud_write_attempted": True,
                "cloud_upsert_succeeded": True,
                "reserved_write_revision": 11,
                "transaction_id": "tx-test",
            },
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="test")
        arm_explicit_sidebar_display_key_save(ss, transaction_id=tx, selected_display_key="Cm", cloud_display_key_before="Dm")
        ss["_music_last_cloud_save_diag"] = {
            "cloud_upsert_attempted": True,
            "cloud_upsert_succeeded": True,
            "cloud_payload_revision": 11,
        }
        record_display_key_supabase_result(ss, saved=True)
        payload = {
            "core": {"display_key": "Cm"},
            "active_song_state": {"display_key": "Cm"},
            "workspace_revision": 11,
        }

        with patch("suite_cloud_state.load_cloud_full_session", return_value=(payload, "ts")):
            ss["_music_last_cloud_fetch_source"] = "network"
            ok, forensic = attempt_explicit_display_key_authoritative_confirmation(
                ss,
                save_reason="display_key_change",
                expected_display_key="Cm",
                payload_state=payload,
            )
        self.assertTrue(ok, forensic)
        self.assertEqual(forensic.get("fetched_display_key"), "Cm")
        self.assertNotIn(DISPLAY_KEY_SIDEBAR_SAVE_ACTIVE_KEY, ss)

    def test_value_mismatch_reports_specific_violation(self) -> None:
        ss: dict[str, Any] = {
            "developer_mode": True,
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            "_music_workspace_save_transaction": {
                "cloud_write_attempted": True,
                "cloud_upsert_succeeded": True,
                "reserved_write_revision": 11,
            },
        }
        tx = begin_display_key_sidebar_transaction(ss, caller="test")
        arm_explicit_sidebar_display_key_save(ss, transaction_id=tx, selected_display_key="Cm")
        record_display_key_supabase_result(ss, saved=True)
        ss["_music_last_cloud_save_diag"] = {
            "cloud_upsert_attempted": True,
            "cloud_upsert_succeeded": True,
        }
        payload = {"core": {"display_key": "Dm"}, "workspace_revision": 11}

        with patch("suite_cloud_state.load_cloud_full_session", return_value=(payload, "ts")):
            ss["_music_last_cloud_fetch_source"] = "network"
            ok, forensic = attempt_explicit_display_key_authoritative_confirmation(
                ss,
                save_reason="display_key_change",
                expected_display_key="Cm",
            )
        self.assertFalse(ok)
        self.assertEqual(forensic.get("failure_code"), DISPLAY_KEY_CLOUD_CONFIRMATION_VALUE_MISMATCH)


if __name__ == "__main__":
    unittest.main()
