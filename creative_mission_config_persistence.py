"""Mission configuration persistence (pick, target chord/section, AI metrics) — Phase 1 Item 2."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    write_canonical_creative_workspace,
)

CREATIVE_MISSION_CONFIG_DIAG_KEY = "_creative_mission_config_diag"
CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY = "_creative_mission_config_hydrated_snapshot"
CREATIVE_MISSION_USER_EVENT_KEY = "_creative_mission_config_last_user_event"
CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY = "_creative_mission_persistence_requested"
CREATIVE_MISSION_SAVE_ACTIVE_KEY = "_creative_mission_save_active_tx"
CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY = "_creative_mission_config_needs_widget_projection"
CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY = "_creative_mission_widgets_instantiated"

SAVE_REASON_MISSION_PICK = "creative_mission_change"
SAVE_REASON_MISSION_TARGET = "creative_mission_target_change"
SAVE_REASON_MISSION_METRICS = "creative_mission_metrics_change"

MISSION_CONFIG_SAVE_REASONS: frozenset[str] = frozenset(
    {
        SAVE_REASON_MISSION_PICK,
        SAVE_REASON_MISSION_TARGET,
        SAVE_REASON_MISSION_METRICS,
    }
)

VIOLATION_PASSIVE_MISSION_STARTUP_WRITE = "CREATIVE_MISSION_PASSIVE_STARTUP_WRITE"
VIOLATION_POST_INSTANTIATION_WIDGET_WRITE = "CREATIVE_MISSION_POST_INSTANTIATION_WIDGET_WRITE"

# Item 2 scope — not generated example / practice lick (Item 3).
MISSION_CONFIG_CANONICAL_KEYS: tuple[str, ...] = (
    "improv_active_mission",
    "improv_mission_pick",
    "improv_mission_progression",
    "improv_mission_chord_options",
    "ii_selected_chord",
    "ii_selected_section",
    "ii_selected_chord_index",
    "ii_selected_chord_label",
    "improv_ai_metric_ids",
    "analysis_criteria_locked",
)

# Flat session keys that Streamlit widgets may own — never assign after instantiation.
MISSION_WIDGET_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "improv_mission_pick",
        "ii_selected_chord",
        "ii_selected_section",
        "ii_selected_chord_index",
        "ii_selected_chord_label",
        "improv_ai_metric_ids",
        "improv_ai_metric_multiselect",
    }
)


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(CREATIVE_MISSION_CONFIG_DIAG_KEY)
    if not isinstance(d, dict):
        d = {}
        session[CREATIVE_MISSION_CONFIG_DIAG_KEY] = d
    return d


def record_mission_config_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)


def is_mission_config_save_reason(reason: str) -> bool:
    return str(reason or "").strip() in MISSION_CONFIG_SAVE_REASONS


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def mark_mission_widgets_instantiated(session: dict[str, Any]) -> None:
    session[CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY] = True


def _record_post_instantiation_widget_write_violation(
    session: dict[str, Any],
    *,
    key: str,
    function: str,
    save_reason: str = "",
    interaction: str = "",
) -> None:
    record_mission_config_violation(
        session,
        VIOLATION_POST_INSTANTIATION_WIDGET_WRITE,
        detail=(
            f"key={key}|function={function}|reason={save_reason or 'none'}"
            f"|interaction={interaction or 'none'}|run_seq={_run_seq(session)}"
        ),
    )


def _safe_assign_mission_widget_key(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    function: str,
    save_reason: str = "",
    interaction: str = "",
    allow_when_widgets_live: bool = False,
) -> bool:
    if (
        not allow_when_widgets_live
        and session.get(CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY)
        and key in MISSION_WIDGET_SESSION_KEYS
    ):
        _record_post_instantiation_widget_write_violation(
            session,
            key=key,
            function=function,
            save_reason=save_reason,
            interaction=interaction,
        )
        return False
    session[key] = copy.deepcopy(value)
    return True


def _config_slice(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in MISSION_CONFIG_CANONICAL_KEYS:
        if key in session:
            out[key] = copy.deepcopy(session[key])
    pick = str(session.get("improv_mission_pick") or session.get("improv_active_mission") or "").strip()
    if pick:
        out["improv_active_mission"] = pick
        out["improv_mission_pick"] = pick
    return out


def canonical_mission_config_value(session: dict[str, Any], key: str) -> Any:
    if key not in MISSION_CONFIG_CANONICAL_KEYS:
        return session.get(key)
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict) and key in blob:
        val = blob.get(key)
        if val is not None and val != "" and val != []:
            return copy.deepcopy(val)
    return copy.deepcopy(session.get(key))


def commit_mission_config_to_canonical(
    session: dict[str, Any],
    *,
    reason: str,
    values: dict[str, Any] | None = None,
    project_widget_keys: bool = False,
    interaction: str = "",
) -> None:
    """Write mission configuration into creative_workspace_state only (default).

    Widget session keys are projected on the next rerun via project_mission_config_from_canonical_before_widgets.
    """
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict):
        base = copy.deepcopy(blob)
    else:
        base = default_creative_workspace_state()
    slice_ = copy.deepcopy(values) if values is not None else _config_slice(session)
    for k, v in slice_.items():
        base[k] = copy.deepcopy(v)
    write_canonical_creative_workspace(session, base, reason=reason)
    if project_widget_keys:
        for k, v in slice_.items():
            _safe_assign_mission_widget_key(
                session,
                k,
                v,
                function="commit_mission_config_to_canonical",
                save_reason=reason,
                interaction=interaction,
            )
    else:
        session[CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY] = True


def project_mission_config_from_canonical_before_widgets(session: dict[str, Any]) -> None:
    """Run before Missions widgets render — applies pending canonical → widget projection."""
    if not session.pop(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY, False):
        return
    session.pop(CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY, None)
    project_mission_config_from_canonical(session, overwrite=True)


def snapshot_hydrated_mission_config(session: dict[str, Any], *, source: str = "prepare") -> None:
    snap = {k: canonical_mission_config_value(session, k) for k in MISSION_CONFIG_CANONICAL_KEYS}
    session[CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY] = snap
    d = _diag(session)
    d["hydrated_mission_config"] = copy.deepcopy(snap)
    d["hydration_source"] = source


def project_mission_config_from_canonical(session: dict[str, Any], *, overwrite: bool = False) -> None:
    for key in MISSION_CONFIG_CANONICAL_KEYS:
        val = canonical_mission_config_value(session, key)
        if val is None or val == "" or val == []:
            continue
        if overwrite or key not in session or session.get(key) in (None, "", []):
            session[key] = copy.deepcopy(val)
    pick = str(canonical_mission_config_value(session, "improv_mission_pick") or "").strip()
    active = str(canonical_mission_config_value(session, "improv_active_mission") or pick).strip()
    if active:
        session["improv_active_mission"] = active
    if pick:
        session["improv_mission_pick"] = pick
    d = _diag(session)
    d["projection_source"] = "creative_workspace_state"


def should_gather_mission_config_from_session(
    session: dict[str, Any],
    key: str,
    session_val: Any,
    *,
    persist_reason: str = "autosave",
) -> bool:
    if key not in MISSION_CONFIG_CANONICAL_KEYS:
        return True
    if persist_reason in MISSION_CONFIG_SAVE_REASONS:
        return True
    if session.get(CREATIVE_MISSION_USER_EVENT_KEY):
        return True
    try:
        from creative_tab_tool_persistence import selector_hydration_complete
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_RESTORED_KEY

        if session.get(CREATIVE_WORKSPACE_RESTORED_KEY) and not session.get("_creative_workspace_restored_applied"):
            return False
        if not selector_hydration_complete(session):
            return False
    except ImportError:
        pass
    canon = canonical_mission_config_value(session, key)
    if canon is not None and canon != "" and canon != []:
        if session_val != canon:
            return False
        return True
    if persist_reason in ("autosave", "force_autosave", ""):
        return False
    return True


def note_passive_mission_config_persist(session: dict[str, Any], *, reason: str) -> None:
    if reason in MISSION_CONFIG_SAVE_REASONS:
        return
    if reason == "page_change":
        return
    snap = session.get(CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if session.get(CREATIVE_MISSION_USER_EVENT_KEY):
        return
    for key in MISSION_CONFIG_CANONICAL_KEYS:
        if canonical_mission_config_value(session, key) != snap.get(key):
            record_mission_config_violation(session, VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, detail=reason)
            return


def begin_mission_config_save_tx(session: dict[str, Any], *, save_reason: str, field: str) -> str:
    tx_id = f"mission-save-{_run_seq(session)}-{uuid.uuid4().hex[:8]}"
    session[CREATIVE_MISSION_SAVE_ACTIVE_KEY] = {
        "transaction_id": tx_id,
        "save_reason": save_reason,
        "field": field,
        "run_seq": _run_seq(session),
    }
    return tx_id


def request_mission_config_cloud_save(session: dict[str, Any], *, save_reason: str) -> bool:
    d = _diag(session)
    d["cloud_save_requested"] = True
    session[CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY] = True
    try:
        import streamlit as st
    except ImportError:
        return False
    try:
        from music_persistent_state import build_music_disk_state, force_save_music_state

        ok = force_save_music_state(st, reason=save_reason)
        d["cloud_save_ok"] = bool(ok)
        session.pop(CREATIVE_MISSION_SAVE_ACTIVE_KEY, None)
        return bool(ok)
    except ImportError:
        try:
            from music_workspace_cloud_save import force_music_workspace_save

            ok = force_music_workspace_save(
                st,
                reason=save_reason,
                build_state=build_music_disk_state,
            )
            d["cloud_save_ok"] = bool(ok)
            session.pop(CREATIVE_MISSION_SAVE_ACTIVE_KEY, None)
            return bool(ok)
        except ImportError:
            return False


def _handle_user_mission_config_change(
    session: dict[str, Any],
    *,
    save_reason: str,
    field: str,
    values: dict[str, Any] | None = None,
    interaction: str = "",
) -> None:
    begin_mission_config_save_tx(session, save_reason=save_reason, field=field)
    session[CREATIVE_MISSION_USER_EVENT_KEY] = {
        "field": field,
        "save_reason": save_reason,
        "run_seq": _run_seq(session),
        "interaction": interaction or None,
    }
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        try:
            from improvisation_mission_persistence import mark_mission_workspace_dirty

            mark_mission_workspace_dirty(session)
        except ImportError:
            pass
    commit_mission_config_to_canonical(
        session,
        reason=save_reason,
        values=values,
        project_widget_keys=False,
        interaction=interaction,
    )
    request_mission_config_cloud_save(session, save_reason=save_reason)


def handle_user_mission_pick_change(session: dict[str, Any]) -> None:
    pick = str(session.get("improv_mission_pick") or "").strip()
    values = _config_slice(session)
    if pick:
        values["improv_active_mission"] = pick
        values["improv_mission_pick"] = pick
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_PICK,
        field="improv_mission_pick",
        values=values,
        interaction="mission_pick_on_change",
    )


def handle_user_mission_target_selection(
    session: dict[str, Any],
    *,
    chord: str,
    section: str,
    chord_index: int,
    chord_label: str,
) -> None:
    """Canonical-only target update (chord tile on_click — no widget key writes)."""
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_NEW_NONCE_KEY
    except ImportError:
        MISSION_EXAMPLE_KEY = "improv_mission_example"
        MISSION_NEW_NONCE_KEY = "improv_mission_new_nonce"
    session.pop(MISSION_EXAMPLE_KEY, None)
    session.pop(MISSION_NEW_NONCE_KEY, None)
    values = _config_slice(session)
    values.update(
        {
            "ii_selected_chord": chord,
            "ii_selected_section": section,
            "ii_selected_chord_index": int(chord_index),
            "ii_selected_chord_label": chord_label,
        }
    )
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_TARGET,
        field="ii_selected_chord_index",
        values=values,
        interaction="chord_tile_on_click",
    )


def handle_user_mission_target_change(session: dict[str, Any]) -> None:
    """Legacy entry — prefer handle_user_mission_target_selection from on_click."""
    values = _config_slice(session)
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_TARGET,
        field="ii_selected_chord_index",
        values=values,
        interaction="chord_tile_legacy",
    )


def handle_user_mission_metrics_change(session: dict[str, Any]) -> None:
    picked = list(session.get("improv_ai_metric_multiselect") or session.get("improv_ai_metric_ids") or [])
    try:
        from mission_analysis_ui import _metric_id_label_maps

        label_to_id, _ = _metric_id_label_maps()
        if picked and isinstance(picked[0], str) and picked[0] in label_to_id:
            selected_ids = [label_to_id[l] for l in picked if l in label_to_id]
        else:
            selected_ids = list(picked)
    except ImportError:
        selected_ids = list(picked)
    values = _config_slice(session)
    values["improv_ai_metric_ids"] = selected_ids
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_METRICS,
        field="improv_ai_metric_ids",
        values=values,
        interaction="metrics_multiselect_on_change",
    )


def collect_creative_mission_config_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    d = dict(_diag(session))
    d.setdefault("hydrated_mission_config", session.get(CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY))
    d.setdefault(
        "canonical_values",
        {k: canonical_mission_config_value(session, k) for k in MISSION_CONFIG_CANONICAL_KEYS},
    )
    d.setdefault("startup_write_attempted", bool(session.get(CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY)))
    d.setdefault("violations", d.get("violations") or [])
    return d


__all__ = [
    "CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY",
    "CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY",
    "CREATIVE_MISSION_SAVE_ACTIVE_KEY",
    "CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY",
    "MISSION_CONFIG_CANONICAL_KEYS",
    "MISSION_CONFIG_SAVE_REASONS",
    "MISSION_WIDGET_SESSION_KEYS",
    "SAVE_REASON_MISSION_METRICS",
    "SAVE_REASON_MISSION_PICK",
    "SAVE_REASON_MISSION_TARGET",
    "VIOLATION_PASSIVE_MISSION_STARTUP_WRITE",
    "VIOLATION_POST_INSTANTIATION_WIDGET_WRITE",
    "collect_creative_mission_config_diagnostics",
    "commit_mission_config_to_canonical",
    "handle_user_mission_metrics_change",
    "handle_user_mission_pick_change",
    "handle_user_mission_target_change",
    "handle_user_mission_target_selection",
    "is_mission_config_save_reason",
    "mark_mission_widgets_instantiated",
    "note_passive_mission_config_persist",
    "project_mission_config_from_canonical",
    "project_mission_config_from_canonical_before_widgets",
    "request_mission_config_cloud_save",
    "should_gather_mission_config_from_session",
    "snapshot_hydrated_mission_config",
]
