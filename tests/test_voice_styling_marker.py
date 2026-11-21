"""Voice lyric styling must not depend on a <script> inside st.markdown (Streamlit never runs it).

The vocal-focus CSS in app_ui used ``[data-vocal-focus="true"]`` on <body>, set only by such a script, so it
could never match in a real browser (found 2026-11-20 with 87's page-follow marker). It now matches the
rendered ``.ls-follow-context[data-vocal-focus]`` marker with :has().
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
UI = (ROOT / "app_ui.py").read_text(encoding="utf-8")


def test_the_marker_carries_the_voice_flag() -> None:
    i = APP.index("'<span class=\"ls-follow-context\" hidden aria-hidden=\"true\" '")
    block = APP[i : i + 600]
    assert "data-vocal-focus=" in block and "km.is_voice_mode(st.session_state)" in block


def test_every_vocal_focus_rule_matches_the_rendered_marker() -> None:
    assert UI.count('body:has(.ls-follow-context[data-vocal-focus="true"])') == 15
    bare = UI.replace('body:has(.ls-follow-context[data-vocal-focus="true"])', "")
    assert '[data-vocal-focus="true"]' not in bare
