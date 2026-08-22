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
ANALYSIS_EVAL_INSTRUMENT_KEY = "analysis_eval_instrument"
ANALYSIS_SONG_SOURCE_TYPE_KEY = "analysis_song_source_type"
ANALYSIS_SONG_SOURCE_ID_KEY = "analysis_song_source_id"
ANALYSIS_SONG_SOURCE_NAME_KEY = "analysis_song_source_name"
ANALYSIS_TARGET_LAYER_KEY = "analysis_target_layer_label"
ANALYSIS_MISSION_CONSTRAINT_KEY = "analysis_mission_constraint"
ANALYSIS_PLAYER_LEVEL_KEY = "analysis_player_level"
ANALYSIS_PRACTICE_FOCUS_KEY = "analysis_practice_focus"
ANALYSIS_PRACTICE_FOCUSES_KEY = "analysis_practice_focuses"
ANALYSIS_INSTRUMENT_FOCUSES_KEY = "analysis_instrument_focuses"
ANALYSIS_IDENTITY_LOCKED_KEY = "analysis_identity_locked"
_MANUAL_MISSION_DEFAULTS_APPLIED_KEY = "_analysis_manual_mission_defaults_applied"
_PREV_RECORDING_TYPE_KEY = "_analysis_prev_recording_type"


def instrument_focus_widget_key(instrument: str) -> str:
    """Stable Streamlit widget key for one instrument's Practice Focus control."""
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(instrument or "").strip())
    return f"_analysis_instrument_focus__{safe}"


def coerce_focus_list(value: Any) -> list[str]:
    """Normalize legacy scalar / list Focus values into a deduped list (order preserved)."""
    if value is None:
        return []
    if isinstance(value, str):
        text_value = value.strip()
        return [text_value] if text_value else []
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            for part in coerce_focus_list(item):
                if part not in seen:
                    seen.add(part)
                    out.append(part)
        return out
    text_value = str(value).strip()
    return [text_value] if text_value else []


def focus_options_for_instrument_safe(instrument: str) -> list[str]:
    try:
        from practice_setup_controls import focus_options_for_instrument

        return list(focus_options_for_instrument(instrument) or [])
    except Exception:
        return [
            "Melody",
            "Harmony",
            "Rhythm",
            "Dynamics",
            "Improvisation",
            "Technique",
            "Ear Training",
        ]


def default_focus_for_instrument(
    instrument: str, session_state: dict[str, Any] | None = None
) -> str:
    """Pick a sensible default Practice Focus for an instrument (legacy scalar helper)."""
    options = focus_options_for_instrument_safe(instrument)
    if not options:
        return "Improvisation"
    ss = session_state or {}
    active_list = coerce_focus_list(
        ss.get(ANALYSIS_PRACTICE_FOCUSES_KEY)
        or ss.get(ANALYSIS_PRACTICE_FOCUS_KEY)
        or ss.get("focus")
        or ss.get("practice_focus")
    )
    if active_list:
        return active_list[0]
    return str(options[0])


def normalize_instrument_focuses_map(
    raw: Any,
    instruments: list[str] | None = None,
) -> dict[str, list[str]]:
    """Migrate legacy instrument->str maps to instrument->list[str]; optionally prune."""
    cleaned: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            inst = str(key).strip()
            if not inst:
                continue
            cleaned[inst] = coerce_focus_list(value)
    if instruments is None:
        return cleaned
    selected = [str(i).strip() for i in instruments if str(i).strip()]
    return {inst: list(cleaned.get(inst) or []) for inst in selected}


def format_focus_list(focuses: list[str]) -> str:
    """Human-readable Focus list for coach copy (not a serialization format)."""
    items = [str(f).strip() for f in focuses if str(f).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def collect_instrument_focuses(
    session_state: dict[str, Any],
    instruments: list[str],
    *,
    prune_to_options: bool = False,
) -> dict[str, list[str]]:
    """Read-only Focus collection for snapshot/analysis. Never mutates session_state."""
    selected = [str(i).strip() for i in instruments if str(i).strip()]
    raw_map = normalize_instrument_focuses_map(session_state.get(ANALYSIS_INSTRUMENT_FOCUSES_KEY))
    result: dict[str, list[str]] = {}
    for inst in selected:
        widget_key = instrument_focus_widget_key(inst)
        focuses: list[str] = []
        if widget_key in session_state:
            focuses = coerce_focus_list(session_state.get(widget_key))
        elif inst in raw_map:
            focuses = list(raw_map[inst])
        elif len(selected) == 1:
            if ANALYSIS_PRACTICE_FOCUSES_KEY in session_state:
                focuses = coerce_focus_list(session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY))
            else:
                focuses = coerce_focus_list(
                    session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY)
                    or session_state.get("focus")
                    or session_state.get("practice_focus")
                )
        if prune_to_options:
            options = set(focus_options_for_instrument_safe(inst))
            if options:
                focuses = [f for f in focuses if f in options]
        result[inst] = focuses
    return result


def prepare_instrument_focus_ui(
    session_state: dict[str, Any],
    instruments: list[str],
    *,
    identity_locked: bool = False,
    single_recording: bool = False,
) -> dict[str, list[str]]:
    """UI-only Focus sync: seed/prune widget state BEFORE Focus widgets are instantiated.

    Must not be called from build_analysis_context_snapshot / Run Analysis paths.
    """
    selected = [str(i).strip() for i in instruments if str(i).strip()]
    collected = collect_instrument_focuses(
        session_state,
        selected,
        prune_to_options=not identity_locked,
    )

    for inst in selected:
        widget_key = instrument_focus_widget_key(inst)
        options = focus_options_for_instrument_safe(inst)
        focuses = list(collected.get(inst) or [])
        if widget_key not in session_state:
            session_state[widget_key] = list(focuses)
        else:
            current = coerce_focus_list(session_state.get(widget_key))
            if not identity_locked and options:
                pruned = [f for f in current if f in options]
                if pruned != current:
                    session_state[widget_key] = pruned
                focuses = pruned
            else:
                focuses = current
        collected[inst] = list(focuses)

    if single_recording and selected:
        inst = selected[0]
        options = focus_options_for_instrument_safe(inst)
        if ANALYSIS_PRACTICE_FOCUSES_KEY not in session_state:
            legacy = coerce_focus_list(
                session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY)
                or collected.get(inst)
                or session_state.get("focus")
                or session_state.get("practice_focus")
            )
            if not identity_locked and options:
                legacy = [f for f in legacy if f in options]
            session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = list(legacy)
        else:
            current = coerce_focus_list(session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY))
            if not identity_locked and options:
                pruned = [f for f in current if f in options]
                if pruned != current:
                    session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = pruned
                current = pruned
            collected[inst] = list(current)
            session_state[instrument_focus_widget_key(inst)] = list(current)

    stale_keys = [
        k for k in list(session_state.keys()) if str(k).startswith("_analysis_instrument_focus__")
    ]
    keep_keys = {instrument_focus_widget_key(i) for i in selected}
    for key in stale_keys:
        if key not in keep_keys:
            session_state.pop(key, None)

    session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY] = {
        inst: list(collected.get(inst) or []) for inst in selected
    }
    return dict(session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY])


def sync_instrument_focuses(
    session_state: dict[str, Any],
    instruments: list[str],
    *,
    identity_locked: bool = False,
    mutate_session: bool = True,
) -> dict[str, list[str]]:
    """Compatibility wrapper.

    mutate_session=True -> UI path (prepare_instrument_focus_ui)
    mutate_session=False -> read-only snapshot path (collect_instrument_focuses)
    """
    if mutate_session:
        return prepare_instrument_focus_ui(
            session_state,
            instruments,
            identity_locked=identity_locked,
        )
    return collect_instrument_focuses(session_state, instruments)


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
        "practice_focuses": [],
        # Canonical: instrument -> list of Practice Focuses (Single and Multitrack).
        "instrument_focuses": {},
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
        "identity_locked": False,
        "backing_track_context": False,
        # Harmonic context owned by the selected Upload song (not ambient active song)
        "sections": {},
        "target_chords": [],
        "practice_bpm": None,
        "time_signature": "",
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

    instruments = _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY))
    if not instruments:
        single = str(session_state.get(ANALYSIS_EVAL_INSTRUMENT_KEY) or "").strip()
        if single:
            instruments = [single]
    if not instruments:
        instruments = _as_list(session_state.get("instrument"))
    snap["instruments"] = instruments

    # READ-ONLY Focus collection. Never write widget-backed Streamlit keys here
    # (Run Analysis runs after Focus widgets already exist).
    instrument_focuses = collect_instrument_focuses(session_state, instruments)
    snap["instrument_focuses"] = {
        inst: list(focuses) for inst, focuses in instrument_focuses.items()
    }
    practice_focuses: list[str] = []
    if instruments:
        practice_focuses = list(instrument_focuses.get(instruments[0]) or [])
    if not practice_focuses and not mt:
        practice_focuses = coerce_focus_list(
            session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY)
            or session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY)
            or session_state.get("focus")
            or session_state.get("practice_focus")
        )
        if practice_focuses and instruments:
            snap["instrument_focuses"][instruments[0]] = list(practice_focuses)
    snap["practice_focuses"] = list(practice_focuses)
    # Legacy scalar = first selected Focus only (never a comma-joined string).
    snap["practice_focus"] = practice_focuses[0] if practice_focuses else ""

    level = str(
        session_state.get(ANALYSIS_PLAYER_LEVEL_KEY)
        or session_state.get("level")
        or ""
    ).strip()
    snap["level"] = level
    snap["instrument_levels"] = {inst: level for inst in instruments} if level else {}
    snap["identity_locked"] = bool(
        session_state.get(ANALYSIS_IDENTITY_LOCKED_KEY)
        or is_genuine_mission_upload_handoff(session_state)
    )
    snap["backing_track_context"] = bool(
        session_state.get("analysis_backing_track_context")
        or session_state.get("_mission_upload_with_backing")
        or (snap["identity_locked"] and is_mission_recording_type(snap.get("recording_type")))
    )

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
            stored = session_state.get("analysis_mission_parameters")
            if isinstance(stored, dict):
                params.update({k: v for k, v in stored.items() if v not in (None, "")})
            if snap.get("backing_track_context"):
                params.setdefault("backing_track", True)
            snap["mission_parameters"] = params
        else:
            snap["mission_id"] = ""
            snap["mission_type"] = ""
            snap["mission_constraint"] = ""
            snap["mission_parameters"] = {}
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
    instrument_focuses = normalize_instrument_focuses_map(
        snap.get("instrument_focuses"),
        instruments or None,
    )
    if not instrument_focuses and instruments:
        legacy_focuses = coerce_focus_list(
            snap.get("practice_focuses") or snap.get("practice_focus")
        )
        if legacy_focuses:
            instrument_focuses = {instruments[0]: legacy_focuses}
    out["instrument_focuses"] = instrument_focuses
    practice_focuses = coerce_focus_list(snap.get("practice_focuses"))
    if not practice_focuses and instruments:
        practice_focuses = list(instrument_focuses.get(instruments[0]) or [])
    if not practice_focuses:
        practice_focuses = coerce_focus_list(snap.get("practice_focus"))
    out["practice_focuses"] = list(practice_focuses)
    out["focuses"] = list(practice_focuses)
    # Legacy scalar = first Focus only (complete list lives in practice_focuses).
    if practice_focuses:
        out["focus"] = practice_focuses[0]
    # Layer coaching: complete Focus list for the target layer/instrument.
    target = str(snap.get("target_layer") or out.get("target_layer") or "").strip()
    if target and target in instrument_focuses:
        target_focuses = list(instrument_focuses.get(target) or [])
        out["practice_focuses"] = target_focuses
        out["focuses"] = target_focuses
        if target_focuses:
            out["focus"] = target_focuses[0]
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
    # Selected-song harmonic authority (snapshot wins over ambient globals)
    sections = snap.get("sections")
    if isinstance(sections, dict) and sections:
        out["sections"] = {str(k): list(v) if isinstance(v, (list, tuple)) else v for k, v in sections.items()}
    chords = snap.get("target_chords")
    if isinstance(chords, (list, tuple)) and chords:
        out["target_chords"] = [str(c) for c in chords if str(c).strip()]
    if snap.get("practice_bpm") not in (None, ""):
        out["practice_bpm"] = snap["practice_bpm"]
    if snap.get("time_signature"):
        out["time_signature"] = snap["time_signature"]
    return out


def persist_snapshot_on_result(result: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Attach snapshot to an analysis result payload."""
    out = dict(result or {})
    out[ANALYSIS_CONTEXT_SNAPSHOT_KEY] = deepcopy(snapshot)
    # Convenience mirrors for Practice Log / history consumers
    out["workflow"] = snapshot.get("workflow")
    out["recording_type"] = snapshot.get("recording_type") or out.get("recording_type")
    out["practice_focus"] = snapshot.get("practice_focus")
    out["practice_focuses"] = list(snapshot.get("practice_focuses") or [])
    out["instrument_focuses"] = normalize_instrument_focuses_map(
        snapshot.get("instrument_focuses")
    )
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
    focuses = coerce_focus_list(
        result.get("practice_focuses")
        or result.get("focus")
        or result.get("practice_focus")
    )
    snap["practice_focuses"] = list(focuses)
    snap["practice_focus"] = focuses[0] if focuses else ""
    snap["level"] = str(result.get("level") or "")
    inst = str(result.get("instrument") or "").strip()
    if inst:
        snap["instruments"] = [inst]
        if focuses:
            snap["instrument_focuses"] = {inst: list(focuses)}
    raw_map = result.get("instrument_focuses")
    if isinstance(raw_map, dict) and raw_map:
        snap["instrument_focuses"] = normalize_instrument_focuses_map(raw_map)
    return snap


def resolve_active_song_source(session_state: dict[str, Any]) -> dict[str, str]:
    """Resolve the active song's source type, stable id, and display name."""
    source_type = SONG_SOURCE_CATALOG
    source_id = ""
    source_name = ""
    artist = ""

    try:
        from songs.music_source import custom_progression_is_active
    except ImportError:
        custom_progression_is_active = lambda _s: False  # type: ignore[assignment,misc]

    try:
        from composition_session_state import get_active_document
    except ImportError:
        get_active_document = lambda _s: None  # type: ignore[assignment,misc]

    composed_doc = None
    try:
        composed_doc = get_active_document(session_state)
    except Exception:
        composed_doc = None

    if isinstance(composed_doc, dict) and (
        str(session_state.get("studio_page") or "") == "composition"
        or session_state.get("analysis_prefer_composed_source")
    ):
        source_type = SONG_SOURCE_COMPOSED
        source_id = str(composed_doc.get("id") or "").strip()
        source_name = str(composed_doc.get("title") or composed_doc.get("name") or "").strip()
    elif custom_progression_is_active(session_state):
        source_type = SONG_SOURCE_CUSTOM
        active = session_state.get("cpl_active_progression") or session_state.get("cpl_active")
        if isinstance(active, dict):
            source_name = str(active.get("name") or active.get("title") or "").strip()
            source_id = str(active.get("id") or active.get("name") or source_name).strip()
            if source_id and not source_id.startswith("custom::"):
                source_id = f"custom::{source_id}"
        if not source_name:
            source_name = str(session_state.get("song") or "").strip()
        if not source_id and source_name:
            source_id = f"custom::{source_name}"
    else:
        source_type = SONG_SOURCE_CATALOG
        selected = session_state.get("selected_song")
        if isinstance(selected, dict):
            source_name = str(selected.get("title") or selected.get("name") or "").strip()
            artist = str(selected.get("artist") or "").strip()
        source_name = source_name or str(session_state.get("song") or "").strip()
        source_id = str(
            session_state.get("active_catalog_pick_key")
            or session_state.get("pick_key")
            or ""
        ).strip()

    # Prefer composed library only when explicitly active elsewhere didn't match catalog/custom
    if not source_name and isinstance(composed_doc, dict):
        source_type = SONG_SOURCE_COMPOSED
        source_id = str(composed_doc.get("id") or "").strip()
        source_name = str(composed_doc.get("title") or composed_doc.get("name") or "").strip()

    return {
        "song_source_type": source_type,
        "song_source_id": source_id,
        "song_source_name": source_name,
        "song_artist": artist,
    }


def seed_session_setup_from_active(session_state: dict[str, Any], *, force: bool = False) -> None:
    """Prefill Upload setup fields from active studio state when unset (or force=True)."""
    try:
        from practice_setup_globals import get_active_focus, get_active_instrument, get_active_level

        inst = str(get_active_instrument(session_state) or session_state.get("instrument") or "").strip()
        try:
            from practice_setup_globals import get_active_instrument_display_name

            inst = str(get_active_instrument_display_name(session_state) or inst).strip()
        except Exception:
            pass
        level = str(get_active_level(session_state) or session_state.get("level") or "").strip()
        focus = str(get_active_focus(session_state) or session_state.get("focus") or "").strip()
    except Exception:
        inst = str(session_state.get("instrument") or "").strip()
        level = str(session_state.get("level") or "").strip()
        focus = str(session_state.get("focus") or session_state.get("practice_focus") or "").strip()

    if force or not _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY)):
        if inst:
            session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = [inst]
            session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = inst
    elif not str(session_state.get(ANALYSIS_EVAL_INSTRUMENT_KEY) or "").strip():
        instruments = _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY))
        if instruments:
            session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = instruments[0]

    song = resolve_active_song_source(session_state)
    if force or not str(session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY) or "").strip():
        session_state[ANALYSIS_SONG_SOURCE_TYPE_KEY] = song["song_source_type"]
    if force or not str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip():
        if song["song_source_name"]:
            session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = song["song_source_name"]
    if force or not str(session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY) or "").strip():
        if song["song_source_id"]:
            session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = song["song_source_id"]
    if force or not str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or "").strip():
        if level:
            session_state[ANALYSIS_PLAYER_LEVEL_KEY] = level
    existing_focuses = coerce_focus_list(
        session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY)
        or session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY)
    )
    if force or not existing_focuses:
        if focus:
            focus_list = coerce_focus_list(focus)
            session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = list(focus_list)
            # Legacy scalar mirror for older readers (not a Streamlit widget key anymore).
            session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = focus_list[0] if focus_list else ""
            instruments = _as_list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY))
            if instruments:
                session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY] = {
                    instruments[0]: list(focus_list)
                }


def apply_manual_mission_recording_defaults(session_state: dict[str, Any]) -> None:
    """Intelligent editable defaults when the user manually chooses Mission Recording.

    Must be called before Streamlit widgets that bind analysis_mode /
    analysis_recording_type / instrument / song / focus / level are created.
    """
    from upload_analysis_modes import SINGLE_RECORDING

    # Ensure identity fields match Mission Recording; safe only pre-widget.
    session_state["analysis_mode"] = SINGLE_RECORDING
    if not is_mission_recording_type(session_state.get("analysis_recording_type")):
        session_state["analysis_recording_type"] = RECORDING_TYPE_MISSION
    session_state[ANALYSIS_IDENTITY_LOCKED_KEY] = False
    seed_session_setup_from_active(session_state, force=True)
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
    session_state[_MANUAL_MISSION_DEFAULTS_APPLIED_KEY] = True


def maybe_apply_manual_mission_defaults(session_state: dict[str, Any]) -> bool:
    """Apply manual Mission defaults once when Recording Type becomes Mission Recording.

    Returns True when defaults were applied. Call near the top of the Upload setup
    render — before any widgets whose keys these defaults may write.
    """
    if is_genuine_mission_upload_handoff(session_state):
        return False
    current = str(session_state.get("analysis_recording_type") or "").strip()
    previous = str(session_state.get(_PREV_RECORDING_TYPE_KEY) or "").strip()
    applied = False
    if is_mission_recording_type(current) and not is_mission_recording_type(previous):
        apply_manual_mission_recording_defaults(session_state)
        applied = True
    if not is_mission_recording_type(current):
        session_state.pop(_MANUAL_MISSION_DEFAULTS_APPLIED_KEY, None)
    session_state[_PREV_RECORDING_TYPE_KEY] = current
    return applied


def apply_mission_recording_defaults(session_state: dict[str, Any]) -> None:
    """Authoritative prefills for a genuine Creative Mission handoff (identity locked)."""
    from upload_analysis_modes import SINGLE_RECORDING

    session_state["analysis_mode"] = SINGLE_RECORDING
    session_state["analysis_recording_type"] = RECORDING_TYPE_MISSION
    session_state[ANALYSIS_IDENTITY_LOCKED_KEY] = True
    session_state["analysis_backing_track_context"] = True
    seed_session_setup_from_active(session_state, force=True)
    try:
        from mission_practice_context import authoritative_mission_type, ensure_mission_practice_context

        mission = str(authoritative_mission_type(session_state) or "").strip()
        if not mission:
            mission = str(
                session_state.get("improv_active_mission")
                or session_state.get("improv_mission_pick")
                or ""
            ).strip()
        if mission:
            session_state[ANALYSIS_MISSION_CONSTRAINT_KEY] = mission
        ctx = ensure_mission_practice_context(session_state)
        params: dict[str, Any] = {"mission_type": mission, "backing_track": True}
        if ctx is not None:
            chord = getattr(getattr(ctx, "chord", None), "symbol", None)
            if chord:
                params["chord"] = str(chord)
            for attr in ("section", "tempo_bpm", "style", "evaluation_focus"):
                val = getattr(ctx, attr, None)
                if val not in (None, ""):
                    params[attr] = val
        session_state["analysis_mission_parameters"] = params
    except Exception:
        session_state.setdefault("analysis_mission_parameters", {"backing_track": True})


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
        target = str(snap.get("target_layer") or "").strip()
        notes.append(
            "This is a Multitrack Layer — analyze only the uploaded target-layer audio for "
            "timing, role fulfillment, placement, and how it supports the arrangement. "
            "Other project instruments are context, not heard performances."
            + (f" Target layer: **{target}**." if target else "")
        )
    elif rtype == RECORDING_TYPE_MT_MIX:
        notes.append(
            "This is a Multitrack Mix — evaluate ensemble timing, balance, groove cohesion, "
            "and how parts work together rather than as a single solo instrument."
        )

    instrument_focuses = normalize_instrument_focuses_map(snap.get("instrument_focuses"))
    practice_focuses = coerce_focus_list(snap.get("practice_focuses") or snap.get("practice_focus"))
    snap_instruments = _as_list(snap.get("instruments"))
    multi_instrument = len(instrument_focuses) > 1 or len(snap_instruments) > 1
    if rtype == RECORDING_TYPE_MT_LAYER:
        target = str(snap.get("target_layer") or "").strip()
        target_focuses = coerce_focus_list(
            instrument_focuses.get(target) if target else None
        ) or practice_focuses
        if target and target_focuses:
            notes.append(
                f"Target-layer Practice Focuses for **{target}**: "
                f"**{format_focus_list(target_focuses)}** — analyze each Focus explicitly "
                "from the uploaded layer audio."
            )
        context_bits = []
        for inst, foc_list in instrument_focuses.items():
            if not inst or inst == target:
                continue
            if foc_list:
                context_bits.append(f"**{inst}** → {format_focus_list(foc_list)}")
        if context_bits:
            notes.append(
                "Project-instrument Focuses (arrangement context only — not scored without "
                "their own audio): " + "; ".join(context_bits) + "."
            )
    elif multi_instrument and instrument_focuses:
        mapped_bits = []
        for inst, foc_list in instrument_focuses.items():
            if foc_list:
                mapped_bits.append(f"**{inst}** → {format_focus_list(foc_list)}")
            else:
                mapped_bits.append(f"**{inst}** → (no Practice Focus selected)")
        if rtype == RECORDING_TYPE_MT_MIX:
            notes.append(
                "Practice Focuses by instrument — "
                + "; ".join(mapped_bits)
                + ". Use them as ensemble-coaching intent; avoid claiming isolated "
                "instrument performances unless separate stems support that evidence."
            )
        else:
            notes.append(
                "Practice Focuses by instrument — "
                + "; ".join(mapped_bits)
                + ". Coach each part toward its own intended goals."
            )
    elif instrument_focuses:
        inst, foc_list = next(iter(instrument_focuses.items()))
        if foc_list:
            notes.append(
                f"Practice Focuses for **{inst}**: **{format_focus_list(foc_list)}** — "
                "keep recommendations aligned with all selected Focuses."
            )
    elif practice_focuses:
        notes.append(
            f"Practice Focuses: **{format_focus_list(practice_focuses)}** — "
            "keep recommendations aligned with all selected Focuses."
        )
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
    level_l = level.lower()
    if "beginner" in level_l:
        notes.append(
            "Player Level Beginner — keep measured timing/pitch scores unchanged, but coach with "
            "encouraging, foundational expectations and concrete next steps."
        )
    elif "advanced" in level_l:
        notes.append(
            "Player Level Advanced — keep measured scores unchanged, but hold higher musical "
            "standards in observations, refinements, and practice recommendations."
        )
    elif "intermediate" in level_l:
        notes.append(
            "Player Level Intermediate — keep measured scores unchanged; balance encouragement "
            "with clear growth targets."
        )
    song = str(snap.get("song_source_name") or "").strip()
    source = str(snap.get("song_source_type") or "").strip()
    if song:
        notes.append(f"Associated music: {source or 'Song'} — **{song}**.")
    return notes


def _flatten_section_chords(sections: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for _name, entries in (sections or {}).items():
        if isinstance(entries, (list, tuple)):
            for item in entries:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                elif isinstance(item, dict):
                    chord = str(item.get("chord") or item.get("symbol") or "").strip()
                    if chord:
                        out.append(chord)
    return out


def resolve_selected_song_harmony(
    session_state: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    song_picker_catalog: dict[str, Any] | None = None,
    catalog_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve harmonic context from the Upload-selected song (not ambient active song).

    Returns sections, target_chords, display_key, practice_bpm, time_signature, and
    song identity fields. Prefer attaching this onto the analysis-context snapshot so
    historical takes keep their own harmony.
    """
    snap = dict(snapshot or {})
    source_type = str(
        snap.get("song_source_type")
        or session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY)
        or ""
    ).strip()
    source_id = str(
        snap.get("song_source_id")
        or session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY)
        or ""
    ).strip()
    source_name = str(
        snap.get("song_source_name")
        or session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY)
        or ""
    ).strip()

    result: dict[str, Any] = {
        "song_source_type": source_type,
        "song_source_id": source_id,
        "song_source_name": source_name,
        "sections": {},
        "target_chords": [],
        "display_key": str(snap.get("display_key") or ""),
        "practice_bpm": snap.get("practice_bpm"),
        "time_signature": str(snap.get("time_signature") or ""),
        "resolved": False,
    }

    # Already captured on a prior snapshot — trust that over ambient globals.
    prior_sections = snap.get("sections")
    prior_chords = snap.get("target_chords")
    if isinstance(prior_sections, dict) and prior_sections:
        result["sections"] = {
            str(k): list(v) if isinstance(v, (list, tuple)) else v for k, v in prior_sections.items()
        }
        result["target_chords"] = (
            [str(c) for c in prior_chords]
            if isinstance(prior_chords, (list, tuple)) and prior_chords
            else _flatten_section_chords(result["sections"])
        )
        result["resolved"] = True
        return result

    try:
        if source_type == SONG_SOURCE_CATALOG and (source_id or source_name):
            records = catalog_records
            picker = song_picker_catalog
            if records is None or picker is None:
                try:
                    from song_catalog.catalog import load_song_catalog

                    _lib, loaded_picker, _genres, loaded_records = load_song_catalog()
                    picker = picker if picker is not None else loaded_picker
                    records = records if records is not None else loaded_records
                except Exception:
                    picker = picker or {}
                    records = records or []
            rec = None
            if records is not None:
                try:
                    from song_catalog.catalog import record_for_pick_key

                    rec = record_for_pick_key(list(records), source_id or source_name)
                except Exception:
                    rec = None
            if rec is None and isinstance(picker, dict) and source_id:
                try:
                    from song_catalog.catalog import parse_pick_key

                    genre, label = parse_pick_key(source_id)
                    bucket = (picker or {}).get(genre) or {}
                    if isinstance(bucket, dict) and label in bucket:
                        rec = bucket[label]
                except Exception:
                    pass
            if isinstance(rec, dict):
                sections = rec.get("sections") if isinstance(rec.get("sections"), dict) else {}
                # Normalize to list[str] chords per section
                norm: dict[str, list[str]] = {}
                for sec_name, entries in sections.items():
                    if isinstance(entries, (list, tuple)):
                        norm[str(sec_name)] = [
                            str(x).strip()
                            for x in entries
                            if str(x).strip() and not isinstance(x, dict)
                        ] or [
                            str(x.get("chord") or x.get("symbol") or "").strip()
                            for x in entries
                            if isinstance(x, dict)
                            and str(x.get("chord") or x.get("symbol") or "").strip()
                        ]
                result["sections"] = norm
                result["target_chords"] = _flatten_section_chords(norm)
                result["display_key"] = str(
                    rec.get("key") or result["display_key"] or ""
                ).strip()
                ext = rec.get("extensions") if isinstance(rec.get("extensions"), dict) else {}
                bpm = ext.get("default_bpm") or rec.get("bpm")
                if bpm not in (None, ""):
                    result["practice_bpm"] = bpm
                ts = ext.get("time_signature") or rec.get("time_signature")
                if ts:
                    result["time_signature"] = str(ts)
                if not result["song_source_name"]:
                    title = str(rec.get("title") or "").strip()
                    artist = str(rec.get("artist") or "").strip()
                    result["song_source_name"] = f"{title} — {artist}" if artist else title
                result["resolved"] = bool(norm)
                return result

        if source_type == SONG_SOURCE_CUSTOM and (source_id or source_name):
            from custom_progression_lab import CPL_SAVED_KEY

            saved = session_state.get(CPL_SAVED_KEY) or {}
            name = source_name
            if source_id.startswith("custom::"):
                name = source_id.split("custom::", 1)[-1].strip() or name
            active = saved.get(name) if isinstance(saved, dict) else None
            if isinstance(active, dict):
                sections = (
                    active.get("original_sections")
                    or active.get("sections")
                    or {}
                )
                if isinstance(sections, dict):
                    try:
                        from custom_progression_lab import sections_to_chord_lists

                        norm = sections_to_chord_lists(sections)
                    except Exception:
                        norm = {
                            str(k): [str(x) for x in (v or []) if str(x).strip()]
                            if isinstance(v, (list, tuple))
                            else []
                            for k, v in sections.items()
                        }
                    result["sections"] = norm
                    result["target_chords"] = _flatten_section_chords(norm)
                    result["display_key"] = str(
                        active.get("original_key_center")
                        or active.get("key")
                        or result["display_key"]
                        or ""
                    ).strip()
                    if active.get("bpm") not in (None, ""):
                        result["practice_bpm"] = active.get("bpm")
                    if active.get("time_signature"):
                        result["time_signature"] = str(active.get("time_signature"))
                    result["song_source_name"] = name or result["song_source_name"]
                    result["resolved"] = bool(norm)
                    return result

        if source_type == SONG_SOURCE_COMPOSED and source_id:
            try:
                from composition_session_state import COMPOSER_LIBRARY_KEY
                from composition_document import chords_for_playback, playback_globals

                lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
                doc = lib.get(source_id) if isinstance(lib, dict) else None
                if isinstance(doc, dict):
                    chords = chords_for_playback(doc, scope="song")
                    result["target_chords"] = [str(c) for c in chords if str(c).strip()]
                    # Preserve a simple single-section map for mission analysis
                    result["sections"] = {"Form": list(result["target_chords"])}
                    g = playback_globals(doc)
                    result["practice_bpm"] = g.get("bpm")
                    result["time_signature"] = str(g.get("time_signature") or "")
                    meta = doc.get("metadata") or {}
                    result["display_key"] = str(
                        meta.get("key") or doc.get("key") or result["display_key"] or ""
                    ).strip()
                    if not result["song_source_name"]:
                        result["song_source_name"] = str(
                            doc.get("title") or doc.get("name") or source_id
                        ).strip()
                    result["resolved"] = bool(result["target_chords"])
                    return result
            except Exception:
                pass
    except Exception:
        pass
    return result


def attach_selected_song_harmony_to_snapshot(
    session_state: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    song_picker_catalog: dict[str, Any] | None = None,
    catalog_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve Upload-selected song harmony into the snapshot (mutates + returns snap)."""
    snap = dict(snapshot or {})
    harmony = resolve_selected_song_harmony(
        session_state,
        snapshot=snap,
        song_picker_catalog=song_picker_catalog,
        catalog_records=catalog_records,
    )
    if harmony.get("sections"):
        snap["sections"] = harmony["sections"]
    if harmony.get("target_chords"):
        snap["target_chords"] = list(harmony["target_chords"])
    if harmony.get("display_key"):
        snap["display_key"] = harmony["display_key"]
    if harmony.get("practice_bpm") not in (None, ""):
        snap["practice_bpm"] = harmony["practice_bpm"]
    if harmony.get("time_signature"):
        snap["time_signature"] = harmony["time_signature"]
    if harmony.get("song_source_name") and not snap.get("song_source_name"):
        snap["song_source_name"] = harmony["song_source_name"]
    return snap
