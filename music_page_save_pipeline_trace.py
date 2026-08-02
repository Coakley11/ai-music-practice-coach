"""Function-level page save pipeline trace (?dev=1 / Phase 1 journal)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

PAGE_SAVE_PIPELINE_TRACE_KEY = "_music_page_save_pipeline_trace"

# Confirms deployed module identity in live JSON (not SHA alone).
page_sync_impl_marker = "music_page_save_pipeline_trace:v1:synchronize"
page_target_impl_marker = "music_page_save_pipeline_trace:v1:page_change_write_target"
prepare_studio_nav_impl_marker = "music_page_save_pipeline_trace:v1:prepare_studio_nav"
build_disk_impl_marker = "music_page_save_pipeline_trace:v1:build_music_disk_state"
finalize_impl_marker = "music_page_save_pipeline_trace:v1:finalize_page_change"
force_save_impl_marker = "music_page_save_pipeline_trace:v1:force_music_workspace_save"
navigate_impl_marker = "music_page_save_pipeline_trace:v1:navigate_studio_page"
prepare_save_impl_marker = "music_page_save_pipeline_trace:v1:prepare_page_change_save_state"
upsert_impl_marker = "music_page_save_pipeline_trace:v1:pre_supabase_upsert"

_TRACE_MAX = 120


def pipeline_trace_enabled(session: dict[str, Any]) -> bool:
    if session.get("_phase1_write_journal_force"):
        return True
    if session.get("developer_mode"):
        return True
    try:
        from music_phase1_write_journal import phase1_journal_enabled

        return bool(phase1_journal_enabled(session))
    except ImportError:
        return False


def _caller_chain(*, depth: int = 5) -> str:
    parts: list[str] = []
    for frame in inspect.stack()[2 : 2 + depth]:
        path = Path(frame.filename)
        parts.append(f"{frame.function}({path.name}:{frame.lineno})")
    return " <- ".join(parts)


def _normalize_page(page: Any) -> str:
    val = str(page or "").strip()
    if not val:
        return ""
    try:
        from music_persistent_state import _normalize_studio_page_for_save

        return _normalize_studio_page_for_save(val) or val
    except ImportError:
        return val


def _envelope_page(session: dict[str, Any]) -> str:
    try:
        from suite_user_persistence import load_user_state

        blob = load_user_state("music")
        if isinstance(blob, dict):
            ws = blob.get("music_workspace_state")
            if isinstance(ws, dict):
                return _normalize_page(ws.get("studio_page") or ws.get("page"))
    except Exception:
        pass
    return _normalize_page(session.get("_suite_last_persisted_page"))


def snapshot_page_bearing_state(
    session: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nav = session.get("studio_nav_state")
    nav_page = ""
    if isinstance(nav, dict):
        nav_page = _normalize_page(nav.get("studio_page") or nav.get("page"))
    pws = session.get("practice_workspace_state")
    pws_page = ""
    if isinstance(pws, dict):
        pws_page = _normalize_page(pws.get("studio_page") or pws.get("page"))
    mws = session.get("music_workspace_state")
    mws_page = ""
    if isinstance(mws, dict):
        mws_page = _normalize_page(mws.get("studio_page") or mws.get("page"))
    origin = ""
    try:
        from music_startup_save_suppression import get_page_change_origin

        origin = str(get_page_change_origin(session) or "").strip()
    except ImportError:
        origin = str(session.get("_music_page_change_origin") or "").strip()
    out: dict[str, Any] = {
        "run_seq": session.get("_script_run_seq"),
        "studio_page": _normalize_page(session.get("studio_page")),
        "canonical_studio_nav_page": nav_page,
        "hydrated_page": _normalize_page(session.get("_music_hydrated_studio_page")),
        "practice_workspace_page": pws_page,
        "music_workspace_page": mws_page,
        "workspace_envelope_page": _envelope_page(session),
        "_suite_page_change_write_pending": _normalize_page(session.get("_suite_page_change_write_pending")),
        "_music_user_navigated_page_this_run": _normalize_page(
            session.get("_music_user_navigated_page_this_run")
        ),
        "page_change_origin": origin or None,
        "_suite_page_user_nav": bool(session.get("_suite_page_user_nav")),
    }
    if isinstance(payload, dict):
        out["payload_pages"] = payload_pages_from_state(payload)
    return out


def payload_pages_from_state(state: dict[str, Any]) -> dict[str, str]:
    try:
        from music_persistent_state import _payload_page_snapshot

        snap = _payload_page_snapshot(state)
        return {
            "core": _normalize_page(snap.get("core")),
            "session": _normalize_page(snap.get("session")),
            "workspace": _normalize_page(snap.get("workspace")),
            "studio_nav": _normalize_page(snap.get("studio_nav")),
        }
    except ImportError:
        core = state.get("core") if isinstance(state.get("core"), dict) else {}
        sess = state.get("session") if isinstance(state.get("session"), dict) else {}
        ws = state.get("music_workspace_state") if isinstance(state.get("music_workspace_state"), dict) else {}
        nav = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}
        return {
            "core": _normalize_page(core.get("studio_page")),
            "session": _normalize_page(sess.get("studio_page")),
            "workspace": _normalize_page(ws.get("studio_page") or ws.get("page")),
            "studio_nav": _normalize_page(nav.get("studio_page") or nav.get("page")),
        }


def _trace_bucket(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(PAGE_SAVE_PIPELINE_TRACE_KEY)
    if isinstance(raw, dict):
        return raw
    fresh: dict[str, Any] = {
        "run_seq": int(session.get("_script_run_seq") or 0),
        "impl_markers": {
            "page_sync": page_sync_impl_marker,
            "page_target": page_target_impl_marker,
            "prepare_studio_nav": prepare_studio_nav_impl_marker,
        },
        "events": [],
        "checkpoints": {},
        "failure_class_hints": [],
    }
    session[PAGE_SAVE_PIPELINE_TRACE_KEY] = fresh
    return fresh


def record_pipeline_event(
    session: dict[str, Any],
    *,
    function: str,
    phase: str,
    branch: str = "",
    selected_target: str = "",
    target_source: str = "",
    extra: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if not pipeline_trace_enabled(session):
        return
    bucket = _trace_bucket(session)
    event: dict[str, Any] = {
        "seq": len(bucket.get("events") or []) + 1,
        "function": function,
        "phase": phase,
        "branch": branch or None,
        "selected_target": selected_target or None,
        "target_source": target_source or None,
        "caller_chain": _caller_chain(),
        "state": snapshot_page_bearing_state(session, payload=payload),
    }
    if extra:
        event["extra"] = extra
    events = bucket.setdefault("events", [])
    events.append(event)
    if len(events) > _TRACE_MAX:
        del events[: len(events) - _TRACE_MAX]


def record_checkpoint(
    session: dict[str, Any],
    checkpoint_id: str,
    *,
    payload: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if not pipeline_trace_enabled(session):
        return
    bucket = _trace_bucket(session)
    entry: dict[str, Any] = {
        "id": checkpoint_id,
        "state": snapshot_page_bearing_state(session, payload=payload),
    }
    if extra:
        entry.update(extra)
    bucket.setdefault("checkpoints", {})[checkpoint_id] = entry


def record_page_target_resolution(
    session: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    selected_page: str,
    selected_source: str,
    branch: str,
) -> None:
    record_pipeline_event(
        session,
        function="_page_change_write_target",
        phase="exit",
        branch=branch,
        selected_target=selected_page,
        target_source=selected_source,
        extra={
            "page_target_impl_marker": page_target_impl_marker,
            "candidates": candidates,
            "precedence": [c.get("key") for c in candidates if c.get("eligible")],
            "selected_candidate": selected_source,
        },
    )


def infer_failure_class(session: dict[str, Any]) -> list[str]:
    """Heuristic labels from checkpoints — diagnostic only."""
    bucket = session.get(PAGE_SAVE_PIPELINE_TRACE_KEY)
    if not isinstance(bucket, dict):
        return []
    ck = bucket.get("checkpoints") or {}
    hints: list[str] = []
    a = ck.get("A_post_navigate_studio_page") or ck.get("A_post_navigate_studio_page_complete")
    b_out = ck.get("B_sync_page_bearing_exit")
    d = ck.get("D_build_music_disk_state_return")
    e = ck.get("E_pre_supabase_upsert")
    clicked = ""
    if isinstance(a, dict):
        st = a.get("state") or {}
        clicked = str(st.get("studio_page") or "").strip()
    if not clicked:
        clicked = str(
            (session.get("_music_user_navigated_page_this_run") or session.get("studio_page") or "")
        ).strip()

    sync_events = [
        e
        for e in (bucket.get("events") or [])
        if isinstance(e, dict) and e.get("function") == "synchronize_page_bearing_state_for_save"
    ]
    if clicked and clicked != "backing" and not sync_events:
        hints.append("1_synchronize_not_called_on_path")

    if isinstance(a, dict):
        st = a.get("state") or {}
        if clicked and not str(st.get("_music_user_navigated_page_this_run") or "").strip():
            hints.append("2_user_nav_marker_missing_or_cleared_early")
        elif clicked and str(st.get("_music_user_navigated_page_this_run") or "") != clicked:
            hints.append("2_user_nav_marker_missing_or_cleared_early")

    target_events = [
        e
        for e in (bucket.get("events") or [])
        if isinstance(e, dict) and e.get("function") == "_page_change_write_target"
    ]
    if target_events:
        last = target_events[-1]
        sel = str(last.get("selected_target") or "").strip()
        if clicked and sel and sel != clicked:
            hints.append("3_page_change_write_target_stale_selection")

    if isinstance(b_out, dict) and clicked:
        st = b_out.get("state") or {}
        for key in ("studio_page", "music_workspace_page", "canonical_studio_nav_page"):
            if str(st.get(key) or "") not in ("", clicked):
                hints.append("B_sync_exit_page_not_clicked")
                break

    if isinstance(d, dict) and clicked:
        pages = d.get("payload_pages") or (d.get("extra") or {}).get("payload_pages") or {}
        if not pages:
            st_d = d.get("state") or {}
            pages = st_d.get("payload_pages") or {}
        if isinstance(pages, dict):
            bad = [k for k, v in pages.items() if v and v != clicked]
            if bad and isinstance(b_out, dict):
                hints.append("4_payload_stale_after_sync_or_rebuilt_later")
            elif bad:
                hints.append("4_payload_stale_without_sync_checkpoint")

    if isinstance(d, dict) and isinstance(e, dict) and clicked:
        d_pages = d.get("payload_pages") or (d.get("extra") or {}).get("payload_pages") or {}
        e_pages = e.get("payload_pages") or (e.get("extra") or {}).get("payload_pages") or {}
        if isinstance(d_pages, dict) and isinstance(e_pages, dict):
            if all(d_pages.get(k) == clicked for k in d_pages if d_pages.get(k)) and any(
                e_pages.get(k) and e_pages.get(k) != clicked for k in e_pages
            ):
                hints.append("5_later_save_overwrites_creative_payload")

    force_early = [
        e
        for e in (bucket.get("events") or [])
        if isinstance(e, dict)
        and e.get("function") == "force_music_workspace_save"
        and e.get("phase") == "early_return"
    ]
    if clicked and force_early and not any(
        ev.get("function") == "build_music_disk_state" for ev in (bucket.get("events") or [])
    ):
        hints.append("8_page_change_payload_never_built_force_save_early_return")
    elif clicked:
        d_extra = (d or {}).get("extra") or {}
        if d_extra.get("belongs_to_current_page_click") is False:
            hints.append("7_stale_checkpoint_d_not_current_page_click")
        if d and not d_extra.get("belongs_to_current_page_click", True):
            if "4_payload_stale_after_sync_or_rebuilt_later" in hints:
                hints.remove("4_payload_stale_after_sync_or_rebuilt_later")
            hints.append("8_page_change_payload_never_built_for_current_click")

    prep_events = [
        e
        for e in (bucket.get("events") or [])
        if isinstance(e, dict) and e.get("function") == "prepare_studio_nav"
    ]
    if prep_events and clicked:
        for pe in prep_events:
            branch = str(pe.get("branch") or "")
            if "workspace_blob" in branch or branch == "canonical_after_restore":
                st = pe.get("state") or {}
                if str(st.get("_music_user_navigated_page_this_run") or "") != clicked:
                    hints.append("6_prepare_studio_nav_before_user_nav_visible")

    if isinstance(e, dict) and not isinstance(d, dict) and clicked:
        hints.append("7_diagnostics_missing_build_return_checkpoint")

    bucket["failure_class_hints"] = hints
    return hints


def build_pipeline_trace_copy_block(session: dict[str, Any]) -> str:
    infer_failure_class(session)
    bucket = session.get(PAGE_SAVE_PIPELINE_TRACE_KEY)
    if not isinstance(bucket, dict):
        bucket = {}
    payload = {
        "page_save_pipeline_trace": bucket,
        "impl_markers": {
            "page_sync_impl_marker": page_sync_impl_marker,
            "page_target_impl_marker": page_target_impl_marker,
            "prepare_studio_nav_impl_marker": prepare_studio_nav_impl_marker,
            "build_disk_impl_marker": build_disk_impl_marker,
            "finalize_impl_marker": finalize_impl_marker,
            "force_save_impl_marker": force_save_impl_marker,
            "navigate_impl_marker": navigate_impl_marker,
            "prepare_save_impl_marker": prepare_save_impl_marker,
            "upsert_impl_marker": upsert_impl_marker,
        },
        "failure_class_hints": bucket.get("failure_class_hints") or [],
    }
    return json.dumps(payload, indent=2, default=str)


__all__ = [
    "PAGE_SAVE_PIPELINE_TRACE_KEY",
    "build_disk_impl_marker",
    "build_pipeline_trace_copy_block",
    "finalize_impl_marker",
    "force_save_impl_marker",
    "infer_failure_class",
    "navigate_impl_marker",
    "page_sync_impl_marker",
    "page_target_impl_marker",
    "payload_pages_from_state",
    "pipeline_trace_enabled",
    "prepare_save_impl_marker",
    "prepare_studio_nav_impl_marker",
    "record_checkpoint",
    "record_page_target_resolution",
    "record_pipeline_event",
    "snapshot_page_bearing_state",
    "upsert_impl_marker",
]
