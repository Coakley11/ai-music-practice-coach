"""Full Creative Entry-mode lifecycle harness — mirrors production order.

Run: streamlit run streamlit_creative_full_production_harness.py

Models: workspace bootstrap, pre-widget consumers, sidebar lock, Creative tab +
Entry & Jam radio, Style Jam / Generator widgets, optional mission-backing pending.
For stop-the-line repro only — not deployed to production app entry.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import streamlit as st

from music_theory import ENHARMONIC_MAJOR_KEYS
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)

HARNESS_RUN_KEY = "_harness_fp_run_seq"
STYLE_SID = "Pop groove"
GEN_SID = "jam-harness-fp-1"
HARNESS_MISSION_BACKING_CLICKS_KEY = "_harness_fp_mission_backing_clicks"
HARNESS_TRACE_KEY = "_harness_fp_trace"

IMPROV_ENTRY_MODES = (
    "Song-Based Improvisation",
    "Style Jam Mode",
    "Jam Session Generator",
)
IMPROV_TAB_NAMES = (
    "Missions",
    "Entry & Jam",
    "Phrase / Motif",
    "Metrics & AI",
    "Live Coach",
    "Harmony Map",
    "Deep Harmony",
)


def _append_trace(session: dict[str, Any], event: str, **payload: Any) -> None:
    bucket = session.get(HARNESS_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"event": event, **payload})
    session[HARNESS_TRACE_KEY] = bucket[-48:]


def _seed_workflows(session: dict[str, Any]) -> None:
    style_sections = {"Head (Pop)": ["C", "G", "Am", "F"]}
    style_blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=STYLE_SID,
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        section_map=copy.deepcopy(style_sections),
        style=STYLE_SID,
    )
    save_workflow_blob(session, style_blob, source="harness_fp_seed")
    gen_sections = {"A": ["Cmaj7", "Am7", "Dm7", "G7"]}
    gen_blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id=GEN_SID,
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        section_map=copy.deepcopy(gen_sections),
        generated_session_id=GEN_SID,
    )
    save_workflow_blob(session, gen_blob, source="harness_fp_seed")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=STYLE_SID),
        source="harness_fp_seed",
    )
    session.update(
        {
            "studio_page": "creative",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": STYLE_SID,
            "improv_style_key": "C",
            "improv_generated_sections": copy.deepcopy(style_sections),
            "improv_jam_key": "C",
            "improv_jam_style": "Harness Jam",
            "improv_jam_session": {"id": GEN_SID, "sections": copy.deepcopy(gen_sections)},
            "display_key": "C",
            "concert_key": "C",
            "_suite_active_workspace_id": "harness-fp",
            "_suite_account_id": "harness-fp-acct",
            "_music_restore_phase_complete": True,
            "_music_startup_restore_finalized": True,
        }
    )


def _simulate_authenticated_bootstrap(session: dict[str, Any]) -> dict[str, str]:
    try:
        from music_restore_phase import begin_music_script_run

        begin_music_script_run(session)
    except ImportError:
        pass
    session[HARNESS_RUN_KEY] = int(session.get(HARNESS_RUN_KEY) or 0) + 1
    session["_script_run_seq"] = session[HARNESS_RUN_KEY]
    session.setdefault("_suite_auth_complete", True)
    session.setdefault("_suite_user_email", "harness@example.com")
    if not session.get("_harness_fp_seeded"):
        _seed_workflows(session)
        session["_harness_fp_seeded"] = True
    from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers

    phases = run_pre_widget_application_consumers(session, st=st)
    _append_trace(session, "bootstrap", phases=phases, run_seq=session[HARNESS_RUN_KEY])
    return phases


def _lock_widgets_like_sidebar(session: dict[str, Any]) -> None:
    try:
        from sidebar_key_identity import prime_sidebar_practice_key_from_identity

        prime_sidebar_practice_key_from_identity(session)
    except ImportError:
        pass
    try:
        from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY

        session[STREAMLIT_WIDGETS_LOCKED_KEY] = True
    except ImportError:
        session["_streamlit_widgets_locked_this_run"] = True


def _mission_backing_click_handler(session: dict[str, Any]) -> Callable[[], None]:
    def _on_click() -> None:
        session[HARNESS_MISSION_BACKING_CLICKS_KEY] = int(session.get(HARNESS_MISSION_BACKING_CLICKS_KEY) or 0) + 1
        try:
            from music_workflow_pending_backing_handoff import (
                arm_pending_backing_handoff_consume,
                queue_pending_backing_workflow_handoff,
                request_pending_backing_handoff_rerun,
            )

            queue_pending_backing_workflow_handoff(
                session,
                backing_source="entry_jam",
                workflow_owner="style_jam",
                activation_source="harness_explicit_open_backing",
            )
            arm_pending_backing_handoff_consume(session)
            request_pending_backing_handoff_rerun(st, session)
        except ImportError:
            pass

    return _on_click


def _render_creative_shell(session: dict[str, Any]) -> None:
    def _on_improv_tab_change() -> None:
        try:
            from music_workflow_creative_nav import sync_workflow_for_creative_tab

            sync_workflow_for_creative_tab(
                session,
                str(session.get("improv_intelligence_tab") or "").strip(),
            )
        except ImportError:
            pass

    active_tab = st.radio(
        "Improvisation section",
        list(IMPROV_TAB_NAMES),
        horizontal=True,
        key="improv_intelligence_tab",
        label_visibility="collapsed",
        on_change=_on_improv_tab_change,
    )
    wf_status = "skipped"
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        wf_status = sync_workflow_for_creative_tab(session, str(active_tab or "").strip())
    except ImportError:
        pass
    _append_trace(session, "creative_tab_sync", status=wf_status, tab=str(active_tab or ""))

    if str(active_tab or "").strip() != "Entry & Jam":
        st.info("Switch to **Entry & Jam** for Style Jam / Generator proofs.")
        return

    from improvisation_intelligence import ImprovSessionContext
    from improvisation_intelligence_ui import _tab_entry_modes

    improv_ctx = ImprovSessionContext(
        song_title="Harness",
        artist="",
        key_center="C",
        display_key="C",
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        sections={},
        bpm=110,
        style_label="",
        progression_flat=[],
        section_order=[],
    )
    _tab_entry_modes(
        st,
        session_state=session,
        improv_ctx=improv_ctx,
        is_custom=False,
        on_open_backing=_mission_backing_click_handler(session),
        on_open_practice=None,
        on_song_source_change=None,
        apply_style_to_playback=None,
    )


st.set_page_config(page_title="Creative full-production harness", layout="wide")
st.title("Creative Entry & Jam — full production harness")

bootstrap = _simulate_authenticated_bootstrap(st.session_state)

st.sidebar.markdown("### Sidebar (production lock order)")
st.sidebar.selectbox(
    "Practice / Concert Key",
    ENHARMONIC_MAJOR_KEYS,
    key="display_key",
)
_lock_after_sidebar = _lock_widgets_like_sidebar(st.session_state)

try:
    from music_workflow_deferred_legacy_projection import try_complete_deferred_legacy_projection

    try_complete_deferred_legacy_projection(st.session_state)
except ImportError:
    pass

_render_creative_shell(st.session_state)

with st.expander("Diagnostics", expanded=False):
    st.json({"bootstrap": bootstrap, "widgets_locked": bool(_lock_after_sidebar)})
    try:
        from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

        pending = peek_pending_backing_workflow_handoff(st.session_state)
        if pending:
            st.warning("Pending backing handoff present")
            st.json(pending)
    except ImportError:
        pending = st.session_state.get("_music_pending_backing_workflow_handoff")
        if pending:
            st.json(pending)
    trace = st.session_state.get("_music_mission_backing_handoff_trace")
    if trace:
        st.markdown("**mission_backing_handoff trace**")
        st.json(trace)
    st.markdown("**Harness trace**")
    st.json(st.session_state.get(HARNESS_TRACE_KEY) or [])
