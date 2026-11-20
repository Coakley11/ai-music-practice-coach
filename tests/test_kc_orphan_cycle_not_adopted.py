"""A saved Key Cycling cycle without its song is never adopted by the active song (user report 2026-11-20).

Cloud Dev: Let It Be (C), Shallow (G) and a Karaoke Blackbird (E) all came up in D. A cycle saved before
cycles recorded their song (no ``song_id``) was adopted, with its old key, by whatever song was active
after a refresh. It now starts again at the active song's own first key: still On, stopped, the
musician's Interval / Direction / Key Spelling kept. The saved Practice Key is never written.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
from backing_transport_intent import PLAYING, transport_intent


class OrphanCycle(unittest.TestCase):
    def setUp(self) -> None:
        self.song = "cat::Let It Be"
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch.object(kc, "_active_song_cycle_identity", side_effect=lambda _s: self.song),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _saved_cycle(self, key: str = "D", *, song_id: str | None = None, interval: int = 5,
                     direction: str = "down", enabled: bool = True) -> dict:
        """A session restored from disk with a cycle started elsewhere in ``key``."""
        s = {"display_key": key, "concert_key": key, "studio_page": "backing", "instrument": "Guitar",
             "backing_source_kind": "catalog"}
        kc.start_key_cycle(s, start_key=key, interval=interval, direction=direction)
        owner = kc.resolve_cycle_owner(s)
        bag = dict(kc.get_owner_cycle_session(s, owner))
        bag.pop(kc.CYCLE_SONG_ID, None)
        if song_id:
            bag[kc.CYCLE_SONG_ID] = song_id
        bag["enabled"] = enabled
        self.owner = owner
        return {"_backing_key_cycle_sessions": {owner: bag}, "backing_key_cycle_enabled": enabled,
                "backing_source_kind": "catalog", "studio_page": "backing", "instrument": "Guitar",
                "display_key": "C", "concert_key": "C", "practice_key_by_source": {"Pop\x1fLet It Be": "C"}}

    def test_a_cycle_without_its_song_is_not_adopted_with_its_old_key(self) -> None:
        s = self._saved_cycle("D")
        self.assertEqual(kc.temporary_playback_key(s), "D")  # what the page used to play
        self.assertTrue(kc.ensure_key_cycle_follows_active_song(s))
        self.assertTrue(kc.is_cycle_active(s))
        self.assertEqual(kc.temporary_playback_key(s), "C")  # the active song's own first key
        data = kc.get_owner_cycle_session(s)
        self.assertEqual(data.get(kc.CYCLE_SONG_ID), "cat::Let It Be")
        self.assertEqual((data.get("interval"), data.get("direction")), (5, "down"))  # settings kept
        self.assertNotEqual(transport_intent(s), PLAYING)  # nothing autoplays

    def test_after_a_refresh_it_still_starts_at_the_songs_own_key(self) -> None:
        s = self._saved_cycle("D")
        kc.ensure_key_cycle_follows_active_song(s)
        kc.normalize_key_cycle_after_browser_restore(s)
        self.assertEqual(kc.temporary_playback_key(s), "C")

    def test_the_saved_practice_key_and_the_sidebar_key_are_not_written(self) -> None:
        s = self._saved_cycle("D")
        kc.ensure_key_cycle_follows_active_song(s)
        self.assertEqual(s["practice_key_by_source"], {"Pop\x1fLet It Be": "C"})
        self.assertEqual((s["display_key"], s["concert_key"]), ("C", "C"))

    def test_key_cycling_off_is_left_alone(self) -> None:
        s = self._saved_cycle("D", enabled=False)
        s["backing_key_cycle_enabled"] = False
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(s))
        self.assertFalse(kc.is_cycle_active(s))

    def test_a_cycle_of_this_same_song_keeps_its_position(self) -> None:
        s = self._saved_cycle("D", song_id="cat::Let It Be")
        s["_kc_settings_activation_epoch"] = 0
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(s))
        self.assertEqual(kc.temporary_playback_key(s), "D")  # its own position, as before

    def test_a_cycle_of_another_song_still_starts_again(self) -> None:
        s = self._saved_cycle("D", song_id="cat::Something Else")
        s["_kc_settings_activation_epoch"] = 0
        self.assertTrue(kc.ensure_key_cycle_follows_active_song(s))
        self.assertEqual(kc.temporary_playback_key(s), "C")


if __name__ == "__main__":
    unittest.main()
