"""Funk groove: a bass line with space, locked to the kick; quiet ghosts; audible stabs.

Measured before (100 BPM, 8 bars): the bass played 12-13 sixteenths a bar (every
16th but the downbeats of 2, 3, 4), all 0.72 of a 16th long, no octave pops; the
bass landed ~40 ms ahead of the kick on shared 16ths; ghost snares were 0.55 of
the backbeat; comp stabs were ~33 ms clicks. Pop / Rock / Jazz renders are
sample-identical before and after this change.
"""
from __future__ import annotations

import statistics

import numpy as np

import backing_audio as ba

KICKS = (0.0, 0.75, 2.5)  # the funk_rnb groove profile's kick


def _bar(chord="Em7", next_chord="A7", *, seed=3, density=1.0, phrase_end=False, kicks=KICKS):
    return ba._funk_bass_bar(chord, next_chord, kicks, np.random.default_rng(seed), density=density, phrase_end=phrase_end)


def _slots(notes):
    return [int(round(b * 4)) for b, *_ in notes]


def test_bar_anchors_the_one_and_locks_every_kick() -> None:
    for seed in range(20):
        notes = _bar(seed=seed)
        slots = _slots(notes)
        assert slots[0] == 0 and notes[0][3] == 1.0
        assert notes[0][2] % 12 == ba.bass_note("Em7") % 12
        for k in KICKS:
            assert int(k * 4) in slots, (seed, slots)


def test_bar_leaves_space() -> None:
    for seed in range(20):
        notes = _bar(seed=seed, phrase_end=seed % 4 == 3)
        assert 5 <= len(notes) <= ba.FUNK_BASS_MAX_NOTES
        assert 16 - len(set(_slots(notes))) >= 7
        # No note rings into the next one.
        for (b0, l0, *_), (b1, *_r) in zip(notes, notes[1:]):
            assert b0 + l0 < b1


def test_octave_pops_and_dead_notes_give_the_16th_feel() -> None:
    pops = dead = 0
    for seed in range(40):
        notes = _bar(seed=seed)
        root = notes[0][2]
        pops += sum(1 for _b, _l, m, _a in notes if m - root in (10, 12))
        dead += sum(1 for _b, l, _m, a in notes if a < 0.5 and l <= 0.125)
    assert pops >= 30   # most bars answer with an octave / b7 pop
    assert dead >= 20   # short, quiet dead notes before accents


def test_chromatic_walk_in_only_when_the_root_changes() -> None:
    notes = _bar("Em7", "A7")
    last_b, _l, last_m, _a = notes[-1]
    assert int(round(last_b * 4)) == 15
    assert min(abs(last_m - ba._bass_register(ba.bass_note("A7"), near=notes[0][2]) + d) for d in (1, -1)) == 0
    same = _bar("Em7", "Em7")
    assert 15 not in _slots(same)


def test_split_bar_lands_each_root_where_its_chord_starts() -> None:
    notes = _bar("Ebm7:2|Ab7:2", "Dbmaj7")
    by_slot = {int(round(b * 4)): m for b, _l, m, _a in notes}
    assert by_slot[0] % 12 == ba.bass_note("Ebm7") % 12
    assert by_slot[8] % 12 == ba.bass_note("Ab7") % 12


def test_pushed_chord_lands_with_the_comp_push_and_owns_the_rest_of_the_bar() -> None:
    # Written on the last 8th; the comp's push attack plays it an 8th earlier (beat 3).
    for seed in range(20):
        notes = _bar("G:3.5|C:0.5p", "C:4", seed=seed, phrase_end=seed % 2 == 0)
        by_slot = {int(round(b * 4)): (m, a) for b, _l, m, a in notes}
        assert by_slot[0][0] % 12 == ba.bass_note("G") % 12
        assert by_slot[12][0] % 12 == ba.bass_note("C") % 12 and by_slot[12][1] >= 0.95
        g_pcs = {(ba.bass_note("G") + i) % 12 for i in (0, 7, 12)}
        c_pcs = {(ba.bass_note("C") + i) % 12 for i in (0, 7, 12)}
        assert all(m % 12 in g_pcs for s, (m, _a) in by_slot.items() if s < 12), (seed, notes)
        assert all(m % 12 in c_pcs for s, (m, _a) in by_slot.items() if s >= 12), (seed, notes)
    assert ba._funk_chord_at("G:3.5|C:0.5p", 2.75) == "G"
    assert ba._funk_chord_at("G:3.5|C:0.5p", 3.25) == "C"
    early = {int(round(b * 4)): m for b, _l, m, _a in _bar("Bm:2|Em:2p", "A")}
    assert early[6] % 12 == ba.bass_note("Em") % 12


def test_no_chord_segment_is_silent_and_nothing_rings_into_it() -> None:
    for seed in range(20):
        notes = _bar("C7:2|N.C.:2", "C7", seed=seed, phrase_end=True)
        assert notes and all(b + l <= 2.0 - 0.15 / 4 + 1e-9 for b, l, _m, _a in notes), (seed, notes)
        late = _bar("N.C.:2|C7:2", "F7", seed=seed)
        assert int(round(late[0][0] * 4)) == 8 and late[0][2] % 12 == ba.bass_note("C7") % 12
        assert all(b >= 2.0 for b, *_r in late)
    assert ba._funk_chord_at("C7:2|N.C.:2", 2.5) == "N.C."
    assert _bar("N.C.:2|N.C.:2") == []


def test_low_density_drops_dead_notes_first() -> None:
    for seed in range(10):
        notes = _bar(seed=seed, density=0.6)
        assert all(a >= 0.5 for *_x, a in notes)


def test_rendered_funk_pocket() -> None:
    log: list[tuple[str, float, float, float]] = []
    orig = (ba._add_tone, ba._add_kick, ba._add_snare)

    def tone(audio, sr, t, dur, midi, vol, wave="sine"):
        log.append(("bass" if str(wave).startswith("bass") else "keys", t, dur, vol))
        return orig[0](audio, sr, t, dur, midi, vol, wave)

    def kick(audio, sr, t, vol, **k):
        log.append(("kick", t, 0.0, vol))
        return orig[1](audio, sr, t, vol, **k)

    def snare(audio, sr, t, vol, **k):
        log.append(("snare", t, 0.0, vol))
        return orig[2](audio, sr, t, vol, **k)

    ba._add_tone, ba._add_kick, ba._add_snare = tone, kick, snare
    try:
        from backing_musical_profile import resolve_backing_musical_profile

        prof = resolve_backing_musical_profile(style="Funk groove", tempo=100, level="Intermediate")
        ba.synthesize_chords_to_numpy(["Em7", "A7", "Em7", "A7"], bpm=100, sr=22050, style="Funk groove",
                                      musical_profile=prof)
    finally:
        ba._add_tone, ba._add_kick, ba._add_snare = orig
    six = 0.15  # one 16th at 100 BPM
    bass = [t for k, t, *_ in log if k == "bass"]
    for _k, t, *_ in (e for e in log if e[0] == "kick"):
        same = [b for b in bass if abs(b - t) < six / 2]
        assert same and min(abs(b - t) for b in same) <= 0.010
    snares = [(t, v) for k, t, _d, v in log if k == "snare"]
    back = [v for t, v in snares if round((t % 2.4) / six) % 16 in (4, 12)]
    ghost = [v for t, v in snares if round((t % 2.4) / six) % 16 not in (4, 12)]
    assert 0.15 <= statistics.median(ghost) / statistics.median(back) <= 0.35
    stabs = [d for k, _t, d, _v in log if k == "keys"]
    assert stabs and 0.8 * six <= statistics.median(stabs) <= 1.5 * six


def test_rendered_push_and_no_chord_bars_agree_with_the_comp() -> None:
    """One bass attack per push (no doubled generic push note); comp and bass share the
    pushed chord; nothing sounds in an N.C. half bar."""
    log: list[tuple[str, float, float, int]] = []
    orig_tone, orig_comp = ba._add_tone, ba._add_comp_chord

    def tone(audio, sr, t, dur, midi, vol, wave="sine"):
        if str(wave).startswith("bass"):
            log.append(("bass", t, dur, int(midi)))
        return orig_tone(audio, sr, t, dur, midi, vol, wave)

    def comp(bus, sr, t, dur, voicing, vol, wave, **k):
        log.append(("comp", t, dur, tuple(int(m) for m in voicing or ())))
        return orig_comp(bus, sr, t, dur, voicing, vol, wave, **k)

    ba._add_tone, ba._add_comp_chord = tone, comp
    try:
        from backing_musical_profile import resolve_backing_musical_profile

        prof = resolve_backing_musical_profile(style="Funk groove", tempo=100, level="Intermediate")
        ba.synthesize_chords_to_numpy(["G:3.5|C:0.5p", "C", "C7:2|N.C.:2", "C7"], bpm=100, sr=22050,
                                      style="Funk groove", musical_profile=prof)
    finally:
        ba._add_tone, ba._add_comp_chord = orig_tone, orig_comp
    beat, bar = 0.6, 2.4
    bass = sorted((t, d, m) for k, t, d, m in log if k == "bass")
    for (t0, *_a), (t1, *_b) in zip(bass, bass[1:]):
        assert t1 - t0 > 0.03, bass   # no doubled attacks
    c_pc = ba.bass_note("C") % 12
    pushed = [m for t, _d, m in bass if 3.0 * beat - 0.04 <= t < 4.0 * beat - 0.04]
    assert pushed and all(m % 12 in {c_pc, (c_pc + 7) % 12} or m % 12 == (c_pc - 1) % 12 for m in pushed), pushed
    # Funk voicings are often rootless, so tell C from G by the third: E, not B.
    pushed_comps = [v for k, t, _d, v in log if k == "comp" and 3.0 * beat - 0.04 <= t < 4.0 * beat - 0.04]
    assert pushed_comps
    for v in pushed_comps:
        pcs = {m % 12 for m in v}
        assert (c_pc + 4) % 12 in pcs and (c_pc + 11) % 12 not in pcs, v
    tacet = (2 * bar + 2 * beat, 3 * bar)
    assert not [t for t, d, _m in bass if tacet[0] - 0.02 <= t < tacet[1] - 0.04]
    assert all(t + d <= tacet[0] + 0.03 for t, d, _m in bass if t < tacet[0])
    assert not [t for k, t, *_r in log if k == "comp" and tacet[0] - 0.02 <= t < tacet[1] - 0.04]
