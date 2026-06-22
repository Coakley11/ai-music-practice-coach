"""Tests for music-reboot-restore-v8 startup restore + display key + multitrack."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock


class TestMusicRebootRestoreV8(unittest.TestCase):
    def test_skip_when_workspace_blob_applied(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss = {"_music_workspace_blob_hydrated": True, "active_catalog_pick_key": "Pop::X — Y"}
        self.assertTrue(music_should_skip_master_song_init(ss))

    def test_ephemeral_default_does_not_skip_init(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss = {
            "active_catalog_pick_key": "Pop::Say — John Mayer",
            "_music_default_song_ephemeral": True,
        }
        self.assertFalse(music_should_skip_master_song_init(ss))

    def test_skip_reason_recorded_on_cold_start(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss: dict = {}
        self.assertFalse(music_should_skip_master_song_init(ss))
        self.assertEqual(ss.get("_music_skip_master_song_init_reason"), "cold_start")

    def test_payload_custom_signals_defer_catalog_pick(self) -> None:
        from music_persistent_state import _payload_has_custom_active_signals

        payload = {
            "core": {"pick_key": "Pop::Say — John Mayer"},
            "session": {
                "active_music_source": "custom_progression",
                "cpl_active_progression": {"id": "trial-1", "name": "Trial Song"},
            },
        }
        self.assertTrue(_payload_has_custom_active_signals(payload))

    def test_custom_pick_key_restore(self) -> None:
        from songs.state import (
            ACTIVE_CATALOG_PICK_KEY,
            SELECTED_SONG_STATE_KEY,
            apply_saved_custom_pick_key_context,
        )

        active = {
            "id": "trial-1",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Home": ["D", "G", "A"]},
        }
        st = MagicMock()
        st.session_state = {
            "cpl_active_progression": active,
            "cpl_saved_progressions": {"Trial Song": active},
        }
        ok = apply_saved_custom_pick_key_context(
            st,
            "custom::trial-1",
            {"display_key": "D"},
            song_picker_catalog={},
            song_library=None,
        )
        self.assertTrue(ok)
        self.assertEqual(st.session_state.get("active_music_source"), "custom_progression")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), "custom::trial-1")
        sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
        self.assertEqual(str(sel.get("pick_key") or ""), "custom::trial-1")

    def test_display_key_identity_uses_pick_key(self) -> None:
        from songs.key_state import IDENTITY_KEY, apply_display_key_for_active_song, song_display_identity

        st = MagicMock()
        st.session_state = {
            IDENTITY_KEY: song_display_identity("Marry You", "Bruno Mars", "F"),
            "display_key": "F",
        }
        identity = song_display_identity("Trial Song", "Custom progression", "D", pick_key="custom::trial-1")
        apply_display_key_for_active_song(st, "D", identity)
        self.assertEqual(st.session_state["display_key"], "D")

    def test_multitrack_snapshot_restore_from_workspace(self) -> None:
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace
        from studio_page_persistence import _encode_snapshot_value

        audio = b"guitar-layer-bytes"
        ss = {
            "_studio_page_snapshots": {
                "multitrack": {
                    "mt_tracks": {"Guitar": _encode_snapshot_value(audio), "Bass": None},
                }
            }
        }
        self.assertTrue(restore_multitrack_layers_from_workspace(ss))
        self.assertEqual(ss["mt_tracks"]["Guitar"], audio)

    def test_multitrack_size_cap_raised(self) -> None:
        from multitrack_session_persistence import MAX_MT_TRACK_BYTES

        self.assertGreaterEqual(MAX_MT_TRACK_BYTES, 2_000_000)

    def test_autosave_blocked_after_default_init(self) -> None:
        from music_persistent_state import autosave_music_state

        st = MagicMock()
        st.session_state = {"_music_default_init_this_run": True}
        result = autosave_music_state(st)
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("skip_reason"), "default_init_cooldown")


if __name__ == "__main__":
    unittest.main()
