"""render_pending_scroll_script must occupy exactly one element slot on every run.

It renders before the page body. When it emitted an element only on the run that had a
queued anchor, every later element index shifted by one on that run, and Streamlit kept
the previous run's Backing body as a stale (inert, faded) duplicate above the live one.
"""
from __future__ import annotations

import unittest
from unittest import mock

import studio_scroll_anchors as ssa


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Slot:
    def __init__(self, log):
        self._log = log

    def container(self):
        self._log.append("slot.container")
        return _Ctx()


class _FakeSt:
    def __init__(self, pending: str | None) -> None:
        self.log: list[str] = []
        self.session_state: dict = {}
        self._pending = pending

    def empty(self):
        self.log.append("empty")
        return _Slot(self.log)

    def container(self):
        self.log.append("container")
        return _Ctx()


class ScrollAnchorStableSlotTests(unittest.TestCase):
    def _run(self, pending):
        fake = _FakeSt(pending)
        html_calls: list[str] = []
        with mock.patch.object(ssa, "consume_pending_anchor", lambda _s: pending), mock.patch(
            "streamlit.components.v1.html", lambda body, **_k: html_calls.append(body)
        ):
            ssa.render_pending_scroll_script(fake)
        return fake.log, html_calls

    def test_no_pending_anchor_still_reserves_one_slot(self) -> None:
        log, html_calls = self._run(None)
        self.assertEqual(log, ["empty"])
        self.assertEqual(html_calls, [])

    def test_pending_anchor_fills_the_same_single_slot(self) -> None:
        log, html_calls = self._run("anchor_backing_main_controls")
        self.assertEqual(log, ["empty", "slot.container"])
        self.assertEqual(len(html_calls), 1)
        self.assertIn("anchor_backing_main_controls", html_calls[0])

    def test_both_runs_emit_one_top_level_element(self) -> None:
        a, _ = self._run(None)
        b, _ = self._run("anchor_backing_main_controls")
        self.assertEqual(a.count("empty"), b.count("empty"))
        self.assertNotIn("container", b)  # never a second top-level element


if __name__ == "__main__":
    unittest.main()
