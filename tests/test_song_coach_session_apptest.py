"""Song-Aware Coaching S6 — a lesson across refreshes, instrument / song / source changes and damaged
saved state, in the real app.

One booted studio: build a lesson on Perfect (custom bars, level, focus, a later challenge, a
ticked check, a shown example with a new idea, a practice tempo and the whole-selection loop),
then: refresh (a fresh app on the same saved workspace), change instrument, switch song and come
back, generate a Jam and switch song, damage the saved record, and edit a Custom chart.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile

import pytest

from tests.test_song_coach_apptest import _click, _no_exception, _open, _state, require_isolated_data_dir

EX = "_song_coach_example_diag"
LOOP = "_song_coach_loop_diag"
CTX = "_song_coach_ctx_diag"


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_session_apptest_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        require_isolated_data_dir(data_dir)
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
        at.run(timeout=300)
        _pick(at, "Perfect")
        _open(at)
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _pick(at, title):
    if at.session_state["studio_page"] != "picker":
        _click(at, "studio_quick_nav_btn_picker")
    dropdown = at.selectbox(key="matching_song_dropdown")
    dropdown.set_value([o for o in dropdown.options if o.startswith(title)][0])
    at.run(timeout=300)


def _get(at, key):
    return at.session_state[key] if key in at.session_state else None


def _set(at, kind, key, value):
    getattr(at, kind)(key=key).set_value(value)
    at.run(timeout=300)


def _plan_shown(at) -> bool:
    return any(m.value.startswith("#### Your plan") for m in at.markdown)


def _infos(at) -> list[str]:
    return [i.value for i in at.info]


def _lesson_snapshot(at) -> dict:
    s = _state(at)
    keep = ("identity", "draft", "built", "plan_id", "stage", "checks", "examples", "example_nonce", "loop_bpm", "loop_range")
    return {k: copy.deepcopy(s[k]) for k in keep}


def test_a_full_lesson_survives_a_refresh(app):
    from streamlit.testing.v1 import AppTest

    at = app
    _set(at, "selectbox", "song_coach_bar_from", 5)
    _set(at, "selectbox", "song_coach_bar_to", 12)
    _set(at, "radio", "song_coach_level", "Advanced")
    _set(at, "selectbox", "song_coach_focus", "rhythmic_development")
    _click(at, "song_coach_build")
    _click(at, "song_coach_next")
    checks = [c for c in at.checkbox if str(c.key).startswith("song_coach_check_")]
    checks[0].check()
    at.run(timeout=300)
    _click(at, "song_coach_example_toggle")
    _click(at, "song_coach_example_new")
    at.slider(key="song_coach_loop_bpm").set_value(80)
    at.run(timeout=300)
    at.radio(key="song_coach_loop_range").set_value("selection")
    at.run(timeout=300)
    _no_exception(at)
    lesson = _lesson_snapshot(at)
    assert lesson["draft"]["start_bar"] == 5 and lesson["draft"]["end_bar"] == 12
    assert lesson["draft"]["level"] == "Advanced" and lesson["draft"]["focus"] == "rhythmic_development"
    assert lesson["stage"] == 1 and lesson["checks"] == {"1": [0]} and lesson["examples"] == [1]
    assert lesson["example_nonce"] == 1 and lesson["loop_bpm"] == 80 and lesson["loop_range"] == "selection"
    phrase = [seg["concert_midi"] for seg in _get(at, EX)["segments"]]
    loop_sig = _get(at, LOOP)["signature"]

    fresh = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)  # a browser refresh
    fresh.run(timeout=300)
    _open(fresh)
    _no_exception(fresh)
    assert _lesson_snapshot(fresh) == lesson, "the whole lesson is restored"
    assert _plan_shown(fresh) and not any("couldn't be read" in t for t in _infos(fresh))
    assert [seg["concert_midi"] for seg in _get(fresh, EX)["segments"]] == phrase, "the same example idea"
    d = _get(fresh, LOOP)
    assert d["signature"] == loop_sig and d["bars"] == [5, 12] and d["bpm"] == 80
    assert d.get("resume_signal") is False, "a refresh never restarts the audio"
    assert fresh.radio(key="song_coach_level").value == "Advanced"
    assert fresh.selectbox(key="song_coach_bar_from").value == 5 and fresh.selectbox(key="song_coach_bar_to").value == 12


def test_an_instrument_change_keeps_progress_and_moves_the_written_notes(app):
    at = app
    lesson = _lesson_snapshot(at)
    concert = _get(at, EX)["segments"][0]
    loop_sig = _get(at, LOOP)["signature"]
    at.selectbox(key="instrument").set_value("Saxophone")
    at.run(timeout=300)
    at.checkbox(key="show_chart_in_instrument_key").set_value(True)
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert _lesson_snapshot(at) == lesson
    seg = _get(at, EX)["segments"][0]
    assert seg["concert_midi"] == concert["concert_midi"] and seg["key"] == "E" and seg["midi"] != concert["midi"]
    assert _get(at, LOOP)["signature"] == loop_sig, "the concert loop is unchanged"
    assert at.session_state["concert_key"] == "G"


def test_switching_song_never_borrows_and_coming_back_restores(app):
    at = app
    lesson = _lesson_snapshot(at)
    _pick(at, "Hotel California")
    _open(at)
    _no_exception(at)
    assert "Hotel California" in _get(at, CTX)["identity"]
    assert any("for a different song" in t for t in _infos(at)) and not _plan_shown(at)
    assert _get(at, EX) is None and _get(at, LOOP) is None, "no example or loop from the other song"
    assert _lesson_snapshot(at) == lesson, "looking at another song changes nothing"
    _pick(at, "Perfect")
    _open(at)
    _no_exception(at)
    assert _plan_shown(at) and _lesson_snapshot(at) == lesson


def test_a_stale_jam_never_reaches_the_next_song(app):
    at = app
    _open(at, "Entry & Jam")
    entry = at.radio(key="improv_entry_mode")
    entry.set_value([o for o in entry.options if "Style Jam" in o][0])
    at.run(timeout=300)
    _click(at, "improv_gen_style")
    assert at.session_state["improv_generated_sections"]
    _pick(at, "Hotel California")
    _open(at)
    _no_exception(at)
    ctx = _get(at, CTX)
    from music_theory import transpose_sections_dict
    from song_catalog.catalog import curated_song_records

    record = next(r for r in curated_song_records() if r["title"] == "Hotel California")
    want = transpose_sections_dict(record["sections"], record["key"], ctx["concert_key"])
    assert {name: list(bars) for name, bars in ctx["sections"]} == want, "Hotel California's own chart, not the Jam"
    _pick(at, "Perfect")
    _open(at)


def test_damaged_saved_state_recovers_with_a_message(app):
    at = app
    good = copy.deepcopy(_state(at))
    at.session_state["song_coach_session"] = {**good, "loop_bpm": 999, "examples": "x",
                                              "draft": {**good["draft"], "level": "Expert"}}
    at.run(timeout=300)
    _no_exception(at)
    assert any("Part of your saved coaching session" in t for t in _infos(at))
    assert at.slider(key="song_coach_loop_bpm").value in range(40, 221)
    assert at.radio(key="song_coach_level").value in ("Beginner", "Intermediate", "Advanced")
    assert _plan_shown(at), "the readable part of the lesson is kept"
    at.session_state["song_coach_session"] = "this is not a coaching record"
    at.run(timeout=300)
    _no_exception(at)
    assert any("couldn't be read, so coaching starts fresh" in t for t in _infos(at))
    assert not _plan_shown(at)
    at.session_state["song_coach_session"] = good  # (restore for the next test)
    at.run(timeout=300)


def test_a_custom_song_coaches_its_own_chords_and_a_key_change_clears_everything(app):
    """Custom source: the coaching, example and loop follow the Custom progression; a Practice
    Key change (a different concert chart) clears the plan, its examples and its audio together.
    (Editing a Custom chart goes through the Custom builder, which rewrites the stored
    progression; chart-content invalidation itself is covered by the fingerprint unit tests.)"""
    from tests.test_song_coach_sources_apptest import TRIAL, TRIAL_BARS_IN_E, _source
    from music_theory import transpose_sections_dict

    at = app
    at.session_state["cpl_active_progression"] = copy.deepcopy(TRIAL)
    _source(at, "Custom")
    _open(at)
    ctx = _get(at, CTX)
    assert ctx["identity"] == "custom|custom::trial-rev-1" and ctx["reason"] == ""
    assert {n: list(b) for n, b in ctx["sections"]} == transpose_sections_dict(TRIAL_BARS_IN_E, "E", ctx["concert_key"])
    _click(at, "song_coach_build")
    _click(at, "song_coach_example_toggle")
    _no_exception(at)
    assert _state(at)["loop_range"] == "challenge", "a new song's lesson starts with default preferences"
    at.radio(key="song_coach_loop_range").set_value("selection")
    at.run(timeout=300)
    loop = _get(at, LOOP)
    assert _plan_shown(at) and _get(at, EX)["available"] and loop["identity"] == ctx["identity"]
    assert loop["tokens"] == [t for n, b in ctx["sections"] for t in b][loop["bars"][0] - 1: loop["bars"][1]]
    old_key = at.session_state["concert_key"]
    new_key = "F" if old_key != "F" else "G"
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    practice_key.set_value(new_key)
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert at.session_state["concert_key"] == new_key
    assert any("Practice Key or the chord chart changed" in t for t in _infos(at))
    assert not _plan_shown(at) and _get(at, EX) is None and _get(at, LOOP) is None
    # Reads never write: the stored record keeps its old fingerprint (so every run clears it)
    # until the musician's next action, which stores a clean lesson.
    _click(at, "song_coach_build")
    state = _state(at)
    assert state["examples"] == [] and state["example_nonce"] == 0 and state["stage"] == 0
    assert state["fingerprint"] == _get(at, CTX)["fingerprint"]
    assert state["loop_range"] == "selection", "practice preferences are kept"
    assert _get(at, EX) is None, "examples stay hidden until asked for again"
    assert _get(at, LOOP)["concert_key"] == new_key
