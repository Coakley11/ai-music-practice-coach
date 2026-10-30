"""Detached, allowlisted recording ownership for activity and review facts."""
from __future__ import annotations
from typing import Any
from uuid import uuid4


def capture_upload(session: Any, *, filename: str = "") -> dict:
    from recording_analysis_context import build_analysis_context_snapshot
    snapshot = build_analysis_context_snapshot(session)
    source_label = str(snapshot.get("song_source_type") or "").lower()
    source = ("composition" if "composed" in source_label else "custom" if "custom" in source_label
              else "catalog" if "catalog" in source_label else "")
    instruments = snapshot.get("instruments") or []
    context = dict(recording_id=uuid4().hex,
                   source_type=source, source_id=str(snapshot.get("song_source_id") or ""),
                   song=str(snapshot.get("song_source_name") or "Recording"),
                   artist=str(snapshot.get("song_artist") or ""),
                   instrument=", ".join(str(i) for i in instruments),
                   display_key=str(snapshot.get("recording_concert_key") or snapshot.get("display_key") or ""),
                   workflow_type="recording", filename=filename)
    session["_activity_recording_context"] = dict(context)
    return context


def report_recording_fact(st: Any, event: str, context: dict, *, page: str, media_type: str = "") -> bool:
    try:
        from suite_activity_client import record_activity
        from music_resume_payload import _resolve_workspace_id
        safe = {k: context.get(k, "") for k in ("recording_id", "source_type", "source_id",
            "song", "artist", "instrument", "display_key", "workflow_type", "filename")}
        safe.update(workspace_id=_resolve_workspace_id(st=st, session=st.session_state),
                    review_status="reviewed" if event == "recording_reviewed" else "not_reviewed",
                    media_type=media_type)
        record_activity("music", event, page=page, metrics=safe,
                        summary=("Reviewed recording for " if event == "recording_reviewed" else
                                 "Uploaded recording for ") + str(safe["song"]))
        return True
    except Exception:
        return False
