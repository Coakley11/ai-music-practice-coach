"""Pause freezes the key that was SOUNDING, even when its handoff ack arrives late.

Browser run 2026-11-13 (Mission, alto sax, Circle of Fourths): the browser
handed off G#m -> C#m, the musician pressed Pause, and the C#m playing ack
reached Python after the pause. ``note_backing_pass_finished`` refused it
("not running"), so Python stayed on G#m: the console snapped back to G#m and
Resume had no take for the key it showed.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc


class TestPauseFreezesAudibleKey(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "C", "concert_key": "C"}
        kc.start_key_cycle(self.ss, start_key="C", interval=5, direction="up")
        self.cid = str(kc.get_owner_cycle_session(self.ss)["cycle_id"])

    def _ack(self, key: str, pass_id: int, ack_id: str) -> dict:
        return {
            "kind": "playing",
            "ackId": ack_id,
            "cycleId": self.cid,
            "passId": pass_id,
            "playingKey": key,
            "fromKey": kc.temporary_playback_key(self.ss),
            "natural": True,
        }

    def test_late_handoff_ack_is_adopted_and_cycle_stays_paused(self) -> None:
        kc.pause_key_cycle(self.ss)
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_HELD)
        moved = kc.note_backing_pass_finished(
            self.ss, pass_signature="p", seamless=True, handoff_ack=self._ack("F", 1, "a1")
        )
        self.assertTrue(moved)
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "F")
        self.assertEqual(data["status"], kc.STATUS_HELD)
        # The same ack again (the component re-delivers) does not move twice.
        self.assertFalse(
            kc.note_backing_pass_finished(self.ss, pass_signature="p", seamless=True, handoff_ack=self._ack("F", 1, "a1"))
        )
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        # Resume continues from F.
        kc.resume_key_cycle(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_RUNNING)

    def test_paused_ack_for_another_key_is_refused(self) -> None:
        kc.pause_key_cycle(self.ss)
        self.assertFalse(
            kc.note_backing_pass_finished(self.ss, pass_signature="p", seamless=True, handoff_ack=self._ack("Bb", 1, "a2"))
        )
        self.assertEqual(kc.temporary_playback_key(self.ss), "C")
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_HELD)

    def test_running_path_unchanged(self) -> None:
        moved = kc.note_backing_pass_finished(
            self.ss, pass_signature="p", seamless=True, handoff_ack=self._ack("F", 1, "a3")
        )
        self.assertTrue(moved)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_RUNNING)

    def test_pause_cancels_a_queued_cold_take_and_resume_requeues_it(self) -> None:
        # Previous / Next to a key with no prepared take queues "prepare and play".
        kc.jump_key_cycle_to_key(self.ss, "F", audible=False)
        self.assertTrue(self.ss.get(kc.BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        kc.pause_key_cycle(self.ss)
        self.assertFalse(self.ss.get(kc.BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        kc.resume_key_cycle(self.ss)
        self.assertTrue(self.ss.get(kc.BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")

    def test_paused_build_is_not_armed_as_a_play(self) -> None:
        from pathlib import Path

        app = (Path(kc.__file__).resolve().parent / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("if (_play_clicked or _play_needs_generate) and not _kc_paused_build:", app)
        js = Path(kc.__file__).read_text(encoding="utf-8")
        self.assertIn("/^Starting/i.test(String(label || ''))", js)


if __name__ == "__main__":
    unittest.main()
