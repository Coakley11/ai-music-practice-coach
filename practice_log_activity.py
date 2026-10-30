"""Practice Log facts belong to the saved entry, never the active Music setup."""
from __future__ import annotations
from typing import Any


def report_practice_log_saved(st: Any, entry: dict) -> bool:
    try:
        from suite_activity_client import record_activity
        from music_resume_payload import _resolve_workspace_id
        pick = str(entry.get("source_id") or entry.get("song_id") or "")
        source = ("composition" if pick.startswith(("composition::", "composition\x1f")) else
                  "custom" if pick.startswith(("custom::", "custom\x1f")) else
                  "catalog" if pick else "")
        explicit_source = str(entry.get("source_type") or "")
        if pick and explicit_source in {"catalog", "custom", "composition"}:
            source = explicit_source
        title = str(entry.get("active_song") or entry.get("song") or "Practice session")
        metrics = dict(song=title, instrument=str(entry.get("instrument") or ""),
                       practice_log_id=str(entry.get("session_id") or ""),
                       workflow_type="practice_log", source_type=source, source_id=pick,
                       pick_key=pick, artist=str(entry.get("artist") or "") if pick else "",
                       display_key=str(entry.get("practice_concert_key") or entry.get("display_key") or ""),
                       minutes=int(entry.get("duration_minutes") or entry.get("minutes") or 0),
                       focus=str(entry.get("focus_area") or entry.get("focus") or ""),
                       workspace_id=_resolve_workspace_id(st=st, session=st.session_state))
        # A log milestone has no local Music Resume workflow. Do not publish a
        # song resume item or a current-state snapshot carrying unrelated globals.
        record_activity("music", "practice_log_saved", page="Practice Log",
                        metrics=metrics, summary=f"Logged practice: {title}")
        return True
    except Exception:
        return False
