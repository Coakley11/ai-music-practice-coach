"""Jazz swing bass: an upright walking line that follows the chart."""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_bass_voice as bv

TWO_FIVE_ONE = ["Dm7", "G7", "Cmaj7", "Cmaj7", "Em7b5", "A7", "Dm7", "G7"]
RHYTHM_CHANGES = ["Bb", "G7", "Cm7", "F7", "Dm7", "G7", "Cm7", "F7"]
FLAT_KEYS = ["Ebm7", "Ab7", "Dbmaj7", "Gb7", "Fm7b5", "Bb7", "Ebm7", "Ab7"]
SHARP_KEYS = ["F#m7", "B7", "Emaj7", "C#7", "F#m7", "B7", "Emaj7", "G#7"]
ALL_CHARTS = [TWO_FIVE_ONE, RHYTHM_CHANGES, FLAT_KEYS, SHARP_KEYS]


@pytest.fixture(autouse=True)
def _upright_on(monkeypatch):
    monkeypatch.setenv("MUSIC_UPRIGHT_BASS", "model")


def walk(chart, passes=4, ppb=4, seed=5):
    """The chart's lines as a list of (chord, next chord, notes), bar by bar."""
    state = {"prev": None, "planned": None, "head": None}
    bars = chart * passes
    out = []
    for i, chord in enumerate(bars):
        nxt = bars[i + 1] if i + 1 < len(bars) else None
        rng = np.random.default_rng(i * 7919 + seed)
        notes = ba._jazz_walk_bar(chord, nxt, ppb, state, rng, phrase_start=i % 4 == 0, phrase_end=i % 4 == 3)
        out.append((chord, nxt, notes))
    return out


def quarters(notes):
    return [n for n in notes if float(n[0]).is_integer()]


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_every_chord_change_lands_on_its_root(chart):
    for chord, _nxt, notes in walk(chart):
        assert notes[0][0] == 0.0
        if chord in chart and chart.count(chord) == 1:  # never held over: no 3rd or 5th start
            assert notes[0][2] % 12 == ba.bass_note(chord) % 12, (chord, notes)


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_four_quarters_a_bar(chart):
    for chord, _nxt, notes in walk(chart):
        assert [n[0] for n in quarters(notes)] == [0.0, 1.0, 2.0, 3.0], (chord, notes)


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_stays_in_the_instruments_range(chart):
    for _c, _n, notes in walk(chart):
        for _b, _d, midi, _a in notes:
            assert ba.JAZZ_BASS_LOW <= midi <= ba.JAZZ_BASS_HIGH


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_beat_three_is_a_chord_tone(chart):
    for chord, nxt, notes in walk(chart):
        tones = set(ba._walk_chord_tones(chord))
        assert quarters(notes)[2][2] % 12 in tones, (chord, notes)


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_beat_two_is_in_the_chord_or_its_scale(chart):
    for chord, _nxt, notes in walk(chart):
        assert quarters(notes)[1][2] % 12 in ba._walk_scale(chord), (chord, notes)


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_last_beat_leads_into_the_next_chord(chart):
    """Half step, whole step, or the next chord's 5th, and the next bar really plays that root."""
    bars = walk(chart)
    for (chord, nxt, notes), (_c2, _n2, after) in zip(bars, bars[1:]):
        if nxt == chord:
            continue
        lead = quarters(notes)[3][2]
        down = after[0][2]
        gap = abs(lead - down)
        fifth = ba._bass_fifth_interval(nxt)
        assert gap in (1, 2, fifth, 12 - fifth), (chord, nxt, lead, down)


@pytest.mark.parametrize("chart", ALL_CHARTS)
def test_no_wide_leaps_or_stuck_notes(chart):
    bars = walk(chart)
    line = [n[2] for _c, _n, notes in bars for n in quarters(notes)]
    assert max(abs(a - b) for a, b in zip(line, line[1:])) <= 12
    repeats = sum(1 for a, b in zip(line, line[1:]) if a == b)
    assert repeats <= len(line) * 0.12, repeats


def test_the_same_changes_are_not_a_copy_each_pass():
    bars = walk(TWO_FIVE_ONE, passes=4)
    n = len(TWO_FIVE_ONE)
    lines = [tuple(tuple(q[2] for q in quarters(b[2])) for b in bars[p * n : (p + 1) * n]) for p in range(4)]
    assert len(set(lines)) == 4


def test_the_line_is_the_same_on_every_render():
    assert walk(TWO_FIVE_ONE) == walk(TWO_FIVE_ONE)


def test_held_chord_may_move_off_the_root_only_inside_a_phrase():
    chart = ["Cmaj7"] * 8
    bars = walk(chart, passes=4)
    for i, (_c, _n, notes) in enumerate(bars):
        assert notes[0][2] % 12 in set(ba._walk_chord_tones("Cmaj7"))
        if i % 4 == 0:
            assert notes[0][2] % 12 == ba.bass_note("Cmaj7") % 12
    assert any(b[2][0][2] % 12 != 0 for b in bars)


def test_slash_bass_is_played_on_the_change():
    bars = walk(["C/E", "F", "G/B", "C"])
    for chord, _n, notes in bars:
        assert notes[0][2] % 12 == ba.bass_note(chord) % 12


def test_two_chords_in_a_bar_each_get_their_root():
    bars = walk(["Dm7:2|G7:2", "Cmaj7"])
    for chord, _n, notes in bars:
        if chord.startswith("Dm7"):
            assert notes[0][2] % 12 == 2
            third = next(n for n in notes if n[0] == 2.0)
            assert third[2] % 12 == 7


def test_no_chord_part_of_a_bar_is_silent():
    state = {"prev": None, "planned": None, "head": None}
    notes = ba._jazz_walk_bar("C7:2|N.C.:2", "F7", 4, state, np.random.default_rng(1))
    assert notes and all(b < 2.0 for b, _d, _m, _a in notes)
    assert all(b + d <= 2.0 + 1e-6 for b, d, _m, _a in notes)


def test_waltz_walks_three_beats():
    for _c, _n, notes in walk(TWO_FIVE_ONE, ppb=3):
        assert [n[0] for n in quarters(notes)] == [0.0, 1.0, 2.0]


def test_upright_voice_is_a_decaying_pluck_at_the_right_pitch():
    sr = 22050
    tone = bv._upright_free(40, 1, sr).astype(np.float64)
    assert np.max(np.abs(tone)) <= 1.0 + 1e-6
    # Quieter a second in than at the start, and not gated to silence.
    early = np.sqrt(np.mean(tone[int(0.02 * sr) : int(0.12 * sr)] ** 2))
    late = np.sqrt(np.mean(tone[int(1.0 * sr) : int(1.1 * sr)] ** 2))
    assert 0.02 * early < late < 0.7 * early
    # Strongest low partial sits on a harmonic of E2.
    seg = tone[int(0.2 * sr) : int(1.2 * sr)]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    peak = freqs[np.argmax(spec * (freqs < 400))]
    f0 = bv._freq(40)
    assert abs(peak / f0 - round(peak / f0)) < 0.03


def test_upright_note_stops_when_released():
    sr = 22050
    bus = np.zeros(sr * 2)
    bv.add_upright_note(bus, sr, 0.1, 0.25, 40, 1.0, 0.6)
    assert np.max(np.abs(bus[int(0.6 * sr) :])) < 1e-3
    assert np.max(np.abs(bus[: int(0.09 * sr)])) == 0.0


@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_jazz_renders_and_others_do_not_use_the_walk(level, monkeypatch):
    calls = []
    real = ba._jazz_walk_bar
    monkeypatch.setattr(ba, "_jazz_walk_bar", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    a, _sr = ba.synthesize_chords_to_numpy(["Dm7", "G7"], bpm=120, sr=11025, style="Jazz swing", level=level)
    assert calls and np.max(np.abs(a)) > 0.1
    calls.clear()
    ba.synthesize_chords_to_numpy(["Dm7", "G7"], bpm=120, sr=11025, style="Pop groove", level=level)
    assert not calls
