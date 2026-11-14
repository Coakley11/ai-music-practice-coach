"""Pause freezes the key that was SOUNDING, reported through the card command.

Browser runs 2026-11-13 (normal speed, 2 of 3): a Pause within ~0.5 s of an
automatic key change interrupted the handoff before the page posted its ack.
The browser held the new key, the server the previous one; Resume played the
new key under the old label, or nothing. The card's Pause now carries an
optional ``kc`` field (the key heard at the press) and the server adopts it
when it is the cycle's next key. The field is additive: every other command
and every other Backing source is handled exactly as before.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import backing_card_commands as cards
import backing_key_cycle as kc
from backing_card_transport import BACKING_CARD_TRANSPORT_KEY
from backing_transport_intent import PAUSED, begin_playback, transport_intent

_ROOT = Path(kc.__file__).resolve().parent


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.nonce = 0
        self.ss: dict = {"display_key": "C", "concert_key": "C"}

    def _cycle(self) -> str:
        kc.start_key_cycle(self.ss, start_key="C", interval=5, direction="up")  # C F Bb Eb ...
        begin_playback(self.ss, reason="test", command="t0")
        return str(kc.get_owner_cycle_session(self.ss)["cycle_id"])

    def _card(self, action: str, **extra) -> str:
        self.nonce += 1
        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": action, "nonce": self.nonce, "session": "s", **extra}
        got, token = cards.pending_card_command(self.ss)
        self.assertEqual(got, action)
        return token

    def _apply(self, action: str, **extra) -> cards.CardCommandOutcome:
        token = self._card(action, **extra)
        out = cards.apply_card_command(self.ss, action, token, has_chords=True, stop_backing=lambda _i: False)
        cards.commit_card_command(self.ss, token)
        return out

    def _key(self) -> str:
        return kc.temporary_playback_key(self.ss)

    def _status(self) -> str:
        return str(kc.get_owner_cycle_session(self.ss)["status"])

    def _natural_ack(self, key: str, ack_id: str, pass_id: int) -> dict:
        return {"kind": "playing", "ackId": ack_id, "cycleId": self.cid, "passId": pass_id,
                "playingKey": key, "fromKey": "", "natural": True}


class TestPauseAroundAnAutomaticTransition(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.cid = self._cycle()

    def test_pause_right_after_transition_freezes_the_new_key(self) -> None:
        # The browser already plays F (handoff interrupted before its ack).
        self._apply("pause", kc={"sounding": "F", "cycleId": self.cid})
        self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_HELD))
        self.assertEqual(transport_intent(self.ss), PAUSED)
        self._apply("resume")
        self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_RUNNING))

    def test_pause_right_before_transition_keeps_the_current_key(self) -> None:
        self._apply("pause", kc={"sounding": "C", "cycleId": self.cid})
        self.assertEqual((self._key(), self._status()), ("C", kc.STATUS_HELD))
        self._apply("resume")
        self.assertEqual(self._key(), "C")

    def test_pause_during_transition_with_a_late_ack_steps_once(self) -> None:
        self._apply("pause", kc={"sounding": "F", "cycleId": self.cid})
        # The interrupted handoff's ack still arrives later (paused, then running).
        self.assertFalse(kc.note_backing_pass_finished(
            self.ss, pass_signature="p", seamless=True, handoff_ack=self._natural_ack("F", "late1", 7)))
        self.assertEqual(self._key(), "F")
        self._apply("resume")
        kc.note_backing_pass_finished(self.ss, pass_signature="q", seamless=True,
                                      handoff_ack=self._natural_ack("F", "late2", 8))
        self.assertEqual(self._key(), "F")

    def test_repeated_pause_resume_cycles_never_drift(self) -> None:
        self._apply("pause", kc={"sounding": "F", "cycleId": self.cid})
        for _ in range(4):
            self._apply("resume")
            self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_RUNNING))
            self._apply("pause", kc={"sounding": "F", "cycleId": self.cid})
            self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_HELD))

    def test_retry_of_the_same_pause_command_is_idempotent(self) -> None:
        token = self._card("pause", kc={"sounding": "F", "cycleId": self.cid})
        for _ in range(3):
            cards.apply_card_command(self.ss, "pause", token, has_chords=True, stop_backing=lambda _i: False)
        cards.commit_card_command(self.ss, token)
        self.assertEqual(self._key(), "F")

    def test_only_the_next_key_of_this_cycle_is_adopted(self) -> None:
        self._apply("pause", kc={"sounding": "Bb", "cycleId": self.cid})  # two steps away
        self.assertEqual(self._key(), "C")
        self._apply("resume")
        self._apply("pause", kc={"sounding": "F", "cycleId": "another-cycle"})
        self.assertEqual(self._key(), "C")
        self._apply("resume")
        self._apply("pause", kc={"sounding": "G", "cycleId": self.cid})  # the previous key
        self.assertEqual(self._key(), "C")

    def test_settings_callbacks_pending_pause_uses_the_report_too(self) -> None:
        self._card("pause", kc={"sounding": "F", "cycleId": self.cid})
        cards.apply_pending_card_pause(self.ss)
        self.assertEqual((self._key(), self._status()), ("F", kc.STATUS_HELD))

    def test_stop_stays_reliable(self) -> None:
        stopped = []
        token = self._card("stop", kc={"sounding": "F", "cycleId": self.cid})
        cards.apply_card_command(self.ss, "stop", token, has_chords=True,
                                 stop_backing=lambda _i: stopped.append(1) or False)
        self.assertEqual(stopped, [1])


class TestBackwardCompatibleChannel(_Base):
    def test_pause_without_report_is_unchanged(self) -> None:
        self.cid = self._cycle()
        self._apply("pause")
        self.assertEqual((self._key(), self._status()), ("C", kc.STATUS_HELD))

    def test_report_is_ignored_without_key_cycling(self) -> None:
        # Ordinary Backing / Style Jam / Custom / Composition: no cycle session.
        begin_playback(self.ss, reason="test", command="t0")
        out = self._apply("pause", kc={"sounding": "F", "cycleId": "x"})
        self.assertEqual(transport_intent(self.ss), PAUSED)
        self.assertFalse(out.rerun)
        self.assertFalse(self.ss.get(kc.BACKING_KEY_CYCLE_SESSIONS_KEY))

    def test_extra_field_does_not_change_the_command_identity(self) -> None:
        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": "pause", "nonce": 3, "session": "s"}
        plain = cards.pending_card_command(self.ss)
        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": "pause", "nonce": 3, "session": "s",
                                               "kc": {"sounding": "F", "cycleId": "c"}}
        self.assertEqual(cards.pending_card_command(self.ss), plain)
        self.assertEqual(cards.pending_card_cycle_report(self.ss), {"sounding": "F", "cycleId": "c"})
        self.ss[BACKING_CARD_TRANSPORT_KEY] = {"action": "pause", "nonce": 3, "session": "s", "kc": "junk"}
        self.assertEqual(cards.pending_card_cycle_report(self.ss), {})

    def test_play_and_resume_ignore_the_field(self) -> None:
        self.cid = self._cycle()
        self._apply("pause")
        self._apply("resume", kc={"sounding": "F"})
        self.assertEqual(self._key(), "C")

    def test_component_sends_the_field_only_with_a_cycling_pause(self) -> None:
        html = (_ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
        self.assertIn('send("pause", kc ? { kc: kc } : null);', html)
        self.assertIn("if (!args.cycle_active) return null;", html)
        for action in ('send("resume")', 'send("ended")'):
            self.assertIn(action, html)
        js = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        self.assertIn("parentWin.__kcPauseSounding = {{", js)
        self.assertIn("W.__kcLiveKey = liveKey;", js)

    def test_live_key_counts_the_incoming_take_from_its_first_frame(self) -> None:
        # Guitar Shape browser run 2026-11-13: Pause pressed in the task that saw
        # the buffer flip (incoming take at currentTime 0.02) reported the
        # OUTGOING key, because liveKey() skipped takes under 0.05 s and fell back
        # to the stale __kcLastLive. The server held Am, the browser held Dm, and
        # Resume played Dm under the Am label.
        js = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        start = js.index("function liveKey() {{")
        body = js[start:js.index("function audibleKey()", start)]
        self.assertNotIn("currentTime || 0) > 0.05", body)
        self.assertIn("!a.paused && !a.ended && !a.muted && Number(a.volume) > 0.01", body)
        self.assertIn("Number(a.currentTime) < Number(live.currentTime)", body)

    def test_player_command_echoes_the_newest_applied_card_click(self) -> None:
        # Guitar Shape browser run 2026-11-13: Resume ~2.7 s after Pause, before
        # the Pause's own paused command (epoch N+1) reached the page. The epoch
        # guard held epoch N, so that command looked newer, silenced the resumed
        # take and latched userPaused; every later press then toggled backwards.
        ss: dict = {}
        self.assertEqual(kc._card_transport_echo(ss), "")
        ss[BACKING_CARD_TRANSPORT_KEY] = {"action": "resume", "nonce": 9, "session": "s"}
        got, token = cards.pending_card_command(ss)
        cards.commit_card_command(ss, token)
        self.assertEqual(kc._card_transport_echo(ss), token)
        self.assertEqual(kc._card_transport_echo(ss), cards.card_echo_token(ss))
        js = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        self.assertIn('"transportConsumed": _card_transport_echo(session),', js)

    def test_page_drops_only_transport_commands_built_before_the_newest_click(self) -> None:
        js = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        start = js.index("const tl = parentWin.__backingTransportLocal;")
        guard = js[start:js.index("}} catch (eTransportGuard) {{}}", start)]
        # Only while the click is unconfirmed, and only a command contradicting it.
        self.assertIn("String(cmd.transportConsumed || '') !== String(tl.token)", guard)
        self.assertIn("Date.now() < Number(tl.until || 0)", guard)
        self.assertIn("(tl.intent === 'playing' && wantsPause) || (tl.intent === 'paused' && wantsPlay)", guard)
        # Stop, explicit Play, Next/Previous restarts and reloads are never held back.
        for exempt in ("!cmd.hardStop", "!cmd.forcePlay", "!cmd.restart", "!cmd.arrangementReload",
                       "!cmd.forceArrangementReplace"):
            self.assertIn(exempt, guard)
        # Only the transport bit is neutralised; the command itself still applies.
        # Browser runs 2026-11-13: dropping the whole command lost its epoch, so
        # 10 natural handoff acks were rejected (stale_epoch) and Python fell a
        # key behind; recording the epoch without applying left the page with no
        # next take (it replayed an old key). Neither variant remains.
        self.assertIn("cmd = Object.assign({{}}, cmd, {{ paused: false, resume: false, autoplay: false }});", guard)
        self.assertNotIn("return;", guard)
        self.assertNotIn("state.epoch =", guard)
        # It runs before the command can pause (abortTransportPlayback) or play.
        self.assertLess(js.index("const tl = parentWin.__backingTransportLocal;"),
                        js.index("if ((cmd.hardStop || cmd.paused) && !cmd.resume && !cmd.restart && !cmd.forcePlay) {{"))
        html = (_ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
        self.assertIn("window.parent.__backingTransportLocal = { intent: intent, token: localToken, until: localUntil };", html)
        # The card's own label still clears on the same echo.
        self.assertIn("if (localIntent && args.consumed === localToken)", html)

    def test_pause_in_a_silent_handoff_gap_is_a_pause_not_a_resume(self) -> None:
        js = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
        # Decided by the transport intent, not by whether a take is audible this instant.
        self.assertIn("if (!prog && !running && !held && tpIntent === 'playing') running = true;", js)


def _bridge_js() -> str:
    return kc.cycle_persistent_player_bridge_html(cmd_json="{}")


class PauseButtonModeIgnoresIconText(unittest.TestCase):
    """The Key Cycling Pause button carries a Material icon, whose ligature text is part of the
    button's innerText ("pause Pause" / "play_arrow Resume"). Browser run 2026-11-14 on the
    integration merge: the live player's Pause (__kcRequestCyclePause) compared that text with
    /^Pause$/, never matched, and skipped the Streamlit click, so the server stayed Running for
    22.7 s while the audio was silent. The bridge now asks the button for its mode."""

    def test_no_exact_label_comparison_remains_on_the_pause_button(self) -> None:
        js = _bridge_js()
        self.assertIn("function kcPauseBtnLabel(b)", js)
        self.assertIn("function kcPauseBtnMode(b)", js)
        self.assertLess(js.index("function kcPauseBtnMode(b)"), js.index("__kcRequestCyclePause = function"))
        self.assertNotIn("/^Pause$/i.test(lab", js)
        self.assertNotIn("/^Resume$/i.test(lab", js)
        self.assertEqual(js.count("kcPauseBtnMode(b0) === 'pause'"), 1)  # live-player Pause, read first
        self.assertEqual(js.count("kcPauseBtnMode(b) !== 'resume'"), 1)  # resume align
        self.assertEqual(js.count("kcPauseBtnMode(b0) === 'resume'"), 2)  # Resume + Back to loop start
        # The fallback routes (no key class after a remount) read the label without the icon too.
        self.assertIn("const lab = kcPauseBtnLabel(btnHit);", js)
        self.assertIn("const label = kcPauseBtnLabel(btn);", js)
        # The state shown on the button is still written by the one transport sync, from the audio.
        self.assertIn("const glyph = paused ? 'play_arrow' : 'pause';", js)

    def test_mode_is_read_from_streamlit_shaped_buttons_in_a_browser(self) -> None:
        try:
            from playwright import sync_api
        except Exception:  # pragma: no cover - browser tooling not installed
            self.skipTest("playwright not installed")
        js = _bridge_js()
        helpers = js[js.index("  function kcPauseBtnLabel(b)"):js.index("  const KC_HOLDER_HIDDEN_CSS")]
        icon = '<span data-testid="stIconMaterial">{}</span>'
        md = '<div data-testid="stMarkdownContainer"><p>{}</p></div>'
        cases = {
            # Streamlit 1.59 st.button(icon=...): icon span + markdown label.
            "pause": (icon.format("pause") + md.format("Pause"), "Pause", "pause"),
            "resume": (icon.format("play_arrow") + md.format("Resume"), "Resume", "resume"),
            # Undecorated buttons and a bare label without the markdown wrapper.
            "plain_pause": (md.format("Pause"), "Pause", "pause"),
            "bare_resume": (icon.format("play_arrow") + "Resume", "Resume", "resume"),
            # Other transport buttons are neither.
            "previous": (icon.format("skip_previous") + md.format("Previous"), "Previous", ""),
            "stop": (icon.format("stop") + md.format("Stop"), "Stop", ""),
        }
        script = (
            "(cases) => {" + helpers + "\n const out = {};"
            " for (const [k, html] of Object.entries(cases)) {"
            "  const b = document.createElement('button'); b.innerHTML = html; document.body.appendChild(b);"
            "  out[k] = {inner: b.innerText.replace(/\\s+/g, ' ').trim(), label: kcPauseBtnLabel(b), mode: kcPauseBtnMode(b)};"
            " } return out; }"
        )
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content("<html><body></body></html>")
                got = page.evaluate(script, {k: v[0] for k, v in cases.items()})
            finally:
                browser.close()
        # The defect's precondition: the icon text really is in innerText.
        self.assertEqual(got["pause"]["inner"], "pause Pause")
        for k, (_html, label, mode) in cases.items():
            self.assertEqual(got[k]["label"], label, (k, got[k]))
            self.assertEqual(got[k]["mode"], mode, (k, got[k]))


class LivePlayerPauseReachesTheServer(unittest.TestCase):
    """The live player's Pause (Lead Sheet stop -> __kcRequestCyclePause) must click the Streamlit
    Pause button once, so the server enters Held. It used to pause the audio first; that set the
    user hold and relabelled the button Resume at once, so the later "is it Pause?" check never
    clicked. The server stayed Running and the audio came back by itself 3-15 s later (browser
    runs 2026-11-14 on dev 59e77f35 and on the integration merge: 0 clicks per press)."""

    _PARENT = (
        '<html><body><div class="st-key-backing_key_cycle_pause_btn"><button>'
        '<span data-testid="stIconMaterial">{icon}</span>'
        '<div data-testid="stMarkdownContainer"><p>{label}</p></div></button></div>'
        '<iframe id="kc-bridge"></iframe></body></html>'
    )

    def _press(self, label: str, icon: str) -> dict:
        try:
            from playwright import sync_api
        except Exception:  # pragma: no cover - browser tooling not installed
            self.skipTest("playwright not installed")
        bridge = _bridge_js()
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                errors: list = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.set_content(self._PARENT.format(label=label, icon=icon))
                # The bridge runs in a frame whose parent is the app page, as components.html mounts it.
                page.evaluate(
                    """(html) => { window.__clicks = []; const btn = document.querySelector('button');
                      window.addEventListener('click', (ev) => {
                        if (ev.target && ev.target.closest && ev.target.closest('button') === btn)
                          window.__clicks.push(btn.querySelector('p').textContent); }, true);
                      document.getElementById('kc-bridge').srcdoc = html; }""",
                    bridge,
                )
                page.wait_for_function("() => typeof window.__kcRequestCyclePause === 'function'", timeout=15000)
                page.evaluate("() => window.__kcRequestCyclePause()")
                page.wait_for_timeout(300)
                got = page.evaluate(
                    "() => ({clicks: window.__clicks, label: document.querySelector('p').textContent,"
                    " userPaused: !!(window.__kcDual || {}).userPaused})"
                )
            finally:
                browser.close()
        got["errors"] = errors
        return got

    def test_pause_from_playing_clicks_the_server_pause_exactly_once(self) -> None:
        got = self._press("Pause", "pause")
        self.assertEqual(len(got["clicks"]), 1, got)
        self.assertTrue(got["userPaused"], got)
        self.assertEqual(got["label"], "Resume", got)  # the button shows what the audio does
        self.assertEqual(got["errors"], [], got)

    def test_pause_when_already_held_does_not_click_and_so_never_resumes(self) -> None:
        # The server toggles on this click (Held -> Resume), so a held player must not click.
        got = self._press("Resume", "play_arrow")
        self.assertEqual(got["clicks"], [], got)
        self.assertEqual(got["errors"], [], got)

    def test_the_mode_is_read_before_the_audio_is_paused(self) -> None:
        js = _bridge_js()
        body = js[js.index("__kcRequestCyclePause = function"):js.index("__kcResumeAudio = function")]
        self.assertLess(body.index("kcPauseBtnMode(b0) === 'pause'"), body.index("parentWin.__kcPauseAudio();"))
        self.assertLess(body.index("parentWin.__kcPauseAudio();"), body.index("if (!wantHeld) return;"))
        self.assertEqual(body.count("b.click()"), 1)
        self.assertNotIn("kcPauseBtnMode(b) !== 'pause'", body)  # no second, after-the-fact check


if __name__ == "__main__":
    unittest.main()
