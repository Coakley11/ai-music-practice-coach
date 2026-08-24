"""Minimal shell harness: restore composer studio_page then render Composition Studio.

Used by AppTest to catch post-restore Practice defaulting / overwrite.
"""

from __future__ import annotations

import streamlit as st

from composition_document import bootstrap_from_vision
from composition_session_state import COMPOSER_ACTIVE_KEY, set_active_document
from composition_studio_page import render_composition_studio_page
from composition_workspace_state_persistence import prepare_composition_workspace_for_render
from music_persistent_state import apply_music_disk_state
from studio_nav_state import prepare_studio_nav


def _seed_blob() -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="nav restore harness",
        title="Nav Restore Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    return {
        "core": {"studio_page": "composer", "instrument": "Piano"},
        "session": {"studio_page": "composer"},
        "music_workspace_state": {"studio_page": "composer", "page": "practice"},
        "studio_nav_state": {"studio_page": "composer", "page": "composer"},
        "composition_workspace_state": {
            "schema_version": 1,
            "active_document": doc,
            "library": {str(doc["id"]): doc},
            "active_section_id": None,
            "focus_lane": "welcome",
            "needs_seed": False,
        },
    }


if "studio_page" not in st.session_state:
    blob = _seed_blob()
    apply_music_disk_state(st, blob, song_picker_catalog={}, song_library={})
    prepare_studio_nav(st.session_state)
    prepare_composition_workspace_for_render(st.session_state)
    if COMPOSER_ACTIVE_KEY not in st.session_state:
        set_active_document(st.session_state, blob["composition_workspace_state"]["active_document"])

page = st.session_state["studio_page"] if "studio_page" in st.session_state else ""
st.caption(f"harness_page={page}")
if page == "composer":
    render_composition_studio_page()
else:
    st.error(f"expected composer, got {page}")
