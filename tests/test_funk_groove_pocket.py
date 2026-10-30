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


def test_pushed_or_tacet_segments_use_the_shared_path() -> None:
    assert _bar("C:3.5|D:0.5p") is None
    assert _bar("C:2|N.C.:2") is None


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
