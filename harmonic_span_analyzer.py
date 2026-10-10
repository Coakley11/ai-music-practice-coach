"""Harmonic-span analysis: ranked contiguous 2- and 3-chord windows of a progression.

Pure and deterministic (music-theory rules only — no Streamlit, no LLM). The input
is the chord map's own section rows ``(label, display chords, raw chart chords)``
from :func:`improvisation_motif.resolve_improv_section_rows`, in concert pitch at
the Practice Key. Windows are taken only from consecutive chords inside one section,
in chart order; consecutive repeats merge into one event that keeps its bar count,
so ``G | G | C`` is the span ``G → C`` with two bars of G, never a lossy ``G → C``.

Each :class:`HarmonicSpan` is a self-contained record of one harmonic window — the
unit a multi-chord generator will receive.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Callable, Sequence

SCOPE_SINGLE = "single"
SCOPE_SPAN2 = "span2"
SCOPE_SPAN3 = "span3"
SCOPE_LENGTHS: dict[str, int] = {SCOPE_SPAN2: 2, SCOPE_SPAN3: 3}

WEAK_SCORE = 40.0
MIN_STRONG_TO_HIDE_WEAK = 3

SectionRow = tuple[str, Sequence[str], Sequence[str]]

_LETTERS = frozenset("ABCDEFG")
_MINORISH = frozenset({"minor", "m7"})
_MAJORISH = frozenset({"major", "maj7"})
_LOWER_CASE = frozenset({"minor", "m7", "half-dim", "dim"})
_NUMERAL_SUFFIX = {"half-dim": "ø", "dim": "°", "aug": "+"}

_MAJOR_NUMERALS = {
    0: ("", "I"), 1: ("b", "II"), 2: ("", "II"), 3: ("b", "III"), 4: ("", "III"), 5: ("", "IV"),
    6: ("#", "IV"), 7: ("", "V"), 8: ("b", "VI"), 9: ("", "VI"), 10: ("b", "VII"), 11: ("", "VII"),
}
_MINOR_NUMERALS = {
    0: ("", "I"), 1: ("b", "II"), 2: ("", "II"), 3: ("", "III"), 4: ("#", "III"), 5: ("", "IV"),
    6: ("#", "IV"), 7: ("", "V"), 8: ("", "VI"), 9: ("#", "VI"), 10: ("", "VII"), 11: ("#", "VII"),
}
# Diatonic (scale degree -> qualities). Minor admits the harmonic-minor V and vii°.
_DIATONIC_MAJOR = {
    0: {"major", "maj7", "sus"}, 2: {"minor", "m7", "sus"}, 4: {"minor", "m7"},
    5: {"major", "maj7", "sus"}, 7: {"major", "dom", "sus"}, 9: {"minor", "m7", "sus"},
    11: {"dim", "half-dim"},
}
_DIATONIC_MINOR = {
    0: {"minor", "m7", "sus"}, 2: {"dim", "half-dim"}, 3: {"major", "maj7"},
    5: {"minor", "m7", "sus"}, 7: {"minor", "m7", "major", "dom", "sus"}, 8: {"major", "maj7"},
    10: {"major", "dom", "sus"}, 11: {"dim"},
}
# Ranked diatonic two-chord motions (degree pairs) not already caught as ii–V / V–I.
_PAIR_SCORES_MAJOR = {(5, 7): 72.0, (5, 0): 70.0, (0, 9): 66.0, (0, 5): 64.0, (9, 2): 64.0,
                      (4, 9): 64.0, (9, 5): 62.0, (0, 7): 62.0}
_PAIR_SCORES_MINOR = {(5, 7): 72.0, (5, 0): 70.0, (8, 7): 66.0, (8, 10): 66.0, (0, 5): 64.0,
                      (10, 0): 64.0, (0, 8): 64.0, (0, 10): 62.0}
_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
_HARMONIC_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 11)


@dataclass(frozen=True)
class ChordEvent:
    """One harmony as charted: consecutive repeats merged, bar count kept."""

    chord: str
    bars: int
    raw_index: int


@dataclass(frozen=True)
class HarmonicSpan:
    span_id: str
    progression_key: str
    source_id: str
    scope: str
    length: int
    section_index: int
    section_label: str
    start_event: int
    end_event: int
    raw_start: int
    raw_end: int
    chords: tuple[str, ...]
    raw_events: tuple[ChordEvent, ...]
    display_global_indices: tuple[int, ...]
    key_center: str
    relationship: str
    relationship_label: str
    roman: tuple[str, ...]
    roman_confident: bool
    score: float
    confidence: float
    target_chord: str
    target_roman: str
    common_scales: tuple[str, ...]
    common_tones: tuple[int, ...]
    voice_leading_cost: int
    repeated_vamp: bool
    occurrences: int
    cross_section: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Chord:
    symbol: str
    pc: int
    quality: str
    tones: frozenset[int]


@dataclass(frozen=True)
class _Rel:
    rel_id: str
    label: str
    score: float
    confidence: float
    target_pc: int = -1
    target_quality: str = ""


@lru_cache(maxsize=2048)
def _parse(symbol: str) -> _Chord:
    from improvisation_motif import chord_tone_names
    from music_theory import chord_root_for_theory, classify_chord_quality, pitch_class_from_spelled_note

    root = chord_root_for_theory(symbol)
    if not root or root[0].upper() not in _LETTERS:
        return _Chord(symbol, -1, "", frozenset())
    tones = frozenset(pitch_class_from_spelled_note(t) for t in chord_tone_names(symbol))
    return _Chord(symbol, pitch_class_from_spelled_note(root), classify_chord_quality(symbol), tones)


def _key_info(key_center: str) -> tuple[int, bool]:
    from music_theory import pitch_class_from_spelled_note, split_key_center

    tonic, mode = split_key_center(str(key_center or "C"))
    return pitch_class_from_spelled_note(tonic), mode == "minor"


def section_events(raw_chords: Sequence[str]) -> list[ChordEvent]:
    out: list[ChordEvent] = []
    for i, ch in enumerate(raw_chords):
        token = str(ch).strip()
        if not token:
            continue
        if out and out[-1].chord == token:
            prev = out[-1]
            out[-1] = ChordEvent(prev.chord, prev.bars + 1, prev.raw_index)
        else:
            out.append(ChordEvent(token, 1, i))
    return out


def _cycle_length(chords: Sequence[str]) -> int:
    """Shortest repeating cell played at least twice (0 when the section never repeats)."""
    n = len(chords)
    for size in range(1, n // 2 + 1):
        if all(chords[i] == chords[i % size] for i in range(n)):
            return size
    return 0


def progression_fingerprint(section_rows: Sequence[SectionRow]) -> str:
    """Transposition-invariant structure hash: Practice Key changes keep it stable."""
    base = next(
        (p.pc for _l, _d, raw in section_rows for p in (_parse(str(c)) for c in raw) if p.pc >= 0),
        0,
    )
    parts = []
    for label, _display, raw in section_rows:
        toks = []
        for sym in raw:
            ch = _parse(str(sym).strip())
            toks.append("x" if ch.pc < 0 else f"{(ch.pc - base) % 12}{ch.quality}")
        parts.append(f"{label}:{','.join(toks)}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _deg(ch: _Chord, key_pc: int) -> int:
    return (ch.pc - key_pc) % 12


def _numeral(degree: int, quality: str, minor: bool) -> str:
    acc, num = (_MINOR_NUMERALS if minor else _MAJOR_NUMERALS)[degree % 12]
    if quality in _LOWER_CASE:
        num = num.lower()
    return f"{acc}{num}{_NUMERAL_SUFFIX.get(quality, '')}"


def _is_diatonic(ch: _Chord, key_pc: int, minor: bool) -> bool:
    table = _DIATONIC_MINOR if minor else _DIATONIC_MAJOR
    return ch.quality in table.get(_deg(ch, key_pc), set())


def _down_fifth(a: _Chord, b: _Chord) -> bool:
    return (b.pc - a.pc) % 12 == 5


def _down_half_step(a: _Chord, b: _Chord) -> bool:
    """Tritone-substitute motion: subV7 resolves down a half step (Gb7 → F)."""
    return (b.pc - a.pc) % 12 == 11


def _dominant_function(ch: _Chord, key_pc: int) -> bool:
    return ch.quality == "dom" or (ch.quality in ("major", "sus") and _deg(ch, key_pc) == 7)


def _functional_path(
    chords: Sequence[_Chord], key_pc: int, minor: bool, following: _Chord | None = None
) -> str:
    """Roman path when every chord is diatonic or an applied dominant to the chord after it.

    ``following`` is the next charted chord after the window in the same section, so a
    window ending on an applied dominant is explained by where the song actually goes.
    """
    out = []
    for i, ch in enumerate(chords):
        nxt = chords[i + 1] if i + 1 < len(chords) else following
        if _is_diatonic(ch, key_pc, minor):
            out.append(_numeral(_deg(ch, key_pc), ch.quality, minor))
        elif ch.quality == "dom" and nxt is not None and nxt.pc >= 0 and _down_fifth(ch, nxt):
            out.append("V" if _deg(nxt, key_pc) == 0 else f"V/{_numeral(_deg(nxt, key_pc), nxt.quality, minor)}")
        elif ch.quality == "dom" and nxt is not None and nxt.pc >= 0 and _down_half_step(ch, nxt):
            out.append(
                "subV" if _deg(nxt, key_pc) == 0 else f"subV/{_numeral(_deg(nxt, key_pc), nxt.quality, minor)}"
            )
        else:
            return ""
    return "–".join(out)


def _implied_target_quality(target_degree: int, half_dim_two: bool, minor: bool) -> str:
    """Quality of a ii–V's (absent) target: the key's own diatonic chord when unambiguous."""
    qualities = (_DIATONIC_MINOR if minor else _DIATONIC_MAJOR).get(target_degree, set())
    has_minor = bool(qualities & _MINORISH)
    has_major = bool(qualities & _MAJORISH)
    if has_minor and not has_major:
        return "minor"
    if has_major and not has_minor:
        return "major"
    return "minor" if half_dim_two else "major"


def _classify_pair(
    a: _Chord, b: _Chord, key_pc: int, minor: bool, following: _Chord | None = None
) -> _Rel:
    if a.pc == b.pc:
        return _Rel("color_change", "", 35.0, 0.4)
    if (
        (a.quality in _MINORISH or a.quality == "half-dim")
        and (b.quality == "dom" or (b.quality in ("major", "sus") and _deg(b, key_pc) == 7))
        and _down_fifth(a, b)
    ):
        half = a.quality == "half-dim"
        target_pc = (b.pc + 5) % 12
        target_quality = _implied_target_quality((target_pc - key_pc) % 12, half, minor)
        core = "iiø–V" if half else "ii–V"
        if (target_pc - key_pc) % 12 == 0:
            return _Rel("ii_V", core, 90.0, 0.95, target_pc, target_quality)
        target = _numeral((target_pc - key_pc) % 12, target_quality, minor)
        return _Rel("ii_V", f"{core} of {target}", 84.0, 0.9, target_pc, target_quality)
    if a.quality == "dom" and b.quality == "dom" and _down_fifth(a, b):
        label = "V/V–V" if _deg(b, key_pc) == 7 else "dominant chain"
        return _Rel("dominant_chain", label, 80.0 if label == "V/V–V" else 76.0, 0.9, (b.pc + 5) % 12, "major")
    if _dominant_function(a, key_pc) and (b.quality in _MAJORISH or b.quality in _MINORISH) and _down_fifth(a, b):
        if _deg(b, key_pc) == 0:
            return _Rel("V_I", "V–i" if b.quality in _MINORISH else "V–I", 88.0, 0.95, b.pc, b.quality)
        target = _numeral(_deg(b, key_pc), b.quality, minor)
        score = 80.0 if _is_diatonic(b, key_pc, minor) else 74.0
        return _Rel("secondary_dominant", f"V/{target}–{target}", score, 0.9, b.pc, b.quality)
    if (a.quality in _MINORISH or a.quality == "half-dim") and b.quality == "dom" and _down_half_step(a, b):
        target_pc = (b.pc - 1) % 12  # ii a whole step above the target, subV a half step above
        target_quality = _implied_target_quality((target_pc - key_pc) % 12, a.quality == "half-dim", minor)
        if (target_pc - key_pc) % 12 == 0:
            return _Rel("ii_subV", "ii–subV", 86.0, 0.9, target_pc, target_quality)
        target = _numeral((target_pc - key_pc) % 12, target_quality, minor)
        return _Rel("ii_subV", f"ii–subV of {target}", 80.0, 0.85, target_pc, target_quality)
    if a.quality == "dom" and (b.quality in _MAJORISH or b.quality in _MINORISH) and _down_half_step(a, b):
        if _deg(b, key_pc) == 0:
            return _Rel("subV_I", "subV–i" if b.quality in _MINORISH else "subV–I", 84.0, 0.9, b.pc, b.quality)
        target = _numeral(_deg(b, key_pc), b.quality, minor)
        return _Rel("subV_I", f"subV/{target}–{target}", 74.0, 0.85, b.pc, b.quality)
    if (
        _dominant_function(a, key_pc)
        and (b.pc - a.pc) % 12 == 2
        and (b.quality in _MINORISH or (minor and b.quality in _MAJORISH))
    ):
        prefix = "V" if _deg(a, key_pc) == 7 else _numeral(_deg(a, key_pc), a.quality, minor)
        label = f"{prefix}–{_numeral(_deg(b, key_pc), b.quality, minor)} (deceptive)"
        return _Rel("deceptive", label, 60.0, 0.75, b.pc, b.quality)
    if _is_diatonic(a, key_pc, minor) and _is_diatonic(b, key_pc, minor):
        table = _PAIR_SCORES_MINOR if minor else _PAIR_SCORES_MAJOR
        score = table.get((_deg(a, key_pc), _deg(b, key_pc)), 64.0 if _down_fifth(a, b) else 55.0)
        return _Rel("diatonic", _functional_path((a, b), key_pc, minor), score, 0.8)
    path = _functional_path((a, b), key_pc, minor, following)
    if path:
        return _Rel("applied", path, 58.0, 0.75)
    if a.quality in _MAJORISH and b.quality in _MAJORISH and (b.pc - a.pc) % 12 in (3, 4, 8, 9):
        return _Rel("chromatic_mediant", "chromatic mediant", 50.0, 0.6)
    if _scale_collections((a, b)):
        return _Rel("shared_scale", "", 45.0, 0.5)
    return _Rel("adjacent", "", 30.0, 0.3)


def _classify_triple(
    chords: Sequence[_Chord], key_pc: int, minor: bool, following: _Chord | None = None
) -> _Rel:
    a, b, c = chords
    head = _classify_pair(a, b, key_pc, minor, c)
    tail = _classify_pair(b, c, key_pc, minor, following)
    tonic_c = _deg(c, key_pc) == 0
    if head.rel_id == "ii_V" and _down_fifth(b, c):
        half = a.quality == "half-dim"
        if c.quality in _MINORISH or c.quality in _MAJORISH or (c.quality == "dom" and tonic_c):
            if tonic_c:
                core = ("iiø–V" if half else "ii–V") + ("–i" if c.quality in _MINORISH else "–I")
                return _Rel("ii_V_I", core, 98.0 if half else 100.0, 0.95, c.pc, c.quality)
            target = _numeral(_deg(c, key_pc), c.quality, minor)
            core = "iiø–V" if half else "ii–V"
            return _Rel("ii_V_I", f"{core} → {target}", 92.0 if half else 94.0, 0.9, c.pc, c.quality)
        if c.quality == "dom":
            return _Rel("ii_V_chain", "ii–V chain", 82.0, 0.85, (c.pc + 5) % 12, "major")
    if head.rel_id == "ii_subV" and _down_half_step(b, c) and (c.quality in _MAJORISH or c.quality in _MINORISH):
        tonic_word = "i" if c.quality in _MINORISH else "I"
        if tonic_c:
            return _Rel("ii_subV_I", f"ii–subV–{tonic_word}", 96.0, 0.9, c.pc, c.quality)
        target = _numeral(_deg(c, key_pc), c.quality, minor)
        return _Rel("ii_subV_I", f"ii–subV → {target}", 90.0, 0.85, c.pc, c.quality)
    if a.quality == "dom" and _dominant_function(b, key_pc) and _down_fifth(a, b) and _down_fifth(b, c):
        if c.quality in _MAJORISH or c.quality in _MINORISH or (c.quality == "dom" and tonic_c):
            if _deg(b, key_pc) == 7 and tonic_c:
                label = "V/V–V–i" if c.quality in _MINORISH else "V/V–V–I"
                return _Rel("dominant_resolution", label, 92.0, 0.95, c.pc, c.quality)
            target = _numeral(_deg(c, key_pc), c.quality, minor)
            return _Rel("dominant_resolution", f"dominant chain → {target}", 84.0, 0.9, c.pc, c.quality)
        if c.quality == "dom":
            return _Rel("dominant_chain", "dominant chain", 80.0, 0.9, (c.pc + 5) % 12, "major")
    path = _functional_path(chords, key_pc, minor, following)
    degrees = tuple(_deg(ch, key_pc) for ch in chords)
    if path and all(_is_diatonic(ch, key_pc, minor) for ch in chords):
        if degrees == (5, 7, 0):
            return _Rel("cadence", path, 85.0, 0.9, c.pc, c.quality)
        if _down_fifth(a, b) and _down_fifth(b, c):
            return _Rel("circle_of_fifths", path, 82.0 if degrees[2] == 7 else 80.0, 0.85)
    best = max(head.score, tail.score)
    if path:
        return _Rel("diatonic", path, best * 0.8 + 8.0, 0.8)
    return _Rel("mixed", "", best * 0.8, min(head.confidence, tail.confidence))


def _scale_collections(chords: Sequence[_Chord]) -> list[tuple[int, str]]:
    tones: set[int] = set()
    for ch in chords:
        tones |= ch.tones
    found = []
    for kind, steps in (("major", _MAJOR_SCALE), ("harmonic minor", _HARMONIC_MINOR_SCALE)):
        for tonic in range(12):
            if tones <= {(tonic + s) % 12 for s in steps}:
                found.append((tonic, kind))
    return found


def _common_scales(chords: Sequence[_Chord], key_center: str, key_pc: int, minor: bool) -> tuple[str, ...]:
    from music_theory import spell_note_in_key

    home = ((key_pc + 3) % 12, "major") if minor else (key_pc, "major")
    home_minor = (key_pc, "harmonic minor") if minor else ((key_pc + 9) % 12, "harmonic minor")
    found = _scale_collections(chords)
    found.sort(key=lambda t: (t != home, t != home_minor, t[1] != "major", t[0]))
    return tuple(f"{spell_note_in_key(pc, key_center)} {kind}" for pc, kind in found[:3])


def _voice_leading(chords: Sequence[_Chord]) -> tuple[tuple[int, ...], int, float]:
    commons: list[int] = []
    cost = 0
    moves = 0
    for a, b in zip(chords, chords[1:]):
        commons.append(len(a.tones & b.tones))
        for t in sorted(a.tones):
            cost += min(min((t - u) % 12, (u - t) % 12) for u in b.tones) if b.tones else 6
            moves += 1
    avg = cost / moves if moves else 6.0
    return tuple(commons), cost, avg


@dataclass(frozen=True)
class _Located:
    section_index: int
    section_label: str
    event_index: int
    event: ChordEvent
    display_offset: int
    display_len: int


def analyze_harmonic_spans(
    section_rows: Sequence[SectionRow],
    *,
    key_center: str,
    length: int,
    source_id: str = "",
    allow_cross_section: bool = False,
    include_weak: bool = False,
) -> list[HarmonicSpan]:
    """Ranked contiguous spans of ``length`` chords (best first, deterministic)."""
    if length not in SCOPE_LENGTHS.values():
        raise ValueError(f"unsupported span length: {length}")
    scope = next(k for k, v in SCOPE_LENGTHS.items() if v == length)
    key_pc, minor = _key_info(key_center)
    progression_key = f"{source_id or 'progression'}#{progression_fingerprint(section_rows)}"

    located: list[_Located] = []
    cycles: dict[int, int] = {}
    offset = 0
    for si, (label, display, raw) in enumerate(section_rows):
        events = section_events(raw)
        cycles[si] = _cycle_length([e.chord for e in events])
        for ei, ev in enumerate(events):
            located.append(_Located(si, str(label), ei, ev, offset, max(1, len(display))))
        offset += len(display)

    first: dict[tuple[str, ...], tuple[list[_Located], _Chord | None]] = {}
    counts: dict[tuple[str, ...], int] = {}
    for start in range(len(located) - length + 1):
        win = located[start : start + length]
        cross = len({w.section_index for w in win}) > 1
        if cross and not allow_cross_section:
            continue
        if any(_parse(w.event.chord).pc < 0 for w in win):
            continue
        seq = tuple(w.event.chord for w in win)
        counts[seq] = counts.get(seq, 0) + 1
        if seq not in first:
            after = located[start + length] if start + length < len(located) else None
            same_section = after is not None and after.section_index == win[-1].section_index
            first[seq] = (win, _parse(after.event.chord) if same_section else None)

    spans = [
        _build_span(
            win, following, counts[seq], scope, length, key_center, key_pc, minor,
            source_id, progression_key, cycles,
        )
        for seq, (win, following) in first.items()
    ]
    spans.sort(key=lambda s: (-s.score, s.section_index, s.start_event))
    if not include_weak:
        strong = [s for s in spans if s.score >= WEAK_SCORE]
        if len(strong) >= MIN_STRONG_TO_HIDE_WEAK:
            spans = strong
    return spans


def _build_span(
    win: Sequence[_Located],
    following: _Chord | None,
    occurrences: int,
    scope: str,
    length: int,
    key_center: str,
    key_pc: int,
    minor: bool,
    source_id: str,
    progression_key: str,
    cycles: dict[int, int],
) -> HarmonicSpan:
    parsed = [_parse(w.event.chord) for w in win]
    if length == 2:
        rel = _classify_pair(parsed[0], parsed[1], key_pc, minor, following)
    else:
        rel = _classify_triple(parsed, key_pc, minor, following)
    head = win[0]
    cross = len({w.section_index for w in win}) > 1
    cycle = 0 if cross else cycles.get(head.section_index, 0)
    repeated = cycle == length and head.event_index % cycle == 0
    redundant_return = not cross and cycle == 2 and length == 3

    label = rel.label
    score = rel.score
    if repeated:
        noun = "vamp" if length == 2 else "loop"
        label = f"{label} {noun}" if label else ("modal vamp" if length == 2 else "repeated loop")
        score = max(score, 58.0) + 10.0
    score += 2.0 * (min(occurrences, 4) - 1)
    commons, vl_cost, vl_avg = _voice_leading(parsed)
    score += min(1.5, 0.5 * sum(commons)) + (2.0 if vl_avg <= 1.0 else 1.0 if vl_avg <= 1.5 else 0.0)
    if redundant_return:
        score -= 20.0
    if cross:
        score -= 15.0

    target_chord = ""
    target_roman = ""
    if rel.target_pc >= 0:
        target_roman = _numeral((rel.target_pc - key_pc) % 12, rel.target_quality, minor)
        if parsed[-1].pc == rel.target_pc:
            target_chord = parsed[-1].symbol
    path = _functional_path(parsed, key_pc, minor, following)
    roman_confident = bool(path)
    roman = (
        tuple(path.split("–"))
        if path
        else tuple(_numeral(_deg(p, key_pc), p.quality, minor) for p in parsed)
    )
    last = win[-1]
    return HarmonicSpan(
        span_id=f"{progression_key}|s{head.section_index}|e{head.event_index}-{head.event_index + length - 1}"
        + ("|x" if cross else ""),
        progression_key=progression_key,
        source_id=source_id,
        scope=scope,
        length=length,
        section_index=head.section_index,
        section_label=head.section_label if not cross else f"{head.section_label} → {last.section_label}",
        start_event=head.event_index,
        end_event=last.event_index,
        raw_start=head.event.raw_index,
        raw_end=last.event.raw_index + last.event.bars - 1,
        chords=tuple(w.event.chord for w in win),
        raw_events=tuple(w.event for w in win),
        display_global_indices=tuple(w.display_offset + w.event_index % w.display_len for w in win),
        key_center=str(key_center or "C"),
        relationship=rel.rel_id,
        relationship_label=label,
        roman=roman,
        roman_confident=roman_confident,
        score=round(score, 2),
        confidence=rel.confidence,
        target_chord=target_chord,
        target_roman=target_roman,
        common_scales=_common_scales(parsed, key_center, key_pc, minor),
        common_tones=commons,
        voice_leading_cost=vl_cost,
        repeated_vamp=repeated,
        occurrences=occurrences,
        cross_section=cross,
    )


def best_fitting_key(section_rows: Sequence[SectionRow], candidates: Sequence[str]) -> str:
    """The candidate key the charted chords actually sit in (first wins ties).

    Only arbitrates between keys the app already supplies (e.g. the authoritative
    Practice Key and the progression's own key center) so Roman labels never describe
    chords against a key they are not in — it never invents a key of its own.
    """
    keys = [str(k).strip() for k in candidates if str(k or "").strip()]
    if not keys:
        return "C"
    chords = [_parse(e.chord) for _l, _d, raw in section_rows for e in section_events(raw)]
    chords = [c for c in chords if c.pc >= 0]

    def fit(key: str) -> int:
        key_pc, minor = _key_info(key)
        diatonic = sum(2 for c in chords if _is_diatonic(c, key_pc, minor))
        cadences = sum(
            3
            for a, b in zip(chords, chords[1:])
            if _deg(b, key_pc) == 0 and (_down_fifth(a, b) or _down_half_step(a, b)) and a.quality == "dom"
        )
        return diatonic + cadences

    best = keys[0]
    best_fit = fit(best)
    for key in keys[1:]:
        score = fit(key)
        if score > best_fit:
            best, best_fit = key, score
    return best


def span_display_label(
    span: HarmonicSpan,
    *,
    project: Callable[[str], str] | None = None,
    include_section: bool = False,
) -> str:
    """``Dm7 → G7 · ii–V`` — chords projected for display; labels are key-relative."""
    proj = project or (lambda ch: ch)
    parts = [" → ".join(proj(ch) or ch for ch in span.chords)]
    if span.relationship_label:
        parts.append(span.relationship_label)
    if include_section and span.section_label:
        parts.append(span.section_label)
    return " · ".join(parts)


def find_span(spans: Sequence[HarmonicSpan], span_id: str) -> HarmonicSpan | None:
    return next((s for s in spans if s.span_id == span_id), None)


__all__ = [
    "ChordEvent",
    "HarmonicSpan",
    "MIN_STRONG_TO_HIDE_WEAK",
    "SCOPE_LENGTHS",
    "SCOPE_SINGLE",
    "SCOPE_SPAN2",
    "SCOPE_SPAN3",
    "WEAK_SCORE",
    "analyze_harmonic_spans",
    "best_fitting_key",
    "find_span",
    "progression_fingerprint",
    "section_events",
    "span_display_label",
]
