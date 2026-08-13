"""Read-only Practice Log summary for coach personalization — no writes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from music_coach_ami.types import CoachContext


@dataclass(frozen=True)
class PracticeHistorySnapshot:
    available: bool = False
    session_count: int = 0
    window_days: int = 0
    unresolved_next_step: str = ""
    recurring_difficulty: str = ""
    last_song: str = ""
    last_section: str = ""
    last_focus: str = ""
    recent_focus_areas: tuple[str, ...] = ()
    recent_songs: tuple[str, ...] = ()
    signals_used: tuple[str, ...] = ()


def _clean(text: Any) -> str:
    return str(text or "").strip()


def _extract_section_hint(text: str) -> str:
    low = str(text or "").lower()
    for sec in ("bridge", "chorus", "verse", "pre-chorus", "intro", "outro", "solo"):
        if sec in low:
            return sec.title() if sec != "pre-chorus" else "Pre-Chorus"
    return ""


def build_practice_history_snapshot(
    practice_log_summary: dict[str, Any] | None,
) -> PracticeHistorySnapshot:
    summary = practice_log_summary if isinstance(practice_log_summary, dict) else {}
    count = int(summary.get("session_count") or summary.get("entry_count_total") or 0)
    if count <= 0 and not summary.get("last_session_summary"):
        return PracticeHistorySnapshot()

    last = summary.get("last_session_summary") if isinstance(summary.get("last_session_summary"), dict) else {}
    next_step = _clean(last.get("next_step") or summary.get("suggested_next_focus"))
    recurring = _clean(summary.get("repeated_challenge") or "")
    if not recurring:
        challenges = summary.get("repeated_challenges") or []
        if isinstance(challenges, list) and challenges:
            recurring = _clean(challenges[0])

    last_song = _clean(last.get("active_song") or summary.get("top_song"))
    last_section = _clean(last.get("section_practiced")) or _extract_section_hint(next_step)
    last_focus = _clean(last.get("focus_area") or last.get("focus") or summary.get("top_focus"))

    focus_areas = summary.get("most_common_focus_areas") or []
    songs = summary.get("most_practiced_songs") or []
    signals: list[str] = []
    if next_step:
        signals.append("unresolved_next_step")
    if recurring:
        signals.append("recurring_difficulty")
    if last_song:
        signals.append("last_song")
    if last_section:
        signals.append("last_section")
    if last_focus:
        signals.append("last_focus")

    return PracticeHistorySnapshot(
        available=True,
        session_count=count,
        window_days=int(summary.get("window_days") or 14),
        unresolved_next_step=next_step,
        recurring_difficulty=recurring,
        last_song=last_song,
        last_section=last_section,
        last_focus=last_focus,
        recent_focus_areas=tuple(_clean(x) for x in focus_areas if _clean(x))[:5],
        recent_songs=tuple(_clean(x) for x in songs if _clean(x))[:5],
        signals_used=tuple(signals),
    )


def snapshot_from_coach_context(ctx: CoachContext) -> PracticeHistorySnapshot:
    extra = ctx.extra if isinstance(ctx.extra, dict) else {}
    summary = extra.get("practice_log_summary")
    if not isinstance(summary, dict) and ctx.recent_practice_evidence:
        return PracticeHistorySnapshot(available=True, session_count=1, signals_used=("summary_evidence",))
    return build_practice_history_snapshot(summary if isinstance(summary, dict) else None)


def history_supports_focus(history: PracticeHistorySnapshot, focus: str) -> bool:
    focus_low = _clean(focus).lower()
    if not focus_low:
        return False
    if focus_low in _clean(history.recurring_difficulty).lower():
        return True
    if focus_low in _clean(history.unresolved_next_step).lower():
        return True
    if focus_low in _clean(history.last_focus).lower():
        return True
    return any(focus_low in _clean(x).lower() for x in history.recent_focus_areas)
