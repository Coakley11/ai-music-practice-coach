"""Minimal ABC → MIDI + duration decoder for tests (L:1/4 motif ABC, one voice).

Deliberately independent of ``music_theory``: key signatures come from the
circle of fifths here, so tests do not validate the encoder against itself.
Semantics match abcjs 6.4.4 (verified by ``scripts/_proof_motif_abc_abcjs.py`` and
``scripts/_proof_rhythm_abc_abcjs.py``):

- ``C`` = middle C (MIDI 60); ``'`` raises and ``,`` lowers an octave after the letter;
  lowercase letters are one octave above uppercase.
- ``K:`` signature applies to every octave of a letter.
- An explicit ``^ _ = ^^ __`` carries to later notes of the same letter *and octave*
  until the next barline.
- Lengths are relative to ``L:1/4``; ``(p`` makes the next *p* notes a tuplet
  (p in the time of q; q = 3 for p = 2 or 4, else 2). Notes may be beamed
  (written without spaces).
"""

from __future__ import annotations

import re
from fractions import Fraction

_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARPS = "FCGDAEB"
_FLATS = "BEADGCF"
# Major key → signed accidental count (positive sharps, negative flats).
_MAJOR_FIFTHS = {
    "Cb": -7, "Gb": -6, "Db": -5, "Ab": -4, "Eb": -3, "Bb": -2, "F": -1, "C": 0,
    "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
}
# Minor tonic → relative-major fifths count.
_MINOR_FIFTHS = {
    "Ab": -7, "Eb": -6, "Bb": -5, "F": -4, "C": -3, "G": -2, "D": -1, "A": 0,
    "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6, "A#": 7,
}
_ACC = {"^^": 2, "^": 1, "=": 0, "_": -1, "__": -2}
_EVENT = re.compile(r"\((\d)|(\^\^|__|\^|_|=)?([A-Ga-gzZ])([,']*)(\d*)(/*)(\d*)")
_TUPLET_Q = {2: 3, 3: 2, 4: 3, 6: 2}


def key_signature(k_field: str) -> dict[str, int]:
    # An ABC K: field may carry directives after the key token (clef=bass,
    # middle=…). They affect how the staff is drawn, never the sounding pitch,
    # so take only the key token.
    k = str(k_field or "C").strip().split()[0] if str(k_field or "").strip() else "C"
    minor = k.endswith("m") and not k.lower().endswith("maj")
    tonic = k[:-1] if minor else k
    count = (_MINOR_FIFTHS if minor else _MAJOR_FIFTHS)[tonic]
    order = _SHARPS if count > 0 else _FLATS
    return {letter: (1 if count > 0 else -1) for letter in order[: abs(count)]}


def _header_and_body(abc: str) -> tuple[list[str], str]:
    lines = str(abc).splitlines()
    k_line = next(i for i, line in enumerate(lines) if line.startswith("K:"))
    return lines[: k_line + 1], " ".join(lines[k_line + 1 :])


def _length(num: str, slashes: str, den: str) -> Fraction:
    n = Fraction(int(num)) if num else Fraction(1)
    if slashes:
        n /= int(den) if den else 2 ** len(slashes)
    return n


def _decode_bar(text: str, sig: dict[str, int], abc: str) -> list[tuple[int | None, Fraction]]:
    out: list[tuple[int | None, Fraction]] = []
    in_bar: dict[tuple[str, int], int] = {}
    tuplet_left = 0
    ratio = Fraction(1)
    text = text.replace(" ", "")
    pos = 0
    while pos < len(text):
        m = _EVENT.match(text, pos)
        assert m and m.end() > pos, f"unparseable ABC at {text[pos:pos + 12]!r} in {abc!r}"
        pos = m.end()
        if m.group(1):
            p = int(m.group(1))
            tuplet_left, ratio = p, Fraction(_TUPLET_Q.get(p, 2), p)
            continue
        acc, letter, marks, num, slashes, den = m.groups()[1:]
        dur = _length(num, slashes, den)
        if tuplet_left:
            dur *= ratio
            tuplet_left -= 1
        if letter in "zZ":
            out.append((None, dur))
            continue
        octave = 4 + (1 if letter.islower() else 0) + marks.count("'") - marks.count(",")
        letter = letter.upper()
        if acc is not None:
            in_bar[(letter, octave)] = _ACC[acc]
        alter = in_bar.get((letter, octave), sig.get(letter, 0))
        out.append((12 * (octave + 1) + _LETTER_PC[letter] + alter, dur))
    return out


def decode_abc_events(abc: str) -> list[tuple[int | None, Fraction]]:
    """(sounding MIDI, or None for a rest; duration in quarter notes) per event."""
    header, body = _header_and_body(abc)
    sig = key_signature(header[-1][2:].strip())
    out: list[tuple[int | None, Fraction]] = []
    for bar in body.split("|"):
        out.extend(_decode_bar(bar, sig, abc))
    return out


def decode_abc_midis(abc: str) -> list[int]:
    """Sounding MIDI for each note in a motif ABC string (rests skipped)."""
    return [m for m, _d in decode_abc_events(abc) if m is not None]


def abc_bar_totals(abc: str) -> list[Fraction]:
    """Total duration (quarter notes) of each non-empty bar, in order."""
    header, body = _header_and_body(abc)
    sig = key_signature(header[-1][2:].strip())
    return [
        sum((d for _m, d in _decode_bar(bar, sig, abc)), Fraction(0))
        for bar in body.split("|")
        if bar.strip()
    ]


def body_tokens(abc: str) -> list[str]:
    _header, body = _header_and_body(abc)
    return [t for t in body.replace("|", " ").split() if not t.startswith("z")]
