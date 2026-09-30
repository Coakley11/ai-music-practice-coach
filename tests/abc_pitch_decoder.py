"""Minimal ABC → MIDI decoder for tests (L:1/4 motif ABC, one voice).

Deliberately independent of ``music_theory``: key signatures come from the
circle of fifths here, so tests do not validate the encoder against itself.
Semantics match abcjs 6.4.4 (verified by ``scripts/_proof_motif_abc_abcjs.py``):

- ``C`` = middle C (MIDI 60); ``'`` raises and ``,`` lowers an octave after the letter;
  lowercase letters are one octave above uppercase.
- ``K:`` signature applies to every octave of a letter.
- An explicit ``^ _ = ^^ __`` carries to later notes of the same letter *and octave*
  until the next barline.
"""

from __future__ import annotations

import re

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
_NOTE = re.compile(r"(\^\^|__|\^|_|=)?([A-Ga-g])([,']*)(\d*/?\d*)")


def key_signature(k_field: str) -> dict[str, int]:
    k = str(k_field or "C").strip()
    minor = k.endswith("m") and not k.lower().endswith("maj")
    tonic = k[:-1] if minor else k
    count = (_MINOR_FIFTHS if minor else _MAJOR_FIFTHS)[tonic]
    order = _SHARPS if count > 0 else _FLATS
    return {letter: (1 if count > 0 else -1) for letter in order[: abs(count)]}


def decode_abc_midis(abc: str) -> list[int]:
    """Sounding MIDI for each note in a motif ABC string (rests skipped)."""
    lines = str(abc).splitlines()
    k_field = next(line[2:].strip() for line in lines if line.startswith("K:"))
    body = " ".join(lines[lines.index(f"K:{k_field}") + 1 :])
    sig = key_signature(k_field)
    out: list[int] = []
    for bar in body.split("|"):
        in_bar: dict[tuple[str, int], int] = {}
        for tok in bar.split():
            if tok.startswith(("z", "Z")):
                continue
            m = _NOTE.fullmatch(tok)
            assert m, f"unparseable ABC note token {tok!r} in {abc!r}"
            acc, letter, marks, _length = m.groups()
            octave = 4 + (1 if letter.islower() else 0) + marks.count("'") - marks.count(",")
            letter = letter.upper()
            if acc is not None:
                in_bar[(letter, octave)] = _ACC[acc]
            alter = in_bar.get((letter, octave), sig.get(letter, 0))
            out.append(12 * (octave + 1) + _LETTER_PC[letter] + alter)
    return out


def body_tokens(abc: str) -> list[str]:
    lines = str(abc).splitlines()
    k_line = next(i for i, line in enumerate(lines) if line.startswith("K:"))
    return [t for t in " ".join(lines[k_line + 1 :]).replace("|", " ").split() if not t.startswith("z")]
