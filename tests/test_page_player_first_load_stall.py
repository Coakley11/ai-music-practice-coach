"""The page player that takes over when the Lead Sheet closes must not stay silent at readyState 1.

Real-app evidence (2026-11-10, trial 06924651 = candidate 2 + dev 9dde75c0; first-load scenario, two rounds):
the page player loads the take for the first time on Close, the takeover's seek cancels its first request, and
when the live position lies inside the part already received Chromium never asks for the rest: the player says
"playing" but stays at readyState 1 with the time frozen, and every later step is silent. Candidate 2 alone
recovered only because its seek fell outside the received part. The outgoing sheet player cannot be kept
sounding in this direction (its iframe goes in the same rerun), so the destination itself is watched:
``guardTakeOver`` asks for the live position again, then reloads, and stops as soon as the player can play.

These pin the guard's contract in the transport component; the browser runs (first-load / fresh / warm close on
the integration) are the behavioural proof.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TRANSPORT = (_ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")


def _js_body(src: str, name: str) -> str:
    i = src.index(f"function {name}(")
    j = src.index("\n      function ", i + 10)
    return src[i:j]


class PagePlayerFirstLoadStallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.take = _js_body(_TRANSPORT, "takeOver")
        self.guard = _js_body(_TRANSPORT, "guardTakeOver")

    def test_only_a_playing_takeover_is_guarded_after_it_starts(self) -> None:
        playing = self.take[self.take.index("if (h.playing) {"): self.take.index("} else if (!target.paused)")]
        self.assertIn("guardTakeOver(target);", playing)
        self.assertLess(playing.index("target.play()"), playing.index("guardTakeOver(target);"))
        # A paused hand-off (the take was paused when the sheet opened / closed) is never started by the guard.
        self.assertEqual(self.take.count("guardTakeOver("), 1)

    def test_the_takeover_still_retires_the_source_before_starting_the_destination(self) -> None:
        self.assertLess(self.take.index("h.el.pause()"), self.take.index("target.play()"))

    def test_the_guard_stops_for_pause_stop_end_removal_and_a_moving_or_ready_player(self) -> None:
        stop_line = next(ln for ln in self.guard.splitlines() if "intentNow()" in ln)
        for cond in ("!target.isConnected", "target.ended", "target.paused", 'intentNow() !== "playing"'):
            self.assertIn(cond, stop_line)
        self.assertIn("target.currentTime > start + 0.15 || target.readyState >= 3", self.guard)
        self.assertIn("Date.now() - t0 > TAKEOVER_GIVE_UP_MS", self.guard)

    def test_the_guard_asks_again_at_the_live_position_then_reloads_once(self) -> None:
        self.assertIn("if (tries <= 2) {", self.guard)
        self.assertIn("target.currentTime = at;", self.guard)
        self.assertIn("} else if (tries === 3) {", self.guard)
        self.assertEqual(self.guard.count("target.load()"), 1)
        # The position it asks for follows the live playhead (where the music would be by now), not the click.
        self.assertIn("start + (Date.now() - t0) / 1000", self.guard)
        self.assertIn("Math.min(live(), target.duration - 0.25)", self.guard)

    def test_the_guard_never_retires_or_pauses_anything_itself(self) -> None:
        self.assertNotIn(".pause()", self.guard)
        self.assertNotIn("__backingPlayheadHandoff", self.guard)

    def test_the_guard_is_bounded(self) -> None:
        check = int(re.search(r"const TAKEOVER_CHECK_MS = (\d+);", _TRANSPORT).group(1))
        give_up = int(re.search(r"const TAKEOVER_GIVE_UP_MS = (\d+);", _TRANSPORT).group(1))
        self.assertTrue(500 <= check <= 2000, check)
        self.assertTrue(give_up <= 10000 and give_up >= 3 * check, (check, give_up))


if __name__ == "__main__":
    unittest.main()
