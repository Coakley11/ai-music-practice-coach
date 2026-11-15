"""Composition cloud save: overlapping script runs must never refuse a session for its OWN earlier write.

Root cause (found in a real browser against an isolated Supabase project): Streamlit starts a new script run while the
previous one is still inside its cloud write. The old run's write lands but it is cut off before the result is recorded,
so the session still believes the old revision is applied. The next run then reserves the SAME revision number again
(reservation is per content fingerprint) and its compare-and-swap is refused because the cloud already holds that
revision - written by this very session. The recovery path only accepted a stored revision BELOW the new candidate, so
this exact case surfaced to the musician as "Another device or tab saved a newer version" and Save kept failing.

These tests drive the real ``save_cloud_full_session`` against an in-memory store with real compare-and-swap semantics.
"""
from __future__ import annotations

import copy
import random
import unittest
from types import SimpleNamespace
from unittest import mock

import suite_cloud_state as scs

APP = "music__ucomptest"


class FakeStore:
    """Row = metrics dict. Accepts a write only when the stored revision equals ``expected`` (0 = no row)."""

    ACTIVE_APP_KEYS = frozenset({"music"})

    def __init__(self):
        self.row = None
        self.writes = []

    def _load_state_row_metrics(self, app_key):
        return copy.deepcopy(self.row) if self.row else {}

    def stored_revision(self):
        return int((self.row or {}).get("workspace_revision") or 0)

    def save_current_state_conditional_cas(self, app, *, page="", summary="", metrics=None,
                                           expected_workspace_revision=0, candidate_workspace_revision=0):
        expected, candidate = int(expected_workspace_revision), int(candidate_workspace_revision)
        stored = self.stored_revision()
        ok = (self.row is None and expected == 0) or (self.row is not None and stored == expected)
        out = {"conditional_write_attempted": True, "unconditional_upsert_attempted": False,
               "expected_workspace_revision": expected, "candidate_workspace_revision": candidate}
        if not ok:
            return {**out, "accepted": False, "rows_affected": 0, "write_mode": "conflict", "reason": "conditional_patch_zero_rows"}
        row = copy.deepcopy(metrics or {})
        row["workspace_revision"] = candidate
        self.row = row
        self.writes.append((expected, candidate, row.get("writer_session"), copy.deepcopy(row.get("full_session"))))
        return {**out, "accepted": True, "rows_affected": 1, "write_mode": "conditional_patch", "reason": "conditional_patch_ok"}


class Device:
    """One Streamlit session (browser tab): its own writer token and its own idea of the applied revision."""

    def __init__(self, store, name="A"):
        self.store, self.name = store, name
        self.ss = {}
        self.applied = 0
        self.counter = 0

    def _prepare(self, session, state):
        return {"candidate_revision": self.counter + 1, "precondition_expected_revision": self.applied,
                "expected_revision": self.applied, "device_applied_revision": self.applied,
                "applied_revision_before_prep": self.applied, "blocked_precheck": False, "violations_precheck": []}

    def save(self, content, *, record=True, revision=None):
        """Run one save. ``record=False`` simulates a run cut off after its write landed (nothing recorded)."""
        state = {"composition_workspace_state": {"active_document": {"content": content}}, "workspace_revision": 0}
        if revision is not None:
            self.counter = revision - 1
        patches = [
            mock.patch.object(scs, "_streamlit_session", return_value=self.ss),
            mock.patch.object(scs, "_cloud_save_account_context", return_value={}),
            mock.patch.object(scs, "_import_storage", return_value=(self.store, "fake")),
            mock.patch.object(scs, "_scoped_storage_app_key", return_value=APP),
            mock.patch.object(scs, "_logical_app_key_for_cloud", return_value="music"),
            mock.patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            mock.patch("suite_storage_config.get_cloud_config", return_value=object()),
            mock.patch("music_workspace_conditional_cloud_write.prepare_music_conditional_write", side_effect=self._prepare),
            mock.patch.object(scs, "invalidate_cloud_full_session_cache"),
        ]
        for p in patches:
            p.start()
        try:
            if not record:
                # the write reaches the store, then the run is interrupted before ANY result is recorded
                token = scs._music_writer_token(self.ss)
                self.store.save_current_state_conditional_cas(
                    APP, metrics={scs.FULL_SESSION_KEY: state, scs.WRITER_SESSION_KEY: token},
                    expected_workspace_revision=self.applied, candidate_workspace_revision=self.counter + 1)
                return None
            result = scs.save_cloud_full_session("music", state, page="composer")
        finally:
            for p in reversed(patches):
                p.stop()
        if result.success:
            self.applied = self.store.stored_revision()
            self.counter = max(self.counter, self.applied)
        return result

    def load_cloud_keep_edits(self):
        """What the app's own 'Load cloud version and keep my edits' does to the bookkeeping."""
        self.applied = self.store.stored_revision()
        self.counter = max(self.counter, self.applied)


def stored_content(store):
    return store.row["full_session"]["composition_workspace_state"]["active_document"]["content"]


class TestPlanner(unittest.TestCase):
    def test_not_ours_or_not_a_revision_mismatch_is_a_real_conflict(self):
        self.assertIsNone(scs.plan_own_write_recovery(0, 11, 17))      # foreign writer (own_rev is 0 for them)
        self.assertIsNone(scs.plan_own_write_recovery(14, 14, 17))     # same revision: the refusal was not about revisions

    def test_cloud_ahead_by_our_own_write_keeps_the_candidate(self):
        self.assertEqual(scs.plan_own_write_recovery(14, 11, 17), (14, 17))

    def test_stored_revision_equal_to_the_candidate_is_bumped_above_it(self):
        self.assertEqual(scs.plan_own_write_recovery(53, 51, 53), (53, 54))   # the browser-observed failure
        self.assertEqual(scs.plan_own_write_recovery(60, 51, 53), (60, 61))   # cloud ahead of the candidate too

    def test_cloud_behind_us_after_an_abandoned_attempt(self):
        self.assertEqual(scs.plan_own_write_recovery(5, 9, 12), (5, 12))


class TestFirstTimeSave(unittest.TestCase):
    def test_new_account_first_save_creates_the_row(self):
        store, a = FakeStore(), None
        a = Device(store)
        r = a.save("v1")
        self.assertTrue(r.success)
        self.assertEqual((stored_content(store), store.stored_revision()), ("v1", 1))

    def test_first_save_then_rapid_edits(self):
        store = FakeStore(); a = Device(store)
        for i in range(1, 8):
            self.assertTrue(a.save("v%d" % i).success, i)
        self.assertEqual(stored_content(store), "v7")


class TestOverlappingRuns(unittest.TestCase):
    def test_interrupted_write_then_same_revision_again_is_not_a_conflict(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v1").success)                               # applied = 1
        a.save("v2", record=False)                                          # run X: write lands at 2, cut off
        r = a.save("v2-later-edit")                                         # run Y reserves revision 2 again
        self.assertTrue(r.success, getattr(r, "failure_stage", ""))
        self.assertEqual(stored_content(store), "v2-later-edit")            # the newer edit is what the cloud holds
        self.assertGreater(store.stored_revision(), 2)

    def test_manual_save_overlapping_autosave(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        a.save("autosave", record=False)                                    # autosave lands, run is interrupted
        r = a.save("manual save")                                           # the musician presses Save
        self.assertTrue(r.success)
        self.assertEqual(stored_content(store), "manual save")
        self.assertTrue(a.save("next edit").success)                        # and saving keeps working afterwards

    def test_two_interrupted_writes_in_a_row(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v0").success)
        a.save("x1", record=False)
        a.save("x2", record=False, revision=store.stored_revision())        # a second cut-off run, same reservation
        self.assertTrue(a.save("final").success)
        self.assertEqual(stored_content(store), "final")

    def test_randomised_rapid_editing_never_loses_the_last_edit(self):
        for seed in range(40):
            rng = random.Random(seed)
            store = FakeStore(); a = Device(store)
            last = None
            for i in range(rng.randint(5, 25)):
                content = "s%d-e%d" % (seed, i)
                if rng.random() < 0.35:
                    a.save(content, record=False)                           # cut-off run; its content may or may not stick
                else:
                    r = a.save(content)
                    self.assertTrue(r.success, "seed %d edit %d: %s" % (seed, i, getattr(r, "failure_stage", "")))
                    last = content
            if last is not None:
                self.assertTrue(a.save("final-%d" % seed).success, seed)
                self.assertEqual(stored_content(store), "final-%d" % seed)


class TestGenuineCrossDeviceConflicts(unittest.TestCase):
    """The recovery must never turn a foreign write into one of ours."""

    def test_another_device_write_is_still_refused_and_never_overwritten(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(a.save("shared base").success)
        b.load_cloud_keep_edits()
        self.assertTrue(b.save("B's newer edit").success)                   # device B writes on top
        before = (store.stored_revision(), stored_content(store))
        r = a.save("A's stale edit")                                        # A still believes the old revision
        self.assertFalse(r.success)
        self.assertEqual(r.failure_stage, "stale_revision_conflict")
        self.assertEqual((store.stored_revision(), stored_content(store)), before)

    def test_same_revision_number_from_another_device_is_still_a_conflict(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(a.save("base").success)
        b.load_cloud_keep_edits()
        b.save("B edit", record=False, revision=2)                          # B's write lands at 2 and is cut off
        r = a.save("A edit", revision=2)                                    # A reserves the SAME number 2
        self.assertFalse(r.success)                                         # not ours -> refused
        self.assertEqual(stored_content(store), "B edit")

    def test_resolving_a_real_conflict_lets_saving_continue(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(a.save("base").success)
        b.load_cloud_keep_edits(); self.assertTrue(b.save("B edit").success)
        self.assertFalse(a.save("A edit").success)
        a.load_cloud_keep_edits()                                           # the app's own recovery button
        self.assertTrue(a.save("A edit again").success)
        self.assertEqual(stored_content(store), "A edit again")

    def test_a_foreign_write_after_our_own_is_not_adopted(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(a.save("base").success)
        a.save("A cut-off", record=False)                                   # ours, landed at 2
        b.load_cloud_keep_edits()
        self.assertTrue(b.save("B on top").success)                         # then B overwrites at 3
        r = a.save("A next")
        self.assertFalse(r.success)                                         # last writer is B: A must not adopt it
        self.assertEqual(stored_content(store), "B on top")


if __name__ == "__main__":
    unittest.main()
