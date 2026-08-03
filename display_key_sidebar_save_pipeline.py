"""Enter/exit trace for explicit sidebar display_key cloud save (?dev=1)."""

from __future__ import annotations

from typing import Any

DISPLAY_KEY_SAVE_PIPELINE_KEY = "_display_key_sidebar_save_pipeline_trace"


def _pipe(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(DISPLAY_KEY_SAVE_PIPELINE_KEY)
    if isinstance(raw, dict):
        return raw
    d: dict[str, Any] = {"steps": []}
    session[DISPLAY_KEY_SAVE_PIPELINE_KEY] = d
    return d


def record_display_key_save_pipeline_step(
    session: dict[str, Any],
    *,
    function: str,
    phase: str,
    transaction_id: str = "",
    save_reason: str = "",
    return_value: Any = None,
    return_type: str = "",
    exception: str = "",
    next_called: str = "",
    **fields: Any,
) -> None:
    if not session.get("developer_mode"):
        return
    steps = _pipe(session).setdefault("steps", [])
    if not isinstance(steps, list):
        steps = []
        _pipe(session)["steps"] = steps
    rv = return_value
    if rv is not None and not return_type:
        return_type = type(rv).__name__
    entry = {
        "function": str(function or "").strip() or None,
        "phase": str(phase or "").strip() or None,
        "transaction_id": str(transaction_id or "").strip() or None,
        "save_reason": str(save_reason or "").strip() or None,
        "return_value": rv,
        "return_type": return_type or None,
        "exception": str(exception or "").strip() or None,
        "next_called": str(next_called or "").strip() or None,
        **{k: v for k, v in fields.items() if v is not None},
    }
    steps.append(entry)
    if len(steps) > 80:
        del steps[:-80]


def resolve_display_key_cloud_save_ok(session: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Authoritative ok from workspace save transaction — not bool(None)."""
    try:
        from display_key_sidebar_cloud_confirmation import _workspace_save_transaction

        tx = _workspace_save_transaction(session)
    except ImportError:
        tx = dict(session.get("_music_workspace_save_transaction") or {})
    force_ok = session.get("_music_force_save_ok")
    cloud_confirmed = tx.get("cloud_confirmed")
    suite_cloud = session.get("_suite_persist_last_save_cloud")
    cloud_write = tx.get("cloud_write_succeeded")
    ok = False
    if force_ok is True and (cloud_confirmed is True or suite_cloud is True or cloud_write is True):
        ok = True
    elif cloud_confirmed is True:
        ok = True
    detail = {
        "_music_force_save_ok": force_ok,
        "_suite_persist_last_save_cloud": suite_cloud,
        "cloud_confirmed": cloud_confirmed,
        "cloud_write_succeeded": cloud_write,
        "force_save_block_reason": session.get("_music_force_save_blocked_reason"),
    }
    return ok, detail


def run_explicit_display_key_cloud_save(st: Any, *, transaction_id: str = "", caller: str = "") -> bool:
    """Accepted music cloud save path (same entry as creative selector saves)."""
    session = st.session_state
    tx_id = str(transaction_id or "").strip()
    reason = "display_key_change"
    record_display_key_save_pipeline_step(
        session,
        function="run_explicit_display_key_cloud_save",
        phase="enter",
        transaction_id=tx_id,
        save_reason=reason,
        caller=caller or None,
    )
    try:
        from display_key_startup_save_queue import attempt_release_stale_startup_suppression_for_display_key

        attempt_release_stale_startup_suppression_for_display_key(st)
    except ImportError:
        pass
    raw_return: Any = None
    exc_text = ""
    try:
        from music_persistent_state import force_save_music_state

        record_display_key_save_pipeline_step(
            session,
            function="force_save_music_state",
            phase="enter",
            transaction_id=tx_id,
            save_reason=reason,
            next_called="force_autosave→force_music_workspace_save",
        )
        raw_return = force_save_music_state(st, reason=reason)
        record_display_key_save_pipeline_step(
            session,
            function="force_save_music_state",
            phase="exit",
            transaction_id=tx_id,
            save_reason=reason,
            return_value=raw_return,
            _music_force_save_ok=session.get("_music_force_save_ok"),
            suite_persist_last_save_cloud=session.get("_suite_persist_last_save_cloud"),
        )
    except Exception as exc:
        exc_text = str(exc)
        record_display_key_save_pipeline_step(
            session,
            function="force_save_music_state",
            phase="exception",
            transaction_id=tx_id,
            save_reason=reason,
            exception=exc_text,
        )
        raw_return = False

    try:
        from display_key_sidebar_cloud_confirmation import finalize_display_key_sidebar_save_outcome

        ok = finalize_display_key_sidebar_save_outcome(
            st,
            transaction_id=tx_id,
            caller=caller or "run_explicit_display_key_cloud_save",
            force_save_return=raw_return,
            save_exception=exc_text,
        )
    except ImportError:
        ok, _ = resolve_display_key_cloud_save_ok(session)
        if raw_return is not None and force_ok_is_false(raw_return, session):
            ok = False

    record_display_key_save_pipeline_step(
        session,
        function="run_explicit_display_key_cloud_save",
        phase="exit",
        transaction_id=tx_id,
        save_reason=reason,
        return_value=ok,
        raw_force_save_return=raw_return,
    )
    return ok


def force_ok_is_false(raw_return: Any, session: dict[str, Any]) -> bool:
    if raw_return is False:
        return True
    if raw_return is None and session.get("_music_force_save_ok") is not True:
        return True
    return False


__all__ = [
    "DISPLAY_KEY_SAVE_PIPELINE_KEY",
    "record_display_key_save_pipeline_step",
    "resolve_display_key_cloud_save_ok",
    "run_explicit_display_key_cloud_save",
]
