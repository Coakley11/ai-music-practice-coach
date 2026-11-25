"""Slice 3: Samba and Latin jazz grooves are their own, distinct from Bossa nova and from each other."""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_latin_grooves as lg


def test_switch_off_keeps_todays_mapping(monkeypatch):
    monkeypatch.delenv("MUSIC_LATIN_GROOVES", raising=False)
    assert lg.engine_style_for("Latin") is None
    assert lg.engine_style_for("Samba") is None


def test_switch_on_routes_latin_and_samba_but_never_bossa(monkeypatch):
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "on")
    assert lg.engine_style_for("Latin") == lg.LATIN_JAZZ
    assert lg.engine_style_for("Samba") == lg.SAMBA
    assert lg.engine_style_for("Bossa Nova") is None
    assert lg.engine_style_for("Bossa nova") is None


def test_son_clave_2_3_and_cascara_line_up_with_their_sides():
    two, three = lg.SON_CLAVE_2_3
    assert two == (1.0, 2.0) and three == (0.0, 1.5, 3.0)
    # 3 side X.X.XX.X, 2 side .XX.X.X.
    assert lg.CASCARA_3_SIDE == (0.0, 1.0, 2.0, 2.5, 3.5)
    assert lg.CASCARA_2_SIDE == (0.5, 1.0, 2.0, 3.0)
    b0, b1 = lg.bar(lg.LATIN_JAZZ, 0), lg.bar(lg.LATIN_JAZZ, 1)
    assert b0.grid["cross_stick"] == [1.0, 2.0] and b0.grid["hat_beats"] == list(lg.CASCARA_2_SIDE)
    assert b1.grid["cross_stick"] == [0.0, 1.5, 3.0] and b1.grid["hat_beats"] == list(lg.CASCARA_3_SIDE)
    assert lg.bar(lg.LATIN_JAZZ, 2).grid == b0.grid  # a two-bar cycle


def test_no_clave_on_brazilian_grooves():
    assert not lg.has_clave(lg.SAMBA) and not lg.has_clave("Bossa nova")
    samba = lg.bar(lg.SAMBA, 0).grid
    clave_onsets = set(lg.SON_CLAVE_2_3[0]) | set(lg.SON_CLAVE_2_3[1])
    assert samba["cross_stick"] == list(lg.PARTIDO_ALTO)
    assert set(samba["cross_stick"]) != clave_onsets


def test_samba_is_driving_sixteenths_with_surdo_accents():
    g = lg.bar(lg.SAMBA, 0).grid
    assert len(g["hat_beats"]) == 16
    assert g["kick_beats"] == list(lg.SAMBA_KICK)
    assert lg.samba_kick_accent(1.0) > lg.samba_kick_accent(0.0) > lg.samba_kick_accent(0.75)
    assert lg.samba_shaker_accent(0.75) > lg.samba_shaker_accent(0.0) > lg.samba_shaker_accent(0.25)
    light = lg.bar(lg.SAMBA, 0, intensity="Light").grid
    assert len(light["kick_beats"]) < len(g["kick_beats"]) and len(light["hat_beats"]) < 16


def test_partido_alto_onsets():
    assert lg.PARTIDO_ALTO == (0.25, 1.0, 1.5, 2.0, 2.5, 3.25)


def test_three_grooves_have_different_grids():
    bossa = ba._style_patterns("Bossa nova")
    samba = ba._style_patterns(lg.SAMBA)
    latin = ba._style_patterns(lg.LATIN_JAZZ)
    keys = ("kick_beats", "hat_beats", "cross_stick", "bass_beats")
    sig = lambda g: tuple(tuple(g.get(k) or ()) for k in keys)  # noqa: E731
    assert len({sig(bossa), sig(samba), sig(latin)}) == 3


def _notes(fn, bars):
    state = {"prev": None, "tie_bar": None, "tie_pc": None}
    out = []
    for i, ch in enumerate(bars):
        nxt = bars[(i + 1) % len(bars)]
        out.append(fn(ch, nxt, state, np.random.default_rng(i), bar_index=i, density=1.0))
    return out


def test_tumbao_anticipates_and_ties_over_the_bar_line():
    bars = ["Cm7", "F7", "Bbmaj7", "Ebmaj7"]
    out = _notes(ba._tumbao_bass_bar, bars)
    # First bar: nothing to tie from, so a root on 1; afterwards beat 1 is open (the tie covers it).
    assert out[0][0][0] == 0.0
    for i, notes in enumerate(out):
        beats = [n[0] for n in notes]
        if i:
            assert 0.0 not in beats
        assert 1.5 in beats and 3.0 in beats
        four = next(n for n in notes if n[0] == 3.0)
        nxt_root = ba._bossa_bass_pcs(bars[(i + 1) % len(bars)])[0]
        assert four[2] % 12 == nxt_root  # beat 4 = the next chord's root
        assert four[0] + four[1] > 4.0  # rings over the bar line
        assert all(ba.BOSSA_BASS_LOW <= n[2] <= ba.BOSSA_BASS_HIGH for n in notes)


def test_samba_bass_is_surdo_shaped_on_chord_tones():
    bars = ["Dm7", "G7", "Cmaj7", "A7"]
    out = _notes(ba._samba_bass_bar, bars)
    for ch, notes in zip(bars, out):
        root_pc, fifth_pc = ba._bossa_bass_pcs(ch)
        by_beat = {n[0]: n for n in notes}
        assert by_beat[0.0][2] % 12 == root_pc and by_beat[2.0][2] % 12 == root_pc
        assert by_beat[1.0][2] % 12 == fifth_pc and by_beat[3.0][2] % 12 == fifth_pc
        assert by_beat[1.0][3] == 1.0 > by_beat[0.0][3]  # the accented "2"
        assert by_beat[1.0][2] < by_beat[0.0][2]  # the low fifth


def test_montuno_gate():
    q = lambda c: ba.split_chord(c)[1]  # noqa: E731
    assert lg.montuno_fits([["Cm7"], ["F7"], ["Cm7"], ["F7"]], q)
    assert not lg.montuno_fits([["Dm7b5"], ["G7alt"], ["Cm"]], q)
    assert not lg.montuno_fits([["C", "Am", "F"]], q)


@pytest.mark.parametrize("style", [lg.SAMBA, lg.LATIN_JAZZ])
def test_short_synth_render(style):
    audio, sr = ba.synthesize_chords_to_numpy(["Dm7", "G7", "Cmaj7", "A7"], style=style, bpm=120, loops=1)
    assert np.isfinite(audio).all() and float(np.max(np.abs(audio))) > 0.01


def test_latin_styles_render_differently_from_bossa():
    chords = ["Dm7", "G7", "Cmaj7", "A7"]
    takes = {st: ba.synthesize_chords_to_numpy(chords, style=st, bpm=120, loops=1)[0]
             for st in ("Bossa nova", lg.SAMBA, lg.LATIN_JAZZ)}
    a, b, c = takes["Bossa nova"], takes[lg.SAMBA], takes[lg.LATIN_JAZZ]
    n = min(len(a), len(b), len(c))
    assert not np.allclose(a[:n], b[:n]) and not np.allclose(a[:n], c[:n]) and not np.allclose(b[:n], c[:n])


def test_montuno_bar_plays_chord_tones_on_the_clave_sides():
    import backing_pianist as pn

    p = pn.Pianist(lg.LATIN_JAZZ, 7, chord_notes=ba.chord_notes, bass_note=ba.bass_note)
    segs = [(0.0, 4.0, "Cm7")]
    for side in (0, 1):
        hits = p.montuno_bar(segs, "F7", side=side)
        assert [h.beat for h in hits] == [c[0] for c in pn.Pianist.MONTUNO_CELLS[side]]
        cm7 = {0, 3, 7, 10}
        f7 = {5, 9, 0, 3}
        for h in hits:
            allowed = f7 if h.push else cm7
            assert all(n % 12 in allowed for n in h.notes), (side, h)
            assert h.notes[-1] - h.notes[0] == 12  # octave-doubled line


def test_montuno_only_where_harmony_fits(monkeypatch):
    monkeypatch.setenv("MUSIC_PIANO_V2", "varied")
    calls = []
    import backing_pianist as pn

    orig = pn.Pianist.montuno_bar

    def spy(self, *a, **k):
        calls.append(1)
        return orig(self, *a, **k)

    pn.Pianist.montuno_bar = spy
    try:
        ba.synthesize_chords_to_numpy(["Cm7", "F7", "Cm7", "F7"], style=lg.LATIN_JAZZ, bpm=120, loops=1)
        fits = len(calls)
        calls.clear()
        ba.synthesize_chords_to_numpy(["Dm7b5", "G7alt", "Cm6", "Cm6"], style=lg.LATIN_JAZZ, bpm=120, loops=1)
        assert fits > 0 and len(calls) == 0
    finally:
        pn.Pianist.montuno_bar = orig
