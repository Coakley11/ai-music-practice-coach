"""Deterministic melody audit: label every note by its relation to the sounding chord.

Single source of truth for "what chord is sounding at beat X" and "is this pitch a chord
tone / extension / passing / neighbor / chromatic approach / non-harmonic".  The melody
generator (composition_melody_engine) and the tests both use it, so generated notes and
the audit can never disagree about harmony.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from music_theory import (
    key_is_minor,
    normalize_chord_for_theory,
    pitch_class_from_spelled_note,
    spell_chord_tones,
    split_chord,
    split_key_center,
)

LABEL_CHORD_TONE = "chord_tone"
LABEL_EXTENSION = "extension"
LABEL_PASSING = "passing"
LABEL_NEIGHBOR = "neighbor"
LABEL_CHROMATIC_APPROACH = "chromatic_approach"
LABEL_NON_HARMONIC = "non_harmonic"
LABEL_REST = "rest"

_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)


def is_rest_event(ev: dict[str, Any]) -> bool:
    return bool(ev.get("is_rest") or str(ev.get("pitch") or "").strip().lower() == "rest")


def tonic_pc(key: str) -> int:
    tonic, _mode = split_key_center(key)
    return int(pitch_class_from_spelled_note(tonic)) % 12


def key_scale_pcs(key: str) -> set[int]:
    t = tonic_pc(key)
    base = _MINOR_SCALE if key_is_minor(key) else _MAJOR_SCALE
    pcs = {(t + s) % 12 for s in base}
    if key_is_minor(key):
        pcs.add((t + 11) % 12)  # harmonic-minor leading tone is idiomatic, not chromatic
    return pcs


@dataclass(frozen=True)
class ChordInfo:
    symbol: str
    root_pc: int
    tone_pcs: tuple[int, ...]
    tone_names: tuple[str, ...]
    quality: str  # maj | min | dom | hdim | dim | aug | sus
    ext_pcs: frozenset[int] = field(default_factory=frozenset)

    @property
    def is_dominant(self) -> bool:
        return self.quality == "dom"

    @property
    def third_pc(self) -> int | None:
        return self.tone_pcs[1] if len(self.tone_pcs) > 1 else None

    @property
    def seventh_pc(self) -> int | None:
        return self.tone_pcs[3] if len(self.tone_pcs) > 3 else None

    def name_for_pc(self, pc: int) -> str | None:
        for p, n in zip(self.tone_pcs, self.tone_names):
            if p == pc % 12:
                return n
        return None


def _quality(suffix: str) -> str:
    raw = str(suffix or "")
    s = raw.lower()
    if s.startswith("sus"):
        return "sus"
    if "m7b5" in s or "ø" in s or "hdim" in s:
        return "hdim"
    if s.startswith(("dim", "o", "°")):
        return "dim"
    if s.startswith(("aug", "+")):
        return "aug"
    if raw.startswith(("M", "Δ")) or s.startswith(("maj", "ma")):
        return "maj"
    if s.startswith("m") or s.startswith("-"):
        return "min"
    if re.match(r"^(7|9|11|13|dom)", s):
        return "dom"
    return "maj"


_INFO_CACHE: dict[tuple[str, str], ChordInfo | None] = {}


def chord_info(chord: str, key: str = "C") -> ChordInfo | None:
    sym = str(chord or "").strip()
    if not sym or sym == "%":
        return None
    ck = (sym, "")
    if ck in _INFO_CACHE:
        return _INFO_CACHE[ck]
    head = normalize_chord_for_theory(sym).split("/", 1)[0].strip() or sym.split("/", 1)[0]
    root, suffix = split_chord(head)
    try:
        names = tuple(spell_chord_tones(sym, reference_key=key) or ())
        pcs = tuple(int(pitch_class_from_spelled_note(n)) % 12 for n in names)
    except Exception:
        names, pcs = (), ()
    if not pcs:
        _INFO_CACHE[ck] = None
        return None
    q = _quality(suffix)
    r = pcs[0]
    if q == "maj":
        ext = {(r + 2) % 12, (r + 9) % 12, (r + 6) % 12}  # 9, 6/13, #11 (lydian colour)
    elif q == "min":
        ext = {(r + 2) % 12, (r + 5) % 12}  # 9, 11
    elif q == "dom":
        ext = {(r + 2) % 12, (r + 9) % 12}  # 9, 13
    else:
        ext = set()
    ext -= set(pcs)
    info = ChordInfo(sym, r, pcs, names, q, frozenset(ext))
    _INFO_CACHE[ck] = info
    return info


def bar_beats(meter: str) -> float:
    try:
        from composition_melody_notation import beats_per_bar

        return max(1.0, float(beats_per_bar(meter)))
    except Exception:
        return 4.0


def is_compound(meter: str) -> bool:
    try:
        from composition_hum_transcription import is_compound_meter

        return bool(is_compound_meter(meter))
    except Exception:
        return False


def strong_offsets(bar: float, compound: bool) -> tuple[float, ...]:
    """Beat offsets (within a bar) that are structurally strong."""
    if compound:
        return (0.0, 3.0) if int(bar) % 6 == 0 and bar >= 6 else (0.0,)
    if bar >= 4 and int(bar) % 2 == 0:
        return (0.0, bar / 2.0)
    return (0.0,)


def chord_segments(chords: list[str], meter: str = "4/4") -> list[tuple[float, float, str]]:
    """(start_beat, end_beat, chord symbol) for the whole progression (one token per bar)."""
    from chord_subdivisions import parse_subdivisions

    bar = bar_beats(meter)
    out: list[tuple[float, float, str]] = []
    for bi, token in enumerate(chords or []):
        subs = parse_subdivisions(str(token), beats_per_bar=bar)
        if not subs:
            continue
        cur = bi * bar
        for sub in subs:
            out.append((cur, cur + float(sub.weight), str(sub.chord)))
            cur += float(sub.weight)
    return out


def chord_at_beat(segments: list[tuple[float, float, str]], beat: float) -> str:
    for a, b, sym in segments:
        if a - 1e-6 <= beat < b - 1e-6:
            return sym
    return segments[-1][2] if segments and beat >= segments[-1][1] - 1e-6 else ""


def secondary_dominant_label(chord: ChordInfo | None, key: str) -> str:
    """'V7/V' style label when a dominant-quality chord is not the key's own V7."""
    if chord is None or not chord.is_dominant:
        return ""
    t = tonic_pc(key)
    target = (chord.root_pc + 5) % 12  # a dominant resolves up a 4th
    rel = (target - t) % 12
    if rel == 0:
        return "V7"
    degrees = {2: "ii", 4: "iii", 5: "IV", 7: "V", 9: "vi"}
    if key_is_minor(key):
        degrees = {3: "III", 5: "iv", 7: "v", 8: "VI", 10: "VII"}
    deg = degrees.get(rel)
    return f"V7/{deg}" if deg else ""


def _midi_of(ev: dict[str, Any]) -> int | None:
    try:
        return int(ev["midi"]) if ev.get("midi") is not None else None
    except (TypeError, ValueError):
        return None


def audit_melody(
    events: list[dict[str, Any]],
    chords: list[str],
    *,
    key: str = "C",
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    """Label every event.  Row keys: index, beat, measure, beat_in_bar, strong, chord, label,
    chromatic, resolved, function, roman, midi, pitch."""
    from roman_numeral_analysis import chord_to_roman

    bar = bar_beats(meter)
    comp = is_compound(meter)
    strong_set = strong_offsets(bar, comp)
    segs = chord_segments(chords, meter)
    scale = key_scale_pcs(key)
    evs = [dict(e) for e in events or [] if isinstance(e, dict)]
    # absolute onsets
    onsets: list[float] = []
    cur = 0.0
    for e in evs:
        try:
            b = float(e["beat"]) if e.get("beat") is not None else cur
        except (TypeError, ValueError):
            b = cur
        onsets.append(b)
        cur = max(cur, b + float(e.get("duration_beats") or 1.0))

    rows: list[dict[str, Any]] = []
    for i, e in enumerate(evs):
        b = onsets[i]
        sym = chord_at_beat(segs, b)
        info = chord_info(sym, key) if sym else None
        in_bar = b - int(b // bar) * bar
        seg_start = next((a for a, z, s in segs if a - 1e-6 <= b < z - 1e-6), None)
        strong = any(abs(in_bar - s) < 1e-6 for s in strong_set) or (
            seg_start is not None and abs(seg_start - b) < 1e-6
        )
        row: dict[str, Any] = {
            "index": i, "beat": b, "measure": int(b // bar) + 1, "beat_in_bar": in_bar,
            "strong": bool(strong), "chord": sym, "midi": _midi_of(e), "pitch": e.get("pitch"),
            "label": LABEL_REST, "chromatic": False, "resolved": True, "function": "",
            "roman": "", "duration_beats": float(e.get("duration_beats") or 1.0),
        }
        if is_rest_event(e) or row["midi"] is None:
            rows.append(row)
            continue
        m = int(row["midi"])
        pc = m % 12
        chromatic = pc not in scale
        row["chromatic"] = chromatic
        try:
            row["roman"] = chord_to_roman(sym, key) if sym else ""
        except Exception:
            row["roman"] = ""
        sec = secondary_dominant_label(info, key)
        if sec:
            row["roman"] = f"{row['roman']} ({sec})" if sec != "V7" else row["roman"]
        prev_ev = evs[i - 1] if i > 0 and not is_rest_event(evs[i - 1]) else None
        next_ev = evs[i + 1] if i + 1 < len(evs) and not is_rest_event(evs[i + 1]) else None
        pm = _midi_of(prev_ev) if prev_ev else None
        nm = _midi_of(next_ev) if next_ev else None
        next_info = None
        if next_ev is not None:
            nsym = chord_at_beat(segs, onsets[i + 1])
            next_info = chord_info(nsym, key) if nsym else None
        _next_ok = (
            nm is not None and next_info is not None and (nm % 12) in next_info.tone_pcs
        )
        _approach = bool(chromatic and nm is not None and abs(nm - m) == 1 and _next_ok)
        if info and pc in info.tone_pcs:
            row["label"] = LABEL_CHORD_TONE
            deg = {0: "root", 1: "3rd", 2: "5th", 3: "7th"}.get(info.tone_pcs.index(pc), "tone")
            row["function"] = f"{deg} of {info.symbol}" + (f" ({sec})" if sec and sec != "V7" else "")
            if info.is_dominant and chromatic and pc == info.third_pc:
                # leading-tone style third of a (secondary) dominant: must step up a semitone
                nxt_m = nm if (nm is not None or next_ev is None) else None
                row["resolved"] = bool(next_ev is None or (nxt_m is not None and nxt_m - m == 1))
                row["function"] += "; leading-tone third resolves up" if row["resolved"] else "; UNRESOLVED"
        elif _approach:
            row["label"] = LABEL_CHROMATIC_APPROACH
            row["function"] = "chromatic approach to a chord tone"
        elif info and pc in info.ext_pcs:
            row["label"] = LABEL_EXTENSION
            row["function"] = f"extension over {info.symbol}"
            if chromatic:  # e.g. #11 over maj7: only acceptable when it resolves
                row["resolved"] = bool(
                    nm is not None and next_info is not None
                    and abs(nm - m) <= 2 and (nm % 12) in next_info.tone_pcs
                )
        else:
            target_ok = (
                nm is not None and next_info is not None and (nm % 12) in next_info.tone_pcs
            )
            step_in = pm is not None and abs(m - pm) <= 2 and m != pm
            step_out = nm is not None and abs(nm - m) <= 2 and nm != m
            if chromatic and nm is not None and abs(nm - m) == 1 and target_ok:
                row["label"] = LABEL_CHROMATIC_APPROACH
                row["function"] = "chromatic approach to a chord tone"
            elif pm is not None and nm is not None and step_in and step_out and (m - pm) * (nm - m) > 0:
                row["label"] = LABEL_PASSING
                row["function"] = "passing tone"
                if chromatic:
                    row["resolved"] = bool(target_ok)
            elif pm is not None and nm is not None and pm == nm and step_in and step_out:
                row["label"] = LABEL_NEIGHBOR
                row["function"] = "neighbor tone"
                if chromatic:
                    row["resolved"] = bool(target_ok)
            else:
                row["label"] = LABEL_NON_HARMONIC
                row["function"] = "non-harmonic"
                row["resolved"] = False
        rows.append(row)
    return rows


def audit_violations(rows: list[dict[str, Any]]) -> list[str]:
    """Rule breaches: strong-beat notes must be chord tones / extensions; non-chord-tone
    chromatics must be resolved chromatic approach tones; nothing may be non-harmonic."""
    bad: list[str] = []
    for r in rows:
        if r["label"] == LABEL_REST:
            continue
        where = f"m{r['measure']} beat {r['beat_in_bar'] + 1:g} {r['pitch']} over {r['chord']}"
        if r["strong"] and r["label"] not in {LABEL_CHORD_TONE, LABEL_EXTENSION}:
            bad.append(f"{where}: strong-beat note is {r['label']}")
        if r["label"] == LABEL_NON_HARMONIC:
            bad.append(f"{where}: unjustified non-harmonic tone")
        if r["chromatic"] and r["label"] != LABEL_CHORD_TONE and not r["resolved"]:
            bad.append(f"{where}: chromatic note without resolution")
    return bad
