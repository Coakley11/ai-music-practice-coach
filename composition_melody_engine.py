"""Harmony-aware melody concepts for Composition Studio.

Every concept has its own musical identity (bar rhythm, contour, phrase plan, articulation,
register).  Strong-beat / structural notes are chosen from the sounding chord by a small
deterministic dynamic program (voice-leading + contour target + resolution of tension);
weak notes are diatonic passing / neighbor tones or - only in expressive styles - a chromatic
approach tone that resolves by semitone into the next chord tone.  Nothing is random.
"""

from __future__ import annotations

from typing import Any

from composition_melody_audit import (
    ChordInfo,
    bar_beats,
    chord_info,
    chord_segments,
    is_compound,
    key_scale_pcs,
    strong_offsets,
    tonic_pc,
)
from music_theory import key_is_minor, spell_note_in_key, spell_pitch_class

# kind: S chord tone on a structural beat, A chord tone off the beat, W weak linking tone,
# R rest.  Tuple = (offset_in_segment, duration, kind, articulation)
Cell = tuple[float, float, str, str]

CONCEPT_ORDER = (
    "direct_line", "question_answer", "offbeat_accent", "expressive_arch",
    "groove_pocket", "forward_climb", "sighing_descent", "motif_hook",
)

CONCEPTS: dict[str, dict[str, Any]] = {
    "direct_line": {
        "name": "Direct line",
        "contour": [(0.0, -4), (0.7, 6), (1.0, 3)],
        "leap_free": 4, "leap_w": 1.2, "rep_pen": 3.0, "wide": False,
    },
    "question_answer": {
        "name": "Question & answer",
        "contour": [(0.0, -3), (0.5, 6), (0.52, 4), (1.0, -3)],
        "leap_free": 5, "leap_w": 0.9, "rep_pen": 2.5, "wide": False,
    },
    "offbeat_accent": {
        "name": "Off-beat accent",
        "contour": [(0.0, 0), (0.5, 4), (1.0, 0)],
        "leap_free": 5, "leap_w": 0.8, "rep_pen": 0.8, "wide": False,
    },
    "expressive_arch": {
        "name": "Expressive arch",
        "contour": [(0.0, -5), (0.65, 10), (1.0, 0)],
        "leap_free": 9, "leap_w": 0.35, "rep_pen": 3.0, "wide": True,
    },
    "groove_pocket": {
        "name": "Groove pocket",
        "contour": [(0.0, -2), (0.5, 2), (1.0, -1)],
        "leap_free": 5, "leap_w": 0.7, "rep_pen": 0.4, "wide": False,
    },
    "forward_climb": {
        "name": "Forward climb",
        "contour": "saw",
        "leap_free": 5, "leap_w": 0.8, "rep_pen": 2.5, "wide": False,
    },
    "sighing_descent": {
        "name": "Sighing descent",
        "contour": [(0.0, 8), (1.0, -3)],
        "leap_free": 4, "leap_w": 1.1, "rep_pen": 3.0, "wide": False,
    },
    "motif_hook": {
        "name": "Motif hook",
        "contour": "hook",
        "leap_free": 5, "leap_w": 0.8, "rep_pen": 0.6, "wide": False,
    },
}

FEEL_CONCEPTS: dict[str, tuple[str, ...]] = {
    "smooth": ("direct_line", "sighing_descent", "question_answer", "expressive_arch"),
    "lyrical": ("question_answer", "direct_line", "expressive_arch", "sighing_descent"),
    "bold": ("expressive_arch", "motif_hook", "offbeat_accent", "forward_climb"),
    "rhythmic": ("offbeat_accent", "groove_pocket", "motif_hook", "direct_line"),
    "emotional": ("sighing_descent", "expressive_arch", "question_answer", "direct_line"),
    "energetic": ("forward_climb", "motif_hook", "offbeat_accent", "direct_line"),
}


def concepts_for_feel(feel: str, *, section_label: str = "", limit: int = 3) -> list[str]:
    ids = list(FEEL_CONCEPTS.get(str(feel or "").lower(), FEEL_CONCEPTS["lyrical"]))
    if section_label == "Chorus" and feel not in {"bold", "energetic"}:
        ids = ["expressive_arch", "motif_hook"] + ids
    elif section_label == "Bridge":
        ids = ["sighing_descent", "expressive_arch"] + ids
    out: list[str] = []
    for i in ids + list(CONCEPT_ORDER):
        if i not in out:
            out.append(i)
    return out[: max(1, limit)]


# ---------------------------------------------------------------- rhythm cells (4/4 beats)
def _cells_4(cid: str, bar_i: int, last: bool, qend: bool, complex_: bool) -> list[Cell]:
    if cid == "direct_line":
        if last:
            return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 2, "S", "tenuto")]
        if complex_:
            return [(0, 1, "S", ""), (1, .5, "W", ""), (1.5, .5, "W", ""), (2, 1, "S", ""),
                    (3, .5, "W", ""), (3.5, .5, "W", "")]
        return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 1, "S", ""), (3, 1, "W", "")]
    if cid == "question_answer":
        if last:
            return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 2, "S", "tenuto")]
        if qend:
            return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 1.5, "S", "tenuto"), (3.5, .5, "R", "")]
        return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 1.5, "S", ""), (3.5, .5, "W", "")]
    if cid == "offbeat_accent":
        if last:
            return [(0, 1, "S", ""), (1, .5, "R", ""), (1.5, 1, "A", "accent"), (2.5, 1.5, "A", "accent")]
        return [(0, 1, "S", ""), (1, .5, "R", ""), (1.5, 1, "A", "accent"),
                (2.5, 1, "A", "accent"), (3.5, .5, "A", "accent")]
    if cid == "expressive_arch":
        if last:
            return [(0, 2, "S", "tenuto"), (2, 2, "S", "tenuto")]
        if bar_i % 2 == 0:
            return [(0, 2, "S", "tenuto"), (2, 1, "S", ""), (3, 1, "W", "")]
        return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 2, "S", "tenuto")]
    if cid == "groove_pocket":
        if last:
            return [(0, 1, "S", ""), (1, 1, "R", ""), (2, 2, "S", "tenuto")]
        return [(0, 1, "S", "staccato"), (1, 1, "R", ""), (2, .5, "S", "staccato"),
                (2.5, .5, "W", "staccato"), (3, 1, "S", "")]
    if cid == "forward_climb":
        if last:
            return [(0, .5, "S", ""), (.5, .5, "W", ""), (1, .5, "S", ""), (1.5, .5, "W", ""),
                    (2, 2, "S", "tenuto")]
        return [(0, .5, "S", ""), (.5, .5, "W", ""), (1, .5, "S", ""), (1.5, .5, "W", ""),
                (2, 1, "S", ""), (3, .5, "W", ""), (3.5, .5, "S", "")]
    if cid == "sighing_descent":
        if last:
            return [(0, 1.5, "S", "tenuto"), (1.5, .5, "W", ""), (2, 2, "S", "tenuto")]
        return [(0, 1.5, "S", "tenuto"), (1.5, .5, "W", ""), (2, 1.5, "S", ""), (3.5, .5, "W", "")]
    if cid == "motif_hook":
        if last:
            return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 2, "S", "tenuto")]
        if bar_i % 2 == 0:
            return [(0, .5, "S", ""), (.5, .5, "S", ""), (1, 1, "W", ""), (2, 1, "S", ""), (3, 1, "W", "")]
        return [(0, .5, "S", ""), (.5, .5, "S", ""), (1, 1, "W", ""), (2, 2, "S", "")]
    return [(0, 1, "S", ""), (1, 1, "W", ""), (2, 2, "S", "")]


_CELLS_3: dict[str, tuple[list[Cell], list[Cell]]] = {
    # (body bar, final bar) written for 3 beats so concepts keep their own rhythm in 3/4
    "question_answer": (
        [(0, 1.5, "S", ""), (1.5, .5, "W", ""), (2, 1, "S", "")],
        [(0, 1, "S", ""), (1, 2, "S", "tenuto")],
    ),
    "expressive_arch": (
        [(0, 2, "S", "tenuto"), (2, 1, "S", "")],
        [(0, 3, "S", "tenuto")],
    ),
}


def _fit(cells: list[Cell], length: float, *, last: bool, cid: str = "") -> list[Cell]:
    if abs(length - 3.0) < 1e-6 and cid in _CELLS_3:
        return list(_CELLS_3[cid][1 if last else 0])
    """Fit a 4-beat pattern into a segment of ``length`` beats (clip, then fill)."""
    if abs(length - 4.0) < 1e-6:
        return cells
    out: list[Cell] = []
    for off, dur, kind, art in cells:
        if off >= length - 1e-6:
            continue
        out.append((off, min(dur, length - off), kind, art))
    if not out:
        return [(0.0, length, "S", "")]
    # fill any trailing gap
    off, dur, kind, art = out[-1]
    end = off + dur
    if length > 4.0 and end < length - 1e-6:
        pos = end
        while pos < length - 1e-6:
            step = min(1.0, length - pos)
            out.append((pos, step, "W", ""))
            pos += step
    elif end < length - 1e-6:
        out[-1] = (off, length - off, kind, art)
    # first sounding must be a chord tone
    if out[0][2] == "W":
        out[0] = (out[0][0], out[0][1], "S", out[0][3])
    if last and out[-1][2] == "W":
        out[-1] = (out[-1][0], out[-1][1], "S", "tenuto")
    return out


def _cells_compound(bar: float, last: bool, cid: str = "") -> list[Cell]:
    cells: list[Cell] = []
    groups = int(bar // 3)
    for g in range(groups):
        s = g * 3.0
        if last and g == groups - 1:
            cells.append((s, 3.0, "S", "tenuto"))
        elif cid == "offbeat_accent":
            cells += [(s, 1.0, "S", ""), (s + 1, 1.0, "A", "accent"), (s + 2, 1.0, "A", "accent")]
        elif cid == "groove_pocket":
            cells += [(s, 1.0, "S", "staccato"), (s + 1, 1.0, "R", ""), (s + 2, 1.0, "S", "")]
        else:
            cells += [(s, 1.0, "S", ""), (s + 1, 1.0, "W", ""), (s + 2, 1.0, "W", "")]
    return cells


# ------------------------------------------------------------------- pitch machinery
def _tonic_midi(key: str, lo: int, hi: int) -> int:
    t = tonic_pc(key)
    center = lo + int((hi - lo) * 0.42)
    base = (center // 12) * 12 + t
    return min((base - 12, base, base + 12), key=lambda m: abs(m - center))


def _contour_value(spec: Any, x: float, *, beat: float, bar: float) -> float:
    if spec == "saw":  # restarts every two bars: climb -3 -> +8
        phase = (beat % (2 * bar)) / (2 * bar)
        return -3 + 11 * phase
    if spec == "hook":  # 2-bar motif shape, repeated
        phase = (beat % (2 * bar)) / (2 * bar)
        return 5 * (1 - abs(2 * phase - 1)) - 1
    pts = spec
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def _name_for(pc: int, info: ChordInfo | None, key: str, direction: int = 0) -> str:
    if info is not None:
        n = info.name_for_pc(pc)
        if n:
            return n
    if pc in key_scale_pcs(key) or direction == 0:
        return spell_note_in_key(pc, key)
    # chromatic: rising approach is written sharp (F# -> G), falling approach flat (Gb -> F)
    return spell_pitch_class(pc, mode="sharp" if direction > 0 else "flat")


def _label(name: str, midi: int) -> str:
    # octave number follows the written letter (Cb / B# edge cases)
    oct_ = (midi // 12) - 1
    if name.startswith("B#"):
        oct_ -= 1
    elif name.startswith("Cb"):
        oct_ += 1
    return f"{name}{oct_}"


def build_concept_events(
    concept_id: str,
    chords: list[str],
    *,
    key: str,
    meter: str = "4/4",
    style: str = "simple",
    feel: str = "",
    intent: dict[str, bool] | None = None,
    bias: dict[str, Any] | None = None,
    range_midi: tuple[int, int] = (55, 79),
    density: float | None = None,
) -> list[dict[str, Any]]:
    cfg = CONCEPTS.get(concept_id) or CONCEPTS["direct_line"]
    intent = intent or {}
    bias = bias or {}
    symbols = [str(c).strip() for c in chords or [] if str(c).strip()]
    if not symbols:
        return []
    bar = bar_beats(meter)
    comp = is_compound(meter)
    strong = strong_offsets(bar, comp)
    segs = chord_segments(symbols, meter)
    if not segs:
        return []
    total = segs[-1][1]
    lo, hi = int(range_midi[0]), int(range_midi[1])
    if intent.get("comfortable"):
        lo, hi = max(lo, 60), min(hi, 76)
    center = _tonic_midi(key, lo, hi)
    if intent.get("start_low"):
        center -= 2
    tpc = tonic_pc(key)
    scale = sorted(key_scale_pcs(key))
    style = str(style or "simple").lower()
    complex_ = style in {"complex", "expressive"} or bool(bias.get("prefer_extensions"))
    allow_chromatic = complex_
    nbars = max(1, int(round(total / bar)))

    # question / answer split (by whole bars; half a bar when the phrase is one bar long)
    split = None
    if concept_id == "question_answer":
        split = (nbars // 2) * bar if nbars >= 2 else bar / 2.0

    # ---------------------------------------------------------------- slots
    slots: list[dict[str, Any]] = []
    for si, (a, z, sym) in enumerate(segs):
        bar_i = int(a // bar + 1e-9)
        is_last_seg = si == len(segs) - 1
        qend = bool(split is not None and nbars >= 2 and abs(z - split) < 1e-6)
        cells = _cells_4(concept_id, bar_i, is_last_seg, qend, complex_) if not comp else _cells_compound(z - a, is_last_seg, concept_id)
        if not comp:
            cells = _fit(cells, z - a, last=is_last_seg, cid=concept_id)
        for off, dur, kind, art in cells:
            slots.append({"beat": a + off, "dur": dur, "kind": kind, "art": art, "chord": sym, "seg": si})
    if split is not None and nbars < 2:
        # single-bar phrase: rest between the two halves
        pass
    # song tempo / energy -> density: slow, intimate songs drop the weak linking notes (their
    # time is absorbed by the preceding chord tone); high-energy songs split long weak notes.
    if density is not None and density <= 0.35 and concept_id not in {"offbeat_accent", "groove_pocket"}:
        merged: list[dict[str, Any]] = []
        for sl in slots:
            if sl["kind"] == "W" and merged and merged[-1]["kind"] in {"S", "A"} and merged[-1]["chord"] == sl["chord"]:
                merged[-1]["dur"] += sl["dur"]
                continue
            merged.append(sl)
        slots[:] = merged
    elif density is not None and density >= 0.7:
        split_slots: list[dict[str, Any]] = []
        for sl in slots:
            if sl["kind"] == "W" and sl["dur"] >= 1.0 and not comp:
                half = sl["dur"] / 2.0
                split_slots.append({**sl, "dur": half})
                split_slots.append({**sl, "beat": sl["beat"] + half, "dur": half})
            else:
                split_slots.append(sl)
        slots[:] = split_slots
    # chord-tone-only invariant: first and last sounding slots are chord tones
    if split is not None:  # the question phrase also ends on a chord tone (its open cadence note)
        before_split = [s for s in slots if s["kind"] != "R" and s["beat"] < split - 1e-6]
        if before_split and before_split[-1]["kind"] == "W":
            before_split[-1]["kind"] = "S"
    snd = [s for s in slots if s["kind"] != "R"]
    if not snd:
        return []
    if snd[0]["kind"] == "W":
        snd[0]["kind"] = "S"
    if snd[-1]["kind"] == "W":
        snd[-1]["kind"] = "S"
    if intent.get("space") and len(snd) > 4:
        mid = snd[len(snd) // 2]
        if mid["kind"] == "W" and mid["dur"] <= 1.0:
            mid["kind"] = "R"
    dp = [s for s in slots if s["kind"] in {"S", "A"}]

    # structural targets
    q_slot = a_slot = None
    if split is not None:
        before = [s for s in slots if s["kind"] != "R" and s["beat"] < split - 1e-6]
        q_slot = next((s for s in reversed(before) if s["kind"] in {"S", "A"}), None)
        a_slot = dp[-1]
    final_slot = dp[-1]

    # ------------------------------------------------------------- DP over chord tones
    def allowed(s: dict[str, Any], idx: int) -> list[int]:
        info = chord_info(s["chord"], key)
        if info is None:
            return []
        pcs = set(info.tone_pcs)
        if complex_ and idx not in (0, len(dp) - 1) and s["kind"] == "S" and info.quality in {"maj", "min", "dom"}:
            pcs |= {p for p in info.ext_pcs if p in key_scale_pcs(key)}
        if s is final_slot or s is a_slot:
            stable = tpc if tpc in info.tone_pcs else info.root_pc
            pcs = {stable}
        if s is q_slot:
            pcs = {p for p in info.tone_pcs if p != tpc} or set(info.tone_pcs)
        return sorted(m for m in range(lo, hi + 1) if m % 12 in pcs)

    cands = [allowed(s, i) for i, s in enumerate(dp)]
    for i, c in enumerate(cands):  # never leave a slot without a candidate
        if not c:
            info = chord_info(dp[i]["chord"], key)
            pc = info.root_pc if info else tpc
            cands[i] = [m for m in range(lo - 12, hi + 13) if m % 12 == pc and lo - 12 <= m <= hi + 12]

    def x_of(s: dict[str, Any]) -> float:
        return min(1.0, max(0.0, s["beat"] / max(total, 1e-6)))

    def step_cost(i: int, m: int, pm: int | None, pinfo: ChordInfo | None, pprev: int | None) -> float:
        s = dp[i]
        info = chord_info(s["chord"], key)
        tgt = center + _contour_value(cfg["contour"], x_of(s), beat=s["beat"], bar=bar)
        c = 0.32 * abs(m - tgt)
        pc = m % 12
        if info is not None:
            if pc == info.root_pc:
                c -= 0.3 if i == 0 else 0.0
            if pc not in info.tone_pcs:
                c += 2.0  # extensions are a deliberate, rare colour
        if pm is not None:
            iv = abs(m - pm)
            c += cfg["leap_w"] * max(0, iv - cfg["leap_free"])
            if iv == 0:
                c += cfg["rep_pen"]
            if iv > 12:
                c += 6
            if intent.get("comfortable"):
                c += 0.8 * max(0, iv - 4)
            # resolve tension of a dominant: 3rd moves up a semitone, 7th down a step
            if pinfo is not None and pinfo.is_dominant and pinfo.third_pc is not None:
                ppc = pm % 12
                d = m - pm
                if ppc == pinfo.third_pc:
                    chrom = ppc not in key_scale_pcs(key)
                    if d == 1:
                        c += 0.0
                    elif d == 2 and not chrom:
                        c += 0.0
                    else:
                        c += 9.0 if chrom else 2.2
                elif pinfo.seventh_pc is not None and ppc == pinfo.seventh_pc:
                    c += 0.0 if d in (-1, -2) else 1.6
        if s is q_slot:
            if pc in {(tpc + 2) % 12, (tpc + 7) % 12}:
                c -= 2.0
            if pm is not None and m < pm:
                c += 1.2  # a question is left open by a lift
        if s is a_slot and pm is not None and m > pm:
            c += 1.0  # the answer settles down
        if s is final_slot and info is not None and pc == tpc:
            c -= 1.0
        return c

    n = len(dp)
    INF = 1e18
    cost = [[INF] * len(c) for c in cands]
    back = [[-1] * len(c) for c in cands]
    for j, m in enumerate(cands[0]):
        cost[0][j] = step_cost(0, m, None, None, None)
    for i in range(1, n):
        pinfo = chord_info(dp[i - 1]["chord"], key)
        for j, m in enumerate(cands[i]):
            best, arg = INF, -1
            for k, pm in enumerate(cands[i - 1]):
                v = cost[i - 1][k] + step_cost(i, m, pm, pinfo, None)
                if v < best - 1e-9:
                    best, arg = v, k
            cost[i][j], back[i][j] = best, arg
    j = min(range(len(cands[-1])), key=lambda q: (cost[-1][q], cands[-1][q]))
    picks = [0] * n
    for i in range(n - 1, -1, -1):
        picks[i] = cands[i][j]
        j = back[i][j] if i else j
    for s, m in zip(dp, picks):
        s["midi"] = m

    # a chromatic dominant third (e.g. F# over D7) must go straight to its resolution:
    # no weak tone may interrupt it, so the third simply rings through that slot.
    for i_, s_ in enumerate(slots[:-1]):
        info_ = chord_info(s_["chord"], key) if "midi" in s_ else None
        if not (info_ is not None and info_.is_dominant and s_["kind"] in {"S", "A"}
                and s_["midi"] % 12 == info_.third_pc and info_.third_pc not in key_scale_pcs(key)):
            continue
        for nxt_ in slots[i_ + 1:]:
            if nxt_["kind"] != "W" or nxt_["chord"] != s_["chord"]:
                break
            s_["dur"] += nxt_["dur"]
            nxt_["kind"] = "X"
    slots[:] = [s_ for s_ in slots if s_["kind"] != "X"]

    # ---------------------------------------------------------------- weak linking tones
    scale_midis = sorted(m for m in range(lo - 12, hi + 13) if m % 12 in set(scale))

    def scale_step(m: int, d: int) -> int:
        if d > 0:
            return next((x for x in scale_midis if x > m), m + 2)
        return next((x for x in reversed(scale_midis) if x < m), m - 2)

    order = [s for s in slots if s["kind"] != "R"]
    chromatic_used = 0

    def near_chord_tone(sym: str, m: int, avoid: int | None, also: int | None = None) -> int:
        info_ = chord_info(sym, key)
        pcs_ = set(info_.tone_pcs) if info_ else {tpc}
        if info_ is not None and not intent.get("comfortable"):
            pcs_ |= {p for p in info_.ext_pcs if p in key_scale_pcs(key)}  # 9th / 6th colour
        opts = [x for x in range(lo, hi + 1) if x % 12 in pcs_ and x not in (avoid, also)]
        if info_ is not None and info_.is_dominant and info_.third_pc not in key_scale_pcs(key):
            # a chromatic dominant third is only usable when it steps up to its target
            opts = [x for x in opts if x % 12 != info_.third_pc or (also is not None and also - x == 1)] or opts
        return min(opts, key=lambda x: (abs(x - m), x)) if opts else m

    for idx, s in enumerate(order):
        if s["kind"] != "W":
            continue
        prev = next((o for o in reversed(order[:idx]) if "midi" in o), None)
        nxt = next((o for o in order[idx + 1:] if o["kind"] in {"S", "A"}), None)
        if prev is None or nxt is None:
            s["kind"], s["midi"] = "S", (nxt["midi"] if nxt else center)
            continue
        pm, target = prev["midi"], nxt["midi"]
        remaining = 0
        for o in order[idx:]:
            if o["kind"] != "W":
                break
            remaining += 1
        gap = target - pm
        dirn = 1 if gap > 0 else -1
        chosen: int | None = None
        into_change = any(abs(nxt["beat"] - a_) < 1e-6 for a_, _z, _c in segs)
        if (allow_chromatic and remaining == 1 and s["dur"] <= 0.5 and abs(gap) >= 2
                and into_change and chromatic_used < max(1, nbars // 2)):
            info_here = chord_info(s["chord"], key)
            for off in ((-1,) if gap > 0 else (1,)):  # approach from the side we come from
                pc_ = (target + off) % 12
                if pc_ not in key_scale_pcs(key) and (info_here is None or pc_ not in info_here.tone_pcs):
                    chosen = target + off
                    s["dir"] = -off  # approached from below -> written sharp
                    chromatic_used += 1
                    break
        if chosen is None:
            if gap == 0:
                up = scale_step(pm, 1)
                chosen = up if up <= hi else scale_step(pm, -1)
            else:
                cand = scale_step(pm, dirn)
                between = (pm < cand < target) if dirn > 0 else (target < cand < pm)
                chosen = cand if between else None
        if chosen is None:
            chosen = near_chord_tone(s["chord"], pm, pm, target)
        s["midi"] = int(chosen)

    # audit-driven repair: any linking tone the audit cannot justify becomes a chord tone
    from composition_melody_audit import LABEL_NON_HARMONIC, audit_melody

    def _events_from_slots() -> list[dict[str, Any]]:
        out_: list[dict[str, Any]] = []
        for s_ in slots:
            ev_ = {"beat": s_["beat"], "duration_beats": s_["dur"], "pitch": "rest", "midi": None}
            if s_["kind"] == "R" or "midi" not in s_:
                ev_["is_rest"] = True
            else:
                ev_["midi"] = int(s_["midi"])
                ev_["pitch"] = "x"
            out_.append(ev_)
        return out_

    for _pass in range(4):
        rows_ = audit_melody(_events_from_slots(), symbols, key=key, meter=meter)
        fixed = False
        for s_, r_ in zip(slots, rows_):
            if s_["kind"] == "W" and "midi" in s_ and (
                r_["label"] == LABEL_NON_HARMONIC or (r_["chromatic"] and not r_["resolved"])
            ):
                pm_ = next((o["midi"] for o in reversed(order[: order.index(s_)]) if "midi" in o), s_["midi"])
                s_["midi"] = near_chord_tone(s_["chord"], s_["midi"], pm_)
                s_.pop("dir", None)
                fixed = True
        if not fixed:
            break

    # ----------------------------------------------------------------- emit events
    events: list[dict[str, Any]] = []
    cursor = 0.0
    for s in slots:
        if s["beat"] > cursor + 1e-6:  # never leave an unaccounted gap in the timeline
            events.append({"pitch": "rest", "midi": None, "is_rest": True, "duration_beats": s["beat"] - cursor,
                           "beat": cursor, "measure": int(cursor // bar) + 1, "chord": s["chord"]})
        cursor = s["beat"] + s["dur"]
        base = {
            "duration_beats": float(s["dur"]),
            "beat": float(s["beat"]),
            "measure": int(s["beat"] // bar) + 1,
            "chord": s["chord"],
        }
        if s["kind"] == "R" or "midi" not in s:
            events.append({"pitch": "rest", "midi": None, "is_rest": True, **base})
            continue
        m = int(s["midi"])
        info = chord_info(s["chord"], key)
        name = _name_for(m % 12, info, key, s.get("dir", 0))
        ev = {"pitch": _label(name, m), "midi": m, **base}
        if s["art"]:
            ev["articulation"] = s["art"]
        events.append(ev)
    # a rest must never be the very last event (it would hide the closing chord tone)
    while events and events[-1].get("is_rest"):
        events.pop()
    # hold the final note when asked / for low-energy sections
    if intent.get("hold_last") and events:
        total_end = segs[-1][1]
        last = events[-1]
        last["duration_beats"] = float(total_end - last["beat"])
    for i, e in enumerate(events):
        e["chord_index"] = int(e["beat"] // bar)
    return events
