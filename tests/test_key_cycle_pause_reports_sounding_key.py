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


class TestServerFollowsVerifiedTransitions(_Base):
    """KC-F1 as traced 2026-11-14: after every Pause/Resume the first natural ack was rejected as
    stale_epoch (Pause and Resume each bump the epoch, but neither moves the cycle), the next ack
    was then two steps ahead and the skip guard refused it, so the server stayed a key behind and
    its commands pulled the page back (Dm at the end -> Gm -> Cm -> back to Gm)."""

    def _ack(self, playing: str, from_key: str, epoch: int, pass_id: int) -> dict:
        self.nonce += 1
        return {"kind": "playing", "ackId": f"a{self.nonce}", "cycleId": self.cycle, "epoch": epoch,
                "playingKey": playing, "fromKey": from_key, "passId": pass_id}

    def setUp(self) -> None:
        super().setUp()
        self.cycle = self._cycle()  # C F Bb Eb Ab ...

    def test_a_pause_and_resume_do_not_make_a_real_handoff_ack_stale(self) -> None:
        from backing_key_cycle_handoff import validate_playing_ack

        e0 = int(self.ss.get("_kc_player_cmd_epoch") or 0)
        kc.pause_key_cycle(self.ss)
        kc.resume_key_cycle(self.ss)
        ok, why = validate_playing_ack(self.ss, self._ack("F", "C", e0, 1))
        self.assertTrue(ok, why)

    def test_a_position_change_still_makes_an_older_ack_stale(self) -> None:
        from backing_key_cycle_handoff import validate_playing_ack

        e0 = int(self.ss.get("_kc_player_cmd_epoch") or 0)
        kc.pause_key_cycle(self.ss)  # transport only
        self.ss["_kc_player_cmd_epoch"] = int(self.ss["_kc_player_cmd_epoch"]) + 1  # a Next / Previous
        self.ss["_kc_player_cmd_epoch"] = int(self.ss["_kc_player_cmd_epoch"]) + 1  # and a Play
        ok, why = validate_playing_ack(self.ss, self._ack("F", "C", e0, 1))
        self.assertFalse(ok)
        self.assertEqual(why, "stale_epoch")

    def test_a_stop_is_not_transport_only(self) -> None:
        from backing_key_cycle_handoff import validate_playing_ack

        e0 = int(self.ss.get("_kc_player_cmd_epoch") or 0)
        kc.hard_stop_key_cycle_audio(self.ss)
        self.ss["_kc_player_cmd_epoch"] = int(self.ss["_kc_player_cmd_epoch"]) + 1
        ok, why = validate_playing_ack(self.ss, self._ack("F", "C", e0, 1))
        self.assertFalse(ok)
        self.assertEqual(why, "stale_epoch")

    def test_a_chained_ack_from_the_expected_key_follows_both_steps(self) -> None:
        # The server is on C (expected F); the F confirmation was lost; the page now plays Bb, from F.
        changed, _ = kc._confirm_owner_cycle_to_playing_key(self.ss, "Bb", from_key="F", pass_id=2)
        self.assertTrue(changed)
        self.assertEqual(self._key(), "Bb")

    def test_a_jump_that_is_not_proven_is_still_refused(self) -> None:
        for playing, from_key in (("Bb", "C"), ("Bb", ""), ("Eb", "F"), ("Ab", "Bb")):
            ss_before = self._key()
            changed, _ = kc._confirm_owner_cycle_to_playing_key(self.ss, playing, from_key=from_key, pass_id=2)
            self.assertFalse(changed, (playing, from_key))
            self.assertEqual(self._key(), ss_before, (playing, from_key))

    def test_a_late_single_step_ack_after_the_chain_cannot_step_again(self) -> None:
        kc._confirm_owner_cycle_to_playing_key(self.ss, "Bb", from_key="F", pass_id=2)
        changed, _ = kc._confirm_owner_cycle_to_playing_key(self.ss, "F", from_key="C", pass_id=1)
        self.assertFalse(changed)
        self.assertEqual(self._key(), "Bb")

    def test_a_pause_at_the_end_of_a_take_holds_the_start_of_the_next_key(self) -> None:
        # Server on C, one confirmation behind: the page finished F, so the paused position is Bb.
        self._apply("pause", kc={"sounding": "Bb", "cycleId": self.cycle, "from": "F"})
        self.assertEqual(self._status(), kc.STATUS_HELD)
        self.assertEqual(self._key(), "Bb")

    def test_a_pause_report_two_ahead_without_the_finished_take_is_refused(self) -> None:
        self._apply("pause", kc={"sounding": "Bb", "cycleId": self.cycle})
        self.assertEqual(self._key(), "C")
        self._apply("resume")
        self._apply("pause", kc={"sounding": "Bb", "cycleId": self.cycle, "from": "C"})
        self.assertEqual(self._key(), "C")


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
        self.assertEqual(js.count("kcPauseBtnMode(b) !== 'resume'"), 1)  # resume align
        self.assertEqual(js.count("kcPauseBtnMode(b0) === 'resume'"), 1)  # Back to loop start
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


_PLAYING = "() => { window.__backingTransportState = {transport: 'playing'}; sessionStorage.setItem('kc_user_paused', '0'); }"
_HELD = "() => { window.__backingTransportState = {transport: 'paused'}; sessionStorage.setItem('kc_user_paused', '1'); }"


def _run_bridge(test: unittest.TestCase, label: str, icon: str, setup_js: str, action_js: str) -> dict:
    """Real bridge in a frame under a Streamlit-shaped Key Cycling Pause button (as components.html
    mounts it); ``action_js`` runs in the page and returns what it saw."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover - browser tooling not installed
        test.skipTest("playwright not installed")
    parent = (
        '<html><body><div class="st-key-backing_key_cycle_pause_btn"><button>'
        f'<span data-testid="stIconMaterial">{icon}</span>'
        f'<div data-testid="stMarkdownContainer"><p>{label}</p></div></button></div>'
        '<iframe id="kc-bridge"></iframe></body></html>'
    )
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors: list = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://kc.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body=parent))
            page.goto("http://kc.test/app/")
            page.evaluate(
                """(html) => { window.__clicks = []; const btn = document.querySelector('button');
                  window.addEventListener('click', (ev) => {
                    if (ev.target && ev.target.closest && ev.target.closest('button') === btn)
                      window.__clicks.push(btn.querySelector('p').textContent); }, true);
                  document.getElementById('kc-bridge').srcdoc = html; }""",
                _bridge_js(),
            )
            page.wait_for_function("() => typeof window.__kcRequestCyclePause === 'function'", timeout=15000)
            page.evaluate(setup_js)
            got = {"at_call": page.evaluate(action_js)}
            page.wait_for_timeout(900)
            got.update(page.evaluate(
                "() => ({clicks: window.__clicks.length, label: document.querySelector('p').textContent,"
                " userPaused: !!(window.__kcDual || {}).userPaused})"
            ))
        finally:
            browser.close()
    got["errors"] = errors
    return got


class LivePlayerUsesTheConsolePause(unittest.TestCase):
    """The Lead Sheet's Pause / Resume (__kcRequestCyclePause / __kcRequestCycleResume) press the
    Key Cycling Pause button itself, once and at once, when the console's own decision agrees.

    Browser runs 2026-11-14 with the real Lead Sheet button, normal speed:
    - dev 59e77f35 / 2313403a: the live Pause never clicked (it paused the audio first, which
      relabelled the button Resume), so the server stayed Running and the audio came back.
    - after reading the button first (e9692f4d): Pause reached the server, but every live Resume
      was silent: its click waited 350 ms on this bridge frame's timer, a Streamlit rerun replaced
      the frame, the timer never fired and the server stayed Held -- the kicked audio was paused
      again 1-3 s later. And the live player still skipped the card's protections (sounding key,
      stale-command guard), so a take starting in a handoff gap leaked for ~3 s."""

    def test_pause_from_playing_presses_the_console_button_once_and_at_once(self) -> None:
        got = _run_bridge(self, "Pause", "pause", _PLAYING,
                          "() => { window.__kcRequestCyclePause(); return window.__clicks.length; }")
        # One press of the console's button, synchronous (no timer a remount can drop). What that
        # press does (handler, card command, server) is the console's own, verified in the browser.
        self.assertEqual(got["at_call"], 1, got)
        self.assertEqual(got["clicks"], 1, got)
        self.assertEqual(got["errors"], [], got)

    def test_pause_when_held_does_not_press(self) -> None:
        # The server toggles on this click (Held -> Resume), so a held player must not press.
        got = _run_bridge(self, "Resume", "play_arrow", _HELD,
                          "() => { window.__kcRequestCyclePause(); return window.__clicks.length; }")
        self.assertEqual(got["clicks"], 0, got)
        self.assertEqual(got["errors"], [], got)

    def test_resume_when_held_presses_at_once_and_survives_a_bridge_remount(self) -> None:
        # The frame that made the call is removed straight away, as a Streamlit rerun does.
        got = _run_bridge(self, "Resume", "play_arrow", _HELD,
                          "() => { window.__kcRequestCycleResume(); const n = window.__clicks.length;"
                          " document.getElementById('kc-bridge').remove(); return n; }")
        self.assertEqual(got["at_call"], 1, got)
        self.assertEqual(got["clicks"], 1, got)
        self.assertFalse(got["userPaused"], got)
        self.assertEqual(got["errors"], [], got)

    def test_resume_when_playing_does_not_press(self) -> None:
        got = _run_bridge(self, "Pause", "pause", _PLAYING,
                          "() => { window.__kcRequestCycleResume(); return window.__clicks.length; }")
        self.assertEqual(got["clicks"], 0, got)
        self.assertEqual(got["errors"], [], got)

    def test_both_controls_share_one_decision_and_one_press(self) -> None:
        js = _bridge_js()
        live = js[js.index("__kcPressCycleTransport = function"):js.index("__kcPauseAudio = function")]
        live += js[js.index("__kcRequestCyclePause = function"):js.index("__kcResumeAudio = function")]
        for gone in ("setTimeout", "__kcProgrammaticPauseClick = true", "__kcSkipPauseHandler = true",
                     "needStreamlitResume", "{ force: true }"):
            self.assertNotIn(gone, live)
        self.assertEqual(live.count("if (kcLivePressPauses()) return;  // already playing"), 1)
        self.assertEqual(live.count("if (!kcLivePressPauses()) return;  // already paused"), 1)
        self.assertEqual(live.count("parentWin.__kcPressCycleTransport()"), 2)
        # The console's own press decides from the same function.
        self.assertIn("const running = kcCyclePressPauses(label);", js)
        self.assertIn("parentWin.__kcCyclePressPauses = function", js)
        # The visible button, never a hidden duplicate.
        self.assertIn("all.find((x) => x.offsetParent !== null) || all[0]", live)


class LeadSheetAsksTheConsole(unittest.TestCase):
    """The Lead Sheet's Pause/Resume button decides (and labels itself) from the console's decision.
    Judged from its own buffer probe, a press during a pause whose hold flag had been cleared at a
    take's end (a handoff still marked in flight) became a second Pause (browser run 2026-11-14)."""

    def _press_lead_sheet(self, console_press_pauses: bool) -> dict:
        try:
            from playwright import sync_api
        except Exception:  # pragma: no cover - browser tooling not installed
            self.skipTest("playwright not installed")
        import streamlit_music_practice_app as app

        html = app.live_follow_along_component_html(b"", [], "", audio_url="app/static/kc/aaaa.wav", autoplay=False)
        stub = (
            "(args) => { const [html, pauses] = args; window.__calls = [];"
            " window.__kcDual = {enabled: true, swapping: true, pendingHandoff: true};"  # a handoff marked in flight
            " window.__kcCyclePressPauses = () => pauses;"
            " window.__kcRequestCyclePause = () => window.__calls.push('pause');"
            " window.__kcRequestCycleResume = () => window.__calls.push('resume');"
            " const f = document.createElement('iframe'); f.id = 'ls'; document.body.appendChild(f); f.srcdoc = html; }"
        )
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route("http://kc.test/**", lambda route: route.fulfill(
                    status=200, content_type="text/html", body="<html><body></body></html>"))
                page.goto("http://kc.test/app/")
                page.evaluate(stub, [html, console_press_pauses])
                frame = None
                for _ in range(100):
                    frame = next((f for f in page.frames if f != page.main_frame
                                  and f.query_selector("#live-stop-btn")), None)
                    if frame:
                        break
                    page.wait_for_timeout(100)
                self.assertIsNotNone(frame, "Lead Sheet frame did not load")
                frame.evaluate("() => { try { syncStopResumeLabel(); } catch (e) {} }")
                label = frame.eval_on_selector("#live-stop-btn", "b => b.textContent")
                frame.eval_on_selector("#live-stop-btn", "b => b.click()")
                page.wait_for_timeout(200)
                calls = page.evaluate("() => window.__calls")
            finally:
                browser.close()
        return {"label": label, "calls": calls}

    def test_a_held_console_makes_the_lead_sheet_resume(self) -> None:
        got = self._press_lead_sheet(console_press_pauses=False)
        self.assertEqual(got["calls"], ["resume"], got)
        self.assertIn("Resume", got["label"], got)

    def test_a_playing_console_makes_the_lead_sheet_pause(self) -> None:
        got = self._press_lead_sheet(console_press_pauses=True)
        self.assertEqual(got["calls"], ["pause"], got)
        self.assertIn("Pause", got["label"], got)


def _silent_wav(seconds: float = 6.0, sr: int = 8000) -> bytes:
    import io
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<h", 0) * int(sr * seconds))
    return buf.getvalue()


_RUNNING = {"enabled": True, "epoch": 9, "cycleId": "cyc-A", "currentUrl": "app/static/kc/bm.wav",
            "nextUrl": "app/static/kc/em.wav", "currentSounding": "Bm", "nextSounding": "Em",
            "autoplay": True, "forcePlay": True}
_SNAP = """() => { const d = window.__kcDual || {};
  const live = [...document.querySelectorAll('audio[id^="kc-"]')].filter(a => !a.paused && !a.ended);
  return {enabled: !!d.enabled, epoch: d.epoch, cycle: d.cycleId, stopped: d.stoppedEpoch != null,
          playing: live.length, plays: window.__plays.length,
          trace: (window.__kcApplyTrace || []).slice(-4).map(r => r.reason)}; }"""


def _run_stop_race(test: unittest.TestCase, ops: list) -> list:
    """Real bridge on a test origin with real (silent) takes; a running cycle is mounted and
    mounted, then ``ops`` run in order: "stop" (the page's Key Cycling Stop), ("cmd", command)
    (a command arriving from the server), ("age", ms) (the Stop is ms older). Returns a
    snapshot after each op."""
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover - browser tooling not installed
        test.skipTest("playwright not installed")
    import json

    wav = _silent_wav()
    parent = ('<html><body><div class="st-key-backing_key_cycle_pause_btn"><button><p>Pause</p></button></div>'
              '<iframe id="kc-bridge"></iframe></body></html>')
    bridge = kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(_RUNNING))

    def handle(route):
        if route.request.url.endswith(".wav"):
            # Byte ranges, as a static file server answers them: without them Chromium cannot seek.
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
            route.fulfill(status=200, content_type="text/html", body=parent)

    snaps = []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page()
            errors: list = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://kc.test/**", handle)
            page.goto("http://kc.test/app/")
            page.evaluate("""(html) => { window.__plays = []; const P = HTMLMediaElement.prototype; const o = P.play;
              P.play = function () { window.__plays.push(this.id); return o.apply(this, arguments); };
              document.getElementById('kc-bridge').srcdoc = html; }""", bridge)
            page.wait_for_function("() => typeof window.__kcHardStop === 'function'", timeout=15000)
            page.wait_for_timeout(1500)
            snaps.append(page.evaluate(_SNAP))
            for op in ops:
                if op == "stop":
                    page.evaluate("() => window.__kcHardStop()")
                elif op[0] == "cmd":
                    page.evaluate("(c) => window.__kcApplyCmd(c)", op[1])
                elif op[0] == "eval":
                    snaps.append({"eval": page.evaluate(op[1])})
                    continue
                elif op[0] == "age":
                    page.evaluate("(ms) => { window.__kcDual.stoppedAt = Number(window.__kcDual.stoppedAt || Date.now()) - ms; }",
                                  op[1])
                page.wait_for_timeout(900)
                snaps.append(page.evaluate(_SNAP))
        finally:
            browser.close()
    test.assertEqual(errors, [], errors)
    return snaps


_START = dict(_RUNNING, epoch=10, restart=True, sounding="Bm")  # a deliberate start: the Bm take plays
_ACTIVE_JS = """() => { const d = window.__kcDual || {}; const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  return a ? {src: String(a.currentSrc || a.src || '').split('/').pop(), ct: Number(a.currentTime || 0), paused: a.paused,
              ended: a.ended, key: a.getAttribute('data-kc-sounding') || '', up: !!d.userPaused} : null; }"""
# Run the take to 0.3 s before its end, Pause and Resume there (the page's own Resume), then wait.
_RESUME_AT_END_JS = """async () => { const d = window.__kcDual; d.sequence = ['Bm', 'Em', 'Am'];
  const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  a.currentTime = Math.max(0, a.duration - 0.3); await new Promise(r => setTimeout(r, 50));
  window.__kcPauseAudio(); await new Promise(r => setTimeout(r, 300));
  window.__kcResumeAudio(); await new Promise(r => setTimeout(r, 2600));
  const live = ['kc-buf-0', 'kc-buf-1'].map(i => document.getElementById(i)).filter(x => x && !x.paused && !x.ended)
    .map(x => String(x.currentSrc || x.src).split('/').pop());
  return {src: String(a.currentSrc || a.src).split('/').pop(), ct: Number(a.currentTime), paused: a.paused, ended: a.ended, live}; }"""
_FINISH_JS = """async () => { const d = window.__kcDual; const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  a.currentTime = Math.max(0, a.duration - 0.2); await new Promise(r => setTimeout(r, 900));
  return {ended: a.ended, ct: Number(a.currentTime)}; }"""


class LateResumeNeverReplaysAFinishedTake(unittest.TestCase):
    """Browser trace 2026-11-14 (Lead Sheet and console, Resume 0.8 s before a take's end):
    Gm, Gm, Cm, Gm. (1) The page's own Resume kept kicking play() at 0 / 500 / 1500 ms; once the
    take had ended, play() restarted it from 0 -- the same key again. (2) The server's answer to
    that Resume arrived 11 s later, after the page had moved on to Cm, and reloaded Gm -- a step
    back. A finished take must continue to the next key; a late answer must not touch the audio."""

    def _assert_not_replayed(self, got: dict) -> None:
        # A replay is the same take playing again from near its start.
        self.assertFalse(got["src"] == "bm.wav" and not got["paused"] and got["ct"] < 2.0, got)

    def test_resume_just_before_the_end_does_not_replay_the_take(self) -> None:
        got = _run_stop_race(self, [("cmd", _START), ("eval", _RESUME_AT_END_JS)])[-1]["eval"]
        self._assert_not_replayed(got)
        self.assertEqual(got["live"], ["em.wav"], got)  # the cycle went on to the next key

    def test_a_late_answer_after_the_take_finished_does_not_replay_it(self) -> None:
        # Bm finishes and the cycle hands off to Em on its own; the server's late answer still names Bm.
        seq = "() => { window.__kcDual.sequence = ['Bm', 'Em', 'Am']; return true; }"
        snaps = _run_stop_race(self, [("cmd", _START), ("eval", seq), ("eval", _FINISH_JS),
                                      ("cmd", dict(_START, epoch=11, restart=False, resume=True)), ("eval", _ACTIVE_JS)])
        got = snaps[-1]["eval"]
        self._assert_not_replayed(got)
        self.assertEqual((got["src"], got["paused"]), ("em.wav", False), got)

    def test_a_late_answer_after_the_cycle_moved_on_does_not_step_back(self) -> None:
        # The page is playing the next take; the server's answer still names the paused one.
        moved = dict(_START, epoch=11, restart=True, currentUrl="app/static/kc/em.wav", sounding="Em",
                     nextUrl="app/static/kc/am.wav", nextSounding="Am")
        late = dict(_START, epoch=12, restart=False, resume=True, currentUrl="app/static/kc/bm.wav", sounding="Bm")
        snaps = _run_stop_race(self, [("cmd", _START), ("cmd", moved), ("cmd", late), ("eval", _ACTIVE_JS)])
        got = snaps[-1]["eval"]
        self.assertEqual(got["src"], "em.wav", got)
        self.assertEqual(got["key"], "Em", got)
        self.assertFalse(got["paused"], got)

    def test_a_deliberate_restart_after_the_take_finished_still_plays_it(self) -> None:
        snaps = _run_stop_race(self, [("cmd", _START), ("eval", _FINISH_JS),
                                      ("cmd", dict(_START, epoch=11)), ("eval", _ACTIVE_JS)])
        got = snaps[-1]["eval"]
        self.assertEqual(got["src"], "bm.wav", got)
        self.assertFalse(got["paused"], got)
        self.assertLess(got["ct"], 2.0, got)  # from the start, as asked

    def test_the_servers_resume_still_resumes_a_page_that_is_still_held(self) -> None:
        # Not an answer to the page's own Resume (the page is still paused): it applies as before.
        snaps = _run_stop_race(self, [("cmd", _START), ("eval", "() => { window.__kcPauseAudio(); return true; }"),
                                      ("cmd", dict(_START, epoch=11, restart=False, resume=True)), ("eval", _ACTIVE_JS)])
        got = snaps[-1]["eval"]
        self.assertEqual(got["src"], "bm.wav", got)
        self.assertFalse(got["paused"], got)
        self.assertFalse(got["up"], got)


class PauseInTheSilentGapReportsTheKeyResumePlays(unittest.TestCase):
    """Browser trace 2026-11-14 (final candidate): a Pause in the gap between two takes reported the
    last AUDIBLE key (Gm), so the server and console held Gm -- but the handoff had already made the
    incoming Cm take the active one, and Resume played Cm. The Pause now reports the key Resume will
    play: the active take's, or the next key when the active take has finished."""

    _GAP = """async (mode) => { const d = window.__kcDual; d.sequence = ['Bm', 'Em', 'Am'];
      await new Promise(r => setTimeout(r, 300));
      if (typeof window.__kcPauseBtnHandler !== 'function') return 'no handler';
      const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
      a.pause();
      if (mode === 'finished') { a.currentTime = a.duration; d.nextSounding = 'Em'; }
      else { a.currentTime = 0; a.setAttribute('data-kc-sounding', 'Em'); }  // the incoming take, not started yet
      await new Promise(r => setTimeout(r, 150));
      window.__kcLastLive = {key: 'Bm', at: Date.now()};  // the last key heard
      window.__backingTransportState = {transport: 'playing'}; d.userPaused = false;
      try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
      window.__kcPauseToggleAt = 0;
      window.__kcPauseBtnHandler();
      return (window.__kcPauseSounding || {}).key || ''; }"""

    def test_a_finished_active_take_reports_the_next_key(self) -> None:
        got = _run_stop_race(self, [("cmd", _START), ("eval", "(" + self._GAP + ")('finished')")])[-1]["eval"]
        self.assertEqual(got, "Em", got)

    def test_an_incoming_take_already_active_reports_its_own_key(self) -> None:
        got = _run_stop_race(self, [("cmd", _START), ("eval", "(" + self._GAP + ")('incoming')")])[-1]["eval"]
        self.assertEqual(got, "Em", got)


class PauseAtATakeBoundaryHasOnePosition(unittest.TestCase):
    """The boundary rule, decided when Pause takes effect (no time margin): a take that has not
    ended keeps its key and position; one that has ended pauses at the start of the next key; the
    final key keeps its completed end state. Recorded failures 2026-11-14 (Lead Sheet, normal speed):
    Dm / Gm / Cm paused at the very end froze the finished key while Resume moved on; Bbm with 0.26 s
    and G#m with 0.28 s left were replayed after Resume."""

    _PRESS = """async ([seq, left, ended]) => { const d = window.__kcDual; d.sequence = seq;
      await new Promise(r => setTimeout(r, 300));
      const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
      if (ended) { a.pause(); a.currentTime = a.duration; }
      else { a.currentTime = Math.max(0, a.duration - left); }
      await new Promise(r => setTimeout(r, 60));
      window.__backingTransportState = {transport: 'playing'}; d.userPaused = false;
      try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
      window.__kcPauseToggleAt = 0;
      const before = Number(a.currentTime);
      window.__kcPauseBtnHandler();
      const stash = window.__kcPauseSounding || {};
      return {key: stash.key || '', from: stash.from || '', at: before, held: Number(window.__kcLastPauseT),
              dur: Number(a.duration)}; }"""

    def _press(self, seq, left, ended):
        return _run_stop_race(self, [("cmd", _START), ("eval", "(" + self._PRESS + ")(" + __import__("json").dumps([seq, left, ended]) + ")")])[-1]["eval"]

    def test_bbm_with_0_26_s_left_keeps_its_key_and_the_remaining_0_26_s(self) -> None:
        got = self._press(["Bm", "Em", "Am"], 0.26, False)
        self.assertEqual((got["key"], got["from"]), ("Bm", ""), got)
        self.assertAlmostEqual(got["held"], got["dur"] - 0.26, delta=0.12)  # the position is kept

    def test_g_sharp_m_with_0_28_s_left_keeps_its_key(self) -> None:
        got = self._press(["Bm", "Em", "Am"], 0.28, False)
        self.assertEqual((got["key"], got["from"]), ("Bm", ""), got)

    def test_a_take_that_has_ended_pauses_at_the_start_of_the_next_key(self) -> None:
        got = self._press(["Bm", "Em", "Am"], 0, True)
        self.assertEqual((got["key"], got["from"]), ("Em", "Bm"), got)

    def test_the_final_key_keeps_its_completed_end_state(self) -> None:
        got = self._press(["Am", "Bm"], 0, True)
        self.assertEqual((got["key"], got["from"]), ("Bm", ""), got)

    def test_resume_continues_the_kept_position(self) -> None:
        probe = """async () => { const d = window.__kcDual; d.sequence = ['Bm', 'Em', 'Am'];
          await new Promise(r => setTimeout(r, 300));
          const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          a.currentTime = 2.0; await new Promise(r => setTimeout(r, 80));
          window.__kcPauseAudio(); await new Promise(r => setTimeout(r, 400));
          window.__kcResumeAudio(); await new Promise(r => setTimeout(r, 500));
          return {src: String(a.currentSrc || a.src).split('/').pop(), ct: Number(a.currentTime), paused: a.paused}; }"""
        got = _run_stop_race(self, [("cmd", _START), ("eval", probe)])[-1]["eval"]
        self.assertEqual(got["src"], "bm.wav", got)
        self.assertFalse(got["paused"], got)
        self.assertGreater(got["ct"], 2.0, got)  # continued from 2.0 s, not restarted
        self.assertLess(got["ct"], 3.5, got)


class ThePageNeverArmsItsOwnKeyAsNext(unittest.TestCase):
    """KC-F1 page side (trace 2026-11-14: playing Dm, expected Gm, armed Dm): a server one
    confirmation behind names the key the page is already playing as "next"; the end-of-take
    check then refused the real next key and the cycle replayed or stepped back."""

    def test_a_server_one_behind_arms_its_following_key_as_next(self) -> None:
        playing_em = dict(_START, epoch=11, restart=True, currentUrl="app/static/kc/em.wav", sounding="Em",
                          nextUrl="app/static/kc/am.wav", nextSounding="Am")
        behind = {"enabled": True, "epoch": 12, "cycleId": "cyc-A", "sounding": "Bm", "currentUrl": "app/static/kc/bm.wav",
                  "nextUrl": "app/static/kc/em.wav", "nextSounding": "Em",
                  "followingUrl": "app/static/kc/am.wav", "followingSounding": "Am",
                  "aheadUrl": "app/static/kc/dm.wav", "aheadSounding": "Dm"}
        snaps = _run_stop_race(self, [("cmd", _START), ("cmd", playing_em), ("cmd", behind),
                                      ("eval", "() => ({next: window.__kcDual.nextSounding, following: window.__kcDual.followingSounding})"),
                                      ("eval", _ACTIVE_JS)])
        got = snaps[-2]["eval"]
        self.assertEqual(got["next"], "Am", got)
        self.assertNotEqual(got["following"], "Am", got)  # never the same take twice
        active = snaps[-1]["eval"]  # and the take the page is playing stays
        self.assertEqual((active["src"], active["key"], active["paused"]), ("em.wav", "Em", False), active)


class PauseCancelsAHandoffInFlight(unittest.TestCase):
    """Browser trace 2026-11-14 (final candidate, real Lead Sheet button, 3 of 6 rounds): a Pause
    about 1 s before an automatic change let the handoff that had already begun start the next
    take behind the Pause (heard Dm; Gm sounding 1 s later; the server then froze Gm). Its
    callbacks (beginPlay / kickPlay, the seek fallback, the re-kick) check only that the
    handoff token is still theirs, and Pause did not change it. A parent-page play retry then
    unmuted a refused take while the server still reported "playing"."""

    def test_pause_invalidates_the_handoff_token(self) -> None:
        got = _run_stop_race(self, [("eval", "() => { window.__kcDual.handoffToken = 'h-in-flight';"
                                               " window.__kcPauseAudio(); return window.__kcDual.handoffToken; }")])
        self.assertIsNone(got[-1]["eval"], got)

    def test_stop_invalidates_the_handoff_token_too(self) -> None:
        got = _run_stop_race(self, [("eval", "() => { window.__kcDual.handoffToken = 'h-in-flight';"
                                               " window.__kcHardStop(); return window.__kcDual.handoffToken; }")])
        self.assertIsNone(got[-1]["eval"], got)

    def test_the_play_retry_never_restarts_a_take_the_musician_paused(self) -> None:
        # A take whose play() is refused (unsupported source) while the page is held; the server's
        # transport state still says "playing" (it confirms a Pause seconds later).
        probe = """async (held) => {
          if (!HTMLMediaElement.prototype.__kcPlayRetryPatched) return 'retry patch not installed';
          if (held) window.__kcPauseAudio();  // the musician's Pause (the page's own hold)
          window.__backingTransportState = {transport: 'playing'};  // the server has not confirmed it yet
          window.__kcDual.userPaused = held;
          try { sessionStorage.setItem('kc_user_paused', held ? '1' : '0'); } catch (e) {}
          const a = document.createElement('audio'); a.id = 'kc-buf-test'; a.muted = true;
          a.src = 'data:audio/wav;base64,AAAA'; document.body.appendChild(a);
          try { await a.play(); } catch (e) {}
          await new Promise(r => setTimeout(r, 400));
          return {muted: a.muted, autoplay: a.autoplay};
        }"""
        held = _run_stop_race(self, [("eval", "() => (" + probe + ")(true)")])[-1]["eval"]
        self.assertEqual(held, {"muted": True, "autoplay": False}, held)
        playing = _run_stop_race(self, [("eval", "() => (" + probe + ")(false)")])[-1]["eval"]
        self.assertEqual(playing, {"muted": False, "autoplay": True}, playing)  # the retry itself still works


_SEQ_GM = ["Gm", "Cm", "Fm", "Bbm", "Ebm"]
# What is heard: every Key Cycling take that is playing, unmuted, at a volume above zero.
_HEARD_JS = """() => { const d = window.__kcDual || {};
  const tail = (x) => String(x.src || x.currentSrc || '').split('/').pop();  // src: currentSrc lags a switch
  const heard = [...document.querySelectorAll('audio[id^="kc-"]')]
    .filter(x => !x.paused && !x.ended && !x.muted && Number(x.volume) > 0.01).map(tail);
  const running = [...document.querySelectorAll('audio[id^="kc-"]')].filter(x => !x.paused && !x.ended)
    .map(x => ({src: tail(x), muted: x.muted, volume: Number(x.volume)}));
  const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  return {heard, running, active: a ? tail(a) : '', key: a ? (a.getAttribute('data-kc-sounding') || '') : '',
          next: String(d.nextSounding || ''), nextUrl: String(d.nextUrl || '').split('/').pop(),
          restored: (window.__kcPlayDiag || []).filter(r => r.ev === 'audible_restored').map(r => r.why)}; }"""
_FINISH_ACTIVE_JS = """async () => { const d = window.__kcDual; const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
  a.currentTime = Math.max(0, a.duration - 0.2); await new Promise(r => setTimeout(r, 900)); return {ended: a.ended}; }"""


def _take(key: str) -> str:
    return f"app/static/kc/{key.lower().replace('#', 's')}.wav"


def _kc_cmd(epoch: int, sounding: str, nxt: str = "", following: str = "", **extra) -> dict:
    cmd = {"enabled": True, "epoch": epoch, "cycleId": "cyc-A", "sequence": list(_SEQ_GM),
           "sounding": sounding, "currentUrl": _take(sounding)}
    if nxt:
        cmd.update(nextUrl=_take(nxt), nextSounding=nxt)
    if following:
        cmd.update(followingUrl=_take(following), followingSounding=following)
    cmd.update(extra)
    return cmd


class ATakeMarkedPlayingIsHeard(unittest.TestCase):
    """Browser trace 2026-11-15 (candidate 0ed8062b, console Resume, six-second Mission takes):
    Cm ended with no next take prepared; the server's late answer named Fm and the page loaded
    it cold into a slot it had silenced as idle (muted, volume 0). The cold start plays muted and
    unmutes when play() resolves, leaving the volume to kickPlay -- which returns once the handoff
    has settled. Fm played its whole six seconds at volume 0 while the server said Running."""

    def _late_answer_after_cm_ended(self, extra_js: str = "") -> dict:
        start = _kc_cmd(10, "Cm", restart=True, autoplay=True, forcePlay=True)  # nothing prepared after Cm
        silence_idle = """() => { const d = window.__kcDual; d.sequence = %s;
          const idle = document.getElementById(d.active === 1 ? 'kc-buf-0' : 'kc-buf-1');
          // As after the switch into Cm: the outgoing slot is emptied and parked muted at volume 0.
          try { idle.pause(); idle.removeAttribute('src'); idle.removeAttribute('data-kc-url');
                idle.removeAttribute('data-kc-sounding'); idle.load(); } catch (e) {}
          idle.muted = true; idle.volume = 0;
          d.nextUrl = ''; d.nextSounding = ''; %s return true; }""" % (__import__("json").dumps(_SEQ_GM), extra_js)
        # The recorded chain: the late answer starts the switch into Fm; a rerun replaces the bridge
        # frame mid-switch and its mount reloads the active take, so Fm's muted cold start is
        # "interrupted by a new load request" (AbortError) and only the rejection handler runs;
        # the parent page's retry then starts it.
        late = _kc_cmd(11, "Cm", "Fm", resume=True, restart=False, autoplay=False)
        answer_and_remount = """async () => { const d = window.__kcDual;
          // The parent page's own start of the switched-in take is in flight (it sets this shared
          // flag around its play()), so the bridge's kickPlay -- the only place this path set the
          // volume -- returns early and the handoff settles through the parent page.
          d._kcPlayInFlight = true;
          window.__kcApplyCmd(%s);
          let act = null;
          for (let i = 0; i < 400; i++) {
            act = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
            if (d.swapping && act && String(act.getAttribute('data-kc-url') || '').endsWith('/fm.wav')) break;
            await new Promise(r => setTimeout(r, 5));
          }
          // The rerun replaces the bridge frame: the frame-side timers and intervals (the page's own
          // "one audible take" sweep among them) die with it, as they do in the app. Its mount
          // reloads the active take, interrupting the muted start.
          const frame = document.getElementById('kc-bridge');
          const html = frame.srcdoc; frame.srcdoc = '';
          act.src = 'app/static/kc/fm.wav'; act.load();
          await new Promise(r => setTimeout(r, 50));
          frame.srcdoc = html;
          await new Promise(r => setTimeout(r, 3000)); return true; }""" % __import__("json").dumps(late)
        snaps = _run_stop_race(self, [("cmd", start), ("eval", silence_idle), ("eval", _FINISH_ACTIVE_JS),
                                      ("eval", answer_and_remount), ("eval", _HEARD_JS)])
        return snaps[-1]["eval"]

    def test_a_cold_take_started_from_a_silenced_slot_is_heard(self) -> None:
        got = self._late_answer_after_cm_ended()
        self.assertEqual((got["active"], got["key"]), ("fm.wav", "Fm"), got)
        self.assertEqual(got["heard"], ["fm.wav"], got)  # heard, and the only take heard

    # __kcEnsureAudible on the playing take, after `setup` (which may await). The musician's own
    # setting is a touch on the player's media controls, then the change.
    _ON_PLAYING = """async () => { const d = window.__kcDual;
      const act = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
      const touch = () => act.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
      const wait = (ms) => new Promise(r => setTimeout(r, ms));
      await wait(2500);  // past the start's own play kicks (they set volume 1 at fixed delays)
      %s
      const restored = window.__kcEnsureAudible(act, 'test');
      return {restored, muted: act.muted, volume: Number(act.volume)}; }"""

    def _on_playing(self, setup: str) -> dict:
        start = _kc_cmd(10, "Cm", "Fm", restart=True, autoplay=True, forcePlay=True)
        return _run_stop_race(self, [("cmd", start), ("eval", self._ON_PLAYING % setup)])[-1]["eval"]

    def test_a_volume_control_level_is_left_alone(self) -> None:
        # Only a ZERO volume is restored; a level that is already set is never raised to 100%.
        got = self._on_playing("act.muted = true; act.volume = 0.4;")
        self.assertEqual(got, {"restored": True, "muted": False, "volume": 0.4}, got)

    def test_a_level_the_musician_set_is_the_level_restored(self) -> None:
        # The musician sets 0.5; later the page parks the take at 0 (no touch): back to 0.5, not 1.0.
        got = self._on_playing("touch(); act.volume = 0.5; await wait(1700); act.muted = true; act.volume = 0;")
        self.assertEqual(got, {"restored": True, "muted": False, "volume": 0.5}, got)

    def test_a_mute_the_musician_chose_is_kept(self) -> None:
        # __kcEnsureAudible leaves it alone (recorded as the musician's mute). Pre-existing and not
        # changed here: the page's one-audible-take sweep unmutes the active take within ~250 ms
        # anyway, so a mute on the native controls does not hold (KC follow-up).
        got = self._on_playing("touch(); act.muted = true; await wait(120); const um = !!d.userMuted;"
                               " act.muted = true; const r0 = window.__kcEnsureAudible(act, 'test');"
                               " return {restored: r0, userMuted: um, mutedAfter: act.muted};")
        self.assertEqual(got, {"restored": False, "userMuted": True, "mutedAfter": True}, got)

    def test_only_the_active_take_is_ever_made_audible(self) -> None:
        # The idle slot (silenced, muted) is never touched: only the take that is playing.
        probe = """async () => { const d = window.__kcDual;
          const idle = document.getElementById(d.active === 1 ? 'kc-buf-0' : 'kc-buf-1');
          idle.muted = true; idle.volume = 0;
          const r = window.__kcEnsureAudible(idle, 'test_idle');
          return {restored: r, muted: idle.muted, volume: Number(idle.volume)}; }"""
        got = _run_stop_race(self, [("cmd", _kc_cmd(10, "Cm", "Fm", restart=True, autoplay=True, forcePlay=True)),
                                    ("eval", probe)])[-1]["eval"]
        self.assertEqual(got, {"restored": False, "muted": True, "volume": 0}, got)

    def test_nothing_is_made_audible_while_paused(self) -> None:
        probe = """async () => { const d = window.__kcDual;
          const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          window.__kcPauseAudio(); await new Promise(r => setTimeout(r, 200));
          a.muted = true; a.volume = 0;
          return {restored: window.__kcEnsureAudible(a, 'test_paused'), muted: a.muted, volume: Number(a.volume)}; }"""
        got = _run_stop_race(self, [("cmd", _kc_cmd(10, "Cm", "Fm", restart=True, autoplay=True, forcePlay=True)),
                                    ("eval", probe)])[-1]["eval"]
        self.assertEqual(got, {"restored": False, "muted": True, "volume": 0}, got)


class ResumePreparesTheNextKeyWithoutTheServer(unittest.TestCase):
    """Browser trace 2026-11-15 (same round): Gm ended inside the Pause, so the server held the
    start of Cm (the boundary rule) and Resume played Cm. The server's answer to the Resume --
    the command naming Cm's next key -- came 6.5 s later, after Cm had ended. The page had armed
    the server's "next" (Fm) as next-after-Gm; the end-of-take check refused it and dropped it,
    so nothing was prepared after Cm. The page now maps a server one key ahead onto its own
    neighbours, so Fm is prepared while Cm plays and starts at Cm's end without that answer."""

    _PAUSE_AT_GM_END = """async () => { const d = window.__kcDual; d.sequence = %s;
      const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
      // Run into the end naturally (Cm is warm-started muted in the other slot), Pause 0.3 s before it.
      a.currentTime = Math.max(0, a.duration - 1.4);
      for (let i = 0; i < 40 && Number(a.currentTime) < a.duration - 0.3; i++) await new Promise(r => setTimeout(r, 50));
      window.__kcPauseAudio(); await new Promise(r => setTimeout(r, 100));
      a.currentTime = a.duration;  // Gm reaches its end inside the Pause
      await new Promise(r => setTimeout(r, 300)); return {ended: a.ended}; }"""
    _RESUME = """async () => { window.__kcResumeAudio(); await new Promise(r => setTimeout(r, 1500)); return true; }"""

    def _resume_without_answer(self, seq, held, after_resume_ops=()):
        start = _kc_cmd(10, "Gm", "Cm", restart=True, autoplay=True, forcePlay=True, sequence=list(seq))
        pause = self._PAUSE_AT_GM_END % __import__("json").dumps(list(seq))
        return _run_stop_race(self, [("cmd", start), ("eval", pause), ("cmd", held), ("eval", self._RESUME),
                                     ("eval", _HEARD_JS), *after_resume_ops, ("eval", _FINISH_ACTIVE_JS),
                                     ("eval", "async () => { await new Promise(r => setTimeout(r, 2500)); return true; }"),
                                     ("eval", _HEARD_JS)])

    def _held_cm(self, **extra):
        # The server's paused command after the boundary Pause: current Cm, its next Fm.
        return _kc_cmd(11, "Cm", "Fm", paused=True, autoplay=False, forcePlay=False, restart=False, **extra)

    def test_fm_is_prepared_while_cm_plays_and_follows_it_audibly(self) -> None:
        snaps = self._resume_without_answer(_SEQ_GM, self._held_cm())
        resumed, after = snaps[5]["eval"], snaps[-1]["eval"]
        self.assertEqual((resumed["active"], resumed["heard"]), ("cm.wav", ["cm.wav"]), resumed)
        self.assertEqual(resumed["next"], "Fm", resumed)  # prepared before any server answer
        self.assertEqual((after["key"], after["heard"]), ("Fm", ["fm.wav"]), after)

    def test_a_following_key_in_the_held_command_is_not_skipped_to(self) -> None:
        snaps = self._resume_without_answer(_SEQ_GM, self._held_cm(followingUrl=_take("Bbm"), followingSounding="Bbm"))
        resumed, after = snaps[5]["eval"], snaps[-1]["eval"]
        self.assertEqual(resumed["next"], "Fm", resumed)
        self.assertEqual((after["key"], after["heard"]), ("Fm", ["fm.wav"]), after)  # Cm, then Fm: never Bbm

    def test_stop_after_the_resume_prepares_and_plays_nothing(self) -> None:
        snaps = self._resume_without_answer(_SEQ_GM, self._held_cm(),
                                            [("eval", "() => { window.__kcHardStop(); return true; }")])
        after = snaps[-1]["eval"]
        self.assertEqual(after["heard"], [], after)
        self.assertEqual(after["running"], [], after)

    def test_pause_after_the_resume_does_not_advance(self) -> None:
        snaps = self._resume_without_answer(_SEQ_GM, self._held_cm(),
                                            [("eval", "() => { window.__kcPauseAudio(); return true; }")])
        after = snaps[-1]["eval"]
        self.assertEqual(after["heard"], [], after)
        self.assertNotIn("fm.wav", [r["src"] for r in after["running"]], after)

    def test_the_final_key_plays_once_and_then_the_cycle_ends(self) -> None:
        # Gm (second-last) ends inside the Pause, so the start of the final key Cm is held. The held
        # command used to latch "final key" from the SERVER's key while the page's take was still Gm,
        # so Resume stopped the cycle (final_key_stop) and Cm was never heard (b65d278a and before).
        seq = ["Gm", "Cm"]
        held = _kc_cmd(11, "Cm", paused=True, autoplay=False, forcePlay=False, restart=False, sequence=seq)
        snaps = self._resume_without_answer(seq, held)
        resumed, after = snaps[5]["eval"], snaps[-1]["eval"]
        self.assertEqual((resumed["key"], resumed["heard"]), ("Cm", ["cm.wav"]), resumed)  # from its start
        self.assertEqual(after["heard"], [], after)  # Cm was the last key: no wrap to Gm
        self.assertEqual(after["running"], [], after)  # and Cm is not started again
        self.assertEqual(after["key"], "Cm", after)


# Records, every 50 ms for `ms`, which take is heard; a take whose position jumps back is a restart.
_RECORD_HEARD_JS = """async (ms) => { const out = []; const restarts = []; const last = {};
  const tail = (x) => String(x.src || x.currentSrc || '').split('/').pop();
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const heard = [...document.querySelectorAll('audio[id^="kc-"]')]
      .filter(x => !x.paused && !x.ended && !x.muted && Number(x.volume) > 0.01);
    heard.forEach(x => { const s = tail(x); const ct = Number(x.currentTime);
      if (last[s] != null && ct < last[s] - 0.5) restarts.push(s); last[s] = ct; });
    const names = heard.map(tail);
    if (names.length > 1) out.push(names.join('+'));
    else if (names.length === 1 && out[out.length - 1] !== names[0]) out.push(names[0]);
    await new Promise(r => setTimeout(r, 50));
  }
  return {sequence: out, restarts}; }"""


class TheFinishedTakeIsNeverReplayedFromTheIdleSlot(unittest.TestCase):
    """Browser trace 2026-11-15 (six-round trace, round 2; Shape of You, Guitar Shape, six-second
    Mission takes, Lead Sheet): the server was one key behind while Gm sounded, so the page had its
    own key Gm armed as "next" and warm-loaded Gm's take into the idle slot. Gm ended inside the
    Pause; the server held Cm, but its command reached the page 2.2 s after Resume. At Resume the
    end-of-take check refused the armed Gm, and the switch fell back to whatever the idle slot held
    -- Gm's own take -- and Gm restarted from 0. The switch now waits for the verified next take."""

    _SEQ = ["Dm", "Gm", "Cm", "Fm", "Bbm"]

    def _scenario(self, answer_after_ms: int, during_wait: str = "", record_ms: int = 9000) -> dict:
        seq = list(self._SEQ)
        start = _kc_cmd(10, "Gm", "Cm", restart=True, autoplay=True, forcePlay=True, sequence=seq)
        # The server one behind: it still names Dm current and Gm (the page's own key) as next.
        behind = _kc_cmd(11, "Dm", "Gm", sequence=seq)
        # Then, as in the trace, the page has Gm armed as next (warm-loaded into the idle slot).
        # The server's URL -> key map holds more than one Cm take, as it does after earlier passes
        # in the app (the page then could not name Cm's take by itself, and fell back to the slot).
        arm_own = """() => { const d = window.__kcDual; d.sequence = %s;
          window.__kcUrlToKey = window.__kcUrlToKey || {}; window.__kcUrlToKey['app/static/kc/cm-pass1.wav'] = 'Cm';
          d.nextUrl = 'app/static/kc/gm.wav'; d.nextSounding = 'Gm'; return true; }""" % __import__("json").dumps(seq)
        pause = ResumePreparesTheNextKeyWithoutTheServer._PAUSE_AT_GM_END % __import__("json").dumps(seq)
        answer = _kc_cmd(12, "Cm", "Fm", resume=True, restart=False, autoplay=False, sequence=seq)
        resume_and_answer = """async () => { const rec = (%s)(%d);
          window.__kcResumeAudio();
          await new Promise(r => setTimeout(r, %d));
          %s
          window.__kcApplyCmd(%s);
          await new Promise(r => setTimeout(r, 1500));  // Cm starts and settles
          const d = window.__kcDual; const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          a.currentTime = Math.max(0, a.duration - 0.3);  // Cm runs to its end, then Fm must follow
          return await rec; }""" % (_RECORD_HEARD_JS, record_ms, answer_after_ms, during_wait,
                                     __import__("json").dumps(answer))
        snaps = _run_stop_race(self, [("cmd", start), ("cmd", behind), ("eval", arm_own), ("eval", pause),
                                      ("eval", resume_and_answer)])
        return snaps[-1]["eval"]

    def test_resume_never_replays_gm_and_plays_cm_once_then_fm(self) -> None:
        got = self._scenario(2200)  # the server's command, 2.2 s after Resume, as recorded
        self.assertNotIn("gm.wav", got["sequence"], got)
        self.assertEqual(got["sequence"], ["cm.wav", "fm.wav"], got)  # Cm once, then Fm; never two at once
        self.assertEqual(got["restarts"], [], got)

    def test_a_take_missing_for_seconds_is_waited_for_safely(self) -> None:
        got = self._scenario(5000, record_ms=11000)  # no valid next take for 5 s
        self.assertEqual(got["sequence"], ["cm.wav", "fm.wav"], got)  # silent wait, then the right take
        self.assertEqual(got["restarts"], [], got)

    def test_stop_while_waiting_stays_stopped(self) -> None:
        got = self._scenario(2200, during_wait="window.__kcHardStop();")
        self.assertEqual(got["sequence"], [], got)


class FinalKeyEndsOnlyWhenItsTakeCompletes(unittest.TestCase):
    """The final key selected (or prepared) is not the final key completed: only the completion of
    the final key's own take ends the sequence. Two-key cycle Gm -> Cm, starting on Cm."""

    _SEQ = ["Gm", "Cm"]

    def _start_cm(self) -> dict:
        return _kc_cmd(10, "Cm", restart=True, autoplay=True, forcePlay=True, sequence=list(self._SEQ))

    def _seq(self) -> str:
        return "() => { window.__kcDual.sequence = %s; return true; }" % __import__("json").dumps(self._SEQ)

    def test_pause_and_resume_during_the_final_key_continue_it(self) -> None:
        probe = """async () => { const d = window.__kcDual;
          const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          a.currentTime = 2.0; await new Promise(r => setTimeout(r, 80));
          window.__kcPauseAudio(); await new Promise(r => setTimeout(r, 400));
          window.__kcResumeAudio(); await new Promise(r => setTimeout(r, 500));
          return {ct: Number(a.currentTime), paused: a.paused}; }"""
        snaps = _run_stop_race(self, [("cmd", self._start_cm()), ("eval", self._seq()), ("eval", probe),
                                      ("eval", _HEARD_JS), ("eval", _FINISH_ACTIVE_JS),
                                      ("eval", "async () => { await new Promise(r => setTimeout(r, 2500)); return true; }"),
                                      ("eval", _HEARD_JS)])
        resumed, heard, after = snaps[3]["eval"], snaps[4]["eval"], snaps[-1]["eval"]
        self.assertFalse(resumed["paused"], resumed)
        self.assertGreater(resumed["ct"], 2.0, resumed)  # continued, not restarted
        self.assertEqual(heard["heard"], ["cm.wav"], heard)
        self.assertEqual((after["heard"], after["running"]), ([], []), after)  # ended after Cm completed

    def test_the_final_key_completing_ends_the_cycle_without_wrapping(self) -> None:
        snaps = _run_stop_race(self, [("cmd", self._start_cm()), ("eval", self._seq()), ("eval", _HEARD_JS),
                                      ("eval", _FINISH_ACTIVE_JS),
                                      ("eval", "async () => { await new Promise(r => setTimeout(r, 2500)); return true; }"),
                                      ("eval", _HEARD_JS)])
        playing, after = snaps[3]["eval"], snaps[-1]["eval"]
        self.assertEqual(playing["heard"], ["cm.wav"], playing)  # the final key playing does not end anything
        self.assertEqual((after["heard"], after["running"], after["key"]), ([], [], "Cm"), after)

    def test_stop_during_the_final_key_silences_it(self) -> None:
        snaps = _run_stop_race(self, [("cmd", self._start_cm()), ("eval", self._seq()), "stop",
                                      ("eval", _FINISH_ACTIVE_JS),
                                      ("eval", "async () => { await new Promise(r => setTimeout(r, 2000)); return true; }"),
                                      ("eval", _HEARD_JS)])
        after = snaps[-1]["eval"]
        self.assertEqual((after["heard"], after["running"]), ([], []), after)

    def test_a_new_start_after_the_cycle_ended_plays(self) -> None:
        new_start = dict(_kc_cmd(12, "Gm", "Cm", restart=True, autoplay=True, forcePlay=True,
                                 sequence=list(self._SEQ)), cycleId="cyc-B")
        snaps = _run_stop_race(self, [("cmd", self._start_cm()), ("eval", self._seq()), ("eval", _FINISH_ACTIVE_JS),
                                      ("eval", "async () => { await new Promise(r => setTimeout(r, 2000)); return true; }"),
                                      ("eval", _HEARD_JS), ("cmd", new_start),
                                      ("eval", "async () => { await new Promise(r => setTimeout(r, 1200)); return true; }"),
                                      ("eval", _HEARD_JS)])
        ended, started = snaps[5]["eval"], snaps[-1]["eval"]
        self.assertEqual(ended["heard"], [], ended)
        self.assertEqual((started["key"], started["heard"]), ("Gm", ["gm.wav"]), started)


class StopOutranksAnEarlierResume(unittest.TestCase):
    """A Resume pressed shortly before Stop must never undo the Stop.

    Browser trace 2026-11-14 (console and Lead Sheet, dev e4123206 too, 3/4 each): the page
    stopped at epoch 9; the server -- answering the Resume late -- sent a running Resume command
    with epoch 10 after the click. The page's Stop guard took "newer epoch" for "after the Stop",
    cleared itself and played that take until the server's own Stop (epoch 11, off) arrived
    5.5 s later. Until that off command, a running command of the stopped cycle is stale; a
    deliberate new Start comes with a new cycle."""

    _STALE_RESUME = dict(_RUNNING, epoch=10, resume=True, autoplay=False, forcePlay=False)
    _OFF = {"enabled": False, "epoch": 11, "cycleId": "cyc-A"}
    _NEW_START = dict(_RUNNING, epoch=12, cycleId="cyc-B", restart=True)

    def test_a_resume_built_before_the_servers_stop_does_not_play_after_stop(self) -> None:
        mounted, stopped, after = _run_stop_race(self, ["stop", ("cmd", self._STALE_RESUME)])
        self.assertTrue(mounted["enabled"], mounted)
        self.assertEqual(stopped["playing"], 0, stopped)
        self.assertEqual(after["playing"], 0, after)
        self.assertEqual(after["plays"], stopped["plays"], after)  # not even an attempt
        self.assertIn("before_stop", after["trace"], after)
        self.assertTrue(after["stopped"], after)  # still waiting for the server's off

    def test_a_running_command_during_an_automatic_change_does_not_play_after_stop(self) -> None:
        handoff = dict(_RUNNING, epoch=10, currentUrl="app/static/kc/em.wav", nextUrl="app/static/kc/am.wav",
                       currentSounding="Em", nextSounding="Am", autoplay=True, forcePlay=False)
        _m, stopped, after = _run_stop_race(self, ["stop", ("cmd", handoff)])
        self.assertEqual(after["playing"], 0, after)
        self.assertEqual(after["plays"], stopped["plays"], after)

    def test_after_the_servers_off_a_new_start_plays(self) -> None:
        _m, stopped, stale, off, start = _run_stop_race(
            self, ["stop", ("cmd", self._STALE_RESUME), ("cmd", self._OFF), ("cmd", self._NEW_START)])
        self.assertEqual(stale["playing"], 0, stale)
        self.assertFalse(off["enabled"], off)
        self.assertFalse(off["stopped"], off)  # the server's off confirms the Stop
        self.assertEqual(start["playing"], 1, start)
        self.assertEqual(start["cycle"], "cyc-B", start)

    def test_a_new_start_before_the_off_arrives_still_plays(self) -> None:
        _m, _stopped, start = _run_stop_race(self, ["stop", ("cmd", self._NEW_START)])
        self.assertEqual(start["playing"], 1, start)
        self.assertFalse(start["stopped"], start)

    def test_stop_after_pause_stays_silent(self) -> None:
        paused = dict(_RUNNING, epoch=10, paused=True, autoplay=False, forcePlay=False)
        *_, after = _run_stop_race(self, ["stop", ("cmd", paused), ("cmd", self._STALE_RESUME)])
        self.assertEqual(after["playing"], 0, after)

    def test_the_stops_widget_echo_does_not_start_a_new_cycle(self) -> None:
        """Server side: the Stop click also posts the Off/On radio's value. With no stored value
        for it, Streamlit fires its on_change in the Stop's own callback batch, which marked a
        user toggle and cancelled the Stop's force-off: render_backing_key_cycle_controls then
        saw On with no active cycle and called start_key_cycle 2 s after Stop (4/4 with a
        Resume still pending)."""
        from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session

        class _St(_ControlsSt):
            # Streamlit returns the value the script set before the widget, as the force-off relies on.
            def radio(self, label, *, options, key, **kwargs):
                if str(label or "").endswith("Key cycling") or str(label or "") == "Key cycling":
                    return self.session.get(key) or self.cycling
                return super().radio(label, options=options, key=key, **kwargs)

        mode = "backing_key_cycle_enabled_ui"
        session = _session()
        session["_kc_cycle_user_toggled"] = True
        kc.render_backing_key_cycle_controls(_ControlsSt(session, cycling="On"), session)
        self.assertTrue(kc.is_cycle_active(session))
        # The console's Stop, and in the same callback batch the radio's echo of "On".
        kc._stop_key_cycle_from_button(session)
        session[mode] = "On"
        session["_kc_cycle_user_toggled"] = True
        kc.render_backing_key_cycle_controls(_St(session, cycling="On"), session)
        self.assertFalse(kc.is_cycle_active(session))
        self.assertEqual(session.get(mode), "Off")
        # A deliberate On afterwards (its own click, a later run) still starts cycling.
        session[mode] = "On"
        session["_kc_cycle_user_toggled"] = True
        kc.render_backing_key_cycle_controls(_St(session, cycling="On"), session)
        self.assertTrue(kc.is_cycle_active(session))

    def test_a_card_resume_still_pending_at_stop_is_not_applied_after_it(self) -> None:
        """Server side: callbacks run before the page applies the card's command, so the Resume
        pressed just before Stop was applied after it and started playback (trace 2026-11-14:
        Stop at +1.4 s, that Resume at +3.2 s). The console's Stop now supersedes it."""
        from backing_transport_intent import PLAYING
        from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session

        for action in ("resume", "pause"):
            session = _session()
            session["_kc_cycle_user_toggled"] = True
            kc.render_backing_key_cycle_controls(_ControlsSt(session, cycling="On"), session)
            self.assertTrue(kc.is_cycle_active(session))
            session[BACKING_CARD_TRANSPORT_KEY] = {"action": action, "session": "s1", "nonce": 7}
            self.assertEqual(cards.pending_card_command(session), (action, "s1:7"))
            kc._stop_key_cycle_from_button(session)
            # What the page does with the card's command later in the same (or the next) run.
            pending, token = cards.pending_card_command(session)
            if pending:
                cards.apply_card_command(session, pending, token, has_chords=True, stop_backing=lambda _i: False)
            self.assertEqual(pending, "", action)
            self.assertNotEqual(transport_intent(session), PLAYING, action)
            self.assertFalse(kc.is_cycle_active(session), action)
            self.assertFalse(session.get("_backing_autoplay"), action)
            self.assertEqual(cards.card_echo_token(session), "s1:7", action)  # echoed, so the card clears its intent
        # A Play pressed with the Stop is not swallowed.
        session = _session()
        session[BACKING_CARD_TRANSPORT_KEY] = {"action": "play", "session": "s1", "nonce": 8}
        kc._stop_key_cycle_from_button(session)
        self.assertEqual(cards.pending_card_command(session), ("play", "s1:8"))

    def test_a_stop_the_server_never_received_does_not_silence_the_page_for_good(self) -> None:
        # Past the 20 s bound the old rule applies again: a newer command re-syncs the page.
        _m, _stopped, _aged, after = _run_stop_race(self, ["stop", ("age", 21000), ("cmd", self._STALE_RESUME)])
        self.assertEqual(after["playing"], 1, after)
        self.assertFalse(after["stopped"], after)


if __name__ == "__main__":
    unittest.main()
