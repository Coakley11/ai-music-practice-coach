"""v16 regression tests — backing play, restore gate, practice log cloud, catalog lock."""

from __future__ import annotations

import unittest

from active_song_state import apply_cloud_active_song_state_if_allowed
from backing_track_state import prepare_backing_transport_for_session
from practice_log_persistence import _merge_logs, load_practice_logs, save_practice_logs
from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, get_song_context


class TestV16BackingPlayRequest(unittest.TestCase):
    def test_play_request_survives_prepare_transport(self) -> None:
        ss = {
            "_backing_play_request": True,
            "_backing_transport_user_stopped": True,
            "_backing_autoplay": False,
            "backing_transport_status": "stopped",
        }
        prepare_backing_transport_for_session(ss)
        self.assertTrue(ss["_backing_autoplay"])
        self.assertEqual(ss["backing_transport_status"], "playing")
        self.assertNotIn("_backing_transport_user_stopped", ss)
        self.assertNotIn("_backing_play_request", ss)

    def test_plain_reload_stays_stopped(self) -> None:
        ss = {
            "backing_track_state": {"backing_transport_status": "playing", "backing_autoplay": True},
            "_last_backing_wav": b"RIFF",
            "backing_transport_status": "ready",
        }
        prepare_backing_transport_for_session(ss)
        self.assertFalse(ss["_backing_autoplay"])
        self.assertEqual(ss["backing_transport_status"], "ready")


class TestV16RestoreGates(unittest.TestCase):
    def test_cloud_custom_skipped_when_user_chose_catalog(self) -> None:
        ss = {USER_CATALOG_SOURCE_CHOICE_KEY: True}
        applied = apply_cloud_active_song_state_if_allowed(
            ss,
            {"active_song_state": {"music_source": "custom", "pick_key": "custom::x"}},
        )
        self.assertFalse(applied)
        self.assertEqual(ss.get("_active_song_restore_skipped_reason"), "user_chose_catalog")

    def test_get_song_context_defers_default_during_restore(self) -> None:
        class _St:
            session_state = {
                ACTIVE_CATALOG_PICK_KEY: "pk::Pop::Trial — Artist",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": "pk::Pop::Trial — Artist",
                    "title": "Trial",
                    "artist": "Artist",
                    "genre": "Pop",
                    "key": "D",
                },
                "_cloud_workspace_restored_this_run": True,
            }

        st = _St()
        catalog = {"Pop": {"Stay — Kid LAROI": {}}}
        library = {"Pop": {"Stay — Kid LAROI": {"title": "Stay", "key": "G"}}}
        genre, title, _data = get_song_context(
            st,
            song_picker_catalog=catalog,
            song_library=library,
        )
        self.assertEqual(title, "Trial")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), "pk::Pop::Trial — Artist")


class TestV16PracticeLogPersistence(unittest.TestCase):
    def test_merge_logs_dedupes(self) -> None:
        entry = {"date": "2026-06-19", "song": "Autumn Leaves", "minutes": 30}
        merged = _merge_logs([entry], [dict(entry)])
        self.assertEqual(len(merged), 1)

    def test_load_practice_logs_local_only(self) -> None:
        logs = load_practice_logs()
        self.assertIsInstance(logs, list)


if __name__ == "__main__":
    unittest.main()
