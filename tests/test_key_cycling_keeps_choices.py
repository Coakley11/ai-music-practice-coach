"""Key Cycling keeps what the musician chose: closed melodies stay closed, settings stay, the position stays.

Dev review 2026-11-25, with Key Cycling running: a closed Practice Melody opened again on the next key; a groove or
tempo chosen while playing went back to the earlier one; a change sent the cycle to its first key. Only a manual
change of the saved Practice Key restarts the sequence.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import melody_panel_visibility as panels
from backing_key_cycle import (
    arm_key_cycle_for_explicit_play,
    note_backing_pass_finished,
    reanchor_key_cycle_from_practice_key,
    settings_change_is_remount_noise,
    start_key_cycle,
    temporary_playback_key,
)
from backing_transport_intent import begin_playback, note_playback_settings_changed, transport_intent

PICK = "Pop\x1fShallow"
APP = Path("streamlit_music_practice_app.py")


def _cycling(passes: int = 2) -> dict:
    s = {
        "studio_page": "backing",
        "active_catalog_pick_key": PICK,
        "display_key": "C",
        "concert_key": "C",
        "practice_key_by_source": {PICK: "C"},
    }
    start_key_cycle(s, start_key="C", interval=2, direction="up")
    begin_playback(s)
    for i in range(passes):
        note_backing_pass_finished(s, pass_signature=f"s{i}")
    return s


# --- the cycle's position ---------------------------------------------------------------------------


def test_the_same_practice_key_again_does_not_restart_the_cycle():
    s = _cycling()
    assert temporary_playback_key(s) == "E"
    for _ in range(3):
        reanchor_key_cycle_from_practice_key(s, new_key="C")
        assert temporary_playback_key(s) == "E"


def test_a_different_practice_key_restarts_the_cycle_from_it():
    s = _cycling()
    reanchor_key_cycle_from_practice_key(s, new_key="F")
    assert temporary_playback_key(s) == "F"


def test_a_finished_background_build_keeps_the_current_key_and_play_starts_over():
    s = _cycling()
    arm_key_cycle_for_explicit_play(s, keep_position=True)
    assert temporary_playback_key(s) == "E"
    arm_key_cycle_for_explicit_play(s)
    assert temporary_playback_key(s) == "C"


# --- settings ---------------------------------------------------------------------------------------


def _filter_callback(ss: dict, canonical: dict, default_groove: str = "Pop groove") -> None:
    source = ast.parse(APP.read_text(encoding="utf-8"))
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "_on_backing_filter_change")

    def _sync():
        canonical.update({k: ss[k] for k in ("backing_groove_style", "backing_track_bpm") if k in ss})

    scope = {
        "st": SimpleNamespace(session_state=ss),
        "transport_intent": transport_intent,
        "note_playback_settings_changed": note_playback_settings_changed,
        "_sync_canonical_backing_after_edit": _sync,
        "km": SimpleNamespace(is_voice_mode=lambda s: False, is_karaoke_session_active=lambda s: False),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<filter callback>", "exec"), scope)
    with (
        patch("backing_track_state.canonical_backing_filters", side_effect=lambda *_a, **_k: dict(canonical)),
        patch("backing_context.backing_page_transport_defaults", return_value=(100, default_groove, "4/4")),
    ):
        scope["_on_backing_filter_change"]()


def _after_play(**kw) -> dict:
    return {**_cycling(), "_kc_settings_applied_this_play": True, "_kc_settings_applied_at": time.time(), **kw}


@pytest.mark.parametrize("chosen", ["Rock groove", "Bossa nova", "Funk groove"])
def test_a_groove_chosen_while_cycling_is_kept(chosen):
    ss = _after_play(backing_groove_style=chosen)
    canonical = {"backing_groove_style": "Jazz swing", "backing_track_bpm": 100}
    _filter_callback(ss, canonical)
    assert ss["backing_groove_style"] == chosen and canonical["backing_groove_style"] == chosen
    assert temporary_playback_key(ss) == "E"


def test_a_tempo_chosen_while_cycling_is_kept():
    ss = _after_play(backing_groove_style="Jazz swing", backing_track_bpm=132)
    canonical = {"backing_groove_style": "Jazz swing", "backing_track_bpm": 100}
    _filter_callback(ss, canonical)
    assert ss["backing_track_bpm"] == 132 and canonical["backing_track_bpm"] == 132


def test_the_default_groove_can_be_chosen_back_later():
    ss = _after_play(backing_groove_style="Pop groove", _kc_settings_applied_at=time.time() - 60)
    canonical = {"backing_groove_style": "Blues groove", "backing_track_bpm": 100}
    _filter_callback(ss, canonical)
    assert ss["backing_groove_style"] == "Pop groove"


def test_the_redrawn_controls_default_right_after_play_is_still_ignored():
    ss = _after_play(backing_groove_style="Pop groove")
    canonical = {"backing_groove_style": "Blues groove", "backing_track_bpm": 100}
    _filter_callback(ss, canonical)
    assert ss["backing_groove_style"] == "Blues groove"


def test_without_a_marker_nothing_is_noise():
    assert not settings_change_is_remount_noise({"backing_groove_style": "Pop groove"})


# --- melody panels ----------------------------------------------------------------------------------


class _St:
    def __init__(self, session):
        self.session_state, self.calls = session, []

    def expander(self, label, **kw):
        self.calls.append((label, self.session_state[kw["key"]]))
        return kw


def test_a_closed_melody_stays_closed_through_keys_and_runs_that_do_not_draw_it():
    s = {}
    st = _St(s)
    kw = panels.melody_expander(st, "Practice Melody", panels.PRACTICE, "song A")
    assert st.calls[-1][1] is True
    s[kw["key"]] = False  # the musician closes it
    with patch("streamlit.session_state", s):
        kw["on_change"](*kw["args"])
    for _ in range(12):  # some runs do not draw the panel, so Streamlit forgets its value
        s.pop(kw["key"], None)
        panels.melody_expander(st, "Practice Melody", panels.PRACTICE, "song A")
        assert st.calls[-1][1] is False


def test_another_song_and_the_other_panel_have_their_own_choice():
    s = {}
    panels.set_open(s, panels.PRACTICE, "song A", False)
    assert panels.is_open(s, panels.PRACTICE, "song B") and panels.is_open(s, panels.ORIGINAL, "song A")


def test_asking_for_the_melody_opens_it():
    from practice_melody_backing import begin_practice_melody_backing_handoff

    s = {}
    panels.set_open(s, panels.PRACTICE, "song A", False)
    begin_practice_melody_backing_handoff(s, melody=object(), song_identity="song A")
    assert panels.is_open(s, panels.PRACTICE, "song A")


def test_no_backing_melody_panel_is_forced_open():
    app = APP.read_text(encoding="utf-8")
    practice = app[app.index("# Practice Melody projection (Slice E/F1)") :]
    practice = practice[: practice.index("if _developer_mode_enabled():")]
    original = app[app.index("# ----- Original Melody panel -----") :][:3500]
    for block in (practice, original):
        assert "expanded=True" not in block and "melody_expander as" in block


def test_no_other_backing_button_looks_like_a_key_cycling_step():
    """Key Cycling's page script claims any button labelled like its Previous / Next (label fallback) and cancels
    the click: the Practice Melody's Previous did nothing on a jam's Backing (browser 2026-11-25)."""
    import re

    kc = Path("backing_key_cycle.py").read_text(encoding="utf-8")
    prev_re = re.compile(r"^([◀⏮]\s*)?Previous( key)?$", re.I)
    next_re = re.compile(r"^([▶⏭]\s*)?Next( key)?(\s*[▶⏭])?$", re.I)
    assert "Previous( key)?$/i" in kc and "Next( key)?" in kc  # the fallback this test guards against
    panel = Path("practice_melody_panel.py").read_text(encoding="utf-8")
    labels = re.findall(r'st\.button\(\s*"([^"]+)"', panel)
    assert labels and not [x for x in labels if prev_re.match(x) or next_re.match(x)]
