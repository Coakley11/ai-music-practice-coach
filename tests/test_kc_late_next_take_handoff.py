"""A pass that ends before its next take arrives starts that take the moment it arrives.

Browser runs 2026-11-20 (Voice, Lead Sheet On, 1280 px; dev 0c679a6f and the Voice candidate
7eaa81a0 alike): the next key's take was synthesized within a second of Play, but it reached the
player only ~159 s later. The first pass ended at ~33 s with nothing to switch to; the page waited
~90 s, gave up, latched a pause and posted a recovery ack Python never received. When the take did
arrive the ended pass never started it: Key Cycling sat silent at 1 / 12 until Next was pressed.

Two fixes, tested here:
* The page asks Python for the take as soon as a pass ends without one (a ``need_next`` ack, which
  only triggers a rerun) and keeps waiting while the cycle plays, so a late take starts on arrival.
  Stop / Pause end that wait: a take arriving afterwards never starts behind them.
* Python takes a ``need_next`` ack without moving the key, and the prefetch hands a synthesized take
  to the player first instead of queueing it behind takes not yet made.

The page tests run the real bridge on a test origin with real (silent) takes, the way the browser
receives Python's commands (``__kcApplyCmd``).
"""
from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

import backing_key_cycle as kc
import backing_key_cycle_handoff as kch
from tests.test_key_cycle_pause_reports_sounding_key import _silent_wav

_ROOT = Path(kc.__file__).resolve().parent
_SEQ = ["Am", "Dm", "Gm", "Cm", "Fm", "Bbm"]  # Circle of Fourths ascending from Am
_URL = {k: f"app/static/kc/{k.lower()}.wav" for k in _SEQ}


def _cmd(epoch: int, current: str, nxt: str = "", **extra) -> dict:
    return dict({
        "enabled": True, "epoch": epoch, "cycleId": "cyc-H", "sequence": list(_SEQ),
        "currentUrl": _URL[current], "sounding": current, "currentSounding": current,
        "nextUrl": _URL[nxt] if nxt else "", "nextSounding": nxt,
        "liveUrls": [u for u in (_URL[current], _URL[nxt] if nxt else "") if u],
        "autoplay": False, "forcePlay": False,
    }, **extra)


_PARENT = ('<html><body><div class="st-key-backing_key_cycle_pause_btn"><button><p>Pause</p></button></div>'
           '<iframe id="kc-bridge"></iframe></body></html>')

_STATE_JS = """() => { const d = window.__kcDual || {};
  const bufs = ['kc-buf-0', 'kc-buf-1'].map(i => document.getElementById(i)).filter(Boolean);
  const live = bufs.filter(a => !a.paused && !a.ended);
  const act = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  const q = (window.__kcPendingPlayingAckQueue || []);
  return {
    live: live.map(a => a.getAttribute('data-kc-sounding') || String(a.currentSrc || a.src).split('/').pop()),
    active: act ? (act.getAttribute('data-kc-sounding') || '') : '',
    activeSrc: act ? String(act.currentSrc || act.src || '').split('/').pop() : '',
    activePaused: act ? act.paused : null,
    // Every ask the page sent (the ack queue is emptied once a handoff ack replaces it).
    needNext: (window.__kcPlayDiag || []).filter(r => r && r.ev === 'need_next_sent').map(r => [r.from, r.expect]),
    queuedNeedNext: q.filter(a => a && a.kind === 'need_next').length,
    playingAcks: q.filter(a => a && a.kind === 'playing').map(a => [a.playingKey, !!a.natural]),
    latePrep: q.filter(a => a && a.kind === 'late_prep_recover').length,
  }; }"""

# Run the active take to just before its end so the pass ends now.
_END_PASS_JS = """async () => { const d = window.__kcDual;
  const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  if (a.paused) { try { await a.play(); } catch (e) {} }
  a.currentTime = Math.max(0, a.duration - 0.25); await new Promise(r => setTimeout(r, 600));
  return {ended: a.ended}; }"""


def _run(test: unittest.TestCase, ops: list) -> list:
    """Mount the real bridge, then run ``ops`` in order. Each op returns a snapshot:
    ("cmd", c) a command from Python; ("end",) the active pass ends; ("wait", ms);
    ("stop",) the page's Key Cycling Stop; ("pause",) the page's Pause."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover - browser tooling not installed
        test.skipTest("playwright not installed")
    wav = _silent_wav(seconds=6.0)
    bridge = kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(ops[0][1]))

    def handle(route):
        if route.request.url.endswith(".wav"):
            rng = (route.request.headers.get("range") or "").replace("bytes=", "")
            if rng:
                a, _, b = rng.partition("-")
                start = int(a or 0)
                end = int(b) if b else len(wav) - 1
                route.fulfill(status=206, body=wav[start:end + 1], headers={
                    "Content-Type": "audio/wav", "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{len(wav)}", "Content-Length": str(end - start + 1)})
            else:
                route.fulfill(status=200, body=wav, headers={"Content-Type": "audio/wav", "Accept-Ranges": "bytes",
                                                             "Content-Length": str(len(wav))})
        else:
            route.fulfill(status=200, content_type="text/html", body=_PARENT)

    snaps: list = []
    errors: list = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://kc.test/**", handle)
            page.goto("http://kc.test/app/")
            page.evaluate("(html) => { document.getElementById('kc-bridge').srcdoc = html; }", bridge)
            page.wait_for_function("() => typeof window.__kcApplyCmd === 'function'"
                                   " && typeof window.__kcHardStop === 'function'", timeout=15000)
            page.wait_for_timeout(1800)
            for op in ops[1:]:
                kind = op[0]
                if kind == "cmd":
                    page.evaluate("(c) => window.__kcApplyCmd(c)", op[1])
                    page.wait_for_timeout(1500)
                elif kind == "end":
                    page.evaluate(_END_PASS_JS)
                elif kind == "wait":
                    page.wait_for_timeout(int(op[1]))
                elif kind == "stop":
                    page.evaluate("() => window.__kcHardStop()")
                    page.wait_for_timeout(300)
                elif kind == "pause":
                    page.evaluate("() => window.__kcPauseAudio()")
                    page.wait_for_timeout(300)
                snaps.append(page.evaluate(_STATE_JS))
        finally:
            browser.close()
    test.assertEqual(errors, [], errors)
    return snaps


_START = _cmd(10, "Am", "", restart=True, autoplay=True, forcePlay=True)


class LateNextTakeStartsOnArrival(unittest.TestCase):
    def test_a_pass_that_ends_without_its_next_take_asks_python_for_it(self) -> None:
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 1500)])
        self.assertEqual(s[-1]["live"], [])                   # nothing to play yet: silence, not a replay
        self.assertIn(["Am", "Dm"], s[-1]["needNext"])         # asked for Dm, the key after Am
        self.assertEqual(s[-1]["playingAcks"], [])             # asking moved no key

    def test_the_late_take_starts_the_moment_it_arrives(self) -> None:
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 2500),
                        ("cmd", _cmd(10, "Am", "Dm")), ("wait", 1200)])
        self.assertEqual(s[-1]["live"], ["Dm"])                # exactly one take plays: Dm
        self.assertEqual(s[-1]["active"], "Dm")
        self.assertIn(["Dm", True], s[-1]["playingAcks"])     # a natural Am -> Dm handoff for Python
        self.assertEqual(s[-1]["latePrep"], 0)

    def test_a_take_arriving_after_a_long_wait_still_starts(self) -> None:
        # Well past the old ~90 s give-up point would take too long here; 12 s covers the asks
        # at 1 s / 5 s and shows the wait does not end on its own while the cycle plays.
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 12000),
                        ("cmd", _cmd(10, "Am", "Dm")), ("wait", 1200)])
        self.assertGreaterEqual(len(s[-1]["needNext"]), 2)    # asked again while it waited
        self.assertEqual(s[-1]["live"], ["Dm"])

    def test_stop_during_the_wait_keeps_a_late_take_silent(self) -> None:
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 1500), ("stop",),
                        ("cmd", _cmd(10, "Am", "Dm")), ("wait", 2000)])
        self.assertEqual(s[-1]["live"], [])
        self.assertNotIn(["Dm", True], s[-1]["playingAcks"])

    def test_pause_during_the_wait_keeps_a_late_take_silent(self) -> None:
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 1500), ("pause",),
                        ("cmd", _cmd(10, "Am", "Dm")), ("wait", 2000)])
        self.assertEqual(s[-1]["live"], [])
        self.assertNotIn(["Dm", True], s[-1]["playingAcks"])

    def test_a_take_already_armed_hands_off_without_asking(self) -> None:
        s = _run(self, [("cmd", _cmd(10, "Am", "Dm", restart=True, autoplay=True, forcePlay=True)),
                        ("wait", 300), ("end",), ("wait", 1500)])
        self.assertEqual(s[-1]["live"], ["Dm"])
        self.assertEqual(s[-1]["needNext"], [])

    def test_repeated_late_transitions_step_one_key_each(self) -> None:
        s = _run(self, [("cmd", _START), ("wait", 300), ("end",), ("wait", 1500),
                        ("cmd", _cmd(10, "Am", "Dm")), ("wait", 6500),   # Dm plays its pass (silence 6 s)
                        ("end",), ("wait", 1500),                       # Dm ends, Gm not here yet
                        ("cmd", _cmd(10, "Dm", "Gm")), ("wait", 1200)])
        self.assertIn(["Dm", "Gm"], s[-2]["needNext"])         # asked for Gm, not a key further on
        self.assertEqual(s[-1]["live"], ["Gm"])
        keys = [k for k, _nat in s[-1]["playingAcks"]]
        self.assertEqual([k for k in keys if k in ("Dm", "Gm")][-2:], ["Dm", "Gm"])


class PythonTakesTheAskWithoutMovingTheKey(unittest.TestCase):
    def test_need_next_is_delivered_to_the_bridge(self) -> None:
        self.assertIn("need_next", kch._DELIVERED_ACK_KINDS)

    def test_the_bridge_consumes_need_next_like_play_started(self) -> None:
        self.assertEqual(kc._KC_NO_ADVANCE_ACK_KINDS, ("play_started", "need_next"))
        src = inspect.getsource(kc.render_backing_key_cycle_pass_bridge)
        self.assertNotIn('== "play_started":', src)  # every no-advance loop takes both kinds
        self.assertGreaterEqual(src.count("in _KC_NO_ADVANCE_ACK_KINDS"), 3)

    def test_need_next_aims_the_prefetch_and_moves_no_key(self) -> None:
        ss: dict = {"_kc_prefetch_cancel": False}
        kc._note_need_next_ack(ss, {"kind": "need_next", "fromKey": "Am", "expectKey": "Dm"})
        self.assertEqual(ss[kc.BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY], "Dm")
        self.assertEqual(set(ss), {"_kc_prefetch_cancel", kc.BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY})
        kc._note_need_next_ack(ss, {"kind": "play_started"})
        self.assertEqual(ss[kc.BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY], "Dm")


class PrefetchHandsAReadyTakeOverFirst(unittest.TestCase):
    def test_a_synthesized_take_without_its_timeline_is_handled_first(self) -> None:
        src = (_ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        frag = src[src.index("def _key_cycle_prefetch_fragment"):src.index("_key_cycle_prefetch_fragment()\n")]
        self.assertIn("_await_tl.append(tgt)", frag)
        self.assertNotIn("pending.append(tgt)\n                                    continue", frag)
        i_order = frag.index("pending = list(_await_tl) + [p for p in pending if p not in _await_tl]")
        self.assertLess(i_order, frag.index("tgt = pending[0]"))


if __name__ == "__main__":
    unittest.main()
