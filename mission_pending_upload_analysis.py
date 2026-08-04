"""Authoritative pending Upload Analysis envelope (mission live take handoff)."""

from __future__ import annotations

import copy
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY = "pending_upload_analysis_envelope"
PENDING_UPLOAD_SCHEMA_VERSION = 1
PENDING_UPLOAD_DIAG_KEY = "_pending_upload_analysis_diag"

SAVE_REASON_MISSION_PENDING_UPLOAD = "mission_pending_upload_handoff"


def audio_fingerprint(audio: bytes) -> str:
    if not audio:
        return ""
    return hashlib.sha256(audio).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mission_identity_from_session(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from mission_practice_context import ensure_mission_practice_context, authoritative_mission_type

        ctx = ensure_mission_practice_context(session)
        mission = authoritative_mission_type(session) or (ctx.mission_type if ctx else "")
        chord = ctx.chord if ctx else None
        return {
            "mission_type": mission,
            "chord_symbol": chord.symbol if chord else str(session.get("ii_selected_chord") or ""),
            "chord_root": chord.root if chord else "",
            "chord_quality": chord.quality if chord else "",
            "chord_extensions": chord.extensions if chord else "",
            "chord_slash_bass": chord.bass if chord else "",
            "section": chord.section if chord else str(session.get("ii_selected_section") or ""),
            "chord_index": int(chord.chord_index if chord else session.get("ii_selected_chord_index") or 0),
        }
    except ImportError:
        return {
            "mission_type": str(session.get("improv_active_mission") or ""),
            "chord_symbol": str(session.get("ii_selected_chord") or ""),
            "section": str(session.get("ii_selected_section") or ""),
            "chord_index": int(session.get("ii_selected_chord_index") or 0),
        }


def _metrics_from_session(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from mission_upload_metrics import (
            ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY,
            ANALYSIS_EFFECTIVE_METRIC_IDS_KEY,
            ANALYSIS_INHERITED_AI_METRIC_IDS_KEY,
        )
    except ImportError:
        ANALYSIS_INHERITED_AI_METRIC_IDS_KEY = "analysis_inherited_ai_metric_ids"
        ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY = "analysis_additional_take_metric_ids"
        ANALYSIS_EFFECTIVE_METRIC_IDS_KEY = "analysis_effective_metric_ids"
    return {
        "inherited_ai_metric_ids": list(session.get(ANALYSIS_INHERITED_AI_METRIC_IDS_KEY) or []),
        "additional_take_metric_ids": list(session.get(ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY) or []),
        "effective_metric_ids": list(session.get(ANALYSIS_EFFECTIVE_METRIC_IDS_KEY) or session.get("analysis_ai_metric_ids") or []),
    }


def build_pending_upload_envelope(
    session: dict[str, Any],
    *,
    dry_asset: dict[str, Any],
    mixed_asset: dict[str, Any] | None = None,
    handoff_revision: int | None = None,
) -> dict[str, Any]:
    rev = int(handoff_revision if handoff_revision is not None else session.get("_pending_upload_handoff_revision") or 0)
    if rev <= 0:
        try:
            from workspace_revision import workspace_revision_from_blob

            rev = int(workspace_revision_from_blob(session.get("creative_workspace_state") or session) or 0)
        except ImportError:
            rev = 1
    seal = copy.deepcopy(session.get("improv_mission_recording_seal") or {})
    criteria = {
        "custom_goal": str(session.get("analysis_custom_goal") or ""),
        "analysis_recording_type": str(session.get("analysis_recording_type") or "Practice take"),
    }
    return {
        "schema_version": PENDING_UPLOAD_SCHEMA_VERSION,
        "take_id": str(dry_asset.get("recording_id") or uuid.uuid4()),
        "handoff_revision": rev,
        "analysis_status": "prepared",
        "active_destination_page": "analysis",
        "navigation": {
            "studio_page": "analysis",
            "workflow_owner": "pending_mission_upload_analysis",
        "resume_upload_analysis": True,
        "mission_jam_route_suppressed": True,
        "route_lock": True,
        "destination_workflow": "pending_mission_upload_analysis",
    },
        "source": "mission_live_recording",
        "capture_timestamp": _utc_now(),
        "recording_seal": seal,
        "mission": _mission_identity_from_session(session),
        "dry_audio": dry_asset,
        "mixed_preview_audio": mixed_asset,
        "metrics": _metrics_from_session(session),
        "evaluation_criteria": criteria,
    }


def envelope_from_session_or_canonical(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY)
    if isinstance(raw, dict) and raw.get("take_id"):
        return raw
    cws = session.get("creative_workspace_state")
    if isinstance(cws, dict):
        blob = cws.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY)
        if isinstance(blob, dict) and blob.get("take_id"):
            return blob
    return None


def is_prepared_pending_upload(session: dict[str, Any]) -> bool:
    env = envelope_from_session_or_canonical(session)
    return bool(env and str(env.get("analysis_status") or "") == "prepared")


def merge_envelope_revisions(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return (envelope, accepted). Reject stale incoming vs existing."""
    if not existing or not existing.get("take_id"):
        return incoming, True
    old_rev = int(existing.get("handoff_revision") or 0)
    new_rev = int(incoming.get("handoff_revision") or 0)
    if new_rev < old_rev:
        return existing, False
    if new_rev == old_rev and existing.get("take_id") == incoming.get("take_id"):
        old_fp = (existing.get("dry_audio") or {}).get("fingerprint")
        new_fp = (incoming.get("dry_audio") or {}).get("fingerprint")
        if old_fp and new_fp == old_fp:
            return existing, True
    return incoming, True
