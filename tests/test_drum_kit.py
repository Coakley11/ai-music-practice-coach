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


def _ctx_song(style: str, seed: int, idx: int, bars: int = 16, role: str = "verse") -> K.BarContext:
    bar = idx % bars
    return K.BarContext(style, bar, role, "chorus" if bar == bars - 1 else "", bar == bars - 1, 4.0, "", seed, idx)


def _moves(style: str, seed: int, role: str = "verse", bars: int = 32) -> dict[int, list[K.Hit]]:
    """Bars with a move, leaving out what the style always plays underneath."""
    out = {}
    for i in range(bars):
        ctx = _ctx_song(style, seed, i, role=role)
        bed = K._style_bed(ctx)
        extra = [h for h in K.bar_extras(ctx) if h not in bed]
        if extra:
            out[i] = extra
    return out


MOVING = ["Pop groove", "Rock groove", "Funk groove", "Jazz swing", "Blues groove"]


@pytest.mark.parametrize("style", MOVING)
def test_the_same_song_drums_the_same_way(style: str) -> None:
    assert _moves(style, 7) == _moves(style, 7)


@pytest.mark.parametrize("style", MOVING)
def test_different_songs_get_different_drumming(style: str) -> None:
    assert _moves(style, 7) != _moves(style, 8)


@pytest.mark.parametrize("style", MOVING)
def test_moves_happen_inside_sections_not_only_at_the_end(style: str) -> None:
    for seed in range(5):
        assert [b for b in _moves(style, seed) if b % 16 != 15], (style, seed)


@pytest.mark.parametrize("style", MOVING)
def test_moves_do_not_follow_a_fixed_interval(style: str) -> None:
    gaps = set()
    for seed in range(6):
        bars = [b for b in _moves(style, seed) if b % 16 != 15]
        gaps |= {b - a for a, b in zip(bars, bars[1:])}
    assert len(gaps) >= 3, (style, gaps)


@pytest.mark.parametrize("style", MOVING)
def test_the_same_fill_does_not_repeat_every_time(style: str) -> None:
    shapes = {tuple((h.beat, h.voice) for h in hits) for seed in range(12) for hits in _moves(style, seed).values()}
    assert len(shapes) >= 3, style


@pytest.mark.parametrize("style, limit", [("Pop groove", 0.35), ("Blues groove", 0.45), ("Rock groove", 0.5), ("Jazz swing", 0.55), ("Funk groove", 0.65)])
def test_most_bars_stay_plain_enough_to_practice_over(style: str, limit: float) -> None:
    moved = sum(len(_moves(style, seed)) for seed in range(12))
    assert moved / (12 * 32) <= limit, (style, moved / (12 * 32))


def test_pop_stays_the_simplest() -> None:
    def rate(style: str) -> float:
        return sum(len(_moves(style, s)) for s in range(12))

    assert rate("Pop groove") < rate("Rock groove") < rate("Funk groove")
    for seed in range(12):
        for bar, hits in _moves("Pop groove", seed).items():
            if bar % 16 != 15:
                assert len(hits) <= 1 and not [h for h in hits if h.voice == "tom"], hits


def test_a_mid_section_move_stays_short() -> None:
    for style in MOVING:
        for seed in range(12):
            for bar, hits in _moves(style, seed).items():
                if bar % 16 != 15 and len(hits) > 1:
                    assert min(h.beat for h in hits) >= 1.5, (style, hits)


def test_jazz_keeps_its_own_time_feel() -> None:
    for seed in range(12):
        hits = [h for bar in _moves("Jazz swing", seed).values() for h in bar]
        assert not [h for h in hits if h.voice in {"tom", "open", "crash"}]
        assert max((h.velocity for h in hits if h.voice == "ghost"), default=0) < 0.5  # comping, never a backbeat
        assert max((h.velocity for h in hits if h.voice == "kick"), default=0) < 0.4
    assert [h.beat for h in K.bar_extras(_ctx("Jazz swing", 0)) if h.voice == "pedal"] == [1.0, 3.0]


def test_rock_uses_toms_and_kick_pushes() -> None:
    hits = [h for seed in range(12) for bar in _moves("Rock groove", seed).values() for h in bar]
    assert {"tom", "kick"} <= {h.voice for h in hits}


def test_funk_has_moving_ghost_notes() -> None:
    bars = {b for seed in range(6) for b in range(8) if any(h.voice == "ghost" for h in K.bar_extras(_ctx_song("Funk groove", seed, b)))}
    assert len(bars) >= 4


def test_section_ends_are_sized_by_what_comes_next() -> None:
    small = K.bar_extras(K.BarContext("Rock groove", 7, "verse", "verse", True, 4.0, "", 3, 7))
    big = K.bar_extras(K.BarContext("Rock groove", 7, "verse", "chorus", True, 4.0, "", 3, 7))
    assert len(big) > len(small)


@pytest.mark.parametrize("style", ["Bossa nova", "Ballad", "Jewish groove", "Klezmer groove"])
def test_other_styles_stay_as_written(style: str) -> None:
    assert all(K.bar_extras(_ctx_song(style, s, i)) == [] for s in range(3) for i in range(32))


def test_styles_do_not_share_a_part() -> None:
    parts = {s: repr(_moves(s, 5)) for s in MOVING + ["Bossa nova"]}
    assert len(set(parts.values())) == len(parts)


@pytest.mark.parametrize("drums", ["hats", "minimal", "ending"])
def test_quiet_sections_stay_quiet(drums: str) -> None:
    assert K.bar_extras(K.BarContext("Funk groove", 3, "verse", "", False, 4.0, drums, 1, 3)) == []


def test_other_meters_get_no_added_notes() -> None:
    assert K.bar_extras(K.BarContext("Funk groove", 1, "verse", "", False, 3.0)) == []


def test_a_fill_takes_the_hands_off_the_hi_hat() -> None:
    assert K.fill_window([K.Hit(3.5, "kick", 0.6)]) is None
    assert K.fill_window(K._tom_run([3.0, 3.5, 3.75])) == pytest.approx((2.99, 3.99))
    kit = K.DrumKit(SR, "Rock groove", defer_hats=True)
    audio = np.zeros(SR * 2)
    kit.noise_hit(audio, 0.1, 0.028, 0.012)
    kit.rest_hats(0.05, 0.2)
    kit.flush()
    assert not np.any(audio)


# ----- Memory and saved audio ------------------------------------------------


def test_the_kit_in_the_repo_is_complete_and_licensed() -> None:
    import json

    folder = K._samples.DEFAULT_PACK
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for voice in ("closed", "half", "three", "open", "pedal", "ride", "bell", "crash", "kick", "kick_close", "snare", "snare_close", "rimshot_close", "rim", "tom_low", "tom_high"):
        assert manifest.get(voice), voice
        for layer in manifest[voice]:
            assert all((folder / name).is_file() for name in layer)
    assert "CC0 1.0 Universal" in (folder / "LICENSE").read_text(encoding="utf-8")
    assert sum(p.stat().st_size for p in folder.iterdir()) < 15 * 1024 * 1024


def test_the_sample_cache_holds_to_its_memory_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSIC_SAMPLE_CACHE_MB", "8")
    cache = K._samples._HitCache()
    for i in range(30):
        cache.put(("hit", i), np.zeros(1024 * 1024 // 4, dtype=np.float32))  # 1 MB each
    assert cache.bytes <= 8 * 1024 * 1024
    assert cache.get(("hit", 29)) is not None and cache.get(("hit", 0)) is None


def test_the_cache_keeps_recently_played_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSIC_SAMPLE_CACHE_MB", "8")
    cache = K._samples._HitCache()
    for i in range(8):
        cache.put(("hit", i), np.zeros(1024 * 1024 // 4, dtype=np.float32))
    assert cache.get(("hit", 0)) is not None
    cache.put(("hit", 99), np.zeros(1024 * 1024 // 4, dtype=np.float32))
    assert cache.get(("hit", 0)) is not None and cache.get(("hit", 1)) is None


def test_a_song_uses_only_a_fraction_of_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    K._samples.HITS.clear()
    _render("Pop groove", monkeypatch, on=True)
    used = K._samples.HITS.bytes
    assert 0 < used < 40 * 1024 * 1024


def test_saved_audio_is_named_for_the_drum_sound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSIC_DRUM_KIT_V2", raising=False)
    assert ba.drum_renderer_tag() == ""
    monkeypatch.setenv("MUSIC_DRUM_KIT_V2", "1")
    recorded = ba.drum_renderer_tag()
    assert recorded.startswith("+drums2-full-")
    monkeypatch.setenv("MUSIC_DRUM_PACK_DIR", "none")
    assert ba.drum_renderer_tag() == "+drums2-synth" != recorded


def test_rock_hits_harder_than_jazz_with_the_recorded_kit() -> None:
    def level(style: str, play) -> float:
        kit = K.DrumKit(SR, style, pack=K._samples.SamplePack(str(K._samples.DEFAULT_PACK), "full"))
        b = np.zeros(SR * 2)
        play(kit, b)
        return float(np.sum(b**2))

    assert level("Rock groove", lambda k, b: k.snare(b, 0, 0.04)) > 1.5 * level("Jazz swing", lambda k, b: k.snare(b, 0, 0.04))
    assert level("Rock groove", lambda k, b: k.kick(b, 0, 0.09)) > 1.5 * level("Jazz swing", lambda k, b: k.kick(b, 0, 0.09))


def test_rock_and_funk_use_the_close_microphones() -> None:
    pack = K._samples.SamplePack(str(K._samples.DEFAULT_PACK), "full")
    assert K.DrumKit(SR, "Rock groove", pack=pack)._recorded("kick", 0.9, 1, 0) is not None
    a = K.DrumKit(SR, "Rock groove", pack=pack)._recorded("snare", 0.8, 1, 0)
    b = K.DrumKit(SR, "Jazz swing", pack=pack)._recorded("snare", 0.8, 1, 0)
    assert len(a) != len(b) or not np.array_equal(a, b)


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
