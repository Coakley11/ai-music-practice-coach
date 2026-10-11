"""MC2 — real app run: generate / build / change rhythm a span motif in Phrase / Motif.

The Girl from Ipanema (catalog, F) with Guitar, Creative → Phrase / Motif → 3 chords →
Gm7 → C7 → Fmaj7 (ii–V–I). The single-chord motif stays untouched throughout.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from tests.abc_pitch_decoder import bar_chord_symbols, decode_abc_midis


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="mc2_span_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=240)
        at.run(timeout=300)
        _button(at, "studio_quick_nav_btn_picker").click()
        at.run(timeout=240)
        dropdown = at.selectbox(key="matching_song_dropdown")
        at.selectbox(key="matching_song_dropdown").set_value([o for o in dropdown.options if "Ipanema" in o][0])
        at.run(timeout=240)
        at.selectbox(key="instrument").set_value("Guitar")
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


def _click(at, key):
    _button(at, key).click()
    at.run(timeout=240)


def _state(at):
    return at.session_state["improv_span_motif"]


def test_span_motif_journey(app):
    from improvisation_motif import midi_from_guitar_position, motif_guitar_tab_placements

    at = app
    _open_tab(at, "Phrase / Motif")
    single_before = at.session_state["improv_motif"] if "improv_motif" in at.session_state else None
    at.radio(key="improv_motif_target_scope").set_value("span3")
    at.run(timeout=240)
    box = at.selectbox(key="improv_motif_span_pick_3")
    label = box.options[box.index].replace(" · ★ Recommended", "")
    # The Outro ii–V–I (Gm7 → C7 → Fmaj7 at the song's F; a Practice Key inherited from
    # earlier app runs in the same process shows the same logical span transposed).
    assert label.endswith("· ii–V–I · Outro"), label
    shown_chords = label.split(" · ")[0].split(" → ")

    _click(at, "improv_span_gen")
    seed = _state(at)["current"]
    assert len(seed["span_chords"]) == 3
    assert set(seed["note_chord_index"]) == {0, 1, 2}
    abc = at.session_state["improv_span_motif_abc"]
    assert decode_abc_midis(abc) == seed["midi"]
    assert bar_chord_symbols(abc) == [[c] for c in shown_chords] + [[]]
    tab = [c.value for c in at.code if "|" in str(c.value) and str(c.value).splitlines()[0].startswith("e")]
    assert tab, "Guitar TAB rendered"
    frets = motif_guitar_tab_placements(seed)
    assert [midi_from_guitar_position(s, f) for s, f in frets] == seed["midi"]

    build_btn = _button(at, "improv_span_build")
    assert build_btn.proto.type == "primary"  # MC2.1: the Build CTA is the red primary button
    _click(at, "improv_span_build")
    built = _state(at)["current"]
    assert built["span_length"] == "standard" and built["span_seed"] == seed["span_seed"]
    assert built["strategy_family"] == seed["strategy_family"]
    assert at.session_state["improv_span_song_style"] == "jazz"  # Ipanema: Jazz genre metadata
    assert decode_abc_midis(at.session_state["improv_span_motif_abc"]) == built["midi"]

    _click(at, "improv_span_rhythm")
    rhythm = _state(at)["current"]
    assert rhythm["midi"] == built["midi"] and rhythm["note_chord_index"] == built["note_chord_index"]
    assert rhythm["rhythm_meta"]["id"] != built["rhythm_meta"]["id"]

    # Leave and re-enter: same span, same developed idea.
    _open_tab(at, "Harmony Map")
    _open_tab(at, "Phrase / Motif")
    assert at.radio(key="improv_motif_target_scope").value == "span3"
    assert _state(at)["current"]["midi"] == rhythm["midi"]
    assert decode_abc_midis(at.session_state["improv_span_motif_abc"]) == rhythm["midi"]

    single_after = at.session_state["improv_motif"] if "improv_motif" in at.session_state else None
    assert single_after == single_before  # the single-chord seed was never replaced
