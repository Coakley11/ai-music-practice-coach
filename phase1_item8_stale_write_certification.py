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


def _bool(session: dict[str, Any], key: str) -> bool | None:
    if key not in session and key.replace("_", "") not in str(session.keys()):
        raw = None
    else:
        raw = session.get(key)
    if raw is None:
        return None
    return bool(raw)


def collect_phase1_item8_stale_write_certification(session: dict[str, Any]) -> dict[str, Any]:
    from music_workspace_cloud_save import collect_save_transaction_diagnostics
    from music_workspace_conditional_cloud_write import ITEM8_DIAG_KEY, ITEM8_VIOLATIONS_KEY
    from workspace_revision import collect_workspace_revision_diagnostics

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

    dirty_preserved = False
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

    return {
        "device_applied_revision": item8.get("device_applied_revision")
        or rev.get("applied_workspace_revision"),
        "candidate_revision": item8.get("candidate_revision") or tx.get("envelope_revision_after"),
        "precondition_expected_revision": item8.get("precondition_expected_revision")
        or item8.get("device_applied_revision"),
        "authoritative_revision_before_write": item8.get("authoritative_revision_before_write")
        or rev.get("cloud_workspace_revision"),
        "cloud_revision_newer_than_applied": item8.get("cloud_revision_newer_than_applied")
        if "cloud_revision_newer_than_applied" in item8
        else rev.get("cloud_state_newer_than_local"),
        "conditional_write_attempted": item8.get("conditional_write_attempted")
        if "conditional_write_attempted" in item8
        else cloud_diag.get("conditional_write_attempted"),
        "conditional_write_rows_affected": item8.get("conditional_write_rows_affected")
        if "conditional_write_rows_affected" in item8
        else cloud_diag.get("conditional_write_rows_affected"),
        "conflict_detected": stale_blocked or rev.get("conflict_detected"),
        "stale_write_blocked": stale_blocked,
        "unconditional_upsert_attempted": item8.get("unconditional_upsert_attempted")
        or cloud_diag.get("unconditional_upsert_attempted"),
        "cloud_write_succeeded": cloud_ok and not stale_blocked,
        "cloud_save_ok": cloud_ok and not stale_blocked,
        "cloud_confirmed": cloud_confirmed and not stale_blocked,
        "dirty_state_preserved": dirty_preserved,
        "latest_network_revision": session.get("_phase1_item8_latest_network_revision")
        or latest_ctx.get("latest_network_revision"),
        "latest_network_workspace_context": latest_ctx or None,
        "violations": violations,
    }


def render_phase1_item8_stale_write_certification_panel(st: Any, session: dict[str, Any]) -> None:
    st.markdown(f"**{ITEM8_PANEL_HEADING}**")
    try:
        diag = collect_phase1_item8_stale_write_certification(session)
    except Exception as exc:
        st.caption(f"`item8_certification_error`: {exc!r}")
        return
    for key in ITEM8_PANEL_KEYS:
        st.caption(f"`{key}`: {diag.get(key)!r}")


__all__ = [
    "ITEM8_PANEL_HEADING",
    "ITEM8_PANEL_KEYS",
    "collect_phase1_item8_stale_write_certification",
    "render_phase1_item8_stale_write_certification_panel",
]
