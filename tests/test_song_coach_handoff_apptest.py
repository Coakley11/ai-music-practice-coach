"""Song-Aware Coaching S7 — Continue in Song-Based Improvisation, and back, in the real app.

Catalog (Perfect), Custom (a saved progression) and Composition (the starter) each go
coaching → Song-Based Improvisation → coaching. Every handoff must keep the authoritative song
and its lane, the Practice Key and the instrument; never start playback; leave the lesson as it
was (plus a note of where the musician was); and come back through Back or the tab with a brief
welcome. A stale Custom preview, a stale Jam, an earlier Creative tab, a Practice Key change
while away and a forged handoff record are covered too.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile

import pytest

from tests.test_song_coach_apptest import _click, _no_exception, _open, _state, require_isolated_data_dir

LOOP = "_song_coach_loop_diag"
CTX = "_song_coach_ctx_diag"
WELCOME = "Welcome back"
GLOBALS = ("concert_key", "display_key", "instrument", "active_music_source", "active_catalog_pick_key",
           "show_chart_in_instrument_key", "selected_transposing_instrument")
TRANSPORT = ("backing_transport_status", "_backing_autoplay", "_backing_play_request", "_backing_play_session")


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_handoff_apptest_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        require_isolated_data_dir(data_dir)
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
        at.run(timeout=300)
        _pick(at, "Perfect")
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


def _get(at, key, default=None):
    return at.session_state[key] if key in at.session_state else default


def _globals(at) -> dict:
    return {k: copy.deepcopy(_get(at, k)) for k in GLOBALS}


def _lesson(at) -> dict:
    s = _state(at)
    return {k: copy.deepcopy(s[k]) for k in ("identity", "fingerprint", "draft", "built", "plan_id", "stage", "checks",
                                             "examples", "example_nonce", "loop_bpm", "loop_range")}


def _texts(at) -> list[str]:
    return [m.value for m in at.markdown] + [s.value for s in at.success] + [i.value for i in at.info]


def _back_destinations(at) -> list[str]:
    from studio_nav_history import NAV_BACK_STACK, history_destination_id

    return [history_destination_id(entry=e) for e in (_get(at, NAV_BACK_STACK) or [])]


def _back(at):
    btn = next(b for b in at.button if str(b.key) == "studio_nav_back_btn")
    assert not btn.disabled
    btn.click()
    at.run(timeout=300)


def _start_lesson(at):
    _click(at, "song_coach_build")
    _click(at, "song_coach_next")
    checks = [c for c in at.checkbox if str(c.key).startswith("song_coach_check_")]
    checks[0].check()
    at.run(timeout=300)
    _no_exception(at)


def _transport(at) -> dict:
    return {k: copy.deepcopy(_get(at, k)) for k in TRANSPORT}


def _continue(at):
    assert any(c.value.startswith("Song-Based Improvisation will open the full song.") for c in at.caption)
    at._transport_before = _transport(at)
    _click(at, "song_coach_continue_sbi")
    _no_exception(at)


def _assert_in_song_based(at, lane):
    assert _get(at, "improv_intelligence_tab") == "Entry & Jam"
    assert _get(at, "improv_entry_mode") == "Song-Based Improvisation"
    assert _get(at, "improv_song_source") == lane
    assert not any(str(b.key) == "song_coach_continue_sbi" for b in at.button), "coaching is no longer on screen"
    assert _get(at, "backing_transport_status") != "playing" and not _get(at, "_backing_play_request")
    assert _transport(at) == at._transport_before, "the handoff changes no Backing transport state"


def _assert_back_in_coaching(at, lesson):
    assert _get(at, "improv_intelligence_tab") == "Song-Aware Coaching"
    assert any(t.startswith("#### Your plan") for t in _texts(at))
    assert _lesson(at) == lesson, "the same lesson and progress"
    h = _state(at)["handoff"]
    welcome = [t for t in _texts(at) if t.startswith(WELCOME)]
    bars = f"bars {h['start_bar']}–{h['end_bar']}" if h["start_bar"] != h["end_bar"] else f"bar {h['start_bar']}"
    assert welcome and bars in welcome[0], welcome
    assert (_get(at, LOOP) or {}).get("resume_signal") is False, "the loop does not start by itself"
    at.run(timeout=300)
    assert not any(t.startswith(WELCOME) for t in _texts(at)), "the welcome is brief (once)"


def test_catalog_with_a_stale_custom_preview_and_jam_from_another_tab(app):
    at = app
    # Stale state first: a Style Jam, then a Custom preview lane in Song-Based Improvisation.
    _open(at, "Entry & Jam")
    entry = at.radio(key="improv_entry_mode")
    entry.set_value([o for o in entry.options if "Style Jam" in o][0])
    at.run(timeout=300)
    _click(at, "improv_gen_style")
    at.radio(key="improv_entry_mode").set_value("Song-Based Improvisation")
    at.run(timeout=300)
    source = at.radio(key="improv_song_source")
    if "Custom progression" in source.options:
        source.set_value("Custom progression")
        at.run(timeout=300)
    _no_exception(at)
    _open(at, "Missions")  # arrive at coaching from another Creative tab
    _open(at)
    _no_exception(at)
    ctx = _get(at, CTX)
    assert ctx["identity"].startswith("catalog|") and "Perfect" in ctx["identity"] and ctx["reason"] == ""
    _start_lesson(at)
    lesson, before = _lesson(at), _globals(at)
    _continue(at)
    _assert_in_song_based(at, "Active song")
    assert _globals(at) == before, "Practice Key, instrument and song unchanged"
    h = _state(at)["handoff"]
    assert (h["identity"], h["concert_key"], h["plan_id"]) == (ctx["identity"], ctx["concert_key"], lesson["plan_id"])
    assert (h["start_bar"], h["end_bar"]) == (lesson["built"]["start_bar"], lesson["built"]["end_bar"])
    assert _lesson(at) == lesson, "the lesson is untouched by the handoff"
    assert _back_destinations(at)[-1] == "creative::Song-Aware Coaching"
    at.run(timeout=300)  # a rerun on Song-Based Improvisation
    assert _globals(at) == before and _get(at, "improv_song_source") == "Active song"
    _back(at)
    _no_exception(at)
    _assert_back_in_coaching(at, lesson)
    assert _globals(at) == before


def test_the_coaching_tab_also_returns(app):
    at = app
    lesson = _lesson(at)
    _continue(at)
    _assert_in_song_based(at, "Active song")
    _open(at)  # the tab, not Back
    _no_exception(at)
    _assert_back_in_coaching(at, lesson)


def test_a_key_change_while_away_never_restores_stale_coaching(app):
    at = app
    _continue(at)
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    old = at.session_state["concert_key"]
    practice_key.set_value("A" if old != "A" else "G")
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert any("Practice Key or the chord chart changed" in t for t in _texts(at))
    assert not any(t.startswith("#### Your plan") for t in _texts(at))
    assert not any(t.startswith(WELCOME) for t in _texts(at))
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    practice_key.set_value(old)
    at.run(timeout=300)
    _open(at)


def test_a_forged_handoff_is_ignored(app):
    at = app
    _click(at, "song_coach_build")
    good = copy.deepcopy(_state(at))
    at.session_state["song_coach_session"] = {**good, "handoff": {**dict(good.get("handoff") or {}), "identity": good["identity"],
                                                                   "fingerprint": good["fingerprint"], "concert_key": "Z",
                                                                   "plan_id": good["plan_id"], "section_id": "x",
                                                                   "start_bar": 1, "end_bar": 2, "at": "forged"}}
    at.run(timeout=300)
    _no_exception(at)
    assert not any(t.startswith(WELCOME) for t in _texts(at)), "a handoff that doesn't match is never welcomed back"
    assert any(t.startswith("#### Your plan") for t in _texts(at))


def test_custom_progression_handoff(app):
    from tests.test_song_coach_sources_apptest import TRIAL, _source

    at = app
    at.session_state["cpl_active_progression"] = copy.deepcopy(TRIAL)
    _source(at, "Custom")
    _open(at)
    _no_exception(at)
    ctx = _get(at, CTX)
    assert ctx["identity"] == "custom|custom::trial-rev-1" and ctx["reason"] == ""
    _start_lesson(at)
    lesson, before = _lesson(at), _globals(at)
    _continue(at)
    _assert_in_song_based(at, "Custom progression")
    assert _globals(at) == before, f"Custom: Practice Key and instrument unchanged ({before} -> {_globals(at)})"
    assert (_get(at, "cpl_active_progression") or {}).get("id") == "trial-rev-1", "the same Custom progression"
    at.run(timeout=300)
    assert _globals(at) == before, "still unchanged after Song-Based Improvisation renders again"
    _back(at)
    _no_exception(at)
    assert _get(at, CTX)["identity"] == ctx["identity"]
    _assert_back_in_coaching(at, lesson)
    assert _globals(at) == before


def test_composition_handoff(app):
    from tests.test_song_coach_sources_apptest import _source

    at = app
    _source(at, "Composition")
    _open(at)
    _no_exception(at)
    ctx = _get(at, CTX)
    assert ctx["identity"].startswith("composition|") and ctx["reason"] == ""
    _start_lesson(at)
    lesson, before = _lesson(at), _globals(at)
    _continue(at)
    _assert_in_song_based(at, "Composition")
    assert _globals(at) == before
    at.run(timeout=300)
    assert _globals(at) == before
    _back(at)
    _no_exception(at)
    assert _get(at, CTX)["identity"] == ctx["identity"]
    _assert_back_in_coaching(at, lesson)


def _autoplaying_audio(at) -> list:
    return [a for a in at.get("audio") if bool(getattr(a.proto, "autoplay", False))]


def test_an_existing_backing_autoplay_preference_never_plays(app):
    """Backing Studio's autoplay preference is already on: the handoff starts nothing, SBI
    plays nothing by itself, the return does not restart the loop, and the preference is kept."""
    from tests.test_song_coach_sources_apptest import _source

    at = app
    _source(at, "catalog")
    _pick(at, "Perfect")
    _open(at)
    _click(at, "song_coach_build")
    at.session_state["_backing_autoplay"] = True  # as left by Backing Studio
    meta = dict(_get(at, "backing_track_state") or {})
    meta["backing_autoplay"] = True
    at.session_state["backing_track_state"] = meta
    at.run(timeout=300)
    _no_exception(at)
    assert _get(at, "_backing_autoplay") is True
    _continue(at)
    _assert_in_song_based(at, "Active song")
    assert not _autoplaying_audio(at), "no autoplaying audio on Song-Based Improvisation"
    at.run(timeout=300)  # SBI renders again with the preference still on
    assert not _autoplaying_audio(at) and _get(at, "backing_transport_status") != "playing"
    assert not _get(at, "_backing_play_request")
    assert _get(at, "_backing_autoplay") is True, "the Backing preference is not overwritten"
    _back(at)
    _no_exception(at)
    assert _get(at, "improv_intelligence_tab") == "Song-Aware Coaching"
    assert (_get(at, LOOP) or {}).get("resume_signal") is False, "the coaching loop does not restart"
    assert not _autoplaying_audio(at)
    assert _get(at, "_backing_autoplay") is True
    assert (_get(at, "backing_track_state") or {}).get("backing_autoplay") is True, "the saved preference is kept"
