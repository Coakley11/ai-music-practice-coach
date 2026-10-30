"""AMI M1d: scale-pattern exercises become structured, revisable ``GeneratedExercise`` objects.

``generate_scale_pattern`` (musical_idea_engine) stays the only thing that chooses notes. This module

* wraps its concert-pitch result in a ``GeneratedExercise`` (``build_exercise``) without changing a note, a duration or a
  byte of the notation the player already gets, and stores it in the working state so later instructions act on it;
* re-renders a stored scale-pattern exercise (``render``) through the same written-pitch transposition and the same ABC
  writer the first answer used, so a tempo / accent revision differs from the original only where it was asked to;
* answers the follow-ups the engine can honour (``compose_scale_followup``): harder, easier, accents / articulation.
  Anything else is refused in words and the exercise is left as it was.

The exercise's harmony is the key centre the engine actually used. The engine builds one scale over the whole pattern and
attaches no chord to any note, so no chord relationship is claimed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, replace
from fractions import Fraction
from typing import Any

from music_coach_ami.exercise_model import (
    ROUTE_LEGACY,
    VOCAB_DEGREE_PATTERN,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
)

ENGINE = "musical_idea_engine"
ENGINE_DETAIL = "generate_scale_pattern"

# Difficulty ladder, expressed only in parameters the engine already honours (rhythm unit and interval cell). The first
# three rungs are the engine's own beginner / intermediate / advanced behaviour; the last two go past "advanced".
LADDER: tuple[dict[str, str], ...] = (
    {"label": "Beginner", "difficulty": "beginner", "rhythm": "quarter", "interval_pattern": "1-2-3-4"},
    {"label": "Intermediate", "difficulty": "intermediate", "rhythm": "", "interval_pattern": "1-2-3-4"},
    {"label": "Advanced", "difficulty": "advanced", "rhythm": "eighth", "interval_pattern": "1-2-3-4"},
    {"label": "Advanced+", "difficulty": "advanced", "rhythm": "eighth", "interval_pattern": "1-3-2-4"},
    {"label": "Advanced++", "difficulty": "advanced", "rhythm": "sixteenth", "interval_pattern": "1-3-2-4"},
)
_RUNG_BY_LEVEL = {"beginner": 0, "intermediate": 1, "advanced": 2}

_EVENT_FIELDS = ("spelled", "octave", "duration", "bar_index", "beat", "articulation", "scale_degree", "pitch_class", "chord",
                 "role", "cell_index", "domain", "tone_role", "slur_group")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _sha(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def is_scale_pattern(ex: GeneratedExercise | None) -> bool:
    return bool(ex is not None and ex.engine == ENGINE and ex.engine_detail == ENGINE_DETAIL)


# ---------------------------------------------------------------- composition <-> dicts


def serialize_events(events: Any) -> list[dict[str, Any]]:
    return [{f: getattr(e, f, None) for f in _EVENT_FIELDS} for e in events]


def _events_from(rows: list[dict[str, Any]]) -> tuple[Any, ...]:
    from music_coach_ami.musical_idea_engine import MusicalEvent

    return tuple(MusicalEvent(**{f: r.get(f) for f in _EVENT_FIELDS if f in r}) for r in rows)


def _is_rest(ev: Any) -> bool:
    return str(ev.duration or "").lower().startswith("rest") or not str(ev.spelled or "").strip()


def _rhythm_events(events: Any, meter: str) -> list[dict[str, Any]]:
    from music_coach_ami.musical_idea_engine import _dur_beats

    out: list[dict[str, Any]] = []
    cursor, note_i = Fraction(0), 0
    for ev in events:
        dur = Fraction(_dur_beats(ev.duration, meter)).limit_denominator(12)
        rest = _is_rest(ev)
        out.append({"on": str(cursor), "dur": str(dur), "w": str(dur), "rest": rest, "tup": None, "ts": False,
                    "n": None if rest else note_i})
        if not rest:
            note_i += 1
        cursor += dur
    return out


def _articulation_string(art: str, accent: bool) -> str:
    return " ".join(x for x in ("accent" if accent else "", _clean(art)) if x)


def composition_of(ex: GeneratedExercise) -> Any:
    """The concert-pitch ``MusicalIdeaComposition`` this exercise stands for, with its current expression applied."""
    from music_coach_ami.musical_idea_engine import MusicalIdeaComposition
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    rows = copy.deepcopy(ex.provenance["events"])
    note_i = 0
    for row in rows:
        if _clean(row.get("spelled")) and not str(row.get("duration") or "").lower().startswith("rest"):
            art = ex.articulation[note_i] if note_i < len(ex.articulation) else ""
            acc = bool(ex.accents[note_i]) if note_i < len(ex.accents) else False
            row["articulation"] = _articulation_string(art, acc)
            row["slur_group"] = int(ex.slur_groups[note_i]) if note_i < len(ex.slur_groups) else 0
            note_i += 1
    prov = ex.provenance
    return MusicalIdeaComposition(
        events=_events_from(rows), reference_key=_clean(prov.get("reference_key")) or ex.tonic, meter=ex.meter, bars=ex.bars,
        object_type=_clean(prov.get("object_type")) or "pattern", style=_clean(prov.get("style")),
        notation_profile=notation_profile_for_instrument(ex.context.notation_instrument or ex.context.instrument),
        strategy=_clean(prov.get("strategy")), tonic=ex.tonic, tonality=ex.mode,
        scale_spelling=tuple(ex.collection_notes), validation_errors=tuple(prov.get("validation_errors") or ()),
        validation_ok=bool(prov.get("validation_ok", True)),
    )


def render(ex: GeneratedExercise, *, bpm: int) -> tuple[str, Any]:
    """(abc, written-domain composition) through exactly the path the first answer took."""
    from music_coach_ami.musical_idea_engine import composition_to_abc
    from music_coach_ami.musical_idea_knowledge import _transpose_composition_preserving_degrees

    comp = composition_of(ex)
    ctx = ex.context
    if ctx.written_transposition_applied and ctx.written_key and ctx.written_key.rstrip("m") != _clean(ex.tonic).rstrip("m"):
        comp = _transpose_composition_preserving_degrees(
            comp, ctx.written_key, int(ctx.transposition_semitones), comp.notation_profile,
            concert_key=_clean(ex.provenance.get("practice_concert_key")) or ctx.concert_key,
        )
    abc, _diag = composition_to_abc(comp, title=_clean(ex.provenance.get("title")) or "Scale pattern", bpm=int(bpm or 96))
    return abc, comp


# ---------------------------------------------------------------- building the exercise


def _validation(comp_concert: Any, notes: list[str], midi: list[int], profile: Any, rhythm: list[dict[str, Any]]) -> dict[str, Any]:
    from music_theory import pitch_class_from_spelled_note

    scale_pcs = {pitch_class_from_spelled_note(n) % 12 for n in comp_concert.scale_spelling}
    low, high = int(getattr(profile, "midi_low", 0) or 0), int(getattr(profile, "midi_high", 127) or 127)
    beats = sum(Fraction(e["dur"]) for e in rhythm)
    from music_coach_ami.musical_idea_engine import _beats_per_bar

    per_bar = Fraction(_beats_per_bar(comp_concert.meter or "4/4")).limit_denominator(4)
    checks = [
        {"name": "engine_validation", "ok": bool(comp_concert.validation_ok), "detail": "; ".join(comp_concert.validation_errors) or "passed"},
        {"name": "inside_scale", "ok": all(pitch_class_from_spelled_note(n) % 12 in scale_pcs for n in notes),
         "detail": " ".join(comp_concert.scale_spelling)},
        {"name": "durations_fill_bars", "ok": beats == per_bar * int(comp_concert.bars), "detail": f"{beats} beats / {comp_concert.bars} bars"},
        {"name": "one_midi_per_note", "ok": len(notes) == len(midi) and bool(notes), "detail": f"{len(notes)} notes"},
    ]
    # Reported, not gating: the engine's own range check (engine_validation) is the authority; the profile window is in the
    # notated domain, so an octave-transposing instrument's sounding pitches are not directly comparable to it.
    in_window = all(low - 1 <= m <= high + 1 for m in midi)
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "info": {"sounding_inside_notation_profile_window": in_window, "profile_window": [low, high]}}


def context_for(*, written_ctx: Any, concert_key: str, instrument: str, notation_instrument: str, song_title: str, section: str,
                level: str, practice_focus: str, meter: str, bpm: int, tonic: str) -> ActiveContext:
    """The context the engine actually used. The Practice Key stays the app's canonical value; the scale's own tonic is
    recorded beside it, not in its place."""
    low = _clean(level).lower()
    label = "Advanced" if "advanced" in low or "hard" in low else "Beginner" if ("begin" in low or "easy" in low or "simple" in low) else "Intermediate"
    return ActiveContext(
        concert_key=_clean(concert_key) or _clean(tonic) or "C", key_source="practice_chart_key", key_candidates={"scale_tonic": _clean(tonic)},
        written_key=_clean(getattr(written_ctx, "written_key", "")),
        written_transposition_applied=bool(getattr(written_ctx, "written_transposition_applied", False)),
        transposition_semitones=int(getattr(written_ctx, "transposition_semitones", 0) or 0),
        instrument=instrument, notation_instrument=notation_instrument, song_title=song_title, section=section, selected_chord="",
        chord_source="none", level=label, level_source="request", meter=meter or "4/4", tempo_bpm=int(bpm or 96),
        practice_focus=practice_focus, field_sources={"concert_key": "practice_chart_key", "level": "request", "chord": "none"},
    )


def rung_of(idea: Any) -> int:
    interval = _clean(getattr(idea, "interval_pattern", "")).lower()
    rhythm = _clean(getattr(idea, "rhythm", "")).lower()
    low = _clean(getattr(idea, "difficulty", "") or getattr(idea, "level", "")).lower()
    base = 2 if "advanced" in low or "hard" in low else 0 if ("begin" in low or "easy" in low or "simple" in low) else 1
    if rhythm in ("sixteenth", "busy"):
        return 4
    if interval in ("1-3-2-4", "1-3-4-2") and base >= 2:
        return 3
    return base


def build_exercise(
    composition_concert: Any, composition_written: Any, idea: Any, *, ctx: ActiveContext, question: str, title: str,
    written_note: str = "",
) -> GeneratedExercise:
    """Wrap the engine's own result. Nothing is recomputed: pitches come from the events, the written projection from
    the composition the player was actually shown."""
    from music_coach_ami.musical_idea_engine import _midi

    events = tuple(composition_concert.events)
    sounding = [e for e in events if not _is_rest(e)]
    notes = [_clean(e.spelled) for e in sounding]
    midi = [_midi(e.spelled, int(e.octave)) for e in sounding]
    meter = composition_concert.meter or "4/4"
    rhythm = _rhythm_events(events, meter)
    written_sounding = [e for e in composition_written.events if not _is_rest(e)]
    degree_labels = [str(e.scale_degree) if e.scale_degree else "" for e in sounding]
    n = len(notes)
    intent = ExerciseIntent(
        raw_question=question, vocabulary=VOCAB_DEGREE_PATTERN, form="pattern",
        scope="section" if getattr(idea, "song_relative", False) else "single_chord", explicit_key=_clean(getattr(idea, "explicit_key", "")),
        length_bars=int(composition_concert.bars), engine_route=ROUTE_LEGACY,
        route_reason="scale pattern: AMI's own generator; structured by the M1d adapter",
    )
    prov = {
        "engine": ENGINE, "engine_function": ENGINE_DETAIL, "route": ROUTE_LEGACY, "events": serialize_events(events),
        "idea": asdict(idea), "title": title, "reference_key": composition_concert.reference_key,
        "object_type": composition_concert.object_type, "style": composition_concert.style, "strategy": composition_concert.strategy,
        "validation_ok": bool(composition_concert.validation_ok), "validation_errors": list(composition_concert.validation_errors),
        "practice_concert_key": ctx.concert_key, "rung": rung_of(idea), "written_note": written_note,
        "harmony": "key centre only: the engine attaches no chord to any note",
    }
    core = {"notes": notes, "midi": midi, "rhythm": [(r["on"], r["dur"]) for r in rhythm], "tonic": composition_concert.tonic,
            "tonality": composition_concert.tonality, "engine": ENGINE}
    profile = composition_concert.notation_profile
    ex = GeneratedExercise(
        id="ex-" + _sha(core), intent=intent, context=ctx, engine=ENGINE, engine_detail=ENGINE_DETAIL, vocabulary=VOCAB_DEGREE_PATTERN,
        collection_label=f"{composition_concert.tonic} {composition_concert.tonality} scale".replace("  ", " ").strip(),
        collection_notes=list(composition_concert.scale_spelling), chord="", tonic=_clean(composition_concert.tonic),
        mode=_clean(composition_concert.tonality), notes=notes, midi=midi, rhythm_events=rhythm,
        rhythm_symbols=[], meter=meter, bars=int(composition_concert.bars), roles=degree_labels, chord_roles=[""] * n,
        chord_assignment=[0] * n, chords=[], articulation=[""] * n, dynamics=[""] * n, accents=[False] * n, slur_groups=[0] * n,
        validation=_validation(composition_concert, notes, midi, profile, rhythm),
        explanation_facts={"scale": list(composition_concert.scale_spelling), "degrees": degree_labels,
                           "harmony": prov["harmony"]},
        provenance=prov,
    )
    ex.written = {
        "applied": bool(ctx.written_transposition_applied), "key": ctx.written_key or ctx.concert_key, "chord": "",
        "notes": [_clean(e.spelled) for e in written_sounding], "midi": [_midi(e.spelled, int(e.octave)) for e in written_sounding],
        "semitones": int(ctx.transposition_semitones or 0), "octave_shift": 0,
    }
    return ex


# ---------------------------------------------------------------- follow-ups


def _refusal(reason: str, fu: Any, parent: GeneratedExercise) -> dict[str, Any]:
    return {
        "direct_answer": reason,
        "practice_steps": ["Your previous exercise is unchanged — for a scale pattern I can make it harder or easier, add accents or "
                           "articulation, change the tempo, and undo or redo."],
        "what_to_listen_for": [], "suggested_next_action": "", "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {"musical_idea_content": True, "exercise_followup": True, "followup_kind": fu.kind, "followup_utterance": fu.raw,
                        "parent_exercise_id": parent.id, "exercise_followup_failed": True, "exercise_followup_failure_reason": reason},
    }


_UNSUPPORTED_TEXT = {
    "variation": "another variation", "same_rhythm_new_notes": "new notes on the same rhythm", "same_notes_new_rhythm": "a new rhythm on the same notes",
    "move": "moving it up or down", "sequence": "sequencing it", "regenerate_in_current_context": "rebuilding it for the current chord",
    "develop": "that kind of development",
}


def _header(ex: GeneratedExercise, parent: GeneratedExercise) -> str:
    """The shared follow-up header, without dev's note-count difficulty score: that score is not a measure of this ladder
    (a faster rhythm over the same shape can score lower), so it is not shown."""
    from music_coach_ami.exercise_followup import _followup_header

    text = _followup_header(ex, parent)
    return chr(10).join(re.sub(r" \(difficulty score .*?\)\.", ".", line) for line in text.split(chr(10)))


def _prose(ex: GeneratedExercise, display_instrument: str) -> dict[str, Any]:
    from music_coach_ami.musical_idea_engine import play_summary

    comp = composition_of(ex)
    written_note = _clean(ex.provenance.get("written_note"))
    title = _clean(ex.provenance.get("title"))
    direct = f"**Try this {ex.bars}-bar {ex.mode or 'scale'} pattern in {ex.tonic}:**"
    if written_note:
        direct += f"\n\n{written_note}"
    steps = [f"**Pattern** — read the staff notation below.", f"Use a comfortable register on **{display_instrument}**.",
             "**How to play it**", *play_summary(comp)]
    return {"title": title, "direct_answer": direct, "practice_steps": steps,
            "what_to_listen_for": ["Even rhythm across the bar line", "Clear phrase shape", "Tone and articulation match your practice focus"]}


def _ladder_step(parent: GeneratedExercise, step: int) -> tuple[dict[str, str] | None, str]:
    cur = int(parent.provenance.get("rung", 1))
    new = cur + step
    if new < 0:
        return None, "This is already the easiest scale pattern I build (Beginner), so I haven't changed it."
    if new >= len(LADDER):
        return None, "This is already the hardest scale pattern I build (sixteenth notes in a 1-3-2-4 shape), so I haven't changed it."
    return LADDER[new], ""


def _regenerate(parent: GeneratedExercise, rung: dict[str, str], *, bpm: int) -> tuple[GeneratedExercise | None, str]:
    from music_coach_ami.musical_idea_engine import generate_scale_pattern
    from music_coach_ami.musical_idea_knowledge import _transpose_composition_preserving_degrees
    from music_coach_ami.musical_idea_request import MusicalIdeaRequest

    raw = dict(parent.provenance["idea"])
    names = set(MusicalIdeaRequest.__dataclass_fields__)
    idea = MusicalIdeaRequest(**{k: v for k, v in raw.items() if k in names})
    idea = replace(idea, difficulty=rung["difficulty"], level=rung["difficulty"], rhythm=rung["rhythm"],
                   interval_pattern=rung["interval_pattern"])
    notation_inst = parent.context.notation_instrument or parent.context.instrument
    concert = generate_scale_pattern(idea, notation_instrument=notation_inst)
    ctx = replace(parent.context, level=rung["label"].rstrip("+") if rung["label"].startswith("Advanced") else rung["label"],
                  level_source="followup_difficulty")
    written = concert
    if ctx.written_transposition_applied and ctx.written_key and ctx.written_key.rstrip("m") != _clean(concert.tonic).rstrip("m"):
        written = _transpose_composition_preserving_degrees(
            concert, ctx.written_key, int(ctx.transposition_semitones), concert.notation_profile,
            concert_key=_clean(parent.provenance.get("practice_concert_key")) or ctx.concert_key,
        )
    ex = build_exercise(concert, written, idea, ctx=ctx, question=parent.intent.raw_question, title=_clean(parent.provenance.get("title")),
                        written_note=_clean(parent.provenance.get("written_note")))
    ex.provenance["rung"] = LADDER.index(rung)
    if not ex.validation.get("ok"):
        bad = next((c for c in ex.validation["checks"] if not c["ok"]), {})
        return None, f"I couldn't build that version safely ({bad.get('name', 'validation')} failed), so nothing was changed."
    return ex, ""


def compose_scale_followup(fu: Any, parent: GeneratedExercise, *, session_ref: Any, instrument: str, notation_instrument: str,
                           display_instrument: str, bpm: int) -> dict[str, Any]:
    """The follow-ups a scale-pattern exercise supports. ``bpm`` is the working tempo."""
    from music_coach_ami.exercise_bridge import store_last_exercise
    from music_coach_ami.exercise_expression import apply_expression, has_rules, merge_requests
    from music_coach_ami.exercise_followup import (
        KIND_EASIER, KIND_EXPRESSION, KIND_HARDER, _carry_expression, _request_of, _stamp,
    )

    base_diag = {"musical_idea_content": True, "exercise_followup": True, "followup_kind": fu.kind, "followup_utterance": fu.raw,
                 "parent_exercise_id": parent.id, "scale_pattern_exercise": True}
    if fu.kind not in (KIND_HARDER, KIND_EASIER, KIND_EXPRESSION):
        what = _UNSUPPORTED_TEXT.get(fu.kind, "that")
        return _refusal(f"I can't do {what} to a scale pattern yet. Your exercise is unchanged.", fu, parent)
    if fu.explicit_key or fu.explicit_chord or fu.current_context or fu.level:
        return _refusal("I can't change the key, chord or level of a scale pattern that way yet — say “harder” or “easier”. "
                        "Your exercise is unchanged.", fu, parent)
    live = {"session_ref": session_ref, "instrument": instrument, "notation_inst": notation_instrument}
    if fu.kind == KIND_EXPRESSION:
        new_req = fu.expression or {}
        if not has_rules(new_req):
            return _refusal("I couldn't tell what articulation to apply. Your exercise is unchanged.", fu, parent)
        if new_req.get("dynamics"):
            return _refusal("Dynamics (loud and soft) aren't notated on scale patterns yet — I can add accents, staccato or "
                            "tenuto. Your exercise is unchanged.", fu, parent)
        needs_chord_roles = any(r.get("rule") == "role" and r.get("role") != "downbeat" for r in new_req.get("articulation") or [])
        if needs_chord_roles:
            return _refusal("A scale pattern has no chord tones, guide tones or other chord roles to target — try “accent the downbeats” or "
                            "“accent every second note”. Your exercise is unchanged.", fu, parent)
        merged = merge_requests(_request_of(parent), new_req)
        ex = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
        apply_expression(ex, merged, source={"articulation": "explicit", "dynamics": "inherited"})
        ex.intent = replace(ex.intent, expression=merged)
        ex = _stamp(ex, parent, fu, inherited=["notes", "rhythm", "key", "tempo"], changed=["articulation"], live=live)
    else:
        rung, why = _ladder_step(parent, 1 if fu.kind == KIND_HARDER else -1)
        if rung is None:
            return _refusal(why, fu, parent)
        ex, why = _regenerate(parent, rung, bpm=bpm)
        if ex is None:
            return _refusal(why, fu, parent)
        ex = _stamp(ex, parent, fu, inherited=["key", "scale", "tempo"], changed=["level", "notes", "rhythm"],
                    extra={"level_from": LADDER[int(parent.provenance.get("rung", 1))]["label"], "level_to": rung["label"],
                               }, live=live)
        _carry_expression(parent, ex, fu)
    ex.tempo_bpm = int(bpm)
    abc, _comp = render(ex, bpm=int(bpm))
    prose = _prose(ex, display_instrument)
    stored = store_last_exercise(session_ref, ex)
    return {
        "direct_answer": "\n\n".join([_header(ex, parent), prose["direct_answer"]]),
        "practice_steps": prose["practice_steps"], "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Try: slower, harder or easier, add accents, or undo that.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [],
        "diagnostics": {**base_diag, "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(), "exercise_context": ex.context.to_dict(),
                        "exercise_validation": ex.validation, "notation_abc_present": bool(abc), "last_exercise_stored": stored,
                        "transform": ex.transform, "practice_concert_key": ex.context.concert_key, "written_key": ex.context.written_key,
                        "resolved_instrument": ex.context.instrument, "notation_instrument": ex.context.notation_instrument,
                        "bars_generated": ex.bars},
    }
