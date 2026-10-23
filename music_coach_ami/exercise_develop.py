"""AMI Slice 5 Stage 4a: conversational development of a multi-chord exercise.

"Make it more chromatic", "keep the notes but change the rhythm", "develop the motif", "make it easier", "play it in a lower
register" - each is applied to the LATEST accepted multi-chord exercise (the AMI-owned last-exercise store), never to a fresh
one, and produces a new ``GeneratedExercise`` whose ``parent_id`` / ``transform`` record exactly what was asked, what changed
and what was kept.

There is no note-generation engine here. Every operation either calls an existing one -
``cycle_span_rhythm`` / ``motivic_candidates`` (a new rhythm for the same notes), ``develop_span_motif`` (the Build
development of a motif) - or makes a small, typed edit of the stored motif (replace a note by its half-step neighbour,
shift the line an octave) and then lets the Mission's own validator, plus AMI's independent checks read from the pitches,
decide whether the result is still an honest example. An edit that cannot keep its invariants is refused with the reason;
the previous exercise is left exactly as it was.

The exercise-development context is the stored exercise itself: ``explanation_facts`` holds its Mission example (notes,
rhythm, chord assignment, handoff), ``transform`` holds the parent link, the request, the structured edits and the lineage
(root example and every step), so a parent can always be rebuilt from structured data, not from prose.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

KIND_DEVELOP = "develop"

# ---------------------------------------------------------------- the follow-up grammar
_PRE = r"(?:(?:please|now|then|ok|okay|and|so)\s+)*(?:(?:can|could) you\s+)?"
_IT = r"(?:it|(?:the|this|that)(?: (?:pattern|line|phrase|exercise|motif|idea))?)"

_OPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("original", (r"(?:go back to|return to|restore|use) the original(?: (?:version|exercise|line|one))?", r"undo (?:all|everything)")),
    ("add_approaches", (r"add (?:some |more )?chromatic approach(?:es| notes)?(?: to (?:it|each chord|the changes))?", r"add (?:some )?approach notes")),
    ("add_enclosure", (r"add an? enclosure(?: (?:before|into|to) the (?:resolution|ending|last chord|last change))?",
                       r"(?:use|put) an? enclosure before the resolution")),
    ("stronger_resolution", (r"make the resolution (?:stronger|clearer|more convincing)", r"strengthen the resolution")),
    ("fewer_chromatic", (r"use fewer chromatic notes", rf"(?:make {_IT} )?less chromatic", r"simplify the chromatic(?:ism)?",
                         r"remove (?:the |some )?chromatic(?: notes| approaches)?", r"take out the chromatic notes")),
    ("more_chromatic", (rf"(?:make|keep) {_IT} (?:a (?:bit|little) |slightly |much )?more chromatic",
                        r"(?:use|add|give me) (?:some |a little )?more chromatic(?:ism| notes| movement)?", r"add (?:some )?chromatic(?:ism| notes)?")),
    ("rhythm_syncopate", (r"use more syncopation", r"add (?:some )?syncopation", rf"make {_IT} more syncopated", r"make the rhythm more syncopated")),
    ("rhythm_simpler", (r"make the rhythm (?:simpler|easier|less busy)", r"simplify the rhythm", r"use a simpler rhythm")),
    ("rhythm_interesting", (r"make the rhythm (?:more interesting|more varied|more complex)", r"give it a more interesting rhythm")),
    ("rhythm_repeat", (r"repeat the same rhythm (?:across|over|through|on|in) (?:all |the |each |every )?chords?",
                       r"use the same rhythm (?:on|for|across|in|over) (?:all |the |each |every )?chords?")),
    ("motif_develop", (rf"develop {_IT}", r"develop the motif", r"repeat (?:the|this) motif and develop it",
                       rf"(?:create|give me|make|write) a variation (?:of|on) {_IT}", r"vary (?:the|this|that) (?:motif|phrase|idea)")),
    ("motif_ending", (r"repeat the idea but change the ending", r"change the ending", rf"keep {_IT} but change the ending")),
    ("motif_next_chord", (r"use the same motif over the next chord", r"play the same motif over the next chord")),
    ("motif_repeat", (r"repeat (?:the|this|that) (?:motif|idea|phrase)", r"restate (?:the|this|that) (?:motif|idea|phrase)")),
    ("fewer_notes", (r"use fewer notes", r"play fewer notes")),
    ("more_movement", (r"add more movement", r"use more movement", rf"make {_IT} more active")),
    ("register_shift", (rf"(?:play|put) {_IT} in (?:a |the )?(?P<d>higher|lower) (?:register|octave)",
                        rf"(?:raise|lower) {_IT} (?:an )?octave", r"(?:go|play) (?:an )?octave (?P<d2>higher|lower|up|down)")),
    ("direction", (rf"make {_IT} (?P<dir>ascend|descend)", r"make the (?:phrase|line|pattern) (?P<dir2>ascending|descending)")),
    ("smaller_range", (r"keep (?:it|the (?:pattern|line|phrase)) within a smaller range", rf"(?:narrow|shrink) the range")),
)
_COMPILED = [(op, [re.compile(_PRE + p + r"\Z") for p in pats]) for op, pats in _OPS]


def parse_development(low: str) -> dict[str, Any] | None:
    """The development request in ``low`` (already lower-cased, without final punctuation), or None.

    The whole utterance must be the request; anything left over means it is not one of these follow-ups.
    """
    for op, rxs in _COMPILED:
        for rx in rxs:
            m = rx.match(low)
            if not m:
                continue
            gd = m.groupdict()
            word = next((v for v in (gd.get("d"), gd.get("d2")) if v), "")
            if not word and op == "register_shift":
                word = "lower" if re.match(_PRE + r"lower", low) else "higher"
            dirword = next((v for v in (gd.get("dir"), gd.get("dir2")) if v), "")
            return {"op": op, "direction": {"higher": 1, "up": 1, "lower": -1, "down": -1}.get(word, 0),
                    "contour": "ascend" if dirword.startswith("asc") else "descend" if dirword.startswith("desc") else ""}
    return None


def _clean(value: object) -> str:
    return str(value or "").strip()


def sha(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- reading a stored span exercise


@dataclass
class _Live:
    """What the stored exercise needs from the live app, resolved once per follow-up."""

    res: Any = None
    reason: str = ""
    ctx: Any = None
    span: Any = None


def _example_of(parent: Any) -> dict[str, Any] | None:
    ex = (parent.explanation_facts or {}).get("mission_example")
    return ex if isinstance(ex, dict) and isinstance(ex.get("motif"), dict) else None


def _plan_of(parent: Any) -> Any:
    from music_coach_ami.exercise_model import PatternPlan

    raw = dict((parent.explanation_facts or {}).get("pattern_plan") or {})
    names = {"vocabulary", "mission_id", "title", "technique", "action_kind", "listen_for", "limitation", "constraints", "target_roles"}
    data = {k: v for k, v in raw.items() if k in names}
    data["listen_for"] = tuple(data.get("listen_for") or ())
    data["target_roles"] = tuple(data.get("target_roles") or ())
    data.setdefault("vocabulary", parent.vocabulary)
    data.setdefault("mission_id", _clean((_example_of(parent) or {}).get("mission_id")))
    data.setdefault("title", parent.collection_label)
    return PatternPlan(**data)


# the live-key comparison uses the project's own helper; imported lazily to keep this module import-light
def _same_key(a: str, b: str) -> bool:
    from music_theory import semitone_distance

    return semitone_distance(a, b) in (0, None)


def resolve_live(session_ref: Any, parent: Any, ctx: Any) -> _Live:
    from improvisation_intelligence_ui import _mission_improv_ctx_from_session, resolve_span_options
    from improvisation_motif import resolve_improv_section_rows
    from music_coach_ami.exercise_span import SpanResolution, _session, _transposed_notation_reason

    info = dict((parent.explanation_facts or {}).get("span") or {})
    if not info.get("span_id"):
        return _Live(reason="I can't tell which chords that exercise was built over, so I haven't changed it.")
    reason = _transposed_notation_reason(ctx, None)
    if reason:
        return _Live(reason=f"I can't change that multi-chord exercise for this instrument yet: {reason}.")
    probe = dict(_session(session_ref))
    probe["improv_intelligence_tab"] = "Missions"
    probe["creative_improv_intelligence_tab"] = "Missions"
    try:
        improv_ctx = _mission_improv_ctx_from_session(probe)
        rows = resolve_improv_section_rows(probe, improv_ctx) if improv_ctx is not None else []
    except Exception:
        improv_ctx, rows = None, []
    if not rows:
        return _Live(reason="The song's chords aren't available any more, so I can't build on that exercise. Ask for a new one.")
    scope = _clean(info.get("scope")) or "span2"
    opts = resolve_span_options(probe, improv_ctx, rows, scope=scope, level=_clean(probe.get("level")) or "Intermediate")
    if opts is None or opts.progression_key != info.get("progression_key"):
        return _Live(reason="The song or its chords have changed since that exercise was made, so I can't build on it. "
                            "Ask for a new exercise on the current song.")
    if not _same_key(opts.concert_key, _clean(info.get("concert_key")) or parent.context.concert_key):
        return _Live(reason=f"Your Practice Key is now {opts.concert_key}, but that exercise is in {info.get('concert_key') or parent.context.concert_key}. "
                            "I won't transpose a multi-chord exercise silently: ask for a new one in the current key, or change the "
                            "Practice Key back.")
    span = next((s for s in opts.ordered if s.span_id == info.get("span_id")), None)
    if span is None:
        return _Live(reason="That stretch of the song isn't available on the current section, so I can't build on that exercise. "
                            "Ask for a new one.")
    res = SpanResolution(span=span, options=opts, info=info, project=opts.project, improv_ctx=improv_ctx, probe=probe)
    return _Live(res=res, ctx=ctx, span=span)


# ---------------------------------------------------------------- motif readers (all from pitches)


def _contexts(span: Any, motif: dict[str, Any]) -> list[Any]:
    from span_motif_engine import _ctx

    return [_ctx(span.key_center, t["chord"]) for t in motif["chord_timeline"]]


def _firsts(motif: dict[str, Any]) -> list[int]:
    return [int(t["first_note"]) for t in motif["chord_timeline"]]


def _chord_role(chord: str, key: str, midi: int) -> str:
    from improvisation_motif import _midi_from_note, chord_tone_names

    pcs = [_midi_from_note(n, 4) % 12 for n in (chord_tone_names(chord, reference_key=key) or [])]
    word = {0: "root", 1: "3rd", 2: "5th", 3: "7th"}
    return word.get(pcs.index(midi % 12), "") if midi % 12 in pcs else ""


def _rung(motif: dict[str, Any], ctxs: list[Any], i: int) -> str:
    """How chord ``i`` is led into: 'enclosure' | 'approach' | 'plain' (read from the pitches of the previous chord's bars)."""
    midi, firsts = motif["midi"], _firsts(motif)
    j = firsts[i]
    t = midi[j]
    if j - 2 >= firsts[i - 1]:
        a, b = midi[j - 2] - t, midi[j - 1] - t
        if a * b < 0 and 1 <= abs(a) <= 2 and 1 <= abs(b) <= 2 and 1 in (abs(a), abs(b)):
            return "enclosure"
    if j - 1 >= firsts[i - 1] and abs(midi[j - 1] - t) == 1 and midi[j - 1] % 12 not in ctxs[i].chord_pcs:
        return "approach"
    return "plain"


def _non_scale(motif: dict[str, Any], ctxs: list[Any]) -> list[int]:
    return [k for k, m in enumerate(motif["midi"]) if m % 12 not in ctxs[motif["note_chord_index"][k]].scale_pcs]


def _resolves(motif: dict[str, Any], k: int) -> bool:
    """A chromatic note must lead somewhere: the next note is within a step of it (a half step for an approach)."""
    midi = motif["midi"]
    return k + 1 < len(midi) and 1 <= abs(midi[k + 1] - midi[k]) <= 2


def _put(motif: dict[str, Any], k: int, midi: int, ctxs: list[Any], kind: str, below: bool | None = None) -> None:
    from span_motif_engine import _note

    ci = motif["note_chord_index"][k]
    n = _note(ctxs[ci], int(midi), ci, kind, below_target=below)
    motif["midi"][k], motif["notes"][k] = int(midi), n.name
    if isinstance(motif.get("pattern_note_roles"), list) and k < len(motif["pattern_note_roles"]):
        motif["pattern_note_roles"][k] = n.role
    if isinstance(motif.get("note_kinds"), list) and k < len(motif["note_kinds"]):
        motif["note_kinds"][k] = kind


def _refresh(motif: dict[str, Any], span: Any) -> dict[str, Any]:
    from improvisation_motif import sync_motif_midi
    from span_motif_engine import musicality

    ctxs = _contexts(span, motif)
    motif["display"] = " – ".join(motif["notes"])
    try:
        motif["musicality"] = musicality(motif["midi"], motif["note_chord_index"], ctxs, level=_clean(motif.get("level")) or "Intermediate")
    except Exception:
        pass
    motif["last_transform"] = "ami_develop"
    return sync_motif_midi(motif)


# ---------------------------------------------------------------- complexity (what easier / harder measure)


def complexity(motif: dict[str, Any], ctxs: list[Any]) -> float:
    """Notes, off-beat / syncopated entries and chromatic notes: a small explainable score."""
    from melodic_rhythm_engine import events_from_json
    from span_motif_engine import rhythm_profile

    midi = motif["midi"]
    meter = _clean(motif.get("meter")) or "4/4"
    prof = rhythm_profile(motif.get("rhythm_events") or [], meter)
    n = len(midi)
    leaps = sum(max(0, abs(b - a) - 4) for a, b in zip(midi, midi[1:]))
    return round(n + 6.0 * prof["offbeat"] + 6.0 * prof["syncopation"] + 0.5 * leaps + 1.5 * len(_non_scale(motif, ctxs)), 2)


# ---------------------------------------------------------------- the edits


@dataclass
class Edit:
    index: int
    before: str
    after: str
    why: str
    chord: str = ""
    detail: str = ""


def _near(options: list[int], ref: int, avoid: tuple[int, ...]) -> list[int]:
    return sorted((m for m in options if m not in avoid), key=lambda m: (abs(m - ref), m))


def _make_approach(motif: dict[str, Any], span: Any, ctxs: list[Any], i: int, key: str) -> list[Edit] | None:
    j, firsts = _firsts(motif)[i], _firsts(motif)
    k = j - 1
    if k <= firsts[i - 1]:
        return None
    t, prev = motif["midi"][j], motif["midi"][k - 1]
    options = [m for m in (t - 1, t + 1) if m % 12 not in ctxs[i].chord_pcs and m != prev and abs(m - prev) <= 7]
    if not options:
        return None
    new = min(options, key=lambda m: (abs(m - prev), m))
    before = motif["notes"][k]
    _put(motif, k, new, ctxs, "connector", below=True if t - new == 1 else None)
    return [Edit(k, before, motif["notes"][k], "approach", motif["chord_timeline"][i]["chord"],
                 f"{motif['notes'][k]} leans a half step into {motif['notes'][j]}, the {_chord_role(motif['chord_timeline'][i]['chord'], key, t) or 'target'} of {motif['chord_timeline'][i]['chord']}")]


def _make_enclosure(motif: dict[str, Any], span: Any, ctxs: list[Any], i: int, key: str) -> list[Edit] | None:
    j, firsts = _firsts(motif)[i], _firsts(motif)
    k2, k1 = j - 2, j - 1
    if k2 <= firsts[i - 1]:
        return None
    t, prev = motif["midi"][j], motif["midi"][k2 - 1]
    upper = [t + d for d in (1, 2) if d == 1 or (t + d) % 12 in ctxs[i].scale_pcs]
    lower = [t - d for d in (1, 2) if d == 1 or (t - d) % 12 in ctxs[i].scale_pcs]
    pairs = []
    for u in upper:
        for lo in lower:
            if 1 not in (u - t, t - lo):
                continue
            for first, second in ((u, lo), (lo, u)):
                if first != prev and abs(first - prev) <= 7:
                    pairs.append((abs(first - prev) + abs(second - first), first, second))
    if not pairs:
        return None
    _c, first, second = min(pairs)
    b1, b2 = motif["notes"][k2], motif["notes"][k1]
    _put(motif, k2, first, ctxs, "connector", below=True if t - first == 1 else None)
    _put(motif, k1, second, ctxs, "connector", below=True if t - second == 1 else None)
    chord = motif["chord_timeline"][i]["chord"]
    return [Edit(k2, b1, motif["notes"][k2], "enclosure", chord), Edit(k1, b2, motif["notes"][k1], "enclosure", chord,
            f"{motif['notes'][k2]} and {motif['notes'][k1]} surround {motif['notes'][j]}, the {_chord_role(chord, key, t) or 'target'} of {chord}")]


def _diatonic_for(motif: dict[str, Any], ctxs: list[Any], k: int, ref: int, avoid: tuple[int, ...]) -> int | None:
    ci = motif["note_chord_index"][k]
    scale = ctxs[ci].scale_pcs
    cands = _near([m for m in range(ref - 4, ref + 5) if m % 12 in scale], motif["midi"][k], avoid)
    return cands[0] if cands else None


def _reduce(motif: dict[str, Any], span: Any, ctxs: list[Any], i: int, key: str) -> list[Edit] | None:
    """Fewer chromatic notes at chord ``i``: each outside-the-scale note that leads into the change becomes the nearest
    scale note (the lead-in keeps its shape: an enclosure stays an enclosure, an approach becomes a scale step)."""
    j, firsts, midi = _firsts(motif)[i], _firsts(motif), motif["midi"]
    t = midi[j]
    chord = motif["chord_timeline"][i]["chord"]
    edits: list[Edit] = []
    for k in (j - 2, j - 1):
        if k <= firsts[i - 1] or midi[k] % 12 in ctxs[i - 1].scale_pcs:
            continue
        nxt = midi[k + 1] if k + 1 < len(midi) else t
        new = _diatonic_for(motif, ctxs, k, midi[k], (t, midi[k - 1], nxt, midi[k]))
        if new is None or abs(new - midi[k]) > 2 or abs(new - t) > 3:
            continue
        before = motif["notes"][k]
        _put(motif, k, new, ctxs, "cell")
        edits.append(Edit(k, before, motif["notes"][k], "chromatic_to_scale", chord,
                          f"{before} became the scale note {motif['notes'][k]} before {motif['notes'][j]}"))
    return edits or None


def _other_chromatic(motif: dict[str, Any], span: Any, ctxs: list[Any], key: str) -> list[Edit] | None:
    """Chromatic notes that are not the lead-in to a change: replaced by the nearest scale tone."""
    firsts = _firsts(motif)
    lead = {f - 1 for f in firsts[1:]} | {f - 2 for f in firsts[1:]}
    for k in _non_scale(motif, ctxs):
        if k in lead:
            continue
        prev = motif["midi"][k - 1] if k else motif["midi"][k]
        nxt = motif["midi"][k + 1] if k + 1 < len(motif["midi"]) else motif["midi"][k]
        new = _diatonic_for(motif, ctxs, k, motif["midi"][k], (prev, nxt))
        if new is None or abs(new - motif["midi"][k]) > 2:
            continue
        before = motif["notes"][k]
        _put(motif, k, new, ctxs, "cell")
        return [Edit(k, before, motif["notes"][k], "chromatic_to_scale", motif["chord_timeline"][motif["note_chord_index"][k]]["chord"],
                     f"{before} became the scale note {motif['notes'][k]}")]
    return None


# ---------------------------------------------------------------- operation results


@dataclass
class Result:
    motif: dict[str, Any] | None = None
    edits: list[Edit] = field(default_factory=list)
    says: list[str] = field(default_factory=list)
    pitches_changed: bool = False
    rhythm_changed: bool = False
    shift: int = 0                 # an octave move: every note moved by this many semitones
    reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _valid(mission_id: str, motif: dict[str, Any], span: Any, level: str, style: str) -> Any:
    from mission_span_engine import validate_mission_line

    try:
        return validate_mission_line(mission_id, motif, span, level=level, style=style)
    except Exception:
        return None


def op_chromatic(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, key: str, op: str) -> Result:
    """More / fewer chromatic material, one rung at the changes (and, going down, other chromatic notes)."""
    motif = copy.deepcopy(parent_motif)
    ctxs = _contexts(span, motif)
    n_changes = len(motif["chord_timeline"]) - 1
    order = range(1, n_changes + 1)
    edits: list[Edit] = []
    if op == "stronger_resolution" or op == "add_enclosure":
        order = [n_changes]                         # the resolution is the arrival on the last chord
    for i in order:
        rung = _rung(motif, ctxs, i)
        trial = copy.deepcopy(motif)
        done = None
        if op in ("add_enclosure", "stronger_resolution"):
            done = _make_enclosure(trial, span, ctxs, i, key) if rung != "enclosure" else None
        elif op == "add_approaches":
            done = _make_approach(trial, span, ctxs, i, key) if rung == "plain" else None
        elif op == "more_chromatic":
            if rung == "plain":
                done = _make_approach(trial, span, ctxs, i, key)
            elif rung == "approach":
                done = _make_enclosure(trial, span, ctxs, i, key)
        elif op == "fewer_chromatic":
            done = _reduce(trial, span, ctxs, i, key)
        if not done or trial["midi"] == motif["midi"]:
            continue
        rep_t = _valid(mission_id, _refresh(trial, span), span, level, style)
        if rep_t is not None and rep_t.valid:
            motif, edits = trial, edits + done
    if op == "fewer_chromatic" and not edits:
        trial = copy.deepcopy(motif)
        done = _other_chromatic(trial, span, ctxs, key)
        if done:
            rep = _valid(mission_id, _refresh(trial, span), span, level, style)
            if rep is not None and rep.valid:
                motif, edits = trial, done
    if not edits:
        return Result(reason=_chromatic_refusal(op, motif, ctxs, mission_id))
    return Result(motif=_refresh(motif, span), edits=[e for e in edits if e.before != e.after], pitches_changed=True,
                  says=_say_edits(edits, op))


def _chromatic_refusal(op: str, motif: dict[str, Any], ctxs: list[Any], mission_id: str) -> str:
    n_changes = len(motif["chord_timeline"]) - 1
    rungs = [_rung(motif, ctxs, i) for i in range(1, n_changes + 1)]
    if op == "fewer_chromatic":
        return "There's no chromatic note in this line that I can take out without changing what the exercise is, so I haven't changed it."
    if mission_id == "chord_tones_each_chord":
        return "This is a chord-tones-only exercise, so adding chromatic notes would turn it into a different exercise. I haven't changed it."
    if mission_id == "pentatonic_per_chord" and op != "fewer_chromatic":
        return ("This is a pentatonic exercise: its chromatic notes may only be the single half-step lead-in right before a change, "
                "and this line already has that, so more chromatic material would stop it being a pentatonic line. I haven't changed it.")
    if all(r == "enclosure" for r in rungs):
        return "Every chord change here is already led into by an enclosure, the most chromatic lead-in I can add while keeping the targets, so I haven't changed it."
    if op == "add_approaches" and all(r != "plain" for r in rungs):
        return "Every chord change here already has a chromatic lead-in, so I haven't changed it."
    return ("I couldn't add chromatic material without breaking this exercise's own rule (the targets, the voice leading or the "
            "rhythm), so I haven't changed it.")


def _say_edits(edits: list[Edit], op: str) -> list[str]:
    out = []
    for e in edits:
        if e.detail:
            out.append(e.detail[0].upper() + e.detail[1:] + ".")
    return out


def _cycle_candidates(motif: dict[str, Any]) -> list[Any]:
    from span_motif_engine import focus_preference
    from span_rhythm_grammar import motivic_candidates

    meta = dict(motif.get("rhythm_meta") or {})
    return motivic_candidates(
        list(meta.get("bar_counts") or []), meter=str(meta.get("meter") or "4/4"), level=str(meta.get("level") or "Intermediate"),
        style=str(meta.get("style") or "default"), focus_pref=focus_preference(str(meta.get("focus") or "")),
        downbeat_bars=list(meta.get("downbeat_bars") or []), seed=int(meta.get("seed") or 0), limit=32,
    )


def op_rhythm(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, op: str) -> Result:
    """The same notes, a different rhythm: the existing rhythm grammar's alternatives for the same per-bar note counts."""
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi
    from melodic_rhythm_engine import events_from_json
    from span_motif_engine import rhythm_profile
    from span_rhythm_grammar import rhythm_coherence

    meta = dict(parent_motif.get("rhythm_meta") or {})
    meter = str(meta.get("meter") or "4/4")
    sty = str(meta.get("style") or "default")
    cur_events = events_from_json(parent_motif.get("rhythm_events") or [])
    cur_sig = tuple((e.duration, e.rest, e.tuplet) for e in cur_events)
    cur_prof = rhythm_profile(parent_motif.get("rhythm_events") or [], meter)
    cur_coh = rhythm_coherence(cur_events, meter, style=sty)
    cands = [c for c in _cycle_candidates(parent_motif) if c.signature != cur_sig]
    scored = []
    for c in cands:
        prof = rhythm_profile(c, meter)
        coh = rhythm_coherence(c.events, meter, style=sty)
        busy = prof["offbeat"] + prof["syncopation"] + prof["sixteenths"]
        cur_busy = cur_prof["offbeat"] + cur_prof["syncopation"] + cur_prof["sixteenths"]
        kinds = len({(e.duration, e.tuplet) for e in c.events if not e.rest})
        cur_kinds = len({(e.duration, e.tuplet) for e in cur_events if not e.rest})
        if op == "rhythm_new":
            scored.append((0.0, c, prof, coh))
        elif op == "rhythm_syncopate" and prof["syncopation"] > cur_prof["syncopation"] + 0.04:
            scored.append((-(prof["syncopation"]), c, prof, coh))
        elif op == "rhythm_simpler" and busy < cur_busy - 0.05:
            scored.append((busy, c, prof, coh))
        elif op == "rhythm_interesting" and kinds > cur_kinds and coh.get("total", 0) >= 0.6:
            scored.append((-(kinds + coh.get("total", 0)), c, prof, coh))
        elif op == "rhythm_repeat" and coh.get("cell_identity", 0) >= 0.9 and coh.get("cell_identity", 0) > cur_coh.get("cell_identity", 0) + 0.04:
            scored.append((-coh.get("cell_identity", 0), c, prof, coh))
    scored.sort(key=lambda t: t[0])
    for _s, c, prof, coh in scored:
        idx = cands.index(c)
        out = dict(copy.deepcopy(parent_motif))
        m2 = dict(meta)
        m2["history"] = (list(meta.get("history") or []) + [str(meta.get("id") or "")])[-12:]
        out.update(_engine_rhythm_fields(c, index=idx, count=len(cands), meta=m2))
        out["rhythm_profile"] = rhythm_profile(c, meter)
        out["rhythm_coherence"] = rhythm_coherence(c.events, meter, style=sty)
        out["last_transform"] = "ami_develop"
        out = sync_motif_midi(out)
        rep = _valid(mission_id, out, span, level, style)
        if rep is not None and rep.valid:
            return Result(motif=out, rhythm_changed=True, extra={"profile_before": cur_prof, "profile_after": prof},
                          says=[_say_rhythm(op, cur_prof, prof)])
    why = {
        "rhythm_new": "I couldn't find a different valid rhythm for these notes in this meter",
        "rhythm_syncopate": "none of the valid rhythms for these notes has more syncopation than this one",
        "rhythm_simpler": "this is already the simplest valid rhythm for these notes",
        "rhythm_interesting": "none of the valid rhythms for these notes is more varied while staying a repeated idea",
        "rhythm_repeat": "no valid rhythm for these notes repeats one cell across the chords more closely than this one",
    }[op]
    return Result(reason=f"I haven't changed it: {why}, and I won't move a note off its chord or its resolution just to change the rhythm.")


def _say_rhythm(op: str, before: dict[str, float], after: dict[str, float]) -> str:
    if op == "rhythm_syncopate":
        return "I kept the same notes and moved more of them onto off-beats that carry across the beat."
    if op == "rhythm_simpler":
        return "I kept the same notes and gave them a plainer rhythm, with fewer off-beat entries."
    if op == "rhythm_interesting":
        return "I kept the same notes and gave them a rhythm that uses more different note lengths."
    if op == "rhythm_repeat":
        return "I kept the same notes and made the same rhythmic cell return across the chords."
    return "I kept the same notes and gave them a different rhythm; every chord still starts on beat 1."


def op_register(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, direction: int) -> Result:
    """The whole line an octave higher or lower - register only; contour, targets and rhythm are untouched."""
    from improvisation_motif import _PATTERN_MIDI_HI, _PATTERN_MIDI_LO, _shift_phrase_into_bounds

    motif = copy.deepcopy(parent_motif)
    moved = [m + 12 * direction for m in motif["midi"]]
    if _shift_phrase_into_bounds(list(moved)) != moved or min(moved) < _PATTERN_MIDI_LO or max(moved) > _PATTERN_MIDI_HI:
        word = "higher" if direction > 0 else "lower"
        return Result(reason=f"I can't take the whole line an octave {word}: it would leave the range the staff and the guitar neck "
                             "can show, and I won't bend single notes to fit. I haven't changed it.")
    motif["midi"] = moved
    rep_motif = _refresh(motif, span)
    rep = _valid(mission_id, rep_motif, span, level, style)
    if rep is None or not rep.valid:
        return Result(reason="Moving it would break this exercise's own rule, so I haven't changed it.")
    word = "higher" if direction > 0 else "lower"
    return Result(motif=rep_motif, pitches_changed=True, shift=12 * direction,
                  says=[f"I played the whole line an octave {word}; every note keeps its place in the chord and the rhythm is unchanged."])


def op_develop(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, key: str) -> Result:
    """The Build development of the stored motif (existing ``develop_span_motif``): its notes and rhythm stay audible."""
    from span_motif_engine import develop_span_motif

    seed = copy.deepcopy(parent_motif)
    try:
        built = develop_span_motif(span, seed, length="standard")
    except Exception as exc:
        return Result(reason=f"The motif-development engine couldn't develop this line ({type(exc).__name__}), so I haven't changed it.")
    rep = _valid(mission_id, built, span, level, style)
    if rep is None or not rep.valid:
        return Result(reason="Developing this motif would break the exercise's own rule (the targets or the voice leading), "
                             "so I haven't changed it.")
    if built["midi"] == parent_motif["midi"]:
        return Result(reason="Developing it would leave the line unchanged, so I haven't changed it.")
    ident = built.get("motif_identity") or {}
    added = len(built["midi"]) - len(parent_motif["midi"])
    return Result(motif=built, pitches_changed=True, rhythm_changed=True, extra={"identity": ident},
                  says=[f"I developed the motif: your notes stay, with {max(0, added)} passing, neighbour or chromatic note(s) added between them "
                        f"(the seed stays {round(100 * float(ident.get('total', 0)))}% recognisable)."])


def op_ending(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, key: str) -> Result:
    """Same idea, a different last note: another chord tone of the last chord within a step or two of where the line is."""
    motif = copy.deepcopy(parent_motif)
    ctxs = _contexts(span, motif)
    last = len(motif["midi"]) - 1
    firsts = _firsts(motif)
    if last <= firsts[-1]:
        return Result(reason="The last chord has a single note, so there is no ending to change.")
    prev, cur = motif["midi"][last - 1], motif["midi"][last]
    ctx = ctxs[-1]
    cands = _near([m for m in range(prev - 5, prev + 6) if m % 12 in ctx.chord_pcs and m != prev], prev, (cur,))
    for new in cands:
        trial = copy.deepcopy(motif)
        before = trial["notes"][last]
        _put(trial, last, new, ctxs, "ending")
        _refresh(trial, span)
        rep = _valid(mission_id, trial, span, level, style)
        if rep is not None and rep.valid:
            chord = trial["chord_timeline"][-1]["chord"]
            role = _chord_role(chord, key, new)
            return Result(motif=trial, pitches_changed=True,
                          edits=[Edit(last, before, trial["notes"][last], "ending", chord)],
                          says=[f"I kept the idea and changed its last note from {before} to {trial['notes'][last]}"
                                + (f", the {role} of {chord}." if role else ".")])
    return Result(reason="I couldn't find a different ending that keeps the exercise's own rule, so I haven't changed it.")


def _apply_op(op: str, motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, key: str) -> Result:
    if op in ("more_chromatic", "fewer_chromatic", "add_approaches", "add_enclosure", "stronger_resolution"):
        return op_chromatic(motif, span, mission_id, level, style, key, op)
    return op_rhythm(motif, span, mission_id, level, style, op)


def op_difficulty(parent_motif: dict[str, Any], span: Any, mission_id: str, level: str, style: str, key: str, harder: bool) -> Result:
    """Easier / harder by measurable steps on the CURRENT line: chromatic material one rung, and the rhythm's busyness.
    The first single step that moves the complexity score by a full point wins; else the two steps together."""
    ctxs = _contexts(span, parent_motif)
    base = complexity(parent_motif, ctxs)
    a, b = ("more_chromatic", "rhythm_syncopate") if harder else ("fewer_chromatic", "rhythm_simpler")
    for chain in ((a,), (b,), (a, b)):
        motif, says, edits, ok, pc, rc = parent_motif, [], [], True, False, False
        for op in chain:
            r = _apply_op(op, motif, span, mission_id, level, style, key)
            if r.motif is None:
                ok = False
                break
            motif, says, edits = r.motif, says + r.says, edits + r.edits
            pc, rc = pc or r.pitches_changed, rc or r.rhythm_changed
        if not ok:
            continue
        after = complexity(motif, _contexts(span, motif))
        if (after >= base + 1.0) if harder else (after <= base - 1.0):
            return Result(motif=motif, edits=edits, says=says, pitches_changed=pc, rhythm_changed=rc,
                          extra={"complexity_before": base, "complexity_after": after, "steps": list(chain)})
    word = "harder" if harder else "easier"
    return Result(reason=f"I can't make this measurably {word} without changing what the exercise is for (its targets and its "
                         "voice leading), so I haven't changed it. Ask for a new exercise at another level instead.")


# ---------------------------------------------------------------- AMI's own checks (from pitches, rhythm, chords)


def _rhythm_sig(motif: dict[str, Any]) -> list[tuple]:
    return [(str(e.get("on")), str(e.get("dur")), bool(e.get("rest"))) for e in motif.get("rhythm_events") or []]


def development_checks(parent: dict[str, Any], new: dict[str, Any], span: Any, key: str, res: Result) -> list[dict[str, Any]]:
    ctxs_new = _contexts(span, new)
    checks: list[dict[str, Any]] = []
    same_timeline = ([(t["chord"], t["start"], t["end"]) for t in parent["chord_timeline"]]
                     == [(t["chord"], t["start"], t["end"]) for t in new["chord_timeline"]])
    checks.append({"name": "harmony_and_timing_preserved", "ok": same_timeline,
                   "detail": "the same chords on the same bars as the previous version"})
    pf, nf = _firsts(parent), _firsts(new)
    shift = res.shift
    targets_ok = len(pf) == len(nf) and all(new["midi"][b] == parent["midi"][a] + shift for a, b in zip(pf, nf))
    checks.append({"name": "harmonic_targets_preserved", "ok": targets_ok,
                   "detail": "every chord still starts on the same note" + (" (an octave away)" if shift else "")})
    if not res.pitches_changed:
        checks.append({"name": "pitches_identical", "ok": new["midi"] == parent["midi"] and new["note_chord_index"] == parent["note_chord_index"],
                       "detail": "same notes, same chord for every note"})
    if not res.rhythm_changed:
        same = len(new["midi"]) == len(parent["midi"]) and new["note_chord_index"] == parent["note_chord_index"]
        checks.append({"name": "chord_assignment_and_rhythm_preserved", "ok": same and _rhythm_sig(new) == _rhythm_sig(parent),
                       "detail": "every note keeps its chord, its entry and its length"})
    if res.rhythm_changed:
        events = new.get("rhythm_events") or []
        starts_ok = all(f < len(events) and Fraction(str(events[f]["on"])) == Fraction(str(t["start"]))
                        for f, t in zip(nf, new["chord_timeline"]))
        checks.append({"name": "chords_start_on_their_downbeat", "ok": starts_ok, "detail": "each chord's first note still sounds when the chord begins"})
    stray = [k for k in _non_scale(new, ctxs_new) if not _resolves(new, k)]
    checks.append({"name": "chromatic_notes_resolve", "ok": not stray,
                   "detail": "every chromatic note moves by a step into the next note" if not stray
                   else f"{new['notes'][stray[0]]} is chromatic and leads nowhere"})
    return checks


def edits_summary(res: Result) -> list[dict[str, Any]]:
    return [{"index": e.index, "before": e.before, "after": e.after, "why": e.why, "chord": e.chord} for e in res.edits]


# ---------------------------------------------------------------- orchestration

_UNSUPPORTED = {
    "fewer_notes": ("Using fewer notes would change how many notes each chord gets, and with it the rhythm and the targets of this "
                    "line, which I don't edit yet. \"Make the rhythm simpler\" or \"use fewer chromatic notes\" make it easier "
                    "while keeping the notes that matter."),
    "more_movement": ("Adding movement means adding notes between the targets. \"Develop the motif\" does that with the existing "
                      "motif-development engine, and \"make it more chromatic\" adds chromatic lead-ins."),
    "direction": ("The shape of a multi-chord line is set by where each chord's target note sits, so I can't turn it into an ascending "
                  "or descending line without changing its targets. I can move the whole line an octave (\"play it in a higher "
                  "register\"), or you can ask for a new exercise."),
    "smaller_range": ("Narrowing the range would mean moving single notes by an octave, which changes the contour, so I haven't. "
                      "I can move the whole line an octave up or down instead."),
    "motif_repeat": ("Repeating the motif across the same chords would need a longer stretch of the song than this exercise covers. "
                     "\"Develop the motif\" builds on it within these chords, or ask for \"the next three chords\"."),
    "motif_next_chord": ("Carrying the motif onto the next chord needs the next chord's span in the song, which this exercise doesn't "
                         "hold; that is not available yet. \"Develop the motif\" builds on it within these chords."),
}

_TITLES = {
    "more_chromatic": "More chromatic", "add_approaches": "Chromatic approaches added", "add_enclosure": "Enclosure before the resolution",
    "stronger_resolution": "Stronger resolution", "fewer_chromatic": "Less chromatic", "rhythm_new": "New rhythm, same notes",
    "rhythm_syncopate": "More syncopation, same notes", "rhythm_simpler": "Simpler rhythm, same notes",
    "rhythm_interesting": "More varied rhythm, same notes", "rhythm_repeat": "One rhythm across the chords, same notes",
    "motif_develop": "Motif developed", "motif_ending": "New ending", "easier": "Easier version", "harder": "Harder version",
    "register_shift": "Register changed", "original": "Back to the original",
}


def _refusal(parent: Any, fu: Any, reason: str) -> dict[str, Any]:
    return {
        "direct_answer": reason,
        "practice_steps": ["Your previous exercise is unchanged — keep working with it, open it in Missions, or ask for something else."],
        "what_to_listen_for": [], "suggested_next_action": "", "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {"musical_idea_content": True, "exercise_followup": True, "followup_kind": getattr(fu, "kind", ""),
                        "followup_utterance": getattr(fu, "raw", ""), "parent_exercise_id": parent.id,
                        "exercise_followup_failed": True, "exercise_followup_failure_reason": reason},
    }


def _op_for(fu: Any) -> tuple[str, int, str]:
    """(operation, direction, refusal). Older follow-up kinds are mapped onto the multi-chord operations."""
    from music_coach_ami import exercise_followup as F

    if fu.kind == KIND_DEVELOP:
        d = fu.develop
        return d["op"], int(d.get("direction") or 0), ""
    if fu.kind == F.KIND_EASIER:
        return "easier", 0, ""
    if fu.kind == F.KIND_HARDER:
        return "harder", 0, ""
    if fu.kind == F.KIND_SAME_NOTES:
        return "rhythm_new", 0, ""
    if fu.kind == F.KIND_MOVE:
        if re.search(r"\b(?:degree|step)s?\b", fu.raw.lower()):
            return "", 0, ("Moving by scale degrees changes which chord tones the line lands on, so it isn't available on a multi-chord "
                           "exercise. Ask me to move it an octave (\"play it in a higher register\"), or for a new exercise.")
        return "register_shift", int(fu.direction or 1), ""
    return "", 0, ("I can't do that to a multi-chord exercise yet. I can make it more or less chromatic, change its rhythm, develop its "
                   "motif, make it easier or harder, move it an octave, or go back to the original. Ask for a new one for anything else "
                   "(for example \"guide-tone line over the next three chords\").")


def _human_header(op: str, says: list[str], kept: list[str], changed: list[str], extra: dict[str, Any]) -> str:
    lines = [f"**{_TITLES.get(op, op)}** — built from your previous exercise.", *says]
    if "complexity_before" in extra:
        lines.append(f"_Difficulty score {extra['complexity_before']} → {extra['complexity_after']}._")
    lines.append(f"Kept: {', '.join(kept) or '—'} · Changed: {', '.join(changed) or '—'}")
    return "\n\n".join(lines)


def compose_span_followup(
    fu: Any, parent: Any, *, session_ref: Any, instrument: str, notation_instrument: str, display_instrument: str, bpm: int,
) -> dict[str, Any]:
    from mission_span_engine import MISSIONS_BY_ID, _example_payload, validate_mission_line
    from music_coach_ami.exercise_bridge import store_last_exercise
    from music_coach_ami.exercise_followup import _next_nonce, _rebound_context
    from music_coach_ami.exercise_span import (
        _guitar_family,
        build_span_exercise,
        render_span_abc,
        span_checks,
        span_prose,
        span_tab,
    )

    op, direction, refusal = _op_for(fu)
    if refusal:
        return _refusal(parent, fu, refusal)
    if op in _UNSUPPORTED:
        return _refusal(parent, fu, _UNSUPPORTED[op])
    example = _example_of(parent)
    if example is None:
        return _refusal(parent, fu, "That exercise doesn't carry the musical data I need to build on it. Ask for a new one.")
    live = {"session_ref": session_ref, "instrument": instrument, "notation_inst": notation_instrument}
    try:
        ctx = _rebound_context(parent.context, live)
        lv = resolve_live(session_ref, parent, ctx)
        if lv.res is None:
            return _refusal(parent, fu, lv.reason)
        span, res = lv.span, lv.res
        mission_id = _clean(example.get("mission_id"))
        level, style = _clean(example.get("level")) or "Intermediate", _clean(example.get("style")) or "default"
        key = _clean((res.info or {}).get("concert_key")) or ctx.concert_key
        motif = example["motif"]
        lineage_prev = dict(parent.transform.get("lineage") or {})
        root_example = copy.deepcopy(lineage_prev.get("root_example") or example)
        if op == "original":
            if not lineage_prev.get("root_example"):
                return _refusal(parent, fu, "This is already the original exercise, so there is nothing to go back to.")
            result = Result(motif=copy.deepcopy(root_example["motif"]), pitches_changed=True, rhythm_changed=True,
                            says=["I restored the first version of this exercise, exactly as it was generated."])
        elif op in ("more_chromatic", "add_approaches", "add_enclosure", "stronger_resolution", "fewer_chromatic"):
            result = op_chromatic(motif, span, mission_id, level, style, key, op)
        elif op.startswith("rhythm_"):
            result = op_rhythm(motif, span, mission_id, level, style, op)
        elif op == "motif_develop":
            result = op_develop(motif, span, mission_id, level, style, key)
        elif op == "motif_ending":
            result = op_ending(motif, span, mission_id, level, style, key)
        elif op in ("easier", "harder"):
            result = op_difficulty(motif, span, mission_id, level, style, key, op == "harder")
        elif op == "register_shift":
            result = op_register(motif, span, mission_id, level, style, direction or 1)
        else:
            return _refusal(parent, fu, "I can't do that to a multi-chord exercise yet.")
        if result.motif is None:
            return _refusal(parent, fu, result.reason)
        report = validate_mission_line(mission_id, result.motif, span, level=level, style=style)
        new_example = _example_payload(MISSIONS_BY_ID[mission_id], span, result.motif, report, level=level,
                                       difficulty=_clean(example.get("difficulty")) or "normal", idea=int(example.get("idea") or 0),
                                       style=style, focus=_clean(example.get("focus")))
        new_example["handoff"]["practice_key"] = key
        plan = _plan_of(parent)
        neutral = replace(plan, technique="", constraints={}, target_roles=())
        checks = span_checks(new_example, span, key, requested_length=len(span.chords), plan=neutral)
        if op != "original":
            checks += development_checks(motif, result.motif, span, key, result)
        bad = [c for c in checks if not c["ok"]]
        if bad:
            return _refusal(parent, fu, "That change didn't pass my checks (" + "; ".join(f"{c['name']}: {c['detail']}" for c in bad)
                            + "), so I haven't changed the exercise.")
        nonce = _next_nonce(parent)
        intent = replace(parent.intent, variation_index=nonce, transform=KIND_DEVELOP)
        ex = build_span_exercise(res, new_example, checks, 1, intent, ctx, neutral)
        kept = ["chords", "key", "mission"] + (["harmonic targets"] if op not in ("original", "motif_ending") else []) \
            + ([] if result.pitches_changed else ["notes"]) + ([] if result.rhythm_changed else ["rhythm"])
        changed = (["notes"] if result.pitches_changed else []) + (["rhythm"] if result.rhythm_changed else [])
        root_id = _clean(lineage_prev.get("root_id")) or parent.id
        ex.parent_id = parent.id
        ex.id = "ex-" + sha({"m": ex.midi, "p": parent.id, "op": op, "n": nonce, "r": _rhythm_sig(result.motif)})
        steps = list(lineage_prev.get("steps") or []) + [{"id": ex.id, "parent": parent.id, "op": op, "utterance": fu.raw}]
        ex.transform = {
            "kind": KIND_DEVELOP, "op": op, "utterance": fu.raw, "parent": parent.id, "root": root_id, "nonce": nonce, "seed": int(ex.seed),
            "inherited": kept, "changed": changed, "overridden": [], "context_mode": "stored_context",
            "edits": edits_summary(result), "says": list(result.says), "details": {k: v for k, v in result.extra.items() if k != "identity"},
            "parent_fingerprints": {"notes_sha1": sha({"midi": parent.midi}), "rhythm_sha1": sha(_rhythm_sig(motif))},
            "preserved": {"notes_sha1": sha({"midi": ex.midi}), "rhythm_sha1": sha(_rhythm_sig(result.motif))},
            "lineage": {"root_id": root_id, "root_example": root_example, "steps": steps},
            "direction": direction, "degrees": 0,
        }
        ex.provenance.update({"parent": parent.id, "transform": KIND_DEVELOP, "development_op": op, "root": root_id,
                              "inherited": kept, "changed": changed, "nonce": nonce})
        ex.intent = replace(ex.intent, variation_index=nonce, transform=KIND_DEVELOP)
        guitar = _guitar_family(ctx.instrument or display_instrument)
        tab = span_tab(ex) if guitar else ""
        prose = span_prose(ex, neutral, display_instrument=display_instrument, tab=tab)
        abc = render_span_abc(ex, bpm=int(bpm or 96), title=f"{neutral.title} — {ex.chord}", instrument=ctx.notation_instrument or ctx.instrument)
        stored = store_last_exercise(session_ref, ex)
    except Exception as exc:  # a follow-up must never silently turn into a different operation
        return _refusal(parent, fu, f"That follow-up hit an unexpected problem ({type(exc).__name__}: {exc}), so I haven't changed the exercise.")
    action = {
        "kind": neutral.action_kind, "exercise_id": ex.id, "label": "Open in Missions", "mission_id": mission_id,
        "span_id": span.span_id, "scope": res.info.get("scope"), "progression_key": res.info.get("progression_key"),
        "concert_key": key, "chords": list(ex.chords), "section": span.section_label, "start_event": span.start_event,
        "example": new_example,
    }
    header = _human_header(op, result.says, kept, changed, result.extra)
    return {
        "direct_answer": header + "\n\n" + prose["direct_answer"],
        "practice_steps": prose["practice_steps"], "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Keep developing it: more or less chromatic, a new rhythm, develop the motif, easier or harder, or open it in Missions.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [],
        "diagnostics": {
            "musical_idea_content": True, "exercise_followup": True, "followup_kind": KIND_DEVELOP, "followup_utterance": fu.raw,
            "parent_exercise_id": parent.id, "exercise_bridge": True, "exercise_span_request": True,
            "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(), "exercise_context": ex.context.to_dict(),
            "exercise_validation": ex.validation, "notation_abc_present": bool(abc), "guitar_tab_present": bool(tab),
            "last_exercise_stored": stored, "transform": ex.transform, "practice_concert_key": ex.context.concert_key,
            "written_key": ex.context.written_key, "resolved_instrument": ex.context.instrument,
            "notation_instrument": ex.context.notation_instrument, "bars_generated": ex.bars, "exercise_span": res.info,
            "open_in_missions": action,
        },
    }
