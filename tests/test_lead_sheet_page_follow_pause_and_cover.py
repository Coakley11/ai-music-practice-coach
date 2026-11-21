"""Two page-follow defects found on 13de912d (2026-11-21), pinned at the source level (browser runs prove behaviour).

1. Karaoke Set, Lead Sheet OFF, 390 px: the singing lyric was 'covered' in 461/461 playing samples. Karaoke's Live
   Follow-Along Player is ``position: sticky; top: 0`` inside its own 820 px scrolling iframe; on a phone its 2 x 2
   status cards make it taller than the 32 % of the box where the frame's follower put the lyric, so the player sat on
   the line. The page controller saw 'covered' and moved the PAGE (9 catch-ups) -- which can never clear a box pinned
   inside the frame -- and kept trying.
2. Pause / Stop moved the page 900-2,000 px with no move of the controller: the rerun re-renders what is around the
   reading position and the browser clamps / re-anchors the scroll position (and queued automatic jumps could still
   fire). Pausing or stopping must not move the page.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lead_sheet_page_follow as lpf  # noqa: E402

APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
ANCHORS = (ROOT / "studio_scroll_anchors.py").read_text(encoding="utf-8")
JS = lpf._CONTROLLER_JS
TL = [{"event_index": 0, "start_time": 0.0, "end_time": 2.0, "chord": "C", "section": "A",
       "bar_in_section": 1, "section_bars": 8}]


def _between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def _tick():
    return _between(JS, "var timer = top.setInterval(", "C.destroy = function")


# ---- 1. the lyric under Karaoke's sticky player ----

def test_the_karaoke_player_is_sticky_inside_its_frame_and_karaoke_keeps_that_layout():
    """The cause: the non-compact player (Karaoke) is sticky at the top of the frame; the compact one is static."""
    css = APP[APP.index("    .live-player {{\n      position: sticky;"):][:120]
    assert "position: sticky;" in css and "top: 0;" in css
    assert ".lf-compact .live-player {{\n      position: static;" in APP


def test_the_box_follower_puts_the_line_below_what_is_pinned_at_the_top_of_its_frame():
    body = _between(APP, "    function boxTopClearance() {{", "    window.__karaokeBoxFollow = followInsideBox;")
    assert 'document.querySelectorAll(".live-player")' in body
    assert 'if (cs.position !== "sticky" && cs.position !== "fixed") return;' in body
    assert "clear = Math.max(clear, (parseFloat(cs.top) || 0) + h);" in body
    fib = body[body.index("function followInsideBox(el)"):]
    # still 32 % on a wide screen, but never above the bottom of the sticky player
    assert "const readAt = Math.max(sc.clientHeight * 0.32, boxTopClearance() + 12);" in fib
    assert "const want = sc.scrollTop + c.top - readAt;" in fib
    assert "sc.clientHeight * 0.32)" not in fib              # the old fixed reading point is gone


def test_the_frame_exposes_its_follower_to_the_page_controller():
    assert "window.__lsBoxFollow = followInsideBox;" in APP
    html = __import__("streamlit_music_practice_app").live_follow_along_component_html(
        b"RIFF", TL, "<div></div>", audio_b64="AA", page_follow=False)
    assert "window.__lsBoxFollow = followInsideBox;" in html
    assert "function boxTopClearance()" in html


def test_a_cover_pinned_inside_the_targets_frame_is_reported_as_in_frame():
    pb = _between(JS, "function pinnedBox(e)", "C.notVisible = function")
    # the covering element's OWN document and window, not only the top window's
    assert "var d = e && e.ownerDocument, w = d && d.defaultView;" in pb
    assert "var pos = w.getComputedStyle(n).position;" in pb
    assert "inFrame: d !== doc" in pb
    assert "var r = rectInTop(n);" in pb                    # mapped into top-window coordinates
    assert "if (n.ownerDocument !== doc) return null;" not in pb


def test_the_page_is_never_moved_for_an_in_frame_cover_the_frame_follower_is_asked_instead():
    cu = _tick()[_tick().index("// Catch-up:"):]
    assert "if (nv.pinned && nv.pinned.inFrame) frameRefollow(ce, nv);" in cu
    assert "else if (catchUpAllowed(ce, nv.why))" in cu
    rf = _between(JS, "function frameRefollow(el, nv)", "// ---- the clock")
    assert 'typeof w.__lsBoxFollow === "function") w.__lsBoxFollow(el);' in rf
    assert "C.follow(" not in rf                               # no page move for it
    assert 'if (!catchUpAllowed(el, "frame-" + nv.why)) return;' in rf
    # and C.follow itself ignores a pin that lives in a frame
    f = _between(JS, "C.follow = function", "// A surface asks to follow")
    assert "if (pin && !pin.inFrame && pin.bottom - pin.top < 0.5 * (vb - vt)) {" in f


def test_a_catch_up_that_cannot_clear_is_not_repeated_for_ever():
    assert "var CATCHUP_TRIES = 2;" in JS
    ca = _between(JS, "function catchUpAllowed(el, why)", "function frameRefollow")
    assert "if (!f || f.el !== el || f.why !== why) { C.futile = { el: el, why: why, n: 1, t: now() }; return true; }" in ca
    assert "if (f.n >= CATCHUP_TRIES) { f.gaveUp = true; return false; }" in ca
    # the count starts again when the target is seen clear or the person scrolls
    assert "} else if (!nv) C.futile = null;" in _tick()
    inter = _between(JS, "function interact(kind)", "function panelToggle(ev)")
    assert "C.futile = null; C.keep = null;" in inter


# ---- 2. Pause / Stop must not move the page ----

def test_the_controller_version_is_bumped_so_open_pages_take_the_new_behaviour():
    assert lpf.CONTROLLER_VERSION >= 7
    assert ">= %d" % lpf.CONTROLLER_VERSION in lpf.page_follow_controller_js()


def test_a_paused_or_stopped_surface_never_moves_the_page():
    req = _between(JS, "C.request = function", "// ---- compact transport")
    gate = req[req.index("if (me && !(opts && opts.why === \"karaoke-set-start\")) {"):]
    assert "try { on = !!me.playing(); } catch (eP) {}" in gate
    assert "if (!on) return false;" in gate
    # the gate comes before anything can call C.follow
    assert req.index("if (!on) return false;") < req.index("return C.follow(el, opts);")


def test_every_tick_runs_the_place_keeper_before_anything_else_can_move_the_page():
    tick = _tick()
    assert tick.index("keepTick();") < tick.index("var s = C.suspended();")
    assert tick.index("keepTick();") < tick.index("C.follow(cur, { why: \"switch\" })")


def test_the_place_is_noted_while_playing_and_kept_after_the_music_stops():
    kt = _between(JS, "function keepTick()", "// ---- a catch-up that cannot clear")
    # noted every settled tick while playing (not mid-move, not while the person scrolls)
    assert "if (t >= C.selfScrollUntil && !C.suspended() && (!C.place || t - C.place.t >= 450)) C.place = notePlace();" in kt
    # at the playing -> stopped transition: an in-flight move of ours is stopped where it is
    stop = kt[kt.index("if (C.wasPlaying) {"):]
    assert "C.selfScrollUntil = 0;" in stop
    assert 'sc0.scrollTo({ top: sc0.scrollTop, behavior: "auto" });' in stop
    # a place older than our last move or the person's last scroll is not trusted
    assert "if (!pl || pl.t < lastMoveAt() || pl.t < C.lastInteraction) pl = notePlace();" in stop
    assert 'why: t - C.transportPressAt < 2500 ? "user-stop" : "stop"' in stop


def test_the_keeper_only_ever_scrolls_back_by_the_drift_and_gives_way_to_the_person():
    kt = _between(JS, "function keepTick()", "// ---- a catch-up that cannot clear")
    assert "var KEEP_MS = 15000, KEEP_SLACK = 24;" in JS
    assert ("if (t - k.since > KEEP_MS || C.lastInteraction > k.since || lastMoveAt() > k.since) "
            "{ C.keep = null; return; }") in kt
    assert "if (C.pointerDown) return;" in kt
    assert "if (d === null || Math.abs(d) <= KEEP_SLACK) return;" in kt
    assert "var want = Math.max(0, Math.min(sc.scrollTop + d, max));" in kt
    # recorded, but not as a follow move (it moves the page nowhere new)
    assert 'C.keeps.push({ t: t, from: Math.round(sc.scrollTop), to: Math.round(want), why: "keep-" + k.why });' in kt
    assert "C.moves.push" not in kt
    # never smooth: it undoes a jump, it is not a glide
    assert 'sc.scrollTo({ top: want, behavior: "auto" });' in kt


def test_the_kept_place_survives_a_re_created_element_through_its_streamlit_key():
    np_ = _between(JS, "function notePlace()", "function placeDrift(pl)")
    assert "if (!e || !movesWithPage(e, sc)) continue;" in np_       # sticky / fixed boxes are not anchors
    assert "e.closest('[data-testid=\"stElementContainer\"]')" in np_
    assert "var key = keyedBlock(host, sc)" in np_
    pd = _between(JS, "function placeDrift(pl)", "function lastMoveAt()")
    assert "if (a.el && a.el.isConnected) {" in pd
    assert 'var kn = doc.querySelector("." + a.key);' in pd
    kb = _between(JS, "function keyedBlock(n, sc)", "function notePlace()")
    assert 'cl[i].indexOf("st-key-") === 0' in kb and 'doc.querySelectorAll("." + cl[i]).length === 1' in kb


def test_only_a_stop_press_while_paused_starts_a_keep_any_other_press_ends_it():
    pp = _between(JS, "function pressPlace(ev)", "function keepTick()")
    assert "if (!isTransport(ev)) { C.keep = null; return; }" in pp
    assert "C.transportPressAt = now();" in pp
    assert "if (!pressStops(ev)) { C.keep = null; return; }" in pp
    assert 'C.keep = pl ? { since: now(), place: pl, why: "user-stop" } : null;' in pp
    stops = _between(JS, "var STOP_SEL = ", "function pressPlace(ev)")
    for sel in ("st-key-backing_key_cycle_stop_btn", "st-key-stop_backing_btn", "#ls-mini-stop"):
        assert sel in stops
    assert 'b.getAttribute("data-state") !== "stopped"' in stops     # the card's button while it offers Stop
    press = _between(JS, "function press(ev)", "// Released:")
    assert "if (panelToggle(ev)) { C.keep = null; return; }" in press
    assert "pressPlace(ev);" in press
    sel = _between(JS, "var TRANSPORT_SEL = ", "C.keep = null; C.keeps = [];")
    for key in ("st-key-backing_key_cycle_", "st-key-backing_card_transport", "#ls-mini-transport", "#live-stop-btn"):
        assert key in sel


def test_the_keeper_never_touches_audio_or_the_highlight():
    keep = _between(JS, "// ---- Pause and Stop leave the page where it is ----", "// ---- the clock")
    for forbidden in (".play(", ".pause(", "currentTime", "classList.add", ".click()"):
        assert forbidden not in keep, forbidden


def test_a_queued_anchor_jump_defers_to_the_controller_and_is_recorded():
    script = ANCHORS[ANCHORS.index("const tryScroll = () =>"):]
    script = script[:script.index("if (tryScroll()) return;")]
    assert "ctl = (window.parent && window.parent.__lsFollow) || window.top.__lsFollow || null;" in script
    assert "(ctl.suspended && ctl.suspended())" in script
    assert "(ctl.keeping && ctl.keeping() === 'user-stop')" in script
    assert script.index("ctl.suspended()") < script.index("sc.scrollTo(")
    assert "why: 'anchor:' + target" in script
    assert "ctl.moves.push(" in script
    # the dropped jump is consumed (returns true), so it cannot fire later
    assert re.search(r"=== 'user-stop'\)\)\) return true;", script)
