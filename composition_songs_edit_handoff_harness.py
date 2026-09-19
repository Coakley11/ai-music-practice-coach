"""Browser / AppTest harness: Songs-like Edit opens the exact saved Composition."""

from __future__ import annotations

import streamlit as st

from composition_document import (
    add_melody_phrase,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import get_active_document, save_document_to_library, set_active_document
from composition_songs_bridge import (
    apply_pending_composer_studio_edit,
    composition_pick_key_for,
    open_saved_composition_for_studio_edit,
)
from studio_page_persistence import handle_studio_page_transition, save_page_snapshot


def _tonic_from_key_label(key: str) -> str:
    raw = str(key or "C").strip()
    token = raw.split()[0] if raw else "C"
    if "minor" in raw.lower() and not token.lower().endswith("m"):
        return f"{token}m"
    return token


def _make_doc(*, title: str, key: str, bpm: int, idea: str, chords: str) -> dict:
    doc = bootstrap_from_vision(
        genre="Pop" if title.endswith("A") else "Rock",
        song_idea=idea,
        title=title,
    )
    g = doc.setdefault("global", {})
    g["original_key_center"] = _tonic_from_key_label(key)
    g["bpm"] = int(bpm)
    g["time_signature"] = "4/4"
    apply_structure_template(doc, "simple")
    first_id = str(ordered_sections(doc)[0]["id"])
    apply_section_chords(doc, first_id, parse_chord_paste(chords))
    add_melody_phrase(doc, first_id, label="Hook", motif="C4 E4 G4", notes="C4 E4 G4")
    return doc


if "_edit_handoff_seeded" not in st.session_state:
    doc_a = _make_doc(
        title="Edit Test A",
        key="C major",
        bpm=100,
        idea="Harness song A",
        chords="C Am F G",
    )
    doc_b = _make_doc(
        title="Edit Test B",
        key="G major",
        bpm=120,
        idea="Harness song B",
        chords="G D Em C",
    )
    set_active_document(st.session_state, doc_a)
    save_document_to_library(st.session_state, doc_a)
    set_active_document(st.session_state, doc_b)
    save_document_to_library(st.session_state, doc_b)
    # Last-active leftover is A; Edit B must still open B.
    set_active_document(st.session_state, doc_a)
    st.session_state["studio_page"] = "composer"
    save_page_snapshot(st.session_state, "composer")
    st.session_state["studio_page"] = "picker"
    st.session_state["_studio_active_page_id"] = "picker"
    st.session_state["_harness_id_a"] = str(doc_a["id"])
    st.session_state["_harness_id_b"] = str(doc_b["id"])
    st.session_state["_harness_pick_a"] = composition_pick_key_for(doc_a)
    st.session_state["_harness_pick_b"] = composition_pick_key_for(doc_b)
    st.session_state["_edit_handoff_seeded"] = True

st.caption("composition_songs_edit_handoff_harness")

if str(st.session_state.get("studio_page") or "") != "composer":
    st.write("Songs → Composition")
    if st.button("Edit Composition A", key="harness_edit_a"):
        open_saved_composition_for_studio_edit(st, str(st.session_state.get("_harness_id_a") or ""))
        st.rerun()
    if st.button("Edit Composition B", key="harness_edit_b"):
        open_saved_composition_for_studio_edit(st, str(st.session_state.get("_harness_id_b") or ""))
        st.rerun()
else:
    handle_studio_page_transition(st.session_state)
    apply_pending_composer_studio_edit(st.session_state)
    if st.button("Back to Songs", key="harness_back_songs"):
        st.session_state["studio_page"] = "picker"
        st.session_state["_studio_active_page_id"] = "picker"
        st.rerun()
    doc = get_active_document(st.session_state)
    if isinstance(doc, dict):
        g = doc.get("global") or {}
        st.caption(
            "handoff_id="
            + str(doc.get("id") or "")
            + " title="
            + str(doc.get("title") or "")
            + " bpm="
            + str(g.get("bpm") or "")
            + " key="
            + str(g.get("original_key_center") or "")
        )
