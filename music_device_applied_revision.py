"""Device applied revision — authoritative hydrate + confirmed write only."""

from __future__ import annotations

from typing import Any

AUTHORITATIVE_HYDRATED_REVISION_KEY = "_music_authoritative_hydrated_revision"
DEVICE_APPLIED_REVISION_SOURCE_KEY = "_music_device_applied_revision_source"
DEVICE_APPLIED_REVISION_SET_STAGE_KEY = "_music_device_applied_revision_set_stage"
DEVICE_APPLIED_WORKSPACE_IDENTITY_KEY = "_music_device_applied_workspace_identity"


def _workspace_identity(session: dict[str, Any]) -> str:
    parts: list[str] = []
    try:
        from suite_user import get_account_user_id

        uid = str(get_account_user_id() or "").strip()
        if uid:
            parts.append(f"account:{uid}")
    except Exception:
        pass
    try:
        from suite_workspace import get_active_workspace_id

        ws = str(get_active_workspace_id() or "").strip()
        if ws:
            parts.append(f"workspace:{ws}")
    except Exception:
        pass
    try:
        from suite_workspace import scoped_cloud_app_id

        parts.append(f"app:{scoped_cloud_app_id('music')}")
    except Exception:
        parts.append("app:music")
    return "|".join(parts) if parts else "music"


def set_device_applied_revision_from_authoritative_hydrate(
    session: dict[str, Any],
    revision: int,
    *,
    stage: str,
    source: str = "authoritative_network_hydrate",
    payload: dict[str, Any] | None = None,
) -> int:
    """Set device_applied_revision only from authoritative hydrate (not reservation)."""
    try:
        from workspace_revision import (
            APPLIED_REVISION_KEY,
            CLOUD_REVISION_KEY,
            LOCAL_REVISION_KEY,
        )
    except ImportError:
        return 0

    rev = int(revision or 0)
    if rev <= 0 and isinstance(payload, dict):
        try:
            from workspace_revision import workspace_revision_from_blob

            rev = int(workspace_revision_from_blob(payload))
        except ImportError:
            rev = 0
    if rev <= 0:
        return 0

    session[APPLIED_REVISION_KEY] = rev
    session[CLOUD_REVISION_KEY] = rev
    session[LOCAL_REVISION_KEY] = max(int(session.get(LOCAL_REVISION_KEY) or 0), rev)
    session[AUTHORITATIVE_HYDRATED_REVISION_KEY] = rev
    session[DEVICE_APPLIED_REVISION_SOURCE_KEY] = str(source or "authoritative_network_hydrate")
    session[DEVICE_APPLIED_REVISION_SET_STAGE_KEY] = str(stage or "hydrate")
    session[DEVICE_APPLIED_WORKSPACE_IDENTITY_KEY] = _workspace_identity(session)
    try:
        from music_workspace_restore_mode import SELECTED_PAYLOAD_REVISION_KEY

        session[SELECTED_PAYLOAD_REVISION_KEY] = rev
    except ImportError:
        session["_music_selected_payload_revision"] = rev
    return rev


def confirm_device_applied_revision_after_successful_cas(
    session: dict[str, Any],
    confirmed_revision: int,
    *,
    stage: str = "cas_write_confirmed",
) -> int:
    """Update applied revision only after successful CAS + confirmation."""
    rev = int(confirmed_revision or 0)
    if rev <= 0:
        return 0
    return set_device_applied_revision_from_authoritative_hydrate(
        session,
        rev,
        stage=stage,
        source="cas_write_confirmed",
    )


def authoritative_hydrated_revision(session: dict[str, Any]) -> int:
    for key in (
        AUTHORITATIVE_HYDRATED_REVISION_KEY,
        "startup_revision_final",
        "startup_revision_loaded",
        "_music_selected_payload_revision",
    ):
        try:
            v = int(session.get(key) or 0)
        except (TypeError, ValueError):
            v = 0
        if v > 0:
            return v
    return 0


def _hydrate_markers_present(session: dict[str, Any]) -> bool:
    if session.get(AUTHORITATIVE_HYDRATED_REVISION_KEY):
        return True
    if session.get("_music_authoritative_payload_applied"):
        return True
    try:
        from music_startup_save_suppression import HYDRATED_CANONICAL_FP_KEY

        fp = str(session.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
        if fp and fp != "(none)":
            return True
    except ImportError:
        fp = str(session.get("_music_hydrated_canonical_fp") or "").strip()
        if fp and fp != "(none)":
            return True
    if session.get("_music_workspace_blob_hydrated"):
        return True
    return False


def resolve_device_applied_revision_for_cas(session: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve expected CAS revision from session.

    Does not treat uninitialized local state as missing cloud row.
    """
    from workspace_revision import APPLIED_REVISION_KEY

    violations: list[str] = []
    try:
        applied = int(session.get(APPLIED_REVISION_KEY) or 0)
    except (TypeError, ValueError):
        applied = 0

    hydrated = authoritative_hydrated_revision(session)
    source = str(session.get(DEVICE_APPLIED_REVISION_SOURCE_KEY) or "")
    stage = str(session.get(DEVICE_APPLIED_REVISION_SET_STAGE_KEY) or "")

    if applied <= 0 and hydrated > 0 and _hydrate_markers_present(session):
        violations.append("DEVICE_APPLIED_REVISION_NOT_INITIALIZED_FROM_HYDRATION")
        applied = hydrated
        set_device_applied_revision_from_authoritative_hydrate(
            session,
            hydrated,
            stage="cas_preflight_repair_from_hydrate_markers",
            source="cas_preflight_repair",
        )
        source = str(session.get(DEVICE_APPLIED_REVISION_SOURCE_KEY) or source)
        stage = str(session.get(DEVICE_APPLIED_REVISION_SET_STAGE_KEY) or stage)

    if applied <= 0 and _hydrate_markers_present(session):
        if "DEVICE_APPLIED_REVISION_NOT_INITIALIZED_FROM_HYDRATION" not in violations:
            violations.append("DEVICE_APPLIED_REVISION_NOT_INITIALIZED_FROM_HYDRATION")

    return {
        "device_applied_revision": applied,
        "authoritative_hydrated_revision": hydrated or session.get(AUTHORITATIVE_HYDRATED_REVISION_KEY),
        "device_applied_revision_source": source or None,
        "device_applied_revision_set_stage": stage or None,
        "device_applied_workspace_identity": session.get(DEVICE_APPLIED_WORKSPACE_IDENTITY_KEY)
        or _workspace_identity(session),
        "expected_revision": applied,
        "violations": violations,
        "create_path_allowed": applied <= 0 and not _hydrate_markers_present(session),
    }


def collect_revision_surface_trace(session: dict[str, Any]) -> dict[str, Any]:
    """Documented revision surfaces for Item 8 diagnostics."""
    from workspace_revision import (
        APPLIED_REVISION_KEY,
        CLOUD_REVISION_KEY,
        LAST_CONFIRMED_REVISION_KEY,
        LOCAL_REVISION_KEY,
        RESERVED_WRITE_REVISION_KEY,
    )

    return {
        "authoritative_hydrated_revision": session.get(AUTHORITATIVE_HYDRATED_REVISION_KEY),
        "startup_revision_loaded": session.get("startup_revision_loaded"),
        "startup_revision_final": session.get("startup_revision_final"),
        "selected_payload_revision": session.get("_music_selected_payload_revision"),
        "applied_workspace_revision": session.get(APPLIED_REVISION_KEY),
        "cloud_workspace_revision": session.get(CLOUD_REVISION_KEY),
        "local_workspace_revision": session.get(LOCAL_REVISION_KEY),
        "last_confirmed_cloud_revision": session.get(LAST_CONFIRMED_REVISION_KEY),
        "reserved_candidate_revision": session.get(RESERVED_WRITE_REVISION_KEY),
        "pending_save_revision": session.get("_music_pending_save_revision"),
        "envelope_revision_after": (session.get("_music_workspace_save_transaction") or {}).get(
            "envelope_revision_after"
        )
        if isinstance(session.get("_music_workspace_save_transaction"), dict)
        else None,
    }


__all__ = [
    "AUTHORITATIVE_HYDRATED_REVISION_KEY",
    "DEVICE_APPLIED_REVISION_SET_STAGE_KEY",
    "DEVICE_APPLIED_REVISION_SOURCE_KEY",
    "DEVICE_APPLIED_WORKSPACE_IDENTITY_KEY",
    "authoritative_hydrated_revision",
    "collect_revision_surface_trace",
    "confirm_device_applied_revision_after_successful_cas",
    "resolve_device_applied_revision_for_cas",
    "set_device_applied_revision_from_authoritative_hydrate",
]
