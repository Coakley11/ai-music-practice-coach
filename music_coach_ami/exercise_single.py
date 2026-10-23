"""AMI Slice 5 Stage 2: advanced single-chord improvisation vocabulary.

AMI never invents notes. A request such as "an enclosure exercise targeting the third of G7" is mapped (``single_plan``) onto
the app's existing pattern engine:

    request  ->  ``single_plan``   (technique -> pattern-engine families + the single-chord Mission that owns the idea)
             ->  ``melodic_pattern_engine.generate_pattern``   (the same engine the Missions and Phrase & Motif use)
             ->  ``validate_pattern`` + AMI's own technique checks (enclosures really surround their target, approaches
                 really resolve by a half step, the target is the chord tone that was asked for, direction and register hold)
             ->  canonical ``GeneratedExercise`` (concert pitch; ``ex.written`` derived by realizing the same pattern natively
                 in the written key and verifying it is the same line)
             ->  card (staff, Guitar TAB, an explanation read from the realized notes)
             ->  "Open in Missions": the exact motif is packaged as a single-chord Mission example (``motif_override``).

Plain "target the third" (no technique) uses the Mission engine's own "Resolve convincingly to the chord's 3rd" generator, which
already ends on the 3rd and has Easier / Normal / Harder variants.

Not supported yet (said to the player, never approximated): combining a technique with another pitch vocabulary (a pentatonic
enclosure) or two techniques in one line; a plain target tone other than the 3rd; follow-ups on these exercises.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import replace
from typing import Any

from music_coach_ami.exercise_model import (
    TECHNIQUE_BEBOP,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_COMPOSITE,
    TECHNIQUE_ENCLOSURE,
    TECHNIQUE_TARGET_TONE,
    VOCAB_CHORD_TONES,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
    PatternPlan,
)

SINGLE_TECHNIQUES = (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH, TECHNIQUE_BEBOP, TECHNIQUE_TARGET_TONE)
ENGINE_NAME = "melodic_pattern_engine"
ENGINE_VERSION = 1
ACTION_KIND = "single_technique"
_ARROW = " → "
_EN = " – "

_MISSION_FOR = {
    TECHNIQUE_ENCLOSURE: "Enclose a target chord tone before resolving",
    TECHNIQUE_CHROMATIC_APPROACH: "Approach a chord tone chromatically",
    TECHNIQUE_BEBOP: "Create a bebop-style line",
    TECHNIQUE_TARGET_TONE: "Resolve convincingly to the chord's 3rd",
}
_TITLE = {
    TECHNIQUE_ENCLOSURE: "Enclosure exercise",
    TECHNIQUE_CHROMATIC_APPROACH: "Chromatic approach exercise",
    TECHNIQUE_BEBOP: "Bebop-style line",
    TECHNIQUE_TARGET_TONE: "Target-the-3rd exercise",
}
_CATEGORY = {
    TECHNIQUE_ENCLOSURE: "enclosure",
    TECHNIQUE_CHROMATIC_APPROACH: "chromatic_approach",
    TECHNIQUE_BEBOP: "bebop",
}
_TONE_ROLE = {"root": "R", "third": "3", "fifth": "5", "seventh": "7"}
_TONE_LABEL = {"R": "root", "3": "3rd", "5": "5th", "7": "7th"}
_REGISTERS = {"low": (53, 74), "high": (67, 88)}
_LISTEN = {
    TECHNIQUE_ENCLOSURE: (
        "A note above and a note below the target surrounding it before the line lands",
        "The target chord tone arriving on its beat, so the surrounding notes feel like they are pulling toward it",
    ),
    TECHNIQUE_CHROMATIC_APPROACH: (
        "The half step that leans into the chord tone, so the chord tone sounds like an arrival",
        "How the same approach shape sounds into different chord tones",
    ),
    TECHNIQUE_BEBOP: (
        "Chord tones landing on the strong beats, with scale and chromatic passing notes between them",
        "How the passing notes keep the line moving without losing the chord",
    ),
    TECHNIQUE_TARGET_TONE: (
        "The line finishing on the chord's 3rd, the note that tells you major or minor",
        "How the lead-in notes make that last note sound like an arrival",
    ),
}
_DIFF_RANK = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
_DIFFS = ("Beginner", "Intermediate", "Advanced")
_ATTEMPT_SEEDS = 12
_CELLS_GENERIC = 3          # a few cells: each one lands on the next chord tone
_PHRASE_FORM_LIMIT = 16


def _clean(value: object) -> str:
    return str(value or "").strip()


def _pretty(text: str) -> str:
    import re

    return re.sub(r"(?<=[A-G])b|b(?=\d)", "♭", str(text or "")).replace("#", "♯")


# ---------------------------------------------------------------- the dispatch contract


def single_plan(intent: ExerciseIntent) -> PatternPlan:
    """Map a single-chord technique request onto the existing engine and Mission, or say what is not supported yet."""
    technique, tone = _clean(intent.technique), _clean(intent.target_tone)
    vocabulary = _clean(intent.vocabulary)
    explicit_vocab = "vocabulary" in (intent.explicit_fields or {})

    def refuse(why: str, title: str = "Single-chord exercise") -> PatternPlan:
        return PatternPlan(vocabulary=vocabulary, technique=technique, mission_id="", title=title,
                           action_kind=ACTION_KIND, limitation=why)

    if technique == TECHNIQUE_COMPOSITE:
        return refuse("combining chromatic approaches, enclosures or bebop vocabulary in one line is not available yet")
    if technique not in SINGLE_TECHNIQUES:
        return refuse("that technique is not available for a single chord yet")
    if explicit_vocab and vocabulary == "guide_tones" and technique in (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH):
        # Stage 3: guide tones with approaches / enclosures - the technique's own Mission, its landings restricted to the 3rd
        # and 7th (or the one tone asked for).
        roles = (_TONE_ROLE[tone],) if tone in _TONE_ROLE else ("3", "7")
        if tone and tone not in ("third", "seventh"):
            return refuse(f"guide tones are the 3rd and the 7th, so a guide-tone line cannot target the {tone}")
        word = "chromatic approaches" if technique == TECHNIQUE_CHROMATIC_APPROACH else "enclosures"
        return PatternPlan(
            vocabulary=vocabulary, technique=technique, mission_id=_MISSION_FOR[technique], title=f"Guide-tone line with {word}",
            action_kind=ACTION_KIND, target_roles=roles, listen_for=_LISTEN[technique],
        )
    if explicit_vocab and vocabulary != VOCAB_CHORD_TONES:
        return refuse(
            f"combining {vocabulary.replace('_', ' ')} pitch vocabulary with {technique.replace('_', ' ')} is not available yet: the "
            f"Missions cannot check a {vocabulary.replace('_', ' ')} framework together with chromatic embellishments, and I won't call "
            "a line that mixes them something it is not"
        )
    if technique == TECHNIQUE_TARGET_TONE and tone != "third":
        return refuse(
            f"targeting the {tone or 'chord tone'} on its own is not a Mission yet; ask for an enclosure or a chromatic "
            f"approach to the {tone or 'chord tone'}, or for a line that targets the 3rd"
        )
    if technique == TECHNIQUE_BEBOP and tone:
        return refuse("a bebop line aimed at a named chord tone is not available yet")
    return PatternPlan(
        vocabulary=VOCAB_CHORD_TONES, technique=technique, mission_id=_MISSION_FOR[technique], title=_TITLE[technique],
        action_kind=ACTION_KIND, listen_for=_LISTEN[technique],
    )


# ---------------------------------------------------------------- realization with the pattern engine


def _wanted_difficulty(ctx: ActiveContext, intent: ExerciseIntent) -> str:
    from melodic_pattern_engine import normalize_difficulty

    rank = _DIFF_RANK[normalize_difficulty(ctx.level)]
    if intent.difficulty_request == "harder":
        rank += 1
    elif intent.difficulty_request == "easier":
        rank -= 1
    return _DIFFS[max(0, min(2, rank))]


def _candidate_families(technique: str, key_ref: str, chord: str, direction: str, wanted: str) -> list[Any]:
    """Families of the technique's category that this chord supports, nearest the wanted difficulty first."""
    from melodic_pattern_engine import build_context, family_supports, list_families

    ctx = build_context(key_ref, chord)
    pool = [f for f in list_families(category=_CATEGORY[technique]) if family_supports(f, ctx, direction)]
    want = _DIFF_RANK[wanted]
    # exactly the wanted difficulty, then the nearest simpler, then the nearest harder
    # (a bebop "line" prefers the longer realizations over the four-note passing figure)
    return sorted(pool, key=lambda f: (abs(_DIFF_RANK[f.difficulty] - want), _DIFF_RANK[f.difficulty] > want,
                                       -f.size if technique == TECHNIQUE_BEBOP else 0, f.id))


def _shift_cell(cell: tuple[Any, ...], semitones: int) -> tuple[Any, ...]:
    return tuple(replace(n, midi=n.midi + semitones) for n in cell)


def _cell_landing_on(family: Any, key_ref: str, chord: str, direction: str, role: str, seed: int, register: tuple[int, int]) -> Any | None:
    """One cell of ``family`` that lands on ``role``. Which chord tone a cell lands on follows from the chord tone it starts
    on, so each starting tone the family allows is tried (the family restricted to that start)."""
    from melodic_pattern_engine import generate_pattern

    for start in family.start_roles:
        try:
            trial = generate_pattern(replace(family, start_roles=(start,)), key=key_ref, chord=chord, direction=direction,
                                     length=1, seed=seed, register=register)
        except ValueError:
            continue
        if [n.chord_role for _c, _i, n in trial.targets()] == [role]:
            return trial
    return None


def _realize(family: Any, key_ref: str, chord: str, direction: str, tone_roles: tuple, seed: int,
             register: tuple[int, int]) -> Any | None:
    """One PatternResult for ``family`` that lands on the asked-for tone(s), or None. Deterministic in ``seed``.

    One tone: a cell that lands on it, then the same cell an octave further in the asked-for direction. Several tones (guide
    tones: the 3rd and the 7th): one cell landing on each, in the order asked.
    """
    from melodic_pattern_engine import PatternResult, generate_pattern

    if tone_roles:
        found = []
        for role in tone_roles:
            trial = _cell_landing_on(family, key_ref, chord, direction, role, seed, register)
            if trial is None:
                return None
            found.append(trial)
        base = found[0]
        cells = [t.cells[0] for t in found]
        if len(tone_roles) == 1:
            shift = 12 if direction == "ascending" else -12
            second = _shift_cell(cells[0], shift)
            lo, hi = register
            if all(lo <= n.midi <= hi for n in second):
                cells.append(second)
        return PatternResult(base.family, base.context, base.direction, base.seed, base.register, tuple(cells))
    n_cells = 1 if family.category == "bebop" else _CELLS_GENERIC
    return generate_pattern(family, key=key_ref, chord=chord, direction=direction, length=n_cells, seed=seed, register=register)


def technique_checks(result: Any, technique: str, *, tone_role: tuple, direction: str, playable: bool) -> list[dict[str, Any]]:
    """AMI's own verification of a realized pattern (the engine's validator is one check, not the only one)."""
    from melodic_pattern_engine import validate_pattern

    fam = result.family
    problems = validate_pattern(result)
    checks: list[dict[str, Any]] = [{"name": "pattern_engine_validator", "ok": not problems, "detail": "; ".join(problems) or "passed"}]
    targets = result.targets()
    cells = result.cells
    if technique in (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH):
        ok, detail = bool(targets), f"{len(targets)} target(s)"
        for ci, ti, tnote in targets:
            cell = cells[ci]
            lead = [n for n in cell[:ti] if n.target == ti] or [cell[ti - 1]] if ti > 0 else []
            if not lead:
                ok, detail = False, f"nothing leads into {tnote.name}"
                break
            if technique == TECHNIQUE_ENCLOSURE:
                above = any(n.midi > tnote.midi for n in lead)
                below = any(n.midi < tnote.midi for n in lead)
                near = all(0 < abs(n.midi - tnote.midi) <= 3 for n in lead)
                if not (above and below and near):
                    ok, detail = False, f"{tnote.name} is not surrounded from above and below"
                    break
            else:
                last = cell[ti - 1]
                if abs(last.midi - tnote.midi) != 1 or last.chord_role:
                    ok, detail = False, f"{last.name} is not a half-step approach into {tnote.name}"
                    break
            if not tnote.chord_role:
                ok, detail = False, f"{tnote.name} is not a chord tone"
                break
        checks.append({"name": f"{technique}_resolves_to_target", "ok": ok, "detail": detail})
    elif technique == TECHNIQUE_BEBOP:
        chord_tones = sum(1 for c in cells for n in c if n.chord_role)
        checks.append({"name": "bebop_chord_tone_grounding", "ok": fam.category == "bebop" and chord_tones >= 2,
                       "detail": f"{chord_tones} chord tones in a bebop family"})
    if tone_role:
        roles = [n.chord_role for _c, _i, n in targets]
        checks.append({"name": "target_is_requested_tone",
                       "ok": bool(roles) and all(r in tone_role for r in roles) and all(r in roles for r in tone_role),
                       "detail": f"targets {roles}, wanted {'/'.join(tone_role)}"})
    if technique != TECHNIQUE_TARGET_TONE and len(cells) > 1 and not tone_role:
        mids = [n.midi for _c, _i, n in targets]
        sign = 1 if direction == "ascending" else -1
        checks.append({"name": "direction_holds", "ok": all(sign * (b - a) > 0 for a, b in zip(mids, mids[1:])),
                       "detail": f"{direction}: target pitches {mids}"})
    checks.append({"name": "playable_on_instrument", "ok": playable, "detail": "every note is within the instrument's range"})
    return checks


def _playable_check(result: Any, instrument: str) -> bool:
    try:
        from improvisation_motif import guitar_midi_is_playable
        from improvisation_missions import _instrument_family

        if _instrument_family(instrument) != "guitar":
            return True
        return all(guitar_midi_is_playable(m) for m in result.midi)
    except Exception:
        return True


def generate_technique(plan: PatternPlan, intent: ExerciseIntent, ctx: ActiveContext, chord: str, key_ref: str) -> dict[str, Any]:
    """Realize + verify. Returns {"result", "checks", "attempts", "family", "notes": [str]} or {"reason": str}."""
    technique = plan.technique
    direction = intent.direction or "ascending"
    tone_role = tuple(plan.target_roles) or ((_TONE_ROLE[intent.target_tone],) if intent.target_tone in _TONE_ROLE else ())
    if technique not in (TECHNIQUE_ENCLOSURE, TECHNIQUE_CHROMATIC_APPROACH):
        tone_role = ()
    register = _REGISTERS.get(intent.register_request, None)
    from melodic_pattern_engine import DEFAULT_REGISTER

    register = register or DEFAULT_REGISTER
    wanted = _wanted_difficulty(ctx, intent)
    families = _candidate_families(technique, key_ref, chord, direction, wanted)
    if not families:
        return {"reason": f"{chord} has no {technique.replace('_', ' ')} pattern in the pattern engine for this chord type"}
    # a new idea rotates which family is tried first within the nearest difficulty; farther difficulties follow in order
    nearest = [f for f in families if f.difficulty == families[0].difficulty]
    rot = int(intent.variation_index) % len(nearest)
    ordered = nearest[rot:] + nearest[:rot] + [f for f in families if f.difficulty != families[0].difficulty]
    attempts, last_problem = 0, "no realization passed the checks"
    for fam in ordered:
        for seed in range(_ATTEMPT_SEEDS):
            attempts += 1
            try:
                result = _realize(fam, key_ref, chord, direction, tone_role, seed + 7 * int(intent.variation_index), register)
            except ValueError as exc:
                last_problem = str(exc)
                continue
            if result is None:
                continue
            checks = technique_checks(result, technique, tone_role=tone_role, direction=direction,
                                      playable=_playable_check(result, ctx.instrument))
            if all(c["ok"] for c in checks):
                notes: list[str] = []
                if fam.difficulty != wanted:
                    notes.append(
                        f"The pattern engine has no {technique.replace('_', ' ')} pattern at {wanted} level that fits this request "
                        f"on {chord}; this is the closest ({fam.difficulty})."
                    )
                return {"result": result, "checks": checks, "attempts": attempts, "family": fam, "notes": notes,
                        "direction": direction, "register": register}
            last_problem = "; ".join(f"{c['name']}: {c['detail']}" for c in checks if not c["ok"])
    return {"reason": last_problem, "attempts": attempts}


def generate_target_third(intent: ExerciseIntent, ctx: ActiveContext, chord: str, key_ref: str) -> dict[str, Any]:
    """Plain "target the 3rd": the Mission engine's own generator (it ends on the 3rd and has easier/harder variants)."""
    from improvisation_mission_specs import validate_mission_motif
    from improvisation_motif import chord_tone_names
    from motif_engine import MissionMotifValidationError, generate_mission_phrase_validated

    mission = _MISSION_FOR[TECHNIQUE_TARGET_TONE]
    variant = intent.difficulty_request if intent.difficulty_request in ("easier", "harder") else "normal"
    level = ctx.level if ctx.level in ("Beginner", "Intermediate", "Advanced") else "Intermediate"
    third = (chord_tone_names(chord, reference_key=key_ref) or ["", ""])[1]
    for attempt in range(_ATTEMPT_SEEDS):
        seed = int(hashlib.sha1(f"{chord}|{key_ref}|{level}|{variant}|{intent.variation_index}|{attempt}".encode()).hexdigest()[:8], 16)
        try:
            motif = generate_mission_phrase_validated(mission, chord, key_center=key_ref, level=level, variant=variant,
                                                      rng=random.Random(seed), idea_variant=(seed + attempt) % 12)
        except MissionMotifValidationError as exc:
            last = str(exc)
            continue
        ok, why = validate_mission_motif(mission, motif, chord=chord, key_center=key_ref)
        from music_coach_ami.exercise_bridge import _pc

        last_note_ok = bool(motif.get("notes")) and third and _pc(str(motif["notes"][-1])) == _pc(third)
        if ok and last_note_ok:
            checks = [{"name": "mission_validator", "ok": True, "detail": "passed"},
                      {"name": "ends_on_the_3rd", "ok": True, "detail": f"{motif['notes'][-1]} is the 3rd ({third})"}]
            return {"motif": motif, "checks": checks, "attempts": attempt + 1, "notes": [], "variant": variant}
        last = why or "the line did not end on the 3rd"
    return {"reason": last if 'last' in locals() else "no line ended on the 3rd"}


# ---------------------------------------------------------------- the canonical exercise


def _interval_word(delta: int) -> str:
    d = abs(delta)
    return {1: "half step", 2: "whole step", 3: "minor third"}.get(d, f"{d} semitones")


def describe_targets(result: Any, names: list[str] | None = None) -> list[dict[str, Any]]:
    """What leads into each landing note, read from the realized notes (never from the family's description).

    ``names``: the spelling the player is shown (one name per note, in order); the engine's own names otherwise.
    """
    out: list[dict[str, Any]] = []
    base = [0]
    for c in result.cells:
        base.append(base[-1] + len(c))

    def name_of(ci: int, ni: int, note: Any) -> str:
        return names[base[ci] + ni] if names and base[ci] + ni < len(names) else note.name

    for ci, ti, tnote in result.targets():
        cell = result.cells[ci]
        lead_idx = [i for i in range(ti) if cell[i].target == ti] or ([ti - 1] if ti > 0 else [])
        out.append({
            "cell": ci, "target": name_of(ci, ti, tnote), "role": tnote.chord_role,
            "lead": [{"note": name_of(ci, i, cell[i]), "side": "above" if cell[i].midi > tnote.midi else "below",
                      "gap": _interval_word(cell[i].midi - tnote.midi)} for i in lead_idx],
        })
    return out


def _roles_for(midi: list[int], chord: str, key_ref: str) -> tuple[list[str], list[str]]:
    from improvisation_motif import _midi_from_note, chord_tone_names
    from music_coach_ami.exercise_bridge import _DEGREE_LABEL, _chord_role_for_pc

    names = chord_tone_names(chord, reference_key=key_ref) or []
    pcs = [_midi_from_note(n, 4) % 12 for n in names]
    root = pcs[0] if pcs else 0
    return [_DEGREE_LABEL[(m - root) % 12] for m in midi], [_chord_role_for_pc(pcs, m % 12) for m in midi]


def _written_projection(ex: GeneratedExercise, ctx: ActiveContext, family: Any, chord: str, direction: str, tone_role: tuple,
                        seed: int, register: tuple[int, int]) -> tuple[dict[str, Any] | None, str]:
    """Transposing instruments: realize the SAME pattern natively in the written key, so the spelling is the engine's own
    (not a key-signature respell) - and accept it only if it is exactly the concert line moved by the transposition."""
    steps = int(ctx.transposition_semitones or 0)
    if not ctx.written_transposition_applied or not steps:
        return {"applied": False, "key": ctx.concert_key, "chord": ex.chord, "notes": list(ex.notes), "midi": list(ex.midi),
                "semitones": 0, "octave_shift": 0}, ""
    from music_theory import split_chord, transpose_chord

    ref = ctx.written_key or ctx.concert_key
    w_chord = transpose_chord(chord, steps, reference_key=ref)
    w_tonic = transpose_chord(ctx.concert_key, steps, reference_key=ref)
    lo, hi = register
    for octave in (0, -12, 12):
        try:
            res = _realize(family, w_tonic, w_chord, direction, tone_role, seed, (lo + steps + octave, hi + steps + octave))
        except ValueError:
            continue
        if res is not None and [m - steps - octave for m in res.midi] == list(ex.midi):
            return {"applied": True, "key": w_tonic, "tonic": split_chord(w_tonic)[0] if w_tonic else "", "chord": w_chord,
                    "notes": list(res.notes), "midi": list(res.midi), "semitones": steps, "octave_shift": octave // 12,
                    "range": [lo, hi]}, ""
    return None, f"I could not verify a correctly spelled written-key version for {ctx.notation_instrument or ctx.instrument}"


def _spelled_like_missions(motif: dict[str, Any], chord: str, concert_key: str) -> dict[str, Any]:
    """Note names exactly as the Missions page will show them: its own chord-aware speller (harmonic_spelling), so the card
    and the Mission example never disagree about an A-flat versus a G-sharp. Pitches are never touched."""
    try:
        from harmonic_spelling import apply_motif_chord_spelling
        from improvisation_motif import _midi_from_note

        out = dict(motif)
        apply_motif_chord_spelling(out, chord, song_display_key=concert_key)
        if [_midi_from_note(n, 4) % 12 for n in out["notes"]] == [int(m) % 12 for m in motif["midi"]]:
            return out
    except Exception:
        pass
    return motif


def build_single_exercise(
    plan: PatternPlan, intent: ExerciseIntent, ctx: ActiveContext, chord: str, key_ref: str, generated: dict[str, Any],
    chord_source: str,
) -> tuple[GeneratedExercise | None, str]:
    from improvisation_motif import _vocabulary_motif
    from music_coach_ami.exercise_bridge import _bars_of

    technique = plan.technique
    meter = _clean(ctx.meter) or "4/4"
    transposed = bool(ctx.written_transposition_applied and int(ctx.transposition_semitones or 0))
    facts: dict[str, Any] = {"technique": technique, "notes_to_player": list(generated.get("notes") or [])}
    fam = result = None
    direction, seed, tone_role = "", 0, ()
    if "result" in generated:
        result = generated["result"]
        fam = generated["family"]
        motif = _vocabulary_motif({"chord": chord, "notes": [], "midi": [], "meter": meter}, result, chord=chord, meter=meter,
                                  level=ctx.level)
        direction = generated["direction"]
        if not transposed:
            motif = _spelled_like_missions(motif, chord, ctx.concert_key)
        facts.update(
            family={"id": fam.id, "name": fam.name, "difficulty": fam.difficulty, "category": fam.category},
            direction=direction, targets=describe_targets(result, motif.get("notes")), register=list(generated["register"]),
            seed=int(result.seed),
        )
        seed = int(result.seed)
        tone_role = (tuple(plan.target_roles) or ((_TONE_ROLE[intent.target_tone],) if intent.target_tone in _TONE_ROLE else ())) \
            if technique != TECHNIQUE_BEBOP else ()
        engine_function = "generate_pattern"
    else:
        motif = dict(generated["motif"])
        if not transposed:
            motif = _spelled_like_missions(motif, chord, ctx.concert_key)
        facts.update(
            family={"id": "mission:resolve_to_3rd", "name": "Resolve to the 3rd", "difficulty": ctx.level, "category": "target"},
            direction="", variant=generated.get("variant"),
            targets=[{"cell": 0, "target": str(motif["notes"][-1]), "role": "3",
                      "lead": [{"note": str(n), "side": "", "gap": ""} for n in motif["notes"][:-1]]}],
        )
        engine_function = "generate_mission_phrase_validated"
    notes = [str(n) for n in motif.get("notes") or []]
    midi = [int(m) for m in motif.get("midi") or []]
    if not notes or len(midi) != len(notes):
        return None, "the pattern engine returned a line without pitches"
    roles, chord_roles = _roles_for(midi, chord, key_ref)
    bars = _bars_of(motif, meter)
    core = {"notes": notes, "midi": midi, "chord": chord, "technique": technique, "tone": intent.target_tone}
    ex_id = "ex-" + hashlib.sha1(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    engine = ENGINE_NAME if result is not None else "mission_motif_engine"
    prov = {
        "engine": engine, "engine_version": ENGINE_VERSION, "engine_function": engine_function,
        "mission_vocabulary": plan.mission_id, "technique": technique, "seed": seed, "attempts": generated.get("attempts", 0),
        "level": ctx.level, "level_source": ctx.level_source, "concert_key": ctx.concert_key, "key_source": ctx.key_source,
        "chord_source": chord_source, "explicit_fields": dict(intent.explicit_fields), "route": intent.engine_route,
        "route_reason": intent.route_reason, "spelling_reference": key_ref, "pattern_family": facts["family"]["id"],
    }
    ex = GeneratedExercise(
        id=ex_id, intent=intent, context=replace(ctx, chord_source=chord_source, field_sources={**ctx.field_sources, "chord": chord_source}),
        engine=engine, engine_detail=plan.mission_id, vocabulary=VOCAB_CHORD_TONES, seed=seed,
        attempts=int(generated.get("attempts", 0)), collection_label=plan.title, collection_notes=[], chord=chord,
        tonic=ctx.concert_key.rstrip("m"), mode="minor" if ctx.concert_key.endswith("m") else "major", notes=notes, midi=midi,
        rhythm_events=[dict(e) for e in (motif.get("rhythm_events") or [])],
        rhythm_symbols=[str(s) for s in motif.get("rhythm_symbols") or []], meter=meter, bars=bars, roles=roles,
        chord_roles=chord_roles, chord_assignment=[0] * len(notes), chords=[chord], articulation=[""] * len(notes),
        dynamics=[""] * len(notes), accents=[False] * len(notes), slur_groups=[0] * len(notes),
        validation={"ok": all(c["ok"] for c in generated["checks"]), "checks": generated["checks"]},
        explanation_facts=facts, provenance=prov,
    )
    facts["motif"] = motif  # the exact motif "Open in Missions" packages
    if result is not None:
        written, why = _written_projection(ex, ctx, fam, chord, direction, tone_role, seed, generated["register"])
        if written is None:
            return None, why
        ex.written = written
    elif transposed:
        return None, (f"a target-the-3rd line for {ctx.notation_instrument or ctx.instrument} needs a written-key version "
                      "that is not available yet")
    else:
        ex.written = {"applied": False, "key": ctx.concert_key, "chord": chord, "notes": list(notes), "midi": list(midi),
                      "semitones": 0, "octave_shift": 0}
    return ex, ""


# ---------------------------------------------------------------- the card


def _tone_name(role: str) -> str:
    return {"R": "root", "3": "3rd", "5": "5th", "7": "7th"}.get(role, role)


def _lead_text(target: dict[str, Any], technique: str) -> str:
    tn = _pretty(target["target"])
    lead = target.get("lead") or []
    if technique == TECHNIQUE_TARGET_TONE:
        return f"the lead-in {_EN.join(_pretty(x['note']) for x in lead)} resolves to {tn}"
    parts = [f"{_pretty(x['note'])} ({x['gap']} {x['side']})" for x in lead if x.get("side")]
    if not parts:
        return f"{tn} is approached and resolved"
    if technique == TECHNIQUE_ENCLOSURE:
        return f"{' and '.join(parts)} surround {tn}, then it resolves to {tn}"
    return f"{' and '.join(parts)} lean into {tn}, which then sounds like an arrival"


def single_prose(ex: GeneratedExercise, plan: PatternPlan, *, display_instrument: str, tab: str = "") -> dict[str, Any]:
    from music_coach_ami.exercise_bridge import _chord_source_text, _key_source_text

    ctx, f = ex.context, ex.explanation_facts
    technique = plan.technique
    chord = _pretty(ex.chord)
    targets = f.get("targets") or []
    lines = [
        f"**Chord:** {chord} ({_chord_source_text(ex.provenance.get('chord_source', ''))}) · **Key:** {ctx.concert_key} "
        f"({_key_source_text(ctx)})",
    ]
    if ex.written.get("applied"):
        lines.append(f"**Concert key:** {ctx.concert_key}  \n**Written key:** {ex.written['key']} for **{ctx.notation_instrument or display_instrument}**")
    if targets:
        roles = [_tone_name(t["role"]) for t in targets if t.get("role")]
        distinct = list(dict.fromkeys(f"{_pretty(t['target'])} ({_tone_name(t['role'])})" if t.get("role") else _pretty(t["target"]) for t in targets))
        lines.append("**Lands on:** " + ", ".join(distinct) + (f" — the {roles[0]} of {chord}" if len(set(roles)) == 1 and roles else ""))
        seen: list[str] = []
        for t in targets:
            text = _lead_text(t, technique)
            if text not in seen:
                seen.append(text)
        lines.append("**How it works:** " + "; ".join(seen[:3]) + ".")
    fam = f.get("family") or {}
    if technique != TECHNIQUE_TARGET_TONE and fam.get("name"):
        d = f.get("direction")
        lines.append(f"**Pattern:** {fam['name']} ({fam['difficulty']})" + (f", {d}" if d else ""))
    for note in f.get("notes_to_player") or []:
        lines.append(f"_{note}_")
    if ex.context.mission_active and ex.context.active_mission:
        lines.append(f"_Your open Mission is “{ex.context.active_mission}”; this exercise opens its own Mission below._")
    if ex.intent.expression:
        lines.append("_Articulation and dynamics aren't applied to these exercises yet, so the line is unmarked._")
    if "section" == ex.intent.scope:
        lines.append("_This version covers one chord; multi-chord section exercises come in a later update, so I used the chord above._")
    spoken = ex.written["notes"] if ex.written.get("applied") else ex.notes
    steps = [
        f"**{plan.title}** — read the staff notation below" + (", with Guitar TAB under it." if tab else "."),
        f"Notes{' (written)' if ex.written.get('applied') else ''}: {_EN.join(_pretty(n) for n in spoken)}",
        f"Play it slowly on **{display_instrument}**, landing each target note on its beat; then loop it and raise the tempo 4–8 BPM once it is clean.",
    ]
    if ex.written.get("applied"):
        steps.append("Open in Missions is available in concert pitch for now, so it is not offered for a transposing instrument.")
    else:
        steps.append("To practise it over a backing track, press **Open in Missions**, then **Practice in Backing Jam**.")
    direct = f"**Try this {plan.title.lower()} over {chord}:**\n\n" + "\n\n".join(lines)
    if tab:
        direct += "\n\n**Guitar TAB**\n\n```\n" + tab.strip("\n") + "\n```"
    return {"direct_answer": direct, "practice_steps": steps, "what_to_listen_for": list(plan.listen_for), "title": plan.title}


def _limit_payload(message: str, intent: ExerciseIntent, base_diag: dict[str, Any]) -> dict[str, Any]:
    return {
        "direct_answer": message,
        "practice_steps": ["Your Practice Key, selected chord and Missions are unchanged.",
                           "Try an enclosure, a chromatic approach or a bebop line over a named chord, "
                           "for example \"enclosure exercise targeting the third of G7\"."],
        "what_to_listen_for": [], "suggested_next_action": "Ask again with one technique (an enclosure, a chromatic approach or a bebop line).",
        "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {**base_diag, "exercise_failed": True, "exercise_failure_reason": message},
    }


def compose_single_payload(
    req: Any, idea: Any, intent: ExerciseIntent, ctx: ActiveContext, written_ctx: Any, *, session_ref: Any,
    display_instrument: str, bpm: int,
) -> dict[str, Any]:
    from improvisation_motif import build_motif_guitar_tab

    from music_coach_ami.exercise_bridge import (
        ENGINE_NAME as _BRIDGE_ENGINE,
        _spell_reference,
        motif_view,
        plan_inputs,
        render_abc,
        store_last_exercise,
    )

    base_diag = {
        "musical_idea_content": True, "exercise_bridge": True, "exercise_single_request": True, "exercise_intent": intent.to_dict(),
        "exercise_context": ctx.to_dict(), "practice_concert_key": ctx.concert_key, "written_key": ctx.written_key,
        "resolved_instrument": ctx.instrument, "notation_instrument": ctx.notation_instrument, "requested_object": intent.form,
        "resolved_object": intent.form, "generation_strategy": ENGINE_NAME,
    }
    plan = single_plan(intent)
    if not plan.supported:
        return _limit_payload(f"I can't build that yet: {plan.limitation}.", intent, {**base_diag, "pattern_plan": plan.to_dict()})
    inputs = plan_inputs(intent, ctx)
    chord = _clean((inputs.get("chords") or [""])[0])
    chord_source = _clean(inputs.get("chord_source"))
    if not chord:
        return _limit_payload("I need a chord to build this on. Name one (for example \"over G7\") or select a chord first.", intent, base_diag)
    key_ref = _spell_reference(chord, ctx.concert_key)
    if plan.technique == TECHNIQUE_TARGET_TONE:
        generated = generate_target_third(intent, ctx, chord, key_ref)
    else:
        generated = generate_technique(plan, intent, ctx, chord, key_ref)
    if "reason" in generated:
        return _limit_payload(
            f"I couldn't build a {plan.title.lower()} over {_pretty(chord)} that passed my checks ({generated['reason']}). Nothing was changed.",
            intent, {**base_diag, "pattern_plan": plan.to_dict()},
        )
    ex, why = build_single_exercise(plan, intent, ctx, chord, key_ref, generated, chord_source)
    if ex is None:
        return _limit_payload(f"I couldn't build that {plan.title.lower()}: {why}.", intent, {**base_diag, "pattern_plan": plan.to_dict()})
    from music_coach_ami.exercise_span import _guitar_family

    guitar = _guitar_family(ctx.instrument or display_instrument)
    tab = build_motif_guitar_tab(motif_view(ex)) if guitar else ""
    prose = single_prose(ex, plan, display_instrument=display_instrument, tab=tab)
    abc = render_abc(ex, bpm=bpm, title=f"{plan.title} — {ex.chord}", instrument=ctx.notation_instrument or ctx.instrument)
    stored = store_last_exercise(session_ref, ex)
    action = None
    if not ex.written.get("applied"):
        action = {
            "kind": ACTION_KIND, "exercise_id": ex.id, "label": "Open in Missions", "mission_id": plan.mission_id, "chord": chord,
            "section": ctx.section, "concert_key": ctx.concert_key, "technique": plan.technique, "motif": ex.explanation_facts["motif"],
            "level": ctx.level, "instrument": ctx.instrument, "bpm": int(bpm or ctx.tempo_bpm or 96),
            "variant": ex.explanation_facts.get("variant") or "normal",
        }
    diag = {
        **base_diag, "exercise_context": ex.context.to_dict(), "generated_exercise_id": ex.id,
        "generated_exercise": {k: v for k, v in ex.to_dict().items()}, "exercise_validation": ex.validation,
        "pattern_plan": plan.to_dict(), "notation_abc_present": bool(abc), "guitar_tab_present": bool(tab),
        "last_exercise_stored": stored, "difficulty_level": ctx.level, "bars_generated": ex.bars,
        "written_music_context": written_ctx.to_diagnostics() if written_ctx is not None else {},
    }
    if action:
        diag["open_in_missions"] = action
    return {
        "direct_answer": prose["direct_answer"], "practice_steps": prose["practice_steps"],
        "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Open it in Missions to hear it over a backing track, or ask for another technique over the same chord.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [], "diagnostics": diag,
    }


# ---------------------------------------------------------------- Open in Missions (one chord)


def _norm_chord(symbol: object) -> str:
    return _clean(symbol).replace("♭", "b").replace("♯", "#")


def open_single_in_missions(session: Any, action: dict[str, Any]) -> dict[str, Any]:
    """Package the AMI motif as a single-chord Mission example and go to Creative -> Missions. Never regenerates the notes."""
    from improvisation_intelligence_ui import SCOPE_SINGLE, _mission_improv_ctx_from_session
    from improvisation_motif import resolve_improv_section_rows
    from improvisation_missions import generate_mission_example, store_mission_example
    from mission_span_ui import MISSION_TARGET_SCOPE_STATE_KEY, MISSION_TARGET_SCOPE_WIDGET_KEY
    from music_coach_ami.exercise_span import _session

    motif = action.get("motif") if isinstance(action, dict) else None
    mission, chord = _clean(action.get("mission_id")), _clean(action.get("chord"))
    if not isinstance(motif, dict) or not motif.get("notes") or not mission or not chord:
        return {"ok": False, "message": "That exercise can no longer be opened — ask for it again."}
    sess = _session(session)
    probe = dict(sess)
    probe["improv_intelligence_tab"] = "Missions"
    probe["creative_improv_intelligence_tab"] = "Missions"
    improv_ctx = _mission_improv_ctx_from_session(probe)
    rows = resolve_improv_section_rows(probe, improv_ctx) if improv_ctx is not None else []
    if not rows:
        return {"ok": False, "message": "I need the song's chords to open this in Missions. Select a song with chords and ask again."}
    from music_theory import semitone_distance

    if semitone_distance(_clean(improv_ctx.key_center), _clean(action.get("concert_key"))) not in (0, None):
        return {"ok": False, "message": "The Practice Key has changed since this exercise was made, so it can't be opened in "
                                        "Missions as it is. Ask for it again in the current key."}
    want = _norm_chord(chord)
    section, index = "", -1
    for label, clean, _raw in rows:
        chords = [_norm_chord(c) for c in clean]
        if want in chords and (not section or label == _clean(action.get("section"))):
            section, index = label, chords.index(want)
            if label == _clean(action.get("section")):
                break
    if not section:
        return {"ok": False, "message": f"{_pretty(chord)} is not one of this song's chords, so the Missions page can't hold it. "
                                        "Practise it from the card, or ask for an exercise over one of the song's chords."}
    level = _clean(probe.get("level")) or _clean(action.get("level")) or "Intermediate"
    instrument = _clean(probe.get("instrument")) or _clean(action.get("instrument")) or "Piano"
    example = generate_mission_example(
        mission, improv_ctx=improv_ctx, chord=chord, section=section, level=level, instrument=instrument,
        focus=_clean(probe.get("focus")) or "Improvisation", variant=_clean(action.get("variant")) or "normal",
        bpm=int(action.get("bpm") or 100), session_state=None, motif_override=dict(motif),
    )
    # The app's own user-event path, in the order the page's callbacks use: pick the Mission, select the chord, then store the
    # example (the first two clear any older example, so the store comes last and is persisted like a Generate press).
    from creative_mission_config_persistence import (
        _expected_mission_chord_label,
        handle_user_mission_pick_change,
        handle_user_mission_target_selection,
    )
    from improvisation_missions import (
        mission_example_artifact_id,
        mission_example_fingerprint,
        motif_material_fingerprint,
    )
    from improvisation_motif import flatten_section_map, global_chord_index, resolve_improv_sections

    sess["improv_mission_pick"] = mission
    sess["improv_active_mission"] = mission
    handle_user_mission_pick_change(sess)
    section_map = resolve_improv_sections(probe, improv_ctx)
    labels = [lab for lab, _chs in section_map]
    global_index = global_chord_index(section_map, labels.index(section), index) if section in labels else index
    handle_user_mission_target_selection(
        sess, chord=chord, section=section, chord_index=int(global_index),
        chord_label=_expected_mission_chord_label(section, chord), button_key="ami_open_in_missions",
    )
    sess["ii_selected_chord_index"] = int(global_index)
    sess[MISSION_TARGET_SCOPE_STATE_KEY] = SCOPE_SINGLE
    sess.pop(MISSION_TARGET_SCOPE_WIDGET_KEY, None)
    sess["_mission_example_artifact_id"] = mission_example_artifact_id(
        sess, mission=mission, chord=chord, section=section, chord_index=int(global_index)
    )
    sess.pop("_mission_example_last_transform", None)
    store_mission_example(sess, example, persist_artifact=True, interaction="ami_open_in_missions")
    sess["_mission_example_output_fp"] = mission_example_fingerprint(example)
    sess["_mission_example_material_fp"] = motif_material_fingerprint(example.motif)
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(sess, "creative")
    except ImportError:
        pass
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
    return {"ok": True, "message": "", "mission": mission, "chord": chord, "section": section}
