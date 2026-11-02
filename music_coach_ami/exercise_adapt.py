"""AMI M1b: conversational instrument changes and song-section retargeting of the working scale pattern.

Handled here, deterministically and with no API call:

* instrument - "make this suitable for flute", "change it from alto saxophone to tenor saxophone", "play it on soprano saxophone instead"
* section    - "apply it to the chorus", "change it to Verse 2", "use the chord changes from Section B"

Both act on the structured working exercise (``exercise_scale_pattern``) and produce a new version of it, so undo and redo work.

**Instrument change** keeps the *sounding* line. Every note keeps its concert pitch, rhythm, chord, articulation and accent; only the written
projection changes (the instrument's exact written-minus-sounding offset, octave included, and the written key). If the line does not fit the new
instrument's range, the whole line moves by whole octaves — the smallest verified shift — and the answer says so. If no octave shift fits, the
same recipe (interval shape, approaches, rhythm, harmony) is rebuilt in the new instrument's register and the answer says that the notes were
re-voiced; if that cannot keep the rhythm and note count either, nothing changes. Only instruments whose written pitch is verified are
supported. The app's global instrument selection is never read or written: the target instrument's written context is resolved from an
isolated mapping.

**Section retargeting** keeps the recipe and rebuilds the line over the target section's real chords, split bars and chord durations (the chart
the app is showing, in the Practice Key). A key-based pattern is not tied to any chord, so it is never relabelled for another section.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami import scale_pattern_transforms as tr
from music_coach_ami.exercise_model import ActiveContext, GeneratedExercise

KIND_INSTRUMENT, KIND_SECTION, KIND_BOTH = "instrument", "section", "both"
PENDING_KEY = "_ami_conv_pending"        # a question AMI asked ("which saxophone?" / "which section?"); purged with the conversation


@dataclass(frozen=True)
class InstrumentSpec:
    key: str
    label: str            # what the player sees ("Alto Saxophone")
    notation: str         # the notation / transposition table name
    family: str           # the instrument the app's written-context builder is given
    ttype: str            # the app's transposing-type label ("" for a concert-pitch instrument)


SPECS: dict[str, InstrumentSpec] = {
    "flute": InstrumentSpec("flute", "Flute", "Flute", "Flute", ""),
    "piano": InstrumentSpec("piano", "Piano", "Piano", "Piano", ""),
    "alto": InstrumentSpec("alto", "Alto Saxophone", "Alto Saxophone", "Saxophone", "Alto saxophone (Eb)"),
    "tenor": InstrumentSpec("tenor", "Tenor Saxophone", "Tenor Saxophone", "Saxophone", "Tenor saxophone (Bb)"),
    "soprano": InstrumentSpec("soprano", "Soprano Saxophone", "Soprano Saxophone", "Saxophone", "Soprano saxophone (Bb)"),
    "baritone": InstrumentSpec("baritone", "Baritone Saxophone", "Baritone Saxophone", "Saxophone", "Baritone saxophone (Eb)"),
    "trumpet": InstrumentSpec("trumpet", "Trumpet", "Trumpet", "Trumpet", "Bb Trumpet"),
    "clarinet": InstrumentSpec("clarinet", "Clarinet", "Clarinet", "Clarinet", "Bb Clarinet"),
}
_SUPPORTED_TEXT = "flute, piano, soprano / alto / tenor / baritone saxophone, trumpet and clarinet"
_UNVERIFIED = ("trombone", "violin", "viola", "cello", "guitar", "bass", "oboe", "horn", "bassoon", "ukulele", "banjo", "recorder", "voice",
               "vocals", "harp", "tuba", "euphonium", "flugelhorn", "piccolo", "mandolin", "harmonica", "accordion", "organ", "keyboard")

_SAX = r"(?:soprano|alto|tenor|bari(?:tone)?)\s+sax(?:ophone)?|sax(?:ophone)?"
_BARE = r"soprano|alto|tenor|bari(?:tone)?"
_NAMED = rf"{_SAX}|flute|piano|trumpet|clarinet|{'|'.join(_UNVERIFIED)}"
_ART = r"(?:a\s+|an\s+|the\s+|my\s+)?"
_REF = re.compile(r"\b(?:it|this|that|these|those|same|the (?:exercise|pattern|line|phrase|idea|lick|notes?))\b")
_QUESTION_START = re.compile(r"^(?:how|what|which|where|when|who|is|are|does|do|did|can i|should i|why)\b")
_LEAD = r"^(?:(?:please|can you|could you|would you|now|then|and|ok|okay|so)[, ]+)*"

_FROM_TO = re.compile(rf"\bfrom\s+{_ART}(?P<a>{_NAMED}|{_BARE})\s+(?:\w+\s+)?to\s+{_ART}(?P<b>{_NAMED}|{_BARE})\b")
_FOR_ON = re.compile(
    rf"\b(?:suitable|good|better|right|ideal|appropriate|adapt\w*|rewrite|transpose|convert|switch|swap|change|play|try|port|arrange|make|do|put|give|"
    rf"write|set|use)\b.{{0,40}}?\b(?:for|on|to|onto|in|with)\s+{_ART}(?P<t>{_NAMED})\b")
_NO_TARGET = re.compile(r"\b(?:change|switch|swap|different|another|other)\s+(?:the\s+|my\s+)?instrument(?:s)?\b")

_SEC = (r"(?:(?:section|part)\s+[a-z]\b|[a-z]\s+section\b|(?:intro|verse|chorus|pre[- ]?chorus|bridge|solo|outro|groove|refrain|interlude|head|tag|coda)"
        r"(?:\s*#?\d{1,2}\b)?)")
_SECTION = re.compile(
    rf"\b(?:apply|use|move|transfer|play|try|put|switch|change|retarget|shift|run|take|rebuild|adapt)\b.{{0,60}}?"
    rf"\b(?:to|on|onto|over|in|from|for|of)\s+(?:the\s+)?(?:chord\s+(?:changes|progression)\s+(?:from|of|in|for|to)\s+)?(?:the\s+)?(?P<sec>{_SEC})")


@dataclass(frozen=True)
class Adaptation:
    kind: str                       # instrument | section | both
    raw: str = ""
    target: str = ""                # SPECS key
    source: str = ""                # "from alto" (named by the player; only echoed back)
    unverified: str = ""            # an instrument named that has no verified pitch table
    ask_which: bool = False         # "a saxophone" / "change the instrument": the player has to say which
    section_text: str = ""


def _norm(question: str) -> str:
    return re.sub(r"\s+", " ", str(question or "").lower()).strip(" .!?,;:")


def _spec_key(word: str) -> str:
    w = word.lower().strip()
    for name in ("soprano", "alto", "tenor"):
        if w.startswith(name):
            return name
    if w.startswith("bari"):
        return "baritone"
    if w.startswith("sax"):
        return "sax"
    return w if w in SPECS else ("unverified:" + w if w in _UNVERIFIED else "")


def parse_adaptation(question: str) -> Adaptation | None:
    """Instrument or section change of the working exercise, or ``None``. Needs a reference to the exercise, so a fresh request
    ("give me a flute exercise over Blue Bossa") is never taken for a revision."""
    raw = str(question or "").strip()
    low = _norm(raw)
    low = re.sub(_LEAD, "", low)
    if not low or len(low.split()) > 26 or _QUESTION_START.match(low):
        return None
    if re.search(r"\b(?:give me|show me|write me|create|generate|build)\b", low) and not _REF.search(low):
        return None
    inst_key, source, unverified, ask = "", "", "", False
    m = _FROM_TO.search(low)
    if m:
        a, b = _spec_key(m.group("a")), _spec_key(m.group("b"))
        source, inst_key = m.group("a"), b
    else:
        m2 = _FOR_ON.search(low)
        if m2 and (_REF.search(low) or re.match(r"(?:play|try)\b", low)):
            inst_key = _spec_key(m2.group("t"))
        elif _NO_TARGET.search(low) and _REF.search(low):
            ask = True
    if inst_key == "sax":
        inst_key, ask = "", True
    if inst_key.startswith("unverified:"):
        unverified, inst_key = inst_key.split(":", 1)[1], ""
    sec = _SECTION.search(low)
    section_text = sec.group("sec").strip() if sec and (_REF.search(low) or re.search(r"\b(?:chord changes|instead)\b", low)) else ""
    has_inst = bool(inst_key or unverified or ask)
    if has_inst and section_text:
        return Adaptation(KIND_BOTH, raw=raw)
    if has_inst:
        return Adaptation(KIND_INSTRUMENT, raw=raw, target=inst_key, source=source, unverified=unverified, ask_which=ask and not inst_key)
    if section_text:
        return Adaptation(KIND_SECTION, raw=raw, section_text=section_text)
    return None


def parse_pending_answer(question: str, pending: dict[str, Any]) -> Adaptation | None:
    """The player's answer to "which saxophone?" / "which section?": a bare name, optionally in a short sentence."""
    low = _norm(question)
    if not low or len(low.split()) > 6:
        return None
    low = re.sub(r"^(?:the|use|try|make it|play it on|on|for|i meant|i mean|let's do|lets do)\s+", "", low).strip()
    if pending.get("kind") == KIND_INSTRUMENT:
        m = re.fullmatch(rf"(?:the\s+)?({_NAMED}|{_BARE})(?:\s+sax(?:ophone)?)?", low)
        if m:
            key = _spec_key(m.group(1))
            if key.startswith("unverified:"):
                return Adaptation(KIND_INSTRUMENT, raw=question, unverified=key.split(":", 1)[1])
            return Adaptation(KIND_INSTRUMENT, raw=question, target=key if key in SPECS else "", ask_which=key not in SPECS)
    if pending.get("kind") == KIND_SECTION:
        for cand in pending.get("options") or []:
            if _norm(cand) == low or _norm(cand).replace("section ", "").replace("part ", "") == low:
                return Adaptation(KIND_SECTION, raw=question, section_text=str(cand))
        m = re.fullmatch(rf"(?:the\s+)?(?:{_SEC})", low)
        if m:
            return Adaptation(KIND_SECTION, raw=question, section_text=m.group(0))
    return None


# ---------------------------------------------------------------- shared helpers


def _clean(value: object) -> str:
    return str(value or "").strip()


def _refusal(reason: str, parent: GeneratedExercise, question: str, *, steps: list[str] | None = None, kind: str = "adapt") -> dict[str, Any]:
    return {
        "ok": False, "direct_answer": reason,
        "practice_steps": steps or ["Your exercise is unchanged — you can still change the tempo, make it harder or easier, change the intervals, "
                                    "add approaches or accents, and undo or redo."],
        "diagnostics": {"exercise_revision_kind": kind, "exercise_revision_failed": True, "exercise_revision_failure_reason": reason[:160],
                        "parent_exercise_id": parent.id, "utterance": question},
    }


def _idea_of(parent: GeneratedExercise, recipe: Any) -> Any:
    from music_coach_ami.musical_idea_request import MusicalIdeaRequest

    names = set(MusicalIdeaRequest.__dataclass_fields__)
    idea = MusicalIdeaRequest(**{k: v for k, v in dict(parent.provenance["idea"]).items() if k in names})
    rhythm = {"triplet_eighth": "triplet"}.get(recipe.subdivision, recipe.subdivision)
    return replace(idea, difficulty=recipe.level, level=recipe.level, rhythm=rhythm, interval_pattern=recipe.cell())


def _key_of(parent: GeneratedExercise) -> sph.KeyScale:
    k = parent.provenance["scale_key"]
    return sph.KeyScale(k["tonic"], k["tonality"], k["source"])


def _rhythm_sig(ex: GeneratedExercise) -> Any:
    from music_coach_ami.exercise_followup import rhythm_signature

    return rhythm_signature(ex)


def _retitle(base: str, bars: int, notation: str, written_tonic: str, with_written: bool) -> str:
    text = re.sub(r"\s+—\s+Written in \S+ for [A-Za-z ]+$", "", _clean(base))
    text = re.sub(r"^\d+-Bar", f"{int(bars)}-Bar", text)
    return text + (f" — Written in {written_tonic} for {notation}" if with_written else "")


def _written_note(key: sph.KeyScale, written_tonic: str, written_tonality: str, notation: str, offset: int) -> str:
    if not offset:
        return ""
    return (f"**Concert key:** {key.tonic} {key.tonality}  \n**Written key:** {written_tonic}"
            f"{(' ' + (written_tonality or key.tonality)) if (written_tonality or key.tonality) else ''} for **{notation}**").strip()


def _carry_expression_exact(parent: GeneratedExercise, ex: GeneratedExercise) -> None:
    """Markings stay on the same notes: the note count and order are identical, so the arrays are copied, not recomputed."""
    ex.articulation, ex.accents = list(parent.articulation), list(parent.accents)
    ex.slur_groups, ex.dynamics = list(parent.slur_groups), list(parent.dynamics)
    ex.dynamic_marks = copy.deepcopy(parent.dynamic_marks)
    ex.expression = copy.deepcopy(parent.expression)
    ex.intent = replace(ex.intent, expression=copy.deepcopy(parent.intent.expression))


def _written_context(spec: InstrumentSpec, parent: GeneratedExercise) -> Any:
    """The app's own written context for ``spec``, resolved from an isolated mapping so the global instrument selection is never touched."""
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    from music_coach_ami.written_music_context import build_written_music_context

    iso = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: spec.ttype} if spec.ttype else {}
    ctx0 = parent.context
    return build_written_music_context(
        instrument=spec.family, practice_concert_key=ctx0.concert_key, original_song_key=_clean(ctx0.key_candidates.get("catalog_original_key")) or ctx0.concert_key,
        concert_chords=[], session_state=iso, register=_clean(parent.provenance.get("register")), chart_already_in_practice_key=True)


def _same_instrument(parent: GeneratedExercise, spec: InstrumentSpec) -> bool:
    cur = _clean(parent.context.notation_instrument or parent.context.instrument).lower()
    return cur == spec.notation.lower()


def _profile_for(notation: str, register: str) -> Any:
    from music_coach_ami.notation_profile import apply_register_override, notation_profile_for_instrument

    return apply_register_override(notation_profile_for_instrument(notation), register)


def _fit_octaves(midi: list[int], offset: int, notation: str, profile: Any) -> list[int]:
    """Whole-octave shifts (in octaves) of the sounding line that keep every written note inside the app's window for the instrument and what
    the horn can play."""
    low, high = int(profile.midi_low) - 2, int(profile.midi_high) + 2
    play = sph.playable_written_range(notation)
    if play is not None:
        low, high = max(low, play[0]), min(high, play[1])
    return [k for k in range(-4, 5) if all(low <= m + 12 * k + offset <= high for m in midi)]


def _best_octave(ks: list[int], midi: list[int], offset: int, profile: Any) -> int:
    centre = (int(profile.midi_low) + int(profile.midi_high)) / 2.0
    mean = sum(midi) / max(1, len(midi))
    return min(ks, key=lambda k: (abs(k), abs(mean + 12 * k + offset - centre)))


def _native(parent: GeneratedExercise, idea: Any, notation: str, offset: int, key: sph.KeyScale) -> tuple[Any, Any]:
    """(the notation profile the engines themselves build a pattern for ``notation`` with, the chord-following result or ``None``).
    Taken from the generator rather than guessed, so a piano line is held to the right-hand window the engines use. Raises ``ValueError``
    (``ChordFollowingUnavailable``) when this exercise cannot be built for the instrument at all."""
    from music_coach_ami import exercise_scale_pattern as esp
    from music_coach_ami import scale_pattern_chords as spc
    from music_coach_ami.musical_idea_engine import generate_scale_pattern

    if esp.kind_of(parent) == esp.KIND_CHORDS:
        cf = spc.generate(idea, list(parent.provenance["section_slots"]), key, notation_instrument=notation, offset=offset, bars=parent.bars)
        return cf.composition.notation_profile, cf
    comp = generate_scale_pattern(idea, notation_instrument=notation, **esp.window_args(notation, offset))
    return comp.notation_profile, None


# ---------------------------------------------------------------- the exercise rebuilt from stored data


def _concert_rows(parent: GeneratedExercise, octave_shift: int) -> list[dict[str, Any]]:
    """The stored line as concert-pitch event rows (same rests, durations, roles and chords), moved ``octave_shift`` octaves."""
    prov = parent.provenance
    rows = copy.deepcopy(prov["written_events"])
    kind = esp_kind(parent)
    to_concert: dict[str, str] = {}
    note_i = 0
    for row in rows:
        if esp_is_rest(row):
            continue
        if kind == "chord_following":
            to_concert.setdefault(_clean(row.get("chord")), parent.chords[parent.chord_assignment[note_i]])
        note_i += 1
    note_i = 0
    for row in rows:
        if esp_is_rest(row):
            row["domain"] = "concert"
            if kind == "chord_following" and _clean(row.get("chord")):
                if _clean(row["chord"]) not in to_concert:
                    raise ValueError("a rest carries a chord label I can't map back to the sounding chord")
                row["chord"] = to_concert[_clean(row["chord"])]
            continue
        spelled, midi = parent.notes[note_i], int(parent.midi[note_i]) + 12 * octave_shift
        row.update(spelled=spelled, octave=sph.octave_for(spelled, midi), pitch_class=sph.pc_of(spelled), domain="concert")
        if kind == "chord_following":
            row["chord"] = parent.chords[parent.chord_assignment[note_i]]
        note_i += 1
    if note_i != len(parent.notes):
        raise ValueError("the stored notes and the stored notation disagree")
    return rows


def esp_kind(ex: GeneratedExercise) -> str:
    from music_coach_ami import exercise_scale_pattern as esp

    return esp.kind_of(ex)


def esp_is_rest(row: dict[str, Any]) -> bool:
    return str(row.get("duration") or "").lower().startswith("rest") or not _clean(row.get("spelled"))


def _project(parent: GeneratedExercise, spec: InstrumentSpec, ctx1: ActiveContext, offset: int, octave_shift: int, question: str,
             profile: Any, cf: Any) -> GeneratedExercise:
    """The parent's sounding line (moved ``octave_shift`` octaves) written for ``spec``; ``ValueError`` when anything cannot be verified."""
    from music_coach_ami import exercise_scale_pattern as esp
    from music_coach_ami import scale_pattern_chords as spc
    from music_theory import transpose_chord

    prov = parent.provenance
    recipe = esp.recipe_of(parent)
    kind = esp.kind_of(parent)
    key = _key_of(parent)
    idea = _idea_of(parent, recipe)
    notation = ctx1.notation_instrument
    base = esp.composition_of(parent)
    rows = _concert_rows(parent, octave_shift)
    concert = replace(base, events=esp._events_from(rows), tonic=key.tonic, tonality=key.tonality, reference_key=key.token,
                      scale_spelling=tuple(parent.collection_notes) if kind == esp.KIND_KEY else tuple(), notation_profile=profile,
                      validation_ok=True, validation_errors=())
    semis = int(ctx1.transposition_semitones or 0)
    if kind == esp.KIND_CHORDS:
        cf = replace(cf, composition=concert)
        written = spc.written_composition(cf, offset, written_key=ctx1.written_key, semitones_mod12=semis)
    else:
        written = spc.key_based_written(concert, offset, written_key=ctx1.written_key) if offset else concert
    written = replace(written, events=tuple(tr.respell_approaches(written.events)), notation_profile=profile)
    note = _written_note(key, written.tonic, written.tonality, notation, offset)
    title = _retitle(prov.get("title_base") or prov.get("title"), parent.bars, notation, written.tonic, bool(note))
    ex = esp.build_exercise(kind=kind, written=written, concert=concert, idea=idea, ctx=ctx1, question=parent.intent.raw_question, title=title,
                            written_note=note, key=key, notation_instrument=notation, chord_following=cf,
                            section_slots=list(prov.get("section_slots") or []), recipe=recipe)
    if not ex.validation.get("ok"):
        bad = next((c for c in ex.validation["checks"] if not c["ok"]), {})
        raise ValueError(f"{bad.get('name', 'validation')}: {bad.get('detail', 'failed')}")
    _carry_expression_exact(parent, ex)
    ex.provenance["title_base"] = _retitle(prov.get("title_base") or prov.get("title"), parent.bars, notation, written.tonic, bool(note))
    ex.provenance["layers"] = copy.deepcopy(prov.get("layers") or {})
    ex.provenance["skipped_steps"] = list(prov.get("skipped_steps") or [])
    # the contract: the same line, rhythm, harmony and markings; only the written projection (and a whole-octave shift) differ
    if [int(m) - 12 * octave_shift for m in ex.midi] != [int(m) for m in parent.midi] or ex.notes != parent.notes:
        raise ValueError("the sounding notes changed")
    if _rhythm_sig(ex) != _rhythm_sig(parent) or ex.bars != parent.bars:
        raise ValueError("the rhythm changed")
    if ex.chords != parent.chords or ex.chord_assignment != parent.chord_assignment:
        raise ValueError("the harmony changed")
    return ex


def _adapted_parent(parent: GeneratedExercise, ctx1: ActiveContext, note: str, title_base: str) -> GeneratedExercise:
    p2 = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
    p2.context = ctx1
    p2.provenance["written_note"] = note
    p2.provenance["title_base"] = title_base
    return p2


# ---------------------------------------------------------------- instrument change


def _fmt_octaves(k: int) -> str:
    n = abs(k)
    return f"{n} octave{'s' if n != 1 else ''} {'up' if k > 0 else 'down'}"


def _interval_name(offset: int) -> str:
    return {0: "the same as", 2: "a major second above", 9: "a major sixth above", 14: "a major ninth above", 21: "a major thirteenth above"}.get(
        offset, f"{offset} semitones above")


def change_instrument(parent: GeneratedExercise, spec: InstrumentSpec, *, question: str, bpm: int, session_ref: Any) -> dict[str, Any]:
    from music_coach_ami import exercise_scale_pattern as esp
    from music_coach_ami.exercise_followup import FollowUp, _stamp

    old_name = _clean(parent.context.notation_instrument or parent.context.instrument) or "your instrument"
    if _same_instrument(parent, spec):
        return _refusal(f"This exercise is already written for **{spec.label}**, so I haven't changed anything.", parent, question, kind="instrument")
    try:
        wctx = _written_context(spec, parent)
        notation = _clean(wctx.provenance.get("notation_instrument")) or spec.notation
        ctx1 = replace(parent.context, instrument=spec.label, notation_instrument=notation, written_key=_clean(wctx.written_key),
                       written_transposition_applied=bool(wctx.written_transposition_applied),
                       transposition_semitones=int(wctx.transposition_semitones or 0))
        offset = esp.projection_offset(notation, ctx1)
    except (ValueError, ImportError) as exc:
        return _refusal(f"I can't verify the written pitch for {spec.label} ({exc}), so I haven't changed your exercise.", parent, question, kind="instrument")
    recipe0 = esp.recipe_of(parent)
    try:
        profile, cf = _native(parent, _idea_of(parent, recipe0), notation, offset, _key_of(parent))
    except ValueError as exc:
        return _refusal(f"I can't build this {'chord-following ' if esp.kind_of(parent) == esp.KIND_CHORDS else ''}pattern for **{spec.label}** yet "
                        f"({_clean(exc).rstrip('.')}), so I haven't changed your exercise.", parent, question, kind="instrument")
    ks = _fit_octaves([int(m) for m in parent.midi], offset, notation, profile)
    shift = _best_octave(ks, [int(m) for m in parent.midi], offset, profile) if ks else None
    how, ex, why_fail = "", None, ""
    if shift is not None:
        try:
            ex = _project(parent, spec, ctx1, offset, shift, question, profile, cf)
            how = "kept" if shift == 0 else "octave"
        except (ValueError, KeyError, IndexError) as exc:
            why_fail = str(exc)
    if ex is None:
        # the sounding line does not fit this instrument at any octave: the same recipe, rebuilt in its register
        recipe = esp.recipe_of(parent)
        key = _key_of(parent)
        written_tonic = sph._token_parts(ctx1.written_key)[0] if ctx1.written_key and sph._token_parts(ctx1.written_key) else key.tonic
        note = _written_note(key, written_tonic, key.tonality, notation, offset)
        p2 = _adapted_parent(parent, ctx1, note, _retitle(parent.provenance.get("title_base") or parent.provenance.get("title"), parent.bars, notation,
                                                           written_tonic, bool(note)))
        ex2, reason = esp.regenerate(p2, recipe)
        if ex2 is not None:
            same_shape = (_rhythm_sig(ex2) == _rhythm_sig(parent) and len(ex2.notes) == len(parent.notes) and ex2.chords == parent.chords
                          and ex2.bars == parent.bars)
            if same_shape:
                ex, how = ex2, "revoiced"
                _carry_expression_exact(parent, ex)
            else:
                why_fail = "the rebuilt line did not keep your rhythm and note count"
        else:
            why_fail = reason or why_fail
        if ex is None:
            lo, hi = int(min(parent.midi)), int(max(parent.midi))
            fits = (f"its line spans {hi - lo} semitones, which doesn't fit the instrument's range at any octave, and rebuilding it there would not keep "
                    f"your rhythm and notes ({why_fail or 'no verified fit'})") if shift is None else (why_fail or "no verified fit")
            return _refusal(f"I couldn't safely adapt this exercise for **{spec.label}**: {fits}. Your exercise is unchanged.", parent, question, kind="instrument")
    fu = FollowUp(kind="instrument", raw=question)
    inherited = ["song", "section", "key", "tempo", "rhythm", "chords" if esp.kind_of(parent) == esp.KIND_CHORDS else "scale", "interval pattern",
                 "articulation and accents", "Practice Key"]
    changed = ["instrument", "written key and note names"] + (["octave"] if how == "octave" else []) + (["notes (re-voiced)"] if how == "revoiced" else [])
    if how == "revoiced":
        inherited = [i for i in inherited if i != "interval pattern"] + ["interval pattern (same recipe)"]
    ex = _stamp(ex, parent, fu, inherited=inherited, changed=changed, context_mode="stored_context",
                extra={"instrument_from": old_name, "instrument_to": spec.label, "octave_shift": 0 if how != "octave" else shift, "adaptation": how,
                       "written_minus_sounding": offset})
    ex.provenance["adaptation"] = {"kind": "instrument", "from": old_name, "to": spec.label, "how": how, "octave_shift": shift if how == "octave" else 0}
    lines = [f"**Now for {spec.label}** — your same exercise, adapted from {old_name}.",
             f"Kept: {', '.join(inherited)} · Changed: {', '.join(changed)}"]
    if offset:
        lines.append(f"Written in **{ex.written.get('key') or ctx1.written_key}** for {spec.label}: every note is written {_interval_name(offset)} "
                     f"the pitch that sounds (octave included), so the concert key stays **{ex.context.concert_key}**.")
    else:
        lines.append(f"{spec.label} is a concert-pitch instrument here, so the written notes are the sounding notes (concert key **{ex.context.concert_key}**).")
    if how == "kept":
        lines.append("Every note keeps its sounding pitch; the line already sits inside the instrument's range.")
    elif how == "octave":
        lines.append(f"**Octave adjustment:** the whole line was moved {_fmt_octaves(shift)} in sounding pitch to fit {spec.label}'s range. "
                     "Every interval, rhythm and chord is unchanged.")
    else:
        lines.append(f"**Re-voiced:** the sounding line doesn't fit {spec.label}'s range at any octave, so the same pattern (interval shape, approaches, "
                     "rhythm, harmony) was rebuilt in its register. The rhythm, chords and number of notes are the same; the exact pitches are not.")
    header = "\n\n".join(lines)
    payload = esp._payload(ex, parent, header, {"musical_idea_content": True, "exercise_revision_kind": "instrument", "utterance": question,
                                                "parent_exercise_id": parent.id, "scale_pattern_exercise": True, "instrument_from": old_name,
                                                "instrument_to": spec.label, "adaptation": how},
                           display_instrument=spec.label, bpm=bpm, session_ref=session_ref)
    payload["ok"] = True
    return payload


# ---------------------------------------------------------------- section retargeting


def _chart_for(session_ref: Any, ami_ctx: dict[str, Any] | None) -> dict[str, Any]:
    from music_coach_ami.chart_context_reader import resolve_coach_chart_snapshot
    from music_coach_ami.session_access import as_session_mapping

    return resolve_coach_chart_snapshot(as_session_mapping(session_ref), ami_ctx=dict(ami_ctx or {}))


def retarget_section(parent: GeneratedExercise, section_text: str, *, question: str, bpm: int, session_ref: Any, ami_ctx: dict[str, Any] | None) -> dict[str, Any]:
    from chord_subdivisions import chord_stream
    from music_coach_ami import exercise_scale_pattern as esp
    from music_coach_ami.exercise_followup import FollowUp, _stamp
    from music_coach_ami.musical_idea_knowledge import extract_requested_section, format_section_display_label, resolve_chart_section

    if esp.kind_of(parent) != esp.KIND_CHORDS:
        return _refusal("This is a key-based pattern: it uses one scale for the whole pattern and isn't tied to any chord, so moving it to another "
                        "section would only change its label. Ask for it “over the chord changes” (for example, “Give me an advanced scale pattern "
                        "over the chord changes of …”) and then I can apply it to a different section. Your exercise is unchanged.", parent, question,
                        kind="section")
    chart = _chart_for(session_ref, ami_ctx)
    sections = chart.get("chart_sections") or {}
    if not sections or not chart.get("chart_verified", True):
        return _refusal("I can't read the chart for the active song, so I haven't changed your exercise.", parent, question, kind="section")
    made_for = _clean(parent.context.concert_key)
    now_key = _clean(chart.get("practice_key"))
    if made_for and now_key and made_for != now_key:
        return _refusal(f"This exercise was built in {made_for}, but the Practice Key is now {now_key}, so I haven't moved it. Ask for a new exercise "
                        f"in {now_key}, or switch the Practice Key back to {made_for}.", parent, question, kind="section")
    if not chart.get("sections_in_practice_key"):
        return _refusal("I can't confirm the chart's chords are in the Practice Key, so I haven't changed your exercise.", parent, question, kind="section")
    requested = extract_requested_section("over the " + section_text)
    res = resolve_chart_section(requested, chart_sections=sections, fallback_section="")
    if res.get("ambiguous"):
        out = _refusal(_clean(res.get("message")) + " Your exercise is unchanged.", parent, question, kind="section")
        out["ask"] = {"kind": KIND_SECTION, "options": list(res.get("candidates") or [])}
        return out
    if not res.get("ok"):
        return _refusal(_clean(res.get("message")) + " Your exercise is unchanged.", parent, question, kind="section")
    name = _clean(res["section"])
    label = format_section_display_label(name) or name
    old_name = _clean(parent.context.section)
    stream = [str(c) for c in (res.get("chords") or [])]
    raw_slots = list((chart.get("chart_sections_raw") or {}).get(name) or [])
    slots = raw_slots if (raw_slots and chord_stream(raw_slots) == stream) else stream
    if not slots:
        return _refusal(f"**{label}** has no chords on the chart, so I haven't changed your exercise.", parent, question, kind="section")
    if name.lower() == old_name.lower():
        return _refusal(f"This exercise is already built on **{label}**, so I haven't changed anything.", parent, question, kind="section")
    if [str(s) for s in slots] == [str(s) for s in parent.provenance.get("section_slots") or []]:
        return _refusal(f"**{label}** has exactly the same chords as {format_section_display_label(old_name) or old_name}, so the exercise already fits it "
                        "and nothing needed to change.", parent, question, kind="section")
    bars = min(16, len(slots))
    recipe = esp.recipe_of(parent)
    p2 = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
    p2.bars = bars
    p2.provenance["section_slots"] = list(slots)
    p2.provenance["idea"] = {**dict(p2.provenance["idea"]), "section": name, "song_relative": True, "bars": bars}
    p2.provenance["title_base"] = re.sub(r"^\d+-Bar", f"{bars}-Bar", _clean(parent.provenance.get("title_base") or parent.provenance.get("title")))
    p2.context = replace(parent.context, section=name)
    ex, reason = esp.regenerate(p2, recipe)
    if ex is None:
        return _refusal(f"I couldn't build this pattern over **{label}** safely ({reason.rstrip('.')}). Your exercise is unchanged.", parent, question, kind="section")
    _carry_expression_exact_or_reapply(parent, ex)
    fu = FollowUp(kind="section", raw=question)
    inherited = ["song", "instrument", "key", "tempo", "Practice Key", "interval pattern", "approaches", "rhythm style", "articulation rules"]
    changed = ["section", "chords", "notes"] + (["length"] if bars != parent.bars else [])
    ex = _stamp(ex, parent, fu, inherited=inherited, changed=changed, extra={"section_from": old_name, "section_to": name})
    ex.provenance["adaptation"] = {"kind": "section", "from": old_name, "to": name, "chords": [str(s) for s in slots], "bars": bars}
    prog = " | ".join(str(s).replace(":", " ") for s in slots[:16])
    lines = [f"**Now over {label}** — your same exercise, rebuilt on this section's chords.",
             f"Kept: {', '.join(inherited)} · Changed: {', '.join(changed)}",
             f"{label} ({bars} bar{'s' if bars != 1 else ''}): {prog}",
             "Every note is chosen from the scale of the chord it sits on, so no note was carried over from the previous section."]
    note = _clean(res.get("resolution_note"))
    if note:
        lines.append(note)
    payload = esp._payload(ex, parent, "\n\n".join(lines), {"musical_idea_content": True, "exercise_revision_kind": "section", "utterance": question,
                                                           "parent_exercise_id": parent.id, "scale_pattern_exercise": True, "section_from": old_name,
                                                           "section_to": name}, display_instrument=ex.context.instrument or "your instrument",
                           bpm=bpm, session_ref=session_ref)
    payload["ok"] = True
    return payload


def _carry_expression_exact_or_reapply(parent: GeneratedExercise, ex: GeneratedExercise) -> None:
    """Articulation / accent rules follow the new notes (the note count differs between sections); an exercise with no markings stays unmarked."""
    from music_coach_ami.exercise_expression import apply_expression, has_rules
    from music_coach_ami.exercise_followup import _request_of

    req = _request_of(parent)
    if req and has_rules(req):
        apply_expression(ex, req, source={"articulation": "inherited", "dynamics": "inherited"})
        ex.intent = replace(ex.intent, expression=req)
