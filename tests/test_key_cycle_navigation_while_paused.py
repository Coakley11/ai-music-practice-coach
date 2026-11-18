"""Previous / Next pressed while paused moves the cycle and stays paused (user decision 2026-11-17).

Before, a Next while paused started the new key at once ("Previous / Next -> playing"). The user's
brief for paused playback: keep playback paused, resume only when the user presses Resume. Pressed
while playing, Previous / Next still play the new key.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
from backing_transport_intent import PAUSED, PLAYING, begin_playback, transport_intent


class NavigationWhilePausedStaysPaused(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "C", "concert_key": "C"}
        # Semitones up from C, as on a seeded song (Blackbird in C): C, Db, D, ...
        kc.start_key_cycle(self.ss, start_key="C", interval=1, direction="up")
        begin_playback(self.ss, reason="test_play")
        self.cid = str(kc.get_owner_cycle_session(self.ss)["cycle_id"])
        kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)
        self.assertEqual(kc.temporary_playback_key(self.ss), "Db")

    def _pause(self) -> None:
        kc._toggle_key_cycle_pause_resume(self.ss)
        self.assertEqual(kc.get_owner_cycle_session(self.ss)["status"], kc.STATUS_HELD)
        self.assertEqual(transport_intent(self.ss), PAUSED)

    def _nav_ack(self, key: str, *, stay_paused: bool, ack_id: str = "nav_1") -> dict:
        return {"kind": "playing", "ackId": ack_id, "cycleId": self.cid, "passId": 1, "playingKey": key,
                "fromKey": "Db", "manualSwitch": True, "navSeq": 1, "switchSeq": 1, "cold": False,
                "natural": False, "stayPaused": stay_paused}

    def _apply(self, ack: dict) -> None:
        kc._apply_manual_nav_ack(self.ss, ack, kc.get_owner_cycle_session(self.ss))

    def _assert_held_on(self, key: str) -> None:
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], key)
        self.assertEqual(data["status"], kc.STATUS_HELD)
        self.assertEqual(transport_intent(self.ss), PAUSED)
        # Nothing armed to start the take: the command the page receives says paused.
        self.assertTrue(self.ss.get("_kc_pause_audio"))
        self.assertFalse(self.ss.get("_kc_restart_play"))
        self.assertFalse(self.ss.get("_kc_resume_play"))
        self.assertFalse(self.ss.get("_backing_autoplay"))
        self.assertFalse(self.ss.get(kc.BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))

    def test_a_next_from_the_page_while_paused_moves_and_stays_paused(self) -> None:
        self._pause()
        self._apply(self._nav_ack("D", stay_paused=True))
        self._assert_held_on("D")

    def test_a_next_from_the_page_while_playing_still_plays(self) -> None:
        self._apply(self._nav_ack("D", stay_paused=False))
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "D")
        self.assertEqual(data["status"], kc.STATUS_RUNNING)
        self.assertEqual(transport_intent(self.ss), PLAYING)

    def test_the_server_step_while_paused_moves_and_stays_paused(self) -> None:
        self._pause()
        kc._step_key_cycle_from_button(self.ss, 1)
        self._assert_held_on("D")
        kc._step_key_cycle_from_button(self.ss, -1)
        self._assert_held_on("Db")

    def test_the_server_step_while_playing_still_plays(self) -> None:
        kc._step_key_cycle_from_button(self.ss, 1)
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "D")
        self.assertEqual(data["status"], kc.STATUS_RUNNING)
        self.assertEqual(transport_intent(self.ss), PLAYING)

    def test_resume_after_a_paused_next_plays_the_new_key(self) -> None:
        self._pause()
        self._apply(self._nav_ack("D", stay_paused=True))
        kc._toggle_key_cycle_pause_resume(self.ss)  # the musician's Resume
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "D")
        self.assertEqual(data["status"], kc.STATUS_RUNNING)
        self.assertEqual(transport_intent(self.ss), PLAYING)


    def test_a_next_made_while_playing_but_applied_after_a_pause_stays_paused(self) -> None:
        # Next, then Pause before the server took the Next: one run applies the card's Pause first
        # (it is handled earlier in the page) and the Next after it. The Next must not undo the Pause.
        self._pause()
        self._apply(self._nav_ack("D", stay_paused=False))
        self._assert_held_on("D")

    def test_a_paused_next_applied_after_a_resume_plays(self) -> None:
        # The mirror order: Next while paused, then Resume before the server took the Next.
        self._pause()
        kc._toggle_key_cycle_pause_resume(self.ss)  # the Resume, applied first
        self._apply(self._nav_ack("D", stay_paused=True))
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(data["current_playback_key"], "D")
        self.assertEqual(data["status"], kc.STATUS_RUNNING)
        self.assertEqual(transport_intent(self.ss), PLAYING)


if __name__ == "__main__":
    unittest.main()
