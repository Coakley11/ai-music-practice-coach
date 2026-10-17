"""A mid-session workspace re-apply must not undo per-device view state.

With the phone open on the same account, each phone save made the desktop
re-apply the phone's snapshot: Key cycling snapped Off, a closed song editor
reopened and the lead sheet closed. A page load (first sync) still restores
the saved view state, so refresh keeps working.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import _device_view_keys, apply_music_disk_state

_LOCAL = {
    "backing_key_cycle_enabled_ui": "On",
    "backing_key_cycle_enabled": True,
    "picker_song_editor_open": False,
    "chart_edit_mode": False,
    "backing_lead_sheet_open": True,
}
_OTHER_DEVICE = {
    "backing_key_cycle_enabled_ui": "Off",
    "backing_key_cycle_enabled": False,
    "picker_song_editor_open": True,
    "chart_edit_mode": True,
    "backing_lead_sheet_open": False,
}


def _apply(session: dict) -> dict:
    st = MagicMock()
    st.session_state = session
    apply_music_disk_state(st, {"session": dict(_OTHER_DEVICE)}, song_picker_catalog={}, song_library={})
    return st.session_state


class DeviceViewStateReapplyTests(unittest.TestCase):
    def test_view_keys_cover_key_cycling_editor_and_lead_sheet(self) -> None:
        keys = _device_view_keys()
        for key in _LOCAL:
            self.assertIn(key, keys)
        self.assertIn("_backing_key_cycle_sessions", keys)

    def test_mid_session_reapply_keeps_this_devices_view_state(self) -> None:
        ss = _apply({**_LOCAL, "_suite_already_synced_before_restore": True})
        for key, value in _LOCAL.items():
            self.assertEqual(ss.get(key), value, key)

    def test_first_sync_restores_the_saved_view_state(self) -> None:
        ss = _apply(dict(_LOCAL))
        # chart_edit_mode has its own restore rules elsewhere; the rest restore as saved.
        for key in ("backing_key_cycle_enabled_ui", "backing_key_cycle_enabled", "picker_song_editor_open", "backing_lead_sheet_open"):
            self.assertEqual(ss.get(key), _OTHER_DEVICE[key], key)

    def test_mid_session_reapply_still_applies_musical_content(self) -> None:
        st = MagicMock()
        st.session_state = {"_suite_already_synced_before_restore": True, "backing_track_loops": 2}
        apply_music_disk_state(
            st, {"session": {"backing_track_loops": 4}}, song_picker_catalog={}, song_library={}
        )
        self.assertEqual(st.session_state.get("backing_track_loops"), 4)


if __name__ == "__main__":
    unittest.main()
