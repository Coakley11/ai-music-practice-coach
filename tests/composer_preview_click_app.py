"""Minimal Streamlit page: Preview click mounts autoplay audio in the same run."""

from __future__ import annotations

import streamlit as st

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_preview import (
    flush_composer_preview_dock,
    play_composer_preview,
    request_composer_preview_dock,
)


def main() -> None:
    if "harness_doc" not in st.session_state:
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="Harness", key="C major", bpm=100, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        st.session_state["harness_doc"] = doc
        st.session_state["harness_sid"] = str(verse["id"])
    request_composer_preview_dock(st.session_state, "harness_stop")
    if st.button("▶ Preview", key="harness_preview"):
        result = play_composer_preview(
            st.session_state,
            st.session_state["harness_doc"],
            section_id=st.session_state["harness_sid"],
            loops=1,
            include_melody=False,
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Could not preview."))
    if st.button("▶ Play chords", key="harness_play_chords"):
        result = play_composer_preview(
            st.session_state,
            st.session_state["harness_doc"],
            section_id=st.session_state["harness_sid"],
            loops=1,
            include_melody=False,
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Could not play chords."))
    flush_composer_preview_dock(st, st.session_state)


main()
