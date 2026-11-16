"""Content readback for one Composition checkpoint; never writes cloud data."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

RESULT_KEY = "_composition_persistence_result"
CLOUD_BASE_KEY = "_composition_cloud_base_hashes"


def doc_hash(doc: Any) -> str:
    d = copy.deepcopy(doc) if isinstance(doc, dict) else {}
    d.pop("updated_at", None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def doc_hashes(blob: dict[str, Any]) -> dict[str, str]:
    lib = blob.get("library") if isinstance(blob.get("library"), dict) else {}
    return {str(k): doc_hash(v) for k, v in lib.items() if isinstance(v, dict)}


# A document's own ``updated_at`` is a bookkeeping stamp that is re-written whenever the document is touched (including
# by a render or a later run), so it can differ between the copy that was saved and the copy compared against it without
# a single character of the composition having changed. ``doc_hash`` already ignores it; so must the fingerprint.
_VOLATILE_DOCUMENT_KEYS = ("updated_at",)


def _without_volatile(doc: Any) -> Any:
    if not isinstance(doc, dict):
        return doc
    return {k: v for k, v in doc.items() if k not in _VOLATILE_DOCUMENT_KEYS}


def workspace_content(blob: dict[str, Any]) -> dict[str, Any]:
    """Retain every document field; ignore only checkpoint timestamps (the workspace's and each document's)."""
    out = {key: copy.deepcopy(blob.get(key)) for key in (
        "active_document", "library", "deleted_document_ids", "library_initialized",
        "needs_seed", "active_section_id", "focus_lane", "workflow_phase",
    )}
    out["active_document"] = _without_volatile(out.get("active_document"))
    if isinstance(out.get("library"), dict):
        out["library"] = {k: _without_volatile(v) for k, v in out["library"].items()}
    return out


def content_fingerprint(blob: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(workspace_content(blob), sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _matching_workspace(state: dict[str, Any], expected: dict[str, Any]) -> bool:
    from composition_workspace_state_persistence import upgrade_composition_workspace_blob

    blob = state.get("composition_workspace_state")
    if not isinstance(blob, dict):
        return False
    return content_fingerprint(upgrade_composition_workspace_blob(blob)) == content_fingerprint(expected)


def _read_disk_state() -> dict[str, Any]:
    from suite_user_persistence import state_file_path, STATE_VERSION

    raw = json.loads(state_file_path("music").read_text(encoding="utf-8"))
    if raw.get("version") != STATE_VERSION or raw.get("app") != "music":
        return {}
    return raw.get("state") if isinstance(raw.get("state"), dict) else {}


def verify_checkpoint(session: Any, expected: dict[str, Any], *, force_ok: bool) -> dict[str, Any]:
    """Require this attempt's acknowledgement AND exact account-scoped readback."""
    result = {
        "status": "memory_only", "disk_verified": False, "cloud_verified": False,
        "cloud_required": True, "fingerprint": content_fingerprint(expected),
        "document_id": str((expected.get("active_document") or {}).get("id") or ""),
        "error": "", "force_ok": bool(force_ok),
    }
    try:
        from suite_storage_config import cloud_storage_enabled
        result["cloud_required"] = bool(cloud_storage_enabled())
    except Exception:
        result["error"] = "cloud_configuration_unknown"
    if session.get("_suite_persist_last_save_disk"):
        try:
            result["disk_verified"] = _matching_workspace(_read_disk_state(), expected)
        except Exception:
            result["error"] = "disk_readback_failed"
    # force_ok protects against stale or incomplete transaction acknowledgements.
    if force_ok and session.get("_suite_persist_last_save_cloud"):
        try:
            from suite_user import account_mode
            if account_mode() != "cloud":
                raise RuntimeError("No resolved cloud account")
            from suite_cloud_state import load_cloud_full_session
            state, _ = load_cloud_full_session("music", force=True)
            result["cloud_verified"] = _matching_workspace(state, expected)
            if not result["cloud_verified"]:
                result["error"] = "cloud_content_readback_mismatch"
        except Exception:
            result["error"] = "cloud_readback_failed"
    if result["cloud_verified"]:
        result["status"] = "cloud_verified"
    elif result["disk_verified"]:
        result["status"] = "server_local_only"
    elif not result["error"]:
        result["error"] = "no_verified_persistence"
    if result["cloud_verified"]:
        # Remember what the cloud held per document, to tell "unchanged remotely" from a real conflict.
        session[CLOUD_BASE_KEY] = doc_hashes(expected)
    result["failure_code"] = "" if result["cloud_verified"] else classify_failure(session, result)
    result["retryable"] = bool(result["failure_code"]) and result["failure_code"] != "cloud_not_configured"
    session[RESULT_KEY] = result
    log_save_outcome(session, result)
    return result


_URL_RE = re.compile(r"https?://\S+")
_HOST_RE = re.compile(r"[A-Za-z0-9.\-]+\.supabase\.(?:co|in|net)")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_\-]+)*")
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{24,}")


def _scrub(text: Any, limit: int = 160) -> str:
    """One short line, no URLs, no long tokens/ids, no newlines (safe for shared logs)."""
    out = _LONG_TOKEN_RE.sub("<id>", _JWT_RE.sub("<jwt>", _HOST_RE.sub("<host>", _URL_RE.sub("<url>", str(text or "")))))
    return out.replace("\n", " ").replace("\r", " ")[:limit]


def log_save_outcome(session: Any, result: dict[str, Any]) -> None:
    """One structured line per Composition checkpoint so an unverified save is diagnosable from the app logs.

    Carries only codes and flags (never titles, lyrics, chords, ids or tokens). This is the line that was missing when a
    production save reported 'not verified' while the logs showed no cause.
    """
    try:
        def flag(key: str) -> Any:
            return session.get(key)

        print(
            "[composition_save] "
            f"status={result.get('status')} failure_code={result.get('failure_code') or '-'} "
            f"error={result.get('error') or '-'} disk_verified={result.get('disk_verified')} "
            f"cloud_verified={result.get('cloud_verified')} cloud_required={result.get('cloud_required')} "
            f"force_ok={result.get('force_ok')} last_save_disk={flag('_suite_persist_last_save_disk')} "
            f"last_save_cloud={flag('_suite_persist_last_save_cloud')} "
            f"blocked_reason={_scrub(flag('_music_force_save_blocked_reason'), 80) or '-'} "
            f"stale={bool(flag('_music_stale_write_blocked'))} "
            f"cloud_stage={_scrub(flag('_suite_last_cloud_save_failure_stage'), 60) or '-'} "
            f"exception={_scrub(flag('_suite_last_cloud_save_exception'), 160) or '-'}",
            flush=True,
        )
    except Exception:  # logging must never break a save
        pass


def classify_failure(session: Any, result: dict[str, Any]) -> str:
    """Name the first reason a cloud write is not confirmed (diagnostic, never a success path)."""
    if not result.get("cloud_required", True):
        return "cloud_not_configured"
    try:
        from suite_user import account_mode
        if account_mode() != "cloud":
            return "not_signed_in"
    except Exception:
        return "account_unresolved"
    blocked = str(session.get("_music_force_save_blocked_reason") or "")
    if session.get("_music_stale_write_blocked") or session.get("stale_write_blocked") or "stale" in blocked:
        return "stale_revision_conflict"
    if blocked in ("strict_save_deferred", "music_egress_strict"):
        return "policy_blocked"
    if result.get("error") == "cloud_content_readback_mismatch":
        return "readback_mismatch"
    if result.get("error") == "cloud_readback_failed":
        return "readback_failed"
    return "cloud_write_failed"


_LOCAL_COPY = ("Saved only to this app server and verified there. Cloud persistence is not confirmed. "
               "This temporary server copy may not survive a restart or redeployment.")
_KEPT = " Your edits are kept and still marked unsaved to the cloud."
_FAILURE_ADVICE = {
    "not_signed_in": " You are not signed in to a cloud account, so nothing can be saved permanently. "
                     "Sign in from the sidebar Account section, then press Save again.",
    "account_unresolved": " Your cloud account could not be resolved. Sign in again, then press Save again.",
    "cloud_not_configured": " Cloud storage is not configured for this deployment, so permanent saving is "
                            "unavailable here.",
    "stale_revision_conflict": " Another device or tab saved a newer version, so this save was refused to avoid "
                               "overwriting it. Use 'Load cloud version and keep my edits', then Save again.",
    "policy_blocked": " The cloud write was deferred by the egress policy. Press Retry cloud save.",
    "readback_mismatch": " The cloud write was acknowledged but the stored copy did not match. Press Retry cloud save.",
    "readback_failed": " The cloud copy could not be read back to confirm it. Press Retry cloud save.",
    "cloud_write_failed": " The cloud write did not complete. Check your connection and press Retry cloud save.",
}


def save_feedback(result: dict[str, Any]) -> tuple[str, str]:
    if result.get("cloud_verified"):
        return "success", "Composition saved to the cloud and its complete contents verified."
    advice = _FAILURE_ADVICE.get(str(result.get("failure_code") or ""), "")
    if result.get("disk_verified"):
        return "warning", _LOCAL_COPY + advice + (_KEPT if advice else "")
    return "error", ("Your composition is still in this session. No persistent save was verified; keep this tab "
                     "open and retry saving." + advice)
