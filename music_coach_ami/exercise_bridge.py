"""Bridge from AMI exercise requests to the Mission/Motif engines.

A thin adapter, not a second generator: the notes come from ``generate_mission_phrase_validated`` with
the Mission's own collection resolvers and validators. This module

* picks the engine inputs (chord, key, level, seed, mission vocabulary) from ``ExerciseIntent`` +
  ``ActiveContext``;
* turns the validated motif into the canonical ``GeneratedExercise`` (concert pitch);
* derives the Written Key projection, ABC and AMI prose *from that object*;
* stores the last exercise under an AMI-owned session key (never Mission state).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import replace
from fractions import Fraction
from typing import Any

from music_coach_ami.exercise_context import key_mode, key_tonic, normalize_key_token
from music_coach_ami.exercise_model import (
    VOCAB_BLUES,
    VOCAB_CHORD_TONES,
    VOCAB_GUIDE_TONES,
    VOCAB_PENTATONIC,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
)

AMI_LAST_EXERCISE_KEY = "_ami_last_generated_exercise"
ENGINE_NAME = "mission_motif_engine"
ENGINE_VERSION = "ami-exercise-bridge/1"

_MISSION_FOR_VOCAB = {
    VOCAB_PENTATONIC: "Improvise using a pentatonic scale that fits the chord",
    VOCAB_BLUES: "Improvise using a blues scale that fits the chord",
    VOCAB_CHORD_TONES: "Improvise using only chord tones",
    VOCAB_GUIDE_TONES: "Target only guide tones (3rds & 7ths)",
}
_DEGREE_LABEL = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "b5", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}
_CHORD_ROLE_NAMES = ("R", "3", "5", "7", "9", "11", "13")
_MAX_ATTEMPTS = 60


def _clean(value: object) -> str:
    return str(value or "").strip()


def _pc(name: str) -> int:
    from improvisation_motif import _midi_from_note

    return _midi_from_note(str(name), 4) % 12


# ---------------------------------------------------------------- chord / collection choice


def _tonic_chords(tonic: str, mode: str, vocabulary: str) -> list[str]:
    """Chords to try for a collection named without a chord. First one the engine accepts wins."""
    if vocabulary == VOCAB_BLUES:
        return [f"{tonic}m7", f"{tonic}7"] if mode == "minor" else [tonic, f"{tonic}maj7"]
    if mode == "minor":
        return [f"{tonic}m7", f"{tonic}m"]
    return [f"{tonic}maj7", tonic]


def _wanted_relationship(vocabulary: str, mode: str) -> str:
    if vocabulary == VOCAB_BLUES:
        return "root_minor_blues" if mode == "minor" else "root_major_blues"
    if vocabulary == VOCAB_PENTATONIC:
        return "root_minor" if mode == "minor" else "root_major"
    return ""


def plan_inputs(intent: ExerciseIntent, ctx: ActiveContext) -> dict[str, Any]:
    """Decide chord(s), tonic/mode and the relationship filter. Records how each was decided."""
    vocab = intent.vocabulary
    explicit_mode = ""
    if intent.collection:
        explicit_mode = "minor" if intent.collection.startswith("minor") else "major"
    key_token = normalize_key_token(intent.explicit_key) if intent.explicit_key else ""
    key_has_mode = key_token.endswith("m")

    mode_source = "context"
    if explicit_mode:
        mode, mode_source = explicit_mode, "explicit_request"
    elif key_has_mode:
        mode, mode_source = "minor", "explicit_request"
    elif vocab == VOCAB_BLUES:
        mode, mode_source = ("major" if intent.both_thirds else "minor"), "blues_default"
    else:
        mode = key_mode(ctx.concert_key)

    plan: dict[str, Any] = {"mode": mode, "mode_source": mode_source, "relationship": ""}
    if intent.explicit_chord:
        plan.update(chords=[intent.explicit_chord], chord_source="explicit_request",
                    tonic=key_tonic(key_token) if key_token else "")
        if vocab in (VOCAB_PENTATONIC, VOCAB_BLUES) and (explicit_mode or intent.both_thirds):
            plan["relationship"] = _wanted_relationship(vocab, mode)
        return plan
    names_collection = vocab in (VOCAB_PENTATONIC, VOCAB_BLUES) and bool(intent.collection or key_token or intent.both_thirds)
    if names_collection or (key_token and vocab in (VOCAB_CHORD_TONES, VOCAB_GUIDE_TONES)):
        tonic = key_tonic(key_token) if key_token else key_tonic(ctx.concert_key)
        if vocab in (VOCAB_CHORD_TONES, VOCAB_GUIDE_TONES):
            chords = [f"{tonic}m7" if mode == "minor" else f"{tonic}maj7"]
        else:
            chords = _tonic_chords(tonic, mode, vocab)
            plan["relationship"] = _wanted_relationship(vocab, mode)
        plan.update(chords=chords, chord_source="synthesized_from_collection", tonic=tonic)
        return plan
    if ctx.selected_chord:
        plan.update(chords=[ctx.selected_chord], chord_source=ctx.chord_source, tonic="")
        return plan
    tonic = key_tonic(ctx.concert_key)
    kmode = key_mode(ctx.concert_key)
    chords = [f"{tonic}m7" if kmode == "minor" else f"{tonic}maj7"]
    plan.update(chords=chords, chord_source="tonic_of_key", tonic=tonic, mode=kmode)
    return plan


# ---------------------------------------------------------------- generation


def _spell_reference(chord: str, key: str) -> str:
    try:
        from harmonic_spelling import harmonic_reference_for_chord

        return harmonic_reference_for_chord(chord, song_display_key=key, song_key_center=key) or key
    except Exception:
        return key


def _seed_for(intent: ExerciseIntent, ctx: ActiveContext, chord: str) -> int:
    raw = "|".join(
        [intent.raw_question.lower(), intent.vocabulary, intent.collection, chord, ctx.concert_key, ctx.level,
         str(intent.variation_index)]
    )
    return int(hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8], 16)


def _collection(motif: dict[str, Any], vocabulary: str, chord: str, key: str) -> dict[str, Any]:
    """Resolved collection for a generated motif (concert spelling)."""
    from improvisation_mission_rules import (
        BLUES_RELATIONSHIPS,
        PENTATONIC_RELATIONSHIPS,
        _guide_third_seventh,
        resolve_blues_choice,
        resolve_pentatonic_choice,
    )
    from improvisation_motif import chord_tone_names

    rel = _clean(motif.get("pentatonic_relationship"))
    if vocabulary == VOCAB_BLUES and rel in BLUES_RELATIONSHIPS:
        root, kind, notes, label, blue = resolve_blues_choice(chord, key, rel)
        return {"relationship": rel, "tonic": root, "kind": kind, "label": f"{root} {kind}", "notes": list(notes),
                "mode": "minor" if kind.startswith("minor") else "major", "blue_note": blue}
    if vocabulary == VOCAB_PENTATONIC and rel in PENTATONIC_RELATIONSHIPS:
        root, kind, notes, label = resolve_pentatonic_choice(chord, key, rel)
        return {"relationship": rel, "tonic": root, "kind": kind, "label": f"{root} {kind}", "notes": list(notes),
                "mode": "minor" if kind.startswith("minor") else "major", "blue_note": ""}
    tones = chord_tone_names(chord, reference_key=key)
    if vocabulary == VOCAB_GUIDE_TONES:
        guides = [g for g in _guide_third_seventh(chord, key_center=key) if g]
        return {"relationship": "", "tonic": tones[0] if tones else "", "kind": "guide tones",
                "label": f"{chord} guide tones (3rd and 7th)", "notes": guides, "mode": "", "blue_note": ""}
    return {"relationship": "", "tonic": tones[0] if tones else "", "kind": "chord tones",
            "label": f"{chord} chord tones", "notes": list(tones[:4]), "mode": "", "blue_note": ""}


def _has_both_thirds(midi: list[int], tonic_pc: int) -> bool:
    pcs = {m % 12 for m in midi}
    return ((tonic_pc + 3) % 12) in pcs and ((tonic_pc + 4) % 12) in pcs


def _bars_of(motif: dict[str, Any], meter: str) -> int:
    beats_bar = {"3/4": 3.0, "6/8": 3.0, "2/4": 2.0}.get(meter, 4.0)
    events = motif.get("rhythm_events") or []
    end = Fraction(0)
    try:
        for e in events:
            end = max(end, Fraction(str(e.get("on"))) + Fraction(str(e.get("dur"))))
    except Exception:
        end = Fraction(0)
    if end <= 0:
        end = Fraction(len(motif.get("notes") or []))
    return max(1, int(-(-float(end) // beats_bar)))


def generate_exercise(intent: ExerciseIntent, ctx: ActiveContext, plan: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    """Run the Mission engine for the plan. Returns (exercise, '') or (None, reason)."""
    from improvisation_mission_specs import validate_mission_motif
    from motif_engine import MissionMotifValidationError, generate_mission_phrase_validated

    vocab = intent.vocabulary
    mission = _MISSION_FOR_VOCAB[vocab]
    level = ctx.level if ctx.level in ("Beginner", "Intermediate", "Advanced") else "Intermediate"
    want_rel = _clean(plan.get("relationship"))
    wanted_bars = intent.length_bars
    reason = "the engine produced no phrase that satisfied the request"
    best: tuple[dict[str, Any], str, int, int] | None = None
    for chord in plan["chords"]:
        key_ref = _spell_reference(chord, ctx.concert_key)
        seed = _seed_for(intent, ctx, chord)
        for attempt in range(_MAX_ATTEMPTS):
            try:
                motif = generate_mission_phrase_validated(
                    mission, chord, key_center=key_ref, level=level, variant="normal",
                    rng=random.Random(seed + attempt * 7919), idea_variant=(seed + attempt) % 12,
                )
            except MissionMotifValidationError as exc:
                reason = str(exc) or reason
                continue
            rel = _clean(motif.get("pentatonic_relationship"))
            if vocab in (VOCAB_PENTATONIC, VOCAB_BLUES):
                if not rel:
                    continue
                if want_rel and rel != want_rel:
                    got = "major" if "major" in rel else "minor"
                    asked = "major" if "major" in want_rel else "minor"
                    reason = f"{chord} resolves to the {got} {vocab} collection, not the {asked} one the request needs"
                    if vocab == VOCAB_BLUES and intent.both_thirds and got == "minor":
                        reason += " (the minor blues collection has no natural 3rd)"
                    continue
                if vocab == VOCAB_BLUES and intent.both_thirds:
                    col = _collection(motif, vocab, chord, key_ref)
                    if not _has_both_thirds([int(m) for m in motif.get("midi") or []], _pc(col["tonic"])):
                        reason = ("no phrase in this collection used both the flat 3rd and the natural 3rd"
                                  if col["mode"] == "major" else
                                  f"{chord} resolves to the minor blues collection, which has no natural 3rd")
                        continue
            meter = _clean(motif.get("meter")) or ctx.meter or "4/4"
            if wanted_bars and _bars_of(motif, meter) != wanted_bars and attempt < _MAX_ATTEMPTS - 1:
                if best is None:
                    best = (motif, chord, attempt, seed)
                continue
            return _build_exercise(intent, ctx, plan, motif, chord, key_ref, attempt + 1, seed, mission), ""
        if best is not None:
            motif, chord_b, attempt_b, seed_b = best
            return _build_exercise(
                intent, ctx, plan, motif, chord_b, _spell_reference(chord_b, ctx.concert_key), attempt_b + 1, seed_b,
                mission, note=f"requested {wanted_bars} bars; the engine's phrase length is chosen by level",
            ), ""
    return None, reason


def _chord_role_for_pc(chord_pcs: list[int], pc: int) -> str:
    for i, tone in enumerate(chord_pcs):
        if tone == pc:
            return _CHORD_ROLE_NAMES[i] if i < len(_CHORD_ROLE_NAMES) else ""
    return ""


def _build_exercise(
    intent: ExerciseIntent, ctx: ActiveContext, plan: dict[str, Any], motif: dict[str, Any], chord: str,
    key_ref: str, attempts: int, seed: int, mission: str, note: str = "",
) -> GeneratedExercise:
    from improvisation_motif import chord_tone_names
    from improvisation_mission_specs import validate_mission_motif

    vocab = intent.vocabulary
    col = _collection(motif, vocab, chord, key_ref)
    notes = [str(n) for n in motif.get("notes") or []]
    midi = [int(m) for m in motif.get("midi") or []]
    tonic_pc = _pc(col["tonic"]) if col["tonic"] else 0
    tones = chord_tone_names(chord, reference_key=key_ref) or []
    chord_pcs = [_pc(t) for t in tones]
    roles = [_DEGREE_LABEL[(m - tonic_pc) % 12] for m in midi]
    chord_roles = [_chord_role_for_pc(chord_pcs, m % 12) for m in midi]
    meter = _clean(motif.get("meter")) or ctx.meter or "4/4"
    ok, why = validate_mission_motif(mission, motif, chord=chord, key_center=key_ref)
    checks: list[dict[str, Any]] = [{"name": "mission_validator", "ok": bool(ok), "detail": why or "passed"}]
    if vocab in (VOCAB_PENTATONIC, VOCAB_BLUES):
        allowed = {_pc(n) for n in col["notes"]}
        checks.append({"name": "inside_collection", "ok": all(m % 12 in allowed for m in midi),
                       "detail": f"{col['label']}: {' '.join(col['notes'])}"})
    if vocab == VOCAB_BLUES and intent.both_thirds:
        checks.append({"name": "both_thirds", "ok": _has_both_thirds(midi, tonic_pc),
                       "detail": "flat 3rd and natural 3rd both sounded"})
    if vocab == VOCAB_CHORD_TONES:
        checks.append({"name": "only_chord_tones", "ok": all(r for r in chord_roles), "detail": " ".join(tones[:4])})
    if vocab == VOCAB_GUIDE_TONES:
        guides = {_pc(n) for n in col["notes"]}
        checks.append({"name": "only_guide_tones", "ok": all(m % 12 in guides for m in midi),
                       "detail": " ".join(col["notes"])})
    flat3 = next((n for n in col["notes"] if (_pc(n) - tonic_pc) % 12 == 3), "")
    nat3 = next((n for n in col["notes"] if (_pc(n) - tonic_pc) % 12 == 4), "")
    core = {"notes": notes, "midi": midi, "chord": chord, "vocab": vocab, "seed": seed}
    ex_id = "ex-" + hashlib.sha1(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    facts: dict[str, Any] = {
        "collection_label": col["label"], "collection_notes": list(col["notes"]),
        "degrees": [{"note": n, "degree": d, "chord_role": r} for n, d, r in zip(notes, roles, chord_roles)],
        "flat_third": flat3, "natural_third": nat3,
        "both_thirds_present": bool(flat3 and nat3 and _has_both_thirds(midi, tonic_pc)),
        "blue_note": col["blue_note"],
        "blue_note_degree": _DEGREE_LABEL[(_pc(col["blue_note"]) - tonic_pc) % 12] if col["blue_note"] else "",
        "mode_source": plan.get("mode_source", ""), "plan_note": note,
        "articulation_requested": intent.articulation_request, "dynamics_requested": intent.dynamics_request,
        "articulation_dynamics_applied": False,
    }
    prov = {
        "engine": ENGINE_NAME, "engine_version": ENGINE_VERSION, "engine_function": "generate_mission_phrase_validated",
        "mission_vocabulary": mission, "relationship": col["relationship"], "seed": seed, "attempts": attempts,
        "level": ctx.level, "level_source": ctx.level_source, "concert_key": ctx.concert_key,
        "key_source": ctx.key_source, "chord_source": plan.get("chord_source", ""),
        "explicit_fields": dict(intent.explicit_fields), "route": intent.engine_route, "route_reason": intent.route_reason,
        "spelling_reference": key_ref,
    }
    ex = GeneratedExercise(
        id=ex_id, intent=intent, context=ctx, engine=ENGINE_NAME, engine_detail=mission, vocabulary=vocab, seed=seed,
        attempts=attempts, collection_label=col["label"], collection_notes=list(col["notes"]), chord=chord,
        tonic=col["tonic"], mode=col["mode"] or plan.get("mode", ""), notes=notes, midi=midi,
        rhythm_events=[dict(e) for e in (motif.get("rhythm_events") or [])],
        rhythm_symbols=[str(s) for s in motif.get("rhythm_symbols") or []], meter=meter, bars=_bars_of(motif, meter),
        roles=roles, chord_roles=chord_roles, chord_assignment=[0] * len(notes), chords=[chord],
        articulation=[""] * len(notes), dynamics=[""] * len(notes),
        validation={"ok": all(c["ok"] for c in checks), "checks": checks}, explanation_facts=facts, provenance=prov,
    )
    ex.written = project_written(ex, ctx, motif=motif)
    return ex


# ---------------------------------------------------------------- Written Key projection (derived)


def staff_key_concert(ex: GeneratedExercise) -> str:
    """Key signature for the concert staff: the collection's own key, else the effective Practice key."""
    if ex.vocabulary in (VOCAB_PENTATONIC, VOCAB_BLUES):
        return ex.tonic + ("m" if ex.mode == "minor" else "")
    return ex.context.concert_key


def project_written(ex: GeneratedExercise, ctx: ActiveContext, *, motif: dict[str, Any] | None = None,
                    midi_low: int | None = None, midi_high: int | None = None) -> dict[str, Any]:
    """Derive the instrument-facing projection from the concert exercise. Never the other way round."""
    steps = int(ctx.transposition_semitones or 0)
    if not ctx.written_transposition_applied or not steps:
        return {"applied": False, "key": staff_key_concert(ex), "chord": ex.chord,
                "notes": list(ex.notes), "midi": list(ex.midi), "semitones": 0, "octave_shift": 0}
    from improvisation_mission_rules import resolve_blues_choice, resolve_pentatonic_choice
    from improvisation_motif import _note_from_midi, chord_tone_names
    from music_theory import transpose_chord

    concert_key = staff_key_concert(ex)
    ref = ctx.written_key or concert_key
    written_chord = transpose_chord(ex.chord, steps, reference_key=ref)
    written_tonic = transpose_chord(concert_key, steps, reference_key=ref)
    rel = _clean(ex.provenance.get("relationship"))
    names: dict[int, str] = {}
    try:
        if rel and ex.vocabulary == VOCAB_BLUES:
            names = {_pc(n): n for n in resolve_blues_choice(written_chord, written_tonic, rel)[2]}
        elif rel and ex.vocabulary == VOCAB_PENTATONIC:
            names = {_pc(n): n for n in resolve_pentatonic_choice(written_chord, written_tonic, rel)[2]}
    except Exception:
        names = {}
    if not names:
        names = {_pc(n): n for n in chord_tone_names(written_chord, reference_key=ref)}
    lo = midi_low if midi_low is not None else 55
    hi = midi_high if midi_high is not None else 79
    base = [m + steps for m in ex.midi]
    best_shift, best_cost = 0, None
    for shift in (0, -12, 12, -24, 24):
        moved = [m + shift for m in base]
        cost = sum(max(0, lo - m) + max(0, m - hi) for m in moved)
        if best_cost is None or cost < best_cost:
            best_shift, best_cost = shift, cost
    midi_w = [m + best_shift for m in base]
    notes_w = [names.get(m % 12) or _note_from_midi(m, ref) for m in midi_w]
    from music_theory import split_chord

    w_root = split_chord(written_tonic)[0] if written_tonic else ""
    return {"applied": True, "key": written_tonic, "tonic": w_root, "chord": written_chord, "notes": notes_w, "midi": midi_w,
            "semitones": steps, "octave_shift": best_shift // 12, "range": [lo, hi]}


# ---------------------------------------------------------------- rendering (derived)


def motif_view(ex: GeneratedExercise, domain: str = "auto") -> dict[str, Any]:
    """A motif dict derived from the exercise, in the requested domain, for the existing renderers."""
    use_written = (domain == "written") or (domain == "auto" and ex.written.get("applied"))
    src = ex.written if use_written and ex.written else {}
    notes = list(src.get("notes") or ex.notes)
    midi = list(src.get("midi") or ex.midi)
    chord = _clean(src.get("chord")) or ex.chord
    return {
        "chord": chord, "notes": notes, "midi": midi, "display": " – ".join(notes),
        "rhythm_events": [dict(e) for e in ex.rhythm_events], "rhythm_symbols": list(ex.rhythm_symbols),
        "meter": ex.meter, "spelling_reference": _clean(src.get("key")) or staff_key_concert(ex),
        "pentatonic_relationship": _clean(ex.provenance.get("relationship")),
    }


def render_abc(ex: GeneratedExercise, *, bpm: int, title: str, instrument: str, domain: str = "auto") -> str:
    from improvisation_motif import build_motif_abc, notation_clef_for_instrument

    view = motif_view(ex, domain)
    staff_key = _clean(view.get("spelling_reference")) or "C"
    return build_motif_abc(view, key_center=staff_key, bpm=int(bpm or 96), title=title,
                           clef=notation_clef_for_instrument(instrument))


def store_last_exercise(session_ref: Any, ex: GeneratedExercise) -> bool:
    """Persist the canonical exercise under an AMI-owned key. Never touches Mission/Motif state."""
    try:
        from music_coach_ami.session_access import as_mutable_session

        session = as_mutable_session(session_ref)
        if session is None:
            return False
        session[AMI_LAST_EXERCISE_KEY] = ex.to_dict()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- prose (derived)


def _key_source_text(ctx: ActiveContext) -> str:
    return {
        "explicit_request": "named in your request",
        "mission_practice_key": "your Mission Practice Key",
        "practice_chart_key": "your Practice key",
        "default": "the default",
    }.get(ctx.key_source, ctx.key_source)


def _chord_source_text(source: str) -> str:
    return {
        "explicit_request": "named in your request",
        "synthesized_from_collection": "built from the collection you asked for",
        "mission_chord_click": "the chord you selected in your Mission",
        "mission_selected_chord": "your selected Mission chord",
        "chart_active_section_first_chord": "the first chord of the active chart section",
        "tonic_of_key": "the tonic chord of the key",
    }.get(source, source)


def _flat(name: str) -> str:
    return str(name).replace("b", "♭") if len(str(name)) > 1 else str(name)


def _degree_root(ex: GeneratedExercise) -> str:
    """The tonic the degree labels count from, in the domain the notes are spoken in."""
    if ex.written.get("applied"):
        written_tonic = _clean(ex.written.get("tonic"))
        if written_tonic:
            return written_tonic
    return ex.tonic


def exercise_prose(ex: GeneratedExercise, *, display_instrument: str) -> dict[str, Any]:
    ctx, f = ex.context, ex.explanation_facts
    form = ex.intent.form or "line"
    title = f"{ex.collection_label}" if ex.vocabulary in (VOCAB_PENTATONIC, VOCAB_BLUES) else ex.collection_label
    direct = f"**Try this {form} — {title}:**"
    lines = [
        f"**Key:** {ctx.concert_key} ({_key_source_text(ctx)}) · **Chord:** {ex.chord} ({_chord_source_text(ex.provenance.get('chord_source', ''))})",
        f"**Collection:** {ex.collection_label} — {' '.join(_flat(n) for n in ex.collection_notes)}",
    ]
    if ex.vocabulary == VOCAB_BLUES and f.get("flat_third") and f.get("natural_third"):
        state = "both appear in this line" if f.get("both_thirds_present") else "this collection contains both"
        lines.append(f"**Two thirds:** {_flat(f['flat_third'])} (♭3) and {_flat(f['natural_third'])} (natural 3) are separate degrees of this scale — {state}.")
    elif ex.vocabulary == VOCAB_BLUES and f.get("flat_third"):
        lines.append(f"**Third:** this collection has the flat 3rd ({_flat(f['flat_third'])}) and no natural 3rd.")
    if f.get("blue_note"):
        lines.append(f"**Blue note:** {_flat(f['blue_note'])} ({_flat(f.get('blue_note_degree', ''))}).")
    if ex.written.get("applied"):
        lines.append(
            f"**Concert key:** {staff_key_concert(ex)}  \n**Written key:** {ex.written['key']} for **{ctx.notation_instrument or display_instrument}**"
        )
    if f.get("plan_note"):
        lines.append(f"_Note: {f['plan_note']}._")
    if ex.intent.scope == "section":
        lines.append("_This version covers one chord; multi-chord section exercises come in a later update, so I used the chord above._")
    asked = [x for x in (ex.intent.articulation_request, ex.intent.dynamics_request) if x]
    if asked:
        lines.append(f"_You asked for {', '.join(asked)}; articulation and dynamics aren't applied to these exercises yet — the notes and rhythm are._")
    spoken = ex.written["notes"] if ex.written.get("applied") else ex.notes
    degree_line = " ".join(f"{_flat(n)}({d})" for n, d in zip(spoken, ex.roles))
    steps = [
        f"**{form.title()}** — read the staff notation below.",
        f"Notes{' (written)' if ex.written.get('applied') else ''}: {' – '.join(_flat(n) for n in spoken)}",
        f"Scale degrees (from {_degree_root(ex)}): {degree_line}",
        f"Use a comfortable register on **{display_instrument}**.",
    ]
    listen = {
        VOCAB_PENTATONIC: ["Every note belongs to the five-note collection", "The line lands on chord tones at the strong beats"],
        VOCAB_BLUES: ["The blue note colours the line", "Notice which third you are playing and how it sounds against the chord"],
        VOCAB_CHORD_TONES: ["Each note is a tone of the chord", "Clean, even rhythm"],
        VOCAB_GUIDE_TONES: ["Every note is the 3rd or the 7th of the chord", "How the 3rd and 7th define the chord's sound"],
    }.get(ex.vocabulary, ["Clear phrase shape"])
    return {"direct_answer": "\n\n".join([direct, *lines]), "practice_steps": steps, "what_to_listen_for": listen, "title": title}


# ---------------------------------------------------------------- entry point used by compose_musical_idea_suggestion


def compose_exercise_payload(
    req: Any, idea: Any, intent: ExerciseIntent, ctx: ActiveContext, written_ctx: Any, *, session_ref: Any,
    display_instrument: str, bpm: int,
) -> dict[str, Any]:
    plan = plan_inputs(intent, ctx)
    # chord_source now says how the chord actually used was decided (the app's own selection stays in selected_chord).
    ctx = replace(ctx, chord_source=plan["chord_source"], field_sources={**ctx.field_sources, "chord": plan["chord_source"]})
    ex, reason = generate_exercise(intent, ctx, plan)
    base_diag = {
        "musical_idea_content": True, "exercise_bridge": True, "exercise_intent": intent.to_dict(),
        "exercise_context": ctx.to_dict(), "exercise_plan": {k: v for k, v in plan.items()},
        "practice_concert_key": ctx.concert_key, "written_key": ctx.written_key,
        "resolved_instrument": ctx.instrument, "notation_instrument": ctx.notation_instrument,
        "requested_object": intent.form, "resolved_object": intent.form, "generation_strategy": ENGINE_NAME,
    }
    if ex is None:
        return {
            "direct_answer": f"I couldn't build that {intent.vocabulary.replace('_', ' ')} exercise: {reason}.",
            "practice_steps": ["Try naming a chord (for example \"over Am7\") or a different collection."],
            "what_to_listen_for": [], "suggested_next_action": "Ask again with a chord or key named.",
            "notation_abc": "", "notation_abc_sections": [],
            "diagnostics": {**base_diag, "exercise_failed": True, "exercise_failure_reason": reason},
        }
    prose = exercise_prose(ex, display_instrument=display_instrument)
    title = f"{prose['title']} — {ex.chord}"
    abc = render_abc(ex, bpm=bpm, title=title, instrument=ctx.notation_instrument or ctx.instrument)
    stored = store_last_exercise(session_ref, ex)
    diag = {
        **base_diag, "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(),
        "exercise_validation": ex.validation, "notation_abc_present": bool(abc), "last_exercise_stored": stored,
        "written_music_context": written_ctx.to_diagnostics() if written_ctx is not None else {},
        "difficulty_level": ctx.level, "bars_generated": ex.bars,
    }
    return {
        "direct_answer": prose["direct_answer"],
        "practice_steps": prose["practice_steps"],
        "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Loop it slowly, then raise the tempo 4–8 BPM once it is clean three times.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [], "diagnostics": diag,
    }
