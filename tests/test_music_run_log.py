"""Tests for unconditional [music_run] Cloud logging."""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from music_run_log import emit_music_run


class TestMusicRunLog(unittest.TestCase):
    def test_emit_prints_stdout_and_stderr_with_event(self) -> None:
        session = {"_script_run_seq": 7, "studio_page": "practice"}
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            emit_music_run("RUN_STARTED", session, page="practice")
        line = out.getvalue().strip()
        err_line = err.getvalue().strip()
        self.assertIn("[music_run]", line)
        self.assertIn("event=RUN_STARTED", line)
        self.assertIn("run_seq=7", line)
        self.assertEqual(line, err_line)

    def test_install_emits_run_started(self) -> None:
        from music_run_boundary import install_music_run_instrumentation

        class _FakeSt:
            session_state: dict = {"_script_run_seq": 1}

            @staticmethod
            def rerun() -> None:
                raise RuntimeError("rerun")

            @staticmethod
            def stop() -> None:
                raise RuntimeError("stop")

        st = _FakeSt()
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            install_music_run_instrumentation(st)
        self.assertIn("event=RUN_STARTED", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
