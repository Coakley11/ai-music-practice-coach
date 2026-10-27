"""Song-Aware Coaching S4 — examples in the real app (Perfect, 6/8, Practice Key G).

Hidden until asked for; the shown phrase is the same across reruns, challenge navigation, tab
changes and an instrument change (only its written display moves); "a different idea" changes
it on purpose; a Practice Key change clears it. Nothing outside coaching is written.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from tests.test_song_coach_apptest import (
    _assert_unchanged,
    _button,
    _click,
    _guarded,
    _no_exception,
    _open,
    _state,
    require_isolated_data_dir,
)

DIAG = "_song_coach_example_diag"
SHOW = "song_coach_example_toggle"
NEW = "song_coach_example_new"


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_examples_apptest_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        require_isolated_data_dir(data_dir)
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
        at.run(timeout=300)
        _click(at, "studio_quick_nav_btn_picker")
        dropdown = at.selectbox(key="matching_song_dropdown")
        dropdown.set_value([o for o in dropdown.options if o.startswith("Perfect")][0])
        at.run(timeout=300)
        _open(at)
        _click(at, "song_coach_build")
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _diag(at):
    return at.session_state[DIAG] if DIAG in at.session_state else None


def _phrase(at):
    d = _diag(at)
    return [seg["concert_midi"] for seg in d["segments"]] if d else None


def _example_shown(at) -> bool:
    return any(m.value.startswith("**Example**") for m in at.markdown)


def test_examples_are_hidden_until_asked_for(app):
    at = app
    _no_exception(at)
    assert _button(at, SHOW) is not None and "Show an Example" in _button(at, SHOW).label
    assert _diag(at) is None and not _example_shown(at)
    assert _state(at)["examples"] == [] and _state(at)["example_nonce"] == 0


def test_show_an_example_draws_validated_concert_notation(app):
    from tests.abc_pitch_decoder import abc_bar_totals, decode_abc_midis

    at = app
    before = _guarded(at)
    _click(at, SHOW)
    _no_exception(at)
    assert _state(at)["examples"] == [0]
    d = _diag(at)
    assert d["available"] and d["kind"] == "idea" and d["segments"]
    seg = d["segments"][0]
    assert seg["key"] == "G" and "M:6/8" in seg["abc"] and "K:G" in seg["abc"]
    assert decode_abc_midis(seg["abc"]) == seg["concert_midi"] == seg["midi"]
    assert all(t == 3 for t in abc_bar_totals(seg["abc"]))
    assert seg["chords"] == ["G", "Em7"]
    assert _example_shown(at)
    assert any("not the song's melody" in c.value for c in at.caption)
    assert "Hide" in _button(at, SHOW).label
    _assert_unchanged(before, _guarded(at))


def test_the_example_keeps_its_identity_across_reruns_navigation_and_tabs(app):
    at = app
    first = _phrase(at)
    at.run(timeout=300)
    assert _phrase(at) == first
    _click(at, "song_coach_next")
    assert _diag(at) is None, "the next challenge's example stays hidden until asked for"
    _click(at, "song_coach_prev")
    assert _phrase(at) == first
    _open(at, "Missions")
    _open(at)
    _no_exception(at)
    assert _phrase(at) == first


def test_alto_sax_moves_only_the_written_display(app):
    at = app
    plan_id, first = _state(at)["plan_id"], _phrase(at)
    at.selectbox(key="instrument").set_value("Saxophone")
    at.run(timeout=300)
    at.checkbox(key="show_chart_in_instrument_key").set_value(True)
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert _state(at)["plan_id"] == plan_id
    assert _phrase(at) == first, "the same concert phrase"
    seg = _diag(at)["segments"][0]
    assert seg["key"] == "E" and "K:E" in seg["abc"]
    assert seg["midi"] == [m + 9 for m in seg["concert_midi"]]
    assert seg["chords"] == ["E", "C#m7"]
    assert at.session_state["concert_key"] == "G"


def test_a_different_idea_changes_the_example_on_purpose(app):
    at = app
    first = _phrase(at)
    _click(at, NEW)
    _no_exception(at)
    assert _state(at)["example_nonce"] == 1
    assert _phrase(at) != first
    again = _phrase(at)
    at.run(timeout=300)
    assert _phrase(at) == again


def test_practice_key_change_clears_the_examples(app):
    at = app
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    practice_key.set_value("A")
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert _diag(at) is None and not _example_shown(at)
    _click(at, "song_coach_build")
    state = _state(at)
    assert state["examples"] == [] and state["example_nonce"] == 0
    _click(at, SHOW)
    seg = _diag(at)["segments"][0]
    assert seg["concert_midi"] and at.session_state["concert_key"] == "A"
    assert seg["chords"] in (["F#", "D#m7"], ["Gb", "Ebm7"]), seg["chords"]  # written for alto at concert A
