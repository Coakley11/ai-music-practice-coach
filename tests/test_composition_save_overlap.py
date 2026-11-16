"""Composition cloud save: overlapping script runs of ONE session.

Root cause (found in a real browser against an isolated Supabase project): Streamlit starts a new script run while the
previous one is still inside its cloud write. The old run's write lands but it is cut off before the result is recorded,
so the session still believes the old revision is applied. The next run then reserves a revision (the SAME number for
identical content, a higher one for new content) and its compare-and-swap is refused because the cloud already holds a
write made by this very session. The musician saw "Another device or tab saved a newer version" and Save kept failing.

Two guarantees are tested against the real ``save_cloud_full_session`` and an in-memory compare-and-swap store:

1. a session is never refused for its OWN earlier write (it recovers on top of it, or recognises it as already saved);
2. a delayed OLDER run never overwrites content a NEWER run already committed, whatever order the writes complete in;
   and a write from ANOTHER session is never adopted or overwritten.

Revisions are reserved in the order runs start (identical content reuses its number, new content always gets a higher
one), so within a session a higher revision is newer content. ``Device`` reproduces exactly that.
"""
from __future__ import annotations

import copy
import itertools
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
        self.writes.append((expected, candidate, row.get("writer_session")))
        return {**out, "accepted": True, "rows_affected": 1, "write_mode": "conditional_patch", "reason": "conditional_patch_ok"}


class Device:
    """One Streamlit session (browser tab): its own writer token, applied revision and revision reservations."""

    def __init__(self, store, name="A"):
        self.store, self.name = store, name
        self.ss = {}
        self.applied = 0          # the revision this session believes is applied in the cloud
        self.counter = 0          # highest revision this session has reserved or seen
        self.pending = None       # (content, revision) reservation: identical content reuses its number

    # --- revision reservation (mirrors workspace_revision.reserve_workspace_revision_for_canonical_fp)
    def _reserve(self, content):
        if self.pending and self.pending[0] == content:
            return self.pending[1]
        self.counter = max(self.counter, self.applied) + 1
        self.pending = (content, self.counter)
        return self.counter

    def begin(self, content, revision=None):
        """Start a run: reserve its revision and capture its base NOW. Completion is separate, so tests can finish
        overlapping runs in any order. ``revision`` forces a number (used to model another DEVICE's counter)."""
        rev = revision if revision is not None else self._reserve(content)
        if revision is not None:
            self.counter = max(self.counter, revision)
        return SimpleNamespace(content=content, expected=self.applied, candidate=rev)

    def complete(self, run, record=True):
        """Finish a run through the real save path. ``record=False``: the write may land but the run is cut off before
        the session records anything (the browser-observed failure)."""
        state = {"composition_workspace_state": {"active_document": {"content": run.content}}, "workspace_revision": 0}
        prepared = {"candidate_revision": run.candidate, "precondition_expected_revision": run.expected,
                    "expected_revision": run.expected, "device_applied_revision": run.expected,
                    "applied_revision_before_prep": run.expected, "blocked_precheck": run.candidate <= run.expected,
                    "violations_precheck": (["REVISION_REUSED_WITH_DIFFERENT_PAYLOAD"] if run.candidate <= run.expected else [])}
        patches = [
            mock.patch.object(scs, "_streamlit_session", return_value=self.ss),
            mock.patch.object(scs, "_cloud_save_account_context", return_value={}),
            mock.patch.object(scs, "_import_storage", return_value=(self.store, "fake")),
            mock.patch.object(scs, "_scoped_storage_app_key", return_value=APP),
            mock.patch.object(scs, "_logical_app_key_for_cloud", return_value="music"),
            mock.patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            mock.patch("suite_storage_config.get_cloud_config", return_value=object()),
            mock.patch("music_workspace_conditional_cloud_write.prepare_music_conditional_write", return_value=prepared),
            mock.patch.object(scs, "invalidate_cloud_full_session_cache"),
        ]
        for p in patches:
            p.start()
        try:
            result = scs.save_cloud_full_session("music", state, page="composer")
        finally:
            for p in reversed(patches):
                p.stop()
        if record and result.success:
            # the app only moves the applied revision forward, and a confirmed save releases its reservation
            self.applied = max(self.applied, self.store.stored_revision())
            self.counter = max(self.counter, self.applied)
            if self.pending and self.pending[0] == run.content:
                self.pending = None
        return result

    def save(self, content, *, record=True, revision=None):
        return self.complete(self.begin(content, revision), record=record)

    def load_cloud_keep_edits(self):
        """What the app's own 'Load cloud version and keep my edits' does to the bookkeeping."""
        self.applied = self.store.stored_revision()
        self.counter = max(self.counter, self.applied)
        self.pending = None


def stored_content(store):
    return store.row["full_session"]["composition_workspace_state"]["active_document"]["content"]


class TestPlanner(unittest.TestCase):
    def test_not_ours_or_not_a_revision_mismatch_is_a_real_conflict(self):
        self.assertIsNone(scs.plan_own_write_recovery(0, 11, 17))      # foreign writer (own_rev is 0 for them)
        self.assertIsNone(scs.plan_own_write_recovery(14, 14, 17))     # same revision: the refusal was not about revisions

    def test_cloud_holds_an_older_write_of_ours_so_retry_on_top(self):
        self.assertEqual(scs.plan_own_write_recovery(14, 11, 17), ("retry", 14, 17))
        self.assertEqual(scs.plan_own_write_recovery(5, 9, 12), ("retry", 5, 12))     # after an abandoned attempt

    def test_stored_revision_equal_to_the_candidate_is_already_persisted(self):
        self.assertEqual(scs.plan_own_write_recovery(53, 51, 53), ("already_persisted", 53, 53))

    def test_stored_revision_above_the_candidate_means_this_run_is_the_older_one(self):
        self.assertEqual(scs.plan_own_write_recovery(60, 51, 53), ("superseded", 60, 53))   # must never overwrite


class TestFirstTimeSave(unittest.TestCase):
    def test_new_account_first_save_creates_the_row(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v1").success)
        self.assertEqual((stored_content(store), store.stored_revision()), ("v1", 1))

    def test_first_save_then_rapid_edits(self):
        store = FakeStore(); a = Device(store)
        for i in range(1, 8):
            self.assertTrue(a.save("v%d" % i).success, i)
        self.assertEqual(stored_content(store), "v7")


class TestInterruptedRuns(unittest.TestCase):
    """A write lands but the run is cut off before recording it: the next run must not be refused for it."""

    def test_same_content_again_is_recognised_as_already_saved(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v1").success)
        a.save("v2", record=False)                                         # lands at revision 2, nothing recorded
        r = a.save("v2")                                                   # the next run reserves the SAME number
        self.assertTrue(r.success, getattr(r, "failure_stage", ""))
        self.assertEqual(stored_content(store), "v2")
        self.assertTrue(a.save("v3").success)

    def test_new_content_after_an_interrupted_write_lands_on_top(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        a.save("autosave", record=False)
        r = a.save("manual save")                                          # newer content, higher revision
        self.assertTrue(r.success, getattr(r, "failure_stage", ""))
        self.assertEqual(stored_content(store), "manual save")
        self.assertTrue(a.save("next edit").success)

    def test_several_interrupted_writes_in_a_row(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v0").success)
        for i in range(4):
            a.save("x%d" % i, record=False)
        self.assertTrue(a.save("final").success)
        self.assertEqual(stored_content(store), "final")

    def test_randomised_rapid_editing_never_loses_the_last_edit(self):
        for seed in range(60):
            rng = random.Random(seed)
            store = FakeStore(); a = Device(store)
            for i in range(rng.randint(5, 25)):
                content = "s%d-e%d" % (seed, i)
                if rng.random() < 0.35:
                    a.save(content, record=False)
                else:
                    r = a.save(content)
                    self.assertTrue(r.success, "seed %d edit %d: %s" % (seed, i, getattr(r, "failure_stage", "")))
                    self.assertEqual(stored_content(store), content)
            self.assertTrue(a.save("final-%d" % seed).success, seed)
            self.assertEqual(stored_content(store), "final-%d" % seed)


class TestReversedCompletionOrder(unittest.TestCase):
    """A delayed OLDER run must never replace content a NEWER run already committed (data-loss guard)."""

    def test_older_run_finishing_last_does_not_overwrite_the_newer_edit(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        older = a.begin("older edit"); newer = a.begin("NEWER edit")
        self.assertTrue(a.complete(newer).success)                         # the newer run commits first
        r = a.complete(older)                                              # the delayed older run arrives afterwards
        self.assertEqual(stored_content(store), "NEWER edit")              # ... and must not replace it
        self.assertEqual(r.failure_stage, "superseded_by_newer_own_write") # nothing written, and not called a conflict
        self.assertFalse(r.stale_write_blocked)
        self.assertFalse(a.ss.get("_music_stale_write_blocked"))           # and it must not leave the session blocked
        self.assertTrue(a.save("next edit").success)                       # saving carries on
        self.assertEqual(stored_content(store), "next edit")

    def test_three_overlapping_runs_in_every_completion_order(self):
        for order in itertools.permutations(range(3)):
            store = FakeStore(); a = Device(store)
            self.assertTrue(a.save("base").success)
            runs = [a.begin("edit-%d" % i) for i in range(3)]                # edit-2 is the newest
            for i in order:
                a.complete(runs[i])
            self.assertEqual(stored_content(store), "edit-2", "order %s" % (order,))
            self.assertTrue(a.save("after").success, "order %s" % (order,))
            self.assertEqual(stored_content(store), "after", "order %s" % (order,))

    def test_autosave_started_before_a_manual_save_cannot_overwrite_it(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        autosave = a.begin("autosave (older state)")
        manual = a.begin("manual save (newer state)")
        self.assertTrue(a.complete(manual).success)
        a.complete(autosave)                                               # the slow autosave lands last
        self.assertEqual(stored_content(store), "manual save (newer state)")

    def test_manual_save_started_before_an_autosave_loses_to_the_newer_autosave(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        manual = a.begin("manual save"); autosave = a.begin("autosave after the manual save")
        a.complete(autosave); a.complete(manual)
        self.assertEqual(stored_content(store), "autosave after the manual save")

    def test_revisions_never_go_backwards(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        seen = [store.stored_revision()]
        runs = [a.begin("e%d" % i) for i in range(5)]
        for i in (4, 1, 3, 0, 2):
            a.complete(runs[i]); seen.append(store.stored_revision())
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(stored_content(store), "e4")

    def test_randomised_overlap_never_loses_the_newest_edit_or_blocks_saving(self):
        for seed in range(200):
            rng = random.Random(seed)
            store = FakeStore(); a = Device(store)
            a.save("base")
            pending, newest = [], None
            for i in range(rng.randint(3, 12)):
                if rng.random() < 0.6 or not pending:
                    run = a.begin("s%d-e%d" % (seed, i)); pending.append(run); newest = run.content
                else:
                    a.complete(pending.pop(rng.randrange(len(pending))))   # any pending run may complete next
            rng.shuffle(pending)
            for run in pending:
                a.complete(run)
            if newest is not None:
                self.assertEqual(stored_content(store), newest, "seed %d" % seed)
            self.assertTrue(a.save("final-%d" % seed).success, "seed %d" % seed)

    def test_randomised_overlap_with_cut_off_runs(self):
        for seed in range(200):
            rng = random.Random(1000 + seed)
            store = FakeStore(); a = Device(store)
            a.save("base")
            pending, newest = [], None
            for i in range(rng.randint(3, 12)):
                r = rng.random()
                if r < 0.5 or not pending:
                    run = a.begin("s%d-e%d" % (seed, i)); pending.append(run); newest = run.content
                else:
                    a.complete(pending.pop(rng.randrange(len(pending))), record=rng.random() < 0.6)
            rng.shuffle(pending)
            for run in pending:
                a.complete(run, record=rng.random() < 0.6)
            if newest is not None:
                self.assertEqual(stored_content(store), newest, "seed %d" % seed)
            self.assertTrue(a.save("final-%d" % seed).success, "seed %d" % seed)
            self.assertEqual(stored_content(store), "final-%d" % seed)

    def test_same_content_started_twice_then_completed_in_reverse(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        first = a.begin("same"); second = a.begin("same")                  # identical content reuses its revision
        self.assertEqual(first.candidate, second.candidate)
        self.assertTrue(a.complete(second).success)
        r = a.complete(first)                                              # already persisted: no write, no conflict
        self.assertTrue(r.success, getattr(r, "failure_stage", ""))
        self.assertEqual(stored_content(store), "same")


class TestLocalRevisionAheadOfCloud(unittest.TestCase):
    """Writes that never landed can push the session's LOCAL revision ahead of the cloud. The next candidate then equals
    the local revision and the pre-flight refused the session for a conflict that does not exist (the banner 'This
    workspace changed on another device' with no other device involved)."""

    def test_cloud_last_written_by_us_and_behind_our_local_revision_is_not_a_conflict(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v1").success)                              # cloud at 1, written by this session
        a.applied = a.counter = 9                                          # local revision ran ahead (writes never landed)
        r = a.save("v2", revision=9)                                       # candidate 9 is not above applied 9
        self.assertTrue(r.success, getattr(r, "failure_stage", ""))
        self.assertEqual(stored_content(store), "v2")
        self.assertEqual(store.stored_revision(), 9)                       # written AT the reserved revision, never bumped
        self.assertEqual(r.cloud_payload_revision, 9)
        self.assertFalse(a.ss.get("_music_stale_write_blocked"))
        self.assertTrue(a.save("v3").success)                              # and saving carries on

    def test_cloud_last_written_by_another_session_stays_refused(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(b.save("B wrote this").success)                    # cloud at 1, written by B
        a.applied = a.counter = 9
        before = (store.stored_revision(), stored_content(store))
        r = a.save("A edit", revision=9)
        self.assertFalse(r.success)                                        # not ours: genuine conflict, refused
        self.assertEqual((store.stored_revision(), stored_content(store)), before)

    def test_cloud_ahead_of_our_local_revision_is_not_adopted(self):
        store = FakeStore(); a = Device(store)
        for i in range(5):
            self.assertTrue(a.save("v%d" % i).success)                     # cloud at 5, ours
        a.applied = 3                                                      # local believes 3, candidate 3: older run
        r = a.save("an old straggler", revision=3)
        self.assertEqual(stored_content(store), "v4")                      # the newer committed content survives
        self.assertFalse(r.success)
        self.assertEqual(r.failure_stage, "superseded_by_newer_own_write") # an older run, not a conflict ...
        self.assertFalse(a.ss.get("_music_stale_write_blocked"))           # ... so no banner and no block

    def test_repeated_local_ahead_episodes(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v0").success)
        for i in range(1, 6):
            a.applied = a.counter = store.stored_revision() + 4            # ahead again each time
            r = a.save("v%d" % i, revision=a.counter)
            self.assertTrue(r.success, "episode %d: %s" % (i, getattr(r, "failure_stage", "")))
            self.assertEqual(stored_content(store), "v%d" % i)
            self.assertEqual(store.stored_revision(), a.counter, "episode %d: the reserved revision is what was written" % i)


class TestWrittenRevisionIsTheReservedRevision(unittest.TestCase):
    """The app confirms a workspace save by comparing the revision READ BACK from the cloud with the revision the run
    RESERVED. A write landed at any other revision can never be confirmed: the cloud holds the data, the session keeps
    saying 'not verified', and every retry climbs the revision again (seen in production: revision 209 with a confirmed
    base of 0). Whatever recovery path a save takes, the revision written must equal the revision reserved."""

    def _check(self, store, run, result, name):
        self.assertTrue(result.success, "%s: %s" % (name, getattr(result, "failure_stage", "")))
        self.assertEqual(result.cloud_payload_revision, run.candidate, name + ": result reports the reserved revision")
        self.assertEqual(store.stored_revision(), run.candidate, name + ": the cloud holds the reserved revision")

    def test_plain_save(self):
        store = FakeStore(); a = Device(store)
        run = a.begin("v1"); self._check(store, run, a.complete(run), "plain")

    def test_retry_on_top_of_our_own_overlapping_write(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        a.save("autosave", record=False)
        run = a.begin("manual"); self._check(store, run, a.complete(run), "retry")

    def test_same_content_already_persisted(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("base").success)
        a.save("v2", record=False)
        run = a.begin("v2"); self._check(store, run, a.complete(run), "already persisted")

    def test_local_revision_ahead_of_the_cloud(self):
        store = FakeStore(); a = Device(store)
        self.assertTrue(a.save("v1").success)
        a.applied = a.counter = 9
        run = a.begin("v2", revision=9); self._check(store, run, a.complete(run), "local ahead")

    def test_every_recovery_path_in_random_sequences(self):
        for seed in range(120):
            rng = random.Random(5000 + seed)
            store = FakeStore(); a = Device(store)
            a.save("base")
            for i in range(rng.randint(3, 14)):
                kind = rng.random()
                if kind < 0.3:
                    a.save("s%d-%d" % (seed, i), record=False)
                elif kind < 0.5:
                    a.applied = a.counter = store.stored_revision() + rng.randint(1, 5)   # local ahead of the cloud
                    run = a.begin("s%d-%d" % (seed, i), revision=a.counter)
                    r = a.complete(run)
                    if r.success:
                        self.assertEqual(store.stored_revision(), run.candidate, "seed %d step %d (local ahead)" % (seed, i))
                else:
                    run = a.begin("s%d-%d" % (seed, i)); r = a.complete(run)
                    if r.success and stored_content(store) == run.content:
                        self.assertEqual(r.cloud_payload_revision, run.candidate, "seed %d step %d" % (seed, i))
            run = a.begin("final-%d" % seed); r = a.complete(run)
            self.assertTrue(r.success, "seed %d final: %s" % (seed, getattr(r, "failure_stage", "")))
            self.assertEqual(store.stored_revision(), run.candidate, "seed %d final" % seed)


class TestConfirmationIsDiagnosable(unittest.TestCase):
    def _log(self, **kw):
        import contextlib, io
        import music_workspace_cloud_save as mws
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mws._log_cloud_confirmation("readback", **kw)
        return buf.getvalue()

    def test_an_unconfirmed_write_names_the_failing_check_and_only_key_names(self):
        payload = {"practice_state": {"note": "SECRET-LYRIC-TEXT"}, "same": {"a": 1}, "composition_workspace_state": {"x": 1}}
        readback = {"practice_state": {"note": "different"}, "same": {"a": 1}, "composition_workspace_state": {"x": 1}}
        out = self._log(readback_rev=210, rev_after=209, fp_matches=False, revision_advanced=True, readback_ok=False,
                        payload=payload, readback=readback)
        self.assertIn("[music_cloud_confirm]", out)
        self.assertIn("confirmed=False", out); self.assertIn("rev_matches=False", out); self.assertIn("fp_matches=False", out)
        self.assertIn("practice_state", out)
        self.assertNotIn("same", out.split("differing_top_level_keys=")[1])
        self.assertNotIn("SECRET-LYRIC-TEXT", out); self.assertNotIn("different", out)

    def test_a_confirmed_write_logs_flags_and_no_keys(self):
        out = self._log(readback_rev=209, rev_after=209, fp_matches=True, revision_advanced=True, readback_ok=True,
                        payload={"a": 1}, readback={"a": 1})
        self.assertIn("confirmed=True", out); self.assertIn("differing_top_level_keys=-", out)

    def test_logging_never_breaks_a_save(self):
        self._log(readback_rev=1, rev_after=1, fp_matches=False, revision_advanced=True, readback_ok=False,
                  payload=object(), readback=object())


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

    def test_a_delayed_older_run_never_overwrites_another_devices_newer_write(self):
        store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
        self.assertTrue(a.save("base").success)
        b.load_cloud_keep_edits()
        a_run = a.begin("A edit"); b_run = b.begin("B edit")
        self.assertTrue(b.complete(b_run).success)
        r = a.complete(a_run)
        self.assertFalse(r.success)
        self.assertEqual(stored_content(store), "B edit")

    def test_foreign_write_in_the_middle_of_our_overlapping_runs(self):
        for order in itertools.permutations(range(3)):
            store = FakeStore(); a = Device(store, "A"); b = Device(store, "B")
            self.assertTrue(a.save("base").success)
            runs = [a.begin("A%d" % i) for i in range(3)]
            a.complete(runs[order[0]])
            b.load_cloud_keep_edits()                                       # B opens the song as A's first run landed
            self.assertTrue(b.save("B foreign").success)
            for i in order[1:]:
                a.complete(runs[i])
            self.assertEqual(stored_content(store), "B foreign", "order %s" % (order,))   # B is the last writer: protected


if __name__ == "__main__":
    unittest.main()
