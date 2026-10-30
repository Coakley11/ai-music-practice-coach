"""AMI M1a: conversational revisions of the working exercise that need no music generation.

Handled here, deterministically and with no API call:

* tempo   - "make it slower", "set it to 100 BPM", "slow it down by 10%", "return to the previous tempo"
* history - "undo that", "redo"
* guard   - a revision that names the exercise ("make it ...", "apply it to ...", "explain why these notes ...") but that
            no engine supports yet gets an honest answer instead of an unrelated generic one

Everything else (easier / harder, new notes, new rhythm, move, sequence, accents, articulation, dynamics ...) stays with
``exercise_followup``; this module only supplies memory (the version history in ``conversation_state``) around it.

A tempo-only change rewrites the ``Q:`` marking of the stored notation and nothing else, so notes, rhythm, articulation,
accents, dynamics, key and chord are byte-identical by construction.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from music_coach_ami import conversation_state as cs
from music_coach_ami.types import CoachIntent, CoachResponse

MIN_BPM, MAX_BPM = 40, 240
STEP_PCT, SMALL_PCT, LARGE_PCT = 0.10, 0.05, 0.20
MIN_STEP_BPM = 4

KIND_TEMPO, KIND_UNDO, KIND_REDO, KIND_UNSUPPORTED = "tempo", "undo", "redo", "unsupported"

_LEAD = r"^(?:(?:please|can you|could you|would you|now|then|and|ok|okay)[, ]+)*"
_IT = r"(?:it|that|this|the (?:exercise|pattern|line|phrase|lick|melody|idea))"

_BPM_SET = re.compile(
    _LEAD + rf"(?:(?:set|put|play|take|bring|change|run|do|make|slow|speed)\s+{_IT}\s+(?:down\s+|up\s+)?(?:to|at)\s+|"
    rf"(?:set|change)\s+(?:the\s+)?(?:tempo|speed)\s+to\s+|(?:at|tempo\s+(?:of|is)?)\s+)"
    r"(?:about\s+|around\s+)?(\d{2,3})\s*(?:bpm|beats per minute)?$"
)
_BPM_BARE = re.compile(_LEAD + r"(\d{2,3})\s*bpm$")
_FASTER = re.compile(r"\b(?:faster|quicker|speed(?:ed)?\s+(?:it\s+|that\s+|this\s+)?up|speed up)\b")
_SLOWER = re.compile(r"\b(?:slower|slow(?:ed)?\s+(?:it\s+|that\s+|this\s+)?down|slow down)\b")
_TEMPO_FORM = re.compile(
    _LEAD + rf"(?:(?:make|play|take|bring|speed|slow|put|run|get)\s+{_IT}\s+|(?:speed|slow)\s+(?:down\s+|up\s+)?{_IT}\s+|"
    r"(?:speed|slow)\s+(?:it\s+|this\s+|that\s+)?(?:up|down)\b|)"
)
_PCT = re.compile(r"\b(\d{1,2})\s*(?:%|percent)")
_DELTA = re.compile(r"\b(?:by\s+)?(\d{1,2})\s*bpm\b")
_SMALL = re.compile(r"\b(?:a\s+(?:bit|little|touch|tad)|slightly|just a (?:bit|little))\b")
_LARGE = re.compile(r"\b(?:much|a\s+lot|way|significantly|a\s+great\s+deal)\b")
_PREVIOUS_TEMPO = re.compile(
    _LEAD + r"(?:go\s+|return\s+|get\s+|put\s+it\s+|take\s+it\s+|switch\s+)?back\s+(?:to\s+)?(?:the\s+)?(?:previous|last|earlier|old|original)\s+(?:tempo|speed|bpm)$"
    r"|" + _LEAD + r"(?:return|revert|go back)\s+to\s+(?:the\s+)?(?:previous|last|earlier|original)\s+(?:tempo|speed|bpm)$"
    r"|" + _LEAD + r"(?:previous|last|original)\s+(?:tempo|speed)(?:\s+again)?$"
)
_UNDO = re.compile(
    _LEAD + r"(?:undo(?:\s+(?:that|it|this|the\s+last\s+(?:change|revision|edit|one)|my\s+last\s+(?:change|request)))?|"
    r"go\s+back(?:\s+one\s+step)?|step\s+back|revert(?:\s+(?:that|it))?|take\s+that\s+back|never\s*mind(?:\s+that)?)$"
)
_REDO = re.compile(_LEAD + r"(?:redo(?:\s+(?:that|it|this))?|put\s+(?:it|that)\s+back\s+again|do\s+that\s+again\s+after\s+undo)$")

# Bare "add accents" has no target: it means the downbeats, and the answer says so.
_BARE_ACCENT = re.compile(_LEAD + r"(?:add|put|give)\s+(?:(?:some|more)\s+)?accents?(?:\s+(?:to\s+)?(?:it|that|this))?$|^accent\s+(?:it|that|this)$")

_UNSUPPORTED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("intervals", re.compile(r"\b(?:thirds?|fourths?|fifths?|sixths?|sevenths?|octaves?|intervals?)\b")),
    ("instrument", re.compile(
        r"\b(?:suitable|good|better|right|ideal|adapt\w*|rewrite|written)\b.{0,24}\b(?:for|on)\b.{0,12}"
        r"\b(?:flute|clarinet|sax\w*|trumpet|trombone|violin|viola|cello|guitar|piano|bass|oboe|horn|voice|vocal\w*)\b"
        r"|\b(?:for|on)\s+(?:a\s+|an\s+|the\s+|my\s+)?(?:flute|clarinet|sax\w*|trumpet|trombone|violin|guitar|piano|oboe|horn)\b")),
    ("section", re.compile(r"\b(?:apply|use|move|transfer|play|try)\b.{0,16}\b(?:to|on|over|in|for)\b.{0,10}\b(?:the\s+)?(?:chorus|verse|bridge|intro|outro|pre-?chorus|solo|section)\b"
                           r"|\bapply\s+(?:it|that|this)\s+to\b")),
    ("explanation", re.compile(
        r"^(?:explain|tell me)\b.{0,40}\b(?:why|how)\b.{0,40}\b(?:notes?|these|those|pattern|line|exercise|work|fit)\b"
        r"|^why\b.{0,30}\b(?:these|those|the notes?|the pattern|the line|the exercise|you (?:chose|picked|choose|pick|used?))\b"
        r"|\bwhy (?:do|does|did|are|is) (?:these|those|the notes?|the pattern|the line|the exercise)\b")),
    ("slurs", re.compile(r"\b(?:slurs?|slurred|legato)\b")),
    ("syncopation", re.compile(r"\bsyncopat\w*\b")),
)
_ANAPHORA = re.compile(r"\b(?:it|that|this|them|these|those|the (?:exercise|pattern|line|phrase|lick|melody|idea|notes|rhythm))\b")
_NAMES_EXPRESSION = re.compile(r"\b(?:slurs?|slurred|syncopat\w*)\b")
_REVISION_VERB = re.compile(r"^(?:(?:please|can you|could you|now|then|and|ok|okay)[, ]+)*(?:make|change|turn|rewrite|modify|adjust|tweak|alter|update|swap|convert|apply|use|add|remove|explain|why|keep|set)\b")


@dataclass(frozen=True)
class Revision:
    kind: str
    mode: str = ""          # tempo: faster | slower | set | previous
    bpm: int = 0
    pct: float = 0.0
    delta: int = 0
    category: str = ""      # unsupported: which capability was asked for
    rewrite: str = ""       # a followup sentence this should be turned into (bare "add accents")
    raw: str = ""


def _norm(question: str) -> str:
    return re.sub(r"\s+", " ", str(question or "").lower()).strip(" .!?,;:")


def parse_revision(question: str, *, has_exercise: bool) -> Revision | None:
    raw = str(question or "").strip()
    low = _norm(raw)
    if not low or len(low.split()) > 16:
        return None
    if _PREVIOUS_TEMPO.search(low):
        return Revision(KIND_TEMPO, mode="previous", raw=raw)
    if _UNDO.search(low) and "original" not in low:
        return Revision(KIND_UNDO, raw=raw)
    if _REDO.search(low):
        return Revision(KIND_REDO, raw=raw)
    m = _BPM_SET.search(low) or _BPM_BARE.search(low)
    if m:
        return Revision(KIND_TEMPO, mode="set", bpm=int(m.group(1)), raw=raw)
    fast, slow = _FASTER.search(low), _SLOWER.search(low)
    if bool(fast) != bool(slow):
        head = _TEMPO_FORM.match(low)
        rest = low[head.end():] if head else low
        rest = _FASTER.sub(" ", _SLOWER.sub(" ", rest))
        pct, delta = _PCT.search(rest), _DELTA.search(rest)
        rest = _DELTA.sub(" ", _PCT.sub(" ", rest))
        rest = _SMALL.sub(" ", _LARGE.sub(" ", rest))
        leftovers = [t for t in re.findall(r"[a-z']+", rest) if t not in
                     {"by", "a", "the", "it", "that", "this", "please", "just", "and", "then", "now", "to", "bit", "little", "much", "lot", "percent", "bpm", "down", "up", "make", "play"}]
        if not leftovers and (head is not None or len(low.split()) <= 4):
            frac = (int(pct.group(1)) / 100.0) if pct else (SMALL_PCT if _SMALL.search(low) else LARGE_PCT if _LARGE.search(low) else STEP_PCT)
            return Revision(KIND_TEMPO, mode="faster" if fast else "slower", pct=frac, delta=int(delta.group(1)) if delta else 0, raw=raw)
    if _BARE_ACCENT.search(low):
        return Revision(KIND_UNSUPPORTED, category="bare_accent", rewrite="accent the downbeats", raw=raw)
    verb, anaphora = _REVISION_VERB.search(low), _ANAPHORA.search(low)
    if not (verb and anaphora or low.startswith(("explain", "why", "apply")) or (verb and _NAMES_EXPRESSION.search(low))):
        return None
    from music_coach_ami.exercise_followup import parse_followup

    if parse_followup(raw) is not None:   # easier / harder / new notes / move / accents on named notes ... belong to the engines
        return None
    for category, rx in _UNSUPPORTED:
        if rx.search(low):
            return Revision(KIND_UNSUPPORTED, category=category, raw=raw)
    if has_exercise and _REVISION_VERB.search(low) and not low.startswith(("why", "explain")) and _ANAPHORA.search(low) and len(low.split()) <= 9:
        return Revision(KIND_UNSUPPORTED, category="other", raw=raw)
    return None


# ---------------------------------------------------------------- responses


_SUPPORTED_NOW = (
    "faster or slower (or “set it to 100 BPM”, “slow it down by 10%”, “return to the previous tempo”), easier or harder, "
    "new notes or a new rhythm, “keep the notes but change the rhythm”, moving or sequencing it, accents, articulation and "
    "dynamics on named notes, “undo that” and “redo”"
)
_CATEGORY_TEXT = {
    "intervals": "changing the pattern to thirds, fourths or other intervals",
    "instrument": "re-writing the exercise for a different instrument",
    "section": "applying the exercise to a different section of the song",
    "explanation": "explaining why the notes fit the chords",
    "slurs": "adding slurs",
    "syncopation": "making the rhythm more syncopated",
    "other": "that change",
}


def _response(direct: str, steps: list[str], *, listen: list[str] | None = None, next_action: str = "", abc: str = "",
              sections: list[str] | None = None, diag: dict[str, Any] | None = None) -> CoachResponse:
    return CoachResponse(
        intent=CoachIntent.SCALE_PRACTICE, direct_answer=direct, practice_steps=steps, what_to_listen_for=list(listen or []),
        suggested_next_action=next_action, notation_abc=abc, notation_abc_sections=list(sections or ([abc] if abc else [])),
        source_solver="ExerciseRevision", confidence=0.9,
        diagnostics={"musical_idea_content": True, "exercise_revision": True, **(diag or {})},
    )


def no_exercise_response(raw: str, *, kind: str) -> CoachResponse:
    what = {"undo": "undo", "redo": "redo"}.get(kind, "change")
    return _response(
        f"There's no exercise from this conversation to {what} yet, so I haven't changed anything.",
        ["Ask for one first — for example “Give me an A minor pentatonic line” or “Give me a guide-tone exercise over Blue Bossa” — "
         "then I can make it slower, harder, add accents, and undo or redo each change."],
        next_action="Ask for an exercise to get started.",
        diag={"exercise_revision_kind": kind, "exercise_revision_failed": True, "exercise_revision_failure_reason": "no_working_exercise", "utterance": raw},
    )


def _unsupported_response(rev: Revision) -> CoachResponse:
    what = _CATEGORY_TEXT.get(rev.category, "that change")
    return _response(
        f"I can't do that to your exercise yet — {what} isn't something I can apply to an existing exercise. Your exercise is unchanged.",
        [f"What I can change right now: {_SUPPORTED_NOW}."],
        next_action="Try one of those, or ask for a new exercise.",
        diag={"exercise_revision_kind": KIND_UNSUPPORTED, "exercise_revision_failed": True,
              "exercise_revision_failure_reason": f"unsupported:{rev.category}", "utterance": rev.raw},
    )


def _swap_tempo(text: str, bpm: int) -> str:
    return re.sub(r"^(Q:\s*1/4\s*=\s*)\d{2,3}", lambda m: f"{m.group(1)}{bpm}", str(text or ""), flags=re.M)


def _retempo_action(action: dict[str, Any] | None, bpm: int) -> tuple[dict[str, Any] | None, bool]:
    """Open-in-Missions carries its own tempo. Only a field that actually exists is updated; otherwise it is left alone."""
    if not isinstance(action, dict):
        return action, False
    out = copy.deepcopy(action)
    changed = False
    if "bpm" in out:
        out["bpm"], changed = int(bpm), True
    ex = out.get("example")
    if isinstance(ex, dict) and "bpm" in ex:
        ex["bpm"], changed = int(bpm), True
    return out, changed


def _new_tempo(rev: Revision, current: int, session_ref: Any) -> tuple[int, str]:
    """(new bpm, "" | reason it cannot be applied)."""
    if rev.mode == "set":
        if not (MIN_BPM <= rev.bpm <= MAX_BPM):
            return 0, f"{rev.bpm} BPM is outside the {MIN_BPM}–{MAX_BPM} BPM range I can notate, so the tempo is unchanged."
        return rev.bpm, ""
    if rev.mode == "previous":
        session = cs._mutable(session_ref)
        st = cs._state(session) if session is not None else None
        if st:
            for ver in reversed(st["versions"][: st["cursor"]]):
                if int(ver["tempo_bpm"]) != current:
                    return int(ver["tempo_bpm"]), ""
        return 0, "There's no earlier tempo in this exercise's history — it has been at the same tempo throughout."
    step = rev.delta or max(MIN_STEP_BPM, round(current * rev.pct))
    new = current + step if rev.mode == "faster" else current - step
    new = max(MIN_BPM, min(MAX_BPM, new))
    if new == current:
        return 0, f"It's already at {current} BPM, the {'fastest' if rev.mode == 'faster' else 'slowest'} tempo I can notate."
    return new, ""


def _apply_tempo(rev: Revision, session_ref: Any) -> CoachResponse:
    ver = cs.current_version(session_ref)
    cur = int(ver["tempo_bpm"])
    new, why = _new_tempo(rev, cur, session_ref)
    base = {"exercise_revision_kind": KIND_TEMPO, "utterance": rev.raw, "tempo_from": cur}
    if why:
        return _response(why + " Your exercise is unchanged.", ["Try “set it to 80 BPM”, or ask for a different change."],
                         diag={**base, "exercise_revision_failed": True, "exercise_revision_failure_reason": "tempo_out_of_range"})
    ex = copy.deepcopy(ver["exercise"])
    ex["tempo_bpm"] = new
    abc = _swap_tempo(ver.get("abc") or "", new)
    sections = [_swap_tempo(s, new) for s in (ver.get("sections") or [])]
    action, missions_updated = _retempo_action(ver.get("action"), new)
    cs.push_version(session_ref, ex, tempo_bpm=new, abc=abc, sections=sections, label=rev.raw, action=action, context=ver.get("context"))
    word = "Faster" if new > cur else "Slower"
    lines = [f"**{word}: {cur} → {new} BPM.** Same exercise — the notes, rhythm, articulation, accents, dynamics, key and chord are unchanged."]
    lines.append(f"The notation's tempo marking now reads {new} BPM.")
    # No Missions claim: the Missions page re-renders its example at the page's own BPM (improv_ctx.bpm / the Backing BPM), so the
    # tempo stored in the Open-in-Missions action is not shown to reach playback. The action is kept in step but never advertised.
    steps = [f"Play it at {new} BPM until it is clean, then bring it back up in small steps.",
             f"Say “undo that” to return to {cur} BPM."]
    diag = {**base, "tempo_to": new, "generated_exercise_id": ex.get("id"), "generated_exercise": ex,
            "missions_tempo_updated": missions_updated, "notation_tempo": new}
    if action:
        diag["open_in_missions"] = action
    return _response("\n\n".join(lines), steps, next_action="Try: slower, harder, add accents, or undo that.", abc=abc, sections=sections, diag=diag)


def _restored(ver: dict[str, Any], header: str, rev: Revision, kind: str, session_ref: Any) -> CoachResponse:
    from music_coach_ami.exercise_bridge import exercise_prose
    from music_coach_ami.exercise_model import GeneratedExercise

    ex = GeneratedExercise.from_dict(ver["exercise"])
    prose = exercise_prose(ex, display_instrument=ex.context.instrument)
    h = cs.history(session_ref)
    diag = {"exercise_revision_kind": kind, "utterance": rev.raw, "generated_exercise_id": ex.id, "generated_exercise": ver["exercise"],
            "tempo_to": int(ver["tempo_bpm"]), "version_index": h["cursor"] + 1, "version_count": h["versions"],
            "can_undo": h["can_undo"], "can_redo": h["can_redo"]}
    if ver.get("action"):
        diag["open_in_missions"] = ver["action"]
    return _response(f"{header}\n\n{prose['direct_answer']}", prose["practice_steps"], listen=prose["what_to_listen_for"],
                     next_action="Say “redo” to bring the change back, or ask for another change.",
                     abc=ver.get("abc") or "", sections=ver.get("sections") or [], diag=diag)


def _apply_history(rev: Revision, session_ref: Any) -> CoachResponse:
    undo = rev.kind == KIND_UNDO
    before = cs.current_version(session_ref)
    ver = cs.step(session_ref, -1 if undo else 1)
    if ver is None:
        text = ("Nothing to undo — this is the first version of the exercise." if undo
                else "Nothing to redo — there's no undone change to bring back.")
        return _response(text, ["Ask for a change (slower, harder, accents …) and I'll keep each version so you can undo and redo."],
                         diag={"exercise_revision_kind": rev.kind, "exercise_revision_failed": True, "exercise_revision_failure_reason": "nothing_to_step", "utterance": rev.raw})
    moved = (before or {}).get("label") if undo else ver.get("label")
    h = cs.history(session_ref)
    where = f"version {h['cursor'] + 1} of {h['versions']}"
    verb = "Undid" if undo else "Redid"
    note = f" “{moved}”" if moved else " the last change"
    return _restored(ver, f"**{verb}{note}.** Back to {where} — {int(ver['tempo_bpm'])} BPM.", rev, rev.kind, session_ref)


# ---------------------------------------------------------------- entry points


def handle_revision(question: str, session_ref: Any) -> tuple[CoachResponse | None, str]:
    """Answer a revision this module owns. Returns (response, "") or (None, rewrite) / (None, "") to let the pipeline go on."""
    has = cs.current_version(session_ref) is not None
    rev = parse_revision(question, has_exercise=has)
    if rev is None:
        return None, ""
    if rev.kind == KIND_UNSUPPORTED and rev.category == "bare_accent":
        return (None, rev.rewrite) if has else (no_exercise_response(rev.raw, kind="expression"), "")
    if not has:
        if rev.kind == KIND_UNSUPPORTED and rev.category == "other":
            return None, ""
        return no_exercise_response(rev.raw, kind=rev.kind), ""
    if rev.kind == KIND_TEMPO:
        return _apply_tempo(rev, session_ref), ""
    if rev.kind in (KIND_UNDO, KIND_REDO):
        return _apply_history(rev, session_ref), ""
    return _unsupported_response(rev), ""
