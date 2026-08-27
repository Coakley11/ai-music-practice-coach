"""Streamlit smoke page: Composition Melody/Chords QA controls at the deployed SHA."""

from __future__ import annotations

import streamlit as st

from composition_document import (
    apply_melody_events,
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
    COMPOSER_NEEDS_SEED_KEY,
    init_composer_page_state,
)
from composition_studio_page import render_composition_studio_page


def _seed() -> None:
    if COMPOSER_ACTIVE_KEY in st.session_state and isinstance(st.session_state.get(COMPOSER_ACTIVE_KEY), dict):
        return
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="QA smoke",
        title="QA Smoke Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    apply_melody_events(
        doc,
        str(verse["id"]),
        [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ],
        replace=True,
    )
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("F G C C"))
    apply_melody_events(
        doc,
        str(chorus["id"]),
        [{"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
        replace=True,
    )
    set_workflow_phase(doc, "melody")
    init_composer_page_state(st.session_state)
    st.session_state[COMPOSER_ACTIVE_KEY] = doc
    st.session_state[COMPOSER_ACTIVE_SECTION_KEY] = str(verse["id"])
    st.session_state[COMPOSER_FOCUS_LANE_KEY] = "melody"
    st.session_state[COMPOSER_NEEDS_SEED_KEY] = False


st.set_page_config(page_title="Composition QA smoke", layout="wide")
_seed()
st.caption(composition_surface_label())
render_composition_studio_page()
