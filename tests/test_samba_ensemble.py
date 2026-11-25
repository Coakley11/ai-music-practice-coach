"""MUSIC_SAMBA_ENSEMBLE: a recorded Samba section (surdos, pandeiro, tamborim, agogo, ganza) that plays like musicians
-- samba microtiming, human variation, rotating takes, hand-muted surdos, a small room -- without getting louder or
harsher than the balanced Samba, and without touching any other style."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_band_balance as bb
import backing_drum_kit as dk
import backing_samba_ensemble as se

CHORDS = [{"chord": c, "section": "A", "bar_in_section": i, "section_bars": 8}
          for i, c in enumerate(["D6", "B7", "Em7", "A7", "D6", "B7", "Em7", "A7"])]


@pytest.fixture
def samba_on(monkeypatch):
    for k, v in (("MUSIC_LATIN_GROOVES", "1"), ("MUSIC_SAMBA_ENSEMBLE", "1"), ("MUSIC_DRUM_KIT_V2", "1")):
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS", raising=False)


def _voices(strokes, prefix):
    return [s.beat for s in strokes if s.voice.startswith(prefix)]


def test_off_unless_both_switches(monkeypatch):
    monkeypatch.delenv("MUSIC_SAMBA_ENSEMBLE", raising=False)
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "1")
    assert not se.enabled() and se.renderer_tag() == ""
    monkeypatch.setenv("MUSIC_SAMBA_ENSEMBLE", "1")
    monkeypatch.delenv("MUSIC_LATIN_GROOVES")
    assert not se.enabled()


def test_pack_is_complete_and_cc0():
    manifest = json.loads((se.PACK / "manifest.json").read_text(encoding="utf-8"))
    assert set(se.LEVEL) == set(manifest)
    for layers in manifest.values():
        for names in layers:
            for name in names:
                assert (se.PACK / name).is_file(), name
    assert "CC0 1.0 Universal" in (se.PACK / "LICENSE").read_text(encoding="utf-8")


def test_the_surdos_answer_each_other():
    s = se.bar_strokes(0)
    low_open = [x.beat for x in s if x.voice == "surdo_low" and not x.muted]
    assert low_open == [1.0, 3.0]  # the primeira's strong "2" in each 2/4 bar
    assert max(x.velocity for x in s if x.voice == "surdo_low") == pytest.approx(0.92)
    assert [x.beat for x in s if x.voice == "surdo_high" and not x.muted] == [0.0, 2.0]
    assert any(x.muted for x in s if x.voice == "surdo_low")  # hand-muted touches
    assert 2.75 in _voices(se.bar_strokes(3), "surdo_low")  # the pickup at a phrase end
    assert 2.75 not in _voices(se.bar_strokes(1), "surdo_low")


def test_pandeiro_ganza_tamborim_agogo():
    s = se.bar_strokes(0)
    jingle = [x for x in s if x.voice == "pandeiro_jingle"]
    accents = sorted(x.beat for x in jingle if x.velocity > 0.7)
    assert accents == [0.75, 1.75, 2.75, 3.75]
    assert len([x for x in s if x.voice.startswith("ganza")]) == 16
    assert sorted(_voices(s, "tamborim")) in ([st * 0.25 for st in se._TELECO_TECO], [st * 0.25 for st in se._TAMBORIM_VARIATION])
    assert _voices(se.bar_strokes(0), "agogo") != _voices(se.bar_strokes(1), "agogo")  # two-bar bell phrase
    light = se.bar_strokes(0, intensity="Light")
    assert not _voices(light, "tamborim") and not _voices(light, "agogo")
    heavy = se.bar_strokes(0, intensity="Heavy")
    assert len(_voices(heavy, "surdo_high")) > len(_voices(s, "surdo_high"))


def test_samba_microtiming_and_human_variation():
    third = se.Stroke(0.5, "ganza_down", 0.5)
    fourth = se.Stroke(0.75, "ganza_up", 0.9)
    first = se.Stroke(1.0, "surdo_low", 0.9)
    assert se.performed_beat(third, 0) < 0.5 - 0.015  # the third sixteenth anticipated
    assert se.performed_beat(fourth, 0) < 0.75 - 0.02  # the fourth more so
    assert se.performed_beat(first, 0) > 1.0  # the surdo sits a touch late
    assert se.performed_beat(third, 0) == se.performed_beat(third, 0)  # deterministic
    assert se.performed_beat(third, 0) != se.performed_beat(third, 1)  # but not identical every bar
    vels = {round(se.performed_velocity(fourth, b), 4) for b in range(8)}
    assert len(vels) > 4 and all(0.75 < v <= 1.0 for v in vels)


def test_takes_rotate_and_nothing_is_pitch_shifted(monkeypatch):
    import soundfile as sf

    manifest = json.loads((se.PACK / "manifest.json").read_text(encoding="utf-8"))
    used = []
    monkeypatch.setattr(se, "_stroke_audio", lambda voice, take, sr, muted, pack="": (used.append((voice, take)), np.zeros(10, np.float32))[1])
    se.play_bar(np.zeros(44100 * 3), 44100, 0, [se.Stroke(b * 0.25, "ganza_down", 0.5) for b in range(0, 16, 2)], lambda b: b * 0.5)
    takes = [t for v, t in used]
    assert all(a != b for a, b in zip(takes, takes[1:]))  # never the same take twice in a row
    monkeypatch.undo()
    name = manifest["surdo_high"][0][0]
    raw, sr = sf.read(str(se.PACK / name), dtype="float32")
    out = se._stroke_audio("surdo_high", name, sr, False)
    energy = float(np.sum(raw.astype(np.float64) ** 2)) / sr
    dry_part = out[: int(0.005 * sr)]  # before the first reflection: exactly the recording, untouched in pitch
    assert np.allclose(dry_part, (raw / np.sqrt(energy))[: len(dry_part)], atol=1e-5)


def test_muted_stroke_is_damped():
    manifest = json.loads((se.PACK / "manifest.json").read_text(encoding="utf-8"))
    name = manifest["surdo_low"][2][0]
    open_ = se._stroke_audio("surdo_low", name, 44100, False)
    muted = se._stroke_audio("surdo_low", name, 44100, True)
    tail = slice(int(0.3 * 44100), int(0.5 * 44100))
    assert np.sqrt(np.mean(muted[tail] ** 2)) < 0.25 * np.sqrt(np.mean(open_[tail] ** 2))


def test_the_kit_lays_out_under_the_section(monkeypatch, samba_on):
    kicks = []
    real = dk.DrumKit.kick
    monkeypatch.setattr(dk.DrumKit, "kick", lambda self, *a, **k: (kicks.append(1), real(self, *a, **k)))
    ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba")
    assert not kicks
    assert "+samba1-" in ba.drum_renderer_tag()


def test_other_styles_are_untouched(monkeypatch, samba_on):
    a, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=116, loops=1, style="Latin jazz")
    monkeypatch.setenv("MUSIC_SAMBA_ENSEMBLE", "0")
    b, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=116, loops=1, style="Latin jazz")
    assert np.array_equal(a, b)


def test_samba_without_the_switch_is_byte_identical(monkeypatch, samba_on):
    monkeypatch.setenv("MUSIC_SAMBA_ENSEMBLE", "0")
    a, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba")
    calls = []
    monkeypatch.setattr(se, "play_bar", lambda *x, **k: calls.append(1))
    b, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba")
    assert np.array_equal(a, b) and not calls


def test_never_louder_than_the_balanced_samba(monkeypatch, samba_on):
    for k, v in (("MUSIC_BAND_BALANCE", "1"), ("MUSIC_PIANO_V2", "recorded")):
        monkeypatch.setenv(k, v)
    import backing_performance_plan as bpp

    ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba", performance=bpp.resolve_performance_plan(style="Samba"))
    assert ba.LAST_MIX_STATS["balance_drums_lu_after"] <= bb.TARGET_LU[bb.SAMBA_ENSEMBLE] + 0.05 <= -10.4


@pytest.mark.parametrize("intensity, balanced_lu", [("Light", -14.02), ("Medium", -10.5), ("Heavy", -10.07)])
def test_no_louder_than_the_balanced_samba_at_any_intensity(monkeypatch, samba_on, intensity, balanced_lu):
    """Measured on the balanced Samba of 85d59815 (recorded band, same chords, 104 BPM)."""
    for k, v in (("MUSIC_BAND_BALANCE", "1"), ("MUSIC_PIANO_V2", "recorded"), ("MUSIC_UPRIGHT_BASS", "recorded")):
        monkeypatch.setenv(k, v)
    import backing_performance_plan as bpp

    ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba",
                                  performance=bpp.resolve_performance_plan(style="Samba", intensity=intensity))
    assert ba.LAST_MIX_STATS["balance_drums_lu_after"] <= balanced_lu + 0.05



# --- MUSIC_SAMBA_AUTHENTIC: real surdo / pandeiro / tamborim recordings (Freesound, CC0 / CC BY) ---------------------

def test_authentic_is_off_unless_asked(monkeypatch, samba_on):
    monkeypatch.delenv("MUSIC_SAMBA_AUTHENTIC", raising=False)
    assert not se.authentic() and "-auth-" not in se.renderer_tag()
    assert se._source("surdo_low")[0] == ""


def test_authentic_voices_use_the_real_recordings(monkeypatch, samba_on):
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", "1")
    assert se.authentic() and "-auth-" in se.renderer_tag()
    for voice, real in se.AUTHENTIC_VOICES.items():
        pack, layers = se._source(voice)
        assert pack == str(se.AUTHENTIC_PACK) and layers and all(f.startswith(real) for L in layers for f in L)
    for voice in ("agogo_high", "ganza_down", "pandeiro_shake"):
        assert se._source(voice)[0] == ""  # already the real instruments / no authentic recording


def test_every_authentic_file_is_credited_and_commercially_licensed():
    attribution = json.loads((se.AUTHENTIC_PACK / "ATTRIBUTION.json").read_text(encoding="utf-8"))
    manifest = json.loads((se.AUTHENTIC_PACK / "manifest.json").read_text(encoding="utf-8"))
    files = {f for layers in manifest.values() for L in layers for f in L}
    credited = {r["file"] for r in attribution}
    assert files == credited
    on_disk = {p.name for p in se.AUTHENTIC_PACK.glob("*.flac")}
    assert files == on_disk
    for r in attribution:
        assert r["license"] in ("CC0 1.0", "CC BY 3.0", "CC BY 4.0"), r
        assert "nc" not in r["license_url"].lower(), r  # never a non-commercial license
        assert r["author"] and r["source"].startswith("https://freesound.org/") and r["modifications"]
    credits = (se.AUTHENTIC_PACK / "CREDITS.md").read_text(encoding="utf-8")
    for r in attribution:
        if r["license"].startswith("CC BY"):
            assert r["author"] in credits and r["source"] in credits


def test_authentic_take_is_its_own(monkeypatch, samba_on):
    a, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba")
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", "1")
    b, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=104, loops=1, style="Samba")
    n = min(len(a), len(b))
    assert not np.allclose(a[:n], b[:n])


def test_each_instrument_can_be_adopted_on_its_own(monkeypatch, samba_on):
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", "surdo,tamborim")
    assert se.authentic_families() == {"surdo", "tamborim"}
    assert se._source("surdo_low")[0] == str(se.AUTHENTIC_PACK)
    assert se._source("tamborim")[0] == str(se.AUTHENTIC_PACK)
    assert se._source("pandeiro_jingle")[0] == ""  # the pandeiro keeps its stand-in
    tag = se.renderer_tag()
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", "1")
    assert se.authentic_families() == set(se.AUTHENTIC_FAMILIES) and se.renderer_tag() != tag
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", "cowbell")
    assert not se.authentic()


def test_a_recording_that_stops_while_ringing_fades_naturally():
    sr = 44100
    t = np.arange(int(0.5 * sr)) / sr
    ringing = (np.sin(2 * np.pi * 60 * t) * np.exp(-t / 2.0)).astype(np.float32)  # still loud at its end
    out = se.natural_end(ringing, sr)
    assert abs(out[-1]) < 1e-3 and np.allclose(out[: int(0.3 * sr)], ringing[: int(0.3 * sr)])
    decayed = (np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.03)).astype(np.float32)  # already silent at its end
    assert np.array_equal(se.natural_end(decayed, sr), decayed)


def test_the_low_surdo_stand_in_no_longer_stops_mid_ring():
    manifest = json.loads((se.PACK / "manifest.json").read_text(encoding="utf-8"))
    x = se._stroke_audio("surdo_low", manifest["surdo_low"][2][0], 44100, False)
    dry_end = x[len(x) - int(se.ROOM_RT60 * 44100) - 200: len(x) - int(se.ROOM_RT60 * 44100)]
    assert np.max(np.abs(dry_end)) < 0.05 * np.max(np.abs(x))


@pytest.mark.parametrize("authentic", ["0", "1"])
def test_no_recording_repeats_back_to_back_over_a_song(monkeypatch, samba_on, authentic):
    monkeypatch.setenv("MUSIC_SAMBA_AUTHENTIC", authentic)
    used = []
    real = se._stroke_audio

    def spy(voice, take, sr, muted, pack=""):
        used.append((se.AUTHENTIC_VOICES.get(voice, voice) if pack else voice, take))
        return real(voice, take, sr, muted, pack)

    monkeypatch.setattr(se, "_stroke_audio", spy)
    rows = [{"chord": c, "section": "A", "bar_in_section": i % 8, "section_bars": 8} for i, c in enumerate(["D6", "B7", "Em7", "A7"] * 4)]
    ba.synthesize_chords_to_numpy(rows, bpm=104, loops=1, style="Samba")
    by = {}
    for v, t in used:
        by.setdefault(v, []).append(t)
    for v, ts in by.items():
        assert sum(a == b for a, b in zip(ts, ts[1:])) == 0, v
    assert len(set(by["agogo_high"])) == 3 and len(set(by["agogo_low"])) == 2  # every agogo recording is used


def test_thin_layers_borrow_their_neighbours():
    assert se.take_pool([["a"], ["b"], ["c"]], 1) == ["b", "a", "c"]
    assert se.take_pool([["a", "b", "c"], ["d"]], 0) == ["a", "b", "c"]



def test_the_section_phrases_with_the_song():
    mid = se.bar_strokes(9, bar_in_section=1, section_bars=8, seed=7)
    last = se.bar_strokes(15, bar_in_section=7, section_bars=8, seed=7)
    first = se.bar_strokes(16, bar_in_section=0, section_bars=8, seed=7)
    # the call into the next section: surdo sixteenths on the last beat, the tamborim's call, the bells lay out for it
    assert {3.25, 3.5, 3.75} <= set(_voices(last, "surdo")) and not {3.25, 3.5, 3.75} <= set(_voices(mid, "surdo"))
    assert [b for b in _voices(last, "tamborim") if b >= 3.0] == [3.0, 3.25, 3.5, 3.75]
    assert not [b for b in _voices(last, "agogo") if b >= 3.0]
    # the primeira marks the new section with an open stroke on "1"
    assert any(x.voice == "surdo_low" and x.beat == 0.0 and not x.muted for x in first)
    assert not any(x.voice == "surdo_low" and x.beat == 0.0 and not x.muted for x in mid)
    assert not any(b >= 3.25 for b in _voices(se.bar_strokes(15, intensity="Light", bar_in_section=7, section_bars=8), "surdo_high"))


def test_different_songs_vary_differently_and_bars_are_not_copies():
    a = [tuple((x.beat, x.voice, round(x.velocity, 2)) for x in se.bar_strokes(b, bar_in_section=b % 8, section_bars=8, seed=1)) for b in range(16)]
    b = [tuple((x.beat, x.voice, round(x.velocity, 2)) for x in se.bar_strokes(b, bar_in_section=b % 8, section_bars=8, seed=2)) for b in range(16)]
    assert a != b  # the variations follow the song
    assert len(set(a)) >= 6  # sixteen bars are not one bar repeated


def test_the_room_adds_air_not_low_end_mud():
    manifest = json.loads((se.PACK / "manifest.json").read_text(encoding="utf-8"))
    from scipy import signal

    x = se._stroke_audio("surdo_low", manifest["surdo_low"][2][0], 44100, False)
    def low_share(y):
        Y = np.abs(np.fft.rfft(y)) ** 2
        f = np.fft.rfftfreq(len(y), 1 / 44100)
        return Y[f < 100].sum() / Y.sum()

    n_dry = len(x) - int(se.ROOM_RT60 * 44100)
    tail = x[n_dry + 2000:]  # only the room is left here
    assert low_share(tail) < 0.25 * low_share(x[:n_dry])  # the room keeps the drum's body out of its reflections
