"""Mission Backing navigation handoff — page_change durability + restore forensics."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY

MISSION_BACKING_HANDOFF_DIAG_KEY = "_mission_backing_handoff_diag"
MISSION_BACKING_HANDOFF_ACTIVE_KEY = "_mission_backing_handoff_active"
MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY = "_mission_backing_handoff_sealed_for_page_change"
MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY = "_mission_backing_handoff_confirmed_revision"
MISSION_BACKING_HANDOFF_CONFIRMED_SNAPSHOT_KEY = "_mission_backing_handoff_confirmed_snapshot"
MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY = "_mission_backing_refresh_hydration_trace"

VIOLATION_POST_CONFIRM_OVERWRITE = "MISSION_BACKING_HANDOFF_POST_CONFIRM_OVERWRITE"
VIOLATION_HANDOFF_SAVE_REASON_NOT_PAGE_CHANGE = "HANDOFF_SAVE_REASON_NOT_PAGE_CHANGE"
VIOLATION_NETWORK_CONFIRM_MISMATCH = "HANDOFF_NETWORK_CONFIRM_MISMATCH"


def _normalize_page(session: dict[str, Any]) -> str:
    return str(session.get("studio_page") or "").strip().lower()


def _backing_subview_from_payload(payload: dict[str, Any]) -> str:
    try:
        from backing_context import BACKING_CONTEXT_KEY

        for src in (
            payload.get("session") if isinstance(payload.get("session"), dict) else {},
            payload,
        ):
            if isinstance(src, dict):
                ctx = src.get(BACKING_CONTEXT_KEY)
                if isinstance(ctx, dict) and ctx.get("source"):
                    return str(ctx.get("source") or "").strip()
    except ImportError:
        pass
    return ""


def _backing_subview_label(session: dict[str, Any]) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            return str(ctx.source or "").strip() or "unknown"
    except ImportError:
        pass
    return ""


def _studio_nav_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    nav = session.get("studio_nav_state")
    if isinstance(nav, dict):
        return copy.deepcopy(nav)
    return {}


def _backing_state_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"backing_subview": _backing_subview_label(session)}
    try:
        from backing_track_state import BACKING_STATE_KEY

        blob = session.get(BACKING_STATE_KEY)
        if isinstance(blob, dict):
            out["backing_track_state_keys"] = sorted(blob.keys())
    except ImportError:
        pass
    try:
        from backing_context import BACKING_CONTEXT_KEY

        ctx = session.get(BACKING_CONTEXT_KEY)
        if isinstance(ctx, dict):
            out["backing_context_source"] = ctx.get("source")
    except ImportError:
        pass
    return out


def _artifact_summary(blob: Any) -> dict[str, Any]:
    if not isinstance(blob, dict):
        return {"present": False}
    motif = blob.get("motif") if isinstance(blob.get("motif"), dict) else {}
    raw = json.dumps(blob, sort_keys=True, default=str)
    return {
        "present": True,
        "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        "variant": blob.get("variant") or blob.get("example_variant"),
        "mission": blob.get("mission") or blob.get("mission_title"),
        "motif_notes": motif.get("notes") if isinstance(motif, dict) else None,
    }


def _cws_key_list(payload: dict[str, Any]) -> list[str]:
    cws = payload.get("creative_workspace_state")
    if isinstance(cws, dict):
        return sorted(str(k) for k in cws.keys())
    return []


def _payload_forensics(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_page_save_pipeline_trace import payload_pages_from_state

        pages = payload_pages_from_state(payload)
    except ImportError:
        pages = {}
    env = payload.get("music_workspace_state")
    if isinstance(env, dict):
        pages.setdefault("envelope", str(env.get("studio_page") or env.get("page") or "").strip())
    cws = payload.get("creative_workspace_state")
    cws_dict = cws if isinstance(cws, dict) else {}
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = workspace_revision_from_blob(payload)
    except ImportError:
        rev = (env or {}).get("workspace_revision") if isinstance(env, dict) else None
    return {
        "payload_revision": rev,
        "page_fields": pages,
        "backing_subview": _backing_subview_from_payload(payload),
        "backing_context_source": _backing_subview_from_payload(payload),
        "improv_mission_example": _artifact_summary(cws_dict.get(MISSION_EXAMPLE_KEY)),
        "improv_mission_practice_lick": _artifact_summary(cws_dict.get(MISSION_PRACTICE_LICK_KEY)),
        "creative_workspace_state_keys": _cws_key_list(payload),
        "backing_view_state_keys": _backing_state_snapshot_from_payload(payload),
    }


def _backing_state_snapshot_from_payload(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    try:
        from backing_track_state import BACKING_STATE_KEY

        for src in (payload.get("session"), payload.get("backing_track_state"), payload):
            if isinstance(src, dict) and isinstance(src.get(BACKING_STATE_KEY), dict):
                keys = sorted(str(k) for k in src[BACKING_STATE_KEY].keys())
                break
            if isinstance(src, dict) and src is payload.get("backing_track_state"):
                keys = sorted(str(k) for k in src.keys())
    except ImportError:
        pass
    return keys


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    if isinstance(raw, dict):
        return raw
    d: dict[str, Any] = {"violations": []}
    session[MISSION_BACKING_HANDOFF_DIAG_KEY] = d
    return d


def _append_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = list(d.get("violations") or [])
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)
    d["violations"] = violations


def handoff_with_practice_lick_pending(session: dict[str, Any]) -> bool:
    d = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    return isinstance(d, dict) and bool(d.get("with_practice_lick"))


def seal_mission_backing_handoff_creative_envelope(session: dict[str, Any]) -> dict[str, Any]:
    """Merge full creative_workspace_state (Items 1–3) before Mission Backing page_change."""
    from creative_mission_artifact_persistence import (
        CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY,
        snapshot_hydrated_mission_artifacts,
    )
    from creative_workspace_state_persistence import (
        CREATIVE_WORKSPACE_STATE_KEY,
        default_creative_workspace_state,
        gather_creative_workspace_from_session,
        write_canonical_creative_workspace,
    )

    base = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    merged = copy.deepcopy(base) if isinstance(base, dict) else default_creative_workspace_state()
    user_ev = session.pop(CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY, None)
    prior_reason = session.get("_music_build_save_reason")
    session["_music_build_save_reason"] = "page_change"
    try:
        gathered = gather_creative_workspace_from_session(session)
        for key, val in gathered.items():
            merged[key] = copy.deepcopy(val)
    finally:
        if user_ev is not None:
            session[CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY] = user_ev
        if prior_reason is not None:
            session["_music_build_save_reason"] = prior_reason
        else:
            session.pop("_music_build_save_reason", None)
    write_canonical_creative_workspace(session, merged, reason="mission_backing_handoff_seal")
    snapshot_hydrated_mission_artifacts(session, source="handoff:seal_full_envelope")
    session[MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY] = True
    return merged


def arm_mission_backing_handoff_page_change(session: dict[str, Any]) -> None:
    seal_mission_backing_handoff_creative_envelope(session)
    d = _diag(session)
    d["sealed_creative_workspace_keys"] = sorted(
        (session.get("creative_workspace_state") or {}).keys()
        if isinstance(session.get("creative_workspace_state"), dict)
        else []
    )


def should_skip_creative_sync_for_handoff_page_change(session: dict[str, Any]) -> bool:
    return bool(session.get(MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY))


def clear_handoff_page_change_build_flag(session: dict[str, Any]) -> None:
    session.pop(MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY, None)


def record_handoff_final_upsert_if_active(
    session: dict[str, Any],
    *,
    state: dict[str, Any],
    save_reason: str,
) -> None:
    if not handoff_with_practice_lick_pending(session) and not session.get(
        MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY
    ):
        return
    if str(save_reason or "").strip() != "page_change":
        _append_violation(
            session,
            VIOLATION_HANDOFF_SAVE_REASON_NOT_PAGE_CHANGE,
            detail=str(save_reason or ""),
        )
        return
    d = _diag(session)
    forensics = _payload_forensics(state)
    d["final_handoff_upsert"] = {
        "workspace_key": str(session.get("_suite_cloud_workspace_key") or ""),
        "transaction_id": session.get("_music_page_change_transaction_seq"),
        "save_reason": save_reason,
        "reserved_revision": session.get("_music_last_reserved_workspace_revision"),
        **forensics,
    }
    d["save_reason"] = save_reason


def note_handoff_page_change_payload_built(session: dict[str, Any], state: dict[str, Any]) -> None:
    if not session.get(MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY):
        return
    record_handoff_final_upsert_if_active(session, state=state, save_reason="page_change")


def confirm_mission_backing_handoff_from_network(session: dict[str, Any]) -> dict[str, Any]:
    """Force network refetch — not session cache or just-built payload."""
    d = _diag(session)
    upsert = d.get("final_handoff_upsert") if isinstance(d.get("final_handoff_upsert"), dict) else {}
    expected_rev = upsert.get("payload_revision") or session.get("_music_last_confirmed_cloud_revision")
    detail: dict[str, Any] = {
        "fetch_source": None,
        "expected_revision": expected_rev,
        "fetched_revision": None,
        "workspace_key": str(session.get("_suite_cloud_workspace_key") or ""),
        "matches_upsert": False,
        "confirmed": False,
    }
    try:
        from suite_cloud_state import load_cloud_full_session

        readback, _ts = load_cloud_full_session("music", force=True)
        session["_music_last_cloud_fetch_source"] = "network"
        detail["fetch_source"] = "network"
        if not isinstance(readback, dict):
            detail["error"] = "empty_readback"
            d["authoritative_confirmation"] = detail
            _append_violation(session, VIOLATION_NETWORK_CONFIRM_MISMATCH, detail="empty_readback")
            return detail
        forensics = _payload_forensics(readback)
        detail.update(forensics)
        detail["fetched_revision"] = forensics.get("payload_revision")
        pages = forensics.get("page_fields") or {}
        page_vals = [str(v).lower() for v in pages.values() if v]
        example_ok = bool((forensics.get("improv_mission_example") or {}).get("present"))
        lick_ok = bool((forensics.get("improv_mission_practice_lick") or {}).get("present"))
        subview_ok = str(forensics.get("backing_subview") or "") == "mission"
        page_ok = page_vals and all(v == "backing" for v in page_vals)
        rev_ok = expected_rev is None or detail["fetched_revision"] == expected_rev
        upsert_pages = upsert.get("page_fields") or {}
        detail["matches_upsert"] = upsert_pages == pages and upsert.get("payload_revision") == detail[
            "fetched_revision"
        ]
        detail["confirmed"] = bool(page_ok and subview_ok and example_ok and lick_ok and rev_ok)
        d["authoritative_confirmation"] = detail
        if detail["confirmed"]:
            session[MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY] = detail["fetched_revision"]
            session[MISSION_BACKING_HANDOFF_CONFIRMED_SNAPSHOT_KEY] = {
                "page_fields": pages,
                "backing_subview": forensics.get("backing_subview"),
                "had_example": example_ok,
                "had_lick": lick_ok,
                "example_hash": (forensics.get("improv_mission_example") or {}).get("hash"),
                "lick_hash": (forensics.get("improv_mission_practice_lick") or {}).get("hash"),
            }
            d["confirmed_revision"] = detail["fetched_revision"]
            d["authoritative_refetched_page"] = pages.get("workspace") or pages.get("envelope")
            d["authoritative_refetched_backing_subview"] = forensics.get("backing_subview")
            d["practice_lick_present_in_payload"] = lick_ok
        else:
            _append_violation(
                session,
                VIOLATION_NETWORK_CONFIRM_MISMATCH,
                detail=json.dumps(
                    {
                        "page_ok": page_ok,
                        "subview_ok": subview_ok,
                        "example_ok": example_ok,
                        "lick_ok": lick_ok,
                        "rev_ok": rev_ok,
                    }
                ),
            )
    except Exception as exc:
        detail["fetch_source"] = "network_error"
        detail["error"] = str(exc)
        d["authoritative_confirmation"] = detail
        _append_violation(session, VIOLATION_NETWORK_CONFIRM_MISMATCH, detail=str(exc))
    return detail


def guard_mission_backing_handoff_post_confirm_overwrite(
    session: dict[str, Any],
    *,
    save_reason: str,
    state: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    confirmed_rev = session.get(MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY)
    if not confirmed_rev:
        return False, {}
    reason = str(save_reason or "").strip()
    if reason == "page_change":
        return False, {}
    if reason in (
        "song_edit",
        "practice_edit",
        "backing_edit",
        "display_key_change",
        "multitrack_upload",
        "multitrack_layer_save",
    ):
        return False, {}
    snap = session.get(MISSION_BACKING_HANDOFF_CONFIRMED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return False, {}
    forensics = _payload_forensics(state)
    pages = forensics.get("page_fields") or {}
    page_vals = [str(v).lower() for v in pages.values() if v]
    regresses_page = any(v == "creative" for v in page_vals) or (
        page_vals and not all(v == "backing" for v in page_vals)
    )
    drops_example = bool(snap.get("had_example")) and not (
        (forensics.get("improv_mission_example") or {}).get("present")
    )
    drops_lick = bool(snap.get("had_lick")) and not (
        (forensics.get("improv_mission_practice_lick") or {}).get("present")
    )
    if not (regresses_page or drops_example or drops_lick):
        return False, {}
    detail = {
        "later_revision": forensics.get("payload_revision"),
        "confirmed_revision": confirmed_rev,
        "reason": reason,
        "caller": "guard_mission_backing_handoff_post_confirm_overwrite",
        "page_fields": pages,
        "backing_subview": forensics.get("backing_subview"),
        "example_present": (forensics.get("improv_mission_example") or {}).get("present"),
        "lick_present": (forensics.get("improv_mission_practice_lick") or {}).get("present"),
    }
    _append_violation(session, VIOLATION_POST_CONFIRM_OVERWRITE, detail=json.dumps(detail))
    d = _diag(session)
    d["post_confirm_overwrite"] = detail
    passive = reason in ("autosave", "force_autosave", "") or reason.startswith("creative_mission_")
    return passive, detail


def record_refresh_hydration_step(
    session: dict[str, Any],
    function: str,
    *,
    page: str | None = None,
    backing_subview: str | None = None,
    example_present: bool | None = None,
    lick_present: bool | None = None,
    overwrite_source: str | None = None,
    overwrite_function: str | None = None,
    fetched_revision: Any = None,
    fetch_source: str | None = None,
) -> None:
    if not session.get("developer_mode"):
        return
    trace = session.get(MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY)
    if not isinstance(trace, dict):
        trace = {"steps": [], "fetch_source": fetch_source, "fetched_revision": fetched_revision}
        session[MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY] = trace
    steps = trace.setdefault("steps", [])
    if not isinstance(steps, list):
        steps = []
        trace["steps"] = steps
    steps.append(
        {
            "function": function,
            "page": page,
            "backing_subview": backing_subview,
            "example_present": example_present,
            "lick_present": lick_present,
            "overwrite_source": overwrite_source,
            "overwrite_function": overwrite_function,
        }
    )


def begin_mission_backing_handoff(
    session: dict[str, Any],
    *,
    navigation_callback: str,
    with_practice_lick: bool,
) -> None:
    session[MISSION_BACKING_HANDOFF_ACTIVE_KEY] = True
    d = _diag(session)
    d.clear()
    d.update(
        {
            "navigation_callback": navigation_callback,
            "with_practice_lick": with_practice_lick,
            "page_before": _normalize_page(session),
            "backing_subview_before": _backing_subview_label(session),
            "studio_nav_state_before": _studio_nav_snapshot(session),
            "backing_view_state_before": _backing_state_snapshot(session),
            "practice_lick_present_before": bool(session.get(MISSION_PRACTICE_LICK_KEY)),
            "violations": [],
        }
    )


def complete_mission_backing_handoff_after_navigation(
    session: dict[str, Any],
    *,
    navigation_callback: str,
    backing_source: str,
) -> None:
    d_raw = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    if not isinstance(d_raw, dict) or not d_raw.get("with_practice_lick"):
        session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
        return
    session.pop(MISSION_BACKING_HANDOFF_ACTIVE_KEY, None)
    d = _diag(session)
    d["navigation_callback"] = navigation_callback
    d["page_after"] = _normalize_page(session)
    d["backing_subview_after"] = _backing_subview_label(session) or str(backing_source or "").strip()
    d["studio_nav_state_after"] = _studio_nav_snapshot(session)
    d["backing_view_state_after"] = _backing_state_snapshot(session)
    d["practice_lick_present_after"] = bool(session.get(MISSION_PRACTICE_LICK_KEY))
    d["save_reason"] = str(session.get("_suite_persist_last_save_reason") or "").strip()
    d["reserved_revision"] = session.get("_music_last_reserved_workspace_revision")
    d["upsert_result"] = bool(session.get("_suite_persist_last_save_cloud"))
    if d.get("save_reason") != "page_change":
        _append_violation(
            session,
            VIOLATION_HANDOFF_SAVE_REASON_NOT_PAGE_CHANGE,
            detail=str(d.get("save_reason") or ""),
        )
    confirm_mission_backing_handoff_from_network(session)


def on_page_change_cloud_save_finished(
    session: dict[str, Any],
    *,
    state: dict[str, Any],
    save_reason: str,
    cloud_confirmed: bool,
) -> None:
    if not handoff_with_practice_lick_pending(session) and not session.get(
        MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY
    ):
        return
    record_handoff_final_upsert_if_active(session, state=state, save_reason=save_reason)
    if cloud_confirmed and handoff_with_practice_lick_pending(session):
        confirm_mission_backing_handoff_from_network(session)


def summarize_handoff_payload_forensics(payload: dict[str, Any]) -> dict[str, Any]:
    return _payload_forensics(payload)


def collect_mission_backing_handoff_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(MISSION_BACKING_HANDOFF_DIAG_KEY)
    out = copy.deepcopy(d) if isinstance(d, dict) else {}
    trace = session.get(MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY)
    if isinstance(trace, dict):
        out["refresh_hydration_trace"] = copy.deepcopy(trace)
    return out


__all__ = [
    "MISSION_BACKING_HANDOFF_DIAG_KEY",
    "MISSION_BACKING_HANDOFF_SEALED_FOR_PAGE_CHANGE_KEY",
    "VIOLATION_POST_CONFIRM_OVERWRITE",
    "arm_mission_backing_handoff_page_change",
    "begin_mission_backing_handoff",
    "clear_handoff_page_change_build_flag",
    "collect_mission_backing_handoff_diagnostics",
    "complete_mission_backing_handoff_after_navigation",
    "confirm_mission_backing_handoff_from_network",
    "guard_mission_backing_handoff_post_confirm_overwrite",
    "handoff_with_practice_lick_pending",
    "note_handoff_page_change_payload_built",
    "on_page_change_cloud_save_finished",
    "record_handoff_final_upsert_if_active",
    "record_refresh_hydration_step",
    "seal_mission_backing_handoff_creative_envelope",
    "should_skip_creative_sync_for_handoff_page_change",
    "summarize_handoff_payload_forensics",
]
