"""Creative tool/tab selectors — canonical creative_workspace_state ownership (?dev=1 diagnostics)."""

from __future__ import annotations

import copy
from typing import Any, Callable

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    mark_creative_workspace_state_dirty,
    write_canonical_creative_workspace,
)

CREATIVE_TAB_TOOL_DIAG_KEY = "_creative_tab_tool_diag"
CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY = "_creative_tab_tool_hydrated_snapshot"
CREATIVE_TAB_MIGRATION_DONE_KEY = "_creative_tab_tool_migration_applied"
CREATIVE_TAB_USER_EVENT_KEY = "_creative_tab_tool_last_user_event"

SAVE_REASON_TAB = "creative_tab_change"
SAVE_REASON_TOOL = "creative_tool_change"

VIOLATION_WIDGET_OVERWROTE = "CREATIVE_TAB_WIDGET_OVERWROTE_HYDRATION"
VIOLATION_PASSIVE_STARTUP_WRITE = "CREATIVE_TAB_PASSIVE_STARTUP_WRITE"
VIOLATION_SAVE_NOT_CONFIRMED = "CREATIVE_TAB_SAVE_NOT_CONFIRMED"
VIOLATION_CREATED_PAGE_CHANGE = "CREATIVE_TAB_CREATED_PAGE_CHANGE"
VIOLATION_MULTIPLE_OWNERS = "CREATIVE_TAB_MULTIPLE_CANONICAL_OWNERS"

# Canonical field → widget key (when different), mirror keys in blob+session, normalizer, save reason.
_SELECTOR_SPECS: tuple[dict[str, Any], ...] = (
    {
        "canonical": "improv_intelligence_tab",
        "widget": "improv_intelligence_tab",
        "mirrors": ("creative_improv_intelligence_tab",),
        "normalize": "_normalize_improv_tab",
        "save_reason": SAVE_REASON_TAB,
        "user_touch_flag": "_improv_tab_user_touched",
    },
    {
        "canonical": "improv_entry_mode",
        "widget": "improv_entry_mode",
        "mirrors": (),
        "normalize": "_normalize_entry_mode",
        "save_reason": SAVE_REASON_TOOL,
        "user_touch_flag": "_improv_tab_user_touched",
    },
    {
        "canonical": "creative_lab_analysis_mode",
        "widget": "creative_lab_analysis_mode",
        "mirrors": ("creative_lab_last_mode",),
        "normalize": "_normalize_analysis_mode",
        "save_reason": SAVE_REASON_TOOL,
        "user_touch_flag": "_creative_mode_user_touched",
    },
)

_ANALYSIS_MODE_OPTIONS: tuple[str, ...] = (
    "Deep Harmonic Analyzer",
    "Improvisation Intelligence",
    "Creative Arrangement Assistant",
    "Adaptive Weakness Detection",
    "AI-Guided Musical Development Tracking",
)


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(CREATIVE_TAB_TOOL_DIAG_KEY)
    if not isinstance(d, dict):
        d = {}
        session[CREATIVE_TAB_TOOL_DIAG_KEY] = d
    return d


def record_creative_tab_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)


def _normalize_improv_tab(value: str) -> str:
    try:
        from creative_session_state import _normalize_improv_intelligence_tab

        return _normalize_improv_intelligence_tab(value)
    except ImportError:
        from studio_page_state import IMPROV_TAB_NAMES

        text = str(value or "").strip()
        return text if text in IMPROV_TAB_NAMES else IMPROV_TAB_NAMES[0]


def _normalize_entry_mode(value: str) -> str:
    from studio_page_state import IMPROV_ENTRY_MODES

    text = str(value or "").strip()
    return text if text in IMPROV_ENTRY_MODES else IMPROV_ENTRY_MODES[0]


def _normalize_analysis_mode(value: str) -> str:
    text = str(value or "").strip()
    if text in _ANALYSIS_MODE_OPTIONS:
        return text
    legacy = {
        "deep": "Deep Harmonic Analyzer",
        "improvisation": "Improvisation Intelligence",
        "improv": "Improvisation Intelligence",
    }
    mapped = legacy.get(text.lower())
    if mapped:
        return mapped
    return _ANALYSIS_MODE_OPTIONS[0]


_NORMALIZERS: dict[str, Callable[[str], str]] = {
    "_normalize_improv_tab": _normalize_improv_tab,
    "_normalize_entry_mode": _normalize_entry_mode,
    "_normalize_analysis_mode": _normalize_analysis_mode,
}


def _spec_for_field(field: str) -> dict[str, Any] | None:
    for spec in _SELECTOR_SPECS:
        if spec["canonical"] == field or spec["widget"] == field:
            return spec
    return None


def _normalize_for_spec(spec: dict[str, Any], value: str) -> str:
    fn_name = str(spec.get("normalize") or "")
    fn = _NORMALIZERS.get(fn_name)
    if fn:
        return fn(value)
    return str(value or "").strip()


def canonical_creative_selector_value(session: dict[str, Any], field: str) -> str:
    spec = _spec_for_field(field)
    if not spec:
        return str(session.get(field) or "").strip()
    canon_key = str(spec["canonical"])
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict) and canon_key in blob:
        raw = str(blob.get(canon_key) or "").strip()
        if raw:
            return _normalize_for_spec(spec, raw)
    for key in (*spec.get("mirrors", ()), canon_key):
        raw = str(session.get(key) or "").strip()
        if raw:
            return _normalize_for_spec(spec, raw)
    return ""


def _ensure_canonical_blob(session: dict[str, Any]) -> dict[str, Any]:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict):
        return copy.deepcopy(blob)
    return default_creative_workspace_state()


def commit_creative_selector_to_canonical(
    session: dict[str, Any],
    field: str,
    value: str,
    *,
    reason: str,
    projection_source: str = "user_selection",
) -> str:
    spec = _spec_for_field(field)
    if not spec:
        return str(value or "").strip()
    canon_key = str(spec["canonical"])
    normalized = _normalize_for_spec(spec, value)
    blob = _ensure_canonical_blob(session)
    prior = str(blob.get(canon_key) or "").strip()
    blob[canon_key] = normalized
    for mirror in spec.get("mirrors", ()):
        blob[str(mirror)] = normalized
    write_canonical_creative_workspace(session, blob, reason=reason)
    session[str(spec["widget"])] = normalized
    for mirror in spec.get("mirrors", ()):
        session[str(mirror)] = normalized
    d = _diag(session)
    canon_blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(canon_blob, dict):
        d["canonical_values"] = {s["canonical"]: canon_blob.get(s["canonical"]) for s in _SELECTOR_SPECS}
    d["widget_values"] = {s["widget"]: session.get(s["widget"]) for s in _SELECTOR_SPECS}
    d["projection_source"] = projection_source
    if prior and prior != normalized:
        d["last_canonical_change"] = {canon_key: {"from": prior, "to": normalized}}
    return normalized


def migrate_invalid_creative_selectors(session: dict[str, Any], *, source: str = "hydrate") -> list[str]:
    """Normalize invalid stored selector values in canonical blob (no cloud write)."""
    if session.get(CREATIVE_TAB_MIGRATION_DONE_KEY):
        return []
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(blob, dict):
        session[CREATIVE_TAB_MIGRATION_DONE_KEY] = True
        return []
    migrated: list[str] = []
    for spec in _SELECTOR_SPECS:
        canon_key = str(spec["canonical"])
        if canon_key not in blob and not any(blob.get(m) for m in spec.get("mirrors", ())):
            continue
        raw = str(blob.get(canon_key) or "").strip()
        if not raw:
            for mirror in spec.get("mirrors", ()):
                raw = str(blob.get(mirror) or "").strip()
                if raw:
                    break
        normalized = _normalize_for_spec(spec, raw)
        if raw and raw == normalized and canon_key in blob:
            continue
        if raw != normalized or (raw and canon_key not in blob):
            migrated.append(canon_key)
            blob[canon_key] = normalized
            for mirror in spec.get("mirrors", ()):
                blob[str(mirror)] = normalized
            session["_creative_tab_migration_reason"] = f"{source}:{canon_key}:{raw or 'missing'}->{normalized}"
    if migrated:
        write_canonical_creative_workspace(session, blob, reason="migration_local")
        d = _diag(session)
        d["migrated_fields"] = migrated
        d["migration_reason"] = session.get("_creative_tab_migration_reason")
    session[CREATIVE_TAB_MIGRATION_DONE_KEY] = True
    return migrated


def snapshot_hydrated_creative_selectors(session: dict[str, Any], *, source: str = "prepare") -> None:
    snap: dict[str, str] = {}
    for spec in _SELECTOR_SPECS:
        canon_key = str(spec["canonical"])
        snap[canon_key] = canonical_creative_selector_value(session, canon_key)
    session[CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY] = snap
    d = _diag(session)
    d["hydrated_tool_tab_values"] = dict(snap)
    d["hydration_source"] = source


def project_creative_selectors_from_canonical(session: dict[str, Any], *, overwrite: bool = False) -> None:
    for spec in _SELECTOR_SPECS:
        canon_key = str(spec["canonical"])
        val = canonical_creative_selector_value(session, canon_key)
        if not val:
            continue
        widget = str(spec["widget"])
        if overwrite or not str(session.get(widget) or "").strip():
            session[widget] = val
        for mirror in spec.get("mirrors", ()):
            if overwrite or not str(session.get(mirror) or "").strip():
                session[mirror] = val
    d = _diag(session)
    d["projection_source"] = "creative_workspace_state"
    d["widget_values"] = {s["widget"]: session.get(s["widget"]) for s in _SELECTOR_SPECS}


def note_selector_restore_overwrite(
    session: dict[str, Any],
    field: str,
    *,
    before: str,
    after: str,
    overwrite_source: str,
) -> None:
    snap = session.get(CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    canon = _spec_for_field(field)
    if not canon:
        return
    key = str(canon["canonical"])
    hydrated = str(snap.get(key) or "").strip()
    if not hydrated or session.get(canon.get("user_touch_flag")):
        return
    if hydrated != before and after != hydrated:
        record_creative_tab_violation(
            session,
            VIOLATION_WIDGET_OVERWROTE,
            detail=f"{key}:{hydrated}->{after} via {overwrite_source}",
        )
        d = _diag(session)
        d["overwrite_source"] = overwrite_source


def hydrate_improv_intelligence_tab_from_canonical(session_state: dict) -> str:
    """Prefer canonical tab before radio defaults (post-restore)."""
    if session_state.get("_improv_tab_user_touched"):
        return ""
    if session_state.get("_creative_restore_from_backing"):
        return ""
    tab = canonical_creative_selector_value(session_state, "improv_intelligence_tab")
    if not tab:
        return ""
    before = str(session_state.get("improv_intelligence_tab") or "").strip()
    if before != tab:
        note_selector_restore_overwrite(
            session_state,
            "improv_intelligence_tab",
            before=before,
            after=tab,
            overwrite_source="ensure_improv_intelligence_tab_restored",
        )
        session_state["improv_intelligence_tab"] = tab
        session_state["creative_improv_intelligence_tab"] = tab
    return tab


def record_creative_tab_save_outcome(session: dict[str, Any], *, save_reason: str, ok: bool) -> None:
    d = _diag(session)
    d["save_reason"] = save_reason
    d["user_selection_event"] = session.get(CREATIVE_TAB_USER_EVENT_KEY)
    d["startup_write_attempted"] = bool(session.get("_creative_tab_startup_write_flag"))
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        d["reserved_revision"] = tx.get("reserved_write_revision") or tx.get("envelope_revision_after")
        d["confirmed_revision"] = tx.get("cloud_readback_revision")
        d["cloud_confirmed"] = tx.get("cloud_confirmed")
        if save_reason in (SAVE_REASON_TAB, SAVE_REASON_TOOL) and not ok:
            record_creative_tab_violation(session, VIOLATION_SAVE_NOT_CONFIRMED)
        elif save_reason in (SAVE_REASON_TAB, SAVE_REASON_TOOL) and ok and tx.get("cloud_confirmed") is False:
            record_creative_tab_violation(session, VIOLATION_SAVE_NOT_CONFIRMED, detail="readback")
    except ImportError:
        pass
    if save_reason == "page_change" and session.get(CREATIVE_TAB_USER_EVENT_KEY):
        record_creative_tab_violation(session, VIOLATION_CREATED_PAGE_CHANGE)
    try:
        from suite_user_persistence import load_current_state

        _ = load_current_state  # noqa: F841 — optional refetch hook for diagnostics
        d["authoritative_refetched_values"] = {
            s["canonical"]: canonical_creative_selector_value(session, s["canonical"]) for s in _SELECTOR_SPECS
        }
    except ImportError:
        d["authoritative_refetched_values"] = {
            s["canonical"]: canonical_creative_selector_value(session, s["canonical"]) for s in _SELECTOR_SPECS
        }


def request_creative_selector_cloud_save(session: dict[str, Any], *, save_reason: str) -> bool:
    try:
        import streamlit as st
    except ImportError:
        return False
    try:
        from music_persistent_state import build_music_disk_state, force_save_music_state

        ok = force_save_music_state(st, reason=save_reason)
        record_creative_tab_save_outcome(session, save_reason=save_reason, ok=bool(ok))
        return bool(ok)
    except ImportError:
        try:
            from music_workspace_cloud_save import force_music_workspace_save

            ok = force_music_workspace_save(
                st,
                reason=save_reason,
                build_state=build_music_disk_state,
            )
            record_creative_tab_save_outcome(session, save_reason=save_reason, ok=bool(ok))
            return bool(ok)
        except ImportError:
            return False


def handle_user_creative_selector_change(session: dict[str, Any], field: str) -> None:
    spec = _spec_for_field(field)
    if not spec:
        return
    widget = str(spec["widget"])
    raw = str(session.get(widget) or "").strip()
    save_reason = str(spec.get("save_reason") or SAVE_REASON_TOOL)
    touch_flag = spec.get("user_touch_flag")
    if touch_flag:
        session[touch_flag] = True
    session[CREATIVE_TAB_USER_EVENT_KEY] = {"field": spec["canonical"], "value": raw}
    mark_creative_workspace_state_dirty(session, reason=save_reason)
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass
    commit_creative_selector_to_canonical(
        session,
        spec["canonical"],
        raw,
        reason=save_reason,
        projection_source="user_selection",
    )
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "creative")
    except ImportError:
        pass
    request_creative_selector_cloud_save(session, save_reason=save_reason)


def note_passive_creative_tab_persist(session: dict[str, Any], *, reason: str) -> None:
    """Detect tab/tool fields entering a save envelope without a user selector event."""
    if reason in (SAVE_REASON_TAB, SAVE_REASON_TOOL):
        return
    if reason == "page_change":
        return
    snap = session.get(CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if session.get(CREATIVE_TAB_USER_EVENT_KEY):
        return
    for spec in _SELECTOR_SPECS:
        key = str(spec["canonical"])
        if canonical_creative_selector_value(session, key) != str(snap.get(key) or ""):
            session["_creative_tab_startup_write_flag"] = True
            record_creative_tab_violation(session, VIOLATION_PASSIVE_STARTUP_WRITE, detail=reason)
            break


def audit_multiple_canonical_owners(session: dict[str, Any]) -> None:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(blob, dict):
        return
    for spec in _SELECTOR_SPECS:
        canon_key = str(spec["canonical"])
        if canon_key not in blob:
            continue
        canon_val = blob.get(canon_key)
        for mirror in spec.get("mirrors", ()):
            if mirror in blob and blob.get(mirror) != canon_val:
                record_creative_tab_violation(
                    session,
                    VIOLATION_MULTIPLE_OWNERS,
                    detail=f"{canon_key}!={mirror}",
                )


def collect_creative_tab_tool_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    d = dict(_diag(session))
    d.setdefault("hydrated_tool_tab_values", session.get(CREATIVE_TAB_HYDRATED_SNAPSHOT_KEY))
    d.setdefault(
        "canonical_values",
        {
            s["canonical"]: (
                (session.get(CREATIVE_WORKSPACE_STATE_KEY) or {}).get(s["canonical"])
                if isinstance(session.get(CREATIVE_WORKSPACE_STATE_KEY), dict)
                else None
            )
            for s in _SELECTOR_SPECS
        },
    )
    d.setdefault("widget_values", {s["widget"]: session.get(s["widget"]) for s in _SELECTOR_SPECS})
    audit_multiple_canonical_owners(session)
    return d


__all__ = [
    "CREATIVE_TAB_TOOL_DIAG_KEY",
    "SAVE_REASON_TAB",
    "SAVE_REASON_TOOL",
    "VIOLATION_CREATED_PAGE_CHANGE",
    "VIOLATION_MULTIPLE_OWNERS",
    "VIOLATION_PASSIVE_STARTUP_WRITE",
    "VIOLATION_SAVE_NOT_CONFIRMED",
    "VIOLATION_WIDGET_OVERWROTE",
    "canonical_creative_selector_value",
    "collect_creative_tab_tool_diagnostics",
    "commit_creative_selector_to_canonical",
    "handle_user_creative_selector_change",
    "hydrate_improv_intelligence_tab_from_canonical",
    "migrate_invalid_creative_selectors",
    "note_passive_creative_tab_persist",
    "project_creative_selectors_from_canonical",
    "record_creative_tab_save_outcome",
    "record_creative_tab_violation",
    "request_creative_selector_cloud_save",
    "snapshot_hydrated_creative_selectors",
]
