"""Playback / Key Cycling buttons carry icons beside unchanged labels (user, 2026-11-11).

Material icons, the convention the Backing card's own buttons set (Lead sheet: On / Off uses menu_book / book).
The labels stay exactly as they were: the Key Cycling bridge, the transport-label writer and the tests read them.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
KC = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")


def _button_call(src: str, key: str) -> str:
    i = src.index(f'key="{key}"')
    start = src.rindex("st.button(", 0, i)
    return src[start: src.index(")", i) + 1]


def test_lead_sheet_row_books_match_the_card() -> None:
    show, hide = _button_call(APP, "backing_leadsheet_show_btn"), _button_call(APP, "backing_leadsheet_hide_btn")
    assert '"Open lead sheet"' in show and 'icon=":material/menu_book:"' in show
    assert '"Close lead sheet"' in hide and 'icon=":material/book:"' in hide
    card = APP[APP.index('key="backing_art_lead_sheet_btn"') - 200: APP.index('key="backing_art_lead_sheet_btn"') + 200]
    assert ":material/menu_book:" in card and ":material/book:" in card


def test_key_cycling_bar_icons_beside_unchanged_labels() -> None:
    want = {
        "backing_key_cycle_prev_btn": ('"Previous key"', ":material/skip_previous:"),
        "backing_key_cycle_advance_btn": ('"Next key"', ":material/skip_next:"),
        "backing_key_cycle_stop_btn": ('"Turn off cycling"', ":material/sync_disabled:"),
    }
    for key, (label, icon) in want.items():
        call = _button_call(KC, key)
        assert label in call and f'icon="{icon}"' in call, key
    pause = _button_call(KC, "backing_key_cycle_pause_btn")
    assert "pause_label," in pause and 'icon=KC_PAUSE_ICON if pause_label != "Resume" else KC_RESUME_ICON' in pause
    assert 'KC_RESUME_ICON = ":material/play_arrow:"' in KC and 'KC_PAUSE_ICON = ":material/pause:"' in KC


def test_the_browser_swaps_the_pause_icon_with_the_label() -> None:
    i = KC.index("const want = paused ? 'Resume' : 'Pause';")
    block = KC[i: i + 900]
    assert "if (cur !== want) labelEl.textContent = want;" in block
    assert "stIconMaterial" in block and "paused ? 'play_arrow' : 'pause'" in block
    # The label is still written to the label element only, never over the icon.
    assert re.search(r"const labelEl = btn\.querySelector\('p'\) \|\| btn;", block)
