"""Durable Custom song saving: a failed or missing cloud save is never shown as success.

The cloud is replaced by an in-memory fake at the module boundary the app calls
(``suite_account.remember_saved_item`` / ``load_saved_items``). No network, no credentials.
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import custom_progression_lab as lab
import custom_song_library as lib
from custom_progression_lab import CPL_SAVED_KEY, save_progression_named


class FakeCloud:
    """Tiny stand-in for suite_saved_items keyed like the real table."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.raise_on_write: Exception | None = None
        self.write_mode = "upsert"
        self.raise_on_read: Exception | None = None
        self.writes = 0

    def remember(self, app, item_type, item_key, *, title, payload=None):
        if self.raise_on_write:
            raise self.raise_on_write
        self.writes += 1
        if self.write_mode == "skipped":
            return {"write_mode": "skipped"}
        self.rows[item_key] = {
            "item_key": item_key,
            "title": title,
            "payload": copy.deepcopy(payload),
            "valid": True,
            "updated_at": "2026-11-01T00:00:00Z",
        }
        return {"write_mode": self.write_mode}

    def load(self, *, app=None, item_type=None, limit=100, offset=0, stable_order=False):
        if self.raise_on_read:
            raise self.raise_on_read
        return [copy.deepcopy(r) for r in self.rows.values() if r["valid"]][offset : offset + limit]


def _song(song_id: str = "song-1", name: str = "Bossa Test") -> dict:
    return {
        "id": song_id,
        "name": name,
        "original_key_center": "F",
        "time_signature": "6/8",
        "bpm": 137,
        "progression_style": "Jazz",
        "section_labels": {"Verse": "A"},
        "lyrics_by_section": {"Verse": "line one\nline two"},
        "original_sections": {
            "Verse": [{"chord": "C:3.5|Am:0.5p", "bars": 1}, {"chord": "Fm6/Ab", "bars": 2}, {"chord": "Db7", "bars": 4}],
            "Chorus": [{"chord": "Bbmaj7", "bars": 2}],
        },
    }


class CloudCase(unittest.TestCase):
    def setUp(self) -> None:
        self.cloud = FakeCloud()
        self.workspace = "daniel"
        self.status = {"enabled": True, "mode": "cloud", "reason": ""}
        patches = [
            mock.patch("custom_song_library.cloud_enabled", side_effect=lambda: self.status["enabled"]),
            mock.patch("suite_user.account_mode", side_effect=lambda: self.status["mode"]),
            mock.patch("suite_user.last_account_error", side_effect=lambda: self.status["reason"]),
            mock.patch("suite_account.remember_saved_item", side_effect=self.cloud.remember),
            mock.patch("suite_account.load_saved_items", side_effect=self.cloud.load),
            mock.patch("custom_song_library.active_workspace_id", side_effect=lambda st=None: self.workspace),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        lib.LAST_CLOUD_MERGE.update({"error": "", "found": 0, "other_workspace": 0})


class TestStatusAndSaveStates(CloudCase):
    def test_durable_only_when_configured_and_the_account_resolves(self) -> None:
        self.assertEqual(lib.cloud_storage_status()["state"], "durable")
        self.status["mode"] = "local"
        self.status["reason"] = "HTTPError: 503"
        st = lib.cloud_storage_status()
        self.assertEqual((st["state"], st["durable"]), ("identity_unavailable", False))
        self.assertIn("503", st["message"])
        self.status["enabled"] = False
        self.assertEqual(lib.cloud_storage_status()["state"], "not_configured")

    def test_healthy_save_is_durable_and_survives_a_restart_intact(self) -> None:
        store: dict = {}
        song = _song()
        save_progression_named(store, "Bossa Test", song)
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["state"], "durable")
        self.assertEqual(self.cloud.writes, 1)

        # restart: new process, empty local state, same account
        fresh: dict = {}
        self.assertTrue(lib.merge_custom_songs_from_cloud(fresh, force=True))
        got = fresh[CPL_SAVED_KEY]["Bossa Test"]
        want = store["Bossa Test"]
        for key in ("id", "name", "original_key_center", "time_signature", "bpm", "progression_style",
                    "section_labels", "lyrics_by_section"):
            self.assertEqual(got[key], want[key], key)
        verse = [e["chord"] for e in got["original_sections"]["Verse"]]
        self.assertEqual(verse, ["C:3.5|Am:0.5p", "Fm6/Ab", "Db7"])
        self.assertEqual([e["bars"] for e in got["original_sections"]["Verse"]], [1, 2, 4])
        self.assertEqual(got["original_sections"]["Chorus"][0]["chord"], "Bbmaj7")

    def test_a_write_error_is_a_failure_never_success(self) -> None:
        self.cloud.raise_on_write = RuntimeError("401 Unauthorized")
        store: dict = {}
        save_progression_named(store, "Bossa Test", _song())
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["state"], "failed")
        self.assertFalse(lab.LAST_CLOUD_SAVE_RESULT["ok"])
        self.assertIn("401", lab.LAST_CLOUD_SAVE_RESULT["error"])
        self.assertIn("Bossa Test", store)  # the local copy is kept, not lost
        level, text = lib.describe_save_status("failed", lab.LAST_CLOUD_SAVE_RESULT["error"])
        self.assertEqual(level, "error")
        self.assertIn("lost when the app restarts", text)

    def test_a_skipped_write_is_a_failure(self) -> None:
        self.cloud.write_mode = "skipped"
        save_progression_named({}, "Bossa Test", _song())
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["state"], "failed")
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["error"], "cloud_write_skipped")

    def test_unconfigured_cloud_is_never_reported_as_durable(self) -> None:
        self.status["enabled"] = False
        save_progression_named({}, "Bossa Test", _song())
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["state"], "not_configured")
        self.assertEqual(self.cloud.writes, 0)
        level, text = lib.describe_save_status("not_configured")
        self.assertEqual(level, "warning")
        self.assertIn("lost when the app restarts", text)

    def test_unreachable_account_does_not_attempt_a_write_and_is_not_success(self) -> None:
        self.status["mode"] = "local"
        save_progression_named({}, "Bossa Test", _song())
        self.assertEqual(lab.LAST_CLOUD_SAVE_RESULT["state"], "identity_unavailable")
        self.assertEqual(self.cloud.writes, 0)

    def test_only_the_durable_state_is_green(self) -> None:
        for state in ("failed", "identity_unavailable", "not_configured", "", "anything"):
            self.assertNotEqual(lib.describe_save_status(state)[0], "success", state)
        self.assertEqual(lib.describe_save_status("durable")[0], "success")


class TestReadBackAndRepair(CloudCase):
    def test_a_read_error_is_recorded_and_local_songs_are_untouched(self) -> None:
        self.cloud.raise_on_read = RuntimeError("timeout")
        local = {CPL_SAVED_KEY: {"Mine": _song("mine", "Mine")}}
        before = copy.deepcopy(local)
        self.assertFalse(lib.merge_custom_songs_from_cloud(local, force=True))
        self.assertEqual(local, before)
        self.assertIn("timeout", lib.LAST_CLOUD_MERGE["error"])

    def test_songs_in_another_workspace_are_counted_not_lost(self) -> None:
        self.workspace = "ariel"
        save_progression_named({}, "Ariel Song", _song("ariel-1", "Ariel Song"))
        self.workspace = "daniel"
        fresh: dict = {}
        lib.merge_custom_songs_from_cloud(fresh, force=True)
        self.assertEqual(lib.LAST_CLOUD_MERGE["other_workspace"], 1)
        self.assertNotIn("Ariel Song", fresh.get(CPL_SAVED_KEY, {}))
        self.assertEqual(len(self.cloud.rows), 1)  # still in the cloud

    def test_merge_is_additive_and_never_removes_a_local_song(self) -> None:
        save_progression_named({}, "Cloud One", _song("c-1", "Cloud One"))
        local = {CPL_SAVED_KEY: {"Local Only": _song("l-1", "Local Only")}}
        lib.merge_custom_songs_from_cloud(local, force=True)
        self.assertEqual(set(local[CPL_SAVED_KEY]), {"Local Only", "Cloud One"})

    def test_unsynced_local_songs_are_uploaded_without_touching_existing_cloud_rows(self) -> None:
        save_progression_named({}, "Already There", _song("a-1", "Already There"))
        cloud_before = copy.deepcopy(self.cloud.rows["custom_a-1"])
        edited_local = _song("a-1", "Already There")
        edited_local["bpm"] = 999  # a different local version must NOT overwrite the cloud row
        session = {CPL_SAVED_KEY: {"Already There": edited_local, "Offline Song": _song("o-1", "Offline Song")}}
        uploaded, err = lib.push_unsynced_custom_songs(session)
        self.assertEqual((uploaded, err), (1, None))
        self.assertEqual(self.cloud.rows["custom_a-1"], cloud_before)
        self.assertIn("custom_o-1", self.cloud.rows)

    def test_nothing_is_pushed_when_the_cloud_cannot_be_listed(self) -> None:
        self.cloud.raise_on_read = RuntimeError("down")
        uploaded, err = lib.push_unsynced_custom_songs({CPL_SAVED_KEY: {"X": _song("x-1", "X")}})
        self.assertEqual(uploaded, 0)
        self.assertIn("down", err)
        self.assertEqual(self.cloud.writes, 0)

    def test_delete_failures_are_recorded_not_swallowed(self) -> None:
        store: dict = {}
        save_progression_named(store, "Gone", _song("g-1", "Gone"))
        with mock.patch("suite_account.forget_saved_item", side_effect=RuntimeError("403")):
            lab.delete_progression(store, "Gone")
        self.assertNotIn("Gone", store)
        self.assertFalse(lab.LAST_CLOUD_DELETE_RESULT["ok"])
        self.assertIn("403", lab.LAST_CLOUD_DELETE_RESULT["error"])


class TestAccountIdentityIsNotPinnedByAFailure(unittest.TestCase):
    def test_a_transient_failure_recovers_without_a_restart(self) -> None:
        import suite_user

        suite_user.reset_account_cache()
        calls = {"n": 0}

        def flaky(*_a, **_k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("connection reset")
            return "00000000-0000-0000-0000-000000000001"

        with mock.patch("suite_user.get_cloud_config", return_value=object()), mock.patch(
            "suite_user.get_external_user_id", return_value="daniel"
        ), mock.patch("suite_storage_supabase.ensure_user_row", side_effect=flaky):
            self.assertTrue(suite_user.get_account_user_id().startswith("local:"))
            self.assertIn("connection reset", suite_user.last_account_error())
            # still inside the short back-off: no hammering of the backend
            self.assertTrue(suite_user.get_account_user_id().startswith("local:"))
            self.assertEqual(calls["n"], 1)
            suite_user._ACCOUNT_UID_FAILURE["at"] -= suite_user._ACCOUNT_UID_RETRY_SECONDS + 1
            self.assertEqual(suite_user.get_account_user_id(), "00000000-0000-0000-0000-000000000001")
            self.assertEqual(suite_user.account_mode(), "cloud")
            self.assertEqual(suite_user.last_account_error(), "")
        suite_user.reset_account_cache()


if __name__ == "__main__":
    unittest.main()
