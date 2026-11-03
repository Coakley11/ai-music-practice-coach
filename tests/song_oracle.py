"""An oracle for song-aware warmups that shares NO code with the generator (no scale_pattern_harmony, no warmup_song).

* ``chord_tones`` : its own tiny chord reader for the qualities Slice 2a supports (third, seventh or sixth as pitch classes).
* ``expected_timeline`` : the chart's bar slots expanded to (onset beat, beats, concert chord), equal parts for "A|B" split bars.
* ``read_tune`` : the written ABC read back as (onset, beats, midi or None, chord label in force) by its own tokenizer.
* ``check_tune`` : every written note, at its onset, must be the third / seventh / sixth of the charted chord there (sounding pitch = written − offset),
  every chord change must start a note or rest exactly on its beat, rests must cover exactly the unsupported chords.
"""

from __future__ import annotations

import re
from fractions import Fraction

from tests.test_abc_bar_accidentals import read_abc

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_pc(name: str) -> int:
    return (_PC[name[0].upper()] + sum(1 if c == "#" else -1 if c == "b" else 0 for c in name[1:])) % 12


def chord_tones(symbol: str):
    """(third_pc, seventh_pc | None, sixth_pc | None) of a charted chord, or None for chords Slice 2a must NOT write (dim, sus, unreadable)."""
    m = re.match(r"^([A-G])([#b]?)([^/]*)(?:/[A-G][#b]?)?$", symbol.strip())
    if not m:
        return None
    root = (_PC[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12
    q = m.group(3)
    ql = q.lower()
    if "dim" in ql or "°" in q or "sus" in ql:
        return None
    major_q = ql.startswith("maj") or q.startswith("M") or "Δ" in q or "△" in q
    minor = (q.startswith("m") or ql.startswith("min") or q.startswith("-")) and not major_q
    third = (root + (3 if minor else 4)) % 12
    if "ø" in ql or "m7b5" in ql:
        return third, (root + 10) % 12, None
    if re.search(r"6/?9", ql):
        return third, None, (root + 9) % 12
    if re.search(r"7|9|11|13", ql):
        return third, (root + 11) % 12 if (major_q or "maj" in ql or "M" in q) else (root + 10) % 12, None
    if re.search(r"(?<![0-9])6", ql):
        return third, None, (root + 9) % 12
    return third, None, None


def expected_timeline(slots: list[str]):
    """[(onset, beats, chord)] for bar slots like ['Cm7', 'Dm7|G7'] in 4/4 (equal parts for split bars)."""
    out = []
    for i, slot in enumerate(slots):
        parts = slot.split("|")
        each = Fraction(4, len(parts))
        for j, c in enumerate(parts):
            out.append((Fraction(4 * i) + each * j, each, c.split(":")[0].split(".hit")[0].strip()))
    return out


_TOKEN = re.compile(r'"(?P<chord>[^"]*)"|(?P<acc>[_^=]*)(?P<note>[A-Ga-gz])(?P<oct>[,\']*)(?P<num>\d*)(?P<sl>/*)(?P<den>\d*)')


def read_tune(abc: str):
    """[(onset, beats, midi | None, chord label in force)] for a tune written with L:1/4, read by an independent tokenizer."""
    assert "L:1/4" in abc, "the oracle reads L:1/4 tunes"
    pitches = iter(read_abc(abc, octave_offset=0))
    body = " ".join(line for line in abc.splitlines() if line and not re.match(r"^[A-Za-z]:", line))
    body = re.sub(r"!\w+!|!>!|[().]|\|\]|\[\|", "", body)
    out, onset, chord = [], Fraction(0), ""
    for m in _TOKEN.finditer(body.replace("|", " ")):
        if m.group("chord") is not None:
            chord = m.group("chord")
            continue
        num = int(m.group("num")) if m.group("num") else 1
        den = int(m.group("den")) if m.group("den") else (2 ** len(m.group("sl")) if m.group("sl") else 1)
        beats = Fraction(num, den)
        midi = None if m.group("note") == "z" else next(pitches)
        out.append((onset, beats, midi, chord))
        onset += beats
    return out


def check_tune(abc: str, slots: list[str], offset: int, written_roots_ok=None) -> list[str]:
    """Problems found (empty list = the tune is exactly the guide-tone line of the chart). ``offset`` = written minus sounding semitones."""
    tune = read_tune(abc)
    bad: list[str] = []
    timeline = expected_timeline(slots)
    total = sum(b for _o, b, _m, _c in tune)
    if total != sum(b for _o, b, _c in timeline):
        bad.append(f"length {total} beats vs the chart's {sum(b for _o, b, _c in timeline)}")
    for onset, beats, chord in timeline:
        tones = chord_tones(chord)
        inside = [t for t in tune if onset <= t[0] < onset + beats]
        starts = [t for t in tune if t[0] == onset]
        if not starts:
            bad.append(f"nothing starts on the {chord} change at beat {onset}")
            continue
        if starts[0][3] == "":
            bad.append(f"no chord symbol on the {chord} change at beat {onset}")
        if any(t[0] + t[1] > onset + beats for t in inside):
            bad.append(f"a note crosses the end of {chord} at beat {onset}")
        if tones is None:
            if any(t[2] is not None for t in inside):
                bad.append(f"notes were written over {chord}, which is not supported")
            continue
        allowed = {p for p in tones if p is not None}
        for _o, _b, midi, _c in inside:
            if midi is None:
                continue
            pc = (midi - offset) % 12
            if pc not in allowed:
                bad.append(f"{midi} (sounding pc {pc}) is not a guide tone of {chord} at beat {onset}; allowed {sorted(allowed)}")
        if starts[0][3] and chord_tones(chord) is not None:
            suffix = re.match(r"^[A-G][#b]?(.*)$", chord).group(1).split("/")[0]
            label = starts[0][3]
            if not label.endswith(suffix) or note_pc(re.match(r"^[A-G][#b]?", label).group(0)) != (note_pc(re.match(r"^[A-G][#b]?", chord).group(0)) + offset) % 12:
                bad.append(f"chord label {label!r} is not {chord} written for this instrument (offset {offset})")
    return bad
