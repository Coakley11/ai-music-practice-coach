"""Rock guitar from recordings: off by default, follows the chart and its sections, varied, and light on memory."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_rock_guitar as rg
import backing_sample_cache as sc

SR = 44100
ROOTS = {"E5": 4, "A5": 9, "C5": 0, "Bdim": 11}


def sec(name, chords):
    return [{"chord": c, "section": name, "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]


FORM = sec("Verse 1", ["E5", "G5", "A5", "A5", "E5", "G5", "C5", "B5"]) + sec("Chorus", ["A5", "C5", "G5", "D5"])


def render(style="Rock groove", chart=FORM):
    a, _ = ba.synthesize_chords_to_numpy(chart, bpm=120, loops=1, sr=SR, style=style, level="Intermediate", song_title="Guitar Test")
    return np.asarray(a, dtype=np.float32)


def bar(tone, chord="E5", *, segments=None, phrase_end=False, section_end=False, index=1, seed="s", next_chord="A5"):
    return rg.rock_guitar_bar(
        segments or [(0.0, 4.0, chord)], 4, tone=tone, fifth_of=ba._power_chord_fifth, root_of=lambda c: ba.chord_notes(c)[0],
        next_chord=next_chord, phrase_end=phrase_end, section_end=section_end, seed=seed, bar_index=index,
    )


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
    files = [t["file"] for z in manifest["zones"] for la in z["layers"] for t in la["takes"]] + [d["file"] for d in manifest["dead"]]
    assert files and all((rg.GUITAR_PACK / f).is_file() for f in files)
    assert "CC0" in (rg.GUITAR_PACK / "LICENSE").read_text(encoding="utf-8")
    assert sum(p.stat().st_size for p in rg.GUITAR_PACK.iterdir()) < 8 * 1024 * 1024


@pytest.mark.parametrize("pc", range(12))
def test_power_chords_sit_low(pc):
    root = rg.power_root(pc)
    assert root % 12 == pc and rg.ROOT_LOW <= root <= rg.ROOT_HIGH
    assert rg.power_chord(pc) == (root, root + 7)
    assert rg.power_chord(pc, wide=True) == (root, root + 7, root + 12)


@pytest.mark.parametrize("chord,fifth", [("E5", 7), ("Am7", 7), ("F#m7b5", 6), ("Bdim", 6), ("Caug", 8), ("G7", 7)])
def test_a_chords_own_fifth_is_kept(chord, fifth):
    assert ba._power_chord_fifth(chord) == fifth


@pytest.mark.parametrize("tone", ["clean", "crunch", "overdrive"])
def test_every_stroke_is_the_charts_chord_and_leaves_the_melody_range_clear(tone):
    for chord, pc in ROOTS.items():
        for index in range(30):
            strokes = bar(tone, chord, index=index)
            assert strokes
            assert max(max(s.pitches) for s in strokes) <= rg.ROOT_HIGH + 12
            whole = [s for s in strokes if len(s.pitches) >= 2]
            assert whole and all(s.pitches[0] % 12 == pc for s in whole)


def test_a_verse_is_mostly_palm_muted_and_a_chorus_rings():
    verse = [s for i in range(16) for s in bar("crunch", index=i)]
    chorus = [s for i in range(16) for s in bar("overdrive", index=i)]
    assert sum(s.kind == "mute" for s in verse) > 0.7 * len(verse)
    assert sum(s.kind == "open" for s in chorus) > 0.7 * len(chorus)


def test_a_quiet_section_is_a_clean_held_chord():
    strokes = bar("clean")
    assert len(strokes) == 1 and strokes[0].kind == "open" and strokes[0].beats == 4.0


def test_sections_choose_their_tone():
    assert rg.section_tone("verse", False) == "crunch"
    assert rg.section_tone("chorus", False) == "overdrive"
    assert rg.section_tone("chorus", True) == "clean"
    assert rg.section_tone("bridge", True) == "clean"


def test_bars_change_and_repeat_exactly():
    a = [tuple((s.beat, s.kind) for s in bar("overdrive", index=i)) for i in range(16)]
    assert len(set(a)) >= 3
    assert a == [tuple((s.beat, s.kind) for s in bar("overdrive", index=i)) for i in range(16)]


def test_a_new_song_plays_a_different_part():
    a = [tuple((s.beat, s.kind) for s in bar("crunch", index=i, seed="one")) for i in range(16)]
    b = [tuple((s.beat, s.kind) for s in bar("crunch", index=i, seed="two")) for i in range(16)]
    assert a != b


def test_riffs_come_at_phrase_ends_on_no_fixed_schedule():
    with_riff = [any(len(s.pitches) == 1 and s.beat == 2.5 and s.kind == "open" for s in bar("crunch", phrase_end=True, index=i)) for i in range(60)]
    assert 10 < sum(with_riff) < 50
    assert not any(s.kind == "open" and len(s.pitches) == 1 for s in bar("crunch", phrase_end=False, index=1))


def test_a_section_end_always_leads_out():
    for i in range(10):
        assert any(s.beat == 2.5 and len(s.pitches) == 1 for s in bar("crunch", section_end=True, index=i))


def test_a_split_bar_changes_chord_on_time():
    strokes = bar("overdrive", segments=[(0.0, 2.0, "E5"), (2.0, 4.0, "A5")])
    assert all(s.pitches[0] % 12 == (4 if s.beat < 2.0 else 9) for s in strokes)
    assert all(s.beat + s.beats <= (2.0 if s.beat < 2.0 else 4.0) + 1e-6 for s in strokes)


def test_a_rest_in_the_chart_stays_silent():
    strokes = bar("crunch", segments=[(0.0, 2.0, "E5"), (2.0, 4.0, None)])
    assert strokes and all(s.beat < 2.0 for s in strokes)


def test_silence_stays_silence_through_the_amp():
    assert not rg.GuitarPart(SR, SR, "x").finish().any()


def test_harder_drive_means_a_denser_sound_at_a_similar_level():
    levels, crest = {}, {}
    for tone in ("clean", "crunch", "overdrive"):
        part = rg.GuitarPart(SR * 4, SR, "x")
        part.play_bar([rg.Stroke(0.0, 4.0, (40, 47, 52), 0.9)], 0.0, 0.5, tone, 2.0, double=False)
        y = part.finish()[: SR]
        levels[tone] = float(np.sqrt(np.mean(y ** 2)))
        crest[tone] = float(np.max(np.abs(y))) / levels[tone]
    assert crest["overdrive"] < crest["clean"]
    assert max(levels.values()) / min(levels.values()) < 4.0


def test_the_amp_adds_upper_harmonics():
    tops = {}
    for tone in ("clean", "overdrive"):
        part = rg.GuitarPart(SR * 2, SR, "x")
        part.play_bar([rg.Stroke(0.0, 2.0, (40,), 0.9)], 0.0, 0.5, tone, 1.0, double=False)
        y = part.finish()[: SR]
        sp, f = np.abs(np.fft.rfft(y)) ** 2, np.fft.rfftfreq(len(y), 1 / SR)
        tops[tone] = sp[(f > 1000) & (f < 5000)].sum() / sp.sum()
    assert tops["overdrive"] > 2 * tops["clean"]


def test_a_long_note_at_the_end_is_cut_cleanly():
    part = rg.GuitarPart(SR // 2, SR, "x")
    part.play_bar([rg.Stroke(0.0, 4.0, (40, 47), 0.9)], 0.4, 0.5, "crunch", 2.0, double=True)
    assert len(part.finish()) == SR // 2


def test_a_recording_never_repeats_the_same_take_in_a_row():
    from backing_sampled_instrument import SampledInstrument

    inst = SampledInstrument(rg.GUITAR_PACK)
    zone, avoid, last = inst._zone(40), {}, {}
    for n in range(100):
        take = inst._take(zone, 0.6, f"s{n}", avoid)
        layer = next(la["velocity"] for la in zone["layers"] if take in la["takes"])
        assert last.get(layer) != take["file"]
        last[layer] = take["file"]


def test_rock_differs_when_on_and_repeats_exactly(monkeypatch):
    monkeypatch.delenv("MUSIC_ROCK_GUITAR", raising=False)
    today = render()
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    one, two = render(), render()
    assert not np.array_equal(today, one)
    assert np.array_equal(one, two)
    assert np.isfinite(one).all() and np.max(np.abs(one)) <= 1.0


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


def test_a_song_costs_little_memory(monkeypatch):
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")
    sc.SHARED.clear()
    render()
    assert 0 < sc.SHARED.bytes < 24 * 1024 * 1024
    assert all(v.dtype == np.int16 for v in sc.SHARED._items.values())
