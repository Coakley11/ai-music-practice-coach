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


def test_compact_bar_offers_only_stop_while_the_card_is_starting():
    """Loading / counting in: the card shows Stop only; a compact Pause there was swallowed by the count-in."""
    js = lpf._CONTROLLER_JS
    assert 'getAttribute("data-state") === "starting"' in js
    click = js[js.index('pz.addEventListener("click"'):][:300]
    assert click.index("if (cardStarting())") < click.index("pauseButton().click()")
    assert 'pz.style.display = cardStarting() ? "none" : ""' in js


# --- Which notation leads the page (user, 2026-11-14) --------------------------------------------------------


def test_an_open_lit_melody_staff_leads_over_the_lead_sheet():
    assert lpf.MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY
    assert lpf.CONTROLLER_VERSION >= 2                    # replaces a v1 controller left on an open page
    html = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=True)
    assert f'id: "lead-sheet", priority: {lpf.LEAD_SHEET_PRIORITY},' in html
    src = APP[APP.index("def render_abc("):APP.index("def render_notation_metronome(")]
    assert "priority: {_pm_follow_priority}" in src and "MELODY_PRIORITY as _pm_follow_priority" in src
    # Only an aligned staff registers: the script returns before registering when there is no measure timeline.
    assert src.index("if (!measureTimeline || !measureTimeline.length) return;") < src.index("function pmRegister()")
    assert "hasCurrent: () => pmMatched" in src


def test_the_leader_must_be_on_screen_and_lit():
    js = lpf._CONTROLLER_JS
    act = js[js.index("function activeProvider()"):js.index("function transportProvider()")]
    assert "if (!shown(p) || !lit(p)) return;" in act
    assert 'details:not([open])' in js                    # a collapsed expander hides its staff
    # among equal priorities (one Original Melody staff per section) the most recent to light a measure leads
    assert "p.lastAt" in act and "if (me) me.lastAt = now();" in js


def test_closing_or_opening_the_melody_hands_the_page_over_at_once():
    js = lpf._CONTROLLER_JS
    tick = js[js.index("var timer = top.setInterval("):]
    assert "if (leadId !== C.leader)" in tick and 'why: "switch"' in tick
    assert tick.index("if (lead && !s)") < tick.index('why: "switch"')   # never while the person scrolls


def test_the_compact_bar_stays_with_the_lead_sheet_whichever_staff_leads():
    js = lpf._CONTROLLER_JS
    bar = js[js.index("function syncBar()"):js.index("var timer = top.setInterval(")]
    assert "var p = transportProvider();" in bar
    click = js[js.index('pz.addEventListener("click"'):][:200]
    assert "transportProvider()" in click


def test_a_newer_controller_keeps_the_surfaces_already_registered():
    js = lpf._CONTROLLER_JS
    assert "inherited = (top.__lsFollow && top.__lsFollow.providers) || []" in js
    assert "providers: inherited.slice()" in js


def test_the_last_rows_get_room_to_reach_the_reading_position():
    """Measured: near the end of a chart the playing chord sat at 91-93 % of the window under the compact bar and
    the page could not scroll further. The controller adds scroll room below the content before it clamps: an empty
    spacer that is the scroller's own last child (padding on an inner container lengthened the scroll by 0 px on
    A Sky Full of Stars), grown by the shortfall each time it is short (the first version compared the new need with
    the room it had already added, so it never grew twice), at most 70 % of the window. Nothing else moves or resizes.

    Its HEIGHT is not the room: the full-height Lead Sheet sizes its own iframe past Streamlit's element container,
    so the scroll end is the chart's bottom edge and a block after the content hid behind it (measured: 591 px of
    spacer, +0 px of scroll, on Composition 390 px and A Sky Full of Stars 1500 / 390 px). The block is sized from
    where the content really ends -- the later of its own top and the bottom of a registered surface's frame (not any
    iframe: a fixed / sticky frame would chase the scroll end) -- plus the room, and re-sized every tick, so a chart
    that grows, shrinks or closes never leaves extra blank space."""
    js = lpf._CONTROLLER_JS
    fol = js[js.index("C.follow = function"):js.index("C.request = function")]
    assert fol.index("roomBelow(sc, ") < fol.index("want = Math.max(0, Math.min(want")
    assert fol.index("if (C.room > 0) spacer(sc);") < fol.index("roomBelow(sc, ")
    room = js[js.index("function roomBelow(sc, px)"):js.index("C.follow = function")]
    assert "var cap = Math.round(0.7 * top.innerHeight);" in room
    assert "Math.min(C.room + Math.ceil(px) + 24, cap)" in room and "if (want <= C.room) return;" in room
    sp = js[js.index("function spacer(sc)"):js.index("function roomBelow(sc, px)")]
    assert 'sp.id = "ls-follow-room"' in sp and "pointer-events:none" in sp
    assert "sc.lastElementChild !== sp" in sp and "sc.appendChild(sp)" in sp
    assert "liveProviders().forEach" in sp and "sc.contains(f)" in sp and "querySelectorAll(\"iframe\")" not in sp
    assert "Math.round(end + C.room - spTop)" in sp
    tick = js[js.index("var timer = top.setInterval"):js.index("C.destroy = function")]
    assert "if (C.room > 0) spacer(scroller());" in tick
    assert "padding-bottom" not in js
    assert 'doc.getElementById("ls-follow-room")' in js[js.index("C.destroy = function"):]
