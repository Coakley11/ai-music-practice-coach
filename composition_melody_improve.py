"""Post-recording slight melody improvements (structured + plain language)."""

from __future__ import annotations

import copy
import re
from typing import Any

from composition_hum_transcription import (
    delete_melody_event,
    nudge_event_pitch,
    set_event_duration,
)
from music_theory import spell_note_in_key

ORIGINAL_TAKE_PREFIX = "composer_hum_original_take_"
IMPROVE_UNDO_PREFIX = "composer_hum_improve_undo_"

QUICK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("smoother_last_measure", "Make the last measure smoother"),
    ("more_rhythm", "Add more rhythm to the melody"),
    ("shorten_first", "Shorten the first note"),
    ("lengthen_last", "Lengthen the last note"),
    ("move_final_later", "Move the final note later"),
    ("simplify_second_measure", "Simplify the second measure"),
)


def original_take_key(section_id: str) -> str:
    return f"{ORIGINAL_TAKE_PREFIX}{section_id}"


def improve_undo_key(section_id: str) -> str:
    return f"{IMPROVE_UNDO_PREFIX}{section_id}"


def preserve_original_take(session: dict[str, Any], section_id: str, events: list[dict[str, Any]]) -> None:
    key = original_take_key(section_id)
    if key not in session:
        session[key] = copy.deepcopy(list(events or []))


def restore_original_take(session: dict[str, Any], section_id: str) -> list[dict[str, Any]] | None:
    snap = session.get(original_take_key(section_id))
    return copy.deepcopy(snap) if isinstance(snap, list) else None


def push_improve_undo(session: dict[str, Any], section_id: str, events: list[dict[str, Any]]) -> None:
    key = improve_undo_key(section_id)
    stack = list(session.get(key) or [])
    stack.append(copy.deepcopy(list(events or [])))
    session[key] = stack[-20:]


def pop_improve_undo(session: dict[str, Any], section_id: str) -> list[dict[str, Any]] | None:
    key = improve_undo_key(section_id)
    stack = list(session.get(key) or [])
    if not stack:
        return None
    prev = stack.pop()
    session[key] = stack
    return prev if isinstance(prev, list) else None


def _beats_per_bar(meter: str) -> float:
    text = str(meter or "4/4")
    if "/" not in text:
        return 4.0
    try:
        num, den = text.split("/", 1)
        return float(num) * (4.0 / float(den))
    except ValueError:
        return 4.0


def _event_measure(ev: dict[str, Any], *, meter: str) -> int:
    bpb = max(1.0, _beats_per_bar(meter))
    beat = float(ev.get("beat") or 0.0)
    return int(beat // bpb) + 1


def _sounding_indices(events: list[dict[str, Any]]) -> list[int]:
    out = []
    for i, ev in enumerate(events):
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            continue
        out.append(i)
    return out


def _clarification(message: str) -> dict[str, Any]:
    return {"ok": False, "needs_clarification": True, "message": message, "events": None, "summary": ""}


def _ok(events: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    return {
        "ok": True,
        "needs_clarification": False,
        "message": "",
        "events": events,
        "summary": summary,
    }


def apply_quick_action(
    events: list[dict[str, Any]],
    action_id: str,
    *,
    key: str = "C",
    meter: str = "4/4",
) -> dict[str, Any]:
    evs = copy.deepcopy(list(events or []))
    sounding = _sounding_indices(evs)
    if not sounding:
        return _clarification("No notes to adjust — record a take first.")

    aid = str(action_id or "").strip()
    if aid == "shorten_first":
        i = sounding[0]
        dur = float(evs[i].get("duration_beats") or 1.0)
        new_dur = max(0.25, dur * 0.5)
        evs = set_event_duration(evs, i, new_dur, meter=meter)
        return _ok(evs, f"Shortened the first note to {new_dur:g} beats.")

    if aid == "lengthen_last":
        i = sounding[-1]
        dur = float(evs[i].get("duration_beats") or 1.0)
        new_dur = min(4.0, dur * 1.5)
        evs = set_event_duration(evs, i, new_dur, meter=meter)
        return _ok(evs, f"Lengthened the last note to {new_dur:g} beats.")

    if aid == "move_final_later":
        i = sounding[-1]
        evs[i]["beat"] = float(evs[i].get("beat") or 0.0) + 0.5
        return _ok(evs, "Moved the final note half a beat later.")

    if aid == "more_rhythm":
        # Split the longest sounding note into two shorter notes
        longest_i = max(sounding, key=lambda j: float(evs[j].get("duration_beats") or 0.0))
        dur = float(evs[longest_i].get("duration_beats") or 1.0)
        if dur < 1.0:
            return _clarification("Notes are already short — try a different improvement or re-record.")
        half = dur / 2.0
        evs = set_event_duration(evs, longest_i, half, meter=meter)
        insert_at = longest_i + 1
        new_ev = copy.deepcopy(evs[longest_i])
        new_ev["beat"] = float(evs[longest_i].get("beat") or 0.0) + half
        new_ev["duration_beats"] = half
        # nudge pitch slightly for motion
        midi = int(new_ev.get("midi") or 60)
        new_ev["midi"] = midi + 2
        new_ev["pitch"] = f"{spell_note_in_key((midi + 2) % 12, key)}{((midi + 2) // 12) - 1}"
        evs.insert(insert_at, new_ev)
        return _ok(evs, "Added rhythmic motion by splitting a long note.")

    if aid == "smoother_last_measure":
        bpb = _beats_per_bar(meter)
        last_m = max(_event_measure(evs[i], meter=meter) for i in sounding)
        idxs = [i for i in sounding if _event_measure(evs[i], meter=meter) == last_m]
        if len(idxs) < 2:
            return _clarification("The last measure needs at least two notes to smooth.")
        # Reduce leaps: pull mid notes toward neighbors
        for i in idxs[1:-1]:
            prev_m = int(evs[idxs[idxs.index(i) - 1]].get("midi") or 60)
            next_m = int(evs[idxs[min(idxs.index(i) + 1, len(idxs) - 1)]].get("midi") or 60)
            target = int(round((prev_m + next_m) / 2.0))
            evs[i]["midi"] = target
            evs[i]["pitch"] = f"{spell_note_in_key(target % 12, key)}{(target // 12) - 1}"
        return _ok(evs, f"Smoothed leaps in measure {last_m}.")

    if aid == "simplify_second_measure":
        idxs = [i for i in sounding if _event_measure(evs[i], meter=meter) == 2]
        if not idxs:
            return _clarification("There is no second measure with notes yet.")
        if len(idxs) <= 2:
            return _clarification("The second measure is already simple.")
        # Keep first and last of measure 2; remove middle
        keep = {idxs[0], idxs[-1]}
        for i in reversed(idxs):
            if i not in keep:
                evs = delete_melody_event(evs, i, meter=meter)
        return _ok(evs, "Simplified the second measure.")

    return _clarification(f"Unknown action: {aid}")


_NOTE_NAME_RE = re.compile(
    r"\b([A-Ga-g])([#b♯♭]?)\b(?:\s*(?:note))?",
)
_MEASURE_RE = re.compile(r"\b(?:measure|bar)\s*(\d+)\b", re.I)
_LAST_NOTE_RE = re.compile(r"\blast\s+note\b", re.I)
_FIRST_NOTE_RE = re.compile(r"\bfirst\s+note\b", re.I)
_CHANGE_TO_RE = re.compile(
    r"(?:change|set|make)\s+(?:the\s+)?(?:last|first|final)?\s*note\s+(?:to\s+)?([A-Ga-g][#b♯♭]?)",
    re.I,
)
_SHORTEN_RE = re.compile(r"\bshorten\b", re.I)
_SMOOTHER_RE = re.compile(r"\bsmooth(?:er|e)?\b", re.I)
_RHYTHM_RE = re.compile(r"\b(?:more\s+rhythm|rhythmic)\b", re.I)
_SIMPLIFY_RE = re.compile(r"\bsimplif", re.I)
_LATER_RE = re.compile(r"\b(?:later|delay)\b", re.I)


def apply_plain_language_improvement(
    events: list[dict[str, Any]],
    instruction: str,
    *,
    key: str = "C",
    meter: str = "4/4",
) -> dict[str, Any]:
    text = str(instruction or "").strip()
    if not text:
        return _clarification("Type a short instruction, or pick a quick action.")

    # Map common phrases to quick actions first
    if _SMOOTHER_RE.search(text) and ("last" in text.lower() or "final" in text.lower()):
        return apply_quick_action(events, "smoother_last_measure", key=key, meter=meter)
    if _RHYTHM_RE.search(text):
        return apply_quick_action(events, "more_rhythm", key=key, meter=meter)
    if _SHORTEN_RE.search(text) and _FIRST_NOTE_RE.search(text):
        return apply_quick_action(events, "shorten_first", key=key, meter=meter)
    if _LATER_RE.search(text) and (_LAST_NOTE_RE.search(text) or "final" in text.lower()):
        return apply_quick_action(events, "move_final_later", key=key, meter=meter)
    if _SIMPLIFY_RE.search(text):
        m = _MEASURE_RE.search(text)
        if m and int(m.group(1)) == 2:
            return apply_quick_action(events, "simplify_second_measure", key=key, meter=meter)
        if "second" in text.lower():
            return apply_quick_action(events, "simplify_second_measure", key=key, meter=meter)
        return _clarification("Which measure should I simplify? (e.g. “Simplify the second measure.”)")

    # Change last/first note to a pitch
    m = _CHANGE_TO_RE.search(text)
    note_target = None
    if m:
        note_target = m.group(1).replace("♯", "#").replace("♭", "b")
    else:
        # “Change the last note to E”
        if ("change" in text.lower() or "to" in text.lower()) and (
            _LAST_NOTE_RE.search(text) or _FIRST_NOTE_RE.search(text)
        ):
            nm = re.search(r"\bto\s+([A-Ga-g][#b♯♭]?)\b", text, re.I)
            if nm:
                note_target = nm.group(1).replace("♯", "#").replace("♭", "b")

    if note_target:
        sounding = _sounding_indices(list(events or []))
        if not sounding:
            return _clarification("No notes to change.")
        if _FIRST_NOTE_RE.search(text):
            idx = sounding[0]
        elif _LAST_NOTE_RE.search(text) or "final" in text.lower():
            idx = sounding[-1]
        else:
            return _clarification("Which note — first or last? e.g. “Change the last note to E.”")
        root = note_target[0].upper() + note_target[1:]
        # Keep octave of existing note; change pitch class
        evs = copy.deepcopy(list(events))
        cur_midi = int(evs[idx].get("midi") or 60)
        from music_theory import CHROMATIC, normalize_root

        nr = normalize_root(root)
        if nr not in CHROMATIC:
            return _clarification(f"I don’t recognize the note “{note_target}”. Try C, D, Eb, F#, …")
        new_pc = CHROMATIC.index(nr)
        new_midi = (cur_midi // 12) * 12 + new_pc
        # Prefer nearer octave
        if abs(new_midi - cur_midi) > 6:
            alt = new_midi - 12 if new_midi > cur_midi else new_midi + 12
            if abs(alt - cur_midi) < abs(new_midi - cur_midi):
                new_midi = alt
        evs[idx]["midi"] = new_midi
        evs[idx]["pitch"] = f"{spell_note_in_key(new_midi % 12, key)}{(new_midi // 12) - 1}"
        return _ok(evs, f"Changed the note to {spell_note_in_key(new_midi % 12, key)}.")

    if len(text) > 120:
        return _clarification(
            "That’s a bigger rewrite — record another take for a substantially different melody. "
            "For slight tweaks, try a short instruction like “Shorten the first note.”"
        )

    return _clarification(
        "I couldn’t apply that as a slight improvement. "
        "Try a quick action, or phrases like “Change the last note to E” or “Make the last measure smoother.”"
    )
