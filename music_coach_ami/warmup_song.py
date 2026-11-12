"""AMI adaptive warmups, Slice 2a: song-aware guide-tone preparation.

Reads the active song's authoritative chart snapshot (read-only), builds the harmonic timeline of one section (split bars included), and writes a
guide-tone line (the third and seventh of each ACTUAL chord) in the pitch the player reads, voice-led across the changes.

Nothing here parses chord symbols on its own: chord quality comes from ``scale_pattern_harmony._classify`` and the chord's tones from
``scale_pattern_harmony.chord_tone_roles`` (computed from the symbol), beats from ``timeline_segments``. A chord the existing components cannot
classify, a chord with no third (sus), or one that cannot be spelled without a double accidental is reported by name and bar and answered with
correctly timed rests - never a guessed note. Every pitch is checked after the fact against ``chord_tone_roles`` of the chart's own chord.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami import warmup_engine as we

FAMILY = "guide_tones"
LABEL = "Guide tones"
SUPPORTED_KINDS = {"major", "major_lydian", "minor", "half_diminished", "minor_major", "dominant", "altered", "lydian_dominant"}
BPM = {"Beginner": 52, "Intermediate": 72, "Advanced": 96}
MIN_SUPPORTED_SHARE = Fraction(1, 2)          # a partial exercise is offered only when at least half the harmonic time can be written correctly
_LETTERS = "CDEFGAB"
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# (tones, first tone, rhythm style) per variant, in the order the planner adds them. Different levels change the music, not just the tempo.
VARIANTS: dict[str, list[tuple[str, str, str]]] = {
    "Beginner": [("thirds", "", "held"), ("sevenths", "", "held"), ("both", "third", "held"), ("both", "seventh", "held")],
    "Intermediate": [("both", "auto", "steady"), ("thirds", "", "pulse"), ("sevenths", "", "pulse"), ("both", "seventh", "steady")],
    "Advanced": [("both", "auto", "cells"), ("both", "auto", "eighths"), ("both", "seventh", "cells"), ("sevenths", "", "eighths"), ("thirds", "", "eighths")],
}
STYLE_LABEL = {"held": "long notes", "steady": "steady quarter notes", "pulse": "a steady pulse", "cells": "mixed quarter and eighth notes", "eighths": "continuous eighth notes"}
TONES_LABEL = {"thirds": "thirds", "sevenths": "sevenths", "both": "thirds and sevenths"}


def _clean(value: object) -> str:
    return str(value or "").strip()


class SongUnavailable(we.WarmupUnavailable):
    """The chord-aware item cannot be built trustworthily; the message says why (shown to the player)."""


# ---------------------------------------------------------------- reading the chart (read-only)


def read_song(ctx: Any) -> tuple[dict[str, Any] | None, str]:
    """(song record, '') from the coach's authoritative chart snapshot, or (None, why not). Nothing is written anywhere."""
    snap = ((getattr(ctx, "extra", None) or {}).get("chart_snapshot")) or {}
    if not snap or not snap.get("chart_verified", True):
        return None, _clean(snap.get("chart_unverified_reason")) or "I can't read the active song's chart right now"
    raw = snap.get("chart_sections_raw") or {}
    sections = {str(k): [str(c) for c in v] for k, v in raw.items() if v}
    if not sections or not snap.get("chart_available"):
        return None, "the active song has no chords to build on"
    title = _clean(snap.get("chart_title") or getattr(ctx, "active_song_title", ""))
    record = {"title": title, "practice_key": _clean(snap.get("practice_key")) or "C", "original_key": _clean(snap.get("original_key")),
              "meter": _clean(snap.get("chart_meter")) or "4/4", "source": _clean(snap.get("chart_source")), "sections": sections,
              "order": list(sections), "active_section": _clean(snap.get("active_section")) or next(iter(sections))}
    record["hash"] = hashlib.sha1(json.dumps([record["title"], record["practice_key"], record["meter"], sections], sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return record, ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(text).lower()).strip()


_GENERIC_TARGET = re.compile(r"^(?:the|this|that|these|those|my|our|your|a|an)?\s*(?:chorus|choruses|changes|chord changes|chords|chord progression|progression|song|tune|form|head|"
                             r"solo section|solos?|soloing|improvisation|improvising|bridge|verse|intro|outro|section [a-z0-9]+|[a-z0-9] section|chart|whole (?:song|tune|form|chorus)|"
                             r"entire (?:song|tune|form|chorus)|full (?:song|tune|form|chorus))$")


def named_song_conflict(phrase: str, song: dict[str, Any]) -> str:
    """'' when the phrase refers to the active song (or to nothing in particular); otherwise the name the musician used for another song."""
    p = _norm(phrase)
    if not p or _GENERIC_TARGET.match(p):
        return ""
    t = _norm(song.get("title") or "")
    if t and (t in p or (len(p) >= 3 and p in t)):
        return ""
    for name in song.get("order", []):                       # "over the bridge", "over section b"
        n = _norm(name)
        if n and (n == p or n in p or p in n):
            return ""
    return _clean(phrase)


def _aliases(name: str) -> list[str]:
    """How a musician might say a section: its name, and the words inside brackets or around a slash ('B (Bridge)' -> 'bridge', 'Final A / Outro' -> 'outro')."""
    out = [_norm(name)]
    for part in re.split(r"[()/]", name):
        n = _norm(part)
        if n and n not in out:
            out.append(n)
    return [a for a in out if a]


def find_section(order: list[str], text: str) -> str:
    """The section of THIS song a message names ('A3', 'the bridge', 'section b', 'outro'), or ''. Matched against the song's own section names, longest first."""
    t = f" {_norm(text)} "
    for name in sorted(order, key=lambda n: -len(_norm(n))):
        for a in _aliases(name):
            if len(a) == 1 and not re.search(rf" (?:section|part) {re.escape(a)} | {re.escape(a)} section ", t):
                continue                                         # a lone letter is a section only when it is called one
            if f" {a} " in t:
                return name
    return ""


_NOT_THE_FORM = r"\b(?:intro|outro|coda|tag|ending|turnaround|interlude|break)\b"
MAX_FORM_BARS = 64
WHOLE_FORM_NAME = "Whole form"


def section_slots(song: dict[str, Any], name: str) -> list[str]:
    """The bar slots of a section; a derived section (the whole form) is the chart's own sections end to end."""
    derived = (song.get("derived") or {}).get(name)
    if derived:
        return [slot for part in derived for slot in song["sections"].get(part, [])]
    return list(song["sections"].get(name) or [])


def section_parts(song: dict[str, Any], name: str) -> list[tuple[str, int, int]]:
    """[(real section, first bar, last bar)] of a section as numbered in the exercise (1-based, continuing across the parts of a derived section)."""
    parts = (song.get("derived") or {}).get(name) or [name]
    out, at = [], 0
    for part in parts:
        n = len(song["sections"].get(part, []))
        out.append((part, at + 1, at + n))
        at += n
    return out


def whole_form(song: dict[str, Any]) -> tuple[list[str], str, str]:
    """(the sections that make up the written form, how it was found, why not when empty). Only sections the chart really has are used."""
    names = [n for n in song["order"] if song["sections"].get(n)]
    for n in names:
        if _norm(n) in ("head", "chorus", "form", "tune", "main"):
            return [n], "named_form", ""
    body = [n for n in names if not re.search(_NOT_THE_FORM, _norm(n))]
    if not body:
        return [], "", "this chart has no sections I can treat as its form"
    if sum(len(song["sections"][n]) for n in body) > MAX_FORM_BARS:
        return [], "", f"the whole form is longer than {MAX_FORM_BARS} bars; pick a section instead (for example “only the bridge”)"
    return body, ("all_sections" if len(body) > 1 else "single_section"), ""


def with_whole_form(song: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """(a copy of the song that also holds the derived whole-form section, how it was built, why not). The original sections are untouched."""
    parts, how, why = whole_form(song)
    if not parts:
        return song, "", why
    if len(parts) == 1:
        return song, how, ""
    out = dict(song)
    out["derived"] = {**(song.get("derived") or {}), WHOLE_FORM_NAME: list(parts)}
    out["order"] = [n for n in song["order"] if n != WHOLE_FORM_NAME] + [WHOLE_FORM_NAME]
    return out, how, ""


def pick_section(song: dict[str, Any], wanted: str = "") -> tuple[str, str]:
    """(section name, how it was chosen). ``wanted`` is the musician's word ('bridge', 'chorus', 'section b', ...); '' means the app's active section."""
    names = song["order"]
    w = _norm(wanted)
    if w:
        for name in names:
            if _norm(name) == w:
                return name, "named"
        for name in names:
            if w in _norm(name) or (len(_norm(name)) >= 2 and _norm(name) in w.split()):
                return name, "named"
        if w in ("bridge", "b section", "section b", "the bridge"):
            for name in names:
                if re.search(r"\b(bridge|b)\b", _norm(name)):
                    return name, "named"
        if w in ("chorus", "the chorus", "choruses", "head", "form", "whole song", "song", "tune", "chart", "changes", "progression"):
            for name in names:
                if _norm(name) in ("chorus", "head", "solo"):
                    return name, "named"
            return song["active_section"], "chorus_is_active_section"
    active = song["active_section"]
    if re.search(r"\b(?:intro|outro|coda|tag|ending|turnaround|interlude|break)\b", _norm(active)):
        for name in names:                                   # a soloist is not warmed up on a two-bar intro: prefer the form itself
            if _norm(name) in ("chorus", "head", "solo", "instrumental", "solos", "main"):
                return name, "not_an_intro"
        sized = [n for n in names if not re.search(r"\b(?:intro|outro|coda|tag|ending|turnaround|interlude|break)\b", _norm(n))]
        if sized:
            return max(sized, key=lambda n: len(song["sections"][n])), "not_an_intro"
    return active, "active_section"


# ---------------------------------------------------------------- the harmonic timeline


@dataclass(frozen=True)
class Seg:
    index: int
    src_bar: int            # 1-based bar of the SECTION
    beat: Fraction          # offset inside the bar
    beats: Fraction
    chord: str              # as charted (concert pitch)
    ok: bool
    reason: str
    info: dict[str, Any]


def build_timeline(song: dict[str, Any], section: str, bars: tuple[int, int] | None, offset: int, semitones: int) -> tuple[list[Seg], int, int]:
    """(segments, first bar, last bar) of the section's chart in beat order. Raises ``SongUnavailable`` when the chart cannot be timed honestly."""
    slots = section_slots(song, section)
    if not slots:
        raise SongUnavailable(f"“{section}” has no chords")
    if sph._beats_per_bar(song.get("meter") or "4/4") != 4:
        raise SongUnavailable(f"this chart is in {song.get('meter')}; chord-aware warmups are written in 4/4 for now")
    lo, hi = (1, len(slots)) if not bars else (max(1, int(bars[0])), min(len(slots), int(bars[1])))
    if lo > hi:
        raise SongUnavailable(f"{section} has {len(slots)} bars, so bars {bars[0]}–{bars[1]} don't exist")
    chosen = slots[lo - 1:hi]
    try:
        raw = sph.timeline_segments(chosen, len(chosen), song.get("meter") or "4/4")
    except ValueError as exc:
        raise SongUnavailable(f"I can't time this section's chords exactly ({exc})") from exc
    segs: list[Seg] = []
    for i, s in enumerate(raw):
        if (s.beats * 4) % 1:                              # nothing finer than a sixteenth can be rested honestly
            raise SongUnavailable("this chart has a chord change on a finer subdivision than I can notate")
        info = chord_info(s.chord, offset, semitones)
        ok = bool(info["ok"]) and (s.beats * 2) % 1 == 0
        reason = info["reason"] if not info["ok"] else ("a chord change shorter than I can notate here" if not ok else "")
        segs.append(Seg(i, lo + s.bar, s.beat, s.beats, s.chord, ok, reason, info))
    return segs, lo, hi


# ---------------------------------------------------------------- chords: tones and spelling (existing components do the classification)


def _spell_tones(root_letter: int, root_pc: int, third_pc: int, upper_pc: int | None, upper_steps: int) -> tuple[str, str, str | None]:
    root = sph._spell(root_letter, root_pc)
    third = sph._spell(root_letter + 2, third_pc)
    upper = sph._spell(root_letter + upper_steps, upper_pc) if upper_pc is not None else None
    return root, third, upper


def chord_info(chord: str, offset: int, semitones: int) -> dict[str, Any]:
    """Third and seventh (or sixth) of a charted chord, spelled for the CONCERT chart and for the WRITTEN staff. ``ok`` False says why not."""
    out: dict[str, Any] = {"ok": False, "reason": "", "chord": chord}
    try:
        root, quality = sph._split_chord(chord)
    except ValueError:
        out["reason"] = "not a chord symbol I can read"
        return out
    kind = sph._classify(quality)
    out["kind"], out["root"], out["quality"] = kind, root, quality
    if kind.startswith("unsupported"):
        out["reason"] = f"{kind.split(':', 1)[1]} chords aren't supported yet"
        return out
    if kind == "sus":
        out["reason"] = "a suspended chord has no third"
        return out
    if kind not in SUPPORTED_KINDS:
        out["reason"] = f"“{chord}” isn't a chord quality I can build guide tones for"
        return out
    roles = sph.chord_tone_roles(chord)
    thirds = [pc for pc, r in roles.items() if r == "3"]
    sevenths = [pc for pc, r in roles.items() if r == "7"]
    sixths = [pc for pc, r in roles.items() if r == "6"]
    if len(thirds) != 1:
        out["reason"] = "I can't find this chord's third"
        return out
    upper_role = "7" if sevenths else "6" if sixths else ""
    upper_pc = sevenths[0] if sevenths else sixths[0] if sixths else None
    upper_steps = 6 if sevenths else 5
    third_pc = thirds[0]
    root_pc = sph.pc_of(root)

    def spelled(shift: int, keep_root: bool) -> tuple[str, str, str | None]:
        want = (root_pc + shift) % 12
        letter0 = _LETTERS.index(root[0].upper())
        cands: list[int] = []
        base = root if keep_root else (sph.transpose_spelled(root, shift) if shift % 12 else root)
        cands.append(_LETTERS.index(base[0].upper()))
        for L in range(7):
            delta = (want - _LETTER_PC[_LETTERS[L]] + 6) % 12 - 6
            if abs(delta) <= 1 and L not in cands:
                cands.append(L)
        if keep_root:
            cands = [letter0]
        last: Exception | None = None
        for L in cands:
            try:
                return _spell_tones(L, want, (third_pc + shift) % 12, (upper_pc + shift) % 12 if upper_pc is not None else None, upper_steps)
            except ValueError as exc:
                last = exc
        raise ValueError(str(last))

    try:
        c_root, c_third, c_upper = spelled(0, True)
        w_root, w_third, w_upper = spelled(offset, False)
    except ValueError:
        out["reason"] = "its tones can't be written for this instrument without double accidentals"
        return out
    suffix = chord[len(root):] if chord.startswith(root) else quality
    suffix = suffix.split("/")[0]
    fifth_pcs = [pc for pc, r in roles.items() if r == "5"]
    fifth_c = fifth_w = None
    if fifth_pcs:
        try:
            fifth_c = sph._spell(_LETTERS.index(c_root[0].upper()) + 4, fifth_pcs[0])
            fifth_w = sph._spell(_LETTERS.index(w_root[0].upper()) + 4, (fifth_pcs[0] + offset) % 12)
        except ValueError:
            fifth_c = fifth_w = None                 # a fifth that cannot be written without a double accidental is left out, never respelled wrongly
    out["root_pc"], out["fifth_pc"] = root_pc, (fifth_pcs[0] if fifth_c else None)
    out.update({
        "ok": True, "third_pc": third_pc, "upper_pc": upper_pc, "upper_role": upper_role,
        "concert": {"root": c_root, "third": c_third, "upper": c_upper, "fifth": fifth_c}, "written": {"root": w_root, "third": w_third, "upper": w_upper, "fifth": fifth_w},
        "symbol_concert": chord.split("/")[0], "symbol_written": w_root + suffix, "slash_bass": "/" in chord,
        "note": "" if upper_role == "7" else ("a sixth chord: its sixth stands in for the seventh" if upper_role == "6" else "a triad: only its third is a guide tone"),
    })
    return out


# ---------------------------------------------------------------- rhythm per level


def _fill(beats: Fraction) -> list[Fraction]:
    out, left = [], Fraction(beats)
    for piece in (Fraction(4), Fraction(2), Fraction(1), Fraction(1, 2)):
        while left >= piece:
            out.append(piece)
            left -= piece
    return out


def _cells(style: str, beats: Fraction, two: bool) -> list[tuple[int, Fraction]]:
    """(which tone 0/1, beats) for one chord of ``beats``. With one tone only index 0 is used."""
    b = Fraction(beats)
    half = Fraction(1, 2)
    if not two:
        if style == "held":
            return [(0, d) for d in _fill(b)]
        if style in ("steady", "pulse"):
            return [(0, Fraction(1))] * int(b) + ([(0, half), (0, half)] if b % 1 else [])
        return [(0, half)] * int(b * 2)
    table: dict[str, dict[Fraction, list[tuple[int, Fraction]]]] = {
        "held": {Fraction(4): [(0, 2), (1, 2)], Fraction(3): [(0, 2), (1, 1)], Fraction(2): [(0, 1), (1, 1)], Fraction(1): [(0, 1)]},
        "steady": {Fraction(4): [(0, 1), (1, 1), (0, 1), (1, 1)], Fraction(3): [(0, 1), (1, 2)], Fraction(2): [(0, 1), (1, 1)], Fraction(1): [(0, half), (1, half)]},
        "cells": {Fraction(4): [(0, half), (1, half), (0, 1), (1, half), (0, half), (1, 1)], Fraction(3): [(0, half), (1, half), (0, half), (1, half), (1, 1)],
                  Fraction(2): [(0, half), (1, half), (0, half), (1, half)], Fraction(1): [(0, half), (1, half)]},
    }
    row = table.get(style, {}).get(b)
    if row is not None:
        return [(i, Fraction(d)) for i, d in row]
    return [(k % 2, half) for k in range(int(b * 2))]       # eighths (also the fallback for unusual lengths)


# ---------------------------------------------------------------- voice-leading (one Viterbi pass over every note)


@dataclass
class Slot:
    seg: int
    role: str          # '3' | '7' | '6'
    pc: int            # WRITTEN pitch class
    name: str          # written spelling
    beats: Fraction
    art: str = ""


def _candidates(pc: int, lo: int, hi: int) -> list[int]:
    return [m for m in range(lo, hi + 1) if m % 12 == pc % 12]


def _leap_cost(a: int, b: int, weight: float, boundary_resolution: bool, prev_role: str, role: str) -> float:
    d = abs(a - b)
    cost = weight * d + (weight * 2 if d > 7 else 0)
    if boundary_resolution and prev_role in ("7", "6") and role == "3":
        if a - b == 1:
            cost -= 6 * weight          # the seventh falls a half step onto the next chord's third
        elif a - b == 2:
            cost -= 3 * weight
    return cost


def lead(pieces: list[list[list[Slot]]], lo: int, hi: int, *, smooth: bool) -> tuple[list[int], list[int]]:
    """Exact Viterbi where the state is (last midi, last role): chosen order index per piece, then midi per slot (flattened in order)."""
    w = 3.0 if smooth else 1.0
    centre = (lo + hi) / 2.0
    # states after a piece: (midi, role) -> (cost, order index, entry state, per-slot midis)
    states: dict[tuple[int, str], tuple[float, int, Any, list[int]]] | None = None
    trail: list[dict[tuple[int, str], tuple[float, int, Any, list[int]]]] = []
    for p, orders in enumerate(pieces):
        new: dict[tuple[int, str], tuple[float, int, Any, list[int]]] = {}
        for oi, slots in enumerate(orders):
            # DP inside the order from each entry state (or from nothing for the first piece)
            entries: list[tuple[Any, float]] = [(None, 0.0)] if states is None else [(k, v[0]) for k, v in states.items()]
            for entry, base in entries:
                layer: dict[int, tuple[float, list[int]]] = {}
                for m in _candidates(slots[0].pc, lo, hi):
                    if entry is None:
                        c = 0.2 * abs(m - centre)
                    else:
                        pm, prole = entry
                        c = base + _leap_cost(pm, m, w, True, prole, slots[0].role) + 0.05 * abs(m - centre)
                    layer[m] = (c, [m])
                for k in range(1, len(slots)):
                    nxt: dict[int, tuple[float, list[int]]] = {}
                    for m in _candidates(slots[k].pc, lo, hi):
                        best = None
                        for pm, (c0, path) in layer.items():
                            c = c0 + _leap_cost(pm, m, w, False, "", "") + 0.05 * abs(m - centre)
                            if best is None or c < best[0]:
                                best = (c, path + [m])
                        nxt[m] = best  # type: ignore[assignment]
                    layer = nxt
                if not layer:
                    raise SongUnavailable("a guide tone has no playable octave in this instrument's window")
                for m, (c, path) in layer.items():
                    key = (m, slots[-1].role)
                    if key not in new or c < new[key][0]:
                        new[key] = (c, oi, entry, path)
        trail.append(new)
        states = new
    assert states is not None
    key = min(states, key=lambda k: states[k][0])
    orders_chosen: list[int] = []
    midis: list[list[int]] = []
    for layer in reversed(trail):
        cost, oi, entry, path = layer[key]
        orders_chosen.append(oi)
        midis.append(path)
        key = entry  # type: ignore[assignment]
    orders_chosen.reverse()
    midis.reverse()
    return orders_chosen, [m for path in midis for m in path]


# ---------------------------------------------------------------- the item


def _tone_slots(seg: Seg, tones: str, first: str, style: str, level: str, w_info: dict[str, Any]) -> list[list[Slot]]:
    """Alternative note orders for one chord (each a list of Slots covering the chord's beats)."""
    third = Slot(seg.index, "3", sph.pc_of(w_info["written"]["third"]), w_info["written"]["third"], Fraction(0))
    up_name = w_info["written"]["upper"]
    upper = Slot(seg.index, w_info["upper_role"], sph.pc_of(up_name), up_name, Fraction(0)) if up_name else None
    want = tones
    if want == "sevenths" and upper is None:
        want = "thirds"            # a triad has no seventh: its third stands in, and the chord is flagged in the explanation
    two = want == "both" and upper is not None
    seqs: list[tuple[Slot, Slot | None]]
    if two:
        seqs = [(third, upper), (upper, third)]
        if first == "third":
            seqs = seqs[:1]
        elif first == "seventh":
            seqs = seqs[1:]
    else:
        single = upper if want == "sevenths" else third
        seqs = [(single, None)]
    out: list[list[Slot]] = []
    for a, b in seqs:
        cells = _cells(style, seg.beats, two)
        slots = []
        for idx, d in cells:
            base = a if idx == 0 or b is None else b
            slots.append(Slot(seg.index, base.role, base.pc, base.name, d))
        if level == "Advanced" and slots:
            slots[0].art = "accent"
        out.append(slots)
    return out


def build(player: we.Player, level: str, song: dict[str, Any], section: str, bars: tuple[int, int] | None, *, tones: str, first: str, style: str,
          smooth: bool = False, title_suffix: str = "") -> we.Built:
    segs, b_lo, b_hi = build_timeline(song, section, bars, player.offset, player.semitones)
    good = [s for s in segs if s.ok]
    total = sum((s.beats for s in segs), Fraction(0))
    share = sum((s.beats for s in good), Fraction(0)) / total
    bad = [s for s in segs if not s.ok]
    if not good or share < MIN_SUPPORTED_SHARE:
        names = "; ".join(f"{s.chord} (bar {s.src_bar}): {s.reason}" for s in bad[:4])
        raise SongUnavailable(f"too much of {section} can't be written correctly to give you a trustworthy guide-tone exercise — {names}")
    lo, hi = player.window(level)
    if hi - lo < 12:
        raise SongUnavailable("this level's register window is too small for guide tones")
    pieces = [_tone_slots(s, tones, first, style, level, s.info) for s in good]
    orders, midis = lead(pieces, lo, hi, smooth=smooth)
    chosen = [pieces[p][o] for p, o in enumerate(orders)]
    flat: list[Slot] = [sl for piece in chosen for sl in piece]
    notes: list[we.Note] = []
    cursor = Fraction(0)
    by_seg: dict[int, list[tuple[Slot, int]]] = {}
    it = iter(midis)
    for sl in flat:
        by_seg.setdefault(sl.seg, []).append((sl, next(it)))
    placed: list[dict[str, Any]] = []
    for s in segs:
        # in a bar, everything before this segment is already placed; rests fill unsupported time
        if not s.ok:
            label = s.info.get("symbol_written") or _written_symbol(s.chord, player)
            for n in we.rests(s.beats):
                n.chord = label
                notes.append(n)
            placed.append({"seg": s.index, "bar": s.src_bar, "beat": float(s.beat), "beats": float(s.beats), "concert": s.chord, "written": label,
                           "supported": False, "reason": s.reason, "notes": []})
            continue
        row = []
        first_in_seg = True
        for sl, m in by_seg[s.index]:
            spelled = sl.name
            octave = sph.octave_for(spelled, m)
            note = we.Note(spelled, octave, next(k for k, v in we._DUR_BEATS.items() if v == sl.beats), sl.art)
            if first_in_seg:
                note.chord = s.info["symbol_written"]
                first_in_seg = False
            notes.append(note)
            row.append({"role": sl.role, "name": spelled, "midi": m, "beats": float(sl.beats)})
        placed.append({"seg": s.index, "bar": s.src_bar, "beat": float(s.beat), "beats": float(s.beats), "concert": s.chord, "written": s.info["symbol_written"],
                       "supported": True, "note": s.info.get("note", ""), "third": s.info["written"]["third"], "upper": s.info["written"]["upper"],
                       "upper_role": s.info["upper_role"], "concert_third": s.info["concert"]["third"], "concert_upper": s.info["concert"]["upper"], "notes": row})
    meta = _meta(placed, section, (b_lo, b_hi), song, tones, first, style, smooth, level, share)
    start = {"third": ", starting on the third", "seventh": ", starting on the seventh"}.get(first, "")
    built_title = (f"Guide tones: {TONES_LABEL[tones]}{start} over {section}" + (f" (bars {b_lo}–{b_hi})" if bars else "") + f" — {STYLE_LABEL.get(style, style)}"
                   + (", smoother voice-leading" if smooth else "") + title_suffix)
    how, listen = _explain(placed, meta, level, style, tones)
    return we.Built(notes=notes, bpm=BPM[level], title=built_title, how=how, listen=listen, meta=meta)


def _written_symbol(chord: str, player: we.Player) -> str:
    """A chord the exercise does not play, labelled the way the app labels chords for this instrument (the symbol only; no tones are derived)."""
    try:
        from music_theory import transpose_chord

        return transpose_chord(chord, int(player.semitones), reference_key=player.written_key) if player.semitones else chord
    except Exception:  # noqa: BLE001 - a label must never stop the exercise; the charted symbol is still true
        return chord


def _meta(placed: list[dict[str, Any]], section: str, bars: tuple[int, int], song: dict[str, Any], tones: str, first: str, style: str, smooth: bool, level: str,
          share: Fraction) -> dict[str, Any]:
    res: list[dict[str, Any]] = []
    flat: list[tuple[dict[str, Any], dict[str, Any]]] = [(p, n) for p in placed if p["supported"] for n in p["notes"]]
    for (p1, n1), (p2, n2) in zip(flat, flat[1:]):
        if p1["seg"] == p2["seg"] or p1["concert"] == p2["concert"]:
            continue
        if n1["role"] in ("7", "6") and n2["role"] == "3":
            d = n1["midi"] - n2["midi"]
            if d in (1, 2):
                res.append({"from_bar": p1["bar"], "to_bar": p2["bar"], "from_chord": p1["written"], "to_chord": p2["written"], "from_note": n1["name"], "to_note": n2["name"],
                            "step": "half step" if d == 1 else "whole step", "from_role": n1["role"]})
    leaps = [abs(b["midi"] - a["midi"]) for (_p, a), (_q, b) in zip(flat, flat[1:])]
    return {"song": song["title"], "song_hash": song["hash"], "section": section, "bars": [bars[0], bars[1]], "tones": tones, "first": first, "style": style, "smooth": smooth,
            "level": level, "segments": placed, "resolutions": res, "unsupported": [p for p in placed if not p["supported"]],
            "supported_share": float(share), "largest_leap": max(leaps) if leaps else 0, "mean_leap": round(sum(leaps) / len(leaps), 2) if leaps else 0.0,
            "kind": "song_guide_tones", "window": None}


def _explain(placed: list[dict[str, Any]], meta: dict[str, Any], level: str, style: str, tones: str) -> tuple[list[str], list[str]]:
    sup = [p for p in placed if p["supported"]]
    how = [f"Play along the chord symbols above the staff — they are written for your instrument, and every note is a {TONES_LABEL[tones][:-1] if tones != 'both' else 'third or seventh'} of the chord it sits under.",
           f"Rhythm: {STYLE_LABEL.get(style, style)} at ♩ = {BPM[level]}. Keep the pulse even and let each change arrive on the beat the chart gives it."]
    if meta["resolutions"]:
        r = meta["resolutions"][0]
        how.append(f"Listen for the pull at the change: the {'seventh' if r['from_role'] == '7' else 'sixth'} of {r['from_chord']} ({r['from_note']}) moves a {r['step']} to the third of {r['to_chord']} ({r['to_note']}) in bar {r['to_bar']}.")
    listen = []
    thirds = [p for p in sup if p.get("third")]
    if thirds:
        p = thirds[0]
        listen.append(f"The third decides the chord's color: {p['third']} makes {p['written']} {'minor' if _is_minor_third(p) else 'major'}." if p.get("third") else "")
    notes = {p["note"] for p in sup if p.get("note")}
    listen.extend(sorted(notes))
    if meta["unsupported"]:
        listen.append("Rests mark chords this version can't write guide tones for: " + "; ".join(f"{p['concert']} (bar {p['bar']}: {p['reason']})" for p in meta["unsupported"]) + ".")
    return how, [x for x in listen if x]


def _is_minor_third(p: dict[str, Any]) -> bool:
    root = p["written"][:1] + (p["written"][1] if len(p["written"]) > 1 and p["written"][1] in "#b" else "")
    try:
        return (sph.pc_of(p["third"]) - sph.pc_of(root)) % 12 == 3
    except ValueError:
        return False


# ---------------------------------------------------------------- verification (against the chart's own chord, not against the generator's tables)


def verify(player: we.Player, level: str, built: we.Built, diag: dict[str, Any]) -> list[dict[str, Any]]:
    meta = built.meta
    lo, hi = player.window(level)
    pitched = [n for n in built.notes if not n.rest]
    midi = [n.midi for n in pitched]
    checks = [
        {"name": "bars_add_up", "ok": we.total_beats(built.notes) % we.BEATS_PER_BAR == 0, "detail": f"{we.total_beats(built.notes) / we.BEATS_PER_BAR} bars of 4"},
        {"name": "written_inside_level_window", "ok": all(lo <= m <= hi for m in midi), "detail": f"{lo}-{hi}"},
        {"name": "written_inside_playable_range", "ok": all(player.play_low <= m <= player.play_high for m in midi), "detail": f"{player.play_low}-{player.play_high}"},
        {"name": "notation_validation", "ok": bool(diag.get("notation_validation_ok")), "detail": "; ".join(diag.get("notation_validation_errors") or []) or "passed"},
    ]
    # every note is the third / seventh (or sixth) of the chord the chart gives at that beat, judged by chord_tone_roles of the CONCERT symbol on the SOUNDING pitch
    pos = Fraction(0)
    ok_tones, ok_time, detail = True, True, ""
    seg_by_start: dict[Fraction, dict[str, Any]] = {}
    for p in meta["segments"]:
        seg_by_start[Fraction(p["bar"] - meta["bars"][0]) * 4 + Fraction(p["beat"]).limit_denominator(8)] = p
    ordered = sorted(seg_by_start.items())
    for n in built.notes:
        seg = next((s for st, s in reversed(ordered) if st <= pos), None)
        if seg is None:
            ok_time, detail = False, "a note before the first chord"
            break
        if not n.rest:
            roles = sph.chord_tone_roles(seg["concert"])
            sounding_pc = (n.midi - player.offset) % 12
            role = roles.get(sounding_pc)
            if role not in ("3", "7", "6") or not seg["supported"]:
                ok_tones, detail = False, f"{n.spelled}{n.octave} is not a guide tone of {seg['concert']} at bar {seg['bar']}"
                break
        pos += n.beats
    for st, s in ordered:                                  # a note (or rest) begins exactly where each chord begins
        t = Fraction(0)
        hit = False
        for n in built.notes:
            if t == st:
                hit = True
                break
            t += n.beats
        if not hit:
            ok_time, detail = False, f"nothing starts on the chord change at bar {s['bar']}"
            break
    expected = sum((Fraction(s["beats"]).limit_denominator(8) for s in meta["segments"]), Fraction(0))
    checks.append({"name": "every_note_is_a_guide_tone_of_its_chord", "ok": ok_tones, "detail": detail or "third/seventh of the charted chord (sounding pitch)"})
    checks.append({"name": "chord_changes_land_on_their_beats", "ok": ok_time and we.total_beats(built.notes) == expected, "detail": detail or f"{expected} beats"})
    checks.append({"name": "sounding_equals_written_minus_offset", "ok": all(((m - player.offset) % 12) == ((sph.pc_of(n.spelled) - player.semitones) % 12) for m, n in zip(midi, pitched)),
                   "detail": f"written − {player.offset} semitones, octave included"})
    bad = [c for c in checks if not c["ok"]]
    if bad:
        raise we.WarmupUnavailable("; ".join(f"{c['name']}: {c['detail']}" for c in bad))
    return checks
