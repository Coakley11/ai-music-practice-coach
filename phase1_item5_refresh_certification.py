"""Phase 1 Item 5 — read-only refresh / cold-reboot certification diagnostics (?dev=1)."""

from __future__ import annotations

import copy
import hashlib
import uuid
from typing import Any

ITEM5_PANEL_HEADING = "Phase 1 Item 5 — Refresh / cold reboot certification"

ITEM5_PANEL_KEYS: tuple[str, ...] = (
    "certification_run_id",
    "session_start_kind",
    "fetch_source",
    "loaded_revision",
    "current_cloud_revision",
    "revision_unchanged",
    "revision_reserved_during_startup",
    "payload_built_during_startup",
    "cloud_write_attempted",
    "cloud_upsert_attempted",
    "startup_write_attempted",
    "restored_globals",
    "restored_studio_navigation",
    "restored_item1",
    "restored_item2",
    "restored_item3",
    "restored_item4",
    "item2_target_tuple",
    "item4_harmony_map",
    "example_artifact_context",
    "practice_lick_artifact_context",
    "envelope_required_fields_present",
    "item1_violations",
    "item2_violations",
    "item3_violations",
    "item4_violations",
    "passive_audit",
    "certification_failures",
    "certification_passed",
)


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _infer_session_start_kind(session: dict[str, Any]) -> str:
    explicit = str(session.get("_phase1_item5_session_start_kind") or "").strip()
    if explicit in ("hard_refresh", "cold_reboot"):
        return explicit
    apply_reason = str(session.get("_suite_persist_apply_reason") or "")
    if "cold_start_hydrate" in apply_reason or "first_sync" in apply_reason:
        return "cold_reboot"
    if session.get("_suite_already_synced_before_restore") and str(
        session.get("_music_last_cloud_fetch_source") or ""
    ).strip() == "network":
        return "hard_refresh"
    return "unknown"


def _artifact_context(blob: Any) -> dict[str, Any]:
    if not isinstance(blob, dict):
        return {"present": False}
    motif = blob.get("motif") if isinstance(blob.get("motif"), dict) else {}
    return {
        "present": True,
        "key_center": blob.get("key_center") or blob.get("display_key"),
        "motif_notes": copy.deepcopy(motif.get("notes")) if isinstance(motif, dict) else None,
        "variant": blob.get("variant"),
        "mission_title": blob.get("mission_title"),
    }


def _read_startup_pipeline(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "revision_reserved_during_startup": False,
        "payload_built_during_startup": False,
        "cloud_write_attempted": False,
        "cloud_upsert_attempted": False,
    }
    if session.get("_music_build_payload_attempted") or session.get("_suite_persist_payload_built"):
        out["payload_built_during_startup"] = True
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
    except ImportError:
        tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        suppressed = bool(
            session.get("startup_write_suppressed")
            or tx.get("duplicate_write_skipped")
            or tx.get("startup_suppressed")
        )
        if tx.get("reserved_write_revision") is not None and not suppressed:
            if tx.get("cloud_write_attempted") or tx.get("cloud_confirmed"):
                out["revision_reserved_during_startup"] = True
        if tx.get("cloud_write_attempted") and not suppressed:
            out["cloud_write_attempted"] = True
        if (tx.get("cloud_upsert_attempted") or tx.get("cloud_upsert_succeeded")) and not suppressed:
            out["cloud_upsert_attempted"] = True
        if tx.get("payload_build_attempted") and not suppressed:
            out["payload_built_during_startup"] = True
    if session.get("_music_cloud_save_entered"):
        out["cloud_write_attempted"] = True
    return out


def _item_violations(session: dict[str, Any]) -> tuple[list[Any], list[Any], list[Any], list[Any]]:
    v1: list[Any] = []
    v2: list[Any] = []
    v3: list[Any] = []
    v4: list[Any] = []
    try:
        from creative_tab_tool_persistence import collect_creative_tab_tool_diagnostics

        d1 = collect_creative_tab_tool_diagnostics(session)
        raw = d1.get("violations") if isinstance(d1, dict) else []
        v1 = list(raw) if isinstance(raw, list) else []
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import collect_creative_mission_config_diagnostics

        d2 = collect_creative_mission_config_diagnostics(session)
        raw = d2.get("violations") if isinstance(d2, dict) else []
        v2 = list(raw) if isinstance(raw, list) else []
    except ImportError:
        pass
    try:
        from creative_mission_artifact_persistence import collect_creative_mission_artifact_diagnostics

        d3 = collect_creative_mission_artifact_diagnostics(session)
        raw = d3.get("violations") if isinstance(d3, dict) else []
        v3 = list(raw) if isinstance(raw, list) else []
    except ImportError:
        pass
    try:
        from creative_context_snapshot_persistence import context_violations_for_current_run

        v4 = context_violations_for_current_run(session)
    except ImportError:
        pass
    return v1, v2, v3, v4


def _passive_audit_allowed(passive: Any) -> bool:
    if not isinstance(passive, dict):
        return True
    if passive.get("violations_suppressed") == "context_gather_blocked_for_passive_reason":
        if not passive.get("passive_save_requested") and not passive.get("passive_payload_built"):
            if not passive.get("passive_revision_reserved") and not passive.get("passive_cloud_write_attempted"):
                return True
    return not bool(passive.get("semantic_drift_keys")) or passive.get("would_gather_keys") == []


def _envelope_presence(session: dict[str, Any]) -> dict[str, bool] | None:
    try:
        from creative_context_snapshot_persistence import collect_creative_context_snapshot_diagnostics

        d = collect_creative_context_snapshot_diagnostics(session)
        pres = d.get("envelope_field_presence")
        return copy.deepcopy(pres) if isinstance(pres, dict) else None
    except ImportError:
        return None


def collect_phase1_item5_refresh_certification(session: dict[str, Any]) -> dict[str, Any]:
    """Read-only — must not mutate session, dirty flags, or routing."""

    loaded = session.get("startup_revision_loaded")
    if loaded is None:
        loaded = session.get("_suite_applied_workspace_revision")
    current = session.get("startup_revision_final")
    if current is None:
        current = session.get("_suite_applied_workspace_revision")
    if current is None:
        payload = session.get("_suite_last_cloud_fetch_payload")
        if isinstance(payload, dict):
            try:
                from workspace_revision import workspace_revision_from_blob

                current = workspace_revision_from_blob(payload)
            except ImportError:
                pass

    fetch_source = str(
        session.get("_music_last_cloud_fetch_source")
        or session.get("_suite_last_cloud_fetch_source")
        or ""
    ).strip() or None

    payload_ref = session.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload_ref, dict) and fetch_source == "network":
        try:
            from workspace_revision import workspace_revision_from_blob

            net_rev = workspace_revision_from_blob(payload_ref)
            if loaded is None:
                loaded = net_rev
            current = net_rev
        except ImportError:
            pass

    pipeline = _read_startup_pipeline(session)
    v1, v2, v3, v4 = _item_violations(session)

    passive_audit = None
    try:
        from creative_context_snapshot_persistence import collect_creative_context_snapshot_diagnostics

        d4 = collect_creative_context_snapshot_diagnostics(session)
        passive_audit = copy.deepcopy(d4.get("passive_audit"))
    except ImportError:
        pass

    try:
        from creative_mission_config_persistence import CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY

        startup_write = bool(session.get(CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY))
    except ImportError:
        startup_write = False

    globals_out = {
        "display_key": str(session.get("display_key") or "").strip(),
        "instrument": str(session.get("instrument") or "").strip(),
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
    }
    nav_out: dict[str, Any] = {"studio_page": str(session.get("studio_page") or "").strip().lower()}
    try:
        from mission_backing_handoff_persistence import collect_mission_backing_handoff_diagnostics

        handoff = collect_mission_backing_handoff_diagnostics(session)
        if isinstance(handoff, dict):
            nav_out["backing_subview"] = handoff.get("backing_subview_after") or handoff.get("backing_subview")
            nav_out["backing_context_source"] = handoff.get("backing_context_source")
    except ImportError:
        pass
    if not nav_out.get("backing_context_source"):
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None:
                nav_out["backing_subview"] = str(ctx.source or "")
                nav_out["backing_context_source"] = str(ctx.source or "")
        except ImportError:
            pass

    item1 = {
        "improv_intelligence_tab": session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab"),
        "improv_entry_mode": session.get("improv_entry_mode"),
        "creative_lab_analysis_mode": session.get("creative_lab_analysis_mode"),
    }
    item2_tuple = {
        "ii_selected_section": session.get("ii_selected_section"),
        "ii_selected_chord_index": session.get("ii_selected_chord_index"),
        "ii_selected_chord": session.get("ii_selected_chord"),
        "ii_selected_chord_label": session.get("ii_selected_chord_label"),
        "improv_ai_metric_ids": session.get("improv_ai_metric_ids"),
    }
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY
    except ImportError:
        MISSION_EXAMPLE_KEY = "improv_mission_example"
        MISSION_PRACTICE_LICK_KEY = "improv_mission_practice_lick"

    item3 = {
        "motif_present": bool(session.get("improv_motif")),
        "example_present": bool(session.get(MISSION_EXAMPLE_KEY)),
        "lick_present": bool(session.get(MISSION_PRACTICE_LICK_KEY)),
    }
    cs = session.get("creative_session")
    cs_tool = cs.get("tool_type") if isinstance(cs, dict) else None
    cs_key = None
    if isinstance(cs, dict):
        cs_key = cs.get("display_key") or cs.get("concert_key")
    item4 = {
        "harmony_map_section": session.get("harmony_map_section"),
        "harmony_map_chord": session.get("harmony_map_chord"),
        "creative_session_tool": cs_tool,
        "creative_session_display_key_snapshot": cs_key,
    }

    rev_loaded = int(loaded) if loaded is not None else None
    rev_current = int(current) if current is not None else None
    if rev_loaded is not None and fetch_source == "network":
        confirmed = session.get("_music_last_confirmed_cloud_revision")
        if confirmed is not None and int(confirmed) == rev_loaded:
            rev_current = rev_loaded
        elif session.get("startup_revision_final") == rev_loaded:
            rev_current = rev_loaded
        elif session.get("_suite_applied_workspace_revision") == rev_loaded:
            rev_current = rev_loaded
    revision_unchanged = (
        rev_loaded is not None and rev_current is not None and rev_loaded == rev_current
    )

    run_seq = _run_seq(session)
    cert_id = session.get("_phase1_item5_certification_run_id")
    if not cert_id:
        seed = f"{run_seq}|{rev_current}|{fetch_source}|{uuid.uuid4().hex[:8]}"
        cert_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    failures: list[str] = []
    if fetch_source != "network":
        failures.append("fetch_source_not_network")
    if rev_loaded is not None and rev_current is not None and rev_loaded != rev_current:
        failures.append("revision_changed_during_startup")
    if pipeline.get("revision_reserved_during_startup"):
        failures.append("revision_reserved_during_startup")
    if pipeline.get("payload_built_during_startup"):
        failures.append("payload_built_during_startup")
    if pipeline.get("cloud_write_attempted") or pipeline.get("cloud_upsert_attempted"):
        failures.append("cloud_write_during_startup")
    if startup_write:
        failures.append("startup_write_attempted")
    for label, viols in (
        ("item1", v1),
        ("item2", v2),
        ("item3", v3),
        ("item4", v4),
    ):
        if viols:
            failures.append(f"{label}_violations_nonempty")
    if not _passive_audit_allowed(passive_audit):
        failures.append("item4_passive_audit_not_allowed")

    certification_passed = len(failures) == 0 and fetch_source == "network"

    return {
        "certification_run_id": cert_id,
        "session_start_kind": _infer_session_start_kind(session),
        "fetch_source": fetch_source,
        "loaded_revision": rev_loaded,
        "current_cloud_revision": rev_current,
        "revision_unchanged": revision_unchanged,
        "revision_reserved_during_startup": pipeline["revision_reserved_during_startup"],
        "payload_built_during_startup": pipeline["payload_built_during_startup"],
        "cloud_write_attempted": pipeline["cloud_write_attempted"],
        "cloud_upsert_attempted": pipeline["cloud_upsert_attempted"],
        "startup_write_attempted": startup_write,
        "restored_globals": globals_out,
        "restored_studio_navigation": nav_out,
        "restored_item1": item1,
        "restored_item2": item2_tuple,
        "restored_item3": item3,
        "restored_item4": item4,
        "item2_target_tuple": item2_tuple,
        "item4_harmony_map": {
            "section": item4.get("harmony_map_section"),
            "chord": item4.get("harmony_map_chord"),
        },
        "example_artifact_context": _artifact_context(session.get(MISSION_EXAMPLE_KEY)),
        "practice_lick_artifact_context": _artifact_context(session.get(MISSION_PRACTICE_LICK_KEY)),
        "envelope_required_fields_present": _envelope_presence(session),
        "item1_violations": v1,
        "item2_violations": v2,
        "item3_violations": v3,
        "item4_violations": v4,
        "passive_audit": passive_audit,
        "certification_failures": failures,
        "certification_passed": certification_passed,
    }


def render_phase1_item5_refresh_certification_panel(st: Any, session: dict[str, Any]) -> None:
    st.markdown(f"**{ITEM5_PANEL_HEADING}**")
    try:
        diag = collect_phase1_item5_refresh_certification(session)
    except Exception as exc:
        st.caption(f"`certification_error`: {exc!r}")
        return
    for key in ITEM5_PANEL_KEYS:
        st.caption(f"`{key}`: {diag.get(key)!r}")


__all__ = [
    "ITEM5_PANEL_HEADING",
    "ITEM5_PANEL_KEYS",
    "collect_phase1_item5_refresh_certification",
    "render_phase1_item5_refresh_certification_panel",
]
