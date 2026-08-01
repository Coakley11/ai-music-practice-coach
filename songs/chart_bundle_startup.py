"""Startup chart-bundle prerequisites and bounded automatic recovery."""

from __future__ import annotations

from typing import Any

CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY = "_chart_bundle_recovery_attempts"
CHART_BUNDLE_RECOVERY_MAX = 2
CHART_BUNDLE_RECOVERY_DIAG_KEY = "_chart_bundle_recovery_diag"
CHART_BUNDLE_RECOVERY_STOP_REASON_KEY = "_chart_bundle_recovery_stop_reason"


def clear_chart_bundle_recovery_state(session_state: dict[str, Any]) -> None:
    session_state.pop(CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY, None)
    session_state.pop("_chart_bundle_build_retry", None)
    session_state.pop(CHART_BUNDLE_RECOVERY_STOP_REASON_KEY, None)


def chart_bundle_recovery_attempts(session_state: dict[str, Any]) -> int:
    return int(session_state.get(CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY) or 0)


def chart_bundle_recovery_exhausted(session_state: dict[str, Any]) -> bool:
    return chart_bundle_recovery_attempts(session_state) >= CHART_BUNDLE_RECOVERY_MAX


def record_chart_bundle_failure(
    session_state: dict[str, Any],
    exc: BaseException,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    catalog_song_data: dict[str, Any] | None = None,
    chart_cache_sig: Any = None,
) -> None:
    session_state[CHART_BUNDLE_RECOVERY_DIAG_KEY] = collect_chart_bundle_restore_diagnostics(
        session_state,
        song_picker_catalog=song_picker_catalog,
        catalog_song_data=catalog_song_data,
        chart_cache_sig=chart_cache_sig,
        last_error=f"{type(exc).__name__}: {exc}",
    )


def collect_chart_bundle_restore_diagnostics(
    session_state: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    catalog_song_data: dict[str, Any] | None = None,
    chart_cache_sig: Any = None,
    last_error: str = "",
) -> dict[str, Any]:
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, reconcile_active_pick_key

    sel = session_state.get(SELECTED_SONG_STATE_KEY) if isinstance(session_state.get(SELECTED_SONG_STATE_KEY), dict) else {}
    overlay = dict(catalog_song_data or {})
    reconciled_pk = reconcile_active_pick_key(
        session_state,
        song_picker_catalog=song_picker_catalog,
    )
    live_pk = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    meta_pk = ""
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            meta_pk = str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "").strip()
    except ImportError:
        pass

    canonical_found = False
    canonical_key = ""
    if reconciled_pk and song_picker_catalog is not None:
        try:
            from songs.state import load_catalog_song_record_by_pick_key

            lib = session_state.get("_reconcile_song_library") or session_state.get("_catalog_backup_library")
            if not isinstance(lib, dict):
                lib = song_picker_catalog
            loaded = load_catalog_song_record_by_pick_key(
                reconciled_pk,
                song_picker_catalog=song_picker_catalog,
                song_library=lib if isinstance(lib, dict) else song_picker_catalog,
            )
            if loaded is not None:
                canonical_found = True
                canonical_key = str(loaded[2].get("key") or "").strip()
        except Exception:
            pass

    restore_phase = {}
    try:
        from music_restore_phase import (
            authoritative_restore_in_progress,
            music_restore_phase_complete,
        )

        restore_phase = {
            "authoritative_restore_in_progress": authoritative_restore_in_progress(session_state),
            "music_restore_phase_complete": music_restore_phase_complete(session_state),
        }
    except ImportError:
        restore_phase = {"import": "music_restore_phase unavailable"}

    stop_reason = str(session_state.get(CHART_BUNDLE_RECOVERY_STOP_REASON_KEY) or "").strip()
    if not stop_reason and chart_bundle_recovery_exhausted(session_state):
        stop_reason = "recovery_attempts_exhausted"
    elif not stop_reason and last_error:
        stop_reason = "chart_build_not_ready"

    workspace_fields: dict[str, Any] = {}
    try:
        from active_song_workspace_restore import merge_active_song_workspace_diagnostics

        workspace_fields = merge_active_song_workspace_diagnostics(session_state)
    except ImportError:
        pass

    return {
        "recovery_attempts": chart_bundle_recovery_attempts(session_state),
        "recovery_max": CHART_BUNDLE_RECOVERY_MAX,
        "recovery_exhausted": chart_bundle_recovery_exhausted(session_state),
        "recovery_stop_reason": stop_reason or "(none)",
        "reconciled_pick_key": reconciled_pk or "(empty)",
        "live_active_catalog_pick_key": live_pk or "(empty)",
        "active_song_state_pick_key": meta_pk or "(empty)",
        "selected_song_has_key": bool(str(sel.get("key") or "").strip()),
        "overlay_has_key": bool(str(overlay.get("key") or "").strip()),
        "canonical_catalog_found": canonical_found,
        "canonical_original_key": canonical_key or "(missing)",
        "music_startup_restore_finalized": bool(session_state.get("_music_startup_restore_finalized")),
        "music_active_pick_key_reconciled": bool(session_state.get("_music_active_pick_key_reconciled")),
        "workspace_blob_hydrated": bool(session_state.get("_music_workspace_blob_hydrated")),
        "restore_phase": restore_phase,
        "chart_cache_signature": repr(chart_cache_sig) if chart_cache_sig is not None else "(not captured)",
        "last_chart_error": last_error or "(none)",
        **workspace_fields,
    }


def render_chart_bundle_restore_diagnostics(st_module: Any, session_state: dict[str, Any]) -> None:
    diag = session_state.get(CHART_BUNDLE_RECOVERY_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = collect_chart_bundle_restore_diagnostics(session_state)
    st_module.markdown("**Chart bundle restore**")
    for key, val in diag.items():
        if key == "restore_phase" and isinstance(val, dict):
            st_module.text(f"{key}:")
            for sub_k, sub_v in val.items():
                st_module.text(f"  {sub_k}: {sub_v}")
        else:
            st_module.text(f"{key}: {val}")


def _hydrate_from_canonical_pick(
    st: Any,
    overlay: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> tuple[str, str, dict[str, Any]] | None:
    from songs.music_source import _merge_chart_song_overlay
    from songs.state import (
        ACTIVE_CATALOG_PICK_KEY,
        load_catalog_song_record_by_pick_key,
        reconcile_active_pick_key,
    )

    pk = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if not pk:
        pk = reconcile_active_pick_key(
            st.session_state,
            song_picker_catalog=song_picker_catalog,
        )
    if not pk or pk.startswith("custom::"):
        return None
    loaded = load_catalog_song_record_by_pick_key(
        pk,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    if loaded is None:
        return None
    genre, title, canon = loaded
    sel = st.session_state.get("selected_song") if isinstance(st.session_state.get("selected_song"), dict) else {}
    merged = _merge_chart_song_overlay(canon, overlay)
    if isinstance(sel, dict) and sel:
        merged = _merge_chart_song_overlay(merged, sel)
    if not str(merged.get("key") or "").strip():
        return None
    return genre, title, merged


def prepare_catalog_song_for_chart_bundle(
    st: Any,
    genre: str,
    song: str,
    song_data: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> tuple[str, str, dict[str, Any]]:
    """Reconcile pick key and refresh catalog song_data when session overlay is partial."""
    from songs.state import (
        SELECTED_SONG_STATE_KEY,
        apply_active_pick_key_reconciliation,
        get_song_context,
    )
    from songs.music_source import stamp_chart_bundle_catalog_context

    stamp_chart_bundle_catalog_context(
        st.session_state,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    apply_active_pick_key_reconciliation(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    overlay = dict(song_data or {})
    sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
    overlay_key = str(overlay.get("key") or "").strip()
    sel_key = str(sel.get("key") or "").strip() if isinstance(sel, dict) else ""
    needs_hydrate = not overlay_key or not sel_key

    if needs_hydrate:
        hydrated = _hydrate_from_canonical_pick(
            st,
            overlay,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
        if hydrated is not None:
            clear_chart_bundle_recovery_state(st.session_state)
            return hydrated
        try:
            g, t, data = get_song_context(
                st,
                song_library=song_library,
                song_picker_catalog=song_picker_catalog,
            )
        except RuntimeError:
            g, t, data = genre, song, overlay
        if str(data.get("key") or "").strip():
            clear_chart_bundle_recovery_state(st.session_state)
            return g, t, data

    if str(overlay.get("key") or "").strip():
        clear_chart_bundle_recovery_state(st.session_state)
    return genre, song, overlay


def run_chart_bundle_automatic_recovery(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> bool:
    """One bounded recovery step. Returns True if caller should ``st.rerun()``."""
    ss = st.session_state
    try:
        from active_song_workspace_restore import should_block_chart_recovery_no_pick_key

        if should_block_chart_recovery_no_pick_key(ss):
            ss[CHART_BUNDLE_RECOVERY_STOP_REASON_KEY] = "missing_active_song_pick_key"
            return False
    except ImportError:
        pass
    if chart_bundle_recovery_exhausted(ss):
        ss[CHART_BUNDLE_RECOVERY_STOP_REASON_KEY] = "recovery_attempts_exhausted"
        return False
    ss[CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY] = chart_bundle_recovery_attempts(ss) + 1
    g, t, data = prepare_catalog_song_for_chart_bundle(
        st,
        str(ss.get("_chart_bundle_recovery_genre") or ""),
        str(ss.get("_chart_bundle_recovery_song") or ""),
        dict(ss.get("_chart_bundle_recovery_song_data") or {}),
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    stash_chart_bundle_recovery_context(ss, genre=g, song=t, song_data=data)
    ss["_chart_bundle_recovery_genre"] = g
    ss["_chart_bundle_recovery_song"] = t
    ss["_chart_bundle_recovery_song_data"] = dict(data or {})
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(ss, "chart_bundle")
    except ImportError:
        pass
    if str(data.get("key") or "").strip():
        ss[CHART_BUNDLE_RECOVERY_STOP_REASON_KEY] = ""
        return True
    ss[CHART_BUNDLE_RECOVERY_STOP_REASON_KEY] = "hydrate_still_missing_key_after_recovery"
    return True


def stash_chart_bundle_recovery_context(
    session_state: dict[str, Any],
    *,
    genre: str,
    song: str,
    song_data: dict[str, Any],
) -> None:
    session_state["_chart_bundle_recovery_genre"] = genre
    session_state["_chart_bundle_recovery_song"] = song
    session_state["_chart_bundle_recovery_song_data"] = dict(song_data or {})
