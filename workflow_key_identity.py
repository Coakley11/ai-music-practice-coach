"""Atomic practice key identity derived from the active workflow blob (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowKeyIdentity:
    workflow_owner: str
    workflow_session_id: str
    practice_tonic: str
    practice_mode: str
    practice_key_token: str
    practice_label: str
    source: str


def _identity_from_blob(owner: str, session_id: str, blob: Any, *, source: str) -> WorkflowKeyIdentity:
    from music_theory import format_key_label_from_parts, key_center_token

    pt = str(blob.keys.practice_tonic or "C").strip() or "C"
    pm = str(blob.keys.practice_mode or "major").strip().lower() or "major"
    token = key_center_token(pt, pm)
    label = format_key_label_from_parts(pt, pm)
    return WorkflowKeyIdentity(
        workflow_owner=str(owner or ""),
        workflow_session_id=str(session_id or ""),
        practice_tonic=pt,
        practice_mode=pm,
        practice_key_token=token,
        practice_label=label,
        source=source,
    )


def active_workflow_owns_practice_key(session: dict[str, Any]) -> bool:
    """True when practice key must come from the active workflow blob, not catalog/session projection."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {
            "style_jam",
            "jam_session_generator",
            "mission_jam",
            "song_based_improvisation",
        }:
            return True
    except ImportError:
        pass
    try:
        from backing_workflow_context import workflow_is_generated

        if workflow_is_generated(session):
            return True
    except ImportError:
        pass
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key

        if generated_jam_owns_practice_key(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing":
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None and str(ctx.source or "") == "entry_jam":
                return True
        except ImportError:
            pass
    return False


def generated_workflow_owns_practice_key(session: dict[str, Any]) -> bool:
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {"style_jam", "jam_session_generator"}:
            return True
    except ImportError:
        pass
    try:
        from backing_workflow_context import workflow_is_generated

        return bool(workflow_is_generated(session))
    except ImportError:
        return False


def resolve_active_workflow_key_identity(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    """Authoritative tonic + mode + token from active owner blob."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
    except ImportError:
        return None
    ptr = get_active_workflow_pointer(session)
    if ptr is None or not str(ptr.workflow_owner or "").strip():
        return None
    owner = str(ptr.workflow_owner or "")
    sid = str(ptr.workflow_session_id or "")
    blob = get_workflow_blob(session, owner, sid)
    if blob is None and owner == "mission_jam":
        try:
            from music_workflow_song_practice import mirror_mission_keys_from_song_blob, song_practice_blob

            mirror_mission_keys_from_song_blob(session)
            parent = song_practice_blob(session)
            if parent is not None:
                blob = get_workflow_blob(session, owner, sid)
        except ImportError:
            pass
    if blob is None:
        return None
    return _identity_from_blob(owner, sid, blob, source="active_workflow_blob")


def resolve_song_practice_key_identity(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    try:
        from music_workflow_song_practice import song_based_blob_session_id, song_practice_blob

        song = song_practice_blob(session)
        if song is None:
            return None
        sid = song_based_blob_session_id(session)
        return _identity_from_blob("song_based_improvisation", sid, song, source="song_practice_blob")
    except ImportError:
        return None


def resolve_practice_key_identity_for_ui(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    """Single resolver for sidebar, backing header, missions, and notation consumers."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer
    except ImportError:
        ptr = None
    else:
        ptr = get_active_workflow_pointer(session)
    owner = str(ptr.workflow_owner or "") if ptr else ""
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    if owner == "mission_jam" or tab == "Missions":
        song_ident = resolve_song_practice_key_identity(session)
        if song_ident is not None:
            return song_ident
    if generated_workflow_owns_practice_key(session):
        gen_ident = resolve_active_workflow_key_identity(session)
        if gen_ident is not None:
            return gen_ident
    if owner in {"song_based_improvisation", "mission_jam", "regular_catalog_backing", "regular_custom_backing"}:
        song_ident = resolve_song_practice_key_identity(session)
        if song_ident is not None:
            return song_ident
    return resolve_active_workflow_key_identity(session)


def apply_practice_key_identity_to_session(
    session: dict[str, Any],
    ident: WorkflowKeyIdentity,
    *,
    source: str,
    widget_safe: bool = True,
) -> None:
    """Project atomic identity into display/concert + owner widget keys."""
    token = ident.practice_key_token
    try:
        from session_widget_safe import safe_assign_display_key, safe_session_assign

        safe_assign_display_key(session, token, widget_safe=widget_safe)
        if ident.workflow_owner == "jam_session_generator":
            from creative_key_sync import IMPROV_JAM_KEY_TRACKER, PENDING_IMPROV_JAM_KEY

            session[PENDING_IMPROV_JAM_KEY] = token
            session[IMPROV_JAM_KEY_TRACKER] = token
            safe_session_assign(session, "improv_jam_key", token, widget_safe=widget_safe)
        elif ident.workflow_owner == "style_jam":
            from creative_key_sync import IMPROV_STYLE_KEY_TRACKER, PENDING_IMPROV_STYLE_KEY

            session[PENDING_IMPROV_STYLE_KEY] = token
            session[IMPROV_STYLE_KEY_TRACKER] = token
            safe_session_assign(session, "improv_style_key", token, widget_safe=widget_safe)
    except ImportError:
        session["display_key"] = token
        session["concert_key"] = token
        session["_pending_display_key"] = token
        if ident.workflow_owner == "jam_session_generator":
            session["improv_jam_key"] = token
        elif ident.workflow_owner == "style_jam":
            session["improv_style_key"] = token
    session["_workflow_practice_key_identity_source"] = source


__all__ = [
    "WorkflowKeyIdentity",
    "active_workflow_owns_practice_key",
    "apply_practice_key_identity_to_session",
    "generated_workflow_owns_practice_key",
    "resolve_active_workflow_key_identity",
    "resolve_practice_key_identity_for_ui",
    "resolve_song_practice_key_identity",
]
