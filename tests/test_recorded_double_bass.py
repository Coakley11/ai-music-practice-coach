"""The recorded double bass: off by default, in tune, deterministic, and light on memory."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_bass_voice as bv
import backing_sample_cache as sc
from backing_sampled_instrument import SampledInstrument

SR = 44100
PACK = bv.DOUBLE_BASS_PACK
CHART = ["Am7", "D7", "Gmaj7", "Cmaj7"]


def render(style="Jazz swing", chart=CHART):
    a, _sr = ba.synthesize_chords_to_numpy(chart, bpm=120, loops=1, sr=SR, style=style, level="Intermediate", song_title="Bass Test")
    return np.asarray(a, dtype=np.float32)


def pitch_cents(x, midi):
    f0 = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    w = x[int(0.15 * SR) : int(1.0 * SR)].astype(np.float64)
    w = (w - w.mean()) * np.hanning(len(w))
    ac = np.fft.irfft(np.abs(np.fft.rfft(w, 2 * len(w))) ** 2)[: len(w)]
    lo, hi = int(SR / (f0 * 1.06)), int(SR / (f0 * 0.94)) + 2
    i = lo + int(np.argmax(ac[lo:hi]))
    y0, y1, y2 = ac[i - 1], ac[i], ac[i + 1]
    lag = i + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
    return 1200.0 * np.log2((SR / lag) / f0)


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", "recorded")


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("MUSIC_UPRIGHT_BASS", raising=False)
    assert bv.upright_mode() == ""
    assert bv.bass_renderer_tag() == ""


@pytest.mark.parametrize("value", ["", "0", "off", "false", "no"])
def test_off_values(monkeypatch, value):
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", value)
    assert bv.upright_mode() == ""


def test_saved_audio_from_each_bass_is_kept_apart(monkeypatch):
    tags = set()
    for value in ("", "model", "recorded"):
        monkeypatch.setenv("MUSIC_UPRIGHT_BASS", value)
        tags.add(bv.bass_renderer_tag())
    assert len(tags) == 3


def test_a_missing_pack_falls_back_to_the_model(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", "recorded")
    monkeypatch.setattr(bv, "DOUBLE_BASS_PACK", tmp_path)
    assert bv.upright_mode() == "model"


def test_the_pack_is_complete_small_and_licensed():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    files = [t["file"] for z in manifest["zones"] for la in z["layers"] for t in la["takes"]]
    assert files and all((PACK / f).is_file() for f in files)
    assert "CC0" in (PACK / "LICENSE").read_text(encoding="utf-8")
    assert sum(p.stat().st_size for p in PACK.iterdir()) < 8 * 1024 * 1024
    for zone in manifest["zones"]:
        assert len(zone["layers"]) == 3
        assert [la["velocity"] for la in zone["layers"]] == sorted(la["velocity"] for la in zone["layers"])


@pytest.mark.parametrize("midi", range(ba.JAZZ_BASS_LOW, ba.JAZZ_BASS_HIGH + 1))
def test_every_walking_note_is_near_a_recording_and_in_tune(midi):
    inst = SampledInstrument(PACK)
    assert abs(inst._zone(midi)["key"] - midi) <= 2
    for velocity in (0.35, 0.85):
        bus = np.zeros(int(1.2 * SR), dtype=np.float32)
        inst.add_note(bus, SR, 0.0, 1.1, midi, 1.0, velocity, f"tune:{midi}")
        assert abs(pitch_cents(bus, midi)) < 9.0, (midi, velocity)


def test_a_note_stops_when_the_finger_comes_off():
    inst = SampledInstrument(PACK)
    bus = np.zeros(SR, dtype=np.float32)
    inst.add_note(bus, SR, 0.1, 0.2, 40, 1.0, 0.6, "stop")
    assert np.max(np.abs(bus[int(0.1 * SR) : int(0.3 * SR)])) > 0.05
    assert np.max(np.abs(bus[int(0.36 * SR) :])) == 0.0


def test_a_note_past_the_end_is_ignored_and_one_near_it_is_cut():
    inst = SampledInstrument(PACK)
    bus = np.zeros(1000, dtype=np.float32)
    inst.add_note(bus, SR, 1.0, 0.5, 40, 1.0, 0.6, "late")
    assert not bus.any()
    inst.add_note(bus, SR, 0.02, 0.5, 40, 1.0, 0.6, "edge")
    assert bus.any()


def test_the_same_seed_plays_the_same_recording():
    inst = SampledInstrument(PACK)
    a, b = np.zeros(SR // 2, dtype=np.float32), np.zeros(SR // 2, dtype=np.float32)
    inst.add_note(a, SR, 0.0, 0.3, 40, 1.0, 0.6, "same")
    inst.add_note(b, SR, 0.0, 0.3, 40, 1.0, 0.6, "same")
    assert np.array_equal(a, b)


def test_the_same_recording_never_plays_twice_in_a_row():
    inst = SampledInstrument(PACK)
    zone = inst._zone(40)
    avoid: dict = {}
    last = {}
    for n in range(300):
        take = inst._take(zone, 0.6, f"s{n}", avoid)
        layer = next(la["velocity"] for la in zone["layers"] if take in la["takes"])
        assert last.get(layer) != take["file"]
        last[layer] = take["file"]


def test_firmer_notes_use_firmer_recordings():
    inst = SampledInstrument(PACK)
    zone = inst._zone(40)
    soft = {inst._take(zone, 0.3, f"s{n}", None)["file"] for n in range(40)}
    firm = {inst._take(zone, 0.9, f"s{n}", None)["file"] for n in range(40)}
    assert not soft & firm


def test_the_store_keeps_to_its_memory_limit(monkeypatch):
    monkeypatch.setenv("MUSIC_SAMPLE_CACHE_MB", "8")
    store = sc.SampleCache()
    for n in range(20):
        store.put(("x", n), np.zeros(1024 * 1024, dtype=np.int16))
    assert store.bytes <= 8 * 1024 * 1024
    assert store.get(("x", 19)) is not None
    assert store.get(("x", 0)) is None


def test_a_recently_played_sample_stays_in_the_store(monkeypatch):
    monkeypatch.setenv("MUSIC_SAMPLE_CACHE_MB", "8")
    store = sc.SampleCache()
    store.put(("keep",), np.zeros(1024 * 1024, dtype=np.int16))
    for n in range(20):
        store.get(("keep",))
        store.put(("x", n), np.zeros(1024 * 1024, dtype=np.int16))
    assert store.get(("keep",)) is not None


def test_a_song_costs_little_memory(recorded):
    sc.SHARED.clear()
    render(chart=CHART * 4)
    assert 0 < sc.SHARED.bytes < 24 * 1024 * 1024
    assert all(v.dtype == np.int16 for v in sc.SHARED._items.values())


def test_recorded_jazz_differs_from_today_and_repeats_exactly(monkeypatch):
    monkeypatch.delenv("MUSIC_UPRIGHT_BASS", raising=False)
    today = render()
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", "recorded")
    one, two = render(), render()
    assert not np.array_equal(today[: len(one)], one[: len(today)])
    assert np.array_equal(one, two)
    assert np.isfinite(one).all() and np.max(np.abs(one)) <= 1.0


@pytest.mark.parametrize("style", ["Pop groove", "Bossa nova", "Funk groove"])
def test_other_styles_are_untouched(monkeypatch, style):
    monkeypatch.delenv("MUSIC_UPRIGHT_BASS", raising=False)
    today = render(style)
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", "recorded")
    assert np.array_equal(today, render(style))


def test_works_when_the_engine_runs_at_another_rate():
    inst = SampledInstrument(PACK)
    bus = np.zeros(22050, dtype=np.float32)
    inst.add_note(bus, 22050, 0.0, 0.8, 45, 1.0, 0.6, "rate")
    assert bus.any()
