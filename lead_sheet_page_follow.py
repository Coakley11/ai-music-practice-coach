"""One page-scroll controller for everything that follows the music down the page (M4).

The Backing Lead Sheet is drawn at its full height (no inner scroll box), so following the music means moving
the *page*. Two surfaces want that: the Lead Sheet (the current chord) and the melody staff -- the Practice Melody,
or a Composition's Original Melody, one staff per section (the current measure). Each lives in its own
components.html iframe, so they cannot share a Python object; instead the first iframe that loads installs a
single controller on the top window (``window.top.__lsFollow``) and every surface registers with it and asks it
to follow. Only one surface leads at a time. The order (user, 2026-11-16, replacing "a melody staff first"):
the Original Melody (a Composition's own melody, one staff per section), then the Practice Melody, then the Lead
Sheet -- each only while it is open on screen and has the playing measure lit (a staff's measures are aligned to
the Backing timeline); otherwise nothing moves the page. Closing the leader hands the page to the next one at once,
and among several section staves the one that lit a measure most recently leads. A melody with no measure alignment (an uploaded
PDF, a staff without a timeline) never registers, so it never claims the page.

That is the only code that moves the page. It never fights the person: while they scroll -- for as long as they
like -- it holds still, and it waits three seconds after their LAST manual scroll (user, 2026-11-18: the three
seconds start when they stop; scrolling again restarts them; 2026-11-16: six was too long). Manual scrolling is a
wheel / trackpad scroll, a finger dragging the page, a scroll key, the scrollbar, and the glide after any of those;
a pointer or finger held down holds the page. Moving the mouse, a click or tap that does not scroll, a chord
lighting up and its own scrolling never hold -- nor does opening or closing a panel, which hands over to the
notation that now leads at once. It never moves while the music is paused or stopped. When the three seconds run
out during playback it returns smoothly to the measure playing NOW, and keeps it genuinely on screen: inside the
window, clear of the sticky header and the compact transport bar, with the next row below it for reading ahead.

It only ever reads ``getBoundingClientRect`` and writes the page scroller's ``scrollTop``: it never touches an
audio element, the follow timeline or the highlight, so it cannot change what is heard or which chord is lit.

While the Lead Sheet is open it also shows a compact Pause / Resume and Stop bar fixed to the bottom of the
window (hidden while the card's own transport row is on screen). Its buttons click the existing controls -- the
sheet's own Pause / Resume button and the card's Stop -- so there is still exactly one transport. The bar belongs
to the Lead Sheet whichever staff the page is following.
"""

from __future__ import annotations

HOLD_MS = 3000
# Bumped whenever the controller's behaviour changes: an open page keeps the copy it installed (one per top
# window) and only a newer version replaces it -- v2 pages kept the 6 s hold and the old spacer after a deploy.
CONTROLLER_VERSION = 4
# Who leads the page when several are open and playing (higher wins; user, 2026-11-16).
LEAD_SHEET_PRIORITY = 10
MELODY_PRIORITY = 20                 # the Practice Melody staff
ORIGINAL_MELODY_PRIORITY = 30        # a Composition's Original Melody (one staff per section)
FOLLOW_ROLES = {"practice-melody": MELODY_PRIORITY, "original-melody": ORIGINAL_MELODY_PRIORITY}

# Plain JS (not an f-string), inserted into the follow surfaces' templates as a value. Streamlit lays out the next
# element where a component's element container ends, and that container keeps the height the component was created
# with -- so a frame that sizes itself to its content (the full-height Lead Sheet, a follow staff) must size the
# boxes between it and that container too, or the next panel is drawn underneath it (measured on dev 68668ef5: the
# Lead Sheet's frame 2396 / 4309 px tall in a 720 px container at 1500 / 390 px; the Original Melody panel below
# started 1644 / 3557 px inside the chart). Re-applied whenever the frame or the container changes size.
FRAME_HOST_FIT_JS = r"""
function lsFitFrameHost(fe, h) {
  try {
    if (!fe || !(h > 0)) return;
    var host = fe.closest && fe.closest('[data-testid="stElementContainer"]');
    if (!host) return;
    var chain = [], el = fe.parentElement;
    while (el && chain.length < 6) { chain.push(el); if (el === host) break; el = el.parentElement; }
    if (chain[chain.length - 1] !== host) return;
    chain.forEach(function (box) {
      if (Math.abs(box.getBoundingClientRect().height - h) <= 1) return;
      // Streamlit's element container is a flex item with a fixed basis (measured: flex 0 0 1130px), which wins
      // over height in its column: the basis must follow the frame too, or a shorter staff leaves a blank below it.
      box.style.setProperty("flex-basis", h + "px", "important");
      box.style.setProperty("height", h + "px", "important");
      box.style.setProperty("min-height", h + "px", "important");
    });
  } catch (e) {}
}
function lsWatchFrameHost(fe, fit) {
  try {
    var host = fe.closest && fe.closest('[data-testid="stElementContainer"]');
    if (host && window.ResizeObserver) new ResizeObserver(fit).observe(host);
  } catch (e) {}
}
"""

# Plain string (not an f-string): it is inserted into the components' f-string templates as a value.
_CONTROLLER_JS = r"""
(function installLeadSheetPageFollow() {
  var V = __V__, HOLD_MS = __HOLD__, LS_PRIORITY = __LS_PRIO__;
  var top;
  try { top = window.top; void top.document.body; } catch (e) { return; }
  if (top.__lsFollow && Number(top.__lsFollow.v) >= V) return;
  // An older controller on this page (an update while the page stayed open): take over its surfaces.
  var inherited = [];
  try { inherited = (top.__lsFollow && top.__lsFollow.providers) || []; } catch (eI) {}
  try { if (top.__lsFollow && top.__lsFollow.destroy) top.__lsFollow.destroy(); } catch (eD) {}
  var doc = top.document;
  var C = { v: V, holdMs: HOLD_MS, lastInteraction: 0, lastKind: "", pointerDown: false,
            selfScrollUntil: 0, providers: inherited.slice(), moves: [], wasSuspended: false, leader: "", seq: 0 };
  function now() { return Date.now(); }

  // ---- the page scroller (Streamlit scrolls stMain; fall back to the document) ----
  function scroller() {
    var sels = ['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]', "section.main"];
    for (var i = 0; i < sels.length; i++) {
      var el = doc.querySelector(sels[i]);
      if (!el) continue;
      var oy = "";
      try { oy = String(top.getComputedStyle(el).overflowY || ""); } catch (e) {}
      if ((oy === "auto" || oy === "scroll" || oy === "overlay") && el.scrollHeight > el.clientHeight + 4) return el;
    }
    return doc.scrollingElement || doc.documentElement;
  }
  function viewTop(sc) {
    if (sc === doc.scrollingElement || sc === doc.documentElement || sc === doc.body) return 0;
    return Math.max(0, sc.getBoundingClientRect().top);
  }
  function viewBottom(sc) {
    var h = top.innerHeight;
    if (sc === doc.scrollingElement || sc === doc.documentElement || sc === doc.body) return h;
    return Math.min(h, sc.getBoundingClientRect().bottom);
  }
  function topInset() {
    try {
      var hd = doc.querySelector('[data-testid="stHeader"]');
      if (!hd) return 0;
      var cs = top.getComputedStyle(hd), r = hd.getBoundingClientRect();
      if ((cs.position === "fixed" || cs.position === "sticky") && cs.display !== "none"
          && cs.visibility !== "hidden" && r.height > 0 && r.bottom > 0 && r.top <= 1) return r.bottom;
    } catch (e) {}
    return 0;
  }
  function bottomInset() {
    var bar = doc.getElementById("ls-mini-transport");
    if (bar && bar.style.display !== "none") return bar.getBoundingClientRect().height + 16;
    return 0;
  }
  // An element's rectangle in the top window, through any number of same-origin iframes.
  function rectInTop(el) {
    try {
      var r = el.getBoundingClientRect();
      var t = r.top, b = r.bottom, l = r.left, rt = r.right, w = el.ownerDocument.defaultView;
      while (w && w !== top) {
        var fe = w.frameElement;
        if (!fe) return null;
        var fr = fe.getBoundingClientRect();
        t += fr.top + (fe.clientTop || 0); b += fr.top + (fe.clientTop || 0);
        l += fr.left + (fe.clientLeft || 0); rt += fr.left + (fe.clientLeft || 0);
        w = w.parent;
      }
      return { top: t, bottom: b, left: l, right: rt };
    } catch (e) { return null; }
  }

  // ---- manual scrolling: hold while the person scrolls, then for HOLD_MS after the LAST manual scroll ----
  // (user, 2026-11-18) There is no limit on how long someone may scroll around the page: the three seconds start
  // when they STOP, and scrolling again before they run out starts them again. What counts as manual scrolling: a
  // wheel / trackpad scroll, a finger dragging the page, a scroll key that moves the page, dragging the scrollbar,
  // and the page still gliding from one of those (touch momentum, a smooth key scroll) -- a pointer or finger held
  // down holds the page however long it stays still. What does not: moving or hovering the mouse, a click or tap that
  // does not scroll the page, a chord lighting up, and this controller's own scrolling.
  C.suspended = function () { return C.pointerDown || (now() - C.lastInteraction < HOLD_MS); };
  C.remainingMs = function () { return C.pointerDown ? HOLD_MS : Math.max(0, HOLD_MS - (now() - C.lastInteraction)); };
  // A page scroll this soon after the person's own input (or after their previous scroll) is still theirs: the
  // glide after a flick, a key's smooth scroll, the scrollbar's arrows.
  var GLIDE_MS = 400;
  C.lastSignal = 0; C.pressScrolled = false;
  function interact(kind) {
    var t = now();
    C.lastInteraction = t; C.lastSignal = t; C.lastKind = kind;
    if (C.pointerDown) C.pressScrolled = true;
    if (t < C.selfScrollUntil) {
      // Stop a return already under way: the person's scroll wins at once.
      C.selfScrollUntil = 0;
      try { var sc = scroller(); sc.scrollTo({ top: sc.scrollTop, behavior: "auto" }); } catch (e) {}
    }
  }
  // Opening or closing a panel (a click / tap on an expander's header) is not scrolling: the page hands over to
  // the notation that now leads at once instead of holding (measured: 6.4 s after closing the Practice Melody),
  // even when the panel's new height makes the page scroll. A drag or wheel that starts on a header still holds.
  function panelToggle(ev) {
    try { var t = ev && ev.target; return !!(t && t.closest && t.closest("summary")); } catch (e) { return false; }
  }
  function press(ev) {
    if (panelToggle(ev)) return;
    C.pointerDown = true; C.pressScrolled = false;
    // a tap that stops the page while it still glides from the person's own scroll is part of that scroll
    if (now() - C.lastSignal < GLIDE_MS) interact("press-stops-glide");
  }
  // Released: the three seconds start now only if this press scrolled the page (a drag, the scrollbar).
  function release(kind) {
    if (!C.pointerDown) return;
    C.pointerDown = false;
    if (C.pressScrolled) interact(kind);
    C.pressScrolled = false;
  }
  var SCROLL_KEYS = { ArrowUp: 1, ArrowDown: 1, PageUp: 1, PageDown: 1, Home: 1, End: 1, " ": 1, Spacebar: 1 };
  function scrollKey(ev) {
    try {
      if (!ev || !SCROLL_KEYS[ev.key] || ev.ctrlKey || ev.metaKey || ev.altKey) return false;
      var t = ev.target, tag = t && t.tagName ? String(t.tagName).toLowerCase() : "";
      return !(tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable));
    } catch (e) { return false; }
  }
  // The page scroller moved: the person's scroll if a press is down or their input was just now; otherwise it is
  // this controller (C.follow), another component or a re-render -- never a reason to hold.
  function pageScrolled(ev) {
    try {
      var sc = scroller();
      if (ev && ev.target !== sc && ev.target !== doc && ev.target !== doc.documentElement) return;
    } catch (e) { return; }
    var t = now();
    if (C.pointerDown || t - C.lastSignal < GLIDE_MS) interact("scroll");
  }
  var seen = new WeakSet();
  function watch(d) {
    if (!d || seen.has(d)) return;
    seen.add(d);
    var opts = { capture: true, passive: true };
    d.addEventListener("wheel", function () { interact("wheel"); }, opts);
    d.addEventListener("touchmove", function () { interact("touchmove"); }, opts);
    // a scroll key only opens the window: the hold starts if the page then really scrolls
    d.addEventListener("keydown", function (ev) { if (scrollKey(ev)) C.lastSignal = now(); }, opts);
    // touch uses the touch events (a finger scrolling the page cancels its pointer at once); mouse / pen the pointer's
    d.addEventListener("touchstart", function (ev) { press(ev); }, opts);
    ["touchend", "touchcancel"].forEach(function (k) {
      d.addEventListener(k, function (ev) { if (!ev.touches || !ev.touches.length) release(k); }, opts);
    });
    d.addEventListener("pointerdown", function (ev) { if (ev.pointerType !== "touch") press(ev); }, opts);
    d.addEventListener("pointerup", function (ev) { if (ev.pointerType !== "touch") release("pointerup"); }, opts);
    // a mouse press that turns into a native drag (selected text, an image) is cancelled while the button is still
    // down: the press lasts until the drag ends
    d.addEventListener("pointercancel", function (ev) { if (ev.pointerType === "pen") release("pointercancel"); }, opts);
    ["dragend", "drop"].forEach(function (k) { d.addEventListener(k, function () { release(k); }, opts); });
    // a release the page never heard (let go outside the window): the next plain move with no button down
    d.addEventListener("pointermove", function (ev) {
      if (C.pointerDown && ev.pointerType === "mouse" && ev.buttons === 0) release("pointermove");
    }, opts);
    if (d === doc) d.addEventListener("scroll", pageScrolled, opts);
  }
  // The page and every same-origin iframe on it (controls live in their own frames).
  function watchAll() {
    watch(doc);
    try {
      doc.querySelectorAll("iframe").forEach(function (f) {
        try { if (f.contentDocument) watch(f.contentDocument); } catch (e) {}
      });
    } catch (e) {}
  }
  C.watch = watch;

  // ---- is the playing chord GENUINELY on screen? (user, 2026-11-18: "a person looking at the screen must clearly
  // see the currently highlighted chord") ----
  // What is drawn at a top-window point, followed down through the frames el sits in: null when it is el itself,
  // otherwise the element covering it there (an overlay, a sticky bar, the page around a frame that clips el).
  function coverAt(el, x, y) {
    var chain = [], w = el.ownerDocument.defaultView;
    while (w && w !== top) { if (!w.frameElement) return null; chain.unshift(w.frameElement); w = w.parent; }
    var d = doc, ox = 0, oy = 0;
    for (var i = 0; i < chain.length; i++) {
      var hit = d.elementFromPoint(x - ox, y - oy);
      if (hit !== chain[i]) return hit || d.documentElement;
      var fr = chain[i].getBoundingClientRect();
      ox += fr.left + (chain[i].clientLeft || 0); oy += fr.top + (chain[i].clientTop || 0);
      d = chain[i].contentDocument;
      if (!d) return null;
    }
    var e = d.elementFromPoint(x - ox, y - oy);
    return (e && (e === el || el.contains(e))) ? null : (e || d.documentElement);
  }
  // The fixed / sticky box a covering element belongs to (top window only), in window coordinates, or null.
  function pinnedBox(e) {
    try {
      for (var n = e; n && n !== doc.body && n !== doc.documentElement; n = n.parentElement) {
        if (n.ownerDocument !== doc) return null;
        var pos = top.getComputedStyle(n).position;
        if (pos === "fixed" || pos === "sticky") { var r = n.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; }
      }
    } catch (e2) {}
    return null;
  }
  // null when el is wholly inside the window between the sticky header and the compact bar and its centre and two
  // inner points show el itself; otherwise { why, pinned } (pinned: the fixed / sticky box covering it, if any).
  C.notVisible = function (el) {
    var r = el && el.isConnected && rectInTop(el);
    if (!r) return { why: "unmapped" };
    var sc = scroller(), vt = viewTop(sc) + topInset(), vb = viewBottom(sc) - bottomInset();
    if (r.top < vt - 1 || r.bottom > vb + 1) return { why: r.bottom <= vt || r.top >= vb ? "outside" : "edge" };
    if (r.left < -1 || r.right > top.innerWidth + 1) return { why: "sideways" };
    // scrolled out of its own frame's box (Karaoke's lyric box scrolls itself): that frame's follower brings it
    // back; moving the page cannot
    try {
      for (var w = el.ownerDocument.defaultView; w && w !== top; w = w.parent) {
        var fe = w.frameElement; if (!fe) break;
        var fr = rectInTop(fe);
        if (fr && (r.top < fr.top - 1 || r.bottom > fr.bottom + 1)) return { why: "clipped" };
      }
    } catch (eF) {}
    var cx = (r.left + r.right) / 2, hgt = r.bottom - r.top, ys = [0.5, 0.25, 0.75];
    for (var i = 0; i < ys.length; i++) {
      var cov = null;
      try { cov = coverAt(el, cx, r.top + hgt * ys[i]); } catch (e) { cov = null; }
      if (cov) return { why: "covered", pinned: pinnedBox(cov) };
    }
    return null;
  };

  // ---- following ----
  function liveProviders() {
    C.providers = C.providers.filter(function (p) {
      try { return p.frame && p.frame.isConnected; } catch (e) { return false; }
    });
    return C.providers;
  }
  // On screen: the frame has a size and is not inside a collapsed expander (a closed <details>).
  function shown(p) {
    try {
      var f = p.frame, r = f.getBoundingClientRect();
      if (r.height < 20 || r.width < 20) return false;
      if (f.closest && f.closest("details:not([open])")) return false;
      var w = f.ownerDocument.defaultView;
      while (w && w !== top) {            // a frame inside a hidden frame is hidden too
        var fe = w.frameElement;
        if (!fe) break;
        var fr = fe.getBoundingClientRect();
        if (fr.height < 20 || fr.width < 20) return false;
        w = w.parent;
      }
      return true;
    } catch (e) { return false; }
  }
  // Has something lit to follow (a melody staff with no lit measure -- an intro bar, a section it does not
  // show -- lets the Lead Sheet lead meanwhile).
  function lit(p) {
    try { return p.hasCurrent ? !!p.hasCurrent() : true; } catch (e) { return false; }
  }
  // The surface that leads the page: open, lit, highest priority; among equals (one staff per section) the one
  // that asked most recently.
  // An active Karaoke Set (user, 2026-11-16): the Lead Sheet if open, else the Karaoke lyrics -- a melody staff
  // never leads then, whatever is on the page.
  function karaokeSetActive() {
    try { return doc.body.getAttribute("data-karaoke-session") === "true"; } catch (e) { return false; }
  }
  function activeProvider() {
    var best = null, karaoke = karaokeSetActive();
    liveProviders().forEach(function (p) {
      if (!shown(p) || !lit(p)) return;
      if (karaoke && (Number(p.priority) || 0) > LS_PRIORITY) return;
      var pr = Number(p.priority) || 0, bp = best ? (Number(best.priority) || 0) : -1;
      if (!best || pr > bp || (pr === bp && (p.lastAt || p.at || 0) >= (best.lastAt || best.at || 0))) best = p;
    });
    return best;
  }
  // The surface whose Pause / Resume the compact bar presses (the Lead Sheet), whichever one leads the page.
  function transportProvider() {
    var best = null;
    liveProviders().forEach(function (p) {
      if (p.transport && (!best || (Number(p.priority) || 0) >= (Number(best.priority) || 0))) best = p;
    });
    return best;
  }
  function uid(p) { return p ? String(p.id) + "#" + String(p.at || 0) : ""; }
  C.register = function (p) {
    liveProviders();
    C.providers = C.providers.filter(function (q) { return q.frame !== p.frame; });
    p.at = now() + (++C.seq) / 1000;
    C.providers.push(p);
    watchAll();
  };
  C.leading = function () { var p = activeProvider(); return p ? p.id : ""; };
  // Extra space under the page's content so the last rows can reach the reading position: an empty block placed
  // as the LAST child of the page scroller itself. Its height is not the room it gives: the full-height Lead Sheet
  // sizes its own iframe past Streamlit's element container, so the page's scroll end is the chart's bottom edge and
  // a block after the content sits behind the chart until it is taller than that overhang (measured: 591 px of
  // spacer, +0 px of scroll). So the block is sized from where the content really ends (the later of the block's
  // own top and the bottom of a registered follow surface's frame) plus the room wanted, and re-sized every tick: if the chart
  // grows, shrinks or closes, the room below stays C.room and never turns into extra blank space. C.room grows by
  // the shortfall only, at most 70 % of the window. Nothing on the page moves or resizes; it takes no clicks/touches.
  C.room = 0;
  C.roomLog = [];
  function spacer(sc) {
    var sp = doc.getElementById("ls-follow-room");
    if (!sp) {
      sp = doc.createElement("div"); sp.id = "ls-follow-room"; sp.setAttribute("aria-hidden", "true");
      sp.style.cssText = "display:block;width:100%;height:0;margin:0;padding:0;border:0;pointer-events:none;flex:none;";
    }
    if (sp.parentNode !== sc || sc.lastElementChild !== sp) sc.appendChild(sp);  // re-attach after a re-render
    var h = 0;
    if (C.room > 0) {
      var origin = sc.getBoundingClientRect().top - sc.scrollTop;   // the scroller's content top, in window terms
      var spTop = sp.getBoundingClientRect().top - origin, end = spTop;
      // only the registered surfaces (the full-height Lead Sheet, melody staves): they are what overhangs, and a
      // fixed / sticky frame elsewhere would otherwise chase the scroll end and grow the block every tick
      liveProviders().forEach(function (p) {
        try {
          // a collapsed panel's frame keeps reporting its old box inside the closed <details>: it is not on the
          // page, so it must not size the room (measured: 2061 / 3632 px of blank after closing the Practice Melody)
          if (!shown(p)) return;
          var f = p.frame; if (!f || !sc.contains(f)) return;
          var r = f.getBoundingClientRect();
          if (r.height > 0 && r.bottom - origin > end) end = r.bottom - origin;
        } catch (e) {}
      });
      h = Math.max(0, Math.round(end + C.room - spTop));
    }
    if (Math.abs((parseFloat(sp.style.height) || 0) - h) > 1) sp.style.height = h + "px";
    return sp;
  }
  function roomBelow(sc, px) {
    var cap = Math.round(0.7 * top.innerHeight);
    var want = Math.min(C.room + Math.ceil(px) + 24, cap);
    if (want <= C.room) return;
    try {
      var before = sc.scrollHeight, wanted = want - C.room;
      C.room = want;
      var sp = spacer(sc);
      C.roomLog.push({ t: now(), wanted: wanted, before: before, after: sc.scrollHeight, room: C.room,
                       spH: Math.round(sp.getBoundingClientRect().height) });
      if (C.roomLog.length > 20) C.roomLog.shift();
    } catch (e) {}
  }
  // Bring el into the reading band (upper part of the window, room below for read-ahead). Returns true if moved.
  C.follow = function (el, opts) {
    opts = opts || {};
    if (!el || !el.isConnected || C.suspended()) return false;
    var r = rectInTop(el);
    if (!r) return false;
    var sc = scroller();
    var vt = viewTop(sc) + topInset(), vb = viewBottom(sc) - bottomInset();
    // something pinned over the chord (an overlay the insets above do not know): keep clear of it as well
    var pin = opts.pinned;
    if (pin && pin.bottom - pin.top < 0.5 * (vb - vt)) {
      if ((pin.top + pin.bottom) / 2 < (vt + vb) / 2) vt = Math.max(vt, pin.bottom + 8);
      else vb = Math.min(vb, pin.top - 8);
    }
    var avail = Math.max(120, vb - vt);
    var bandTop = vt + 0.04 * avail, bandBottom = vt + 0.62 * avail;
    if (!opts.force && r.top >= bandTop && r.bottom <= bandBottom) return false;
    var want = sc.scrollTop + (r.top - (vt + 0.18 * avail));
    // The last rows of a chart near the end of the page: the page cannot scroll far enough to bring them up to
    // the reading position (measured: the chord sat at 91-93 % of the window, under the compact bar, and the
    // page never moved). Give the page just enough room below, once, so it can.
    if (C.room > 0) spacer(sc);
    if (want > sc.scrollHeight - sc.clientHeight + 4) roomBelow(sc, want - (sc.scrollHeight - sc.clientHeight));
    want = Math.max(0, Math.min(want, sc.scrollHeight - sc.clientHeight));
    if (Math.abs(want - sc.scrollTop) < 4) return false;
    C.selfScrollUntil = now() + 1200;
    C.moves.push({ t: now(), from: Math.round(sc.scrollTop), to: Math.round(want), why: opts.why || "" });
    if (C.moves.length > 60) C.moves.shift();
    try { sc.scrollTo({ top: want, behavior: opts.instant ? "auto" : "smooth" }); } catch (e) { sc.scrollTop = want; }
    return true;
  };
  // A surface asks to follow; only the leading surface moves the page.
  C.request = function (id, el, opts) {
    var me = null;
    try {
      var fe = el && el.ownerDocument && el.ownerDocument.defaultView && el.ownerDocument.defaultView.frameElement;
      liveProviders().forEach(function (q) { if (q.frame === fe) me = q; });
    } catch (e) {}
    if (me) me.lastAt = now();
    var p = activeProvider();
    if (p && (me ? p !== me : p.id !== id)) return false;
    return C.follow(el, opts);
  };

  // ---- compact transport while the Lead Sheet is open ----
  var BAR_CSS = "position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:999990;display:none;"
    + "gap:8px;padding:6px;border-radius:999px;background:rgba(15,23,42,.92);box-shadow:0 6px 24px rgba(15,23,42,.28);"
    + "align-items:center;font-family:system-ui,-apple-system,Segoe UI,sans-serif;";
  var BTN_CSS = "border:0;border-radius:999px;padding:9px 16px;font-size:15px;font-weight:600;cursor:pointer;"
    + "min-height:44px;min-width:44px;white-space:nowrap;line-height:1;";
  function cardTransportDoc() {
    try {
      var f = doc.querySelector(".st-key-backing_card_transport_row iframe");
      return f && f.contentDocument;
    } catch (e) { return null; }
  }
  function visibleInWindow(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.height > 0 && r.bottom > topInset() + 8 && r.top < top.innerHeight - 8;
  }
  function ensureBar() {
    var bar = doc.getElementById("ls-mini-transport");
    if (bar) return bar;
    bar = doc.createElement("div");
    bar.id = "ls-mini-transport";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Playback");
    bar.style.cssText = BAR_CSS;
    var pz = doc.createElement("button");
    pz.type = "button"; pz.id = "ls-mini-pause"; pz.style.cssText = BTN_CSS + "background:#22c55e;color:#04220f;";
    var stop = doc.createElement("button");
    stop.type = "button"; stop.id = "ls-mini-stop"; stop.style.cssText = BTN_CSS + "background:#f1f5f9;color:#0f172a;";
    stop.textContent = "■ Stop Backing Track";   // what it stops (Key Cycling has its own "Stop Key Cycling")
    stop.setAttribute("aria-label", "Stop Backing Track");
    pz.addEventListener("click", function () {
      var p = transportProvider();
      if (cardStarting() || keyCyclingOn()) { syncBar(); return; }
      try { if (p && p.pauseButton && p.pauseButton()) p.pauseButton().click(); } catch (e) {}
      setTimeout(syncBar, 120);
    });
    stop.addEventListener("click", function () {
      var d = cardTransportDoc(), b = d && d.getElementById("btn");
      try { if (b && b.getAttribute("data-state") !== "stopped" && !b.disabled) b.click(); } catch (e) {}
      setTimeout(syncBar, 120);
    });
    bar.appendChild(pz); bar.appendChild(stop);
    doc.body.appendChild(bar);
    return bar;
  }
  // Loading or counting in: the card offers only Stop (its take is held), so the bar does the same --
  // a Pause / Resume press there reached a player the count-in holds and was silently lost.
  function cardStarting() {
    var d = cardTransportDoc(), b = d && d.getElementById("btn");
    return !!b && b.getAttribute("data-state") === "starting";
  }
  // Key Cycling on (its console, with its own Pause / Resume, is on the page only while a cycle is active): the
  // bar offers Stop only. Temporary (user, 2026-11-15) until the Key Cycling transport fixes land: a Stop pressed
  // ~3 s after a bar Resume was undone for 2-3 s (4/6) by that Resume's delayed command.
  function keyCyclingOn() {
    return !!doc.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]');
  }
  function syncBar() {
    var p = transportProvider();
    var bar = doc.getElementById("ls-mini-transport");
    if (!p || !p.transport) { if (bar) bar.style.display = "none"; return; }
    bar = ensureBar();
    var d = cardTransportDoc(), card = d && d.getElementById("btn");
    var stopped = !card || card.getAttribute("data-state") === "stopped";
    var row = doc.querySelector(".st-key-backing_card_transport_row");
    var pb = null;
    try { pb = p.pauseButton && p.pauseButton(); } catch (e) {}
    var show = !!pb && !stopped && !visibleInWindow(row);
    bar.style.display = show ? "flex" : "none";
    if (!show) return;
    var paused = false;
    try { paused = !p.playing(); } catch (e) {}
    var pz = doc.getElementById("ls-mini-pause");
    var stopBtn = doc.getElementById("ls-mini-stop");
    if (stopBtn) {
      if (keyCyclingOn()) stopBtn.title = "Stops playback. The next Play restarts Key Cycling from its first key.";
      else stopBtn.removeAttribute("title");
    }
    // Hidden AND disabled: Key Cycling's page-wide click listener matches any "Pause" / "Resume" button by its label,
    // so even a hidden button's click would reach Key Cycling; a disabled button sends no click at all.
    var only = cardStarting() || keyCyclingOn();
    pz.style.display = only ? "none" : "";
    pz.disabled = only;
    var want = paused ? "▶ Resume" : "⏸ Pause";
    if (pz.textContent !== want) pz.textContent = want;
    pz.setAttribute("aria-label", paused ? "Resume" : "Pause");
  }

  // ---- the clock: return after the hold, keep the bar in step ----
  var timer = top.setInterval(function () {
    try {
      watchAll();
      var s = C.suspended();
      // The leading surface changed (the melody opened, closed, or another section's staff lit up): go to
      // its playing measure now, unless the person is scrolling (then the return after the hold does it).
      var lead = activeProvider(), leadId = uid(lead);
      if (leadId !== C.leader) {
        C.leader = leadId;
        if (lead && !s) {
          var playingNow = false;
          try { playingNow = !!lead.playing(); } catch (eP) {}
          var cur = null;
          try { cur = lead.current(); } catch (eC) {}
          if (playingNow && cur) C.follow(cur, { why: "switch" });
        }
      }
      if (s) { C.wasSuspended = true; }
      else if (C.wasSuspended) {
        var p = activeProvider();
        if (p && p.playing()) {
          C.wasSuspended = false;
          var el = p.current();
          if (el) C.follow(el, { why: "return" });
        }
        // Paused / stopped: stay put; the next measure change after Resume follows (no hold debt).
        else if (p) C.wasSuspended = false;
      }
      // Catch-up: playing, not held, no move of ours in flight, and the playing measure not GENUINELY visible --
      // outside the window, cut by its edge, under the header / the compact bar / an overlay -> bring it into the
      // reading position now. Measured 2026-11-17 (Voice, Blackbird, 360 px): every missed sample was bar 1 just after
      // Play / Play again / a return / a reload -- its highlight was set before the page followed, so the page
      // waited ~2 s for the next chord change with the playing bar below the window. A measure clearly on screen is
      // untouched (no nudging while it can be read).
      if (!s && lead && now() >= C.selfScrollUntil) {
        try {
          if (lead.playing()) {
            var ce = lead.current(), nv = ce && C.notVisible(ce);
            if (nv && (nv.why === "outside" || nv.why === "edge" || nv.why === "covered")) {
              C.lastHidden = { t: now(), why: nv.why };
              C.follow(ce, { why: "catchup-" + nv.why, force: true, pinned: nv.pinned });
            }
          }
        } catch (eCu) {}
      }
      if (C.room > 0) spacer(scroller());   // keep the room below at C.room as the chart / page changes size
      syncBar();
    } catch (e) {}
  }, 250);
  C.destroy = function () {
    try { top.clearInterval(timer); } catch (e) {}
    var bar = doc.getElementById("ls-mini-transport");
    if (bar) bar.remove();
    var room = doc.getElementById("ls-follow-room");
    if (room) room.remove();
  };
  top.__lsFollow = C;
  watchAll();
})();
"""


def page_follow_controller_js() -> str:
    """The controller installer, safe to include in any number of same-origin iframes (first one wins).

    The controller runs in the top window's own realm (a script element added there), so it keeps working when
    the iframe that installed it is closed or remounted.
    """
    import json

    code = (
        _CONTROLLER_JS.replace("__V__", str(CONTROLLER_VERSION))
        .replace("__HOLD__", str(HOLD_MS))
        .replace("__LS_PRIO__", str(LEAD_SHEET_PRIORITY))
    )
    return (
        "(function () { try { var t = window.top;"
        f" if (t.__lsFollow && Number(t.__lsFollow.v) >= {CONTROLLER_VERSION}) return;"
        " var s = t.document.createElement('script'); s.textContent = "
        + json.dumps(code).replace("</", "<\\u002f")
        + "; t.document.head.appendChild(s); s.remove(); } catch (e) {} })();"
    )
