"""Regression test for the groove-staleness root cause found and fixed in
this checkpoint: a stale ``backing_groove_style``/local-dirty leftover from
a *previous* song could win over the newly-active song's own authoritative
default when ``apply_backing_defaults_for_song`` ran a genuine catalog song
switch -- producing "Pop groove" for a freshly-picked Jazz standard on the
Practice page's Session summary and (before the Guitar TAB groove-
propagation fix) Guitar TAB too.

The fix (streamlit_music_practice_app.py) does not touch the Backing
play-session "preserve manual tweaks" logic itself -- that guard is correct
for the Backing page's own widgets. Instead, Practice-page groove
resolution now reads the song's raw catalog default (``_default_groove``,
computed straight from the chart bundle) instead of the Backing-session-
guarded ``default_groove_style`` output. This test proves why that's
necessary: it reproduces the exact session shape that makes
``apply_backing_defaults_for_song`` return a stale groove, and shows the
raw chart-bundle default stays correct through the same scenario.
"""

from __future__ import annotations

import unittest

from backing_track_state import BACKING_DIRTY_KEY, BACKING_USER_EDIT_INTENT_KEY
from practice_state import resolve_practice_groove_style
from songs.playback_defaults import apply_backing_defaults_for_song


class _FakeSt:
    """Minimal ``st``-like shim: only ``session_state`` is used by the
    functions under test."""

    def __init__(self, session: dict) -> None:
        self.session_state = session


class TestGrooveStalenessAcrossSongSwitch(unittest.TestCase):
    def _stale_session(self) -> dict:
        """A session that just left a Pop song with a leftover Backing
        dirty/user-edit-intent flag -- the exact shape that makes a
        genuine switch to a Jazz standard still resolve 'Pop groove'."""
        return {
            "last_backing_defaults_song_id": "cat::Say::Pop",
            "backing_groove_style": "Pop groove",
            "practice_groove_style": "Pop groove",
            BACKING_DIRTY_KEY: True,
            BACKING_USER_EDIT_INTENT_KEY: True,
        }

    def test_stale_backing_dirty_flag_leaks_pop_groove_into_synced_default(self) -> None:
        """Ground truth for the bug: apply_backing_defaults_for_song's own
        'preserve a live Backing play session' guard returns the stale
        groove across an unrelated catalog song switch when a dirty/
        edit-intent flag never got cleared."""
        session = self._stale_session()
        st_like = _FakeSt(session)
        bpm, groove = apply_backing_defaults_for_song(
            st_like,
            song_id="cat::All the Things You Are::Jazz Standard",
            default_bpm=72,
            default_groove="Jazz swing",
        )
        self.assertEqual(
            groove,
            "Pop groove",
            "this is the bug being guarded against: it must reproduce as "
            "'Pop groove' here, proving default_groove_style is unsafe to "
            "feed into Practice-page groove display/generation directly",
        )

    def test_raw_chart_bundle_default_is_unaffected_by_the_same_staleness(self) -> None:
        """The fix's source of truth: resolve_practice_groove_style, given
        the song's own raw default (never touched by
        apply_backing_defaults_for_song), resolves correctly even with the
        identical stale session."""
        session = self._stale_session()
        session["_active_song_identity"] = "pk::Jazz\x1fAll the Things You Are - Jazz Standard"
        resolved = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(resolved, "Jazz swing")

    def test_resolver_fed_the_corrupted_synced_value_reproduces_the_bug(self) -> None:
        """End-to-end proof that feeding resolve_practice_groove_style the
        *synced* default_groove_style (as the code did before this
        checkpoint) reproduces the live bug, while feeding it the raw
        chart-bundle default (the fix) does not."""
        session = self._stale_session()
        st_like = _FakeSt(session)
        _, corrupted_default = apply_backing_defaults_for_song(
            st_like,
            song_id="cat::All the Things You Are::Jazz Standard",
            default_bpm=72,
            default_groove="Jazz swing",
        )
        session["_active_song_identity"] = "pk::Jazz\x1fAll the Things You Are - Jazz Standard"
        before_fix = resolve_practice_groove_style(session, default_groove=corrupted_default)
        self.assertEqual(before_fix, "Pop groove", "reproduces the pre-fix live bug")

        session2 = self._stale_session()
        session2["_active_song_identity"] = "pk::Jazz\x1fAll the Things You Are - Jazz Standard"
        after_fix = resolve_practice_groove_style(session2, default_groove="Jazz swing")
        self.assertEqual(after_fix, "Jazz swing", "the fix: raw default resolves correctly")


if __name__ == "__main__":
    unittest.main()
