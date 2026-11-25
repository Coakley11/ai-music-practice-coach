"""The recorded tenor saxophone (backing_horns): off by default, in range, no clicks, smooth guide tones."""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

import backing_horns as bh
import backing_sample_cache

ROOT = pathlib.Path(__file__).resolve().parents[1]
SR = 44100


@pytest.fixture
def horns_on(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    yield


# --- The switch -------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "0", "off", "false", "no", "maybe"])
def test_switch_off_plays_nothing_and_loads_nothing(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("MUSIC_HORNS", raising=False)
    else:
        monkeypatch.setenv("MUSIC_HORNS", value)
    bh._pack.cache_clear()
    before = {k for k in backing_sample_cache.SHARED._items if "tenor_sax" in str(k[0])}
    assert not bh.enabled()
    assert bh.horns_renderer_tag() == ""
    assert bh.render_line([bh.HornNote(0.0, 1.0, 60)]) is None
    assert bh.render_horn_background(["Cm7", "F7", "Bbmaj7"], 4, 120) is None
    assert bh._pack.cache_info().currsize == 0  # the recordings were never opened
    after = {k for k in backing_sample_cache.SHARED._items if "tenor_sax" in str(k[0])}
    assert after == before


@pytest.mark.parametrize("value", ["1", "on", "true", "tenor", "recorded"])
def test_switch_on_values(monkeypatch, value):
    monkeypatch.setenv("MUSIC_HORNS", value)
    assert bh.enabled()
    assert bh.horns_renderer_tag() == "+horns-tenor1"


def test_engine_and_ensembles_do_not_use_the_horns():
    """This slice adds an instrument; no existing render, renderer list or ensemble changes."""
    import backing_performance_plan as pp

    for name in ("backing_audio.py", "backing_performance_plan.py", "backing_sound_status.py"):
        assert "backing_horns" not in (ROOT / name).read_text(encoding="utf-8")
    assert "horns" not in pp.RENDERABLE_ROLES
    assert "horns" in pp.ENSEMBLES["Jazz quartet"].missing
    assert all("horns" not in spec.roles for spec in pp.ENSEMBLES.values())


# --- The pack ---------------------------------------------------------------------------------------


def test_pack_is_small_licensed_mono_flac():
    import soundfile as sf

    manifest = json.loads((bh.HORN_PACK / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sr"] == SR
    assert "CC0" in manifest["source"]
    assert "CC0 1.0 Universal" in (bh.HORN_PACK / "LICENSE").read_text(encoding="utf-8")
    files = {t["file"] for z in manifest["zones"] + manifest["articulations"]["staccato"] for la in z["layers"] for t in la["takes"]}
    assert len(files) == 48
    for name in files:
        info = sf.info(str(bh.HORN_PACK / name))
        assert (info.format, info.subtype, info.channels, info.samplerate) == ("FLAC", "PCM_16", 1, SR)
    total = sum(p.stat().st_size for p in bh.HORN_PACK.iterdir())
    assert total <= 8 * 1024 * 1024


def test_recorded_range_is_the_tenors_concert_range():
    manifest = json.loads((bh.HORN_PACK / "manifest.json").read_text(encoding="utf-8"))
    keys = [z["key"] for z in manifest["zones"]] + [z["key"] for z in manifest["articulations"]["staccato"]]
    assert (min(keys), max(keys)) == (bh.TENOR_LOW, bh.TENOR_HIGH) == bh.pack_range() == (44, 76)  # Ab2-E5
    takes = [t for z in manifest["zones"] + manifest["articulations"]["staccato"] for la in z["layers"] for t in la["takes"]]
    assert all(abs(t["cents"]) < 15 for t in takes)


# --- Range and articulation -------------------------------------------------------------------------


@pytest.mark.parametrize("midi, expected", [(44, 44), (76, 76), (43, 55), (30, 54), (77, 65), (88, 76), (100, 76), (60, 60)])
def test_clamp_to_range_keeps_the_pitch_class(midi, expected):
    out = bh.clamp_to_range(midi)
    assert out == expected
    assert bh.TENOR_LOW <= out <= bh.TENOR_HIGH and out % 12 == midi % 12


def test_articulation_follows_note_length():
    assert bh.choose_articulation(0.1) == "staccato"
    assert bh.choose_articulation(bh.STACCATO_MAX_SEC) == "staccato"
    assert bh.choose_articulation(bh.STACCATO_MAX_SEC + 0.01) == "sustain"
    assert bh.choose_articulation(2.0) == "sustain"


def test_short_note_plays_a_staccato_recording(horns_on, monkeypatch):
    used = []
    real = bh.SampledInstrument._audio

    def spy(self, name, variant=None):
        used.append(name)
        return real(self, name, variant)

    monkeypatch.setattr(bh.SampledInstrument, "_audio", spy)
    bh.render_line([bh.HornNote(0.0, 0.15, 60)], SR)
    bh.render_line([bh.HornNote(0.0, 1.5, 60)], SR)
    assert used[0].startswith("stac_") and used[1].startswith("sus_")


def test_out_of_range_note_still_sounds_in_range(horns_on):
    y = bh.render_line([bh.HornNote(0.0, 0.8, 90)], SR, gain=1.0)  # E6 -> E5
    assert y is not None and np.abs(y).max() > 0.01


# --- Envelopes and level ----------------------------------------------------------------------------


@pytest.mark.parametrize("dur", [0.12, 0.25, 0.8, 2.0, 4.5])
@pytest.mark.parametrize("midi", [44, 57, 66, 76])
def test_notes_start_and_end_without_a_click(horns_on, midi, dur):
    start = 0.05
    y = bh.render_line([bh.HornNote(start, dur, midi, 0.8)], SR, gain=1.0)
    s = int(start * SR)
    peak = float(np.abs(y).max())
    assert peak > 0.01
    assert np.all(y[:s] == 0.0)
    assert abs(y[s]) < 1e-3 and np.abs(y[s : s + 10]).max() < 0.05 * peak  # a fade-in, not a step
    nz = np.nonzero(y)[0]
    last = int(nz[-1])
    assert np.abs(y[last - 10 : last + 1]).max() < 0.02 * peak  # the release reaches silence
    art = bh.choose_articulation(dur)
    assert last <= s + int((dur + bh.RELEASE_SEC[art]) * SR) + 1  # and stops where it should


def test_long_sustain_continues_past_the_recording_smoothly(horns_on):
    y = bh.render_line([bh.HornNote(0.0, 6.0, 62, 0.7)], SR, gain=1.0)
    w = int(0.02 * SR)
    env = np.array([np.sqrt(np.mean(y[k : k + w] ** 2)) for k in range(int(0.4 * SR), int(5.9 * SR), w)])
    db = 20 * np.log10(env / np.median(env))
    assert db.min() > -4.0 and db.max() < 4.0  # no hole or bump where the loop joins


def test_velocity_sets_layer_and_level(horns_on, monkeypatch):
    used = []
    real = bh.SampledInstrument._audio
    monkeypatch.setattr(bh.SampledInstrument, "_audio", lambda self, name, variant=None: used.append(name) or real(self, name, variant))
    soft = bh.render_line([bh.HornNote(0.0, 0.2, 62, 0.3)], SR, gain=1.0)
    loud = bh.render_line([bh.HornNote(0.0, 0.2, 62, 0.95)], SR, gain=1.0)
    assert used == ["stac_62_v1.flac", "stac_62_v2.flac"]
    assert np.sqrt(np.mean(loud**2)) > 1.5 * np.sqrt(np.mean(soft**2))
    pads = [bh.render_line([bh.HornNote(0.0, 1.0, 62, v)], SR, gain=1.0) for v in (0.4, 0.9)]
    assert np.sqrt(np.mean(pads[1] ** 2)) > 1.5 * np.sqrt(np.mean(pads[0] ** 2))


# --- Breathing --------------------------------------------------------------------------------------


def test_one_player_never_overlaps_and_breathes_in_a_long_phrase():
    notes = [bh.HornNote(i * 1.0, 1.2, 60 + (i % 3)) for i in range(14)]  # overlapping, 14 s without a gap
    out = bh.breathe(notes)
    gaps = [b.start_sec - (a.start_sec + a.dur_sec) for a, b in zip(out, out[1:])]
    assert min(gaps) >= bh.TONGUE_GAP_SEC - 1e-9
    assert any(g >= bh.BREATH_SEC - 1e-9 for g in gaps)
    # No stretch longer than a phrase without a breath.
    phrase_start = out[0].start_sec
    for a, b in zip(out, out[1:]):
        if b.start_sec - (a.start_sec + a.dur_sec) >= bh.BREATH_SEC - 1e-9:
            phrase_start = b.start_sec
        assert (a.start_sec + a.dur_sec) - phrase_start <= bh.MAX_PHRASE_SEC + 1.0


def test_two_voices_breathe_on_their_own():
    notes = [bh.HornNote(0.0, 2.0, 63, voice=0), bh.HornNote(0.0, 2.0, 58, voice=1)]
    assert len(bh.breathe(notes)) == 2  # a second player is not an overlap


# --- Parts ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chords, largest_step",
    [
        (["Cm7", "F7", "Bbmaj7", "Bbmaj7"], 2),
        # Cmaj7 -> Em7b5: the lower voice of a pair has no guide tone nearer than a minor third.
        (["Dm7", "G7", "Cmaj7", "Cmaj7", "Em7b5", "A7", "Dm7", "G7"], 3),
        (["Em7b5", "A7", "Dm7", "G7", "Cm7", "F7", "Bbmaj7", "Ebmaj7"], 2),
        # Cmaj7 -> A7 and C7 -> A7 have no guide tone nearer than a minor third.
        (["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"], 3),
        (["C7", "F7", "C7", "C7", "F7", "F7", "C7", "A7", "Dm7", "G7", "C7", "G7"], 3),
    ],
)
@pytest.mark.parametrize("voices", [1, 2])
def test_guide_tone_line_moves_by_small_steps(chords, largest_step, voices):
    line = bh.guide_tone_line(chords, voices=voices)
    assert len(line) == len(chords) and all(len(p) == voices for p in line)
    for chord, pitches in zip(chords, line):
        assert {p % 12 for p in pitches} <= set(bh.guide_tones(chord))  # 3rds and 7ths only
        assert all(bh.TENOR_LOW <= p <= bh.TENOR_HIGH for p in pitches)
        if voices == 2:
            assert pitches[1] < pitches[0]
    for v in range(voices):
        steps = [abs(b[v] - a[v]) for a, b in zip(line, line[1:])]
        assert max(steps) <= largest_step, (chords, v, steps)


def test_ii_v_i_in_bb_resolves_seventh_to_third():
    # Cm7 -> F7 -> Bbmaj7: Eb (3rd of Cm7) is F7's 7th and falls a half step to D, Bbmaj7's 3rd.
    assert [p[0] for p in bh.guide_tone_line(["Cm7", "F7", "Bbmaj7"])] == [63, 63, 62]


def test_sustained_background_ties_and_breathes():
    tl = bh.chord_timeline(["Cm7", "F7", "Bbmaj7", "Bbmaj7"], 8, 120)
    notes = bh.sustained_background(tl)
    assert all(n.articulation == "sustain" for n in notes)
    assert [(round(n.start_sec, 3), n.midi) for n in notes] == [(0.0, 63), (4.0, 62), (8.0, 63), (12.0, 62)]
    for a, b in zip(notes, notes[1:]):
        gap = b.start_sec - (a.start_sec + a.dur_sec)
        assert gap >= bh.TONGUE_GAP_SEC - 1e-9
        if abs(b.start_sec % 8.0) < 1e-9:  # a four-bar phrase ends here
            assert gap >= bh.BREATH_SEC - 1e-9


def test_staccato_hits_on_and_of_two_and_four():
    tl = bh.chord_timeline(["Cm7", "F7"], 2, 120)
    notes = bh.staccato_hits(tl)
    assert [round(n.start_sec, 3) for n in notes] == [0.75, 1.5, 2.75, 3.5]
    assert all(n.articulation == "staccato" and n.dur_sec <= bh.STACCATO_MAX_SEC for n in notes)


def test_chord_timeline_with_beats_and_repeats():
    tl = bh.chord_timeline([("Dm7", 2), ("G7", 2), "Cmaj7"], 4, 120)
    assert [(s.chord, s.beats) for s in tl] == [("Dm7", 2), ("G7", 2), ("Cmaj7", 4), ("Dm7", 2), ("G7", 2), ("Cmaj7", 4)]
    assert tl[-1].start_sec + tl[-1].dur_sec == pytest.approx(8.0)


@pytest.mark.parametrize("part, voices", [("pads", 1), ("pads", 2), ("hits", 2)])
def test_background_render_does_not_clip(horns_on, part, voices):
    y = bh.render_horn_background(["Cm7", "F7", "Bbmaj7", "Bbmaj7"], 4, 120, part=part, voices=voices)
    assert y is not None and y.dtype == np.float32
    assert len(y) == int((4 * 4 * 0.5 + 0.6) * SR)
    peak = float(np.abs(y).max())
    assert 0.02 < peak < 0.9
    assert y[0] == 0.0 and abs(y[-1]) < 1e-6
