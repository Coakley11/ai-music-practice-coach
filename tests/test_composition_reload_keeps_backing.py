"""Android retest 2026-11-24: a reload while a Composition song is the active song replaced the Backing Feel.

Reproduced in the real app (disposable data dir, Composition song "Jazz tune" active, a Style Jam Bossa Nova in D at
112 BPM open in Backing) and traced write by write: on a reload the saved active song is restored through the same
path as choosing it (activate_composition_by_pick_key -> commit_composition_active_song ->
on_active_song_identity_changed(force_reset=True)). That reset Backing to the song's defaults and queued its tempo and
groove (request_backing_bpm / request_backing_groove, from reset_backing_on_active_song_change and
prepare_composition_backing_handoff). The saved Backing session was restored next, but the Backing page then
flushed the queued groove over it: the jam's card read "Jazz swing" instead of "Bossa nova".

A reload re-establishes the same song: its identity and Practice Key are applied as before, Backing is not reset.
Choosing the song, or a restore that changes the song, still sets Backing up for it.
"""

from __future__ import annotations

import unittest
from unittest import mock

from tests import test_owner_key_identity_contract as T

PENDING = ("_pending_backing_groove", "_pending_backing_track_bpm")


def _jazz_tune(ss: dict) -> str:
    from composition_session_state import save_document_to_library
    from composition_songs_bridge import composition_pick_key_for

    doc = T._composition_in_key("D", title="Jazz tune", song_id="jazz-tune")
    doc["global"]["groove_style"] = "Jazz swing"
    doc["global"]["bpm"] = 120
    save_document_to_library(ss, doc)
    return composition_pick_key_for(doc)


def _activate(ss: dict, pick: str, *, restore: bool) -> None:
    from composition_songs_bridge import activate_composition_by_pick_key

    with mock.patch("songs.state.persist_music_local_state"):
        assert activate_composition_by_pick_key(T._st(ss), pick, restore=restore)


class CompositionReloadKeepsBackingTests(unittest.TestCase):
    def test_a_reload_queues_none_of_the_songs_backing_defaults(self) -> None:
        ss = {"instrument": "Piano", "studio_page": "backing"}
        _activate(ss, _jazz_tune(ss), restore=True)
        for key in (*PENDING, "backing_groove_style"):
            self.assertIsNone(ss.get(key), key)

    def test_a_reload_still_makes_it_the_active_song_with_its_practice_key(self) -> None:
        ss = {"instrument": "Piano", "studio_page": "backing"}
        pick = _jazz_tune(ss)
        _activate(ss, pick, restore=True)
        self.assertEqual(ss.get("active_catalog_pick_key"), pick)
        self.assertEqual((ss.get("display_key"), ss.get("concert_key")), ("D", "D"))
        from backing_context import get_backing_context

        self.assertEqual(get_backing_context(ss).source, "composition_song")

    def test_a_reload_keeps_a_saved_practice_key(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        ss = {"instrument": "Piano", "studio_page": "backing"}
        pick = _jazz_tune(ss)
        set_practice_concert_key(ss, "E", pick_key=pick)
        _activate(ss, pick, restore=True)
        self.assertEqual(ss.get("concert_key"), "E")

    def test_choosing_the_song_still_sets_backing_up_for_it(self) -> None:
        ss = {"instrument": "Piano", "studio_page": "backing"}
        _activate(ss, _jazz_tune(ss), restore=False)
        self.assertEqual(ss.get("_pending_backing_track_bpm"), 120)
        self.assertTrue(ss.get("_pending_backing_groove"))

    def test_a_restore_that_changes_the_song_still_resets_backing(self) -> None:
        ss = {"instrument": "Piano", "studio_page": "backing", "active_catalog_pick_key": "composition::other-song"}
        _activate(ss, _jazz_tune(ss), restore=True)
        self.assertEqual(ss.get("_pending_backing_track_bpm"), 120)


if __name__ == "__main__":
    unittest.main()
