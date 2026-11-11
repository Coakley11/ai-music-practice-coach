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

import os

from typing import Any, Mapping

__all__ = [
    "CONFIRM_KEY",
    "RESTORED_DISPLAY_KEY",
    "RESTORED_DISPLAY_PICK",
    "consume_restored_display_key",
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

#: One-shot handoff for the restored key, read by the sidebar before its Practice Key
#: widget is built. Needed because the restore runs *after* that widget already exists
#: for this script run, so nothing can change it until the next one.
RESTORED_DISPLAY_KEY = "_mt_restore_display_key"
RESTORED_DISPLAY_PICK = "_mt_restore_display_pick"


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

    A **Catalog** ``source_id`` is already the pick key, verbatim - and it legitimately
    contains a unit separator, as in ``JazzAll the Things You Are - Jerome Kern``.
    An earlier version of this rewrote every ```` to ``::`` and so turned a valid
    catalog pick into one that matched nothing: the key was "committed" to a store
    nobody reads and the project reopened in the wrong key anyway.

    **Custom** and **Composition** are the ones that need mapping. ``_context`` stores
    their picks with ``<type>`` where the pick key has ``<type>::`` - it does that
    same substitution itself when it validates them.
    """
    source_type, source_id = _text(source_type), _text(source_id)
    if not source_type or not source_id:
        return ""
    if source_type == "catalog":
        return source_id
    pick = source_id
    if pick.startswith(f"{source_type}"):
        pick = f"{source_type}::" + pick[len(source_type) + 1:]
    elif not pick.startswith(f"{source_type}::"):
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
    if _apply_to_live_sidebar(session_state, pick, token):
        # The writer above defers whenever widgets already exist, which they do by the
        # time a project is opened. Leave the key for the sidebar to pick up on its next
        # pass, scoped to the pick it belongs to.
        _set(session_state, RESTORED_DISPLAY_KEY, token)
        _set(session_state, RESTORED_DISPLAY_PICK, pick)
    return token


def consume_restored_display_key(
    session_state: Any,
    *,
    widget_key: str = "",
    options: Any = None,
    site: str = "",
) -> str:
    """Apply a restored key to the sidebar, before its widget is built. One shot.

    Called from the sidebar at the point the pending display key is already seeded the
    same way, which is the only moment a widget-backed value can still be set for this
    run. Refuses unless the song the key belongs to is still the active one, and unless
    the key is actually offered for that song - seeding a value outside the options
    would leave the control showing something it cannot represent.
    """
    token = ""
    pick = ""
    try:
        token = _text(session_state.get(RESTORED_DISPLAY_KEY))
        pick = _text(session_state.get(RESTORED_DISPLAY_PICK))
    except Exception:
        return ""
    _trace(session_state, "handoff_seen", token=token, pick=pick, widget_key=widget_key,
           site=site, n_options=len(list(options or [])))
    if not token:
        return ""
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY
    except Exception:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
    active = _text(session_state.get(ACTIVE_CATALOG_PICK_KEY))
    choices = [str(o) for o in (options or [])]
    if not choices:
        # Called from a site that does not know the widget's options yet. Derive them
        # from the active song so a key it cannot represent is still refused.
        try:
            from music_theory import display_key_options

            choices = [str(o) for o in display_key_options(
                _text(session_state.get("original_key")))]
        except Exception:
            choices = []
    if (pick and active and pick != active) or (choices and token not in choices):
        _trace(session_state, "handoff_refused", token=token, active=active, pick=pick,
               offered=token in choices if choices else "no options")
        for key in (RESTORED_DISPLAY_KEY, RESTORED_DISPLAY_PICK):
            try:
                session_state.pop(key, None)
            except Exception:
                pass
        return ""
    for key in (RESTORED_DISPLAY_KEY, RESTORED_DISPLAY_PICK):
        try:
            session_state.pop(key, None)
        except Exception:
            pass
    errors: list[str] = []
    for key in ("display_key", "concert_key"):
        try:
            session_state[key] = token
        except Exception as exc:
            errors.append(f"{key}:{exc.__class__.__name__}")
    if widget_key and widget_key not in ("display_key", "concert_key"):
        try:
            session_state[widget_key] = token
        except Exception as exc:
            errors.append(f"{widget_key}:{exc.__class__.__name__}")
    try:
        from songs.key_state import PENDING_DISPLAY_KEY

        session_state.pop(PENDING_DISPLAY_KEY, None)
    except Exception:
        pass
    _trace(session_state, "handoff_applied", token=token, widget_key=widget_key,
           write_errors=",".join(errors), dk_now=_text(session_state.get("display_key")))
    return token


def _apply_to_live_sidebar(session_state: Any, pick: str, token: str) -> bool:
    """Put the restored key on the sidebar now, when this project's song is the active one.

    The commit above is correct and durable - the store, the override mark and the token
    all hold - and on its own it does **not** reach the sidebar. The reason is specific:
    ``apply_display_key_for_active_song`` honours ``_pk_user_commit_token`` only in its
    *same song* branch, and that branch requires ``_pk_user_commit_pick == identity_pk``.
    ``render_global_studio_bar`` builds the identity with
    ``song_display_identity(title, artist, key)`` and no ``pick_key``, so ``identity_pk``
    is the song **title** while the commit carries the real pick key. The comparison
    fails and the commit is skipped. A karaoke entry escapes this only because
    activating it changes the active song, taking the other branch, which consumes the
    pending display key instead.

    Loading a project does not change the song, so this applies the key through the same
    widget-safe writer every other owner-specific sync uses - and only once the project's
    pick is confirmed to be the active one, so a project belonging to another song can
    never paint its key onto the song in front of the musician.
    """
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY
    except Exception:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
    try:
        active = _text(session_state.get(ACTIVE_CATALOG_PICK_KEY))
    except Exception:
        return False
    if not active or active != _text(pick):
        # Another song is active. The store keeps the key for when this one comes back.
        _trace(session_state, "sidebar_skipped", reason="pick is not active",
               active=active, pick=_text(pick))
        return False
    try:
        from types import SimpleNamespace

        from songs.key_state import _apply_display_key_before_widget

        _apply_display_key_before_widget(
            SimpleNamespace(session_state=session_state),
            token,
            source="multitrack_project_load",
        )
    except Exception as exc:
        _trace(session_state, "sidebar_error", error=str(exc))
        return False
    _trace(session_state, "sidebar_applied", token=token)
    return True


def _trace(session_state: Any, stage: str, **fields: Any) -> None:
    """Append one line of what actually happened, for diagnosing a live session.

    The failure this exists for could not be reproduced in-process: the load path set
    the store correctly on a plain dict and left the sidebar on the old key in the real
    app, which means the interesting state is the one only a running session has.
    """
    if not os.environ.get("MUSIC_MT_KEY_TRACE"):
        return
    try:
        import json
        import time

        path = os.path.join(
            os.environ.get("MUSIC_APP_DATA_DIR") or ".", "_mt_key_restore.jsonl")
        row = {"t": round(time.time(), 3), "stage": stage}
        row.update({k: ("" if v is None else v) for k, v in fields.items()})
        for key in ("display_key", "concert_key", "_pending_display_key",
                    "_pk_user_commit_token", "_pk_user_commit_pick",
                    "active_catalog_pick_key", "studio_page",
                    RESTORED_DISPLAY_KEY, RESTORED_DISPLAY_PICK):
            try:
                row[key] = _text(session_state.get(key))
            except Exception:
                row[key] = "<unreadable>"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=True) + chr(10))
    except Exception:
        pass


def restore_practice_key_for_project(
    session_state: Any,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the plan for this project. Returns what was done, for the caller to report."""
    plan = project_key_restore_plan(row)
    _trace(session_state, "plan", action=plan["action"], key=plan["key"],
           pick=plan["pick_key"], status=plan["status"])
    action = plan["action"]
    if action == RESTORE_RESTORE:
        applied = commit_project_practice_key(
            session_state, pick_key=plan["pick_key"], key=plan["key"]
        )
        plan["applied"] = bool(applied)
        if applied:
            clear_key_confirmation(session_state)
        stored = ""
        try:
            from songs.practice_key_state import get_practice_concert_key

            stored = _text(get_practice_concert_key(
                session_state, pick_key=plan["pick_key"]))
        except Exception:
            pass
        _trace(session_state, "after_commit", applied=bool(applied),
               wanted=plan["key"], stored_now=stored)
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
