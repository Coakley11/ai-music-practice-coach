"""Safe session writes when Streamlit widgets may already be instantiated."""

from __future__ import annotations

from typing import Any

from songs.key_state import (
    PENDING_DISPLAY_KEY,
    PENDING_DISPLAY_KEY_PICK,
    PENDING_DISPLAY_KEY_SOURCE,
)

_SBI_ACTIVE_PK_RESTORE_SOURCE = "sbi_active_catalog"

# Keys bound to Streamlit widgets — never assign directly after widget render.
WIDGET_BOUND_KEYS: frozenset[str] = frozenset(
    {
        "display_key",
        "custom_workspace_practice_key",
        "instrument",
        "level",
        "focus",
        "backing_track_bpm",
        "bpm",
        "improv_entry_mode",
        "improv_intelligence_tab",
        "creative_lab_analysis_mode",
        "improv_style_key",
        "improv_jam_key",
        "improv_style",
        "improv_style_bpm",
        "improv_jam_bpm",
        "improv_mood",
        "improv_difficulty",
        "improv_groove",
        "improv_jam_mood",
        "improv_ensemble",
        "improv_jam_style",
        "show_chart_in_instrument_key",
        "song_picker_active_source",
        "selected_transposing_instrument",
        "practice_focus_section",
        "cpl_original_key",
    }
)

PENDING_INSTRUMENT_KEY = "_pending_instrument"
PENDING_LEVEL_KEY = "_pending_level"
PENDING_FOCUS_KEY = "_pending_focus"
PENDING_IMPROV_ENTRY_MODE_KEY = "_pending_improv_entry_mode"
PENDING_IMPROV_INTELLIGENCE_TAB_KEY = "_pending_improv_intelligence_tab"
PENDING_CREATIVE_LAB_MODE_KEY = "_pending_creative_lab_analysis_mode"
PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"
PENDING_IMPROV_STYLE_NAME_KEY = "_pending_improv_style_name"
PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"
PENDING_IMPROV_STYLE_BPM_KEY = "_pending_improv_style_bpm"
PENDING_IMPROV_JAM_BPM_KEY = "_pending_improv_jam_bpm"
PENDING_IMPROV_MOOD_KEY = "_pending_improv_mood"
PENDING_IMPROV_DIFFICULTY_KEY = "_pending_improv_difficulty"
PENDING_IMPROV_GROOVE_KEY = "_pending_improv_groove"
PENDING_IMPROV_JAM_MOOD_KEY = "_pending_improv_jam_mood"
PENDING_IMPROV_ENSEMBLE_KEY = "_pending_improv_ensemble"
PENDING_IMPROV_JAM_STYLE_KEY = "_pending_improv_jam_style"
PENDING_CHART_IN_INSTRUMENT_KEY = "_pending_show_chart_in_instrument_key"
PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY = "_pending_song_picker_active_source"
PENDING_TRANSPOSING_INSTRUMENT_KEY = "_pending_selected_transposing_instrument"
PENDING_WIDGET_ASSIGN_DIAG_KEY = "_pending_widget_assign_diag"
PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY = "_pending_custom_workspace_practice_key"
PENDING_CPL_ORIGINAL_KEY = "_pending_cpl_original_key"

_PENDING_FOR_WIDGET_KEY: dict[str, str] = {
    "display_key": PENDING_DISPLAY_KEY,
    "custom_workspace_practice_key": PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY,
    "cpl_original_key": PENDING_CPL_ORIGINAL_KEY,
    "instrument": PENDING_INSTRUMENT_KEY,
    "level": PENDING_LEVEL_KEY,
    "focus": PENDING_FOCUS_KEY,
    "improv_entry_mode": PENDING_IMPROV_ENTRY_MODE_KEY,
    "improv_intelligence_tab": PENDING_IMPROV_INTELLIGENCE_TAB_KEY,
    "creative_lab_analysis_mode": PENDING_CREATIVE_LAB_MODE_KEY,
    "improv_style_key": PENDING_IMPROV_STYLE_KEY,
    "improv_style": PENDING_IMPROV_STYLE_NAME_KEY,
    "improv_jam_key": PENDING_IMPROV_JAM_KEY,
    "improv_style_bpm": PENDING_IMPROV_STYLE_BPM_KEY,
    "improv_jam_bpm": PENDING_IMPROV_JAM_BPM_KEY,
    "improv_mood": PENDING_IMPROV_MOOD_KEY,
    "improv_difficulty": PENDING_IMPROV_DIFFICULTY_KEY,
    "improv_groove": PENDING_IMPROV_GROOVE_KEY,
    "improv_jam_mood": PENDING_IMPROV_JAM_MOOD_KEY,
    "improv_ensemble": PENDING_IMPROV_ENSEMBLE_KEY,
    "improv_jam_style": PENDING_IMPROV_JAM_STYLE_KEY,
    "show_chart_in_instrument_key": PENDING_CHART_IN_INSTRUMENT_KEY,
    "song_picker_active_source": PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY,
    "selected_transposing_instrument": PENDING_TRANSPOSING_INSTRUMENT_KEY,
}


def _generic_pending_key(widget_key: str) -> str:
    return f"_pending_widget_{widget_key}"


def _record_deferred_widget_assign(
    session: dict[str, Any],
    *,
    widget_key: str,
    pending_key: str,
    value: Any,
    writer: str = "safe_session_assign",
) -> None:
    diag = dict(session.get(PENDING_WIDGET_ASSIGN_DIAG_KEY) or {})
    diag[widget_key] = {
        "pending_key": pending_key,
        "value": value,
        "writer": writer,
    }
    session[PENDING_WIDGET_ASSIGN_DIAG_KEY] = diag


def widgets_likely_instantiated(session: dict[str, Any]) -> bool:
    """True after sidebar/global widgets have rendered this script run."""
    if session.get("_streamlit_widgets_locked_this_run"):
        return True
    try:
        from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY

        if session.get(STREAMLIT_WIDGETS_LOCKED_KEY):
            return True
    except ImportError:
        pass
    return False


def safe_session_assign(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    widget_safe: bool = True,
) -> None:
    """Write session value without touching locked widget keys when ``widget_safe``."""
    if not widget_safe:
        old = session.get(key)
        session[key] = value
        try:
            from music_phase1_write_journal import record_phase1_session_key_write

            record_phase1_session_key_write(
                session,
                key,
                value,
                module="session_widget_safe",
                function="safe_session_assign",
                reason="safe_session_assign",
                origin="widget_safe_off",
            )
        except ImportError:
            pass
        return
    locked = widgets_likely_instantiated(session)
    if not locked:
        old = session.get(key)
        session[key] = value
        try:
            from music_phase1_write_journal import record_phase1_session_key_write

            record_phase1_session_key_write(
                session,
                key,
                value,
                module="session_widget_safe",
                function="safe_session_assign",
                reason="safe_session_assign",
                origin="pre_widget",
            )
        except ImportError:
            pass
        return
    pending_key = _PENDING_FOR_WIDGET_KEY.get(key) or _generic_pending_key(key)
    session[pending_key] = value
    _record_deferred_widget_assign(
        session,
        widget_key=key,
        pending_key=pending_key,
        value=value,
    )


def safe_assign_display_key(
    session: dict[str, Any],
    key: str,
    *,
    widget_safe: bool = True,
    st_like: Any | None = None,
) -> None:
    """Set concert/display key via pending queue when widgets may exist."""
    concert = str(key or "C").strip() or "C"
    locked = widgets_likely_instantiated(session)
    session["concert_key"] = concert
    if locked:
        if str(session.get("display_key") or "").strip() == concert:
            session.pop(PENDING_DISPLAY_KEY, None)
            return
        session[PENDING_DISPLAY_KEY] = concert
        if st_like is not None:
            try:
                from songs.key_state import request_display_key

                request_display_key(st_like, concert)
            except ImportError:
                pass
        return
    session.pop(PENDING_DISPLAY_KEY, None)
    if widget_safe or not locked:
        session["display_key"] = concert


def reconcile_practice_key_fields(session: dict[str, Any], *, authoritative: str) -> str:
    """Align concert_key and pending display_key with the authoritative practice key."""
    concert = str(authoritative or "C").strip() or "C"
    session["concert_key"] = concert
    locked = widgets_likely_instantiated(session)
    if not locked:
        session.pop(PENDING_DISPLAY_KEY, None)
        session["display_key"] = concert
        return concert
    if str(session.get("display_key") or "").strip() == concert:
        session.pop(PENDING_DISPLAY_KEY, None)
        return concert
    session[PENDING_DISPLAY_KEY] = concert
    return concert


def _clear_pending_display_key(session: dict[str, Any]) -> None:
    session.pop(PENDING_DISPLAY_KEY, None)
    session.pop(PENDING_DISPLAY_KEY_PICK, None)
    session.pop(PENDING_DISPLAY_KEY_SOURCE, None)


def _sbi_active_catalog_pending_restore_ok(session: dict[str, Any]) -> bool:
    """Drop Catalog SBI Active pending restore when another owner now owns PK.

    Inline (no import of ``sbi_active_catalog_practice_key``) so this module
    stays the single pending-hydrate consumer and avoids import cycles.
    """
    source = str(session.get(PENDING_DISPLAY_KEY_SOURCE) or "").strip()
    if source != _SBI_ACTIVE_PK_RESTORE_SOURCE:
        return True
    preview = str(
        session.get("sbi_preview_source") or session.get("improv_song_source") or ""
    ).strip()
    if preview in {"Custom progression", "Composition"}:
        return False
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if tab in {"Entry & Jam", ""} and entry in {
        "Jam Session Generator",
        "Style Jam Mode",
    }:
        return False
    try:
        from creative_key_sync import mission_owns_left_panel_key

        if mission_owns_left_panel_key(session):
            return False
    except ImportError:
        pass
    pending_pick = str(session.get(PENDING_DISPLAY_KEY_PICK) or "").strip()
    if not pending_pick:
        return False
    live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    if live_pick and pending_pick != live_pick:
        return False
    return True


def apply_pending_widget_hydrates(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply queued pending values before widgets render (early in rerun).

    When sidebar/global widgets are already instantiated, widget-bound keys are
    left pending; only canonical fields such as ``concert_key`` are updated.
    """
    locked = widgets_likely_instantiated(session)

    try:
        from songs.music_source import composition_song_is_active

        if composition_song_is_active(session):
            from composition_songs_bridge import (
                hydrate_composition_practice_key,
                resolve_composition_canonical_keys,
            )

            _home, practice = resolve_composition_canonical_keys(session)
            if practice:
                hydrate_composition_practice_key(session, practice)
                pending_now = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
                if pending_now != str(practice).strip():
                    session[PENDING_DISPLAY_KEY] = practice
                    session[PENDING_DISPLAY_KEY_SOURCE] = "composition"
    except ImportError:
        pass

    pending_display = session.get(PENDING_DISPLAY_KEY)
    if pending_display is not None:
        pending_src = str(session.get(PENDING_DISPLAY_KEY_SOURCE) or "").strip()
        if pending_src == "composition":
            pending_pick = str(session.get(PENDING_DISPLAY_KEY_PICK) or "").strip()
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
            if pending_pick and live_pick and pending_pick != live_pick:
                _clear_pending_display_key(session)
                pending_display = None
        if pending_display is not None and not _sbi_active_catalog_pending_restore_ok(session):
            _clear_pending_display_key(session)
        elif pending_display is not None:
            concert = str(pending_display).strip() or "C"
            live_dk = str(session.get("display_key") or "").strip()
            pending_src = str(session.get(PENDING_DISPLAY_KEY_SOURCE) or "").strip()
            skip_concert = False
            if (
                locked
                and live_dk
                and live_dk != concert
                and pending_src == _SBI_ACTIVE_PK_RESTORE_SOURCE
            ):
                router = session.get("_practice_key_write_router")
                router_new = ""
                if isinstance(router, dict):
                    router_new = str(router.get("new") or "").strip()
                commit = str(session.get("_pk_user_commit_token") or "").strip()
                overrides = session.get("practice_key_user_override_picks") or []
                pick = str(session.get("active_catalog_pick_key") or "").strip()
                has_override = bool(
                    pick
                    and pick
                    in (
                        {str(k).strip() for k in overrides}
                        if isinstance(overrides, (list, tuple, set))
                        else set()
                    )
                )
                if (
                    (router_new and live_dk == router_new)
                    or (commit and live_dk == commit)
                    or has_override
                ):
                    skip_concert = True
                    _clear_pending_display_key(session)
            if not skip_concert:
                session["concert_key"] = concert
                if not locked:
                    _clear_pending_display_key(session)
                    session["display_key"] = concert
                elif str(session.get("display_key") or "").strip() == concert:
                    _clear_pending_display_key(session)

    pending_picker = session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY)
    if pending_picker is not None:
        current_s = str(session.get("song_picker_active_source") or "").strip()
        pending_s = str(pending_picker or "").strip()
        if current_s and current_s == pending_s:
            session.pop(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, None)
        elif current_s and current_s != pending_s:
            # Drop only reclaiming pending that snaps an intentional leave:
            # - Catalog seed over live Custom/Composition
            # - Composition ensure over live Custom
            # - Composition ensure over live Catalog while USER_CATALOG leave stamp
            # Still allow pending Custom/Composition over Catalog without the
            # Catalog leave stamp (Catalog bounce mid Custom→Composition).
            pending_is_catalog = pending_s.startswith("Song Selection")
            pending_is_composition = (
                pending_s == "Composition" or "Composition" in pending_s
            )
            live_is_custom = (
                current_s.startswith("Use Custom") or "Custom Progression" in current_s
            )
            live_is_catalog = current_s.startswith("Song Selection")
            user_catalog_leave = bool(session.get("_user_chose_catalog_music_source"))
            reclaim = (
                (pending_is_catalog and not live_is_catalog)
                or (pending_is_composition and live_is_custom)
                or (pending_is_composition and live_is_catalog and user_catalog_leave)
            )
            if reclaim:
                session.pop(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, None)
            elif not locked:
                session.pop(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, None)
                session["song_picker_active_source"] = pending_picker
        elif not locked:
            session.pop(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, None)
            session["song_picker_active_source"] = pending_picker

    for widget_key, pending_key in _PENDING_FOR_WIDGET_KEY.items():
        if widget_key in {"display_key", "song_picker_active_source"}:
            continue
        pending = session.get(pending_key)
        if pending is None:
            continue
        current = session.get(widget_key)
        if current is not None and str(current) == str(pending):
            session.pop(pending_key, None)
            continue
        if widget_key == "improv_jam_key":
            session[widget_key] = pending
            live_dk = str(session.get("display_key") or "").strip()
            if str(session.get(widget_key) or "").strip() == str(pending).strip() and live_dk == str(pending).strip():
                session.pop(pending_key, None)
            continue
        if locked:
            continue
        session.pop(pending_key, None)
        session[widget_key] = pending

    if not locked:
        prefix = "_pending_widget_"
        for pending_key in list(session.keys()):
            if not str(pending_key).startswith(prefix):
                continue
            widget_key = str(pending_key)[len(prefix) :]
            pending = session.get(pending_key)
            if pending is None:
                continue
            current = session.get(widget_key)
            if current is not None and str(current) == str(pending):
                session.pop(pending_key, None)
                continue
            session.pop(pending_key, None)
            session[widget_key] = pending
        session.pop(PENDING_WIDGET_ASSIGN_DIAG_KEY, None)


__all__ = [
    "PENDING_CREATIVE_LAB_MODE_KEY",
    "PENDING_CUSTOM_WORKSPACE_PRACTICE_KEY",
    "PENDING_IMPROV_ENTRY_MODE_KEY",
    "PENDING_IMPROV_INTELLIGENCE_TAB_KEY",
    "PENDING_IMPROV_JAM_BPM_KEY",
    "PENDING_IMPROV_JAM_KEY",
    "PENDING_IMPROV_JAM_MOOD_KEY",
    "PENDING_IMPROV_ENSEMBLE_KEY",
    "PENDING_IMPROV_JAM_STYLE_KEY",
    "PENDING_IMPROV_STYLE_BPM_KEY",
    "PENDING_IMPROV_STYLE_KEY",
    "PENDING_CHART_IN_INSTRUMENT_KEY",
    "PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY",
    "PENDING_TRANSPOSING_INSTRUMENT_KEY",
    "PENDING_WIDGET_ASSIGN_DIAG_KEY",
    "PENDING_INSTRUMENT_KEY",
    "WIDGET_BOUND_KEYS",
    "apply_pending_widget_hydrates",
    "reconcile_practice_key_fields",
    "safe_assign_display_key",
    "safe_session_assign",
    "widgets_likely_instantiated",
]
