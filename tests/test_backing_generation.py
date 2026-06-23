"""Tests for backing generation cache helpers."""

from __future__ import annotations

from backing_generation import prepare_wav_b64, record_backing_timing_event


class _FakeSession:
    def __init__(self) -> None:
        self.session_state: dict = {}


def test_prepare_wav_b64_caches_in_session():
    st = _FakeSession()
    sig = ("song", 120, "E")
    wav = b"RIFF" + b"\x00" * 128
    b64_a, ms_a, hit_a = prepare_wav_b64(st.session_state, sig, wav)
    b64_b, ms_b, hit_b = prepare_wav_b64(st.session_state, sig, wav)
    assert hit_a is False
    assert hit_b is True
    assert b64_a == b64_b
    assert ms_b == 0.0


def test_record_backing_timing_event_orders_deltas():
    ss: dict = {}
    record_backing_timing_event(ss, "generate_start")
    record_backing_timing_event(ss, "generate_complete", extra={"total_ms": 42.0})
    record_backing_timing_event(ss, "play_start")
    trace = ss["_backing_timing_trace"]
    assert trace["last_event"] == "play_start"
    assert trace["generate_complete"]["since_generate_start_ms"] >= 0.0
    assert trace["play_start"]["since_generate_start_ms"] >= trace["generate_complete"]["since_generate_start_ms"]
    assert trace["generate_complete"]["total_ms"] == 42.0
