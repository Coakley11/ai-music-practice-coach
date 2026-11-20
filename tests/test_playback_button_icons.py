"""Playback / Key Cycling buttons carry icons beside unchanged labels (user, 2026-11-11).

Material icons, the convention the Backing card's own buttons set (Lead sheet: On / Off uses menu_book / book).
The labels stay exactly as they were: the Key Cycling bridge, the transport-label writer and the tests read them.

Adapted 2026-11-15 to the purple/gold Key Cycling console that replaced the four-button row (Previous /
Pause|Resume / Next / Stop, buttons drawn by its ``_btn`` helper). Same guarantees: an icon beside every
unchanged label, the browser swaps the pause / play icon with the label, and the bridge decides Pause or Resume
from kcPauseBtnMode(), never from exact display text.
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


def _console_button(key: str) -> str:
    """The console's ``_btn(label, "<key>", icon=..., ...)`` call for this widget key."""
    i = KC.index(f'"{key}",')
    start = KC.rindex("_btn(", 0, i)
    return KC[start: KC.index("\n            )", i) + len("\n            )")]


def test_lead_sheet_row_books_match_the_card() -> None:
    show, hide = _button_call(APP, "backing_leadsheet_show_btn"), _button_call(APP, "backing_leadsheet_hide_btn")
    assert '"Open lead sheet"' in show and 'icon=":material/menu_book:"' in show
    assert '"Close lead sheet"' in hide and 'icon=":material/book:"' in hide
    card = APP[APP.index('key="backing_art_lead_sheet_btn"') - 200: APP.index('key="backing_art_lead_sheet_btn"') + 200]
    assert ":material/menu_book:" in card and ":material/book:" in card


def test_key_cycling_console_icons_beside_unchanged_labels() -> None:
    # Labels say what each button does (user report 2026-11-16: "Stop -- stop what?"): this Stop ends
    # Key Cycling; the card's "Stop Backing Track" stops the audio and keeps cycling on.
    want = {
        "backing_key_cycle_prev_btn": ('"Previous Key"', ":material/skip_previous:"),
        "backing_key_cycle_advance_btn": ('"Next Key"', ":material/skip_next:"),
        "backing_key_cycle_stop_btn": ('"Stop Key Cycling"', ":material/stop:"),
    }
    for key, (label, icon) in want.items():
        call = _console_button(key)
        assert label in call and f'icon="{icon}"' in call, key
    # The page still recognises Previous / Next by their labels (case-insensitive, optional "key").
    import re

    prev_re = re.compile(r"^([◀⏮]\s*)?Previous( key)?$", re.I)
    next_re = re.compile(r"^([▶⏭]\s*)?Next( key)?(\s*[▶⏭])?$", re.I)
    assert prev_re.match("Previous Key") and next_re.match("Next Key")
    assert "Previous( key)?$/i.test(" in KC and "Next( key)?" in KC  # the page's matchers
    pause = _console_button("backing_key_cycle_pause_btn")
    # The label is the plain "Pause" / "Resume" the bridge reads; the icon follows it.
    assert "pause_label," in pause and 'icon=KC_PAUSE_ICON if pause_label != "Resume" else KC_RESUME_ICON' in pause
    assert 'KC_RESUME_ICON = ":material/play_arrow:"' in KC and 'KC_PAUSE_ICON = ":material/pause:"' in KC
    # The old four-button row is not back.
    assert '"Turn off cycling"' not in KC and '"Previous key"' not in KC


def test_the_browser_swaps_the_pause_icon_with_the_label() -> None:
    i = KC.index("const want = (paused && !ended) ? 'Resume' : 'Pause';")
    block = KC[i: i + 1300]
    assert "if (cur !== want) labelEl.textContent = want;" in block
    assert "stIconMaterial" in block and "(paused && !ended) ? 'play_arrow' : 'pause'" in block
    # A cycle that ended on its completed final key never offers an actionable Resume.
    assert KC[i - 200: i].rstrip().endswith("const ended = finalTakeCompleted();")
    assert "if (!btn.disabled) {{ btn.disabled = true; btn.setAttribute('data-kc-final-end', '1'); }}" in block
    # The label is still written to the label element only, never over the icon.
    assert re.search(r"const labelEl = btn\.querySelector\('p'\) \|\| btn;", block)


def test_key_cycle_bridge_decides_pause_or_resume_from_a_mode_not_exact_text():
    """The icon's ligature text is part of the button's innerText ("pause Pause"); the bridge must not compare
    display text exactly -- it asks kcPauseBtnMode() for 'pause' / 'resume'."""
    import backing_key_cycle as kc

    js = kc.cycle_persistent_player_bridge_html(cmd_json="{}")
    assert "function kcPauseBtnMode(b)" in js and "function kcPauseBtnLabel(b)" in js
    assert js.index("function kcPauseBtnMode(b)") < js.index("__kcRequestCyclePause = function")
    assert "/^Pause$/i.test(lab" not in js and "/^Resume$/i.test(lab" not in js
    # Every Pause / Resume decision asks the button's mode (or the console's shared decision), never its text.
    assert js.count("kcPauseBtnMode(") == 4  # the definition and its three callers below
    assert js.count("kcPauseBtnMode(b) !== 'resume'") == 1  # Live Resume after an audible kick
    assert js.count("kcPauseBtnMode(b0) === 'resume'") == 1  # Back to loop start, Held capture
    # The Lead Sheet and console share one decision (__kcCyclePressPauses); without it the live press
    # falls back to the button's mode -- never to its text.
    live = js[js.index("function kcLivePressPauses()"):js.index("function kcLivePressPauses()") + 600]
    assert "parentWin.__kcCyclePressPauses()" in live
    assert "kcPauseBtnMode(" in live and "=== 'pause'" in live
    # Live Pause and Live Resume each press the console's button once, and only when that press does what
    # was asked (a Pause on a held player, or a Resume on a playing one, does nothing).
    resume = js[js.index("parentWin.__kcRequestCycleResume = function"):js.index("parentWin.__kcPauseAudio = function")]
    pause = js[js.index("parentWin.__kcRequestCyclePause = function"):js.index("parentWin.__kcResumeAudio = function")]
    assert "if (kcLivePressPauses()) return;" in resume and resume.count("__kcPressCycleTransport()") == 1
    assert "if (!kcLivePressPauses()) return;" in pause and pause.count("__kcPressCycleTransport()") == 1
    # One gesture is handled once: the document and the button both see it, the second call is dropped.
    handler = js[js.index("parentWin.__kcPauseBtnHandler = function"):]
    assert "now - Number(parentWin.__kcPauseToggleAt || 0) < 500) return;" in handler[:1200]
    assert 'stIconMaterial' in js[js.index("function kcPauseBtnLabel(b)"):js.index("function kcPauseBtnMode(b)")]
