"""Key presentation for the Songs and Backing cards (v12 key-caption rule).

Both keys on these cards are concert pitch, so each value carries a "Concert pitch"
caption. A distance line appears only when the Practice Key differs from the Original
Key in the same mode: the shortest distance in semitones (1-5 higher or lower; 6 is
"a tritone away", with no direction). It is hidden when the keys match (enharmonic
spellings count as the same key), when the modes differ, and it never describes the
written pitch of a transposing instrument. Pure functions, no Streamlit.
"""
from __future__ import annotations

import re

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_KEY_RE = re.compile(r"^\s*([A-Ga-g])\s*([#b♯♭]*)\s*(.*)$")


def _parse(key: str) -> tuple[int, str] | None:
    """(pitch class, 'major'|'minor') for 'Db', 'C#m', 'Eb minor', 'D♭ major'; None if unreadable."""
    m = _KEY_RE.match(str(key or ""))
    if not m:
        return None
    pc = _PC[m.group(1).upper()]
    for ch in m.group(2):
        pc += 1 if ch in "#♯" else -1
    rest = m.group(3).strip().lower()
    minor = rest.startswith("min") or (rest.startswith("m") and not rest.startswith("maj"))
    return pc % 12, ("minor" if minor else "major")


def pretty_key_name(key: str) -> str:
    """'Db' -> 'D♭ major', 'C#m' -> 'C♯ minor', 'Eb minor' -> 'E♭ minor'; unreadable text unchanged."""
    m = _KEY_RE.match(str(key or ""))
    if not m or _parse(key) is None:
        return str(key or "")
    acc = m.group(2).replace("#", "♯").replace("b", "♭")
    mode = _parse(key)[1]
    return f"{m.group(1).upper()}{acc} {mode}"


def same_key(a: str, b: str) -> bool:
    pa, pb = _parse(a), _parse(b)
    return pa is not None and pa == pb


def key_relation_caption(original: str, practice: str) -> str:
    """'2 semitones higher' / '1 semitone lower' / 'a tritone away', or '' (same key, mode change, unreadable)."""
    po, pp = _parse(original), _parse(practice)
    if po is None or pp is None or po[1] != pp[1] or po[0] == pp[0]:
        return ""
    d = (pp[0] - po[0]) % 12
    if d == 6:
        return "a tritone away"
    n, way = (d, "higher") if d < 6 else (12 - d, "lower")
    return f"{n} semitone{'s' if n != 1 else ''} {way}"


def key_token_from_name(name: str) -> str:
    """Inverse of pretty_key_name: 'D♭ major' -> 'Db', 'C♯ minor' -> 'C#m'; a bare token is returned as is."""
    m = _KEY_RE.match(str(name or ""))
    parsed = _parse(name)
    if not m or parsed is None:
        return str(name or "")
    acc = m.group(2).replace("♯", "#").replace("♭", "b")
    return f"{m.group(1).upper()}{acc}{'m' if parsed[1] == 'minor' else ''}"
