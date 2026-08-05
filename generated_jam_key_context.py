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
    try:
        from creative_key_sync import creative_entry_concert_key, to_major_key_preserve_spelling
    except ImportError:
        creative_entry_concert_key = lambda s: str(s.get("improv_jam_key") or s.get("improv_style_key") or "C")  # type: ignore
        to_major_key_preserve_spelling = lambda k: k  # type: ignore

    tonic = str(practice_key or "").strip()
    if not tonic:
        tonic = to_major_key_preserve_spelling(creative_entry_concert_key(session) or "C")
    else:
        tonic = to_major_key_preserve_spelling(tonic)
    session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
        "generated_session_id": _jam_session_id(session),
        "practice_tonic": tonic,
        "practice_mode": "major",
        "key_owner": "jam_session_generator" if "Generator" in entry else "entry_jam",
        "sidebar_key_list_mode": "major",
        "entry_mode": entry,
    }
    session["_generated_jam_key_owner_active"] = True
    try:
        from creative_key_sync import apply_creative_concert_key

        apply_creative_concert_key(session, tonic, source="generated_jam_key_owner")
    except ImportError:
        session["concert_key"] = tonic
        session["display_key"] = tonic
        session["_pending_display_key"] = tonic


def deactivate_generated_jam_key_ownership(session: dict[str, Any], *, pre_widget: bool = False) -> bool:
    """Release generated-jam key ownership and restore song practice key snapshot.

    Returns False when widgets are locked — caller must defer to pre-widget reconciliation.
    """
    if not pre_widget:
        try:
            from session_widget_safe import widgets_likely_instantiated

            if widgets_likely_instantiated(session):
                return False
        except ImportError:
            if session.get("_streamlit_widgets_locked_this_run"):
                return False
    snap = session.pop(SONG_PRACTICE_KEY_SNAPSHOT_KEY, None)
    session.pop(GENERATED_JAM_KEY_CONTEXT_KEY, None)
    session.pop("_generated_jam_key_owner_active", None)
    if not isinstance(snap, dict):
        return True
    for key in ("display_key", "concert_key", "practice_concert_key"):
        val = str(snap.get(key) or "").strip()
        if val:
            session[key] = val
    pending = str(snap.get("display_key") or snap.get("concert_key") or "").strip()
    if pending:
        session["_pending_display_key"] = pending
    return True


def generated_jam_owns_practice_key(session: dict[str, Any]) -> bool:
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    if isinstance(raw, dict) and raw.get("key_owner"):
        page = str(session.get("studio_page") or "").strip().lower()
        if page in {"creative", "backing"}:
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
    "snapshot_song_practice_key_if_needed",
]
