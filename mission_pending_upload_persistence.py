"""Persist and restore mission live take → Upload Analysis handoff."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from mission_pending_upload_analysis import (
    PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
    PENDING_UPLOAD_DIAG_KEY,
    SAVE_REASON_MISSION_PENDING_UPLOAD,
    audio_fingerprint,
    build_pending_upload_envelope,
    envelope_from_session_or_canonical,
    is_prepared_pending_upload,
    merge_envelope_revisions,
)
from mission_live_recording_mix import wav_duration_sec

_LAST_DRY_UPLOAD_FP_KEY = "_mission_pending_dry_upload_fp"


def _persist_audio_asset(
    session: dict[str, Any],
    audio: bytes,
    *,
    filename: str,
    st: Any | None = None,
    suffix: str = "dry",
) -> dict[str, Any]:
    fp = audio_fingerprint(audio)
    take_id = str(session.get("_mission_pending_take_id") or uuid.uuid4())
    session["_mission_pending_take_id"] = take_id
    cache_key = f"{suffix}:{fp}"
    if suffix == "dry" and session.get(_LAST_DRY_UPLOAD_FP_KEY) == fp:
        env = envelope_from_session_or_canonical(session)
        prior = (env or {}).get("dry_audio") if isinstance(env, dict) else None
        if isinstance(prior, dict) and prior.get("fingerprint") == fp and (
            prior.get("storage_ref") or prior.get("local_path")
        ):
            return prior
    try:
        from media_storage import persist_recording_audio

        store = persist_recording_audio(
            st,
            take_id if suffix == "dry" else f"{take_id}-{suffix}",
            audio,
            filename=filename,
            mime_type="audio/wav",
        )
    except ImportError:
        store = {"ok": False, "playback_status": "metadata_only"}
    asset = {
        "recording_id": take_id if suffix == "dry" else f"{take_id}-{suffix}",
        "fingerprint": fp,
        "storage_ref": store.get("storage_ref"),
        "local_path": store.get("local_path"),
        "mime_type": "audio/wav",
        "byte_size": len(audio),
        "duration_sec": round(wav_duration_sec(audio), 3),
        "playback_status": store.get("playback_status"),
        "label": "Performance Only (dry)" if suffix == "dry" else "Performance + Backing (preview)",
    }
    if suffix == "dry":
        session[_LAST_DRY_UPLOAD_FP_KEY] = fp
    return asset


def persist_mission_pending_upload_handoff(
    session: dict[str, Any],
    *,
    dry_bytes: bytes,
    mixed_bytes: bytes | None = None,
    filename: str = "mission_live_take.wav",
    st: Any | None = None,
) -> dict[str, Any]:
    """Write envelope + audio refs and sync creative workspace (metadata only in JSON)."""
    dry_asset = _persist_audio_asset(session, bytes(dry_bytes), filename=filename, st=st, suffix="dry")
    mixed_asset = None
    if mixed_bytes and mixed_bytes != dry_bytes:
        mixed_asset = _persist_audio_asset(
            session,
            bytes(mixed_bytes),
            filename="mission_live_mixed_preview.wav",
            st=st,
            suffix="mixed",
        )
    incoming = build_pending_upload_envelope(session, dry_asset=dry_asset, mixed_asset=mixed_asset)
    existing = envelope_from_session_or_canonical(session)
    merged, accepted = merge_envelope_revisions(existing, incoming)
    diag: dict[str, Any] = {
        "accepted": accepted,
        "take_id": merged.get("take_id"),
        "handoff_revision": merged.get("handoff_revision"),
        "dry_fingerprint": (merged.get("dry_audio") or {}).get("fingerprint"),
        "mixed_fingerprint": (merged.get("mixed_preview_audio") or {}).get("fingerprint"),
        "persistence_write": "pending",
    }
    if not accepted:
        diag["persistence_write"] = "rejected_stale"
        session[PENDING_UPLOAD_DIAG_KEY] = diag
        return diag
    session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = copy.deepcopy(merged)
    try:
        from creative_workspace_state_persistence import (
            gather_creative_workspace_from_session,
            write_canonical_creative_workspace,
        )
        from mission_pending_upload_analysis import SAVE_REASON_MISSION_PENDING_UPLOAD

        blob = gather_creative_workspace_from_session(session)
        blob[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = copy.deepcopy(merged)
        write_canonical_creative_workspace(session, blob, reason=SAVE_REASON_MISSION_PENDING_UPLOAD)
    except ImportError:
        pass
    try:
        from pending_upload_route_precedence import commit_pending_upload_navigation_handoff

        commit_pending_upload_navigation_handoff(session, st=None, persist_save=False)
    except ImportError:
        pass
    if st is not None:
        try:
            from music_persistent_state import force_save_music_state

            ok = force_save_music_state(st, reason=SAVE_REASON_MISSION_PENDING_UPLOAD)
            cloud_ok = bool(st.session_state.get("_suite_persist_last_save_cloud"))
            diag["persistence_write"] = "ok" if ok and cloud_ok else f"save_error:cloud={cloud_ok}"
            diag["cloud_confirmed"] = cloud_ok
            diag["workspace_revision"] = st.session_state.get("_suite_last_persisted_revision")
        except Exception as exc:
            diag["persistence_write"] = f"save_error:{type(exc).__name__}"
            diag["cloud_confirmed"] = False
    else:
        diag["persistence_write"] = "session_only"
        diag["cloud_confirmed"] = False
    session[PENDING_UPLOAD_DIAG_KEY] = diag
    return diag


def _load_asset_bytes(asset: dict[str, Any], *, st: Any | None = None) -> tuple[bytes | None, str]:
    if not isinstance(asset, dict):
        return None, "missing_asset"
    row = {
        "recording_id": asset.get("recording_id"),
        "local_path": asset.get("local_path"),
        "storage_ref": asset.get("storage_ref"),
        "filename": "mission_live_take.wav",
        "mime_type": asset.get("mime_type") or "audio/wav",
        "workspace_id": asset.get("workspace_id"),
    }
    try:
        from media_storage import load_recording_audio

        return load_recording_audio(row, st=st)
    except ImportError:
        return None, "media_storage_unavailable"


def apply_pending_upload_envelope_to_session(
    session: dict[str, Any],
    *,
    st: Any | None = None,
    source: str = "envelope",
) -> dict[str, Any]:
    """Hydrate Upload Analysis session from pending envelope (no AI run)."""
    env = envelope_from_session_or_canonical(session)
    diag: dict[str, Any] = {"restored": False, "restored_source": source, "hydrate": "none"}
    if not env or str(env.get("analysis_status") or "") != "prepared":
        session[PENDING_UPLOAD_DIAG_KEY] = diag
        return diag
    dry = env.get("dry_audio") if isinstance(env.get("dry_audio"), dict) else {}
    dry_bytes, err = _load_asset_bytes(dry, st=st)
    if not dry_bytes:
        diag["hydrate"] = err or "dry_missing"
        session[PENDING_UPLOAD_DIAG_KEY] = diag
        return diag
    from upload_media import PreparedUpload

    prepared = PreparedUpload(bytes(dry_bytes), "mission_live_take.wav")
    session["_analysis_prepared_upload"] = prepared
    session["last_analysis_audio"] = bytes(dry_bytes)
    session["last_analysis_source_label"] = prepared.name
    session["analysis_mode"] = "Single recording"
    session["mission_upload_capture_mode"] = "live"
    session["_mission_upload_handoff_source"] = str(env.get("source") or "mission_live_recording")
    session["_mission_upload_is_live_take"] = True
    metrics = env.get("metrics") if isinstance(env.get("metrics"), dict) else {}
    if metrics.get("inherited_ai_metric_ids"):
        session["analysis_inherited_ai_metric_ids"] = list(metrics["inherited_ai_metric_ids"])
    if metrics.get("additional_take_metric_ids"):
        session["analysis_additional_take_metric_ids"] = list(metrics["additional_take_metric_ids"])
    if metrics.get("effective_metric_ids"):
        session["analysis_ai_metric_ids"] = list(metrics["effective_metric_ids"])
        session["analysis_mission_ids"] = list(metrics["effective_metric_ids"])
    crit = env.get("evaluation_criteria") if isinstance(env.get("evaluation_criteria"), dict) else {}
    if crit.get("custom_goal") is not None:
        session["analysis_custom_goal"] = str(crit.get("custom_goal") or "")
    try:
        from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY
        from mission_analysis_ui import prepare_mission_upload_from_missions, ANALYSIS_CRITERIA_LOCKED

        session[MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY] = True
        session["analysis_sync_creative_mission"] = True
        session[ANALYSIS_CRITERIA_LOCKED] = True
        prepare_mission_upload_from_missions(session)
    except ImportError:
        pass
    session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = copy.deepcopy(env)
    session["studio_page"] = "analysis"
    session["_navigate_to_studio_page"] = "analysis"
    diag.update(
        {
            "restored": True,
            "take_id": env.get("take_id"),
            "handoff_revision": env.get("handoff_revision"),
            "dry_fingerprint": dry.get("fingerprint"),
            "mixed_fingerprint": (env.get("mixed_preview_audio") or {}).get("fingerprint"),
            "hydrate": "ok",
            "active_destination_page": env.get("active_destination_page"),
        }
    )
    session[PENDING_UPLOAD_DIAG_KEY] = diag
    return diag


def try_restore_pending_mission_upload_on_startup(session: dict[str, Any], *, st: Any | None = None) -> dict[str, Any]:
    if not is_prepared_pending_upload(session):
        return {"restored": False, "reason": "no_envelope"}
    if str(session.get("studio_page") or "").strip().lower() == "analysis":
        return apply_pending_upload_envelope_to_session(session, st=st, source="startup_analysis_page")
    if session.get("_pending_upload_restore_attempted"):
        return {"restored": False, "reason": "already_attempted"}
    session["_pending_upload_restore_attempted"] = True
    return apply_pending_upload_envelope_to_session(session, st=st, source="startup")


def clear_prepared_mission_upload(session: dict[str, Any], *, st: Any | None = None) -> None:
    session.pop(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, None)
    session.pop("_analysis_prepared_upload", None)
    session.pop("last_analysis_audio", None)
    session.pop(_LAST_DRY_UPLOAD_FP_KEY, None)
    session.pop("_mission_pending_take_id", None)
    session.pop("_pending_upload_user_left_analysis", None)
    session.pop("_pending_upload_suppresses_mission_backing", None)
    try:
        from pending_upload_route_precedence import PENDING_UPLOAD_ROUTE_LOCK_KEY

        session.pop(PENDING_UPLOAD_ROUTE_LOCK_KEY, None)
    except ImportError:
        session.pop("_pending_upload_route_lock", None)
    try:
        from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY

        session.pop(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY, None)
    except ImportError:
        pass
    cws = session.get("creative_workspace_state")
    if isinstance(cws, dict):
        cws.pop(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, None)
    if st is not None:
        try:
            from music_persistent_state import force_save_music_state

            force_save_music_state(st, reason="mission_pending_upload_cleared")
        except Exception:
            pass
    session[PENDING_UPLOAD_DIAG_KEY] = {"cleared": True}


def render_pending_upload_dev_diagnostics(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    env = envelope_from_session_or_canonical(session) or {}
    diag = dict(session.get(PENDING_UPLOAD_DIAG_KEY) or {})
    nav = env.get("navigation") if isinstance(env.get("navigation"), dict) else {}
    route = {}
    cws = session.get("creative_workspace_state")
    if isinstance(cws, dict) and env.get("take_id"):
        route["cloud_envelope"] = True
    else:
        route["cloud_envelope"] = bool(env.get("take_id"))
    route["destination"] = nav.get("studio_page") or env.get("active_destination_page")
    route["route_lock_durable"] = bool(nav.get("route_lock"))
    route["revision"] = diag.get("workspace_revision") or env.get("handoff_revision")
    try:
        from pending_upload_route_precedence import (
            PENDING_UPLOAD_ROUTE_LOCK_KEY,
            PENDING_UPLOAD_ROUTE_DIAG_KEY,
            durable_pending_upload_route_active,
        )

        route_diag = session.get(PENDING_UPLOAD_ROUTE_DIAG_KEY) or {}
        route["final_owner"] = route_diag.get("winning_route_reason") or "—"
        route["lock_session"] = bool(session.get(PENDING_UPLOAD_ROUTE_LOCK_KEY))
        route["lock_durable"] = durable_pending_upload_route_active(
            session, session.get("_suite_last_cloud_fetch_payload")
        )
    except ImportError:
        pass
    deploy = str(session.get("_studio_ui_release_sha") or "—")
    st_module.caption(
        f"DEV pending upload · take `{env.get('take_id', '—')}` · "
        f"rev `{route.get('revision', '—')}` · "
        f"envelope `{route.get('cloud_envelope')}` · "
        f"dest `{route.get('destination', '—')}` · "
        f"lock durable `{route.get('lock_durable')}` · "
        f"hydrate `{diag.get('hydrate', '—')}` · "
        f"owner `{route.get('final_owner', '—')}` · "
        f"write `{diag.get('persistence_write', '—')}` · "
        f"sha `{deploy[:7] if deploy else '—'}`"
    )
