"""Song-Aware Coaching S5 — the practice loop in the real app (Perfect, 6/8, Practice Key G).

The player follows the active challenge's bars, keeps the same loop across reruns, tab
changes and challenges that loop the same bars, re-renders for a tempo or range change, is
cleared with the plan when the Practice Key changes, and never writes anything outside the
coaching record.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from tests.test_song_coach_apptest import _click, _no_exception, _open, _state, require_isolated_data_dir

DIAG = "_song_coach_loop_diag"
# Session keys a coaching loop must never change (prefixes): Backing, Key Cycling, keys,
# focus, instrument, source, Missions, Motif, SBI.
FORBIDDEN_PREFIXES = (
    "backing", "_backing", "kc", "_kc", "concert_key", "display_key", "practice_key", "focus", "level",
    "instrument", "selected_transposing", "show_chart_in_instrument_key", "active_", "selected_song",
    "improv_", "ii_", "harmony_map", "mission", "_mission", "sbi", "_sbi", "practice_focus", "key_cycle",
)


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_loop_apptest_")
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


def _players(at):
    return [e for e in at.get("iframe") if "data-song-coach-loop" in str(getattr(e.proto, "srcdoc", ""))]


def _snapshot(at) -> dict:
    out = {}
    for key in at.session_state.filtered_state:
        if key.startswith(FORBIDDEN_PREFIXES):
            try:
                out[key] = repr(at.session_state[key])
            except Exception:
                pass
    return out


# Bookkeeping, not settings: the Creative save path stamps this whenever any coaching choice is
# saved (as since S3). Keys that change on a plain rerun (run counters) are measured per test.
SAVE_STAMPS = {"improv_mission_workspace_updated_at"}


def _volatile(at) -> set:
    """Keys under the guarded prefixes that change on a plain rerun with no user action."""
    a = _snapshot(at)
    at.run(timeout=300)
    b = _snapshot(at)
    return {k for k in a.keys() & b.keys() if a[k] != b[k]} | SAVE_STAMPS


def _assert_isolated(before: dict, after: dict, volatile: set) -> None:
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k] and k not in volatile)
    assert not changed, f"the practice loop changed global / Backing / Key Cycling state: {changed}"


def test_player_plays_the_challenge_bars(app):
    at = app
    _no_exception(at)
    d = _diag(at)
    assert d and d["refusal"] == ""
    assert d["meter"] == "6/8" and d["concert_key"] == "G" and d["identity"].startswith("catalog|")
    assert d["style"] == "Ballad", "Perfect's own catalog groove, as Backing Studio's Auto"
    assert d["bpm"] == at.session_state["song_coach_loop_bpm"]
    assert d["tokens"] and all(t for t in d["tokens"])
    assert abs(d["seconds"] - d["bar_seconds"] * (d["bars"][1] - d["bars"][0] + 1)) < 1e-3
    players = _players(at)
    assert len(players) == 1 and d["signature"] in players[0].proto.srcdoc
    assert "<audio" not in players[0].proto.srcdoc
    assert any("Practice loop" in m.value for m in at.markdown)


def test_challenges_with_the_same_bars_keep_the_same_loop(app):
    at = app
    volatile = _volatile(at)
    before = _snapshot(at)
    seen = {}
    for _ in range(8):
        d = _diag(at)
        key = tuple(d["bars"])
        doc = _players(at)[0].proto.srcdoc
        bars = f"Bar {key[0]}" if key[0] == key[1] else f"Bars {key[0]}–{key[1]}"
        assert d["scope"] == "challenge" and "Looping this challenge&#x27;s bars" in doc and bars in doc
        if key in seen:
            assert seen[key] == d["signature"], "same bars, same loop (the player keeps playing)"
        seen[key] = d["signature"]
        nxt = next((b for b in at.button if str(b.key) == "song_coach_next"), None)
        if nxt is None or nxt.disabled:
            break
        _click(at, "song_coach_next")
        _no_exception(at)
    assert len(set(seen.values())) == len(seen), "different bars, a different loop"
    _assert_isolated(before, _snapshot(at), volatile)
    while not next(b for b in at.button if str(b.key) == "song_coach_prev").disabled:
        _click(at, "song_coach_prev")


def test_reruns_and_tab_switches_keep_the_loop(app):
    at = app
    sig = _diag(at)["signature"]
    at.run(timeout=300)
    assert _diag(at)["signature"] == sig
    _open(at, "Missions")
    assert not _players(at), "no player outside the coaching tab"
    _open(at)
    _no_exception(at)
    assert _diag(at)["signature"] == sig


def test_tempo_and_range_changes_make_a_new_loop_without_touching_globals(app):
    at = app
    volatile = _volatile(at)
    before = _snapshot(at)
    d0 = _diag(at)
    song_bpm = d0["bpm"]
    at.slider(key="song_coach_loop_bpm").set_value(song_bpm - 13)
    at.run(timeout=300)
    _no_exception(at)
    d1 = _diag(at)
    assert d1["bpm"] == song_bpm - 13 and d1["signature"] != d0["signature"] and d1["range_key"] == d0["range_key"]
    assert _state(at)["loop_bpm"] == song_bpm - 13
    at.radio(key="song_coach_loop_range").set_value("selection")
    at.run(timeout=300)
    d2 = _diag(at)
    state = _state(at)
    assert state["loop_range"] == "selection"
    assert d2["bars"] == [state["built"]["start_bar"], state["built"]["end_bar"]]
    assert d2["range_key"] != d1["range_key"] or d1["bars"] == d2["bars"]
    assert d2["scope"] == "selection" and "Looping the whole selection" in _players(at)[0].proto.srcdoc
    at.slider(key="song_coach_loop_bpm").set_value(song_bpm)
    at.run(timeout=300)
    assert _state(at)["loop_bpm"] == 0, "the song's own tempo is stored as 'song tempo'"
    _assert_isolated(before, _snapshot(at), volatile)
    assert at.session_state["_song_coach_last_commit"]["interaction"] == "loop_tempo"


def test_practice_key_change_clears_the_stale_loop(app):
    at = app
    old = _diag(at)
    practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
    practice_key.set_value("A")
    at.run(timeout=300)
    _open(at)
    _no_exception(at)
    assert _diag(at) is None and not _players(at), "the plan (and its loop) is cleared"
    _click(at, "song_coach_build")
    d = _diag(at)
    assert d["concert_key"] == "A" and d["signature"] != old["signature"]
    assert _state(at)["loop_range"] == "selection", "loop preferences survive a rebuild"
