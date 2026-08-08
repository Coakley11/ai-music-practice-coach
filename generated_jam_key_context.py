"""Generated jam key authority — isolated from catalog song practice key."""

from __future__ import annotations

from typing import Any

GENERATED_JAM_KEY_CONTEXT_KEY = "_generated_jam_key_context"
SONG_PRACTICE_KEY_SNAPSHOT_KEY = "_song_practice_key_snapshot"


def _jam_session_id(session: dict[str, Any]) -> str:
    jam = session.get("improv_jam_session")
    if isinstance(jam, dict) and jam.get("id"):
        return str(jam.get("id"))
    style = str(session.get("improv_jam_style") or session.get("improv_style") or "").strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    return f"{entry}|{style}" if style or entry else entry or "generated_jam"


def _practice_key_from_blob(session: dict[str, Any]) -> tuple[str, str, str]:
    """Return (tonic, mode, sidebar token) from active generated workflow blob."""
    try:
        from music_theory import key_center_token
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if not ptr or str(ptr.workflow_owner or "") not in {"style_jam", "jam_session_generator"}:
            return "", "", ""
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            return "", "", ""
        pt = str(blob.keys.practice_tonic or "C").strip() or "C"
        pm = str(blob.keys.practice_mode or "major").strip().lower() or "major"
        return pt, pm, key_center_token(pt, pm)
    except ImportError:
        return "", "", ""


def refresh_generated_jam_key_context_from_blob(session: dict[str, Any]) -> None:
    """Keep generated-jam key ownership aligned with authoritative blob keys."""
    if not session.get(GENERATED_JAM_KEY_CONTEXT_KEY) and not session.get("_generated_jam_key_owner_active"):
        return
    pt, pm, token = _practice_key_from_blob(session)
    if not token:
        return
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    entry = str(session.get("improv_entry_mode") or (raw.get("entry_mode") if isinstance(raw, dict) else "") or "").strip()
    owner = "jam_session_generator" if "Generator" in entry else "entry_jam"
    session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
        "generated_session_id": _jam_session_id(session),
        "practice_tonic": pt,
        "practice_mode": pm,
        "practice_key_token": token,
        "key_owner": owner,
        "sidebar_key_list_mode": "major" if pm != "minor" else "minor",
        "entry_mode": entry,
    }


def snapshot_song_practice_key_if_needed(session: dict[str, Any]) -> None:
    if isinstance(session.get(SONG_PRACTICE_KEY_SNAPSHOT_KEY), dict):
        return
    session[SONG_PRACTICE_KEY_SNAPSHOT_KEY] = {
        "display_key": str(session.get("display_key") or "").strip(),
        "concert_key": str(session.get("concert_key") or "").strip(),
        "practice_concert_key": str(session.get("practice_concert_key") or "").strip(),
    }


def activate_generated_jam_key_ownership(
    session: dict[str, Any],
    *,
    entry_mode: str = "",
    practice_key: str = "",
) -> None:
    """While generator/entry jam owns creative or backing route, practice key follows generated session."""
    entry = str(entry_mode or session.get("improv_entry_mode") or "").strip()
    if entry not in {"Style Jam Mode", "Jam Session Generator"}:
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is None or str(ctx.source or "") != "entry_jam":
                return
            entry = str(ctx.entry_mode or "").strip()
            if entry not in {"Style Jam Mode", "Jam Session Generator"}:
                return
        except ImportError:
            return

    snapshot_song_practice_key_if_needed(session)
    pt, pm, blob_token = _practice_key_from_blob(session)
    token = blob_token
    if not token:
        try:
            from creative_key_sync import creative_entry_concert_key
            from music_theory import key_center_token, split_key_center

            raw = str(practice_key or creative_entry_concert_key(session) or "C").strip() or "C"
            pt, pm = split_key_center(raw)
            if entry in {"Style Jam Mode", "Jam Session Generator"} and pm != "minor":
                pm = "major"
            token = key_center_token(pt, pm)
        except ImportError:
            token = str(practice_key or "C").strip() or "C"
            pt, pm = token, "major"

    session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
        "generated_session_id": _jam_session_id(session),
        "practice_tonic": pt,
        "practice_mode": pm,
        "practice_key_token": token,
        "key_owner": "jam_session_generator" if "Generator" in entry else "entry_jam",
        "sidebar_key_list_mode": "major" if pm != "minor" else "minor",
        "entry_mode": entry,
    }
    session["_generated_jam_key_owner_active"] = True
    try:
        from creative_key_sync import apply_creative_concert_key

        apply_creative_concert_key(session, token, source="generated_jam_key_owner")
    except ImportError:
        session["concert_key"] = token
        session["display_key"] = token
        session["_pending_display_key"] = token


def deactivate_generated_jam_key_ownership(session: dict[str, Any], *, pre_widget: bool = False) -> bool:
    """Release generated-jam key ownership and restore song practice key snapshot.

    When sidebar widgets are already instantiated, widget-bound keys (``display_key``)
    are restored via ``_pending_display_key`` / ``concert_key`` — never direct assignment.

    Returns False only when ``pre_widget`` is false and widgets are locked (defer caller).
    """
    try:
        from session_widget_safe import reconcile_practice_key_fields, widgets_likely_instantiated

        locked = widgets_likely_instantiated(session)
    except ImportError:
        locked = bool(session.get("_streamlit_widgets_locked_this_run"))

    if locked and not pre_widget:
        return False

    snap = session.pop(SONG_PRACTICE_KEY_SNAPSHOT_KEY, None)
    session.pop(GENERATED_JAM_KEY_CONTEXT_KEY, None)
    session.pop("_generated_jam_key_owner_active", None)
    if not isinstance(snap, dict):
        return True

    authoritative = str(snap.get("display_key") or snap.get("concert_key") or "").strip()
    practice_concert = str(snap.get("practice_concert_key") or authoritative).strip()
    if authoritative:
        try:
            from session_widget_safe import reconcile_practice_key_fields

            reconcile_practice_key_fields(session, authoritative=authoritative)
        except ImportError:
            session["concert_key"] = authoritative
            if not locked:
                session["display_key"] = authoritative
            else:
                try:
                    from songs.key_state import PENDING_DISPLAY_KEY

                    session[PENDING_DISPLAY_KEY] = authoritative
                except ImportError:
                    session["_pending_display_key"] = authoritative
    if practice_concert:
        session["practice_concert_key"] = practice_concert
    pending = authoritative or practice_concert
    if pending and not locked:
        session["_pending_display_key"] = pending
    return True


def generated_jam_owns_practice_key(session: dict[str, Any]) -> bool:
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    if isinstance(raw, dict) and raw.get("key_owner"):
        page = str(session.get("studio_page") or "").strip().lower()
        if page in {"creative", "backing"}:
            try:
                from musical_context_authority import catalog_song_should_own_sidebar_practice_key

                if catalog_song_should_own_sidebar_practice_key(session):
                    return False
            except ImportError:
                pass
            entry = str(session.get("improv_entry_mode") or raw.get("entry_mode") or "").strip()
            if entry not in {"Style Jam Mode", "Jam Session Generator"}:
                return False
            try:
                from backing_workflow_context import workflow_is_generated

                if page == "backing" and not workflow_is_generated(session):
                    return False
            except ImportError:
                pass
            return True
    return False


__all__ = [
    "GENERATED_JAM_KEY_CONTEXT_KEY",
    "SONG_PRACTICE_KEY_SNAPSHOT_KEY",
    "activate_generated_jam_key_ownership",
    "deactivate_generated_jam_key_ownership",
    "generated_jam_owns_practice_key",
    "refresh_generated_jam_key_context_from_blob",
    "snapshot_song_practice_key_if_needed",
]
