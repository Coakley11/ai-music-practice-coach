"""Phase 2A+2B: a late startup restore must not put one song's groove onto
another, and a groove's song provenance must travel with the groove.

Live failure this pins (traced in the browser, 5/15 clean runs): a startup
snapshot captured while Say was active -> the user explicitly picks All the
Things You Are -> the resolver correctly writes Jazz swing stamped for ATTYA
-> ``run_late_startup_restore_guard`` re-runs
``finalize_startup_canonical_alignment``, whose
``align_authoritative_canonical_from_hydrated`` re-applied Say's snapshot
(Ballad) -> the finalize gather-save paired that Ballad with a separate
session identity copy that still said ATTYA -> canonical "Ballad stamped
ATTYA", which the cd9231f identity check could no longer reject.

2A: the snapshot's song-scoped musical state is applied only while the live
committed song is the snapshot's song.
2B: only the resolver and restore paths may stamp provenance; generic
gather/save paths carry the existing stamp only while the groove value is
unchanged, so a stale groove keeps its own (wrong-song) provenance and the
resolver still rejects it.
"""

from __future__ import annotations

import unittest

from backing_track_state import mark_backing_user_edit
from music_startup_canonical_align import (
    align_authoritative_canonical_from_hydrated,
    snapshot_owns_live_song,
)
from practice_state import (
    PRACTICE_STATE_KEY,
    apply_cloud_practice_state_if_allowed,
    canonical_practice_filters,
    commit_practice_state_from_session,
    flush_practice_edits,
    mark_practice_local_edit,
    prepare_practice_page,
    resolve_practice_groove_style,
    write_canonical_practice_state,
)
from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

SAY = "Pop\x1fSay — John Mayer"
ATTYA = "Jazz\x1fAll the Things You Are — Jazz Standard"
SAY_ID = f"pk::{SAY}"
ATTYA_ID = f"pk::{ATTYA}"


def _activate(session: dict, pick_key: str) -> None:
    """Commit ``pick_key`` as the live active song (the fields the real
    commit_catalog_active_song path leaves behind that these modules read,
    including its explicit-Catalog-choice stamp, which is what keeps the
    startup re-align from restoring the snapshot's active song itself)."""
    session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
    session["_active_song_identity"] = f"pk::{pick_key}"
    session["active_catalog_pick_key"] = pick_key
    ass = dict(session.get("active_song_state") or {})
    ass["pick_key"] = pick_key
    session["active_song_state"] = ass


def _render(session: dict, pick_key: str, default_groove: str) -> str:
    _activate(session, pick_key)
    return resolve_practice_groove_style(session, default_groove=default_groove)


def _snapshot(pick_key: str | None, groove: str, provenance: str | None, *, backing: str = "Pop groove") -> dict:
    practice = {"practice_groove_style": groove, "practice_minutes": 30, "practice_focus_section": "Full Song"}
    if provenance is not None:
        practice["practice_groove_song_identity"] = provenance
    payload: dict = {
        "practice_state": practice,
        "backing_track_state": {"backing_groove_style": backing, "backing_track_bpm": 82},
    }
    if pick_key is not None:
        payload["active_song_state"] = {"pick_key": pick_key, "music_source": "catalog_song"}
    return payload


def _canon(session: dict) -> tuple[str, str]:
    c = canonical_practice_filters(session) or {}
    return c.get("practice_groove_style", ""), c.get("practice_groove_song_identity", "")


class TestA_LegitimateStartupRestore(unittest.TestCase):
    def test_snapshot_for_the_live_song_is_restored_with_its_provenance(self) -> None:
        session: dict = {}
        _activate(session, ATTYA)
        align_authoritative_canonical_from_hydrated(session, _snapshot(ATTYA, "Bossa nova", ATTYA_ID))
        self.assertEqual(_canon(session), ("Bossa nova", ATTYA_ID))
        self.assertEqual(session.get("practice_groove_style"), "Bossa nova")
        self.assertNotIn("_startup_align_song_scoped_skipped", session)

    def test_restore_applies_when_no_live_song_is_committed_yet(self) -> None:
        session: dict = {}
        align_authoritative_canonical_from_hydrated(session, _snapshot(SAY, "Ballad", SAY_ID))
        self.assertEqual(_canon(session), ("Ballad", SAY_ID))

    def test_snapshot_without_song_identity_keeps_legacy_restore(self) -> None:
        session: dict = {}
        _activate(session, ATTYA)
        self.assertTrue(snapshot_owns_live_song(session, _snapshot(None, "Ballad", None)))


class TestB_NewerExplicitSongSelectionWins(unittest.TestCase):
    def _live_sequence(self) -> dict:
        session: dict = {}
        self.assertEqual(_render(session, SAY, "Ballad"), "Ballad")
        snapshot = _snapshot(SAY, "Ballad", SAY_ID)  # captured while Say was active
        self.assertEqual(_render(session, ATTYA, "Jazz swing"), "Jazz swing")  # explicit pick
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))
        # Late startup guard: re-align from the old snapshot, then the
        # finalize gather-save -- the exact two calls the trace shows.
        align_authoritative_canonical_from_hydrated(session, snapshot)
        commit_practice_state_from_session(session, reason="autosave")
        return session

    def test_late_restore_does_not_reintroduce_previous_songs_groove(self) -> None:
        session = self._live_sequence()
        self.assertEqual(session["_active_song_identity"], ATTYA_ID)
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))
        self.assertEqual(session.get("practice_groove_style"), "Jazz swing")
        self.assertEqual(
            session["_startup_align_song_scoped_skipped"],
            {"snapshot_pick": SAY, "live_pick": ATTYA},
        )

    def test_late_restore_does_not_overwrite_backing_groove_with_snapshot(self) -> None:
        session = self._live_sequence()
        self.assertEqual(session.get("backing_groove_style"), "Jazz swing")

    def test_following_reruns_stay_jazz_swing(self) -> None:
        session = self._live_sequence()
        for _ in range(4):
            self.assertEqual(_render(session, ATTYA, "Jazz swing"), "Jazz swing")
            commit_practice_state_from_session(session, reason="autosave")
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))


class TestC_NoProvenanceLaundering(unittest.TestCase):
    def _stale_say_groove_while_attya_active(self) -> dict:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        # Say's groove arrives with Say's provenance (e.g. via a restore).
        apply_cloud_practice_state_if_allowed(
            session, _snapshot(SAY, "Ballad", SAY_ID), authoritative=True
        )
        self.assertEqual(_canon(session), ("Ballad", SAY_ID))
        self.assertEqual(session["_active_song_identity"], ATTYA_ID)
        return session

    def test_autosave_keeps_the_grooves_own_provenance(self) -> None:
        session = self._stale_say_groove_while_attya_active()
        commit_practice_state_from_session(session, reason="autosave")
        self.assertEqual(_canon(session), ("Ballad", SAY_ID))

    def test_every_generic_save_path_keeps_the_grooves_own_provenance(self) -> None:
        for name, save in (
            ("page_change", lambda s: commit_practice_state_from_session(s, reason="page_change")),
            ("flush_practice_edits", flush_practice_edits),
            ("prepare_practice_page", prepare_practice_page),
            ("local_edit_preserve", lambda s: (mark_practice_local_edit(s), prepare_practice_page(s))),
        ):
            with self.subTest(path=name):
                session = self._stale_say_groove_while_attya_active()
                save(session)
                self.assertEqual(_canon(session), ("Ballad", SAY_ID))

    def test_resolver_still_rejects_it_after_generic_saves(self) -> None:
        session = self._stale_say_groove_while_attya_active()
        commit_practice_state_from_session(session, reason="autosave")
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))

    def test_changed_session_groove_is_saved_unprovenanced_not_as_current_song(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        session["practice_groove_style"] = "Ballad"  # some non-resolver write
        commit_practice_state_from_session(session, reason="page_change")
        self.assertEqual(_canon(session), ("Ballad", ""))
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")

    def test_identity_in_a_generic_payload_is_ignored(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        write_canonical_practice_state(
            session,
            {"practice_groove_style": "Ballad", "practice_groove_song_identity": ATTYA_ID},
            reason="some_generic_copy",
        )
        self.assertEqual(_canon(session), ("Ballad", ""))

    def test_field_merge_in_startup_align_carries_snapshot_provenance(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        # Snapshot without a song pick -> legacy restore applies; the merged
        # groove must keep the snapshot's provenance, never ATTYA's.
        align_authoritative_canonical_from_hydrated(session, _snapshot(None, "Ballad", SAY_ID))
        commit_practice_state_from_session(session, reason="autosave")
        self.assertEqual(session[PRACTICE_STATE_KEY]["practice_groove_song_identity"], SAY_ID)
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")


class TestD_MatchingProvenanceSurvives(unittest.TestCase):
    def test_save_restore_rerun_cycles_keep_attya_stamp(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        for _ in range(3):
            commit_practice_state_from_session(session, reason="autosave")
            prepare_practice_page(session)
            saved = {PRACTICE_STATE_KEY: dict(session[PRACTICE_STATE_KEY])}
            apply_cloud_practice_state_if_allowed(session, saved, authoritative=True)
            self.assertEqual(_render(session, ATTYA, "Jazz swing"), "Jazz swing")
            self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))


class TestE_GenuineCurrentSongGroove(unittest.TestCase):
    def test_genuine_edit_is_stamped_for_current_song_and_survives_saves(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        session["backing_groove_style"] = "Bossa nova"
        mark_backing_user_edit(session)
        self.assertEqual(_render(session, ATTYA, "Jazz swing"), "Bossa nova")
        self.assertEqual(_canon(session), ("Bossa nova", ATTYA_ID))
        commit_practice_state_from_session(session, reason="autosave")
        saved = {PRACTICE_STATE_KEY: dict(session[PRACTICE_STATE_KEY])}
        apply_cloud_practice_state_if_allowed(session, saved, authoritative=True)
        self.assertEqual(_canon(session), ("Bossa nova", ATTYA_ID))


class TestF_PreProvenanceBlobs(unittest.TestCase):
    """Blobs saved before groove provenance existed carry no stamp. They are
    restored as unprovenanced (no identity is invented for them) and self-heal
    once to the active song's authoritative default. Consequence: a manual
    groove override saved before provenance existed is dropped once."""

    def test_unstamped_groove_restores_unprovenanced_then_heals_once(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        apply_cloud_practice_state_if_allowed(session, _snapshot(None, "Ballad", None), authoritative=True)
        self.assertEqual(_canon(session), ("Ballad", ""))
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))
        healed_blob = dict(session[PRACTICE_STATE_KEY])
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")
        self.assertEqual(session[PRACTICE_STATE_KEY], healed_blob, "healed more than once")

    def test_pre_provenance_manual_override_is_dropped_once(self) -> None:
        session: dict = {}
        _render(session, ATTYA, "Jazz swing")
        apply_cloud_practice_state_if_allowed(session, _snapshot(None, "Bossa nova", None), authoritative=True)
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")


class TestH_StaleBackingStillContained(unittest.TestCase):
    """d21b373: a stale Backing groove without user edit intent must not
    become Practice's groove, including after a skipped late restore."""

    def test_stale_backing_groove_does_not_leak_into_practice(self) -> None:
        session: dict = {}
        _render(session, SAY, "Ballad")
        snapshot = _snapshot(SAY, "Ballad", SAY_ID)
        _render(session, ATTYA, "Jazz swing")
        align_authoritative_canonical_from_hydrated(session, snapshot)
        session["backing_groove_style"] = "Pop groove"  # e.g. a play-session expiry
        for _ in range(3):
            self.assertEqual(_render(session, ATTYA, "Jazz swing"), "Jazz swing")
        self.assertEqual(_canon(session), ("Jazz swing", ATTYA_ID))


if __name__ == "__main__":
    unittest.main()
