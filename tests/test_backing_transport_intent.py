"""Explicit Backing transport: STOPPED / PLAYING / PAUSED decide what may sound.

A settings change, a finished background render or a leftover resume / restart
flag used to start a stopped or paused take. Stop used to be a hold that the
next setting change undid. Key cycling Previous / Next only accepted ±1 from
Python's own key, so a coalesced or wrapping move left Python on the old key.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
import karaoke_mode as km
from backing_key_cycle import (
    BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY,
    BACKING_KEY_CYCLE_SESSIONS_KEY,
    BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY,
    STATUS_HELD,
    STATUS_RUNNING,
    cycle_key_sequence,
    get_owner_cycle_session,
    jump_key_cycle_to_key,
    note_key_cycle_arrangement_settings_changed,
    rewind_key_cycle_to_first_key,
    start_key_cycle,
    temporary_playback_key,
)
from backing_track_state import page_player_autoplay, prepare_backing_transport_for_session
from backing_transport_intent import (
    PAUSED,
    PLAYING,
    STOPPED,
    begin_playback,
    consume_restart_on_resume,
    continue_playback,
    note_playback_settings_changed,
    pause_playback,
    playback_allowed,
    restart_on_resume,
    stop_playback,
    transport_generation,
    transport_intent,
    transport_session_active,
)


def _cycle_session(**extra) -> dict:
    ss = {
        "backing_source_kind": "catalog",
        "practice_key": "C",
        "concert_practice_key": "C",
        BACKING_KEY_CYCLE_SESSIONS_KEY: {},
        **extra,
    }
    with mock.patch.object(kc, "persist_key_cycle_position", return_value=True):
        start_key_cycle(ss, start_key="C", interval=1, direction="up")
    return ss


class TransportIntentModelTests(unittest.TestCase):
    def test_default_is_stopped_and_never_plays(self) -> None:
        ss: dict = {}
        self.assertEqual(transport_intent(ss), STOPPED)
        self.assertFalse(playback_allowed(ss))
        self.assertFalse(transport_session_active(ss))

    def test_play_pause_resume_stop(self) -> None:
        ss: dict = {}
        begin_playback(ss)
        gen = transport_generation(ss)
        self.assertEqual(transport_intent(ss), PLAYING)
        pause_playback(ss)
        self.assertEqual(transport_intent(ss), PAUSED)
        self.assertTrue(transport_session_active(ss))
        self.assertFalse(playback_allowed(ss))
        continue_playback(ss)
        self.assertEqual(transport_intent(ss), PLAYING)
        self.assertEqual(transport_generation(ss), gen, "Resume continues the same session")
        stop_playback(ss)
        self.assertEqual(transport_intent(ss), STOPPED)
        self.assertGreater(transport_generation(ss), gen, "Stop ends the session")

    def test_pause_while_stopped_stays_stopped(self) -> None:
        ss: dict = {}
        self.assertEqual(pause_playback(ss), STOPPED)

    def test_settings_while_paused_restart_on_resume(self) -> None:
        ss: dict = {}
        begin_playback(ss)
        note_playback_settings_changed(ss)
        self.assertFalse(restart_on_resume(ss), "while playing the take is rebuilt live")
        pause_playback(ss)
        self.assertEqual(note_playback_settings_changed(ss), PAUSED)
        self.assertTrue(restart_on_resume(ss))
        self.assertTrue(consume_restart_on_resume(ss))
        self.assertFalse(restart_on_resume(ss))

    def test_settings_while_stopped_change_nothing(self) -> None:
        ss: dict = {}
        self.assertEqual(note_playback_settings_changed(ss), STOPPED)
        self.assertFalse(playback_allowed(ss))
        self.assertFalse(restart_on_resume(ss))


class GatedArmPointsTests(unittest.TestCase):
    def test_stale_play_request_after_stop_does_not_autoplay(self) -> None:
        ss = {"_backing_play_request": True, "_script_run_seq": 7}
        begin_playback(ss)
        stop_playback(ss)
        prepare_backing_transport_for_session(ss)
        self.assertFalse(ss.get("_backing_autoplay"))

    def test_play_request_while_playing_autoplays(self) -> None:
        ss = {"_backing_play_request": True, "_script_run_seq": 8}
        begin_playback(ss)
        prepare_backing_transport_for_session(ss)
        self.assertTrue(ss.get("_backing_autoplay"))

    def test_page_player_never_autoplays_a_take_while_stopped(self) -> None:
        ss = {"_backing_autoplay": True}
        self.assertFalse(page_player_autoplay(ss, "a.wav"))
        begin_playback(ss)
        self.assertTrue(page_player_autoplay(ss, "a.wav"))

    def test_paused_take_keeps_its_props_but_a_new_take_waits(self) -> None:
        ss = {"_backing_autoplay": True}
        begin_playback(ss)
        page_player_autoplay(ss, "a.wav")
        pause_playback(ss)
        ss["_backing_autoplay"] = False
        # Same take: unchanged props, so the element keeps its paused place.
        self.assertTrue(page_player_autoplay(ss, "a.wav"))
        # A rebuilt take while paused mounts without autoplay.
        self.assertFalse(page_player_autoplay(ss, "b.wav"))


class KeyCycleSettingsNeverStartAudioTests(unittest.TestCase):
    def _hold(self, ss: dict) -> None:
        data = dict(get_owner_cycle_session(ss) or {})
        data["status"] = STATUS_HELD
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY][kc.resolve_cycle_owner(ss)] = data
        ss["_kc_current_static_url"] = "app/static/kc/s/x.wav"

    def _change(self, ss: dict) -> None:
        ss["_kc_user_arrangement_edit"] = True
        with mock.patch.object(kc, "persist_key_cycle_position", return_value=True):
            note_key_cycle_arrangement_settings_changed(ss)

    def test_stopped_cycle_settings_change_arms_nothing(self) -> None:
        ss = _cycle_session()
        self._hold(ss)
        stop_playback(ss)
        self._change(ss)
        self.assertEqual(get_owner_cycle_session(ss)["status"], STATUS_HELD)
        self.assertFalse(ss.get("_backing_autoplay"))
        self.assertFalse(ss.get("_kc_restart_play"))
        self.assertFalse(ss.get("_kc_resume_play"))
        self.assertFalse(ss.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertFalse(ss.get("_kc_arr_key_lock"))
        self.assertTrue(ss.get(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY), "Play rebuilds with it")

    def test_paused_cycle_settings_change_waits_for_resume(self) -> None:
        ss = _cycle_session()
        self._hold(ss)
        begin_playback(ss)
        pause_playback(ss)
        self._change(ss)
        self.assertEqual(transport_intent(ss), PAUSED)
        self.assertEqual(get_owner_cycle_session(ss)["status"], STATUS_HELD)
        self.assertFalse(ss.get("_backing_autoplay"))
        self.assertTrue(restart_on_resume(ss))

    def test_playing_cycle_settings_change_rebuilds_and_keeps_playing(self) -> None:
        ss = _cycle_session()
        begin_playback(ss)
        ss["_kc_current_static_url"] = "app/static/kc/s/x.wav"
        self._change(ss)
        self.assertEqual(get_owner_cycle_session(ss)["status"], STATUS_RUNNING)
        self.assertTrue(ss.get("_backing_autoplay"))
        self.assertTrue(ss.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertTrue(ss.get("_kc_restart_play"))


class KeyCycleNavigationJumpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._persist = mock.patch.object(kc, "persist_key_cycle_position", return_value=True)
        self._persist.start()

    def tearDown(self) -> None:
        self._persist.stop()

    def _at(self, ss: dict, index: int) -> None:
        jump_key_cycle_to_key(ss, cycle_key_sequence(ss)[index])

    def test_jump_adopts_any_distance_and_both_wraps(self) -> None:
        ss = _cycle_session()
        seq = cycle_key_sequence(ss)
        n = len(seq)
        # (start index, presses) -> landing index, as the browser computes it.
        for start, presses in ((3, -3), (3, -4), (3, 3), (3, 4), (0, -1), (n - 1, 1), (3, -10), (3, 10)):
            self._at(ss, start)
            want = seq[(start + presses) % n]
            moved, _ = jump_key_cycle_to_key(ss, want)
            self.assertEqual(temporary_playback_key(ss), want, (start, presses))
            data = get_owner_cycle_session(ss)
            self.assertEqual(data["status"], STATUS_RUNNING)
            self.assertEqual(data["offset_semitones"], seq.index(want) * 1)

    def test_next_off_the_final_key_wraps_instead_of_stopping(self) -> None:
        ss = _cycle_session()
        seq = cycle_key_sequence(ss)
        self._at(ss, len(seq) - 1)
        jump_key_cycle_to_key(ss, seq[0])
        self.assertEqual(temporary_playback_key(ss), seq[0])
        self.assertFalse(ss.get("_kc_hard_stop"))
        self.assertFalse(ss.get("_kc_cycle_finished_final"))

    def test_jump_beats_stale_arrangement_markers(self) -> None:
        ss = _cycle_session()
        ss.update({
            "_kc_arrangement_url": "app/static/kc/s/old.wav",
            "_kc_force_arrangement_replace": True,
            "_kc_arr_key_lock": "C",
        })
        jump_key_cycle_to_key(ss, cycle_key_sequence(ss)[5])
        for flag in ("_kc_arrangement_url", "_kc_force_arrangement_replace", "_kc_arr_key_lock"):
            self.assertNotIn(flag, ss)

    def test_audible_jump_does_not_restart_the_switched_buffer(self) -> None:
        ss = _cycle_session()
        jump_key_cycle_to_key(ss, cycle_key_sequence(ss)[2], audible=True)
        self.assertTrue(ss.get("_kc_skip_audio_remount"))
        self.assertFalse(ss.get("_kc_restart_play"))
        self.assertEqual(ss["_kc_last_playing_confirm"]["key"], cycle_key_sequence(ss)[2])

    def test_cold_jump_prepares_and_starts_from_the_first_chord(self) -> None:
        ss = _cycle_session()
        jump_key_cycle_to_key(ss, cycle_key_sequence(ss)[4], audible=False)
        self.assertTrue(ss.get("_kc_restart_play"))
        self.assertTrue(ss.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))

    def test_key_outside_the_sequence_is_rejected(self) -> None:
        ss = _cycle_session(**{"backing_key_cycle_step": "whole"})
        before = temporary_playback_key(ss)
        moved, _ = jump_key_cycle_to_key(ss, "Q#m")
        self.assertFalse(moved)
        self.assertEqual(temporary_playback_key(ss), before)

    def test_every_move_bumps_the_position_sequence(self) -> None:
        ss = _cycle_session()
        seqs = []
        for i in (5, 4, 3, 2):
            self._at(ss, i)
            seqs.append(get_owner_cycle_session(ss)["position_seq"])
        self.assertEqual(seqs, sorted(set(seqs)), "Previous moves are newer, not 'behind'")


class ManualNavAckTests(unittest.TestCase):
    """The browser's Previous / Next report is applied whatever else is pending."""

    def setUp(self) -> None:
        self._persist = mock.patch.object(kc, "persist_key_cycle_position", return_value=True)
        self._persist.start()
        self.ss = _cycle_session()
        begin_playback(self.ss)
        self.seq = cycle_key_sequence(self.ss)
        self.data = get_owner_cycle_session(self.ss)

    def tearDown(self) -> None:
        self._persist.stop()

    def _ack(self, key: str, *, cold: bool = False, n: int = 1) -> dict:
        return {
            "kind": "playing", "ackId": f"nav_test_{n}", "cycleId": self.data["cycle_id"],
            "passId": 0, "playingKey": key, "fromKey": self.seq[0], "manualSwitch": True,
            "navSeq": n, "cold": cold, "switchSeq": 1000 + n,
        }

    def test_coalesced_ack_lands_three_keys_away_and_plays(self) -> None:
        pause_playback(self.ss)
        self.assertTrue(kc._apply_manual_nav_ack(self.ss, self._ack(self.seq[3]), self.data))
        self.assertEqual(temporary_playback_key(self.ss), self.seq[3])
        self.assertEqual(transport_intent(self.ss), PLAYING, "Previous / Next plays the target")
        self.assertEqual(self.ss["_kc_acked_switch_seq"], 1001)

    def test_ack_lands_despite_a_previous_plays_arrangement_markers_and_pending_settings(self) -> None:
        self.ss.update({
            "_kc_arrangement_url": "app/static/kc/s/old.wav",
            "_kc_force_arrangement_replace": True,
            BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY: True,
        })
        self.assertTrue(kc._apply_manual_nav_ack(self.ss, self._ack(self.seq[-1]), self.data))
        self.assertEqual(temporary_playback_key(self.ss), self.seq[-1])

    def test_cold_ack_prepares_the_target_and_never_republishes_the_old_take(self) -> None:
        self.ss["_kc_current_static_url"] = "app/static/kc/s/old-key.wav"
        kc._apply_manual_nav_ack(self.ss, self._ack(self.seq[6], cold=True), self.data)
        self.assertEqual(temporary_playback_key(self.ss), self.seq[6])
        self.assertNotIn("_kc_current_static_url", self.ss)
        self.assertTrue(self.ss.get("_kc_restart_play"))

    def test_ack_from_before_a_stop_does_not_revive_the_session(self) -> None:
        begin_playback(self.ss)
        stop_playback(self.ss)
        self.assertFalse(kc._apply_manual_nav_ack(self.ss, self._ack(self.seq[5], cold=True), self.data))
        self.assertEqual(transport_intent(self.ss), STOPPED)
        self.assertEqual(temporary_playback_key(self.ss), self.seq[0])

    def test_stale_cycle_ack_is_refused(self) -> None:
        ack = dict(self._ack(self.seq[2]), cycleId="an-older-cycle")
        self.assertFalse(kc._apply_manual_nav_ack(self.ss, ack, self.data))
        self.assertEqual(temporary_playback_key(self.ss), self.seq[0])


class StopRewindsTests(unittest.TestCase):
    def test_stop_rewinds_the_cycle_to_its_first_key_and_arms_nothing(self) -> None:
        with mock.patch.object(kc, "persist_key_cycle_position", return_value=True):
            ss = _cycle_session()
            seq = cycle_key_sequence(ss)
            jump_key_cycle_to_key(ss, seq[3])
            ss.update({"_kc_resume_play": True, "_kc_restart_play": True, BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY: True})
            rewind_key_cycle_to_first_key(ss)
        self.assertEqual(temporary_playback_key(ss), seq[0])
        self.assertEqual(get_owner_cycle_session(ss)["status"], STATUS_HELD)
        for flag in ("_kc_resume_play", "_kc_restart_play", BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY):
            self.assertFalse(ss.get(flag), flag)

    def test_karaoke_stop_returns_now_singing_to_the_first_entry(self) -> None:
        ss: dict = {"instrument": "Voice"}
        for title in ("Shallow", "Autumn Leaves", "Blues in F minor"):
            km.add_to_queue(ss, f"Pop\x1f{title}", title=title, artist="A", practice_key="C", bpm=100)
        km.start_session(ss)
        km.advance_session(ss, skip_repeats=True)
        km.advance_session(ss, skip_repeats=True)
        ss.pop(km.PENDING_KARAOKE_AUTO_GENERATE_KEY, None)
        km.rewind_session_to_first_entry(ss)
        self.assertTrue(km.is_karaoke_session_active(ss), "the set stays open")
        self.assertEqual((km.current_session_entry(ss) or {}).get("title"), "Shallow")
        self.assertNotIn(km.PENDING_KARAOKE_AUTO_GENERATE_KEY, ss, "nothing starts by itself")

    def test_end_karaoke_set_stops_playback_and_leaves_now_editing(self) -> None:
        from karaoke_ui import end_karaoke_set

        ss: dict = {"instrument": "Voice", "active_catalog_pick_key": "Pop\x1fPerfect"}
        for title in ("Shallow", "Autumn Leaves"):
            km.add_to_queue(ss, f"Pop\x1f{title}", title=title, artist="A", practice_key="C", bpm=100)
        ss[km.KARAOKE_EDITING_PICK_KEY] = "Pop\x1fShallow"
        km.start_session(ss)
        begin_playback(ss)
        km.advance_session(ss, skip_repeats=True)
        end_karaoke_set(ss)
        self.assertEqual(transport_intent(ss), STOPPED)
        self.assertFalse(km.is_karaoke_session_active(ss))
        self.assertEqual(ss.get("karaoke_session_index"), 0)
        self.assertEqual(ss.get("active_catalog_pick_key"), "Pop\x1fPerfect", "Now Editing untouched")
        self.assertNotIn(km.PENDING_KARAOKE_AUTO_GENERATE_KEY, ss)


if __name__ == "__main__":
    unittest.main()
