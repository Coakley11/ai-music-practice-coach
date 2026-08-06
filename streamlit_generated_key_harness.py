"""Minimal Streamlit lifecycle repro — production callbacks + pre-widget bootstrap.

Run: streamlit run streamlit_generated_key_harness.py

Uses the same capture → rerun → run_pre_widget_application_consumers path as the
main app (without auth/chart bundle). For stop-the-line UI verification only.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import streamlit as st

from music_theory import ENHARMONIC_MAJOR_KEYS, key_center_token
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)

STYLE_SID = "Pop groove"
GEN_SID = "jam-harness-1"
HARNESS_RUN_KEY = "_harness_run_seq"


def _seed_style_jam(session: dict[str, Any]) -> None:
    sections = {"Head (Pop)": ["C", "G", "Am", "F"]}
    sid = STYLE_SID
    blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        section_map=copy.deepcopy(sections),
        style=sid,
    )
    save_workflow_blob(session, blob, source="harness_seed")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
        source="harness_seed",
    )
    session.update(
        {
            "studio_page": "creative",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": sid,
            "improv_style_key": "C",
            "improv_generated_sections": copy.deepcopy(sections),
        }
    )


def _seed_generator(session: dict[str, Any]) -> None:
    sections = {"A": ["Cmaj7", "Am7", "Dm7", "G7"]}
    jam_id = GEN_SID
    blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id=jam_id,
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        section_map=copy.deepcopy(sections),
        generated_session_id=jam_id,
    )
    save_workflow_blob(session, blob, source="harness_seed")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id=jam_id),
        source="harness_seed",
    )
    session.update(
        {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "improv_jam_style": "Harness Jam",
            "improv_jam_session": {"id": jam_id, "sections": copy.deepcopy(sections)},
        }
    )


def _sync_selector_from_blob(session: dict[str, Any], owner: str, session_id: str) -> str:
    blob = get_workflow_blob(session, owner, session_id)
    if blob is None:
        return "C"
    token = key_center_token(str(blob.keys.practice_tonic or "C"), str(blob.keys.practice_mode or "major"))
    if owner == "style_jam":
        session["improv_style_key"] = token
    else:
        session["improv_jam_key"] = token
    return token


def _harness_bootstrap(session: dict[str, Any]) -> dict[str, str]:
    try:
        from music_restore_phase import begin_music_script_run

        begin_music_script_run(session)
    except ImportError:
        pass
    session[HARNESS_RUN_KEY] = int(session.get(HARNESS_RUN_KEY) or 0) + 1
    session.setdefault("_suite_active_workspace_id", "harness")
    session.setdefault("_suite_account_id", "harness-acct")
    session.setdefault("_script_run_seq", session[HARNESS_RUN_KEY])
    session.pop("_music_first_streamlit_widget", None)
    session.pop("_streamlit_widgets_locked_this_run", None)
    if not session.get("_harness_seeded"):
        _seed_style_jam(session)
        _seed_generator(session)
        session["_harness_seeded"] = True
    from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers

    return run_pre_widget_application_consumers(session, st=st)


st.set_page_config(page_title="Generated Key Harness", layout="wide")
st.title("Generated key lifecycle harness")

bootstrap_phases = _harness_bootstrap(st.session_state)

style_token = _sync_selector_from_blob(st.session_state, "style_jam", STYLE_SID)
gen_token = _sync_selector_from_blob(st.session_state, "jam_session_generator", GEN_SID)

tab_style, tab_gen, tab_hevenu, tab_diag = st.tabs(
    ["Style Jam", "Generator", "Hevenu sidebar", "Diagnostics"]
)

with tab_style:
    st.subheader("Style Jam — improv_style_key")
    st.caption(f"Canonical selector token (from blob): {style_token}")
    from creative_key_sync import on_improv_style_key_change

    st.selectbox(
        "Style Jam key",
        ENHARMONIC_MAJOR_KEYS,
        key="improv_style_key",
        on_change=on_improv_style_key_change,
    )
    blob = get_workflow_blob(st.session_state, "style_jam", STYLE_SID)
    if blob:
        st.json(
            {
                "practice_tonic": blob.keys.practice_tonic,
                "practice_mode": blob.keys.practice_mode,
                "progression": blob.section_map,
            }
        )

with tab_gen:
    st.subheader("Jam Session Generator — improv_jam_key")
    st.caption(f"Canonical selector token (from blob): {gen_token}")
    from creative_key_sync import on_improv_jam_key_change

    st.selectbox(
        "Generator key",
        ENHARMONIC_MAJOR_KEYS,
        key="improv_jam_key",
        on_change=on_improv_jam_key_change,
    )
    gb = get_workflow_blob(st.session_state, "jam_session_generator", GEN_SID)
    if gb:
        st.json(
            {
                "practice_tonic": gb.keys.practice_tonic,
                "practice_mode": gb.keys.practice_mode,
                "progression": gb.section_map,
            }
        )

with tab_hevenu:
    st.subheader("Hevenu Shalom — sidebar key identity")
    hevenu_session = {
        **st.session_state,
        "studio_page": "creative",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
        "selected_song": {"pick_key": "Jewish|Hevenu Shalom Aleichem", "key": "Dm"},
        "display_key": "D#",
        "concert_key": "D#",
    }
    try:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

        hevenu_session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
            "key_owner": "entry_jam",
            "entry_mode": "Style Jam Mode",
        }
    except ImportError:
        pass
    from sidebar_key_identity import resolve_sidebar_key_identity

    ident = resolve_sidebar_key_identity(hevenu_session)
    st.json(
        {
            "concert_tonic": ident.concert_tonic,
            "concert_mode": ident.concert_mode,
            "practice_tonic": ident.practice_tonic,
            "practice_mode": ident.practice_mode,
            "label": ident.label,
            "selector_token": ident.selector_token,
            "owner": ident.owner,
        }
    )
    st.warning("Stale compatibility display_key in session is D# — identity must still be D minor.")

with tab_diag:
    st.subheader("Pre-widget bootstrap (this run)")
    st.json(bootstrap_phases)
    st.subheader("Pending / outcome / projection")
    for key in (
        "_music_pending_generated_key_edit",
        "_music_generated_key_edit_outcome",
        "_music_projection_block_last",
        "_music_workflow_deferred_legacy_projection",
        "_music_pre_widget_bootstrap_last",
    ):
        val = st.session_state.get(key)
        if val:
            st.markdown(f"**{key}**")
            st.json(val if isinstance(val, (dict, list)) else {"value": val})

    st.subheader("Deploy identity (local git / env)")
    try:
        from music_deploy_verification import resolve_deploy_identity

        st.json(resolve_deploy_identity())
    except ImportError:
        pass
