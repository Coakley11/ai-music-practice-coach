"""Issue 64 slice 4: holding a navigation request still until the musician answers.

`multitrack_work_state.switch_guard` can say *whether* something is at risk. It cannot
stop anything on its own, and in Streamlit knowing is the easy half.

**Why a pending transition is needed at all.** By the time an ``on_change`` callback
runs, the widget has already changed: ``st.session_state["display_key"]`` says Bb
whether or not the move is allowed. Asking after the fact is too late, and a confirmation
dialog cannot block - the script simply reruns. So a guarded move is split in two. The
request is recorded, together with the value each widget must go back to; nothing else
happens. On the next rerun the prompt renders, and only when an answer *succeeds* does
the move actually apply.

**Cancel has to be able to undo the widget.** That is what ``revert`` carries: the
previous selection, written back so the sidebar shows the key the recording was actually
made in. Without it, Cancel would leave the control claiming a key that nothing had
applied - the display lying about the session.

**Saving must come before moving, not beside it.** ``resolve_choice`` runs the save, and
only calls the navigation when the save reports success. A failed save leaves the
pending request in place, with its error, so the musician is asked again rather than
silently carried into another song minus the take.

**One answer, once.** The record is removed before its action runs, so a double click,
a refresh mid-flight or a stray rerun finds nothing pending and does nothing. If the
action fails the record goes back, with a fresh token.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping

__all__ = [
    "CHOICE_CANCEL",
    "CHOICE_CONTINUE_EDITING",
    "CHOICE_DISCARD",
    "CHOICE_SAVE_AS_NEW",
    "CHOICE_SAVE_CHANGES",
    "KIND_LOAD_PROJECT",
    "KIND_NEW_PROJECT",
    "KIND_PRACTICE_KEY",
    "KIND_SONG",
    "PENDING_KEY",
    "clear_pending",
    "describe_pending",
    "pending_switch",
    "request_switch",
    "resolve_choice",
    "switch_is_pending",
]

#: Where the held-back request lives. One at a time: a second request while one is open
#: would mean two destinations and no way to tell which answer belonged to which.
PENDING_KEY = "_mt_pending_switch"

KIND_SONG = "song"
KIND_PRACTICE_KEY = "practice_key"
KIND_LOAD_PROJECT = "load_project"
KIND_NEW_PROJECT = "new_project"

CHOICE_SAVE_CHANGES = "Save Changes"
CHOICE_SAVE_AS_NEW = "Save as New Project"
CHOICE_CONTINUE_EDITING = "Continue Editing"
CHOICE_DISCARD = "Discard"
CHOICE_CANCEL = "Cancel"

#: Answers that keep the musician where they are. Both revert the widgets; they differ
#: only in what the musician was told they were doing.
_STAY = (CHOICE_CONTINUE_EDITING, CHOICE_CANCEL)


def _set(session_state: Any, key: str, value: Any) -> None:
    try:
        session_state[key] = value
    except Exception:
        pass


def _pop(session_state: Any, key: str, default: Any = None) -> Any:
    try:
        return session_state.pop(key, default)
    except Exception:
        return default


def pending_switch(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """The request currently waiting for an answer, or an empty dict."""
    record = session_state.get(PENDING_KEY)
    return dict(record) if isinstance(record, Mapping) else {}


def switch_is_pending(session_state: Mapping[str, Any]) -> bool:
    return bool(pending_switch(session_state))


def clear_pending(session_state: Any) -> dict[str, Any]:
    record = _pop(session_state, PENDING_KEY, None)
    return dict(record) if isinstance(record, Mapping) else {}


def request_switch(
    session_state: Any,
    *,
    kind: str,
    target: str = "",
    revert: Mapping[str, Any] | None = None,
    reason: str = "",
    payload: Any = None,
) -> dict[str, Any]:
    """Ask to replace or re-point the working recording.

    Returns a record whose ``allowed`` says whether the caller may go ahead *now*. When
    it is false the request has been stored and the caller must do nothing else - the
    prompt will render on the next rerun.
    """
    from multitrack_work_state import switch_guard

    guard = switch_guard(session_state, reason=reason or kind, target=target)
    if guard.get("allowed"):
        # Nothing to lose, so nothing to ask. A clean workspace is never interrupted.
        return {**guard, "kind": kind, "pending": False}

    record = {
        **guard,
        "kind": kind,
        "target": str(target or ""),
        "revert": dict(revert or {}),
        "payload": payload,
        "token": uuid.uuid4().hex,
        "error": "",
        "pending": True,
    }
    _set(session_state, PENDING_KEY, record)
    return record


def describe_pending(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """The prompt to render: what is at risk, where the musician was going, what to offer."""
    record = pending_switch(session_state)
    if not record:
        return {}
    kind = str(record.get("kind") or "")
    target = str(record.get("target") or "")
    where = {
        KIND_SONG: f"Opening **{target}**" if target else "Opening another song",
        KIND_PRACTICE_KEY: (
            f"Changing the Practice Key to **{target}**" if target
            else "Changing the Practice Key"
        ),
        KIND_LOAD_PROJECT: (
            f"Loading **{target}**" if target else "Loading another project"
        ),
        KIND_NEW_PROJECT: "Starting a new project",
    }.get(kind, "This change")
    return {
        **record,
        "heading": f"{where} would affect your current recording",
        "message": str(record.get("message") or ""),
        "choices": list(record.get("choices") or []),
    }


def _revert(session_state: Any, record: Mapping[str, Any]) -> None:
    """Put every widget back where it was, so no control claims an unapplied change."""
    revert = record.get("revert")
    if isinstance(revert, Mapping):
        for key, value in revert.items():
            _set(session_state, str(key), value)


def resolve_choice(
    session_state: Any,
    choice: str,
    *,
    save_changes: Callable[[], Any] | None = None,
    save_as_new: Callable[[], Any] | None = None,
    discard: Callable[[], Any] | None = None,
    apply_switch: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Carry out one answer. The move happens only if the answer's own action succeeded.

    ``status`` is one of:

    ``stale``     nothing was pending - a double click, or a refresh after the answer.
    ``stayed``    Cancel or Continue Editing: widgets reverted, nothing else touched.
    ``switched``  the move was applied.
    ``failed``    the save (or discard) did not succeed; the request is still pending.
    """
    record = clear_pending(session_state)       # popped first: one answer, once
    if not record:
        return {"status": "stale", "choice": str(choice or ""), "switched": False}

    answer = str(choice or "").strip()

    if answer in _STAY:
        _revert(session_state, record)
        return {"status": "stayed", "choice": answer, "switched": False,
                "kind": record.get("kind", "")}

    action = {
        CHOICE_SAVE_CHANGES: save_changes,
        CHOICE_SAVE_AS_NEW: save_as_new,
        CHOICE_DISCARD: discard,
    }.get(answer)

    if answer in (CHOICE_SAVE_CHANGES, CHOICE_SAVE_AS_NEW, CHOICE_DISCARD):
        if action is None:
            return _put_back(session_state, record, answer,
                             f"{answer} is not available here.")
        ok, detail = _run(action)
        if not ok:
            # The take is still only in this session. Do not move.
            return _put_back(session_state, record, answer, detail)

    if apply_switch is not None:
        ok, detail = _run(apply_switch)
        if not ok:
            return _put_back(session_state, record, answer, detail)

    return {"status": "switched", "choice": answer, "switched": True,
            "kind": record.get("kind", ""), "target": record.get("target", "")}


def _run(action: Callable[[], Any]) -> tuple[bool, str]:
    """Call an action and decide whether it succeeded.

    ``None`` counts as success (a plain function that raises on failure).
    ``False`` and ``(False, "...")`` are failures, so an existing save helper that
    already reports that way needs no adapter.
    """
    try:
        outcome = action()
    except Exception as exc:                       # a raising save is a failed save
        return False, str(exc) or exc.__class__.__name__
    if outcome is None or outcome is True:
        return True, ""
    if outcome is False:
        return False, "The operation did not complete."
    if isinstance(outcome, tuple) and len(outcome) == 2:
        ok, detail = outcome
        return bool(ok), "" if ok else str(detail or "")
    if isinstance(outcome, Mapping) and "ok" in outcome:
        return bool(outcome["ok"]), str(outcome.get("error") or "")
    return True, ""


def _put_back(
    session_state: Any,
    record: Mapping[str, Any],
    choice: str,
    detail: str,
) -> dict[str, Any]:
    """A failed answer leaves the request open, with a new token and the reason."""
    again = {**dict(record), "token": uuid.uuid4().hex,
             "error": detail or "That did not work.", "pending": True}
    _set(session_state, PENDING_KEY, again)
    return {"status": "failed", "choice": str(choice or ""), "switched": False,
            "error": again["error"], "kind": record.get("kind", "")}
