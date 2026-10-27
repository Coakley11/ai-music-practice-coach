"""Card Play / Stop / Pause / Resume survive a run cut off at any session access.

Streamlit (fastReruns) stops a run at its next st.session_state access when the
musician clicks again, with a BaseException. A command consumed on receipt and
cut off before its transport mutation was lost. These tests stop the command
at every session access it makes, then let the next run handle it again, and
check it is applied exactly once.
"""

from __future__ import annotations

import unittest

from backing_card_commands import (
    CardCommandOutcome,
    apply_card_command,
    card_echo_token,
    commit_card_command,
    commit_handled_card_command,
    pending_card_command,
)
from backing_card_transport import BACKING_CARD_TRANSPORT_KEY
from backing_transport_intent import (
    PAUSED,
    PLAYING,
    STOPPED,
    begin_playback,
    note_playback_settings_changed,
    pause_playback,
    playback_allowed,
    restart_on_resume,
    stop_playback,
    transport_generation,
    transport_intent,
)


class _Stopped(BaseException):
    """Streamlit's StopException: not an Exception, so nothing catches it."""


class _YieldingSession(dict):
    """A session whose ``stop_at``-th access ends the run, as fastReruns does."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.stop_at: int | None = None
        self.accesses = 0

    def _tick(self) -> None:
        self.accesses += 1
        if self.stop_at is not None and self.accesses >= self.stop_at:
            self.stop_at = None
            raise _Stopped()

    def __getitem__(self, k):
        self._tick()
        return super().__getitem__(k)

    def __setitem__(self, k, v) -> None:
        self._tick()
        super().__setitem__(k, v)

    def __contains__(self, k) -> bool:
        self._tick()
        return super().__contains__(k)

    def get(self, k, default=None):
        self._tick()
        return super().get(k, default)

    def pop(self, k, *default):
        self._tick()
        return super().pop(k, *default)

    def setdefault(self, k, default=None):
        self._tick()
        return super().setdefault(k, default)


def _click(session: dict, action: str, nonce: int) -> str:
    dict.__setitem__(session, BACKING_CARD_TRANSPORT_KEY, {"action": action, "nonce": nonce, "session": "card"})
    return f"card:{nonce}"


class _Page:
    """The Backing page's part: Stop's side effects and arming a Play."""

    def __init__(self, session: dict) -> None:
        self.session = session
        self.stop_calls: list[int] = []

    def stop_backing(self, karaoke_before: int) -> bool:
        stop_playback(self.session, reason="stop")
        self.session.pop("_backing_play_request", None)
        self.session["karaoke_session_index"] = 0
        self.stop_calls.append(karaoke_before)
        return karaoke_before != 0

    def run(self, *, stop_at: int | None = None) -> CardCommandOutcome | None:
        """One script run: handle the pending command; Play arms, then commits."""
        s = self.session
        s.stop_at = stop_at
        s.accesses = 0
        try:
            action, token = pending_card_command(s)
            if action not in ("play", "stop", "pause", "resume"):
                return None
            out = apply_card_command(
                s, action, token, has_chords=True,
                stop_backing=self.stop_backing,
                karaoke_index=lambda: int(s.get("karaoke_session_index") or 0),
            )
            if out.commit:
                commit_card_command(s, token)
            if out.play:
                s["_backing_play_request"] = True  # armed
                commit_handled_card_command(s)
            return out
        finally:
            s.stop_at = None


def _accesses_of_one_run(prepare, action: str) -> int:
    session = _YieldingSession()
    prepare(session)
    _click(session, action, 1)
    page = _Page(session)
    page.run()
    return session.accesses


class _ExhaustiveCase:
    """Stop the command at each access k, rerun, and check the final state."""

    def exhaust(self, prepare, action: str, check) -> None:
        n = _accesses_of_one_run(prepare, action)
        self.assertGreater(n, 3)
        for k in range(1, n + 1):
            with self.subTest(stopped_at_access=k, of=n):
                session = _YieldingSession()
                prepare(session)
                before = dict(session)
                _click(session, action, 1)
                page = _Page(session)
                try:
                    page.run(stop_at=k)
                except _Stopped:
                    pass
                page.run()          # the next run handles it again
                self.assertEqual(pending_card_command(session), ("", ""), "committed")
                page.run()          # and never again
                check(session, page, before)


def _playing(session: dict) -> None:
    begin_playback(session, reason="test")
    session["_backing_play_request"] = False


class ActionRaceTests(_ExhaustiveCase, unittest.TestCase):
    def test_action_race_1_play_cut_off_anywhere_starts_once(self) -> None:
        def check(s, page, before):
            self.assertEqual(transport_intent(s), PLAYING)
            self.assertEqual(transport_generation(s), transport_generation(before) + 1, "one new session")
            self.assertTrue(s.get("_backing_play_request"), "armed")
            self.assertEqual(card_echo_token(s), "card:1")

        self.exhaust(lambda s: None, "play", check)

    def test_action_race_2_stop_cut_off_anywhere_is_terminal(self) -> None:
        def prepare(s):
            _playing(s)
            s["karaoke_session_index"] = 2

        def check(s, page, before):
            self.assertEqual(transport_intent(s), STOPPED)
            self.assertFalse(playback_allowed(s), "nothing restarts")
            self.assertNotIn("_backing_play_request", s)
            self.assertEqual(s["karaoke_session_index"], 0)
            # A retry decides as the first attempt did: the set was on entry 3.
            self.assertTrue(page.stop_calls and set(page.stop_calls) == {2}, page.stop_calls)

        self.exhaust(prepare, "stop", check)

    def test_action_race_3_pause_cut_off_anywhere_ends_paused(self) -> None:
        def check(s, page, before):
            self.assertEqual(transport_intent(s), PAUSED)
            self.assertFalse(s.get("_backing_autoplay"))
            self.assertEqual(transport_generation(s), transport_generation(before), "same session")

        self.exhaust(_playing, "pause", check)

    def test_action_race_4_resume_cut_off_anywhere_applies_once(self) -> None:
        def prepare(s):
            _playing(s)
            pause_playback(s, reason="test")

        def check(s, page, before):
            self.assertEqual(transport_intent(s), PLAYING)
            self.assertEqual(transport_generation(s), transport_generation(before), "continues the session")
            self.assertTrue(s.get("_backing_autoplay"))

        self.exhaust(prepare, "resume", check)

    def test_action_race_4b_resume_after_a_scope_change_restarts_even_when_cut_off(self) -> None:
        # continue_playback clears the restart flag: a retry must still restart.
        def prepare(s):
            _playing(s)
            pause_playback(s, reason="test")
            note_playback_settings_changed(s)

        def check(s, page, before):
            self.assertEqual(transport_intent(s), PLAYING)
            self.assertFalse(restart_on_resume(s))
            self.assertTrue(s.get("_backing_play_request"), "the new selection was started")

        self.exhaust(prepare, "resume", check)


class CommandOrderTests(unittest.TestCase):
    def _page(self) -> _Page:
        return _Page(_YieldingSession())

    def test_action_race_5_play_then_stop_ends_stopped(self) -> None:
        for k in range(1, _accesses_of_one_run(lambda s: None, "play") + 1):
            with self.subTest(play_stopped_at=k):
                page = self._page()
                s = page.session
                _click(s, "play", 1)
                try:
                    page.run(stop_at=k)       # the Stop click ends the Play run
                except _Stopped:
                    pass
                _click(s, "stop", 2)          # the newer command replaces it
                page.run()
                for _ in range(3):
                    page.run()
                self.assertEqual(transport_intent(s), STOPPED)
                self.assertNotIn("_backing_play_request", s, "no stale Play wins later")
                self.assertEqual(pending_card_command(s), ("", ""))

    def test_action_race_6_stop_then_play_starts_a_fresh_session(self) -> None:
        for k in range(1, 12):
            with self.subTest(stop_stopped_at=k):
                page = self._page()
                s = page.session
                _playing(s)
                gen0 = transport_generation(s)
                _click(s, "stop", 1)
                try:
                    page.run(stop_at=k)
                except _Stopped:
                    pass
                _click(s, "play", 2)
                page.run()
                page.run()
                self.assertEqual(transport_intent(s), PLAYING)
                self.assertGreater(transport_generation(s), gen0, "a new session from the beginning")
                self.assertTrue(s.get("_backing_play_request"))

    def test_action_race_7_pause_setting_change_resume(self) -> None:
        page = self._page()
        s = page.session
        _click(s, "play", 1)
        page.run()
        _click(s, "pause", 2)
        page.run()
        s["_backing_play_request"] = False
        note_playback_settings_changed(s)      # BPM / scope / loops while paused
        self.assertEqual(transport_intent(s), PAUSED, "a setting never starts audio")
        self.assertFalse(playback_allowed(s))
        _click(s, "resume", 3)
        try:
            page.run(stop_at=4)
        except _Stopped:
            pass
        out = page.run()
        self.assertTrue(out.play, "Resume starts the changed selection from its first chord")
        self.assertEqual(transport_intent(s), PLAYING)


class ResumeAfterChangeTests(unittest.TestCase):
    def test_resume_restarts_when_the_paused_take_no_longer_matches(self) -> None:
        # A post-Play guard swallowed the change note; the invalidated take was
        # un-paused into silence. A needed rebuild is proof enough to restart.
        s: dict = {}
        _playing(s)
        pause_playback(s, reason="test")
        self.assertFalse(restart_on_resume(s))
        _click(s, "resume", 9)
        action, token = pending_card_command(s)
        out = apply_card_command(s, action, token, has_chords=True, stop_backing=lambda _i: False,
                                 selection_changed=lambda: True)
        self.assertTrue(out.play and not out.commit)
        self.assertEqual(transport_intent(s), PLAYING)

    def test_resume_continues_when_nothing_changed(self) -> None:
        s: dict = {}
        _playing(s)
        pause_playback(s, reason="test")
        _click(s, "resume", 10)
        action, token = pending_card_command(s)
        out = apply_card_command(s, action, token, has_chords=True, stop_backing=lambda _i: False,
                                 selection_changed=lambda: False)
        self.assertTrue(out.commit and not out.play)
        self.assertTrue(s.get("_backing_autoplay"))


class PendingPauseBeforeSettingTests(unittest.TestCase):
    def test_a_setting_changed_after_a_pending_pause_restarts_on_resume(self) -> None:
        # The Pause's run was cut off by the edit; the edit's callback ran first.
        from backing_card_commands import apply_pending_card_pause

        s: dict = {}
        _playing(s)
        _click(s, "pause", 4)
        apply_pending_card_pause(s)          # what the settings callback does first
        note_playback_settings_changed(s)
        self.assertEqual(transport_intent(s), PAUSED)
        self.assertTrue(restart_on_resume(s), "Resume starts the changed selection")
        self.assertEqual(pending_card_command(s), ("", ""))

    def test_other_pending_commands_are_left_to_the_page(self) -> None:
        from backing_card_commands import apply_pending_card_pause

        s: dict = {}
        _playing(s)
        _click(s, "stop", 5)
        apply_pending_card_pause(s)
        self.assertEqual(transport_intent(s), PLAYING)
        self.assertEqual(pending_card_command(s), ("stop", "card:5"))


class EchoTests(unittest.TestCase):
    def test_play_is_echoed_when_applied_and_committed_once_armed(self) -> None:
        s: dict = {}
        _click(s, "play", 7)
        action, token = pending_card_command(s)
        out = apply_card_command(s, action, token, has_chords=True, stop_backing=lambda _i: False)
        self.assertTrue(out.play and not out.commit)
        self.assertEqual(card_echo_token(s), "card:7", "the card leaves Starting… now")
        self.assertEqual(pending_card_command(s), ("play", "card:7"), "still pending until armed")
        commit_handled_card_command(s)
        self.assertEqual(pending_card_command(s), ("", ""))

    def test_ended_is_consumed_on_receipt(self) -> None:
        from backing_card_transport import consume_backing_card_transport_action

        s: dict = {}
        _click(s, "ended", 3)
        self.assertEqual(consume_backing_card_transport_action(s), "ended")
        self.assertEqual(consume_backing_card_transport_action(s), "")
        self.assertEqual(card_echo_token(s), "card:3")


if __name__ == "__main__":
    unittest.main()
