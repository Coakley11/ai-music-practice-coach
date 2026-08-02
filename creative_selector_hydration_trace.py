"""Dev trace: Creative selector hydration from cloud_restore (?dev=1)."""

from __future__ import annotations

import copy
from typing import Any

CREATIVE_SELECTOR_HYDRATION_TRACE_KEY = "_creative_selector_hydration_trace"
CREATIVE_SELECTOR_OVERWRITE_JOURNAL_KEY = "_creative_selector_overwrite_journal"
CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY = "_creative_selector_hydration_complete"
CREATIVE_SELECTOR_LAST_CONFIRMED_KEY = "_creative_selector_last_confirmed"

SELECTOR_CANONICAL_FIELDS: tuple[str, ...] = (
    "improv_intelligence_tab",
    "improv_entry_mode",
    "creative_lab_analysis_mode",
)

SELECTOR_MIRROR_FIELDS: tuple[str, ...] = (
    "creative_improv_intelligence_tab",
    "creative_lab_last_mode",
)

VIOLATION_CONFIRMED_MISSING_FROM_CLOUD = "CREATIVE_SELECTOR_CONFIRMED_VALUE_MISSING_FROM_CLOUD"
VIOLATION_HYDRATED_VALUE_CLEARED = "CREATIVE_SELECTOR_HYDRATED_VALUE_CLEARED"
VIOLATION_DEFAULT_OVERWROTE_RESTORE = "CREATIVE_SELECTOR_DEFAULT_OVERWROTE_RESTORE"
VIOLATION_DIAG_RAN_BEFORE_HYDRATION = "CREATIVE_SELECTOR_DIAGNOSTIC_RAN_BEFORE_HYDRATION"
VIOLATION_ALL_EMPTY_AFTER_RESTORE = "CREATIVE_SELECTOR_ALL_FIELDS_EMPTY_AFTER_CLOUD_RESTORE"

_LEGACY_SESSION_PATH = "session"
_TOP_CWS_PATH = "creative_workspace_state"
_NESTED_CWS_PATH = "music_workspace_state.creative_workspace_state"


def _trace(session: dict[str, Any]) -> dict[str, Any]:
    t = session.get(CREATIVE_SELECTOR_HYDRATION_TRACE_KEY)
    if not isinstance(t, dict):
        t = {}
        session[CREATIVE_SELECTOR_HYDRATION_TRACE_KEY] = t
    return t


def _journal(session: dict[str, Any]) -> list[dict[str, Any]]:
    j = session.get(CREATIVE_SELECTOR_OVERWRITE_JOURNAL_KEY)
    if not isinstance(j, list):
        j = []
        session[CREATIVE_SELECTOR_OVERWRITE_JOURNAL_KEY] = j
    return j


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _field_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    return False


def _payload_revision(payload: dict[str, Any]) -> int | None:
    for key in ("workspace_revision",):
        try:
            if payload.get(key) is not None:
                return int(payload[key])
        except (TypeError, ValueError):
            pass
    mws = payload.get("music_workspace_state")
    if isinstance(mws, dict) and mws.get("workspace_revision") is not None:
        try:
            return int(mws["workspace_revision"])
        except (TypeError, ValueError):
            return None
    return None


def _raw_selector_values(payload: dict[str, Any]) -> dict[str, Any]:
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    pws = payload.get("practice_workspace_state")
    mws = payload.get("music_workspace_state")
    top_cws = payload.get("creative_workspace_state")
    nested_cws = mws.get("creative_workspace_state") if isinstance(mws, dict) else None
    out: dict[str, Any] = {
        "core": payload.get("core") if isinstance(payload.get("core"), dict) else {},
        "session": {
            k: session_extra.get(k)
            for k in (*SELECTOR_CANONICAL_FIELDS, *SELECTOR_MIRROR_FIELDS)
            if isinstance(session_extra, dict)
        },
        "practice_workspace_state": (
            {k: pws.get(k) for k in SELECTOR_CANONICAL_FIELDS if isinstance(pws, dict) and k in pws}
            if isinstance(pws, dict)
            else {}
        ),
        "music_workspace_state": (
            {k: mws.get(k) for k in SELECTOR_CANONICAL_FIELDS if isinstance(mws, dict) and k in mws}
            if isinstance(mws, dict)
            else {}
        ),
        "creative_workspace_state": (
            {k: top_cws.get(k) for k in (*SELECTOR_CANONICAL_FIELDS, *SELECTOR_MIRROR_FIELDS) if isinstance(top_cws, dict)}
            if isinstance(top_cws, dict)
            else {}
        ),
        "nested_creative_workspace_state": (
            {
                k: nested_cws.get(k)
                for k in (*SELECTOR_CANONICAL_FIELDS, *SELECTOR_MIRROR_FIELDS)
                if isinstance(nested_cws, dict)
            }
            if isinstance(nested_cws, dict)
            else {}
        ),
        "legacy_mirrors": {
            "creative_improv_intelligence_tab": session_extra.get("creative_improv_intelligence_tab")
            if isinstance(session_extra, dict)
            else None,
            "creative_lab_last_mode": session_extra.get("creative_lab_last_mode")
            if isinstance(session_extra, dict)
            else None,
        },
    }
    return out


def record_raw_network_row(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    fetch_source: str = "",
    workspace_key: str = "",
) -> None:
    t = _trace(session)
    t["A_raw_network_row"] = {
        "fetched_revision": _payload_revision(payload),
        "workspace_account_key": workspace_key or str(session.get("_suite_cloud_workspace_key") or ""),
        "fetch_source": fetch_source or str(session.get("_music_last_cloud_fetch_source") or ""),
        "raw_selector_values": _raw_selector_values(payload),
    }


def record_envelope_extraction(
    session: dict[str, Any],
    field: str,
    *,
    source_path: str,
    extracted_value: Any,
    status: str,
    migration_source: str = "",
    migration_result: str = "",
) -> None:
    t = _trace(session)
    bucket = t.setdefault("B_envelope_extraction", {})
    if not isinstance(bucket, dict):
        bucket = {}
        t["B_envelope_extraction"] = bucket
    bucket[field] = {
        "source_path": source_path,
        "extracted_value": extracted_value,
        "status": status,
        "migration_source": migration_source or None,
        "migration_result": migration_result or None,
    }


def record_canonical_stage(
    session: dict[str, Any],
    stage: str,
    field: str,
    *,
    canonical_before: Any,
    incoming_value: Any,
    canonical_after: Any,
    widget_after: Any,
    function: str,
    branch: str = "",
    authoritative_restore: bool | None = None,
) -> None:
    t = _trace(session)
    stages = t.setdefault("C_canonical_application", {})
    if not isinstance(stages, dict):
        stages = {}
        t["C_canonical_application"] = stages
    stage_log = stages.setdefault(stage, [])
    if not isinstance(stage_log, list):
        stage_log = []
        stages[stage] = stage_log
    stage_log.append(
        {
            "field": field,
            "canonical_before": canonical_before,
            "incoming_hydrated_value": incoming_value,
            "canonical_after": canonical_after,
            "widget_after": widget_after,
            "function": function,
            "branch": branch or None,
            "run_seq": _run_seq(session),
            "authoritative_restore": authoritative_restore,
        }
    )


def record_selector_field_write(
    session: dict[str, Any],
    field: str,
    *,
    old_value: Any,
    new_value: Any,
    function: str,
    reason: str = "",
    authoritative_restore: bool = False,
    default_initialization: bool = False,
) -> None:
    if field not in SELECTOR_CANONICAL_FIELDS:
        return
    _journal(session).append(
        {
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "function": function,
            "reason": reason,
            "run_seq": _run_seq(session),
            "authoritative_restore": authoritative_restore,
            "default_initialization": default_initialization,
        }
    )


def mark_selector_hydration_complete(session: dict[str, Any], *, source: str = "") -> None:
    t = _trace(session)
    payload = session.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict) and not payload_has_selector_data(payload):
        session[CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY] = False
        t["hydration_complete"] = False
        t["hydration_status"] = "no_selector_state_in_authoritative_cloud_row"
        t["hydration_complete_source"] = source or None
        record_violation(session, VIOLATION_ALL_EMPTY_AFTER_RESTORE, detail="cloud_row_has_no_selector_fields")
        return
    session[CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY] = True
    t["hydration_complete"] = True
    t["hydration_status"] = "selectors_present_or_local_only"
    t["hydration_complete_source"] = source or None


def store_last_confirmed_selectors(session: dict[str, Any], values: dict[str, str]) -> None:
    clean = {k: str(v).strip() for k, v in values.items() if k in SELECTOR_CANONICAL_FIELDS and str(v or "").strip()}
    if not clean:
        return
    session[CREATIVE_SELECTOR_LAST_CONFIRMED_KEY] = copy.deepcopy(clean)


def merge_selector_fields_into_blob(
    target: dict[str, Any],
    *sources: Any,
    prefer_non_empty: bool = True,
) -> None:
    """Fill selector keys in target from sources without empty overwrites."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in (*SELECTOR_CANONICAL_FIELDS, *SELECTOR_MIRROR_FIELDS):
            if key not in src:
                continue
            val = src[key]
            if prefer_non_empty and _field_empty(val):
                continue
            if prefer_non_empty and not _field_empty(target.get(key)):
                continue
            target[key] = copy.deepcopy(val)


def extract_merged_creative_blob_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge all envelope locations for Creative workspace (selectors preserved)."""
    from creative_workspace_persistence import CREATIVE_WORKSPACE_KEYS
    from creative_workspace_state_persistence import (
        CREATIVE_WORKSPACE_STATE_KEY,
        default_creative_workspace_state,
        upgrade_creative_workspace_blob,
    )

    merged = default_creative_workspace_state()
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    legacy_session = {
        key: copy.deepcopy(session_extra[key])
        for key in CREATIVE_WORKSPACE_KEYS
        if isinstance(session_extra, dict) and key in session_extra
    }
    top = payload.get(CREATIVE_WORKSPACE_STATE_KEY)
    mws = payload.get("music_workspace_state")
    nested = mws.get(CREATIVE_WORKSPACE_STATE_KEY) if isinstance(mws, dict) else None

    for part in (legacy_session, nested if isinstance(nested, dict) else None, top if isinstance(top, dict) else None):
        if not isinstance(part, dict):
            continue
        for key, val in part.items():
            if key in CREATIVE_WORKSPACE_KEYS or key in ("schema_version", "updated_at"):
                if _field_empty(val) and key in merged and not _field_empty(merged.get(key)):
                    continue
                merged[key] = copy.deepcopy(val)

    merge_selector_fields_into_blob(merged, legacy_session, nested if isinstance(nested, dict) else None, top if isinstance(top, dict) else None)
    return upgrade_creative_workspace_blob(merged)


def payload_has_selector_data(payload: dict[str, Any]) -> bool:
    raw = _raw_selector_values(payload)
    for block in raw.values():
        if isinstance(block, dict):
            for val in block.values():
                if not _field_empty(val):
                    return True
    return False


def record_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    try:
        from creative_tab_tool_persistence import record_creative_tab_violation

        record_creative_tab_violation(session, code, detail=detail)
    except ImportError:
        pass


def audit_selector_hydration_after_restore(session: dict[str, Any]) -> None:
    """Post-restore diagnostic violations (distinct causes for empty selectors)."""
    try:
        from creative_tab_tool_persistence import canonical_creative_selector_value
        from studio_page_state import (
            CREATIVE_MAJOR_KEY_OPTIONS,
            IMPROV_ENTRY_MODES,
            IMPROV_TAB_NAMES,
        )
    except ImportError:
        return

    origin = str(session.get("_music_page_change_origin") or session.get("page_change_origin") or "").strip()
    is_cloud_restore = origin == "cloud_restore" or bool(session.get("_cloud_workspace_restored_this_run"))

    values = {f: canonical_creative_selector_value(session, f) for f in SELECTOR_CANONICAL_FIELDS}
    all_empty = all(_field_empty(v) for v in values.values())
    if not all_empty:
        return

    t = _trace(session)
    hydration_status = str(t.get("hydration_status") or "")
    hydration_done = bool(session.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY))
    if not hydration_done:
        if (
            hydration_status == "no_selector_state_in_authoritative_cloud_row"
            and is_cloud_restore
            and all_empty
        ):
            return
        record_violation(session, VIOLATION_DIAG_RAN_BEFORE_HYDRATION)
        t["hydration_status"] = "diagnostics_before_hydration_complete"
        return

    if not is_cloud_restore:
        return

    payload = session.get("_suite_last_cloud_fetch_payload")
    t = _trace(session)
    if isinstance(payload, dict) and not payload_has_selector_data(payload):
        session[CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY] = False
        t["hydration_complete"] = False
        t["hydration_status"] = "no_selector_state_in_authoritative_cloud_row"
        record_violation(session, VIOLATION_ALL_EMPTY_AFTER_RESTORE, detail="no_selector_data_in_cloud_row")
        return

    _ = (IMPROV_TAB_NAMES, IMPROV_ENTRY_MODES, CREATIVE_MAJOR_KEY_OPTIONS)


def collect_selector_hydration_trace(session: dict[str, Any]) -> dict[str, Any]:
    t = dict(_trace(session))
    t["overwrite_journal"] = list(_journal(session))
    complete = bool(session.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY))
    t["hydration_complete"] = complete
    if not complete and not t.get("hydration_status"):
        t["hydration_status"] = "pending_or_no_selector_state_in_cloud_row"
    t["last_confirmed_selectors"] = session.get(CREATIVE_SELECTOR_LAST_CONFIRMED_KEY)
    return t


__all__ = [
    "CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY",
    "CREATIVE_SELECTOR_HYDRATION_TRACE_KEY",
    "CREATIVE_SELECTOR_LAST_CONFIRMED_KEY",
    "SELECTOR_CANONICAL_FIELDS",
    "VIOLATION_ALL_EMPTY_AFTER_RESTORE",
    "VIOLATION_CONFIRMED_MISSING_FROM_CLOUD",
    "VIOLATION_DEFAULT_OVERWROTE_RESTORE",
    "VIOLATION_DIAG_RAN_BEFORE_HYDRATION",
    "VIOLATION_HYDRATED_VALUE_CLEARED",
    "audit_selector_hydration_after_restore",
    "collect_selector_hydration_trace",
    "extract_merged_creative_blob_from_payload",
    "mark_selector_hydration_complete",
    "merge_selector_fields_into_blob",
    "payload_has_selector_data",
    "record_canonical_stage",
    "record_envelope_extraction",
    "record_raw_network_row",
    "record_selector_field_write",
    "store_last_confirmed_selectors",
]
