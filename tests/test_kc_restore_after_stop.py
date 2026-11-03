"""A refreshed page must not restore a stopped key cycle as a paused session.

Stop ends the playback session. Before this fix the browser restore always
re-created a paused session from a held cycle, so the card offered "Stop" with
nothing playing and no take for the lead sheet. A refresh during playback or
while paused still restores the paused session at that key.
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import tempfile
from pathlib import Path

from backing_key_cycle import (
    BACKING_KEY_CYCLE_SESSIONS_KEY,
    CYCLE_SESSION_OVER,
    STATUS_HELD,
    advance_key_cycle_now,
    arm_key_cycle_for_explicit_play,
    get_owner_cycle_session,
    normalize_key_cycle_after_browser_restore,
    pause_key_cycle,
    resume_key_cycle,
    rewind_key_cycle_to_first_key,
    start_key_cycle,
    temporary_playback_key,
)
from backing_transport_intent import (
    PAUSED,
    STOPPED,
    begin_playback,
    stop_playback,
    transport_intent,
)

SHAPE_PICK = "Pop|Shape of You"


def _session(**extra):
    session = {
        "studio_page": "backing",
        "active_catalog_pick_key": SHAPE_PICK,
        "display_key": "Bm",
        "concert_key": "Bm",
        "practice_key_by_source": {SHAPE_PICK: "Bm"},
        "_backing_explicit_handoff_source": "regular_song",
        "backing_key_cycle_step": "semitone",
        "backing_key_cycle_direction": "up",
    }
    session.update(extra)
    return session


def _play(session) -> None:
    """Card Play with cycling On, as the app applies it."""
    begin_playback(session, reason="card_play")
    arm_key_cycle_for_explicit_play(session)


def _stop(session) -> None:
    """Card Stop: the transport ends and the cycle rewinds to its first key."""
    stop_playback(session, reason="card_stop")
    rewind_key_cycle_to_first_key(session)


def _fresh(session):
    """A new browser session: only what is saved (the cycle bag) comes back."""
    return {
        "studio_page": "backing",
        "active_catalog_pick_key": SHAPE_PICK,
        "practice_key_by_source": dict(session["practice_key_by_source"]),
        BACKING_KEY_CYCLE_SESSIONS_KEY: copy.deepcopy(session[BACKING_KEY_CYCLE_SESSIONS_KEY]),
        "backing_key_cycle_enabled": True,
    }


def test_restore_after_stop_is_stopped_not_paused() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)
    advance_key_cycle_now(s)
    _stop(s)
    fresh = _fresh(s)
    assert normalize_key_cycle_after_browser_restore(fresh)
    assert transport_intent(fresh) == STOPPED
    data = get_owner_cycle_session(fresh)
    assert data["status"] == STATUS_HELD and data["enabled"]
    # Cycling stays On at the first key; the next Play starts a new cycle there.
    assert temporary_playback_key(fresh) == "Bm"
    assert not fresh.get("_kc_refresh_resume_from_start")
    assert fresh["practice_key_by_source"][SHAPE_PICK] == "Bm"


def test_restore_after_turning_cycling_on_while_stopped_is_stopped() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")  # On, never played
    fresh = _fresh(s)
    assert normalize_key_cycle_after_browser_restore(fresh)
    assert transport_intent(fresh) == STOPPED


def test_restore_during_playback_is_still_a_paused_session_at_that_key() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)
    advance_key_cycle_now(s)
    cur = temporary_playback_key(s)
    fresh = _fresh(s)  # the tab closed while playing
    assert normalize_key_cycle_after_browser_restore(fresh)
    assert transport_intent(fresh) == PAUSED
    assert temporary_playback_key(fresh) == cur
    assert fresh.get("_kc_refresh_resume_from_start")


def test_restore_while_paused_is_still_a_paused_session() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)
    pause_key_cycle(s)
    fresh = _fresh(s)
    assert normalize_key_cycle_after_browser_restore(fresh)
    assert transport_intent(fresh) == PAUSED


def test_play_after_stop_clears_the_marker_so_a_later_refresh_restores_paused() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)
    _stop(s)
    assert get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)
    _play(s)
    assert not get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)
    fresh = _fresh(s)
    assert normalize_key_cycle_after_browser_restore(fresh)
    assert transport_intent(fresh) == PAUSED


def test_resume_and_next_clear_the_marker() -> None:
    s = _session()
    start_key_cycle(s, start_key="Bm")
    assert get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)
    resume_key_cycle(s)
    assert not get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)
    _stop(s)
    assert get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)
    advance_key_cycle_now(s)  # manual Next continues playback
    assert not get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)


def test_turning_cycling_on_during_playback_keeps_the_session() -> None:
    s = _session()
    begin_playback(s, reason="card_play")
    start_key_cycle(s, start_key="Bm")
    assert not get_owner_cycle_session(s).get(CYCLE_SESSION_OVER)


@contextlib.contextmanager
def _workspace_dir():
    """A temporary data dir holding one workspace save file; yields that file."""
    import suite_user_persistence as sup
    import suite_workspace as sw

    with tempfile.TemporaryDirectory() as td:
        old_sw, old_sup = sw.DATA_DIR, getattr(sup, "DATA_DIR", None)
        old_env = os.environ.get("MUSIC_APP_DATA_DIR")
        try:
            sw.DATA_DIR = Path(td)
            if old_sup is not None:
                sup.DATA_DIR = Path(td)
            os.environ["MUSIC_APP_DATA_DIR"] = td
            ws = Path(td) / "workspaces" / "daniel"
            ws.mkdir(parents=True, exist_ok=True)
            seed = {"version": 1, "app": "music", "state": {"session": {"practice_key_by_source": {SHAPE_PICK: "Bm"}}}}
            path = ws / "music_user_state.json"
            path.write_text(json.dumps(seed), encoding="utf-8")
            yield path
        finally:
            sw.DATA_DIR = old_sw
            if old_sup is not None:
                sup.DATA_DIR = old_sup
            if old_env is None:
                os.environ.pop("MUSIC_APP_DATA_DIR", None)
            else:
                os.environ["MUSIC_APP_DATA_DIR"] = old_env


def _disk_bag(path):
    disk = json.loads(path.read_text(encoding="utf-8"))
    return disk["state"]["session"][BACKING_KEY_CYCLE_SESSIONS_KEY]


def _restored_from(bag):
    fresh = _session()
    fresh[BACKING_KEY_CYCLE_SESSIONS_KEY] = copy.deepcopy(bag)
    fresh["backing_key_cycle_enabled"] = True
    assert normalize_key_cycle_after_browser_restore(fresh)
    return fresh


def test_saved_stop_marker_survives_the_disk_merge() -> None:
    from backing_key_cycle import persist_key_cycle_position

    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)
    advance_key_cycle_now(s)
    with _workspace_dir() as path:
        assert persist_key_cycle_position(s)  # saved mid-cycle
        _stop(s)  # Stop writes the save itself
        bag = _disk_bag(path)
        assert bag["catalog"].get(CYCLE_SESSION_OVER) is True
        assert transport_intent(_restored_from(bag)) == STOPPED


def test_a_stale_write_cannot_bring_back_the_stopped_session() -> None:
    """Stop at the first key moves nothing; the marker alone must win the merge."""
    from backing_key_cycle import persist_key_cycle_position

    s = _session()
    start_key_cycle(s, start_key="Bm")
    _play(s)  # playing the first key
    with _workspace_dir() as path:
        assert persist_key_cycle_position(s)
        stale = copy.deepcopy(s)  # e.g. a deferred autosave from before Stop
        _stop(s)
        assert persist_key_cycle_position(stale)
        bag = _disk_bag(path)
        assert bag["catalog"].get(CYCLE_SESSION_OVER) is True
        assert transport_intent(_restored_from(bag)) == STOPPED


def test_stop_and_restore_keep_the_cycle_settings() -> None:
    s = _session(backing_key_cycle_step="whole", backing_key_cycle_direction="down")
    start_key_cycle(s, start_key="Bm")
    before = get_owner_cycle_session(s)
    _play(s)
    advance_key_cycle_now(s)
    _stop(s)
    fresh = _restored_from(s[BACKING_KEY_CYCLE_SESSIONS_KEY])
    data = get_owner_cycle_session(fresh)
    assert data["enabled"] is True
    assert data["interval"] == before["interval"] == 2
    assert data["direction"] == before["direction"] == "down"
    assert data.get("spelling_prefs") == before.get("spelling_prefs")
    assert data.get("start_cycle_key") == before.get("start_cycle_key")
    assert s["backing_key_cycle_step"] == "whole" and s["backing_key_cycle_direction"] == "down"
    assert fresh["practice_key_by_source"][SHAPE_PICK] == "Bm"
