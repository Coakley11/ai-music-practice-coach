"""Durability transaction retention across reruns + hydration (diagnostics only)."""

from __future__ import annotations

import unittest
from typing import Any

from music_page_cloud_durability_trace import (
    PAGE_CLOUD_DURABILITY_TRACE_KEY,
    begin_navigation_page_change_transaction,
    classify_failure,
    durability_journal_payload,
    record_fresh_hydration,
    record_force_save_durability_entry,
)
from music_phase1_write_journal import record_phase1_page_write


class _FakeSessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _backing_payload(rev: int = 191) -> dict[str, Any]:
    return {
        "core": {"studio_page": "backing", "page": "backing"},
        "session": {"studio_page": "backing"},
        "music_workspace_state": {"studio_page": "backing", "workspace_revision": rev},
        "workspace_revision": rev,
    }


class PageCloudDurabilityTransactionRerunTests(unittest.TestCase):
    def test_three_run_nav_save_hydration_retains_transaction(self) -> None:
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_script_run_seq": 1,
                "studio_page": "backing",
                "startup_revision_loaded": 191,
            }
        )
        record_fresh_hydration(ss, _backing_payload(), fetch_source="run1_hydrate", used_cache=False)
        self.assertEqual(len(ss[PAGE_CLOUD_DURABILITY_TRACE_KEY]["transactions"]), 0)

        ss["_script_run_seq"] = 2
        tx_id = begin_navigation_page_change_transaction(
            ss, clicked_page="creative", prior_page="backing", origin="user_navigation"
        )
        self.assertTrue(tx_id)
        record_force_save_durability_entry(ss, reason="page_change", stage="entry")
        txs = ss[PAGE_CLOUD_DURABILITY_TRACE_KEY]["transactions"]
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].get("clicked_page"), "creative")
        self.assertEqual(txs[0].get("status"), "save_entered")
        self.assertTrue(txs[0].get("force_save_events"))

        ss["_script_run_seq"] = 3
        record_fresh_hydration(ss, _backing_payload(), fetch_source="run3_hydrate", used_cache=True)
        txs_after = ss[PAGE_CLOUD_DURABILITY_TRACE_KEY]["transactions"]
        self.assertGreaterEqual(len(txs_after), 1)
        self.assertEqual(txs_after[0].get("transaction_id"), tx_id)
        hydrate = ss[PAGE_CLOUD_DURABILITY_TRACE_KEY].get("fresh_hydration")
        self.assertIsInstance(hydrate, dict)
        self.assertEqual(hydrate.get("fetch_source"), "run3_hydrate")

        payload = durability_journal_payload(ss)
        self.assertEqual(payload.get("status"), "ok")
        self.assertGreaterEqual(payload.get("diagnostic_integrity", {}).get("transaction_count"), 1)

    def test_missing_tx_classifies_diagnostic_not_cache(self) -> None:
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_script_run_seq": 5,
                "studio_page": "creative",
                "_music_user_navigated_page_this_run": "creative",
            }
        )
        record_phase1_page_write(
            ss,
            key="studio_page",
            old_page="backing",
            new_page="creative",
            module="test",
            function="test",
            reason="user_navigation",
            origin="user_navigation",
        )
        record_fresh_hydration(ss, _backing_payload(), fetch_source="hydrate", used_cache=True)
        failure = classify_failure(ss)
        self.assertEqual(failure, "diagnostic_transaction_missing")

    def test_integrity_violation_when_phase1_nav_without_tx(self) -> None:
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_music_user_navigated_page_this_run": "creative",
            }
        )
        record_phase1_page_write(
            ss,
            key="studio_page",
            old_page="backing",
            new_page="creative",
            origin="user_navigation",
            reason="user_navigation",
            module="t",
            function="t",
        )
        from music_page_cloud_durability_trace import evaluate_durability_transaction_integrity

        integrity = evaluate_durability_transaction_integrity(ss)
        self.assertTrue(integrity.get("transaction_lost_across_rerun"))
        viols = ss[PAGE_CLOUD_DURABILITY_TRACE_KEY].get("violations") or []
        self.assertTrue(any(v.get("code") == "PAGE_CLOUD_DURABILITY_TRANSACTION_LOST" for v in viols))


if __name__ == "__main__":
    unittest.main()
