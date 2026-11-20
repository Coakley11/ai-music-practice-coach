"""User rule 2026-11-20: in Voice the singing panel is always there, and the Lead Sheet's own header
collapses / expands it through the Backing card's one Lead Sheet switch.

* The follow-along surface (lyrics, cues, optional chords) mounts for Voice whether or not a Karaoke
  Set is active - it no longer disappears with the Lead Sheet closed outside a set.
* Countdown and auto-advance stay set-only (``_karaoke_engaged`` = Voice AND an active set).
* The fold header presses ``.st-key-backing_art_lead_sheet_btn button`` - no second variable - and
  its words follow the page marker, so the component HTML never changes with the switch.
"""
from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _block(start: str, size: int = 900) -> str:
    i = SRC.index(start)
    return SRC[i : i + size]


def test_the_surface_mounts_for_voice_with_or_without_a_set() -> None:
    block = _block("    _karaoke_needs_surface = False\n    try:", 400)
    assert "_karaoke_needs_surface = bool(km.is_voice_mode(st.session_state))" in block
    assert "is_karaoke_session_active" not in block


def test_countdown_and_auto_advance_stay_set_only() -> None:
    assert "_karaoke_engaged = _karaoke_active and _karaoke_voice" in SRC
    assert "_karaoke_engaged\n            and km.countdown_enabled(st.session_state)" in SRC
    assert "_karaoke_engaged and km.auto_advance_enabled(st.session_state)" in SRC


def test_the_fold_header_presses_the_one_lead_sheet_switch() -> None:
    js = _block("    function installFoldHeader() {{", 900)
    assert '.st-key-backing_art_lead_sheet_btn button' in js
    assert "btn.click()" in js and "ev.preventDefault()" in js
    assert "installFoldHeader();" in _block("    if (KARAOKE_HOLD) {{", 300)


def test_the_header_words_follow_the_switch_not_the_html() -> None:
    js = _block("    function syncFoldHeader(ls) {{", 600)
    assert "Collapse Lead Sheet" in js and "Expand Lead Sheet" in js
    assert "syncFoldHeader(ls);" in _block("    function syncChartFold() {{", 400)
    fold = _block("    if karaoke_hide_chart:", 1400)
    assert 'class="ls-fold-action"' in fold and "Lead Sheet" in fold
