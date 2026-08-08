"""One-transaction workspace boundary trace — answers save vs hydrate (Hevenu + Log repro).

Append-only event log in session ``_music_workspace_boundary_trace``. Dev sidebar via
``music_persistence_trace`` expander. Does not change persistence behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

BOUNDARY_TRACE_KEY = "_music_workspace_boundary_trace"
_MAX_EVENTS = 48


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_page(page: Any) -> str:
    text = str(page or "").strip()
    if not text:
        return ""
    try:
        from studio_nav_history import STUDIO_PAGE_IDS

        return text if text in STUDIO_PAGE_IDS else text
    except ImportError:
        return text


def _pick_key_from_block(block: Any) -> str:
    if not isinstance(block, dict):
        return ""
    return str(block.get("pick_key") or "").strip()


def _active_song_title_from_block(block: Any) -> str:
    if not isinstance(block, dict):
        return ""
    sel = block.get("selected_song")
    if isinstance(sel, dict):
        return str(sel.get("title") or sel.get("label") or "").strip()
    active = block.get("active_song")
    if isinstance(active, dict):
        return str(active.get("title") or active.get("pick_key") or "").strip()
    return ""


def live_session_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    core = session.get("core") if isinstance(session.get("core"), dict) else {}
    ass = session.get("active_song_state") if isinstance(session.get("active_song_state"), dict) else {}
    ws = session.get("music_workspace_state") if isinstance(session.get("music_workspace_state"), dict) else {}
    ws_active = ws.get("active_song") if isinstance(ws.get("active_song"), dict) else {}
    nav = session.get("studio_nav_state") if isinstance(session.get("studio_nav_state"), dict) else {}
    snap: dict[str, Any] = {
        "studio_page": _normalize_page(session.get("studio_page")),
        "canonical_studio_page": _normalize_page(nav.get("studio_page") or nav.get("page")),
        "pick_key": _pick_key_from_block(core) or _pick_key_from_block(ass),
        "active_song_title": _active_song_title_from_block(ass) or _active_song_title_from_block(ws_active),
        "music_workspace_studio_page": _normalize_page(ws.get("studio_page")),
        "music_workspace_pick_key": _pick_key_from_block(ws_active),
        "deferred_page_change_save": _normalize_page(session.get("_suite_deferred_page_change_save")),
        "page_change_origin": str(session.get("music_page_change_origin") or "").strip() or None,
        "page_user_nav": bool(session.get("_suite_page_user_nav")),
    }
    try:
        from suite_user_persistence import _local_dirty_key

        snap["suite_local_dirty"] = bool(session.get(_local_dirty_key("music")))
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import collect_startup_save_suppression_diagnostics

        sup = collect_startup_save_suppression_diagnostics(session)
        snap["startup_fingerprint_matches"] = sup.get("startup_fingerprint_matches")
        snap["startup_suppression_released"] = sup.get("startup_suppression_released")
        snap["startup_save_suppression_reason"] = sup.get("startup_save_suppression_reason")
    except ImportError:
        pass
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        snap["last_save_tx"] = collect_save_transaction_diagnostics(session)
    except ImportError:
        pass
    try:
        from suite_workspace import resolve_workspace_id

        snap["workspace_id"] = resolve_workspace_id()
    except ImportError:
        snap["workspace_id"] = str(session.get("_suite_workspace_id") or "").strip() or None
    return snap


def envelope_snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    ass = state.get("active_song_state") if isinstance(state.get("active_song_state"), dict) else {}
    ws = state.get("music_workspace_state") if isinstance(state.get("music_workspace_state"), dict) else {}
    ws_active = ws.get("active_song") if isinstance(ws.get("active_song"), dict) else {}
    nav = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}
    rev = 0
    try:
        from workspace_revision import workspace_revision_from_blob

        rev = workspace_revision_from_blob(state)
    except ImportError:
        rev = int(ws.get("workspace_revision") or state.get("workspace_revision") or 0)
    return {
        "workspace_revision": rev,
        "core_studio_page": _normalize_page(core.get("studio_page") or core.get("page")),
        "session_studio_page": _normalize_page(
            (state.get("session") or {}).get("studio_page")
            if isinstance(state.get("session"), dict)
            else None
        ),
        "music_workspace_studio_page": _normalize_page(ws.get("studio_page")),
        "studio_nav_studio_page": _normalize_page(nav.get("studio_page") or nav.get("page")),
        "pick_key": _pick_key_from_block(core) or _pick_key_from_block(ass),
        "music_workspace_pick_key": _pick_key_from_block(ws_active),
        "active_song_title": _active_song_title_from_block(ass),
    }


def append_boundary_event(session: dict[str, Any], phase: str, **fields: Any) -> None:
    events = session.get(BOUNDARY_TRACE_KEY)
    if not isinstance(events, list):
        events = []
    row: dict[str, Any] = {"phase": str(phase or "unknown"), "at": _utc_now_iso()}
    for key, val in fields.items():
        if val is not None:
            row[key] = val
    events.append(row)
    if len(events) > _MAX_EVENTS:
        events = events[-_MAX_EVENTS :]
    session[BOUNDARY_TRACE_KEY] = events


def record_live_boundary(session: dict[str, Any], phase: str, **extra: Any) -> None:
    snap = live_session_snapshot(session)
    append_boundary_event(session, phase, live=snap, **extra)


def record_serialize_boundary(
    session: dict[str, Any],
    state: dict[str, Any] | None,
    *,
    save_reason: str = "",
    **extra: Any,
) -> None:
    append_boundary_event(
        session,
        "serialize_payload",
        save_reason=str(save_reason or "").strip() or None,
        payload=envelope_snapshot(state),
        live=live_session_snapshot(session),
        **extra,
    )


def record_hydrate_pick_boundary(
    session: dict[str, Any],
    *,
    source: str,
    pick_reason: str,
    state: dict[str, Any] | None,
    cloud_ts: str | None = None,
    before_apply: bool = True,
) -> None:
    append_boundary_event(
        session,
        "hydrate_raw_picked" if before_apply else "hydrate_after_apply",
        source=str(source or ""),
        pick_reason=str(pick_reason or ""),
        cloud_ts=cloud_ts,
        payload=envelope_snapshot(state),
        workspace_id=live_session_snapshot(session).get("workspace_id"),
    )


def record_save_outcome_boundary(
    session: dict[str, Any],
    *,
    save_reason: str,
    ok: bool,
    block_reason: str = "",
    cloud_ok: bool | None = None,
) -> None:
    append_boundary_event(
        session,
        "save_complete" if ok else "save_blocked",
        save_reason=str(save_reason or ""),
        ok=bool(ok),
        block_reason=str(block_reason or "").strip() or None,
        cloud_ok=cloud_ok,
        live=live_session_snapshot(session),
    )


def read_local_durable_envelope(app_id: str = "music") -> dict[str, Any]:
    """Best-effort disk read (Streamlit Cloud may differ; cloud readback lives in save tx)."""
    try:
        from suite_user_persistence import _load_raw

        state, _warn, saved_at = _load_raw(app_id)
        return {"saved_at": saved_at, "envelope": envelope_snapshot(state), "raw_keys": list(state.keys())[:12]}
    except Exception as exc:
        return {"error": str(exc)}


def evaluate_binary_refresh_question(
    *,
    live_before_refresh: dict[str, Any],
    durable_envelope: dict[str, Any],
) -> dict[str, Any]:
    """Classify A/B/C/D from captured live vs durable fields (trace evidence)."""
    live_page = _normalize_page(live_before_refresh.get("studio_page"))
    live_key = str(live_before_refresh.get("pick_key") or "").strip()
    dur = durable_envelope if isinstance(durable_envelope, dict) else {}
    dur_page = _normalize_page(
        dur.get("music_workspace_studio_page")
        or dur.get("core_studio_page")
        or dur.get("studio_nav_studio_page")
    )
    dur_key = str(dur.get("pick_key") or dur.get("music_workspace_pick_key") or "").strip()
    live_matches_intent = bool(live_page and live_key)
    durable_matches_live = live_page == dur_page and (not live_key or live_key == dur_key or live_key in dur_key)
    durable_stale_default = dur_page in ("", "practice") and "Say" in dur_key
    if live_matches_intent and not durable_matches_live:
        if not dur_page and not dur_key:
            hypothesis = "A_never_written"
        elif dur_page == "practice" and live_page != "practice":
            hypothesis = "A_or_B_save_pipeline_stale"
        else:
            hypothesis = "A_or_B_save_pipeline_stale"
    elif durable_matches_live:
        hypothesis = "C_hydration_or_wrong_revision_if_ui_wrong"
    else:
        hypothesis = "unknown_insufficient_trace"
    return {
        "hypothesis": hypothesis,
        "live_page": live_page,
        "live_pick_key": live_key,
        "durable_page": dur_page,
        "durable_pick_key": dur_key,
        "durable_matches_live_before_refresh": durable_matches_live,
        "interpretation": (
            "If live=Hevenu+Log but durable=Say+Practice before refresh → save/materialization (A/B/D). "
            "If durable=Hevenu+Log but UI loads Say+Practice → hydration/version (C)."
        ),
    }


def render_boundary_trace_expander(st: Any, session: dict[str, Any]) -> None:
    events = session.get(BOUNDARY_TRACE_KEY)
    if not isinstance(events, list) or not events:
        return
    with st.expander("Workspace boundary trace (save vs hydrate)", expanded=True):
        st.caption(
            "Capture before refresh: last serialize_payload + save_complete vs hydrate_raw_picked on reload."
        )
        for row in events[-12:]:
            phase = row.get("phase")
            st.markdown(f"**{phase}** @ {row.get('at')}")
            if row.get("save_reason"):
                st.text(f"save_reason: {row.get('save_reason')}")
            if row.get("block_reason"):
                st.text(f"block_reason: {row.get('block_reason')}")
            live = row.get("live")
            if isinstance(live, dict):
                st.text(
                    f"live: page={live.get('studio_page')} pick={live.get('pick_key')} "
                    f"ws_page={live.get('music_workspace_studio_page')} "
                    f"fp_match={live.get('startup_fingerprint_matches')}"
                )
            payload = row.get("payload")
            if isinstance(payload, dict):
                st.text(
                    f"payload: page={payload.get('music_workspace_studio_page')} "
                    f"pick={payload.get('pick_key')} rev={payload.get('workspace_revision')}"
                )
        live = live_session_snapshot(session)
        disk = read_local_durable_envelope("music")
        env = disk.get("envelope") if isinstance(disk.get("envelope"), dict) else {}
        verdict = evaluate_binary_refresh_question(live_before_refresh=live, durable_envelope=env)
        st.markdown("**Binary question (disk readback + live session)**")
        st.json(verdict)


__all__ = [
    "BOUNDARY_TRACE_KEY",
    "append_boundary_event",
    "evaluate_binary_refresh_question",
    "live_session_snapshot",
    "envelope_snapshot",
    "read_local_durable_envelope",
    "record_hydrate_pick_boundary",
    "record_live_boundary",
    "record_save_outcome_boundary",
    "record_serialize_boundary",
    "render_boundary_trace_expander",
]
