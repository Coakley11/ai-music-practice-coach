"""The final key's take completed: the page and the server agree that the cycle has ended.

Browser trace 2026-11-16 (Shape of You, Guitar Shape / capo, the 12-key Circle of Fourths
cycle Bm ... F#m, six-second Mission takes): F#m, the last key, completed and the page ended the
cycle (``final_key_stop``), but the handoff receiver passed on only playing acks, so the server
never saw it. The server stayed F#m / Running, the console offered Resume, and a press replayed
the completed F#m take.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
import backing_key_cycle_handoff as handoff
from backing_transport_intent import STOPPED, transport_intent



class FinalKeyCompletedSealsTheCycle(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "B", "concert_key": "B"}
        # Circle of Fourths from Bm: 12 keys, the last one F#m (as in the trace).
        kc.start_key_cycle(self.ss, start_key="Bm", interval=5, direction="up")
        self.cid = str(kc.get_owner_cycle_session(self.ss)["cycle_id"])
        self.seq = list(kc.cycle_key_sequence(self.ss))
        self.assertEqual(len(self.seq), 12)

    def _go_to(self, index: int) -> None:
        for _ in range(index):
            kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)
        self.assertEqual(kc.temporary_playback_key(self.ss), self.seq[index])

    def _final_ack(self, key: str = "", ack_id: str = "fks_1", cycle_id: str = "") -> dict:
        return {"kind": "final_key_stop", "ackId": ack_id, "cycleId": cycle_id or self.cid, "passId": 12,
                "playingKey": key or self.seq[-1], "fromKey": key or self.seq[-1], "natural": True}

    def _sealed(self) -> bool:
        return bool(self.ss.get("_kc_cycle_finished_final"))

    def test_the_receiver_delivers_the_final_key_ack(self) -> None:
        raw = self._final_ack()
        with mock.patch.object(handoff, "_kc_handoff_component", return_value=dict(raw)):
            got = handoff.render_handoff_component(object(), self.ss, expect_cycle_id=self.cid)
        self.assertIsInstance(got, dict)
        self.assertEqual(got["kind"], "final_key_stop")
        # Inside a batch (the page queued it behind a playing ack) it is delivered too.
        import json

        batch = {"kind": "playing_batch", "cycleId": self.cid, "count": 2, "acks_json": json.dumps([
            {"kind": "playing", "ackId": "ack_2", "cycleId": self.cid, "passId": 12, "playingKey": self.seq[-1]},
            raw])}
        ss2: dict = {}
        with mock.patch.object(handoff, "_kc_handoff_component", return_value=batch):
            first = handoff.render_handoff_component(object(), ss2, expect_cycle_id=self.cid)
        self.assertEqual(first["kind"], "playing")
        nxt = handoff.drain_pending_handoff_ack(ss2)
        self.assertIsInstance(nxt, dict)
        self.assertEqual(nxt["kind"], "final_key_stop")

    def _page_sends_final_key_stop(self) -> int:
        """One server run of the real pass bridge receiving the page's final_key_stop."""

        class _St:
            reruns = 0

            def rerun(self):
                _St.reruns += 1

        with mock.patch.object(handoff, "_kc_handoff_component", return_value=self._final_ack()):
            kc.render_backing_key_cycle_pass_bridge(_St(), self.ss)
        return _St.reruns

    def test_the_page_ending_the_cycle_on_the_final_key_ends_it_on_the_server(self) -> None:
        # Exactly the trace: the server on F#m and Running when the page completed F#m.
        self._go_to(11)
        reruns = self._page_sends_final_key_stop()
        self.assertTrue(self._sealed())
        self.assertEqual(transport_intent(self.ss), STOPPED)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F#m")
        self.assertEqual(reruns, 1)  # the page is rebuilt from the ended state

    def test_the_page_ending_the_cycle_with_the_server_one_behind_ends_it_there_too(self) -> None:
        self._go_to(10)
        self._page_sends_final_key_stop()
        self.assertTrue(self._sealed())
        self.assertEqual(kc.temporary_playback_key(self.ss), "F#m")
        self.assertEqual(transport_intent(self.ss), STOPPED)

    def test_server_on_the_final_key_records_the_end(self) -> None:
        self._go_to(11)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        self.assertTrue(self._sealed())
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "F#m")
        self.assertEqual(data["status"], kc.STATUS_HELD)
        self.assertEqual(transport_intent(self.ss), STOPPED)  # the console's end state (Pause disabled)
        self.assertTrue(self.ss.get("_kc_hard_stop"))

    def test_server_one_key_behind_adopts_the_final_key_and_records_the_end(self) -> None:
        self._go_to(10)  # C#m: it missed the page's switch to F#m (KC-F1)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        self.assertTrue(self._sealed())
        self.assertEqual(kc.temporary_playback_key(self.ss), "F#m")  # not stepped past, not left behind
        self.assertEqual(transport_intent(self.ss), STOPPED)

    def test_a_pause_pressed_while_the_confirmation_was_pending_is_still_sealed(self) -> None:
        self._go_to(11)
        kc._toggle_key_cycle_pause_resume(self.ss)  # Pause: Held
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_HELD)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        self.assertTrue(self._sealed())
        self.assertEqual(transport_intent(self.ss), STOPPED)

    def test_a_resume_press_after_the_end_does_not_restart_the_final_key(self) -> None:
        self._go_to(11)
        kc.seal_final_key_from_ack(self.ss, self._final_ack())
        epoch = int(self.ss.get("_kc_player_cmd_epoch") or 0)
        kc._toggle_key_cycle_pause_resume(self.ss)  # a press that raced the re-render
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["status"], kc.STATUS_HELD)
        self.assertEqual(transport_intent(self.ss), STOPPED)
        self.assertFalse(self.ss.get("_kc_resume_play"))
        self.assertEqual(int(self.ss.get("_kc_player_cmd_epoch") or 0), epoch)  # no new command

    def test_acks_that_do_not_prove_the_final_key_completed_are_refused(self) -> None:
        self._go_to(11)
        self.assertFalse(kc.seal_final_key_from_ack(self.ss, self._final_ack(key="C#m")))  # not the last key
        self.assertFalse(kc.seal_final_key_from_ack(self.ss, self._final_ack(cycle_id="old-cycle")))  # stale cycle
        self.assertFalse(self._sealed())
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_RUNNING)

    def test_a_server_two_keys_behind_is_not_moved_to_the_end(self) -> None:
        self._go_to(9)  # G#m
        self.assertFalse(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        self.assertFalse(self._sealed())
        self.assertEqual(kc.temporary_playback_key(self.ss), "G#m")

    def test_a_resent_ack_after_the_end_changes_nothing(self) -> None:
        self._go_to(11)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, self._final_ack()))
        epoch = int(self.ss.get("_kc_player_cmd_epoch") or 0)
        self.assertFalse(kc.seal_final_key_from_ack(self.ss, self._final_ack(ack_id="fks_2")))
        self.assertEqual(int(self.ss.get("_kc_player_cmd_epoch") or 0), epoch)

    def test_a_new_start_after_the_end_begins_at_the_first_key(self) -> None:
        self._go_to(11)
        kc.seal_final_key_from_ack(self.ss, self._final_ack())
        kc.arm_key_cycle_for_explicit_play(self.ss)  # the card's Play after the end
        self.assertFalse(self._sealed())
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "Bm")
        self.assertEqual(data["status"], kc.STATUS_RUNNING)

    def test_stop_after_the_end_turns_cycling_off(self) -> None:
        self._go_to(11)
        kc.seal_final_key_from_ack(self.ss, self._final_ack())
        kc._stop_key_cycle_from_button(self.ss)
        self.assertFalse(kc.is_cycle_active(self.ss))


if __name__ == "__main__":
    unittest.main()
