"""Sidebar Song-Based / Mission practice key — capture intent + pre-widget apply."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("music.song_practice_key_change")

SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY = "_music_song_practice_key_edit_outcome"


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def sidebar_song_practice_key_mutation_deferred(session: dict[str, Any]) -> bool:
    """True when blob mutation must wait for pre-widget consume."""
    try:
        from music_workflow_pending_song_practice_key_edit import peek_pending_song_practice_key_edit

        if peek_pending_song_practice_key_edit(session):
            return True
    except ImportError:
        pass
    return _widgets_locked(session)


def finalize_sidebar_song_practice_key_after_mutation(
    session: dict[str, Any],
    new_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    """Legacy session + backing sync after canonical practice key commit."""
    session["concert_key"] = new_key
    try:
        from improvisation_missions import MISSIONS_GENERATE_CONTEXT_KEY

        session.pop(MISSIONS_GENERATE_CONTEXT_KEY, None)
        session.pop("_mission_example_output_fp", None)
        session.pop("_mission_example_material_fp", None)
    except ImportError:
        session.pop("_missions_tab_generate_context", None)
    try:
        from mission_practice_context import ensure_mission_practice_context

        ensure_mission_practice_context(session, force=True)
    except ImportError:
        pass
    try:
        from music_workflow_song_practice import rehydrate_full_song_concert_sections

        rehydrate_full_song_concert_sections(session, source="sidebar_song_practice_key_finalize")
    except ImportError:
        pass
    try:
        from music_workflow_legacy_projection import project_active_blob_to_legacy_session
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {"mission_jam", "song_based_improvisation"}:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None:
                project_active_blob_to_legacy_session(session, blob)
    except ImportError:
        pass
    try:
        from backing_context import sync_improv_widgets_from_live_concert_key

        sync_improv_widgets_from_live_concert_key(session)
    except ImportError:
        pass
    try:
        from backing_musical_state import clear_stale_chart_session_keys
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        clear_stale_chart_session_keys(session)
        if st_like is not None:
            invalidate_backing_cache(st_like)
        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    try:
        from creative_key_sync import invalidate_creative_backing_context

        invalidate_creative_backing_context(session)
    except ImportError:
        pass
    try:
        from creative_key_sync import _apply_pending_backing_context_on_page

        _apply_pending_backing_context_on_page(session, st_like=st_like)
    except ImportError:
        pass
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    # Mission Backing PK mutation must update the sealed Return destination so
    # Return-to-Mission restores Dbm (not the pre-Backing Cm snapshot).
    try:
        from backing_context import get_backing_context
        from mission_return_destination import sync_mission_return_destination_after_practice_key_change

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "mission":
            sync_mission_return_destination_after_practice_key_change(
                session,
                new_key=new_key,
                from_key="",
            )
            try:
                from pathlib import Path

                from improvisation_missions import (
                    MISSION_EXAMPLE_KEY,
                    MISSION_PRACTICE_LICK_KEY,
                    parse_abc_k_field,
                )

                ex = session.get(MISSION_EXAMPLE_KEY)
                lick = session.get(MISSION_PRACTICE_LICK_KEY)
                motif = {}
                abc = ""
                if isinstance(ex, dict):
                    motif = dict(ex.get("motif") or {})
                    abc = str(ex.get("abc") or "")
                if isinstance(lick, dict) and not motif.get("midi"):
                    motif = dict(lick)
                    abc = str(lick.get("abc") or abc)
                out = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing"
                out.mkdir(parents=True, exist_ok=True)
                (out / "_mission_midi_abc_diag.json").write_text(
                    __import__("json").dumps(
                        {
                            "new_key": new_key,
                            "display_key": session.get("display_key"),
                            "sealed_dest": (
                                session.get("_music_mission_canonical_return_destination") or {}
                            ).get("display_key"),
                            "chord": session.get("ii_selected_chord"),
                            "notes": motif.get("notes"),
                            "midi": motif.get("midi"),
                            "abc_k": parse_abc_k_field(abc) if abc else "",
                            "abc_len": len(abc),
                            "lick_key_center": (
                                lick.get("key_center") if isinstance(lick, dict) else ""
                            ),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as _diag_exc:
                try:
                    from pathlib import Path

                    out = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing"
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "_mission_midi_abc_diag_err.txt").write_text(
                        repr(_diag_exc), encoding="utf-8"
                    )
                except Exception:
                    pass
    except ImportError:
        pass


def capture_sidebar_song_practice_key_edit_intent(session: dict[str, Any]) -> bool:
    """Sidebar callback — queue only; canonical mutation runs pre-widget next run."""
    requested = str(session.get("display_key") or "").strip()
    if not requested:
        return False
    try:
        from music_workflow_state_store import get_active_workflow_pointer
    except ImportError:
        return False
    ptr = get_active_workflow_pointer(session)
    owner = str(ptr.workflow_owner or "").strip() if ptr else ""
    session_id = str(ptr.workflow_session_id or "").strip() if ptr else ""
    # Mission / SBI Backing must still queue even if the active pointer drifted
    # (e.g. after handoff). Sealed backing source is authoritative for ownership.
    if owner not in {"song_based_improvisation", "mission_jam"}:
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            src = str(getattr(ctx, "source", "") or "").strip() if ctx else ""
            if src == "mission":
                owner = "mission_jam"
                if not session_id:
                    try:
                        from music_workflow_song_practice import mission_blob_session_id

                        session_id = mission_blob_session_id(session)
                    except ImportError:
                        session_id = ""
            elif src == "song_improv":
                owner = "song_based_improvisation"
                if not session_id:
                    try:
                        from music_workflow_song_practice import song_based_blob_session_id

                        session_id = song_based_blob_session_id(session)
                    except ImportError:
                        session_id = ""
        except ImportError:
            pass
    # Creative Missions / SBI workspace (no sealed backing yet) must still queue.
    if owner not in {"song_based_improvisation", "mission_jam"}:
        page = str(session.get("studio_page") or "").strip().lower()
        tab = str(
            session.get("improv_intelligence_tab")
            or session.get("creative_improv_intelligence_tab")
            or ""
        ).strip()
        if page == "creative" and tab == "Missions":
            owner = "mission_jam"
            if not session_id:
                try:
                    from music_workflow_song_practice import mission_blob_session_id

                    session_id = mission_blob_session_id(session)
                except ImportError:
                    session_id = ""
        elif page == "creative" and tab in {
            "Song-Based Improvisation",
            "Phrase / Motif",
            "Harmony Map",
            "Live Coach",
        }:
            owner = "song_based_improvisation"
            if not session_id:
                try:
                    from music_workflow_song_practice import song_based_blob_session_id

                    session_id = song_based_blob_session_id(session)
                except ImportError:
                    session_id = ""
    if owner not in {"song_based_improvisation", "mission_jam"}:
        return False
    try:
        from music_workflow_pending_song_practice_key_edit import queue_pending_song_practice_key_edit

        pending = queue_pending_song_practice_key_edit(
            session,
            selected_key_token=requested,
            workflow_owner=owner,
            workflow_session_id=session_id,
        )
        if not pending:
            return False
        _LOG.info(
            "[song_practice_key_change] intent_captured seq=%s owner=%s key=%s locked=%s",
            pending.get("request_seq"),
            pending.get("workflow_owner"),
            requested,
            _widgets_locked(session),
        )
        return True
    except ImportError:
        return False


def apply_pending_song_practice_key_edit_pre_widget(
    session: dict[str, Any],
    pending: dict[str, Any],
    *,
    st_like: Any | None = None,
) -> bool:
    requested = str(pending.get("selected_key_token") or "").strip()
    if not requested:
        return False
    try:
        from music_workflow_mutation import update_active_practice_key

        result = update_active_practice_key(
            session,
            requested,
            source="sidebar_song_improv",
            transpose_progression=True,
        )
        if not result.ok:
            session[SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY] = {
                "canonical_commit": "FAIL",
                "error_code": result.error_code,
            }
            _LOG.info("[song_practice_key_change] mutation_failed %s", result.error_code)
            return False
    except ImportError:
        return False
    session[SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY] = {"canonical_commit": "SUCCESS"}
    finalize_sidebar_song_practice_key_after_mutation(session, requested, st_like=st_like)
    try:
        from song_creative_focus import retarget_song_creative_focus_after_practice_key_change

        retarget_song_creative_focus_after_practice_key_change(session)
    except ImportError:
        pass
    return True


__all__ = [
    "SONG_PRACTICE_KEY_EDIT_OUTCOME_KEY",
    "apply_pending_song_practice_key_edit_pre_widget",
    "capture_sidebar_song_practice_key_edit_intent",
    "finalize_sidebar_song_practice_key_after_mutation",
    "sidebar_song_practice_key_mutation_deferred",
]
