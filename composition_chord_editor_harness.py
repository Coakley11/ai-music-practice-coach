"""Streamlit harness — Manual / advanced chord editor widget lifecycle.

Opens the Chords-phase editor, including the refinement selectbox that used
to crash when ``Try another`` wrote a live widget key.
"""

from __future__ import annotations

import streamlit as st

from composition_chord_editor import MANUAL_EDITOR_EXPANDED_KEY
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    set_workflow_phase,
)
from composition_preview import composition_surface_label
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_NEEDS_SEED_KEY,
    init_composer_page_state,
    set_active_document,
)
from composition_studio_page import render_composition_studio_page
from composition_workspace_state_persistence import (
    apply_composition_workspace_from_payload,
    checkpoint_composition_workspace,
    gather_composition_workspace_from_session,
    prepare_composition_workspace_for_render,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


def _seed() -> None:
    if COMPOSER_ACTIVE_KEY in st.session_state and isinstance(st.session_state.get(COMPOSER_ACTIVE_KEY), dict):
        return
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="Manual chord editor harness",
        title="Editor Harness Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("F G C C"))
    set_workflow_phase(doc, "chords")
    init_composer_page_state(st.session_state)
    set_active_document(st.session_state, doc)
    st.session_state[COMPOSER_LIBRARY_KEY] = {str(doc["id"]): doc}
    st.session_state[COMPOSER_ACTIVE_SECTION_KEY] = str(verse["id"])
    st.session_state[COMPOSER_FOCUS_LANE_KEY] = "chords"
    st.session_state[COMPOSER_NEEDS_SEED_KEY] = False
    st.session_state[MANUAL_EDITOR_EXPANDED_KEY] = True
    st.session_state["harness_verse_id"] = str(verse["id"])
    st.session_state["harness_chorus_id"] = str(chorus["id"])
    st.session_state["studio_page"] = "composer"


def _simulate_refresh() -> None:
    """In-session refresh: persist, drop widget keys, rehydrate the document."""
    ss = st.session_state
    checkpoint_composition_workspace(ss, reason="harness_refresh", force_disk=False, st=st)
    blob = gather_composition_workspace_from_session(ss)
    drop = [
        k
        for k in list(ss.keys())
        if str(k).startswith("composer_refine_intent")
        or str(k).startswith("composer_cedit_")
        or str(k).startswith("composer_refine_proposal")
    ]
    for key in drop:
        ss.pop(key, None)
    apply_composition_workspace_from_payload(
        ss, {"composition_workspace_state": blob}, authoritative=True
    )
    ss[MANUAL_EDITOR_EXPANDED_KEY] = True
    prepare_composition_workspace_for_render(ss)


def _simulate_cold_restore() -> None:
    """Cold session: disk envelope → empty state → prepare for render."""
    ss = st.session_state
    checkpoint_composition_workspace(ss, reason="harness_cold", force_disk=False, st=st)
    class _St:
        session_state = ss

    blob = build_music_disk_state(_St())
    keep_ids = {
        "harness_verse_id": ss.get("harness_verse_id"),
        "harness_chorus_id": ss.get("harness_chorus_id"),
    }
    for key in list(ss.keys()):
        if str(key).startswith("composer") or key in {
            COMPOSER_ACTIVE_KEY,
            COMPOSER_LIBRARY_KEY,
            COMPOSER_ACTIVE_SECTION_KEY,
            COMPOSER_FOCUS_LANE_KEY,
            COMPOSER_NEEDS_SEED_KEY,
            "composition_workspace_state",
            "studio_page",
        }:
            ss.pop(key, None)
    apply_music_disk_state(
        st,
        blob,
        song_picker_catalog={},
        song_library={},
        authoritative_restore=True,
    )
    prepare_composition_workspace_for_render(ss)
    ss[MANUAL_EDITOR_EXPANDED_KEY] = True
    ss.update({k: v for k, v in keep_ids.items() if v})
    ss["studio_page"] = "composer"


st.set_page_config(page_title="Composition chord editor harness", layout="wide")
_seed()
st.caption(composition_surface_label())
h1, h2 = st.columns(2)
with h1:
    if st.button("Harness: simulate refresh", key="harness_simulate_refresh"):
        _simulate_refresh()
        st.rerun()
with h2:
    if st.button("Harness: cold restore", key="harness_cold_restore"):
        _simulate_cold_restore()
        st.rerun()
render_composition_studio_page()
