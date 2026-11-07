"""The album-cover card's actions drive the existing features; none of them is decorative.

* Show / Close lead sheet: the same buttons (same keys) and the same callback as the row under today's card.
* Advanced settings: opens the existing Advanced playback settings (a keyed expander) and scrolls to it;
  only its open state changes, so playback is not stopped.
* Key Cycling: does exactly what a click on the Off / On radio in Advanced settings does, so direction,
  interval, the saved key's return and Fixed Key all follow from the existing Key Cycling controls.
"""

from __future__ import annotations

import inspect
import pathlib
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CSS = (ROOT / "song_card_art.css").read_text(encoding="utf-8")


@pytest.fixture()
def app(monkeypatch):
    import streamlit_music_practice_app as module

    monkeypatch.setattr(module, "st", SimpleNamespace(session_state={}))
    return module


def test_the_actions_row_sits_after_the_play_row_inside_the_card() -> None:
    i = APP.index("def _create_backing_card_slots(")
    body = APP[i:APP.index("\ndef ", i + 10)]
    assert body.index('st.container(key="backing_art_play_row")') < body.index('st.container(key="backing_art_actions")')
    assert "return head, (keys, bpm_col, play_col, facts, actions)" in body
    # Today's card is unchanged: three columns, no actions row.
    assert "cols = st.columns([1.7, 1.0, 1.2]" in body


def test_the_slot_is_set_per_run_and_reset_with_the_card(app) -> None:
    app._set_backing_art_actions_slot(("k", "b", "p", "f", "ACTIONS"))
    assert app._backing_art_actions_slot == "ACTIONS"
    app._set_backing_art_actions_slot(("k", "b", "p"))  # today's card
    assert app._backing_art_actions_slot is None
    assert "_backing_art_actions_slot = None" in inspect.getsource(app._backing_art_wanted)


@pytest.mark.parametrize("before, after", [("Off", "On"), ("On", "Off"), (None, "On")])
def test_key_cycling_on_the_card_is_the_radio_click(app, before, after) -> None:
    if before is not None:
        app.st.session_state["backing_key_cycle_enabled_ui"] = before
    app._toggle_backing_key_cycle_from_card()
    assert app.st.session_state["backing_key_cycle_enabled_ui"] == after
    # The radio's own on_change sets only this mark; the controls then start or stop cycling as for a click.
    assert app.st.session_state["_kc_cycle_user_toggled"] is True
    # Off from the card is never mistaken for a remount snap: it carries the controls' explicit force-off.
    assert bool(app.st.session_state.get("_key_cycle_force_ui_off")) is (after == "Off")


def test_the_controls_honour_force_off_even_while_the_stray_off_guard_is_armed() -> None:
    import backing_key_cycle as kc

    assert kc.should_honor_cycle_off_request(user_toggled=True, force_off=True, suppress_spurious=True)
    assert not kc.should_honor_cycle_off_request(user_toggled=True, force_off=False, suppress_spurious=True)
    src = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
    assert 'force_off = bool(session.pop("_key_cycle_force_ui_off", False))' in src


def test_the_radio_sets_the_same_mark() -> None:
    kc = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
    assert 'mode_key = "backing_key_cycle_enabled_ui"' in kc
    assert 'session["_kc_cycle_user_toggled"] = True' in kc


def test_advanced_settings_opens_the_existing_expander_and_scrolls_to_it(app) -> None:
    from studio_scroll_anchors import ANCHOR_BACKING_PLAYBACK_SETTINGS, KNOWN_ANCHORS, PENDING_SCROLL_ANCHOR_KEY

    app._open_backing_advanced_settings()
    assert app.st.session_state[app.BACKING_ADVANCED_SETTINGS_KEY] is True
    assert app.st.session_state[PENDING_SCROLL_ANCHOR_KEY] == ANCHOR_BACKING_PLAYBACK_SETTINGS
    assert ANCHOR_BACKING_PLAYBACK_SETTINGS in KNOWN_ANCHORS
    # Nothing else: no transport, play-session or key state is touched.
    assert set(app.st.session_state) == {app.BACKING_ADVANCED_SETTINGS_KEY, PENDING_SCROLL_ANCHOR_KEY}


def test_the_expander_is_keyed_and_the_home_shortcut_opens_the_same_state() -> None:
    i = APP.index('with st.expander("Advanced playback settings"')
    head = APP[i - 420:i + 200]
    assert 'key=BACKING_ADVANCED_SETTINGS_KEY, on_change=_note_backing_advanced_toggle' in head
    assert 'st.session_state.pop("_home_open_key_cycle", False)' in head
    assert "render_scroll_anchor_marker(st, ANCHOR_BACKING_PLAYBACK_SETTINGS)" in head
    assert "expanded=" not in APP[i:i + 200].split(")", 1)[0]


def test_the_lead_sheet_button_on_the_card_is_the_existing_one() -> None:
    src = APP[APP.index("def _render_backing_art_actions("):]
    src = src[:src.index("\ndef ")]
    assert 'key="backing_leadsheet_show_btn"' in src and 'key="backing_leadsheet_hide_btn"' in src
    assert "on_click=set_leadsheet_open, args=(True,)" in src and "on_click=set_leadsheet_open, args=(False,)" in src
    assert "disabled=not leadsheet_ready" in src  # shown, but only usable once there is a take to follow
    call = APP[APP.index("_ls_in_card = _render_backing_art_actions("):][:260]
    assert "set_leadsheet_open=_set_backing_lead_sheet_open" in call
    assert "leadsheet_ready=_leadsheet_controls_ready" in call


def test_key_cycling_on_the_card_only_where_the_feature_is_allowed() -> None:
    src = APP[APP.index("def _render_backing_art_actions("):]
    src = src[:src.index("\ndef ")]
    assert "access_decision(Feature.KEY_CYCLING" in src and "if kc_allowed:" in src


def test_the_actions_wear_the_card_colours_and_stack_on_a_phone() -> None:
    assert ".st-key-backing_art_card .st-key-backing_art_actions button{" in CSS
    assert 'button[data-testid="stBaseButton-primary"]{background:var(--play-bg' in CSS
    phone = CSS.split("@container card (max-width:640px){\n  .st-key-backing_art_card .st-key-backing_art_actions", 1)[1][:400]
    assert "flex-direction:column" in phone
