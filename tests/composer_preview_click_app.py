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
from composition_preview import play_composer_preview, render_local_composer_playback


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
    if st.button("▶ Preview", key="harness_preview"):
        result = play_composer_preview(
            st.session_state,
            st.session_state["harness_doc"],
            section_id=st.session_state["harness_sid"],
            loops=1,
            include_melody=False,
            slot="harness-preview",
            label="Playing · Preview",
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Could not preview."))
    render_local_composer_playback(st, st.session_state, slot="harness-preview")
    if st.button("▶ Play chords", key="harness_play_chords"):
        result = play_composer_preview(
            st.session_state,
            st.session_state["harness_doc"],
            section_id=st.session_state["harness_sid"],
            loops=1,
            include_melody=False,
            slot="harness-play-chords",
            label="Playing chords",
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Could not play chords."))
    render_local_composer_playback(st, st.session_state, slot="harness-play-chords")


main()
