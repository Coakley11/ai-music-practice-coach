"""Unified ?dev=1 workflow architecture panel (Phase 3 Commit 1)."""

from __future__ import annotations

from typing import Any

from music_workflow_compatibility import build_workflow_blob_from_legacy, peek_legacy_inferred_owner
from music_workflow_state_store import (
    WORKFLOW_COMPAT_FALLBACKS_KEY,
    WORKFLOW_LEGACY_READS_KEY,
    collect_consistency_violations,
    get_active_workflow_pointer,
    get_workflow_blob,
    resolve_workspace_identity,
    workflow_cache_identity,
)


def _dev_enabled(session: dict[str, Any], st_module: Any | None) -> bool:
    if session.get("dev_mode"):
        return True
    try:
        from suite_workspace import is_developer_mode_enabled

        return is_developer_mode_enabled(st=st_module)
    except ImportError:
        return False


def build_workflow_architecture_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    ptr = get_active_workflow_pointer(session)
    active_blob = None
    if ptr and ptr.workflow_owner:
        active_blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    legacy_owner = peek_legacy_inferred_owner(session)
    legacy_peek = build_workflow_blob_from_legacy(session, legacy_owner) if legacy_owner else None
    ws, acct = resolve_workspace_identity(session)
    store = session.get("_music_workflow_state_store") or {}
    stats = store.get("stats") if isinstance(store, dict) else {}
    activation = session.get("_music_workflow_activation_last") or session.get("_music_workflow_activation_diag") or {}
    mutation = session.get("_music_workflow_mutation_last") or session.get("_music_workflow_mutation_diag") or {}
    bootstrap = session.get("_music_workflow_bootstrap_trace") or {}
    direct_writes = list(session.get("_music_workflow_direct_write_log") or [])[-6:]
    return {
        "workspace_id": ws,
        "account_id": acct,
        "active_pointer": ptr.to_dict() if ptr else None,
        "active_blob": active_blob.to_dict() if active_blob else None,
        "legacy_inferred_owner": legacy_owner,
        "legacy_peek_blob": legacy_peek.to_dict() if legacy_peek else None,
        "store_blob_keys": list((store.get("blobs") or {}).keys()) if isinstance(store, dict) else [],
        "context_revision_seq": store.get("context_revision_seq") if isinstance(store, dict) else None,
        "store_stats": stats,
        "legacy_reads": list(session.get(WORKFLOW_LEGACY_READS_KEY) or [])[-12:],
        "compat_fallbacks": list(session.get(WORKFLOW_COMPAT_FALLBACKS_KEY) or [])[-12:],
        "cache_identity": workflow_cache_identity(session),
        "violations": collect_consistency_violations(session),
        "activation_last": activation,
        "mutation_last": mutation,
        "bootstrap_trace": bootstrap,
        "active_creative_view": str(session.get("_music_active_creative_view") or ""),
        "direct_owner_writes": direct_writes,
        "page": str(session.get("studio_page") or ""),
        "tab": str(session.get("improv_intelligence_tab") or ""),
        "entry_mode": str(session.get("improv_entry_mode") or ""),
        "deploy_sha": str(session.get("_studio_ui_release_sha") or "")[:7],
    }


def render_unified_workflow_architecture_panel(st_module: Any, session: dict[str, Any]) -> None:
    if not _dev_enabled(session, st_module):
        return
    snap = build_workflow_architecture_snapshot(session)
    ptr = snap.get("active_pointer") or {}
    blob = snap.get("active_blob") or {}
    keys = blob.get("keys") or {}
    legacy = snap.get("legacy_peek_blob") or {}
    lkeys = legacy.get("keys") or {}
    st_module.caption(
        "DEV workflow architecture · "
        f"ptr `{ptr.get('workflow_owner', '—')}` / `{str(ptr.get('workflow_session_id', ''))[:20]}` · "
        f"rev `{ptr.get('context_revision', '—')}` · "
        f"ws `{snap.get('workspace_id')}` · "
        f"page `{snap.get('page')}` tab `{snap.get('tab')}` entry `{snap.get('entry_mode')}` · "
        f"practice `{keys.get('practice_tonic', lkeys.get('practice_tonic', '—'))}` "
        f"{keys.get('practice_mode', lkeys.get('practice_mode', ''))}` · "
        f"chord `{blob.get('selected_chord_symbol') or legacy.get('selected_chord_symbol') or '—'}` · "
        f"legacy_infer `{snap.get('legacy_inferred_owner') or '—'}` · "
        f"store_keys `{len(snap.get('store_blob_keys') or [])}` · "
        f"stats `{snap.get('store_stats')}` · "
        f"cache `{str(snap.get('cache_identity', ''))[:12]}` · "
        f"violations `{snap.get('violations')}` · "
        f"legacy_reads `{len(snap.get('legacy_reads') or [])}` · "
        f"fallbacks `{len(snap.get('compat_fallbacks') or [])}` · "
        f"sha `{snap.get('deploy_sha') or '—'}`"
    )
    with st_module.expander("DEV workflow architecture (detail)", expanded=False):
        st_module.json(
            {
                "pointer": snap.get("active_pointer"),
                "active_blob": snap.get("active_blob"),
                "legacy_peek": snap.get("legacy_peek_blob"),
                "store_keys": snap.get("store_blob_keys"),
                "legacy_reads": snap.get("legacy_reads"),
                "compat_fallbacks": snap.get("compat_fallbacks"),
                "violations": snap.get("violations"),
            }
        )


__all__ = [
    "build_workflow_architecture_snapshot",
    "render_unified_workflow_architecture_panel",
]
