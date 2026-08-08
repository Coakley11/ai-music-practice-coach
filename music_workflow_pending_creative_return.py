"""Pre-widget Return to Creative Page from Backing (typed intent + consume)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

PENDING_CREATIVE_RETURN_KEY = "_music_pending_creative_return_handoff"
PENDING_CREATIVE_RETURN_CONSUMED_TOKEN_KEY = "_music_pending_creative_return_consumed_token"
PENDING_CREATIVE_RETURN_RERUN_SEQ_KEY = "_music_pending_creative_return_rerun_for_seq"

ConsumePhase = Literal["applied", "skipped", "already_consumed"]


def _consume_token(req: dict[str, Any]) -> str:
    return str(req.get("consume_token") or "")


def queue_pending_creative_return_from_backing(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from backing_context import get_backing_context
    except ImportError:
        return None
    ctx = get_backing_context(session)
    if ctx is None:
        return None
    prev = session.get(PENDING_CREATIVE_RETURN_KEY)
    seq = int(prev.get("request_seq") or 0) + 1 if isinstance(prev, dict) else 1
    try:
        from backing_source_navigation import seal_creative_return_context_from_backing

        sealed = seal_creative_return_context_from_backing(session, ctx)
    except ImportError:
        sealed = {
            "source": str(getattr(ctx, "source", "") or ""),
            "entry_mode": str(getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or ""),
            "creative_tab": str(
                session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
            ),
            "display_key": str(getattr(ctx, "display_key", "") or getattr(ctx, "concert_key", "") or ""),
            "concert_key": str(getattr(ctx, "concert_key", "") or ""),
            "song_pick": str(session.get("active_catalog_pick_key") or ""),
        }
    req = {
        "request_seq": seq,
        "sealed_context": sealed,
        "consume_token": hashlib.sha256(json.dumps(sealed, sort_keys=True).encode()).hexdigest()[:24],
    }
    session[PENDING_CREATIVE_RETURN_KEY] = req
    session.pop(PENDING_CREATIVE_RETURN_CONSUMED_TOKEN_KEY, None)
    try:
        from creative_return_trace import trace_return_handoff_queued

        trace_return_handoff_queued(session, req)
    except ImportError:
        pass
    return req


def request_pending_creative_return_rerun(st_module: Any, session: dict[str, Any]) -> bool:
    pending = session.get(PENDING_CREATIVE_RETURN_KEY)
    if not isinstance(pending, dict):
        return False
    seq = pending.get("request_seq")
    if session.get(PENDING_CREATIVE_RETURN_RERUN_SEQ_KEY) == seq:
        return False
    session[PENDING_CREATIVE_RETURN_RERUN_SEQ_KEY] = seq
    try:
        from music_app_rerun import request_app_rerun

        return bool(
            request_app_rerun(
                st_module,
                session,
                reason="pending_creative_return_handoff",
                stage="creative_return_pre_widget",
            )
        )
    except ImportError:
        return False


def consume_pending_creative_return_handoff(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    pending = session.get(PENDING_CREATIVE_RETURN_KEY)
    if not isinstance(pending, dict):
        try:
            from creative_return_trace import trace_return_consume_phase

            trace_return_consume_phase(session, "skipped")
        except ImportError:
            pass
        return "skipped"
    sealed = pending.get("sealed_context") if isinstance(pending.get("sealed_context"), dict) else {}
    token = _consume_token(pending)
    if session.get(PENDING_CREATIVE_RETURN_CONSUMED_TOKEN_KEY) == token:
        session.pop(PENDING_CREATIVE_RETURN_KEY, None)
        try:
            from creative_return_trace import trace_return_consume_phase

            trace_return_consume_phase(session, "already_consumed", sealed=sealed)
        except ImportError:
            pass
        return "already_consumed"
    try:
        from backing_source_navigation import CREATIVE_RESTORE_FROM_BACKING_KEY, prepare_return_to_backing_source

        prepare_return_to_backing_source(session)
        session[CREATIVE_RESTORE_FROM_BACKING_KEY] = True
        try:
            from generated_workflow_projection import project_generated_owner_from_active_blob

            project_generated_owner_from_active_blob(session, writer="creative_return_consume")
        except ImportError:
            pass
        try:
            from creative_return_trace import emit_creative_return_trace

            emit_creative_return_trace(session, "ON_RETURN_AFTER_PREPARE_BEFORE_NAV")
        except ImportError:
            pass
    except ImportError:
        try:
            from creative_return_trace import trace_return_consume_phase

            trace_return_consume_phase(session, "skipped", sealed=sealed)
        except ImportError:
            pass
        return "skipped"
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(session, "creative")
    except ImportError:
        session["studio_page"] = "creative"
    try:
        from music_persistent_state import mark_user_navigated_page_this_run

        mark_user_navigated_page_this_run(session, "creative")
    except ImportError:
        pass
    try:
        from creative_key_sync import apply_entry_jam_authoritative_practice_key, entry_jam_practice_key_authority_active

        if entry_jam_practice_key_authority_active(session):
            apply_entry_jam_authoritative_practice_key(session, source="creative_return_entry_jam")
        else:
            from music_workflow_song_practice import sync_session_practice_key_from_song_blob

            sync_session_practice_key_from_song_blob(session, source="creative_return_consume")
    except ImportError:
        try:
            from music_workflow_song_practice import sync_session_practice_key_from_song_blob

            sync_session_practice_key_from_song_blob(session, source="creative_return_consume")
        except ImportError:
            pass
    session[PENDING_CREATIVE_RETURN_CONSUMED_TOKEN_KEY] = token
    session.pop(PENDING_CREATIVE_RETURN_KEY, None)
    try:
        from creative_return_trace import trace_return_consume_phase

        trace_return_consume_phase(session, "applied", sealed=sealed)
    except ImportError:
        pass
    return "applied"


def handle_return_to_creative_click(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from creative_return_trace import trace_return_click_before

        trace_return_click_before(session)
    except ImportError:
        pass
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "backing")
    except ImportError:
        pass
    req = queue_pending_creative_return_from_backing(session)
    if req is None:
        try:
            st_module.warning("Return to Creative could not find backing context.")
        except Exception:
            pass
        return
    phase = consume_pending_creative_return_handoff(session, st=st_module)
    try:
        from creative_return_trace import emit_creative_return_trace

        emit_creative_return_trace(
            session,
            "ON_RETURN_CLICK_AFTER_CONSUME",
            extra={"consume_phase": str(phase or "")},
        )
    except ImportError:
        pass
    if phase == "skipped":
        try:
            st_module.warning("Return to Creative could not apply backing context.")
        except Exception:
            pass
        return
    try:
        from music_restore_phase import mark_page_snapshot_hydrated
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "creative")
        mark_page_snapshot_hydrated(session, "creative")
    except ImportError:
        pass
    try:
        from music_rerun_loop_guard import clear_rerun_loop_block

        clear_rerun_loop_block(session, reason="creative_return_click")
    except ImportError:
        pass
    try:
        from studio_page_route_trace import trace_return_before_rerun, trace_return_rerun_outcome

        trace_return_before_rerun(session, dispatch_local="backing")
    except ImportError:
        pass
    rerun_invoked = False
    fallback_rerun = False
    try:
        from music_app_rerun import request_app_rerun

        rerun_invoked = bool(
            request_app_rerun(
                st_module,
                session,
                reason="creative_return_click",
                stage="post_consume",
            )
        )
        if not rerun_invoked:
            fallback_rerun = True
            st_module.rerun()
    except ImportError:
        try:
            fallback_rerun = True
            st_module.rerun()
        except Exception:
            pass
    try:
        from studio_page_route_trace import trace_return_rerun_outcome

        trace_return_rerun_outcome(
            session,
            rerun_requested=True,
            rerun_invoked=rerun_invoked,
            fallback_rerun=fallback_rerun,
        )
    except ImportError:
        pass
    if str(session.get("studio_page") or "").strip().lower() == "creative":
        try:
            from studio_page_route_trace import trace_post_return_stop_guard

            trace_post_return_stop_guard(session)
        except ImportError:
            pass
        try:
            from music_app_rerun import request_app_stop

            request_app_stop(st_module, session, reason="creative_return_dispatch_guard")
        except ImportError:
            try:
                st_module.stop()
            except Exception:
                pass


__all__ = [
    "PENDING_CREATIVE_RETURN_KEY",
    "consume_pending_creative_return_handoff",
    "handle_return_to_creative_click",
    "queue_pending_creative_return_from_backing",
]
