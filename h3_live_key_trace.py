"""Env-gated H3 live C/Eb dump. Active only when MUSIC_APP_DATA_DIR is set.

Isolated proofs write JSONL to ``$MUSIC_APP_DATA_DIR/_h3_live_key.jsonl``.
Not a product authority — tracing only.
"""
from __future__ import annotations

import inspect
import json
import os
import time
from typing import Any


def _enabled() -> bool:
    return bool(str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip())


def _path() -> str:
    return os.path.join(str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip(), "_h3_live_key.jsonl")


def _page_path() -> str:
    return os.path.join(str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip(), "_h3_studio_page.jsonl")


def _tonic_of_blob_raw(raw: Any) -> str:
    if raw is None:
        return ""
    if hasattr(raw, "keys"):
        keys = getattr(raw, "keys", None)
        return str(getattr(keys, "practice_tonic", "") or "").strip()
    if isinstance(raw, dict):
        keys = raw.get("keys") if isinstance(raw.get("keys"), dict) else {}
        return str(keys.get("practice_tonic") or "").strip()
    return ""


def _section_hint(raw: Any) -> str:
    sm = getattr(raw, "section_map", None) if raw is not None and not isinstance(raw, dict) else None
    if sm is None and isinstance(raw, dict):
        sm = raw.get("section_map")
    if not isinstance(sm, dict):
        return ""
    for chords in sm.values():
        if isinstance(chords, list) and chords:
            return ",".join(str(c) for c in chords[:4])
    return ""


def _store_copy_row(name: str, store: Any, uuid: str) -> dict[str, Any]:
    if not isinstance(store, dict):
        return {"path": name, "present": False}
    blobs = store.get("blobs") if isinstance(store.get("blobs"), dict) else {}
    if not blobs and isinstance(store.get("store"), dict):
        inner = store.get("store") or {}
        blobs = inner.get("blobs") if isinstance(inner.get("blobs"), dict) else {}
        store = inner
    uuid_key = f"jam_session_generator|{uuid}" if uuid else ""
    uuid_raw = blobs.get(uuid_key) if uuid_key else None
    jam_rows = []
    for k, v in list(blobs.items())[:24]:
        if str(k).startswith("jam_session_generator|"):
            jam_rows.append(
                {
                    "key": str(k),
                    "tonic": _tonic_of_blob_raw(v),
                    "sections": _section_hint(v),
                }
            )
    return {
        "path": name,
        "present": True,
        "obj_id": id(store),
        "uuid_tonic": _tonic_of_blob_raw(uuid_raw) if uuid_raw is not None else "",
        "uuid_sections": _section_hint(uuid_raw) if uuid_raw is not None else "",
        "jam_blobs": jam_rows,
        "revision_seq": store.get("context_revision_seq"),
    }


def enumerate_workflow_store_copies(session: dict[str, Any]) -> list[dict[str, Any]]:
    uuid = str(session.get("_jam_session_generator_session_id") or "").strip()
    jam = session.get("improv_jam_session")
    if not uuid and isinstance(jam, dict):
        uuid = str(jam.get("id") or "").strip()
    rows: list[dict[str, Any]] = []
    rows.append(_store_copy_row("session._music_workflow_state_store", session.get("_music_workflow_state_store"), uuid))
    rows.append(_store_copy_row("session.music_workflow_state_v1", session.get("music_workflow_state_v1"), uuid))
    cws = session.get("creative_workspace_state")
    nested = cws.get("music_workflow_state_v1") if isinstance(cws, dict) else None
    nested_store = nested.get("store") if isinstance(nested, dict) else None
    rows.append(_store_copy_row("cws.music_workflow_state_v1.store", nested_store or nested, uuid))
    mws = session.get("music_workspace_state")
    mws_cws = mws.get("creative_workspace_state") if isinstance(mws, dict) else None
    mws_nested = mws_cws.get("music_workflow_state_v1") if isinstance(mws_cws, dict) else None
    mws_store = mws_nested.get("store") if isinstance(mws_nested, dict) else None
    rows.append(_store_copy_row("music_workspace_state.cws.music_workflow_state_v1.store", mws_store or mws_nested, uuid))
    return rows


def snapshot_live_keys(session: dict[str, Any]) -> dict[str, Any]:
    """Complete C/Eb table for one moment in a live rerun."""
    jam = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else {}
    bctx = session.get("backing_context") if isinstance(session.get("backing_context"), dict) else {}
    snap = session.get("_backing_owner_artifact_snapshot")
    if not isinstance(snap, dict):
        cws = session.get("creative_workspace_state")
        snap = cws.get("_backing_owner_artifact_snapshot") if isinstance(cws, dict) else {}
    ptr = session.get("_music_active_workflow") if isinstance(session.get("_music_active_workflow"), dict) else {}
    jam_ctx = session.get("_generated_jam_key_context")
    if not isinstance(jam_ctx, dict):
        jam_ctx = {}
    uuid = str(session.get("_jam_session_generator_session_id") or jam.get("id") or "").strip()
    live_blob_tonic = ""
    live_blob_sections = ""
    ui_ident = ""
    active_ident = ""
    live_ctx_key = ""
    try:
        from generated_jam_key_change import resolve_generated_workflow_session_id
        from music_workflow_state_store import get_workflow_blob

        sid = resolve_generated_workflow_session_id(session, "jam_session_generator")
        uuid = sid or uuid
        blob = get_workflow_blob(session, "jam_session_generator", sid) if sid else None
        if blob is not None:
            live_blob_tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "")
            live_blob_sections = _section_hint(blob)
    except Exception as exc:
        live_blob_tonic = f"err:{type(exc).__name__}"
    try:
        from workflow_key_identity import (
            resolve_active_workflow_key_identity,
            resolve_practice_key_identity_for_ui,
        )

        ui = resolve_practice_key_identity_for_ui(dict(session) if isinstance(session, dict) else session)
        act = resolve_active_workflow_key_identity(session)
        if ui is not None:
            ui_ident = f"{ui.workflow_owner}|{ui.workflow_session_id}|{ui.practice_key_token}"
        if act is not None:
            active_ident = f"{act.workflow_owner}|{act.workflow_session_id}|{act.practice_key_token}"
    except Exception as exc:
        ui_ident = f"err:{type(exc).__name__}"
    try:
        from backing_context import build_entry_jam_context, get_backing_context

        stored = get_backing_context(session)
        live_ctx = build_entry_jam_context(session)
        live_ctx_key = str(
            getattr(live_ctx, "concert_key", "")
            or getattr(live_ctx, "display_key", "")
            or getattr(live_ctx, "key", "")
            or ""
        )
        stored_key = str(
            getattr(stored, "concert_key", "")
            or getattr(stored, "display_key", "")
            or getattr(stored, "key", "")
            or ""
        ) if stored is not None else ""
    except Exception:
        stored_key = str(bctx.get("concert_key") or bctx.get("key") or "")
        live_ctx_key = ""
    return {
        "studio_page": session.get("studio_page"),
        "display_key": session.get("display_key"),
        "concert_key": session.get("concert_key"),
        "pending_display_key": session.get("_pending_display_key"),
        "last_write_source": session.get("_display_key_last_write_source"),
        "improv_jam_key": session.get("improv_jam_key"),
        "improv_jam_session_key": jam.get("key"),
        "improv_jam_session_id": jam.get("id"),
        "stored_uuid": session.get("_jam_session_generator_session_id"),
        "ptr_owner": ptr.get("workflow_owner"),
        "ptr_sid": ptr.get("workflow_session_id"),
        "live_get_workflow_blob_tonic": live_blob_tonic,
        "live_get_workflow_blob_sections": live_blob_sections,
        "ui_ident": ui_ident,
        "active_ptr_ident": active_ident,
        "jam_ctx_token": jam_ctx.get("practice_key_token"),
        "backing_source": bctx.get("source") or session.get("backing_source"),
        "backing_context_key": stored_key if "stored_key" in locals() else str(bctx.get("concert_key") or bctx.get("key") or ""),
        "build_entry_jam_context_key": live_ctx_key,
        "snap_tonic": str((snap or {}).get("practice_tonic") or "") if isinstance(snap, dict) else "",
        "snap_sid": str((snap or {}).get("workflow_session_id") or "") if isinstance(snap, dict) else "",
        "widgets_locked": bool(
            session.get("_streamlit_widgets_locked_this_run")
            or session.get("_streamlit_widgets_locked")
        ),
        "stores": enumerate_workflow_store_copies(session),
    }


def emit(session: dict[str, Any], phase: str, **extra: Any) -> None:
    if not _enabled() or session is None:
        return
    try:
        sess = session if isinstance(session, dict) else dict(session)
    except Exception:
        try:
            sess = {str(k): session[k] for k in list(session.keys())}  # type: ignore[attr-defined]
        except Exception:
            return
    try:
        stack = [
            f"{fr.function}:{fr.lineno}"
            for fr in inspect.stack()[1:8]
            if fr.function not in {"emit", "emit_display_key_write"}
        ]
        row = {
            "ts": time.time(),
            "phase": phase,
            **snapshot_live_keys(sess),
            **extra,
            "stack": stack,
        }
        with open(_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        try:
            with open(_path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "phase": phase, "emit_error": True, **extra}, default=str) + "\n")
        except Exception:
            return


def emit_display_key_write(session: dict[str, Any], value: str, *, source: str) -> None:
    if not _enabled() or session is None:
        return
    before = str(session.get("display_key") or "")
    emit(
        session,
        "display_key_write",
        write_source=source,
        write_value=str(value or ""),
        display_key_before_assign=before,
    )


def dump_studio_page_write(
    session: dict[str, Any],
    *,
    old_page: Any,
    new_page: str,
    reason: str = "",
) -> None:
    """Every studio_page write during isolated H3 proofs."""
    if not _enabled():
        return
    old = str(old_page or "").strip()
    new = str(new_page or "").strip()
    if old == new:
        return
    nav = session.get("studio_nav_state") if isinstance(session.get("studio_nav_state"), dict) else {}
    bctx = session.get("backing_context") if isinstance(session.get("backing_context"), dict) else {}
    jam = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else {}
    row = {
        "ts": time.time(),
        "old_page": old,
        "new_page": new,
        "reason": str(reason or ""),
        "backing_source": str(bctx.get("source") or session.get("backing_source") or ""),
        "handoff": str(session.get("_backing_explicit_handoff_source") or ""),
        "jam_uuid": str(session.get("_jam_session_generator_session_id") or jam.get("id") or ""),
        "navigate_pending": str(session.get("_navigate_to_studio_page") or ""),
        "user_nav": bool(session.get("_suite_page_user_nav")),
        "user_nav_page": str(session.get("_music_user_navigated_page_this_run") or ""),
        "nav_reason": str(nav.get("last_write_reason") or ""),
        "stack": [
            f"{fr.function}:{fr.lineno}"
            for fr in inspect.stack()[1:10]
            if fr.function not in {"dump_studio_page_write"}
        ],
    }
    try:
        with open(_page_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        return
