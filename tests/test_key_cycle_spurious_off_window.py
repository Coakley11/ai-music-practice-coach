"""Key cycling: the stray-Off guard expires, so an intentional Off sticks (e.g. after refresh)."""

from __future__ import annotations

import time
import unittest

import backing_key_cycle as kc


class KeyCycleSpuriousOffWindowTests(unittest.TestCase):
    def test_guard_expires_after_its_window(self) -> None:
        ss: dict = {}
        kc._arm_spurious_off_window(ss)
        self.assertFalse(kc.spurious_off_window_expired(ss))
        ss["_kc_suppress_armed_at"] = time.time() - kc.SPURIOUS_OFF_WINDOW_SEC - 1
        self.assertTrue(kc.spurious_off_window_expired(ss))

    def test_unknown_arm_time_never_expires(self) -> None:
        self.assertFalse(kc.spurious_off_window_expired({}))
        self.assertFalse(kc.spurious_off_window_expired({"_kc_suppress_armed_at": "x"}))

    def test_restore_and_start_arm_the_window(self) -> None:
        import inspect

        src = inspect.getsource(kc)
        # every place that arms the stray-Off guard also stamps its window
        arm_sites = src.count('session["_kc_suppress_spurious_cycle_off"] = True')
        self.assertGreaterEqual(src.count("_arm_spurious_off_window(session)"), arm_sites)


if __name__ == "__main__":
    unittest.main()
