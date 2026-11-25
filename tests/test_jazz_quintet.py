"""The Jazz quintet: trumpet and tenor sax over piano, upright bass and drums (MUSIC_HORNS).

What is checked:
* it is offered, and its band names the trumpet and tenor, only while both horns have working audio;
* the quartet (one tenor) is unchanged;
* the two horns interact phrase by phrase: rests, one horn alone, staggered entries, call and response,
  harmonised riffs, shots - never one texture twice running, never doubling each other, never a second or
  seventh apart, always in their background registers, with dynamics that move;
* held notes are in tune, shots avoid the brass takes whose attack scoops;
* in the band the horns sit under the rhythm section and the take stays at -22 LUFS.
"""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_horn_arranger as A
import backing_horns as bh
import backing_performance_plan as pp
import jam_control_ownership as jco


@pytest.fixture
def horns_on(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")


def _form(sections):
    return [(c, i, len(cs)) for _n, cs in sections for i, c in enumerate(cs)]


BB = _form([("A", ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm7", "G7"]),
            ("B", ["Cm7", "F7", "Dm7", "G7", "Cm7", "F7", "Bbmaj7", "Bbmaj7"])]) * 2
GM = _form([("A", ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm6", "Gm6"]),
            ("B", ["Am7b5", "D7", "Gm6", "Gm6", "Cm7", "F7", "Bbmaj7", "Ebmaj7"])])
BLUES = _form([("C", ["F7", "Bb7", "F7", "Cm7 F7", "Bb7", "Bdim7", "F7", "Am7b5 D7", "Gm7", "C7", "F7 D7", "Gm7 C7"])]) * 2


def _bars(rows, bar_sec=2.0):
    out = []
    for i, (c, b, sb) in enumerate(rows):
        parts = c.split()
        w = 4.0 / len(parts)
        out.append(A.ArrBar(i, i * bar_sec, bar_sec / 4, tuple((p, k * w, (k + 1) * w) for k, p in enumerate(parts)),
                            bar_in_section=b, section_bars=sb))
    return out


def _arr(rows=BB, **kw):
    kw.setdefault("swing", 0.62)
    return A.arrange(_bars(rows), **kw)


def _sounding(notes, t):
    return [n.midi for n in notes if n.start_sec <= t < n.start_sec + n.dur_sec]


ALL = [(rows, inten, mood, seed) for rows in (BB, GM, BLUES) for inten in ("Light", "Medium", "Heavy")
       for mood in ("Mellow", "Energetic") for seed in range(3)]


# --- Offered only with working audio -----------------------------------------------------------------


def test_quintet_is_offered_only_while_both_horns_can_play(monkeypatch):
    monkeypatch.delenv("MUSIC_HORNS", raising=False)
    assert "Jazz quintet" not in jco.jam_ensembles()
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quintet")
    assert not plan.plays("horns") and "horns" in plan.unavailable and plan.horns == ()
    assert "trumpet" not in pp.band_summary(plan).lower()
    monkeypatch.setenv("MUSIC_HORNS", "1")
    names = jco.jam_ensembles()
    assert names.index("Jazz quintet") == names.index("Jazz quartet") + 1
    assert set(jco.JAM_ENSEMBLES) < set(names)


def test_a_missing_trumpet_pack_withdraws_the_quintet(horns_on, monkeypatch, tmp_path):
    monkeypatch.setitem(bh.HORNS, "trumpet", bh.HORNS["trumpet"].__class__(**{**bh.HORNS["trumpet"].__dict__, "pack": tmp_path}))
    assert "Jazz quintet" not in jco.jam_ensembles()
    assert not pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quintet").plays("horns")


def test_the_quintets_band_is_what_plays(horns_on):
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quintet")
    assert plan.plays("horns") and plan.horns == ("trumpet", "tenor") and not plan.unavailable
    assert pp.band_summary(plan) == "Piano, trumpet, tenor sax, bass, drums"
    assert pp.role_names(plan) == ["piano", "trumpet", "tenor sax", "bass", "drums"]
    quartet = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    assert quartet.horns == ("tenor",) and quartet.tag().endswith("-k.h.b.d")  # the quartet's take is unchanged
    assert plan.tag() != quartet.tag() and plan.tag().endswith(A.arranger_tag("trumpet", "tenor"))


def test_a_saved_quintet_choice_is_kept_only_while_offered(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    assert "Jazz quintet" in jco._control_options()["ensemble"]
    monkeypatch.delenv("MUSIC_HORNS")
    assert "Jazz quintet" not in jco._control_options()["ensemble"]


# --- The arrangement ----------------------------------------------------------------------------------


@pytest.mark.parametrize("rows, inten, mood, seed", ALL[::5])
def test_textures_vary_and_leave_room(rows, inten, mood, seed):
    arr = _arr(rows, intensity=inten, mood=mood, seed=seed)
    tex = [t for _b, t in arr.phrases]
    assert all(a != b for a, b in zip(tex, tex[1:])), tex  # never the same texture twice running
    run = 0
    for t in tex:
        run = 0 if t == "rest" else run + 1
        assert run <= A._MAX_RUN[inten], tex  # the horns lay out after a run of playing phrases
    if len(tex) > 2:
        assert tex[0] == ("staggered" if inten == "Heavy" else "rest")  # the rhythm section sets the tune up
        assert "rest" in tex


def test_a_short_vamp_never_starts_by_resting():
    rows = _form([("A", ["Dm7", "G7", "Cmaj7", "A7"])])
    for inten in ("Light", "Medium", "Heavy"):
        arr = _arr(rows, intensity=inten, seed=1)
        assert arr.phrases[0][1] != "rest"
        assert arr.notes["trumpet"] or arr.notes["tenor"]


def test_intensity_moves_the_arrangement_not_just_the_level():
    stats = {}
    for inten in ("Light", "Medium", "Heavy"):
        both = busy = vel = n = 0.0
        for rows in (BB, GM, BLUES):
            for seed in range(6):
                arr = _arr(rows, intensity=inten, mood="Mellow", seed=seed)
                tn, bn = arr.notes["trumpet"], arr.notes["tenor"]
                end = len(rows) * 2.0
                ts = np.arange(0, end, 0.05)
                both += np.mean([bool(_sounding(tn, t)) and bool(_sounding(bn, t)) for t in ts])
                busy += (len(tn) + len(bn)) / len(rows)
                vel += sum(x.velocity for x in tn + bn)
                n += len(tn) + len(bn)
        stats[inten] = (both / 18, busy / 18, vel / n)
    light, medium, heavy = stats["Light"], stats["Medium"], stats["Heavy"]
    assert light[0] < medium[0] < heavy[0], stats  # more two-horn writing as it gets heavier
    assert light[1] < heavy[1], stats  # more notes
    assert light[2] < medium[2] < heavy[2], stats  # harder touch


@pytest.mark.parametrize("rows, inten, mood, seed", ALL[::3])
def test_the_horns_harmonise_and_never_double(rows, inten, mood, seed):
    arr = _arr(rows, intensity=inten, mood=mood, seed=seed)
    tn, bn = arr.notes["trumpet"], arr.notes["tenor"]
    for t in np.arange(0, len(rows) * 2.0, 0.02):
        a, b = _sounding(tn, t), _sounding(bn, t)
        if a and b:
            iv = a[0] - b[0]
            assert iv > 0, (t, a, b)  # the trumpet always on top
            assert iv % 12 != 0, (t, a, b)  # no unison or octave doubling
            assert iv in (3, 4, 5, 7, 8, 9, 10, 15, 16, 17), (t, a, b)  # thirds / sixths / tenths; no seconds or sevenths


@pytest.mark.parametrize("rows, inten, mood, seed", ALL[::3])
def test_every_note_is_in_its_horns_register(rows, inten, mood, seed):
    arr = _arr(rows, intensity=inten, mood=mood, seed=seed)
    for name in ("trumpet", "tenor"):
        h = bh.horn(name)
        lo, hi = A._figure_range(h)
        for n in arr.notes[name]:
            assert h.low <= n.midi <= h.high and lo - 2 <= n.midi <= hi, (name, n)
            assert n.dur_sec >= 0.03 and 0.2 <= n.velocity <= 1.0


def test_held_notes_and_figures_use_chord_tones():
    """Held notes are chord tones (never the root or bass note); a figure may add a chromatic approach."""
    for rows in (BB, GM, BLUES):
        bars = _bars(rows)
        for seed in range(4):
            arr = A.arrange(bars, intensity="Heavy", seed=seed, swing=0.62)
            for name, ns in arr.notes.items():
                for n in ns:
                    bar = bars[int((n.start_sec + 0.02) // 2.0)]
                    beat = (n.start_sec + 0.02 - bar.start_sec) / bar.beat_sec
                    guides, tones = bh.section_tones(bar.chord_at(beat))
                    if n.articulation == "sustain" and n.dur_sec > 1.0:
                        assert n.midi % 12 in set(tones) | set(guides), (name, n, bar.chord_at(beat))


def test_call_and_response():
    """In a call phrase one horn plays in bar 1 while the other waits, and the other answers in bar 3."""
    found = 0
    for rows in (BB, GM, BLUES):
        bars = _bars(rows)
        for seed in range(8):
            arr = A.arrange(bars, intensity="Medium", seed=seed, swing=0.62)
            for start, tex in arr.phrases:
                if tex != "call":
                    continue
                found += 1
                b1 = (bars[start].start_sec, bars[start].start_sec + 2.0)
                b3 = (bars[start + 2].start_sec, bars[start + 2].start_sec + 2.0)

                def plays(name, span):
                    return [n for n in arr.notes[name] if span[0] - 0.05 <= n.start_sec < span[1] - 0.05]

                callers = [nm for nm in ("trumpet", "tenor") if plays(nm, b1)]
                assert len(callers) == 1, (seed, start, callers)
                answerer = "tenor" if callers[0] == "trumpet" else "trumpet"
                assert plays(answerer, b3) and not plays(callers[0], b3), (seed, start)
    assert found >= 5
    # Both horns get to call.
    callers = set()
    for seed in range(8):
        arr = _arr(BB, intensity="Medium", seed=seed)
        bars = _bars(BB)
        for start, tex in arr.phrases:
            if tex == "call":
                b1 = bars[start].start_sec
                callers |= {nm for nm in ("trumpet", "tenor") if any(b1 - 0.05 <= n.start_sec < b1 + 1.95 for n in arr.notes[nm])}
    assert callers == {"trumpet", "tenor"}


def test_sections_are_set_up_with_two_shots():
    bars = _bars(BB)
    arr = A.arrange(bars, intensity="Medium", seed=2, swing=0.62)
    for b in bars:
        if b.bar_in_section == b.section_bars - 1 and b.index < len(bars) - 1:
            shots = [n for n in arr.notes["trumpet"] if b.start_sec + 2.4 * b.beat_sec <= n.start_sec < b.start_sec + 4 * b.beat_sec]
            assert len(shots) == 2 and all(n.articulation == "staccato" for n in shots), (b.index, shots)


def test_off_beats_swing_with_the_band():
    bars = _bars(BB)
    arr = A.arrange(bars, intensity="Heavy", seed=0, swing=0.62)
    offs = []
    for n in arr.notes["trumpet"] + arr.notes["tenor"]:
        beat = (n.start_sec - (n.start_sec // 2.0) * 2.0) / 0.5
        frac = beat % 1
        if 0.3 < frac < 0.8:
            offs.append(frac)
    assert offs and all(abs(f - 0.62) < 0.05 for f in offs), sorted(offs)[:5]
    straight = A.arrange(bars, intensity="Heavy", seed=0, swing=0.5)
    offs = [((n.start_sec % 2.0) / 0.5) % 1 for n in straight.notes["trumpet"]]
    assert all(not (0.55 < f < 0.7) for f in offs)


def test_dynamics_move_within_and_between_phrases():
    arr = _arr(BB, intensity="Medium", seed=3)
    v = np.array([n.velocity for n in arr.notes["trumpet"] + arr.notes["tenor"]])
    assert v.std() > 0.03
    swells = [n.swell for n in arr.notes["trumpet"] + arr.notes["tenor"] if n.articulation == "sustain"]
    assert any(s > 0 for s in swells) and any(s < 0 for s in swells)


def test_the_same_take_arranges_the_same_way_and_another_one_differently():
    a, b = _arr(BB, seed=11), _arr(BB, seed=11)
    assert a.notes == b.notes and a.phrases == b.phrases
    others = {tuple(t for _s, t in _arr(BB, seed=s).phrases) for s in range(8)}
    assert len(others) >= 4


# --- Sound -------------------------------------------------------------------------------------------


def _f0_cents(x, midi, sr=44100):
    want = 440.0 * 2 ** ((midi - 69) / 12)
    x = x - x.mean()
    n = len(x)
    lo, hi = int(sr / (want * 2 ** (1 / 12))), int(sr / (want / 2 ** (1 / 12))) + 1
    X = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(X * np.conj(X))[:n]
    ac = ac / (ac[0] + 1e-12)
    k = lo + int(np.argmax(ac[lo:hi]))
    a, b, c = ac[k - 1], ac[k], ac[k + 1]
    d = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    return 1200 * np.log2(sr / (k + d) / want)


@pytest.mark.parametrize("name", ["trumpet", "tenor"])
def test_held_notes_are_in_tune_across_the_register(horns_on, name):
    lo, hi = A._figure_range(bh.horn(name))
    for midi in range(lo, hi + 1, 2):
        y = bh.render_line([bh.HornNote(0.0, 3.0, midi, 0.6, "sustain")], 44100, gain=1.0, seconds=3.4, instrument=name)
        y = y.astype(np.float64)
        for a, b in ((0.3, 0.8), (2.0, 2.5)):  # the steady part, then inside the loop
            assert abs(_f0_cents(y[int(a * 44100): int(b * 44100)], midi)) < 10, (name, midi, a)


def test_brass_shots_avoid_scooping_takes(horns_on):
    for name in ("trumpet", "trombone"):
        inst = bh._pack(name)["staccato"]
        for z in inst.zones:
            steady = bh._steady_attack_zone(z)
            for la, la2 in zip(z["layers"], steady["layers"]):
                if any(abs(t.get("attack_cents", 0)) <= bh.ATTACK_CENTS_MAX for t in la["takes"]):
                    assert all(abs(t["attack_cents"]) <= bh.ATTACK_CENTS_MAX for t in la2["takes"])
                assert la2["takes"]
    assert not bh.HORNS["tenor"].steady_attacks  # the tenor plays exactly as before


def test_swell_zero_leaves_a_note_unchanged_and_a_swell_shapes_it(horns_on):
    note = bh.HornNote(0.0, 1.5, 65, 0.6, "sustain")
    plain = bh.render_line([note], gain=1.0, instrument="trumpet")
    assert np.array_equal(plain, bh.render_line([note], gain=1.0, instrument="trumpet"))
    up = bh.render_line([bh.HornNote(0.0, 1.5, 65, 0.6, "sustain", swell=6.0)], gain=1.0, instrument="trumpet")

    def rms(y, a, b):
        return float(np.sqrt(np.mean(y[int(a * 44100): int(b * 44100)].astype(np.float64) ** 2)))

    assert rms(up, 1.1, 1.4) / rms(up, 0.15, 0.45) > rms(plain, 1.1, 1.4) / rms(plain, 0.15, 0.45) * 1.5


CHORDS = [{"chord": c, "section": s, "bar_in_section": i % 8, "section_bars": 8}
          for i, (s, c) in enumerate([("A", c) for c in ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm7", "G7"]]
                                     + [("B", c) for c in ["Cm7", "F7", "Dm7", "G7", "Cm7", "F7", "Bbmaj7", "Bbmaj7"]])]


def test_in_the_band_the_horns_sit_under_the_rhythm_section(horns_on, monkeypatch):
    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS", "match")
    import backing_loudness as bl

    seen = []
    real = bh.render_line
    monkeypatch.setattr(bh, "render_line", lambda *a, **k: seen.append(k.get("instrument", "tenor")) or real(*a, **k))
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quintet", intensity="Heavy")
    audio, sr = ba.synthesize_chords_to_numpy(CHORDS, bpm=132, loops=1, style="Jazz swing", performance=plan)
    st = dict(ba.LAST_MIX_STATS)
    assert sorted(seen) == ["tenor", "trumpet"]
    assert st["horns_rms"] > 0 and st["horn_textures"]
    assert abs(bl.integrated_lufs(audio, sr) + 22.0) < 0.5
    assert np.isfinite(audio).all()


def test_switch_off_the_quintet_plays_no_horn(monkeypatch):
    monkeypatch.delenv("MUSIC_HORNS", raising=False)
    calls = []
    monkeypatch.setattr(bh, "render_line", lambda *a, **k: calls.append(1))
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quintet")
    ba.synthesize_chords_to_numpy(CHORDS[:4], bpm=132, loops=1, style="Jazz swing", performance=plan)
    assert not calls and "horns_rms" not in ba.LAST_MIX_STATS
