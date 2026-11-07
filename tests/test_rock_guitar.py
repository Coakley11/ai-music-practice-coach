"""Rock guitar from recordings: off by default, a different guitarist per song, real amp behaviour, light on memory."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_guitar_amp as amp
import backing_rock_guitar as rg
import backing_sample_cache as sc
from backing_sampled_instrument import SampledInstrument

SR = 44100


def sec(name, chords):
    return [{"chord": c, "section": name, "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]


FORM = sec("Verse 1", ["E5", "G5", "A5", "A5", "E5", "G5", "C5", "B5"]) + sec("Chorus", ["A5", "C5", "G5", "D5"])
notes_of = ba.chord_notes_for_guitar


def render(style="Rock groove", chart=FORM, title="Guitar Test", bpm=120):
    a, _ = ba.synthesize_chords_to_numpy(chart, bpm=bpm, loops=1, sr=SR, style=style, level="Intermediate", song_title=title)
    return np.asarray(a, dtype=np.float32)


def plan(part, seed="s", tones=("crunch", "overdrive")):
    return rg.Plan(part, tones, seed)


def bar(part, chord="E5", *, chorus=False, tone="crunch", segments=None, index=1, seed="s", phrase_end=False, section_end=False, next_chord="A5"):
    return rg.guitar_bar(segments or [(0.0, 4.0, chord)], plan(part, seed), tone=tone, chord_notes=notes_of, next_chord=next_chord,
                         phrase_end=phrase_end, section_end=section_end, bar_index=index, chorus=chorus)


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("MUSIC_ROCK_GUITAR", raising=False)
    assert not rg.enabled()
    assert rg.guitar_renderer_tag() == ""


@pytest.mark.parametrize("value", ["", "0", "off", "false", "no"])
def test_off_values(monkeypatch, value):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", value)
    assert not rg.enabled()


def test_saved_audio_is_kept_apart(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    assert rg.guitar_renderer_tag()


def test_a_missing_pack_keeps_todays_sound(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    monkeypatch.setattr(rg, "GUITAR_PACK", tmp_path)
    assert not rg.enabled()


def test_the_pack_is_complete_small_and_licensed():
    manifest = json.loads((rg.GUITAR_PACK / "manifest.json").read_text(encoding="utf-8"))
    files = [t["file"] for z in manifest["zones"] for la in z["layers"] for t in la["takes"]]
    files += [d["file"] for d in manifest["dead"]] + [d["file"] for d in manifest["release"]]
    assert files and all((rg.GUITAR_PACK / f).is_file() for f in files)
    assert "CC0" in (rg.GUITAR_PACK / "LICENSE").read_text(encoding="utf-8")
    assert sum(p.stat().st_size for p in rg.GUITAR_PACK.iterdir()) < 10 * 1024 * 1024


# --- A different guitarist for different songs. ----------------------------------------------------------


def test_songs_get_different_parts():
    chords = ["E5", "G5", "A5", "C5"]
    parts = {rg.choose_plan(chords, notes_of, 120, f"song{n}").part for n in range(40)}
    assert len(parts) >= 5


def test_a_song_keeps_its_guitarist():
    chords = ["E5", "G5"]
    assert rg.choose_plan(chords, notes_of, 120, "a") == rg.choose_plan(chords, notes_of, 120, "a")


def test_songs_full_of_sevenths_get_full_harmony():
    chords = ["Am7", "D7", "Gmaj7", "Cmaj7"]
    parts = {rg.choose_plan(chords, notes_of, 120, f"song{n}").part for n in range(40)}
    assert parts <= {"strum", "arena", "stabs"}


def test_fast_songs_drive_and_slow_songs_breathe():
    chords = ["E5", "G5"]
    fast = {rg.choose_plan(chords, notes_of, 160, f"s{n}").part for n in range(30)}
    slow = {rg.choose_plan(chords, notes_of, 76, f"s{n}").part for n in range(30)}
    assert "chug" in fast and "arena" not in fast
    assert "arena" in slow and "chug" not in slow


def test_each_part_really_plays_differently():
    rhythm = {p: tuple((s.beat, s.kind, len(s.pitches)) for s in bar(p, chorus=False, tone="crunch")) for p in rg.PARTS}
    assert len(set(rhythm.values())) == len(rg.PARTS)


@pytest.mark.parametrize("part", rg.PARTS)
@pytest.mark.parametrize("chorus", [False, True])
def test_every_part_keeps_time_and_stays_out_of_the_melody(part, chorus):
    for chord in ("E5", "Am7", "F#m7b5", "Bb", "C#m", "Gmaj7", "Dsus4"):
        for index in range(12):
            strokes = bar(part, chord, chorus=chorus, index=index)
            assert strokes
            for s in strokes:
                assert 0.0 <= s.beat < 4.0 and s.beat + s.beats <= 4.0 + 1e-6
                assert max(s.pitches) <= rg.TOP_NOTE and min(s.pitches) >= rg.ROOT_LOW
                assert s.velocity > 0


@pytest.mark.parametrize("part", ["chug", "boogie", "strum", "arena", "stabs"])
def test_a_rest_in_the_chart_stays_silent(part):
    strokes = bar(part, segments=[(0.0, 2.0, "E5"), (2.0, 4.0, None)])
    assert strokes and all(s.beat < 2.0 for s in strokes)


@pytest.mark.parametrize("part", rg.PARTS)
def test_a_split_bar_changes_chord_on_time(part):
    strokes = bar(part, segments=[(0.0, 2.0, "E5"), (2.0, 4.0, "A5")], chorus=True)
    assert any(s.beat >= 2.0 for s in strokes)
    assert all(s.beat + s.beats <= 2.0 + 1e-6 for s in strokes if s.beat < 2.0)


@pytest.mark.parametrize("part", rg.PARTS)
def test_bars_vary_or_are_reproducible(part):
    a = [tuple((s.beat, s.kind, s.pitches) for s in bar(part, index=i)) for i in range(16)]
    assert a == [tuple((s.beat, s.kind, s.pitches) for s in bar(part, index=i)) for i in range(16)]


def test_a_new_song_plays_a_different_part_of_the_same_kind():
    a = [tuple((s.beat, s.kind) for s in bar("chug", index=i, seed="one")) for i in range(16)]
    b = [tuple((s.beat, s.kind) for s in bar("chug", index=i, seed="two")) for i in range(16)]
    assert a != b


def test_pickups_come_at_phrase_ends_on_no_fixed_schedule():
    got = [any(len(s.pitches) == 1 and s.beat == 2.5 and s.kind == "open" for s in bar("chug", phrase_end=True, index=i)) for i in range(60)]
    assert 10 < sum(got) < 50


def test_a_section_end_always_leads_out():
    for i in range(10):
        assert any(s.beat == 2.5 and len(s.pitches) == 1 for s in bar("chug", section_end=True, index=i))


def test_a_verse_chug_is_palm_muted_and_a_chorus_rings():
    verse = [s for i in range(16) for s in bar("chug", index=i)]
    chorus = [s for i in range(16) for s in bar("chug", index=i, chorus=True, tone="overdrive")]
    assert sum(s.kind == "mute" for s in verse) > 0.7 * len(verse)
    assert all(s.kind == "open" for s in chorus)


def test_strumming_goes_both_ways_and_upstrokes_catch_the_thin_strings():
    strokes = bar("strum", "Am7", chorus=True)
    downs = [s for s in strokes if not s.up and s.kind == "open"]
    ups = [s for s in strokes if s.up and s.kind == "open"]
    assert downs and ups
    assert all(len(s.pitches) == 3 for s in ups)
    assert max(len(s.pitches) for s in downs) >= 4


def test_clean_picking_is_single_ringing_notes():
    strokes = bar("arena", "Am7", tone="clean")
    assert all(len(s.pitches) == 1 for s in strokes)
    assert len({s.pitches for s in strokes}) >= 3


# --- Chord shapes. ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("pc", range(12))
def test_power_chords_sit_low(pc):
    root = rg.power_root(pc)
    assert root % 12 == pc and rg.ROOT_LOW <= root <= rg.ROOT_HIGH


@pytest.mark.parametrize("chord,fifth", [("E5", 7), ("Am7", 7), ("F#m7b5", 6), ("Bdim", 6), ("Caug", 8), ("G7", 7)])
def test_a_chords_own_fifth_is_kept(chord, fifth):
    shape = rg.chord_shape(notes_of(chord))
    assert shape.power[1] - shape.power[0] == fifth


@pytest.mark.parametrize("chord", ["C", "Am", "Dm7", "G7", "Fmaj7", "Bbm", "Dsus4", "E7"])
def test_a_full_chord_is_the_charts_chord(chord):
    shape = rg.chord_shape(notes_of(chord))
    want = {n % 12 for n in notes_of(chord)[:4]}
    assert {p % 12 for p in shape.full} <= want | {notes_of(chord)[0] % 12}
    assert len({p % 12 for p in shape.full}) >= 3
    assert max(shape.full) <= rg.TOP_NOTE


def test_major_and_minor_shapes_differ_where_a_power_chord_would_not():
    assert rg.chord_shape(notes_of("C")).power == rg.chord_shape(notes_of("Cm")).power
    assert rg.chord_shape(notes_of("C")).full != rg.chord_shape(notes_of("Cm")).full


# --- The amp. --------------------------------------------------------------------------------------------


def tone_of(name, midi=40, seconds=1.0, gain=1.0):
    x = np.zeros(int(SR * (seconds + 0.2)), dtype=np.float32)
    rg._guitar().add_note(x, SR, 0.02, seconds, midi, gain, 0.8, "amp")
    return amp.amplify(x, name, SR)


def top_share(y, lo=1000, hi=5000):
    sp, f = np.abs(np.fft.rfft(y)) ** 2, np.fft.rfftfreq(len(y), 1 / SR)
    return float(sp[(f > lo) & (f < hi)].sum() / sp.sum())


@pytest.mark.parametrize("tone", amp.TONES)
def test_the_amp_keeps_length_and_silence(tone):
    assert np.max(np.abs(amp.amplify(np.zeros(SR // 2, dtype=np.float32), tone, SR))) < 1e-6
    assert len(amp.amplify(np.zeros(1234, dtype=np.float32), tone, SR)) == 1234


def test_more_gain_means_more_harmonics_and_more_sustain():
    shares = {t: top_share(tone_of(t)) for t in amp.TONES}
    assert shares["clean"] < shares["crunch"] < shares["distorted"]
    for t in ("clean", "distorted"):
        y = tone_of(t, seconds=2.0)
        early, late = y[int(0.1 * SR) : int(0.3 * SR)], y[int(1.6 * SR) : int(1.9 * SR)]
        ratio = np.sqrt(np.mean(late ** 2) / np.mean(early ** 2))
        if t == "clean":
            clean_ratio = ratio
    assert ratio > clean_ratio


def test_tones_sit_at_similar_levels():
    levels = [float(np.sqrt(np.mean(tone_of(t)[int(0.05 * SR) : int(0.5 * SR)] ** 2))) for t in amp.TONES]
    assert max(levels) / min(levels) < 3.0


def test_a_harder_stroke_breaks_up_more_through_the_same_amp():
    soft, hard = tone_of("crunch", gain=0.25), tone_of("crunch", gain=1.0)
    assert top_share(hard) > top_share(soft)


def test_the_speaker_removes_fizz_and_lows():
    ir = amp.speaker_ir("closed", SR)
    h = np.abs(np.fft.rfft(ir, 8192))
    f = np.fft.rfftfreq(8192, 1 / SR)
    at = lambda hz: h[np.argmin(np.abs(f - hz))]
    assert at(10000) < 0.05 * at(1000)
    assert at(40) < 0.3 * at(150)
    assert at(2450) > at(1000)


def test_clipping_does_not_fold_much_junk_below_the_note():
    t = np.arange(SR) / SR
    x = (0.5 * np.sin(2 * np.pi * 110.0 * t)).astype(np.float32)
    y = amp.amplify(x, "distorted", SR)[SR // 4 :]
    sp, f = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2, np.fft.rfftfreq(len(y), 1 / SR)
    below = sp[(f > 20) & (f < 100)].sum()
    assert below < 0.02 * sp.sum()


# --- The hands. ------------------------------------------------------------------------------------------


def test_a_palm_mute_is_short_and_dark():
    inst = rg._guitar()
    name = inst.zones[1]["layers"][1]["takes"][0]["file"]
    plain, palm = inst._audio(name), inst._audio(name, "palm")
    assert len(palm) < 0.5 * SR
    a = plain[: len(palm)].astype(np.float32)
    b = palm.astype(np.float32)
    assert top_share(b, 1200, 5000) < 0.5 * top_share(a, 1200, 5000)
    assert np.sqrt(np.mean(b[int(0.3 * SR) :] ** 2)) < 0.25 * np.sqrt(np.mean(b[: int(0.05 * SR)] ** 2))


def test_two_strokes_of_the_same_chord_are_never_identical():
    part = rg.GuitarPart(SR * 3, SR, plan("chug"))
    stroke = rg.Stroke(0.0, 1.0, (40, 47, 52), 0.9)
    a, b = np.zeros(SR, dtype=np.float32), np.zeros(SR, dtype=np.float32)
    part._play(a, stroke, 0.1, 0.5, 1.0, "a")
    part._play(b, stroke, 0.1 + 0.0, 0.5, 1.0, "b")
    assert not np.allclose(a, b, atol=1e-3)


def test_a_downstroke_starts_on_the_low_string_and_an_upstroke_on_a_high_one():
    part = rg.GuitarPart(SR, SR, plan("chug"))
    calls = []
    inst = rg._guitar()
    original = inst.add_note
    inst.add_note = lambda bus, sr, at, held, midi, *a, **k: calls.append((at, midi))
    try:
        part._play(np.zeros(SR, dtype=np.float32), rg.Stroke(0.0, 0.2, (40, 47, 52), 0.5), 0.1, 0.5, 1.0, "a")
        down = list(calls)
        calls.clear()
        part._play(np.zeros(SR, dtype=np.float32), rg.Stroke(0.0, 0.2, (40, 47, 52), 0.5, up=True), 0.1, 0.5, 1.0, "a")
        up = list(calls)
    finally:
        del inst.add_note
    assert original is not None
    assert [m for _t, m in down] == [40, 47, 52]
    assert [m for _t, m in up] == [52, 47, 40]
    assert down[1][0] > down[0][0] and down[2][0] > down[1][0]


def test_a_note_offset_and_detune_change_the_sound_but_not_the_length_much():
    inst = rg._guitar()
    a, b = np.zeros(SR, dtype=np.float32), np.zeros(SR, dtype=np.float32)
    inst.add_note(a, SR, 0.0, 0.5, 40, 1.0, 0.6, "x")
    inst.add_note(b, SR, 0.0, 0.5, 40, 1.0, 0.6, "x", offset_sec=0.003, detune_cents=5.0)
    assert not np.allclose(a, b, atol=1e-3)
    assert abs(int(np.count_nonzero(a)) - int(np.count_nonzero(b))) < 200


def test_only_used_tones_make_a_bus_and_silent_songs_stay_silent():
    part = rg.GuitarPart(SR, SR, plan("chug"))
    assert not part.finish().any()
    assert part.buses == {}


def test_a_long_note_at_the_end_is_cut_cleanly():
    part = rg.GuitarPart(SR // 2, SR, plan("chug"))
    part.play_bar([rg.Stroke(0.0, 4.0, (40, 47), 0.9)], 0.4, 0.5, "crunch", 2.0, double=True)
    assert len(part.finish()) == SR // 2


def test_a_recording_never_repeats_the_same_take_in_a_row():
    inst = SampledInstrument(rg.GUITAR_PACK)
    zone, avoid, last = inst._zone(40), {}, {}
    for n in range(100):
        take = inst._take(zone, 0.6, f"s{n}", avoid)
        layer = next(la["velocity"] for la in zone["layers"] if take in la["takes"])
        assert last.get(layer) != take["file"]
        last[layer] = take["file"]


# --- In the engine. --------------------------------------------------------------------------------------


def test_rock_differs_when_on_and_repeats_exactly(monkeypatch):
    monkeypatch.delenv("MUSIC_ROCK_GUITAR", raising=False)
    today = render()
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    one, two = render(), render()
    assert not np.array_equal(today, one)
    assert np.array_equal(one, two)
    assert np.isfinite(one).all() and np.max(np.abs(one)) <= 1.0


def test_songs_differ_with_the_same_chords(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    assert not np.array_equal(render(title="First Song"), render(title="Second Song"))


@pytest.mark.parametrize("style", ["Pop groove", "Jazz swing", "Funk groove", "Blues groove"])
def test_other_styles_are_untouched(monkeypatch, style):
    monkeypatch.delenv("MUSIC_ROCK_GUITAR", raising=False)
    today = render(style)
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    assert np.array_equal(today, render(style))


def test_a_no_chord_bar_has_no_guitar(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    played = []
    original = rg.GuitarPart.play_bar
    monkeypatch.setattr(rg.GuitarPart, "play_bar", lambda self, strokes, bar_start, *a, **k: (played.append(bar_start), original(self, strokes, bar_start, *a, **k))[1])
    render(chart=sec("Verse 1", ["E5", "N.C.", "A5", "A5"]))
    assert played == [0.0, 4.0, 6.0]


def test_the_keys_layer_stays_the_keys_and_the_guitar_is_its_own(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    a, _ = ba.synthesize_chords_to_numpy(FORM, bpm=120, loops=1, sr=SR, style="Rock groove", level="Intermediate", song_title="L", layers=("guitar",))
    assert np.max(np.abs(np.asarray(a))) > 0.1
    k, _ = ba.synthesize_chords_to_numpy(FORM, bpm=120, loops=1, sr=SR, style="Rock groove", level="Intermediate", song_title="L", layers=("keys",))
    assert not np.array_equal(np.asarray(a), np.asarray(k))


def test_a_song_costs_little_memory(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    sc.SHARED.clear()
    render()
    assert 0 < sc.SHARED.bytes < 36 * 1024 * 1024
    assert all(v.dtype == np.int16 for v in sc.SHARED._items.values())


def test_a_power_chord_has_no_third_in_any_part():
    shape = rg.chord_shape(notes_of("E5"))
    assert 8 not in {p % 12 for p in shape.full + shape.high + shape.wide}
