"""The loudness-matched master: off by default, one loudness per take when on, every sample under the ceiling."""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

import backing_loudness as L

ROOT = pathlib.Path(__file__).resolve().parents[1]
SR = 44100


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS", "match")
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS_TARGET", raising=False)


def _sine(amp, secs=5.0, hz=997.0):
    t = np.arange(int(secs * SR)) / SR
    return amp * np.sin(2 * np.pi * hz * t)


def test_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS", raising=False)
    assert L.loudness_mode() == "" and L.loudness_renderer_tag() == ""


def test_the_meter_reads_the_bs1770_reference() -> None:
    # A full-scale 997 Hz sine reads -3.01 LUFS; at -20 dBFS it reads 20 dB less.
    assert L.integrated_lufs(_sine(1.0), SR) == pytest.approx(-3.01, abs=0.1)
    assert L.integrated_lufs(_sine(0.1), SR) == pytest.approx(-23.01, abs=0.1)
    assert L.integrated_lufs(np.zeros(SR), SR) == float("-inf")


def test_the_limiter_holds_the_ceiling_and_leaves_the_rest_alone() -> None:
    rng = np.random.default_rng(3)
    x = 0.2 * rng.standard_normal(SR * 4) * 0.3
    hits = np.arange(SR // 2, len(x), SR)
    for h in hits:  # sparse sharp peaks, like recorded drum attacks
        x[h:h + 40] += np.hanning(40) * 1.6
    ceiling = 10 ** (-1 / 20)
    y, st = L.limit(x, SR, ceiling)
    assert np.max(np.abs(y)) <= ceiling + 1e-12
    # Only around the peaks: no peak keeps the level down (by more than 0.5 dB) for over a quarter second.
    assert st["limited_pct"] / 100 * (len(x) / SR) / len(hits) < 0.25
    quiet = np.ones(len(x), bool)
    for h in hits:  # look-ahead before a peak, then the 80 ms release (eight time constants)
        quiet[max(0, h - int(0.02 * SR)):h + int(0.65 * SR)] = False
    assert np.allclose(y[quiet], x[quiet], rtol=1e-3, atol=0)  # untouched away from the peaks
    flat, st2 = L.limit(0.5 * x / np.max(np.abs(x)), SR, ceiling)
    assert st2["max_gr_db"] == 0.0 and np.array_equal(flat, 0.5 * x / np.max(np.abs(x)))


def test_master_reaches_the_target_without_exceeding_the_ceiling(on) -> None:
    rng = np.random.default_rng(7)
    x = 0.02 * rng.standard_normal(SR * 6)
    x[::SR // 3] = 0.86  # quiet mix, high peaks: today's master would leave it quiet
    y, st = L.master(x, SR)
    assert st["lufs_out"] == pytest.approx(L.DEFAULT_TARGET_LUFS, abs=0.3)
    assert np.max(np.abs(y)) <= 10 ** (L.CEILING_DBFS / 20) + 1e-12
    assert L.LAST_STATS["gain_db"] == st["gain_db"]


def test_the_take_identity_names_the_master(on, monkeypatch) -> None:
    assert L.loudness_renderer_tag() == "+lufs-22c-1"
    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS_TARGET", "-20")
    assert L.loudness_renderer_tag() == "+lufs-20c-1"
    app = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = app.index("def _backing_arrangement_tag(")
    assert "loudness_renderer_tag()" in app[i:i + 900]


def _render(**kw):
    import backing_audio as ba

    ev = [{"chord": c, "section": "A", "bar_in_section": i, "section_bars": 8} for i, c in enumerate(["Fm7", "Bb7", "Ebmaj7", "Abmaj7"] * 2)]
    return ba.synthesize_chords_to_numpy(ev, bpm=96, loops=1, style="Jazz swing", **kw)


def test_full_mix_takes_follow_the_switch_and_layers_keep_todays_master(monkeypatch) -> None:
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS", raising=False)
    today, sr = _render()
    assert float(np.max(np.abs(today))) == pytest.approx(0.86, abs=1e-6)
    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS", "match")
    matched, sr = _render()
    assert L.integrated_lufs(matched, sr) == pytest.approx(L.DEFAULT_TARGET_LUFS, abs=0.3)
    assert float(np.max(np.abs(matched))) <= 10 ** (L.CEILING_DBFS / 20) + 1e-9
    keys_only, _ = _render(layers=["keys"])
    assert float(np.max(np.abs(keys_only))) == pytest.approx(0.86, abs=1e-6)
