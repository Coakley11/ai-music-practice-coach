"""MC1 — real app run: Phrase / Motif target scope at a transposed, written-key chart.

Boots the studio exactly as R9 does — The Girl from Ipanema (catalog, original F),
alto saxophone, written charts on, explicit concert Practice Key E (written C#), the
setup R9 proves survives Creative navigation — then opens Creative → Phrase / Motif.
The spans shown must be the *same logical spans* (same ids, same ranking, same
key-relative labels) the analyzer gives the original F chart, displayed in the alto's
written key.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

SONG = "Ipanema"


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="mc1_span_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=240)
        at.run(timeout=300)
        _button(at, "studio_quick_nav_btn_picker").click()
        at.run(timeout=240)
        dropdown = at.selectbox(key="matching_song_dropdown")
        at.selectbox(key="matching_song_dropdown").set_value([o for o in dropdown.options if SONG in o][0])
        at.run(timeout=240)
        at.selectbox(key="instrument").set_value("Saxophone")
        at.run(timeout=240)
        at.checkbox(key="show_chart_in_instrument_key").set_value(True)
        at.run(timeout=240)
        [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0].set_value("E")
        at.run(timeout=240)
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _button(at, key):
    return next((w for w in at.button if str(w.key) == key), None)


def _open_tab(at, needle):
    if at.session_state["studio_page"] != "creative":
        _button(at, "studio_quick_nav_btn_creative").click()
        at.run(timeout=240)
    try:
        at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
        at.run(timeout=240)
    except Exception:
        pass
    options = at.radio(key="improv_intelligence_tab").options
    at.radio(key="improv_intelligence_tab").set_value([o for o in options if needle in o][0])
    at.run(timeout=240)


def _shown(box) -> str:
    return box.options[box.index]


def _offline_spans_at_original_key(pick_key: str):
    """Analyzer output for the untransposed catalog chart (F) with the app's source id."""
    from harmonic_span_analyzer import analyze_harmonic_spans
    from improvisation_intelligence_ui import _safe_widget_key_part
    from improvisation_motif import section_harmony_rows
    from song_catalog.catalog import curated_song_records

    record = next(r for r in curated_song_records() if SONG in r["title"])
    sections = record["sections"]
    rows = section_harmony_rows(sections, section_names=record.get("section_order") or list(sections))
    return analyze_harmonic_spans(rows, key_center=record["key"], length=3, source_id=_safe_widget_key_part(pick_key))


def _chart_key(at) -> str:
    from effective_practice_context import musician_facing_chart_key

    return musician_facing_chart_key(dict(at.session_state.filtered_state))


def test_span_scope_at_a_transposed_practice_key(app):
    from music_theory import chord_root_for_theory, pitch_class_from_spelled_note

    at = app
    _open_tab(at, "Phrase / Motif")
    assert at.session_state["concert_key"] == "E"
    assert _chart_key(at) == "C#"
    # Original chart F → shown written chart C#.
    shift = (pitch_class_from_spelled_note("C#") - pitch_class_from_spelled_note("F")) % 12

    # Single chord stays the default and keeps the generator.
    assert at.radio(key="improv_motif_target_scope").value == "single"
    assert _button(at, "improv_gen_motif_chord") is not None

    at.radio(key="improv_motif_target_scope").set_value("span3")
    at.run(timeout=240)
    assert _button(at, "improv_gen_motif_chord") is None  # no fake single-chord generation
    box = at.selectbox(key="improv_motif_span_pick_3")

    offline = _offline_spans_at_original_key(at.session_state["active_catalog_pick_key"])
    shown_ids = [at.session_state["improv_motif_span_pick_3"]]
    # Same logical spans in the same order: every label keeps its key-relative harmony
    # and section, and every chord is the F chart moved to the alto's written C# chart.
    assert len(box.options) == len(offline)
    for label, span in zip(box.options, offline):
        chords, *rest = label.split(" · ")
        expected_rest = [p for p in (span.relationship_label, span.section_label) if p]
        assert rest == expected_rest, (label, span)
        roots = [pitch_class_from_spelled_note(chord_root_for_theory(c)) for c in chords.split(" → ")]
        expected = [(pitch_class_from_spelled_note(chord_root_for_theory(c)) + shift) % 12 for c in span.chords]
        assert roots == expected, (label, span.chords)
    assert box.options[0].endswith("· ii–V–I · Outro")
    # Stable identity: the selected span id at G is the analyzer's id for the F chart.
    assert shown_ids[0] == offline[0].span_id

    # A user pick survives leaving and re-entering the tab.
    target_index = next(i for i, s in enumerate(offline) if s.relationship_label == "ii–subV–I")
    box.select_index(target_index)
    at.run(timeout=240)
    picked_id = at.session_state["improv_motif_span_pick_3"]
    assert picked_id == offline[target_index].span_id
    _open_tab(at, "Harmony Map")
    _open_tab(at, "Phrase / Motif")
    assert at.radio(key="improv_motif_target_scope").value == "span3"
    assert at.session_state["improv_motif_span_pick_3"] == picked_id
    assert _shown(at.selectbox(key="improv_motif_span_pick_3")).endswith("· ii–subV–I · A")
    assert at.session_state["concert_key"] == "E"  # MC1 never moves the Practice Key
    assert _chart_key(at) == "C#"

    # Back to single chord: the generator returns.
    at.radio(key="improv_motif_target_scope").set_value("single")
    at.run(timeout=240)
    assert _button(at, "improv_gen_motif_chord") is not None
