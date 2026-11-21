"""The cycle finishes the moment its final key's take ends, and a manual switch reports the take it started.

Browser runs 2026-11-20 on the acceptance candidate 13de912d (eight runs, 1280 / 390 / 360 px):

* Final stop: after the 12th key's take ended there was no next take to warm, so the cycle depended on the
  take's ``ended`` reaching ``onEnded``. It did not: the page logged nothing until the parent watcher's
  late-take give-up 90 s later. Meanwhile the console read "playing 12 / 12" and the next Play acted as
  Stop. The parent watcher now finishes the cycle itself when the active take ended at the sequence's
  final key -- also after the bridge frame was replaced by a rerun and when an earlier hand-off left
  ``_onEndedGate`` set.
* Manual Next / Previous: the switch ack reported ``currentSrc``, which Chromium keeps on the previous
  take's URL until the new source loads. Next2 to Gm acked the Am take's URL, Python judged the switch
  not audible and queued a Gm restart; after Previous that restart repainted the card and the Lead Sheet
  in Gm while Dm played (5.7 - 10.1 s). The ack now reports the source the switch gave the element.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import backing_key_cycle as kc
from tests.test_key_cycle_pause_reports_sounding_key import _silent_wav

_SEQ = ["Am", "Dm", "Gm"]          # a short cycle: Gm is the final key
_URL = {k: f"app/static/kc/{k.lower()}.wav" for k in _SEQ}


def _cmd(epoch: int, current: str, nxt: str = "", **extra) -> dict:
    return dict({
        "enabled": True, "epoch": epoch, "cycleId": "cyc-F", "sequence": list(_SEQ),
        "currentUrl": _URL[current], "sounding": current, "currentSounding": current,
        "nextUrl": _URL[nxt] if nxt else "", "nextSounding": nxt,
        "liveUrls": [u for u in (_URL[current], _URL[nxt] if nxt else "") if u],
        "autoplay": False, "forcePlay": False,
    }, **extra)


_PARENT = ('<html><body><div class="st-key-backing_key_cycle_pause_btn"><button><p>Pause</p></button></div>'
           '<iframe id="kc-bridge"></iframe></body></html>')

_STATE_JS = """() => { const d = window.__kcDual || {};
  const bufs = ['kc-buf-0', 'kc-buf-1'].map(i => document.getElementById(i)).filter(Boolean);
  const live = bufs.filter(a => !a.paused && !a.ended && !a.muted);
  const q = (window.__kcPendingPlayingAckQueue || []).concat(window.__kcPendingPlayingAck ? [window.__kcPendingPlayingAck] : []);
  const diag = (window.__kcPlayDiag || []);
  return {
    live: live.map(a => a.getAttribute('data-kc-sounding') || String(a.currentSrc || a.src).split('/').pop()),
    finalAcks: q.filter(a => a && a.kind === 'final_key_stop').length,
    finalDiag: diag.filter(r => r && r.ev === 'final_key_stop').length,
    needNext: q.filter(a => a && a.kind === 'need_next').length,
    atFinal: !!d.atFinalKey, finalCompleted: !!d.finalCompleted,
  }; }"""

_END_PASS_JS = """async () => { const d = window.__kcDual;
  const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  if (a.paused) { try { await a.play(); } catch (e) {} }
  a.currentTime = Math.max(0, a.duration - 0.25); await new Promise(r => setTimeout(r, 600));
  return {ended: a.ended}; }"""


def _run(test: unittest.TestCase, ops: list) -> list:
    """("cmd", c) a command; ("remount", c) Streamlit replaces the bridge frame (a rerun);
    ("gate",) an earlier hand-off left _onEndedGate set; ("end",) the active pass ends; ("wait", ms)."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover
        test.skipTest("playwright not installed")
    wav = _silent_wav(seconds=6.0)

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
            page.evaluate("(html) => { document.getElementById('kc-bridge').srcdoc = html; }",
                          kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(ops[0][1])))
            page.wait_for_function("() => typeof window.__kcApplyCmd === 'function'", timeout=15000)
            page.wait_for_timeout(1800)
            for op in ops[1:]:
                kind = op[0]
                if kind == "cmd":
                    page.evaluate("(c) => window.__kcApplyCmd(c)", op[1])
                    page.wait_for_timeout(1500)
                elif kind == "remount":
                    page.evaluate("""(html) => { const old = document.getElementById('kc-bridge');
                        const f = document.createElement('iframe'); f.id = 'kc-bridge';
                        old.replaceWith(f); f.srcdoc = html; }""",
                                  kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(op[1])))
                    page.wait_for_timeout(2000)
                elif kind == "gate":
                    page.evaluate("() => { window.__kcDual._onEndedGate = true; }")
                elif kind == "end":
                    page.evaluate(_END_PASS_JS)
                elif kind == "wait":
                    page.wait_for_timeout(int(op[1]))
                snaps.append(page.evaluate(_STATE_JS))
        finally:
            browser.close()
    test.assertEqual(errors, [], errors)
    return snaps


_AT_FINAL = _cmd(20, "Gm", "", restart=True, autoplay=True, forcePlay=True)


class FinalKeyEndFinishesTheCycle(unittest.TestCase):
    def test_final_take_ending_after_a_rerun_finishes_the_cycle_within_seconds(self) -> None:
        s = _run(self, [("cmd", _AT_FINAL), ("wait", 300), ("remount", _cmd(20, "Gm", "")),
                        ("end",), ("wait", 2500)])
        self.assertGreaterEqual(s[-1]["finalAcks"] + s[-1]["finalDiag"], 1, s[-1])  # not after a 90 s wait
        self.assertTrue(s[-1]["atFinal"])
        self.assertEqual(s[-1]["live"], [])
        self.assertEqual(s[-1]["needNext"], 0)          # the final key has no next take to ask for

    def test_a_gate_left_by_an_earlier_handoff_does_not_swallow_the_final_end(self) -> None:
        s = _run(self, [("cmd", _AT_FINAL), ("wait", 300), ("gate",), ("end",), ("wait", 2500)])
        self.assertGreaterEqual(s[-1]["finalAcks"] + s[-1]["finalDiag"], 1, s[-1])
        self.assertTrue(s[-1]["atFinal"])
        self.assertEqual(s[-1]["live"], [])

    def test_after_the_final_stop_a_new_start_plays_the_first_key(self) -> None:
        s = _run(self, [("cmd", _AT_FINAL), ("wait", 300), ("gate",), ("end",), ("wait", 2500),
                        ("cmd", _cmd(21, "Am", "Dm", restart=True, autoplay=True, forcePlay=True)), ("wait", 1500)])
        self.assertEqual(s[-1]["live"], ["Am"])          # one take, the first key -- nothing stale sounds

    def test_a_mid_cycle_end_still_waits_for_the_next_take(self) -> None:
        # Not the final key: the late-take wait (need_next) is unchanged.
        s = _run(self, [("cmd", _cmd(20, "Am", "", restart=True, autoplay=True, forcePlay=True)),
                        ("wait", 300), ("end",), ("wait", 2500)])
        self.assertEqual(s[-1]["finalAcks"] + s[-1]["finalDiag"], 0)
        self.assertFalse(s[-1]["atFinal"])


class SwitchAckReportsTheAssignedSource(unittest.TestCase):
    def test_both_switch_acks_prefer_the_assigned_source_over_current_src(self) -> None:
        src = Path(kc.__file__).read_text(encoding="utf-8")
        acks = re.findall(r"playingUrl: (.+?),\n", src)
        built = [a for a in acks if "currentSrc" in a]
        self.assertEqual(len(built), 2, acks)
        for a in built:
            # currentSrc may only be the last resort
            self.assertLess(a.index("getAttribute('src')"), a.index("currentSrc"), a)

    def test_the_parent_watcher_was_reinstalled_for_the_final_end(self) -> None:
        src = Path(kc.__file__).read_text(encoding="utf-8")
        self.assertIn("window.__kcWatchVersion = 33;", src)
        self.assertIn("final_take_ended_watch", src)




class PlayAfterTheFinishedCycleStartsTheFirstKey(unittest.TestCase):
    """Play right after the cycle finished: the run that handles it resolved its chart and audio from
    the held final key, so the app rewinds to the first key and runs again (the Play command is not
    committed yet, so the next run applies it with the first key). Browser probe 2026-11-21 on
    34cc4898: the card said Starting and nothing sounded."""

    def setUp(self) -> None:
        from unittest import mock

        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "A", "concert_key": "A"}
        kc.start_key_cycle(self.ss, start_key="Am", interval=5, direction="up")
        self.cid = str(kc.get_owner_cycle_session(self.ss)["cycle_id"])
        self.seq = list(kc.cycle_key_sequence(self.ss))
        for _ in range(len(self.seq) - 1):
            kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, {
            "kind": "final_key_stop", "ackId": "fks_p", "cycleId": self.cid, "passId": 12,
            "playingKey": self.seq[-1], "fromKey": self.seq[-1], "natural": True}))

    def test_the_finished_cycle_holds_its_final_key_until_play(self) -> None:
        self.assertTrue(self.ss.get("_kc_cycle_finished_final"))
        self.assertEqual(kc.temporary_playback_key(self.ss), self.seq[-1])
        self.assertTrue(kc.is_cycle_active(self.ss))

    def test_the_rewind_play_triggers_puts_the_first_key_and_ends_the_finished_state(self) -> None:
        kc.rewind_key_cycle_to_first_key(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), self.seq[0])
        # the re-applied Play is an ordinary Play: no second rewind / rerun
        self.assertFalse(self.ss.get("_kc_cycle_finished_final"))
        kc.arm_key_cycle_for_explicit_play(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), self.seq[0])
        self.assertTrue(self.ss.get("_kc_restart_play"))

    def test_the_app_rewinds_and_reruns_before_handling_play_after_the_finish(self) -> None:
        src = (Path(kc.__file__).resolve().parent / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        i = src.index("_kc_play_after_finish = False")
        block = src[i:i + 900]
        self.assertIn('st.session_state.get("_kc_cycle_finished_final")', block)
        self.assertIn("_kc_pf_rewind(st.session_state)", block)
        self.assertIn("carry_card_play_over_rerun(st.session_state, _card_token)", block)
        self.assertIn("st.rerun()", block)
        self.assertLess(block.index("carry_card_play_over_rerun"), block.index("st.rerun()"))
        # the run reads the carried Play when the card's own value is gone
        self.assertIn("_card_action, _card_token = card_command_for_this_run(st.session_state)", src)
        # the rerun is outside the try/except that would swallow Streamlit's rerun exception
        self.assertLess(block.index("except Exception"), block.index("st.rerun()"))


class APlayCarriedOverTheRewindRerunIsArmed(unittest.TestCase):
    """Diagnostic trace 2026-11-21 (d96439de, 6 whole tones): Play after the finished cycle rewound to
    the first key and reran, but in the rerun ``backing_card_transport`` was None, so no command was
    handled, nothing was armed and the cycle stayed Held at 1 / 6 with no take. The Play is now carried
    over the rerun until it is committed; a newer command or a Stop drops it."""

    TOKEN = "s1:2"

    def setUp(self) -> None:
        from unittest import mock

        import backing_card_commands as bcc

        self.bcc = bcc
        for p_ in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p_.start()
            self.addCleanup(p_.stop)
        self.ss: dict = {"display_key": "A", "concert_key": "A"}
        kc.start_key_cycle(self.ss, start_key="Am", interval=2, direction="up")
        self.cid = str(kc.get_owner_cycle_session(self.ss)["cycle_id"])
        self.seq = list(kc.cycle_key_sequence(self.ss))
        for _ in range(len(self.seq) - 1):
            kc._step_owner_cycle(self.ss, steps=1, force=False, queue_continue=False, allow_wrap=False)
        self.assertTrue(kc.seal_final_key_from_ack(self.ss, {
            "kind": "final_key_stop", "ackId": "fks_c", "cycleId": self.cid, "passId": 6,
            "playingKey": self.seq[-1], "fromKey": self.seq[-1], "natural": True}))

    def _card(self, action: str, nonce: int) -> None:
        from backing_card_transport import BACKING_CARD_TRANSPORT_KEY

        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": action, "session": "s1", "nonce": nonce}

    def _apply(self, action: str, token: str):
        return self.bcc.apply_card_command(self.ss, action, token, has_chords=True, stop_backing=lambda _i: False)

    def _first_run_handles_play_and_reruns(self) -> None:
        """Run 1: the card's Play with the cycle finished -> rewind, carry the Play, rerun."""
        from backing_card_transport import BACKING_CARD_TRANSPORT_KEY

        self._card("play", 2)
        action, token = self.bcc.card_command_for_this_run(self.ss)
        self.assertEqual((action, token), ("play", self.TOKEN))
        self.assertTrue(self._apply(action, token).play)
        self.assertTrue(self.ss.get("_kc_cycle_finished_final"))
        kc.rewind_key_cycle_to_first_key(self.ss)
        self.bcc.carry_card_play_over_rerun(self.ss, token)
        # the rerun: the card's value is gone (measured in the browser)
        self.ss[BACKING_CARD_TRANSPORT_KEY] = None

    def test_the_rerun_still_handles_the_play_and_arms_the_first_key(self) -> None:
        self._first_run_handles_play_and_reruns()
        action, token = self.bcc.card_command_for_this_run(self.ss)
        self.assertEqual((action, token), ("play", self.TOKEN))
        self.assertTrue(self._apply(action, token).play)
        # an ordinary Play now: no second rewind, the cycle runs from its first key
        self.assertFalse(self.ss.get("_kc_cycle_finished_final"))
        kc.arm_key_cycle_for_explicit_play(self.ss)
        bag = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(bag.get("status"), kc.STATUS_RUNNING)
        self.assertEqual(kc.temporary_playback_key(self.ss), self.seq[0])
        self.assertTrue(self.ss.get("_kc_restart_play"))
        self.assertTrue(self.ss.get("_backing_autoplay"))
        for stale in ("_kc_hard_stop", "_kc_pause_audio", "_kc_at_final_key"):
            self.assertFalse(self.ss.get(stale), stale)

    def test_once_armed_and_committed_it_is_never_handled_again(self) -> None:
        self._first_run_handles_play_and_reruns()
        action, token = self.bcc.card_command_for_this_run(self.ss)
        self._apply(action, token)
        kc.arm_key_cycle_for_explicit_play(self.ss)
        self.bcc.commit_handled_card_command(self.ss)
        self.assertEqual(self.bcc.card_command_for_this_run(self.ss), ("", ""))
        self.assertNotIn(self.bcc.CARD_CARRIED_PLAY_KEY, self.ss)

    def test_a_run_cut_off_before_arming_handles_the_same_play_again(self) -> None:
        from backing_transport_intent import TRANSPORT_COMMAND_KEY

        self._first_run_handles_play_and_reruns()
        for _ in range(2):  # not committed: the next run handles it again
            self.assertEqual(self.bcc.card_command_for_this_run(self.ss), ("play", self.TOKEN))
        gen = self.ss[TRANSPORT_COMMAND_KEY]["generation"]
        self._apply("play", self.TOKEN)  # the same playback session, not another one
        self.assertEqual(self.ss[TRANSPORT_COMMAND_KEY]["generation"], gen)

    def test_a_card_stop_pressed_during_the_rerun_wins(self) -> None:
        self._first_run_handles_play_and_reruns()
        self._card("stop", 3)
        self.assertEqual(self.bcc.card_command_for_this_run(self.ss), ("stop", "s1:3"))
        self.assertNotIn(self.bcc.CARD_CARRIED_PLAY_KEY, self.ss)

    def test_the_key_cycling_stop_drops_the_carried_play(self) -> None:
        self._first_run_handles_play_and_reruns()
        kc._stop_key_cycle_from_button(self.ss)
        self.assertEqual(self.bcc.card_command_for_this_run(self.ss), ("", ""))

    def test_an_already_committed_token_is_not_replayed(self) -> None:
        from backing_card_transport import BACKING_CARD_TRANSPORT_CONSUMED_KEY

        self.bcc.carry_card_play_over_rerun(self.ss, self.TOKEN)
        self.ss[BACKING_CARD_TRANSPORT_CONSUMED_KEY] = self.TOKEN
        self.assertEqual(self.bcc.card_command_for_this_run(self.ss), ("", ""))
        self.assertNotIn(self.bcc.CARD_CARRIED_PLAY_KEY, self.ss)

    def test_the_saved_practice_key_is_not_touched(self) -> None:
        before = (self.ss.get("display_key"), self.ss.get("concert_key"))
        self._first_run_handles_play_and_reruns()
        action, token = self.bcc.card_command_for_this_run(self.ss)
        self._apply(action, token)
        kc.arm_key_cycle_for_explicit_play(self.ss)
        self.assertEqual((self.ss.get("display_key"), self.ss.get("concert_key")), before)


_CONSOLE_PARENT = (
    '<html><body><div class="st-key-backing_key_cycle_pause_btn"><button><p>Pause</p></button></div>'
    '<div class="ui-key-cycle-playbar kc-console" data-status="playing" data-seq="Am,Dm,Gm"'
    ' data-kc-labels=\'["A minor","D minor","G minor"]\' data-kc-sounding-labels=\'["A minor","D minor","G minor"]\'>'
    '<span class="kc-console-position">2 / 3</span><span class="kc-console-current">D minor</span>'
    '<span class="ui-key-cycle-chip ui-key-cycle-chip-on" data-key="Dm">Dm</span>'
    '<span class="ui-key-cycle-chip" data-key="Gm">Gm</span></div>'
    '<iframe id="kc-panel" srcdoc="<div id=&quot;live-chart-root&quot;><div class=&quot;lead-sheet&quot;'
    ' data-kc-chart-key=&quot;Dm&quot;>Dm chart</div></div>"></iframe>'
    '<iframe id="kc-bridge"></iframe></body></html>')

_SHOWN_JS = """() => { const bar = document.querySelector('.ui-key-cycle-playbar.kc-console');
  const f = document.getElementById('kc-panel'); const d = f && f.contentDocument;
  const sh = d && d.querySelector('#live-chart-root .lead-sheet');
  const bufs = ['kc-buf-0', 'kc-buf-1'].map(i => document.getElementById(i)).filter(Boolean);
  return { current: bar.querySelector('.kc-console-current').textContent.trim(),
           pos: bar.querySelector('.kc-console-position').textContent.trim(),
           chip: (bar.querySelector('.ui-key-cycle-chip-on') || {getAttribute: () => ''}).getAttribute('data-key'),
           chart: sh ? sh.getAttribute('data-kc-chart-key') : '',
           playing: bufs.filter(a => !a.paused && !a.muted && a.currentTime > 0.3).length,
           repairs: (window.__kcDisplayRepairs || []).map(r => r.what) }; }"""

_STALE_RENDER_JS = """() => { const bar = document.querySelector('.ui-key-cycle-playbar.kc-console');
  bar.querySelector('.kc-console-current').textContent = 'D minor';
  bar.querySelector('.kc-console-position').textContent = '2 / 3';
  bar.querySelectorAll('.ui-key-cycle-chip').forEach(c => c.classList.toggle('ui-key-cycle-chip-on', c.getAttribute('data-key') === 'Dm'));
  const d = document.getElementById('kc-panel').contentDocument;
  d.getElementById('live-chart-root').innerHTML = '<div class="lead-sheet" data-kc-chart-key="Dm">Dm chart</div>'; }"""


def _run_console(test: unittest.TestCase, first: dict, ops: list) -> list:
    """The page holds the server-rendered console and a singing panel; ("stale",) re-renders both
    from an older key as a late Streamlit run does; ("pause",) pauses the sounding take."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover
        test.skipTest("playwright not installed")
    wav = _silent_wav(seconds=8.0)

    def handle(route):
        if route.request.url.endswith(".wav"):
            rng = (route.request.headers.get("range") or "").replace("bytes=", "")
            start, end = 0, len(wav) - 1
            if rng:
                a, _, b = rng.partition("-")
                start, end = int(a or 0), (int(b) if b else len(wav) - 1)
            route.fulfill(status=206 if rng else 200, body=wav[start:end + 1], headers={
                "Content-Type": "audio/wav", "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{len(wav)}", "Content-Length": str(end - start + 1)})
        else:
            route.fulfill(status=200, content_type="text/html", body=_CONSOLE_PARENT)

    snaps: list = []
    errors: list = []
    with sync_api.sync_playwright() as p_:
        browser = p_.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://kc.test/**", handle)
            page.goto("http://kc.test/app/")
            page.wait_for_timeout(300)
            page.evaluate("(html) => { document.getElementById('kc-bridge').srcdoc = html; }",
                          kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(first)))
            page.wait_for_function("() => typeof window.__kcApplyCmd === 'function'", timeout=15000)
            page.wait_for_timeout(2000)
            snaps.append(page.evaluate(_SHOWN_JS))
            for op in ops:
                if op[0] == "stale":
                    page.evaluate(_STALE_RENDER_JS)
                elif op[0] == "pause":
                    page.evaluate("() => ['kc-buf-0','kc-buf-1'].forEach(i => { const a = document.getElementById(i); if (a) a.pause(); })")
                elif op[0] == "wait":
                    page.wait_for_timeout(int(op[1]))
                snaps.append(page.evaluate(_SHOWN_JS))
        finally:
            browser.close()
    test.assertEqual(errors, [], errors)
    return snaps


class AStaleRenderNeverOutlivesTheSoundingTake(unittest.TestCase):
    """Browser runs 2026-11-21 on 51e6aaaa: after Next2 the G minor take sounded while a page render
    the server built before it saw the Next put the console back to "2 / 12 D minor" (~4 s); after
    Previous the D minor take sounded under G minor's Lead Sheet cells (~5 s). The console, the
    highlighted chip and the Lead Sheet chart follow the take that is actually sounding."""

    GM = dict(_cmd(30, "Gm", "", autoplay=True, forcePlay=True, restart=True),
              currentChartHtml='<div class="lead-sheet" data-kc-chart-key="Gm">Gm chart</div>')

    def test_a_stale_render_is_repaired_to_the_sounding_key(self) -> None:
        snaps = _run_console(self, self.GM, [("wait", 600), ("stale",), ("wait", 1200)])
        self.assertEqual(snaps[0]["playing"], 1, snaps[0])
        after = snaps[-1]
        self.assertEqual((after["current"], after["pos"], after["chip"]), ("G minor", "3 / 3", "Gm"), snaps)
        self.assertEqual(after["chart"], "Gm", snaps)
        self.assertIn("console", after["repairs"])
        self.assertIn("chart", after["repairs"])

    def test_nothing_is_rewritten_while_no_take_sounds(self) -> None:
        snaps = _run_console(self, self.GM, [("wait", 600), ("pause",), ("wait", 300), ("stale",), ("wait", 1200)])
        after = snaps[-1]
        self.assertEqual(after["playing"], 0, snaps)
        # the repair acts only on a take that is sounding (a paused Previous / Next is the page's own
        # pause handling, unchanged here)
        self.assertEqual(after["repairs"], [], snaps)


if __name__ == "__main__":
    unittest.main()
