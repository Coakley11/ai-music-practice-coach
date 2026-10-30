"""AMI Slice 2: conversational follow-ups that transform the last canonical ``GeneratedExercise``.

natural-language follow-up → ``FollowUp`` (this module) → transformation of the stored exercise →
a NEW ``GeneratedExercise`` whose ``parent_id`` / ``transform`` point back at the one it came from.

Rules:

* The AMI-owned last-exercise store (Slice 1) is the only input. Nothing is reverse-engineered from
  rendered text and no Mission / chart / song state is read or written.
* The stored exercise's own context stays authoritative (key, chord, level, collection). Live state is
  used only for the player's current instrument (Written Key) — and when the user explicitly asks for the
  current context ("another one for the current chord") or names a new key / chord / level.
* A follow-up is recognised only when the whole utterance functions as one ("another one", "make it
  easier", "move it up", "keep the rhythm but change the notes" ...). Anything else is left alone.
* A transform that cannot be applied returns a reason; the previous exercise stays as it was.
* Movement reuses ``mission_degree_shift`` and its range policy; rhythm reuses ``cycle_motif_rhythm`` (the
  melodic rhythm engine); new notes come from the same Mission engines through ``generate_exercise``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

from music_coach_ami.exercise_bridge import (
    AMI_LAST_EXERCISE_KEY,
    _MISSION_FOR_VOCAB,
    _bars_of,
    _build_exercise,
    exercise_prose,
    generate_exercise,
    plan_inputs,
    render_abc,
    store_last_exercise,
)
from music_coach_ami.exercise_context import key_mode, normalize_key_token
from music_coach_ami.exercise_expression import (
    ABC_CAPABILITY,
    apply_expression,
    has_rules,
    merge_requests,
    parse_expression,
    vary_request,
)
from music_coach_ami.exercise_intent import (
    _ARTICULATION_RE,
    _DYNAMICS_RE,
    _OVER_CHORD_RE,
    _key_from_text,
)
from music_coach_ami.exercise_model import (
    VOCAB_BLUES,
    VOCAB_CHORD_TONES,
    VOCAB_GUIDE_TONES,
    VOCAB_PENTATONIC,
    ActiveContext,
    ExerciseIntent,
    GeneratedExercise,
)

LEVELS = ("Beginner", "Intermediate", "Advanced")

KIND_VARIATION = "variation"
KIND_EASIER = "easier"
KIND_HARDER = "harder"
KIND_SAME_RHYTHM = "same_rhythm_new_notes"
KIND_SAME_NOTES = "same_notes_new_rhythm"
KIND_MOVE = "move"
KIND_SEQUENCE = "sequence"
KIND_REGENERATE = "regenerate_in_current_context"
KIND_EXPRESSION = "expression"
KIND_DEVELOP = "develop"   # Stage 4a: chromatic / rhythm / motif / difficulty / register development of a multi-chord exercise


def _clean(value: object) -> str:
    return str(value or "").strip()


# ---------------------------------------------------------------- parsing


@dataclass(frozen=True)
class FollowUp:
    kind: str
    direction: int = 0            # move / sequence: +1 up, -1 down
    degrees: int = 1
    collection_word: str = ""     # pentatonic | blues | chord_tone | guide_tone | scale ("" = the exercise's own)
    explicit_key: str = ""
    explicit_chord: str = ""
    level: str = ""
    current_context: bool = False
    articulation_request: str = ""   # the words used (provenance); the structured request is ``expression``
    dynamics_request: str = ""
    develop: dict = field(default_factory=dict)      # Stage 4a: a multi-chord development request (exercise_develop.parse_development)
    expression: dict = field(default_factory=dict)   # exercise_expression.parse_expression result (rules only)
    vary: str = ""                   # "articulation" | "dynamics": "give me a different ..."
    raw: str = ""

    def overrides(self) -> list[str]:
        out = []
        if self.explicit_key:
            out.append("key")
        if self.explicit_chord:
            out.append("chord")
        if self.level:
            out.append("level")
        if self.current_context:
            out.append("current_context")
        return out


_ANOTHER_RE = re.compile(
    r"^(?:(?:please|can you|could you)\s+)?(?:(?:give me|show me|let me (?:have|see)|can i (?:have|get)|i(?:'d| would) like)\s+)?"
    r"(?:another|one more|a different|a new|a fresh)\b"
)
_EASIER_RE = re.compile(r"\b(?:easier|simpler|less (?:difficult|complex|busy)|more basic)\b")
_HARDER_RE = re.compile(r"\b(?:harder|tougher|more (?:advanced|difficult|challenging|complex))\b")
_MOVE_RE = re.compile(
    r"\b(?:move|shift|take|bring|transpose|raise|lower)\s+(?:it|that|this|the\s+(?:line|idea|lick|phrase|motif|exercise|pattern))"
    r"(?:\s+(up|down|higher|lower|upward|upwards|downward|downwards))?\b"
)
_SEQUENCE_RE = re.compile(r"\bsequence\s+(?:it|that|this)(?:\s+(up|upward|upwards|down|downward|downwards))?\b")
_RESTATE_RE = re.compile(
    r"\b(?:repeat|restate|play)\s+the\s+(?:motif|idea|line|phrase|lick)\b.{0,12}\bstart(?:ing)?\s+(?:one|a)\s+(?:\w+\s+)?degree\s+(higher|lower|up|down)\b"
)
_DEGREES_RE = re.compile(
    r"\b(?:by\s+)?(one|two|three|four|a|1|2|3|4)?\s*(scale|pentatonic|blues|diatonic|chord[- ]?tone|guide[- ]?tone)?[- ]?(?:degree|step)s?\b"
)
_KEEP_RHYTHM_RE = re.compile(r"\b(?:keep|same|retain|preserve)\s+(?:the\s+)?rhythm\b|\bsame\s+rhythm\b")
_KEEP_NOTES_RE = re.compile(r"\b(?:keep|same|retain|preserve)\s+(?:the\s+)?notes?\b|\bsame\s+notes?\b|\bsame\s+idea\b")
_CHANGE_RHYTHM_RE = re.compile(r"\b(?:change|vary|alter|new|different|another)\s+(?:the\s+)?rhythm\b|\bin a different rhythm\b|\bdifferent rhythm\b")
_CHANGE_NOTES_RE = re.compile(r"\b(?:change|vary|alter|swap|new|different|another)\s+(?:the\s+)?notes?\b|\bdifferent notes?\b")
_CURRENT_RE = re.compile(
    r"\b(?:for|over|on|using|with|in)\s+(?:the\s+|my\s+)?(?:current|this|live)\s+(?:chord|key|section|progression|harmony|context)\b"
)
_KEY_PHRASE_RE = re.compile(r"\bin\s+(?:the\s+key\s+of\s+)?[a-g][#b]?\s*(?:major|minor|maj|min)?\b")
_CHORD_PHRASE_RE = re.compile(r"\bover\s+[a-g][#b]?[a-z0-9#/]*\b")
_LEVEL_PHRASE_RE = re.compile(r"\b(?:at|for|in)\s+(?:a\s+)?(?:beginner|intermediate|advanced)(?:\s+level)?\b")
_PRESERVE_ALL_RE = re.compile(
    r"\b(?:keep|same|retain|preserve)\s+(?:the\s+)?(?:notes?\s+and\s+(?:the\s+)?rhythm|rhythm\s+and\s+(?:the\s+)?notes?)\b"
    r"|\b(?:keep|retain)\s+everything(?:\s+(?:else|the\s+same))?\b|\bsame\s+(?:pattern|exercise|idea|line)\b"
)

_FILLERS = frozenset(
    "please it that this the a an but and with then now just can you could give me show make to one i would like want "
    "keep same use using let's lets try do for in of by more some another again also too version variation take idea "
    "line lick phrase motif exercise pattern up down higher lower upward upwards downward downwards degree degrees "
    "step steps move shift thanks thank add everything else shape shapes dynamics dynamic articulation articulations instead through throughout phrase into turn apply put play different again".split()
)

_NUMBER_WORDS = {"a": 1, "one": 1, "1": 1, "two": 2, "2": 2, "three": 3, "3": 3, "four": 4, "4": 4}


def _norm(question: str) -> str:
    low = re.sub(r"\s+", " ", _clean(question).lower())
    return low.strip(" .!?,;:")


def _direction(word: str) -> int:
    word = _clean(word)
    if word in ("up", "higher", "upward", "upwards"):
        return 1
    if word in ("down", "lower", "downward", "downwards"):
        return -1
    return 0


def parse_followup(question: str) -> FollowUp | None:
    """Recognise an exercise follow-up. Returns None for anything that is not clearly one."""
    raw = _clean(question)
    low = _norm(raw)
    if not low or len(low.split()) > 24:
        return None
    from music_coach_ami.exercise_develop import parse_development

    dev = parse_development(low)
    if dev is not None:
        return FollowUp(kind=KIND_DEVELOP, develop=dev, raw=raw)
    kind = ""
    direction = 0
    consumed: list[re.Pattern[str]] = []
    expr = parse_expression(low)
    expr_spans = list(expr.pop("spans", []))
    expr_rules = has_rules(expr)

    m_seq = _SEQUENCE_RE.search(low)
    m_rest = _RESTATE_RE.search(low)
    m_move = _MOVE_RE.search(low)
    keep_r, keep_n = _KEEP_RHYTHM_RE.search(low), _KEEP_NOTES_RE.search(low)
    chg_r, chg_n = _CHANGE_RHYTHM_RE.search(low), _CHANGE_NOTES_RE.search(low)
    if m_seq or m_rest:
        kind = KIND_SEQUENCE
        direction = _direction((m_seq or m_rest).group(1)) or 1
        consumed += [_SEQUENCE_RE, _RESTATE_RE]
    elif m_move and (_direction(m_move.group(1)) or re.search(r"\b(?:degree|step)s?\b", low)):
        kind = KIND_MOVE
        direction = _direction(m_move.group(1))
        if not direction:
            word = re.search(r"\b(higher|lower|up|down)\b", low)
            direction = _direction(word.group(1)) if word else 0
        if not direction:
            return None
        consumed.append(_MOVE_RE)
    elif expr_rules and (expr["vary"] or _PRESERVE_ALL_RE.search(low)):
        kind = KIND_EXPRESSION  # "different articulation", "keep everything the same and add a crescendo"
        consumed.append(_PRESERVE_ALL_RE)
    elif (keep_r and (chg_n or "notes" in low)) or (chg_n and not keep_n and not chg_r):
        kind = KIND_SAME_RHYTHM
        consumed += [_KEEP_RHYTHM_RE, _CHANGE_NOTES_RE]
    elif (keep_n and (chg_r or "rhythm" in low)) or (chg_r and not keep_r):
        kind = KIND_SAME_NOTES
        consumed += [_KEEP_NOTES_RE, _CHANGE_RHYTHM_RE]
    elif _HARDER_RE.search(low) and not _EASIER_RE.search(low):
        kind = KIND_HARDER
        consumed.append(_HARDER_RE)
    elif _EASIER_RE.search(low) and not _HARDER_RE.search(low):
        kind = KIND_EASIER
        consumed.append(_EASIER_RE)
    elif _ANOTHER_RE.search(low):
        kind = KIND_VARIATION
        consumed.append(_ANOTHER_RE)
        if keep_r:
            kind = KIND_SAME_RHYTHM
        elif keep_n:
            kind = KIND_SAME_NOTES
        consumed += [_KEEP_RHYTHM_RE, _KEEP_NOTES_RE]
    elif expr_rules:
        kind = KIND_EXPRESSION  # "make it staccato", "add accents to the guide tones", "give it a crescendo"
    if not kind:
        return None

    degrees, word = 1, ""
    if kind in (KIND_MOVE, KIND_SEQUENCE):
        dm = _DEGREES_RE.search(low)
        if dm:
            degrees = _NUMBER_WORDS.get(_clean(dm.group(1)), 1)
            word = _clean(dm.group(2)).replace("-", "_").replace(" ", "_")
            word = {"chordtone": "chord_tone", "guidetone": "guide_tone", "diatonic": "scale"}.get(word, word)
        consumed.append(_DEGREES_RE)
    explicit_key = _key_from_text(raw, "", "")
    chord_m = _OVER_CHORD_RE.search(raw)
    art, dyn = _ARTICULATION_RE.search(raw), _DYNAMICS_RE.search(raw)
    current = bool(_CURRENT_RE.search(low))
    level = ""
    if kind not in (KIND_EASIER, KIND_HARDER):
        for rx_word, label in (("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")):
            if re.search(rf"\b(?:at|for|in)\s+(?:a\s+)?{rx_word}\b", low):
                level = label

    # Everything that is left must be filler: an unrecognised remainder means this is not a follow-up.
    blank = list(low)
    for a, b in expr_spans:
        for i in range(a, min(b, len(blank))):
            blank[i] = " "
    rest = "".join(blank)
    for rx in (*consumed, _CURRENT_RE, _KEY_PHRASE_RE, _CHORD_PHRASE_RE, _LEVEL_PHRASE_RE, _ARTICULATION_RE, _DYNAMICS_RE,
               _KEEP_RHYTHM_RE, _KEEP_NOTES_RE, _CHANGE_RHYTHM_RE, _CHANGE_NOTES_RE):
        rest = rx.sub(" ", rest)
    if [t for t in re.findall(r"[a-z']+", rest) if t not in _FILLERS]:
        return None
    return FollowUp(
        kind=kind, direction=direction, degrees=degrees, collection_word=word,
        explicit_key=normalize_key_token(explicit_key) if explicit_key else "",
        explicit_chord=chord_m.group(1) if chord_m else "", level=level, current_context=current,
        articulation_request=art.group(1).lower() if art else "", dynamics_request=dyn.group(0).lower() if dyn else "",
        expression=expr if expr_rules else {}, vary=expr.get("vary", ""), raw=raw,
    )


def is_exercise_followup(question: str) -> bool:
    return parse_followup(question) is not None


# ---------------------------------------------------------------- helpers


def last_exercise(session_ref: Any) -> GeneratedExercise | None:
    """The AMI-owned last exercise, rebuilt from its stored dict (never from rendered text)."""
    try:
        from music_coach_ami.session_access import as_mutable_session
        from music_coach_ami.session_scope import is_owned, unstamped

        session = as_mutable_session(session_ref)
        raw = session.get(AMI_LAST_EXERCISE_KEY) if session is not None else None
        if raw is not None and not is_owned(raw, session):   # another account's / workspace's exercise: never readable
            return None
        raw = unstamped(raw) if isinstance(raw, dict) else raw
    except Exception:
        raw = None
    if not isinstance(raw, dict) or not raw.get("notes"):
        return None
    try:
        return GeneratedExercise.from_dict(raw)
    except Exception:
        return None


def sha(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def rhythm_signature(ex: GeneratedExercise) -> dict[str, Any]:
    return {"events": [{k: e.get(k) for k in ("on", "dur", "rest", "tup")} for e in ex.rhythm_events],
            "symbols": list(ex.rhythm_symbols), "meter": ex.meter}


def complexity(midi: list[int], events: list[dict[str, Any]], n_notes: int) -> float:
    """A small, explainable difficulty score: note count, off-beat onsets, wide leaps."""
    off = 0
    for e in events:
        if e.get("rest"):
            continue
        try:
            if Fraction(str(e.get("on"))) % 1 != 0:
                off += 1
        except Exception:
            pass
    leaps = sum(max(0, abs(b - a) - 4) for a, b in zip(midi, midi[1:]))
    return round(n_notes + 2.0 * off + 0.5 * leaps, 2)


def _score(ex: GeneratedExercise) -> float:
    return complexity(ex.midi, ex.rhythm_events, len(ex.notes))


def _rebound_context(parent_ctx: ActiveContext, live: dict[str, Any], *, concert_key: str = "", chord: str = "") -> ActiveContext:
    """The stored context, with only the player's current instrument (Written Key) taken from live state."""
    from music_coach_ami.exercise_context import _session_copy
    from music_coach_ami.written_music_context import build_written_music_context

    key = concert_key or parent_ctx.concert_key
    original = _clean(parent_ctx.key_candidates.get("catalog_original_key")) or key
    written = build_written_music_context(
        instrument=live["instrument"], practice_concert_key=key, original_song_key=original,
        concert_chords=[chord] if chord else [], session_state=_session_copy(live["session_ref"]),
        chart_already_in_practice_key=True,
    )
    return replace(
        parent_ctx, instrument=live["instrument"], notation_instrument=live["notation_inst"],
        written_key=_clean(written.written_key), written_transposition_applied=bool(written.written_transposition_applied),
        transposition_semitones=int(written.transposition_semitones or 0),
    )


def _stamp(ex: GeneratedExercise, parent: GeneratedExercise, fu: FollowUp, *, inherited: list[str], changed: list[str],
           extra: dict[str, Any] | None = None, context_mode: str = "stored_context", live: dict[str, Any] | None = None) -> GeneratedExercise:
    live = live or {}
    overridden = fu.overrides()
    meta = {
        "kind": fu.kind, "utterance": fu.raw, "parent": parent.id, "direction": fu.direction, "degrees": fu.degrees,
        "inherited": inherited, "changed": changed, "overridden": overridden, "context_mode": context_mode,
        "nonce": int(ex.intent.variation_index), "seed": int(ex.seed),
        "instrument_rebound": bool(parent.context.instrument and live.get("instrument") and parent.context.instrument != live["instrument"]),
        "preserved": {"rhythm_sha1": sha(rhythm_signature(ex)), "notes_sha1": sha({"notes": ex.notes, "midi": ex.midi})},
        "parent_fingerprints": {"rhythm_sha1": sha(rhythm_signature(parent)), "notes_sha1": sha({"notes": parent.notes, "midi": parent.midi})},
        "articulation_request": fu.articulation_request, "dynamics_request": fu.dynamics_request,
        **(extra or {}),
    }
    ex.parent_id = parent.id
    ex.transform = meta
    # A transformed exercise is a new object even when its notes equal an ancestor's (Up then Down): its id
    # covers the parent link, the transformation, the nonce and the rhythm, not just the notes.
    ex.id = "ex-" + sha({"notes": ex.notes, "midi": ex.midi, "chord": ex.chord, "rhythm": rhythm_signature(ex),
                         "parent": parent.id, "kind": fu.kind, "nonce": meta["nonce"], "seed": ex.seed})
    ex.provenance.update({
        "parent": parent.id, "transform": fu.kind, "inherited": inherited, "changed": changed, "overridden": overridden,
        "context_mode": context_mode, "nonce": meta["nonce"],
    })
    return ex


def _pinned_plan(intent: ExerciseIntent, ctx: ActiveContext, parent: GeneratedExercise) -> dict[str, Any]:
    """The plan that regenerates the parent's own chord and collection."""
    plan = plan_inputs(intent, ctx)
    plan["relationship"] = _clean(parent.provenance.get("relationship"))
    plan["chords"] = [parent.chord]
    plan["chord_source"] = "inherited_from_parent"
    plan["mode"] = parent.mode or plan.get("mode", "")
    return plan


def _intent_for(parent: GeneratedExercise, fu: FollowUp, nonce: int, *, keep_vocab_only: bool = False) -> ExerciseIntent:
    """The parent's intent, with only what this follow-up explicitly changes. The seed stays tied to the
    original request text, so (request, nonce) fully determines the result."""
    base = parent.intent
    kwargs: dict[str, Any] = {
        "variation_index": nonce,
        "articulation_request": fu.articulation_request or base.articulation_request,
        "dynamics_request": fu.dynamics_request or base.dynamics_request,
        "transform": fu.kind,
        "explicit_chord": parent.chord,
    }
    if fu.explicit_key:
        kwargs.update(explicit_key=fu.explicit_key, explicit_chord="")
    if fu.explicit_chord:
        kwargs.update(explicit_chord=fu.explicit_chord, explicit_key="", collection="")
    if keep_vocab_only:
        kwargs.update(explicit_key="", explicit_chord="", collection="")
    return replace(base, **kwargs)


def _next_nonce(parent: GeneratedExercise) -> int:
    return max(int(parent.intent.variation_index), int(parent.transform.get("nonce", 0) or 0)) + 1


# ---------------------------------------------------------------- transformations


def _result(ex: GeneratedExercise | None, reason: str = "") -> tuple[GeneratedExercise | None, str]:
    return ex, reason


def _generate(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any], *, accept: Any,
              accept_reason: str, inherited: list[str], changed: list[str], extra: dict[str, Any] | None = None,
              graft_rhythm: bool = False) -> tuple[GeneratedExercise | None, str]:
    nonce = _next_nonce(parent)
    intent = _intent_for(parent, fu, nonce)
    if fu.explicit_key or fu.explicit_chord:
        plan = plan_inputs(intent, ctx)
    else:
        plan = _pinned_plan(intent, ctx, parent)
    ex, reason = generate_exercise(intent, ctx, plan, accept=accept, accept_reason=accept_reason)
    if ex is None:
        return None, reason
    if graft_rhythm:
        ex.rhythm_events = [dict(e) for e in parent.rhythm_events]
        ex.rhythm_symbols = list(parent.rhythm_symbols)
        ex.meter = parent.meter
        ex.bars = parent.bars
    return _stamp(ex, parent, fu, inherited=inherited, changed=changed, extra=extra, live=live), ""


def do_variation(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    before = list(parent.midi)
    inherited = ["vocabulary", "collection", "chord", "key", "level"]
    if fu.explicit_key or fu.explicit_chord:
        inherited = [x for x in inherited if not ((fu.explicit_key and x in ("key", "chord", "collection")) or (fu.explicit_chord and x in ("key", "chord", "collection")))]
    return _generate(parent, fu, ctx, live, accept=lambda m: [int(x) for x in m.get("midi") or []] != before,
                     accept_reason="I couldn't find a different line with the same ingredients",
                     inherited=inherited, changed=["notes", "rhythm"])


def do_same_rhythm_new_notes(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    n, before = len(parent.notes), list(parent.midi)

    def accept(m: dict[str, Any]) -> bool:
        midi = [int(x) for x in m.get("midi") or []]
        return len(midi) == n and midi != before

    return _generate(
        parent, fu, ctx, live, accept=accept,
        accept_reason=f"I couldn't find different notes that fit that {n}-note rhythm",
        inherited=["vocabulary", "collection", "chord", "key", "level", "rhythm"], changed=["notes"], graft_rhythm=True,
    )


def do_level(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    step = 1 if fu.kind == KIND_HARDER else -1
    cur = parent.context.level if parent.context.level in LEVELS else "Intermediate"
    new_i = LEVELS.index(cur) + step
    if new_i < 0:
        return None, "This is already at the easiest level (Beginner), so I haven't changed it."
    if new_i >= len(LEVELS):
        return None, "This is already at the hardest level (Advanced), so I haven't changed it."
    new_level = LEVELS[new_i]
    ctx2 = replace(ctx, level=new_level, level_source=f"followup_{fu.kind}")
    base = _score(parent)

    def accept(m: dict[str, Any]) -> bool:
        midi = [int(x) for x in m.get("midi") or []]
        score = complexity(midi, list(m.get("rhythm_events") or []), len(midi))
        # a meaningful change, not a one-note nudge: at least a full point of difficulty either way
        return score >= base + 1.0 if step > 0 else score <= base - 1.0

    word = "more demanding" if step > 0 else "simpler"
    ex, reason = _generate(
        parent, fu, ctx2, live, accept=accept, accept_reason=f"I couldn't find a {word} version that keeps the same vocabulary",
        inherited=["vocabulary", "collection", "chord", "key"], changed=["level", "notes", "rhythm"],
        extra={"level_from": cur, "level_to": new_level, "complexity_before": base},
    )
    if ex is not None:
        ex.transform["complexity_after"] = _score(ex)
    return ex, reason


def do_same_notes_new_rhythm(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    from improvisation_motif import cycle_motif_rhythm
    from music_coach_ami.exercise_bridge import motif_view

    before = rhythm_signature(parent)
    motif = motif_view(parent, "concert")
    new_motif: dict[str, Any] | None = None
    for _ in range(14):
        try:
            motif = cycle_motif_rhythm(dict(motif), meter=parent.meter, level=parent.context.level)
        except Exception as exc:
            return None, f"The rhythm engine couldn't build another rhythm for these notes ({exc})."
        cand = {"events": [{k: e.get(k) for k in ("on", "dur", "rest", "tup")} for e in (motif.get("rhythm_events") or [])],
                "symbols": list(motif.get("rhythm_symbols") or []), "meter": _clean(motif.get("meter")) or parent.meter}
        if cand != before and (cand["events"] or cand["symbols"]):
            new_motif = motif
            break
    if new_motif is None:
        return None, "I couldn't find a different valid rhythm for these notes in this meter."
    meter = _clean(new_motif.get("meter")) or parent.meter
    motif_dict = {
        "notes": list(parent.notes), "midi": list(parent.midi), "rhythm_events": [dict(e) for e in new_motif.get("rhythm_events") or []],
        "rhythm_symbols": [str(s) for s in new_motif.get("rhythm_symbols") or []], "meter": meter,
        "pentatonic_relationship": _clean(parent.provenance.get("relationship")),
    }
    ex = _build_exercise(parent.intent, ctx, {"mode": parent.mode, "mode_source": "inherited_from_parent", "chord_source": "inherited_from_parent"},
                         motif_dict, parent.chord, _clean(parent.provenance.get("spelling_reference")) or ctx.concert_key,
                         0, parent.seed, _MISSION_FOR_VOCAB[parent.vocabulary])
    if ex.notes != parent.notes or ex.midi != parent.midi:
        return None, "That rhythm would have changed the notes, so I haven't applied it."
    ex.intent = replace(ex.intent, variation_index=_next_nonce(parent), transform=fu.kind)
    return _stamp(ex, parent, fu, inherited=["vocabulary", "collection", "chord", "key", "level", "notes"], changed=["rhythm"], live=live), ""


def _allowed_words(vocab: str) -> set[str]:
    return {VOCAB_PENTATONIC: {"pentatonic", "scale"}, VOCAB_BLUES: {"blues", "scale"},
            VOCAB_CHORD_TONES: {"chord_tone", "scale"}, VOCAB_GUIDE_TONES: {"guide_tone", "scale"}}.get(vocab, {"scale"})


def _moved_pitches(parent: GeneratedExercise, direction: int, degrees: int) -> tuple[list[str], list[int], str] | tuple[None, str, str]:
    from mission_degree_shift import MoveRefused, move_concert_motif
    from improvisation_motif import _shift_phrase_into_bounds

    ref = _clean(parent.provenance.get("spelling_reference")) or parent.context.concert_key
    like = {"pentatonic_relationship": _clean(parent.provenance.get("relationship")), "spelling_reference": ref}
    mission = _MISSION_FOR_VOCAB[parent.vocabulary]
    cur, notes, label = list(parent.midi), list(parent.notes), ""
    try:
        for _ in range(max(1, degrees)):
            notes, cur, label = move_concert_motif(like, cur, mission=mission, chord=parent.chord, key_center=ref, direction=direction)
    except MoveRefused as exc:
        return None, f"Couldn't move this {'up' if direction > 0 else 'down'} a scale degree: {exc}.", ""
    if _shift_phrase_into_bounds(list(cur)) != cur:
        return None, f"Couldn't move this {'up' if direction > 0 else 'down'} a scale degree: that would take the phrase outside the staff range.", ""
    return notes, cur, label


def do_move(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    if fu.collection_word and fu.collection_word not in _allowed_words(parent.vocabulary):
        own = parent.collection_label
        return None, (f"This is a {own} exercise, so I can move it by {own} degrees. Ask me to move it up or down a degree "
                      "without naming a different scale.")
    notes, midi, label = _moved_pitches(parent, fu.direction, fu.degrees)
    if notes is None:
        return None, str(midi)
    motif_dict = {
        "notes": notes, "midi": midi, "rhythm_events": [dict(e) for e in parent.rhythm_events],
        "rhythm_symbols": list(parent.rhythm_symbols), "meter": parent.meter,
        "pentatonic_relationship": _clean(parent.provenance.get("relationship")),
    }
    ex = _build_exercise(parent.intent, ctx, {"mode": parent.mode, "mode_source": "inherited_from_parent", "chord_source": "inherited_from_parent"},
                         motif_dict, parent.chord, _clean(parent.provenance.get("spelling_reference")) or ctx.concert_key,
                         0, parent.seed, _MISSION_FOR_VOCAB[parent.vocabulary],
                         # "both thirds" is a property of the original request; a moved line keeps each degree's
                         # identity (E♭→E, E→G) but need not still contain both.
                         require_both_thirds=False)
    if not ex.validation.get("ok"):
        bad = "; ".join(c["detail"] for c in ex.validation.get("checks", []) if not c.get("ok"))
        return None, f"Moving it would break the exercise's own rule ({bad}), so I haven't changed it."
    ex.intent = replace(ex.intent, variation_index=_next_nonce(parent), transform=fu.kind)
    return _stamp(ex, parent, fu, inherited=["vocabulary", "collection", "chord", "key", "level", "rhythm"], changed=["notes"],
                  extra={"framework": label}, live=live), ""


def do_sequence(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    """State the idea, then restate it one degree higher / lower (same rhythm)."""
    if fu.collection_word and fu.collection_word not in _allowed_words(parent.vocabulary):
        return None, f"This is a {parent.collection_label} exercise; I can sequence it by its own degrees only."
    notes2, midi2, _label = _moved_pitches(parent, fu.direction, fu.degrees)
    if notes2 is None:
        return None, str(midi2)
    meter = parent.meter
    beats_bar = {"3/4": 3, "6/8": 3, "2/4": 2}.get(meter, 4)
    offset = Fraction(parent.bars * beats_bar)
    events2 = []
    for e in parent.rhythm_events:
        d = dict(e)
        d["on"] = str(Fraction(str(e.get("on"))) + offset)
        if d.get("n") is not None:
            d["n"] = int(e["n"]) + len(parent.notes)
        events2.append(d)
    motif_dict = {
        "notes": list(parent.notes) + notes2, "midi": list(parent.midi) + midi2,
        "rhythm_events": [dict(e) for e in parent.rhythm_events] + events2,
        "rhythm_symbols": list(parent.rhythm_symbols) + list(parent.rhythm_symbols), "meter": meter,
        "pentatonic_relationship": _clean(parent.provenance.get("relationship")),
    }
    ex = _build_exercise(parent.intent, ctx, {"mode": parent.mode, "mode_source": "inherited_from_parent", "chord_source": "inherited_from_parent"},
                         motif_dict, parent.chord, _clean(parent.provenance.get("spelling_reference")) or ctx.concert_key,
                         0, parent.seed, _MISSION_FOR_VOCAB[parent.vocabulary])
    if not ex.validation.get("ok"):
        return None, "The restated idea would break the exercise's own rule, so I haven't changed it."
    ex.bars = max(ex.bars, parent.bars * 2)
    ex.intent = replace(ex.intent, variation_index=_next_nonce(parent), transform=fu.kind)
    return _stamp(ex, parent, fu, inherited=["vocabulary", "collection", "chord", "key", "level", "rhythm"], changed=["notes", "length"],
                  extra={"statements": 2}, live=live), ""


# ---------------------------------------------------------------- expression (articulation / dynamics)


def _request_of(ex: GeneratedExercise) -> dict[str, Any]:
    return dict((ex.expression or {}).get("request") or {})


def _expr_meta(ex: GeneratedExercise, fu: FollowUp, source: dict[str, str], how: str) -> dict[str, Any]:
    e = ex.expression or {}
    return {
        "articulation_request": fu.articulation_request or "", "dynamics_request": fu.dynamics_request or "",
        "articulation_source": source.get("articulation", "inherited"), "dynamics_source": source.get("dynamics", "inherited"),
        "how": how, "rules_applied": e.get("rules_applied", []), "roles_used": e.get("roles_used", {}),
        "unmatched": e.get("unmatched", []), "dynamic_map": e.get("dynamic_map", {}), "summary": e.get("summary", {}),
        "capability": {"notation": "abcjs 6.4.4 renders these markings", "playback": ABC_CAPABILITY["playback"]["ami_card"]},
    }


def _carry_expression(parent: GeneratedExercise, ex: GeneratedExercise, fu: FollowUp) -> None:
    """Give a transformed exercise the parent's expression.

    * Move: pitches change but markings stay attached to the same note positions (copied, not recomputed), unless
      the follow-up itself asks for new ones.
    * Everything else that produces different notes or rhythm (another one, easier / harder, same rhythm / new notes,
      same notes / new rhythm, sequence, current context): the parent's *request* is re-applied to the new exercise,
      so note-attached rules (slur groups, ramps, roles) follow the notes and beat-position rules (accent beat 1)
      are re-evaluated against the new rhythm.
    """
    import copy

    parent_req, new_req = _request_of(parent), fu.expression or {}
    source = {"articulation": "explicit" if new_req.get("articulation") else "inherited",
              "dynamics": "explicit" if new_req.get("dynamics") else "inherited"}
    if fu.kind == KIND_MOVE and not has_rules(new_req):
        if parent.expression and len(ex.notes) == len(parent.notes):
            ex.articulation, ex.accents = list(parent.articulation), list(parent.accents)
            ex.slur_groups, ex.dynamics = list(parent.slur_groups), list(parent.dynamics)
            ex.dynamic_marks = copy.deepcopy(parent.dynamic_marks)
            ex.expression = {**copy.deepcopy(parent.expression), "carried_from": parent.id, "attached_by": "note_index",
                             "source": {"articulation": "inherited", "dynamics": "inherited"}}
            ex.transform["expression"] = _expr_meta(ex, fu, ex.expression["source"], "carried by note position")
        return
    merged = merge_requests(parent_req, new_req)
    if has_rules(merged):
        apply_expression(ex, merged, source=source)
        ex.intent = replace(ex.intent, expression=merged)
        ex.transform["expression"] = _expr_meta(ex, fu, source, "request re-applied to the new exercise")


def do_expression(parent: GeneratedExercise, fu: FollowUp, ctx: ActiveContext, live: dict[str, Any]) -> tuple[GeneratedExercise | None, str]:
    """Same notes, same rhythm, same everything — only the articulation and/or dynamics change."""
    import copy

    from music_coach_ami.exercise_bridge import project_written

    nonce = _next_nonce(parent)
    parent_req = _request_of(parent)
    new_req = vary_request(parent_req, fu.vary, nonce) if fu.vary else (fu.expression or {})
    if not has_rules(new_req):
        return None, "I couldn't tell what articulation or dynamics to apply."
    merged = merge_requests(parent_req, new_req)
    ex = GeneratedExercise.from_dict(copy.deepcopy(parent.to_dict()))
    ex.context = ctx
    ex.written = project_written(ex, ctx)
    dims = [d for d in ("articulation", "dynamics") if new_req.get(d)]
    source = {"articulation": "explicit" if "articulation" in dims else "inherited",
              "dynamics": "explicit" if "dynamics" in dims else "inherited"}
    apply_expression(ex, merged, source=source)
    ex.intent = replace(ex.intent, variation_index=nonce, transform=KIND_EXPRESSION, expression=merged)
    ex.explanation_facts = {**ex.explanation_facts, "articulation_dynamics_applied": True}
    inherited = ["vocabulary", "collection", "chord", "key", "level", "notes", "rhythm"] + [d for d in ("articulation", "dynamics") if d not in dims]
    stamped = _stamp(ex, parent, fu, inherited=inherited, changed=dims, live=live)
    stamped.transform["expression"] = _expr_meta(stamped, fu, source, "new expression on identical notes and rhythm")
    return stamped, ""


# ---------------------------------------------------------------- orchestration


def _no_exercise_payload() -> dict[str, Any]:
    return {
        "direct_answer": "There's no generated exercise to build on yet.",
        "practice_steps": ["Ask for one first — for example “Give me an A minor pentatonic line” — then I can make it "
                           "easier or harder, move it, change its rhythm or notes, or give you another."],
        "what_to_listen_for": [], "suggested_next_action": "Ask for an exercise to get started.",
        "notation_abc": "", "notation_abc_sections": [],
        "diagnostics": {"musical_idea_content": True, "exercise_followup": True, "exercise_followup_failed": True,
                        "exercise_followup_failure_reason": "no_prior_exercise"},
    }


_TRANSFORM_TEXT = {
    KIND_VARIATION: "another variation", KIND_EASIER: "an easier version", KIND_HARDER: "a harder version",
    KIND_SAME_RHYTHM: "same rhythm, new notes", KIND_SAME_NOTES: "same notes, new rhythm",
    KIND_MOVE: "moved", KIND_SEQUENCE: "sequenced", KIND_REGENERATE: "same idea in the current context",
    KIND_EXPRESSION: "same notes and rhythm, new expression",
}


def _followup_header(ex: GeneratedExercise, parent: GeneratedExercise) -> str:
    t = ex.transform
    kind = t.get("kind", "")
    text = _TRANSFORM_TEXT.get(kind, kind)
    if kind == KIND_MOVE:
        text = f"moved {'up' if t.get('direction', 0) > 0 else 'down'} {t.get('degrees', 1)} degree{'s' if t.get('degrees', 1) != 1 else ''}"
    if kind == KIND_SEQUENCE:
        text = f"sequenced {'up' if t.get('direction', 0) > 0 else 'down'} one degree"
    lines = [f"**{text[0].upper() + text[1:]}** — built from your previous {parent.collection_label} exercise.",
             f"Kept: {', '.join(t.get('inherited', [])) or '—'} · Changed: {', '.join(t.get('changed', [])) or '—'}"
             + (f" · You changed: {', '.join(t.get('overridden', []))}" if t.get("overridden") else "")]
    if kind in (KIND_EASIER, KIND_HARDER):
        lines.append(f"Level {t.get('level_from')} → {t.get('level_to')} (difficulty score {t.get('complexity_before')} → {t.get('complexity_after')}).")
    if t.get("context_mode") == "current_context":
        lines.append("_Rebuilt for your current chord and key, as you asked._")
    if t.get("instrument_rebound"):
        lines.append("_Notated for your current instrument._")
    return "\n\n".join(lines)


def compose_followup_payload(
    req: Any, idea: Any, fu: FollowUp, *, session_ref: Any, instrument: str, notation_instrument: str,
    display_instrument: str, bpm: int, meter: str, chart: dict[str, Any], section_label: str, section_chords: list[str],
) -> dict[str, Any]:
    parent = last_exercise(session_ref)
    if parent is None:
        return _no_exercise_payload()
    from music_coach_ami.exercise_scale_pattern import compose_scale_followup, is_scale_pattern

    if is_scale_pattern(parent):   # M1d: scale patterns (AMI's own generator) have their own follow-up handler
        return compose_scale_followup(fu, parent, session_ref=session_ref, instrument=instrument,
                                      notation_instrument=notation_instrument, display_instrument=display_instrument, bpm=bpm)
    if parent.intent.scope == "span":   # Stage 4a: multi-chord exercises are developed by exercise_develop
        from music_coach_ami.exercise_develop import compose_span_followup

        return compose_span_followup(fu, parent, session_ref=session_ref, instrument=instrument,
                                     notation_instrument=notation_instrument, display_instrument=display_instrument, bpm=bpm)
    if parent.intent.technique or fu.kind == KIND_DEVELOP:   # Stage 4b: single-chord technique exercises and the new development phrases
        from music_coach_ami.exercise_develop_single import compose_single_followup

        return compose_single_followup(fu, parent, session_ref=session_ref, instrument=instrument,
                                       notation_instrument=notation_instrument, display_instrument=display_instrument, bpm=bpm)
    live = {"session_ref": session_ref, "instrument": instrument, "notation_inst": notation_instrument}
    base_diag = {"musical_idea_content": True, "exercise_followup": True, "followup_kind": fu.kind, "followup_utterance": fu.raw,
                 "parent_exercise_id": parent.id}
    try:
        if fu.current_context:
            ex, reason = _regenerate_in_current_context(req, idea, parent, fu, live, chart=chart, section_label=section_label,
                                                        section_chords=section_chords, bpm=bpm, meter=meter,
                                                        notation_instrument=notation_instrument)
            if ex is not None:
                _carry_expression(parent, ex, replace(fu, kind=KIND_REGENERATE))
        else:
            ctx = _rebound_context(parent.context, live, concert_key=fu.explicit_key if fu.explicit_key else "")
            if fu.explicit_key:
                ctx = replace(ctx, concert_key=fu.explicit_key, key_source="explicit_request",
                              key_candidates={**ctx.key_candidates, "previous_exercise_key": parent.context.concert_key})
            if fu.level:
                ctx = replace(ctx, level=fu.level, level_source="explicit_request")
            fn = {KIND_VARIATION: do_variation, KIND_SAME_RHYTHM: do_same_rhythm_new_notes, KIND_SAME_NOTES: do_same_notes_new_rhythm,
                  KIND_EASIER: do_level, KIND_HARDER: do_level, KIND_MOVE: do_move, KIND_SEQUENCE: do_sequence,
                  KIND_EXPRESSION: do_expression}[fu.kind]
            ex, reason = fn(parent, fu, ctx, live)
            if ex is not None and fu.kind != KIND_EXPRESSION:
                _carry_expression(parent, ex, fu)
    except Exception as exc:  # a follow-up must never silently turn into a different operation
        ex, reason = None, f"That follow-up hit an unexpected problem ({type(exc).__name__}: {exc})."
    if ex is None:
        return {
            "direct_answer": reason, "practice_steps": ["Your previous exercise is unchanged — you can keep working with it or ask for something else."],
            "what_to_listen_for": [], "suggested_next_action": "", "notation_abc": "", "notation_abc_sections": [],
            "diagnostics": {**base_diag, "exercise_followup_failed": True, "exercise_followup_failure_reason": reason},
        }
    prose = exercise_prose(ex, display_instrument=display_instrument)
    abc = render_abc(ex, bpm=bpm, title=f"{prose['title']} — {ex.chord}", instrument=ex.context.notation_instrument or ex.context.instrument)
    stored = store_last_exercise(session_ref, ex)
    return {
        "direct_answer": "\n\n".join([_followup_header(ex, parent), prose["direct_answer"]]),
        "practice_steps": prose["practice_steps"], "what_to_listen_for": prose["what_to_listen_for"],
        "suggested_next_action": "Try another follow-up: easier, harder, move it up or down, new notes, or a new rhythm.",
        "notation_abc": abc, "notation_abc_sections": [abc] if abc else [],
        "diagnostics": {
            **base_diag, "exercise_bridge": True, "generated_exercise_id": ex.id, "generated_exercise": ex.to_dict(),
            "exercise_context": ex.context.to_dict(), "exercise_validation": ex.validation, "notation_abc_present": bool(abc),
            "last_exercise_stored": stored, "transform": ex.transform, "practice_concert_key": ex.context.concert_key,
            "written_key": ex.context.written_key, "resolved_instrument": ex.context.instrument,
            "notation_instrument": ex.context.notation_instrument, "bars_generated": ex.bars,
        },
    }


def _regenerate_in_current_context(req, idea, parent, fu, live, *, chart, section_label, section_chords, bpm, meter, notation_instrument):
    """"Another one for the current chord": same intent, resolved against LIVE context."""
    from music_coach_ami.exercise_context import resolve_active_context

    nonce = _next_nonce(parent)
    intent = _intent_for(parent, fu, nonce, keep_vocab_only=True)
    if fu.explicit_key:
        intent = replace(intent, explicit_key=fu.explicit_key)
    ctx, _written = resolve_active_context(
        req, idea, intent, session_ref=live["session_ref"], chart=chart, instrument=live["instrument"],
        notation_instrument=notation_instrument, section_label=section_label, section_chords=section_chords, bpm=bpm, meter=meter,
    )
    if fu.level:
        ctx = replace(ctx, level=fu.level, level_source="explicit_request")
    else:
        level = parent.context.level if parent.context.level in LEVELS else "Intermediate"
        if fu.kind in (KIND_EASIER, KIND_HARDER):
            level = LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(level) + (1 if fu.kind == KIND_HARDER else -1)))]
        ctx = replace(ctx, level=level, level_source="inherited_from_parent" if level == parent.context.level else f"followup_{fu.kind}")
    plan = plan_inputs(intent, ctx)
    ctx = replace(ctx, chord_source=plan["chord_source"], field_sources={**ctx.field_sources, "chord": plan["chord_source"]})
    before = list(parent.midi)
    ex, reason = generate_exercise(intent, ctx, plan, accept=lambda m: [int(x) for x in m.get("midi") or []] != before)
    if ex is None:
        return None, reason
    fu2 = replace(fu, kind=KIND_REGENERATE)
    return _stamp(ex, parent, fu2, inherited=["vocabulary", "level"], changed=["key", "chord", "notes", "rhythm"],
                  context_mode="current_context", live=live), ""
