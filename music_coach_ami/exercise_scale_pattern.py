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

Follow-ups a scale pattern supports (M1c): the interval shape (scale steps, thirds, fourths, fifths), chromatic approach notes, rhythm
(syncopation, displacement), harmonic anticipation of the next chord, harder / easier (a deterministic walk through the recipe in
``scale_pattern_recipe``), accents and articulation. Everything else is refused in words and the exercise is left as it was.

The exercise carries its ``Recipe`` in ``provenance["recipe"]``; a revision changes the recipe fields it names and the line is
regenerated from the recipe by the deterministic engines (``scale_pattern_transforms`` for the approach / rhythm / anticipation layers).
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
from music_coach_ami import scale_pattern_transforms as tr
from music_coach_ami import scale_pattern_recipe as rc
from music_coach_ami.scale_pattern_recipe import Recipe, recipe_from_idea
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


_CORE_ROLES = ("R", "3", "5", "7", "6")


def core_tones(chord: str) -> set[int]:
    """Pitch classes of the chord's own tones (root, third, fifth, seventh, sixth) — tensions named in the symbol are not approach targets."""
    return {pc for pc, role in sph.chord_tone_roles(chord).items() if role in _CORE_ROLES}


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
    recipe: Recipe | None = None,
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
    from music_coach_ami.musical_idea_engine import _unit_duration

    recipe = recipe or recipe_from_idea(idea, _unit_duration(idea))
    tagged = (tr.APPROACH_BELOW, tr.APPROACH_ABOVE, tr.ANTICIPATION)
    plain_events = [e for e in c_events if e.tone_role not in tagged]   # approach notes and anticipations are checked on their own, below
    m1c_active = len(plain_events) != len(c_events) or bool(recipe.syncopation or recipe.displaced or recipe.anticipation or recipe.has_chromatic())
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
        checks.append({"name": "inside_scale", "ok": all(sph.pc_of(e.spelled) in scale_pcs for e in plain_events), "detail": " ".join(concert.scale_spelling)})
    else:
        ok_scale = all(sph.pc_of(e.spelled) in {sph.pc_of(x) for x in chord_following.scales[e.chord].notes} for e in plain_events)
        checks.append({"name": "inside_each_chords_scale", "ok": ok_scale, "detail": f"{len(chord_following.scales)} chord scales"})
        checks.append({"name": "follows_the_timeline", "ok": True, "detail": f"{len(chord_following.segments)} chord segments"})
    beats = sum(Fraction(r["dur"]) for r in rhythm)
    per_bar = Fraction(_beats_per_bar(meter)).limit_denominator(4)
    checks.append({"name": "durations_fill_bars", "ok": beats == per_bar * int(concert.bars), "detail": f"{beats} beats / {concert.bars} bars"})
    m1c_facts: dict[str, Any] = {}
    if m1c_active:
        if kind == KIND_CHORDS:
            def is_target(ev: Any) -> bool:
                return sph.pc_of(ev.spelled) in core_tones(ev.chord)
            chord_pcs = core_tones
        else:
            def is_target(ev: Any) -> bool:
                return ev.scale_degree in (1, 3, 5)
            chord_pcs = None
        problems = tr.verify(concert.events, per_bar=per_bar, bars=int(concert.bars), is_target=is_target, chord_pcs=chord_pcs)
        m1c_facts = tr.facts(concert.events, per_bar=per_bar)
        checks.append({"name": "approaches_rhythm_and_anticipations_verified", "ok": not problems,
                       "detail": "; ".join(problems) or (f"{len(m1c_facts['approaches'])} approach notes, {len(m1c_facts['anticipations'])} anticipations, "
                                                         f"bars add up")})

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
        "segments": segments_info, "key_based_note": kind == KIND_KEY, "recipe": recipe.to_dict(), "m1c": m1c_facts, "title_base": title,
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
        explanation_facts={"kind": kind, "harmony": harmony, "scales": segments_info, "limits": _limits(kind, recipe, m1c_facts)},
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


def _limits(kind: str, recipe: Recipe, facts: dict[str, Any]) -> list[str]:
    out = ["no chord relationship is claimed"] if kind == KIND_KEY else []
    if not facts.get("approaches") and not facts.get("anticipations"):
        out.append("no chromatic approach or passing note outside the scale is added")
    return out


def recipe_of(ex: GeneratedExercise) -> Recipe:
    raw = ex.provenance.get("recipe")
    if raw:
        return Recipe.from_dict(raw)
    from music_coach_ami.musical_idea_engine import _unit_duration
    from music_coach_ami.musical_idea_request import MusicalIdeaRequest

    names = set(MusicalIdeaRequest.__dataclass_fields__)
    idea = MusicalIdeaRequest(**{k: v for k, v in dict(ex.provenance.get("idea") or {}).items() if k in names})
    return recipe_from_idea(idea, _unit_duration(idea))


def _beat_text(beat: str) -> str:
    return {"1": "1", "1.5": "the “and” of 1", "2": "2", "2.5": "the “and” of 2", "3": "3", "3.5": "the “and” of 3", "4": "4",
            "4.5": "the “and” of 4"}.get(beat, beat)


_EXPECTED_SEMITONES = {"fourths": ({5}, 3), "fifths": ({7}, 4)}
_SPAN_NAME = {("fourths", 6): "an augmented fourth (a tritone)", ("fourths", 4): "a diminished fourth (it sounds like a major third)",
              ("fifths", 6): "a diminished fifth (a tritone)", ("fifths", 8): "an augmented fifth"}


def interval_remarks(ex: GeneratedExercise) -> list[str]:
    """Fourths and fifths are counted in scale steps, so each scale has a few that are not perfect. Say which, for the scales actually used."""
    shape = recipe_of(ex).shape
    if shape not in _EXPECTED_SEMITONES:
        return []
    ok, step = _EXPECTED_SEMITONES[shape]
    if kind_of(ex) == KIND_CHORDS:
        scales = {(g["scale"], tuple(g["scale_notes"])) for g in ex.provenance.get("segments") or []}
    else:
        key = ex.provenance.get("scale_key") or {}
        scales = {(f"{key.get('tonic')} {key.get('tonality')}", tuple(ex.collection_notes))}
    out: list[str] = []
    for label, notes in sorted(scales):
        if len(notes) != 7:
            continue
        for i, a in enumerate(notes):
            b = notes[(i + step) % 7]
            semis = (sph.pc_of(b) - sph.pc_of(a)) % 12
            if semis not in ok:
                out.append(f"in {label}, {a}–{b} is {_SPAN_NAME.get((shape, semis), f'{semis} semitones')}")
    return out[:4]


def describe_recipe(ex: GeneratedExercise) -> list[str]:
    """What the M1c layers did to this exercise, in plain lines. Empty for a plain M1d pattern (its text is unchanged)."""
    from music_coach_ami.scale_pattern_recipe import CELL_TEXT, SHAPE_NAME

    r = recipe_of(ex)
    facts = ex.provenance.get("m1c") or {}
    chords = kind_of(ex) == KIND_CHORDS
    lines: list[str] = []
    if r.shape != "scalar" and ex.provenance.get("transform"):
        lines.append(f"**Intervals** — {SHAPE_NAME[r.shape]}: {CELL_TEXT[(r.shape, r.tier)]}.")
        remarks = interval_remarks(ex)
        if remarks:
            lines.append(f"_Intervals are counted in scale steps, so a few aren't perfect: {'; '.join(remarks)}._")
    if r.has_chromatic():
        app = facts.get("approaches") or []
        what = "a chord tone" if chords else "a tone of the key's own tonic chord"
        if app:
            side = {"below": "from below", "above": "from above", "both": "from the side the line is coming from"}[r.approach]
            lines.append(f"**Chromatic approaches** ({side}) — {len(app)} note{'s' if len(app) != 1 else ''}. Each approach is a half step away from {what} "
                         "on a strong beat and resolves straight to it; it takes the place of the scale note that would have stood there:")
            for a in app[:6]:
                lines.append(f"- bar {a['bar']}, beat {_beat_text(a['beat'])}: {a['note']} → {a['target']}" + (f" ({a['chord']})" if a.get("chord") else ""))
            if len(app) > 6:
                lines.append(f"- … and {len(app) - 6} more")
            if not chords:
                lines.append("_These approach the key's tonic-triad tones, not chords — a key-based pattern doesn't follow the chord changes._")
        else:
            lines.append("**Chromatic approaches** — no strong-beat target had room for one, so none were added.")
    if r.syncopation or r.displaced:
        if r.syncopation:
            how = ("a longer note starts on the “and” of 1 (and of 3) and is held across the beat" if r.syncopation > 1
                   else "in every other two-beat group a longer note starts on the “and” and is held across the beat")
            lines.append(f"**Rhythm** — syncopated: {how}. The pitches are in the same order as before.")
        if r.displaced:
            lines.append("**Displacement** — each chord segment starts one subdivision late (a rest on the beat), so the line sits against the pulse; "
                         "to keep every note, the last note or two of each segment are shortened (a pick-up into what follows).")
    ants = facts.get("anticipations") or []
    if r.anticipation:
        if ants:
            lines.append(f"**Anticipations** — {len(ants)}: the first note of the next chord is played an eighth note early, in front of the chord change:")
            for a in ants[:6]:
                lines.append(f"- bar {a['bar']}, beat {_beat_text(a['beat'])}: {a['note']} (from {a['to_chord']}) while the chart still reads {a['from_chord']}")
            lines.append("_Only these notes come from the upcoming chord; the chord symbols stay where the chart changes them._")
        else:
            lines.append("**Anticipations** — no chord change had room for one.")
    return lines


def describe_harmony(ex: GeneratedExercise) -> list[str]:
    """Plain lines saying what the exercise follows, so the player is never told more than is true."""
    key = ex.provenance.get("scale_key") or {}
    facts = ex.provenance.get("m1c") or {}
    extra = bool(facts.get("approaches") or facts.get("anticipations"))
    if kind_of(ex) == KIND_KEY:
        tail = " — apart from the chromatic approach notes described below" if extra else ""
        return [f"_Key-based: every note comes from the {key.get('tonic')} {key.get('tonality')} scale (your Practice Key's own mode){tail}. "
                "It does not follow the chord changes — ask for “… over the chord changes” for a pattern that does._"]
    lines = ["**Scales by chord** — the line changes scale where the chord changes:"]
    seen: set[tuple[str, str]] = set()
    for seg in ex.provenance.get("segments") or []:
        key_ = (seg["chord"], seg["scale"])
        if key_ in seen:
            continue
        seen.add(key_)
        lines.append(f"- **{seg['chord']}** (bar {seg['bar']}, beat {seg['beat']}): {seg['scale']} — {' '.join(seg['scale_notes'])}. {seg['why'][:1].upper() + seg['why'][1:]}.")
    lines.append("_Apart from the approach notes and anticipations described below, every note is a chord tone or a note of that chord's scale._" if extra
                 else "_Every note is a chord tone or a note of that chord's scale; no chromatic approach notes are added._")
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
             *play_summary(comp), *describe_harmony(ex), *describe_recipe(ex)]
    listen = ["Even rhythm across the bar line", "Clear phrase shape", "Tone and articulation match your practice focus"]
    r = recipe_of(ex)
    if r.has_chromatic():
        listen[1] = "Each approach note leaning into its target"
    if r.syncopation or r.displaced:
        listen[0] = "The held notes landing against the pulse — keep the beat steady"
    return {"title": _clean(ex.provenance.get("title")), "direct_answer": direct, "practice_steps": steps, "what_to_listen_for": listen}


# ---------------------------------------------------------------- regenerating from a recipe


def _concert_bounds(notation_instrument: str, profile: Any, offset: int) -> tuple[int, int]:
    """The sounding range a line may use: the profile window (plus the engines' tolerance) and what the horn can write, minus the offset."""
    low, high = int(profile.midi_low) - _RANGE_TOLERANCE - offset, int(profile.midi_high) + _RANGE_TOLERANCE - offset
    playable = sph.playable_written_range(notation_instrument)
    if playable is not None:
        low, high = max(low, playable[0] - offset), min(high, playable[1] - offset)
    return low, high


def _suffix(r: Recipe) -> str:
    from music_coach_ami.scale_pattern_recipe import SHAPE_NAME

    bits = []
    if r.shape != "scalar":
        bits.append(SHAPE_NAME[r.shape].replace("diatonic ", "").title() if r.shape != "mixed" else "Thirds and Fourths")
    if r.has_chromatic():
        bits.append("Chromatic Approaches")
    if r.syncopation:
        bits.append("Syncopated")
    if r.displaced:
        bits.append("Displaced")
    if r.anticipation:
        bits.append("Anticipations")
    return (" — " + ", ".join(bits)) if bits else ""


def _layers(concert: Any, recipe: Recipe, *, pieces: list[tuple[Fraction, Fraction]], boundaries: list[tuple[Fraction, str, str]], chords: bool,
            bounds: tuple[int, int]) -> tuple[Any, dict[str, Any]]:
    """Apply the recipe's approach / rhythm / anticipation layers to a freshly generated (straight) concert-pitch pattern."""
    per_bar = tr.per_bar_of(concert.meter or "4/4")
    events = list(concert.events)
    info: dict[str, Any] = {"approaches": 0, "anticipations": 0, "anticipation_skipped": []}
    if recipe.has_chromatic():
        if chords:
            def is_target(ev: Any) -> bool:
                return sph.pc_of(ev.spelled) in core_tones(ev.chord)
        else:
            def is_target(ev: Any) -> bool:
                return ev.scale_degree in (1, 3, 5)
        events, applied = tr.add_approaches(events, per_bar=per_bar, mode=recipe.approach, density=recipe.approach_density, is_target=is_target,
                                            segment_starts={p[0] for p in pieces}, bounds=bounds)
        info["approaches"] = len(applied)
    if recipe.syncopation or recipe.displaced:
        events, _kept = tr.retime(events, per_bar=per_bar, pieces=pieces, level=recipe.syncopation, displaced=recipe.displaced)
    if recipe.anticipation and chords:
        events, records = tr.anticipate(events, per_bar=per_bar, boundaries=boundaries)
        info["anticipations"] = sum(1 for r in records if "skipped" not in r)
        info["anticipation_skipped"] = [r["skipped"] for r in records if "skipped" in r]
    return replace(concert, events=tuple(events)), info


def regenerate(parent: GeneratedExercise, recipe: Recipe) -> tuple[GeneratedExercise | None, str]:
    """Build the exercise for ``recipe`` from the parent's own song, section, key, instrument and tempo. ``(None, why)`` when it can't be
    done safely; the caller then leaves the exercise as it was."""
    from music_coach_ami import scale_pattern_chords as spc
    from music_coach_ami.musical_idea_engine import generate_scale_pattern
    from music_coach_ami.musical_idea_request import MusicalIdeaRequest

    prov = parent.provenance
    names = set(MusicalIdeaRequest.__dataclass_fields__)
    idea = MusicalIdeaRequest(**{k: v for k, v in dict(prov["idea"]).items() if k in names})
    rhythm = {"triplet_eighth": "triplet"}.get(recipe.subdivision, recipe.subdivision)
    idea = replace(idea, difficulty=recipe.level, level=recipe.level, rhythm=rhythm, interval_pattern=recipe.cell())
    notation_inst = parent.context.notation_instrument or parent.context.instrument
    key = sph.KeyScale(prov["scale_key"]["tonic"], prov["scale_key"]["tonality"], prov["scale_key"]["source"])
    ctx = replace(parent.context, level=recipe.level.capitalize(), level_source="followup_difficulty")
    base_title = _clean(prov.get("title_base")) or _clean(prov.get("title"))
    title = base_title + _suffix(recipe)
    chords = kind_of(parent) == KIND_CHORDS
    old = recipe_of(parent)
    try:
        offset = projection_offset(notation_inst, ctx)
        per_bar = tr.per_bar_of(parent.meter or "4/4")
        if chords:
            cf = spc.generate(idea, list(prov["section_slots"]), key, notation_instrument=notation_inst, offset=offset, bars=parent.bars)
            pieces = [(per_bar * s.bar + s.beat, s.beats) for s in cf.segments]
            boundaries = [(pieces[i][0], cf.segments[i - 1].chord, cf.segments[i].chord) for i in range(1, len(cf.segments))
                          if cf.segments[i].chord != cf.segments[i - 1].chord]
            bounds = _concert_bounds(notation_inst, cf.composition.notation_profile, offset)
            comp, info = _layers(cf.composition, recipe, pieces=pieces, boundaries=boundaries, chords=True, bounds=bounds)
            cf2 = replace(cf, composition=comp)
            written = spc.written_composition(cf2, offset, written_key=ctx.written_key, semitones_mod12=int(ctx.transposition_semitones or 0))
            written = replace(written, events=tuple(tr.respell_approaches(written.events)))
            ex = build_exercise(kind=KIND_CHORDS, written=written, concert=comp, idea=idea, ctx=ctx, question=parent.intent.raw_question, title=title,
                                written_note=_clean(prov.get("written_note")), key=key, notation_instrument=notation_inst, chord_following=cf2,
                                section_slots=list(prov["section_slots"]), recipe=recipe)
        else:
            concert = generate_scale_pattern(idea, notation_instrument=notation_inst, **window_args(notation_inst, offset))
            pieces = [(per_bar * b, per_bar) for b in range(int(parent.bars))]
            bounds = _concert_bounds(notation_inst, concert.notation_profile, offset)
            comp, info = _layers(concert, recipe, pieces=pieces, boundaries=[], chords=False, bounds=bounds)
            written = spc.key_based_written(comp, offset, written_key=ctx.written_key) if offset else comp
            written = replace(written, events=tuple(tr.respell_approaches(written.events)))
            ex = build_exercise(kind=KIND_KEY, written=written, concert=comp, idea=idea, ctx=ctx, question=parent.intent.raw_question, title=title,
                                written_note=_clean(prov.get("written_note")), key=key, notation_instrument=notation_inst, recipe=recipe)
    except tr.TransformUnavailable as exc:
        text = str(exc).strip().rstrip(".")
        return None, f"{text[:1].upper() + text[1:]}. Nothing was changed."
    except (spc.ChordFollowingUnavailable, ValueError) as exc:
        return None, f"I couldn't build that version safely ({exc}), so nothing was changed."
    if not ex.validation.get("ok"):
        bad = next((c for c in ex.validation["checks"] if not c["ok"]), {})
        return None, f"I couldn't build that version safely ({bad.get('name', 'validation')}: {bad.get('detail', 'failed')}), so nothing was changed."
    from music_coach_ami.musical_idea_engine import composition_to_abc

    _abc, ndiag = composition_to_abc(composition_of(ex), title=_clean(ex.provenance.get("title")) or "Scale pattern", bpm=int(parent.tempo_bpm or 96))
    if not ndiag.get("notation_validation_ok", True):
        return None, ("I couldn't build that version safely (the notation did not validate: "
                      f"{'; '.join(str(x) for x in ndiag.get('notation_validation_errors') or [])[:160]}), so nothing was changed.")
    if recipe.has_chromatic() and not old.has_chromatic() and not info["approaches"]:
        return None, (("No chord tone" if chords else "No tonic-chord tone") + " on a strong beat has room for a chromatic approach in this pattern, "
                      "so I haven't changed it.")
    if recipe.anticipation and not old.anticipation and not info["anticipations"]:
        why = info["anticipation_skipped"][0] if info["anticipation_skipped"] else "this section has no chord change within the pattern"
        return None, f"I couldn't anticipate any chord change ({why}), so I haven't changed the exercise."
    broken = revision_contract(parent, ex, old, recipe)
    if broken:
        return None, broken + ". Nothing was changed."
    ex.provenance["layers"] = info
    return ex, ""


_RHYTHM_FIELDS = ("syncopation", "displaced")
_PITCH_FIELDS = ("level", "shape", "tier", "approach", "approach_density")


def _line(ex: GeneratedExercise) -> tuple[list[tuple[str, int]], list[tuple[str, bool]]]:
    """(the pitches in order, the durations in order with a flag for rests) read back from the notation the player will see."""
    evs = ex.provenance["written_events"]
    pitches = [(str(e["spelled"]), int(e["octave"])) for e in evs if str(e["spelled"] or "").strip()]
    rhythm = [(str(e["duration"]).replace("rest_", ""), not str(e["spelled"] or "").strip()) for e in evs]
    return pitches, rhythm


def revision_contract(parent: GeneratedExercise, child: GeneratedExercise, old: Recipe, new: Recipe) -> str:
    """What a revision may and may not change, checked on the finished notation (a reason when it was broken, otherwise "").

    * A rhythm-only revision (syncopation / displacement only) keeps every pitch, in order.
    * A pitch-only revision (interval shape, tier, level, approaches) keeps the rhythm and every bar's length.
    Anticipation is the one explicit exception: it replaces notes by design and is the only layer allowed to do so.
    """
    def changed(fields: tuple[str, ...]) -> bool:
        return any(getattr(old, f) != getattr(new, f) for f in fields)

    p_old, r_old = _line(parent)
    p_new, r_new = _line(child)
    if changed(_RHYTHM_FIELDS) and not changed(_PITCH_FIELDS) and old.anticipation == new.anticipation:
        if p_old != p_new:
            if new.anticipation:
                return ("The anticipations are tied to the notes that fall in front of each chord change, so this rhythm would change which notes "
                        "they replace — take the anticipations out first, change the rhythm, then add them again")
            return "That rhythm can't keep all of your notes in order"
    if changed(_PITCH_FIELDS) and not changed(_RHYTHM_FIELDS) and old.anticipation == new.anticipation and new.subdivision == old.subdivision:
        if r_old != r_new:
            return "That change would have moved the rhythm, and you only asked for different notes"
    return ""


# ---------------------------------------------------------------- follow-ups


_PITCH_OPS = {"shape", "interval_advance", "wider", "narrower", "simplify_notes", "approach", "approach_more", "approach_off"}
_RHYTHM_OPS = {"displace", "sync_more", "sync_less", "new_rhythm"}


def _payload(ex: GeneratedExercise, parent: GeneratedExercise, header: str, base_diag: dict[str, Any], *, display_instrument: str, bpm: int,
             session_ref: Any) -> dict[str, Any]:
    from music_coach_ami.exercise_bridge import store_last_exercise

    ex.tempo_bpm = int(bpm)
    abc, _comp = render(ex, bpm=int(bpm))
    prose = _prose(ex, display_instrument)
    stored = store_last_exercise(session_ref, ex)
    return {
        "direct_answer": "\n\n".join([header, prose["direct_answer"]]),
        "practice_steps": prose["practice_steps"], "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Try: slower, more advanced, change the intervals, add chromatic approaches or syncopation, add accents, or undo that.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [],
        "diagnostics": {**base_diag, "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(), "exercise_context": ex.context.to_dict(),
                        "exercise_validation": ex.validation, "notation_abc_present": bool(abc), "last_exercise_stored": stored,
                        "transform": ex.transform, "practice_concert_key": ex.context.concert_key, "written_key": ex.context.written_key,
                        "resolved_instrument": ex.context.instrument, "notation_instrument": ex.context.notation_instrument,
                        "bars_generated": ex.bars},
    }


def revise(parent: GeneratedExercise, ops: tuple[tuple[str, str], ...], fu: Any, *, session_ref: Any, display_instrument: str, bpm: int,
           expression: dict[str, Any] | None = None, bare_accent: bool = False, notes: tuple[str, ...] = (),
           live: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply recipe changes (``scale_pattern_recipe.PatternChange.ops``) to a scale-pattern exercise and return the answer payload."""
    from music_coach_ami.exercise_expression import apply_expression, has_rules, merge_requests
    from music_coach_ami.exercise_followup import KIND_EASIER, KIND_HARDER, _carry_expression, _request_of, _stamp
    from music_coach_ami.scale_pattern_recipe import apply_ops

    base_diag = {"musical_idea_content": True, "exercise_followup": True, "followup_kind": fu.kind, "followup_utterance": fu.raw,
                 "parent_exercise_id": parent.id, "scale_pattern_exercise": True}
    old = recipe_of(parent)
    names = {n for n, _a in ops}
    skipped: list[str] = []
    if names <= {"harder", "easier"} and len(ops) == 1:
        # difficulty: take the first step that this instrument and chord range can actually hold, and say which ones didn't fit
        up = names == {"harder"}
        cands = rc.advance_candidates(old) if up else rc.ease_candidates(old)
        if not cands:
            _r, _c, why = apply_ops(old, ops, chord_following=kind_of(parent) == KIND_CHORDS)
            return _refusal(why + " Your exercise is unchanged.", fu, parent)
        ex, last_why = None, ""
        known = list(parent.provenance.get("skipped_steps") or [])      # steps already found not to fit this instrument: not retried, not repeated
        tried: list[str] = []
        for cand, text in cands:
            if text in known:
                tried.append(text)
                continue
            ex, last_why = regenerate(parent, cand)
            if ex is not None:
                new, changes = cand, [text if up else f"simplified: {text}"]
                break
            skipped.append(text)
            tried.append(text)
        if ex is None:
            return _refusal(f"This is already the {'hardest' if up else 'easiest'} version I can build on {display_instrument} for this pattern "
                            f"(the remaining step — {', '.join(tried)} — can't be built here without losing notes or leaving the instrument's range), so I haven't changed it. Your exercise is unchanged.",
                            fu, parent)
        ex.provenance["skipped_steps"] = known + skipped
    else:
        new, changes, why = apply_ops(old, ops, chord_following=kind_of(parent) == KIND_CHORDS)
        if why:
            return _refusal(why + " Your exercise is unchanged.", fu, parent)
        ex, why = regenerate(parent, new)
        if ex is None:
            return _refusal(why, fu, parent)
    changed = (["notes"] if names & _PITCH_OPS else []) + (["rhythm"] if names & _RHYTHM_OPS else [])
    if names & {"harder", "easier"}:
        changed = ["level", "notes", "rhythm"] if (old.subdivision != new.subdivision or old.level != new.level) else ["level", "notes"]
    if "anticipate" in names:
        changed.append("a few notes at the chord changes")
    inherited = ["song", "section", "key", "instrument", "tempo", "scale" if kind_of(parent) == KIND_KEY else "chords"]
    if "rhythm" not in changed:
        inherited.append("rhythm")
    if names <= _RHYTHM_OPS:
        inherited.append("pitch order")
    ex = _stamp(ex, parent, fu, inherited=inherited, changed=changed,
                extra={"level_from": old.label(), "level_to": new.label(), "recipe_changes": changes}, live=live or {})
    _carry_expression(parent, ex, fu)
    if expression and has_rules(expression):
        merged = merge_requests(_request_of(ex) or _request_of(parent), expression)
        apply_expression(ex, merged, source={"articulation": "explicit", "dynamics": "inherited"})
        ex.intent = replace(ex.intent, expression=merged)
    if fu.kind in (KIND_HARDER, KIND_EASIER):
        header = _header(ex, parent) + "\n\n" + ("Added: " if fu.kind == KIND_HARDER else "") + "; ".join(changes) + "."
    else:
        said = "; ".join(changes)
        header = (f"**{said[:1].upper() + said[1:]}** — your same exercise, revised.\n\n"
                  f"Kept: {', '.join(inherited)} · Changed: {', '.join(changed) or '—'}")
        if bare_accent:
            header += "\n\n_You didn't say which notes to accent, so I accented the downbeats — say “accent the guide tones” (or another group) to change that._"
    if skipped:
        header += f"\n\n_I skipped {', '.join(skipped)}: it can't be built on this pattern for {display_instrument} without losing notes or leaving the instrument's range, so I took the next step instead._"
    if "jazz_vocabulary" in notes:
        header += ("\n\n_Chromatic approach notes are the jazz vocabulary I can add so far — enclosures, bebop scales and longer licks aren't "
                   "something I build yet._")
    return _payload(ex, parent, header, base_diag, display_instrument=display_instrument, bpm=bpm, session_ref=session_ref)


def compose_scale_followup(fu: Any, parent: GeneratedExercise, *, session_ref: Any, instrument: str, notation_instrument: str,
                           display_instrument: str, bpm: int) -> dict[str, Any]:
    """The follow-ups a scale-pattern exercise supports. ``bpm`` is the working tempo."""
    from music_coach_ami.exercise_expression import apply_expression, has_rules, merge_requests
    from music_coach_ami.exercise_followup import KIND_EASIER, KIND_EXPRESSION, KIND_HARDER, _request_of, _stamp

    base_diag = {"musical_idea_content": True, "exercise_followup": True, "followup_kind": fu.kind, "followup_utterance": fu.raw,
                 "parent_exercise_id": parent.id, "scale_pattern_exercise": True}
    if fu.kind not in (KIND_HARDER, KIND_EASIER, KIND_EXPRESSION):
        what = _UNSUPPORTED_TEXT.get(fu.kind, "that")
        return _refusal(f"I can't do {what} to a scale pattern yet. Your exercise is unchanged.", fu, parent)
    if fu.explicit_key or fu.explicit_chord or fu.current_context or fu.level:
        return _refusal("I can't change the key, chord or level of a scale pattern that way yet — say “harder” or “easier”. "
                        "Your exercise is unchanged.", fu, parent)
    # A scale pattern keeps the instrument it was written for (M1b can change it on request), so a follow-up is never "rebound" to the page's
    # instrument: leaving ``instrument`` out keeps the shared "notated for your current instrument" note from being claimed here.
    live = {"session_ref": session_ref, "notation_inst": notation_instrument}
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
        return _payload(ex, parent, _header(ex, parent), base_diag, display_instrument=display_instrument, bpm=bpm, session_ref=session_ref)
    return revise(parent, ((("harder" if fu.kind == KIND_HARDER else "easier"), ""),), fu, session_ref=session_ref,
                  display_instrument=display_instrument, bpm=bpm, live=live)
