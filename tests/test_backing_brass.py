"""The recorded trombone and trumpet (backing_horns): CC0 packs, real ranges, articulations, clean envelopes,
two-horn voicing - and the tenor sax exactly as it was."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import numpy as np
import pytest

import backing_horns as bh
import backing_sample_cache

SR = 44100
BRASS = ("trombone", "trumpet")
JAZZ = {
    "ii-V-I": ["Cm7", "F7", "Bbmaj7", "Bbmaj7"],
    "turnaround": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
    "blues": ["F7", "Bb7", "F7", "F7", "Bb7", "Bb7", "F7", "D7", "Gm7", "C7", "F7", "C7"],
    "minor": ["Em7b5", "A7", "Dm7", "G7", "Cm7", "F7", "Bbmaj7", "Ebmaj7"],
    "rhythm": ["Bbmaj7", "G7", "Cm7", "F7", "Dm7", "G7", "Cm7", "F7", "Fm7", "Bb7", "Ebmaj7", "Ab7"],
}
SECTIONS = [("trumpet", "tenor"), ("tenor", "trombone"), ("trumpet", "trombone")]


@pytest.fixture
def horns_on(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    yield


def _manifest(name):
    return json.loads((bh.horn(name).pack / "manifest.json").read_text(encoding="utf-8"))


def _takes(manifest):
    return [t for z in manifest["zones"] + manifest["articulations"]["staccato"] for la in z["layers"] for t in la["takes"]]


# --- The packs --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", BRASS)
def test_pack_is_small_licensed_mono_flac(name):
    import soundfile as sf

    pack = bh.horn(name).pack
    manifest = _manifest(name)
    assert manifest["sr"] == SR
    assert "VSCO 2" in manifest["source"] and "CC0" in manifest["source"]
    licence = (pack / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("CC0 1.0 Universal") and "Statement of Purpose" in licence
    readme = (pack / "README.md").read_text(encoding="utf-8")
    assert "sgossner/VSCO-2-CE" in readme and "440300901dfe9275fd84e0b7763af1f8443ae62e" in readme
    files = {t["file"] for t in _takes(manifest)}
    on_disk = {p.name for p in pack.glob("*.flac")}
    assert files == on_disk  # nothing listed is missing, nothing on disk is unlisted
    for f in files:
        info = sf.info(str(pack / f))
        assert (info.format, info.subtype, info.channels, info.samplerate) == ("FLAC", "PCM_16", 1, SR)
    assert sum(p.stat().st_size for p in pack.iterdir()) <= 6 * 1024 * 1024
    assert all(t["source_file"].endswith(".wav") and t["gain"] > 0 for t in _takes(manifest))


@pytest.mark.parametrize(
    "name, low, high, sustain_layers, staccato_layers",
    [("trombone", 41, 67, 2, 2), ("trumpet", 53, 84, 2, 3)],  # concert F2-G4 / F3-C6
)
def test_recorded_range_layers_and_tuning(name, low, high, sustain_layers, staccato_layers):
    manifest = _manifest(name)
    h = bh.horn(name)
    keys = [z["key"] for z in manifest["zones"]] + [z["key"] for z in manifest["articulations"]["staccato"]]
    assert (min(keys), max(keys)) == (h.low, h.high) == bh.pack_range(name) == tuple(manifest["range"]) == (low, high)
    assert {len(z["layers"]) for z in manifest["zones"]} == {sustain_layers}
    assert {len(z["layers"]) for z in manifest["articulations"]["staccato"]} == {staccato_layers}
    # Short notes have two round robins in every layer, so repeated punches alternate recordings.
    assert all(len(la["takes"]) == 2 for z in manifest["articulations"]["staccato"] for la in z["layers"])
    assert all(abs(t["cents"]) < 25 for t in _takes(manifest))
    # No note is more than two semitones from a recording (the player resamples within that).
    for zones in (manifest["zones"], manifest["articulations"]["staccato"]):
        zk = np.array([z["key"] for z in zones])
        assert max(int(np.min(np.abs(zk - m))) for m in range(low, high + 1)) <= 2


def test_tenor_pack_is_untouched():
    manifest = json.loads((bh.HORN_PACK / "manifest.json").read_text(encoding="utf-8"))
    assert len({t["file"] for t in _takes(manifest)}) == 48 and manifest["range"] == [44, 76]
    assert bh.horn("tenor").pack == bh.HORN_PACK


# --- The switch -------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "0", "off"])
def test_switch_off_no_brass_plays_or_loads(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("MUSIC_HORNS", raising=False)
    else:
        monkeypatch.setenv("MUSIC_HORNS", value)
    bh._pack.cache_clear()
    before = set(backing_sample_cache.SHARED._items)
    for name in BRASS:
        assert not bh.available(name)
        assert bh.render_line([bh.HornNote(0.0, 1.0, 60)], instrument=name) is None
        assert bh.render_horn_background(["Cm7", "F7"], 2, 120, instrument=name) is None
    for top, bottom in SECTIONS:
        assert bh.render_section_background(["Cm7", "F7"], 2, 120, top=top, bottom=bottom) is None
    assert bh._pack.cache_info().currsize == 0
    assert set(backing_sample_cache.SHARED._items) == before


def test_a_missing_pack_is_never_offered(horns_on, monkeypatch, tmp_path):
    monkeypatch.setitem(bh.HORNS, "trumpet", dataclasses.replace(bh.HORNS["trumpet"], pack=tmp_path / "nothing"))
    assert bh.enabled() and not bh.available("trumpet")
    assert bh.render_line([bh.HornNote(0.0, 1.0, 70)], instrument="trumpet") is None
    assert bh.render_section_background(["Cm7"], 1, 120, top="trumpet", bottom="tenor") is None


def test_unknown_horn_is_an_error():
    with pytest.raises(ValueError):
        bh.horn("flugelhorn")


def test_no_ensemble_uses_the_brass(monkeypatch):
    import backing_performance_plan as pp

    monkeypatch.setenv("MUSIC_HORNS", "1")
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    assert pp.band_summary(plan) == "Piano, tenor sax, bass, drums"
    for name in pp.ENSEMBLES:
        summary = pp.band_summary(pp.resolve_performance_plan(style="Jazz swing", ensemble=name)).lower()
        assert "trumpet" not in summary and "trombone" not in summary, (name, summary)


# --- Range and articulation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, midi, expected",
    [
        ("trombone", 41, 41), ("trombone", 67, 67), ("trombone", 40, 52), ("trombone", 70, 58), ("trombone", 28, 52),
        ("trumpet", 53, 53), ("trumpet", 84, 84), ("trumpet", 52, 64), ("trumpet", 86, 74), ("trumpet", 40, 64),
    ],
)
def test_clamp_to_each_horns_range(name, midi, expected):
    h = bh.horn(name)
    out = bh.clamp_to_range(midi, h.low, h.high)
    assert out == expected and h.low <= out <= h.high and out % 12 == midi % 12


@pytest.mark.parametrize("name", BRASS)
def test_out_of_range_notes_sound_inside_the_range(horns_on, name, monkeypatch):
    used = []
    real = bh.SampledInstrument._zone
    monkeypatch.setattr(bh.SampledInstrument, "_zone", lambda self, m: used.append(m) or real(self, m))
    h = bh.horn(name)
    y = bh.render_line([bh.HornNote(0.0, 0.8, h.low - 13), bh.HornNote(1.0, 0.8, h.high + 14)], SR, gain=1.0, instrument=name)
    assert y is not None and np.abs(y).max() > 0.01
    assert used and all(h.low <= m <= h.high for m in used)


@pytest.mark.parametrize("name", BRASS)
def test_short_notes_play_staccato_long_notes_sustain(horns_on, monkeypatch, name):
    used = []
    real = bh.SampledInstrument._audio
    monkeypatch.setattr(bh.SampledInstrument, "_audio", lambda self, f, v=None: used.append((self.folder.name, f)) or real(self, f, v))
    bh.render_line([bh.HornNote(0.0, 0.15, 60 if name == "trombone" else 70)], SR, instrument=name)
    bh.render_line([bh.HornNote(0.0, 1.5, 60 if name == "trombone" else 70)], SR, instrument=name)
    assert [u[0] for u in used] == [name, name]
    assert used[0][1].startswith("stac_") and used[1][1].startswith("sus_")


@pytest.mark.parametrize("name", BRASS)
def test_a_held_line_keeps_one_layer_per_dynamic(horns_on, monkeypatch, name):
    """The sustain layers differ in tone: a line at one velocity must not flip between them note by note."""
    used = []
    real = bh.SampledInstrument._audio
    monkeypatch.setattr(bh.SampledInstrument, "_audio", lambda self, f, v=None: used.append(f) or real(self, f, v))
    m = bh.horn(name).background[2]
    for velocity, layer in ((0.6, "soft"), (0.75, "loud"), (0.45, "soft"), (0.9, "loud")):
        used.clear()
        notes = [bh.HornNote(i * 0.5, 0.4, m + (i % 3), velocity, "sustain") for i in range(12)]
        bh.render_line(notes, SR, instrument=name, seed=f"layers-{velocity}")
        soft = {"trombone": ("_v3.flac", "_v2.flac"), "trumpet": ("_v1.flac",)}[name]  # trombone G4: v2 stands in
        assert used and {f.endswith(soft) for f in used} == {layer == "soft"}, (velocity, used)


@pytest.mark.parametrize("name", BRASS)
def test_velocity_sets_the_level(horns_on, name):
    m = bh.horn(name).background[2]
    rms = lambda y: float(np.sqrt(np.mean(y**2)))
    for art, dur in (("staccato", 0.2), ("sustain", 1.0)):
        soft = bh.render_line([bh.HornNote(0.0, dur, m, 0.3, art)], SR, gain=1.0, instrument=name)
        loud = bh.render_line([bh.HornNote(0.0, dur, m, 0.95, art)], SR, gain=1.0, instrument=name)
        assert rms(loud) > 1.5 * rms(soft), art


# --- Envelopes ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("dur", [0.12, 0.25, 0.8, 2.0, 4.5])
@pytest.mark.parametrize("name, midi", [("trombone", 41), ("trombone", 55), ("trombone", 67), ("trumpet", 53), ("trumpet", 68), ("trumpet", 84)])
def test_notes_start_and_end_without_a_click(horns_on, name, midi, dur):
    start = 0.05
    h = bh.horn(name)
    for velocity in (0.4, 0.9):
        y = bh.render_line([bh.HornNote(start, dur, midi, velocity)], SR, gain=1.0, instrument=name)
        s = int(start * SR)
        peak = float(np.abs(y).max())
        assert peak > 0.01
        assert np.all(y[:s] == 0.0)
        assert abs(y[s]) < 1e-3 and np.abs(y[s : s + 10]).max() < 0.05 * peak
        last = int(np.nonzero(y)[0][-1])
        assert np.abs(y[last - 10 : last + 1]).max() < 0.02 * peak
        assert last <= s + int((dur + h.release_sec[bh.choose_articulation(dur)]) * SR) + 1


@pytest.mark.parametrize("name", BRASS)
def test_long_sustains_loop_without_holes(horns_on, name):
    """6 s held notes across the background register: the crossfaded loop neither drops out nor swells."""
    lo, hi, _ = bh.horn(name).background
    w = int(0.02 * SR)
    for m in range(lo, hi + 1, 2):
        for velocity in (0.45, 0.8):
            y = bh.render_line([bh.HornNote(0.0, 6.0, m, velocity)], SR, gain=1.0, instrument=name)
            env = np.array([np.sqrt(np.mean(y[k : k + w] ** 2)) for k in range(int(0.4 * SR), int(5.9 * SR), w)])
            db = 20 * np.log10(env / np.median(env))
            assert db.min() > -5.0 and db.max() < 5.0, (m, velocity, db.min(), db.max())


# --- Voicing ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", BRASS)
def test_single_brass_guide_tone_line_stays_in_its_register(name):
    lo, hi, _ = bh.horn(name).background
    for chords in JAZZ.values():
        line = bh.guide_tone_line(chords, instrument=name)
        assert all(lo <= p[0] <= hi for p in line)
        assert all(p[0] % 12 in bh.guide_tones(c) for c, p in zip(chords, line))
        assert max(abs(b[0] - a[0]) for a, b in zip(line, line[1:])) <= 3


@pytest.mark.parametrize("top, bottom", SECTIONS)
@pytest.mark.parametrize("prog", list(JAZZ))
def test_two_horns_a_third_or_sixth_apart_moving_smoothly(top, bottom, prog):
    import backing_audio
    from backing_pianist import harmony_of

    chords = JAZZ[prog]
    pairs = bh.section_voicing(chords, top=top, bottom=bottom)
    t_lo, t_hi, _ = bh.horn(top).background
    b_lo, b_hi, _ = bh.horn(bottom).background
    assert len(pairs) == len(chords)
    for chord, (t, b) in zip(chords, pairs):
        h = harmony_of(chord, backing_audio.chord_notes, backing_audio.bass_note, colour=True)
        assert t_lo <= t <= t_hi and b_lo <= b <= b_hi and b < t
        assert t - b in bh.SECTION_INTERVALS, (chord, t, b)  # a 3rd, 6th or 10th on these progressions
        assert t % 12 in h.guides  # the lead is on the 3rd or 7th
        assert {t % 12, b % 12}.isdisjoint({h.root, h.bass})  # never the bass's note
        assert b % 12 in h.allowed
    for v in (0, 1):
        assert max(abs(q[v] - p[v]) for p, q in zip(pairs, pairs[1:])) <= 4, (prog, v, pairs)


def test_section_voicing_handles_triads_slash_chords_and_bare_fifths():
    import backing_audio
    from backing_pianist import harmony_of

    chords = ["C", "F", "G", "C/E", "Am", "D/F#", "G7sus4", "C5", "Bb7#9", "Ebm6"]
    for top, bottom in SECTIONS:
        pairs = bh.section_voicing(chords, top=top, bottom=bottom)
        for chord, (t, b) in zip(chords, pairs):
            h = harmony_of(chord, backing_audio.chord_notes, backing_audio.bass_note, colour=True)
            assert b < t
            if chord != "C5":  # a power chord has nothing but root and fifth
                assert {t % 12, b % 12}.isdisjoint({h.root, h.bass}), (chord, t, b)


def test_ii_v_i_trumpet_over_tenor():
    # Cm7 -> F7 -> Bbmaj7: the trumpet's Bb (7th) falls to A (3rd of F7) and stays as Bbmaj7's 7th;
    # the tenor a sixth under it: D (9th of Cm7), then C (5th of F7, 9th of Bbmaj7).
    assert bh.section_voicing(JAZZ["ii-V-I"], top="trumpet", bottom="tenor") == [(70, 62), (69, 60), (69, 60), (69, 60)]


def test_section_background_gives_each_horn_its_own_breathing_part():
    tl = bh.chord_timeline(JAZZ["turnaround"], 8, 120)
    parts = bh.section_background(tl, top="trumpet", bottom="trombone")
    assert set(parts) == {"trumpet", "trombone"}
    for notes in parts.values():
        assert notes and all(n.voice == 0 and n.articulation == "sustain" for n in notes)
        gaps = [b.start_sec - (a.start_sec + a.dur_sec) for a, b in zip(notes, notes[1:])]
        assert min(gaps) >= bh.TONGUE_GAP_SEC - 1e-9
    hits = bh.section_background(tl, top="trumpet", bottom="trombone", part="hits")
    assert all(n.articulation == "staccato" and n.dur_sec <= bh.STACCATO_MAX_SEC for ns in hits.values() for n in ns)


@pytest.mark.parametrize("top, bottom", SECTIONS)
@pytest.mark.parametrize("part", ["pads", "hits"])
def test_section_render_is_balanced_and_does_not_clip(horns_on, top, bottom, part):
    y = bh.render_section_background(JAZZ["ii-V-I"], 4, 120, top=top, bottom=bottom, part=part)
    assert y is not None and y.dtype == np.float32 and len(y) == int((4 * 4 * 0.5 + 0.6) * SR)
    peak = float(np.abs(y).max())
    assert 0.02 < peak < 0.95
    assert y[0] == 0.0 and abs(y[-1]) < 1e-6


# --- The tenor, exactly as before --------------------------------------------------------------------

# sha256 (first 16 hex digits) of the tenor's float32 renders, taken before the brass was added.
TENOR_RENDERS = {
    ("pads", 1): "de7329e734492261",
    ("pads", 2): "bffde28ccfbccc18",
    ("hits", 1): "ce88b5ccd5bff02d",
    ("hits", 2): "019bddbcb29214bf",
}


@pytest.mark.parametrize("part, voices", list(TENOR_RENDERS))
def test_tenor_renders_are_byte_identical(horns_on, part, voices):
    y = bh.render_horn_background(["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Em7b5", "A7", "Dm7", "G7"], 8, 132, part=part, voices=voices)
    assert hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest()[:16] == TENOR_RENDERS[(part, voices)]


def test_tenor_line_is_byte_identical(horns_on):
    notes = [bh.HornNote(0.1 * i, d, m, v) for i, (d, m, v) in enumerate([(0.2, 40, 0.3), (1.0, 60, 0.6), (6.0, 66, 0.9), (0.1, 90, 0.5), (2.5, 50, 0.7)])]
    y = bh.render_line(notes, SR, gain=0.8)
    assert hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest()[:16] == "d2b16a61652ae182"
    assert bh.render_line(notes, SR, gain=0.8, instrument="tenor").tobytes() == y.tobytes()
    assert bh.guide_tone_line(["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Em7b5", "A7", "Dm7", "G7"], voices=2) == [
        (63, 58), (63, 57), (62, 57), (62, 57), (62, 55), (61, 55), (60, 53), (59, 53)]


def test_the_quartet_still_plays_only_the_tenor(horns_on, monkeypatch):
    import backing_audio as ba
    import backing_performance_plan as pp

    seen = []
    real = bh.render_line
    monkeypatch.setattr(bh, "render_line", lambda *a, **k: seen.append(k.get("instrument", "tenor")) or real(*a, **k))
    chords = [{"chord": c, "section": "A", "bar_in_section": i, "section_bars": 4} for i, c in enumerate(JAZZ["ii-V-I"])]
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    ba.synthesize_chords_to_numpy(chords, bpm=120, loops=1, style="Jazz swing", performance=plan)
    assert seen == ["tenor"]


@pytest.mark.parametrize("name", BRASS)
@pytest.mark.parametrize("part", ["pads", "hits"])
def test_brass_backgrounds_sound_as_loud_as_the_tenors(horns_on, name, part):
    """Horn.level: at the default dynamics a brass background is as loud as the tenor's (within 1.5 dB)."""

    def sounding_db(y):
        w = int(0.05 * SR)
        env = np.array([np.sqrt(np.mean(y[k : k + w] ** 2)) for k in range(0, len(y) - w, w)])
        on = env[env > env.max() * 0.1]
        return 20 * np.log10(np.sqrt(np.mean(on**2)))

    chords = JAZZ["turnaround"]
    tenor = sounding_db(bh.render_horn_background(chords, 8, 120, part=part, gain=1.0))
    brass = sounding_db(bh.render_horn_background(chords, 8, 120, part=part, gain=1.0, instrument=name))
    assert abs(brass - tenor) < 1.5, (brass, tenor)
