"""Upload Analysis setup UI: workflow → recording type → instruments → song source."""

from __future__ import annotations

from typing import Any

from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_MISSION_CONSTRAINT_KEY,
    ANALYSIS_PLAYER_LEVEL_KEY,
    ANALYSIS_PRACTICE_FOCUS_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_TYPE_MT_LAYER,
    SONG_SOURCE_OPTIONS,
    SONG_SOURCE_OTHER,
    is_mission_recording_type,
    normalize_recording_type_for_workflow,
    recording_types_for_workflow,
    seed_session_setup_from_active,
)
from upload_analysis_modes import (
    WORKFLOW_OPTIONS,
    is_multitrack_workflow,
    normalize_analysis_workflow,
)

_LEVEL_OPTIONS = ("Beginner", "Intermediate", "Advanced")


def _mission_options(session_state: dict[str, Any]) -> list[str]:
    options: list[str] = []
    try:
        from improvisation_intelligence import PRACTICE_MISSIONS

        options.extend(str(m) for m in PRACTICE_MISSIONS if str(m).strip())
    except Exception:
        pass
    try:
        from mission_analysis import MISSION_LABELS

        for label in MISSION_LABELS:
            if label not in options:
                options.append(label)
    except Exception:
        pass
    current = str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or "").strip()
    if current and current not in options:
        options = [current] + options
    return options or ["Chord-tone targeting"]


def render_upload_analysis_setup(
    st: Any,
    session_state: dict[str, Any],
    *,
    instrument_options: list[str] | None = None,
    default_instrument: str = "",
    default_song_name: str = "",
    from_mission_handoff: bool = False,
) -> dict[str, Any]:
    """Render Workflow → Recording Type → evaluation context. Returns current selections.

    Controls stay editable for ordinary Uploads and for Mission handoffs.
    Handoff only prefills known mission/song/instrument answers.
    """
    normalize_analysis_workflow(session_state)
    seed_session_setup_from_active(session_state)

    if from_mission_handoff:
        st.info(
            "Prefill from Creative Mission handoff — Single Recording · Mission Recording, "
            "plus the mission, song, and instrument from the take you just recorded. "
            "You can still edit these fields."
        )

    col_mode, col_type = st.columns([1, 1])
    with col_mode:
        st.radio(
            "Workflow",
            list(WORKFLOW_OPTIONS),
            horizontal=True,
            key="analysis_mode",
        )
    normalize_recording_type_for_workflow(session_state)
    allowed = recording_types_for_workflow(
        "Multitrack recording" if is_multitrack_workflow(session_state) else "Single recording"
    )
    with col_type:
        current = str(session_state.get("analysis_recording_type") or allowed[0])
        idx = allowed.index(current) if current in allowed else 0
        st.selectbox(
            "Recording type",
            list(allowed),
            index=idx,
            key="analysis_recording_type",
            help=(
                "Recording type shapes how the coach interprets this take. "
                "Baseline playing scores stay; emphasis and recommendations change. "
                "Choose Mission Recording only when evaluating a Mission constraint."
            ),
        )

    st.markdown(
        '<p class="ui-upload-step-kicker">Step 2 · What should the coach evaluate?</p>',
        unsafe_allow_html=True,
    )
    options = list(instrument_options or [])
    if default_instrument and default_instrument not in options:
        options = [default_instrument] + options
    if not options:
        options = [default_instrument or "Piano"]

    existing = session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY)
    if not isinstance(existing, list) or not existing:
        seed = default_instrument or (options[0] if options else "Piano")
        session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = [seed]

    st.multiselect(
        "Instrument(s) to evaluate",
        options=options,
        key=ANALYSIS_EVAL_INSTRUMENTS_KEY,
        help="Which instrument or part should the coach judge on this recording?",
    )

    level_options = list(_LEVEL_OPTIONS)
    current_level = str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or "").strip()
    if current_level and current_level not in level_options:
        level_options = [current_level] + level_options
    if not current_level:
        session_state[ANALYSIS_PLAYER_LEVEL_KEY] = level_options[1] if len(level_options) > 1 else level_options[0]
    st.selectbox(
        "Player level",
        level_options,
        key=ANALYSIS_PLAYER_LEVEL_KEY,
    )

    focus_seed = str(session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY) or "").strip()
    if not focus_seed:
        session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = str(
            session_state.get("focus") or session_state.get("practice_focus") or ""
        ).strip()
    st.text_input(
        "Current Practice Focus",
        key=ANALYSIS_PRACTICE_FOCUS_KEY,
        help="What the musician is currently working on (separate from Evaluating Criteria).",
    )

    source_type = st.selectbox(
        "What music/song is this recording?",
        list(SONG_SOURCE_OPTIONS),
        key=ANALYSIS_SONG_SOURCE_TYPE_KEY,
    )
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip() and default_song_name:
        session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = default_song_name

    if source_type == SONG_SOURCE_OTHER:
        st.text_input(
            "Describe the recording context",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            placeholder="e.g. Free improvisation over blues form",
        )
    else:
        st.text_input(
            "Song / piece name",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            help="Stable identity for this recording — not rewritten when you later change the active song.",
        )
        st.text_input(
            "Stable song/source ID (optional)",
            key=ANALYSIS_SONG_SOURCE_ID_KEY,
            help="Catalog pick key, custom song id, or composition project id when known.",
        )

    rtype = str(session_state.get("analysis_recording_type") or "")
    if is_mission_recording_type(rtype):
        st.markdown("##### Mission constraint")
        mission_opts = _mission_options(session_state)
        if not str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or "").strip():
            session_state[ANALYSIS_MISSION_CONSTRAINT_KEY] = mission_opts[0]
        current_mission = str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or mission_opts[0])
        m_idx = mission_opts.index(current_mission) if current_mission in mission_opts else 0
        st.selectbox(
            "Which Mission / constraint should the coach evaluate?",
            mission_opts,
            index=m_idx,
            key=ANALYSIS_MISSION_CONSTRAINT_KEY,
            help="Mission compliance is evaluated in addition to Evaluating Criteria emphasis.",
        )
    if is_multitrack_workflow(session_state) and rtype == RECORDING_TYPE_MT_LAYER:
        st.text_input(
            "Target layer / part label",
            key=ANALYSIS_TARGET_LAYER_KEY,
            placeholder="e.g. Tenor sax overdub, Bass stem",
        )

    return {
        "workflow": str(session_state.get("analysis_mode") or ""),
        "recording_type": str(session_state.get("analysis_recording_type") or ""),
        "instruments": list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY) or []),
        "song_source_type": str(session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY) or ""),
        "song_source_name": str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or ""),
        "song_source_id": str(session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY) or ""),
        "target_layer": str(session_state.get(ANALYSIS_TARGET_LAYER_KEY) or ""),
        "practice_focus": str(session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY) or ""),
        "level": str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or ""),
        "mission_constraint": str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or ""),
        "from_mission_handoff": bool(from_mission_handoff),
        "is_mission_recording": is_mission_recording_type(rtype),
    }
