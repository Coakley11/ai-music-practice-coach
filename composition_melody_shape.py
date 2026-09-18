"""Shape / Refine and Advanced Phrase Editor transforms for Composition melody events."""

from __future__ import annotations

import copy
import re
from typing import Any

from music_theory import CHROMATIC, normalize_root, spell_note_in_key

MELODY_REFINEMENTS: tuple[tuple[str, str, str], ...] = (
    ("smoother", "Make it smoother", "Connect notes with smaller steps; fewer leaps."),
    ("energetic", "Make it more energetic", "Add forward motion — shorter notes, more lift on peaks."),
    ("rhythm", "Add more rhythm", "Syncopate or repeat a rhythmic cell twice."),
    ("simplify", "Simplify it", "Fewer notes; one clear shape per phrase."),
    ("emotional", "Make it more emotional", "Widen the dynamic arc — longer notes at the peak."),
    ("range_up", "Increase the range", "Reach one step higher on the climax note."),
    ("singable", "Make it easier to sing", "Stay in a narrow range with mostly steps."),
)


def _pitch_label(midi: int, key: str) -> str:
    m = int(midi)
    return f"{spell_note_in_key(m % 12, key)}{(m // 12) - 1}"


def _sounding(events: list[dict[str, Any]]) -> list[int]:
    out: list[int] = []
    for i, ev in enumerate(events):
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            continue
        out.append(i)
    return out


def events_signature(events: list[dict[str, Any]] | None) -> tuple:
    rows = []
    for e in list(events or []):
        if not isinstance(e, dict):
            continue
        rows.append(
            (
                str(e.get("pitch") or ""),
                float(e.get("duration_beats") or 1.0),
                float(e.get("beat") or 0.0),
                bool(e.get("is_rest")),
                int(e.get("midi") or -1),
            )
        )
    return tuple(rows)


def _repack_beats(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    beat = 0.0
    out = []
    for ev in events:
        row = dict(ev)
        row["beat"] = beat
        beat += float(row.get("duration_beats") or 1.0)
        out.append(row)
    return out


def propose_melody_refinement(
    events: list[dict[str, Any]],
    refinement_id: str,
    *,
    key: str = "C",
) -> dict[str, Any]:
    """Return a changed event proposal for a Shape/Refine action (does not mutate input)."""
    rid = str(refinement_id or "").strip()
    src = [dict(e) for e in list(events or []) if isinstance(e, dict)]
    if not src:
        return {
            "ok": False,
            "unchanged": True,
            "events": [],
            "summary": "No active melody notes to refine yet.",
            "refinement_id": rid,
        }
    label = next((lab for i, lab, _ in MELODY_REFINEMENTS if i == rid), rid)
    updated = [dict(e) for e in src]
    sounding = _sounding(updated)

    if rid == "smoother":
        if len(sounding) < 3:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "Need at least three notes to smooth leaps.",
                "refinement_id": rid,
            }
        for pos, i in enumerate(sounding[1:-1], start=1):
            prev_m = int(updated[sounding[pos - 1]].get("midi") or 60)
            next_m = int(updated[sounding[pos + 1]].get("midi") or 60)
            cur = int(updated[i].get("midi") or 60)
            target = int(round((prev_m + next_m) / 2.0))
            if abs(cur - prev_m) >= 5 or abs(cur - next_m) >= 5:
                updated[i]["midi"] = target
                updated[i]["pitch"] = _pitch_label(target, key)
                updated[i]["is_rest"] = False

    elif rid == "energetic":
        for i in sounding:
            dur = float(updated[i].get("duration_beats") or 1.0)
            updated[i]["duration_beats"] = max(0.25, round(dur * 0.65 * 4) / 4)
        if sounding:
            peak = max(sounding, key=lambda j: int(updated[j].get("midi") or 60))
            midi = int(updated[peak].get("midi") or 60) + 2
            updated[peak]["midi"] = midi
            updated[peak]["pitch"] = _pitch_label(midi, key)
        updated = _repack_beats(updated)

    elif rid == "rhythm":
        if not sounding:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "No sounding notes to rhythmize.",
                "refinement_id": rid,
            }
        longest_i = max(sounding, key=lambda j: float(updated[j].get("duration_beats") or 0.0))
        dur = float(updated[longest_i].get("duration_beats") or 1.0)
        if dur < 1.0:
            for n, i in enumerate(sounding):
                if n % 2 == 1:
                    d = float(updated[i].get("duration_beats") or 1.0)
                    updated[i]["duration_beats"] = max(0.25, d * 0.5)
            updated = _repack_beats(updated)
        else:
            half = dur / 2.0
            updated[longest_i]["duration_beats"] = half
            insert = copy.deepcopy(updated[longest_i])
            insert["beat"] = float(updated[longest_i].get("beat") or 0.0) + half
            insert["duration_beats"] = half
            midi = int(insert.get("midi") or 60) + 2
            insert["midi"] = midi
            insert["pitch"] = _pitch_label(midi, key)
            updated.insert(longest_i + 1, insert)
            updated = _repack_beats(updated)

    elif rid == "simplify":
        if len(sounding) <= 3:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "Melody is already simple — try a different shape.",
                "refinement_id": rid,
            }
        keep = set(sounding[::2])
        keep.add(sounding[-1])
        updated = [ev for i, ev in enumerate(updated) if i in keep]
        if len(_sounding(updated)) < 2:
            updated = [dict(e) for e in src][::2]
        updated = _repack_beats(updated)

    elif rid == "emotional":
        if not sounding:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "No notes to emphasize.",
                "refinement_id": rid,
            }
        peak = max(sounding, key=lambda j: int(updated[j].get("midi") or 60))
        updated[peak]["duration_beats"] = min(
            4.0, float(updated[peak].get("duration_beats") or 1.0) + 1.0
        )
        idx = sounding.index(peak)
        if idx > 0:
            prev = sounding[idx - 1]
            midi = int(updated[prev].get("midi") or 60)
            peak_m = int(updated[peak].get("midi") or 60)
            if abs(peak_m - midi) > 4:
                mid = midi + (1 if peak_m > midi else -1) * 2
                updated[prev]["midi"] = mid
                updated[prev]["pitch"] = _pitch_label(mid, key)
        updated = _repack_beats(updated)

    elif rid == "range_up":
        if not sounding:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "No climax note to raise.",
                "refinement_id": rid,
            }
        peak = max(sounding, key=lambda j: int(updated[j].get("midi") or 60))
        midi = int(updated[peak].get("midi") or 60) + 2
        updated[peak]["midi"] = midi
        updated[peak]["pitch"] = _pitch_label(midi, key)

    elif rid == "singable":
        if len(sounding) < 2:
            return {
                "ok": False,
                "unchanged": True,
                "events": src,
                "summary": "Need more notes to narrow the singing range.",
                "refinement_id": rid,
            }
        midis = [int(updated[i].get("midi") or 60) for i in sounding]
        center = int(round(sum(midis) / float(len(midis))))
        lo, hi = center - 5, center + 5
        for i in sounding:
            m = max(lo, min(hi, int(updated[i].get("midi") or 60)))
            updated[i]["midi"] = m
            updated[i]["pitch"] = _pitch_label(m, key)
        for n in range(1, len(sounding)):
            a, b = sounding[n - 1], sounding[n]
            ma = int(updated[a].get("midi") or 60)
            mb = int(updated[b].get("midi") or 60)
            if abs(mb - ma) > 4:
                mb = ma + (2 if mb > ma else -2)
                updated[b]["midi"] = mb
                updated[b]["pitch"] = _pitch_label(mb, key)

    else:
        return {
            "ok": False,
            "unchanged": True,
            "events": src,
            "summary": f"Unknown refinement: {rid}",
            "refinement_id": rid,
        }

    if events_signature(updated) == events_signature(src):
        return {
            "ok": False,
            "unchanged": True,
            "events": src,
            "summary": f"“{label}” did not change this melody — try another shape or edit notes directly.",
            "refinement_id": rid,
        }
    return {
        "ok": True,
        "unchanged": False,
        "events": updated,
        "summary": f"Applied: {label}",
        "refinement_id": rid,
        "label": label,
    }


def insert_melody_note(
    events: list[dict[str, Any]],
    *,
    at_index: int,
    pitch: str,
    duration_beats: float = 0.5,
    key: str = "C",
    before: bool = True,
) -> list[dict[str, Any]]:
    """Insert a new note before/after ``at_index`` and repack beats."""
    rows = [dict(e) for e in list(events or [])]
    if not rows:
        at_index = 0
        insert_at = 0
    else:
        at_index = max(0, min(int(at_index), len(rows) - 1))
        insert_at = at_index if before else at_index + 1
    text = str(pitch or "C4").strip()
    is_rest = text.lower() == "rest"
    midi: int | None = 60
    if not is_rest:
        octv = 4
        name = text
        if name and name[-1].isdigit():
            octv = int(name[-1])
            name = name[:-1]
        root = normalize_root(name.replace("♯", "#").replace("♭", "b"))
        if root in CHROMATIC:
            midi = 12 * (octv + 1) + CHROMATIC.index(root)
            text = _pitch_label(midi, key)
        else:
            midi = 60
    else:
        midi = None
    new_ev = {
        "pitch": "rest" if is_rest else text,
        "midi": midi,
        "duration_beats": float(duration_beats),
        "beat": 0.0,
        "is_rest": is_rest,
    }
    rows.insert(insert_at, new_ev)
    return _repack_beats(rows)


def delete_melody_note_preserve_gap(
    events: list[dict[str, Any]],
    index: int,
) -> list[dict[str, Any]]:
    """Replace the selected note with a rest of the same duration (keeps measure timing)."""
    rows = [dict(e) for e in list(events or [])]
    if not rows:
        return []
    idx = int(index)
    if idx < 0 or idx >= len(rows):
        return rows
    row = dict(rows[idx])
    if row.get("is_rest") or str(row.get("pitch") or "").lower() == "rest":
        # Already a rest — remove it only if adjacent timing should collapse; keep as no-op.
        return rows
    row["is_rest"] = True
    row["pitch"] = "rest"
    row["midi"] = None
    rows[idx] = row
    return rows


_NOTE_TOKEN = re.compile(r"\b([A-Ga-g])([#b♯♭]?)\b")
_BAR_RE = re.compile(r"\b(?:bar|measure)\s*(\d+)\b", re.I)
_HOLD_RE = re.compile(r"\b(?:hold|lengthen|longer|sustain)\b", re.I)
_ADD_RE = re.compile(r"\b(?:add|insert)\b", re.I)
_OCTAVE_UP_RE = re.compile(r"\b(?:up\s+an\s+octave|octave\s+up)\b", re.I)
_SPACE_RE = re.compile(r"\b(?:more\s+space|leave\s+space)\b", re.I)
_FINAL_RE = re.compile(r"\b(?:final|last)\s+note\b", re.I)
_FIRST_RE = re.compile(r"\bfirst\s+note\b", re.I)
_DELETE_RE = re.compile(r"\b(?:delete|remove|take\s+out|omit)\b", re.I)
_PASS_ORDINAL = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
}
_PASS_RE = re.compile(
    r"\b(?:"
    r"(?P<ord>first|second|third|fourth|1st|2nd|3rd|4th)\s+(?:time|pass|repeat|occurrence)"
    r"|pass\s*(?P<pnum>\d+)"
    r"|repeat\s*(?P<rnum>\d+)"
    r")\b",
    re.I,
)


def _parse_pass_index(text: str) -> int | None:
    """Return 0-based pass/repeat index if the instruction names one."""
    m = _PASS_RE.search(str(text or ""))
    if not m:
        return None
    ord_tok = m.group("ord")
    if ord_tok:
        return _PASS_ORDINAL.get(ord_tok.lower())
    for g in ("pnum", "rnum"):
        raw = m.group(g)
        if raw:
            try:
                n = int(raw)
            except (TypeError, ValueError):
                return None
            return max(0, n - 1)
    return None


def _event_pass_index(ev: dict[str, Any]) -> int | None:
    if ev.get("pass_index") is not None:
        try:
            return int(ev.get("pass_index"))
        except (TypeError, ValueError):
            return None
    if ev.get("repeat_index") is not None:
        try:
            return int(ev.get("repeat_index"))
        except (TypeError, ValueError):
            return None
    return None


def _filter_indices_by_pass(events: list[dict[str, Any]], indices: list[int], pass_i: int | None) -> list[int]:
    if pass_i is None:
        return list(indices)
    out: list[int] = []
    for i in indices:
        if i < 0 or i >= len(events):
            continue
        pi = _event_pass_index(events[i])
        if pi is None or pi == pass_i:
            out.append(i)
    return out


def _pass_choice_prompt(events: list[dict[str, Any]], indices: list[int], *, action: str) -> dict[str, Any]:
    choices = []
    for i in indices:
        ev = events[i]
        pi = _event_pass_index(ev)
        pass_bit = f" · pass {pi + 1}" if pi is not None else ""
        choices.append(
            {
                "index": i,
                "label": (
                    f"Note {i + 1}: {ev.get('pitch')} @ beat {float(ev.get('beat') or 0):g}{pass_bit}"
                ),
            }
        )
    return {
        "ok": False,
        "needs_choice": True,
        "message": f"Which occurrence should I {action}? Choose a pass/note.",
        "choices": choices,
        "events": [dict(e) for e in events],
        "pending_action": {"kind": action, "indices": indices},
    }


def _pc_name(token: str) -> str:
    t = token.replace("♯", "#").replace("♭", "b")
    root = normalize_root(t[0].upper() + t[1:] if t else "")
    return root if root in CHROMATIC else ""


def _events_in_bar(events: list[dict[str, Any]], bar: int, *, beats_per_bar: float = 4.0) -> list[int]:
    out = []
    for i, ev in enumerate(events):
        beat = float(ev.get("beat") or 0.0)
        m = int(beat // max(1.0, beats_per_bar)) + 1
        if m == bar:
            out.append(i)
    return out


def _match_pitch_indices(events: list[dict[str, Any]], pc: str) -> list[int]:
    want = normalize_root(pc)
    if want not in CHROMATIC:
        return []
    want_pc = CHROMATIC.index(want)
    hits = []
    for i, ev in enumerate(events):
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            continue
        midi = ev.get("midi")
        if midi is not None:
            if int(midi) % 12 == want_pc:
                hits.append(i)
            continue
        pitch = str(ev.get("pitch") or "")
        name = pitch[:-1] if pitch and pitch[-1].isdigit() else pitch
        if normalize_root(name) == want:
            hits.append(i)
    return hits


def apply_natural_language_melody_edit(
    events: list[dict[str, Any]],
    instruction: str,
    *,
    key: str = "C",
    meter: str = "4/4",
) -> dict[str, Any]:
    """Interpret a short musical instruction against the active event timeline."""
    text = str(instruction or "").strip()
    src = [dict(e) for e in list(events or [])]
    if not text:
        return {"ok": False, "needs_choice": False, "message": "Type a short musical change.", "events": src}
    if not src:
        return {"ok": False, "needs_choice": False, "message": "No active melody to edit.", "events": []}

    try:
        num = int(str(meter or "4/4").split("/", 1)[0])
        bpb = float(num)
    except Exception:
        bpb = 4.0

    updated = [dict(e) for e in src]
    sounding = _sounding(updated)
    bar_m = _BAR_RE.search(text)
    bar = int(bar_m.group(1)) if bar_m else None
    pass_i = _parse_pass_index(text)

    # Delete / remove note
    if _DELETE_RE.search(text):
        candidates: list[int] = []
        note_m = _NOTE_TOKEN.search(text)
        if note_m:
            pc = _pc_name(note_m.group(1) + (note_m.group(2) or ""))
            candidates = _match_pitch_indices(updated, pc)
            if bar is not None:
                in_bar = set(_events_in_bar(updated, bar, beats_per_bar=bpb))
                candidates = [i for i in candidates if i in in_bar]
            candidates = _filter_indices_by_pass(updated, candidates, pass_i)
            # "second G" → second match when no pass filter
            if re.search(r"\bsecond\b", text, re.I) and pass_i is None and len(candidates) >= 2:
                candidates = [candidates[1]]
            elif re.search(r"\bfirst\b", text, re.I) and pass_i is None and candidates:
                candidates = [candidates[0]]
        elif _FINAL_RE.search(text) and sounding:
            if pass_i is not None:
                pass_idxs = [i for i in sounding if _event_pass_index(updated[i]) == pass_i]
                candidates = [pass_idxs[-1]] if pass_idxs else [sounding[-1]]
            else:
                candidates = [sounding[-1]]
        elif _FIRST_RE.search(text) and sounding:
            candidates = _filter_indices_by_pass(updated, [sounding[0]], pass_i) or [sounding[0]]
        if len(candidates) > 1:
            return _pass_choice_prompt(updated, candidates, action="delete")
        if len(candidates) == 1:
            updated = delete_melody_note_preserve_gap(updated, candidates[0])
            return {
                "ok": True,
                "needs_choice": False,
                "message": "Replaced that note with a rest (timing preserved).",
                "events": updated,
            }
        return {
            "ok": False,
            "needs_choice": False,
            "message": "Could not find which note to delete.",
            "events": src,
        }

    # Pass-aware climax: "second time through end higher" / "third pass ... higher"
    if pass_i is not None and (
        _OCTAVE_UP_RE.search(text)
        or re.search(r"\b(?:higher|end\s+higher|climax)\b", text, re.I)
        or (_FINAL_RE.search(text) and re.search(r"\b(?:higher|up|raise)\b", text, re.I))
    ):
        pass_idxs = [i for i in sounding if _event_pass_index(updated[i]) == pass_i]
        if pass_idxs:
            target_idx = pass_idxs[-1]
            midi = int(updated[target_idx].get("midi") or 60) + 12
            updated[target_idx]["midi"] = midi
            updated[target_idx]["pitch"] = _pitch_label(midi, key)
            return {
                "ok": True,
                "needs_choice": False,
                "message": f"Raised the ending of pass {pass_i + 1}.",
                "events": updated,
            }
        return _pass_choice_prompt(
            updated,
            sounding[-min(6, len(sounding)) :],
            action="octave_up",
        )

    if _OCTAVE_UP_RE.search(text):
        target_idx = None
        gm = re.search(r"second\s+([A-Ga-g][#b♯♭]?)", text, re.I)
        if gm:
            pc = _pc_name(gm.group(1))
            hits = _filter_indices_by_pass(updated, _match_pitch_indices(updated, pc), pass_i)
            if len(hits) >= 2 and pass_i is None:
                target_idx = hits[1]
            elif len(hits) == 1:
                target_idx = hits[0]
            elif len(hits) > 1:
                return _pass_choice_prompt(updated, hits, action="octave_up")
            else:
                return {
                    "ok": False,
                    "needs_choice": False,
                    "message": f"Could not find a {pc} to move up an octave.",
                    "events": src,
                }
        if target_idx is None and _FINAL_RE.search(text) and sounding:
            finals = _filter_indices_by_pass(updated, sounding, pass_i)
            target_idx = finals[-1] if finals else sounding[-1]
        if target_idx is None and _FIRST_RE.search(text) and sounding:
            firsts = _filter_indices_by_pass(updated, sounding, pass_i)
            target_idx = firsts[0] if firsts else sounding[0]
        if target_idx is not None:
            midi = int(updated[target_idx].get("midi") or 60) + 12
            updated[target_idx]["midi"] = midi
            updated[target_idx]["pitch"] = _pitch_label(midi, key)
            return {"ok": True, "needs_choice": False, "message": "Moved the note up an octave.", "events": updated}

    # Compound: hold D ... and add short E before F
    hold_done = False
    if _HOLD_RE.search(text):
        candidates: list[int] = []
        note_m = _NOTE_TOKEN.search(text)
        if note_m:
            pc = _pc_name(note_m.group(1) + (note_m.group(2) or ""))
            candidates = _match_pitch_indices(updated, pc)
            if bar is not None:
                in_bar = set(_events_in_bar(updated, bar, beats_per_bar=bpb))
                candidates = [i for i in candidates if i in in_bar]
            candidates = _filter_indices_by_pass(updated, candidates, pass_i)
        elif _FINAL_RE.search(text) and sounding:
            if pass_i is not None:
                pass_idxs = [i for i in sounding if _event_pass_index(updated[i]) == pass_i]
                candidates = [pass_idxs[-1]] if pass_idxs else [sounding[-1]]
            else:
                candidates = [sounding[-1]]
        elif _FIRST_RE.search(text) and sounding:
            candidates = _filter_indices_by_pass(updated, [sounding[0]], pass_i) or [sounding[0]]
        if len(candidates) > 1:
            return _pass_choice_prompt(updated, candidates, action="hold")
        if len(candidates) == 1:
            i = candidates[0]
            updated[i]["duration_beats"] = min(4.0, float(updated[i].get("duration_beats") or 1.0) + 1.0)
            hold_done = True
        elif _FINAL_RE.search(text) and sounding:
            i = sounding[-1]
            updated[i]["duration_beats"] = min(4.0, float(updated[i].get("duration_beats") or 1.0) + 1.0)
            hold_done = True

    if _ADD_RE.search(text):
        m = re.search(
            r"add\s+(?:a\s+)?(?:short\s+)?([A-Ga-g][#b♯♭]?\d?)\s+(before|after)\s+(?:the\s+)?([A-Ga-g][#b♯♭]?\d?)",
            text,
            re.I,
        )
        if m:
            add_pitch = m.group(1)
            where = m.group(2).lower()
            target_pitch = m.group(3)
            pc = _pc_name(re.sub(r"\d", "", target_pitch))
            hits = _match_pitch_indices(updated, pc)
            if bar is not None:
                in_bar = set(_events_in_bar(updated, bar, beats_per_bar=bpb))
                hits = [i for i in hits if i in in_bar]
            hits = _filter_indices_by_pass(updated, hits, pass_i)
            if len(hits) > 1:
                choices = []
                for i in hits:
                    ev = updated[i] if hold_done else src[i]
                    pi = _event_pass_index(ev if isinstance(ev, dict) else {})
                    pass_bit = f" · pass {pi + 1}" if pi is not None else ""
                    choices.append(
                        {
                            "index": i,
                            "label": (
                                f"Note {i + 1}: {ev.get('pitch')} @ beat "
                                f"{float(ev.get('beat') or 0):g}{pass_bit}"
                            ),
                        }
                    )
                return {
                    "ok": False,
                    "needs_choice": True,
                    "message": f"There are several {pc} notes. Where should I insert {add_pitch}?",
                    "choices": choices,
                    "events": src if not hold_done else updated,
                    "pending_action": {
                        "kind": "insert",
                        "pitch": add_pitch,
                        "before": where == "before",
                        "indices": hits,
                        "base_events": updated,
                    },
                }
            if len(hits) == 1:
                updated = insert_melody_note(
                    updated,
                    at_index=hits[0],
                    pitch=add_pitch,
                    duration_beats=0.5,
                    key=key,
                    before=(where == "before"),
                )
            elif not hits:
                return {
                    "ok": False,
                    "needs_choice": False,
                    "message": f"Could not find a {pc} note to insert around.",
                    "events": src,
                }

    if _SPACE_RE.search(text) and sounding:
        last = sounding[-1]
        updated = insert_melody_note(
            updated,
            at_index=last,
            pitch="rest",
            duration_beats=1.0,
            key=key,
            before=True,
        )

    updated = _repack_beats(updated)
    if events_signature(updated) == events_signature(src):
        return {
            "ok": False,
            "needs_choice": False,
            "message": (
                "I couldn’t apply that as a structured edit. "
                "Try “Hold the final note longer”, “Add a short E before the F”, "
                "or select a note and edit it directly."
            ),
            "events": src,
        }
    return {
        "ok": True,
        "needs_choice": False,
        "message": "Updated the melody proposal from your instruction.",
        "events": updated,
    }


def resolve_melody_edit_choice(
    events: list[dict[str, Any]],
    pending_action: dict[str, Any],
    choice_index: int,
    *,
    key: str = "C",
) -> dict[str, Any]:
    """Apply a previously ambiguous NL edit after the user picks a target note."""
    base = pending_action.get("base_events")
    src = [dict(e) for e in list(base if isinstance(base, list) else events or [])]
    kind = str((pending_action or {}).get("kind") or "")
    idx = int(choice_index)
    if kind == "hold":
        if idx < 0 or idx >= len(src):
            return {"ok": False, "message": "Invalid note choice.", "events": src}
        src[idx]["duration_beats"] = min(4.0, float(src[idx].get("duration_beats") or 1.0) + 1.0)
        return {"ok": True, "message": "Lengthened the selected note.", "events": _repack_beats(src)}
    if kind == "delete":
        if idx < 0 or idx >= len(src):
            return {"ok": False, "message": "Invalid note choice.", "events": src}
        out = delete_melody_note_preserve_gap(src, idx)
        return {"ok": True, "message": "Replaced that note with a rest.", "events": out}
    if kind == "octave_up":
        if idx < 0 or idx >= len(src):
            return {"ok": False, "message": "Invalid note choice.", "events": src}
        midi = int(src[idx].get("midi") or 60) + 12
        src[idx]["midi"] = midi
        src[idx]["pitch"] = _pitch_label(midi, key)
        return {"ok": True, "message": "Moved the selected note up an octave.", "events": _repack_beats(src)}
    if kind == "insert":
        pitch = str(pending_action.get("pitch") or "C4")
        before = bool(pending_action.get("before", True))
        out = insert_melody_note(src, at_index=idx, pitch=pitch, duration_beats=0.5, key=key, before=before)
        return {"ok": True, "message": f"Inserted {pitch}.", "events": out}
    return {"ok": False, "message": "Nothing to resolve.", "events": src}
