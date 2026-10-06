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

from backing_track_state import (
    BACKING_DIRTY_KEY,
    BACKING_USER_EDIT_INTENT_KEY,
    mark_backing_user_edit,
)
from practice_state import resolve_practice_groove_style
from songs.playback_defaults import apply_backing_defaults_for_song, sync_playback_defaults_for_active_song


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


ATTYA_PICK_KEY = "Jazz\x1fAll the Things You Are · Jazz Standard"
SAY_PICK_KEY = "Pop\x1fSay"


def _render(session: dict, *, pick_key: str, default_groove: str) -> str:
    """One simulated Streamlit rerun: the exact call order/order of
    operations the app uses on every Practice-page render --
    ``sync_playback_defaults_for_active_song`` (which runs
    ``apply_backing_defaults_for_song`` internally) first, then
    ``resolve_practice_groove_style``. Returns the resolved Practice-page
    groove for that render."""
    st_like = _FakeSt(session)
    session["_active_song_identity"] = f"pk::{pick_key}"
    sync_playback_defaults_for_active_song(
        st_like,
        song_id="cat::whatever::whatever",
        default_bpm=120,
        default_groove=default_groove,
        song_data={},
        pick_key=pick_key,
        is_custom=False,
    )
    return resolve_practice_groove_style(session, default_groove=default_groove)


class TestGrooveOwnershipAcrossRerunsAndSwitches(unittest.TestCase):
    """Required invariant: for a given active song identity, (1) a genuine
    song change initializes groove from that song's authoritative default,
    (2) ordinary reruns must not resurrect a stale groove from the
    previous song, (3) a genuine user Backing groove edit made after
    initialization for the current song may override the song default,
    (4) that override must survive ordinary reruns, (5) switching songs
    must not carry the override into the new song, and (6) the resolved
    groove must be identical across Session summary / Deep Focus /
    Notation-TAB / Backing / Practice Melody (all of which call this same
    resolver)."""

    def test_a_song_switch_remains_stable_across_reruns(self) -> None:
        session: dict = {}
        _render(session, pick_key=SAY_PICK_KEY, default_groove="Ballad")
        first = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(first, "Jazz swing")
        for rerun in range(6):
            groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
            self.assertEqual(groove, "Jazz swing", f"reverted on ordinary rerun {rerun}")
            self.assertEqual(
                session.get("backing_groove_style"),
                "Jazz swing",
                f"backing_groove_style spontaneously reverted to Ballad on rerun {rerun}",
            )

    def test_b_genuine_current_song_manual_edit_survives_reruns(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        # The actual state transition a real Backing groove selectbox
        # on_change handler produces: a new value plus the dirty/edit-
        # intent flags (mark_backing_user_edit), not just a raw write.
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        overridden = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(overridden, "Bossa nova")
        for rerun in range(6):
            groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
            self.assertEqual(
                groove,
                "Bossa nova",
                f"genuine manual override did not survive ordinary rerun {rerun}",
            )

    def test_c_manual_edit_does_not_leak_to_next_song(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        switched = _render(session, pick_key=SAY_PICK_KEY, default_groove="Pop groove")
        self.assertEqual(
            switched,
            "Pop groove",
            "the previous song's manual override contaminated the new song's default",
        )
        for rerun in range(3):
            groove = _render(session, pick_key=SAY_PICK_KEY, default_groove="Pop groove")
            self.assertEqual(groove, "Pop groove", f"unstable after the switch on rerun {rerun}")

    def test_d_repeated_switching_settles_immediately_each_time(self) -> None:
        session: dict = {}
        sequence = [
            (SAY_PICK_KEY, "Pop groove"),
            (SAY_PICK_KEY, "Pop groove"),
            (ATTYA_PICK_KEY, "Jazz swing"),
            (ATTYA_PICK_KEY, "Jazz swing"),
            (ATTYA_PICK_KEY, "Jazz swing"),
            (SAY_PICK_KEY, "Pop groove"),
            (SAY_PICK_KEY, "Pop groove"),
            (ATTYA_PICK_KEY, "Jazz swing"),
            (ATTYA_PICK_KEY, "Jazz swing"),
        ]
        for step, (pick_key, expected_groove) in enumerate(sequence):
            groove = _render(session, pick_key=pick_key, default_groove=expected_groove)
            self.assertEqual(groove, expected_groove, f"wrong groove at step {step}")

    def test_e_no_oscillation_recorded_sequence_is_constant(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        observed = [
            _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
            for _ in range(8)
        ]
        self.assertEqual(
            observed,
            ["Jazz swing"] * 8,
            f"groove oscillated across reruns instead of holding constant: {observed}",
        )


if __name__ == "__main__":
    unittest.main()
