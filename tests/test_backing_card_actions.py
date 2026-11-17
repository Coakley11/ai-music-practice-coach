"""The album-cover card's actions drive the existing features; none of them is decorative.

* Lead sheet On / Off: one preference shared with the Open / Close lead sheet control above the sheet (which
  stays where it was). On shows the sheet when there is a take and Play opens it for the take it makes; Off
  closes it and Play leaves it closed.
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


def test_lead_sheet_on_the_card_before_a_take_is_the_preference_play_reads(app) -> None:
    calls = []
    app._toggle_backing_lead_sheet_from_card(False, calls.append)
    assert app.st.session_state[app.BACKING_LEAD_SHEET_ON_PLAY_KEY] is True
    assert app.backing_lead_sheet_preference(app.st.session_state) is True
    assert calls == []  # nothing to show yet: no playhead handoff
    app.st.session_state["backing_lead_sheet_open"] = True
    app._toggle_backing_lead_sheet_from_card(False, calls.append)
    assert app.st.session_state[app.BACKING_LEAD_SHEET_ON_PLAY_KEY] is False
    assert app.st.session_state["backing_lead_sheet_open"] is False
    assert calls == []


@pytest.mark.parametrize("open_now, after", [(False, True), (True, False)])
def test_lead_sheet_on_the_card_with_a_take_is_the_open_close_click(app, open_now, after) -> None:
    calls = []
    app.st.session_state["backing_lead_sheet_open"] = open_now  # an older session: no preference saved yet
    app._toggle_backing_lead_sheet_from_card(True, calls.append)
    assert calls == [after]  # the same callback as Open / Close lead sheet


def test_the_open_close_control_stays_above_the_sheet_and_writes_the_same_choice() -> None:
    card = APP[APP.index("def _render_backing_art_actions("):]
    card = card[:card.index("\ndef ")]
    assert 'key="backing_art_lead_sheet_btn"' in card
    assert "backing_leadsheet_show_btn" not in card and "backing_leadsheet_hide_btn" not in card
    assert ':material/menu_book:" if (sheet_shown or sheet_pref) else ":material/book:"' in card  # open / closed sheet
    page = APP[APP.index("def _set_backing_lead_sheet_open(open_: bool)"):]
    setter, rest = page[:page.index("\n\n    #")], page
    assert 'st.session_state["backing_lead_sheet_open"] = bool(open_)' in setter
    assert "st.session_state[BACKING_LEAD_SHEET_ON_PLAY_KEY] = bool(open_)" in setter
    row = rest[rest.index("if _leadsheet_controls_ready:"):][:1400]
    assert '"Open lead sheet"' in row and 'key="backing_leadsheet_show_btn"' in row
    assert '"Close lead sheet"' in row and 'key="backing_leadsheet_hide_btn"' in row
    call = APP[APP.index("    _render_backing_art_actions("):][:320]
    assert "leadsheet_ready=_leadsheet_controls_ready" in call and "set_leadsheet_open=_set_backing_lead_sheet_open" in call
    assert "sheet_visible=bool(_leadsheet_controls_ready and _leadsheet_open)" in call


def test_the_card_lead_sheet_button_hands_the_playhead_over_like_open_close() -> None:
    # Opening or closing the sheet swaps the player; the transport records where the music was for the button
    # clicked. Without the card's button here, a close from the card left the music paused.
    js = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
    i = js.index("recordHandoff();\n          }")
    sel = js[js.rindex("if (closest(", 0, i):i]
    for key in ("backing_leadsheet_show_btn", "backing_leadsheet_hide_btn", "backing_art_lead_sheet_btn"):
        assert f'[class*="st-key-{key}"] button' in sel


def test_play_opens_the_sheet_while_lead_sheet_is_on() -> None:
    i = APP.index("    if _play_clicked:\n")
    block = APP[i:i + 1100]
    read = block.index("_sheet_on_play = backing_lead_sheet_preference(st.session_state)")
    init = block.index("initialize_backing_presentation(st.session_state, _bpm_sync_id)")
    assert read < init  # a new song's presentation starts closed: read the choice first
    # Voice is an instrument (user, 2026-11-16): only an active Karaoke Set keeps its own presentation.
    assert "if _sheet_on_play and not (\n            km.is_voice_mode(st.session_state) and km.is_karaoke_session_active(st.session_state)\n        ):" in block
    assert block.index("km.is_karaoke_session_active(st.session_state)\n        ):") < block.index('st.session_state["backing_lead_sheet_open"] = True')


def test_the_lead_sheet_choice_is_kept_like_the_sheet_itself() -> None:
    src = (ROOT / "music_persistent_state.py").read_text(encoding="utf-8")
    assert src.count('"backing_lead_sheet_on_play"') == 3
    assert 'keys = {"backing_lead_sheet_open", "backing_lead_sheet_on_play"}' in src


def test_key_cycling_on_the_card_only_where_the_feature_is_allowed() -> None:
    src = APP[APP.index("def _render_backing_art_actions("):]
    src = src[:src.index("\ndef ")]
    assert "access_decision(Feature.KEY_CYCLING" in src and "if kc_allowed:" in src


def test_the_actions_wear_the_card_colours_and_stack_on_a_phone() -> None:
    assert ".st-key-backing_art_card .st-key-backing_art_actions button{" in CSS
    assert 'button[data-testid="stBaseButton-primary"]{background:var(--play-bg' in CSS
    phone = CSS.split("@container card (max-width:640px){\n  .st-key-backing_art_card .st-key-backing_art_actions", 1)[1][:400]
    assert "flex-direction:column" in phone


# --- Lead sheet status vs the open-on-Play preference (user, 2026-11-16) ---------------------------------------

def test_the_card_says_on_only_when_the_sheet_is_on_screen() -> None:
    """Measured on dev 6e9da78b: "Lead sheet: On" while no sheet was on screen -- before the first Play, after a
    reload, and all session long with Voice. On = visible; closed with the preference set = "Opens on Play"."""
    card = APP[APP.index("def _render_backing_art_actions("):]
    card = card[:card.index("\ndef ")]
    assert "sheet_shown = bool(sheet_visible)" in card
    on = card.index('sheet_label, sheet_help = "Lead sheet: On", None')
    assert card.index("if sheet_shown:") < on < card.index("elif sheet_pref:") < card.index('sheet_label = "Lead sheet: Opens on Play"')
    assert 'sheet_label = "Lead sheet: Off"' in card
    assert 'type="primary" if sheet_shown else "secondary"' in card
    assert "args=(bool(leadsheet_ready), set_leadsheet_open, sheet_shown)" in card


@pytest.mark.parametrize("visible, after", [(False, True), (True, False)])
def test_with_a_take_the_card_opens_or_closes_what_is_on_screen(app, visible, after) -> None:
    """The preference said On while the sheet was closed: a press then closed a closed sheet. With a take to
    follow, the press acts on what is on screen."""
    calls = []
    app.st.session_state[app.BACKING_LEAD_SHEET_ON_PLAY_KEY] = True
    app._toggle_backing_lead_sheet_from_card(True, calls.append, visible)
    assert calls == [after]


def test_voice_play_message_mentions_karaoke_only_in_a_karaoke_set() -> None:
    i = APP.index("_karaoke_voice_play = bool(")
    expr = APP[i:i + 200]
    assert "km.is_voice_mode(st.session_state) and km.is_karaoke_session_active(st.session_state)" in expr

