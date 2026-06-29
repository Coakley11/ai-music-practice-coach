"""suite_resume_items idempotent upsert tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from suite_storage_supabase import upsert_resume_item


class TestSuiteResumeUpsert(unittest.TestCase):
    def test_first_write_uses_post_with_on_conflict(self) -> None:
        calls: list[tuple] = []

        def _fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {}

        with patch("suite_storage_supabase._scoped_storage_app", return_value="music:daniel"):
            with patch("suite_storage_supabase._scoped_user_id", return_value="user-1"):
                with patch("suite_storage_supabase.normalize_app_key", return_value="music"):
                    with patch("suite_storage_supabase._request", side_effect=_fake_request):
                        result = upsert_resume_item(
                            "music",
                            "ai:practice_log_analysis:abc123",
                            title="Music Practice Log Analysis",
                            subtitle="Practice history",
                            action_url="https://example.com/resume",
                        )
        self.assertEqual(result.get("write_mode"), "upsert")
        self.assertFalse(result.get("duplicate_handled"))
        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][2].get("params"), {"on_conflict": "user_id,app,item_key"})

    def test_duplicate_409_falls_back_to_patch_update(self) -> None:
        calls: list[tuple] = []

        def _fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            if method == "POST":
                raise RuntimeError(
                    "Supabase POST suite_resume_items failed (409): duplicate key "
                    "(user_id, app, item_key)=(user-1, music:daniel, ai:practice_log_analysis:abc123) already exists"
                )
            return {}

        with patch("suite_storage_supabase._scoped_storage_app", return_value="music:daniel"):
            with patch("suite_storage_supabase._scoped_user_id", return_value="user-1"):
                with patch("suite_storage_supabase.normalize_app_key", return_value="music"):
                    with patch("suite_storage_supabase._request", side_effect=_fake_request):
                        result = upsert_resume_item(
                            "music",
                            "ai:practice_log_analysis:abc123",
                            title="Music Practice Log Analysis",
                            subtitle="Updated subtitle",
                            action_url="https://example.com/resume?v=2",
                        )
        self.assertEqual(result.get("write_mode"), "update")
        self.assertTrue(result.get("duplicate_handled"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], "PATCH")
        patch_body = calls[1][2].get("json_body") or {}
        self.assertEqual(patch_body.get("title"), "Music Practice Log Analysis")
        self.assertEqual(patch_body.get("subtitle"), "Updated subtitle")
        self.assertEqual(patch_body.get("action_url"), "https://example.com/resume?v=2")
        self.assertTrue(patch_body.get("valid"))


if __name__ == "__main__":
    unittest.main()
