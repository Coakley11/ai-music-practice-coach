"""Minimal Streamlit harness — Composition Vision widget lifecycle."""

from __future__ import annotations

import streamlit as st

from composition_document import bootstrap_from_vision
from composition_session_state import init_composer_page_state, set_active_document
from composition_studio_page import _render_phase_vision

st.set_page_config(page_title="Composition Vision Harness", layout="wide")
init_composer_page_state(st.session_state)
if "harness_doc" not in st.session_state:
    st.session_state["harness_doc"] = bootstrap_from_vision(
        genre="Jewish",
        song_idea="A reflective prayer melody.",
        key="D minor",
        bpm=88,
        meter="4/4",
    )
    set_active_document(st.session_state, st.session_state["harness_doc"])
_render_phase_vision(st.session_state, st.session_state["harness_doc"])
