"""The regression comparison must not report a clean run when subtests failed.

``scripts/_matched_test_run.py`` compares an outcome per test ID between two worktrees,
which is how a previously passing test that stops running gets noticed. It had a blind
spot that made it do the opposite: its pattern expected ``SUBFAIL`` followed by
whitespace, and pytest-subtests actually prints ``SUBFAILED(params...)``. So every
subtest failure was skipped, the parent's own ``PASSED`` line was recorded, and a test
whose subtests had all failed was reported as unchanged.

That cost a real miss - eight failing subtests in a mission-register test were called
clean - so the parsing is pinned here rather than left to be rediscovered. These are
verbatim lines from pytest's ``-rA`` summary.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_matched_test_run",
    Path(__file__).resolve().parents[1] / "scripts" / "_matched_test_run.py",
)
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def outcomes(lines):
    """The parsing half of ``run()``, applied to captured summary lines."""
    out = {}
    for line in lines:
        m = runner.OUTCOME.match(line.strip())
        if not m:
            continue
        status, nodeid = m.group(1), m.group(2).split(" ")[0]
        if status.startswith("SUB"):
            status = "FAILED" if status == "SUBFAILED" else out.get(nodeid, "PASSED")
        if out.get(nodeid) in ("FAILED", "ERROR"):
            continue
        out[nodeid] = status
    return out


NODE = "tests/test_qa22_37_instrument_register.py::TestMissionExamplesStayInRange::test_every_wind_level_and_mission"


class SubtestFailuresAreNotLost(unittest.TestCase):
    def test_a_subfailed_line_is_recognised_at_all(self):
        line = f"SUBFAILED(inst='Saxophone', level='Beginner') {NODE}"
        self.assertIsNotNone(runner.OUTCOME.match(line))

    def test_a_parent_that_passed_is_still_recorded_as_failed(self):
        """The exact shape of the miss: PASSED first, then the subtest failures."""
        lines = [
            f"PASSED {NODE}",
            f"SUBFAILED(inst='Saxophone', level='Beginner') {NODE}",
            f"SUBFAILED(inst='Alto Saxophone', level='Intermediate') {NODE}",
        ]
        self.assertEqual(outcomes(lines)[NODE], "FAILED")

    def test_the_order_does_not_matter(self):
        lines = [
            f"SUBFAILED(inst='Baritone Saxophone', level='Beginner') {NODE}",
            f"PASSED {NODE}",
        ]
        self.assertEqual(outcomes(lines)[NODE], "FAILED")

    def test_a_clean_parent_is_still_passed(self):
        self.assertEqual(outcomes([f"PASSED {NODE}"])[NODE], "PASSED")

    def test_subpass_does_not_mask_a_failure(self):
        lines = [
            f"SUBFAILED(x=1) {NODE}",
            f"SUBPASS(x=2) {NODE}",
            f"PASSED {NODE}",
        ]
        self.assertEqual(outcomes(lines)[NODE], "FAILED")

    def test_multiline_parameters_do_not_break_the_first_line(self):
        """Long parameter lists wrap in the summary; the id is on the first line."""
        line = "SUBFAILED(key='G', chord='Am7', inst='Guitar') tests/t.py::C::test_x"
        m = runner.OUTCOME.match(line)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "tests/t.py::C::test_x")

    def test_the_ordinary_statuses_still_parse(self):
        for status in ("PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS"):
            with self.subTest(status=status):
                m = runner.OUTCOME.match(f"{status} tests/t.py::C::test_x")
                self.assertIsNotNone(m)
                self.assertEqual(m.group(1), status)

    def test_a_narrative_line_is_not_mistaken_for_an_outcome(self):
        for line in ("1 failed, 2 passed in 3s", "=== short test summary info ===",
                     "PASSEDish tests/t.py::C::t"):
            with self.subTest(line=line):
                self.assertFalse(outcomes([line]))


class CollectionErrorsDoNotAbortTheComparison(unittest.TestCase):
    """One uncollectable file used to end the run and compare nothing at all."""

    def test_the_runner_asks_pytest_to_continue(self):
        source = (Path(runner.__file__)).read_text(encoding="utf-8")
        self.assertIn("--continue-on-collection-errors", source)

    def test_an_error_is_recorded_as_an_outcome_so_a_one_sided_one_shows_up(self):
        got = outcomes(["ERROR tests/test_notation_metronome_integration.py"])
        self.assertEqual(got["tests/test_notation_metronome_integration.py"], "ERROR")


if __name__ == "__main__":
    unittest.main()
