"""A fresh Play never hands a playhead to the sheet it opens (browser 2026-11-26).

A Lead sheet press on a jam whose take was already made, before its first Play, set the sheet hand-off flag while
no sheet was drawn. Play then opened the sheet with that stale flag; finding no hand-off from the page player, the
sheet paused itself at 0:00 ("opened while nothing was playing") and the first Play was silent.
"""

from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"


def _play_block() -> str:
    src = APP.read_text(encoding="utf-8")
    start = src.index("    if _play_clicked:\n        # Lead sheet On")
    end = src.index("st.session_state[BACKING_AUTOPLAY] = True", start)
    return src[start:end]


def test_play_drops_a_stale_sheet_handoff_before_it_opens_the_sheet():
    block = _play_block()
    drop = block.index('st.session_state.pop("_backing_sheet_open_handoff", None)')
    assert drop < block.index('st.session_state["backing_lead_sheet_open"] = True')


def test_the_handoff_is_still_set_by_an_open_click_and_read_where_the_sheet_is_drawn():
    src = APP.read_text(encoding="utf-8")
    assert 'st.session_state["_backing_sheet_open_handoff"] = True' in src
    assert 'st.session_state.pop("_backing_sheet_open_handoff", False)' in src
