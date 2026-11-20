"""Key Cycling Pause / Stop: no page update the music does not need (2026-11-19).

Phone measurements on dev 5caee5e3: a Key Cycling Pause cost two full script runs
(the card command's run plus an explicit rerun, 0.5-1.5 MB each to the phone) and
a Stop up to three (the page re-pressed Stop every 2.5 s while the first Stop's run
was still in flight). Every extra run delayed the musician's next press.

* Pause reruns only when it adopted the key the page had already moved to (the
  take that run prepared is for the key before); otherwise the cycle bar, bridge
  and player, all built after the command, already draw the held cycle.
* Stop is re-pressed only when the server never received it: not while a script
  run is in progress or requested, and only after the page was idle for 1 s.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import backing_card_commands as cards
import backing_key_cycle as kc
from backing_transport_intent import PAUSED, transport_intent
from tests.test_key_cycle_pause_reports_sounding_key import _Base

_ROOT = Path(kc.__file__).resolve().parent


class PauseNeedsOneRun(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.cid = self._cycle()

    def test_a_pause_on_the_current_key_does_not_rerun(self) -> None:
        out = self._apply("pause", kc={"sounding": "C", "cycleId": self.cid})
        self.assertFalse(out.rerun)
        self.assertTrue(out.commit)
        self.assertEqual((self._key(), self._status()), ("C", kc.STATUS_HELD))
        self.assertEqual(transport_intent(self.ss), PAUSED)

    def test_a_pause_without_a_report_does_not_rerun(self) -> None:
        out = self._apply("pause")
        self.assertFalse(out.rerun)
        self.assertEqual((self._key(), self._status()), ("C", kc.STATUS_HELD))

    def test_a_pause_that_adopts_the_next_key_reruns(self) -> None:
        # The page already plays F (an automatic change it had not acked yet).
        out = self._apply("pause", kc={"sounding": "F", "cycleId": self.cid})
        self.assertTrue(out.rerun)
        self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_HELD))

    def test_a_refused_report_does_not_rerun(self) -> None:
        out = self._apply("pause", kc={"sounding": "Bb", "cycleId": self.cid})  # two steps away
        self.assertFalse(out.rerun)
        self.assertEqual(self._key(), "C")

    def test_resume_still_reruns(self) -> None:
        self._apply("pause", kc={"sounding": "C", "cycleId": self.cid})
        out = self._apply("resume")
        self.assertTrue(out.rerun)
        self.assertEqual(self._status(), kc.STATUS_RUNNING)

    def test_a_repeated_pause_command_stays_held_without_reruns(self) -> None:
        token = self._card("pause", kc={"sounding": "C", "cycleId": self.cid})
        outs = [cards.apply_card_command(self.ss, "pause", token, has_chords=True, stop_backing=lambda _i: False)
                for _ in range(3)]
        cards.commit_card_command(self.ss, token)
        self.assertEqual([o.rerun for o in outs], [False, False, False])
        self.assertEqual((self._key(), self._status()), ("C", kc.STATUS_HELD))


class StopRetryWaitsForTheServer(unittest.TestCase):
    """The page's Stop re-press (bridge script) checks the app's script-run state."""

    @classmethod
    def setUpClass(cls) -> None:
        src = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        i = src.index("// Key Cycling Stop retry (see __kcOnTransportClick).")
        cls.block = src[i:i + 3200]

    def test_no_re_press_while_a_run_is_in_progress_or_requested(self) -> None:
        self.assertIn("data-test-script-state", self.block)
        self.assertRegex(self.block, r"rs === 'running' \|\| rs === 'rerunRequested'")
        self.assertIn("if (runBusy) parentWin.__kcStopIdleSince = 0;", self.block)

    def test_re_press_needs_2_5_s_since_the_press_and_1_s_idle(self) -> None:
        self.assertRegex(self.block, r"> 2500 && idleMs >= 1000")

    def test_the_stop_still_ends_when_the_console_is_gone_and_tries_are_capped(self) -> None:
        self.assertIn("if (!consoleUp) {{", self.block)
        self.assertIn("tries >= 5", self.block)
        self.assertIn("sb.click();", self.block)

    def test_an_unknown_run_state_falls_back_to_the_old_timing(self) -> None:
        # No attribute (another Streamlit build): not busy, so the 2.5 s retry still works.
        self.assertRegex(self.block, re.escape("} catch (eRs) {{ runBusy = false; }}"))

    def test_the_press_itself_still_silences_at_once(self) -> None:
        src = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        i = src.index("const kcStopRoot = t.closest('[class*=\"st-key-backing_key_cycle_stop_btn\"]');")
        self.assertIn("parentWin.__kcHardStop()", src[i:i + 700])


if __name__ == "__main__":
    unittest.main()
