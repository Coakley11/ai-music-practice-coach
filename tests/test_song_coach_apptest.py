"""Song-Aware Coaching S3 — real app run: Creative → Improvisation Intelligence → Song-Aware Coaching.

One booted studio (Perfect, Piano) walks through: tab visibility, plan build and challenge
navigation, progress across reruns / tab changes / a refresh, selection and bar-range changes,
alto sax projection, a Practice Key change, a song change — and checks that coaching never
mutates Backing, Missions, Motif, SBI or global practice settings.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile

import pytest

TAB = "Song-Aware Coaching"
GUARDED = (
    "display_key", "concert_key", "focus", "level", "instrument", "active_catalog_pick_key",
    "backing_track_bpm", "backing_track_scope", "backing_track_loops", "improv_song_source",
    "sbi_preview_source", "improv_entry_mode", "improv_motif", "improv_span_motif", "improv_span_mission",
    "improv_active_mission", "improv_mission_pick", "ii_selected_chord", "ii_selected_section",
    "harmony_map_section", "harmony_map_chord", "practice_focus_section",
)


def require_isolated_data_dir(data_dir: str) -> None:
    """The app fixes its data folder when ``suite_workspace`` is first imported. If an earlier
    test in this process imported it, this app would run against the worktree's own data
    folder instead of ``data_dir`` — so the module must run in its own pytest process."""
    import pathlib
    import sys

    mod = sys.modules.get("suite_workspace")
    if mod is not None and pathlib.Path(mod.DATA_DIR).resolve() != pathlib.Path(data_dir).resolve():
        pytest.skip("run this real-app module in its own pytest process: the app's data folder was "
                    "already fixed by an earlier import, so isolation to a temp folder cannot be guaranteed")


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_apptest_")
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
        at.data_dir = data_dir
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
    at.run(timeout=300)


def _open(at, needle=TAB):
    if at.session_state["studio_page"] != "creative":
        _click(at, "studio_quick_nav_btn_creative")
    try:
        at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
        at.run(timeout=300)
    except Exception:
        pass
    options = at.radio(key="improv_intelligence_tab").options
    at.radio(key="improv_intelligence_tab").set_value([o for o in options if needle in o][0])
    at.run(timeout=300)


def _state(at):
    return at.session_state["song_coach_session"] if "song_coach_session" in at.session_state else None


def _texts(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]


def _header(at):
    return next((t for t in _texts(at) if "data-song-coach-concert-key" in t), "")


def _card_title(at):
    return next((m.value for m in at.markdown if m.value.startswith("### ") and m.value[4:5].isdigit()), "")


def _guarded(at):
    out = {}
    for key in GUARDED:
        if key in at.session_state:
            out[key] = copy.deepcopy(at.session_state[key])
    return out


def _assert_unchanged(before, after):
    """Values of guarded keys never change. (Streamlit drops widget state for widgets that are
    not on screen — e.g. Entry & Jam's mode radio while another tab is open — so a key may be
    absent; it is restored when its page renders, which test_progress_survives_... checks.)"""
    changed = {k: (before[k], after[k]) for k in before.keys() & after.keys() if before[k] != after[k]}
    assert not changed, f"coaching changed global / Backing / Missions / Motif / SBI state: {changed}"


def _no_exception(at):
    assert not at.exception, [str(getattr(e, "value", e))[:800] for e in at.exception]


def test_tab_is_listed_after_missions_and_renders(app):
    at = app
    _open(at)
    _no_exception(at)
    names = [o.split(" ", 1)[1] for o in at.radio(key="improv_intelligence_tab").options]
    assert names.index(TAB) == names.index("Missions") + 1
    header = _header(at)
    assert "Perfect" in header and "Practice Key G (concert)" in header and "Verified chord chart" in header
    assert at.selectbox(key="song_coach_section").value == "verse-1"
    assert (at.selectbox(key="song_coach_bar_from").value, at.selectbox(key="song_coach_bar_to").value) == (1, 8)
    assert at.radio(key="song_coach_level").value == at.session_state["level"]
    assert _state(at) is None, "opening the tab must not write coaching state"


def test_build_navigate_and_self_check_without_side_effects(app):
    at = app
    before = _guarded(at)
    _click(at, "song_coach_build")
    _no_exception(at)
    state = _state(at)
    assert state["plan_id"] and state["stage"] == 0
    assert _card_title(at).startswith("### 1. ")
    assert any(t.startswith("#### Your plan · Verse · bars 1–8") for t in _texts(at))
    _click(at, "song_coach_next")
    _click(at, "song_coach_next")
    assert _state(at)["stage"] == 2 and _card_title(at).startswith("### 3. ")
    _click(at, "song_coach_prev")
    assert _state(at)["stage"] == 1
    check = next(c for c in at.checkbox if str(c.key).startswith(f"song_coach_check_{state['plan_id']}_1_"))
    check.check()
    at.run(timeout=300)
    assert _state(at)["checks"] == {"1": [0]}
    _assert_unchanged(before, _guarded(at))


def test_progress_survives_reruns_and_tab_changes(app):
    at = app
    before = _guarded(at)
    at.run(timeout=300)
    assert _state(at)["stage"] == 1 and _card_title(at).startswith("### 2. ")
    _assert_unchanged(before, _guarded(at))  # a rerun on the coaching tab changes nothing else
    # Other tabs keep their own behaviour (e.g. Live Coach / Missions select a chord); coaching
    # progress and Entry & Jam's mode survive the tour.
    _open(at, "Live Coach")
    _open(at, "Missions")
    _open(at, "Entry & Jam")
    assert at.session_state["improv_entry_mode"] == "Song-Based Improvisation"
    _open(at)
    _no_exception(at)
    assert _state(at)["stage"] == 1 and _state(at)["checks"] == {"1": [0]}
    assert _card_title(at).startswith("### 2. ")


def test_selection_changes_keep_the_plan_until_rebuilt(app):
    at = app
    plan_id = _state(at)["plan_id"]
    at.radio(key="song_coach_level").set_value("Advanced")
    at.run(timeout=300)
    state = _state(at)
    assert state["draft"]["level"] == "Advanced" and state["plan_id"] == plan_id
    assert any("Press **Build My Coaching Plan** to update" in t for t in _texts(at))
    at.selectbox(key="song_coach_bar_to").set_value(16)
    at.run(timeout=300)
    at.selectbox(key="song_coach_bar_from").set_value(9)
    at.run(timeout=300)
    assert (_state(at)["draft"]["start_bar"], _state(at)["draft"]["end_bar"]) == (9, 16)
    _click(at, "song_coach_build")
    state = _state(at)
    assert state["plan_id"] != plan_id and state["stage"] == 0
    assert state["built"] == {**state["built"], "start_bar": 9, "end_bar": 16, "level": "Advanced"}
    assert any(t.startswith("#### Your plan · Verse · bars 9–16") for t in _texts(at))
    at.selectbox(key="song_coach_section").set_value("chorus-1")
    at.run(timeout=300)
    assert _state(at)["draft"]["section_id"] == "chorus-1"
    assert (at.selectbox(key="song_coach_bar_from").value, at.selectbox(key="song_coach_bar_to").value) == (1, 8)


def test_alto_sax_projects_written_names_without_touching_the_plan(app):
    at = app
    _click(at, "song_coach_next")
    before = _state(at)
    concert_text = [m.value for m in at.markdown if m.value.startswith("- ")]
    at.selectbox(key="instrument").set_value("Saxophone")
    at.run(timeout=300)
    at.checkbox(key="show_chart_in_instrument_key").set_value(True)
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    after = _state(at)
    assert after["plan_id"] == before["plan_id"] and after["stage"] == before["stage"]
    assert at.session_state["concert_key"] == "G"
    header = _header(at)
    assert "Practice Key G (concert)" in header and "Written key E" in header and "Alto Saxophone" in header
    written_text = [m.value for m in at.markdown if m.value.startswith("- ")]
    assert written_text != concert_text
    assert any("C#m7" in t or "Aadd9" in t or "B/D#" in t for t in written_text + _texts(at))


def test_practice_key_change_invalidates_the_plan(app):
    at = app
    draft = _state(at)["draft"]
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    practice_key.set_value("A")
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert at.session_state["concert_key"] == "A"
    assert any("Practice Key or the chord chart changed" in i.value for i in at.info)
    assert not any(t.startswith("#### Your plan") for t in _texts(at))
    assert "Practice Key A (concert)" in _header(at)
    _click(at, "song_coach_build")
    state = _state(at)
    assert state["draft"]["section_id"] == draft["section_id"] and state["stage"] == 0
    assert any(t.startswith("#### Your plan") for t in _texts(at))


def test_refresh_restores_the_coaching_session(app):
    from streamlit.testing.v1 import AppTest

    at = app
    _click(at, "song_coach_next")
    saved = _state(at)
    fresh = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
    fresh.run(timeout=300)
    _no_exception(fresh)
    assert fresh.session_state["studio_page"] == "creative"
    assert fresh.session_state["improv_intelligence_tab"] == TAB
    restored = _state(fresh)
    assert restored is not None and restored["plan_id"] == saved["plan_id"] and restored["stage"] == saved["stage"]
    assert _card_title(fresh).startswith(f"### {saved['stage'] + 1}. ")


def test_song_change_never_shows_the_previous_songs_plan(app):
    at = app
    stored = _state(at)
    _click(at, "studio_quick_nav_btn_picker")
    dropdown = at.selectbox(key="matching_song_dropdown")
    dropdown.set_value([o for o in dropdown.options if "Ipanema" in o][0])
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    header = _header(at)
    assert "The Girl from Ipanema" in header and "Simplified practice chart" in header
    assert any("for a different song" in i.value for i in at.info)
    assert not any(t.startswith("#### Your plan") for t in _texts(at))
    assert _state(at) == stored, "navigation alone must not rewrite coaching state"
    _click(at, "song_coach_build")
    assert "Ipanema" in _state(at)["identity"]
