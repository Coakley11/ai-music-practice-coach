"""Minimal Streamlit harness — Composition Welcome widget lifecycle (crash repro)."""

from __future__ import annotations

import streamlit as st

from composition_session_state import COMPOSER_NEEDS_SEED_KEY, init_composer_page_state
from composition_studio_page import _render_welcome_entry

st.set_page_config(page_title="Composition Welcome Harness", layout="wide")
init_composer_page_state(st.session_state)
st.session_state[COMPOSER_NEEDS_SEED_KEY] = True
_render_welcome_entry(st.session_state)
