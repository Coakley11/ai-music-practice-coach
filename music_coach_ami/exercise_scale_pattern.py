"""AMI M1d: scale-pattern exercises become structured, revisable ``GeneratedExercise`` objects.

Two kinds of pattern, never confused:

* ``key_based``       - the legacy ``generate_scale_pattern`` result: one scale for the whole pattern, in the Practice Key's own mode
                        (a minor key gives a minor scale). No chord is attached to any note and none is claimed.
* ``chord_following`` - ``scale_pattern_chords``: each chord of the section's real timeline (split bars included) gets the scale that
                        chord calls for.

This module wraps either result in a ``GeneratedExercise`` without changing a note, a duration or a byte of the notation the player
gets, and stores it in the working state so later instructions act on it. The exercise holds the line as the player reads it (the
*written* events) and as it sounds (concert pitch = written minus the instrument's exact transposition, octave included); the two are
checked to differ by that one constant before anything is stored. If they cannot be verified, no exercise is built and the caller keeps
the legacy answer.

Follow-ups a scale pattern supports: harder / easier (a ladder of the engine's own rhythm and interval-cell parameters), accents and
articulation. Everything else is refused in words and the exercise is left as it was.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, replace
from fractions import Fraction
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.exercise_model import (
    ROUTE_LEGACY,
    VOCAB_DEGREE_PATTERN,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
)

ENGINE = "musical_idea_engine"
ENGINE_DETAIL = "generate_scale_pattern"            # key-based
ENGINE_DETAIL_CHORDS = "scale_pattern_chords"       # chord-following
KIND_KEY = "key_based"
KIND_CHORDS = "chord_following"

# Difficulty ladder, expressed only in parameters the engines already honour (rhythm unit and interval cell). The first three rungs are
# the legacy engine's own beginner / intermediate / advanced behaviour; the last two go past "advanced".
LADDER: tuple[dict[str, str], ...] = (
    {"label": "Beginner", "difficulty": "beginner", "rhythm": "quarter", "interval_pattern": "1-2-3-4"},
    {"label": "Intermediate", "difficulty": "intermediate", "rhythm": "", "interval_pattern": "1-2-3-4"},
    {"label": "Advanced", "difficulty": "advanced", "rhythm": "eighth", "interval_pattern": "1-2-3-4"},
    {"label": "Advanced+", "difficulty": "advanced", "rhythm": "eighth", "interval_pattern": "1-3-2-4"},
    {"label": "Advanced++", "difficulty": "advanced", "rhythm": "sixteenth", "interval_pattern": "1-3-2-4"},
)

_EVENT_FIELDS = ("spelled", "octave", "duration", "bar_index", "beat", "articulation", "scale_degree", "pitch_class", "chord",
                 "role", "cell_index", "domain", "tone_role", "slur_group")
_RANGE_TOLERANCE = 2          # the engines' own tolerance around a notation profile window


def _clean(value: object) -> str:
    return str(value or "").strip()


def _sha(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def is_scale_pattern(ex: GeneratedExercise | None) -> bool:
    return bool(ex is not None and ex.engine == ENGINE and ex.engine_detail in (ENGINE_DETAIL, ENGINE_DETAIL_CHORDS))


def kind_of(ex: GeneratedExercise) -> str:
    return _clean(ex.provenance.get("kind")) or KIND_KEY


# ---------------------------------------------------------------- events <-> dicts


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
        out.append({"on": str(cursor), "dur": str(dur), "w": str(dur), "rest": rest, "tup": None, "ts": False, "n": None if rest else note_i})
        if not rest:
            note_i += 1
        cursor += dur
    return out


def _articulation_string(art: str, accent: bool) -> str:
    return " ".join(x for x in ("accent" if accent else "", _clean(art)) if x)


# ---------------------------------------------------------------- rendering (the player's notation)


def composition_of(ex: GeneratedExercise) -> Any:
    """The written-domain ``MusicalIdeaComposition`` the player reads, with the exercise's current expression applied."""
    from music_coach_ami.musical_idea_engine import MusicalIdeaComposition
    from music_coach_ami.notation_profile import apply_register_override, notation_profile_for_instrument

    prov = ex.provenance
    rows = copy.deepcopy(prov["written_events"])
    note_i = 0
    for row in rows:
        if _clean(row.get("spelled")) and not str(row.get("duration") or "").lower().startswith("rest"):
            art = ex.articulation[note_i] if note_i < len(ex.articulation) else ""
            acc = bool(ex.accents[note_i]) if note_i < len(ex.accents) else False
            row["articulation"] = _articulation_string(art, acc)
            row["slur_group"] = int(ex.slur_groups[note_i]) if note_i < len(ex.slur_groups) else 0
            note_i += 1
    profile = apply_register_override(notation_profile_for_instrument(ex.context.notation_instrument or ex.context.instrument),
                                      _clean(prov.get("register")))
    return MusicalIdeaComposition(
        events=_events_from(rows), reference_key=_clean(prov.get("written_reference_key")), meter=ex.meter, bars=ex.bars,
        object_type="pattern", style=_clean(prov.get("style")), notation_profile=profile, strategy=_clean(prov.get("strategy")),
        tonic=_clean(prov.get("written_tonic")), tonality=_clean(prov.get("written_tonality")),
        scale_spelling=tuple(prov.get("written_scale_spelling") or ()), validation_errors=tuple(prov.get("validation_errors") or ()),
        validation_ok=bool(prov.get("validation_ok", True)),
    )


def render(ex: GeneratedExercise, *, bpm: int) -> tuple[str, Any]:
    """(abc, written composition): the same writer the first answer used, fed the stored written events."""
    from music_coach_ami.musical_idea_engine import composition_to_abc

    comp = composition_of(ex)
    abc, _diag = composition_to_abc(comp, title=_clean(ex.provenance.get("title")) or "Scale pattern", bpm=int(bpm or 96))
    return abc, comp


# ---------------------------------------------------------------- verification


def projection_offset(notation_instrument: str, ctx: ActiveContext) -> int:
    """Written minus sounding semitones (octave included), or ``ValueError`` when this instrument's pitch projection can't be verified."""
    off = sph.exact_offset(notation_instrument, int(ctx.transposition_semitones or 0))
    if off is None:
        raise ValueError(f"the written/sounding pitch relationship for {notation_instrument or 'this instrument'} can't be verified")
    return off


def window_args(notation_instrument: str, offset: int) -> dict[str, Any]:
    """Keyword arguments for ``generate_scale_pattern`` that build the line in sounding pitch inside the window that writes inside the
    instrument's written range. Empty for an instrument that does not transpose (the legacy window, unchanged)."""
    if not offset:
        return {}
    rng = sph.playable_written_range(notation_instrument)
    return {"window_shift": int(offset), "written_limits": rng} if rng else {}


def _verify_pair(written: list[Any], concert: list[Any], offset: int, notation_instrument: str, profile: Any) -> None:
    """Every written note is its concert note plus ``offset`` (pitch class AND octave), inside the instrument's playable written range
    and, give or take the engines' tolerance, the app's profile window."""
    if len(written) != len(concert):
        raise ValueError("written and concert lines differ in length")
    low, high = int(profile.midi_low) - _RANGE_TOLERANCE, int(profile.midi_high) + _RANGE_TOLERANCE
    playable = sph.playable_written_range(notation_instrument)
    for w, c in zip(written, concert):
        wm, cm = sph.midi_of(w.spelled, int(w.octave)), sph.midi_of(c.spelled, int(c.octave))
        if wm - cm != offset:
            raise ValueError(f"written {w.spelled}{w.octave} is not concert {c.spelled}{c.octave} + {offset} semitones")
        if not (low <= wm <= high):
            raise ValueError(f"written {w.spelled}{w.octave} is outside the instrument's profile range")
        if playable is not None and not (playable[0] <= wm <= playable[1]):
            raise ValueError(f"written {w.spelled}{w.octave} is outside what {notation_instrument} can play")


def _validation(checks: list[dict[str, Any]], info: dict[str, Any]) -> dict[str, Any]:
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "info": info}


# ---------------------------------------------------------------- building the exercise


def context_for(*, written_ctx: Any, concert_key: str, instrument: str, notation_instrument: str, song_title: str, section: str,
                level: str, practice_focus: str, meter: str, bpm: int, key: sph.KeyScale, original_key: str = "") -> ActiveContext:
    """The context the pattern was built in. The Practice Key stays the app's canonical value; the scale's own tonic and mode are recorded
    beside it, not in its place."""
    low = _clean(level).lower()
    label = "Advanced" if "advanced" in low or "hard" in low else "Beginner" if ("begin" in low or "easy" in low or "simple" in low) else "Intermediate"
    return ActiveContext(
        concert_key=_clean(concert_key) or key.token, key_source="practice_chart_key" if key.source == "practice_key" else key.source,
        key_candidates={"scale_tonic": key.tonic, "scale_mode": key.tonality, "scale_key_source": key.source,
                        "catalog_original_key": _clean(original_key)},
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
    *, kind: str, written: Any, concert: Any, idea: Any, ctx: ActiveContext, question: str, title: str, written_note: str = "",
    key: sph.KeyScale, notation_instrument: str, chord_following: Any = None, section_slots: list[str] | None = None,
) -> GeneratedExercise:
    """Wrap the engines' own result; raises ``ValueError`` if its pitch projection or range cannot be verified (the caller then keeps the
    legacy answer). ``written`` is what the player was shown, ``concert`` the same line in sounding pitch."""
    from music_coach_ami.musical_idea_engine import _beats_per_bar

    offset = projection_offset(notation_instrument, ctx)
    profile = written.notation_profile
    w_events = [e for e in written.events if not _is_rest(e)]
    c_events_all = list(concert.events)
    c_events = [e for e in c_events_all if not _is_rest(e)]
    _verify_pair(w_events, c_events, offset, notation_instrument, profile)
    # pitch-class check against the app's own transposition, independent of the octave arithmetic above
    semis = int(ctx.transposition_semitones or 0)
    if any((sph.pc_of(w.spelled) - sph.pc_of(c.spelled)) % 12 != semis % 12 for w, c in zip(w_events, c_events)):
        raise ValueError("written pitch classes disagree with the app's transposition")

    meter = concert.meter or "4/4"
    notes = [_clean(e.spelled) for e in c_events]
    midi = [sph.midi_of(e.spelled, int(e.octave)) for e in c_events]
    rhythm = _rhythm_events(c_events_all, meter)
    n = len(notes)
    chords_distinct: list[str] = []
    assignment: list[int] = []
    chord_roles: list[str] = []
    degree_labels = [str(e.scale_degree) if e.scale_degree else "" for e in c_events]
    segments_info: list[dict[str, Any]] = []
    if kind == KIND_CHORDS and chord_following is not None:
        role_maps: dict[str, dict[int, str]] = {}
        for e in c_events:
            if e.chord not in chords_distinct:
                chords_distinct.append(e.chord)
                role_maps[e.chord] = sph.chord_tone_roles(e.chord)
            assignment.append(chords_distinct.index(e.chord))
            chord_roles.append(role_maps[e.chord].get(sph.pc_of(e.spelled), ""))
        for seg in chord_following.segments:
            sc = chord_following.scales[seg.chord]
            segments_info.append({"bar": seg.bar + 1, "beat": f"{float(seg.beat + 1):g}", "beats": f"{float(seg.beats):g}", "chord": seg.chord,
                                  "scale": sc.label, "scale_notes": list(sc.notes), "why": sc.why, "push": seg.push})
    else:
        chord_roles, assignment = [""] * n, [0] * n

    checks = [
        {"name": "written_equals_concert_plus_offset", "ok": True, "detail": f"+{offset} semitones, octave included, for all {n} notes"},
        {"name": "written_inside_instrument_range", "ok": True, "detail": f"{int(profile.midi_low)}-{int(profile.midi_high)} ± {_RANGE_TOLERANCE}"},
        {"name": "engine_validation", "ok": bool(concert.validation_ok), "detail": "; ".join(concert.validation_errors) or "passed"},
        {"name": "one_midi_per_note", "ok": n == len(midi) and n > 0, "detail": f"{n} notes"},
    ]
    if kind == KIND_KEY:
        scale_pcs = {sph.pc_of(x) for x in concert.scale_spelling}
        checks.append({"name": "inside_scale", "ok": all(sph.pc_of(x) in scale_pcs for x in notes), "detail": " ".join(concert.scale_spelling)})
    else:
        ok_scale = all(sph.pc_of(e.spelled) in {sph.pc_of(x) for x in chord_following.scales[e.chord].notes} for e in c_events)
        checks.append({"name": "inside_each_chords_scale", "ok": ok_scale, "detail": f"{len(chord_following.scales)} chord scales"})
        checks.append({"name": "follows_the_timeline", "ok": True, "detail": f"{len(chord_following.segments)} chord segments"})
    beats = sum(Fraction(r["dur"]) for r in rhythm)
    per_bar = Fraction(_beats_per_bar(meter)).limit_denominator(4)
    checks.append({"name": "durations_fill_bars", "ok": beats == per_bar * int(concert.bars), "detail": f"{beats} beats / {concert.bars} bars"})

    intent = ExerciseIntent(
        raw_question=question, vocabulary=VOCAB_DEGREE_PATTERN, form="pattern", scope="section" if getattr(idea, "song_relative", False) else "single_chord",
        explicit_key=_clean(getattr(idea, "explicit_key", "")), length_bars=int(concert.bars), engine_route=ROUTE_LEGACY,
        route_reason="scale pattern: AMI's own generator; structured by the M1d adapter",
    )
    harmony = ("follows the chords of the section's timeline; each chord has its own scale" if kind == KIND_CHORDS
               else f"key-based: the {key.tonic} {key.tonality} scale throughout; no chord is attached to any note")
    prov: dict[str, Any] = {
        "engine": ENGINE, "kind": kind, "route": ROUTE_LEGACY, "title": title, "idea": asdict(idea), "register": _clean(getattr(idea, "register", "")),
        "written_events": serialize_events(written.events), "written_tonic": written.tonic, "written_tonality": written.tonality,
        "written_reference_key": written.reference_key, "written_scale_spelling": list(written.scale_spelling), "style": written.style,
        "strategy": written.strategy, "validation_ok": bool(concert.validation_ok), "validation_errors": list(concert.validation_errors),
        "practice_concert_key": ctx.concert_key, "scale_key": {"tonic": key.tonic, "tonality": key.tonality, "source": key.source},
        "rung": rung_of(idea), "written_note": written_note, "harmony": harmony, "offset": offset, "section_slots": list(section_slots or []),
        "segments": segments_info, "key_based_note": kind == KIND_KEY,
    }
    core = {"notes": notes, "midi": midi, "rhythm": [(r["on"], r["dur"]) for r in rhythm], "kind": kind, "chords": chords_distinct, "engine": ENGINE}
    ex = GeneratedExercise(
        id="ex-" + _sha(core), intent=intent, context=ctx, engine=ENGINE, vocabulary=VOCAB_DEGREE_PATTERN,
        engine_detail=ENGINE_DETAIL_CHORDS if kind == KIND_CHORDS else ENGINE_DETAIL,
        collection_label=(f"{key.tonic} {key.tonality} scale" if kind == KIND_KEY else f"scales for the chords in {key.token}"),
        collection_notes=list(concert.scale_spelling) if kind == KIND_KEY else [], chord=chords_distinct[0] if chords_distinct else "",
        tonic=key.tonic, mode=key.tonality, notes=notes, midi=midi, rhythm_events=rhythm, rhythm_symbols=[], meter=meter, bars=int(concert.bars),
        roles=degree_labels, chord_roles=chord_roles, chord_assignment=assignment, chords=chords_distinct, articulation=[""] * n,
        dynamics=[""] * n, accents=[False] * n, slur_groups=[0] * n, validation=_validation(checks, {"offset": offset}),
        explanation_facts={"kind": kind, "harmony": harmony, "scales": segments_info,
                           "limits": ["no chromatic approach or passing note outside the scale is added"] if kind == KIND_CHORDS else
                                     ["no chord relationship is claimed"]},
        provenance=prov,
    )
    ex.written = {
        "applied": bool(ctx.written_transposition_applied), "key": ctx.written_key or ctx.concert_key, "chord": "",
        "notes": [_clean(e.spelled) for e in w_events], "midi": [sph.midi_of(e.spelled, int(e.octave)) for e in w_events],
        "semitones": offset, "octave_shift": offset // 12,
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


def describe_harmony(ex: GeneratedExercise) -> list[str]:
    """Plain lines saying what the exercise follows, so the player is never told more than is true."""
    key = ex.provenance.get("scale_key") or {}
    if kind_of(ex) == KIND_KEY:
        return [f"_Key-based: every note comes from the {key.get('tonic')} {key.get('tonality')} scale (your Practice Key's own mode). "
                "It does not follow the chord changes — ask for “… over the chord changes” for a pattern that does._"]
    lines = ["**Scales by chord** — the line changes scale where the chord changes:"]
    seen: set[tuple[str, str]] = set()
    for seg in ex.provenance.get("segments") or []:
        key_ = (seg["chord"], seg["scale"])
        if key_ in seen:
            continue
        seen.add(key_)
        lines.append(f"- **{seg['chord']}** (bar {seg['bar']}, beat {seg['beat']}): {seg['scale']} — {' '.join(seg['scale_notes'])}. {seg['why'][:1].upper() + seg['why'][1:]}.")
    lines.append("_Every note is a chord tone or a note of that chord's scale; no chromatic approach notes are added._")
    return lines


def _prose(ex: GeneratedExercise, display_instrument: str) -> dict[str, Any]:
    from music_coach_ami.musical_idea_engine import play_summary

    comp = composition_of(ex)
    written_note = _clean(ex.provenance.get("written_note"))
    key = ex.provenance.get("scale_key") or {}
    what = "chord-following scale pattern" if kind_of(ex) == KIND_CHORDS else f"{key.get('tonality') or ex.mode} pattern in {key.get('tonic') or ex.tonic}"
    direct = f"**Try this {ex.bars}-bar {what}:**"
    if written_note:
        direct += f"\n\n{written_note}"
    steps = ["**Pattern** — read the staff notation below.", f"Use a comfortable register on **{display_instrument}**.", "**How to play it**",
             *play_summary(comp), *describe_harmony(ex)]
    return {"title": _clean(ex.provenance.get("title")), "direct_answer": direct, "practice_steps": steps,
            "what_to_listen_for": ["Even rhythm across the bar line", "Clear phrase shape", "Tone and articulation match your practice focus"]}


def _ladder_step(parent: GeneratedExercise, step: int) -> tuple[dict[str, str] | None, str]:
    cur = int(parent.provenance.get("rung", 1))
    new = cur + step
    if new < 0:
        return None, "This is already the easiest scale pattern I build (Beginner), so I haven't changed it."
    if new >= len(LADDER):
        return None, "This is already the hardest scale pattern I build (sixteenth notes in a 1-3-2-4 shape), so I haven't changed it."
    return LADDER[new], ""


def _regenerate(parent: GeneratedExercise, rung: dict[str, str]) -> tuple[GeneratedExercise | None, str]:
    from music_coach_ami import scale_pattern_chords as spc
    from music_coach_ami.musical_idea_engine import generate_scale_pattern
    from music_coach_ami.musical_idea_request import MusicalIdeaRequest
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    prov = parent.provenance
    raw = dict(prov["idea"])
    names = set(MusicalIdeaRequest.__dataclass_fields__)
    idea = MusicalIdeaRequest(**{k: v for k, v in raw.items() if k in names})
    idea = replace(idea, difficulty=rung["difficulty"], level=rung["difficulty"], rhythm=rung["rhythm"], interval_pattern=rung["interval_pattern"])
    notation_inst = parent.context.notation_instrument or parent.context.instrument
    key = sph.KeyScale(prov["scale_key"]["tonic"], prov["scale_key"]["tonality"], prov["scale_key"]["source"])
    label = rung["label"].rstrip("+")
    ctx = replace(parent.context, level=label, level_source="followup_difficulty")
    try:
        if kind_of(parent) == KIND_CHORDS:
            offset = projection_offset(notation_inst, ctx)
            cf = spc.generate(idea, list(prov["section_slots"]), key, notation_instrument=notation_inst, offset=offset, bars=parent.bars)
            written = spc.written_composition(cf, offset, written_key=ctx.written_key, semitones_mod12=int(ctx.transposition_semitones or 0))
            ex = build_exercise(kind=KIND_CHORDS, written=written, concert=cf.composition, idea=idea, ctx=ctx, question=parent.intent.raw_question,
                                title=_clean(prov.get("title")), written_note=_clean(prov.get("written_note")), key=key,
                                notation_instrument=notation_inst, chord_following=cf, section_slots=list(prov["section_slots"]))
        else:
            offset = projection_offset(notation_inst, ctx)
            concert = generate_scale_pattern(idea, notation_instrument=notation_inst, **window_args(notation_inst, offset))
            written = spc.key_based_written(concert, offset, written_key=ctx.written_key) if offset else concert
            ex = build_exercise(kind=KIND_KEY, written=written, concert=concert, idea=idea, ctx=ctx, question=parent.intent.raw_question,
                                title=_clean(prov.get("title")), written_note=_clean(prov.get("written_note")), key=key, notation_instrument=notation_inst)
    except (spc.ChordFollowingUnavailable, ValueError) as exc:
        return None, f"I couldn't build that version safely ({exc}), so nothing was changed."
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
    from music_coach_ami.exercise_followup import KIND_EASIER, KIND_EXPRESSION, KIND_HARDER, _carry_expression, _request_of, _stamp

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
        needs_roles = any(r.get("rule") == "role" and r.get("role") != "downbeat" for r in new_req.get("articulation") or [])
        if needs_roles and not any(parent.chord_roles):
            return _refusal("A key-based scale pattern has no chord tones, guide tones or other chord roles to target — try “accent the "
                            "downbeats” or “accent every second note”, or ask for a pattern over the chord changes. Your exercise is "
                            "unchanged.", fu, parent)
        merged = merge_requests(_request_of(parent), new_req)
        ex = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
        apply_expression(ex, merged, source={"articulation": "explicit", "dynamics": "inherited"})
        ex.intent = replace(ex.intent, expression=merged)
        ex = _stamp(ex, parent, fu, inherited=["notes", "rhythm", "key", "tempo"], changed=["articulation"], live=live)
    else:
        rung, why = _ladder_step(parent, 1 if fu.kind == KIND_HARDER else -1)
        if rung is None:
            return _refusal(why, fu, parent)
        ex, why = _regenerate(parent, rung)
        if ex is None:
            return _refusal(why, fu, parent)
        ex = _stamp(ex, parent, fu, inherited=["key", "scale" if kind_of(parent) == KIND_KEY else "chords", "tempo"], changed=["level", "notes", "rhythm"],
                    extra={"level_from": LADDER[int(parent.provenance.get("rung", 1))]["label"], "level_to": rung["label"]}, live=live)
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
