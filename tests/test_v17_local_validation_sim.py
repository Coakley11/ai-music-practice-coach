"""v17/v18 lifecycle fixes — deferred song context, backing stop, display key owner, sync id."""

from __future__ import annotations

import unittest

from active_song_state import _push_resolved_display_key_to_session
from backing_track_state import bind_backing_rendered_widgets_from_canonical
from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
from songs.playback_defaults import resolve_active_bpm_sync_id


class TestV18BpmSyncIdResolution(unittest.TestCase):
    def test_resolve_from_pick_key_when_globals_missing(self) -> None:
        ss = {
            "active_catalog_pick_key": "Pop::Trial — Artist",
            "selected_song": {"pick_key": "Pop::Trial — Artist"},
        }
        sync_id = resolve_active_bpm_sync_id(
            ss,
            song_title="Trial",
            song_artist="Artist",
            pick_key="Pop::Trial — Artist",
        )
        self.assertEqual(sync_id, "pk::Pop::Trial — Artist")
        self.assertEqual(ss.get("_active_bpm_sync_id"), sync_id)


class TestV17BackingStopGuard(unittest.TestCase):
    def test_bind_skips_when_user_stopped(self) -> None:
        ss = {
            "_backing_transport_user_stopped": True,
            "backing_track_state": {"backing_track_bpm": 108},
            "backing_track_bpm": 120,
        }
        bind_backing_rendered_widgets_from_canonical(ss, sync_id="pk::test", default_bpm=100)
        self.assertEqual(ss.get("backing_track_bpm"), 120)


class TestV17DisplayKeyOwnerSync(unittest.TestCase):
    def test_canonical_push_restores_owner_identity(self) -> None:
        ss = {
            "display_key": "D",
            "active_catalog_pick_key": "pk::Pop::Trial — Artist",
            "selected_song": {
                "pick_key": "pk::Pop::Trial — Artist",
                "title": "Trial",
                "artist": "Artist",
                "key": "D",
            },
        }
        ctx = {
            "pick_key": "pk::Pop::Trial — Artist",
            "display_key": "Eb",
            "display_key_owner_identity": "",
            "selected_song": ss["selected_song"],
            "music_source": "catalog",
        }
        _push_resolved_display_key_to_session(ss, ctx)
        self.assertEqual(ss.get("display_key"), "Eb")
        self.assertTrue(str(ss.get(DISPLAY_KEY_OWNER_IDENTITY_KEY) or "").strip())


if __name__ == "__main__":
    unittest.main()
