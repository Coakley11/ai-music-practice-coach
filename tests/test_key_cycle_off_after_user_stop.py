"""A genuine Key Cycling Off after the user's Stop is honoured, even before the player proved it started.

The stray-Off guard swallows Off snaps from remount churn while Key Cycling arms; the player's
``play_started`` proof clears it. With a slow first render (16 s with the recorded kit in the real-app
trace, longer than the guard's 10 s window) a user who pressed Stop first and then switched Key Cycling Off
had the Off turned back On: Key Cycling stayed on, the saved Practice Key did not come back, and the next
Play rendered a new take in a cycled key. An explicit Stop now ends the start-up phase and disarms the guard.
"""
from __future__ import annotations

import inspect
import pathlib

import backing_key_cycle as kc
from backing_key_cycle import (
    disarm_spurious_off_on_user_stop,
    get_owner_cycle_session,
    is_cycle_active,
    render_backing_key_cycle_controls,
    temporary_playback_key,
)
from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session

MODE = "backing_key_cycle_enabled_ui"
RUNS = "_kc_suppress_spurious_cycle_off_runs"
FLAG = "_kc_suppress_spurious_cycle_off"
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _turn_on(session: dict) -> None:
    session["_kc_cycle_user_toggled"] = True
    render_backing_key_cycle_controls(_ControlsSt(session, cycling="On"), session)
    assert is_cycle_active(session)


def _off_click(session: dict) -> None:
    """The radio set to Off with its on_change mark: a user click and a remount snap look the same."""
    session[MODE] = "Off"
    session["_kc_cycle_user_toggled"] = True
    render_backing_key_cycle_controls(_ControlsSt(session, cycling="Off"), session)


def test_off_after_stop_before_play_started_is_honoured_and_the_saved_key_returns() -> None:
    session = _session()
    base = kc.current_backing_owner_practice_key(session)
    _turn_on(session)
    kc.advance_key_cycle_now(session) if hasattr(kc, "advance_key_cycle_now") else None
    assert session.get(FLAG) and int(session.get(RUNS) or 0) >= 12  # armed, no play_started yet

    assert disarm_spurious_off_on_user_stop(session) is True  # the user's Stop
    _off_click(session)  # the user's single Off click

    assert not is_cycle_active(session)
    assert session.get(MODE) == "Off"
    assert session.get("backing_key_cycle_enabled") is False
    data = get_owner_cycle_session(session) or {}
    assert str(data.get("current_playback_key") or "") == str(data.get("base_practice_key") or base)
    # With the cycle off the audio key is the Practice Key again: same signature, so the next Play reuses
    # the take it had before cycling (the app only substitutes a cycle key while the cycle is active).
    assert temporary_playback_key(session) == ""
    assert kc.current_backing_owner_practice_key(session) == base


def test_without_a_stop_the_enable_storm_is_still_swallowed() -> None:
    session = _session()
    _turn_on(session)
    for i in range(8):
        _off_click(session)  # remount snaps right after enable
        assert is_cycle_active(session), f"collapsed on remount {i}"
        assert session.get(MODE) == "On"


def test_disarm_on_stop_is_harmless_when_nothing_is_armed() -> None:
    session = _session()
    assert disarm_spurious_off_on_user_stop(session) is False
    _turn_on(session)
    assert disarm_spurious_off_on_user_stop(session) is True
    assert not session.get(FLAG) and not session.get(RUNS) and "_kc_suppress_armed_at" not in session


def test_only_the_explicit_user_stop_disarms_it() -> None:
    app = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    stop = app[app.index("def _stop_backing_playback("):]
    stop = stop[:stop.index("\ndef ")]
    assert "disarm_spurious_off_on_user_stop(st.session_state)" in stop
    assert app.count("disarm_spurious_off_on_user_stop(") == 1
    src = inspect.getsource(kc)
    # Key Cycling's own stop, Pause and reprojects keep the guard: the call lives only in the app's Stop.
    assert src.count("disarm_spurious_off_on_user_stop(") == 1  # its definition
