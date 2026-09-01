"""Creative tool/tab selectors — canonical creative_workspace_state ownership (?dev=1 diagnostics)."""

from __future__ import annotations

import copy
import uuid
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
CREATIVE_SELECTOR_LAST_TX_KEY = "_creative_selector_last_transaction"
CREATIVE_SELECTOR_PENDING_TX_KEY = "_creative_selector_pending_transaction"

SAVE_REASON_TAB = "creative_tab_change"
SAVE_REASON_TOOL = "creative_tool_change"
STARTUP_DEFAULT_PROJECTION_REASON = "startup_default_projection"

CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY = "_creative_selector_persistence_requested"
_CREATIVE_SELECTOR_LOCAL_DEFAULT_PREFIX = "_creative_selector_local_default_"

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
    # Nested SBI source tab (Active vs Custom) — distinct from top-level Custom page.
    {
        "canonical": "improv_song_source",
        "widget": "improv_song_source",
        "mirrors": ("sbi_preview_source",),
        "normalize": "_normalize_song_source",
        "save_reason": SAVE_REASON_TOOL,
        "user_touch_flag": "_improv_song_source_user_touched",
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


def selector_hydration_complete(session: dict[str, Any]) -> bool:
    try:
        from creative_selector_hydration_trace import CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY

        return bool(session.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY))
    except ImportError:
        return bool(session.get("_creative_selector_hydration_complete"))


def _local_default_flag(canon_key: str) -> str:
    return f"{_CREATIVE_SELECTOR_LOCAL_DEFAULT_PREFIX}{canon_key}"


def should_gather_selector_from_session(
    session: dict[str, Any],
    key: str,
    session_val: Any,
    *,
    persist_reason: str = "autosave",
) -> bool:
    """Block autosave from promoting widget-only defaults into canonical CWS."""
    spec = _spec_for_field(key)
    if not spec:
        return True
    canon_key = str(spec["canonical"])
    touch = spec.get("user_touch_flag")
    if touch and session.get(touch):
        return True
    if persist_reason in (SAVE_REASON_TAB, SAVE_REASON_TOOL):
        return True
    if session.get(CREATIVE_TAB_USER_EVENT_KEY):
        return True
    try:
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_RESTORED_KEY

        if session.get(CREATIVE_WORKSPACE_RESTORED_KEY) and not session.get("_creative_workspace_restored_applied"):
            return False
    except ImportError:
        pass
    if not selector_hydration_complete(session):
        return False
    canon = canonical_creative_selector_value(session, canon_key)
    canon_s = str(canon or "").strip()
    val_s = str(session_val or "").strip()
    if session.get(_local_default_flag(canon_key)):
        return False
    if canon_s and val_s != canon_s:
        return False
    if canon_s:
        return val_s == canon_s
    if persist_reason in ("autosave", "force_autosave", "", STARTUP_DEFAULT_PROJECTION_REASON):
        return False
    return True


def project_startup_default_selector(session: dict[str, Any], canon_key: str, value: str) -> str:
    """Widget-only default before any cloud persist (empty authoritative cloud row)."""
    spec = _spec_for_field(canon_key)
    if not spec:
        return str(value or "").strip()
    if not selector_hydration_complete(session):
        return ""
    if canonical_creative_selector_value(session, canon_key):
        return canonical_creative_selector_value(session, canon_key)
    normalized = _normalize_for_spec(spec, value)
    if not normalized:
        return ""
    widget = str(spec["widget"])
    session[widget] = normalized
    for mirror in spec.get("mirrors", ()):
        session[str(mirror)] = normalized
    session[_local_default_flag(canon_key)] = True
    d = _diag(session)
    projected = d.setdefault("local_default_projected", {})
    if isinstance(projected, dict):
        projected[canon_key] = normalized
    d["projection_source"] = STARTUP_DEFAULT_PROJECTION_REASON
    return normalized


def establish_canonical_selector_without_cloud_dirty(
    session: dict[str, Any],
    canon_key: str,
    value: str,
) -> str:
    """Runtime canonical for empty cloud — never triggers cloud save by itself."""
    spec = _spec_for_field(canon_key)
    if not spec:
        return str(value or "").strip()
    normalized = _normalize_for_spec(spec, value)
    if not normalized:
        return ""
    blob = _ensure_canonical_blob(session)
    if str(blob.get(canon_key) or "").strip():
        return str(blob.get(canon_key) or "").strip()
    blob[canon_key] = normalized
    for mirror in spec.get("mirrors", ()):
        blob[str(mirror)] = normalized
    write_canonical_creative_workspace(session, blob, reason=STARTUP_DEFAULT_PROJECTION_REASON)
    d = _diag(session)
    d["canonical_default_initialized_without_dirtying"] = True
    d.setdefault("local_default_projected", {})[canon_key] = normalized
    return normalized


def establish_selector_defaults_when_cloud_empty(session: dict[str, Any]) -> None:
    """After hydration: local UI defaults when authoritative cloud had no selector fields."""
    if not selector_hydration_complete(session):
        return
    try:
        from creative_selector_hydration_trace import payload_has_selector_data

        payload = session.get("_suite_last_cloud_fetch_payload")
        if isinstance(payload, dict) and payload_has_selector_data(payload):
            return
    except ImportError:
        pass
    try:
        from studio_page_state import IMPROV_ENTRY_MODES, IMPROV_TAB_NAMES
    except ImportError:
        IMPROV_TAB_NAMES = ("Entry & Jam",)
        IMPROV_ENTRY_MODES = ("Song-Based Improvisation",)
    defaults = {
        "improv_intelligence_tab": IMPROV_TAB_NAMES[0],
        "improv_entry_mode": IMPROV_ENTRY_MODES[0],
        "creative_lab_analysis_mode": "Deep Harmonic Analyzer",
    }
    for key, val in defaults.items():
        if canonical_creative_selector_value(session, key):
            continue
        project_startup_default_selector(session, key, val)


def record_creative_tab_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)


def _current_run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _selector_value_from_envelope(state: dict[str, Any], field: str) -> str:
    if not isinstance(state, dict):
        return ""
    blocks: list[dict[str, Any]] = [state]
    nested = state.get("music_workspace_state")
    if isinstance(nested, dict):
        blocks.append(nested)
    for block in blocks:
        cws = block.get("creative_workspace_state")
        if isinstance(cws, dict) and field in cws:
            return str(cws.get(field) or "").strip()
    session_extra = state.get("session")
    if isinstance(session_extra, dict) and field in session_extra:
        return str(session_extra.get(field) or "").strip()
    return ""


def _workspace_save_tx(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        return tx if isinstance(tx, dict) else {}
    except ImportError:
        tx = session.get("_music_workspace_save_transaction")
        return dict(tx) if isinstance(tx, dict) else {}


def _cloud_save_diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get("_suite_last_cloud_save_result")
    if isinstance(raw, dict):
        return dict(raw)
    raw2 = session.get("_music_last_cloud_save_diag")
    return dict(raw2) if isinstance(raw2, dict) else {}


def _cloud_workspace_key(session: dict[str, Any]) -> str:
    for key in (
        "_suite_cloud_workspace_key",
        "_music_cloud_workspace_key",
        "music_cloud_workspace_key",
    ):
        val = str(session.get(key) or "").strip()
        if val:
            return val
    return ""


def evaluate_selector_save_confirmation(
    session: dict[str, Any],
    *,
    field: str,
    new_value: str,
    save_reason: str,
    save_ok: bool,
) -> dict[str, Any]:
    """Selector-specific confirmation — never uses Studio page_change confirmation."""
    workspace_tx = _workspace_save_tx(session)
    cloud_diag = _cloud_save_diag(session)
    pending = session.get(CREATIVE_SELECTOR_PENDING_TX_KEY)
    pending_dict = pending if isinstance(pending, dict) else {}

    reserved_raw = workspace_tx.get("reserved_write_revision") or workspace_tx.get("envelope_revision_after")
    try:
        reserved_revision = int(reserved_raw) if reserved_raw is not None else None
    except (TypeError, ValueError):
        reserved_revision = None

    upsert_raw = cloud_diag.get("cloud_payload_revision") or workspace_tx.get("envelope_revision_after")
    try:
        revision_in_upsert_payload = int(upsert_raw) if upsert_raw is not None else None
    except (TypeError, ValueError):
        revision_in_upsert_payload = None

    refetch_raw = workspace_tx.get("cloud_readback_revision")
    try:
        authoritative_refetch_revision = int(refetch_raw) if refetch_raw is not None else None
    except (TypeError, ValueError):
        authoritative_refetch_revision = None

    fetch_source = str(session.get("_music_last_cloud_fetch_source") or "").strip()
    cache_bypassed = fetch_source == "network" and bool(workspace_tx.get("cloud_readback_attempted"))

    authoritative_refetched_value = _selector_value_from_envelope(
        session.get("_music_last_authoritative_cloud_state") or {},
        field,
    )

    cloud_key = _cloud_workspace_key(session)
    account_ok = bool(cloud_key) or bool(session.get("_suite_active_workspace"))

    checks = {
        "save_ok": bool(save_ok),
        "cloud_upsert_succeeded": bool(
            cloud_diag.get("cloud_upsert_succeeded") or workspace_tx.get("cloud_write_succeeded")
        ),
        "cache_bypassed_for_refetch": cache_bypassed,
        "refetch_revision_equals_reserved": (
            reserved_revision is not None
            and authoritative_refetch_revision is not None
            and int(authoritative_refetch_revision) == int(reserved_revision)
        ),
        "refetched_field_equals_selected": str(authoritative_refetched_value or "").strip() == str(new_value or "").strip(),
        "workspace_cloud_key_match": account_ok,
    }

    refetch_confirmed = all(
        (
            checks["save_ok"],
            checks["cloud_upsert_succeeded"],
            checks["cache_bypassed_for_refetch"],
            checks["refetch_revision_equals_reserved"],
            checks["refetched_field_equals_selected"],
            checks["workspace_cloud_key_match"],
        )
    )

    if refetch_confirmed:
        confirmation_status = "confirmed"
        confirmation_stage = "authoritative_refetch"
    else:
        confirmation_status = "unconfirmed"
        confirmation_stage = "evaluation_failed"

    confirmed_revision = authoritative_refetch_revision if checks["refetch_revision_equals_reserved"] else None

    return {
        "transaction_id": str(pending_dict.get("transaction_id") or uuid.uuid4().hex[:12]),
        "transaction_run_seq": pending_dict.get("transaction_run_seq", _current_run_seq(session)),
        "field": field,
        "old_value": pending_dict.get("old_value"),
        "new_value": new_value,
        "save_reason": save_reason,
        "reserved_revision": reserved_revision,
        "revision_in_upsert_payload": revision_in_upsert_payload,
        "authoritative_refetch_revision": authoritative_refetch_revision,
        "authoritative_refetched_value": authoritative_refetched_value,
        "confirmed_revision": confirmed_revision,
        "confirmation_checks": checks,
        "confirmation_status": confirmation_status,
        "confirmation_stage": confirmation_stage,
        "user_selection_event": copy.deepcopy(session.get(CREATIVE_TAB_USER_EVENT_KEY)),
        "authoritative_refetched_values": {
            s["canonical"]: canonical_creative_selector_value(session, s["canonical"]) for s in _SELECTOR_SPECS
        },
    }


def _refresh_selector_diag_display(session: dict[str, Any]) -> None:
    """Separate current-run selector activity from the last completed transaction."""
    d = _diag(session)
    run_seq = _current_run_seq(session)
    last_tx = session.get(CREATIVE_SELECTOR_LAST_TX_KEY)
    last_tx_dict = last_tx if isinstance(last_tx, dict) else None
    event = session.get(CREATIVE_TAB_USER_EVENT_KEY)
    if isinstance(event, dict) and int(event.get("run_seq") or 0) == run_seq:
        d["current_run_user_selection_event"] = copy.deepcopy(event)
    else:
        d["current_run_user_selection_event"] = None

    d["last_selector_transaction"] = copy.deepcopy(last_tx_dict) if last_tx_dict else None
    belongs = (
        isinstance(last_tx_dict, dict) and int(last_tx_dict.get("transaction_run_seq") or 0) == run_seq
    )
    d["belongs_to_current_run"] = belongs
    d["transaction_confirmed"] = (
        last_tx_dict.get("confirmation_status") == "confirmed" if last_tx_dict else None
    )

    if last_tx_dict:
        for key in (
            "user_selection_event",
            "save_reason",
            "reserved_revision",
            "confirmed_revision",
            "authoritative_refetched_values",
            "confirmation_status",
            "confirmation_stage",
            "confirmation_checks",
        ):
            if key in last_tx_dict:
                d[key] = last_tx_dict.get(key)

    violations = d.get("violations")
    if not isinstance(violations, list):
        violations = []
    if last_tx_dict and last_tx_dict.get("confirmation_status") == "confirmed":
        violations = [v for v in violations if v.get("code") != VIOLATION_SAVE_NOT_CONFIRMED]
    d["violations"] = violations


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


def _normalize_song_source(value: str) -> str:
    from studio_page_state import IMPROV_SONG_SOURCES

    text = str(value or "").strip()
    return text if text in IMPROV_SONG_SOURCES else IMPROV_SONG_SOURCES[0]


_NORMALIZERS: dict[str, Callable[[str], str]] = {
    "_normalize_improv_tab": _normalize_improv_tab,
    "_normalize_entry_mode": _normalize_entry_mode,
    "_normalize_analysis_mode": _normalize_analysis_mode,
    "_normalize_song_source": _normalize_song_source,
}


def _spec_for_field(field: str) -> dict[str, Any] | None:
    for spec in _SELECTOR_SPECS:
        if spec["canonical"] == field or spec["widget"] == field:
            return spec
        if field in spec.get("mirrors", ()):
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
        live_widget = str(session.get(widget) or "").strip()
        live_preview = str(session.get("sbi_preview_source") or "").strip()
        follow_active = False
        try:
            from source_session_state import sbi_must_follow_global_active

            follow_active = sbi_must_follow_global_active(session)
        except ImportError:
            follow_active = bool(session.get("_sbi_follow_active_after_explicit_catalog"))
        if canon_key == "improv_song_source" and follow_active:
            val = "Active song"
        elif canon_key == "improv_song_source" and not follow_active:
            last = str(session.get("_last_improv_song_source") or "").strip()
            explicit = str(session.get("_explicit_sbi_source_click") or "").strip()
            pending = str(session.get("_pending_improv_song_source") or "").strip()
            hydrated = bool(session.get("_sbi_song_source_hydrated"))
            live_is_click = live_widget in {
                "Active song",
                "Custom progression",
                "Composition",
            } and (
                explicit in {"Active song", "Custom progression", "Composition"}
                or pending in {"Active song", "Custom progression", "Composition"}
                or (hydrated and last and last != live_widget)
            )
            if live_is_click:
                for mirror in spec.get("mirrors", ()):
                    if overwrite or not str(session.get(mirror) or "").strip():
                        session[mirror] = live_widget
                continue
        keep_custom = (
            not follow_active
            and canon_key == "improv_song_source"
            and val != "Custom progression"
            and (
                live_widget == "Custom progression"
                or live_preview == "Custom progression"
                or bool(session.get("_restore_sbi_custom_source"))
            )
        )
        if keep_custom:
            if not session.get("_sbi_song_source_hydrated"):
                session[widget] = "Custom progression"
                for mirror in spec.get("mirrors", ()):
                    session[mirror] = "Custom progression"
            continue
        if overwrite or not live_widget:
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
    if save_reason not in (SAVE_REASON_TAB, SAVE_REASON_TOOL):
        if save_reason == "page_change" and session.get(CREATIVE_TAB_USER_EVENT_KEY):
            record_creative_tab_violation(session, VIOLATION_CREATED_PAGE_CHANGE)
        return

    event = session.get(CREATIVE_TAB_USER_EVENT_KEY)
    if not isinstance(event, dict):
        return

    field = str(event.get("field") or "").strip()
    new_value = str(event.get("value") or "").strip()
    tx_record: dict[str, Any]
    try:
        from creative_selector_save_durability_trace import (
            finalize_selector_save_confirmation,
            perform_authoritative_selector_refetch,
        )

        perform_authoritative_selector_refetch(session)
        tx_record = finalize_selector_save_confirmation(session, force_save_ok=bool(ok))
        tx_record["authoritative_refetched_values"] = {
            s["canonical"]: _selector_value_from_envelope(
                session.get("_creative_selector_authoritative_refetch_payload") or {},
                s["canonical"],
            )
            for s in _SELECTOR_SPECS
        }
    except ImportError:
        tx_record = {
            "confirmation_status": "unconfirmed",
            "confirmation_stage": "durability_trace_unavailable",
            "field": field,
            "new_value": new_value,
            "save_reason": save_reason,
        }
    session[CREATIVE_SELECTOR_LAST_TX_KEY] = copy.deepcopy(tx_record)
    session.pop(CREATIVE_SELECTOR_PENDING_TX_KEY, None)

    if tx_record.get("confirmation_status") == "confirmed":
        try:
            from creative_selector_hydration_trace import store_last_confirmed_selectors

            field = str((session.get(CREATIVE_TAB_USER_EVENT_KEY) or {}).get("field") or "")
            val = str((session.get(CREATIVE_TAB_USER_EVENT_KEY) or {}).get("value") or "")
            if field and val:
                store_last_confirmed_selectors(session, {field: val})
        except ImportError:
            pass

    d = _diag(session)
    d["startup_write_attempted"] = bool(session.get(CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY))
    d.update(
        {
            "save_reason": save_reason,
            "reserved_revision": tx_record.get("reserved_revision"),
            "confirmed_revision": tx_record.get("confirmed_revision"),
            "authoritative_refetched_values": tx_record.get("authoritative_refetched_values"),
            "confirmation_status": tx_record.get("confirmation_status"),
            "confirmation_stage": tx_record.get("confirmation_stage"),
            "confirmation_checks":         tx_record.get("confirmation_checks"),
            "selector_save_durability": tx_record.get("durability_trace"),
        }
    )
    d["cloud_upsert_attempted"] = bool(
        ((tx_record.get("durability_trace") or {}).get("D_supabase_result") or {}).get("request_attempted")
    )

    if tx_record.get("confirmation_status") != "confirmed":
        failed = [
            k for k, passed in (tx_record.get("confirmation_checks") or {}).items() if not passed
        ]
        record_creative_tab_violation(
            session,
            VIOLATION_SAVE_NOT_CONFIRMED,
            detail=",".join(failed) or str(tx_record.get("confirmation_stage")),
        )

    _refresh_selector_diag_display(session)


def request_creative_selector_cloud_save(session: dict[str, Any], *, save_reason: str) -> bool:
    d = _diag(session)
    d["cloud_save_requested"] = True
    session[CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY] = True
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
    session.pop(_local_default_flag(str(spec["canonical"])), None)
    old_value = canonical_creative_selector_value(session, str(spec["canonical"]))
    run_seq = _current_run_seq(session)
    tx_id = f"sel-{run_seq}-{uuid.uuid4().hex[:8]}"
    session[CREATIVE_SELECTOR_PENDING_TX_KEY] = {
        "transaction_id": tx_id,
        "transaction_run_seq": run_seq,
        "field": spec["canonical"],
        "old_value": old_value,
        "new_value": raw,
        "save_reason": save_reason,
    }
    session[CREATIVE_TAB_USER_EVENT_KEY] = {
        "field": spec["canonical"],
        "value": raw,
        "old_value": old_value,
        "run_seq": run_seq,
        "transaction_id": tx_id,
    }
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
    try:
        from creative_selector_save_durability_trace import begin_selector_save_durability

        begin_selector_save_durability(
            session,
            field=str(spec["canonical"]),
            old_value=old_value,
            selected_value=raw,
            widget_key=widget,
            save_reason=save_reason,
            transaction_id=tx_id,
        )
    except ImportError:
        pass
    request_creative_selector_cloud_save(session, save_reason=save_reason)


def note_passive_creative_tab_persist(session: dict[str, Any], *, reason: str) -> None:
    """Detect tab/tool fields entering a save envelope without a user selector event."""
    if reason in (SAVE_REASON_TAB, SAVE_REASON_TOOL, STARTUP_DEFAULT_PROJECTION_REASON):
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
    try:
        from creative_selector_hydration_trace import (
            CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY,
            audit_selector_hydration_after_restore,
            collect_selector_hydration_trace,
        )

        if session.get(CREATIVE_SELECTOR_HYDRATION_COMPLETE_KEY):
            snapshot_hydrated_creative_selectors(session, source="diag_refresh")
        else:
            audit_selector_hydration_after_restore(session)
        hydration_trace = collect_selector_hydration_trace(session)
    except ImportError:
        hydration_trace = {}

    _refresh_selector_diag_display(session)
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
    d.setdefault("startup_write_attempted", bool(session.get(CREATIVE_SELECTOR_PERSISTENCE_REQUESTED_KEY)))
    if hydration_trace:
        d["selector_hydration_trace"] = hydration_trace
    try:
        from creative_selector_save_durability_trace import collect_selector_save_durability_trace

        d["selector_save_durability_trace"] = collect_selector_save_durability_trace(session)
    except ImportError:
        pass
    audit_multiple_canonical_owners(session)
    try:
        from creative_selector_hydration_trace import audit_selector_hydration_after_restore

        audit_selector_hydration_after_restore(session)
    except ImportError:
        pass
    d["violations"] = (_diag(session).get("violations") or d.get("violations"))
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
    "evaluate_selector_save_confirmation",
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
