"""Issue 64 slice 4: the prompt that stands between a take and losing it.

Rendered wherever the musician can be when a guarded move was held - the sidebar, so it
cannot be missed by being on another page, and the Multitrack page itself. It renders
from the held request alone, so a refresh re-renders the same question rather than
dropping it.

Each button does exactly one thing and reports whether it worked. Save goes through the
same ``save_multitrack_session_with_notes`` the Project Library uses - not a second save
path that could succeed where the real one fails. Discard clears only this session's
working layers; saved Project Library rows are not touched, because the thing being
thrown away is the unsaved take, not the musician's history.

**The applier is supplied by whoever held the move**, registered on the session each
render. A held Practice Key change replays the page's own ``on_change`` callback; a held
project load replays the Library's own loader. Replaying the real path is the only way
the move that finally happens is the move that was asked for.
"""

from __future__ import annotations

from typing import Any, Callable

from multitrack_switch_intent import (
    CHOICE_CANCEL,
    CHOICE_CONTINUE_EDITING,
    CHOICE_DISCARD,
    CHOICE_SAVE_AS_NEW,
    CHOICE_SAVE_CHANGES,
    KIND_LOAD_PROJECT,
    KIND_NEW_PROJECT,
    KIND_PRACTICE_KEY,
    KIND_SONG,
    describe_pending,
    resolve_choice,
    switch_is_pending,
)

__all__ = [
    "APPLIER_KEYS",
    "register_applier",
    "render_switch_prompt",
]

#: Where each kind of held move leaves the function that performs it.
APPLIER_KEYS = {
    KIND_PRACTICE_KEY: "_mt_apply_practice_key",
    KIND_LOAD_PROJECT: "_mt_apply_project_load",
    KIND_NEW_PROJECT: "_mt_apply_new_project",
}

#: Short labels; the heading already says where the musician was going.
_HELP = {
    CHOICE_SAVE_CHANGES: "Save into the project you have open, then continue.",
    CHOICE_SAVE_AS_NEW: "Keep this as its own project, then continue.",
    CHOICE_CONTINUE_EDITING: "Stay here with this recording.",
    CHOICE_DISCARD: "Throw away this unsaved recording, then continue.",
    CHOICE_CANCEL: "Change nothing.",
}


def register_applier(session_state: Any, kind: str, fn: Callable[[], Any]) -> None:
    """Leave the function that performs a held move of this kind, for the prompt to call."""
    key = APPLIER_KEYS.get(kind)
    if not key:
        return
    try:
        session_state[key] = fn
    except Exception:
        pass


def _applier(session_state: Any, record: dict[str, Any]) -> Callable[[], Any] | None:
    kind = str(record.get("kind") or "")
    if kind == KIND_SONG:
        return _song_applier(session_state, record)
    key = APPLIER_KEYS.get(kind)
    fn = session_state.get(key) if key else None
    return fn if callable(fn) else None


def _song_applier(session_state: Any, record: dict[str, Any]) -> Callable[[], Any] | None:
    """Replay the exact commit that was held, with a one-shot permission."""
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    replay = payload.get("replay")
    pick_key = str(payload.get("pick_key") or "")
    if not isinstance(replay, dict) or not replay.get("st") or not pick_key:
        return None

    def apply() -> None:
        from multitrack_navigation_guard import approve_song_commit
        from songs.music_source import commit_catalog_active_song

        approve_song_commit(session_state, pick_key)
        commit_catalog_active_song(**replay)

    return apply


def _save_action(st_obj: Any, session_state: Any, *, save_mode: str, song_title: str):
    """The Project Library's own save, reporting failure as failure."""

    def run() -> tuple[bool, str]:
        from media_multitrack_catalog import save_multitrack_session_with_notes
        from multitrack_work_state import mark_project_saved

        try:
            from multitrack_mixer_state import commit_all_multitrack_mixer_widgets
            from multitrack_session_persistence import flush_multitrack_workspace_snapshot

            commit_all_multitrack_mixer_widgets(session_state)
            flush_multitrack_workspace_snapshot(session_state, st=st_obj)
        except ImportError:
            pass
        name = str(session_state.get("mt_history_save_name") or "").strip()
        if not name:
            try:
                from multitrack_history import default_project_name

                name = default_project_name(session_state, song_title=song_title)
            except Exception:
                name = "Multitrack session"
        ok, item_key, err = save_multitrack_session_with_notes(
            session_state,
            project_name=name,
            notes=str(session_state.get("mt_history_save_notes") or ""),
            song_title=song_title,
            st=st_obj,
            save_mode=save_mode,
        )
        if not ok:
            return False, str(err or "The project could not be saved.")
        session_state["mt_hist_active_item"] = item_key
        session_state["multitrack_catalog_active_id"] = item_key
        session_state["_last_catalog_multitrack_id"] = item_key
        mark_project_saved(session_state)
        return True, ""

    return run


def _discard_action(session_state: Any):
    """Throw away this session's working layers. Saved library rows are untouched."""

    def run() -> None:
        from multitrack_session_persistence import reset_multitrack_working_session
        from multitrack_work_state import mark_project_saved

        reset_multitrack_working_session(session_state)
        # That helper leaves the prepared-backing stamp, which on its own still counts
        # as saveable content - so a discard would come back still "at risk".
        for key in ("mt_backing_prepared_at", "multitrack_catalog_active_id",
                    "mt_hist_active_item", "_last_catalog_multitrack_id"):
            session_state.pop(key, None)
        mark_project_saved(session_state)      # nothing left to be at risk

    return run


def render_switch_prompt(
    st_obj: Any,
    session_state: Any,
    *,
    song_title: str = "",
    where: str = "page",
) -> bool:
    """Render the held question, if there is one. True when it rendered."""
    if not switch_is_pending(session_state):
        return False
    record = describe_pending(session_state)
    if not record:
        return False

    token = str(record.get("token") or "")
    container = st_obj.container(border=True) if hasattr(st_obj, "container") else st_obj
    with container:
        st_obj.warning(record.get("heading") or "Unsaved recording")
        if record.get("message"):
            st_obj.caption(str(record["message"]))
        if record.get("error"):
            st_obj.error(str(record["error"]))

        choices = [c for c in record.get("choices") or []]
        applier = _applier(session_state, record)
        if applier is None and record.get("kind") != KIND_NEW_PROJECT:
            # Without a way to carry out the move, offering to continue would be a lie.
            choices = [c for c in choices
                       if c in (CHOICE_CONTINUE_EDITING, CHOICE_CANCEL)]
            st_obj.caption(
                "The destination is no longer available — your recording is unchanged."
            )

        for choice in choices:
            if st_obj.button(
                choice,
                key=f"mt_switch_{where}_{token}_{choice.replace(' ', '_').lower()}",
                use_container_width=True,
                type="primary" if choice.startswith("Save") else "secondary",
                help=_HELP.get(choice, ""),
            ):
                outcome = resolve_choice(
                    session_state,
                    choice,
                    save_changes=_save_action(st_obj, session_state,
                                              save_mode="update", song_title=song_title),
                    save_as_new=_save_action(st_obj, session_state,
                                             save_mode="new", song_title=song_title),
                    discard=_discard_action(session_state),
                    apply_switch=applier,
                )
                if outcome.get("status") == "failed":
                    st_obj.error(outcome.get("error") or "That did not work.")
                st_obj.rerun()
    return True
