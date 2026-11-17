"""M4: the Backing Lead Sheet at full height, the page following the music through ONE controller that holds
still for three seconds after any manual scroll / touch / control interaction, and a compact transport.

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


def test_hold_is_three_seconds_and_counts_from_the_last_interaction():
    """User, 2026-11-16: three seconds after the most recent genuine manual scroll (six was too long)."""
    js = lpf._CONTROLLER_JS
    assert lpf.HOLD_MS == 3000
    assert lpf.CONTROLLER_VERSION >= 3                    # an open v2 page (6 s hold) is replaced
    assert "now() - C.lastInteraction < HOLD_MS" in js          # measured from the LAST interaction
    assert "C.lastInteraction = now()" in js                    # every interaction restarts it
    for kind in ("wheel", "touchstart", "touchmove", "keydown", "pointerdown"):
        assert kind in js
    assert "C.pointerDown ||" in js                              # never moves while a press is held


def test_opening_or_closing_a_panel_hands_over_without_the_hold():
    """Measured: closing the Practice Melody kept the page still for 6.4 s, because the header click counted as
    manual scrolling. A tap / click on an expander header (<summary>) no longer starts the hold; a drag or wheel that
    starts there still does (touchmove and wheel are never excused)."""
    js = lpf._CONTROLLER_JS
    w = js[js.index("function panelToggle(ev)"):js.index("// The page and every same-origin iframe")]
    assert 't.closest("summary")' in w
    assert "var TOGGLE_KINDS = { touchstart: 1 };" in w            # only the tap's start, never touchmove / wheel
    assert "if (TOGGLE_KINDS[k] && panelToggle(ev)) return; interact(k);" in w
    assert 'if (panelToggle(ev)) return;\n      C.pointerDown = true; interact("pointerdown");' in w
    assert "C.pointerDown = false; if (!panelToggle(ev)) interact(k);" in w
    assert 'C.pointerDown = false; if (!panelToggle(ev)) interact("touchend");' in w


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
    assert "__lsFollow.request('{_pm_follow_id}'" in src


def test_no_other_page_scroller_was_added():
    """One thing moves the page: this controller. Karaoke keeps a box of its own, and that box is
    the component's own iframe document - it used to scroll ``.live-follow-shell``, which has no
    height and no overflow, so it moved nothing (measured: box_top 0 in every sample of a Karaoke
    follow run, 2026-11-15). An iframe scrolling itself is not a second page scroller."""
    assert "const sc = document.scrollingElement || document.documentElement;" in APP
    assert APP.count("sc.scrollTop = Math.max(0, Math.min(want, max));") == 1
    # The app never scrolls a page itself; only this module does.
    assert "scrollTo(" not in APP
    # Three page-moving sites, all asking this one controller: the melody staff, the full-height
    # sheet, and Karaoke's sung lyric line. Karaoke registers as the same "lead-sheet" provider
    # and the controller keeps one provider per frame, so the lyrics and the chart cannot both
    # claim the page. Spelled out at each site on purpose - a call behind a local alias would
    # pass this count by being invisible to it.
    assert len(re.findall(r"__lsFollow\.request\(", APP)) == 3


def test_compact_bar_offers_only_stop_while_the_card_is_starting():
    """Loading / counting in: the card shows Stop only; a compact Pause there was swallowed by the count-in."""
    js = lpf._CONTROLLER_JS
    assert 'getAttribute("data-state") === "starting"' in js
    click = js[js.index('pz.addEventListener("click"'):][:300]
    assert click.index("if (cardStarting() || keyCyclingOn())") < click.index("pauseButton().click()")
    assert "var only = cardStarting() || keyCyclingOn();" in js
    assert 'pz.style.display = only ? "none" : "";' in js and "pz.disabled = only;" in js


def test_compact_bar_offers_only_stop_while_key_cycling_is_on():
    """User, 2026-11-15 (temporary, until the Key Cycling transport fixes land): a Stop pressed ~3 s after a bar
    Resume was undone for 2-3 s by that Resume's delayed command. While a cycle is active -- its console, with its
    own Pause / Resume, is only rendered then -- the bar hides Pause / Resume and ignores a press; Stop stays."""
    js = lpf._CONTROLLER_JS
    kc = js[js.index("function keyCyclingOn()"):][:160]
    assert "st-key-backing_key_cycle_pause_btn" in kc
    bar = js[js.index("function syncBar()"):js.index("var timer = top.setInterval(")]
    assert "keyCyclingOn()" in bar and 'bar.style.display = show ? "flex" : "none";' in bar   # Stop still shows
    stop = js[js.index('stop.addEventListener("click"'):][:300]
    assert "keyCyclingOn" not in stop                                                       # Stop never gated


# --- Which notation leads the page (user, 2026-11-14) --------------------------------------------------------


def test_an_open_lit_melody_staff_leads_over_the_lead_sheet():
    assert lpf.MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY
    assert lpf.CONTROLLER_VERSION >= 2                    # replaces a v1 controller left on an open page
    html = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=True)
    assert f'id: "lead-sheet", priority: {lpf.LEAD_SHEET_PRIORITY},' in html
    src = APP[APP.index("def render_abc("):APP.index("def render_notation_metronome(")]
    assert "priority: {_pm_follow_priority}" in src and "FOLLOW_ROLES as _pm_follow_roles" in src
    # Only an aligned staff registers: the script returns before registering when there is no measure timeline.
    assert src.index("if (!measureTimeline || !measureTimeline.length) return;") < src.index("function pmRegister()")
    assert "hasCurrent: () => pmMatched" in src


def test_original_melody_leads_then_practice_melody_then_the_lead_sheet():
    """User, 2026-11-16 (replaces "any melody staff first"): Original Melody > Practice Melody > Lead Sheet. Each
    staff registers and asks to follow under its own role, so the controller can tell the two melodies apart."""
    assert lpf.ORIGINAL_MELODY_PRIORITY > lpf.MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY
    assert lpf.FOLLOW_ROLES == {"practice-melody": lpf.MELODY_PRIORITY, "original-melody": lpf.ORIGINAL_MELODY_PRIORITY}
    src = APP[APP.index("def render_abc("):APP.index("def render_notation_metronome(")]
    assert 'def render_abc(abc_text, *, measure_sync=None, follow_role="practice-melody"):' in src
    assert "id: '{_pm_follow_id}', priority: {_pm_follow_priority}," in src
    assert "__lsFollow.request('{_pm_follow_id}'," in src
    # both Original Melody panels (Backing and Practice) register as the Original Melody; the Practice Melody keeps the default
    assert APP.count('follow_role="original-melody")') == 2
    assert 'render_abc(_bk_model["abc"], measure_sync=_bk_msync, follow_role="original-melody")' in APP
    assert 'render_abc(_cm_model["abc"], measure_sync=_cm_msync, follow_role="original-melody")' in APP
    # uploaded personal melodies are not part of the order yet: the documents panel never renders a follow staff
    panel = (ROOT / "song_document_panel.py").read_text(encoding="utf-8")
    assert "__lsFollow" not in panel and "render_abc" not in panel


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
    # a collapsed surface (closed Practice Melody) still reports its old frame box: measured 2061 / 3632 px of
    # blank at 1500 / 390 px when it sized the room, so only surfaces on screen count
    assert sp.index("if (!shown(p)) return;") < sp.index("var r = f.getBoundingClientRect();")
    tick = js[js.index("var timer = top.setInterval"):js.index("C.destroy = function")]
    assert "if (C.room > 0) spacer(scroller());" in tick
    assert "padding-bottom" not in js
    assert 'doc.getElementById("ls-follow-room")' in js[js.index("C.destroy = function"):]


# --- No notation panel is drawn under another one (user, 2026-11-16) -----------------------------------------


def test_a_follow_frame_sizes_the_space_streamlit_keeps_for_it():
    """Measured on dev 68668ef5: the full-height Lead Sheet's frame was 2396 / 4309 px tall (1500 / 390 px) inside a
    720 px Streamlit element container, so the Original Melody panel below was drawn 1644 / 3557 px inside the chart;
    and a shorter staff left its container at the old height, because the container is a flex item whose fixed basis
    wins over height. The shared helper sizes every box from the frame up to (and only up to) its element container."""
    js = lpf.FRAME_HOST_FIT_JS
    fit = js[js.index("function lsFitFrameHost(fe, h)"):js.index("function lsWatchFrameHost(fe, fit)")]
    assert "fe.closest('[data-testid=\"stElementContainer\"]')" in fit
    assert "if (chain[chain.length - 1] !== host) return;" in fit            # never above the element container
    for prop in ('"flex-basis"', '"height"', '"min-height"'):
        assert f'box.style.setProperty({prop}, h + "px", "important");' in fit
    assert "new ResizeObserver(fit).observe(host)" in js                    # Streamlit resetting it is undone
    assert "</" not in js


def test_the_lead_sheet_sizes_its_container_with_its_frame():
    html = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=True)
    assert "function lsFitFrameHost(fe, h)" in html
    assert "lsFitFrameHost(fe, Math.round(parseFloat(fe.style.height) || h));" in html
    assert "lsWatchFrameHost(fe, fit);" in html
    off = _app().live_follow_along_component_html(b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=False)
    # Karaoke's own box is unchanged: the helper is not even included, and the call sits behind PAGE_FOLLOW = false
    assert "function lsFitFrameHost" not in off and "const PAGE_FOLLOW = false;" in off


def test_a_follow_staff_is_drawn_at_its_own_height_with_no_inner_scroll_box():
    """Measured on dev 68668ef5 at 390 px: the Practice Melody staff hid 1715 px inside its own scroll box, which the
    page controller cannot reach. A staff aligned to the Backing timeline is sized to its notation instead; a plain
    staff (no measure timeline) keeps today's fixed frame."""
    src = APP[APP.index("def render_abc("):APP.index("def render_notation_metronome(")]
    sync = src[src.index('sync_script = f"""'):src.index("_bar_count = max(1, abc_text.count")]
    assert "(function pmFullHeight()" in sync and "{_pm_frame_host_fit_js}" in sync
    assert "fe.setAttribute('scrolling', 'no');" in sync
    assert "lsFitFrameHost(fe, Math.round(parseFloat(fe.style.height) || h));" in sync
    assert src.index("if measure_sync:") < src.index("(function pmFullHeight()")


def test_compact_bar_stop_says_what_it_stops():
    """User, 2026-11-16: "Stop Backing Track" (Key Cycling's own button says "Stop Key Cycling"). The "■ Stop"
    prefix stays: Key Cycling recognises the bar's Stop by it and stops its buffers too."""
    js = lpf._CONTROLLER_JS
    assert 'stop.textContent = "■ Stop Backing Track";' in js
    assert 'stop.setAttribute("aria-label", "Stop Backing Track");' in js


def test_compact_bar_stop_explains_the_key_cycling_restart():
    js = lpf._CONTROLLER_JS
    bar = js[js.index("function syncBar()"):js.index("var timer = top.setInterval(")]
    assert 'if (keyCyclingOn()) stopBtn.title = "Stops playback. The next Play restarts Key Cycling from its first key.";' in bar


def test_no_melody_leads_while_a_karaoke_set_is_active():
    """User, 2026-11-16: in an active Karaoke Set the page follows the Lead Sheet if open, else the Karaoke lyrics
    (registered below the Lead Sheet); a Practice / Original Melody staff never leads then."""
    js = lpf._CONTROLLER_JS
    ap = js[js.index("function activeProvider()"):js.index("function transportProvider()")]
    assert "var best = null, karaoke = karaokeSetActive();" in ap
    assert "if (karaoke && (Number(p.priority) || 0) > LS_PRIORITY) return;" in ap
    assert 'doc.body.getAttribute("data-karaoke-session") === "true"' in js
    code = lpf.page_follow_controller_js()
    assert "LS_PRIORITY = %d" % lpf.LEAD_SHEET_PRIORITY in code and "__LS_PRIO__" not in code
    assert lpf.MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY and lpf.ORIGINAL_MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY



def test_compact_bar_buttons_are_easy_to_tap():
    """User, 2026-11-17: Stop / Pause easy to tap at 360 px. Measured 40 px tall; 44 x 44 px is the comfortable
    minimum."""
    assert "min-height:44px;min-width:44px;" in lpf._CONTROLLER_JS
