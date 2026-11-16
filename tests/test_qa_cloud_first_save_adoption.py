"""QA cloud pass: a brand-new account's first workspace save must not be refused forever.

Lightweight page/state saves (login, navigation) create the account's ``music`` state row BEFORE any
workspace exists. The first workspace save used to see "row exists, expected revision 0" and was
refused as a conflict on every attempt. A metadata-only row (no saved workspace, no revision) may now
be adopted; a row that already carries a workspace is still refused.
"""
from __future__ import annotations

import unittest
from unittest import mock

import suite_storage_supabase as s


class TestMetadataOnlyRow(unittest.TestCase):
    def test_classification(self) -> None:
        self.assertTrue(s.metrics_is_metadata_only({"song": "Say", "focus": "x"}))
        self.assertFalse(s.metrics_is_metadata_only({}))
        self.assertFalse(s.metrics_is_metadata_only({"song": "x", "full_session": {"a": 1}}))
        self.assertFalse(s.metrics_is_metadata_only({"song": "x", "workspace_revision": 3}))


class TestFirstWorkspaceSaveAdoptsMetadataRow(unittest.TestCase):
    def _run(self, existing: dict, patch_rows: list):
        calls: list = []

        def fake_request(method, table, **kw):
            calls.append((method, table, kw))
            return patch_rows

        with mock.patch.object(s, "_request", fake_request), \
             mock.patch.object(s, "_load_state_row_metrics", return_value=existing), \
             mock.patch.object(s, "_cloud_user_id", return_value="u-1"), \
             mock.patch.object(s, "_scoped_storage_app", return_value="music"):
            r = s.save_current_state_conditional_cas(
                "music", page="home", summary="x", metrics={"full_session": {"w": 1}},
                expected_workspace_revision=0, candidate_workspace_revision=1)
        return r, calls

    def test_adopts_metadata_only_row_with_a_guarded_patch(self) -> None:
        r, calls = self._run({"song": "Say", "genre": "Pop"}, [{"app": "music"}])
        self.assertTrue(r["accepted"])
        self.assertEqual(r["write_mode"], "adopt_metadata_row")
        method, _table, kw = calls[-1]
        self.assertEqual(method, "PATCH")
        self.assertEqual(kw["params"]["app"], "eq.music")
        self.assertEqual(kw["params"]["user_id"], "eq.u-1")
        self.assertEqual(kw["params"]["metrics->full_session"], "is.null")  # only while still workspace-less
        # existing metadata is preserved, workspace added
        self.assertEqual(kw["json_body"]["metrics"]["song"], "Say")
        self.assertIn("full_session", kw["json_body"]["metrics"])

    def test_lost_race_is_a_conflict_not_an_overwrite(self) -> None:
        r, _ = self._run({"song": "Say"}, [])  # another session adopted first: 0 rows matched
        self.assertFalse(r["accepted"])
        self.assertEqual(r["write_mode"], "conflict")

    def test_row_that_already_has_a_workspace_is_still_refused(self) -> None:
        r, calls = self._run({"song": "Say", "full_session": {"x": 1}, "workspace_revision": 2}, [{"app": "music"}])
        self.assertFalse(r["accepted"])
        self.assertEqual(r["reason"], "row_exists_expected_zero")
        self.assertFalse(calls)  # nothing was written


if __name__ == "__main__":
    unittest.main()
