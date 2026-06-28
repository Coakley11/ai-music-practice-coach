"""Structured AMI payload builder for practice log analysis."""

from __future__ import annotations

from typing import Any

from practice_log_state import (
    compute_practice_log_summary,
    load_entries,
    normalize_practice_log_entries,
    PRACTICE_CONCERT_KEY_LABEL,
    WRITTEN_KEY_LABEL,
    SHAPE_KEY_LABEL,
    ORIGINAL_KEY_LABEL,
    is_guitar_instrument,
    is_transposing_log_instrument,
)


def _entry_notes(entry: dict[str, Any]) -> str:
    return str(entry.get("notes") or entry.get("practice") or "").strip()


def _entry_song(entry: dict[str, Any]) -> str:
    return str(entry.get("active_song") or entry.get("song") or "").strip()


def _entry_minutes(entry: dict[str, Any]) -> int:
    try:
        return int(entry.get("duration_minutes") or entry.get("minutes") or 0)
    except (TypeError, ValueError):
        return 0


def _compact_session(entry: dict[str, Any]) -> dict[str, Any]:
    ratings = entry.get("ratings") if isinstance(entry.get("ratings"), dict) else {}
    instrument = str(entry.get("instrument") or "")
    out: dict[str, Any] = {
        "session_id": entry.get("session_id"),
        "date": entry.get("date"),
        "duration_minutes": _entry_minutes(entry),
        "instrument": entry.get("instrument"),
        "active_song": _entry_song(entry),
        "song_id": entry.get("song_id"),
        "original_key": entry.get("original_key"),
        "original_key_label": ORIGINAL_KEY_LABEL,
        "practice_concert_key": entry.get("practice_concert_key") or entry.get("display_key"),
        "practice_concert_key_label": PRACTICE_CONCERT_KEY_LABEL,
        "display_key": entry.get("display_key"),
        "display_key_label": PRACTICE_CONCERT_KEY_LABEL,
        "bpm": entry.get("bpm"),
        "section_practiced": entry.get("section_practiced"),
        "focus_area": entry.get("focus_area") or entry.get("focus"),
        "practice_type": entry.get("practice_type") or entry.get("mode"),
        "notes": _entry_notes(entry),
        "what_went_well": entry.get("what_went_well"),
        "what_was_hard": entry.get("what_was_hard"),
        "next_step": entry.get("next_step"),
        "ratings": ratings,
        "tags": entry.get("tags") or [],
        "source_page": entry.get("source_page"),
    }
    shape = str(entry.get("guitar_shape_key") or "").strip()
    if shape or is_guitar_instrument(instrument):
        out["guitar_shape_key"] = shape or entry.get("guitar_shape_key")
        out["shape_key_label"] = SHAPE_KEY_LABEL
    written = str(entry.get("written_key") or "").strip()
    if written and is_transposing_log_instrument(instrument):
        out["written_key"] = written
        out["written_key_label"] = WRITTEN_KEY_LABEL
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def _build_trends(entries: list[dict[str, Any]], *, window_days: int) -> dict[str, Any]:
    try:
        from practice_log_insights import _aggregate_log_stats, _score_trends, generate_practice_log_insights
        from practice_log_insights import load_analysis_history

        stats = _aggregate_log_stats(entries)
        analysis = load_analysis_history()
        insights = generate_practice_log_insights(entries, analysis_history=analysis)
        score_trends = _score_trends(analysis)
        return {
            "stats": {
                "total": stats.get("total", 0),
                "last_14_count": stats.get("last_14_count", 0),
                "avg_rating": stats.get("avg_rating"),
            },
            "patterns_detected": insights.patterns_detected[:6],
            "weak_areas": insights.weak_areas[:6],
            "recommended_practice": insights.recommended_practice[:6],
            "long_term_trends": insights.long_term_trends[:4],
            "recording_score_trends": score_trends,
        }
    except Exception:
        return {}


def _active_song_context(session_state: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_ami_context import gather_practice_ami_snapshot

        return gather_practice_ami_snapshot(session_state, include_practice_logs=False)
    except TypeError:
        try:
            from music_ami_context import gather_practice_ami_snapshot

            return gather_practice_ami_snapshot(session_state)
        except Exception:
            return {}
    except Exception:
        return {}


def _recording_analysis_context() -> list[dict[str, Any]]:
    try:
        from practice_log_insights import load_analysis_history

        rows = load_analysis_history()
        out: list[dict[str, Any]] = []
        for row in rows[-8:]:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "date": row.get("date"),
                    "song": row.get("song"),
                    "instrument": row.get("instrument"),
                    "weakest_category": row.get("weakest_category"),
                    "strongest_category": row.get("strongest_category"),
                    "next_focus": row.get("next_focus"),
                    "coach_summary": str(row.get("coach_summary") or "")[:240],
                }
            )
        return out
    except Exception:
        return []


def build_practice_log_ami_payload(
    session_state: dict[str, Any],
    entries: list[dict[str, Any]] | None = None,
    *,
    window_days: int = 14,
) -> dict[str, Any]:
    """Build structured practice history payload for AMI / Command Center."""
    if entries is None:
        entries = load_entries(session_state)
    else:
        entries = normalize_practice_log_entries(entries)

    summary = compute_practice_log_summary(entries, window_days=window_days)
    window_entries = entries
    if window_days > 0:
        from practice_log_state import filter_practice_log_entries

        window_entries = filter_practice_log_entries(entries, {"window_days": window_days})

    last = window_entries[0] if window_entries else (entries[0] if entries else {})
    repeated = summary.get("repeated_challenges") or []
    if not repeated:
        from collections import Counter

        hard = Counter(
            str(e.get("what_was_hard") or "").strip().lower()
            for e in window_entries
            if str(e.get("what_was_hard") or "").strip()
        )
        repeated = [c for c, _ in hard.most_common(5)]

    practice_log_summary = {
        "window_days": window_days,
        "session_count": summary.get("session_count", 0),
        "total_minutes": summary.get("total_minutes", 0),
        "sessions_this_week": summary.get("sessions_this_week", 0),
        "minutes_this_week": summary.get("minutes_this_week", 0),
        "most_practiced_songs": summary.get("most_practiced_songs") or [],
        "most_common_focus_areas": summary.get("most_common_focus_areas") or [],
        "repeated_challenges": repeated,
        "suggested_next_focus": summary.get("suggested_next_focus") or "",
        "last_session_summary": _compact_session(last) if last else {},
        "trends": _build_trends(entries, window_days=window_days),
    }

    return {
        "practice_log_summary": practice_log_summary,
        "recent_sessions": [_compact_session(e) for e in window_entries[:30]],
        "active_song_context": _active_song_context(session_state),
        "recording_analysis_context": _recording_analysis_context(),
        "user_request": "analyze_practice",
    }
