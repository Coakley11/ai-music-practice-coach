"""MC3 — real app run: Missions page, Target Scope 3 chords on Ipanema's Outro ii–V–I.

Generate / Harder / New idea a span Mission, check notation fidelity, then return to
Single chord and confirm the existing Missions flow is still there and untouched.
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

    data_dir = tempfile.mkdtemp(prefix="mc3_span_missions_")
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
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _button(at, key):
    return next((w for w in at.button if str(w.key) == key), None)


def _click(at, key):
    _button(at, key).click()
    at.run(timeout=240)


def _open_missions(at):
    if at.session_state["studio_page"] != "creative":
        _button(at, "studio_quick_nav_btn_creative").click()
        at.run(timeout=240)
    try:
        at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
        at.run(timeout=240)
    except Exception:
        pass
    options = at.radio(key="improv_intelligence_tab").options
    at.radio(key="improv_intelligence_tab").set_value([o for o in options if "Mission" in o][0])
    at.run(timeout=240)


def test_span_mission_journey(app):
    at = app
    _open_missions(at)
    assert at.radio(key="improv_mission_target_scope").value == "single"  # default unchanged
    assert any(str(s.key) == "improv_mission_pick" for s in at.selectbox)  # single-chord Missions as before
    single_before = at.session_state["improv_mission_example"] if "improv_mission_example" in at.session_state else None

    at.radio(key="improv_mission_target_scope").set_value("span3")
    at.run(timeout=240)
    box = at.selectbox(key="improv_mission_span_pick_3")
    label = box.options[box.index].replace(" · ★ Recommended", "")
    assert label.endswith("· ii–V–I · Outro"), label
    shown_chords = label.split(" · ")[0].split(" → ")
    missions = at.selectbox(key="improv_span_mission_pick")
    assert "Resolve through a ii–V–I" in missions.options
    assert "Voice-lead the guide tones" in missions.options
    missions.set_value("guide_tone_voice_leading")
    at.run(timeout=240)

    _click(at, "improv_span_mission_gen")
    state = at.session_state["improv_span_mission"]
    example = state["example"]
    assert example["valid"] and example["mission_id"] == "guide_tone_voice_leading"
    assert example["difficulty"] == "normal"
    abc = at.session_state["improv_span_mission_abc"]
    assert decode_abc_midis(abc) == example["motif"]["midi"]
    assert bar_chord_symbols(abc)[:3] == [[c] for c in shown_chords]
    assert any("Where the Mission happens" in str(m.value) for m in at.markdown)

    _click(at, "improv_span_mission_harder")
    harder = at.session_state["improv_span_mission"]["example"]
    assert harder["difficulty"] == "harder" and harder["valid"]
    assert len(harder["motif"]["midi"]) > len(example["motif"]["midi"])

    _click(at, "improv_span_mission_new")
    new = at.session_state["improv_span_mission"]["example"]
    assert new["difficulty"] == "harder" and new["idea"] == 1 and new["valid"]
    assert new["motif"]["midi"] != harder["motif"]["midi"]

    at.radio(key="improv_mission_target_scope").set_value("single")
    at.run(timeout=240)
    assert any(str(s.key) == "improv_mission_pick" for s in at.selectbox)
    single_after = at.session_state["improv_mission_example"] if "improv_mission_example" in at.session_state else None
    assert single_after == single_before
