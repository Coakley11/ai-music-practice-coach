"""AMI Slice 5 Stage 4b: conversational development of a SINGLE-CHORD exercise.

The Stage 4a architecture, applied to the Stage 2 single-chord exercises (enclosure, chromatic approach, bebop, target the 3rd)
and to the plain chord-tone / guide-tone / pentatonic lines: every follow-up applies to the latest accepted exercise, produces
a new ``GeneratedExercise`` whose ``parent_id`` / ``transform`` (lineage, edits, before/after) point back at it, and is accepted
only when AMI's own checks, read from the pitches and durations, say the exercise is still the same technique on the same
target tone. Parsing, results, edits and lineage are the 4a ones (``exercise_develop``); rhythm uses the existing rhythm
cycler (``cycle_motif_rhythm``). There is no note-generation engine here: an operation is a small, typed edit of the stored motif
(a neighbour note moved to its half-step, an octave shift, a cell dropped) that is refused when it would change what the
exercise is.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from fractions import Fraction
from typing import Any

from music_coach_ami.exercise_develop import (
    KIND_DEVELOP,
    Edit,
    Result,
    _TITLES,
    _clean,
    _refusal,
    edits_summary,
    sha,
)
from music_coach_ami.exercise_model import (
    TECHNIQUE_BEBOP,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_ENCLOSURE,
    TECHNIQUE_TARGET_TONE,
    GeneratedExercise,
)

_FIGURE_ROLES = ("approach", "neighbor")
_CHROMATIC_OPS = ("more_chromatic", "add_approaches", "add_enclosure", "fewer_chromatic")

_UNSUPPORTED_SINGLE = {
    "more_movement": ("Adding movement means adding notes, which would change the figure this exercise is built around. "
                      "\"Make it more chromatic\" or \"make it harder\" add difficulty while keeping the figure."),
    "direction": ("The direction of this pattern is part of how its figure is built (which side it approaches from, which way it "
                  "climbs), so I can't turn it ascending or descending without changing the exercise. I can move it an octave "
                  "(\"play it in a higher register\"), or you can ask for a new pattern in the other direction."),
    "motif_next_chord": ("This exercise sits on one chord. Carrying the motif onto another chord needs a multi-chord exercise: ask "
                         "for \"the next two chords\"."),
}


# ---------------------------------------------------------------- reading the stored exercise


def _motif_of(parent: GeneratedExercise) -> dict[str, Any]:
    from music_coach_ami.exercise_bridge import motif_view

    stored = (parent.explanation_facts or {}).get("motif")
    if isinstance(stored, dict) and stored.get("notes") and len(stored.get("midi") or []) == len(stored["notes"]):
        return copy.deepcopy(stored)
    return copy.deepcopy(motif_view(parent, "concert"))


def _key_ref(parent: GeneratedExercise) -> str:
    return _clean(parent.provenance.get("spelling_reference")) or parent.context.concert_key


def _roles(m: dict[str, Any]) -> list[str]:
    r = list(m.get("pattern_note_roles") or [])
    return r if len(r) == len(m["notes"]) else [""] * len(m["notes"])


def _targets(m: dict[str, Any]) -> list[int]:
    return [i for i, r in enumerate(_roles(m)) if r == "target"]


def _lead(m: dict[str, Any], t: int) -> list[int]:
    roles, out, j = _roles(m), [], t - 1
    while j >= 0 and roles[j] in _FIGURE_ROLES:
        out.insert(0, j)
        j -= 1
    return out


def _figure(m: dict[str, Any]) -> set[int]:
    idx: set[int] = set()
    for t in _targets(m):
        idx.add(t)
        idx.update(_lead(m, t))
    return idx


def _cell_lens(m: dict[str, Any]) -> list[int]:
    cells = [c for c in (m.get("cells") or []) if c]
    lens = [len(c) for c in cells]
    return lens if sum(lens) == len(m["notes"]) and lens else [len(m["notes"])]


def _ctx(parent: GeneratedExercise) -> Any:
    from melodic_pattern_engine import build_context

    return build_context(_key_ref(parent), parent.chord)


def _chord_pcs(parent: GeneratedExercise) -> list[int]:
    from improvisation_motif import _midi_from_note, chord_tone_names

    return [_midi_from_note(n, 4) % 12 for n in (chord_tone_names(parent.chord, reference_key=_key_ref(parent)) or [])]


def _role_of(parent: GeneratedExercise, midi: int) -> str:
    pcs = _chord_pcs(parent)
    return {0: "R", 1: "3", 2: "5", 3: "7"}.get(pcs.index(midi % 12), "") if midi % 12 in pcs else ""


def _non_scale(m: dict[str, Any], ctx: Any) -> list[int]:
    return [k for k, v in enumerate(m["midi"]) if v % 12 not in ctx.scale_pcs]


def _events(m: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in (m.get("rhythm_events") or [])]


def _symbolic(m: dict[str, Any]) -> bool:
    """True when the exercise carries only rhythm symbols (no per-note events): the plain Mission chord-tone / target-tone lines."""
    ev = [e for e in _events(m) if not e.get("rest")]
    return len(ev) != len(m.get("notes") or [])


_NEEDS_EVENTS = ("more_chromatic", "add_approaches", "add_enclosure", "fewer_chromatic", "rhythm_new", "rhythm_syncopate", "rhythm_simpler",
                 "rhythm_interesting", "rhythm_repeat", "stronger_resolution", "motif_repeat", "fewer_notes", "smaller_range", "motif_ending")
_SYMBOLIC_WHY = ("This exercise is a plain note line with a fixed rhythm, so I can't change its rhythm, length or chromatic content and still "
                 "verify the result from note durations. I can move it an octave, vary its notes (\"develop the motif\"), or you can ask for "
                 "a new exercise, for example an enclosure or a bebop line.")


def _onsets(m: dict[str, Any]) -> list[Fraction]:
    return [Fraction(str(e.get("on"))) for e in _events(m) if not e.get("rest")]


def _complexity(m: dict[str, Any], ctx: Any) -> float:
    from span_motif_engine import rhythm_profile

    meter = _clean(m.get("meter")) or "4/4"
    prof = rhythm_profile(m.get("rhythm_events") or [], meter)
    leaps = sum(max(0, abs(b - a) - 4) for a, b in zip(m["midi"], m["midi"][1:]))
    return round(len(m["midi"]) + 6.0 * prof["offbeat"] + 6.0 * prof["syncopation"] + 0.5 * leaps + 1.5 * len(_non_scale(m, ctx)), 2)


# ---------------------------------------------------------------- editing helpers


def _name(midi: int) -> str:
    from music_theory import spell_pitch_class

    return spell_pitch_class(int(midi) % 12, mode="sharp")


def _set(m: dict[str, Any], k: int, midi: int, role: str | None = None) -> None:
    m["midi"][k] = int(midi)
    m["notes"][k] = _name(midi)
    if role is not None:
        roles = _roles(m)
        roles[k] = role
        m["pattern_note_roles"] = roles


def _finalize(parent: GeneratedExercise, m: dict[str, Any]) -> dict[str, Any]:
    """Cells, display and chord-aware spelling follow the edited notes (pitches are never touched by the speller)."""
    from music_coach_ami.exercise_single import _spelled_like_missions

    lens = _cell_lens(m) if m.get("cells") else [len(m["notes"])]
    notes, pos = list(m["notes"]), 0
    cells = []
    for n in lens:
        cells.append(notes[pos:pos + n])
        pos += n
    if m.get("cells"):
        m["cells"] = cells
    m["display"] = " – ".join(m["notes"])
    m["last_transform"] = "ami_develop"
    if not (parent.context.written_transposition_applied and int(parent.context.transposition_semitones or 0)):
        spelled = _spelled_like_missions(m, parent.chord, parent.context.concert_key)
        if spelled is not m:
            m.update({k: spelled[k] for k in ("notes", "display") if k in spelled})
            if m.get("cells"):
                pos, cells = 0, []
                for n in lens:
                    cells.append(list(m["notes"][pos:pos + n]))
                    pos += n
                m["cells"] = cells
    return m


# ---------------------------------------------------------------- the chromatic edits, by technique


def _enclosure_neighbours(m: dict[str, Any], ctx: Any, *, chromatic: bool) -> list[Edit] | None:
    edits: list[Edit] = []
    for t in _targets(m):
        lead = _lead(m, t)
        if len(lead) != 2:
            continue
        tv = m["midi"][t]
        for k in lead:
            above = m["midi"][k] > tv
            if chromatic:
                new = tv + 1 if above else tv - 1
            else:
                two = tv + 2 if above else tv - 2
                one = tv + 1 if above else tv - 1
                new = two if two % 12 in ctx.scale_pcs else one if one % 12 in ctx.scale_pcs else m["midi"][k]
            if new != m["midi"][k]:
                before = m["notes"][k]
                _set(m, k, new)
                edits.append(Edit(k, before, m["notes"][k], "enclosure_neighbour", detail=""))
    return edits or None


def _approach_double(m: dict[str, Any], ctx: Any) -> list[Edit] | None:
    edits: list[Edit] = []
    for t in _targets(m):
        lead = _lead(m, t)
        if len(lead) != 1 or lead[0] - 1 < 0:
            continue
        b = lead[0]
        p = b - 1
        if _roles(m)[p] in ("target",) or m["midi"][t] == m["midi"][p]:
            continue
        side = 1 if m["midi"][b] > m["midi"][t] else -1
        new = m["midi"][t] + 2 * side
        if m["midi"][p] == new:
            continue
        before = m["notes"][p]
        _set(m, p, new, "approach")
        edits.append(Edit(p, before, m["notes"][p], "double_approach"))
    return edits or None


def _approach_single(parent: GeneratedExercise, m: dict[str, Any], ctx: Any) -> list[Edit] | None:
    edits: list[Edit] = []
    roles = _roles(m)
    for t in _targets(m):
        lead = _lead(m, t)
        if len(lead) < 2:
            continue
        p = lead[0]
        old = m["midi"][p]
        pcs = _chord_pcs(parent)
        options = [v for v in range(old - 6, old + 7) if v % 12 in pcs and v != old and v not in (m["midi"][p - 1] if p else -1, m["midi"][p + 1])]
        if not options:
            continue
        new = min(options, key=lambda v: (abs(v - old), v))
        before = m["notes"][p]
        _set(m, p, new, "chord_tone")
        edits.append(Edit(p, before, m["notes"][p], "double_to_single_approach"))
    return edits or None


def _lead_in_to_ct(parent: GeneratedExercise, m: dict[str, Any], ctx: Any, *, add: bool) -> list[Edit] | None:
    """Bebop / target-the-3rd lines: add (or take away) the half-step lead-in to a chord tone that lands on a beat."""
    if add:
        onsets = []
        pos = 0
        for e in _events(m):
            if not e.get("rest"):
                onsets.append(Fraction(str(e.get("on"))))
        pcs = _chord_pcs(parent)
        fig = _figure(m)
        for j in range(1, len(m["midi"])):
            if m["midi"][j] % 12 not in pcs or onsets[j] % 1 != 0 or (j - 1) in fig:
                continue
            p = j - 1
            if m["midi"][p] % 12 in pcs or m["midi"][p] % 12 not in ctx.scale_pcs and abs(m["midi"][p] - m["midi"][j]) == 1:
                continue
            prev = m["midi"][p - 1] if p else m["midi"][p]
            opts = [v for v in (m["midi"][j] - 1, m["midi"][j] + 1) if v % 12 not in pcs and v != prev and abs(v - prev) <= 7]
            if not opts:
                continue
            opts.sort(key=lambda v: (v % 12 in ctx.scale_pcs, abs(v - prev)))
            before = m["notes"][p]
            _set(m, p, opts[0])
            return [Edit(p, before, m["notes"][p], "lead_in")]
        return None
    for k in _non_scale(m, ctx):
        if k in _figure(m):
            continue
        prev = m["midi"][k - 1] if k else m["midi"][k]
        nxt = m["midi"][k + 1] if k + 1 < len(m["midi"]) else m["midi"][k]
        opts = [v for v in range(m["midi"][k] - 2, m["midi"][k] + 3) if v % 12 in ctx.scale_pcs and v not in (prev, nxt, m["midi"][k])]
        if opts:
            before = m["notes"][k]
            _set(m, k, min(opts, key=lambda v: abs(v - m["midi"][k])))
            return [Edit(k, before, m["notes"][k], "chromatic_to_scale")]
    return None


def op_chromatic(parent: GeneratedExercise, op: str) -> Result:
    technique = parent.intent.technique
    ctx = _ctx(parent)
    m = _motif_of(parent)
    edits: list[Edit] | None = None
    why = ""
    if technique == TECHNIQUE_ENCLOSURE:
        if op in ("add_approaches", "add_enclosure"):
            why = "This exercise already is an enclosure of its target, so there is nothing to add; ask for \"more chromatic\" to close the neighbours to half steps."
        elif op == "more_chromatic":
            edits = _enclosure_neighbours(m, ctx, chromatic=True)
            why = "Both notes of the enclosure are already a half step from the target, the most chromatic enclosure there is."
        else:
            edits = _enclosure_neighbours(m, ctx, chromatic=False)
            why = "The enclosure's neighbours are already scale notes, so there is no chromatic note to take out."
    elif technique == TECHNIQUE_CHROMATIC_APPROACH:
        if op == "add_enclosure":
            why = "Adding an enclosure would turn this chromatic approach into a different exercise. Ask for an enclosure exercise instead."
        elif op in ("more_chromatic", "add_approaches"):
            edits = _approach_double(m, ctx)
            why = "This approach already has its second chromatic step, or the note before it can't take one, so I haven't changed it."
        else:
            edits = _approach_single(parent, m, ctx)
            why = "A single half-step approach is the technique itself, so there is no extra chromatic step to take out."
    elif technique in (TECHNIQUE_BEBOP, TECHNIQUE_TARGET_TONE):
        if op in ("more_chromatic", "add_approaches"):
            edits = _lead_in_to_ct(parent, m, ctx, add=True)
            why = "There is no chord tone on a beat that still needs a chromatic lead-in, so I haven't changed it."
        elif op == "add_enclosure":
            why = "This line's resolution is built differently, and an enclosure would change the exercise. Ask for an enclosure exercise instead."
        else:
            edits = _lead_in_to_ct(parent, m, ctx, add=False)
            why = "There's no chromatic note in this line that I can take out without changing what the exercise is."
    else:
        why = ("This is a plain note-collection exercise, so adding chromatic notes would turn it into a different exercise. "
               "Ask for a chromatic approach, an enclosure or a bebop line instead.")
    if not edits:
        return Result(reason=why + (" I haven't changed it." if "haven't changed" not in why else ""))
    _finalize(parent, m)
    return Result(motif=m, edits=[e for e in edits if e.before != e.after], pitches_changed=True,
                  says=[_say_chromatic(parent, m, edits, op)])


def _say_chromatic(parent: GeneratedExercise, m: dict[str, Any], edits: list[Edit], op: str) -> str:
    names = ", ".join(dict.fromkeys(m["notes"][e.index] for e in edits))
    t = _targets(m)
    target = f"{m['notes'][t[0]]}, the {_role_word(_role_of(parent, m['midi'][t[0]]))} of {parent.chord}" if t else parent.chord
    kind = parent.intent.technique
    if op == "fewer_chromatic":
        return f"I replaced chromatic note(s) with scale notes ({names}); the figure into {target} is intact." if t else f"I replaced chromatic note(s) with scale notes ({names})."
    if kind == TECHNIQUE_ENCLOSURE:
        return f"I closed the enclosure to half steps ({names}) around {target}."
    if kind == TECHNIQUE_CHROMATIC_APPROACH:
        return f"I added a second chromatic step ({names}) so the approach now climbs in half steps into {target}."
    return f"I added a chromatic lead-in ({names}) just before a chord tone on the beat."


def _role_word(role: str) -> str:
    return {"R": "root", "3": "3rd", "5": "5th", "7": "7th"}.get(role, "target")


# ---------------------------------------------------------------- rhythm


def op_rhythm(parent: GeneratedExercise, op: str) -> Result:
    from improvisation_motif import cycle_motif_rhythm
    from span_motif_engine import rhythm_profile

    m0 = _motif_of(parent)
    meter = _clean(m0.get("meter")) or parent.meter or "4/4"
    level = parent.context.level or "Intermediate"
    prof0 = rhythm_profile(m0.get("rhythm_events") or [], meter)
    sig0 = [(str(e.get("on")), str(e.get("dur")), bool(e.get("rest"))) for e in _events(m0)]
    end0 = max((Fraction(str(e.get("on"))) + Fraction(str(e.get("dur"))) for e in _events(m0)), default=Fraction(0))
    tg = _targets(m0)
    beat0 = [Fraction(str(_events(m0)[i]["on"])) % 1 == 0 for i in tg if i < len(_events(m0))]
    dur0 = [Fraction(str(_events(m0)[i]["dur"])) for i in tg if i < len(_events(m0))]
    seen, scored, cur = {tuple(sig0)}, [], m0
    for _ in range(40):
        try:
            cur = cycle_motif_rhythm(dict(cur), meter=meter, level=level)
        except Exception:
            break
        ev = [e for e in _events(cur)]
        sig = tuple((str(e.get("on")), str(e.get("dur")), bool(e.get("rest"))) for e in ev)
        if sig in seen:
            break
        seen.add(sig)
        if len(ev) != len(_events(m0)) or max((Fraction(str(e["on"])) + Fraction(str(e["dur"])) for e in ev), default=Fraction(0)) != end0:
            continue
        beat1 = [Fraction(str(ev[i]["on"])) % 1 == 0 for i in tg if i < len(ev)]
        if beat1 != beat0:
            continue                                   # a target that sat on a beat stays on a beat
        prof = rhythm_profile(ev, meter)
        busy, busy0 = prof["offbeat"] + prof["syncopation"] + prof["sixteenths"], prof0["offbeat"] + prof0["syncopation"] + prof0["sixteenths"]
        durs = [Fraction(str(ev[i]["dur"])) for i in tg if i < len(ev)]
        kinds = len({(e.get("dur"), bool(e.get("tup"))) for e in ev if not e.get("rest")})
        kinds0 = len({(e.get("dur"), bool(e.get("tup"))) for e in _events(m0) if not e.get("rest")})
        if op == "rhythm_new":
            scored.append((0.0, cur, prof))
        elif op == "rhythm_syncopate" and prof["syncopation"] > prof0["syncopation"] + 0.04:
            scored.append((-prof["syncopation"], cur, prof))
        elif op == "rhythm_simpler" and busy < busy0 - 0.05:
            scored.append((busy, cur, prof))
        elif op == "rhythm_interesting" and kinds > kinds0:
            scored.append((-kinds, cur, prof))
        elif op == "rhythm_repeat" and _cells_share_rhythm(cur, m0):
            scored.append((0.0, cur, prof))
        elif op == "stronger_resolution" and tg and sum(durs) > sum(dur0) and all(Fraction(str(ev[i]["on"])) % 1 == 0 for i in tg):
            scored.append((-float(sum(durs)), cur, prof))
    scored.sort(key=lambda t: t[0])
    for _s, cand, prof in scored:
        out = copy.deepcopy(m0)
        for k in ("rhythm_events", "rhythm_symbols", "rhythm_meta", "rhythm", "rhythm_key", "cell_rhythm_symbols", "meter"):
            if k in cand:
                out[k] = copy.deepcopy(cand[k])
        out["last_transform"] = "ami_develop"
        return Result(motif=out, rhythm_changed=True, says=[_say_rhythm(op)], extra={"profile_before": prof0, "profile_after": prof})
    why = {
        "rhythm_new": "I couldn't find a different valid rhythm for these notes",
        "rhythm_syncopate": "none of the valid rhythms for these notes has more syncopation than this one",
        "rhythm_simpler": "this is already the simplest valid rhythm for these notes",
        "rhythm_interesting": "none of the valid rhythms for these notes is more varied",
        "rhythm_repeat": "no valid rhythm for these notes repeats one cell more closely than this one",
        "stronger_resolution": "no valid rhythm gives the target note a longer value on a beat",
    }[op]
    return Result(reason=f"I haven't changed it: {why}, and I won't move a target note off its beat just to change the rhythm.")


def _cells_share_rhythm(cand: dict[str, Any], base: dict[str, Any]) -> bool:
    lens = _cell_lens(base)
    ev = [e for e in _events(cand) if not e.get("rest")]
    if len(lens) < 2 or sum(lens) != len(ev):
        return False
    first = [(Fraction(str(e["on"])), str(e["dur"])) for e in ev[:lens[0]]]
    start2 = first[0][0] if first else Fraction(0)
    second = ev[lens[0]:lens[0] + lens[1]]
    off = Fraction(str(second[0]["on"])) - first[0][0] if second else Fraction(0)
    return all(Fraction(str(b["on"])) - off == a[0] and str(b["dur"]) == a[1] for a, b in zip(first, second))


def _say_rhythm(op: str) -> str:
    return {
        "rhythm_syncopate": "I kept the same notes and moved more of them onto off-beats that carry across the beat.",
        "rhythm_simpler": "I kept the same notes and gave them a plainer rhythm, with fewer off-beat entries.",
        "rhythm_interesting": "I kept the same notes and gave them a rhythm that uses more different note lengths.",
        "rhythm_repeat": "I kept the same notes and made the same rhythmic cell return in each repeat.",
        "stronger_resolution": "I kept the same notes and gave the target note a longer value on the beat, so the resolution is stronger.",
    }.get(op, "I kept the same notes and gave them a different rhythm; the target note still lands on its beat.")


# ---------------------------------------------------------------- length, register, motif


def _bounds_ok(parent: GeneratedExercise, midis: list[int]) -> bool:
    from improvisation_motif import _PATTERN_MIDI_HI, _PATTERN_MIDI_LO, _shift_phrase_into_bounds, guitar_midi_is_playable
    from improvisation_missions import _instrument_family

    if _shift_phrase_into_bounds(list(midis)) != list(midis) or min(midis) < _PATTERN_MIDI_LO or max(midis) > _PATTERN_MIDI_HI:
        return False
    if _instrument_family(parent.context.instrument) == "guitar":
        return all(guitar_midi_is_playable(v) for v in midis)
    return True


def op_register(parent: GeneratedExercise, direction: int) -> Result:
    m = _motif_of(parent)
    moved = [v + 12 * direction for v in m["midi"]]
    if not _bounds_ok(parent, moved):
        word = "higher" if direction > 0 else "lower"
        return Result(reason=f"I can't take the whole line an octave {word}: it would leave the range the staff"
                             f"{' and the guitar neck' if True else ''} can show, and I won't bend single notes to fit. I haven't changed it.")
    m["midi"] = moved
    m["display"] = " – ".join(m["notes"])
    m["last_transform"] = "ami_develop"
    word = "higher" if direction > 0 else "lower"
    return Result(motif=m, pitches_changed=True, shift=12 * direction,
                  says=[f"I played the whole line an octave {word}; every note keeps its place in the chord and the rhythm is unchanged."])


def op_smaller_range(parent: GeneratedExercise) -> Result:
    m = _motif_of(parent)
    lens = _cell_lens(m)
    if len(lens) < 2:
        return Result(reason="This line is a single cell with no octave repeat to bring closer, so there is nothing to narrow without changing its contour. I haven't changed it.")
    n1 = lens[0]
    first = m["midi"][:n1]
    new = list(m["midi"])
    pos = 0
    for n in lens:
        seg = m["midi"][pos:pos + n]
        shift = round((first[0] - seg[0]) / 12) * 12 if n == n1 else 0
        if n != n1 or [v + shift for v in seg] != first:
            return Result(reason="The repeat of this line isn't an exact octave copy of the first cell, so I can't fold it down without changing notes. I haven't changed it.")
        new[pos:pos + n] = first
        pos += n
    if max(new) - min(new) >= max(m["midi"]) - min(m["midi"]):
        return Result(reason="The line is already within its smallest range. I haven't changed it.")
    m["midi"] = new
    m["last_transform"] = "ami_develop"
    return Result(motif=m, pitches_changed=True,
                  says=[f"I brought the repeat down into the first cell's octave: the range is now {max(new) - min(new)} semitones instead of {max(parent.midi) - min(parent.midi)}."])


def _retime(m: dict[str, Any], keep: int) -> None:
    m["rhythm_events"] = [dict(e) for e in _events(m)[:keep]]
    m["rhythm_symbols"] = list(m.get("rhythm_symbols") or [])[:keep]


def op_fewer_notes(parent: GeneratedExercise) -> Result:
    m = _motif_of(parent)
    lens = _cell_lens(m)
    if len(lens) < 2 or any(e.get("rest") for e in _events(m)):
        return Result(reason="This line is a single figure; removing notes from it would break the figure, so I haven't changed it. "
                             "\"Make the rhythm simpler\" makes it easier without removing notes.")
    n1 = lens[0]
    for key in ("notes", "midi", "pattern_note_roles"):
        if isinstance(m.get(key), list):
            m[key] = m[key][:n1]
    m["cells"] = [m["cells"][0]] if m.get("cells") else m.get("cells")
    m["pattern_length"] = 1
    _retime(m, n1)
    m["display"] = " – ".join(m["notes"])
    m["last_transform"] = "ami_develop"
    return Result(motif=m, pitches_changed=True, rhythm_changed=True,
                  says=[f"I kept the first statement of the figure and dropped its octave repeat: {len(parent.midi)} notes became {n1}."])


def op_repeat(parent: GeneratedExercise) -> Result:
    from music_coach_ami.exercise_bridge import _bars_of

    m = _motif_of(parent)
    meter = _clean(m.get("meter")) or parent.meter or "4/4"
    bars = _bars_of(m, meter)
    beats = {"3/4": 3, "6/8": 3, "2/4": 2}.get(meter, 4)
    offset = Fraction(bars * beats)
    n = len(m["notes"])
    if n * 2 > 24:
        return Result(reason="Repeating this line would make it longer than the exercises I build, so I haven't changed it.")
    for key in ("notes", "midi", "pattern_note_roles", "rhythm_symbols"):
        if isinstance(m.get(key), list):
            m[key] = m[key] + list(m[key])
    ev2 = []
    for e in _events(m):
        d = dict(e)
        d["on"] = str(Fraction(str(e.get("on"))) + offset)
        if d.get("n") is not None:
            d["n"] = int(e["n"]) + n
        ev2.append(d)
    m["rhythm_events"] = [dict(e) for e in _events(m)] + ev2
    if m.get("cells"):
        m["cells"] = list(m["cells"]) + [list(c) for c in m["cells"]]
        m["pattern_length"] = len(m["cells"])
    m["display"] = " – ".join(m["notes"])
    m["last_transform"] = "ami_develop"
    return Result(motif=m, pitches_changed=True, rhythm_changed=True,
                  says=["I repeated the whole figure exactly (same notes, same rhythm), a second time after it."])


def op_develop(parent: GeneratedExercise, nonce: int) -> Result:
    """A variation that keeps the figure (the lead-in and the target) and the rhythm: the other chord tones become other chord tones."""
    m = _motif_of(parent)
    pcs = _chord_pcs(parent)
    fig = _figure(m)
    changed: list[Edit] = []
    new = list(m["midi"])
    for k in range(len(new)):
        if k in fig or m["midi"][k] % 12 not in pcs:
            continue
        old = m["midi"][k]
        prev = new[k - 1] if k else None
        nxt = m["midi"][k + 1] if k + 1 < len(m["midi"]) else None

        def _smooth(v: int, prev: Any = prev, nxt: Any = nxt) -> bool:   # no repeated pitch class, no big leap next to a neighbour
            return all(n is None or (v % 12 != n % 12 and abs(v - n) <= 9) for n in (prev, nxt))

        opts = sorted((v for v in range(old - 6, old + 7) if v % 12 in pcs and v != old and _smooth(v)), key=lambda v: (abs(v - old), v))
        if not opts:
            continue
        new[k] = opts[(nonce + k) % min(2, len(opts))] if len(opts) > 1 else opts[0]
        changed.append(Edit(k, m["notes"][k], _name(new[k]), "chord_tone_variation"))
    if not changed:
        return Result(reason="Every note of this exercise belongs to its figure, so a variation would change the technique itself. I haven't changed it.")
    for k in range(len(new)):
        if new[k] != m["midi"][k]:
            _set(m, k, new[k], "guide_tone" if _role_of(parent, new[k]) in ("3", "7") else "chord_tone" if _roles(m)[k] else None)
    _finalize(parent, m)
    names = ", ".join(dict.fromkeys(e.after for e in changed))
    return Result(motif=m, edits=changed, pitches_changed=True,
                  says=[f"I varied the line around its figure: the notes outside the lead-in and the target became other chord tones ({names}), "
                        "and the rhythm and the target are unchanged."])


def op_ending(parent: GeneratedExercise) -> Result:
    m = _motif_of(parent)
    fig = _figure(m)
    last = len(m["midi"]) - 1
    pcs = _chord_pcs(parent)
    if last in fig or m["midi"][last] % 12 not in pcs:
        return Result(reason="This exercise ends on its target, so changing the ending would change the exercise. I haven't changed it.")
    old, prev = m["midi"][last], m["midi"][last - 1]
    opts = sorted((v for v in range(prev - 5, prev + 6) if v % 12 in pcs and v != prev and v != old), key=lambda v: (abs(v - prev), v))
    if not opts:
        return Result(reason="I couldn't find a different chord tone to end on. I haven't changed it.")
    before = m["notes"][last]
    _set(m, last, opts[0])
    _finalize(parent, m)
    role = _role_word(_role_of(parent, opts[0]))
    return Result(motif=m, edits=[Edit(last, before, m["notes"][last], "ending")], pitches_changed=True,
                  says=[f"I kept the idea and changed its last note from {before} to {m['notes'][last]}, the {role} of {parent.chord}."])


def op_difficulty(parent: GeneratedExercise, harder: bool) -> Result:
    ctx = _ctx(parent)
    base = _complexity(_motif_of(parent), ctx)
    steps = ("more_chromatic", "rhythm_syncopate") if harder else ("fewer_chromatic", "rhythm_simpler", "fewer_notes")
    for chain in [(s,) for s in steps] + ([(steps[0], steps[1])] if len(steps) >= 2 else []):
        cur_parent, motif, says, edits, pc, rc, ok = parent, None, [], [], False, False, True
        for op in chain:
            r = _apply(cur_parent, op, 0)
            if r.motif is None:
                ok = False
                break
            motif, says, edits = r.motif, says + r.says, edits + r.edits
            pc, rc = pc or r.pitches_changed, rc or r.rhythm_changed
            cur_parent = _clone_with(cur_parent, motif)
        if not ok or motif is None:
            continue
        after = _complexity(motif, ctx)
        if (after >= base + 1.0) if harder else (after <= base - 1.0):
            return Result(motif=motif, edits=edits, says=says, pitches_changed=pc, rhythm_changed=rc,
                          extra={"complexity_before": base, "complexity_after": after, "steps": list(chain)})
    word = "harder" if harder else "easier"
    return Result(reason=f"I can't make this measurably {word} without changing what the exercise is (its figure and its target), "
                         "so I haven't changed it.")


def _clone_with(parent: GeneratedExercise, motif: dict[str, Any]) -> GeneratedExercise:
    c = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
    _apply_motif(c, motif)
    return c


def _apply(parent: GeneratedExercise, op: str, nonce: int) -> Result:
    if op in _NEEDS_EVENTS and _symbolic(_motif_of(parent)):
        return Result(reason=_SYMBOLIC_WHY + " I haven't changed it.")
    if op in _CHROMATIC_OPS:
        return op_chromatic(parent, op)
    if op in ("rhythm_new", "rhythm_syncopate", "rhythm_simpler", "rhythm_interesting", "rhythm_repeat", "stronger_resolution"):
        return op_rhythm(parent, op)
    if op == "motif_develop":
        return op_develop(parent, nonce)
    if op == "motif_ending":
        return op_ending(parent)
    if op == "motif_repeat":
        return op_repeat(parent)
    if op == "fewer_notes":
        return op_fewer_notes(parent)
    if op == "smaller_range":
        return op_smaller_range(parent)
    return Result(reason="I can't do that to this exercise yet.")


# ---------------------------------------------------------------- the exercise from an edited motif


def _apply_motif(ex: GeneratedExercise, m: dict[str, Any]) -> None:
    from music_coach_ami.exercise_bridge import _bars_of
    from music_coach_ami.exercise_single import _roles_for, describe_targets

    ex.notes, ex.midi = [str(n) for n in m["notes"]], [int(v) for v in m["midi"]]
    ex.rhythm_events = [dict(e) for e in (m.get("rhythm_events") or [])]
    ex.rhythm_symbols = [str(s) for s in (m.get("rhythm_symbols") or [])]
    ex.meter = _clean(m.get("meter")) or ex.meter
    ex.bars = _bars_of(m, ex.meter)
    ex.roles, ex.chord_roles = _roles_for(ex.midi, ex.chord, _key_ref(ex))
    ex.chord_assignment = [0] * len(ex.notes)
    ex.articulation, ex.dynamics = [""] * len(ex.notes), [""] * len(ex.notes)
    ex.accents, ex.slur_groups = [False] * len(ex.notes), [0] * len(ex.notes)
    ex.written = {"applied": False, "key": ex.context.concert_key, "chord": ex.chord, "notes": list(ex.notes), "midi": list(ex.midi),
                  "semitones": 0, "octave_shift": 0}
    facts = dict(ex.explanation_facts)
    facts["motif"] = m
    facts["targets"] = _describe(m, ex)
    ex.explanation_facts = facts


def _describe(m: dict[str, Any], ex: GeneratedExercise) -> list[dict[str, Any]]:
    out = []
    lens = _cell_lens(m)
    starts = [sum(lens[:i]) for i in range(len(lens))]
    for t in _targets(m):
        lead = _lead(m, t)
        ci = max(i for i, s in enumerate(starts) if s <= t)
        tv = m["midi"][t]
        out.append({
            "cell": ci, "target": m["notes"][t], "role": _role_of(ex, tv),
            "lead": [{"note": m["notes"][k], "side": "above" if m["midi"][k] > tv else "below",
                      "gap": {1: "half step", 2: "whole step"}.get(abs(m["midi"][k] - tv), f"{abs(m['midi'][k] - tv)} semitones")}
                     for k in lead],
        })
    return out


# ---------------------------------------------------------------- AMI's own checks, from pitches and durations


def single_development_checks(parent: GeneratedExercise, new: GeneratedExercise, res: Result) -> list[dict[str, Any]]:
    from music_coach_ami.exercise_single import _playable_check

    technique = parent.intent.technique
    pm, nm = _motif_of(parent), new.explanation_facts["motif"]
    ctx = _ctx(new)
    checks: list[dict[str, Any]] = []
    checks.append({"name": "same_chord_and_key", "ok": new.chord == parent.chord and new.context.concert_key == parent.context.concert_key,
                   "detail": f"{new.chord} in {new.context.concert_key}"})
    pt, nt = _targets(pm), _targets(nm)
    shift = res.shift
    fewer = len(nt) != len(pt)
    t_ok = bool(nt) if technique in (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH) else True
    if pt and nt and not fewer:
        t_ok = all(nm["midi"][b] == pm["midi"][a] + shift for a, b in zip(pt, nt))
    elif pt and nt and res.pitches_changed and res.rhythm_changed:   # length changes keep the first target
        t_ok = nm["midi"][nt[0]] == pm["midi"][pt[0]] + shift
    checks.append({"name": "target_tone_preserved", "ok": t_ok, "detail": "the target note is the same pitch" + (" an octave away" if shift else "")})
    if technique == TECHNIQUE_ENCLOSURE:
        ok = bool(nt)
        for t in nt:
            lead = _lead(nm, t)
            vals = [nm["midi"][k] for k in lead]
            ok = ok and len(vals) == 2 and any(v > nm["midi"][t] for v in vals) and any(v < nm["midi"][t] for v in vals) \
                and all(0 < abs(v - nm["midi"][t]) <= 3 for v in vals)
        checks.append({"name": "enclosure_geometry_holds", "ok": ok, "detail": "every target is surrounded from above and below within a minor third"})
    elif technique == TECHNIQUE_CHROMATIC_APPROACH:
        ok = bool(nt)
        for t in nt:
            lead = _lead(nm, t)
            ok = ok and bool(lead) and abs(nm["midi"][t - 1] - nm["midi"][t]) == 1 and nm["midi"][t - 1] % 12 not in _chord_pcs(new)
            if len(lead) == 2:      # a double approach keeps climbing in half steps from the same side
                ok = ok and abs(nm["midi"][lead[0]] - nm["midi"][t]) == 2 and (nm["midi"][lead[0]] - nm["midi"][t]) * (nm["midi"][lead[1]] - nm["midi"][t]) > 0
        checks.append({"name": "approach_resolves_by_semitone", "ok": ok, "detail": "the note before every target is a non-chord tone a semitone away"})
    elif technique == TECHNIQUE_BEBOP:
        cts = sum(1 for v in nm["midi"] if v % 12 in _chord_pcs(new))
        checks.append({"name": "bebop_chord_tone_grounding", "ok": cts >= 2, "detail": f"{cts} chord tones"})
    elif technique == TECHNIQUE_TARGET_TONE:
        checks.append({"name": "ends_on_the_3rd", "ok": _role_of(new, nm["midi"][-1]) == "3", "detail": "the line still ends on the 3rd"})
    def _stray(mm: dict[str, Any]) -> set[tuple[int, int]]:
        return {(k, mm["midi"][k] % 12) for k in _non_scale(mm, ctx) if not (k + 1 < len(mm["midi"]) and 1 <= abs(mm["midi"][k + 1] - mm["midi"][k]) <= 2)}

    # a chromatic note the exercise already had (its figure) is not re-judged; every NEW chromatic note must move by step into the next
    fresh = _stray(nm) - _stray(pm) if len(nm["midi"]) == len(pm["midi"]) else _stray(nm)
    checks.append({"name": "chromatic_notes_resolve", "ok": not fresh, "detail": "every chromatic note this change adds moves by a step into the next note"})
    ev = [e for e in _events(nm) if not e.get("rest")]
    if _symbolic(nm):
        syms = list(nm.get("rhythm_symbols") or [])
        checks.append({"name": "durations_valid", "ok": len(syms) == len(nm["midi"]) and new.bars >= 1,
                       "detail": f"{len(syms)} written durations for {len(nm['midi'])} notes, {new.bars} bar(s)"})
    else:
        contiguous = all(Fraction(str(a["on"])) + Fraction(str(a["dur"])) <= Fraction(str(b["on"])) for a, b in zip(ev, ev[1:]))
        checks.append({"name": "durations_valid", "ok": len(ev) == len(nm["midi"]) and contiguous and new.bars >= 1,
                       "detail": f"{len(ev)} notes, no overlaps, {new.bars} bar(s)"})
    if not res.pitches_changed:
        checks.append({"name": "pitches_identical", "ok": nm["midi"] == pm["midi"], "detail": "same notes in the same order"})
    class _R:  # the pattern-engine playable check wants an object with .midi
        midi = nm["midi"]
    checks.append({"name": "playable_on_instrument", "ok": _playable_check(_R, new.context.instrument) and 40 <= min(nm["midi"]) and max(nm["midi"]) <= 96,
                   "detail": "every note is within the instrument's range"})
    return checks


# ---------------------------------------------------------------- orchestration


def _live_single(session_ref: Any, parent: GeneratedExercise, ctx: Any) -> str:
    """'' when the stored exercise still belongs to the live app, else the reason it does not."""
    from improvisation_intelligence_ui import _mission_improv_ctx_from_session
    from music_coach_ami.exercise_span import _session
    from music_theory import semitone_distance

    if ctx.written_transposition_applied and int(ctx.transposition_semitones or 0):
        return (f"{ctx.notation_instrument or ctx.instrument} reads a transposed written key, and developing a single-chord exercise "
                "is only available in concert pitch for now, so I won't show you wrong written notes. Ask for a new exercise instead.")
    probe = dict(_session(session_ref))
    probe["improv_intelligence_tab"] = "Missions"
    probe["creative_improv_intelligence_tab"] = "Missions"
    try:
        improv = _mission_improv_ctx_from_session(probe)
    except Exception:
        improv = None
    song = _clean(parent.context.song_title)
    if improv is not None:
        if song and _clean(getattr(improv, "song_title", "")) and _clean(improv.song_title) != song:
            return "The song has changed since that exercise was made, so I can't build on it. Ask for a new exercise on the current song."
        live_key = _clean(getattr(improv, "key_center", ""))
        if live_key and semitone_distance(live_key, parent.context.concert_key) not in (0, None):
            return (f"Your Practice Key is now {live_key}, but that exercise is in {parent.context.concert_key}. I won't transpose it "
                    "silently: ask for a new one in the current key, or change the Practice Key back.")
    elif song:
        return "The song's chords aren't available any more, so I can't build on that exercise. Ask for a new one."
    return ""


def _op_for_single(fu: Any) -> tuple[str, int, str]:
    from music_coach_ami import exercise_develop as D

    return D._op_for(fu)


def compose_single_followup(
    fu: Any, parent: GeneratedExercise, *, session_ref: Any, instrument: str, notation_instrument: str, display_instrument: str, bpm: int,
) -> dict[str, Any]:
    from improvisation_motif import build_motif_guitar_tab

    from music_coach_ami.exercise_bridge import exercise_prose, motif_view, render_abc, store_last_exercise
    from music_coach_ami.exercise_followup import _next_nonce, _rebound_context
    from music_coach_ami.exercise_single import ACTION_KIND, single_plan, single_prose
    from music_coach_ami.exercise_span import _guitar_family

    op, direction, refusal = _op_for_single(fu)
    if refusal:
        return _refusal(parent, fu, refusal.replace("a multi-chord exercise", "this exercise"))
    if op in _UNSUPPORTED_SINGLE:
        return _refusal(parent, fu, _UNSUPPORTED_SINGLE[op])
    live = {"session_ref": session_ref, "instrument": instrument, "notation_inst": notation_instrument}
    try:
        ctx = _rebound_context(parent.context, live)
        why = _live_single(session_ref, parent, ctx)
        if why:
            return _refusal(parent, fu, why)
        lineage_prev = dict(parent.transform.get("lineage") or {})
        root_ex = copy.deepcopy(lineage_prev.get("root_exercise") or parent.to_dict())
        nonce = _next_nonce(parent)
        if op == "original":
            if not lineage_prev.get("root_exercise"):
                return _refusal(parent, fu, "This is already the original exercise, so there is nothing to go back to.")
            result = Result(motif=copy.deepcopy(root_ex["explanation_facts"].get("motif") or {}), pitches_changed=True, rhythm_changed=True,
                            says=["I restored the first version of this exercise, exactly as it was generated."])
            if not result.motif.get("notes"):
                result = Result(reason="The first version of this exercise can't be rebuilt from what I stored.")
        elif op == "register_shift":
            result = op_register(parent, direction or 1)
        elif op == "easier" or op == "harder":
            result = op_difficulty(parent, op == "harder")
        else:
            result = _apply(parent, op, nonce)
        if result.motif is None:
            return _refusal(parent, fu, result.reason)
        ex = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
        ex.context = ctx
        _apply_motif(ex, result.motif)
        if op == "original":
            ex = GeneratedExercise.from_dict(copy.deepcopy(root_ex))
            ex.context = ctx
        checks = [] if op == "original" else single_development_checks(parent, ex, result)
        bad = [c for c in checks if not c["ok"]]
        if bad:
            return _refusal(parent, fu, "That change didn't pass my checks (" + "; ".join(f"{c['name']}: {c['detail']}" for c in bad)
                            + "), so I haven't changed the exercise.")
        if checks:
            ex.validation = {"ok": True, "checks": list(parent.validation.get("checks") or []) + checks}
        kept = ["chord", "key", "technique", "target tone"] + ([] if result.pitches_changed else ["notes"]) + ([] if result.rhythm_changed else ["rhythm"])
        changed = (["notes"] if result.pitches_changed else []) + (["rhythm"] if result.rhythm_changed else [])
        root_id = _clean(lineage_prev.get("root_id")) or parent.id
        ex.parent_id = parent.id
        ex.id = "ex-" + sha({"m": ex.midi, "p": parent.id, "op": op, "n": nonce, "r": [(str(e.get("on")), str(e.get("dur"))) for e in ex.rhythm_events]})
        steps = list(lineage_prev.get("steps") or []) + [{"id": ex.id, "parent": parent.id, "op": op, "utterance": fu.raw}]
        ex.transform = {
            "kind": KIND_DEVELOP, "op": op, "utterance": fu.raw, "parent": parent.id, "root": root_id, "nonce": nonce, "seed": int(ex.seed),
            "inherited": kept, "changed": changed, "overridden": [], "context_mode": "stored_context",
            "edits": edits_summary(result), "says": list(result.says), "details": {k: v for k, v in result.extra.items() if k != "identity"},
            "before": {"notes": list(parent.notes), "midi": list(parent.midi), "rhythm_sha1": sha([(str(e.get("on")), str(e.get("dur"))) for e in parent.rhythm_events])},
            "after": {"notes": list(ex.notes), "midi": list(ex.midi), "rhythm_sha1": sha([(str(e.get("on")), str(e.get("dur"))) for e in ex.rhythm_events])},
            "parent_fingerprints": {"notes_sha1": sha({"midi": parent.midi})}, "preserved": {"notes_sha1": sha({"midi": ex.midi})},
            "lineage": {"root_id": root_id, "root_exercise": root_ex, "steps": steps}, "direction": direction, "degrees": 0,
        }
        ex.provenance.update({"parent": parent.id, "transform": KIND_DEVELOP, "development_op": op, "root": root_id,
                              "inherited": kept, "changed": changed, "nonce": nonce})
        ex.intent = replace(ex.intent, variation_index=nonce, transform=KIND_DEVELOP)
        technique = parent.intent.technique
        guitar = _guitar_family(ctx.instrument or display_instrument)
        tab = build_motif_guitar_tab(motif_view(ex)) if guitar else ""
        if technique:
            plan = single_plan(parent.intent)
            prose = single_prose(ex, plan, display_instrument=display_instrument, tab=tab)
            title = plan.title
        else:
            prose = exercise_prose(ex, display_instrument=display_instrument)
            plan, title = None, prose.get("title", parent.collection_label)
        abc = render_abc(ex, bpm=int(bpm or 96), title=f"{title} — {ex.chord}", instrument=ctx.notation_instrument or ctx.instrument)
        stored = store_last_exercise(session_ref, ex)
    except Exception as exc:  # a follow-up must never silently turn into a different operation
        return _refusal(parent, fu, f"That follow-up hit an unexpected problem ({type(exc).__name__}: {exc}), so I haven't changed the exercise.")
    action = None
    if plan is not None:
        action = {
            "kind": ACTION_KIND, "exercise_id": ex.id, "label": "Open in Missions", "mission_id": plan.mission_id, "chord": ex.chord,
            "section": ctx.section, "concert_key": ctx.concert_key, "technique": plan.technique, "motif": ex.explanation_facts["motif"],
            "level": ctx.level, "instrument": ctx.instrument, "bpm": int(bpm or ctx.tempo_bpm or 96),
            "variant": ex.explanation_facts.get("variant") or "normal",
        }
    lines = [f"**{_TITLES.get(op, op)}** — built from your previous exercise.", *result.says]
    if "complexity_before" in result.extra:
        lines.append(f"_Difficulty score {result.extra['complexity_before']} → {result.extra['complexity_after']}._")
    lines.append(f"Kept: {', '.join(kept) or '—'} · Changed: {', '.join(changed) or '—'}")
    diag = {
        "musical_idea_content": True, "exercise_followup": True, "followup_kind": KIND_DEVELOP, "followup_utterance": fu.raw,
        "parent_exercise_id": parent.id, "exercise_bridge": True, "exercise_single_request": True, "generated_exercise_id": ex.id,
        "generated_exercise": ex.to_dict(), "exercise_context": ex.context.to_dict(), "exercise_validation": ex.validation,
        "notation_abc_present": bool(abc), "guitar_tab_present": bool(tab), "last_exercise_stored": stored, "transform": ex.transform,
        "practice_concert_key": ex.context.concert_key, "written_key": ex.context.written_key, "resolved_instrument": ex.context.instrument,
        "notation_instrument": ex.context.notation_instrument, "bars_generated": ex.bars,
    }
    if action:
        diag["open_in_missions"] = action
    return {
        "direct_answer": "\n\n".join(lines) + "\n\n" + prose["direct_answer"],
        "practice_steps": prose["practice_steps"], "what_to_listen_for": prose.get("what_to_listen_for") or [],
        "suggested_next_action": "Keep developing it: more or less chromatic, a new rhythm, easier or harder, or open it in Missions.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [], "diagnostics": diag,
    }
