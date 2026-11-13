"""M4: the Backing Lead Sheet at full height, the page following the music through ONE controller that holds
still for six seconds after any manual scroll / touch / control interaction, and a compact transport.

Browser behaviour is proven in the real app (scratchpad probe_m4.py); these pin the wiring so it cannot drift:
one controller, used by both follow surfaces, never touching audio, off for Karaoke.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lead_sheet_page_follow as lpf  # noqa: E402

APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
TL = [{"event_index": 0, "start_time": 0.0, "end_time": 2.0, "chord": "C", "section": "A",
       "bar_in_section": 1, "section_bars": 8}]


def _app():
    import streamlit_music_practice_app as app
    return app


def test_hold_is_six_seconds_and_counts_from_the_last_interaction():
    js = lpf._CONTROLLER_JS
    assert lpf.HOLD_MS == 6000
    assert "now() - C.lastInteraction < HOLD_MS" in js          # measured from the LAST interaction
    assert "C.lastInteraction = now()" in js                    # every interaction restarts it
    for kind in ("wheel", "touchstart", "touchmove", "keydown", "pointerdown"):
        assert kind in js
    assert "C.pointerDown ||" in js                              # never moves while a press is held


def test_controller_only_scrolls_never_touches_audio_or_the_highlight():
    js = lpf._CONTROLLER_JS
    for forbidden in (".play(", ".pause(", "currentTime =", "currentTime=", "classList.add", "__karaokeTimeline"):
        assert forbidden not in js, forbidden
    # The only page writes are the scroller's scroll position.
    assert "scrollTo(" in js


def test_controller_installs_once_into_the_top_window():
    inst = lpf.page_follow_controller_js()
    assert "t.__lsFollow" in inst and ">= %d" % lpf.CONTROLLER_VERSION in inst
    assert "</" not in inst.split("s.textContent = ", 1)[1].split("; t.document.head", 1)[0]


def test_backing_sheet_is_full_height_and_follows_through_the_controller():
    html = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=True)
    assert "const PAGE_FOLLOW = true;" in html
    assert "installLeadSheetPageFollow" in html
    assert 'request("lead-sheet", currentCell' in html
    assert 'fe.setAttribute("scrolling", "no")' in html
    assert 'pauseButton: () => document.getElementById("live-stop-btn")' in html


def test_without_page_follow_the_sheet_is_unchanged():
    html = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=False)
    assert "const PAGE_FOLLOW = false;" in html
    assert "installLeadSheetPageFollow" not in html


def test_backing_turns_it_on_and_karaoke_keeps_its_own_box():
    call = APP[APP.index("_kr_component_html = live_follow_along_component_html("):]
    call = call[: call.index("\n        )\n")]
    assert "page_follow=not (_karaoke_engaged or km.is_karaoke_session_active(st.session_state))" in call


def test_practice_melody_no_longer_scrolls_the_page_itself():
    src = APP[APP.index("def render_abc("):APP.index("def render_notation_metronome(")]
    assert ".scrollIntoView(" not in src
    assert "__lsFollow.request('practice-melody'" in src


def test_no_other_page_scroller_was_added():
    # The sheet's old inner-box scroll stays only for the non-follow (Karaoke) path.
    assert APP.count("shell.scrollTop += delta") == 1
    assert len(re.findall(r"__lsFollow\.request\(", APP)) == 2
