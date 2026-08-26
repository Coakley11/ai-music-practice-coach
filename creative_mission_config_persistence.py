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
CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY = "_creative_mission_passive_startup_write_requested"
CREATIVE_MISSION_USER_SAVE_THIS_RUN_KEY = "_creative_mission_user_save_this_run"
CREATIVE_MISSION_PERSISTENCE_JOURNAL_KEY = "_creative_mission_persistence_journal"
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
VIOLATION_TARGET_IDENTITY_MISMATCH = "CREATIVE_MISSION_TARGET_IDENTITY_MISMATCH"
VIOLATION_METRICS_WIDGET_DIVERGENCE = "CREATIVE_MISSION_METRICS_WIDGET_DIVERGENCE"

MISSION_TARGET_IDENTITY_KEYS: tuple[str, ...] = (
    "ii_selected_section",
    "ii_selected_chord_index",
    "ii_selected_chord",
    "ii_selected_chord_label",
)

IMPROV_MISSION_SECTION_MAP_SESSION_KEY = "_improv_mission_section_map"

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


def _mission_chord_options_from_session(session: dict[str, Any]) -> list[str]:
    raw = session.get("improv_mission_chord_options")
    if isinstance(raw, list) and raw:
        return [str(c) for c in raw]
    section_map = session.get(IMPROV_MISSION_SECTION_MAP_SESSION_KEY)
    if isinstance(section_map, list) and section_map:
        try:
            from improvisation_motif import flatten_section_map

            return flatten_section_map(section_map)
        except ImportError:
            pass
    return []


def _mission_section_map_from_session(session: dict[str, Any]) -> list[tuple[str, list[str]]]:
    raw = session.get(IMPROV_MISSION_SECTION_MAP_SESSION_KEY)
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, list[str]]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            label = str(item[0])
            chords_raw = item[1]
            if isinstance(chords_raw, list):
                out.append((label, [str(c) for c in chords_raw]))
    return out


def _expected_mission_chord_label(section: str, chord: str) -> str:
    sec = str(section or "").strip()
    ch = str(chord or "").strip()
    if sec:
        return f"{sec} · {ch}"
    return ch


def _read_mission_target_tuple(
    session: dict[str, Any],
    values: dict[str, Any] | None = None,
    *,
    prefer_canonical: bool = False,
) -> dict[str, Any]:
    def from_mapping(src: dict[str, Any]) -> dict[str, Any]:
        return {
            "ii_selected_chord_index": src.get("ii_selected_chord_index"),
            "ii_selected_chord": src.get("ii_selected_chord"),
            "ii_selected_section": src.get("ii_selected_section"),
            "ii_selected_chord_label": src.get("ii_selected_chord_label"),
        }

    canonical = {
        k: canonical_mission_config_value(session, k) for k in MISSION_TARGET_IDENTITY_KEYS
    }
    from_values = from_mapping(values) if values else {}
    from_session = from_mapping(session)
    if prefer_canonical:
        order = (canonical, from_values, from_session)
    else:
        order = (from_values, canonical, from_session)
    merged: dict[str, Any] = {}
    for src in order:
        for k, v in src.items():
            if v is None or v == "":
                continue
            if k not in merged:
                merged[k] = copy.deepcopy(v)
    return merged


def mission_target_identity_valid(
    chord_options: list[str],
    section_map: list[tuple[str, list[str]]],
    *,
    index: Any,
    chord: Any,
    section: Any,
    label: Any,
) -> bool:
    if not chord_options:
        return False
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return False
    if idx < 0 or idx >= len(chord_options):
        return False
    ch = str(chord or "").strip()
    if str(chord_options[idx]) != ch:
        return False
    if section_map:
        try:
            from improvisation_motif import section_and_chord_at_global_index

            exp_sec, exp_ch = section_and_chord_at_global_index(section_map, idx)
        except ImportError:
            exp_sec, exp_ch = str(section or ""), ch
        if str(exp_ch) != ch:
            return False
        if str(section or "").strip() and str(section) != str(exp_sec):
            return False
        exp_label = _expected_mission_chord_label(exp_sec, ch)
    else:
        exp_label = _expected_mission_chord_label(str(section or ""), ch)
    return str(label or "") == exp_label


def derive_default_mission_target(
    chord_options: list[str],
    section_map: list[tuple[str, list[str]]],
) -> dict[str, Any]:
    if not chord_options:
        return {
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "",
            "ii_selected_section": "",
            "ii_selected_chord_label": "",
        }
    idx = 0
    ch = str(chord_options[0])
    sec = ""
    if section_map:
        try:
            from improvisation_motif import section_and_chord_at_global_index

            sec, ch = section_and_chord_at_global_index(section_map, idx)
            ch = str(ch)
        except ImportError:
            pass
    return {
        "ii_selected_chord_index": idx,
        "ii_selected_chord": ch,
        "ii_selected_section": sec,
        "ii_selected_chord_label": _expected_mission_chord_label(sec, ch),
    }


def reconcile_mission_target_identity(
    session: dict[str, Any],
    values: dict[str, Any],
    *,
    save_reason: str,
    function: str,
    prefer_canonical_target: bool = False,
) -> dict[str, Any]:
    """Return an internally consistent target tuple + chord_options for commit.

    Explicit chord-tile clicks (``SAVE_REASON_MISSION_TARGET``) must not be
    rewritten to a stale canonical chord when Practice Key has transposed the
    live map (e.g. click Gbm while disk options still list Abm).
    """
    section_map = _mission_section_map_from_session(session)
    chord_options = list(values.get("improv_mission_chord_options") or _mission_chord_options_from_session(session))
    # Live section map is authoritative for options after a Practice Key change.
    if section_map:
        try:
            from improvisation_motif import flatten_section_map

            live_options = flatten_section_map(section_map)
        except ImportError:
            live_options = []
        if live_options:
            click_ch = str(values.get("ii_selected_chord") or "").strip()
            if (
                save_reason == SAVE_REASON_MISSION_TARGET
                and click_ch
                and click_ch in live_options
            ) or (not chord_options) or (
                click_ch
                and click_ch in live_options
                and click_ch not in chord_options
            ):
                chord_options = list(live_options)
    if chord_options:
        values["improv_mission_chord_options"] = list(chord_options)

    # Explicit click: if the payload already matches the live map, keep it —
    # never fall through to a stale canonical Abm while the user clicked Gbm.
    if save_reason == SAVE_REASON_MISSION_TARGET:
        click_tuple = {
            k: values.get(k) for k in MISSION_TARGET_IDENTITY_KEYS if k in values
        }
        if mission_target_identity_valid(
            chord_options,
            section_map,
            index=click_tuple.get("ii_selected_chord_index"),
            chord=click_tuple.get("ii_selected_chord"),
            section=click_tuple.get("ii_selected_section"),
            label=click_tuple.get("ii_selected_chord_label"),
        ):
            values.update({k: copy.deepcopy(click_tuple[k]) for k in MISSION_TARGET_IDENTITY_KEYS})
            return values

    candidates: list[dict[str, Any]] = []
    if prefer_canonical_target:
        candidates.append(_read_mission_target_tuple(session, values, prefer_canonical=True))
    else:
        candidates.append(_read_mission_target_tuple(session, values, prefer_canonical=False))
        # Only consult canonical after click when this is not an explicit tile save.
        if save_reason != SAVE_REASON_MISSION_TARGET:
            candidates.append(_read_mission_target_tuple(session, values, prefer_canonical=True))

    seen: set[tuple[Any, ...]] = set()
    for cand in candidates:
        key = tuple(cand.get(k) for k in MISSION_TARGET_IDENTITY_KEYS)
        if key in seen:
            continue
        seen.add(key)
        if mission_target_identity_valid(
            chord_options,
            section_map,
            index=cand.get("ii_selected_chord_index"),
            chord=cand.get("ii_selected_chord"),
            section=cand.get("ii_selected_section"),
            label=cand.get("ii_selected_chord_label"),
        ):
            values.update({k: copy.deepcopy(cand[k]) for k in MISSION_TARGET_IDENTITY_KEYS})
            return values

    default = derive_default_mission_target(chord_options, section_map)
    values.update(default)
    return values


def record_mission_target_identity_mismatch(
    session: dict[str, Any],
    *,
    mission: str,
    chord_options: list[str],
    section: Any,
    index: Any,
    chord: Any,
    label: Any,
    function: str,
    save_reason: str,
) -> None:
    entry = {
        "mission": mission,
        "chord_options": list(chord_options),
        "selected_section": section,
        "selected_index": index,
        "selected_chord": chord,
        "selected_label": label,
        "function": function,
        "save_reason": save_reason,
        "run_seq": _run_seq(session),
    }
    _diag(session)["last_target_identity_mismatch"] = copy.deepcopy(entry)
    record_mission_config_violation(
        session,
        VIOLATION_TARGET_IDENTITY_MISMATCH,
        detail=(
            f"mission={mission}|index={index}|chord={chord}|label={label}|"
            f"section={section}|function={function}|reason={save_reason}|run_seq={_run_seq(session)}"
        ),
    )


def ensure_atomic_mission_target_before_save(
    session: dict[str, Any],
    values: dict[str, Any],
    *,
    save_reason: str,
    function: str,
    prefer_canonical_target: bool = False,
) -> bool:
    chord_options = list(values.get("improv_mission_chord_options") or _mission_chord_options_from_session(session))
    if not chord_options:
        if save_reason == SAVE_REASON_MISSION_TARGET:
            idx = values.get("ii_selected_chord_index")
            ch = values.get("ii_selected_chord")
            if idx is not None and ch not in (None, ""):
                return True
        for k in MISSION_TARGET_IDENTITY_KEYS:
            v = canonical_mission_config_value(session, k)
            if k == "ii_selected_chord_index" and v is not None:
                values[k] = copy.deepcopy(v)
            elif v is not None and v != "" and v != []:
                values[k] = copy.deepcopy(v)
        return True
    reconcile_mission_target_identity(
        session,
        values,
        save_reason=save_reason,
        function=function,
        prefer_canonical_target=prefer_canonical_target,
    )
    chord_options = list(values.get("improv_mission_chord_options") or [])
    section_map = _mission_section_map_from_session(session)
    mission = str(
        values.get("improv_active_mission")
        or values.get("improv_mission_pick")
        or session.get("improv_mission_pick")
        or ""
    ).strip()
    if mission_target_identity_valid(
        chord_options,
        section_map,
        index=values.get("ii_selected_chord_index"),
        chord=values.get("ii_selected_chord"),
        section=values.get("ii_selected_section"),
        label=values.get("ii_selected_chord_label"),
    ):
        return True
    record_mission_target_identity_mismatch(
        session,
        mission=mission,
        chord_options=chord_options,
        section=values.get("ii_selected_section"),
        index=values.get("ii_selected_chord_index"),
        chord=values.get("ii_selected_chord"),
        label=values.get("ii_selected_chord_label"),
        function=function,
        save_reason=save_reason,
    )
    return False


def canonical_mission_config_value(session: dict[str, Any], key: str) -> Any:
    if key not in MISSION_CONFIG_CANONICAL_KEYS:
        return session.get(key)
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict) and key in blob:
        val = blob.get(key)
        if key == "ii_selected_chord_index" and val is not None:
            return copy.deepcopy(val)
        if key == "improv_ai_metric_ids" and isinstance(val, list):
            return copy.deepcopy(val)
        if val is not None and val != "" and val != []:
            return copy.deepcopy(val)
    return copy.deepcopy(session.get(key))


def mission_metrics_configured_in_canonical(session: dict[str, Any]) -> bool:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    return isinstance(blob, dict) and "improv_ai_metric_ids" in blob


def canonical_mission_metric_ids(session: dict[str, Any]) -> list[str] | None:
    """None = field absent in cloud canonical; otherwise explicit list (may be empty)."""
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if not isinstance(blob, dict) or "improv_ai_metric_ids" not in blob:
        return None
    val = blob.get("improv_ai_metric_ids")
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


def _metric_labels_for_ids(metric_ids: list[str]) -> list[str]:
    try:
        from mission_analysis import AI_IMPROV_METRIC_IDS, MISSION_BY_ID

        id_to_label = {mid: MISSION_BY_ID[mid].label for mid in AI_IMPROV_METRIC_IDS if mid in MISSION_BY_ID}
        return [id_to_label[mid] for mid in metric_ids if mid in id_to_label]
    except ImportError:
        return []


def _metric_ids_from_widget_labels(labels: list[Any]) -> list[str]:
    try:
        from mission_analysis_ui import _metric_id_label_maps

        label_to_id, _ = _metric_id_label_maps()
        return [label_to_id[str(l)] for l in labels if str(l) in label_to_id]
    except ImportError:
        return []


def local_default_mission_metric_ids(session: dict[str, Any]) -> list[str]:
    """Never persisted — only when improv_ai_metric_ids is absent from canonical."""
    try:
        from mission_analysis import mission_ids_from_legacy

        legacy = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "")
        return list(mission_ids_from_legacy(legacy))[:18]
    except ImportError:
        return []


def resolve_mission_metric_ids_for_display(session: dict[str, Any]) -> list[str]:
    configured = canonical_mission_metric_ids(session)
    if configured is not None:
        return list(configured)
    if mission_metrics_configured_in_canonical(session):
        return []
    flat = session.get("improv_ai_metric_ids")
    if isinstance(flat, list):
        return [str(x) for x in flat]
    return local_default_mission_metric_ids(session)


def project_mission_metrics_widgets_from_canonical(
    session: dict[str, Any],
    *,
    overwrite: bool = False,
    key_prefix: str = "improv",
) -> list[str]:
    """Project canonical improv_ai_metric_ids into flat ids + multiselect widget labels (pre-widget)."""
    ids = resolve_mission_metric_ids_for_display(session)
    widget_key = f"{key_prefix}_ai_metric_multiselect"
    store_key = f"{key_prefix}_ai_metric_ids"
    labels = _metric_labels_for_ids(ids)
    canonical_configured = mission_metrics_configured_in_canonical(session)
    if overwrite or canonical_configured or widget_key not in session:
        session[store_key] = copy.deepcopy(ids)
        session[widget_key] = copy.deepcopy(labels)
    d = _diag(session)
    d.setdefault("metrics_widget_projection", {})
    if isinstance(d.get("metrics_widget_projection"), dict):
        d["metrics_widget_projection"] = {
            "canonical_ids": list(ids) if canonical_configured else canonical_mission_metric_ids(session),
            "projected_ids": copy.deepcopy(ids),
            "projected_labels": copy.deepcopy(labels),
            "widget_key": widget_key,
            "overwrite": overwrite,
            "canonical_configured": canonical_configured,
        }
    return ids


def audit_mission_metrics_widget_divergence(
    session: dict[str, Any],
    *,
    key_prefix: str = "improv",
    function: str = "render_ai_improv_metrics_selector",
) -> None:
    if not mission_metrics_configured_in_canonical(session):
        return
    ev = session.get(CREATIVE_MISSION_USER_EVENT_KEY)
    if isinstance(ev, dict) and ev.get("save_reason") == SAVE_REASON_MISSION_METRICS:
        try:
            if int(ev.get("run_seq") or -1) == _run_seq(session):
                return
        except (TypeError, ValueError):
            pass
    canonical_ids = list(canonical_mission_metric_ids(session) or [])
    widget_key = f"{key_prefix}_ai_metric_multiselect"
    store_key = f"{key_prefix}_ai_metric_ids"
    widget_labels = list(session.get(widget_key) or [])
    widget_ids = _metric_ids_from_widget_labels(widget_labels)
    session_ids = list(session.get(store_key) or [])
    hydrated = (session.get(CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY) or {}).get("improv_ai_metric_ids")
    d = _diag(session)
    d["widget_values"] = {
        "improv_ai_metric_ids": copy.deepcopy(session_ids),
        "improv_ai_metric_multiselect": copy.deepcopy(widget_labels),
        "improv_ai_metric_ids_from_widget": copy.deepcopy(widget_ids),
    }
    if canonical_ids == widget_ids == session_ids:
        return
    detail = (
        f"hydrated={hydrated!r}|canonical={canonical_ids!r}|session={session_ids!r}|"
        f"widget={widget_ids!r}|labels={widget_labels!r}|function={function}|run_seq={_run_seq(session)}"
    )
    record_mission_config_violation(session, VIOLATION_METRICS_WIDGET_DIVERGENCE, detail=detail)


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
    try:
        from mission_practice_context import mark_mission_practice_context_dirty

        if any(k in slice_ for k in (*MISSION_TARGET_IDENTITY_KEYS, "improv_active_mission", "improv_mission_pick")):
            mark_mission_practice_context_dirty(session)
    except ImportError:
        pass


CREATIVE_MISSION_CHORD_CLICK_TRACE_KEY = "_creative_mission_chord_click_trace"


def _mission_target_canonical_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "ii_selected_chord": canonical_mission_config_value(session, "ii_selected_chord"),
        "ii_selected_section": canonical_mission_config_value(session, "ii_selected_section"),
        "ii_selected_chord_index": canonical_mission_config_value(session, "ii_selected_chord_index"),
        "ii_selected_chord_label": canonical_mission_config_value(session, "ii_selected_chord_label"),
    }


def record_mission_chord_click_trace(
    session: dict[str, Any],
    *,
    button_key: str,
    callback_invoked: bool,
    args: dict[str, Any],
    phase: str,
    canonical_before: dict[str, Any] | None = None,
    canonical_after: dict[str, Any] | None = None,
    save_requested: bool | None = None,
    overwrite_source: str = "",
) -> None:
    d = _diag(session)
    entry = {
        "phase": phase,
        "button_key": button_key,
        "callback_invoked": callback_invoked,
        "args": copy.deepcopy(args),
        "run_seq": _run_seq(session),
        "canonical_before": copy.deepcopy(canonical_before) if canonical_before else None,
        "canonical_after": copy.deepcopy(canonical_after) if canonical_after else None,
        "save_requested": save_requested,
        "overwrite_source": overwrite_source or None,
        "session_index_after": session.get("ii_selected_chord_index"),
    }
    d["last_chord_click_trace"] = entry
    journal = d.setdefault("chord_click_journal", [])
    if isinstance(journal, list):
        journal.append(entry)
    session[CREATIVE_MISSION_CHORD_CLICK_TRACE_KEY] = copy.deepcopy(entry)


def sync_mission_target_from_canonical(session: dict[str, Any]) -> int:
    """Prefer canonical global chord index for highlight (projects when pending)."""
    project_mission_config_from_canonical_before_widgets(session)
    raw = canonical_mission_config_value(session, "ii_selected_chord_index")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    try:
        return int(session.get("ii_selected_chord_index", 0))
    except (TypeError, ValueError):
        return 0


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
    try:
        from music_workflow_restore_guard import restore_guard_active

        if restore_guard_active(session):
            return
    except ImportError:
        pass
    try:
        from music_workflow_mutation import should_project_mission_config_from_canonical

        if not should_project_mission_config_from_canonical(session):
            return
    except ImportError:
        pass
    for key in MISSION_CONFIG_CANONICAL_KEYS:
        val = canonical_mission_config_value(session, key)
        if key == "ii_selected_chord_index":
            if val is None:
                continue
        elif key == "improv_ai_metric_ids":
            if not mission_metrics_configured_in_canonical(session):
                continue
            session[key] = copy.deepcopy(val if isinstance(val, list) else [])
            continue
        elif val is None or val == "" or val == []:
            continue
        if overwrite or key not in session or session.get(key) in (None, "", []):
            session[key] = copy.deepcopy(val)
    pick = str(canonical_mission_config_value(session, "improv_mission_pick") or "").strip()
    active = str(canonical_mission_config_value(session, "improv_active_mission") or pick).strip()
    if active:
        session["improv_active_mission"] = active
    if pick:
        session["improv_mission_pick"] = pick
    project_mission_metrics_widgets_from_canonical(session, overwrite=overwrite)
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
    # User mission save commits to CWS first; session widget keys are still stale in on_click.
    if persist_reason in MISSION_CONFIG_SAVE_REASONS:
        return False
    if session.get(CREATIVE_MISSION_USER_EVENT_KEY):
        return False
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
    if key == "ii_selected_chord_index":
        if canon is not None and session_val != canon:
            return False
        if canon is not None:
            return True
    elif canon is not None and canon != "" and canon != []:
        if session_val != canon:
            return False
        return True
    if key == "improv_ai_metric_ids" and mission_metrics_configured_in_canonical(session):
        if canon is not None and session_val != canon:
            return False
        if isinstance(canon, list):
            return True
    if persist_reason in ("autosave", "force_autosave", ""):
        return False
    return True


def _append_mission_persistence_journal(session: dict[str, Any], entry: dict[str, Any]) -> None:
    d = _diag(session)
    journal = d.setdefault("persistence_journal", [])
    if not isinstance(journal, list):
        journal = []
        d["persistence_journal"] = journal
    row = copy.deepcopy(entry)
    row.setdefault("run_seq", _run_seq(session))
    journal.append(row)
    session[CREATIVE_MISSION_PERSISTENCE_JOURNAL_KEY] = copy.deepcopy(journal)


def mission_user_save_this_run(session: dict[str, Any]) -> bool:
    try:
        run = int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        run = 0
    return session.get(CREATIVE_MISSION_USER_SAVE_THIS_RUN_KEY) == run


def mission_passive_sync_suppressed_this_run(session: dict[str, Any], *, reason: str) -> bool:
    if str(reason or "").strip() not in ("autosave", "force_autosave", ""):
        return False
    return mission_user_save_this_run(session)


def _workspace_save_fields(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        if isinstance(tx, dict):
            return {
                "reserved_revision": tx.get("reserved_write_revision") or tx.get("envelope_revision_after"),
                "duplicate_skipped": tx.get("duplicate_write_skipped"),
                "upsert_attempted": tx.get("cloud_write_attempted"),
            }
    except ImportError:
        pass
    tx = session.get("_music_workspace_save_transaction")
    if isinstance(tx, dict):
        return {
            "reserved_revision": tx.get("reserved_write_revision") or tx.get("envelope_revision_after"),
            "duplicate_skipped": tx.get("duplicate_write_skipped"),
            "upsert_attempted": tx.get("cloud_write_attempted"),
        }
    return {}


def note_passive_mission_config_persist(session: dict[str, Any], *, reason: str) -> None:
    if reason in MISSION_CONFIG_SAVE_REASONS:
        return
    if reason == "page_change":
        return
    if mission_passive_sync_suppressed_this_run(session, reason=reason):
        _append_mission_persistence_journal(
            session,
            {
                "phase": "passive_mission_sync_suppressed",
                "reason": reason,
                "caller": "note_passive_mission_config_persist",
            },
        )
        return
    snap = session.get(CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if session.get(CREATIVE_MISSION_USER_EVENT_KEY):
        return
    for key in MISSION_CONFIG_CANONICAL_KEYS:
        if canonical_mission_config_value(session, key) != snap.get(key):
            session[CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY] = True
            record_mission_config_violation(session, VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, detail=reason)
            _append_mission_persistence_journal(
                session,
                {
                    "phase": "passive_startup_write_violation",
                    "reason": reason,
                    "caller": "note_passive_mission_config_persist",
                    "field": key,
                    "contributed_to_startup_write_attempted": True,
                },
            )
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
    active = session.get(CREATIVE_MISSION_SAVE_ACTIVE_KEY) if isinstance(session.get(CREATIVE_MISSION_SAVE_ACTIVE_KEY), dict) else {}
    user_ev = session.get(CREATIVE_MISSION_USER_EVENT_KEY) if isinstance(session.get(CREATIVE_MISSION_USER_EVENT_KEY), dict) else {}
    _append_mission_persistence_journal(
        session,
        {
            "phase": "cloud_save_start",
            "reason": save_reason,
            "interaction": user_ev.get("interaction"),
            "field": user_ev.get("field") or active.get("field"),
            "transaction_id": active.get("transaction_id"),
            "user_event_active": bool(user_ev),
            "mission_save_active": bool(active),
            "caller": "request_mission_config_cloud_save",
            "contributed_to_startup_write_attempted": False,
        },
    )
    try:
        import streamlit as st
    except ImportError:
        return False
    try:
        from music_persistent_state import build_music_disk_state, force_save_music_state

        ok = force_save_music_state(st, reason=save_reason)
        d["cloud_save_ok"] = bool(ok)
        ws = _workspace_save_fields(session)
        _append_mission_persistence_journal(
            session,
            {
                "phase": "cloud_save_end",
                "reason": save_reason,
                "interaction": user_ev.get("interaction"),
                "field": user_ev.get("field") or active.get("field"),
                "transaction_id": active.get("transaction_id"),
                "user_event_active": bool(user_ev),
                "mission_save_active": False,
                "cloud_save_requested": True,
                "cloud_save_ok": bool(ok),
                "caller": "request_mission_config_cloud_save",
                "contributed_to_startup_write_attempted": False,
                **ws,
            },
        )
        if ok and is_mission_config_save_reason(save_reason):
            session[CREATIVE_MISSION_USER_SAVE_THIS_RUN_KEY] = _run_seq(session)
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
            ws = _workspace_save_fields(session)
            _append_mission_persistence_journal(
                session,
                {
                    "phase": "cloud_save_end",
                    "reason": save_reason,
                    "interaction": user_ev.get("interaction"),
                    "field": user_ev.get("field") or active.get("field"),
                    "transaction_id": active.get("transaction_id"),
                    "cloud_save_ok": bool(ok),
                    "caller": "request_mission_config_cloud_save",
                    "contributed_to_startup_write_attempted": False,
                    **ws,
                },
            )
            if ok and is_mission_config_save_reason(save_reason):
                session[CREATIVE_MISSION_USER_SAVE_THIS_RUN_KEY] = _run_seq(session)
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
    prefer_canonical_target: bool = False,
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
    payload = copy.deepcopy(values) if values is not None else _config_slice(session)
    if not ensure_atomic_mission_target_before_save(
        session,
        payload,
        save_reason=save_reason,
        function="_handle_user_mission_config_change",
        prefer_canonical_target=prefer_canonical_target,
    ):
        d = _diag(session)
        d["cloud_save_requested"] = False
        d["cloud_save_ok"] = False
        session.pop(CREATIVE_MISSION_SAVE_ACTIVE_KEY, None)
        return
    commit_mission_config_to_canonical(
        session,
        reason=save_reason,
        values=payload,
        project_widget_keys=False,
        interaction=interaction,
    )
    snapshot_hydrated_mission_config(session, source=f"user_save:{save_reason}")
    request_mission_config_cloud_save(session, save_reason=save_reason)


def handle_user_mission_pick_change(session: dict[str, Any]) -> None:
    pick = str(session.get("improv_mission_pick") or "").strip()
    values = _config_slice(session)
    if pick:
        values["improv_active_mission"] = pick
        values["improv_mission_pick"] = pick
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_NEW_NONCE_KEY
    except ImportError:
        MISSION_EXAMPLE_KEY = "improv_mission_example"
        MISSION_NEW_NONCE_KEY = "improv_mission_new_nonce"
    session.pop(MISSION_EXAMPLE_KEY, None)
    session.pop(MISSION_NEW_NONCE_KEY, None)
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_PICK,
        field="improv_mission_pick",
        values=values,
        interaction="mission_pick_on_change",
        prefer_canonical_target=True,
    )


def handle_user_mission_target_selection(
    session: dict[str, Any],
    *,
    chord: str,
    section: str,
    chord_index: int,
    chord_label: str,
    button_key: str = "",
) -> None:
    """Chord tile on_click — commit canonical target and seal session index immediately.

    Session keys must update in the click callback. Waiting for next-run CWS projection
    loses to sticky/restored selection when focus/blob briefly disagree with canonical.
    """
    canonical_before = _mission_target_canonical_snapshot(session)
    click_args = {
        "chord": chord,
        "section": section,
        "chord_index": int(chord_index),
        "chord_label": chord_label,
    }
    record_mission_chord_click_trace(
        session,
        button_key=button_key or f"chord_tile_{chord_index}",
        callback_invoked=True,
        args=click_args,
        phase="callback_start",
        canonical_before=canonical_before,
    )
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
    # Refresh options from the live stamped section map so a Practice Key
    # transpose cannot invalidate the click against stale Eb-keyed options.
    section_map = _mission_section_map_from_session(session)
    if section_map:
        try:
            from improvisation_motif import flatten_section_map

            live_options = flatten_section_map(section_map)
        except ImportError:
            live_options = []
        if live_options:
            values["improv_mission_chord_options"] = list(live_options)
            session["improv_mission_chord_options"] = list(live_options)
    _handle_user_mission_config_change(
        session,
        save_reason=SAVE_REASON_MISSION_TARGET,
        field="ii_selected_chord_index",
        values=values,
        interaction="chord_tile_on_click",
    )
    # Click outranks sticky/restored selection — seal index-authoritative session now.
    # Do not run write_authoritative's resolve remap here: a briefly stale section_map
    # would map the new click back onto the restored Am/F#m sticky index.
    sym = str(chord or "").strip()
    sec = str(section or "").strip()
    gidx = int(chord_index)
    label = str(chord_label or "").strip() or (f"{sec} · {sym}" if sec and sym else sym)
    session["ii_selected_chord"] = sym
    session["ii_selected_section"] = sec
    session["ii_selected_chord_index"] = gidx
    session["ii_selected_chord_label"] = label
    session["harmony_map_chord"] = sym
    session["harmony_map_section"] = sec
    session["II_SELECTED_CHORD"] = sym
    session["II_SELECTED_SECTION"] = sec
    session["_mission_chord_click_authority"] = {
        "chord": sym,
        "section": sec,
        "chord_index": gidx,
        "run_seq": _run_seq(session),
    }
    # Projection already applied to session — avoid a later stale-focus block wiping it.
    session.pop(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY, None)
    canonical_after = _mission_target_canonical_snapshot(session)
    record_mission_chord_click_trace(
        session,
        button_key=button_key or f"chord_tile_{chord_index}",
        callback_invoked=True,
        args=click_args,
        phase="callback_after_save",
        canonical_before=canonical_before,
        canonical_after=canonical_after,
        save_requested=True,
        overwrite_source="session_click_authority",
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
    d.setdefault("startup_write_attempted", bool(session.get(CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY)))
    d.setdefault("persistence_journal", d.get("persistence_journal"))
    d.setdefault("violations", d.get("violations") or [])
    d.setdefault("last_chord_click_trace", d.get("last_chord_click_trace"))
    d.setdefault("last_target_identity_mismatch", d.get("last_target_identity_mismatch"))
    d.setdefault("widget_values", d.get("widget_values"))
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
    "VIOLATION_TARGET_IDENTITY_MISMATCH",
    "VIOLATION_METRICS_WIDGET_DIVERGENCE",
    "audit_mission_metrics_widget_divergence",
    "project_mission_metrics_widgets_from_canonical",
    "canonical_mission_metric_ids",
    "mission_metrics_configured_in_canonical",
    "collect_creative_mission_config_diagnostics",
    "commit_mission_config_to_canonical",
    "ensure_atomic_mission_target_before_save",
    "reconcile_mission_target_identity",
    "IMPROV_MISSION_SECTION_MAP_SESSION_KEY",
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
    "sync_mission_target_from_canonical",
    "record_mission_chord_click_trace",
    "CREATIVE_MISSION_PERSISTENCE_JOURNAL_KEY",
    "CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY",
    "mission_passive_sync_suppressed_this_run",
    "mission_user_save_this_run",
    "snapshot_hydrated_mission_config",
]
