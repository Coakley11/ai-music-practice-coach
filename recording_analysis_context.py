"""Reusable recording analysis-context snapshot (Upload + Practice Log).

Authority rule: once a recording exists, its saved snapshot owns historical meaning
(song, instrument, criteria, mission, workflow). Current UI state may only seed
defaults when creating a new take.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ANALYSIS_CONTEXT_SNAPSHOT_KEY = "analysis_context_snapshot"
LAST_ANALYSIS_CONTEXT_KEY = "last_analysis_context_snapshot"

WORKFLOW_SINGLE = "Single recording"
WORKFLOW_MULTITRACK = "Multitrack recording"

RECORDING_TYPE_SOLO = "Solo performance"
RECORDING_TYPE_PRACTICE = "Practice take"
RECORDING_TYPE_BACKING = "Over backing track"
RECORDING_TYPE_MISSION = "Mission Recording"
RECORDING_TYPE_MT_LAYER = "Multitrack layer"
RECORDING_TYPE_MT_MIX = "Multitrack mix"

SONG_SOURCE_CATALOG = "Catalog Song"
SONG_SOURCE_CUSTOM = "Custom Song"
SONG_SOURCE_COMPOSED = "Composed Song"
SONG_SOURCE_OTHER = "Other / Not a Song"

SINGLE_RECORDING_TYPES: tuple[str, ...] = (
    RECORDING_TYPE_SOLO,
    RECORDING_TYPE_PRACTICE,
    RECORDING_TYPE_BACKING,
    RECORDING_TYPE_MISSION,
)
MULTITRACK_RECORDING_TYPES: tuple[str, ...] = (
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
)

SONG_SOURCE_OPTIONS: tuple[str, ...] = (
    SONG_SOURCE_CATALOG,
    SONG_SOURCE_CUSTOM,
    SONG_SOURCE_COMPOSED,
    SONG_SOURCE_OTHER,
)

# Session keys for Upload setup (pre-analysis UI)
ANALYSIS_EVAL_INSTRUMENTS_KEY = "analysis_eval_instruments"
ANALYSIS_SONG_SOURCE_TYPE_KEY = "analysis_song_source_type"
ANALYSIS_SONG_SOURCE_ID_KEY = "analysis_song_source_id"
ANALYSIS_SONG_SOURCE_NAME_KEY = "analysis_song_source_name"
ANALYSIS_TARGET_LAYER_KEY = "analysis_target_layer_label"
ANALYSIS_MISSION_CONSTRAINT_KEY = "analysis_mission_constraint"
ANALYSIS_PLAYER_LEVEL_KEY = "analysis_player_level"
ANALYSIS_PRACTICE_FOCUS_KEY = "analysis_practice_focus"


def is_genuine_mission_upload_handoff(session_state: dict[str, Any]) -> bool:
    """True only when a Creative → Missions take was handed off to Upload.

    Do not treat ambient Creative mission state, analysis_sync_creative_mission
    defaults, or an active improv_active_mission as a handoff.
    """
    try:
        from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY
    except ImportError:
        MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY = "_mission_upload_analysis_handoff"
    return bool(session_state.get(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY))


def is_mission_recording_type(value: Any) -> bool:
    text = str(value or "").strip().lower().replace("_", " ")
    return text in {"mission recording", "mission"}


def recording_types_for_workflow(workflow: str) -> tuple[str, ...]:
    mode = str(workflow or WORKFLOW_SINGLE).strip()
    if mode in {WORKFLOW_MULTITRACK, "Multitrack comparison"}:
        return MULTITRACK_RECORDING_TYPES
    return SINGLE_RECORDING_TYPES


def normalize_recording_type_for_workflow(session_state: dict[str, Any]) -> str:
    """Keep analysis_recording_type valid for the current workflow."""
    from upload_analysis_modes import is_multitrack_workflow, normalize_analysis_workflow

    normalize_analysis_workflow(session_state)
    allowed = recording_types_for_workflow(
        WORKFLOW_MULTITRACK if is_multitrack_workflow(session_state) else WORKFLOW_SINGLE
    )
    current = str(session_state.get("analysis_recording_type") or "").strip()
    if current not in allowed:
        default = RECORDING_TYPE_MT_MIX if is_multitrack_workflow(session_state) else RECORDING_TYPE_PRACTICE
        session_state["analysis_recording_type"] = default
        return default
    return current


def empty_analysis_context_snapshot() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow": WORKFLOW_SINGLE,
        "recording_type": RECORDING_TYPE_PRACTICE,
        "evaluating_criteria_ids": [],
        "evaluating_criteria_labels": [],
        "practice_focus": "",
        "instruments": [],
        "instrument_levels": {},
        "song_source_type": SONG_SOURCE_CATALOG,
        "song_source_id": "",
        "song_source_name": "",
        "song_artist": "",
        "mission_id": "",
        "mission_type": "",
        "mission_constraint": "",
        "mission_parameters": {},
        "multitrack_project_id": "",
        "multitrack_project_name": "",
        "target_layer": "",
        "target_instruments": [],
        "display_key": "",
        "level": "",
        "association": "",
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def build_analysis_context_snapshot(
    session_state: dict[str, Any],
    *,
    association: str = "",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a durable snapshot from current session defaults + optional overrides."""
    from upload_analysis_modes import is_multitrack_workflow, normalize_analysis_workflow

    normalize_analysis_workflow(session_state)
    snap = empty_analysis_context_snapshot()
    mt = is_multitrack_workflow(session_state)
    snap["workflow"] = WORKFLOW_MULTITRACK if mt else WORKFLOW_SINGLE
    snap["recording_type"] = str(
        session_state.get("analysis_recording_type")
        or (RECORDING_TYPE_MT_MIX if mt else RECORDING_TYPE_PRACTICE)
    ).strip()

    criteria_ids = list(
        session_state.get("analysis_effective_metric_ids")
        or session_state.get("analysis_ai_metric_ids")
        or session_state.get("improv_ai_metric_ids")
        or []
    )
    snap["evaluating_criteria_ids"] = [str(x) for x in criteria_ids if str(x).strip()]
    try:
        from mission_analysis_ui import criteria_labels_from_session

        snap["evaluating_criteria_labels"] = list(criteria_labels_from_session(session_state) or [])
    except Exception:
        snap["evaluating_criteria_labels"] = list(snap["evaluating_criteria_ids"])

    focus = str(
        session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY)
        or session_state.get("focus")
        or session_state.get("practice_focus")
        or ""
    ).strip()
    snap["practice_focus"] = focus

    instruments = _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY))
    if not instruments:
        instruments = _as_list(session_state.get("instrument"))
    snap["instruments"] = instruments
    level = str(
        session_state.get(ANALYSIS_PLAYER_LEVEL_KEY)
        or session_state.get("level")
        or ""
    ).strip()
    snap["level"] = level
    snap["instrument_levels"] = {inst: level for inst in instruments} if level else {}

    song_type = str(
        session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY) or SONG_SOURCE_CATALOG
    ).strip()
    if song_type not in SONG_SOURCE_OPTIONS:
        song_type = SONG_SOURCE_CATALOG
    snap["song_source_type"] = song_type
    snap["song_source_id"] = str(
        session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY)
        or session_state.get("active_catalog_pick_key")
        or session_state.get("pick_key")
        or ""
    ).strip()
    snap["song_source_name"] = str(
        session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY)
        or session_state.get("song")
        or ""
    ).strip()
    selected = session_state.get("selected_song")
    if isinstance(selected, dict):
        snap["song_artist"] = str(selected.get("artist") or "").strip()
        if not snap["song_source_name"]:
            snap["song_source_name"] = str(selected.get("title") or selected.get("name") or "").strip()

    snap["display_key"] = str(
        session_state.get("display_key")
        or session_state.get("chart_key")
        or ""
    ).strip()

    # Mission context — only when this take is explicitly a Mission Recording
    if is_mission_recording_type(snap.get("recording_type")):
        mission_type = str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or "").strip()
        if not mission_type:
            try:
                from mission_practice_context import authoritative_mission_type

                mission_type = str(authoritative_mission_type(session_state) or "").strip()
            except Exception:
                mission_type = ""
        if mission_type:
            snap["mission_type"] = mission_type
            snap["mission_id"] = str(
                session_state.get("improv_active_mission_id")
                or session_state.get("active_practice_mission_id")
                or mission_type
            ).strip()
            snap["mission_constraint"] = mission_type
            params: dict[str, Any] = {"mission_type": mission_type}
            try:
                from mission_practice_context import ensure_mission_practice_context

                ctx = ensure_mission_practice_context(session_state)
                if ctx is not None:
                    chord = getattr(getattr(ctx, "chord", None), "symbol", None)
                    if chord:
                        params["chord"] = str(chord)
                    for attr in ("section", "tempo_bpm", "style", "evaluation_focus"):
                        val = getattr(ctx, attr, None)
                        if val not in (None, ""):
                            params[attr] = val
            except Exception:
                pass
            snap["mission_parameters"] = params
    else:
        snap["mission_id"] = ""
        snap["mission_type"] = ""
        snap["mission_constraint"] = ""
        snap["mission_parameters"] = {}

    snap["target_layer"] = str(session_state.get(ANALYSIS_TARGET_LAYER_KEY) or "").strip()
    snap["target_instruments"] = list(snap["instruments"])
    snap["multitrack_project_id"] = str(
        session_state.get("multitrack_project_id")
        or session_state.get("active_multitrack_project_id")
        or ""
    ).strip()
    snap["multitrack_project_name"] = str(
        session_state.get("multitrack_project_name")
        or session_state.get("active_multitrack_project_name")
        or ""
    ).strip()
    snap["association"] = str(association or "").strip()

    if overrides:
        for key, value in overrides.items():
            if key in snap:
                snap[key] = deepcopy(value)
    return snap


def apply_snapshot_to_analysis_ctx(ctx: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a saved snapshot into the runtime analysis context (snapshot wins)."""
    out = dict(ctx or {})
    snap = dict(snapshot or {})
    if not snap:
        return out
    out["analysis_context_snapshot"] = deepcopy(snap)
    out["recording_type"] = snap.get("recording_type") or out.get("recording_type")
    out["workflow"] = snap.get("workflow") or out.get("workflow")
    instruments = _as_list(snap.get("instruments"))
    if instruments:
        out["instrument"] = instruments[0]
        out["instruments"] = instruments
    if snap.get("level"):
        out["level"] = snap["level"]
    if snap.get("practice_focus"):
        out["focus"] = snap["practice_focus"]
    if snap.get("song_source_name"):
        out["song"] = snap["song_source_name"]
    if snap.get("song_artist"):
        out["artist"] = snap["song_artist"]
    if snap.get("display_key"):
        out["display_key"] = snap["display_key"]
    if snap.get("evaluating_criteria_ids"):
        out["mission_ids"] = list(snap["evaluating_criteria_ids"])
    if snap.get("mission_type"):
        out["mission_type"] = snap["mission_type"]
        out["mission_constraint"] = snap.get("mission_constraint") or snap["mission_type"]
    if isinstance(snap.get("mission_parameters"), dict):
        out["mission_parameters"] = dict(snap["mission_parameters"])
    out["song_source_type"] = snap.get("song_source_type")
    out["song_source_id"] = snap.get("song_source_id")
    out["target_layer"] = snap.get("target_layer")
    out["multitrack_project_id"] = snap.get("multitrack_project_id")
    out["multitrack_project_name"] = snap.get("multitrack_project_name")
    return out


def persist_snapshot_on_result(result: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Attach snapshot to an analysis result payload."""
    out = dict(result or {})
    out[ANALYSIS_CONTEXT_SNAPSHOT_KEY] = deepcopy(snapshot)
    # Convenience mirrors for Practice Log / history consumers
    out["workflow"] = snapshot.get("workflow")
    out["recording_type"] = snapshot.get("recording_type") or out.get("recording_type")
    out["practice_focus"] = snapshot.get("practice_focus")
    out["evaluating_criteria_ids"] = list(snapshot.get("evaluating_criteria_ids") or [])
    out["evaluating_criteria_labels"] = list(snapshot.get("evaluating_criteria_labels") or [])
    out["instruments"] = list(snapshot.get("instruments") or [])
    out["song_source_type"] = snapshot.get("song_source_type")
    out["song_source_id"] = snapshot.get("song_source_id")
    out["song_source_name"] = snapshot.get("song_source_name")
    out["mission_type"] = snapshot.get("mission_type")
    out["mission_parameters"] = dict(snapshot.get("mission_parameters") or {})
    return out


def store_snapshot_in_session(session_state: dict[str, Any], snapshot: dict[str, Any]) -> None:
    session_state[LAST_ANALYSIS_CONTEXT_KEY] = deepcopy(snapshot)
    session_state[ANALYSIS_CONTEXT_SNAPSHOT_KEY] = deepcopy(snapshot)


def load_snapshot_from_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return empty_analysis_context_snapshot()
    snap = result.get(ANALYSIS_CONTEXT_SNAPSHOT_KEY)
    if isinstance(snap, dict) and snap:
        return deepcopy(snap)
    # Reconstruct a minimal snapshot from older results
    snap = empty_analysis_context_snapshot()
    snap["recording_type"] = str(result.get("recording_type") or RECORDING_TYPE_PRACTICE)
    snap["song_source_name"] = str(result.get("song") or "")
    snap["practice_focus"] = str(result.get("focus") or "")
    snap["level"] = str(result.get("level") or "")
    inst = str(result.get("instrument") or "").strip()
    if inst:
        snap["instruments"] = [inst]
    return snap


def seed_session_setup_from_active(session_state: dict[str, Any]) -> None:
    """Prefill Upload setup fields from active studio state when unset."""
    if not _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY)):
        inst = str(session_state.get("instrument") or "").strip()
        if inst:
            session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = [inst]
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY) or "").strip():
        session_state[ANALYSIS_SONG_SOURCE_TYPE_KEY] = SONG_SOURCE_CATALOG
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip():
        selected = session_state.get("selected_song")
        title = ""
        if isinstance(selected, dict):
            title = str(selected.get("title") or selected.get("name") or "").strip()
        title = title or str(session_state.get("song") or "").strip()
        if title:
            session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = title
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY) or "").strip():
        pk = str(
            session_state.get("active_catalog_pick_key")
            or session_state.get("pick_key")
            or ""
        ).strip()
        if pk:
            session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = pk
    if not str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or "").strip():
        level = str(session_state.get("level") or "").strip()
        if level:
            session_state[ANALYSIS_PLAYER_LEVEL_KEY] = level
    if not str(session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY) or "").strip():
        focus = str(session_state.get("focus") or session_state.get("practice_focus") or "").strip()
        if focus:
            session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = focus


def apply_mission_recording_defaults(session_state: dict[str, Any]) -> None:
    """Prefill Workflow / Recording Type / song / instrument for a Creative Mission handoff.

    Fields remain editable in the Upload UI; this only seeds known answers.
    """
    from upload_analysis_modes import SINGLE_RECORDING

    session_state["analysis_mode"] = SINGLE_RECORDING
    session_state["analysis_recording_type"] = RECORDING_TYPE_MISSION
    seed_session_setup_from_active(session_state)
    try:
        from mission_practice_context import authoritative_mission_type

        mission = str(authoritative_mission_type(session_state) or "").strip()
        if not mission:
            mission = str(
                session_state.get("improv_active_mission")
                or session_state.get("improv_mission_pick")
                or ""
            ).strip()
        if mission:
            session_state[ANALYSIS_MISSION_CONSTRAINT_KEY] = mission
    except Exception:
        pass


def coach_emphasis_notes(snapshot: dict[str, Any] | None) -> list[str]:
    """Human-readable coaching emphasis cues derived from the snapshot."""
    snap = snapshot or {}
    notes: list[str] = []
    rtype = str(snap.get("recording_type") or "")
    if rtype == RECORDING_TYPE_PRACTICE:
        notes.append(
            "This is a Practice Take — prioritize diagnostic feedback and the next useful drill "
            "over polished-performance praise."
        )
    elif rtype == RECORDING_TYPE_SOLO:
        notes.append(
            "This is a Solo Performance — judge the complete musical presentation as a standalone take."
        )
    elif rtype == RECORDING_TYPE_BACKING:
        notes.append(
            "This was recorded Over a Backing Track — emphasize lock with accompaniment, "
            "rhythmic placement, entrances, groove, and phrasing over the harmony."
        )
    elif is_mission_recording_type(rtype):
        notes.append(
            "This is a Mission Recording — explicitly assess mission-constraint compliance, "
            "then apply Evaluating Criteria inside that restriction."
        )
    elif rtype == RECORDING_TYPE_MT_LAYER:
        notes.append(
            "This is a Multitrack Layer — evaluate the selected part for timing, role fulfillment, "
            "placement, and how it supports the arrangement."
        )
    elif rtype == RECORDING_TYPE_MT_MIX:
        notes.append(
            "This is a Multitrack Mix — evaluate ensemble timing, balance, groove cohesion, "
            "and how parts work together rather than as a single solo instrument."
        )

    focus = str(snap.get("practice_focus") or "").strip()
    if focus:
        notes.append(f"Current Practice Focus is **{focus}** — keep recommendations aligned with that work.")

    labels = list(snap.get("evaluating_criteria_labels") or [])
    if labels:
        joined = ", ".join(labels)
        notes.append(
            f"Evaluating Criteria emphasis: **{joined}**. Keep baseline scores, but deepen "
            f"observations, deep-dive wording, and next-step tips around these criteria."
        )

    mission = str(snap.get("mission_type") or snap.get("mission_constraint") or "").strip()
    if mission:
        notes.append(
            f"Mission constraint: **{mission}**. Explicitly assess mission compliance, then "
            f"apply the Evaluating Criteria inside that constraint."
        )
    instruments = _as_list(snap.get("instruments"))
    level = str(snap.get("level") or "").strip()
    if instruments:
        inst_txt = ", ".join(instruments)
        level_txt = f" ({level})" if level else ""
        notes.append(f"Evaluate instrument(s): **{inst_txt}**{level_txt}.")
    song = str(snap.get("song_source_name") or "").strip()
    source = str(snap.get("song_source_type") or "").strip()
    if song:
        notes.append(f"Associated music: {source or 'Song'} — **{song}**.")
    return notes
