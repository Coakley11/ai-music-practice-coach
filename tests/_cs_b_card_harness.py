"""AppTest harness: render one chord suggestion card + the refinement panel (cluster B)."""
import sys

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, ".")

from composition_chord_suggestions import suggest_progressions  # noqa: E402
from composition_document import (  # noqa: E402
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
import composition_studio_page as csp  # noqa: E402

st.session_state["_html_calls"] = []


def _fake_html(html, height=None, scrolling=False, **kw):
    st.session_state["_html_calls"].append({"html": str(html), "height": height})


components.html = _fake_html

if "doc" not in st.session_state:
    doc = bootstrap_from_vision(genre="Jazz", song_idea="A song.", key="C major", bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    sec0 = ordered_sections(doc)[0]
    apply_section_chords(doc, str(sec0["id"]), parse_chord_paste("Cmaj7 Am7 Dm7 G7"))
    st.session_state["doc"] = doc
    st.session_state["sec_id"] = str(sec0["id"])
doc = st.session_state["doc"]
section_id = st.session_state["sec_id"]
section = csp.section_by_id(doc, section_id)
sugs = suggest_progressions(doc, section, "tense", limit=3)
st.session_state["_sugs"] = [s["id"] for s in sugs]
for i, sug in enumerate(sugs):
    csp._render_suggestion_card(st.session_state, doc, section_id, sug, prefix=f"t{i}", section=section)
if st.session_state.get("_show_refine"):
    csp._render_chord_refinement_panel(st.session_state, doc, section_id, section)
