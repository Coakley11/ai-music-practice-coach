"""Tests for MUSIC_EGRESS_STRICT policy."""

import os
import unittest
from unittest.mock import patch

from music_egress_config import (
    MUSIC_EGRESS_STRICT_KEY,
    get_music_egress_policy,
    music_cloud_write_allowed,
    music_egress_strict_enabled,
    sanitize_studio_page_snapshots_for_persist,
    saved_items_list_limit,
    should_merge_custom_songs_from_cloud,
    skip_cloud_readback_after_write,
)


class TestMusicEgressConfig(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_strict_off_by_default(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)
        self.assertFalse(music_egress_strict_enabled())
        self.assertTrue(music_cloud_write_allowed(save_reason="autosave"))

    def test_strict_env_enables_policy(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        self.assertTrue(music_egress_strict_enabled())
        policy = get_music_egress_policy()
        self.assertTrue(policy.strict)
        self.assertTrue(policy.skip_cloud_readback_after_save)
        self.assertFalse(music_cloud_write_allowed(save_reason="autosave"))
        self.assertTrue(music_cloud_write_allowed(save_reason="page_change"))
        self.assertFalse(music_cloud_write_allowed(save_reason="passive_rerun"))

    def test_saved_items_limit_reduced(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        self.assertEqual(saved_items_list_limit(default=200), 25)
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)
        self.assertEqual(saved_items_list_limit(default=200), 200)

    def test_lazy_custom_song_merge(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss: dict = {}
        self.assertFalse(should_merge_custom_songs_from_cloud(ss, force=False))
        self.assertTrue(should_merge_custom_songs_from_cloud(ss, force=True))

    def test_skip_readback_music_only(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        self.assertTrue(skip_cloud_readback_after_write("music"))
        self.assertFalse(skip_cloud_readback_after_write("baseball"))

    def test_sanitize_strips_ephemeral_keys(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        raw = {
            "composer": {
                "composer_active_section_id": "x",
                "composer_preview_wav": b"wav-bytes",
            }
        }
        cleaned = sanitize_studio_page_snapshots_for_persist(raw)
        self.assertIn("composer_active_section_id", cleaned["composer"])
        self.assertNotIn("composer_preview_wav", cleaned["composer"])

    @patch.dict(os.environ, {MUSIC_EGRESS_STRICT_KEY: "true"}, clear=False)
    def test_truthy_variants(self) -> None:
        self.assertTrue(music_egress_strict_enabled())


if __name__ == "__main__":
    unittest.main()
