"""Issue 64 G26: reopening a project brings back the key it was recorded in.

Loading a saved project restored its layers, its mixer and its backing, and left the
Practice Key wherever the musician happened to be. Come back to the B flat project from
*Eleanor Rigby* in E minor and you got your flute take with an E minor chart over it.

**Why this is not a session-state write.** The Practice Key has an ownership and
hydration architecture - pick-scoped stores, user-override marks, commit tokens, Fixed
Key locks, Mission ownership of the left panel - and writing ``display_key`` directly
would be overwritten, or worse, would overwrite someone else's live key. So this does
exactly what an explicit *sidebar* key change for a Catalog song does, through the same
calls, in the same order: the per-song store, the override mark, the commit token, the
Backing widget's ownership forgotten, and a *requested* display key for the next render
rather than a value forced into this one. ``karaoke_mode.commit_entry_practice_key`` is
the precedent; an explicit project load is the same kind of act as picking a setlist
entry, so it earns the same commit.

**What counts as a key worth restoring.** Only one the project's own layers attest to:

``single``    every layer agrees on one key - restore it.
``partial``   one key is known and some layers carry no stamp - restore the known key,
              which is the one thing here that is not a guess, and keep saying that the
              others are unrecorded.
``mixed``     two or more keys. There is no one key to restore and inventing one would
              file a take under a key nobody played it in. Show the layers instead.
``unknown``   nothing attests to anything. The key stays unknown and the musician is
              asked, because the current sidebar is not evidence about a take recorded
              last month.

An answer to that question is the musician telling us what they played in. That is
testimony, not inference, so it is recorded - on the layers that had no stamp, never
over one that did.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "CONFIRM_KEY",
    "RESTORE_ASK",
    "RESTORE_NONE",
    "RESTORE_RESTORE",
    "RESTORE_SHOW_LAYERS",
    "clear_key_confirmation",
    "commit_project_practice_key",
    "confirm_project_recording_key",
    "pending_key_confirmation",
    "project_key_restore_plan",
    "restore_practice_key_for_project",
]

#: What to do about the key when a project is opened.
RESTORE_RESTORE = "restore"
RESTORE_SHOW_LAYERS = "show_layers"
RESTORE_ASK = "ask"
RESTORE_NONE = "none"

#: Where an outstanding "what key was this recorded in?" question waits.
CONFIRM_KEY = "_mt_project_key_confirm"


def _text(value: Any) -> str:
    return str(value or "").strip()


def project_key_restore_plan(row: Mapping[str, Any]) -> dict[str, Any]:
    """What the key should do when this project is opened. Never a guess."""
    from multitrack_project_discovery import (
        KEY_STATUS_LEGACY,
        KEY_STATUS_MIXED,
        KEY_STATUS_PARTIAL,
        KEY_STATUS_SINGLE,
        layer_key_lines,
        project_key_label,
        project_key_status,
        project_source,
    )

    status, keys = project_key_status(row)
    source_type, source_id = project_source(row)
    plan: dict[str, Any] = {
        "status": status,
        "keys": list(keys),
        "key": "",
        "pick_key": _pick_key_for(source_type, source_id),
        "source_type": source_type,
        "label": project_key_label(row),
        "layer_lines": layer_key_lines(row),
        "action": RESTORE_NONE,
    }
    if status in (KEY_STATUS_SINGLE, KEY_STATUS_PARTIAL) and keys:
        plan["key"] = keys[0]
        plan["action"] = RESTORE_RESTORE if plan["pick_key"] else RESTORE_NONE
    elif status == KEY_STATUS_MIXED:
        plan["action"] = RESTORE_SHOW_LAYERS
    elif status == KEY_STATUS_LEGACY:
        plan["action"] = RESTORE_ASK
    return plan


def _pick_key_for(source_type: str, source_id: str) -> str:
    """The pick key the Practice Key store is scoped by, or "" when it cannot be named.

    For a Catalog project ``source_id`` *is* the pick key: ``global_song_identity``
    builds ``catalog|<pick>`` straight from ``active_catalog_pick_key``. Custom and
    Composition picks can arrive with the unit separator in place of ``::``.
    """
    source_type, source_id = _text(source_type), _text(source_id)
    if not source_type or not source_id:
        return ""
    pick = source_id.replace("\x1f", "::")
    if source_type in ("custom", "composition") and not pick.startswith(f"{source_type}::"):
        pick = f"{source_type}::{pick}"
    try:
        from songs.practice_key_state import is_song_source_pick

        if not is_song_source_pick(pick):
            return ""
    except Exception:
        pass
    return pick


def commit_project_practice_key(
    session_state: Any,
    *,
    pick_key: str,
    key: str,
) -> str:
    """Make this project's recorded key the song's Practice Key.

    The same commit a sidebar Practice Key change makes for a Catalog song, through the
    same calls - the durable per-song store, the user-override mark, the commit token for
    this pick, the Backing widget's stale ownership dropped, and the display key
    *requested* for the next render. Nothing here writes a widget for the current run,
    so hydration still decides what the sidebar shows.
    """
    pick, token = _text(pick_key), _text(key)
    if not pick or not token:
        return ""
    try:
        from songs.practice_key_state import (
            mark_practice_key_user_override,
            set_practice_concert_key,
        )

        mark_practice_key_user_override(session_state, pick)
        set_practice_concert_key(
            session_state,
            token,
            pick_key=pick,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
    except Exception:
        return ""
    # The commit token is what stops a stale remount writing the old key back over this
    # one a second later.
    session_state["_pk_user_commit_token"] = token
    session_state["_pk_user_commit_pick"] = pick
    session_state["concert_key"] = token
    try:
        # An explicit open with its own key makes the shared Catalog Backing widget's
        # leftover value foreign even for the same song, so Backing reseeds from here.
        from backing_practice_key_control import CATALOG_BACKING_PK_WIDGET_PICK_KEY

        session_state.pop(CATALOG_BACKING_PK_WIDGET_PICK_KEY, None)
    except Exception:
        pass
    try:
        from songs.key_state import request_display_key

        request_display_key(session_state, token)
    except Exception:
        pass
    return token


def restore_practice_key_for_project(
    session_state: Any,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the plan for this project. Returns what was done, for the caller to report."""
    plan = project_key_restore_plan(row)
    action = plan["action"]
    if action == RESTORE_RESTORE:
        applied = commit_project_practice_key(
            session_state, pick_key=plan["pick_key"], key=plan["key"]
        )
        plan["applied"] = bool(applied)
        if applied:
            clear_key_confirmation(session_state)
        return plan
    if action == RESTORE_ASK:
        # The key is unknown and must stay unknown until the musician says otherwise.
        _set(session_state, CONFIRM_KEY, {
            "multitrack_id": _text(row.get("multitrack_id")),
            "pick_key": plan["pick_key"],
            "title": _text(row.get("title")),
            "layer_lines": list(plan["layer_lines"]),
        })
        plan["applied"] = False
        return plan
    clear_key_confirmation(session_state)
    plan["applied"] = False
    return plan


def _set(session_state: Any, key: str, value: Any) -> None:
    try:
        session_state[key] = value
    except Exception:
        pass


def pending_key_confirmation(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """The open "what key was this recorded in?" question, or an empty dict."""
    record = session_state.get(CONFIRM_KEY)
    return dict(record) if isinstance(record, Mapping) else {}


def clear_key_confirmation(session_state: Any) -> None:
    try:
        session_state.pop(CONFIRM_KEY, None)
    except Exception:
        pass


def confirm_project_recording_key(session_state: Any, key: str) -> dict[str, Any]:
    """The musician states the key a legacy project was recorded in.

    Recorded against the layers that carry no stamp - their key genuinely was not
    saved - and never over a layer that already has one. This is the musician's own
    account of what they played, which is why it may be written at all; the current
    sidebar would not qualify.
    """
    pending = pending_key_confirmation(session_state)
    token = _text(key)
    if not pending or not token:
        return {"applied": False, "reason": "nothing pending" if not pending else "no key"}

    stamped: list[str] = []
    try:
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            note_layer_recorded,
        )

        existing = session_state.get(MT_LAYER_RECORDING_KEYS_KEY)
        existing = dict(existing) if isinstance(existing, Mapping) else {}
        from multitrack_slots import MULTITRACK_SLOTS

        tracks = session_state.get("mt_tracks")
        tracks = tracks if isinstance(tracks, Mapping) else {}
        for slot in MULTITRACK_SLOTS:
            if not isinstance(tracks.get(slot), (bytes, bytearray)):
                continue
            if _text(existing.get(slot)):
                continue                      # that layer's key is already known
            note_layer_recorded(session_state, slot, concert_key=token)
            stamped.append(slot)
    except Exception:
        pass

    applied = commit_project_practice_key(
        session_state, pick_key=pending.get("pick_key", ""), key=token
    )
    clear_key_confirmation(session_state)
    return {"applied": bool(applied), "key": token, "stamped": stamped,
            "multitrack_id": pending.get("multitrack_id", "")}
