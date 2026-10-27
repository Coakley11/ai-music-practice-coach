"""Next Song must survive a mid-session workspace re-apply.

On Cloud, another device's save (the phone on the same account) is re-applied
mid-session. Its blob carried that device's set position, so the run after
Next restored Now Singing to the first entry before the page rendered: the
card, chart and audio stayed on the first song. Reproduced in the browser
with a stale cloud blob published as Next was pressed. The set position is
per-device playback state now; the setlist itself still syncs.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import karaoke_mode as km
from music_persistent_state import (
    KARAOKE_DEVICE_POSITION_KEYS,
    _device_view_keys,
    apply_music_disk_state,
)

_TITLES = ("Shallow", "Autumn Leaves", "Blues in F minor")


def _session() -> dict:
    ss: dict = {"instrument": "Voice"}
    for i, title in enumerate(_TITLES):
        km.add_to_queue(ss, f"Pop\x1f{title}", title=title, artist="A", practice_key="C", bpm=100 + i)
    km.start_session(ss)
    return ss


def _other_device_blob(ss: dict) -> dict:
    """What a device that is still on the first entry saved."""
    return {key: ss.get(key) for key in KARAOKE_DEVICE_POSITION_KEYS} | {
        "karaoke_queue": km.get_queue(ss),
    }


def _apply(ss: dict, blob: dict) -> dict:
    st = MagicMock()
    st.session_state = ss
    apply_music_disk_state(st, {"session": blob}, song_picker_catalog={}, song_library={})
    return st.session_state


class KaraokePositionDeviceStateTests(unittest.TestCase):
    def test_position_keys_are_device_state(self) -> None:
        keys = _device_view_keys()
        for key in KARAOKE_DEVICE_POSITION_KEYS:
            self.assertIn(key, keys)
        self.assertNotIn("karaoke_queue", keys)

    def test_next_survives_a_mid_session_reapply(self) -> None:
        ss = _session()
        stale = _other_device_blob(ss)
        km.advance_session(ss, skip_repeats=True)
        ss["_suite_already_synced_before_restore"] = True
        _apply(ss, stale)
        self.assertEqual(ss.get("karaoke_session_index"), 1)
        self.assertEqual((km.current_session_entry(ss) or {}).get("title"), "Autumn Leaves")

    def test_page_load_still_restores_the_saved_position(self) -> None:
        saved = _session()
        km.advance_session(saved, skip_repeats=True)
        km.advance_session(saved, skip_repeats=True)
        blob = _other_device_blob(saved)
        fresh = _apply({"instrument": "Voice"}, blob)
        self.assertEqual(fresh.get("karaoke_session_index"), 2)
        self.assertEqual((km.current_session_entry(fresh) or {}).get("title"), "Blues in F minor")

    def test_mid_session_reapply_still_syncs_the_setlist(self) -> None:
        ss = _session()
        km.advance_session(ss, skip_repeats=True)
        blob = _other_device_blob(ss)
        blob["karaoke_queue"] = blob["karaoke_queue"] + [
            dict(blob["karaoke_queue"][0], entry_id="added-elsewhere", title="Shape of You")
        ]
        ss["_suite_already_synced_before_restore"] = True
        _apply(ss, blob)
        self.assertEqual([e["title"] for e in km.get_queue(ss)], list(_TITLES) + ["Shape of You"])
        self.assertEqual(ss.get("karaoke_session_index"), 1)


if __name__ == "__main__":
    unittest.main()
