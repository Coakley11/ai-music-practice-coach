"""One page-scroll controller for everything that follows the music down the page (M4).

The Backing Lead Sheet is drawn at its full height (no inner scroll box), so following the music means moving
the *page*. Two surfaces want that: the Lead Sheet (the current chord) and the melody staff -- the Practice Melody,
or a Composition's Original Melody, one staff per section (the current measure). Each lives in its own
components.html iframe, so they cannot share a Python object; instead the first iframe that loads installs a
single controller on the top window (``window.top.__lsFollow``) and every surface registers with it and asks it
to follow. Only one surface leads at a time (user, 2026-11-14): a melody staff that is open on screen and has the
playing measure lit (its measures are aligned to the Backing timeline) leads; otherwise the Lead Sheet; otherwise
nothing moves the page. Collapsing the melody hands the page back to the Lead Sheet at once, and among several
section staves the one that lit a measure most recently leads. A melody with no measure alignment (an uploaded
PDF, a staff without a timeline) never registers, so it never claims the page.

That is the only code that moves the page, and it holds still for six seconds after any
manual scroll, touch, key or click (each new one restarts the six seconds), never moves while a pointer is down,
and never moves while the music is paused or stopped. When the six seconds run out during playback it returns
smoothly to the current measure.

It only ever reads ``getBoundingClientRect`` and writes the page scroller's ``scrollTop``: it never touches an
audio element, the follow timeline or the highlight, so it cannot change what is heard or which chord is lit.

While the Lead Sheet is open it also shows a compact Pause / Resume and Stop bar fixed to the bottom of the
window (hidden while the card's own transport row is on screen). Its buttons click the existing controls -- the
sheet's own Pause / Resume button and the card's Stop -- so there is still exactly one transport. The bar belongs
to the Lead Sheet whichever staff the page is following.
"""

from __future__ import annotations

HOLD_MS = 6000
CONTROLLER_VERSION = 2
# Who leads the page when both are open and playing (higher wins).
LEAD_SHEET_PRIORITY = 10
MELODY_PRIORITY = 20

# Plain string (not an f-string): it is inserted into the components' f-string templates as a value.
_CONTROLLER_JS = r"""
(function installLeadSheetPageFollow() {
  var V = __V__, HOLD_MS = __HOLD__;
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
      var t = r.top, b = r.bottom, w = el.ownerDocument.defaultView;
      while (w && w !== top) {
        var fe = w.frameElement;
        if (!fe) return null;
        var fr = fe.getBoundingClientRect();
        t += fr.top + (fe.clientTop || 0); b += fr.top + (fe.clientTop || 0);
        w = w.parent;
      }
      return { top: t, bottom: b };
    } catch (e) { return null; }
  }

  // ---- manual interaction: hold for HOLD_MS after the last one ----
  C.suspended = function () { return C.pointerDown || (now() - C.lastInteraction < HOLD_MS); };
  C.remainingMs = function () { return C.pointerDown ? HOLD_MS : Math.max(0, HOLD_MS - (now() - C.lastInteraction)); };
  function interact(kind) {
    C.lastInteraction = now(); C.lastKind = kind;
    if (now() < C.selfScrollUntil) {
      // Stop a return already under way: the person's scroll wins at once.
      C.selfScrollUntil = 0;
      try { var sc = scroller(); sc.scrollTo({ top: sc.scrollTop, behavior: "auto" }); } catch (e) {}
    }
  }
  var KINDS = ["wheel", "touchstart", "touchmove", "keydown"];
  var seen = new WeakSet();
  function watch(d) {
    if (!d || seen.has(d)) return;
    seen.add(d);
    var opts = { capture: true, passive: true };
    KINDS.forEach(function (k) { d.addEventListener(k, function () { interact(k); }, opts); });
    d.addEventListener("pointerdown", function () { C.pointerDown = true; interact("pointerdown"); }, opts);
    ["pointerup", "pointercancel"].forEach(function (k) {
      d.addEventListener(k, function () { C.pointerDown = false; interact(k); }, opts);
    });
    d.addEventListener("touchend", function () { C.pointerDown = false; interact("touchend"); }, opts);
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
  function activeProvider() {
    var best = null;
    liveProviders().forEach(function (p) {
      if (!shown(p) || !lit(p)) return;
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
    var avail = Math.max(120, vb - vt);
    var bandTop = vt + 0.04 * avail, bandBottom = vt + 0.62 * avail;
    if (r.top >= bandTop && r.bottom <= bandBottom) return false;
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
    + "min-height:40px;white-space:nowrap;line-height:1;";
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
    stop.textContent = "■ Stop";
    pz.addEventListener("click", function () {
      var p = transportProvider();
      if (cardStarting()) { syncBar(); return; }
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
    pz.style.display = cardStarting() ? "none" : "";
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
        // Paused / stopped: stay put; the next measure change after Resume follows (no 6 s debt).
        else if (p) C.wasSuspended = false;
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

    code = _CONTROLLER_JS.replace("__V__", str(CONTROLLER_VERSION)).replace("__HOLD__", str(HOLD_MS))
    return (
        "(function () { try { var t = window.top;"
        f" if (t.__lsFollow && Number(t.__lsFollow.v) >= {CONTROLLER_VERSION}) return;"
        " var s = t.document.createElement('script'); s.textContent = "
        + json.dumps(code).replace("</", "<\\u002f")
        + "; t.document.head.appendChild(s); s.remove(); } catch (e) {} })();"
    )
