"""Resume continues the same Key Cycling cycle: no new cycle id, no return to the first key.

Acceptance run 2026-11-21 on 0cc15d8c (Karaoke Set, 390 px): about 2 s after Resume -- a rerun cut off at
once by the next -- the Interval / Direction re-check that runs after the radios found its stored "applied"
settings out of step and reset the cycle playing D minor to its first key under a new cycle id, with the
same Fourths / Ascending settings. The console read "1 / 12 A minor" while D minor sounded for 2.6 s.
A musician's own click on the radios resets the cycle in its callback; this check no longer does it on its
own while a playback session is live (playing or paused).
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import backing_card_commands as bcc
import backing_key_cycle as kc
from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session


class ResumeKeepsTheCycle(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.writes: list = []
        real = kc._log_cycle_key_write
        p = mock.patch.object(kc, "_log_cycle_key_write",
                              side_effect=lambda s, **kw: (self.writes.append(kw), real(s, **kw)))
        p.start()
        self.addCleanup(p.stop)
        self.ss = _session()
        self.ui = _ControlsSt(self.ss, cycling="On")
        kc.start_key_cycle(self.ss, start_key="C", interval=5, direction="up")
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self._card("play", 1)
        kc.advance_key_cycle_now(self.ss)                      # C -> F: the cycle has moved on
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.before = dict(kc.get_owner_cycle_session(self.ss) or {})

    def _card(self, action: str, nonce: int) -> None:
        self.ss["backing_card_transport"] = {"action": action, "session": "s", "nonce": nonce}
        a, t = bcc.card_command_for_this_run(self.ss)
        out = bcc.apply_card_command(self.ss, a, t, has_chords=True, stop_backing=lambda _i: False)
        if out.commit:
            bcc.commit_card_command(self.ss, t)

    def _state(self) -> tuple:
        d = kc.get_owner_cycle_session(self.ss) or {}
        return d.get("cycle_id"), d.get("current_playback_key"), d.get("interval"), d.get("direction")

    def test_pause_and_resume_keep_the_cycle(self) -> None:
        self._card("pause", 2)
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self._card("resume", 3)
        for _ in range(3):
            kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.assertEqual(self._state(), (self.before["cycle_id"], "F", 5, "up"))
        self.assertEqual((kc.get_owner_cycle_session(self.ss) or {}).get("status"), kc.STATUS_RUNNING)

    def test_a_stale_settings_record_after_resume_does_not_reset_the_cycle(self) -> None:
        self._card("pause", 2)
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self._card("resume", 3)
        # the delayed reset: the next run's check finds its stored "applied" settings out of step
        self.ss["_kc_cycle_settings_applied"] = (1, "up", self.before["cycle_id"])
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.assertEqual(self._state(), (self.before["cycle_id"], "F", 5, "up"))
        self.assertNotIn("reset_for_cycle_settings", [w["trigger"] for w in self.writes[-6:]])
        kept = [w for w in self.writes if w["trigger"] == "settings_check_kept_live_cycle"]
        self.assertTrue(kept, self.writes[-4:])
        self.assertEqual(kept[-1]["extra"]["reason"], "applied_differs_from_ui")
        # the radios show the cycle's own settings
        self.assertEqual((self.ss.get("backing_key_cycle_step_ui"), self.ss.get("backing_key_cycle_direction_ui")),
                         ("fourth", "up"))

    def test_while_paused_the_check_keeps_the_cycle_too(self) -> None:
        self._card("pause", 2)
        self.ss["_kc_cycle_settings_applied"] = (2, "down", self.before["cycle_id"])
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.assertEqual(self._state(), (self.before["cycle_id"], "F", 5, "up"))

    def test_stopped_the_check_still_applies_the_radios(self) -> None:
        # unchanged when no playback session is live: the safety net resets to the radios' settings
        from backing_transport_intent import STOPPED, stop_playback, transport_intent

        stop_playback(self.ss, reason="test_stop")
        self.assertEqual(transport_intent(self.ss), STOPPED)
        kc.start_key_cycle(self.ss, start_key="C", interval=5, direction="up")
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        cid = (kc.get_owner_cycle_session(self.ss) or {}).get("cycle_id")
        self.ss["_kc_cycle_settings_applied"] = (1, "up", cid)
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.assertIn("reset_for_cycle_settings", [w["trigger"] for w in self.writes])


class _CallbackSt(_ControlsSt):
    """Keeps each radio's on_change, so a test can fire it the way Streamlit does."""

    def __init__(self, session, *, cycling):
        super().__init__(session, cycling=cycling)
        self.callbacks: dict = {}

    def radio(self, label, *, options, key, **kwargs):
        if kwargs.get("on_change"):
            self.callbacks[str(label)] = kwargs["on_change"]
        return super().radio(label, options=options, key=key, **kwargs)


class ARadioChangeToTheSameSettingsKeepsTheCycle(unittest.TestCase):
    """Acceptance run 2026-11-21 on 07fcbf5e (Karaoke Set, 390 px): about 2 s after Resume the Interval /
    Direction callback itself fired -- the Resume click posted every widget's value -- and reset the cycle
    playing D minor to its first key under a new cycle id, with the same Fourths / Ascending."""

    def setUp(self) -> None:
        for p_ in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p_.start()
            self.addCleanup(p_.stop)
        self.ss = _session()
        self.ui = _CallbackSt(self.ss, cycling="On")
        kc.start_key_cycle(self.ss, start_key="C", interval=5, direction="up")
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        from backing_transport_intent import begin_playback

        begin_playback(self.ss, reason="test_play")
        kc.advance_key_cycle_now(self.ss)                      # C -> F
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.cid = (kc.get_owner_cycle_session(self.ss) or {}).get("cycle_id")

    def _state(self):
        d = kc.get_owner_cycle_session(self.ss) or {}
        return d.get("cycle_id"), d.get("current_playback_key"), d.get("interval"), d.get("direction")

    def test_a_spurious_change_with_the_same_values_does_nothing(self) -> None:
        self.assertIn("Interval", self.ui.callbacks)
        self.ui.callbacks["Interval"]()                         # same "fourth" / "up" posted by a click
        self.ui.callbacks["Direction"]()
        kc.render_backing_key_cycle_controls(self.ui, self.ss)
        self.assertEqual(self._state(), (self.cid, "F", 5, "up"))

    def test_a_real_change_still_resets_to_the_saved_key(self) -> None:
        self.ss["backing_key_cycle_step_ui"] = "whole"
        self.ui.callbacks["Interval"]()
        d = kc.get_owner_cycle_session(self.ss) or {}
        self.assertEqual((d.get("interval"), d.get("current_playback_key")), (2, "C"))
        self.assertNotEqual(d.get("cycle_id"), self.cid)


if __name__ == "__main__":
    unittest.main()
