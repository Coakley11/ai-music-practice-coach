"""The "Recent practice" card on Home - verified saved history only.

A session the musician actually finished is one that was *written down*. The
Practice Log is that record: it is persisted per workspace, it survives a reload
and a different device, and each entry already stores the keys in the three forms
that matter - the Practice/concert key, the written key for a transposing
instrument, and the guitar shape key.

What this module deliberately does **not** do is build a card out of live session
state. The song currently loaded in the workspace is simply the song that is
loaded; it is not evidence that a previous session happened, and presenting it as
"where you left off" would be a guess dressed as a fact. With no saved entry,
:func:`verified_recent_session` returns ``None`` and Home shows its empty state.

This card reports; it does not resume. It routes to the workspace that session
was recorded in, and the song, instrument and keys stay exactly as the musician
left them. The heading says "Recent practice" and the button names its
destination for that reason: nothing here should read as a promise to put the
workspace back the way it was. Genuine resume is a later slice, and it belongs
on ``music_resume_payload.apply_music_resume_payload``.
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
}

#: Practice types that additionally select a Creative Lab workspace.
_TYPE_TO_CREATIVE_DEST: dict[str, str] = {
    "mission practice": "creative::Missions",
}

#: What to call each destination on the button, so the action names where it goes.
_PAGE_LABEL: dict[str, str] = {
    "practice": "Practice",
    "backing": "Backing",
    "custom": "Custom Progressions",
    "multitrack": "Multitrack",
    "composer": "Composition",
    "creative": "Creative Lab",
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
    creative_dest: str = ""
    when_label: str = ""
    #: ("Practice/Concert key", "F minor"), ("Written key", "G minor"), ...
    key_parts: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    duration_minutes: int = 0
    section_label: str = ""

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
    now = today or date.today()
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
        instrument=str(entry.get("instrument") or "").strip(),
        practice_type=practice_type,
        focus_area=str(entry.get("focus_area") or "").strip(),
        page=page,
        creative_dest=_TYPE_TO_CREATIVE_DEST.get(practice_type, ""),
        when_label=_relative_day_label(entry.get("date"), today=today),
        key_parts=_entry_key_parts(entry),
        duration_minutes=max(duration, 0),
        section_label=section,
    )


def verified_recent_session(
    session_state: Any,
    *,
    entries: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> VerifiedRecentSession | None:
    """Newest saved Practice Log session for this workspace, or None.

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
            return None

    for entry in rows or []:
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
    "it will show up here."
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
