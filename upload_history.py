"""Upload Analysis history library — cloud-backed, workspace-scoped."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from analysis_session_persistence import analysis_result_ready, sanitize_analysis_result_for_persist
from studio_history_cloud import (
    active_workspace_id,
    decode_audio_b64,
    encode_audio_if_safe,
    json_safe,
    list_history_items,
    new_history_item_key,
    save_history_item,
)

ITEM_TYPE = "upload_history"
PAYLOAD_VERSION = 1


def scores_summary_from_result(result: dict[str, Any]) -> dict[str, Any]:
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    return {
        "coach_summary": str(result.get("coach_summary") or "")[:500],
        "overall_improv_score": result.get("overall_improv_score"),
        "timing": scores.get("timing"),
        "pitch": scores.get("pitch"),
        "technique": scores.get("technique"),
        "groove": scores.get("groove"),
        "musicality": scores.get("musicality"),
        "confidence": scores.get("confidence"),
        "tone": scores.get("tone"),
        "multitrack": bool(result.get("multitrack")),
    }


def default_upload_title(session_state: dict[str, Any]) -> str:
    label = str(session_state.get("last_analysis_source_label") or "").strip()
    if label:
        return label.rsplit(".", 1)[0][:80] or label[:80]
    result = session_state.get("last_analysis_result")
    if isinstance(result, dict):
        summary = str(result.get("coach_summary") or "").strip()
        if summary:
            return summary[:80]
    rec = str(session_state.get("analysis_recording_type") or "Practice take")
    return f"{rec} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"


def build_upload_history_payload(
    session_state: dict[str, Any],
    *,
    title: str,
    notes: str = "",
    st: Any | None = None,
) -> dict[str, Any] | None:
    raw = session_state.get("last_analysis_result")
    if not analysis_result_ready(raw):
        return None
    result = sanitize_analysis_result_for_persist(raw)
    audio = session_state.get("last_analysis_audio")
    audio_b64, audio_skip = encode_audio_if_safe(audio if isinstance(audio, (bytes, bytearray)) else None)
    source_label = str(
        session_state.get("last_analysis_source_label")
        or session_state.get("analysis_source_filename")
        or ""
    ).strip()
    recording_type = str(session_state.get("analysis_recording_type") or session_state.get("last_analysis_recording_type") or "")
    return json_safe(
        {
            "version": PAYLOAD_VERSION,
            "workspace_id": active_workspace_id(st=st),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "title": str(title or default_upload_title(session_state)).strip()[:120],
            "source_label": source_label[:200],
            "recording_type": recording_type[:80],
            "notes": str(notes or "").strip()[:2000],
            "analysis_result": result,
            "scores_summary": scores_summary_from_result(result),
            "audio_b64": audio_b64,
            "audio_skip_reason": audio_skip,
        }
    )


def save_upload_to_history(
    session_state: dict[str, Any],
    *,
    title: str,
    notes: str = "",
    st: Any | None = None,
) -> tuple[bool, str]:
    payload = build_upload_history_payload(session_state, title=title, notes=notes, st=st)
    if not payload:
        return False, ""
    item_key = new_history_item_key("upload")
    ok = save_history_item(
        item_type=ITEM_TYPE,
        item_key=item_key,
        title=str(payload.get("title") or "Upload analysis"),
        payload=payload,
    )
    return ok, item_key


def list_upload_history(*, st: Any | None = None, limit: int = 40) -> list[dict[str, Any]]:
    return list_history_items(item_type=ITEM_TYPE, st=st, limit=limit)


def apply_upload_history(session_state: dict[str, Any], payload: dict[str, Any]) -> bool:
    result = payload.get("analysis_result")
    if not analysis_result_ready(result):
        return False
    session_state["last_analysis_result"] = sanitize_analysis_result_for_persist(result)
    session_state["last_analysis_source_label"] = str(payload.get("source_label") or "")
    session_state["last_analysis_recording_type"] = str(payload.get("recording_type") or "")
    if payload.get("notes"):
        session_state["upload_history_loaded_notes"] = str(payload.get("notes") or "")
    audio = decode_audio_b64(payload.get("audio_b64"))
    if audio:
        session_state["last_analysis_audio"] = audio
    else:
        session_state.pop("last_analysis_audio", None)
    return True


def history_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    summary = payload.get("scores_summary") if isinstance(payload.get("scores_summary"), dict) else {}
    coach = str(summary.get("coach_summary") or row.get("title") or "Upload analysis")
    source = str(payload.get("source_label") or "").strip()
    if source:
        return f"{coach[:100]} · {source[:40]}"
    return coach[:120]
