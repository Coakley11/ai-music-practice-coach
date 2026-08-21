"""Upload Analysis setup UI: workflow → recording type → instruments → song source."""

from __future__ import annotations

from typing import Any

from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_TYPE_MT_LAYER,
    SONG_SOURCE_OPTIONS,
    SONG_SOURCE_OTHER,
    normalize_recording_type_for_workflow,
    recording_types_for_workflow,
    seed_session_setup_from_active,
)
from upload_analysis_modes import (
    WORKFLOW_OPTIONS,
    is_multitrack_workflow,
    normalize_analysis_workflow,
)


def render_upload_analysis_setup(
    st: Any,
    session_state: dict[str, Any],
    *,
    instrument_options: list[str] | None = None,
    default_instrument: str = "",
    default_song_name: str = "",
    mission_locked: bool = False,
) -> dict[str, Any]:
    """Render Workflow → Recording Type → evaluation context. Returns current selections."""
    normalize_analysis_workflow(session_state)
    seed_session_setup_from_active(session_state)

    if mission_locked:
        st.info(
            "Mission recording context is attached automatically "
            "(Single Recording · Solo Performance · mission song/instrument)."
        )

    col_mode, col_type = st.columns([1, 1])
    with col_mode:
        st.radio(
            "Workflow",
            list(WORKFLOW_OPTIONS),
            horizontal=True,
            key="analysis_mode",
            disabled=mission_locked,
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
            disabled=mission_locked,
            help=(
                "Recording type shapes how the coach interprets this take. "
                "Baseline playing scores stay; emphasis and recommendations change."
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
        disabled=mission_locked,
        help="Which instrument or part should the coach judge on this recording?",
    )
    level = str(session_state.get("level") or "").strip()
    if level:
        st.caption(f"Player level used for coaching: **{level}**")

    focus = str(session_state.get("focus") or session_state.get("practice_focus") or "").strip()
    if focus:
        st.caption(f"Current Practice Focus: **{focus}**")

    source_type = st.selectbox(
        "What music/song is this recording?",
        list(SONG_SOURCE_OPTIONS),
        key=ANALYSIS_SONG_SOURCE_TYPE_KEY,
        disabled=mission_locked,
    )
    if not str(session_state.get(ANALYSIS_SONG_SOURCE_NAME_KEY) or "").strip() and default_song_name:
        session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = default_song_name

    if source_type == SONG_SOURCE_OTHER:
        st.text_input(
            "Describe the recording context",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            disabled=mission_locked,
            placeholder="e.g. Free improvisation over blues form",
        )
    else:
        st.text_input(
            "Song / piece name",
            key=ANALYSIS_SONG_SOURCE_NAME_KEY,
            disabled=mission_locked,
            help="Stable identity for this recording — not rewritten when you later change the active song.",
        )
        if not mission_locked:
            st.text_input(
                "Stable song/source ID (optional)",
                key=ANALYSIS_SONG_SOURCE_ID_KEY,
                help="Catalog pick key, custom song id, or composition project id when known.",
            )

    if is_multitrack_workflow(session_state):
        rtype = str(session_state.get("analysis_recording_type") or "")
        if rtype == RECORDING_TYPE_MT_LAYER:
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
        "practice_focus": focus,
        "level": level,
    }
