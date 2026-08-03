"""Phase 1 Item 8 — read-only stale-device write protection diagnostics (?dev=1)."""

from __future__ import annotations

from typing import Any

ITEM8_PANEL_HEADING = "Phase 1 Item 8 — Stale-device revision protection"

ITEM8_PANEL_KEYS: tuple[str, ...] = (
    "device_applied_revision",
    "candidate_revision",
    "precondition_expected_revision",
    "authoritative_revision_before_write",
    "cloud_revision_newer_than_applied",
    "conditional_write_attempted",
    "conditional_write_rows_affected",
    "conflict_detected",
    "stale_write_blocked",
    "unconditional_upsert_attempted",
    "cloud_write_succeeded",
    "cloud_save_ok",
    "cloud_confirmed",
    "dirty_state_preserved",
    "latest_network_revision",
    "latest_network_workspace_context",
    "violations",
)


def default_item8_dev_diag(_session: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit defaults for ?dev=1 panel before any stale-write or cloud-save event."""
    return {
        "device_applied_revision": None,
        "candidate_revision": None,
        "precondition_expected_revision": None,
        "authoritative_revision_before_write": None,
        "cloud_revision_newer_than_applied": None,
        "conditional_write_attempted": None,
        "conditional_write_rows_affected": None,
        "conflict_detected": False,
        "stale_write_blocked": False,
        "unconditional_upsert_attempted": None,
        "cloud_write_succeeded": None,
        "cloud_save_ok": None,
        "cloud_confirmed": None,
        "dirty_state_preserved": None,
        "latest_network_revision": None,
        "latest_network_workspace_context": None,
        "violations": [],
    }


def collect_phase1_item8_stale_write_certification(session: dict[str, Any]) -> dict[str, Any]:
    base = default_item8_dev_diag(session)
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics
        from music_workspace_conditional_cloud_write import ITEM8_DIAG_KEY, ITEM8_VIOLATIONS_KEY
        from workspace_revision import collect_workspace_revision_diagnostics
    except ImportError:
        return base

    tx = collect_save_transaction_diagnostics(session)
    item8 = session.get(ITEM8_DIAG_KEY)
    item8 = dict(item8) if isinstance(item8, dict) else {}
    rev = collect_workspace_revision_diagnostics(session)
    cloud_diag = session.get("_suite_last_cloud_save_result")
    cloud_diag = dict(cloud_diag) if isinstance(cloud_diag, dict) else {}

    violations = list(session.get(ITEM8_VIOLATIONS_KEY) or [])
    stale_blocked = bool(
        session.get("_music_stale_write_blocked")
        or session.get("stale_write_blocked")
        or item8.get("stale_write_blocked")
        or cloud_diag.get("stale_write_blocked")
    )
    cloud_ok = bool(tx.get("cloud_write_succeeded") or cloud_diag.get("cloud_upsert_succeeded"))
    cloud_confirmed = bool(tx.get("cloud_confirmed"))
    if stale_blocked and cloud_confirmed:
        violations.append("CONFLICT_WRITE_REPORTED_CONFIRMED")
    if stale_blocked and tx.get("dirty_cleared_after_confirmed_save"):
        violations.append("STALE_WRITE_CLEARED_DIRTY_STATE")

    dirty_preserved: bool | None = None
    try:
        from suite_user_persistence import _local_dirty_key

        dirty_preserved = bool(session.get(_local_dirty_key("music")))
    except ImportError:
        dirty_preserved = bool(session.get("_suite_local_dirty::music"))
    if stale_blocked:
        dirty_preserved = dirty_preserved or not cloud_confirmed

    latest_ctx = session.get("_phase1_item8_latest_network_context")
    if not isinstance(latest_ctx, dict):
        latest_ctx = {}

    merged = {
        **base,
        "device_applied_revision": item8.get("device_applied_revision")
        if item8.get("device_applied_revision") is not None
        else rev.get("applied_workspace_revision"),
        "candidate_revision": item8.get("candidate_revision")
        if item8.get("candidate_revision") is not None
        else tx.get("envelope_revision_after"),
        "precondition_expected_revision": item8.get("precondition_expected_revision")
        if item8.get("precondition_expected_revision") is not None
        else item8.get("device_applied_revision"),
        "authoritative_revision_before_write": item8.get("authoritative_revision_before_write")
        if item8.get("authoritative_revision_before_write") is not None
        else rev.get("cloud_workspace_revision"),
        "cloud_revision_newer_than_applied": item8.get("cloud_revision_newer_than_applied")
        if "cloud_revision_newer_than_applied" in item8
        else rev.get("cloud_state_newer_than_local"),
        "conditional_write_attempted": item8.get("conditional_write_attempted")
        if "conditional_write_attempted" in item8
        else cloud_diag.get("conditional_write_attempted"),
        "conditional_write_rows_affected": item8.get("conditional_write_rows_affected")
        if "conditional_write_rows_affected" in item8
        else cloud_diag.get("conditional_write_rows_affected"),
        "conflict_detected": stale_blocked or bool(rev.get("conflict_detected")),
        "stale_write_blocked": stale_blocked,
        "unconditional_upsert_attempted": item8.get("unconditional_upsert_attempted")
        if item8.get("unconditional_upsert_attempted") is not None
        else cloud_diag.get("unconditional_upsert_attempted"),
        "cloud_write_succeeded": (cloud_ok and not stale_blocked) if tx or cloud_diag else None,
        "cloud_save_ok": (cloud_ok and not stale_blocked) if tx or cloud_diag else None,
        "cloud_confirmed": (cloud_confirmed and not stale_blocked) if tx or cloud_diag else None,
        "dirty_state_preserved": dirty_preserved,
        "latest_network_revision": session.get("_phase1_item8_latest_network_revision")
        or latest_ctx.get("latest_network_revision"),
        "latest_network_workspace_context": latest_ctx if latest_ctx else None,
        "violations": violations,
    }
    return {k: merged.get(k) for k in ITEM8_PANEL_KEYS}


def render_phase1_item8_stale_write_certification_panel(st: Any, session: dict[str, Any]) -> None:
    st.markdown(f"**{ITEM8_PANEL_HEADING}**")
    diag = default_item8_dev_diag(session)
    try:
        diag = collect_phase1_item8_stale_write_certification(session)
    except Exception as exc:
        st.caption(f"`item8_certification_error`: {exc!r}")
    for key in ITEM8_PANEL_KEYS:
        st.caption(f"`{key}`: {diag.get(key)!r}")


__all__ = [
    "ITEM8_PANEL_HEADING",
    "ITEM8_PANEL_KEYS",
    "collect_phase1_item8_stale_write_certification",
    "default_item8_dev_diag",
    "render_phase1_item8_stale_write_certification_panel",
]
