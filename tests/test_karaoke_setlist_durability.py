"""A saved Karaoke setlist stays saved until the singer deliberately changes it.

The browser reproduction (scripts/_accept_karaoke_setlist_durability.py, dev f42e1d0b) showed the
chain: a tab with no setlist saved over the server disk, a new session restored that empty disk, its
save replaced the cloud row's session, and a restart left the setlist nowhere. These pin each link.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import karaoke_setlist_durability as ksd

SET = [{"entry_id": "e1", "title": "Shape of You", "practice_key": "Bm"},
       {"entry_id": "e2", "title": "Perfect", "practice_key": "Ab"},
       {"entry_id": "e3", "title": "Let It Be", "practice_key": "C"}]
STAMP_OLD = "2026-11-15T10:00:00.000000+00:00"
STAMP_NEW = "2026-11-16T10:00:00.000000+00:00"


def full(queue=None, stamp=None, **other):
    session = dict(other)
    if queue is not None:
        session[ksd.QUEUE_KEY] = [dict(e) for e in queue]
    if stamp:
        session[ksd.META_KEY] = {"saved_at": stamp, "count": len(queue or []), "deliberate": True}
    return {"core": {"pick_key": "x"}, "session": session}


def titles(state):
    q, _ = ksd.setlist_of(state)
    return None if q is None else [e["title"] for e in q]


class TheRule(unittest.TestCase):
    def test_a_missing_setlist_never_replaces_a_saved_one(self):
        self.assertEqual(titles(ksd.merge_cloud_full_session(full(), full(SET, STAMP_OLD))), [e["title"] for e in SET])

    def test_an_empty_setlist_nobody_cleared_never_replaces_a_saved_one(self):
        self.assertEqual(len(ksd.setlist_of(ksd.merge_cloud_full_session(full([]), full(SET)))[0]), 3)
        self.assertEqual(len(ksd.setlist_of(ksd.merge_cloud_full_session(full([]), full(SET, STAMP_OLD)))[0]), 3)

    def test_an_older_copy_never_replaces_a_newer_deliberate_edit(self):
        older = full(SET[:1], STAMP_OLD)
        newer = full(SET, STAMP_NEW)
        self.assertEqual(len(ksd.setlist_of(ksd.merge_cloud_full_session(older, newer))[0]), 3)

    def test_a_deliberate_edit_replaces_the_stored_setlist(self):
        self.assertEqual(titles(ksd.merge_cloud_full_session(full(SET[::-1], STAMP_NEW), full(SET, STAMP_OLD))),
                         ["Let It Be", "Perfect", "Shape of You"])

    def test_a_deliberate_clear_wins(self):
        self.assertEqual(ksd.setlist_of(ksd.merge_cloud_full_session(full([], STAMP_NEW), full(SET, STAMP_OLD)))[0], [])

    def test_order_and_keys_survive_exactly(self):
        out = ksd.merge_cloud_full_session(full(), full(SET, STAMP_OLD))
        self.assertEqual(ksd.setlist_of(out)[0], SET)

    def test_the_rest_of_the_incoming_session_is_kept(self):
        out = ksd.merge_cloud_full_session(full(None, None, studio_page="Songs"), full(SET, STAMP_OLD))
        self.assertEqual(out["session"]["studio_page"], "Songs")
        self.assertEqual(out["core"], {"pick_key": "x"})

    def test_the_incoming_state_is_not_mutated(self):
        incoming = full(None, None, studio_page="Songs")
        ksd.merge_cloud_full_session(incoming, full(SET, STAMP_OLD))
        self.assertNotIn(ksd.QUEUE_KEY, incoming["session"])

    def test_nothing_expires(self):
        ancient = full(SET, "2021-01-01T00:00:00.000000+00:00")
        self.assertEqual(len(ksd.setlist_of(ksd.merge_cloud_full_session(full(), ancient))[0]), 3)


class TheSavingSessionAdoptsTheSavedSetlist(unittest.TestCase):
    def test_cloud_guard_hands_the_setlist_to_the_session(self):
        session = {"studio_page": "Songs"}
        ksd.merge_cloud_full_session(full(), full(SET, STAMP_OLD), session=session)
        self.assertEqual(session[ksd.QUEUE_KEY], SET)
        self.assertEqual(session[ksd.META_KEY]["saved_at"], STAMP_OLD)


class DiskSave(unittest.TestCase):
    def setUp(self):
        ksd.reset_disk_cache_for_tests()
        self.tmp = Path(tempfile.mkdtemp())
        self.file = self.tmp / "music_user_state.json"
        import suite_user_persistence as sup

        self.sup = sup
        self.p = mock.patch.object(sup, "state_file_path", lambda app_id, workspace_id=None: self.file)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        ksd.reset_disk_cache_for_tests()

    def test_a_tab_without_the_setlist_cannot_erase_it_from_disk(self):
        self.assertTrue(self.sup.save_user_state("music", full(SET, STAMP_OLD)))
        self.assertTrue(self.sup.save_user_state("music", full(None, None, studio_page="Practice")))
        state, _warn, _ts = self.sup._load_raw("music")
        self.assertEqual(titles(state), [e["title"] for e in SET])
        self.assertEqual(state["session"]["studio_page"], "Practice")

    def test_it_holds_after_a_process_restart_too(self):
        self.sup.save_user_state("music", full(SET, STAMP_OLD))
        ksd.reset_disk_cache_for_tests()  # a new server process: nothing cached, the file is read
        self.sup.save_user_state("music", full([]))
        state, _w, _t = self.sup._load_raw("music")
        self.assertEqual(len(ksd.setlist_of(state)[0]), 3)

    def test_a_deliberate_clear_is_written(self):
        self.sup.save_user_state("music", full(SET, STAMP_OLD))
        self.sup.save_user_state("music", full([], STAMP_NEW))
        state, _w, _t = self.sup._load_raw("music")
        self.assertEqual(ksd.setlist_of(state)[0], [])

    def test_reset_to_default_forgets_the_file(self):
        self.sup.save_user_state("music", full(SET, STAMP_OLD))
        self.sup.reset_user_state("music")
        self.sup.save_user_state("music", full([], STAMP_NEW))
        state, _w, _t = self.sup._load_raw("music")
        self.assertEqual(ksd.setlist_of(state)[0], [])

    def test_other_apps_are_untouched(self):
        self.sup.save_user_state("baseball", {"session": {ksd.QUEUE_KEY: SET}})
        self.sup.save_user_state("baseball", {"session": {}})
        state, _w, _t = self.sup._load_raw("baseball")
        self.assertNotIn(ksd.QUEUE_KEY, state["session"])


class CloudSave(unittest.TestCase):
    def test_both_cloud_write_paths_keep_the_setlist(self):
        import suite_storage_supabase as sss

        prior = {"full_session": full(SET, STAMP_OLD), "workspace_revision": 4}
        with mock.patch.object(sss, "_load_state_row_metrics", return_value=prior):
            merged = sss._metrics_for_conditional_write("music", {"full_session": full()}, candidate_workspace_revision=5)
        self.assertEqual(titles(merged["full_session"]), [e["title"] for e in SET])
        with mock.patch.object(sss, "_request", return_value=[{"metrics": prior}]), \
                mock.patch.object(sss, "_cloud_user_id", return_value=None):
            merged2 = sss._merge_state_metrics("music", {"full_session": full([])})
        self.assertEqual(len(ksd.setlist_of(merged2["full_session"])[0]), 3)

    def test_other_apps_are_untouched(self):
        import suite_storage_supabase as sss

        prior = {"full_session": {"session": {ksd.QUEUE_KEY: SET}}}
        with mock.patch.object(sss, "_load_state_row_metrics", return_value=prior):
            merged = sss._metrics_for_conditional_write("baseball", {"full_session": {"session": {}}},
                                                        candidate_workspace_revision=1)
        self.assertNotIn(ksd.QUEUE_KEY, merged["full_session"]["session"])


class Restore(unittest.TestCase):
    def test_a_new_session_gets_the_setlist_from_whichever_copy_still_has_it(self):
        session: dict = {}
        winner = ksd.reconcile_session(session, [("payload", full()), ("disk", full()), ("cloud", full(SET, STAMP_OLD))])
        self.assertEqual(winner, "cloud")
        self.assertEqual(session[ksd.QUEUE_KEY], SET)

    def test_the_newest_deliberate_copy_wins(self):
        session: dict = {}
        ksd.reconcile_session(session, [("disk", full(SET[:1], STAMP_NEW)), ("cloud", full(SET, STAMP_OLD))])
        self.assertEqual(len(session[ksd.QUEUE_KEY]), 1)

    def test_a_session_with_a_newer_edit_keeps_it(self):
        session = {ksd.QUEUE_KEY: SET[:2], ksd.META_KEY: {"saved_at": STAMP_NEW}}
        self.assertEqual(ksd.reconcile_session(session, [("cloud", full(SET, STAMP_OLD))]), "session")
        self.assertEqual(len(session[ksd.QUEUE_KEY]), 2)

    def test_apply_music_disk_state_no_longer_copies_the_setlist_blindly(self):
        import music_persistent_state as mps

        src = Path(mps.__file__).read_text(encoding="utf-8")
        self.assertIn('elif key in ("karaoke_queue", "karaoke_setlist_meta"):', src)
        self.assertIn("_reconcile_karaoke_setlist_on_apply(ss, session_extra)", src)


def meta(stamp, base_stamp="", base=None):
    return {"saved_at": stamp, "base_stamp": base_stamp, "base": base or {}, "deliberate": True}


class TwoEditsThatDidNotSeeEachOther(unittest.TestCase):
    V1 = "2026-11-16T09:00:00.000000+00:00"
    TA = "2026-11-16T10:00:00.000000+00:00"
    TB = "2026-11-16T11:00:00.000000+00:00"

    def test_a_removal_and_an_addition_are_both_kept(self):
        base = ksd.fingerprints(SET)
        a = ([SET[0], SET[2]], meta(self.TA, self.V1, base))                       # A removed Perfect
        new = {"entry_id": "e4", "title": "Love Story", "practice_key": "G"}
        b = (list(SET) + [new], meta(self.TB, self.V1, base))                        # B added Love Story
        q, m = ksd.resolve(b, a)
        self.assertEqual([e["title"] for e in q], ["Shape of You", "Let It Be", "Love Story"])
        self.assertTrue(m.get("merged"))
        self.assertEqual(ksd.resolve(a, b)[0], q)  # same answer whichever copy arrives first

    def test_a_key_change_and_a_reorder_are_both_kept(self):
        base = ksd.fingerprints(SET)
        a = ([SET[2], SET[0], SET[1]], meta(self.TA, self.V1, base))                # A moved Let It Be first
        changed = dict(SET[1], practice_key="A")
        b = ([SET[0], changed, SET[2]], meta(self.TB, self.V1, base))               # B re-keyed Perfect
        q, _m = ksd.resolve(b, a)
        self.assertEqual([(e["title"], e["practice_key"]) for e in q],
                         [("Let It Be", "C"), ("Shape of You", "Bm"), ("Perfect", "A")])

    def test_an_edit_made_from_the_stored_copy_simply_wins(self):
        a = (list(SET), meta(self.TA, self.V1, {}))
        b = ([SET[0]], meta(self.TB, self.TA, ksd.fingerprints(SET)))
        self.assertIs(ksd.resolve(b, a), b)

    def test_an_older_copy_with_no_edit_never_wins(self):
        newer = ([SET[0], SET[2]], meta(self.TA, self.V1, ksd.fingerprints(SET)))
        older = (list(SET), meta(self.V1))
        self.assertIs(ksd.resolve(older, newer), newer)
        self.assertIs(ksd.resolve(newer, older), newer)

    def test_the_disk_save_merges_too(self):
        base = ksd.fingerprints(SET)
        stored = full([SET[0], SET[2]], self.TA)
        stored["session"][ksd.META_KEY].update(base_stamp=self.V1, base=base)
        incoming = full(list(SET) + [{"entry_id": "e4", "title": "Love Story", "practice_key": "G"}], self.TB)
        incoming["session"][ksd.META_KEY].update(base_stamp=self.V1, base=base)
        out = ksd.merge_cloud_full_session(incoming, stored)
        self.assertEqual(titles(out), ["Shape of You", "Let It Be", "Love Story"])

    def test_an_edit_remembers_the_copy_it_started_from(self):
        session = {ksd.QUEUE_KEY: list(SET)}
        ksd.reconcile_session(session, [("cloud", full(SET, self.V1))])
        session[ksd.QUEUE_KEY] = [SET[0]]
        m = ksd.stamp_deliberate_edit(session)
        self.assertEqual(m["base_stamp"], self.V1)
        self.assertEqual(m["base"], ksd.fingerprints(SET))


class LegacyCopiesStillSync(unittest.TestCase):
    def test_an_unstamped_copy_from_another_device_still_brings_its_songs(self):
        session = {ksd.QUEUE_KEY: SET[:2]}
        self.assertEqual(ksd.reconcile_session(session, [("payload", full(SET))]), "payload")
        self.assertEqual(len(session[ksd.QUEUE_KEY]), 3)

    def test_but_an_unstamped_empty_one_still_cannot_erase(self):
        session = {ksd.QUEUE_KEY: SET}
        self.assertEqual(ksd.reconcile_session(session, [("payload", full([]))]), "session")


class DiskCacheFollowsTheFile(DiskSave):
    def test_a_file_changed_behind_the_cache_is_read_again(self):
        self.sup.save_user_state("music", full(SET, STAMP_OLD))
        import json, time
        raw = json.loads(self.file.read_text(encoding="utf-8"))
        raw["state"] = full(SET[:1], STAMP_NEW)
        time.sleep(0.01)
        self.file.write_text(json.dumps(raw), encoding="utf-8")
        self.sup.save_user_state("music", full())
        state, _w, _t = self.sup._load_raw("music")
        self.assertEqual(len(ksd.setlist_of(state)[0]), 1)

    def test_a_deleted_file_holds_nothing(self):
        self.sup.save_user_state("music", full(SET, STAMP_OLD))
        self.file.unlink()
        self.sup.save_user_state("music", full([]))
        state, _w, _t = self.sup._load_raw("music")
        self.assertEqual(ksd.setlist_of(state)[0], [])


class SaveStatus(unittest.TestCase):
    def test_messages_say_where_the_setlist_is(self):
        s: dict = {ksd.QUEUE_KEY: SET}
        lvl, txt = ksd.save_status_message(ksd.record_save_status(s, ok=True, cloud_enabled=True, cloud_ok=True))
        self.assertEqual(lvl, "success")
        self.assertIn("saved to your account (3 songs)", txt)
        lvl, txt = ksd.save_status_message(ksd.record_save_status(s, ok=True, cloud_enabled=True, cloud_ok=False,
                                                                  reason="stale_revision_conflict"))
        self.assertEqual(lvl, "error")
        self.assertIn("NOT saved to your account", txt)
        self.assertIn("Refresh this page", txt)

    def test_persist_reports_failure_when_the_cloud_did_not_confirm(self):
        import karaoke_ui

        class St:
            session_state: dict = {}

        st = St()
        st.session_state = {ksd.QUEUE_KEY: list(SET)}

        def fake_save(st_, reason=""):
            st_.session_state["_suite_persist_last_save_cloud"] = False
            st_.session_state["_music_force_save_blocked_reason"] = "stale_revision_conflict"
            return True  # disk only - which is what the old code reported as success

        with mock.patch("music_persistent_state.force_save_music_state", side_effect=fake_save), \
                mock.patch("suite_storage_config.cloud_storage_enabled", return_value=True):
            self.assertFalse(karaoke_ui.persist_karaoke_setlist(st))
        self.assertEqual(st.session_state[ksd.SAVE_STATUS_KEY]["where"], "not_saved_to_cloud")
        self.assertTrue(st.session_state[ksd.META_KEY]["saved_at"])


class ClearNeedsConfirmation(unittest.TestCase):
    def test_clear_setlist_only_asks(self):
        import karaoke_ui

        src = Path(karaoke_ui.__file__).read_text(encoding="utf-8")
        block = src[src.index('key="karaoke_clear_queue"'):src.index('key="karaoke_clear_queue"') + 400]
        self.assertIn("CLEAR_CONFIRM_KEY] = True", block)
        self.assertNotIn("clear_queue(st.session_state)", block)
        self.assertIn('key="karaoke_clear_confirm_yes"', src)
        self.assertIn('key="karaoke_clear_confirm_no"', src)


class ResetToDefaultNamesTheSetlist(unittest.TestCase):
    def _warning(self, queue):
        import suite_user_persistence as sup

        shown = []

        class Col:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class St:
            session_state = {}

            def caption(self, *a, **k):
                pass

            def markdown(self, *a, **k):
                pass

            def warning(self, text):
                shown.append(text)

            def columns(self, n):
                return [Col() for _ in range(n)]

            def button(self, *a, **k):
                return False

            def expander(self, *a, **k):
                return Col()

        st = St()
        st.session_state = {sup.reset_confirm_session_key("music"): True}
        if queue is not None:
            st.session_state["karaoke_queue"] = queue
        sup.render_reset_controls(st, "music", on_reset=lambda _st: None, nested=True)
        return " ".join(shown)

    def test_the_confirmation_says_the_setlist_will_be_erased(self):
        text = self._warning(list(SET))
        self.assertIn("erases your saved Karaoke setlist (3 songs", text)

    def test_without_a_setlist_it_says_nothing_about_one(self):
        self.assertNotIn("Karaoke", self._warning([]))


if __name__ == "__main__":
    unittest.main()
