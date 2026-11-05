"""The "Recent practice" card on Home - verified saved history only.

Saved Practice Log rows and versioned Music practice-context events provide the
history. Events describe recorded practice starts, not necessarily completed
sessions. Artist and keys come only from the historical record.

What this module deliberately does **not** do is build a card out of live session
state. The song currently loaded in the workspace is simply the song that is
loaded; it is not evidence that a previous session happened, and presenting it as
"where you left off" would be a guess dressed as a fact. With no saved entry,
:func:`verified_recent_session` returns ``None`` and Home shows its empty state.

Complete records may offer an explicit historical Resume through
``home_practice_resume``. Incomplete records keep navigation-only wording.
The historical metadata itself is never inferred from current live state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: Practice-log ``practice_type`` -> the studio page that work belongs to.
#: Inverse of ``practice_log_state._STUDIO_PAGE_TO_PRACTICE_TYPE``, collapsed to
#: one page per type. Anything unrecognised falls back to Practice.
_TYPE_TO_PAGE: dict[str, str] = {
    "song practice": "practice",
    "backing track": "backing",
    "custom progression": "custom",
    "karaoke/performance": "practice",
    "multitrack/upload": "multitrack",
    "composition practice": "composer",
    "mission practice": "creative",
    "song-aware coaching": "creative",
    "upload analysis": "analysis",
}

#: Practice types that additionally select a Creative Lab workspace.
_TYPE_TO_CREATIVE_DEST: dict[str, str] = {
    "mission practice": "creative::Missions",
    "song-aware coaching": "creative::SBI",
}

#: What to call each destination on the button, so the action names where it goes.
_PAGE_LABEL: dict[str, str] = {
    "practice": "Practice",
    "backing": "Backing",
    "custom": "Custom Progressions",
    "multitrack": "Multitrack",
    "composer": "Composition",
    "creative": "Creative Lab",
    "analysis": "Upload Analysis",
}


@dataclass(frozen=True)
class VerifiedRecentSession:
    """A practice session that is on record, not inferred."""

    session_id: str
    song_title: str
    instrument: str
    practice_type: str
    focus_area: str
    page: str
    artist: str = ""
    creative_dest: str = ""
    when_label: str = ""
    #: ("Practice/Concert key", "F minor"), ("Written key", "G minor"), ...
    key_parts: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    duration_minutes: int = 0
    section_label: str = ""
    restore_record: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def verified(self) -> bool:
        return True

    def key_summary(self) -> str:
        return " · ".join(f"{label}: {value}" for label, value in self.key_parts)

    def destination_label(self) -> str:
        """Where the button goes, by name - Home never promises more than it does."""
        if self.creative_dest == "creative::Missions":
            return "Missions"
        if self.creative_dest == "creative::SBI":
            return "Song-Aware Coaching"
        return _PAGE_LABEL.get(self.page, "Practice")

    def action_label(self) -> str:
        return f"Go to {self.destination_label()}"


def _relative_day_label(iso_date: str, *, today: date | None = None) -> str:
    try:
        when = date.fromisoformat(str(iso_date or "").strip())
    except ValueError:
        return ""
    from datetime import datetime
    from activity_time import DISPLAY_TIMEZONE
    now = today or datetime.now(DISPLAY_TIMEZONE).date()
    delta = (now - when).days
    if delta <= 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 7:
        return f"{delta} days ago"
    if delta < 14:
        return "Last week"
    return when.strftime("%d %b %Y").lstrip("0")


def _entry_key_parts(entry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Concert / written / shape / original keys, labelled by the Practice Log itself."""
    try:
        from practice_log_state import entry_key_display_parts
    except ImportError:
        concert = str(entry.get("practice_concert_key") or entry.get("display_key") or "").strip()
        return (("Practice/Concert key", concert),) if concert else ()
    return tuple(
        (str(label), str(value))
        for label, value in entry_key_display_parts(entry)
        if str(value).strip() and str(value).strip() != "—"
    )


def session_from_entry(
    entry: dict[str, Any],
    *,
    today: date | None = None,
) -> VerifiedRecentSession | None:
    """Build the card from one saved Practice Log entry, or None if it is unusable."""
    if not isinstance(entry, dict):
        return None
    session_id = str(entry.get("session_id") or "").strip()
    if not session_id or entry.get("deleted"):
        return None

    practice_type = str(entry.get("practice_type") or "").strip().lower()
    page = _TYPE_TO_PAGE.get(practice_type, "practice")
    song = str(entry.get("active_song") or "").strip()

    duration = entry.get("duration_minutes")
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 0

    section = str(entry.get("section_name") or "").strip()
    if not section:
        raw = str(entry.get("section_practiced") or "").strip()
        section = "" if raw in {"", "whole song"} else raw

    return VerifiedRecentSession(
        session_id=session_id,
        song_title=song,
        artist=str(entry.get("artist") or "").strip(),
        instrument=str(entry.get("instrument") or "").strip(),
        practice_type=practice_type,
        focus_area=str(entry.get("focus_area") or "").strip(),
        page=page,
        creative_dest=_TYPE_TO_CREATIVE_DEST.get(practice_type, ""),
        when_label=_relative_day_label(entry.get("date"), today=today),
        key_parts=_entry_key_parts(entry),
        duration_minutes=max(duration, 0),
        section_label=section,
        restore_record=dict(entry),
    )


def verified_recent_session(
    session_state: Any,
    *,
    entries: list[dict[str, Any]] | None = None,
    activities: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> VerifiedRecentSession | None:
    """Newest recorded practice from this workspace, or None.

    ``entries`` is for tests. In the app the rows come from
    ``practice_log_state.load_entries``, which is already workspace-scoped,
    tombstone-filtered and sorted newest-first.
    """
    rows = entries
    if rows is None:
        try:
            from practice_log_state import load_entries

            rows = load_entries(session_state)
        except Exception:
            rows = []

    from home_activity_history import load_practice_events, practice_entry_from_event
    from activity_time import parse_activity_timestamp
    from datetime import datetime, timezone, time
    events = activities if activities is not None else (
        load_practice_events(session_state) if entries is None else []
    )
    candidates = list(rows or []) + [entry for event in events
                                    if (entry := practice_entry_from_event(event)) is not None]

    def recorded_time(entry):
        # Practice date wins over a later edit; within that date use creation time.
        day = str(entry.get("date") or "")
        stamp = parse_activity_timestamp(entry.get("created_at"))
        if stamp:
            from activity_time import to_display_local
            if to_display_local(stamp).date().isoformat() == day:
                return stamp
        try:
            from activity_time import DISPLAY_TIMEZONE
            return datetime.combine(date.fromisoformat(day), time.min, tzinfo=DISPLAY_TIMEZONE)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    for entry in sorted((e for e in candidates if isinstance(e, dict)), key=recorded_time, reverse=True):
        if entry.get('workspace_id'):
            from music_resume_payload import _resolve_workspace_id, payload_workspace_matches
            if not payload_workspace_matches(entry, _resolve_workspace_id(session=session_state)):
                continue
        built = session_from_entry(entry, today=today)
        if built is not None:
            return built
    return None


#: The section heading. "Recent Practice" reports what the Practice Log holds; it
#: does not promise to put the workspace back the way it was, because this slice
#: does not restore the song, the instrument or the keys.
SECTION_EYEBROW = "Recent practice"

#: Shown when nothing is on record. Honest about why, and offers a way forward.
EMPTY_STATE_TITLE = "Every great session starts somewhere."
EMPTY_STATE_BODY = (
    "No saved practice session yet. Once you log a session in the Practice Log, "
    "it will show up here. Recorded practice activity can appear here too."
)

#: Printed under the button so the action cannot be mistaken for a restore.
ACTION_CAPTION = (
    "Opens {destination}. Your current song, instrument and keys stay exactly as "
    "they are — this does not reload the song from that session."
)


__all__ = (
    "VerifiedRecentSession",
    "verified_recent_session",
    "session_from_entry",
    "SECTION_EYEBROW",
    "EMPTY_STATE_TITLE",
    "EMPTY_STATE_BODY",
    "ACTION_CAPTION",
)
