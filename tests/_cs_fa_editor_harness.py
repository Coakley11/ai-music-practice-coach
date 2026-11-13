"""AppTest harness: render the Advanced Phrase Editor for one section (fix-analysis)."""
import sys

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, ".")

from composition_document import (  # noqa: E402
    apply_melody_events, apply_section_chords, apply_structure_template,
    bootstrap_from_vision, ordered_sections, parse_chord_paste,
)
import importlib  # noqa: E402
import composition_studio_page as csp  # noqa: E402

csp = importlib.reload(csp)  # other tests monkeypatch module functions; start from the real ones

st.session_state["_html_calls"] = []


def _fake_html(html, height=None, scrolling=False, **kw):
    st.session_state["_html_calls"].append(str(html))


components.html = _fake_html

if "doc" not in st.session_state:
    doc = bootstrap_from_vision(genre="Pop", song_idea="A song.", key="C major", bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    sec0 = ordered_sections(doc)[0]
    apply_section_chords(doc, str(sec0["id"]), parse_chord_paste("C Am F G"))
    evs = [
        {"pitch": p, "midi": m, "duration_beats": 1.0, "beat": float(i)}
        for i, (p, m) in enumerate([("E4", 64), ("G4", 67), ("A4", 69), ("G4", 67)])
    ]
    apply_melody_events(doc, str(sec0["id"]), evs, concept={"id": "c1", "name": "C1"}, replace=True)
    st.session_state["doc"] = doc
    st.session_state["sec_id"] = str(sec0["id"])
if st.session_state.get("_arm"):
    st.session_state["composer_preview_slot"] = f"melody:{st.session_state['sec_id']}:editor_draft"
    st.session_state["composer_preview_wav"] = b"RIFF0000WAVE"
csp._render_active_melody_phrase_editor(st.session_state, st.session_state["doc"], st.session_state["sec_id"])
