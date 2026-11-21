"""Key Cycling in a Karaoke Set (user rule 2026-11-18): the hooks the set calls.

* ``restart_key_cycle_for_entry``: a new song cycles from its own key -- the position never carries
  over, even between two songs in the same key -- with Key Cycling's settings kept.
* ``key_cycle_sequence_complete`` / ``consume_key_cycle_completion``: the set moves on only after the
  final key's take ended, never while paused or after a Stop, and at most once per cycle, even when
  the final-key confirmation arrives again or late.
* With Key Cycling Off all three do nothing (ordinary Karaoke unchanged).
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc


class KaraokeSetHooks(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "G", "concert_key": "G"}
        # Song 1 in G, Circle of Fourths: 12 keys.
        kc.start_key_cycle(self.ss, start_key="G", interval=5, direction="up")
        self.seq = list(kc.cycle_key_sequence(self.ss))
        self.assertEqual(len(self.seq), 12)

    # helpers
    def _cid(self) -> str:
        return str((kc.get_owner_cycle_session(self.ss) or {}).get("cycle_id") or "")

    def _go_to(self, index: int) -> None:
        for _ in range(index):
            kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)

    def _final_ack(self, cycle_id: str = "", ack_id: str = "fks_1") -> dict:
        seq = list(kc.cycle_key_sequence(self.ss))
        return {"kind": "final_key_stop", "ackId": ack_id, "cycleId": cycle_id or self._cid(), "passId": 12,
                "playingKey": seq[-1], "fromKey": seq[-1], "natural": True}

    def _finish_cycle(self) -> None:
        self._go_to(len(self.seq) - 1)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))

    # 2. the position resets for every new song
    def test_a_next_song_in_the_same_key_starts_at_its_first_key_with_a_new_cycle(self) -> None:
        self._go_to(4)
        old_cid = self._cid()
        self.assertNotEqual(kc.temporary_playback_key(self.ss), "G")
        data = kc.restart_key_cycle_for_entry(self.ss, "G")
        self.assertIsNotNone(data)
        self.assertEqual(kc.temporary_playback_key(self.ss), "G")
        self.assertEqual(list(kc.cycle_key_sequence(self.ss))[0], "G")
        self.assertNotEqual(self._cid(), old_cid)
        self.assertTrue(kc.is_cycle_active(self.ss))

    def test_a_next_song_in_another_key_cycles_from_that_key_with_the_same_settings(self) -> None:
        self._go_to(3)
        kc.restart_key_cycle_for_entry(self.ss, "Eb")
        data = kc.get_owner_cycle_session(self.ss) or {}
        self.assertEqual(kc.temporary_playback_key(self.ss), "Eb")
        self.assertEqual(list(kc.cycle_key_sequence(self.ss))[0], "Eb")
        self.assertEqual((int(data.get("interval") or 0), data.get("direction")), (5, "up"))  # 1. settings kept

    def test_a_restart_after_a_finished_cycle_is_not_finished(self) -> None:
        self._finish_cycle()
        self.assertTrue(kc.consume_key_cycle_completion(self.ss))
        kc.restart_key_cycle_for_entry(self.ss, "C")
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))

    # 3. / 7. the final key finishing advances once
    def test_the_final_key_finishing_is_the_cue_once(self) -> None:
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        self._finish_cycle()
        self.assertTrue(kc.key_cycle_sequence_complete(self.ss))
        self.assertTrue(kc.key_cycle_sequence_complete(self.ss, self._cid()))
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss, "another-cycle"))
        self.assertTrue(kc.consume_key_cycle_completion(self.ss))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))  # a later run

    def test_a_repeated_or_late_final_key_confirmation_does_not_advance_again(self) -> None:
        self._finish_cycle()
        self.assertTrue(kc.consume_key_cycle_completion(self.ss))
        kc.seal_final_key_from_ack(self.ss, self._final_ack(ack_id="fks_again"))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))

    def test_the_previous_songs_late_confirmation_does_not_finish_the_new_song(self) -> None:
        self._go_to(len(self.seq) - 1)
        old_cid = self._cid()
        kc.restart_key_cycle_for_entry(self.ss, "D")
        kc.seal_final_key_from_ack(self.ss, self._final_ack(cycle_id=old_cid, ack_id="fks_old"))
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))
        self.assertEqual(kc.temporary_playback_key(self.ss), "D")

    # 5. not while paused or while another key plays
    def test_no_cue_while_a_key_before_the_last_is_playing_or_paused(self) -> None:
        self._go_to(5)
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        kc.pause_key_cycle(self.ss)
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))
        kc.resume_key_cycle(self.ss)
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))

    def test_a_pause_during_the_final_key_is_not_its_end(self) -> None:
        self._go_to(len(self.seq) - 1)
        kc.pause_key_cycle(self.ss)
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        kc.resume_key_cycle(self.ss)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        self.assertTrue(kc.consume_key_cycle_completion(self.ss))

    # 6. Stop is authoritative
    def test_a_stop_before_the_final_key_never_advances(self) -> None:
        self._go_to(6)
        kc.stop_key_cycle(self.ss)
        self.assertFalse(kc.key_cycle_sequence_complete(self.ss))
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))

    def test_a_stop_after_the_final_key_but_before_the_set_moved_on_does_not_advance(self) -> None:
        self._finish_cycle()
        kc.stop_key_cycle(self.ss)
        self.assertFalse(kc.consume_key_cycle_completion(self.ss))

    def test_a_stop_turns_key_cycling_off_for_the_next_song(self) -> None:
        kc.stop_key_cycle(self.ss)
        self.assertIsNone(kc.restart_key_cycle_for_entry(self.ss, "A"))
        self.assertFalse(kc.is_cycle_active(self.ss))

    # 8. Key Cycling Off: ordinary Karaoke
    def test_with_key_cycling_off_the_hooks_do_nothing(self) -> None:
        ss: dict = {"display_key": "G", "concert_key": "G"}
        self.assertIsNone(kc.restart_key_cycle_for_entry(ss, "G"))
        self.assertFalse(kc.key_cycle_sequence_complete(ss))
        self.assertFalse(kc.consume_key_cycle_completion(ss))
        self.assertFalse(kc.is_cycle_active(ss))
        self.assertFalse(ss.get("backing_key_cycle_enabled"))


if __name__ == "__main__":
    unittest.main()
