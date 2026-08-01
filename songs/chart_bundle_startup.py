"""Startup chart-bundle prerequisites and bounded automatic recovery."""

from __future__ import annotations

from typing import Any

CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY = "_chart_bundle_recovery_attempts"
CHART_BUNDLE_RECOVERY_MAX = 2


def clear_chart_bundle_recovery_state(session_state: dict[str, Any]) -> None:
    session_state.pop(CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY, None)
    session_state.pop("_chart_bundle_build_retry", None)


def chart_bundle_recovery_attempts(session_state: dict[str, Any]) -> int:
    return int(session_state.get(CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY) or 0)


def chart_bundle_recovery_exhausted(session_state: dict[str, Any]) -> bool:
    return chart_bundle_recovery_attempts(session_state) >= CHART_BUNDLE_RECOVERY_MAX


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
    from songs.music_source import stamp_chart_bundle_catalog_context
    from songs.state import (
        ACTIVE_CATALOG_PICK_KEY,
        SELECTED_SONG_STATE_KEY,
        apply_active_pick_key_reconciliation,
        get_song_context,
    )

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
    pick = str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    overlay_key = str(overlay.get("key") or "").strip()
    sel_key = str(sel.get("key") or "").strip() if isinstance(sel, dict) else ""
    if pick and (not overlay_key or not sel_key):
        g, t, data = get_song_context(
            st,
            song_library=song_library,
            song_picker_catalog=song_picker_catalog,
        )
        if str(data.get("key") or "").strip():
            return g, t, data
    return genre, song, overlay


def run_chart_bundle_automatic_recovery(
    st: Any,
    *,
    song_picker_catalog: dict[str, dict[str, dict]],
    song_library: dict[str, dict[str, dict]],
) -> bool:
    """One bounded recovery step. Returns True if caller should ``st.rerun()``."""
    ss = st.session_state
    if chart_bundle_recovery_exhausted(ss):
        return False
    ss[CHART_BUNDLE_RECOVERY_ATTEMPTS_KEY] = chart_bundle_recovery_attempts(ss) + 1
    prepare_catalog_song_for_chart_bundle(
        st,
        str(ss.get("_chart_bundle_recovery_genre") or ""),
        str(ss.get("_chart_bundle_recovery_song") or ""),
        dict(ss.get("_chart_bundle_recovery_song_data") or {}),
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    try:
        from studio_cache import invalidate_session_cache

        invalidate_session_cache(ss, "chart_bundle")
    except ImportError:
        pass
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
