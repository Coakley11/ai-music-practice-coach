"""AMI adaptive warmups, Slice 2b: chord-tone arpeggios and chromatic / diatonic approach notes over the active song's actual chords.

Built on Slice 2a's harmonic timeline (``warmup_song``): the same chart snapshot, the same split-bar timing, the same chord reading
(``scale_pattern_harmony``), the same written-pitch rules. Nothing here parses chord symbols.

* ``chord_tones``  - an arpeggio of each chord's own tones (root, third, fifth, seventh; a sixth chord's sixth in the seventh's place; a triad's three),
  in a chosen shape (up, down, up-and-back, skipping, zig-zag) starting on a chosen chord tone (or the one that connects best to the previous chord).
* ``approach_notes`` - at each chord CHANGE the line lands on a deliberately chosen chord tone of the new chord (its third, seventh, ...), and the
  last beat(s) of the old chord approach that target: a chromatic note from below or above, a diatonic one, a double-chromatic run, or an enclosure.
  An approach note is never a chord tone of the chord it leaves or of the chord it enters; the approach resolves onto the target on the beat the chart
  changes chord (halfway through a bar when the chart splits it). The last chord approaches the first, ready for the repeat.

Every candidate line is a complete, checked sequence of pitches; one dynamic-programming pass picks, for the whole exercise, the start tones and octaves
with the smoothest voice-leading (a seventh falling onto the next chord's third is rewarded, as in the guide-tone lines).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami import warmup_engine as we
from music_coach_ami import warmup_song as ws

CHORD_TONES = "chord_tones"
APPROACH = "approach_notes"
BPM = {CHORD_TONES: {"Beginner": 52, "Intermediate": 72, "Advanced": 96}, APPROACH: {"Beginner": 46, "Intermediate": 64, "Advanced": 84}}
UNIT = {"Beginner": Fraction(1), "Intermediate": Fraction(1, 2), "Advanced": Fraction(1, 2)}       # the note value the line moves in
ROLE_ORDER = ("R", "3", "5", "7", "6")

# (direction, shape, start tone, articulation) per variant, in the order the planner adds them
CHORD_VARIANTS: dict[str, list[tuple[str, str, str, str]]] = {
    "Beginner": [("up", "straight", "root", ""), ("down", "straight", "seventh", ""), ("up", "straight", "third", ""), ("up", "straight", "auto", "")],
    "Intermediate": [("up", "updown", "auto", ""), ("up", "straight", "third", "slur2"), ("down", "straight", "seventh", ""), ("up", "skip", "root", "")],
    "Advanced": [("up", "skip", "auto", "accent"), ("down", "zig", "seventh", ""), ("up", "updown", "third", "slur2"), ("down", "skip", "fifth", ""), ("up", "zig", "auto", "accent")],
}
# (kind, target tone) per variant
APPROACH_VARIANTS: dict[str, list[tuple[str, str]]] = {
    "Beginner": [("below", "third"), ("above", "third")],
    "Intermediate": [("below", "third"), ("above", "seventh"), ("diatonic", "third"), ("mixed", "auto")],
    "Advanced": [("double", "third"), ("enclosure", "auto"), ("mixed", "auto"), ("double_above", "seventh")],
}
SHAPE_LABEL = {"straight": "straight", "updown": "up and back", "skip": "skipping (1-5-3-7)", "zig": "zig-zag (1-7-3-5)"}
START_WORD = {"root": "the root", "third": "the third", "fifth": "the fifth", "seventh": "the seventh", "auto": "whichever chord tone connects best"}
START_ROLE = {"root": "R", "third": "3", "fifth": "5", "seventh": "7"}
KIND_LABEL = {"below": "a chromatic approach from below", "above": "a chromatic approach from above", "diatonic": "a diatonic approach (the scale note below)",
              "double": "a double-chromatic approach from below", "double_above": "a double-chromatic approach from above", "enclosure": "an enclosure (above, then below)",
              "mixed": "chromatic approaches, alternately from below and above"}
TARGET_WORD = {"third": "the third", "seventh": "the seventh", "root": "the root", "fifth": "the fifth", "auto": "the chord tone that connects best"}


def _norm_pc(x: int) -> int:
    return x % 12


# ---------------------------------------------------------------- a chord's tones, for the written staff


@dataclass(frozen=True)
class Tone:
    role: str            # 'R' | '3' | '5' | '7' | '6'
    pc: int              # WRITTEN pitch class
    name: str            # written spelling
    concert: str         # concert spelling


def tones_of(info: dict[str, Any]) -> list[Tone]:
    """The chord's tones from root upward (root, third, fifth when writable, seventh or sixth when the chord has one)."""
    w, c = info["written"], info["concert"]
    out = [Tone("R", sph.pc_of(w["root"]), w["root"], c["root"]), Tone("3", sph.pc_of(w["third"]), w["third"], c["third"])]
    if w.get("fifth"):
        out.append(Tone("5", sph.pc_of(w["fifth"]), w["fifth"], c["fifth"]))
    if w.get("upper"):
        out.append(Tone(info["upper_role"] or "7", sph.pc_of(w["upper"]), w["upper"], c["upper"]))
    return out


def _ladder(tones: list[Tone], start_role: str, direction: str) -> list[Tone]:
    """The tones in the order they are met going ``direction`` from the start tone (a missing start tone falls back to the root)."""
    idx = next((i for i, t in enumerate(tones) if t.role == start_role or (start_role == "7" and t.role == "6")), 0)
    ring = tones[idx:] + tones[:idx]
    return ring if direction == "up" else [ring[0]] + list(reversed(ring[1:]))


def contour(shape: str, k: int) -> list[int]:
    if k <= 1:
        return [0]
    if shape == "updown":
        return list(range(k)) + list(range(k - 2, 0, -1))
    if shape == "skip":
        return [0, 2, 1, 3][:k] if k >= 4 else [0, 2, 1][:k]
    if shape == "zig":
        return [0, 3, 1, 2] if k >= 4 else [0, 2, 1][:k]
    return list(range(k))


def _ladder_midis(ladder: list[Tone], base: int, direction: str) -> list[int]:
    out = [base]
    for t in ladder[1:]:
        m = out[-1] + 1 if direction == "up" else out[-1] - 1
        while m % 12 != t.pc:
            m += 1 if direction == "up" else -1
        out.append(m)
    return out


# ---------------------------------------------------------------- spelling approach notes (written pitch)

_LETTERS = "CDEFGAB"
_LPC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def near_name(target: str, delta: int) -> str | None:
    """The written name of the pitch ``delta`` semitones from ``target``, spelled the way an approach is read: fewest accidentals first; then the letter next to the
    target's in the direction of the neighbour (a note below the target is the sharp or natural of the letter below: C# leading up to D; a note above is the flat or
    natural of the letter above: Eb falling to D); then the target's own letter. Never a double accidental; None when no single-accidental spelling exists."""
    tl = _LETTERS.index(target[0].upper())
    pc = (sph.pc_of(target) + delta) % 12
    want = -1 if delta < 0 else 1
    best: tuple[int, int, str] | None = None
    for step in (0, -1, 1, -2, 2):
        L = _LETTERS[(tl + step) % 7]
        d = (pc - _LPC[L] + 6) % 12 - 6
        if abs(d) > 1:
            continue
        name = L + ("#" if d == 1 else "b" if d == -1 else "")
        rank = 0 if step == want else 1 if step == 0 else 2
        key = (abs(d), rank, name)
        if best is None or key < best:
            best = key
    return best[2] if best else None


# ---------------------------------------------------------------- the figure that approaches a target


def targets_for(info: dict[str, Any], allowed: list[str]) -> list[str]:
    """The asked-for target tones this chord really has; a chord with none of them (a triad has no seventh) is approached on its third."""
    tones = tones_of(info)
    present = [w for w in allowed if any(t.role == START_ROLE[w] or (START_ROLE[w] == "7" and t.role == "6") for t in tones)]
    return present or ["third"]


def figure_offsets(kind: str, flip: bool) -> list[list[int]]:
    """Alternative approach figures as semitone offsets from the target (the last offset is the note just before it). First entry is preferred."""
    if kind == "below":
        return [[-1], [1]]
    if kind == "above":
        return [[1], [-1]]
    if kind == "mixed":
        return [[1], [-1]] if flip else [[-1], [1]]
    if kind == "double":
        return [[-2, -1], [2, 1]]
    if kind == "double_above":
        return [[2, 1], [-2, -1]]
    if kind == "enclosure":
        return [[1, -1], [-1, 1]]
    return [[-1], [1]]                  # diatonic is resolved against the target chord's own scale (see ``diatonic_below``)


def diatonic_below(target_pc_concert: int, chord: str, key: sph.KeyScale) -> int | None:
    """Semitones from the target down to the nearest note of the target chord's scale (1 or 2), or None when the existing scale reader has none."""
    try:
        scale = sph.chord_scale_for(chord, key)
    except ValueError:
        return None
    pcs = {sph.pc_of(n) for n in scale.notes}
    for d in (1, 2):
        if (target_pc_concert - d) % 12 in pcs:
            return d
    return None


# ---------------------------------------------------------------- candidates


@dataclass
class Note:
    midi: int
    name: str
    role: str                 # chord-tone role, or 'approach'
    beats: Fraction
    art: str = ""
    slur: int = 0
    target: bool = False


@dataclass
class Cand:
    body: list[Note]
    pre: list[Note] = field(default_factory=list)       # approach notes that sit at the END of the previous segment, resolving onto body[0]
    target_role: str = ""
    figure: str = ""
    key: tuple = ()


def _split(total: Fraction, unit: Fraction) -> list[Fraction]:
    out, left = [], Fraction(total)
    while left >= unit:
        out.append(unit)
        left -= unit
    if left > 0:
        out.append(left)
    return out


def _unit_for(beats: Fraction, level: str) -> Fraction:
    u = UNIT[level]
    return u if (beats % u) == 0 else Fraction(1, 2)


def arpeggio_candidates(info: dict[str, Any], beats: Fraction, level: str, lo: int, hi: int, direction: str, shape: str, start: str, art: str) -> list[Cand]:
    """Every complete arpeggio of this chord over ``beats``: one per (start tone, octave) that fits the player's window."""
    tones = tones_of(info)
    u = _unit_for(beats, level)
    n = int(beats / u)
    starts = [start] if start != "auto" else ["root", "third", "fifth", "seventh"]
    out: list[Cand] = []
    for s in starts:
        role = START_ROLE.get(s, "R")
        if role != "R" and not any(t.role == role or (role == "7" and t.role == "6") for t in tones):
            continue
        ladder = _ladder(tones, role, direction)
        pos = contour(shape, len(ladder))
        seq = [pos[i % len(pos)] for i in range(n)]
        first = ladder[0]
        for base in range(lo, hi + 1):
            if base % 12 != first.pc:
                continue
            mids = _ladder_midis(ladder, base, direction)
            line = [mids[p] for p in seq]
            if min(line) < lo or max(line) > hi:
                continue
            notes = [Note(line[i], ladder[seq[i]].name, ladder[seq[i]].role, u) for i in range(n)]
            _articulate(notes, art, True)
            out.append(Cand(notes, key=(s, base)))
    return out


def _articulate(notes: list[Note], art: str, arrival: bool) -> None:
    if art == "accent" and arrival and notes:
        notes[0].art = "accent"
    if art == "slur2":
        gid = 1
        for i in range(0, len(notes) - 1, 2):
            notes[i].slur = notes[i + 1].slur = gid
            gid += 1


def body_candidates(info: dict[str, Any], body_beats: Fraction, level: str, lo: int, hi: int, targets: list[str], arrival: bool, art: str) -> list[Cand]:
    """The body of a segment in an approach exercise: the target chord tone (an arrival) followed by the chord's own tones going up, then down if the register ends."""
    tones = tones_of(info)
    u = _unit_for(body_beats, level)
    out: list[Cand] = []
    roles = targets if arrival else ["root", "third", "fifth", "seventh"]
    for tr in roles:
        role = START_ROLE.get(tr, "R")
        if role != "R" and not any(t.role == role or (role == "7" and t.role == "6") for t in tones):
            continue
        for direction in ("up", "down"):
            ladder = _ladder(tones, role, direction)
            tdur = min(Fraction(1), body_beats) if arrival else u
            durs = [tdur] + _split(body_beats - tdur, u)
            k = len(ladder)
            bounce = [(i % (2 * (k - 1))) if k > 1 else 0 for i in range(len(durs))]
            bounce = [b if b < k else 2 * (k - 1) - b for b in bounce]       # up (or down) the chord's tones and back: a long body never leaves the octave
            for base in range(lo, hi + 1):
                if base % 12 != ladder[0].pc:
                    continue
                mids = _ladder_midis(ladder, base, direction)
                line = [mids[b] for b in bounce]
                if min(line) < lo or max(line) > hi:
                    continue
                notes = [Note(line[i], ladder[bounce[i]].name, ladder[bounce[i]].role, durs[i], target=(arrival and i == 0)) for i in range(len(durs))]
                _articulate(notes, art, arrival)
                out.append(Cand(notes, target_role=ladder[0].role, key=(tr, direction, base)))
    # an arrival and its descending twin are the same first note: keep both, the DP chooses by voice-leading
    return out


# ---------------------------------------------------------------- voice-leading over complete candidate lines


def _leap(a: int, b: int, smooth: bool) -> float:
    w = 3.0 if smooth else 1.0
    d = abs(a - b)
    return w * d + (w * 2 if d > 7 else 0)


def _join_cost(prev_last: Note | None, nxt_first: Note | None, smooth: bool, boundary: bool) -> float:
    if prev_last is None or nxt_first is None:
        return 0.0
    cost = _leap(prev_last.midi, nxt_first.midi, smooth)
    if boundary and prev_last.role in ("7", "6") and nxt_first.role == "3":
        d = prev_last.midi - nxt_first.midi
        cost -= (6 if d == 1 else 3 if d == 2 else 0) * (3.0 if smooth else 1.0)
    return cost


def _internal_cost(c: Cand, centre: float, smooth: bool) -> float:
    seq = [*c.pre, *c.body]
    cost = sum(_leap(a.midi, b.midi, smooth) for a, b in zip(seq, seq[1:])) * 0.5
    return cost + 0.05 * sum(abs(n.midi - centre) for n in seq) / max(1, len(seq))


def lead_lines(options: list[list[Cand]], lo: int, hi: int, *, smooth: bool, loop: bool, boundaries: list[bool]) -> list[Cand]:
    """Pick one candidate per segment minimising leaps, with a cyclic close (the last segment's tail approaches segment 0's target) when ``loop``.

    ``boundaries[j]`` is True when segment j begins a new chord (a seventh falling onto a third is rewarded there)."""
    m = len(options)
    centre = (lo + hi) / 2.0
    if any(not o for o in options):
        raise ws.SongUnavailable("a chord has no line that fits this instrument's register at this level")
    INF = float("inf")
    firsts = options[0] if loop else [None]
    best_total, best_path = INF, None
    for c0i, c0 in enumerate(firsts):
        # dp[j][ci] = (cost, backpointer)
        dp: list[dict[int, tuple[float, int | None]]] = []
        start = options[0] if not loop else [c0]
        layer = {}
        for ci, c in enumerate(options[0]):
            if loop and c is not c0:
                continue
            layer[ci] = (_internal_cost(c, centre, smooth), None)
        dp.append(layer)
        for j in range(1, m):
            layer = {}
            for ci, c in enumerate(options[j]):
                top = None
                for pi, (pc, _b) in dp[j - 1].items():
                    prev = options[j - 1][pi]
                    last = prev.body[-1] if prev.body else None
                    first = c.pre[0] if c.pre else (c.body[0] if c.body else None)
                    cost = pc + _join_cost(last, first, smooth, boundaries[j] and not c.pre) + _internal_cost(c, centre, smooth)
                    if top is None or cost < top[0]:
                        top = (cost, pi)
                layer[ci] = top  # type: ignore[assignment]
            dp.append(layer)
        for ci, (cost, _b) in dp[m - 1].items():
            total = cost
            if loop and c0.pre:
                total += _join_cost(options[m - 1][ci].body[-1], c0.pre[0], smooth, False)
            if total < best_total:
                path = [ci]
                for j in range(m - 1, 0, -1):
                    path.append(dp[j][path[-1]][1])  # type: ignore[index]
                path.reverse()
                best_total, best_path = total, (c0i, path)
    assert best_path is not None
    return [options[j][ci] for j, ci in enumerate(best_path[1])]


# ---------------------------------------------------------------- building a whole exercise

_DUR_NAME = {v: k for k, v in we._DUR_BEATS.items()}


def _prepare(player: we.Player, level: str, song: dict[str, Any], section: str, bars: tuple[int, int] | None, what: str):
    segs, b_lo, b_hi = ws.build_timeline(song, section, bars, player.offset, player.semitones)
    good = [s for s in segs if s.ok]
    total = sum((s.beats for s in segs), Fraction(0))
    share = sum((s.beats for s in good), Fraction(0)) / total
    if not good or share < ws.MIN_SUPPORTED_SHARE:
        names = "; ".join(f"{s.chord} (bar {s.src_bar}): {s.reason}" for s in segs if not s.ok)[:300]
        raise ws.SongUnavailable(f"too much of {section} can't be written correctly to give you a trustworthy {what} exercise — {names}")
    lo, hi = player.window(level)
    if hi - lo < 12:
        raise ws.SongUnavailable("this level's register window is too small for this exercise")
    return segs, good, b_lo, b_hi, share, lo, hi


def _emit(player: we.Player, segs: list[ws.Seg], bodies: dict[int, list[Note]], tails: dict[int, list[Note]]) -> tuple[list[we.Note], list[dict[str, Any]]]:
    """The notation: for every segment its body then the approach notes (if any) that belong to its tail; rests for chords that cannot be written."""
    notes: list[we.Note] = []
    placed: list[dict[str, Any]] = []
    for s in segs:
        base = {"seg": s.index, "bar": s.src_bar, "beat": float(s.beat), "beats": float(s.beats), "concert": s.chord}
        if not s.ok:
            label = s.info.get("symbol_written") or ws._written_symbol(s.chord, player)
            for r in we.rests(s.beats):
                r.chord = label
                notes.append(r)
            placed.append({**base, "written": label, "supported": False, "reason": s.reason, "notes": []})
            continue
        row, first = [], True
        for n in [*bodies[s.index], *tails.get(s.index, [])]:
            oct_ = sph.octave_for(n.name, n.midi)
            wn = we.Note(n.name, oct_, _DUR_NAME[n.beats], n.art, n.slur)
            if first:
                wn.chord = s.info["symbol_written"]
                first = False
            notes.append(wn)
            row.append({"role": n.role, "name": n.name, "midi": n.midi, "beats": float(n.beats), "target": n.target})
        w, c = s.info["written"], s.info["concert"]
        placed.append({**base, "written": s.info["symbol_written"], "supported": True, "note": s.info.get("note", ""), "third": w["third"], "upper": w["upper"],
                       "upper_role": s.info["upper_role"], "concert_third": c["third"], "concert_upper": c["upper"], "root": w["root"], "fifth": w.get("fifth"),
                       "concert_root": c["root"], "concert_fifth": c.get("fifth"), "notes": row})
    return notes, placed


def build_chord_tones(player: we.Player, level: str, song: dict[str, Any], section: str, bars: tuple[int, int] | None, *, direction: str, shape: str, start: str,
                      art: str = "", smooth: bool = False) -> we.Built:
    segs, good, b_lo, b_hi, share, lo, hi = _prepare(player, level, song, section, bars, "chord-tone")
    options = [arpeggio_candidates(s.info, s.beats, level, lo, hi, direction, shape, start, art) for s in good]
    if any(not o for o in options):                          # a fixed start tone may not fit one chord's register: let the best connecting tone stand in there
        options = [o or arpeggio_candidates(s.info, s.beats, level, lo, hi, direction, shape, "auto", art) for o, s in zip(options, good)]
    bounds = [i == 0 or good[i].chord != good[i - 1].chord for i in range(len(good))]
    chosen = lead_lines(options, lo, hi, smooth=smooth, loop=False, boundaries=bounds)
    bodies = {s.index: c.body for s, c in zip(good, chosen)}
    notes, placed = _emit(player, segs, bodies, {})
    meta = _meta(placed, section, (b_lo, b_hi), song, level, share, "song_chord_tones", {"direction": direction, "shape": shape, "start": start, "smooth": smooth, "art": art})
    title = (f"Chord tones: {_dir_word(direction, shape)} arpeggios from {START_WORD[start]} over {section}" + (f" (bars {b_lo}–{b_hi})" if bars else "")
             + (", smoother voice-leading" if smooth else ""))
    how, listen = _explain_chord_tones(placed, meta, level, direction, shape, start, art)
    return we.Built(notes=notes, bpm=BPM[CHORD_TONES][level], title=title, how=how, listen=listen, meta=meta)


def _dir_word(direction: str, shape: str) -> str:
    return {"straight": "ascending" if direction == "up" else "descending", "updown": "up-and-back" if direction == "up" else "down-and-back",
            "skip": "skipping", "zig": "zig-zag"}[shape]


def build_approach(player: we.Player, level: str, song: dict[str, Any], section: str, bars: tuple[int, int] | None, *, kind: str, target: str, smooth: bool = False,
                   loop: bool = True) -> we.Built:
    segs, good, b_lo, b_hi, share, lo, hi = _prepare(player, level, song, section, bars, "approach-note")
    key = sph.practice_key_scale(song.get("practice_key"), song.get("original_key"))
    m = len(good)
    adjacent = lambda a, b: good[b].index == good[a].index + 1
    arrival = [j == 0 or not adjacent(j - 1, j) or good[j - 1].chord != good[j].chord for j in range(m)]
    looping = bool(loop and m > 1 and good[0].index == 0 and good[-1].index == len(segs) - 1 and good[-1].chord != good[0].chord)
    src: dict[int, int | None] = {}
    for j in range(m):
        if not arrival[j]:
            src[j] = None
        elif j > 0 and adjacent(j - 1, j):
            src[j] = j - 1
        elif j == 0 and looping:
            src[j] = m - 1
        else:
            src[j] = None
    allowed_roles = [target] if target != "auto" else ["third", "seventh", "root", "fifth"]
    figure: dict[int, dict[str, list[tuple[list[int], str]]]] = {}      # j -> target word -> [(offsets, note on how it was found)]
    skipped: list[dict[str, Any]] = []
    out_a: dict[int, Fraction] = {}
    notes_in: dict[int, int] = {}
    for j in range(m):
        p = src[j]
        if p is None:
            continue
        s_p, s_j = good[p], good[j]
        u = _unit_for(s_p.beats, level)
        prev_pcs = {t.pc for t in tones_of(s_p.info)}
        t_tones = tones_of(s_j.info)
        t_pcs = {t.pc for t in t_tones}
        per_role: dict[str, list[tuple[list[int], str]]] = {}
        for tw in targets_for(s_j.info, allowed_roles):
            role = START_ROLE.get(tw, "R")
            tone = next((t for t in t_tones if t.role == role or (role == "7" and t.role == "6")), None)
            if tone is None:
                continue
            opts = figure_offsets(kind, flip=(j % 2 == 1))
            how_found = "" if tw in allowed_roles else f"{s_j.info['symbol_written']} has no {target if target != 'auto' else 'such'} tone, so its third is the target"
            if kind == "diatonic":
                cp = s_j.info["concert"]
                tc = {"R": s_j.info["root_pc"], "3": s_j.info["third_pc"], "5": s_j.info.get("fifth_pc"), "7": s_j.info["upper_pc"], "6": s_j.info["upper_pc"]}.get(tone.role)
                d = diatonic_below(tc, s_j.chord, key) if tc is not None else None
                opts = [[-d], [1]] if d else [[-1], [1]]
                how_found = how_found or ("" if d else "the scale reader had no scale for this chord, so a chromatic approach stands in")
            for k_alt, off in enumerate(opts):
                pcs = [(tone.pc + o) % 12 for o in off]
                if any(pc in prev_pcs or pc in t_pcs for pc in pcs):
                    continue                                   # a neighbour that is itself a chord tone is not an approach
                if any(near_name(tone.name, o) is None for o in off):
                    continue
                said = how_found
                if k_alt and kind not in ("mixed", "enclosure"):
                    said = ("approached from the other side: the usual neighbour is a chord tone of " + s_p.info["symbol_written"] + " or " + s_j.info["symbol_written"]
                            + ", so it would not be an approach")
                per_role.setdefault(tw, []).append((off, said))
                break
        if not per_role:
            skipped.append({"to_bar": s_j.src_bar, "to_chord": s_j.chord, "reason": "every approach to this chord's target would land on a chord tone"})
            src[j] = None
            continue
        n_fig = len(next(iter(per_role.values()))[0][0])
        a = u * n_fig
        if s_p.beats - a < u:
            skipped.append({"to_bar": s_j.src_bar, "to_chord": s_j.chord, "reason": f"{s_p.chord} is too short to hold the approach"})
            src[j] = None
            continue
        out_a[p], notes_in[j], figure[j] = a, n_fig, per_role
    options: list[list[Cand]] = []
    for j, s in enumerate(good):
        body_len = s.beats - out_a.get(j, Fraction(0))
        u = _unit_for(s.beats, level)
        art = "accent" if level == "Advanced" else ""
        roles = list(figure[j]) if j in figure else (targets_for(s.info, allowed_roles) if arrival[j] else [])
        cands = body_candidates(s.info, body_len, level, lo, hi, roles or ["root"], arrival[j], art)
        if j in figure:
            withpre: list[Cand] = []
            for c in cands:
                tw = next((w for w in figure[j] if START_ROLE.get(w, "R") == c.target_role or (c.target_role == "6" and w == "seventh")), None)
                if tw is None:
                    continue
                off = figure[j][tw][0][0]
                T = c.body[0]
                u_p = _unit_for(good[src[j]].beats, level)
                pre, ok = [], True
                for o in off:
                    nm = near_name(T.name, o)
                    mid = T.midi + o
                    if nm is None or mid < lo or mid > hi:
                        ok = False
                        break
                    pre.append(Note(mid, nm, "approach", u_p))
                if ok:
                    withpre.append(Cand(c.body, pre, c.target_role, tw, c.key + (tw,)))
            cands = withpre
        options.append(cands)
    bounds = [bool(arrival[j]) for j in range(m)]
    chosen = lead_lines(options, lo, hi, smooth=smooth, loop=bool(looping and src.get(0) is not None), boundaries=bounds)
    bodies = {good[j].index: chosen[j].body for j in range(m)}
    tails: dict[int, list[Note]] = {}
    approaches: list[dict[str, Any]] = []
    for j in range(m):
        p = src.get(j)
        if p is None or not chosen[j].pre:
            continue
        tails[good[p].index] = chosen[j].pre
        tgt = chosen[j].body[0]
        approaches.append({"from_bar": good[p].src_bar, "from_chord": good[p].info["symbol_written"], "from_concert": good[p].chord, "to_bar": good[j].src_bar,
                           "to_chord": good[j].info["symbol_written"], "to_concert": good[j].chord, "to_beat": float(good[j].beat), "target_word": chosen[j].figure,
                           "target_role": tgt.role, "target": tgt.name, "approach": [n.name for n in chosen[j].pre], "offsets": [n.midi - tgt.midi for n in chosen[j].pre],
                           "kind": kind, "loop_back": bool(j == 0), "note": figure[j][chosen[j].figure][0][1]})
    notes, placed = _emit(player, segs, bodies, tails)
    meta = _meta(placed, section, (b_lo, b_hi), song, level, share, "song_approach", {"kind": kind, "target": target, "smooth": smooth, "loop": bool(looping)})
    meta["approaches"], meta["skipped_approaches"], meta["looping"] = approaches, skipped, bool(looping and src.get(0) is not None)
    title = (f"Approach notes: {KIND_LABEL[kind]} into {TARGET_WORD[target]} over {section}" + (f" (bars {b_lo}–{b_hi})" if bars else "") + (", smoother voice-leading" if smooth else ""))
    how, listen = _explain_approach(placed, meta, level, kind, target)
    return we.Built(notes=notes, bpm=BPM[APPROACH][level], title=title, how=how, listen=listen, meta=meta)


def _meta(placed: list[dict[str, Any]], section: str, bars: tuple[int, int], song: dict[str, Any], level: str, share: Fraction, kind: str, extra: dict[str, Any]) -> dict[str, Any]:
    flat = [n for p in placed if p["supported"] for n in p["notes"]]
    leaps = [abs(b["midi"] - a["midi"]) for a, b in zip(flat, flat[1:])]
    return {"song": song["title"], "song_hash": song["hash"], "section": section, "bars": [bars[0], bars[1]], "level": level, "segments": placed, "kind": kind,
            "unsupported": [p for p in placed if not p["supported"]], "supported_share": float(share), "largest_leap": max(leaps) if leaps else 0,
            "mean_leap": round(sum(leaps) / len(leaps), 2) if leaps else 0.0, "resolutions": [], **extra}


# ---------------------------------------------------------------- explanations (facts computed from the notes actually written)


def _rhythm_word(level: str) -> str:
    return "quarter notes" if UNIT[level] == 1 else "eighth notes"


def _explain_chord_tones(placed, meta, level, direction, shape, start, art) -> tuple[list[str], list[str]]:
    how = [f"Play each chord's own notes, {_dir_word(direction, shape)}, starting on {START_WORD[start]}, in {_rhythm_word(level)} at ♩ = {BPM[CHORD_TONES][level]}. "
           "The chord symbols above the staff are written for your instrument, and every note is the root, third, fifth or seventh of the chord it sits under.",
           "The arpeggio changes on the beat the chart changes chord — in a split bar that is halfway through the bar."]
    if art == "slur2":
        how.append("Slur each pair of notes; tongue the first note of every pair.")
    if art == "accent":
        how.append("Accent the first note of every chord.")
    listen = ["Hear the chord quality as you climb: the third tells you major or minor, the seventh its colour."]
    notes = {p["note"] for p in placed if p["supported"] and p.get("note")}
    listen.extend(sorted(notes))
    if meta["unsupported"]:
        listen.append("Rests mark chords this version can't write chord tones for: " + "; ".join(f"{p['concert']} (bar {p['bar']}: {p['reason']})" for p in meta["unsupported"]) + ".")
    return how, listen


def _explain_approach(placed, meta, level, kind, target) -> tuple[list[str], list[str]]:
    how = [f"Play the chord's tones, and in the last {'beat' if level == 'Beginner' else 'part of the beat'} before the chart changes chord play {KIND_LABEL[kind]} into {TARGET_WORD[target]} of the new chord, "
           f"landing exactly on the beat of the change, in {_rhythm_word(level)} at ♩ = {BPM[APPROACH][level]}.",
           "The approach notes are the only notes in this line that are NOT chord tones; each one is chosen so it is not a chord tone of the chord it leaves or of the chord it enters."]
    listen = []
    for a in meta["approaches"][:3]:
        steps = ", ".join(f"{n} ({o:+d})" for n, o in zip(a["approach"], a["offsets"]))
        listen.append(f"Bar {a['from_bar']} → {a['to_bar']}: {a['from_chord']} → {a['to_chord']}: {steps} resolves to the {('seventh' if a['target_role'] in ('7', '6') else 'third' if a['target_role'] == '3' else 'root' if a['target_role'] == 'R' else 'fifth')} {a['target']}"
                      + (" (back to the top of the form, for the repeat)." if a["loop_back"] else ".") + (f" ({a['note']})" if a.get("note") else ""))
    for sk in meta["skipped_approaches"][:3]:
        listen.append(f"No approach into bar {sk['to_bar']} ({sk['to_chord']}): {sk['reason']}.")
    if meta["unsupported"]:
        listen.append("Rests mark chords this version can't write for: " + "; ".join(f"{p['concert']} (bar {p['bar']}: {p['reason']})" for p in meta["unsupported"]) + ".")
    return how, listen


# ---------------------------------------------------------------- verification against the chart's own chords


def _tone_pcs(chord: str) -> dict[int, str]:
    return {pc: r for pc, r in sph.chord_tone_roles(chord).items() if r in ("R", "3", "5", "7", "6")}


def verify(player: we.Player, level: str, built: we.Built, diag: dict[str, Any]) -> list[dict[str, Any]]:
    """Checks made against the chart's own chord symbols (``chord_tone_roles``), on the sounding pitch, with the stored rows tied note-for-note to the notation."""
    meta = built.meta
    lo, hi = player.window(level)
    pitched = [n for n in built.notes if not n.rest]
    midi = [n.midi for n in pitched]
    checks = [
        {"name": "bars_add_up", "ok": we.total_beats(built.notes) % we.BEATS_PER_BAR == 0, "detail": f"{we.total_beats(built.notes) / we.BEATS_PER_BAR} bars of 4"},
        {"name": "written_inside_level_window", "ok": all(lo <= m <= hi for m in midi), "detail": f"{lo}-{hi}"},
        {"name": "written_inside_playable_range", "ok": all(player.play_low <= m <= player.play_high for m in midi), "detail": f"{player.play_low}-{player.play_high}"},
        {"name": "notation_validation", "ok": bool(diag.get("notation_validation_ok")), "detail": "; ".join(diag.get("notation_validation_errors") or []) or "passed"},
        {"name": "sounding_equals_written_minus_offset", "ok": all(((m - player.offset) % 12) == ((sph.pc_of(n.spelled) - player.semitones) % 12) for m, n in zip(midi, pitched)),
         "detail": f"written − {player.offset} semitones, octave included"},
    ]
    bad = _check_rows(built, meta, player)
    checks.append({"name": "every_note_is_what_the_exercise_says_it_is", "ok": not bad, "detail": bad or "chord tones of their chord; approach notes resolve onto a chord tone"})
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise we.WarmupUnavailable("; ".join(f"{c['name']}: {c['detail']}" for c in failed))
    return checks


def _check_rows(built: we.Built, meta: dict[str, Any], player: we.Player) -> str:
    segs = meta["segments"]
    i, pos = 0, Fraction(0)
    starts: list[Fraction] = []
    rows: list[tuple[Fraction, dict[str, Any], dict[str, Any]]] = []
    for p in segs:
        t0 = Fraction(p["bar"] - meta["bars"][0]) * 4 + Fraction(p["beat"]).limit_denominator(8)
        if t0 != pos:
            return f"the chord at bar {p['bar']} starts at beat {pos}, not {t0}"
        starts.append(t0)
        if not p["supported"]:
            left = Fraction(p["beats"]).limit_denominator(8)
            while left > 0:
                if i >= len(built.notes) or not built.notes[i].rest:
                    return f"bar {p['bar']} ({p['concert']}) should be a rest"
                left -= built.notes[i].beats
                pos += built.notes[i].beats
                i += 1
            if left != 0:
                return f"the rest over {p['concert']} does not fill its beats"
            continue
        used = Fraction(0)
        for r in p["notes"]:
            if i >= len(built.notes) or built.notes[i].rest or built.notes[i].midi != r["midi"] or built.notes[i].beats != Fraction(r["beats"]).limit_denominator(8):
                return f"the written notation differs from the exercise at bar {p['bar']}"
            rows.append((pos, r, p))
            pos += built.notes[i].beats
            used += built.notes[i].beats
            i += 1
        if used != Fraction(p["beats"]).limit_denominator(8):
            return f"the notes over {p['concert']} (bar {p['bar']}) do not fill its beats"
    if i != len(built.notes):
        return "the notation has notes the exercise does not describe"
    # roles against the chart's own chords
    for k, (t, r, p) in enumerate(rows):
        pcs = _tone_pcs(p["concert"])
        pc = (r["midi"] - player.offset) % 12
        if r["role"] == "approach":
            if pc in pcs:
                return f"approach note {r['name']} in bar {p['bar']} is a chord tone of {p['concert']}"
        elif pcs.get(pc) != r["role"] and not (r["role"] in ("7", "6") and pcs.get(pc) in ("7", "6")):
            return f"{r['name']} is not the {r['role']} of {p['concert']} at bar {p['bar']}"
    # every run of approach notes lands on a chord tone of the chord that follows it, on that chord's first beat
    n = len(rows)
    k = 0
    while k < n:
        if rows[k][1]["role"] != "approach":
            k += 1
            continue
        j = k
        while j < n and rows[j][1]["role"] == "approach":
            j += 1
        nxt = rows[j % n] if (j < n or meta.get("looping")) else None
        if nxt is None:
            return f"approach notes in bar {rows[k][2]['bar']} have nothing to resolve onto"
        t_t, t_r, t_p = nxt
        last = rows[j - 1]
        if t_p["concert"] == rows[k][2]["concert"]:
            return f"the approach in bar {rows[k][2]['bar']} does not leave its own chord"
        if not t_r.get("target") or _tone_pcs(t_p["concert"]).get((t_r["midi"] - player.offset) % 12) not in ("R", "3", "5", "7", "6"):
            return f"the approach in bar {rows[k][2]['bar']} does not land on a chord tone of {t_p['concert']}"
        if not (j < n and last[0] + Fraction(last[1]["beats"]).limit_denominator(8) == t_t) and not (j >= n and meta.get("looping")):
            return f"the approach in bar {rows[k][2]['bar']} does not land on the beat the chart changes chord"
        if abs(last[1]["midi"] - t_r["midi"]) not in (1, 2):
            return f"the last approach note in bar {rows[k][2]['bar']} is not a step from its target"
        if any((a[1]["midi"] - player.offset) % 12 in _tone_pcs(t_p["concert"]) for a in rows[k:j]):
            return f"an approach note in bar {rows[k][2]['bar']} is a chord tone of {t_p['concert']}"
        k = j
    return ""
