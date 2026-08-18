"""Handoff stderr must never crash Streamlit on Windows OSError 22."""

from __future__ import annotations

import sys

import music_mission_backing_handoff_trace as backing
import music_mission_return_handoff_trace as ret


def test_log_consume_survives_broken_stderr(monkeypatch):
    class Broken:
        def write(self, *_a, **_k):
            raise OSError(22, "Invalid argument")

        def flush(self):
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr(sys, "stderr", Broken())
    session: dict = {}
    backing.log_consume(session, phase="skipped", detail={"reason": "no_pending"})
    assert session["_music_mission_backing_handoff_trace"][-1]["phase"] == "skipped"


def test_return_consume_survives_broken_stderr(monkeypatch):
    class Broken:
        def write(self, *_a, **_k):
            raise OSError(22, "Invalid argument")

        def flush(self):
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr(sys, "stderr", Broken())
    session: dict = {}
    ret.log_mission_return_consume(session, phase="skipped", detail={"reason": "x"})
    assert session["_music_mission_return_handoff_trace"][-1]["phase"] == "skipped"
