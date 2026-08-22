"""Upload Analysis setup UI — Step 1 recording-analysis context."""

from __future__ import annotations

from typing import Any

from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENT_KEY,
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_INSTRUMENT_FOCUSES_KEY,
    ANALYSIS_MISSION_CONSTRAINT_KEY,
    ANALYSIS_PLAYER_LEVEL_KEY,
    ANALYSIS_PRACTICE_FOCUS_KEY,
    ANALYSIS_PRACTICE_FOCUSES_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_TYPE_MT_LAYER,
    SONG_SOURCE_CATALOG,
    SONG_SOURCE_COMPOSED,
    SONG_SOURCE_CUSTOM,
    SONG_SOURCE_OPTIONS,
    SONG_SOURCE_OTHER,
    coerce_focus_list,
    instrument_focus_widget_key,
    is_mission_recording_type,
    maybe_apply_manual_mission_defaults,
    normalize_recording_type_for_workflow,
    prepare_instrument_focus_ui,
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


def _choice_labels(choices: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for row in choices:
        label = str(row.get("label") or row.get("id") or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _id_for_label(choices: list[dict[str, str]], label: str) -> str:
    for row in choices:
        if str(row.get("label") or "") == label:
            return str(row.get("id") or "").strip()
    return ""


def _select_from_library(
    st: Any,
    *,
    label: str,
    choices: list[dict[str, str]],
    session_state: dict[str, Any],
    disabled: bool,
    empty_message: str,
    widget_key: str,
) -> None:
    labels = _choice_labels(choices)
    if not labels:
        st.caption(empty_message)
        st.text_input(
            "Song / piece name",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            disabled=disabled,
        )
        return

    current_name = str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip()
    current_id = str(session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY) or "").strip()
    if not current_name and current_id:
        for row in choices:
            if str(row.get("id") or "") == current_id:
                current_name = str(row.get("label") or "")
                break
    if current_name not in labels:
        if current_name:
            labels = [current_name] + labels
        else:
            current_name = labels[0]
            session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = current_name
            session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = _id_for_label(choices, current_name)

    idx = labels.index(current_name) if current_name in labels else 0
    picked = st.selectbox(
        label,
        labels,
        index=idx,
        key=widget_key,
        disabled=disabled,
    )
    session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = str(picked)
    matched_id = _id_for_label(choices, str(picked))
    if matched_id:
        session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = matched_id
    elif current_id:
        session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = current_id


def render_upload_analysis_setup(
    st: Any,
    session_state: dict[str, Any],
    *,
    instrument_options: list[str] | None = None,
    default_instrument: str = "",
    default_song_name: str = "",
    from_mission_handoff: bool = False,
    catalog_song_choices: list[dict[str, str]] | None = None,
    custom_song_choices: list[dict[str, str]] | None = None,
    composed_song_choices: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Render Step 1: what the coach should evaluate.

    Genuine Creative Mission handoff locks recording identity fields.
    Manual Mission Recording only receives intelligent editable defaults.
    """
    normalize_analysis_workflow(session_state)
    seed_session_setup_from_active(session_state)
    identity_locked = bool(from_mission_handoff)

    # CRITICAL: apply Mission defaults BEFORE any widgets whose keys they may write.
    # On the rerun after the user picks Mission Recording, analysis_recording_type is
    # already the new value in session_state. Mutating widget-backed keys after
    # st.radio/st.selectbox instantiation causes StreamlitAPIException.
    if not identity_locked:
        maybe_apply_manual_mission_defaults(session_state)

    st.markdown("### Step 1 — What should the coach evaluate?")
    st.caption(
        "Tell the coach what this recording represents before capturing audio. "
        "These answers are saved with the recording for Practice Log."
    )

    if identity_locked:
        st.info(
            "Creative Mission handoff — recording identity is locked "
            "(workflow, type, instrument, song, and mission). "
            "You can still change Evaluating Criteria / Metrics before analysis."
        )

    col_mode, col_type = st.columns([1, 1])
    with col_mode:
        st.radio(
            "Workflow",
            list(WORKFLOW_OPTIONS),
            horizontal=True,
            key="analysis_mode",
            disabled=identity_locked,
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
            disabled=identity_locked,
            help=(
                "Shapes how the coach interprets this take. Baseline playing scores stay; "
                "emphasis and recommendations change. Choose Mission Recording only when "
                "evaluating a Mission constraint."
            ),
        )

    options = list(instrument_options or [])
    if default_instrument and default_instrument not in options:
        options = [default_instrument] + options
    if not options:
        options = [default_instrument or "Piano"]

    # Preserve legacy generic "Saxophone" (and any other saved labels) in the
    # selector when restoring older Upload analyses — without reintroducing it
    # as the default shared catalog choice.
    existing_seed = session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY)
    if isinstance(existing_seed, list):
        for raw in existing_seed:
            label = str(raw or "").strip()
            if label and label not in options:
                options.append(label)
    existing_one = str(session_state.get(ANALYSIS_EVAL_INSTRUMENT_KEY) or "").strip()
    if existing_one and existing_one not in options:
        options.append(existing_one)

    existing = session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY)
    if not isinstance(existing, list) or not existing:
        seed = default_instrument or options[0]
        session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = [seed]
        session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = seed
    if not str(session_state.get(ANALYSIS_EVAL_INSTRUMENT_KEY) or "").strip():
        session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = list(
            session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY) or [options[0]]
        )[0]

    # Recording type is chosen above — branch Multitrack labels by Layer vs Mix.
    _rtype_for_instruments = str(session_state.get("analysis_recording_type") or "")
    _is_mt_layer_ui = (
        is_multitrack_workflow(session_state)
        and _rtype_for_instruments == RECORDING_TYPE_MT_LAYER
    )

    if is_multitrack_workflow(session_state):
        st.multiselect(
            "Project instruments" if _is_mt_layer_ui else "Instrument(s) / parts in this mix",
            options=options,
            key=ANALYSIS_EVAL_INSTRUMENTS_KEY,
            disabled=identity_locked,
            help=(
                "Instruments that belong to this Multitrack project/arrangement. "
                "You can select one or many — Multitrack Layer does not require multiple instruments."
                if _is_mt_layer_ui
                else "Which instruments or parts are in this Multitrack Mix?"
            ),
        )
        selected_instruments = [
            str(x).strip()
            for x in (session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY) or [])
            if str(x).strip()
        ]
        if not selected_instruments:
            selected_instruments = [options[0]]
            session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = list(selected_instruments)
        selected_instrument = selected_instruments[0]
        session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = selected_instrument
        if _is_mt_layer_ui:
            st.caption(
                "Project instruments describe the overall arrangement. "
                "Only the Layer being analyzed is scored from the uploaded audio — "
                "a single-instrument Layer project is valid."
            )
            _layer_options = list(selected_instruments)
            _current_target = str(session_state.get(ANALYSIS_TARGET_LAYER_KEY) or "").strip()
            if _current_target and _current_target not in _layer_options:
                _layer_options = [_current_target] + _layer_options
            if session_state.get(ANALYSIS_TARGET_LAYER_KEY) not in _layer_options:
                session_state[ANALYSIS_TARGET_LAYER_KEY] = _layer_options[0]
            st.selectbox(
                "Layer being analyzed",
                options=_layer_options,
                key=ANALYSIS_TARGET_LAYER_KEY,
                disabled=identity_locked,
                help=(
                    "The one instrument whose uploaded audio is analyzed. "
                    "Other project instruments remain arrangement context only."
                ),
            )
    else:
        current_inst = str(session_state.get(ANALYSIS_EVAL_INSTRUMENT_KEY) or options[0])
        if current_inst not in options:
            options = [current_inst] + options
        inst_idx = options.index(current_inst) if current_inst in options else 0
        picked_inst = st.selectbox(
            "Instrument to evaluate",
            options,
            index=inst_idx,
            key=ANALYSIS_EVAL_INSTRUMENT_KEY,
            disabled=identity_locked,
            help="Single Recording evaluates exactly one instrument.",
        )
        session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = [str(picked_inst)]
        selected_instrument = str(picked_inst)
        selected_instruments = [selected_instrument]

    level_options = list(_LEVEL_OPTIONS)
    current_level = str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or "").strip()
    if current_level and current_level not in level_options:
        level_options = [current_level] + level_options
    if not current_level:
        session_state[ANALYSIS_PLAYER_LEVEL_KEY] = (
            level_options[1] if len(level_options) > 1 else level_options[0]
        )
    st.selectbox(
        "Player level",
        level_options,
        key=ANALYSIS_PLAYER_LEVEL_KEY,
        disabled=identity_locked,
    )

    # Practice Focus — any number of Focuses per instrument (Single + Multitrack).
    try:
        from practice_setup_controls import focus_options_for_instrument as _focus_options_for_instrument
    except Exception:
        def _focus_options_for_instrument(instrument: str) -> list[str]:
            return [
                "Melody",
                "Harmony",
                "Rhythm",
                "Dynamics",
                "Improvisation",
                "Technique",
                "Ear Training",
            ]

    if is_multitrack_workflow(session_state):
        prepare_instrument_focus_ui(
            session_state,
            selected_instruments,
            identity_locked=identity_locked,
            single_recording=False,
        )
        _target_for_focus = str(session_state.get(ANALYSIS_TARGET_LAYER_KEY) or "").strip()
        if _is_mt_layer_ui:
            st.caption(
                "Practice Focuses on the Layer being analyzed are scored from the uploaded audio. "
                "Focuses on other project instruments are arrangement context only."
            )
        else:
            st.caption(
                "Choose any number of Practice Focuses for each selected instrument/part "
                "(zero, one, or many)."
            )
        for inst in selected_instruments:
            focus_options = list(_focus_options_for_instrument(inst) or []) or ["Improvisation"]
            widget_key = instrument_focus_widget_key(inst)
            current = coerce_focus_list(session_state.get(widget_key))
            if identity_locked:
                for foc in current:
                    if foc and foc not in focus_options:
                        focus_options = [foc] + focus_options
            else:
                pruned = [f for f in current if f in focus_options]
                if pruned != current:
                    session_state[widget_key] = pruned
            _is_target_inst = _is_mt_layer_ui and inst == _target_for_focus
            _focus_label = (
                f"{inst} — Practice Focus (layer being analyzed)"
                if _is_target_inst
                else (
                    f"{inst} — Practice Focus (project context)"
                    if _is_mt_layer_ui
                    else f"{inst} — Practice Focus"
                )
            )
            st.multiselect(
                _focus_label,
                focus_options,
                key=widget_key,
                disabled=identity_locked,
                help=(
                    f"These Focuses are analyzed from the uploaded {inst} audio."
                    if _is_target_inst
                    else (
                        f"Arrangement context for {inst} — not scored unless that instrument's "
                        "audio is uploaded."
                        if _is_mt_layer_ui
                        else f"Any number of Practice Focuses for {inst} on this Multitrack recording."
                    )
                ),
            )
        instrument_focuses = {
            inst: coerce_focus_list(session_state.get(instrument_focus_widget_key(inst)))
            for inst in selected_instruments
        }
        session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY] = instrument_focuses
        if selected_instruments:
            first_focuses = instrument_focuses.get(selected_instruments[0], [])
            session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = list(first_focuses)
            # Legacy scalar mirror only (not a Streamlit widget key).
            session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = first_focuses[0] if first_focuses else ""
    else:
        prepare_instrument_focus_ui(
            session_state,
            [selected_instrument] if selected_instrument else [],
            identity_locked=identity_locked,
            single_recording=True,
        )
        focus_options = list(_focus_options_for_instrument(selected_instrument) or [])
        if not focus_options:
            focus_options = [
                "Melody",
                "Harmony",
                "Rhythm",
                "Dynamics",
                "Improvisation",
                "Technique",
                "Ear Training",
            ]
        current = coerce_focus_list(session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY))
        if identity_locked:
            for foc in current:
                if foc and foc not in focus_options:
                    focus_options = [foc] + focus_options
        else:
            pruned = [f for f in current if f in focus_options]
            if pruned != current:
                session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = pruned
        st.multiselect(
            "Practice Focus",
            focus_options or ["Improvisation"],
            key=ANALYSIS_PRACTICE_FOCUSES_KEY,
            disabled=identity_locked,
            help=(
                "Any number of Practice Focuses for the selected instrument "
                "(separate from Evaluating Criteria)."
            ),
        )
        focuses = coerce_focus_list(session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY))
        session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY] = {selected_instrument: list(focuses)}
        # Legacy scalar mirror only (not a Streamlit widget key).
        session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = focuses[0] if focuses else ""

    source_type = st.selectbox(
        "What music/song is this recording?",
        list(SONG_SOURCE_OPTIONS),
        key=ANALYSIS_SONG_SOURCE_TYPE_KEY,
        disabled=identity_locked,
    )
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip() and default_song_name:
        session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = default_song_name

    if source_type == SONG_SOURCE_OTHER:
        st.text_input(
            "Song / piece name",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            disabled=identity_locked,
            placeholder="e.g. Free improvisation over blues form",
        )
        session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = ""
    elif source_type == SONG_SOURCE_CATALOG:
        _select_from_library(
            st,
            label="Catalog song",
            choices=list(catalog_song_choices or []),
            session_state=session_state,
            disabled=identity_locked,
            empty_message="No catalog songs available — type the piece name.",
            widget_key="_analysis_song_pick_catalog",
        )
    elif source_type == SONG_SOURCE_CUSTOM:
        _select_from_library(
            st,
            label="Custom song",
            choices=list(custom_song_choices or []),
            session_state=session_state,
            disabled=identity_locked,
            empty_message="No saved Custom songs yet — type the piece name.",
            widget_key="_analysis_song_pick_custom",
        )
    elif source_type == SONG_SOURCE_COMPOSED:
        _select_from_library(
            st,
            label="Composed song",
            choices=list(composed_song_choices or []),
            session_state=session_state,
            disabled=identity_locked,
            empty_message="No saved Composed songs yet — type the piece name.",
            widget_key="_analysis_song_pick_composed",
        )

    rtype = str(session_state.get("analysis_recording_type") or "")
    if is_mission_recording_type(rtype):
        st.markdown("##### Mission")
        mission_opts = _mission_options(session_state)
        if not str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or "").strip():
            session_state[ANALYSIS_MISSION_CONSTRAINT_KEY] = mission_opts[0]
        current_mission = str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or mission_opts[0])
        m_idx = mission_opts.index(current_mission) if current_mission in mission_opts else 0
        st.selectbox(
            "Mission / constraint",
            mission_opts,
            index=m_idx,
            key=ANALYSIS_MISSION_CONSTRAINT_KEY,
            disabled=identity_locked,
            help="Mission compliance is evaluated in addition to Evaluating Criteria emphasis.",
        )
        params = session_state.get("analysis_mission_parameters")
        if identity_locked and isinstance(params, dict) and params:
            bits = []
            if params.get("chord"):
                bits.append(f"Chord: {params['chord']}")
            if params.get("section"):
                bits.append(f"Section: {params['section']}")
            if params.get("tempo_bpm"):
                bits.append(f"Tempo: {params['tempo_bpm']}")
            if params.get("backing_track"):
                bits.append("Backing track: yes")
            if bits:
                st.caption(" · ".join(str(b) for b in bits))

    # Layer target is chosen earlier (with Project instruments) for clearer ownership.

    return {
        "workflow": str(session_state.get("analysis_mode") or ""),
        "recording_type": str(session_state.get("analysis_recording_type") or ""),
        "instruments": list(session_state.get(ANALYSIS_EVAL_INSTRUMENTS_KEY) or []),
        "song_source_type": str(session_state.get(ANALYSIS_SONG_SOURCE_TYPE_KEY) or ""),
        "song_source_name": str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or ""),
        "song_source_id": str(session_state.get(ANALYSIS_SONG_SOURCE_ID_KEY) or ""),
        "target_layer": str(session_state.get(ANALYSIS_TARGET_LAYER_KEY) or ""),
        "practice_focus": str(session_state.get(ANALYSIS_PRACTICE_FOCUS_KEY) or ""),
        "practice_focuses": list(session_state.get(ANALYSIS_PRACTICE_FOCUSES_KEY) or []),
        "instrument_focuses": dict(session_state.get(ANALYSIS_INSTRUMENT_FOCUSES_KEY) or {}),
        "level": str(session_state.get(ANALYSIS_PLAYER_LEVEL_KEY) or ""),
        "mission_constraint": str(session_state.get(ANALYSIS_MISSION_CONSTRAINT_KEY) or ""),
        "from_mission_handoff": bool(from_mission_handoff),
        "identity_locked": identity_locked,
        "is_mission_recording": is_mission_recording_type(rtype),
    }
