"""Regression tests for the groove hydration/navigation-identity defect:
the final R2 blocker found during Guitar Pentatonics (39ee7fd) acceptance
testing, on top of the ordinary-rerun groove fix (d21b373).

Root cause (reproduced with the REAL ``apply_cloud_practice_state_if_allowed``
restore entrypoint -- the actual function the disk/cloud hydration call
chain in music_persistent_state.py invokes to restore Practice canonical
state, not a stand-in): the canonical Practice-state blob's
``practice_groove_style`` carried no record of which song it was resolved
for. ``d21b373`` correctly re-derives and persists the right groove on a
genuine song switch and on every ordinary rerun after it, but a page
navigation (Practice -> Songs picker -> Practice) triggers a hydration/
restore cycle that reads an older disk/cloud snapshot -- still reflecting
the previous song -- and overwrites the canonical blob with it, with no
way for the resolver to tell "this canonical groove was correctly
resolved a moment ago" apart from "this canonical groove is a stale
leftover from a different song that was never actually re-switched to".
``_active_song_identity`` itself is untouched by the restore (it is not
part of what gets hydrated here), so ``song_changed`` reads False on the
very next render and the resolver trusted the now-stale canonical value.

The fix: the canonical blob now also stores ``practice_groove_song_identity``
-- the identity of the song its ``practice_groove_style`` value was
resolved/edited for -- written every time resolve_practice_groove_style
writes a groove into canonical (song-switch correction AND a genuine
Backing override). On every read, a canonical groove whose stamped
identity does not match the currently active song is treated as
unprovenanced for THIS song and triggers the same re-derive-from-default
self-healing a genuine song switch already performs. Ownership invariant:
song identity outranks a stale persisted musical default, regardless of
*how* that stale value reappeared (a different session key, a cache that
didn't invalidate, or -- this defect -- a hydration/restore cycle).
"""

from __future__ import annotations

import unittest

from backing_track_state import mark_backing_user_edit
from practice_state import (
    apply_cloud_practice_state_if_allowed,
    canonical_practice_filters,
    resolve_practice_groove_style,
)
from songs.playback_defaults import sync_playback_defaults_for_active_song

ATTYA_PICK_KEY = "Jazz\x1fAll the Things You Are · Jazz Standard"
SAY_PICK_KEY = "Pop\x1fSay"


class _FakeSt:
    def __init__(self, session: dict) -> None:
        self.session_state = session


def _render(session: dict, *, pick_key: str, default_groove: str) -> str:
    """One simulated Streamlit rerun, same real call order the app uses."""
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


def _simulate_navigation_hydration(session: dict, *, stale_payload: dict) -> bool:
    """Simulate "navigate to Songs picker -> a hydration/restore cycle
    runs" by calling the REAL production restore entrypoint
    (apply_cloud_practice_state_if_allowed, the function
    music_persistent_state.py's disk/cloud restore chain actually calls)
    with an older snapshot. Returns what that function returned."""
    return apply_cloud_practice_state_if_allowed(session, stale_payload, authoritative=False)


_STALE_SAY_PAYLOAD = {
    "practice_state": {
        "practice_groove_style": "Ballad",
        "practice_focus_section": "",
        "practice_minutes": 30,
        # No practice_groove_song_identity -- exactly what a snapshot
        # captured before this fix existed (or before ATTYA's own
        # correction was ever flushed) looks like.
    }
}


class TestA_InitialSwitch(unittest.TestCase):
    def test_say_ballad_then_attya_jazz_swing(self) -> None:
        session: dict = {}
        self.assertEqual(_render(session, pick_key=SAY_PICK_KEY, default_groove="Ballad"), "Ballad")
        groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")
        canon = canonical_practice_filters(session) or {}
        self.assertEqual(canon.get("practice_groove_style"), "Jazz swing")
        self.assertEqual(canon.get("practice_groove_song_identity"), f"pk::{ATTYA_PICK_KEY}")


class TestB_OrdinaryReruns(unittest.TestCase):
    def test_several_reruns_stay_jazz_swing(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        for _ in range(5):
            self.assertEqual(
                _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing"), "Jazz swing"
            )


class TestC_NavigationHydration(unittest.TestCase):
    def test_single_navigation_cycle_stays_jazz_swing(self) -> None:
        session: dict = {}
        _render(session, pick_key=SAY_PICK_KEY, default_groove="Ballad")
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        for _ in range(2):
            _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")

        restored = _simulate_navigation_hydration(session, stale_payload=_STALE_SAY_PAYLOAD)
        self.assertTrue(restored, "restore should be allowed (not locally dirty)")
        # The canonical blob is now stale immediately after the simulated
        # hydration -- this is the defect's own ground truth, proven
        # against the real restore function.
        canon = canonical_practice_filters(session) or {}
        self.assertEqual(canon.get("practice_groove_style"), "Ballad")

        groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing", "navigation-triggered hydration contaminated the groove")

    def test_repeated_navigation_cycles_stay_jazz_swing(self) -> None:
        session: dict = {}
        _render(session, pick_key=SAY_PICK_KEY, default_groove="Ballad")
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        for cycle in range(4):
            _simulate_navigation_hydration(session, stale_payload=_STALE_SAY_PAYLOAD)
            groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
            self.assertEqual(groove, "Jazz swing", f"reverted on navigation cycle {cycle}")


class TestD_AppStyleHydrationRestore(unittest.TestCase):
    def test_real_restore_entrypoint_cannot_overwrite_with_wrong_provenance(self) -> None:
        """Uses apply_cloud_practice_state_if_allowed directly -- the actual
        production function -- not a hand-rolled stand-in."""
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        _simulate_navigation_hydration(session, stale_payload=_STALE_SAY_PAYLOAD)
        groove = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")

    def test_stale_payload_stamped_for_a_different_song_is_also_rejected(self) -> None:
        """Not just a missing stamp -- an explicit stamp for the WRONG song
        must also be rejected, proving this is a real identity check and
        not just an "empty means trust it" loophole."""
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        wrong_song_payload = {
            "practice_state": {
                "practice_groove_style": "Bossa nova",
                "practice_groove_song_identity": f"pk::{SAY_PICK_KEY}",
            }
        }
        _simulate_navigation_hydration(session, stale_payload=wrong_song_payload)
        groove = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")

    def test_payload_stamped_for_the_current_song_is_trusted(self) -> None:
        """The identity check must not reject EVERY restore -- a payload
        genuinely belonging to the current song (e.g. the self-healed
        canonical blob round-tripping through disk unchanged) is trusted."""
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        same_song_payload = {
            "practice_state": {
                "practice_groove_style": "Jazz swing",
                "practice_groove_song_identity": f"pk::{ATTYA_PICK_KEY}",
            }
        }
        _simulate_navigation_hydration(session, stale_payload=same_song_payload)
        groove = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")


class TestE_GenuineCurrentSongEdit(unittest.TestCase):
    def test_genuine_edit_takes_effect_and_is_stamped_for_current_song(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(groove, "Bossa nova")
        canon = canonical_practice_filters(session) or {}
        self.assertEqual(canon.get("practice_groove_style"), "Bossa nova")
        self.assertEqual(
            canon.get("practice_groove_song_identity"),
            f"pk::{ATTYA_PICK_KEY}",
            "a genuine edit must be stamped for the song it was made on, "
            "not left as an unexplained global value",
        )

    def test_genuine_edit_survives_ordinary_reruns(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        for _ in range(4):
            self.assertEqual(
                _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing"), "Bossa nova"
            )


class TestF_NavigationAfterGenuineEdit(unittest.TestCase):
    """Documents the EXISTING, unmodified product semantics for a genuine
    edit across a navigation/hydration cycle -- this fix does not change
    them, only makes the SONG-SWITCH-correction case stable. A navigation
    cycle that restores a payload already reflecting the edit (same song,
    same value -- e.g. the edit was already flushed/durable, or a multi-
    tab sync round-trip) preserves it, exactly like test D's "trusted"
    case. This is the behavior the architecture already provides once the
    edit's own canonical write carries the correct identity stamp (see
    TestE) -- no new persistence semantics were invented for this."""

    def test_navigation_restoring_the_edited_value_preserves_it(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")

        edited_payload = {
            "practice_state": {
                "practice_groove_style": "Bossa nova",
                "practice_groove_song_identity": f"pk::{ATTYA_PICK_KEY}",
            }
        }
        _simulate_navigation_hydration(session, stale_payload=edited_payload)
        groove = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(groove, "Bossa nova")

    def test_navigation_restoring_a_pre_edit_snapshot_for_the_same_song_is_trusted(self) -> None:
        """Documented, NOT changed, existing behavior: the identity stamp
        alone cannot distinguish "stale pre-edit value" from "a legitimate
        newer canonical value for this same song" -- both carry matching
        provenance, so the identity check (correctly) does not reject this
        restore. What happens next is governed by the PRE-EXISTING
        override-detection heuristic in the "not song_changed" branch,
        which this fix does not change: it only treats
        ``backing_groove_style`` as a fresh override when it differs from
        ``_practice_groove_last_resolved_value`` (the value this resolver
        itself returned last time). Here backing_groove_style ("Bossa
        nova") is UNCHANGED since the override was already resolved and
        recorded as last_resolved, so from the resolver's point of view
        nothing new happened in Backing -- it is not re-detected as a
        fresh edit, and the (identity-valid) restored canonical "Jazz
        swing" wins. This is existing, unmodified product behavior around
        how a repeated/unchanged backing_groove_style value is
        distinguished from a genuinely new one; this test exists so it is
        explicit and verified rather than assumed."""
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")

        pre_edit_same_song_payload = {
            "practice_state": {
                "practice_groove_style": "Jazz swing",
                "practice_groove_song_identity": f"pk::{ATTYA_PICK_KEY}",
            }
        }
        _simulate_navigation_hydration(session, stale_payload=pre_edit_same_song_payload)
        groove = resolve_practice_groove_style(session, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")


class TestG_SwitchAfterGenuineEdit(unittest.TestCase):
    def test_old_songs_manual_groove_does_not_contaminate_new_song(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")

        groove = _render(session, pick_key=SAY_PICK_KEY, default_groove="Pop groove")
        self.assertEqual(groove, "Pop groove")
        canon = canonical_practice_filters(session) or {}
        self.assertEqual(canon.get("practice_groove_song_identity"), f"pk::{SAY_PICK_KEY}")


class TestH_ReturnToAttya(unittest.TestCase):
    """Documents the EXISTING, unmodified behavior on return: a genuine
    song switch (song_changed=True) always re-derives from that song's own
    authoritative default -- it does not resurrect a previous manual
    override for that song. This is symmetric with TestG (the old song's
    override must not leak forward) and was true before this fix; this
    test exists so the behavior is explicit and verified, not assumed."""

    def test_returning_to_attya_gets_its_authoritative_default_not_the_old_override(self) -> None:
        session: dict = {}
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")

        _render(session, pick_key=SAY_PICK_KEY, default_groove="Pop groove")
        groove = _render(session, pick_key=ATTYA_PICK_KEY, default_groove="Jazz swing")
        self.assertEqual(groove, "Jazz swing")


class TestI_RepeatedSongAndNavigationStress(unittest.TestCase):
    def test_say_attya_say_attya_with_navigation_between_each(self) -> None:
        session: dict = {}
        sequence = [
            (SAY_PICK_KEY, "Pop groove"),
            (ATTYA_PICK_KEY, "Jazz swing"),
            (SAY_PICK_KEY, "Pop groove"),
            (ATTYA_PICK_KEY, "Jazz swing"),
        ]
        for step, (pick_key, expected) in enumerate(sequence):
            groove = _render(session, pick_key=pick_key, default_groove=expected)
            self.assertEqual(groove, expected, f"wrong groove right after switch at step {step}")
            # Navigate to Songs and back: a stale, unstamped snapshot from
            # whatever song was active BEFORE this whole sequence started
            # tries to hydrate in on every single cycle.
            _simulate_navigation_hydration(session, stale_payload=_STALE_SAY_PAYLOAD)
            groove = _render(session, pick_key=pick_key, default_groove=expected)
            self.assertEqual(groove, expected, f"oscillated/contaminated after navigation at step {step}")


if __name__ == "__main__":
    unittest.main()
