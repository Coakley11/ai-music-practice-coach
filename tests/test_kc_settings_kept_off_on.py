"""Key Cycling keeps Interval / Direction / Key Spelling across Off / On and across leaving Backing.

Real-app trace (9 Nov 2026, Streamlit session writes logged with their callers): the Interval / Direction radios
unmount while cycling is Off. On the run that turns it On again their keys were still present (the setdefault seeding
wrote nothing), yet the remounted radios came back at their first option, Semitone / Up, and the app then saved that
over Whole tone / Down and rebuilt the cycle. The stand-in session below behaves the same way: a radio drawn again
after a run without it ignores the leftover value unless the app writes the key on that run.
"""
from __future__ import annotations

from backing_key_cycle import (
    end_key_cycle_on_page_leave,
    get_owner_cycle_session,
    is_cycle_active,
    remembered_key_cycle_settings,
    render_backing_key_cycle_controls,
    resolve_cycle_owner,
    spelling_prefs_from_session,
)
from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session

RADIOS = ("backing_key_cycle_step_ui", "backing_key_cycle_direction_ui")


class _StaleWidgetSession(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.stale: set[str] = set()

    def __setitem__(self, key, value):
        self.stale.discard(key)  # written by the app before the radio is drawn: the radio shows it
        super().__setitem__(key, value)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def click(self, key, value):  # the person's click
        dict.__setitem__(self, key, value)
        self.stale.discard(key)

    def end_run(self, drawn):
        for key in RADIOS:
            if key not in drawn and key in self:
                self.stale.add(key)  # still present, but a remounted radio will not use it


class _St(_ControlsSt):
    def __init__(self, session, *, cycling):
        super().__init__(session, cycling=cycling)
        self.drawn: set[str] = set()
        self.callbacks: dict = {}

    def radio(self, label, *, options, key, **kwargs):
        self.drawn.add(key)
        if kwargs.get("on_change"):
            self.callbacks[key] = kwargs["on_change"]
        if key in getattr(self.session, "stale", ()):  # remounted after a run without it: first option
            dict.__setitem__(self.session, key, options[0])
            self.session.stale.discard(key)
        if key not in self.session and "index" in kwargs:  # like st.radio: no stored value -> its index
            self.session[key] = options[int(kwargs["index"])]
        return super().radio(label, options=options, key=key, **kwargs)


def _run(session, cycling, *, toggled=False, click=None, callbacks=None):
    if toggled:
        session["_kc_cycle_user_toggled"] = True
    if click:
        session.click(*click)
        if callbacks and click[0] in callbacks:
            callbacks[click[0]]()  # Streamlit runs on_change before the script
    st = _St(session, cycling=cycling)
    render_backing_key_cycle_controls(st, session)
    session.end_run(st.drawn)
    return st


def _past_the_stray_off_guard(session):
    for k in ("_kc_suppress_spurious_cycle_off", "_kc_suppress_spurious_cycle_off_runs", "_kc_suppress_armed_at"):
        session.pop(k, None)


def _cycle(session):
    data = get_owner_cycle_session(session, resolve_cycle_owner(session)) or {}
    return int(data.get("interval") or 0), str(data.get("direction") or "")


def _whole_down_on(session):
    st = _run(session, "On", toggled=True)
    st = _run(session, "On", click=("backing_key_cycle_step_ui", "whole"), callbacks=st.callbacks)
    st = _run(session, "On", click=("backing_key_cycle_direction_ui", "down"), callbacks=st.callbacks)
    assert (session["backing_key_cycle_step"], session["backing_key_cycle_direction"]) == ("whole", "down")
    assert _cycle(session) == (2, "down")
    _past_the_stray_off_guard(session)


def test_whole_tone_down_survive_off_then_on() -> None:
    session = _StaleWidgetSession(_session())
    _whole_down_on(session)
    _run(session, "Off", toggled=True)
    assert not is_cycle_active(session)
    _run(session, "Off")
    _run(session, "On", toggled=True)
    assert is_cycle_active(session)
    assert (session["backing_key_cycle_step_ui"], session["backing_key_cycle_direction_ui"]) == ("whole", "down")
    assert (session["backing_key_cycle_step"], session["backing_key_cycle_direction"]) == ("whole", "down")
    assert _cycle(session) == (2, "down")  # the running cycle moves in whole tones, downwards
    _run(session, "On")  # and a plain rerun keeps it
    assert _cycle(session) == (2, "down") and session["backing_key_cycle_step_ui"] == "whole"


def test_a_user_click_still_changes_the_setting() -> None:
    session = _StaleWidgetSession(_session())
    _whole_down_on(session)
    st = _run(session, "On")
    _run(session, "On", click=("backing_key_cycle_step_ui", "semitone"), callbacks=st.callbacks)
    assert session["backing_key_cycle_step"] == "semitone" and _cycle(session) == (1, "down")


def test_defaults_only_when_nothing_was_chosen() -> None:
    assert remembered_key_cycle_settings({}) == ("semitone", "up")
    assert remembered_key_cycle_settings({"backing_key_cycle_step": "whole", "backing_key_cycle_direction": "down"}) == ("whole", "down")
    assert remembered_key_cycle_settings({}, {"enabled": True, "interval": 2, "direction": "down"}) == ("whole", "down")
    session = _StaleWidgetSession(_session())
    _run(session, "On", toggled=True)
    assert (session["backing_key_cycle_step_ui"], session["backing_key_cycle_direction_ui"]) == ("semitone", "up")


def test_leaving_backing_turns_cycling_off_but_keeps_the_settings() -> None:
    session = _StaleWidgetSession(_session())
    _whole_down_on(session)
    prefs = dict(spelling_prefs_from_session(session))
    flipped = {pair: (pair.split("/")[0] if v == pair.split("/")[1] else pair.split("/")[1]) for pair, v in prefs.items()}
    session["backing_key_spelling_prefs"] = flipped
    end_key_cycle_on_page_leave(session)
    assert not is_cycle_active(session) and session["backing_key_cycle_enabled_ui"] == "Off"
    assert (session["backing_key_cycle_step"], session["backing_key_cycle_direction"]) == ("whole", "down")
    assert spelling_prefs_from_session(session) == flipped
    _past_the_stray_off_guard(session)
    _run(session, "Off")
    _run(session, "On", toggled=True)
    assert _cycle(session) == (2, "down")
    assert spelling_prefs_from_session(session) == flipped
