"""Pre-widget consume for shared SongCreativeFocus chord selection."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any, Literal

_LOG = logging.getLogger("music.song_creative_focus")

PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY = "_music_pending_song_creative_focus_edit"
PENDING_SONG_CREATIVE_FOCUS_CONSUMED_TOKEN_KEY = "_music_pending_song_creative_focus_consumed_token"
PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY = "_music_pending_song_creative_focus_last_diag"

ConsumePhase = Literal["applied", "skipped", "failed", "already_consumed", "invalid"]
_CALLBACK_SOURCE = "song_creative_focus_selector"


def _next_seq(session: dict[str, Any]) -> int:
    raw = session.get(PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY)
    if isinstance(raw, dict):
        return int(raw.get("request_seq") or 0) + 1
    return 1


def clear_pending_song_creative_focus_edit(session: dict[str, Any]) -> None:
    session.pop(PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY, None)


def queue_pending_song_creative_focus_edit(
    session: dict[str, Any],
    *,
    section: str,
    concert_chord: str,
    chord_index: int,
    source_page: str,
    written_chord: str = "",
) -> dict[str, Any] | None:
    from song_creative_focus import build_song_creative_focus, stable_song_id

    chord = str(concert_chord or "").strip()
    if not chord:
        return None
    sid = stable_song_id(session)
    if not sid:
        return None
    focus = build_song_creative_focus(
        session,
        section=section,
        concert_chord=chord,
        chord_index=int(chord_index),
        source_page=source_page,
        written_chord=written_chord,
    )
    seq = _next_seq(session)
    payload = {
        **focus,
        "request_seq": seq,
        "request_token": hashlib.sha256(
            json.dumps({"seq": seq, "sid": sid, "ch": chord, "src": _CALLBACK_SOURCE}, sort_keys=True).encode()
        ).hexdigest()[:24],
        "callback_source": _CALLBACK_SOURCE,
    }
    try:
        from music_workflow_pending_intent_scope import capture_pending_intent_scope

        payload["scope"] = capture_pending_intent_scope(session)
    except ImportError:
        pass
    session[PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY] = payload
    return copy.deepcopy(payload)


def _widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY

        if session.get(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY):
            return False
    except ImportError:
        pass
    try:
        from session_widget_safe import widgets_likely_instantiated

        return bool(widgets_likely_instantiated(session))
    except ImportError:
        return bool(session.get("_streamlit_widgets_locked_this_run"))


def _validate_pending(session: dict[str, Any], pending: dict[str, Any]) -> str | None:
    from song_creative_focus import focus_binding_matches

    if not str(pending.get("request_token") or "").strip():
        return "malformed_request_token"
    if str(pending.get("callback_source") or "") != _CALLBACK_SOURCE:
        return "callback_source_mismatch"
    if not str(pending.get("selected_concert_chord") or "").strip():
        return "invalid_chord"
    if not focus_binding_matches(session, pending):
        return "catalog_pick_mismatch"
    return None


def consume_pending_song_creative_focus_edit(session: dict[str, Any], *, st: Any | None = None) -> ConsumePhase:
    pending = session.get(PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY)
    if not isinstance(pending, dict):
        return "skipped"
    token = str(pending.get("request_token") or "").strip()
    if token and session.get(PENDING_SONG_CREATIVE_FOCUS_CONSUMED_TOKEN_KEY) == token:
        clear_pending_song_creative_focus_edit(session)
        return "already_consumed"
    if _widgets_locked(session):
        return "skipped"
    err = _validate_pending(session, pending)
    if err:
        session[PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY] = {"failed_predicate": err}
        clear_pending_song_creative_focus_edit(session)
        return "invalid"
    try:
        from music_workflow_pending_intent_scope import pending_intent_scope_matches, workflow_mutation_consume_allowed

        allowed, auth_reason = workflow_mutation_consume_allowed(session)
        if not allowed:
            session[PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY] = {"consume_deferred": True, "failed_predicate": auth_reason}
            return "skipped"
        scope_ok, scope_reason = pending_intent_scope_matches(session, pending)
        if not scope_ok:
            clear_pending_song_creative_focus_edit(session)
            session[PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY] = {"failed_predicate": scope_reason}
            return "invalid"
    except ImportError:
        pass
    try:
        from song_creative_focus_change import apply_pending_song_creative_focus_pre_widget

        ok = apply_pending_song_creative_focus_pre_widget(session, pending)
    except ImportError:
        ok = False
    if not ok:
        clear_pending_song_creative_focus_edit(session)
        return "failed"
    if token:
        session[PENDING_SONG_CREATIVE_FOCUS_CONSUMED_TOKEN_KEY] = token
    clear_pending_song_creative_focus_edit(session)
    session[PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY] = {"result": "applied"}
    return "applied"


__all__ = [
    "PENDING_SONG_CREATIVE_FOCUS_EDIT_KEY",
    "PENDING_SONG_CREATIVE_FOCUS_CONSUMED_TOKEN_KEY",
    "PENDING_SONG_CREATIVE_FOCUS_LAST_DIAG_KEY",
    "clear_pending_song_creative_focus_edit",
    "consume_pending_song_creative_focus_edit",
    "queue_pending_song_creative_focus_edit",
]
