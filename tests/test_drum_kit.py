"""The improved kit: off by default, level-matched, and a different drummer for each style."""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_drum_kit as K
from backing_musical_profile import resolve_backing_musical_profile

SR = 44100
BPM = 100


def _sec(name: str, chords: list[str]) -> list[dict]:
    return [{"chord": c, "section": name, "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]


CHART = _sec("Verse 1", ["C", "G", "Am7", "F", "C", "G", "F", "G"]) + _sec("Chorus", ["F", "G", "C", "Am7"])


def _render(style: str, monkeypatch: pytest.MonkeyPatch, on: bool) -> np.ndarray:
    if on:
        monkeypatch.setenv("MUSIC_DRUM_KIT_V2", "1")
    else:
        monkeypatch.delenv("MUSIC_DRUM_KIT_V2", raising=False)
    prof = resolve_backing_musical_profile(style=style, tempo=BPM, level="Intermediate", time_signature="4/4")
    a, _ = ba.synthesize_chords_to_numpy(CHART, bpm=BPM, loops=1, sr=SR, style=style, level="Intermediate", musical_profile=prof)
    return np.asarray(a, dtype=np.float64)


def _ctx(style: str, bar: int = 1, role: str = "verse", next_role: str = "", ends: bool = False, drums: str = "") -> K.BarContext:
    return K.BarContext(style, bar, role, next_role, ends, 4.0, drums)


def _song_hits(style: str, role: str, bars: int = 8, next_role: str = "chorus") -> list[K.Hit]:
    hits: list[K.Hit] = []
    for b in range(bars):
        end = b == bars - 1
        hits += K.bar_extras(_ctx(style, b, role, next_role if end else "", end))
    return hits


def test_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSIC_DRUM_KIT_V2", raising=False)
    assert K.drum_kit_enabled() is False


def test_switch_off_never_builds_a_kit(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **k):
        raise AssertionError("the kit must not run while it is off")

    monkeypatch.setattr(K, "DrumKit", boom)
    _render("Pop groove", monkeypatch, on=False)


def test_kit_does_not_stay_on_after_a_render(monkeypatch: pytest.MonkeyPatch) -> None:
    _render("Funk groove", monkeypatch, on=True)
    assert ba._ACTIVE_DRUM_KIT.get() is None


@pytest.mark.parametrize("style", ["Pop groove", "Rock groove", "Funk groove", "Jazz swing", "Bossa nova", "Ballad", "Blues groove"])
def test_same_song_renders_the_same_every_time(style: str, monkeypatch: pytest.MonkeyPatch) -> None:
    a = _render(style, monkeypatch, on=True)
    b = _render(style, monkeypatch, on=True)
    assert np.array_equal(a, b)
    assert np.max(np.abs(a)) <= 1.0


@pytest.mark.parametrize("style", ["Pop groove", "Funk groove", "Jazz swing"])
def test_the_kit_really_changes_the_sound_when_on(style: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert not np.array_equal(_render(style, monkeypatch, on=False), _render(style, monkeypatch, on=True))


def _energy(fn) -> float:
    b = np.zeros(SR * 3)
    fn(b)
    return float(np.sum(b**2) / SR)


@pytest.mark.parametrize(
    "name, constant, measured",
    [
        ("kick", K._E_KICK, lambda b: ba._add_kick(b, SR, 0, 1.0, punch=1.45, seed=3)),
        ("snare", K._E_SNARE, lambda b: ba._add_snare(b, SR, 0, 1.0, crack=1.35, seed=3)),
        ("ride", K._E_RIDE, lambda b: ba._add_ride(b, SR, 0, 1.0, seed=3)),
        ("rim", K._E_RIM, lambda b: ba._add_noise_hit(b, SR, 0, 0.05, 1.0, seed=3, tone=0.45)),
    ],
)
def test_level_targets_match_todays_voices(name: str, constant: float, measured) -> None:
    assert _energy(measured) == pytest.approx(constant, rel=0.12), name


@pytest.mark.parametrize(
    "play, voice_energy",
    [
        (lambda kit, b: kit.kick(b, 0, 0.095), K._E_KICK * 0.095**2),
        (lambda kit, b: kit.snare(b, 0, 0.040), K._E_SNARE * 0.040**2),
        (lambda kit, b: kit.ride(b, 0, 0.185), K._E_RIDE * 0.185**2),
        (lambda kit, b: kit.noise_hit(b, 0, 0.028, 0.012), 0.028 * K._NOISE_ENERGY_PER_SEC * 0.012**2),
    ],
)
def test_each_new_hit_has_the_energy_of_the_hit_it_replaces(play, voice_energy: float) -> None:
    kit = K.DrumKit(SR, "Pop groove")
    assert _energy(lambda b: play(kit, b)) == pytest.approx(voice_energy, rel=0.02)


def test_harder_hits_are_brighter() -> None:
    def centroid(x: np.ndarray) -> float:
        spec = np.abs(np.fft.rfft(x)) ** 2
        f = np.fft.rfftfreq(len(x), 1 / SR)
        return float(np.sum(f * spec) / np.sum(spec))

    soft = K._sample("closed", 0, 0, SR, "Pop groove")
    hard = K._sample("closed", 2, 0, SR, "Pop groove")
    assert centroid(hard) > centroid(soft)


def test_repeated_hits_differ() -> None:
    assert not np.array_equal(K._sample("snare", 2, 0, SR, "Pop groove"), K._sample("snare", 2, 1, SR, "Pop groove"))


# ----- Each style keeps its own character -----------------------------------


def test_pop_fills_stay_restrained() -> None:
    verse = _song_hits("Pop groove", "verse", next_role="verse")
    assert not [h for h in verse if h.voice in {"tom", "ghost"}]
    assert len(verse) <= 1
    into_chorus = _song_hits("Pop groove", "verse", next_role="chorus")
    assert len([h for h in into_chorus if h.voice == "tom"]) == 2
    assert not [h for h in _song_hits("Pop groove", "chorus") if h.voice == "ghost"]


def test_funk_has_moving_ghosts_and_a_fuller_fill() -> None:
    hits = _song_hits("Funk groove", "verse")
    bars_with_ghost = {b for b in range(8) if any(h.voice == "ghost" for h in K.bar_extras(_ctx("Funk groove", b)))}
    assert bars_with_ghost and len(bars_with_ghost) < 8
    assert len([h for h in hits if h.voice == "tom"]) == 4
    assert [h for h in hits if h.voice == "kick"]


def test_rock_lifts_the_chorus_without_ghost_notes() -> None:
    assert not [h for h in _song_hits("Rock groove", "verse", next_role="verse")]
    chorus = _song_hits("Rock groove", "chorus", next_role="verse")
    assert chorus and not [h for h in chorus if h.voice == "ghost"]


def test_jazz_keeps_its_own_time_feel() -> None:
    hits = _song_hits("Jazz swing", "verse")
    assert not [h for h in hits if h.voice in {"tom", "kick", "open"}]
    assert not K.replaces_section_fill("Jazz swing", "chorus")
    pedals = [h.beat for h in K.bar_extras(_ctx("Jazz swing", 0)) if h.voice == "pedal"]
    assert pedals == [1.0, 3.0]
    assert max(h.velocity for h in hits if h.voice == "ghost") < 0.5  # comping, never a backbeat


def test_bossa_pattern_is_untouched() -> None:
    assert _song_hits("Bossa nova", "verse") == []
    assert not K.replaces_section_fill("Bossa nova", "chorus")


def test_styles_do_not_share_a_part() -> None:
    parts = {s: tuple(_song_hits(s, "chorus", next_role="chorus")) for s in ("Pop groove", "Rock groove", "Funk groove", "Jazz swing", "Bossa nova")}
    assert len(set(parts.values())) == len(parts)


@pytest.mark.parametrize("drums", ["hats", "minimal", "ending"])
def test_quiet_sections_stay_quiet(drums: str) -> None:
    assert K.bar_extras(_ctx("Funk groove", 1, drums=drums)) == []


def test_other_meters_get_no_added_notes() -> None:
    assert K.bar_extras(K.BarContext("Funk groove", 1, "verse", "", False, 3.0)) == []


# ----- Hi-hat choke and recorded hits ---------------------------------------


def test_a_closing_hat_chokes_an_open_one() -> None:
    kit = K.DrumKit(SR, "Funk groove", defer_hats=True)
    audio = np.zeros(SR * 2)
    kit.open_hat(audio, 0.0, 0.012)
    kit.noise_hit(audio, 0.1, 0.028, 0.001)
    assert not np.any(audio), "hats wait so the next one can close them"
    kit.flush()
    just_after_choke = audio[int(0.125 * SR) : int(0.18 * SR)]
    ringing = K.DrumKit(SR, "Funk groove")
    free = np.zeros(SR * 2)
    ringing.open_hat(free, 0.0, 0.012)
    assert np.sum(just_after_choke**2) < 0.05 * np.sum(free[int(0.125 * SR) : int(0.18 * SR)] ** 2)


def test_held_hats_all_play_after_flush() -> None:
    kit = K.DrumKit(SR, "Pop groove", defer_hats=True)
    audio = np.zeros(SR)
    for i in range(4):
        kit.noise_hit(audio, i * 0.2, 0.028, 0.012, seed=i)
    kit.flush()
    assert all(np.any(audio[int(i * 0.2 * SR) : int((i * 0.2 + 0.05) * SR)]) for i in range(4))
    assert kit._hats == []


@pytest.fixture()
def tiny_pack(tmp_path):
    import json

    import soundfile as sf

    rng = np.random.default_rng(1)
    manifest = {}
    for voice in ("closed", "open", "ride", "crash", "kick", "snare"):
        names = []
        for layer in range(2):
            name = f"{voice}_v{layer}.flac"
            sf.write(str(tmp_path / name), rng.normal(0, 0.1 + 0.2 * layer, SR // 2) * np.linspace(1, 0, SR // 2), SR, subtype="PCM_16", format="FLAC")
            names.append([name])
        manifest[voice] = names
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_cymbal_mode_records_only_the_cymbals(tiny_pack) -> None:
    pack = K._samples.SamplePack(str(tiny_pack), "cymbals")
    assert pack.has("closed") and pack.has("ride")
    assert not pack.has("kick") and not pack.has("snare")
    assert K._samples.SamplePack(str(tiny_pack), "full").has("kick")


def test_velocity_chooses_the_recorded_layer(tiny_pack) -> None:
    pack = K._samples.SamplePack(str(tiny_pack), "full")
    assert not np.array_equal(pack.hit("snare", 0.1, 0, SR), pack.hit("snare", 1.0, 0, SR))


def test_missing_voice_falls_back_to_the_synthesized_one(tiny_pack) -> None:
    kit = K.DrumKit(SR, "Pop groove", pack=K._samples.SamplePack(str(tiny_pack), "full"))
    audio = np.zeros(SR)
    kit.tom(audio, 0.0, 45, 0.06)
    assert np.any(audio)


def test_a_pack_does_nothing_unless_the_kit_is_on(tiny_pack, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSIC_DRUM_PACK_DIR", str(tiny_pack))
    off = _render("Pop groove", monkeypatch, on=False)
    monkeypatch.delenv("MUSIC_DRUM_PACK_DIR")
    assert np.array_equal(off, _render("Pop groove", monkeypatch, on=False))
