"""Tests for music-reboot-restore-v10 snapshot guards + reboot + multitrack cloud."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from songs.picker_session import WORKSPACE_GENRE_FILTERS_KEY, toggle_genre_filter
from studio_page_persistence import apply_page_snapshot, capture_page_snapshot


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeSt:
    def __init__(self, session_state: dict | None = None) -> None:
        self.session_state = session_state if session_state is not None else _FakeSessionState()


class TestGenreSnapshotTouchGuard(unittest.TestCase):
    def test_user_touched_genre_filters_not_clobbered_by_snapshot(self) -> None:
        ss = {
            WORKSPACE_GENRE_FILTERS_KEY: ["Pop", "Rock"],
            "_genre_filters_user_touched": True,
        }
        snap = capture_page_snapshot({WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"]}, "picker")
        apply_page_snapshot(ss, snap)
        self.assertEqual(ss[WORKSPACE_GENRE_FILTERS_KEY], ["Pop", "Rock"])

    def test_toggle_updates_picker_snapshot(self) -> None:
        ss = {WORKSPACE_GENRE_FILTERS_KEY: [], "_studio_page_snapshots": {}}
        toggle_genre_filter(ss, "Jazz")
        self.assertEqual(ss[WORKSPACE_GENRE_FILTERS_KEY], ["Jazz"])
        picker_snap = (ss.get("_studio_page_snapshots") or {}).get("picker") or {}
        self.assertEqual(picker_snap.get(WORKSPACE_GENRE_FILTERS_KEY), ["Jazz"])


class TestCreativeModeTouchGuard(unittest.TestCase):
    def test_user_touched_improv_tab_not_clobbered(self) -> None:
        ss = {
            "improv_intelligence_tab": "Live Coach",
            "_improv_tab_user_touched": True,
        }
        snap = capture_page_snapshot({"improv_intelligence_tab": "Deep Harmony"}, "creative")
        apply_page_snapshot(ss, snap)
        self.assertEqual(ss["improv_intelligence_tab"], "Live Coach")


class TestEphemeralPickKeyStrip(unittest.TestCase):
    def test_ephemeral_default_omits_pick_key_from_disk_state(self) -> None:
        from music_persistent_state import build_music_disk_state

        ss = _FakeSessionState(
            {
                "studio_page": "practice",
                "_music_default_song_ephemeral": True,
                "active_catalog_pick_key": "Pop::Say — John Mayer",
            }
        )
        st = _FakeSt(ss)
        state = build_music_disk_state(st)
        core = state.get("core") or {}
        self.assertFalse(str(core.get("pick_key") or "").strip())


class TestMultitrackCloudSaveGate(unittest.TestCase):
    def test_multitrack_force_save_fails_without_cloud(self) -> None:
        from music_persistent_state import force_save_music_state

        st = MagicMock()
        st.session_state = {}
        with patch("music_persistent_state.force_autosave", return_value=True):
            ok = force_save_music_state(st, reason="multitrack_upload")
        self.assertFalse(ok)
        self.assertEqual(st.session_state.get("_music_force_save_blocked_reason"), "multitrack_cloud_save_failed")


class TestCustomRestoreFinalize(unittest.TestCase):
    def test_cloud_payload_custom_active_skip_reason(self) -> None:
        from music_persistent_state import music_skip_master_song_init_reason

        ss = {}
        payload = {
            "core": {"pick_key": "Pop::Say — John Mayer"},
            "session": {
                "active_music_source": "custom_progression",
                "cpl_active_progression": {"id": "trial-1", "name": "Trial Song"},
            },
        }
        ss["_suite_last_cloud_fetch_payload"] = payload
        reason = music_skip_master_song_init_reason(ss)
        self.assertEqual(reason, "cloud_payload_custom_active")


if __name__ == "__main__":
    unittest.main()
