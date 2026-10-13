"""MC2.2 — localized explanations for a span motif: this chord + these notes + this concept.

Everything here is *derived from the line as generated* (pitches, chord spellings, rhythm
events, and the generator's per-note kinds / colour choices) and every claim is
re-checked against the notes before it is made:

- a note role (3rd, ♭9, …) is computed from the active chord's spelling;
- "enclosure" needs one note above and one below the target, both within a whole step;
- a colour scale (altered, diminished, whole-tone, lydian dominant) is named only when
  notes on that chord actually come from it and not from the plain chord-scale;
- a pentatonic is named only when the chord's notes (approaches aside) fit it;
- "syncopation" needs an off-beat onset that sustains across the next beat.

Works on a concert motif or a written (projected) one: pass the chart key and the chord
symbols as displayed, and every name is spelled in that chart.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Sequence

LETTERS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACC = {0: "", 1: "#", 2: "##", 11: "b", 10: "bb"}

_MODES: dict[tuple[int, ...], str] = {
    (0, 2, 4, 5, 7, 9, 11): "Ionian (major)",
    (0, 2, 3, 5, 7, 9, 10): "Dorian",
    (0, 1, 3, 5, 7, 8, 10): "Phrygian",
    (0, 2, 4, 6, 7, 9, 11): "Lydian",
    (0, 2, 4, 5, 7, 9, 10): "Mixolydian",
    (0, 2, 3, 5, 7, 8, 10): "Aeolian (natural minor)",
    (0, 1, 3, 5, 6, 8, 10): "Locrian",
    (0, 2, 3, 5, 7, 8, 11): "harmonic minor",
    (0, 1, 4, 5, 7, 8, 10): "Phrygian dominant",
    (0, 2, 3, 5, 7, 9, 11): "melodic minor",
    (0, 2, 4, 6, 7, 9, 10): "Lydian dominant",
    (0, 1, 3, 4, 6, 8, 10): "altered",
    (0, 1, 3, 5, 6, 9, 10): "Locrian ♮6",
    (0, 2, 3, 5, 6, 8, 10): "Locrian ♮2",
    (0, 2, 4, 5, 7, 8, 10): "Mixolydian ♭6",
}
_PARENT_OFFSET = {"Ionian (major)": 0, "Dorian": 2, "Phrygian": 4, "Lydian": 5, "Mixolydian": 7,
                  "Aeolian (natural minor)": 9, "Locrian": 11}
# (semitones above the root, letter steps above the root) — conventional jazz spellings.
_COLOR_SPELLING: dict[str, tuple[tuple[int, int], ...]] = {
    "altered": ((0, 0), (1, 1), (3, 2), (4, 2), (6, 4), (8, 5), (10, 6)),
    "diminished": ((0, 0), (1, 1), (3, 2), (4, 2), (6, 3), (7, 4), (9, 5), (10, 6)),
    "whole_tone": ((0, 0), (2, 1), (4, 2), (6, 3), (8, 4), (10, 6)),
    "lydian_dominant": ((0, 0), (2, 1), (4, 2), (6, 3), (7, 4), (9, 5), (10, 6)),
}
COLOR_NAMES = {
    "altered": "altered scale",
    "diminished": "half-whole diminished",
    "whole_tone": "whole-tone scale",
    "lydian_dominant": "Lydian dominant",
    "side_slip": "side-slip",
}
DETAIL_TEXT = {
    "passing": "passing tone",
    "neighbour": "neighbour tone",
    "chord_tone": "chord tone",
    "chromatic_passing": "chromatic passing tone",
    "enclosure": "enclosure",
}


def pretty(name: str) -> str:
    """Bb → B♭, F# → F♯ (letter kept, accidentals as music symbols)."""
    text = str(name or "")
    return text[:1] + text[1:].replace("#", "♯").replace("b", "♭") if text else text


def spell_from_root(root_name: str, pattern: Sequence[tuple[int, int]]) -> list[str]:
    from music_theory import pitch_class_from_spelled_note

    root_pc = int(pitch_class_from_spelled_note(root_name)) % 12
    li = LETTERS.index(root_name[0].upper())
    out = []
    for semis, letter_steps in pattern:
        letter = LETTERS[(li + letter_steps) % 7]
        acc = (root_pc + semis - NATURAL[letter]) % 12
        out.append(letter + _ACC.get(acc, ""))
    return out


def degree_label(ctx: Any, pc: int) -> str:
    """The note's function against the chord's own root and quality (3rd, 7th, ♭9, ♯11 …)."""
    root = ctx.chord_pcs[0]
    iv = (pc - root) % 12
    q = ctx.quality
    minorish = q in ("minor", "m7", "half-dim", "dim")
    table = {
        0: "root",
        1: "♭9",
        2: "9th",
        3: "3rd" if minorish else "♯9",
        4: "3rd" if not minorish else "major 3rd",
        5: "4th" if q == "sus" else "11th",
        6: "♭5" if q in ("half-dim", "dim") else "♯11",
        7: "5th",
        8: "♯5" if q == "aug" else ("♭13" if q == "dom" else "♭6"),
        9: "7th" if q == "dim" else ("13th" if q == "dom" else "6th"),
        10: "7th" if q in ("m7", "dom", "half-dim") else "♭7",
        11: "7th" if q == "maj7" else "major 7th",
    }
    return table[iv]


def _root_name(chord: str) -> str:
    from music_theory import split_chord

    return str(split_chord(str(chord).split("/", 1)[0])[0] or "C")


def _rotate_scale(ctx: Any) -> list[str]:
    root = ctx.chord_pcs[0]
    pairs = sorted(zip(ctx.scale_pcs, ctx.scale_names), key=lambda t: (t[0] - root) % 12)
    return [n for _pc, n in pairs]


def mode_name(ctx: Any, chord: str) -> dict[str, Any]:
    """Chord-scale as a named mode (and its parent major scale when it is a church mode)."""
    root = ctx.chord_pcs[0]
    ivs = tuple(sorted({(p - root) % 12 for p in ctx.scale_pcs}))
    mode = _MODES.get(ivs)
    names = _rotate_scale(ctx)
    root_name = _root_name(chord)
    out: dict[str, Any] = {"kind": "scale", "notes": [pretty(n) for n in names], "pcs": sorted(set(ctx.scale_pcs))}
    if mode is None:
        out["name"] = f"{pretty(root_name)} chord-scale"
        return out
    out["name"] = f"{pretty(root_name)} {mode}" if mode != "Ionian (major)" else f"{pretty(root_name)} major scale"
    if mode in _PARENT_OFFSET and _PARENT_OFFSET[mode]:
        parent_pc = (root - _PARENT_OFFSET[mode]) % 12
        parent = next((n for p, n in zip(ctx.scale_pcs, ctx.scale_names) if p == parent_pc), None)
        if parent:
            out["parent"] = f"{pretty(parent)} major scale"
    return out


def _pentatonic_info(ctx: Any, chord: str) -> dict[str, Any] | None:
    from span_motif_engine import _pentatonic

    pcs = _pentatonic(ctx)
    if len(pcs) != 5:
        return None
    root = ctx.chord_pcs[0]
    ivs = tuple(sorted((p - root) % 12 for p in pcs))
    quality = {(0, 3, 5, 7, 10): "minor pentatonic", (0, 2, 4, 7, 9): "major pentatonic",
               (0, 3, 5, 6, 10): "minor pentatonic ♭5"}.get(ivs)
    if quality is None:
        return None
    names = [ctx.name_for_pc(p) or "" for p in sorted(pcs, key=lambda p: (p - root) % 12)]
    return {"kind": "pentatonic", "name": f"{pretty(_root_name(chord))} {quality}",
            "notes": [pretty(n) for n in names], "pcs": sorted(pcs)}


def _color_info(color: str, ctx: Any, chord: str) -> dict[str, Any] | None:
    from span_motif_engine import _color_collection

    pcs = _color_collection(color, ctx)
    if pcs is None:
        return None
    root_name = _root_name(chord)
    if color in _COLOR_SPELLING:
        names = spell_from_root(root_name, _COLOR_SPELLING[color])
        name = f"{pretty(root_name)} {COLOR_NAMES.get(color, color)}"
    else:
        from music_theory import spell_pitch_class

        slipped = (ctx.chord_pcs[0] + 1) % 12
        names = [spell_pitch_class(p, mode="flat") for p in sorted(set(pcs), key=lambda p: (p - slipped) % 12)]
        mode = _MODES.get(tuple(sorted({(p - ctx.chord_pcs[0]) % 12 for p in ctx.scale_pcs})), "scale")
        name = f"side-slip — the {pretty(chord)} idea a half step up ({pretty(names[0])} {mode})"
    return {"kind": "color", "color": color, "name": name, "notes": [pretty(n) for n in names], "pcs": sorted(set(pcs))}


def _beat_label(onset: Fraction, bar_len: Fraction) -> tuple[int, str]:
    bar = int(onset // bar_len) + 1
    pos = onset - bar_len * (bar - 1)
    beat = int(pos) + 1
    frac = pos - int(pos)
    if frac == 0:
        return bar, f"beat {beat}"
    if frac == Fraction(1, 2):
        return bar, f"the “and” of {beat}"
    if frac == Fraction(1, 4):
        return bar, f"the “e” of {beat}"
    if frac == Fraction(3, 4):
        return bar, f"the “a” of {beat}"
    return bar, f"beat {beat} (triplet)"


def _crosses_beat(onset: Fraction, duration: Fraction, beat: Fraction) -> bool:
    if onset % beat == 0:
        return False
    return onset + duration > onset - onset % beat + beat


def _bars_text(bars: Sequence[int]) -> str:
    bars = sorted(set(bars))
    if not bars:
        return ""
    if len(bars) == 1:
        return f"bar {bars[0]}"
    if bars == list(range(bars[0], bars[-1] + 1)):
        return f"bars {bars[0]}–{bars[-1]}"
    return "bars " + ", ".join(str(b) for b in bars)


# --------------------------------------------------------------------------- analysis


def explain_span_motif(
    motif: dict[str, Any],
    *,
    key: str,
    chords: Sequence[str] | None = None,
    seed_motif: dict[str, Any] | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    """Chord-by-chord, voice-leading and rhythm explanations for ``motif`` (see module doc)."""
    from melodic_pattern_engine import build_context
    from melodic_rhythm_engine import display_rhythm, events_from_json, parse_meter
    from span_rhythm_grammar import bar_signatures

    timeline = list(motif.get("chord_timeline") or [])
    symbols = list(chords) if chords else [t["chord"] for t in timeline]
    lvl = str(level or motif.get("level") or "Intermediate")
    rank = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}.get(lvl, 1)
    names = [str(n) for n in motif.get("notes") or []]
    midis = [int(m) for m in motif.get("midi") or []]
    cis = [int(c) for c in motif.get("note_chord_index") or []]
    kinds = list(motif.get("note_kinds") or [""] * len(midis))
    details = list(motif.get("note_details") or kinds)
    meter = str(motif.get("meter") or (motif.get("rhythm_meta") or {}).get("meter") or "4/4")
    m = parse_meter(meter)
    events = [e for e in events_from_json(motif.get("rhythm_events") or []) if not e.rest]
    ctxs = [build_context(key, sym) for sym in symbols]
    n_slots_seed = len((seed_motif or {}).get("chord_timeline") or []) or len(timeline)
    seed_idx = set(motif.get("seed_note_indices") or [])
    colors = {int(c["chord_index"]): str(c["color"]) for c in motif.get("advanced_colors") or []}
    family = str(motif.get("strategy_family") or "")
    pent_focus = family == "pentatonic_cell" or motif.get("focus_preference") == "pentatonic"

    def first_note(i: int) -> int:
        return int(timeline[i]["first_note"])

    def last_note(i: int) -> int:
        return int(timeline[i]["last_note"])

    targets = {first_note(i) for i in range(len(timeline))}

    # ---- per-note function (verified)
    functions: list[str] = []
    for k, (mid, ci) in enumerate(zip(midis, cis)):
        ctx = ctxs[ci]
        pc = mid % 12
        nxt_t = k + 1 if k + 1 in targets else None
        f = ""
        if k in targets:
            f = "target"
        elif k == len(midis) - 1:
            f = "ending"
        elif nxt_t is not None and k >= 1 and k - 1 not in targets:
            t = midis[nxt_t]
            a, b = midis[k - 1], mid
            if 1 <= abs(a - t) <= 2 and 1 <= abs(b - t) <= 2 and (a - t) * (b - t) < 0:
                f = "enclosure"
        if not f and k + 2 in targets and k + 2 < len(midis) and k not in targets:
            t = midis[k + 2]
            a, b = mid, midis[k + 1]
            if 1 <= abs(a - t) <= 2 and 1 <= abs(b - t) <= 2 and (a - t) * (b - t) < 0:
                f = "enclosure"
        if not f and nxt_t is not None:
            t = midis[nxt_t]
            if abs(t - mid) == 1 and pc not in ctx.scale_pcs:
                f = "chromatic approach"
            elif abs(t - mid) <= 2:
                f = "step into the change"
        if not f:
            color = colors.get(ci)
            col = _color_info(color, ctx, symbols[ci]) if color else None
            if col and pc in col["pcs"] and pc not in ctx.scale_pcs:
                f = "colour tension"
            elif pc not in ctx.scale_pcs:
                f = "chromatic passing tone" if 0 < k < len(midis) - 1 and (midis[k - 1] - mid) * (mid - midis[k + 1]) > 0 else "chromatic note"
            elif pc in ctx.chord_pcs:
                f = "chord tone"
            elif 0 < k < len(midis) - 1 and (midis[k - 1] - mid) * (mid - midis[k + 1]) > 0:
                f = "passing tone"
            elif 0 < k < len(midis) - 1 and midis[k - 1] == midis[k + 1]:
                f = "neighbour tone"
            else:
                f = "scale tone"
        functions.append(f)

    # ---- chord blocks
    chord_blocks = []
    for i, slot in enumerate(timeline):
        ctx = ctxs[i]
        sym = symbols[i]
        lo, hi = first_note(i), last_note(i)
        idx = list(range(lo, hi + 1))
        bars = list(range(int(slot["first_bar"]) + 1, int(slot["first_bar"]) + int(slot["bars"]) + 1))
        approach = {k for k in idx if functions[k] in ("enclosure", "chromatic approach")}
        core_pcs = {midis[k] % 12 for k in idx if k not in approach}
        collection = None
        evidence: list[str] = []
        color = colors.get(i)
        if color:
            col = _color_info(color, ctx, sym)
            if col:
                ev = [k for k in idx if midis[k] % 12 in col["pcs"] and midis[k] % 12 not in ctx.scale_pcs]
                if ev:
                    collection = col
                    evidence = list(dict.fromkeys(pretty(names[k]) for k in ev))
        if collection is None and pent_focus:
            pent = _pentatonic_info(ctx, sym)
            if pent and core_pcs <= set(pent["pcs"]) and len(core_pcs) >= 2:
                collection = pent
        if collection is None:
            if core_pcs <= set(ctx.chord_pcs):
                tones = [pretty(n) for n in ctx.chord_names]
                collection = {"kind": "chord", "name": f"{pretty(sym)} chord tones", "notes": tones, "pcs": sorted(ctx.chord_pcs)}
            elif core_pcs <= set(ctx.scale_pcs):
                collection = mode_name(ctx, sym)
            else:
                from span_motif_engine import _bebop

                bebop = set(_bebop(ctx))
                if core_pcs <= bebop and family == "bebop_run":
                    from music_theory import spell_pitch_class

                    extra = sorted(bebop - set(ctx.scale_pcs))
                    root = ctx.chord_pcs[0]
                    ordered = sorted(bebop, key=lambda p: (p - root) % 12)
                    collection = {
                        "kind": "bebop", "name": f"{pretty(_root_name(sym))} bebop scale", "pcs": sorted(bebop),
                        "notes": [pretty(ctx.name_for_pc(p) or spell_pitch_class(p, mode="sharp")) for p in ordered],
                        "passing": [pretty(ctx.name_for_pc(p) or spell_pitch_class(p, mode="sharp")) for p in extra],
                    }
        note_rows = []
        for k in idx:
            pc = midis[k] % 12
            role = degree_label(ctx, pc)
            bar, where = _beat_label(events[k].onset, m.bar) if k < len(events) else (0, "")
            note_rows.append({
                "index": k, "name": pretty(names[k]), "role": role, "chord_tone": pc in ctx.chord_pcs,
                "function": functions[k], "bar": bar, "where": where, "seed": k in seed_idx,
                "detail": details[k] if k < len(details) else "",
            })
        chord_blocks.append({
            "index": i, "chord": pretty(sym), "bars": _bars_text(bars), "collection": collection,
            "evidence": evidence, "notes": note_rows, "lines": _chord_lines(note_rows, collection, evidence, rank),
        })

    # ---- voice leading at each change
    vl = []
    for i in range(1, len(timeline)):
        t_idx = first_note(i)
        prev_idx = list(range(first_note(i - 1), last_note(i - 1) + 1))
        if not prev_idx:
            continue
        a_ctx, b_ctx = ctxs[i - 1], ctxs[i]
        a_sym, b_sym = pretty(symbols[i - 1]), pretty(symbols[i])
        t = midis[t_idx]
        t_name, t_role = pretty(names[t_idx]), degree_label(b_ctx, t % 12)
        p_idx = prev_idx[-1]
        p = midis[p_idx]
        items = []
        sevenths = [k for k in prev_idx[-3:] if degree_label(a_ctx, midis[k] % 12) == "7th" and midis[k] % 12 in a_ctx.chord_pcs]
        if sevenths and t_role == "3rd" and 1 <= abs(midis[sevenths[-1]] - t) <= 2:
            s = sevenths[-1]
            items.append(("7→3", f"{pretty(names[s])} (7th of {a_sym}) → {t_name} (3rd of {b_sym}) — the guide-tone resolution"))
        if (
            a_ctx.quality == "dom" and degree_label(a_ctx, p % 12) == "3rd" and t - p == 1 and t_role == "root"
        ):
            items.append(("leading_tone", f"{pretty(names[p_idx])} (3rd of {a_sym}) rises a half step to {t_name}, the root of {b_sym}"))
        if t % 12 in a_ctx.chord_pcs:
            items.append(("common_tone", f"{t_name} is common to {a_sym} and {b_sym}: the {degree_label(a_ctx, t % 12)} of {a_sym} becomes the {t_role} of {b_sym}"))
        if functions[p_idx] == "enclosure" and len(prev_idx) >= 2:
            items.append(("enclosure", f"{pretty(names[p_idx - 1])} and {pretty(names[p_idx])} enclose {t_name} ({t_role} of {b_sym})"))
        elif functions[p_idx] == "chromatic approach":
            side = "below" if p < t else "above"
            items.append(("chromatic_approach", f"{pretty(names[p_idx])} approaches {t_name} chromatically from {side}"))
        if not items:
            move = "steps" if abs(t - p) <= 2 else "moves"
            items.append(("step", f"{pretty(names[p_idx])} {move} to {t_name}, the {t_role} of {b_sym}"))
        vl.append({"from_chord": i - 1, "to_chord": i, "from_index": p_idx, "to_index": t_idx,
                   "kinds": [k for k, _ in items], "lines": [txt for _, txt in items]})
    end = len(midis) - 1
    ending = None
    if midis:
        last_ctx = ctxs[cis[end]]
        ending = f"Ends on {pretty(names[end])} — the {degree_label(last_ctx, midis[end] % 12)} of {pretty(symbols[cis[end]])}"

    # ---- rhythm
    sigs = bar_signatures(events, meter)
    rhythm = []
    if sigs:
        cell = sigs[0]
        cell_events = [e for e in events if e.onset < m.bar]
        cell_text = display_rhythm(cell_events, meter)
        same = [b + 1 for b, s in enumerate(sigs) if b > 0 and s == cell]
        related = [
            b + 1 for b, s in enumerate(sigs)
            if b > 0 and s != cell and len(s) >= 2
            and len({x[0] for x in cell} & {x[0] for x in s}) / max(1, len({x[0] for x in cell})) >= 0.6
        ]
        text = f"Rhythmic cell {cell_text} — stated in bar 1"
        if same:
            text += f", repeated in {_bars_text(same)}"
        if related and rank >= 1:
            text += f", varied in {_bars_text(related)}"
        rhythm.append({"kind": "cell", "bars": [1] + same, "text": text})
        if seed_motif and motif.get("span_length") in ("standard", "extended"):
            s_ev = [e for e in events_from_json(seed_motif.get("rhythm_events") or []) if not e.rest]
            seed_cell = display_rhythm([e for e in s_ev if e.onset < m.bar], meter)
            if seed_cell and seed_cell != cell_text:
                rhythm.append({"kind": "development", "bars": [1],
                               "text": f"Seed rhythm {seed_cell} is subdivided to {cell_text}: the seed's notes keep their beats, new notes fill the split values"})
    if rank >= 1:
        syncs = [k for k, e in enumerate(events) if _crosses_beat(e.onset, e.duration, m.beat)]
        cap = 6 if rank == 2 else 2
        for k in syncs[:cap]:
            bar, where = _beat_label(events[k].onset, m.bar)
            nxt_change = (k + 1) in targets
            label = "Anticipation" if nxt_change else "Syncopation"
            rhythm.append({"kind": "syncopation", "bars": [bar], "index": k,
                           "text": f"{label}: {pretty(names[k])} enters on {where} of bar {bar} ({pretty(symbols[cis[k]])}) and is held across the beat"})
        if len(syncs) > cap:
            rhythm.append({"kind": "syncopation_more", "bars": [], "text": f"…and {len(syncs) - cap} more syncopated entries"})
        trip_bars: dict[int, int] = {}
        for k, e in enumerate(events):
            if e.tuplet and e.tuplet_start:
                trip_bars.setdefault(int(e.onset // m.bar) + 1, k)
        for bar, k in trip_bars.items():
            _b, where = _beat_label(events[k].onset, m.bar)
            rhythm.append({"kind": "triplet", "bars": [bar], "index": k,
                           "text": f"Triplet figure from {where.replace(' (triplet)', '')} of bar {bar} over {pretty(symbols[cis[k]])}"})
    for k, e in enumerate(events):
        if e.duration < 2:
            continue
        bar, where = _beat_label(e.onset, m.bar)
        if k == len(events) - 1:
            reason = "held resolution — the phrase ends"
        elif (e.onset + e.duration) % m.bar == 0 and (k + 1) in targets:
            reason = f"a breath before {pretty(symbols[cis[k + 1]])}"
        elif e.onset % m.bar == 0:
            reason = "an arrival held on the barline"
        else:
            reason = "space inside the phrase"
        if rank >= 1 or k == len(events) - 1:
            rhythm.append({"kind": "long", "bars": [bar], "index": k, "text": f"Held {pretty(names[k])} ({where}, bar {bar}): {reason}"})

    # ---- development (Build): where the seed lives in the exercise
    development = []
    if seed_idx and motif.get("span_length") in ("standard", "extended"):
        for i in range(len(timeline)):
            idx = list(range(first_note(i), last_note(i) + 1))
            kept = [pretty(names[k]) for k in idx if k in seed_idx]
            added = []
            for k in idx:
                if k in seed_idx:
                    continue
                d = details[k] if k < len(details) else ""
                verified = _verify_detail(d, k, midis, ctxs[cis[k]])
                added.append(f"{pretty(names[k])} ({DETAIL_TEXT.get(verified, 'added note')})")
            pass_no = i // n_slots_seed + 1 if len(timeline) > n_slots_seed else None
            label = pretty(symbols[i]) + (f" (pass {pass_no})" if pass_no else "")
            if kept:
                text = f"{label}: seed {' – '.join(kept)} kept"
                text += f"; added {', '.join(added)}" if added else ""
            else:
                text = f"{label}: new line back to the opening ({' – '.join(pretty(names[k]) for k in idx)})"
            development.append({"chord_index": i, "text": text, "kept": kept, "added": added})

    summary = []
    key_ctx = build_context(key, None)
    if timeline and all(midis[k] % 12 in set(key_ctx.key_pcs) for k in range(len(midis))):
        tonic = pretty(key_ctx.tonic)
        summary.append(f"Every note comes from the {tonic} {'minor' if key_ctx.mode == 'minor' else 'major'} scale — "
                       f"the chords share one parent scale here")
    return {
        "level": lvl, "summary": summary, "chords": chord_blocks, "voice_leading": vl, "ending": ending,
        "rhythm": rhythm, "development": development, "functions": functions,
    }


def _verify_detail(detail: str, k: int, midis: Sequence[int], ctx: Any) -> str:
    """The generator's label for an added note, kept only if the notes bear it out."""
    if not 0 < k < len(midis) - 1:
        return detail if detail in DETAIL_TEXT else ""
    a, x, b = midis[k - 1], midis[k], midis[k + 1]
    between = (a - x) * (x - b) > 0
    if detail == "passing" and between:
        return "passing"
    if detail == "chromatic_passing" and between and x % 12 not in ctx.scale_pcs:
        return "chromatic_passing"
    if detail == "chord_tone" and x % 12 in ctx.chord_pcs:
        return "chord_tone"
    if detail == "enclosure":
        return "enclosure"
    if detail in ("neighbour", "passing") and (abs(x - a) <= 2 or abs(x - b) <= 2):
        return "passing" if between else "neighbour"
    return ""


def _chord_lines(rows: Sequence[dict[str, Any]], collection: dict[str, Any] | None, evidence: Sequence[str], rank: int) -> list[str]:
    lines = []
    if collection:
        notes = "–".join(collection.get("notes") or [])
        if collection["kind"] == "color":
            lines.append(f"Uses {collection['name']} here: {notes}" + (f" (in the line: {', '.join(evidence)})" if evidence else ""))
        elif collection["kind"] == "scale":
            parent = f" — from the {collection['parent']}" if collection.get("parent") else ""
            if rank == 0:
                lines.append(f"Notes from {collection.get('parent') or collection['name']}")
            else:
                lines.append(f"Uses {collection['name']}{parent}: {notes}")
        elif collection["kind"] in ("pentatonic", "bebop"):
            lines.append(f"Uses {collection['name']}: {notes}")
        elif collection["kind"] == "chord":
            lines.append(f"Chord tones only: {notes}")
        if collection.get("passing"):
            lines.append(f"Bebop passing tone: {', '.join(collection['passing'])}")
    seen: set[tuple[str, str]] = set()
    for r in rows:
        f = r["function"]
        role = r["role"]
        if collection and collection.get("color") == "side_slip" and f == "colour tension":
            role = "side-slip note"
        if (r["name"], role) in seen and f not in ("enclosure", "chromatic approach"):
            continue
        line = None
        if f == "target":
            line = f"{r['name']} — {role}, lands on {r['where']}"
        elif rank == 0:
            continue
        elif f == "enclosure":
            line = f"{r['name']} — enclosure note around the next target"
        elif f == "chromatic approach":
            line = f"{r['name']} — chromatic approach into the change"
        elif f == "ending":
            line = f"{r['name']} — {role}, the final note"
        elif f == "colour tension" and rank >= 2:
            line = f"{r['name']} — {role} (colour tension)"
        elif r["chord_tone"] and role in ("3rd", "7th"):
            line = f"{r['name']} — {role} ({r['where']})"
        elif rank >= 2 and f == "chromatic passing tone":
            line = f"{r['name']} — {f}"
        if line:
            seen.add((r["name"], role))
            lines.append(line)
    return lines


def explanation_markdown(expl: dict[str, Any]) -> list[str]:
    """Compact markdown blocks for the UI (Beginner short; Advanced richer)."""
    rank = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}.get(str(expl.get("level")), 1)
    out = []
    harmony = []
    for line in expl.get("summary") or []:
        harmony.append(f"_{line}._")
    for block in expl.get("chords") or []:
        lines = block["lines"] if rank else block["lines"][:2]
        if not lines:
            continue
        harmony.append(f"**{block['chord']}** · {block['bars']}  \n" + "  \n".join(f"• {x}" for x in lines))
    if harmony:
        out.append("**Harmony & melody**\n\n" + "\n\n".join(harmony))
    vl = []
    for item in expl.get("voice_leading") or []:
        vl.extend(item["lines"][: (1 if rank == 0 else 2 if rank == 1 else 3)])
    if expl.get("ending"):
        vl.append(expl["ending"])
    if vl:
        out.append("**Voice leading**  \n" + "  \n".join(f"• {x}" for x in vl))
    rhythm = [r["text"] for r in expl.get("rhythm") or []]
    if rhythm:
        out.append("**Rhythm**  \n" + "  \n".join(f"• {x}" for x in rhythm))
    dev = [d["text"] for d in expl.get("development") or []]
    if dev:
        out.append("**Where the seed is**  \n" + "  \n".join(f"• {x}" for x in dev))
    return out


__all__ = ["degree_label", "explain_span_motif", "explanation_markdown", "mode_name", "pretty", "spell_from_root"]
