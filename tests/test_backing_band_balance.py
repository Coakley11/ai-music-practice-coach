"""MUSIC_BAND_BALANCE: the drums and percussion sit under the music -- softer cymbals, rounded attacks, a per-style
perceived level -- without changing the music's own balance; off, nothing changes."""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_band_balance as bb
import backing_loudness as bl
import backing_performance_plan as bpp

SR = 44100
JAZZ = [{"chord": c, "section": "A", "bar_in_section": i, "section_bars": 8}
        for i, c in enumerate(["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Em7", "A7"])]


@pytest.fixture
def recorded_kit(monkeypatch):
    monkeypatch.setenv("MUSIC_DRUM_KIT_V2", "1")
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS", raising=False)


def _render(style, intensity="Medium", **kw):
    plan = bpp.resolve_performance_plan(style=style, intensity=intensity)
    audio, _ = ba.synthesize_chords_to_numpy(JAZZ, bpm=120, loops=1, style=style, performance=plan, **kw)
    return audio, dict(ba.LAST_MIX_STATS)


def test_off_by_default_and_byte_identical(monkeypatch, recorded_kit):
    monkeypatch.delenv("MUSIC_BAND_BALANCE", raising=False)
    assert not bb.enabled() and bb.renderer_tag() == "" and "+bal1" not in ba.drum_renderer_tag()
    a, stats = _render("Jazz swing")
    assert not any(k.startswith("balance_") for k in stats)
    calls = []
    monkeypatch.setattr(bb, "place_drums", lambda *x, **k: calls.append(1))
    b, _ = _render("Jazz swing")
    assert np.array_equal(a, b) and not calls


def test_on_the_drums_are_placed_and_the_take_is_its_own(monkeypatch, recorded_kit):
    monkeypatch.setenv("MUSIC_BAND_BALANCE", "1")
    assert ba.drum_renderer_tag().endswith("+bal1")
    _, stats = _render("Jazz swing")
    assert stats["balance_drum_gain_db"] <= 0.0  # never louder than today
    assert stats["balance_drums_lu_after"] <= stats["balance_drums_lu_before"]
    # on the target, unless the safety cap stopped the cut (the synthesized band's drums start far louder)
    target = bb.TARGET_LU["Jazz swing"]
    assert (abs(stats["balance_drums_lu_after"] - target) < 0.05  # cut to the target
            or stats["balance_drum_gain_db"] == -bb.MAX_CUT_DB  # the safety cap stopped the cut
            or (stats["balance_drum_gain_db"] == 0.0 and stats["balance_drums_lu_before"] <= target))  # already under


def test_the_music_keeps_its_own_balance(monkeypatch, recorded_kit):
    """Piano / bass are levelled against the same rhythm reference as before; only the drums move."""
    monkeypatch.delenv("MUSIC_BAND_BALANCE", raising=False)
    _, off = _render("Bossa nova")
    monkeypatch.setenv("MUSIC_BAND_BALANCE", "1")
    _, on = _render("Bossa nova")
    assert on["keys_rms"] == pytest.approx(off["keys_rms"], rel=1e-9)


def test_intensity_moves_the_drums_only_a_little():
    assert max(bb.INTENSITY_LU.values()) - min(bb.INTENSITY_LU.values()) <= 2.0


def test_a_style_already_in_balance_is_not_turned_up():
    rng = np.random.default_rng(1)
    music = rng.normal(0, 0.1, SR * 4)
    quiet_drums = rng.normal(0, 0.005, SR * 4)
    out, stats = bb.place_drums(quiet_drums, music, SR, style="Pop groove")
    assert stats["drum_gain_db"] == 0.0


def test_spike_softener_rounds_clicks_and_leaves_the_low_band():
    t = np.arange(SR * 2) / SR
    low = 0.2 * np.sin(2 * np.pi * 110 * t)
    clicks = np.zeros_like(t)
    hiss = np.random.default_rng(2).normal(0, 0.003, len(t))
    for k in range(8):
        i = int((0.1 + k * 0.25) * SR)
        clicks[i:i + 40] = np.hanning(40) * 0.8 * np.sign(np.sin(np.arange(40) * 2.7))
    x = low + clicks + hiss
    y = bb.soften_spikes(x, SR)
    from scipy import signal

    sos = signal.butter(4, 3000, "highpass", fs=SR, output="sos")
    assert np.max(np.abs(signal.sosfilt(sos, y))) < 0.6 * np.max(np.abs(signal.sosfilt(sos, x)))
    lo = signal.butter(4, 300, "lowpass", fs=SR, output="sos")
    assert np.allclose(signal.sosfilt(lo, y)[SR // 2:], signal.sosfilt(lo, x)[SR // 2:], atol=0.01)


def test_shelf_calms_the_top_only():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 0.1, SR * 2)
    y = bb._high_shelf(x, SR, bb.SHELF_HZ, -4.0)
    X, Y = np.abs(np.fft.rfft(x)) ** 2, np.abs(np.fft.rfft(y)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    top = 10 * np.log10(Y[f > 9000].sum() / X[f > 9000].sum())
    body = 10 * np.log10(Y[(f > 200) & (f < 1500)].sum() / X[(f > 200) & (f < 1500)].sum())
    assert top < -3.0 and abs(body) < 0.3


@pytest.mark.parametrize("style", ["Bossa nova", "Jazz swing", "Samba", "Latin jazz"])
def test_drums_sit_under_the_music_by_perceived_loudness(monkeypatch, recorded_kit, style):
    """With the recorded band (the sound the app plays) every style reaches its target under the music."""
    for k, v in (("MUSIC_BAND_BALANCE", "1"), ("MUSIC_LATIN_GROOVES", "1"), ("MUSIC_PIANO_V2", "recorded"),
                 ("MUSIC_UPRIGHT_BASS", "recorded")):
        monkeypatch.setenv(k, v)
    _, stats = _render(style)
    assert stats["balance_drums_lu_after"] <= bb.TARGET_LU[style] + 0.05


def test_loudness_matching_still_applies(monkeypatch, recorded_kit):
    monkeypatch.setenv("MUSIC_BAND_BALANCE", "1")
    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS", "match")
    audio, _ = _render("Jazz swing")
    assert bl.integrated_lufs(audio, SR) == pytest.approx(-22.0, abs=0.5)
