"""AMI exercises across a 2-/3-chord HarmonicSpan, and "Open in Missions".

AMI never builds the line itself. The musical content comes from the Missions engines:

    request  ->  ``resolve_span`` (the span the Missions page would offer: ``resolve_span_options``)
             ->  a typed ``PatternPlan`` selecting an existing span Mission
             ->  ``generate_mission_span_example(plan.mission_id, span, ...)``  (validated by the engine)
             ->  common ownership checks plus the established guide-tone checks where applicable
             ->  canonical ``GeneratedExercise`` (concert pitch; ``chords`` + ``chord_assignment`` say which chord each
                 note belongs to)
             ->  card (staff, optional Guitar TAB, explanation read from the engine's own evidence)
             ->  "Open in Missions": the *same* example is staged into the Missions span state, not regenerated.

Not supported yet (said to the player, never approximated): blues or composite techniques across a span,
transposing instruments / capo shapes, a named key that differs from the song's Practice Key, follow-ups on a span
exercise, articulation/dynamics on a span exercise.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any

from music_coach_ami.exercise_model import (
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_COMPOSITE,
    TECHNIQUE_ENCLOSURE,
    VOCAB_BLUES,
    VOCAB_CHORD_TONES,
    VOCAB_GUIDE_TONES,
    VOCAB_PENTATONIC,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
    PatternPlan,
)

# Compatibility alias retained for Slice 4 callers and tests.
SPAN_MISSION_ID = "guide_tone_voice_leading"
SUPPORTED_SPAN_MISSION_IDS = frozenset(
    {
        SPAN_MISSION_ID,
        "pentatonic_per_chord",
        "chord_tones_each_chord",
        "approach_next_chord",
        "enclose_next_target",
    }
)
ENGINE_NAME = "mission_span_engine"
ENGINE_VERSION = 1
_ATTEMPTS = 6  # New-Idea indexes tried when an example fails AMI's own checks (the engine already tries 40 seeds each)
_DEGREE_LABEL = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "b5", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}
_DEFAULT_LENGTH = 2
_RELATION_LENGTH = {"ii_V_I": 3, "ii_V": 2, "V_I": 2}
_ARROW = " → "
_EN = " – "
_RELATION_WORDS = {"ii_V_I": "ii–V–I", "ii_V": "ii–V", "V_I": "V–I"}


def span_pattern_plan(intent: ExerciseIntent) -> PatternPlan:
    """Map normalized intent to an existing validated span Mission.

    Pitch vocabulary and technique remain independent. Stage 1 deliberately
    refuses combinations such as a pentatonic enclosure or a guide-tone line
    with chromatic approaches; those composite constraints belong to Stage 3.
    """
    technique = _clean(intent.technique)
    vocabulary = _clean(intent.vocabulary)
    explicit_vocab = "vocabulary" in (intent.explicit_fields or {})
    if technique == TECHNIQUE_COMPOSITE:
        return PatternPlan(
            vocabulary=vocabulary,
            technique=technique,
            mission_id="",
            title="Composite span exercise",
            limitation="combining chromatic approaches and enclosures in one span exercise is not available yet",
        )
    if technique and explicit_vocab and vocabulary != VOCAB_CHORD_TONES:
        return PatternPlan(
            vocabulary=vocabulary,
            technique=technique,
            mission_id="",
            title="Composite span exercise",
            limitation=(
                f"combining {vocabulary.replace('_', ' ')} pitch vocabulary with "
                f"{technique.replace('_', ' ')} across several chords is not available yet"
            ),
        )
    if technique == TECHNIQUE_CHROMATIC_APPROACH:
        return PatternPlan(
            vocabulary=VOCAB_CHORD_TONES,
            technique=technique,
            mission_id="approach_next_chord",
            title="Chromatic approach exercise",
            listen_for=(
                "The approach note resolving into a chord tone exactly when the next chord arrives",
                "How the half-step pull makes each chord change audible",
            ),
        )
    if technique == TECHNIQUE_ENCLOSURE:
        return PatternPlan(
            vocabulary=VOCAB_CHORD_TONES,
            technique=technique,
            mission_id="enclose_next_target",
            title="Enclosure exercise",
            listen_for=(
                "The notes above and below the target surrounding it before the chord change",
                "The enclosed chord tone landing exactly when the next chord arrives",
            ),
        )
    if vocabulary == VOCAB_GUIDE_TONES:
        return PatternPlan(
            vocabulary=vocabulary,
            mission_id=SPAN_MISSION_ID,
            title="Guide-tone line",
            action_kind="span_guide_tones",
            listen_for=(
                "Each chord's first note is its 3rd or 7th — the notes that define the chord's sound",
                "How the line moves from one chord's guide tone to the next by step or by holding the note",
            ),
        )
    if vocabulary == VOCAB_PENTATONIC:
        return PatternPlan(
            vocabulary=vocabulary,
            mission_id="pentatonic_per_chord",
            title="Pentatonic pattern",
            listen_for=(
                "How the pentatonic collection follows each sounding chord",
                "The chord change staying clear even though the line keeps one connected shape",
            ),
        )
    if vocabulary == VOCAB_CHORD_TONES:
        return PatternPlan(
            vocabulary=vocabulary,
            mission_id="chord_tones_each_chord",
            title="Chord-tone pattern",
            listen_for=(
                "Every note belonging to the chord sounding at that moment",
                "A defining note making each chord change audible",
            ),
        )
    if vocabulary == VOCAB_BLUES:
        return PatternPlan(
            vocabulary=vocabulary,
            mission_id="",
            title="Blues span exercise",
            limitation="blues exercises across several chords are not supported by the span Mission engine",
        )
    return PatternPlan(
        vocabulary=vocabulary,
        mission_id="",
        title="Span exercise",
        limitation=f"{vocabulary.replace('_', ' ') or 'that'} span vocabulary is not available yet",
    )


def _clean(value: object) -> str:
    return str(value or "").strip()


def _sym(chord: object) -> str:
    return _clean(chord).replace("♭", "b").replace("♯", "#")


def _pretty(text: str) -> str:
    """Chord symbol or note name for display: flats and sharps as ♭ / ♯ (the symbol itself is unchanged)."""
    return re.sub(r"(?<=[A-G])b|b(?=\d)", "♭", str(text or "")).replace("#", "♯")


def _session(session_ref: Any) -> dict[str, Any]:
    try:
        from music_coach_ami.session_access import as_mutable_session

        raw = as_mutable_session(session_ref)
    except ImportError:
        raw = session_ref
    return raw if isinstance(raw, dict) or hasattr(raw, "get") else {}


# ---------------------------------------------------------------- span resolution


@dataclass
class SpanResolution:
    """Outcome of ``resolve_span``: the span (or the reason there is none) and how it was chosen."""

    span: Any = None
    options: Any = None
    info: dict[str, Any] | None = None
    message: str = ""
    project: Any = None
    improv_ctx: Any = None
    probe: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.span is not None


def _scope_for_length(length: int) -> str:
    return "span3" if length == 3 else "span2"


def _transposed_notation_reason(ctx: ActiveContext, opts: Any) -> str:
    """Why this player's written/shape notation cannot be shown correctly yet ('' when concert pitch is what they read)."""
    if ctx.written_transposition_applied or int(ctx.transposition_semitones or 0):
        return (
            f"{ctx.notation_instrument or ctx.instrument} reads a transposed written key, and multi-chord exercises are "
            "only available in concert pitch for now (their written spelling still needs a chord-aware respell), "
            "so I won't show you wrong written notes"
        )
    if opts is not None:
        try:
            from music_theory import semitone_distance

            if semitone_distance(opts.concert_key, opts.chart_key) not in (0, None):
                return (
                    f"your chart is shown in {opts.chart_key} (a capo or shape key) while the Practice Key is {opts.concert_key}; "
                    "multi-chord exercises are only available when the chart and Practice Key agree for now, "
                    "so I won't show you wrong notes"
                )
        except Exception:
            pass
    return ""


def _limit(message: str, **info: Any) -> SpanResolution:
    return SpanResolution(message=message, info={"resolved": False, "reason": message, **info})


def resolve_span(
    session_ref: Any, ctx: ActiveContext, intent: ExerciseIntent, plan: PatternPlan | None = None
) -> SpanResolution:
    """Choose the HarmonicSpan for a span request. Read-only: the session is never written.

    Same analysis as the Missions page offers (``resolve_span_options``), evaluated as the Missions tab would see it, so
    the span ids match and "Open in Missions" lands on exactly this span.
    """
    plan = plan or span_pattern_plan(intent)
    if intent.span_unsupported:
        return _limit(f"I can't build that yet: {intent.span_unsupported}.", unsupported=intent.span_unsupported)
    if not plan.supported:
        return _limit(f"I can't build that yet: {plan.limitation}.", unsupported=plan.limitation)
    reason = _transposed_notation_reason(ctx, None)
    if reason:
        return _limit(f"I can't build that multi-chord exercise yet: {reason}.", unsupported="written_key")

    from improvisation_intelligence_ui import (
        SPAN_SONG_STYLE_STATE_KEY,
        _mission_improv_ctx_from_session,
        resolve_span_options,
    )
    from improvisation_motif import resolve_improv_section_rows
    from mission_span_engine import MISSIONS_BY_ID, unavailable_reason
    from mission_span_ui import MISSION_SPAN_SELECTION_STATE_KEY

    probe = dict(_session(session_ref))  # evaluated as the Missions tab would; the real session is untouched
    probe["improv_intelligence_tab"] = "Missions"
    probe["creative_improv_intelligence_tab"] = "Missions"
    try:
        improv_ctx = _mission_improv_ctx_from_session(probe)
        rows = resolve_improv_section_rows(probe, improv_ctx) if improv_ctx is not None else []
    except Exception as exc:
        return _limit(f"I couldn't read this song's chords ({type(exc).__name__}).", unsupported="no_chords")
    if not rows:
        return _limit("I need the song's chords to build a multi-chord exercise. Select a song with chords (or a Custom "
                      "progression) and ask again.", unsupported="no_chords")

    # How many chords: the request, else the relationship asked for, else the Missions span scope, else two.
    mission = ctx.mission_active
    stored_scope = _clean(probe.get("_improv_mission_target_scope_choice"))
    if intent.span_length in (2, 3):
        length, length_source = intent.span_length, "explicit_request"
    elif intent.span_relationship:
        length, length_source = _RELATION_LENGTH.get(intent.span_relationship, _DEFAULT_LENGTH), "relationship_request"
    elif mission and stored_scope in ("span2", "span3"):
        length, length_source = (3 if stored_scope == "span3" else 2), "mission_span_scope"
    else:
        length, length_source = _DEFAULT_LENGTH, "default_two"
    scope = _scope_for_length(length)
    level = _clean(probe.get("level")) or ctx.level
    opts = resolve_span_options(probe, improv_ctx, rows, scope=scope, level=level)
    if opts is None:
        if intent.span_relationship:
            return _limit(f"I couldn't find a {_RELATION_WORDS.get(intent.span_relationship, intent.span_relationship)} in this "
                          f"progression: no {length}-chord span fits inside a single section of it.", length=length)
        return _limit(f"No {length}-chord span fits inside a single section of this progression.", length=length)
    reason = _transposed_notation_reason(ctx, opts)
    if reason:
        return _limit(f"I can't build that multi-chord exercise yet: {reason}.", unsupported="written_key")
    if intent.explicit_key and _clean(ctx.key_source) == "explicit_request":
        from music_theory import semitone_distance

        if semitone_distance(opts.concert_key, ctx.concert_key) not in (0, None):
            return _limit(
                f"You named {ctx.concert_key}, but this song's Practice Key is {opts.concert_key}. Multi-chord exercises "
                "follow the song's Practice Key for now: change the Practice Key, or ask again without naming a key.",
                unsupported="explicit_key",
            )

    ordered = list(opts.ordered)
    chosen, source = None, ""
    anchor, anchor_origin = _anchor_chord(ctx, opts)
    if intent.span_relationship:
        matches = [s for s in ordered if s.relationship == intent.span_relationship]
        if not matches:
            offered = "; ".join(f"{_ARROW.join(opts.project(c) for c in s.chords)}" for s in ordered[:4])
            return _limit(
                f"I couldn't find a {_RELATION_WORDS.get(intent.span_relationship, intent.span_relationship)} in this "
                f"progression at your level." + (f" The {length}-chord spans on offer are: {offered}." if offered else ""),
                length=length, relationship=intent.span_relationship,
            )
        chosen, source = _prefer_near(matches, ctx, anchor), "relationship_match"
    else:
        sel = probe.get(MISSION_SPAN_SELECTION_STATE_KEY)
        picked = sel.get(scope) if isinstance(sel, dict) and sel.get("progression_key") == opts.progression_key else None
        by_id = {s.span_id: s for s in ordered}
        if mission and picked in by_id and (length_source in ("mission_span_scope", "default_two") or intent.span_length == length):
            chosen, source = by_id[picked], "mission_span_selection"
        else:
            anchor, anchor_origin = _anchor_chord(ctx, opts)
            starts = [s for s in ordered if _sym(s.chords[0]) == anchor and (not ctx.section or s.section_label == ctx.section)]
            starts = starts or [s for s in ordered if _sym(s.chords[0]) == anchor]
            if starts:
                chosen, source = starts[0], "selected_chord_window"
            else:
                offered = "; ".join(_ARROW.join(opts.project(c) for c in s.chords) for s in ordered[:4])
                return _limit(
                    f"The {length} chords starting at {anchor or 'the selected chord'} aren't a span the Missions "
                    f"page offers at your level, so I won't invent one." + (f" Spans on offer: {offered}." if offered else ""),
                    length=length, anchor=anchor,
                )
    mission_obj = MISSIONS_BY_ID[plan.mission_id]
    style = _clean(probe.get(SPAN_SONG_STYLE_STATE_KEY)) or "default"
    why = unavailable_reason(mission_obj, chosen, level=_level(opts, level), style=style)
    if why:
        fits = [s for s in ordered if not unavailable_reason(mission_obj, s, level=_level(opts, level), style=style)]
        offered = "; ".join(_ARROW.join(opts.project(c) for c in s.chords) for s in fits[:3])
        return _limit(
            f"A {plan.title.lower()} doesn't fit {_ARROW.join(opts.project(c) for c in chosen.chords)}: {why}."
            + (f" It does fit: {offered}." if offered else ""),
            span_id=chosen.span_id,
        )
    info = {
        "resolved": True, "span_id": chosen.span_id, "chords": list(chosen.chords),
        "player_chords": [opts.project(c) for c in chosen.chords], "roman": list(chosen.roman),
        "relationship": chosen.relationship, "relationship_label": chosen.relationship_label,
        "section": chosen.section_label, "scope": scope, "length": length, "length_source": length_source,
        "selection_source": source, "anchor_chord": anchor, "anchor_origin": anchor_origin, "progression_key": opts.progression_key,
        "concert_key": opts.concert_key, "key_center": chosen.key_center, "level": level, "style": style,
        "pattern_plan": plan.to_dict(), "mission_id": plan.mission_id,
        "mission_selection_considered": bool(mission),
    }
    return SpanResolution(span=chosen, options=opts, info=info, project=opts.project, improv_ctx=improv_ctx, probe=probe)


def _level(opts: Any, level: str) -> str:
    from span_motif_engine import _level as engine_level

    return engine_level(level)


def _anchor_chord(ctx: ActiveContext, opts: Any) -> tuple[str, str]:
    """The chord the span starts from, read from the same rows the Missions page uses.

    The Mission's own selected chord when a Mission is engaged; otherwise the first chord of the active section.
    """
    if ctx.mission_active and ctx.chord_source in ("mission_selected_chord", "mission_chord_click") and _clean(ctx.selected_chord):
        return _sym(ctx.selected_chord), "mission_selected_chord"
    rows = list(opts.section_rows)
    row = next((r for r in rows if _clean(r[0]) == _clean(ctx.section)), rows[0] if rows else None)
    if row and row[1]:
        return _sym(row[1][0]), "section_first_chord"
    return _sym(ctx.selected_chord), "context_chord"


def _prefer_near(matches: list[Any], ctx: ActiveContext, anchor: str) -> Any:
    """Among spans of the asked-for relationship, the one starting at the anchor chord, else the first in section order."""
    for s in matches:
        if _sym(s.chords[0]) == anchor and (not ctx.section or s.section_label == ctx.section):
            return s
    for s in matches:
        if ctx.section and s.section_label == ctx.section:
            return s
    return matches[0]


# ---------------------------------------------------------------- generation and AMI's own checks


def _guide_pcs(chord: str, key: str) -> tuple[set[int], list[str]]:
    from improvisation_motif import _midi_from_note, chord_tone_names

    names = chord_tone_names(chord, reference_key=key) or []
    pcs = [_midi_from_note(n, 4) % 12 for n in names]
    guide = set()
    if len(pcs) > 1:
        guide.add(pcs[1])
    if len(pcs) > 3:
        guide.add(pcs[3])
    return guide, names


def span_checks(
    example: dict[str, Any], span: Any, key: str, *, requested_length: int, plan: PatternPlan
) -> list[dict[str, Any]]:
    """AMI's own verification of an engine example (the engine's validator is one check, not the only one)."""
    motif = example.get("motif") or {}
    midi = [int(m) for m in motif.get("midi") or []]
    timeline = list(motif.get("chord_timeline") or [])
    assign = [int(i) for i in motif.get("note_chord_index") or []]
    checks: list[dict[str, Any]] = [
        {"name": "mission_validator", "ok": bool(example.get("valid")) and example.get("mission_id") == plan.mission_id,
         "detail": "; ".join(example.get("problems") or []) or f"{plan.mission_id} passed"},
        {"name": "span_length", "ok": len(span.chords) == requested_length and len(timeline) == requested_length,
         "detail": f"{len(timeline)} chords in the line, {requested_length} requested"},
        {"name": "chord_assignment", "ok": len(assign) == len(midi) and all(0 <= i < len(span.chords) for i in assign)
         and assign == sorted(assign) and sorted(set(assign)) == list(range(len(span.chords))),
         "detail": f"{len(midi)} notes assigned across {len(span.chords)} chords"},
    ]
    boundary_ok = len(timeline) == len(span.chords)
    boundary_detail: list[str] = []
    for idx, slot in enumerate(timeline):
        first, last = int(slot.get("first_note", -1)), int(slot.get("last_note", -1))
        owned = [i for i, chord_idx in enumerate(assign) if chord_idx == idx]
        expected_chord = _sym(span.chords[idx]) if idx < len(span.chords) else ""
        actual_chord = _sym(slot.get("chord"))
        slot_ok = bool(owned) and (owned[0], owned[-1]) == (first, last) and actual_chord == expected_chord
        boundary_ok = boundary_ok and slot_ok
        boundary_detail.append(f"{actual_chord}: notes {first}-{last} owned by slot {idx}")
    checks.append({"name": "harmonic_boundaries", "ok": boundary_ok, "detail": "; ".join(boundary_detail)})

    evidence_names = [str(item.get("check") or "") for item in example.get("evidence") or []]
    evidence_contract = {
        "pentatonic_per_chord": ("notes from the chord's pentatonic", len(timeline)),
        "chord_tones_each_chord": ("only chord tones of the sounding chord", 1),
        "approach_next_chord": ("approach into the next chord", max(1, len(timeline) - 1)),
        "enclose_next_target": ("enclosure resolves at the change", max(1, len(timeline) - 1)),
    }.get(plan.mission_id)
    if evidence_contract:
        check_name, expected = evidence_contract
        actual = evidence_names.count(check_name)
        checks.append({
            "name": "requested_technique",
            "ok": actual >= expected,
            "detail": f"{actual}/{expected} '{check_name}' validations passed",
        })
    if plan.mission_id != SPAN_MISSION_ID:
        return checks

    # Slice 4's independent guide-tone verification remains unchanged.
    arrivals: list[int] = []
    on_guide, motion_ok, details = True, True, []
    for t in timeline:
        first = int(t.get("first_note", 0))
        if not (0 <= first < len(midi)):
            on_guide = False
            continue
        arrivals.append(midi[first])
        guide, _names = _guide_pcs(_clean(t.get("chord")), key)
        hit = midi[first] % 12 in guide
        on_guide = on_guide and hit
        details.append(f"{t.get('chord')}: {midi[first] % 12 in guide}")
    for a, b in zip(arrivals, arrivals[1:]):
        motion_ok = motion_ok and abs(b - a) <= 2
    checks.append({"name": "guide_tone_on_each_arrival", "ok": on_guide and len(arrivals) == len(timeline), "detail": "; ".join(details)})
    checks.append({"name": "guide_tone_voice_leading", "ok": motion_ok and len(arrivals) > 1,
                   "detail": "arrival notes move by a step or stay: " + " → ".join(str(m) for m in arrivals)})
    return checks


def generate_span_example(
    res: SpanResolution, ctx: ActiveContext, intent: ExerciseIntent, plan: PatternPlan
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], int, str]:
    """(example, checks, attempts, reason). The engine example is accepted only if AMI's own checks also pass."""
    from mission_span_engine import generate_mission_span_example

    span, info = res.span, res.info or {}
    last_reason = f"no example demonstrated the requested {plan.title.lower()}"
    for k in range(_ATTEMPTS):
        try:
            example = generate_mission_span_example(
                plan.mission_id, span, level=_clean(info.get("level")) or ctx.level, variant="normal", instrument=ctx.instrument,
                idea=int(intent.variation_index) + k, style=_clean(info.get("style")) or "default", focus=ctx.practice_focus,
            )
        except Exception as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            continue
        example["handoff"]["practice_key"] = _clean(info.get("concert_key")) or ctx.concert_key
        checks = span_checks(
            example,
            span,
            _clean(info.get("concert_key")) or ctx.concert_key,
            requested_length=int(info.get("length") or len(span.chords)),
            plan=plan,
        )
        if all(c["ok"] for c in checks):
            return example, checks, k + 1, ""
        last_reason = "; ".join(f"{c['name']}: {c['detail']}" for c in checks if not c["ok"])
    return None, [], _ATTEMPTS, last_reason


# ---------------------------------------------------------------- the canonical exercise


def _chord_role_for_pc(chord_pcs: list[int], pc: int) -> str:
    names = ("R", "3", "5", "7", "9", "11", "13")
    for i, tone in enumerate(chord_pcs):
        if tone == pc:
            return names[i] if i < len(names) else ""
    return ""


def build_span_exercise(
    res: SpanResolution, example: dict[str, Any], checks: list[dict[str, Any]], attempts: int, intent: ExerciseIntent,
    ctx: ActiveContext, plan: PatternPlan,
) -> GeneratedExercise:
    from improvisation_motif import _midi_from_note, chord_tone_names
    from music_coach_ami.exercise_context import key_mode, key_tonic

    span, info, motif = res.span, res.info or {}, example["motif"]
    key = _clean(info.get("concert_key")) or ctx.concert_key
    chords = [str(c) for c in span.chords]
    midi = [int(m) for m in motif.get("midi") or []]
    notes = [str(n) for n in motif.get("notes") or []]
    assign = [int(i) for i in motif.get("note_chord_index") or []]
    roles, chord_roles = [], []
    for m, idx in zip(midi, assign):
        chord = chords[idx]
        names = chord_tone_names(chord, reference_key=key) or []
        pcs = [_midi_from_note(n, 4) % 12 for n in names]
        root = pcs[0] if pcs else 0
        roles.append(_DEGREE_LABEL[(m - root) % 12])
        chord_roles.append(_chord_role_for_pc(pcs, m % 12))
    meter = _clean(motif.get("meter")) or ctx.meter or "4/4"
    bars = int(example.get("handoff", {}).get("loop_bars") or 0) or sum(int(t.get("bars") or 1) for t in motif.get("chord_timeline") or [])
    core = {"span": span.span_id, "midi": midi, "chords": chords, "example": example.get("handoff", {}).get("example_id")}
    ex_id = "ex-" + hashlib.sha1(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    arrivals = []
    for t in motif.get("chord_timeline") or []:
        first = int(t.get("first_note", 0))
        if 0 <= first < len(notes):
            arrivals.append({"chord": _clean(t.get("chord")), "note": notes[first], "role": chord_roles[first], "beat": 1})
    facts: dict[str, Any] = {
        "span": dict(info), "evidence": [dict(e) for e in example.get("evidence") or []], "arrivals": arrivals,
        "degrees": [{"note": n, "degree": d, "chord_role": r, "chord": chords[i]} for n, d, r, i in zip(notes, roles, chord_roles, assign)],
        "mission_label": example.get("mission_label"), "mission_brief": example.get("mission_brief"),
        "pattern_plan": plan.to_dict(),
        "mission_example": example,  # the exact example "Open in Missions" stages
        "articulation_requested": intent.articulation_request, "dynamics_requested": intent.dynamics_request,
        "articulation_dynamics_applied": False,
    }
    prov = {
        "engine": ENGINE_NAME, "engine_version": ENGINE_VERSION, "engine_function": "generate_mission_span_example",
        "mission_vocabulary": plan.mission_id, "span_id": span.span_id, "span_selection": dict(info), "attempts": attempts,
        "pitch_vocabulary": plan.vocabulary, "technique": plan.technique, "pattern_plan": plan.to_dict(),
        "example_id": example.get("handoff", {}).get("example_id"), "level": ctx.level, "level_source": ctx.level_source,
        "concert_key": key, "key_source": ctx.key_source, "chord_source": info.get("selection_source", ""),
        "explicit_fields": dict(intent.explicit_fields), "route": intent.engine_route, "route_reason": intent.route_reason,
    }
    ctx_span = replace(ctx, concert_key=key, span=dict(info), field_sources={**ctx.field_sources, "chord": info.get("selection_source", "")})
    ex = GeneratedExercise(
        id=ex_id, intent=intent, context=ctx_span, engine=ENGINE_NAME, engine_detail=plan.mission_id,
        vocabulary=plan.vocabulary, seed=int(example.get("idea") or 0), attempts=attempts, collection_label=plan.title,
        collection_notes=[], chord=" → ".join(chords), tonic=key_tonic(key), mode=key_mode(key), notes=notes, midi=midi,
        rhythm_events=[dict(e) for e in (motif.get("rhythm_events") or [])],
        rhythm_symbols=[str(s) for s in motif.get("rhythm_symbols") or []], meter=meter, bars=bars, roles=roles,
        chord_roles=chord_roles, chord_assignment=assign, chords=chords, articulation=[""] * len(notes),
        dynamics=[""] * len(notes), accents=[False] * len(notes), slur_groups=[0] * len(notes),
        validation={"ok": all(c["ok"] for c in checks), "checks": checks}, explanation_facts=facts, provenance=prov,
    )
    ex.written = {"applied": False, "key": key, "chord": ex.chord, "notes": list(notes), "midi": list(midi), "semitones": 0, "octave_shift": 0}
    return ex


# ---------------------------------------------------------------- the card


def _guitar_family(instrument: str) -> bool:
    from improvisation_missions import _instrument_family

    return _instrument_family(instrument) == "guitar"


def render_span_abc(ex: GeneratedExercise, *, bpm: int, title: str, instrument: str) -> str:
    from improvisation_motif import build_motif_abc, notation_clef_for_instrument

    motif = ex.explanation_facts["mission_example"]["motif"]
    return build_motif_abc(
        motif, key_center=_clean(ex.context.span.get("key_center")) or ex.context.concert_key, bpm=int(bpm or 96), title=title,
        clef=notation_clef_for_instrument(instrument),
    )


def span_tab(ex: GeneratedExercise) -> str:
    from improvisation_motif import build_motif_guitar_tab

    return build_motif_guitar_tab(ex.explanation_facts["mission_example"]["motif"])


def _evidence(ex: GeneratedExercise, check: str) -> list[dict[str, Any]]:
    return [e for e in ex.explanation_facts.get("evidence") or [] if e.get("check") == check]


def span_prose(
    ex: GeneratedExercise, plan: PatternPlan, *, display_instrument: str, tab: str = ""
) -> dict[str, Any]:
    ctx, f = ex.context, ex.explanation_facts
    info = ctx.span or {}
    chords = [_pretty(c) for c in info.get("player_chords") or ex.chords]
    romans = " – ".join(info.get("roman") or [])
    label = _clean(info.get("relationship_label"))
    rel = label or romans
    key_text = {"explicit_request": "named in your request", "mission_practice_key": "your Mission Practice Key",
                "practice_chart_key": "your Practice key"}.get(ctx.key_source, ctx.key_source)
    where = f" · {info['section']}" if info.get("section") else ""
    lines = [
        f"**Chords:** {_ARROW.join(chords)}" + (f" — {rel}" if rel else "") + where,
        f"**Key:** {ctx.concert_key} ({key_text})",
    ]
    arrivals = f.get("arrivals") or []
    if arrivals:
        parts = [f"{_pretty(a['chord'])} → **{_pretty(a['note'])}**" + (f" (the {'3rd' if a['role'] == '3' else '7th' if a['role'] == '7' else a['role']})" if a.get("role") else "")
                 for a in arrivals]
        lines.append("**Where it lands (beat 1 of each chord):** " + "; ".join(parts))
    moves = _evidence(ex, "guide tones voice-led")
    if moves:
        lines.append("**Voice leading:** " + "; ".join(f"{_pretty(m['where'])}: {m['text']}" for m in moves))
    resolutions = [e for e in f.get("evidence") or [] if e.get("check") == "7th → 3rd resolution"]
    if resolutions:
        lines.append("**Result:** " + ", ".join(e["text"] for e in resolutions) + " (a 7th falling to the next chord's 3rd)")
    if plan.mission_id != SPAN_MISSION_ID:
        evidence = [e for e in f.get("evidence") or [] if _clean(e.get("text"))]
        if evidence:
            lines.append("**Why it fits:** " + "; ".join(_clean(e["text"]) for e in evidence))
    if ex.intent.span_length == 0 and info.get("length_source") == "default_two":
        lines.append(f"_You didn't say how many chords, so I used {info.get('length')} — ask for \"three chords\" or \"the ii–V–I\" for a longer line._")
    if ex.intent.expression:
        lines.append("_Articulation and dynamics aren't applied to multi-chord exercises yet, so this line is unmarked._")
    if ex.intent.level_override:
        lines.append("_Multi-chord exercises follow your current level for now._")
    spans_text = []
    for idx, seg_chord in enumerate(ex.chords):
        seg = [n for n, a in zip(ex.notes, ex.chord_assignment) if a == idx]
        spans_text.append(f"{_pretty(seg_chord)}: {_EN.join(_pretty(n) for n in seg)}")
    if plan.mission_id == SPAN_MISSION_ID:
        steps = [
            "**Guide-tone line** — read the staff notation below" + (", with Guitar TAB under it." if tab else "."),
            "Notes by chord: " + " | ".join(spans_text),
            f"Play it slowly, one chord at a time. Land the first note of each chord on beat 1 — that is the guide tone — then loop the whole line on **{display_instrument}**.",
            "To practise it over a backing track, press **Open in Missions**, then **Practice in Backing Jam**.",
        ]
    else:
        steps = [
            f"**{plan.title}** — read the staff notation below" + (", with Guitar TAB under it." if tab else "."),
            "Notes by chord: " + " | ".join(spans_text),
            f"Play it slowly on **{display_instrument}**, keeping each note with the chord shown above it before you loop the whole line.",
            "To practise it over a backing track, press **Open in Missions**, then **Practice in Backing Jam**.",
        ]
    listen = list(plan.listen_for)
    direct = f"**Try this {plan.title.lower()} across {len(ex.chords)} chords:**\n\n" + "\n\n".join(lines)
    if tab:
        direct += "\n\n**Guitar TAB**\n\n```\n" + tab.strip("\n") + "\n```"
    return {"direct_answer": direct, "practice_steps": steps, "what_to_listen_for": listen, "title": plan.title}


# ---------------------------------------------------------------- payload (called from exercise_bridge)


def limitation_payload(
    message: str, intent: ExerciseIntent, ctx: ActiveContext, base_diag: dict[str, Any], info: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "direct_answer": message,
        "practice_steps": [
            "Your Practice Key, selected chord and Missions are unchanged.",
            "Try a guide-tone, pentatonic, chord-tone, chromatic-approach, or enclosure exercise over the next two or three chords.",
        ],
        "what_to_listen_for": [], "suggested_next_action": "Ask again with a different span, or generate it on the Missions page (Target scope: 2 or 3 chords).",
        "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {**base_diag, "exercise_failed": True, "exercise_failure_reason": message, "exercise_span": info or {"resolved": False}},
    }


def compose_span_payload(
    req: Any, idea: Any, intent: ExerciseIntent, ctx: ActiveContext, written_ctx: Any, *, session_ref: Any, display_instrument: str, bpm: int,
) -> dict[str, Any]:
    from music_coach_ami.exercise_bridge import store_last_exercise

    plan = span_pattern_plan(intent)
    base_diag = {
        "musical_idea_content": True, "exercise_bridge": True, "exercise_span_request": True, "exercise_intent": intent.to_dict(),
        "exercise_context": ctx.to_dict(), "practice_concert_key": ctx.concert_key, "written_key": ctx.written_key,
        "resolved_instrument": ctx.instrument, "notation_instrument": ctx.notation_instrument, "requested_object": intent.form,
        "resolved_object": intent.form, "generation_strategy": ENGINE_NAME, "pattern_plan": plan.to_dict(),
    }
    res = resolve_span(session_ref, ctx, intent, plan)
    if not res.ok:
        return limitation_payload(res.message, intent, ctx, base_diag, res.info)
    example, checks, attempts, reason = generate_span_example(res, ctx, intent, plan)
    if example is None:
        return limitation_payload(
            f"I couldn't build a {plan.title.lower()} across {_ARROW.join(res.project(c) for c in res.span.chords)} that passed "
            f"my checks ({reason}). Nothing was changed.", intent, ctx, base_diag, res.info,
        )
    ex = build_span_exercise(res, example, checks, attempts, intent, ctx, plan)
    guitar = _guitar_family(ctx.instrument or display_instrument)
    tab = span_tab(ex) if guitar else ""
    prose = span_prose(ex, plan, display_instrument=display_instrument, tab=tab)
    abc = render_span_abc(ex, bpm=bpm, title=f"{plan.title} — {ex.chord}", instrument=ctx.notation_instrument or ctx.instrument)
    stored = store_last_exercise(session_ref, ex)
    action = {
        "kind": plan.action_kind, "exercise_id": ex.id, "label": "Open in Missions", "mission_id": plan.mission_id,
        "span_id": res.span.span_id, "scope": res.info["scope"], "progression_key": res.info["progression_key"],
        "concert_key": res.info["concert_key"], "chords": list(ex.chords), "section": res.span.section_label,
        "start_event": res.span.start_event, "example": example,
    }
    diag = {
        **base_diag, "exercise_context": ex.context.to_dict(), "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(),
        "exercise_validation": ex.validation, "notation_abc_present": bool(abc), "guitar_tab_present": bool(tab),
        "last_exercise_stored": stored, "difficulty_level": ctx.level, "bars_generated": ex.bars, "exercise_span": res.info,
        "written_music_context": written_ctx.to_diagnostics() if written_ctx is not None else {},
        "open_in_missions": action,
    }
    return {
        "direct_answer": prose["direct_answer"], "practice_steps": prose["practice_steps"],
        "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Open it in Missions to hear it over a backing track, or ask for the next three chords.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [], "diagnostics": diag,
    }


# ---------------------------------------------------------------- Open in Missions


def _with_example(history: list[dict[str, Any]], example: dict[str, Any]) -> list[dict[str, Any]]:
    """The Missions idea history with this example once (opening the same card again adds nothing)."""
    midi = example["motif"].get("midi")
    if history and (history[-1].get("motif") or {}).get("midi") == midi:
        return history
    return (history + [{"motif": example["motif"], "difficulty": "normal"}])[-6:]


def open_exercise_in_missions(session: Any, action: dict[str, Any]) -> dict[str, Any]:
    """Stage the AMI example as the Missions span example and go to Creative -> Missions. Never regenerates.

    The example, span id, scope, chosen Mission and Practice Key are written exactly as the Missions page itself keeps them,
    so the page, its Backing handoff and Return to Mission / Return to Creative treat it like an example made there. Refuses
    (without touching anything) when the song or progression has changed since the exercise was made.
    """
    from improvisation_intelligence_ui import _mission_improv_ctx_from_session, resolve_span_options
    from improvisation_motif import resolve_improv_section_rows
    from mission_span_ui import (
        MISSION_AMI_SPAN_PICK_KEY,
        MISSION_SPAN_WIDGET_PREFIX,
        MISSION_TARGET_SCOPE_STATE_KEY,
        MISSION_TARGET_SCOPE_WIDGET_KEY,
        SPAN_MISSION_CHOICE_KEY,
        SPAN_MISSION_PICK_KEY,
        SPAN_MISSION_STATE_KEY,
        span_mission_context,
    )

    example = action.get("example") if isinstance(action, dict) else None
    if not isinstance(example, dict) or not isinstance(example.get("motif"), dict):
        return {"ok": False, "message": "That exercise can no longer be opened — ask for it again."}
    mission_id = _clean(action.get("mission_id"))
    if (
        mission_id not in SUPPORTED_SPAN_MISSION_IDS
        or _clean(example.get("mission_id")) != mission_id
        or _clean((example.get("handoff") or {}).get("mission_id")) != mission_id
    ):
        return {"ok": False, "message": "That exercise's Mission no longer matches its generated example — ask for it again."}
    sess = _session(session)
    scope = _clean(action.get("scope"))
    probe = dict(sess)
    probe["improv_intelligence_tab"] = "Missions"
    probe["creative_improv_intelligence_tab"] = "Missions"
    improv_ctx = _mission_improv_ctx_from_session(probe)
    rows = resolve_improv_section_rows(probe, improv_ctx) if improv_ctx is not None else []
    opts = resolve_span_options(probe, improv_ctx, rows, scope=scope, level=_clean(probe.get("level")) or "Intermediate") if rows else None
    span = next((s for s in (opts.ordered if opts else []) if s.span_id == action.get("span_id")), None)
    if span is None or opts.progression_key != action.get("progression_key"):
        return {"ok": False, "message": "The song or progression has changed since this exercise was made, so it can't be opened "
                                        "in Missions. Ask for it again on the current song."}
    from span_motif_engine import _level as engine_level

    level = engine_level(_clean(probe.get("level")) or "Intermediate")
    style = _clean(probe.get("improv_span_song_style")) or "default"
    prior = sess.get(SPAN_MISSION_STATE_KEY) if isinstance(sess.get(SPAN_MISSION_STATE_KEY), dict) else {}
    history = list(prior.get("history") or []) if prior.get("context") == span_mission_context(
        mission_id, span.span_id, level, getattr(improv_ctx, "song_title", ""), style
    ) else []
    state = {
        "context": span_mission_context(mission_id, span.span_id, level, getattr(improv_ctx, "song_title", ""), style),
        "bucket": "normal", "ideas": {}, "history": _with_example(history, example),
        "example": example,
        # The Missions page adopts this example even if its own style/level inputs differ from AMI's.
        "ami_handoff": {"exercise_id": action.get("exercise_id"), "mission_id": mission_id,
                        "chords": list(span.chords), "section": span.section_label},
    }
    sess[MISSION_TARGET_SCOPE_STATE_KEY] = scope
    sess.pop(MISSION_TARGET_SCOPE_WIDGET_KEY, None)
    # The page's span picker selects the span by chords + section (one-shot), then keeps it in its own selection state.
    sess[MISSION_AMI_SPAN_PICK_KEY] = {"scope": scope, "chords": list(span.chords), "section": span.section_label,
                                       "start_event": span.start_event}
    sess.pop(f"{MISSION_SPAN_WIDGET_PREFIX}_{opts.length}", None)
    sess[SPAN_MISSION_CHOICE_KEY] = mission_id
    sess.pop(SPAN_MISSION_PICK_KEY, None)
    sess[SPAN_MISSION_STATE_KEY] = state
    sess.pop("improv_span_mission_abc", None)
    try:
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

        sess[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Missions"
    except ImportError:
        sess["creative_improv_intelligence_tab"] = "Missions"
    sess["improv_intelligence_tab"] = "Missions"
    sess["creative_lab_analysis_mode"] = "Improvisation Intelligence"
    sess.pop("_improv_tab_user_touched", None)
    try:
        from app_ui import navigate_studio_page

        navigate_studio_page(sess, "creative")
    except Exception:
        sess["studio_page"] = "creative"
    return {"ok": True, "message": "", "span_id": span.span_id, "scope": scope}
