"""Practice Start / Stop wear the app's transport icons (user 2026-11-20, Android screenshots).

The metronome (one widget for Tone/Tuner and the Notation tab) and the live tuner (its guitar string
targets included) had plain "Start" / "Stop" text. They now use ACTION_ICONS play / stop, the same
glyphs as the app's other transport, with the words kept and an accessible name per button.
"""
from __future__ import annotations

import re
from pathlib import Path

from music_feature_icons import ACTION_ICONS, action_label

ROOT = Path(__file__).resolve().parents[1]
PLAY, STOP = ACTION_ICONS["play"], ACTION_ICONS["stop"]


def _button(doc: str, dom_id_suffix: str) -> str:
    m = re.search(r'<button[^>]*id="[^"]*' + re.escape(dom_id_suffix) + r'"[^>]*>(.*?)</button>', doc, re.S)
    assert m, dom_id_suffix
    return m.group(0)


def test_metronome_start_and_stop() -> None:
    from practice_metronome import build_metronome_widget_html

    doc = build_metronome_widget_html(default_bpm=100, default_signature="4/4")
    start, stop = _button(doc, "metro-start"), _button(doc, "metro-stop")
    assert f">{PLAY} Start<" in start and 'aria-label="Start metronome"' in start
    assert f">{STOP} Stop<" in stop and 'aria-label="Stop metronome"' in stop


def test_tuner_start_and_stop_keep_their_disabled_state() -> None:
    src = (ROOT / "tuner_live.py").read_text(encoding="utf-8")
    assert '_TUNER_START_LABEL = action_label("play", "Start Tuner")' in src
    assert '_TUNER_STOP_LABEL = action_label("stop", "Stop Tuner")' in src
    stop_tag = re.search(r'<button[^>]*-stop"[^>]*>', src).group(0)
    assert "disabled" in stop_tag and 'aria-label="Stop Tuner"' in stop_tag
    # The tuner's own script still only toggles .disabled - it never rewrites the labels.
    assert "startBtn.textContent" not in src and "stopBtn.textContent" not in src


def test_practice_tool_close_uses_the_close_verb() -> None:
    src = (ROOT / "practice_tools_ui.py").read_text(encoding="utf-8")
    assert 'action_label("close", "Close")' in src


def test_start_and_stop_are_the_transport_glyphs() -> None:
    assert action_label("play", "Start") == f"{PLAY} Start"
    assert action_label("stop", "Stop Tuner") == f"{STOP} Stop Tuner"
    assert STOP != ACTION_ICONS["close"]


def test_generate_notation_matches_creative_sheet_music() -> None:
    src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    assert 'action_label("sheet_music", "Generate notation / TAB")' in src
