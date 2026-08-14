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


def normalize_user_practice_key_selection(raw: str, *, default_mode: str = "major") -> tuple[str, str, str]:
    """Parse sidebar/control label into (tonic, mode, token) atomically."""
    from music_theory import format_key_label_from_parts, key_center_token, split_key_center

    text = str(raw or "").strip()
    if not text:
        text = "C"
    if text.lower().endswith(" major"):
        tonic, _ = split_key_center(text)
        mode = "major"
    elif text.lower().endswith(" minor"):
        tonic, _ = split_key_center(text)
        mode = "minor"
    else:
        tonic, mode = split_key_center(text)
        if mode not in {"major", "minor"}:
            mode = str(default_mode or "major").strip().lower() or "major"
    token = key_center_token(tonic, mode)
    return tonic, mode, token


def song_or_mission_workflow_owns_practice_key(session: dict[str, Any]) -> bool:
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    if tab in {
        "Missions",
        "Song-Based Improvisation",
        "Phrase / Motif",
        "Harmony Map",
        "Live Coach",
        "Metrics & AI",
    }:
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(ctx.source or "") in {"mission", "song_improv", "regular_song"}:
            return True
    except ImportError:
        pass
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {
            "mission_jam",
            "song_based_improvisation",
            "regular_catalog_backing",
            "regular_custom_backing",
        }:
            return True
    except ImportError:
        pass
    return False


def fixed_practice_key_projection_blocked(session: dict[str, Any]) -> bool:
    """Catalog fixed-key family must not override generated jam / explicit song practice blob."""
    if generated_workflow_owns_practice_key(session):
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(ctx.source or "") == "entry_jam":
            return True
    except ImportError:
        pass
    if song_or_mission_workflow_owns_practice_key(session):
        try:
            if resolve_song_practice_key_token(session):
                return True
        except ImportError:
            pass
    return False


def resolve_song_practice_key_token(session: dict[str, Any]) -> str:
    try:
        from music_workflow_song_practice import resolve_song_practice_key_token as _tok

        return str(_tok(session) or "").strip()
    except ImportError:
        ident = resolve_song_practice_key_identity(session)
        return ident.practice_key_token if ident else ""


def diagnose_generated_key_identity_drift(session: dict[str, Any]) -> dict[str, Any]:
    """Compare generated artifact/snapshot identity vs active blob vs UI projection."""
    out: dict[str, Any] = {"drift": False, "violations": []}
    if not generated_workflow_owns_practice_key(session):
        return out
    blob_ident = resolve_active_workflow_key_identity(session)
    ui_ident = resolve_practice_key_identity_for_ui(session)
    if blob_ident is None:
        return out
    if ui_ident and (
        ui_ident.practice_tonic != blob_ident.practice_tonic
        or ui_ident.practice_mode != blob_ident.practice_mode
    ):
        out["drift"] = True
        out["violations"].append(
            f"ui_vs_blob:{ui_ident.practice_key_token}!={blob_ident.practice_key_token}"
        )
    try:
        from generated_workflow_artifact import peek_backing_owner_artifact_snapshot

        snap = peek_backing_owner_artifact_snapshot(session)
        if snap is not None:
            st = str(snap.practice_tonic or "")
            sm = str(snap.practice_mode or "major").strip().lower()
            if st != blob_ident.practice_tonic or sm != blob_ident.practice_mode:
                out["drift"] = True
                out["violations"].append("artifact_vs_blob_mode_tonic_mismatch")
    except ImportError:
        pass
    return out


def resolve_song_practice_key_identity(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    try:
        from music_workflow_song_practice import song_based_blob_session_id, song_practice_blob

        song = song_practice_blob(session)
        if song is None:
            return None
        sid = song_based_blob_session_id(session)
        return _identity_from_blob("song_based_improvisation", sid, song, source="song_based_blob_practice_key")
    except ImportError:
        return None


def _identity_from_live_practice_key(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    """Full tonic+mode from live Practice Key — used only when song/mission owns and blob is absent."""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return None
    from music_theory import format_key_label_from_parts, key_center_token, split_key_center

    tonic, mode = split_key_center(live)
    if mode not in {"major", "minor"}:
        mode = "major"
    token = key_center_token(tonic, mode)
    sid = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    try:
        from music_workflow_song_practice import song_based_blob_session_id

        sid = song_based_blob_session_id(session) or sid
    except ImportError:
        pass
    return WorkflowKeyIdentity(
        workflow_owner="song_based_improvisation",
        workflow_session_id=sid,
        practice_tonic=tonic,
        practice_mode=mode,
        practice_key_token=token,
        practice_label=format_key_label_from_parts(tonic, mode),
        source="live_practice_display_key",
    )


def resolve_practice_key_identity_for_ui(session: dict[str, Any]) -> WorkflowKeyIdentity | None:
    """Single resolver for sidebar, backing header, missions, and notation consumers."""
    ctx_source = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(ctx.source or "").strip()
    except ImportError:
        pass
    song_owns = ctx_source == "mission" or (
        song_or_mission_workflow_owns_practice_key(session) and ctx_source != "entry_jam"
    )
    if song_owns:
        if not session.get("_missions_parent_key_hydrate_guard"):
            session["_missions_parent_key_hydrate_guard"] = True
            try:
                from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

                ensure_missions_parent_practice_key_hydrated(session)
            except ImportError:
                pass
            finally:
                session.pop("_missions_parent_key_hydrate_guard", None)
        song_ident = resolve_song_practice_key_identity(session)
        if song_ident is not None:
            return song_ident
        live_ident = _identity_from_live_practice_key(session)
        if live_ident is not None:
            return live_ident
        return None
    if generated_workflow_owns_practice_key(session) and ctx_source != "mission":
        gen_ident = resolve_active_workflow_key_identity(session)
        if gen_ident is not None and str(gen_ident.workflow_owner or "") in {
            "style_jam",
            "jam_session_generator",
        }:
            return gen_ident
        if gen_ident is not None and ctx_source == "entry_jam":
            return gen_ident
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        owner = str(ptr.workflow_owner or "") if ptr else ""
    except ImportError:
        owner = ""
    if owner in {"song_based_improvisation", "mission_jam", "regular_catalog_backing", "regular_custom_backing"}:
        song_ident = resolve_song_practice_key_identity(session)
        if song_ident is not None:
            return song_ident
        live_ident = _identity_from_live_practice_key(session)
        if live_ident is not None:
            return live_ident
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
    "diagnose_generated_key_identity_drift",
    "fixed_practice_key_projection_blocked",
    "generated_workflow_owns_practice_key",
    "normalize_user_practice_key_selection",
    "resolve_active_workflow_key_identity",
    "resolve_practice_key_identity_for_ui",
    "resolve_song_practice_key_identity",
    "resolve_song_practice_key_token",
    "song_or_mission_workflow_owns_practice_key",
]
