"""Tests for backing generation cache helpers."""

from __future__ import annotations

from backing_generation import prepare_wav_b64


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
