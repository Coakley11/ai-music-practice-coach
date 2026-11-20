"""Key Cycling across a Karaoke Set (user rule 2026-11-19).

* A fresh set starts with Key Cycling Off; whatever was on before the set is remembered.
* Turned On during the set it stays On -- Interval / Direction / Key Spelling -- for every later
  song (a song change inside the set is NOT the ordinary settings reset); Off also carries.
* End Set restores the pre-set state for ordinary Backing: On/Off and the settings, a restored On
  at the current song's first key and stopped. Safe without a snapshot.
* Outside a set the ordinary song-change reset is unchanged.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
from backing_transport_intent import STOPPED, begin_playback, transport_intent

FOURTHS = kc.CYCLE_STEP_FOURTH


class KaraokeSetLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        import active_song_transition as ast_mod

        self.ast = ast_mod
        self.song = "song-A"
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch.object(kc, "_active_song_cycle_identity", side_effect=lambda _s: self.song),
            mock.patch("songs.music_source.resolve_active_song_identity", side_effect=lambda _s: self.song),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "D", "concert_key": "D", "studio_page": "backing", "instrument": "Voice"}
        self._run()

    # helpers
    def _run(self) -> None:
        """One Backing script run: the activation stamp, then Backing's own song-follow check."""
        self.ast.note_active_song_activation(self.ss)
        kc.ensure_key_cycle_follows_active_song(self.ss)

    def _choose(self, step: str, direction: str, spelling: dict | None = None) -> None:
        self.ss[kc.BACKING_KEY_CYCLE_STEP_KEY] = step
        self.ss[kc.BACKING_KEY_CYCLE_DIRECTION_KEY] = direction
        if spelling:
            self.ss[kc.BACKING_KEY_SPELLING_PREFS_KEY] = dict(kc.default_spelling_prefs(), **spelling)

    def _settings(self) -> tuple:
        return (kc.normalize_cycle_step_name(self.ss.get(kc.BACKING_KEY_CYCLE_STEP_KEY)) or kc.CYCLE_STEP_SEMITONE,
                str(self.ss.get(kc.BACKING_KEY_CYCLE_DIRECTION_KEY) or "up"),
                kc.spelling_prefs_from_session(self.ss))

    def _turn_on(self, key: str = "D") -> None:
        self.ss["display_key"] = self.ss["concert_key"] = key
        begin_playback(self.ss, reason="test", command="p")
        kc.start_key_cycle(self.ss, start_key=key, interval=5, direction="down")

    def _start_set(self) -> None:
        kc.key_cycle_karaoke_set_started(self.ss)
        # A real setlist: an "active" set with an empty queue is closed by Karaoke's own reconcile.
        self.ss["karaoke_queue"] = [{"entry_id": "e1", "pick_key": "Pop|Song A"},
                                    {"entry_id": "e2", "pick_key": "Pop|Song B"}]
        self.ss["karaoke_session_index"] = 0
        self.ss["karaoke_session_active"] = True

    def _end_set(self) -> None:
        self.ss["karaoke_session_active"] = False
        kc.key_cycle_karaoke_set_ended(self.ss)

    def _next_entry(self, song: str, key: str) -> None:
        """The set moves to another entry: a real active-song change, then the entry restart."""
        self.song = song
        self.ss["display_key"] = self.ss["concert_key"] = key
        self._run()
        kc.restart_key_cycle_for_entry(self.ss, key)
        self._run()

    # 1. a fresh set starts Off
    def test_a_fresh_set_starts_with_key_cycling_off_even_if_it_was_on(self) -> None:
        self._choose(FOURTHS, "down")
        self._turn_on()
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertTrue(kc.key_cycle_karaoke_set_started(self.ss))
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertFalse(self.ss.get("backing_key_cycle_enabled"))
        self.assertTrue(self.ss[kc.KC_PRE_KARAOKE_SET_KEY]["enabled"])

    def test_a_fresh_set_with_key_cycling_already_off_stays_off(self) -> None:
        self._start_set()
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertTrue(self.ss.get("_key_cycle_force_ui_off"))
        self.assertFalse(self.ss[kc.KC_PRE_KARAOKE_SET_KEY]["enabled"])

    def test_the_snapshot_is_the_state_from_before_the_set_not_a_second_call(self) -> None:
        self._choose(FOURTHS, "down")
        self._turn_on()
        self._start_set()
        self.assertFalse(kc.key_cycle_karaoke_set_started(self.ss))  # e.g. Start pressed again
        self.assertTrue(self.ss[kc.KC_PRE_KARAOKE_SET_KEY]["enabled"])

    # 2. On during the set carries to later songs with its settings
    def test_turned_on_in_the_set_it_stays_on_with_its_settings_for_later_songs(self) -> None:
        self._start_set()
        self._choose(FOURTHS, "down", {"F#/Gb": "Gb"})
        self._turn_on("D")
        want = self._settings()
        self._next_entry("song-B", "F")
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertEqual(self._settings(), want)
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual((data.get("interval"), data.get("direction")), (5, "down"))
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")  # its own first key
        self._next_entry("song-A", "D")  # Previous back to the first song
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertEqual(self._settings(), want)

    def test_off_in_the_set_also_carries(self) -> None:
        self._start_set()
        self._choose(FOURTHS, "down")
        self._next_entry("song-B", "F")
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertIsNone(kc.restart_key_cycle_for_entry(self.ss, "F"))
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))

    def test_a_now_editing_row_tap_in_the_set_is_not_a_reset(self) -> None:
        self._start_set()
        self._choose(FOURTHS, "down")
        self._turn_on("D")
        self.song = "song-C"  # the active song changed without an entry restart yet
        self._run()
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))
        self.assertTrue(kc.is_cycle_active(self.ss))

    # 3. End Set
    def test_end_set_restores_the_pre_set_on_with_its_settings_at_the_first_key_stopped(self) -> None:
        self._choose(kc.CYCLE_STEP_SEMITONE, "up", {"F#/Gb": "F#"})
        self._turn_on("D")
        before = self._settings()
        self._start_set()
        self._choose(FOURTHS, "down")
        self._turn_on("D")
        self._next_entry("song-B", "F")
        self._end_set()
        self.assertEqual(self._settings(), before)
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")  # the song now active, first key
        self.assertEqual(transport_intent(self.ss), STOPPED)       # nothing autoplays
        self.assertNotIn(kc.KC_PRE_KARAOKE_SET_KEY, self.ss)
        self._run()                                                 # the next Backing run keeps it
        self.assertEqual(self._settings(), before)
        self.assertTrue(kc.is_cycle_active(self.ss))

    def test_end_set_restores_off_when_it_was_off_before(self) -> None:
        self._choose(FOURTHS, "down")
        self._start_set()
        self._turn_on("D")
        self._next_entry("song-B", "F")
        self._end_set()
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertFalse(self.ss.get("backing_key_cycle_enabled"))
        self._run()
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))

    def test_end_set_without_a_snapshot_is_safe_and_leaves_key_cycling_off(self) -> None:
        self._turn_on("D")
        self.assertFalse(kc.key_cycle_karaoke_set_ended(self.ss))
        self.assertFalse(kc.is_cycle_active(self.ss))

    def test_the_finished_markers_of_the_set_do_not_reach_ordinary_backing(self) -> None:
        self._start_set()
        self._turn_on("D")
        self.ss["_kc_cycle_finished_final"] = True
        self.ss["_kc_completion_consumed"] = "x"
        self._end_set()
        self.assertNotIn("_kc_cycle_finished_final", self.ss)
        self.assertNotIn("_kc_completion_consumed", self.ss)

    def test_the_snapshot_is_saved_with_the_cycle(self) -> None:
        import music_persistent_state as mps

        self.assertIn(kc.KC_PRE_KARAOKE_SET_KEY, kc.KEY_CYCLE_PERSIST_KEYS)
        self.assertIn(kc.KC_PRE_KARAOKE_SET_KEY, kc._CYCLE_DISK_SESSION_KEYS)
        self.assertIn(kc.KC_PRE_KARAOKE_SET_KEY, mps._PERSIST_KEYS)

    # 3b. leaving the Backing page during a set (e.g. back to the setlist) stops audio only
    def test_a_page_leave_in_a_set_keeps_key_cycling_on_with_its_settings(self) -> None:
        self._start_set()
        self._choose(FOURTHS, "down", {"F#/Gb": "Gb"})
        self._turn_on("D")
        want = self._settings()
        kc.end_key_cycle_on_page_leave(self.ss)
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertTrue(self.ss.get("backing_key_cycle_enabled"))
        self.assertNotEqual(self.ss.get("backing_key_cycle_enabled_ui"), "Off")
        self.assertTrue(kc.get_owner_cycle_session(self.ss))  # the cycle sessions are not wiped
        self.assertEqual(self._settings(), want)
        self.assertEqual(kc.temporary_playback_key(self.ss), "D")  # held at its first key
        self._run()  # back on Backing: the set's Key Cycling continues
        self.assertTrue(kc.is_cycle_active(self.ss))
        self.assertEqual(self._settings(), want)

    def test_a_page_leave_in_a_set_with_key_cycling_off_leaves_it_off(self) -> None:
        self._start_set()
        self._choose(FOURTHS, "down")
        kc.end_key_cycle_on_page_leave(self.ss)
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertEqual(self._settings()[:2], (FOURTHS, "down"))

    def test_a_page_leave_outside_a_set_still_turns_key_cycling_off(self) -> None:
        self._turn_on("D")
        kc.end_key_cycle_on_page_leave(self.ss)
        self.assertFalse(kc.is_cycle_active(self.ss))
        self.assertFalse(self.ss.get("backing_key_cycle_enabled"))

    # 4. outside a set nothing changes
    def test_outside_a_set_a_song_change_still_resets_to_defaults(self) -> None:
        self._choose(FOURTHS, "down")
        self._turn_on("D")
        self.song = "song-B"
        self._run()
        self.assertEqual(self._settings()[:2], (kc.CYCLE_STEP_SEMITONE, "up"))

    def test_a_set_flag_without_voice_is_not_a_karaoke_set(self) -> None:
        self.ss["instrument"] = "Guitar"
        self.ss["karaoke_session_active"] = True
        self.assertFalse(kc.key_cycle_in_karaoke_set(self.ss))
        self._choose(FOURTHS, "down")
        self.song = "song-B"
        self._run()
        self.assertEqual(self._settings()[:2], (kc.CYCLE_STEP_SEMITONE, "up"))


if __name__ == "__main__":
    unittest.main()
