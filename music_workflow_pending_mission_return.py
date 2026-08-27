"""Pre-widget Mission return from Backing (Return to Mission)."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal

from mission_return_destination import (
    MISSION_CANONICAL_RETURN_DESTINATION_KEY,
    peek_mission_return_destination,
)

PENDING_MISSION_RETURN_KEY = "_music_pending_mission_return_handoff"
PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY = "_music_pending_mission_return_consumed_token"
PENDING_MISSION_RETURN_RERUN_SEQ_KEY = "_music_pending_mission_return_rerun_for_seq"
PENDING_MISSION_RETURN_RERUN_DIAG_KEY = "_music_pending_mission_return_rerun_diag"
PENDING_MISSION_RETURN_USER_MESSAGE_KEY = "_music_pending_mission_return_user_message"

ConsumePhase = Literal["applied", "skipped", "already_consumed"]


def _consume_token(req: dict[str, Any]) -> str:
    return str(req.get("consume_token") or req.get("return_token") or "")


def _next_seq(session: dict[str, Any]) -> int:
    raw = session.get(PENDING_MISSION_RETURN_KEY)
    prev = int(raw.get("request_seq") or 0) if isinstance(raw, dict) else 0
    return prev + 1


def queue_pending_mission_return_from_backing(session: dict[str, Any]) -> dict[str, Any] | None:
    # Refresh sealed dest from live Mission Backing musical state before queueing.
    # PK mutations on Backing update the dest; this is a last-line safety net so
    # Return never re-applies a pre-Backing Cm snapshot over live Dbm.
    try:
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if live:
            from mission_return_destination import sync_mission_return_destination_after_practice_key_change

            sync_mission_return_destination_after_practice_key_change(
                session, new_key=live, from_key=""
            )
    except ImportError:
        pass
    dest = peek_mission_return_destination(session)
    if not isinstance(dest, dict) or not str(dest.get("mission_id") or "").strip():
        return None
    seq = _next_seq(session)
    req = {
        "request_seq": seq,
        "return_destination": copy.deepcopy(dest),
        "mission_id": str(dest.get("mission_id") or ""),
        "mission_session_id": str(dest.get("mission_session_id") or ""),
        "handoff_mode": str(dest.get("handoff_mode") or ""),
        "with_practice_lick": bool(dest.get("with_practice_lick")),
        "destination_page": str(dest.get("destination_page") or "creative"),
        "creative_tab": str(dest.get("creative_tab") or "Missions"),
        "return_token": str(dest.get("return_token") or ""),
    }
    req["consume_token"] = f"return:{req['return_token']}:seq={seq}"
    session[PENDING_MISSION_RETURN_KEY] = req
    session.pop(PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY, None)
    session.pop(PENDING_MISSION_RETURN_RERUN_DIAG_KEY, None)
    session.pop(PENDING_MISSION_RETURN_USER_MESSAGE_KEY, None)
    try:
        from music_mission_return_handoff_trace import log_mission_return_queued

        log_mission_return_queued(session, req)
    except ImportError:
        pass
    return req


def should_request_mission_return_rerun(session: dict[str, Any]) -> bool:
    pending = session.get(PENDING_MISSION_RETURN_KEY)
    if not isinstance(pending, dict):
        return False
    seq = pending.get("request_seq")
    if seq is None:
        return True
    if session.get(PENDING_MISSION_RETURN_RERUN_SEQ_KEY) == seq:
        return False
    session[PENDING_MISSION_RETURN_RERUN_SEQ_KEY] = seq
    return True


def build_mission_return_rerun_fingerprint(session: dict[str, Any], pending: dict[str, Any]) -> str:
    parts = {
        "kind": "pending_mission_return_handoff",
        "request_seq": pending.get("request_seq"),
        "consume_token": str(pending.get("consume_token") or ""),
        "return_token": str(pending.get("return_token") or ""),
        "mission_id": str(pending.get("mission_id") or ""),
        "studio_page": str(session.get("studio_page") or ""),
    }
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def request_pending_mission_return_rerun(st_module: Any, session: dict[str, Any]) -> bool:
    pending = session.get(PENDING_MISSION_RETURN_KEY)
    if not isinstance(pending, dict):
        return False
    if not should_request_mission_return_rerun(session):
        session[PENDING_MISSION_RETURN_RERUN_DIAG_KEY] = {
            "status": "rerun_already_requested_for_seq",
            "request_seq": pending.get("request_seq"),
        }
        return False
    fp = build_mission_return_rerun_fingerprint(session, pending)
    rerun_sent = False
    try:
        from music_app_rerun import request_app_rerun

        rerun_sent = bool(
            request_app_rerun(
                st_module,
                session,
                reason="pending_mission_return_handoff",
                stage="mission_return_pre_widget",
                fingerprint=fp,
            )
        )
    except ImportError:
        pass
    try:
        from music_mission_return_handoff_trace import log_mission_return_rerun

        log_mission_return_rerun(session, allowed=rerun_sent, fingerprint=fp)
    except ImportError:
        pass
    if not rerun_sent:
        session[PENDING_MISSION_RETURN_RERUN_DIAG_KEY] = {
            "status": "rerun_guard_rejected",
            "request_seq": pending.get("request_seq"),
            "fingerprint": fp,
        }
        session[PENDING_MISSION_RETURN_USER_MESSAGE_KEY] = (
            "Return to Mission is queued but navigation was paused to prevent a rerun loop. "
            "Refresh the page to continue."
        )
    return rerun_sent


def _apply_return_destination_session_fields(session: dict[str, Any], dest: dict[str, Any]) -> None:
    mission_id = str(dest.get("mission_id") or "").strip()
    if mission_id:
        session["improv_active_mission"] = mission_id
        session["improv_mission_pick"] = mission_id
    section = str(dest.get("section_label") or "").strip()
    chord = str(dest.get("chord_symbol") or "").strip()
    if section:
        session["ii_selected_section"] = section
        session["II_SELECTED_SECTION"] = section
    if chord:
        session["ii_selected_chord"] = chord
        session["II_SELECTED_CHORD"] = chord
    try:
        raw_idx = dest.get("chord_index")
        if raw_idx is not None and str(raw_idx).strip() != "":
            idx = int(raw_idx)
            session["ii_selected_chord_index"] = idx
            if section and chord:
                session["ii_selected_chord_label"] = f"{section} · {chord}"
    except (TypeError, ValueError):
        pass
    notes = dest.get("example_notes")
    midi = dest.get("example_midi")
    if isinstance(notes, list) and notes:
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY
        except ImportError:
            MISSION_EXAMPLE_KEY = "improv_mission_example"
        raw = session.get(MISSION_EXAMPLE_KEY)
        raw = dict(raw) if isinstance(raw, dict) else {}
        motif = dict(raw.get("motif") or {})
        motif["notes"] = [str(n) for n in notes]
        if isinstance(midi, list) and midi:
            motif["midi"] = [int(m) for m in midi]
        if chord:
            motif["chord"] = chord
            raw["chord"] = chord
        raw["motif"] = motif
        session[MISSION_EXAMPLE_KEY] = raw
    # Return restores sealed selection; a later tile click must outrank this.
    session.pop("_mission_chord_click_authority", None)
    pick = str(dest.get("song_pick_key") or "").strip()
    if pick:
        session["active_catalog_pick_key"] = pick
    concert = str(dest.get("concert_key") or dest.get("concert_tonic") or "").strip()
    display = str(dest.get("display_key") or "").strip()
    if concert or display:
        key_tok = str(display or concert).strip()
        try:
            from session_widget_safe import safe_assign_display_key

            safe_assign_display_key(session, key_tok, widget_safe=True)
        except ImportError:
            if concert:
                session["concert_key"] = concert
            if display:
                session["display_key"] = display
                session["_pending_display_key"] = display
        # Persist sticky Practice Key for the Mission song pick so Missions hydrate
        # does not re-seal the pre-Backing Cm after Return.
        if key_tok and pick:
            try:
                from songs.practice_key_state import set_practice_concert_key

                set_practice_concert_key(session, key_tok, pick_key=pick)
            except ImportError:
                pass
        try:
            from music_workflow_song_practice import (
                ensure_song_practice_blob_for_active_song,
                mirror_mission_keys_from_song_blob,
            )

            ensure_song_practice_blob_for_active_song(session, practice_key=key_tok)
            mirror_mission_keys_from_song_blob(session)
        except ImportError:
            pass
        # Force Creative sidebar widget key so Live Coach → Missions cannot
        # re-instantiate a stale pre-Backing Cm from Streamlit widget state.
        try:
            from songs.key_state import LAST_DISPLAY_KEY, PENDING_DISPLAY_KEY

            session[PENDING_DISPLAY_KEY] = key_tok
            session[LAST_DISPLAY_KEY] = key_tok
            if not session.get("_streamlit_widgets_locked_this_run"):
                session["display_key"] = key_tok
        except ImportError:
            session["_pending_display_key"] = key_tok
            session["display_key"] = key_tok
    tab = str(dest.get("creative_tab") or "Missions")
    try:
        from session_widget_safe import PENDING_IMPROV_INTELLIGENCE_TAB_KEY, safe_session_assign

        safe_session_assign(session, "improv_intelligence_tab", tab, widget_safe=True)
        session[PENDING_IMPROV_INTELLIGENCE_TAB_KEY] = tab
        session["creative_improv_intelligence_tab"] = tab
    except ImportError:
        session["improv_intelligence_tab"] = tab
        session["creative_improv_intelligence_tab"] = tab
    session["creative_lab_analysis_mode"] = "Improvisation Intelligence"
    session["creative_lab_last_mode"] = "Improvisation Intelligence"
    session["improv_entry_mode"] = str(session.get("improv_entry_mode") or "Song-Based Improvisation")


def _mission_return_restoration_verified(session: dict[str, Any], dest: dict[str, Any]) -> bool:
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "creative":
        return False
    tab = str(session.get("improv_intelligence_tab") or "").strip()
    pending_tab = str(session.get("_pending_improv_intelligence_tab") or "").strip()
    if tab != "Missions" and pending_tab != "Missions":
        return False
    mid = str(dest.get("mission_id") or "").strip()
    if mid:
        active = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
        if active and active != mid:
            return False
    # Chord spelling may drift (Gsus4 ↔ G) after Mission Backing projection /
    # Custom GA restore. Page + Missions tab + mission_id are enough to accept.
    return True


def consume_pending_mission_return_handoff(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    pending = session.get(PENDING_MISSION_RETURN_KEY)
    if not isinstance(pending, dict):
        return "skipped"
    token = _consume_token(pending)
    if session.get(PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY) == token:
        session.pop(PENDING_MISSION_RETURN_KEY, None)
        return "already_consumed"

    dest = pending.get("return_destination")
    if not isinstance(dest, dict):
        session.pop(PENDING_MISSION_RETURN_KEY, None)
        return "skipped"

    try:
        from music_mission_return_handoff_trace import log_mission_return_consume

        log_mission_return_consume(
            session,
            phase="start",
            detail={
                "studio_page": session.get("studio_page"),
                "mission_id": dest.get("mission_id"),
                "handoff_mode": dest.get("handoff_mode"),
                "with_practice_lick": dest.get("with_practice_lick"),
            },
        )
    except ImportError:
        pass

    activation_ok = True
    try:
        from music_workflow_activation import activate_workflow_simple

        result = activate_workflow_simple(
            session,
            "mission_jam",
            activation_source="return_from_backing",
            page_route="creative",
            return_route="backing",
            navigation_intent="return_to_mission",
            persist_policy="durable_handoff",
        )
        activation_ok = bool(result.ok)
    except ImportError:
        activation_ok = False

    alignment_ok = True
    try:
        from mission_backing_alignment import apply_pending_mission_backing_alignment

        alignment_ok = bool(apply_pending_mission_backing_alignment(session, dest))
    except ImportError:
        alignment_ok = False

    # Soft-fail under Custom GA / owner mismatch: still return to Missions with the
    # sealed destination. Hard-blocking left users stuck on Mission Backing with no
    # warning when activate/align failed after an explicit Return click.
    if not activation_ok or not alignment_ok:
        session["_music_pending_mission_return_error"] = {
            "activation_ok": activation_ok,
            "alignment_ok": alignment_ok,
            "token": token,
            "soft_continue": True,
        }
        try:
            from music_mission_return_handoff_trace import log_mission_return_consume

            log_mission_return_consume(
                session,
                phase="soft_continue",
                detail=session["_music_pending_mission_return_error"],
            )
        except ImportError:
            pass

    _apply_return_destination_session_fields(session, dest)

    try:
        from backing_context import get_backing_context
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            _clear_creative_page_hydrate_flags,
            restore_session_widgets_from_backing_context,
        )

        ctx = get_backing_context(session)
        _clear_creative_page_hydrate_flags(session)
        session[CREATIVE_RESTORE_FROM_BACKING_KEY] = True
        if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
            restore_session_widgets_from_backing_context(session, ctx, widget_safe=True)
            # restore_session_widgets may push stale ctx PK/chord (pre-Backing Cm).
            # Sealed return destination (synced on Mission Backing PK change) wins.
            _apply_return_destination_session_fields(session, dest)
    except ImportError:
        session["_creative_restore_from_backing"] = True

    try:
        from mission_practice_context import refresh_mission_practice_context

        refresh_mission_practice_context(session)
    except ImportError:
        pass

    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(session, "creative")
    except ImportError:
        session["studio_page"] = "creative"

    if not _mission_return_restoration_verified(session, dest):
        session["_music_pending_mission_return_error"] = {
            "reason": "restoration_incomplete",
            "studio_page": session.get("studio_page"),
            "token": token,
        }
        try:
            from music_mission_return_handoff_trace import log_mission_return_consume

            log_mission_return_consume(
                session,
                phase="navigation_failed",
                detail=session["_music_pending_mission_return_error"],
            )
        except ImportError:
            pass
        return "skipped"

    session[PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY] = token
    session.pop(PENDING_MISSION_RETURN_KEY, None)
    try:
        from music_mission_return_handoff_trace import log_mission_return_consume

        log_mission_return_consume(
            session,
            phase="applied",
            detail={
                "token": token,
                "mission_id": dest.get("mission_id"),
                "studio_page": session.get("studio_page"),
            },
        )
    except ImportError:
        pass
    return "applied"


def handle_return_to_mission_click(st_module: Any, session: dict[str, Any]) -> None:
    """Queue typed return + one guarded rerun; no post-widget workflow projection."""
    try:
        from backing_context import get_backing_context
        from mission_return_destination import peek_mission_return_destination

        ctx = get_backing_context(session)
        dest = peek_mission_return_destination(session) or {}
        try:
            from music_mission_return_handoff_trace import log_mission_return_click

            log_mission_return_click(
                session,
                detail={
                    "studio_page": session.get("studio_page"),
                    "backing_source": str(getattr(ctx, "source", "") if ctx else ""),
                    "handoff_mode": dest.get("handoff_mode"),
                    "with_practice_lick": dest.get("with_practice_lick"),
                    "return_route": dest.get("destination_page"),
                    "mission_id": dest.get("mission_id"),
                    "mission_session_id": dest.get("mission_session_id"),
                    "section": dest.get("section_label"),
                    "chord": dest.get("chord_symbol"),
                    "song_pick_key": dest.get("song_pick_key"),
                },
            )
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
        try:
            from music_nav_dedupe import save_page_snapshot_deduped

            save_page_snapshot_deduped(session, "creative")
        except ImportError:
            save_page_snapshot(session, "creative")
    except ImportError:
        pass

    # Prevent a leftover Mission→Backing pending handoff from re-opening Backing
    # on the next pre-widget consume after Return has queued Creative.
    try:
        from music_workflow_pending_backing_handoff import clear_pending_backing_workflow_handoff

        clear_pending_backing_workflow_handoff(session)
    except ImportError:
        session.pop("_music_pending_backing_workflow_handoff", None)
    try:
        from music_workflow_mission_backing_click import MISSION_BACKING_CLICK_INTENT_KEY

        session.pop(MISSION_BACKING_CLICK_INTENT_KEY, None)
    except ImportError:
        session.pop("_music_mission_backing_click_intent", None)

    req = queue_pending_mission_return_from_backing(session)
    if req is None:
        try:
            st_module.warning(
                "Return to Mission could not find the saved mission context. "
                "Open Creative → Missions manually."
            )
        except Exception:
            pass
        return

    if not request_pending_mission_return_rerun(st_module, session):
        msg = session.pop(PENDING_MISSION_RETURN_USER_MESSAGE_KEY, None)
        if msg:
            try:
                st_module.warning(str(msg))
            except Exception:
                pass
        # Last-resort sync navigate when guarded rerun is blocked — still leave Backing.
        try:
            phase = consume_pending_mission_return_handoff(session, st=st_module)
            if phase == "applied":
                try:
                    from music_app_rerun import request_app_rerun

                    request_app_rerun(
                        st_module,
                        session,
                        reason="pending_mission_return_fallback_consume",
                        stage="mission_return_click_fallback",
                    )
                except ImportError:
                    try:
                        st_module.rerun()
                    except Exception:
                        pass
        except Exception:
            pass


__all__ = [
    "PENDING_MISSION_RETURN_KEY",
    "PENDING_MISSION_RETURN_USER_MESSAGE_KEY",
    "consume_pending_mission_return_handoff",
    "handle_return_to_mission_click",
    "queue_pending_mission_return_from_backing",
    "request_pending_mission_return_rerun",
]
