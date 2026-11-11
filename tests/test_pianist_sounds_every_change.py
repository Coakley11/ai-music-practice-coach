"""The pianist sounds every change of harmony where it happens (user, 2026-11-11).

Measured on the user's 12-bar F minor blues before this: the first attack on a new chord came on beat 2 or 3 in 11
of 28 chord spans, so the piano harmony arrived a beat after the Lead Sheet, and a split bar's second chord was
heard for one beat. Now each change sounds on its first beat (or was pushed in an 8th before it); the comping
idea, its space and its syncopation are otherwise unchanged, and a chord that continues keeps its freedom.
"""
from __future__ import annotations

import pytest

import backing_audio as ba
import backing_pianist as pn

USER_CHART = ["Fm6", "Fm6", "Db7", "C7", "Fm6", "Fm6", "Db7|G7", "C7|Bbm7", "Fm7", "Bb7", "Fm7", "C7"]


def _segments(tok):
    parts = tok.split("|")
    w = 4.0 / len(parts)
    return [(i * w, (i + 1) * w, c) for i, c in enumerate(parts)]


def _play(style, chart, seed, loops=2):
    p = pn.start(style, seed, has_guitar=False, level="Intermediate", chord_notes=ba.chord_notes, bass_note=ba.bass_note)
    out = []
    form = chart * loops
    for i, tok in enumerate(form):
        nxt = form[i + 1].split("|")[0] if i + 1 < len(form) else None
        segs = _segments(tok)
        hits = p.bar(segs, nxt, role="verse", quiet=False, bar_in_section=i % len(chart), section_bars=len(chart),
                     section_end=(i % len(chart) == len(chart) - 1), bar_index=i, pulses_per_bar=4)
        out.append((segs, hits))
    return out


def _unheard_changes(played):
    """(bar, chord) for each change whose first beat has no attack and that was not pushed in from the bar before."""
    missing, prev, pushed = [], None, False
    for b, (segs, hits) in enumerate(played):
        for n, (start, _end, chord) in enumerate(segs):
            change = chord != prev
            prev = chord
            if not change:
                continue
            tones = {n % 12 for n in ba.chord_notes(chord)}
            # Any attack on the first beat that sounds a tone of the new chord establishes it (the blues
            # turnaround's figure puts the root on top on beat 1, for example).
            on_time = any(start - 1e-6 <= h.beat < start + 0.26 and not h.push and {n % 12 for n in h.notes} & tones for h in hits)
            if not on_time and not (n == 0 and pushed):
                missing.append((b + 1, chord))
        pushed = any(h.push for h in hits)
    return missing


@pytest.mark.parametrize("seed", ["Blues in F minor", "a", "b", "c", "d", "e"])
def test_every_change_of_the_users_blues_sounds_on_its_first_beat(seed) -> None:
    assert _unheard_changes(_play("Blues groove", USER_CHART, seed)) == []


@pytest.mark.parametrize("style", ["Jazz swing", "Pop groove", "Rock groove", "Funk groove", "Ballad", "Bossa nova", "Soul"])
def test_every_style_sounds_each_change(style) -> None:
    chart = ["Dm7", "G7", "Cmaj7", "Cmaj7", "Am7|D7", "Gm7|C7", "Fmaj7", "E7"]
    for seed in ("x", "y", "z"):
        assert _unheard_changes(_play(style, chart, seed)) == [], (style, seed)


def test_a_chord_that_continues_may_still_leave_its_downbeat_empty() -> None:
    """Space is kept where the harmony does not move: not every repeat bar gets a downbeat."""
    downbeat_free = 0
    for seed in [str(i) for i in range(12)]:
        for b, (segs, hits) in enumerate(_play("Blues groove", ["Fm7", "Fm7", "Fm7", "Fm7"], seed, loops=3)):
            if b % 4 and not any(h.beat < 0.26 and h.kind != "figure" for h in hits):
                downbeat_free += 1
    assert downbeat_free > 0


def test_the_comping_stays_varied_not_a_block_chord_on_every_beat() -> None:
    """The rule adds at most a soft attack on a change; the comping keeps its space and its rhythmic variety.

    Measured on this chart over these seeds: 3.34 attacks per bar before the rule, 3.83 after (bars from 1 to 8).
    """
    means = []
    for seed in ("Blues in F minor", "q", "r", "s"):
        played = _play("Blues groove", USER_CHART, seed)
        attacks = [len({round(h.beat, 2) for h in hits}) for _segs, hits in played]
        rhythms = {tuple(sorted({round(h.beat, 2) for h in hits})) for _segs, hits in played}
        means.append(sum(attacks) / len(attacks))
        assert len(rhythms) >= 5, (seed, rhythms)
        assert min(attacks) <= 2, (seed, attacks)  # some bars still leave space
    assert sum(means) / len(means) <= 4.0, means
