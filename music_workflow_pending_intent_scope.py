"""Account/workspace scoping for pre-widget pending workflow intents."""

from __future__ import annotations

from typing import Any


def capture_pending_intent_scope(session: dict[str, Any]) -> dict[str, str]:
    try:
        from music_workflow_state_store import resolve_workspace_identity

        ws, acct = resolve_workspace_identity(session)
    except ImportError:
        ws = str(session.get("_suite_active_workspace_id") or "default").strip() or "default"
        acct = str(session.get("_suite_account_id") or ws).strip() or ws
    return {"workspace_id": ws, "account_id": acct}


def pending_intent_scope_matches(session: dict[str, Any], pending: dict[str, Any]) -> tuple[bool, str]:
    scope = pending.get("scope") if isinstance(pending.get("scope"), dict) else {}
    live = capture_pending_intent_scope(session)
    pw = str(scope.get("workspace_id") or "").strip()
    pa = str(scope.get("account_id") or "").strip()
    if pw and pw != live["workspace_id"]:
        return False, "workspace_scope_mismatch"
    if pa and pa != live["account_id"]:
        return False, "account_scope_mismatch"
    return True, ""


def workflow_mutation_consume_allowed(session: dict[str, Any]) -> tuple[bool, str]:
    """When Real Accounts is on, do not apply cross-account pending mutations while signed out."""
    try:
        from suite_auth import is_auth_enabled, is_authenticated

        if is_auth_enabled() and not is_authenticated(session):
            return False, "auth_required"
    except ImportError:
        pass
    return True, ""


def quarantine_account_scoped_pending_intents(session: dict[str, Any]) -> None:
    """Logout / auth clear — drop pending edits that must not survive account switches."""
    try:
        from music_workflow_pending_generated_key_edit import clear_pending_generated_key_edit

        clear_pending_generated_key_edit(session)
    except ImportError:
        session.pop("_music_pending_generated_key_edit", None)
