"""Tests for music workspace save transaction dev diagnostics."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_workspace_cloud_save import MUSIC_SAVE_TX_KEY, record_save_transaction
from music_workspace_save_transaction_debug import (
    append_workspace_save_transaction_snapshot,
    build_save_transaction_debug_bundle,
    ensure_streamlit_run_sequence,
)


class MusicWorkspaceSaveTransactionDebugTests(unittest.TestCase):
    def test_bundle_merges_tx_and_cloud_diag(self) -> None:
        ss: dict = {
            MUSIC_SAVE_TX_KEY: {
                "force_save_reason": "song_edit",
                "raw_save_reason": "song_edit",
                "normalized_save_reason": "song_edit",
                "strict_egress_plan_action": "duplicate_skip",
                "duplicate_write_skipped": True,
                "envelope_revision_before": 3,
                "envelope_revision_after": 3,
                "cloud_write_succeeded": True,
                "cloud_readback_matches": True,
            },
            "_suite_last_cloud_save_result": {
                "cloud_upsert_attempted": False,
                "save_cloud_full_session_return_value": False,
            },
            "_suite_persist_last_save_cloud": False,
            "_music_force_save_blocked_reason": "cloud_save_unconfirmed",
        }
        record_save_transaction(ss, cloud_confirmed=False, revision_advanced=False)
        bundle = build_save_transaction_debug_bundle(ss)
        summary = bundle["summary"]
        self.assertEqual(summary["raw_save_reason"], "song_edit")
        self.assertEqual(summary["strict_egress_plan_action"], "duplicate_skip")
        self.assertTrue(summary["duplicate_write_skipped"])
        self.assertFalse(summary["revision_advanced"])
        self.assertFalse(summary["cloud_confirmed"])
        self.assertFalse(summary["suite_persist_last_save_cloud"])

    def test_history_keeps_snapshots_for_same_run(self) -> None:
        ss: dict = {}
        st = MagicMock()
        st.runtime.scriptrunner.get_script_run_ctx.return_value = MagicMock(script_run_id="run-a")
        ensure_streamlit_run_sequence(ss, st)
        append_workspace_save_transaction_snapshot(ss, st=st, event="first")
        append_workspace_save_transaction_snapshot(ss, st=st, event="second")
        self.assertEqual(len(ss.get("_music_workspace_save_tx_rerun_history") or []), 2)
        self.assertEqual(ss.get("_music_workspace_save_tx_global_seq"), 2)


if __name__ == "__main__":
    unittest.main()
