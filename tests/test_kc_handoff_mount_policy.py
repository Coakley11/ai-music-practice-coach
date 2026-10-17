"""The kc_handoff receiver is mounted only while a key cycle is active.

Mounting it (disarmed) on every Backing visit, and re-creating it as the cycle
changed state, gave Streamlit Cloud many fresh component loads that could miss
the 60 s ready window ("having trouble loading ...kc_handoff").
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
import backing_key_cycle_handoff as handoff


class HandoffMountPolicyTests(unittest.TestCase):
    def _bridge(self, *, active: bool, status: str | None) -> list[dict]:
        calls: list[dict] = []

        def fake_render(st, session, *, expect_cycle_id="", armed=True):
            calls.append({"armed": armed, "expect_cycle_id": expect_cycle_id})
            return None

        data = {"status": status, "cycle_id": "abc123"} if status else None
        with mock.patch.object(kc, "is_cycle_active", return_value=active), \
             mock.patch.object(kc, "get_owner_cycle_session", return_value=data), \
             mock.patch.object(kc, "key_cycle_settings_pending", return_value=False), \
             mock.patch.object(handoff, "render_handoff_component", side_effect=fake_render), \
             mock.patch.object(handoff, "drain_pending_handoff_ack", return_value=None):
            kc.render_backing_key_cycle_pass_bridge(mock.MagicMock(), {})
        return calls

    def test_cycling_off_mounts_no_receiver(self) -> None:
        self.assertEqual(self._bridge(active=False, status=None), [])

    def test_active_but_stopped_keeps_one_disarmed_receiver(self) -> None:
        calls = self._bridge(active=True, status=kc.STATUS_STOPPED)
        self.assertEqual(calls, [{"armed": False, "expect_cycle_id": "abc123"}])

    def test_running_and_held_arm_the_receiver(self) -> None:
        for status in (kc.STATUS_RUNNING, kc.STATUS_HELD):
            with self.subTest(status=status):
                calls = self._bridge(active=True, status=status)
                self.assertEqual(calls, [{"armed": True, "expect_cycle_id": "abc123"}])

if __name__ == "__main__":
    unittest.main()
