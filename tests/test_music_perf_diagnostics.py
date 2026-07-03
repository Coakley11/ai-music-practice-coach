"""Tests for music_perf_diagnostics timing trace."""

from __future__ import annotations

import unittest

from music_perf_diagnostics import begin_run, record_span, top_slow_paths


class _FakeSt:
    def __init__(self) -> None:
        self.session_state: dict = {"_script_run_seq": 1}


class TestMusicPerfDiagnostics(unittest.TestCase):
    def test_records_and_ranks_spans(self) -> None:
        st = _FakeSt()
        begin_run(st, page_id="practice")
        record_span(st, "workspace_sync", 120.5)
        record_span(st, "canonical_reconcile", 45.0)
        record_span(st, "workspace_sync", 10.0)
        slow = top_slow_paths(st)
        self.assertEqual(slow[0][0], "workspace_sync")
        self.assertEqual(slow[0][1], 130.5)


if __name__ == "__main__":
    unittest.main()
