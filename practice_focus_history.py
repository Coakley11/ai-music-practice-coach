"""Historical Practice Focus aggregation for Practice Log / Practice Coach.

Consumes ``practice_focus_snapshot`` / ``practice_focus_policy``.
Does **not** own the live Practice Focus selector.

Exact Focus vs coarse ``focus_area`` vs missing are distinguished.
Missing historical Focus is never invented from today's selector.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Mapping

from practice_focus_policy import resolve_focus_profile
from practice_focus_snapshot import (
    SNAPSHOT_KEY,
    historical_focus_prompt_block,
    read_practice_focus_snapshot,
    snapshot_from_historical_fields,
)

FOCUS_SOURCE_EXACT = "exact"
FOCUS_SOURCE_COARSE = "coarse_focus_area"
FOCUS_SOURCE_MISSING = "not_recorded"

_COARSE_AREAS = frozenset(
    {
        "tone",
        "timing/rhythm",
        "melody",
        "chords",
        "soloing/improv",
        "transcription",
        "ear training",
        "lyrics/cues",
        "backing track",
        "performance",
        "technical exercise",
        "scales/technique",
        "repertoire",
        "general",
    }
)


def _parse_date(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _entry_minutes(entry: Mapping[str, Any]) -> int | None:
    """Return recorded minutes, or None when duration was not meaningfully logged.

    Does not invent minutes. Zero or missing → None.
    """
    for key in ("duration_minutes", "minutes"):
        if key not in entry:
            continue
        raw = entry.get(key)
        if raw is None or raw == "":
            return None
        try:
            mins = int(raw)
        except (TypeError, ValueError):
            return None
        if mins <= 0:
            return None
        return mins
    return None


def exact_practice_focus_from_entry(entry: Mapping[str, Any] | None) -> str:
    """Exact user-facing Practice Focus from a historical row. Empty if absent."""
    if not isinstance(entry, Mapping):
        return ""
    snap = read_practice_focus_snapshot(entry.get(SNAPSHOT_KEY))
    if snap and snap.get("practice_focus"):
        return str(snap["practice_focus"]).strip()
    for key in ("practice_focus", "focus"):
        label = str(entry.get(key) or "").strip()
        if not label:
            continue
        # Do not treat coarse taxonomy labels as exact Practice Focus.
        if label.lower() in _COARSE_AREAS:
            continue
        return label
    return ""


def coarse_focus_area_from_entry(entry: Mapping[str, Any] | None) -> str:
    if not isinstance(entry, Mapping):
        return ""
    return str(entry.get("focus_area") or "").strip()


def resolve_entry_historical_focus(entry: Mapping[str, Any] | None) -> dict[str, Any]:
    """Classify one log row: exact / coarse-only / missing."""
    if not isinstance(entry, Mapping):
        return {
            "source": FOCUS_SOURCE_MISSING,
            "exact_focus": "",
            "focus_area": "",
            "instrument": "",
            "snapshot": None,
        }
    exact = exact_practice_focus_from_entry(entry)
    coarse = coarse_focus_area_from_entry(entry)
    instrument = str(
        entry.get("instrument_family")
        or entry.get("instrument")
        or ""
    ).strip()
    snap = read_practice_focus_snapshot(entry.get(SNAPSHOT_KEY))
    if exact and snap is None:
        snap = snapshot_from_historical_fields(
            instrument=instrument,
            practice_focus=exact,
            captured_at=entry.get("created_at") or entry.get("date"),
            instrument_display=str(entry.get("instrument") or instrument),
        )
    if exact:
        source = FOCUS_SOURCE_EXACT
    elif coarse and coarse.lower() not in ("", "general"):
        source = FOCUS_SOURCE_COARSE
    else:
        source = FOCUS_SOURCE_MISSING
        coarse = coarse if coarse and coarse.lower() != "general" else ""
    return {
        "source": source,
        "exact_focus": exact,
        "focus_area": coarse,
        "instrument": instrument or str(entry.get("instrument") or "").strip(),
        "snapshot": snap,
        "date": str(entry.get("date") or "").strip(),
        "notes": str(entry.get("notes") or entry.get("practice") or "").strip(),
        "what_went_well": str(entry.get("what_went_well") or "").strip(),
        "what_was_hard": str(entry.get("what_was_hard") or "").strip(),
        "duration_minutes": _entry_minutes(entry),
    }


def log_entry_focus_caption(entry: Mapping[str, Any] | None) -> str:
    """Understated UI label for a Practice Log card."""
    info = resolve_entry_historical_focus(entry)
    if info["source"] == FOCUS_SOURCE_EXACT and info["exact_focus"]:
        return f"Practice Focus: {info['exact_focus']}"
    if info["source"] == FOCUS_SOURCE_COARSE and info["focus_area"]:
        return f"Focus area: {info['focus_area']} (exact Practice Focus not recorded)"
    return "Practice Focus: Not recorded"


def preserve_historical_focus_on_update(
    existing: Mapping[str, Any],
    updates: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Keep frozen Focus unless the update intentionally sets a new exact Focus.

    Editing ordinary fields (notes, duration, coarse focus_area) must not
    replace historical Focus with today's live selector.
    """
    out = dict(updates or {})
    intentional = False
    for key in ("practice_focus", "focus", SNAPSHOT_KEY):
        if key in out and str(out.get(key) or "").strip():
            intentional = True
            break
    if intentional:
        return out
    # Strip accidental empties / live contamination; restore from existing.
    for key in ("focus", "practice_focus", SNAPSHOT_KEY):
        out.pop(key, None)
        if existing.get(key) not in (None, "", {}, []):
            out[key] = existing.get(key)
    return out


def filter_entries_for_period(
    entries: list[Mapping[str, Any]] | None,
    *,
    window_days: int = 0,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    rows = [dict(e) for e in (entries or []) if isinstance(e, Mapping) and not e.get("deleted")]
    start = _parse_date(start_date) if start_date and not isinstance(start_date, date) else start_date
    end = _parse_date(end_date) if end_date and not isinstance(end_date, date) else end_date
    if window_days and window_days > 0 and start is None and end is None:
        anchor = today or date.today()
        start = anchor - timedelta(days=max(0, int(window_days) - 1))
        end = anchor
    out: list[dict[str, Any]] = []
    for row in rows:
        d = _parse_date(row.get("date"))
        if start is not None and (d is None or d < start):
            continue
        if end is not None and (d is None or d > end):
            continue
        out.append(row)
    return out


def aggregate_practice_focus_history(
    entries: list[Mapping[str, Any]] | None,
    *,
    window_days: int = 0,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    today: date | None = None,
    current_focus: str = "",
    current_instrument: str = "",
) -> dict[str, Any]:
    """Compute reliable Focus facts for a period (before AI narrative)."""
    visible = filter_entries_for_period(
        entries,
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        today=today,
    )
    resolved = [resolve_entry_historical_focus(e) for e in visible]

    exact_session_counts: Counter[str] = Counter()
    exact_minutes: Counter[str] = Counter()
    coarse_session_counts: Counter[str] = Counter()
    pair_session_counts: Counter[str] = Counter()
    pair_minutes: Counter[str] = Counter()
    dates_by_focus: dict[str, list[str]] = defaultdict(list)
    notes_by_focus: dict[str, list[str]] = defaultdict(list)
    missing_exact = 0
    missing_duration = 0
    recorded_minutes_total = 0
    sessions_with_duration = 0

    for info in resolved:
        mins = info.get("duration_minutes")
        if mins is None:
            missing_duration += 1
        else:
            sessions_with_duration += 1
            recorded_minutes_total += int(mins)

        exact = str(info.get("exact_focus") or "").strip()
        coarse = str(info.get("focus_area") or "").strip()
        inst = str(info.get("instrument") or "").strip() or "Unknown"
        d = str(info.get("date") or "").strip()

        if info["source"] == FOCUS_SOURCE_EXACT and exact:
            exact_session_counts[exact] += 1
            if mins is not None:
                exact_minutes[exact] += int(mins)
            pair = f"{inst} · {exact}"
            pair_session_counts[pair] += 1
            if mins is not None:
                pair_minutes[pair] += int(mins)
            if d:
                dates_by_focus[exact].append(d)
            note_bits = [
                t
                for t in (
                    info.get("notes"),
                    info.get("what_went_well"),
                    info.get("what_was_hard"),
                )
                if t
            ]
            if note_bits:
                notes_by_focus[exact].append(" | ".join(note_bits)[:240])
        else:
            missing_exact += 1
            if coarse:
                coarse_session_counts[coarse] += 1

    dominant_exact = exact_session_counts.most_common(1)[0][0] if exact_session_counts else ""
    current = str(current_focus or "").strip()

    return {
        "period": {
            "window_days": int(window_days or 0),
            "start_date": str(start_date or "")[:10],
            "end_date": str(end_date or "")[:10],
            "session_count": len(visible),
        },
        "current_practice_focus": current,
        "current_instrument": str(current_instrument or "").strip(),
        "exact_focus_session_counts": dict(exact_session_counts.most_common()),
        "exact_focus_recorded_minutes": dict(exact_minutes.most_common()),
        "instrument_focus_session_counts": dict(pair_session_counts.most_common()),
        "instrument_focus_recorded_minutes": dict(pair_minutes.most_common()),
        "coarse_focus_area_session_counts": dict(coarse_session_counts.most_common()),
        "dates_by_exact_focus": {k: v for k, v in dates_by_focus.items()},
        "notes_by_exact_focus": {k: v[:5] for k, v in notes_by_focus.items()},
        "sessions_missing_exact_focus": missing_exact,
        "sessions_missing_duration": missing_duration,
        "sessions_with_recorded_duration": sessions_with_duration,
        "recorded_minutes_total": recorded_minutes_total,
        "dominant_exact_focus": dominant_exact,
        "current_differs_from_historical": bool(
            current and dominant_exact and current != dominant_exact
        ),
    }


def compact_focus_fields_for_ami(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Fields to merge into AMI compact session / recent_entry records."""
    info = resolve_entry_historical_focus(entry)
    out: dict[str, Any] = {
        "focus_source": info["source"],
        "focus_area": info.get("focus_area") or None,
    }
    if info["exact_focus"]:
        out["practice_focus"] = info["exact_focus"]
        out["exact_practice_focus"] = info["exact_focus"]
    if info.get("snapshot"):
        out[SNAPSHOT_KEY] = info["snapshot"]
    return {k: v for k, v in out.items() if v not in (None, "", {}, [])}


def compact_practice_focus_coach_block(
    history: Mapping[str, Any] | None,
    *,
    max_priorities: int = 4,
) -> str:
    """Compact prompt/context for weekly/monthly Practice Coach — not full policy dicts."""
    hist = history if isinstance(history, Mapping) else {}
    lines: list[str] = [
        "Historical Practice Focus context (past sessions are frozen; do not rewrite them):",
    ]
    period = hist.get("period") if isinstance(hist.get("period"), Mapping) else {}
    session_count = int(period.get("session_count") or 0)
    lines.append(f"- Sessions in period: {session_count}")
    lines.append(
        f"- Recorded minutes (entries with duration only): "
        f"{int(hist.get('recorded_minutes_total') or 0)} "
        f"across {int(hist.get('sessions_with_recorded_duration') or 0)} sessions; "
        f"{int(hist.get('sessions_missing_duration') or 0)} session(s) lack duration."
    )
    exact_counts = hist.get("exact_focus_session_counts") or {}
    if exact_counts:
        bits = [f"{k} ({v})" for k, v in list(exact_counts.items())[:6]]
        lines.append(f"- Exact Practice Focus distribution (sessions): {', '.join(bits)}")
    else:
        lines.append("- Exact Practice Focus distribution: none recorded in this period.")
    mins = hist.get("exact_focus_recorded_minutes") or {}
    if mins:
        bits = [f"{k} ({v} min)" for k, v in list(mins.items())[:6]]
        lines.append(f"- Exact Focus recorded minutes: {', '.join(bits)}")
    pairs = hist.get("instrument_focus_session_counts") or {}
    if pairs:
        bits = [f"{k} ({v})" for k, v in list(pairs.items())[:6]]
        lines.append(f"- Instrument · Focus pairings: {', '.join(bits)}")
    coarse = hist.get("coarse_focus_area_session_counts") or {}
    if coarse:
        bits = [f"{k} ({v})" for k, v in list(coarse.items())[:4]]
        lines.append(
            f"- Coarse focus_area only (no exact Practice Focus): {', '.join(bits)}. "
            "Do not invent an exact Focus label from these."
        )
    missing = int(hist.get("sessions_missing_exact_focus") or 0)
    if missing:
        lines.append(
            f"- {missing} session(s) have no exact Practice Focus. "
            "Do not assign the current selector to them."
        )
    current = str(hist.get("current_practice_focus") or "").strip()
    dominant = str(hist.get("dominant_exact_focus") or "").strip()
    if current:
        lines.append(f"- Current Practice Focus (for next-step recommendations only): {current}")
    if hist.get("current_differs_from_historical") and dominant and current:
        lines.append(
            f"- Distinguish past vs present: historical period was mostly **{dominant}**; "
            f"current goal is **{current}**. Interpret past sessions as {dominant}."
        )
    # Compact meaning for top exact focuses only
    for label in list(exact_counts.keys())[:2]:
        inst = str(hist.get("current_instrument") or "").strip()
        for pair in (hist.get("instrument_focus_session_counts") or {}):
            if str(pair).endswith(f"· {label}") or str(pair).endswith(label):
                inst = str(pair).split("·", 1)[0].strip() or inst
                break
        profile = resolve_focus_profile(inst, label)
        priorities = "; ".join(profile.coaching_priorities[:max_priorities])
        lines.append(f"- Meaning of historical Focus **{label}**: {priorities}")
        notes = (hist.get("notes_by_exact_focus") or {}).get(label) or []
        if notes:
            lines.append(f"- User notes under **{label}**: {notes[0]}")
    lines.append(
        "- Do not invent causal % improvements or unsupported measurements. "
        "Prefer session counts, recorded minutes, and the user's own notes."
    )
    return "\n".join(lines)


def attach_history_to_practice_payload(
    payload: dict[str, Any],
    entries: list[Mapping[str, Any]] | None,
    *,
    window_days: int = 14,
    current_focus: str = "",
    current_instrument: str = "",
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Attach structured Focus history + compact coach block onto an AMI payload."""
    history = aggregate_practice_focus_history(
        entries,
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        today=today,
        current_focus=current_focus,
        current_instrument=current_instrument,
    )
    block = compact_practice_focus_coach_block(history)
    payload["practice_focus_history"] = history
    payload["practice_focus_history_block"] = block
    pl = payload.get("practice_log_summary")
    if isinstance(pl, dict):
        pl = dict(pl)
        pl["practice_focus_history"] = history
        pl["exact_focus_session_counts"] = history.get("exact_focus_session_counts")
        pl["exact_focus_recorded_minutes"] = history.get("exact_focus_recorded_minutes")
        pl["instrument_focus_session_counts"] = history.get("instrument_focus_session_counts")
        pl["sessions_missing_exact_focus"] = history.get("sessions_missing_exact_focus")
        pl["sessions_missing_duration"] = history.get("sessions_missing_duration")
        pl["current_practice_focus"] = history.get("current_practice_focus")
        payload["practice_log_summary"] = pl
    return payload


def freeze_focus_for_new_log_entry(session_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Snapshot exact live Focus for a NEW log entry (same-rerun safe)."""
    try:
        from practice_focus_evaluation import freeze_focus_snapshot_for_analysis

        snap = freeze_focus_snapshot_for_analysis(session_state)
        if snap:
            return {
                "practice_focus_snapshot": snap,
                "focus": snap.get("practice_focus") or "",
                "practice_focus": snap.get("practice_focus") or "",
            }
    except ImportError:
        pass
    ss = session_state if isinstance(session_state, Mapping) else {}
    exact = str(ss.get("focus") or "").strip()
    inst = str(ss.get("instrument") or "").strip()
    if not exact:
        return {}
    snap = snapshot_from_historical_fields(instrument=inst, practice_focus=exact)
    if not snap:
        return {}
    return {
        "practice_focus_snapshot": snap,
        "focus": snap.get("practice_focus") or exact,
        "practice_focus": snap.get("practice_focus") or exact,
    }


def single_entry_historical_prompt(
    entry: Mapping[str, Any],
    *,
    current_focus: str = "",
) -> str:
    info = resolve_entry_historical_focus(entry)
    if info["source"] == FOCUS_SOURCE_EXACT and info.get("snapshot"):
        return historical_focus_prompt_block(info["snapshot"], current_focus=current_focus)
    if info["source"] == FOCUS_SOURCE_COARSE:
        return (
            f"This older session was categorized broadly as {info['focus_area']}; "
            "an exact Practice Focus was not recorded. "
            "Do not invent one from the user's current selector."
        )
    return (
        "This record has no stored Practice Focus. Do not invent one from "
        "the user's current selector."
    )
