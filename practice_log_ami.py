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
        "focus_area": entry.get("focus_area"),
        "practice_type": entry.get("practice_type") or entry.get("mode"),
        "notes": _entry_notes(entry),
        "what_went_well": entry.get("what_went_well"),
        "what_was_hard": entry.get("what_was_hard"),
        "next_step": entry.get("next_step"),
        "ratings": ratings,
        "tags": entry.get("tags") or [],
        "source_page": entry.get("source_page"),
    }
    try:
        from practice_focus_history import compact_focus_fields_for_ami

        out.update(compact_focus_fields_for_ami(entry))
    except ImportError:
        if entry.get("focus") or entry.get("practice_focus"):
            out["practice_focus"] = entry.get("practice_focus") or entry.get("focus")
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


def _recording_analysis_context_from_summary(upload_summary: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in upload_summary.get("recent_analyses") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "date": row.get("created_at"),
                "song": row.get("song_title") or row.get("song"),
                "instrument": row.get("instrument"),
                "weakest_category": row.get("weakest_category"),
                "strongest_category": row.get("strongest_category"),
                "next_focus": (row.get("improvement_suggestions") or [None])[0],
                "coach_summary": str(row.get("coach_summary") or "")[:240],
                "source": row.get("source"),
                "recording_type": row.get("recording_type"),
            }
        )
    if out:
        return out[:8]
    try:
        from practice_log_insights import load_analysis_history

        legacy: list[dict[str, Any]] = []
        for row in load_analysis_history()[-8:]:
            if not isinstance(row, dict):
                continue
            legacy.append(
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
        return legacy
    except Exception:
        return []


def build_practice_log_ami_payload(
    session_state: dict[str, Any],
    entries: list[dict[str, Any]] | None = None,
    *,
    window_days: int = 14,
    st: Any | None = None,
) -> dict[str, Any]:
    """Build structured practice history payload for AMI / Command Center."""
    from practice_history_synthesis import build_practice_history_ami_payload

    synthesized = build_practice_history_ami_payload(
        session_state,
        entries=entries,
        window_days=window_days,
        st=st,
    )

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

    pl_block = dict(synthesized.get("practice_log_summary") or {})
    practice_log_summary = {
        **pl_block,
        "window_days": window_days,
        "session_count": summary.get("session_count", pl_block.get("entry_count_total", 0)),
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

    upload_summary = synthesized.get("upload_analysis_summary") or {}
    tone_history = synthesized.get("tone_history_summary") or {}
    export_summary = synthesized.get("multitrack_export_summary") or {}

    result: dict[str, Any] = {
        **synthesized,
        "practice_log_summary": practice_log_summary,
        "recent_sessions": [_compact_session(e) for e in window_entries[:30]],
        "active_song_context": _active_song_context(session_state),
        "recording_analysis_context": _recording_analysis_context_from_summary(upload_summary),
        "tone_history": tone_history,
        "multitrack_exports": export_summary,
        "media_summary": {
            "upload_count": upload_summary.get("analysis_count_total", 0),
            "multitrack_count": 0,
            "multitrack_export_count": export_summary.get("export_count_total", 0),
            "tone_take_count": tone_history.get("tone_take_count_total", 0),
            "analyzed_export_count": export_summary.get("analyzed_export_count", 0),
            "window_days": max(window_days, 30),
        },
        "user_request": "analyze_practice",
    }
    # Keep historical Focus facts after summary merge
    if synthesized.get("practice_focus_history"):
        result["practice_focus_history"] = synthesized["practice_focus_history"]
    if synthesized.get("practice_focus_history_block"):
        result["practice_focus_history_block"] = synthesized["practice_focus_history_block"]
    if synthesized.get("current_practice_focus"):
        result["current_practice_focus"] = synthesized["current_practice_focus"]
        practice_log_summary["current_practice_focus"] = synthesized["current_practice_focus"]
        result["practice_log_summary"] = practice_log_summary
    from practice_history_synthesis import build_log_page_analysis_summary, build_practice_progress_report

    result["progress_report"] = build_practice_progress_report(result)
    result["log_page_summary"] = build_log_page_analysis_summary(result)
    return result
