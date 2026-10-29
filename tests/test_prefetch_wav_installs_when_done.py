"""A finished Key Cycle neighbor synthesis lands in the WAV cache by itself.

Browser acceptance: on Next, the stepped-to key's run found no cached WAV (the
prefetch fragment had not ticked again to collect its finished job), threw the
job away for carrying another take request, and synthesized the same
arrangement again -- 12-48 s per key on written-key and concert runs alike.
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import backing_wav_runtime_cache as rc

ROOT = Path(__file__).resolve().parents[1]


def _job(sig) -> Future:
    fut: Future = Future()
    rc.BACKING_WAV_FUTURES[sig] = fut
    rc.install_when_done(sig, fut)
    return fut


def teardown_function() -> None:
    for sig in [k for k in rc.BACKING_WAV_FUTURES if isinstance(k, tuple) and k[:1] == ("_t",)]:
        rc.BACKING_WAV_FUTURES.pop(sig, None)
    for sig in [k for k in rc.BACKING_WAV_CACHE if isinstance(k, tuple) and k[:1] == ("_t",)]:
        rc.BACKING_WAV_CACHE.pop(sig, None)


def test_finished_job_is_cached_without_another_tick() -> None:
    sig = ("_t", "Ebm", 1)
    _job(sig).set_result(b"wav-ebm")
    assert rc.BACKING_WAV_CACHE[sig] == b"wav-ebm"


def test_replaced_or_failed_job_installs_nothing() -> None:
    sig = ("_t", "Em", 2)
    old = _job(sig)
    rc.BACKING_WAV_FUTURES[sig] = Future()   # superseded by a newer job
    old.set_result(b"stale")
    assert sig not in rc.BACKING_WAV_CACHE
    sig2 = ("_t", "Fm", 3)
    _job(sig2).set_exception(RuntimeError("synth failed"))
    assert sig2 not in rc.BACKING_WAV_CACHE
    sig3 = ("_t", "F#m", 4)
    _job(sig3).set_result(b"")
    assert sig3 not in rc.BACKING_WAV_CACHE


def test_existing_cache_entry_is_kept() -> None:
    sig = ("_t", "Gm", 5)
    rc.BACKING_WAV_CACHE[sig] = b"live"
    _job(sig).set_result(b"prefetch")
    assert rc.BACKING_WAV_CACHE[sig] == b"live"


def test_prefetch_fragment_asks_for_install_on_completion() -> None:
    src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = src.index("_wav_ready, _wav_status = _cached_backing_wav_nonblocking(")
    assert "install_when_done=True" in src[i:i + 1200]
    j = src.index("_BACKING_WAV_FUTURES[signature] = fut")
    assert "_install_wav_when_done(signature, fut)" in src[j:j + 200]
