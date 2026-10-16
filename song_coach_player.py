"""Song-Aware Coaching (S5) — the in-page practice-loop player.

A compact transport inside the challenge card: Play / Pause / Stop, a seamless loop of the
practice bars, a practice tempo, a volume control, and the bars / meter / concert Practice Key
on display. The challenge text and example notation stay on screen while it plays.

Isolation:

- **Its own playback.** The loop plays through the Web Audio API inside this component's own
  iframe — no HTML audio element (Key Cycling's watchers attach to those), none of its globals,
  no Backing Studio transport, cache or session keys. Leaving the tab, or any change to the
  song, chart, Practice Key or bars, removes or replaces the iframe and its audio stops.
- **Only coaching state is written**: the tempo and loop-range preferences in the coaching
  record (through the same user-event save path as every coaching choice) and a session-only
  diagnostic. Practice Key, Practice Focus, instrument, source, Backing, Key Cycling, Missions,
  Motif and SBI state are read at most, never written.
- **One loop at a time.** Players talk over a same-origin ``BroadcastChannel``: starting one
  stops any other, and a newly mounted player for a different loop stops a lingering old one,
  so rapid navigation can never leave two loops sounding.
- **Stable across reruns.** The player's HTML depends only on the loop (its audio and labels),
  so a rerun or a change to a challenge that loops the same bars leaves it playing.
- **Never starts by itself (S6)** — except straight after the musician changes the tempo of the
  loop that was playing: the tempo callback leaves a one-shot signal, rendered *after* the
  player for that run only, and the new player resumes only for that same range when the old
  one was playing a moment earlier. A refresh, returning to the tab or navigating between
  challenges never sends the signal, so audio is never revived.
"""

from __future__ import annotations

import base64
import html
import json
from typing import Any, Callable

from song_coach_state import LOOP_RANGE_CHALLENGE, LOOP_RANGE_SELECTION, commit, with_loop

LOOP_DIAG_KEY = "_song_coach_loop_diag"  # session-only: what the loop player drew this run
LOOP_RESUME_KEY = "_song_coach_loop_resume"  # session-only one-shot: the musician just changed the tempo
W_LOOP_BPM = "song_coach_loop_bpm"
W_LOOP_RANGE = "song_coach_loop_range"
PLAYER_HEIGHT = 132
RESUME_WINDOW_MS = 4000
RANGE_LABELS = {LOOP_RANGE_CHALLENGE: "This challenge's bars", LOOP_RANGE_SELECTION: "Whole selection"}
SCOPE_TEXT = {LOOP_RANGE_CHALLENGE: "Looping this challenge's bars", LOOP_RANGE_SELECTION: "Looping the whole selection"}
CHANNEL = "song-coach-loop"


# --------------------------------------------------------------------------- pure helpers


def loop_bars(plan: Any, challenge: Any, loop_range: str) -> tuple[int, int]:
    """Section bars to loop: the challenge's practice bars, or the plan's whole selection."""
    if loop_range == LOOP_RANGE_SELECTION or challenge is None:
        return int(plan.start_bar), int(plan.end_bar)
    return int(challenge.loop_start), int(challenge.loop_end)


def song_style(session: Any, ctx: Any) -> str:
    """The arranger groove: a catalog song's own groove (as Backing Studio's "Auto"), else the
    coaching style mapped. Read-only."""
    from song_coach_backing import arranger_style

    record = None
    try:
        from song_coach_context import SOURCE_CATALOG, live_catalog_record

        if ctx.source_kind == SOURCE_CATALOG:
            record = live_catalog_record(session) or None
    except ImportError:
        record = None
    return arranger_style(ctx.style, record)


def song_bpm(ctx: Any) -> int:
    from song_coach_backing import DEFAULT_BPM, clamp_bpm

    return clamp_bpm(getattr(ctx, "bpm", 0) or DEFAULT_BPM)


_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{color-scheme:light dark;--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#7c3aed;--btn:#ffffff}
@media (prefers-color-scheme:dark){:root{--bg:#111827;--fg:#e5e7eb;--muted:#9ca3af;--line:#374151;--accent:#a78bfa;--btn:#1f2937}}
html,body{margin:0;padding:0;background:transparent;font-family:"Source Sans Pro",system-ui,sans-serif;color:var(--fg)}
.scl{border:1px solid var(--line);border-radius:12px;padding:8px 12px;background:var(--bg)}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
button{font:inherit;font-size:14px;border:1px solid var(--line);background:var(--btn);color:var(--fg);border-radius:8px;padding:4px 12px;cursor:pointer}
button:disabled{opacity:.45;cursor:default}
button.on{border-color:var(--accent);color:var(--accent)}
.vol{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:13px;margin-left:auto}
.vol input{width:96px;accent-color:var(--accent)}
.meta{color:var(--muted);font-size:13px;margin-top:6px}
.meta .scope{color:var(--fg);font-weight:600}
.now{font-size:14px;margin-top:2px}
.now b{color:var(--accent)}
.hint{color:var(--muted);font-size:12px}
</style></head><body>
<div class="scl" data-song-coach-loop="__SIG__">
  <div class="row">
    <button id="play" title="Play the loop">&#9654; Play</button>
    <button id="pause" title="Pause" disabled>&#10074;&#10074; Pause</button>
    <button id="stop" title="Stop and go back to the first bar" disabled>&#9632; Stop</button>
    <label class="vol">Volume <input id="vol" type="range" min="0" max="100" value="80" aria-label="Loop volume"></label>
  </div>
  <div class="meta"><b class="scope">__SCOPE__</b> &middot; __META__</div>
  <div class="now"><span id="pos">__FIRST__</span> &middot; <b id="chord">__FIRST_CHORD__</b> <span id="state" class="hint">Stopped</span></div>
</div>
<script>
(function () {
  "use strict";
  var CFG = __CFG__;
  var B64 = "__B64__";
  var ctx = null, gain = null, buffer = null, decoding = null, src = null;
  var startedAt = 0, offset = 0, state = "stopped", wantPlay = false, raf = 0;
  var $ = function (id) { return document.getElementById(id); };
  var ME = Math.random().toString(36).slice(2) + Date.now().toString(36);
  var bus = null;
  try { bus = new BroadcastChannel("__CHANNEL__"); } catch (e) { bus = null; }
  function tell(type) { try { if (bus) bus.postMessage({type: type, id: ME, sig: CFG.sig, range: CFG.range}); } catch (e) {} }
  var LABELS = {stopped: "Stopped", loading: "Loading…", playing: "Playing", paused: "Paused", error: "Audio unavailable"};

  function setState(s) {
    state = s;
    $("state").textContent = LABELS[s] || s;
    $("play").disabled = (s === "playing" || s === "loading");
    $("pause").disabled = (s !== "playing");
    $("stop").disabled = (s === "stopped");
    $("play").classList.toggle("on", s === "playing");
  }
  function ensureCtx() {
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      ctx = new AC();
      gain = ctx.createGain();
      gain.gain.value = volume() / 100;
      gain.connect(ctx.destination);
    }
    return ctx;
  }
  function ensureBuffer() {
    if (buffer) return Promise.resolve(buffer);
    if (!decoding) {
      var bin = atob(B64), bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      decoding = new Promise(function (resolve, reject) {
        ensureCtx().decodeAudioData(bytes.buffer, resolve, reject);
      }).then(function (b) { buffer = b; return b; });
    }
    return decoding;
  }
  function elapsed() {
    if (state === "playing" && ctx) return ctx.currentTime - startedAt;
    return offset;
  }
  function stopSource() {
    if (src) {
      try { src.stop(); } catch (e) {}
      try { src.disconnect(); } catch (e) {}
      src = null;
    }
  }
  function startSource() {
    stopSource();
    src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    src.loopStart = 0;
    src.loopEnd = buffer.duration;
    src.connect(gain);
    var from = offset % buffer.duration;
    startedAt = ctx.currentTime - offset;
    src.start(0, from);
    setState("playing");
    remember(true);
    tell("play");
    draw();
  }
  function play() {
    wantPlay = true;
    if (state === "playing" || state === "loading") return;
    setState("loading");
    var c;
    try { c = ensureCtx(); } catch (e) { setState("error"); return; }
    var resumed = c.resume ? c.resume() : Promise.resolve();
    Promise.all([resumed, ensureBuffer()]).then(function () {
      if (!wantPlay) { setState(offset > 0 ? "paused" : "stopped"); return; }
      if (c.state !== "running") { setState(offset > 0 ? "paused" : "stopped"); return; }
      startSource();
    }, function () { setState("error"); });
  }
  function pause() {
    wantPlay = false;
    if (state === "playing") {
      offset = elapsed();
      stopSource();
      setState("paused");
      remember(false);
      draw();
    }
  }
  function stop() {
    wantPlay = false;
    stopSource();
    offset = 0;
    if (state !== "loading") setState("stopped");
    remember(false);
    draw();
  }
  function where(t) {
    var pos = ((t % CFG.loop) + CFG.loop) % CFG.loop;
    var bar = Math.min(CFG.bars - 1, Math.floor(pos / CFG.bar + 1e-9));
    var label = CFG.events.length ? CFG.events[0][2] : "";
    for (var i = 0; i < CFG.events.length; i++) {
      if (pos + 1e-6 >= CFG.events[i][0]) label = CFG.events[i][2];
    }
    return {bar: CFG.first + bar, chord: label};
  }
  function draw() {
    cancelAnimationFrame(raf);
    var w = where(elapsed());
    $("pos").textContent = "Bar " + w.bar + " (" + (w.bar - CFG.first + 1) + " of " + CFG.bars + ")";
    $("chord").textContent = w.chord || "N.C.";
    if (state === "playing") raf = requestAnimationFrame(draw);
  }
  function volume() {
    var v = Number($("vol").value);
    return isFinite(v) ? v : 80;
  }
  try {
    var saved = window.localStorage.getItem("songCoachLoopVolume");
    if (saved !== null && saved !== "") $("vol").value = String(Math.max(0, Math.min(100, Number(saved))));
  } catch (e) {}
  $("vol").addEventListener("input", function () {
    if (gain && ctx) gain.gain.setTargetAtTime(volume() / 100, ctx.currentTime, 0.015);
    try { window.localStorage.setItem("songCoachLoopVolume", String(volume())); } catch (e) {}
  });
  function remember(playing) {
    try {
      if (playing) window.sessionStorage.setItem("songCoachLoopPlaying", JSON.stringify({range: CFG.range, t: Date.now()}));
      else window.sessionStorage.removeItem("songCoachLoopPlaying");
    } catch (e) {}
  }
  $("play").addEventListener("click", play);
  $("pause").addEventListener("click", pause);
  $("stop").addEventListener("click", stop);
  if (bus) {
    bus.onmessage = function (ev) {
      var m = ev && ev.data || {};
      if (!m.id || m.id === ME) return;
      if (m.type === "ping") { tell("pong:" + state); return; }
      if (m.type === "resume") { tryResume(m); return; }
      // Another loop started, or a player for a different loop appeared: this one gives way.
      if (m.type === "play" || (m.type === "mount" && m.sig !== CFG.sig)) {
        if (state === "playing" || state === "loading" || state === "paused") stop();
      }
    };
  }
  window.addEventListener("pagehide", function () {
    try {
      if (state === "playing") window.sessionStorage.setItem("songCoachLoopPlaying", JSON.stringify({range: CFG.range, t: Date.now()}));
    } catch (e) {}
    var was = state;
    stopSource();
    try { if (ctx) ctx.close(); } catch (e) {}
    state = "stopped";
    tell(was === "playing" ? "stopped-on-leave" : "left");
    try { if (bus) bus.close(); } catch (e) {}
  });
  window.__songCoachLoop = {
    sig: CFG.sig, range: CFG.range, loopSeconds: CFG.loop, barSeconds: CFG.bar, id: ME, scope: CFG.scope,
    get state() { return state; },
    get elapsed() { return elapsed(); },
    get loops() { return Math.floor(elapsed() / CFG.loop); },
    get position() { return where(elapsed()); },
    get volume() { return volume(); },
    get contextState() { return ctx ? ctx.state : "none"; },
    get bufferSeconds() { return buffer ? buffer.duration : 0; },
    play: play, pause: pause, stop: stop
  };
  // Resume only on the one-shot tempo signal for this same range, if it was just playing.
  function tryResume(token) {
    try {
      if (!token || token.range !== CFG.range || Date.now() - Number(token.t || 0) > __RESUME_MS__) return;
      var prev = JSON.parse(window.sessionStorage.getItem("songCoachLoopPlaying") || "null");
      window.sessionStorage.removeItem("songCoachLoopResume");
      if (prev && prev.range === CFG.range && Date.now() - Number(prev.t || 0) < __RESUME_MS__) play();
    } catch (e) {}
  }
  try { tryResume(JSON.parse(window.sessionStorage.getItem("songCoachLoopResume") || "null")); } catch (e) {}
  tell("mount");
  setState(state);
  draw();
})();
</script></body></html>"""


_SIGNAL = """<!doctype html><html><head><meta charset="utf-8"></head><body><script>
(function () {
  var token = {type: "resume", id: "tempo-signal", range: "__RANGE__", t: Date.now()};
  try { window.sessionStorage.setItem("songCoachLoopResume", JSON.stringify(token)); } catch (e) {}
  try { var bus = new BroadcastChannel("__CHANNEL__"); bus.postMessage(token); bus.close(); } catch (e) {}
})();
</script></body></html>"""


def resume_signal_html(range_key: str) -> str:
    """One-shot document telling the player for ``range_key`` that the tempo just changed."""
    return _SIGNAL.replace("__RANGE__", html.escape(range_key)).replace("__CHANNEL__", CHANNEL)


def player_html(loop: Any, *, chord_label: Callable[[str], str] | None = None, style_label: str = "",
                scope: str = LOOP_RANGE_CHALLENGE) -> str:
    """The self-contained player for ``loop`` (deterministic for the same loop and labels)."""
    req = loop.request
    label = chord_label or (lambda c: c)
    events = [[round(ev.start, 6), round(ev.end, 6), label(ev.chord) if ev.chord else "N.C."] for ev in loop.events]
    cfg = {
        "sig": loop.signature, "range": req.range_key(), "loop": round(loop.loop_seconds, 6),
        "bar": round(loop.bar_seconds, 6), "bars": req.bar_count, "first": req.start_bar, "events": events,
        "scope": scope,
    }
    bars = f"Bar {req.start_bar}" if req.start_bar == req.end_bar else f"Bars {req.start_bar}–{req.end_bar}"
    meta = (f"{bars} · {req.meter} · {req.bpm} BPM · Practice Key {req.concert_key} (concert)"
            + (f" · {style_label} feel" if style_label else ""))
    first = events[0][2] if events else "N.C."
    out = _TEMPLATE
    for token, value in (
        ("__SIG__", html.escape(loop.signature)),
        ("__SCOPE__", html.escape(SCOPE_TEXT.get(scope, SCOPE_TEXT[LOOP_RANGE_CHALLENGE]))),
        ("__CHANNEL__", CHANNEL),
        ("__META__", html.escape(meta)),
        ("__FIRST__", html.escape(f"Bar {req.start_bar} (1 of {req.bar_count})")),
        ("__FIRST_CHORD__", html.escape(first)),
        ("__RESUME_MS__", str(RESUME_WINDOW_MS)),
        ("__CFG__", json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")),
        ("__B64__", base64.b64encode(loop.wav).decode("ascii")),
    ):
        out = out.replace(token, value)
    return out


# --------------------------------------------------------------------------- user actions


def _current(session: Any, ctx: Any) -> Any:
    from song_coach_ui import current

    return current(session, ctx)


def on_loop_tempo(session: Any, ctx: Any) -> None:
    from song_coach_backing import clamp_bpm

    rec = _current(session, ctx)
    if rec.plan is None:
        return
    raw = session.get(W_LOOP_BPM)
    bpm = clamp_bpm(raw, song_bpm(ctx)) if raw else 0
    bpm = 0 if bpm == song_bpm(ctx) else bpm
    if bpm == rec.state.loop_bpm:
        return
    session[LOOP_RESUME_KEY] = True  # the very next render may carry on playing (same bars)
    commit(session, with_loop(rec.state, bpm=bpm), interaction="loop_tempo")


def on_loop_range(session: Any, ctx: Any) -> None:
    rec = _current(session, ctx)
    if rec.plan is None:
        return
    choice = str(session.get(W_LOOP_RANGE) or LOOP_RANGE_CHALLENGE)
    if choice == rec.state.loop_range:
        return
    commit(session, with_loop(rec.state, loop_range=choice), interaction="loop_range")


# --------------------------------------------------------------------------- rendering


def render_practice_loop(st: Any, session: Any, ctx: Any, rec: Any, challenge: Any,
                         chord_label: Callable[[str], str] | None = None) -> None:
    """The practice-loop block for ``challenge`` (controls, then the player or why not)."""
    from song_coach_backing import TEMPO_MAX, TEMPO_MIN, check_loop, clamp_bpm, loop_request, render_loop

    state, plan = rec.state, rec.plan
    default = song_bpm(ctx)
    bpm = clamp_bpm(state.loop_bpm or default, default)  # a damaged record never breaks the slider
    resume = bool(session.pop(LOOP_RESUME_KEY, False)) if hasattr(session, "pop") else False
    if session.get(W_LOOP_BPM) != bpm:
        session[W_LOOP_BPM] = bpm
    if session.get(W_LOOP_RANGE) != state.loop_range:
        session[W_LOOP_RANGE] = state.loop_range
    st.markdown("**🎧 Practice loop**")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.radio("Loop", list(RANGE_LABELS), format_func=lambda k: RANGE_LABELS[k], horizontal=True, key=W_LOOP_RANGE,
                 on_change=on_loop_range, args=(session, ctx), label_visibility="collapsed")
    with c2:
        st.slider("Practice tempo (BPM)", TEMPO_MIN, TEMPO_MAX, key=W_LOOP_BPM, on_change=on_loop_tempo,
                  args=(session, ctx), help=f"The song's tempo is {default} BPM.")
    start, end = loop_bars(plan, challenge, state.loop_range)
    style = song_style(session, ctx)
    request = loop_request(ctx, rec.scope, start_bar=start, end_bar=end, bpm=bpm, style=style, level=plan.level)
    diag: dict[str, Any] = {
        "scope": state.loop_range,
        "signature": request.signature(), "range_key": request.range_key(), "bars": [request.start_bar, request.end_bar],
        "tokens": list(request.bars), "meter": request.meter, "bpm": request.bpm, "style": request.style,
        "concert_key": request.concert_key, "identity": request.identity, "refusal": "",
    }
    refusal = check_loop(request)
    if refusal is not None:
        diag["refusal"] = refusal.kind
        session[LOOP_DIAG_KEY] = diag
        st.info(refusal.message)
        return
    loop = render_loop(request)
    diag.update({"seconds": round(loop.loop_seconds, 4), "bar_seconds": round(loop.bar_seconds, 6),
                 "events": [[e.start, e.end, e.chord] for e in loop.events], "passes": loop.passes})
    session[LOOP_DIAG_KEY] = diag
    try:
        import streamlit.components.v1 as components

        components.html(player_html(loop, chord_label=chord_label, style_label=style, scope=state.loop_range),
                        height=PLAYER_HEIGHT)
        if resume:  # after the player, so the player keeps its place in the page
            components.html(resume_signal_html(request.range_key()), height=0)
        diag["resume_signal"] = resume
    except Exception:  # pragma: no cover - never fall back to an HTML audio element (Key Cycling watches those)
        st.caption("The practice loop player isn't available here.")


__all__ = [
    "LOOP_DIAG_KEY",
    "LOOP_RESUME_KEY",
    "PLAYER_HEIGHT",
    "RANGE_LABELS",
    "CHANNEL",
    "RESUME_WINDOW_MS",
    "SCOPE_TEXT",
    "W_LOOP_BPM",
    "W_LOOP_RANGE",
    "loop_bars",
    "on_loop_range",
    "on_loop_tempo",
    "player_html",
    "render_practice_loop",
    "resume_signal_html",
    "song_bpm",
    "song_style",
]
