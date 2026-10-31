"""Custom-song cloud listing: the row limit is a page size, never a cap on visible songs."""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import custom_song_library as lib
from custom_progression_lab import CPL_SAVED_KEY


class PagingCloud:
    """In-memory suite_saved_items for one account, newest first, with limit/offset."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.calls: list[tuple[int, int]] = []
        self.writes: list[str] = []

    def add(self, n: int, workspace: str = "daniel", prefix: str = "s") -> None:
        for i in range(n):
            sid = f"{prefix}{i}"
            idx = len(self.rows)
            self.rows.append(
                {
                    "item_key": f"custom_{sid}",
                    "title": f"Song {sid}",
                    "payload": {
                        "workspace_id": workspace,
                        "progression": {"id": sid, "name": f"Song {sid}", "updated_at": 1000 + idx},
                    },
                    "valid": True,
                    "updated_at": f"2026-11-01T{idx // 3600:02d}:{(idx // 60) % 60:02d}:{idx % 60:02d}",
                }
            )

    def load(self, *, app=None, item_type=None, limit=100, offset=0, stable_order=False):
        self.calls.append((limit, offset))
        ordered = sorted(self.rows, key=lambda r: (r["updated_at"], r["item_key"]), reverse=True)
        return [copy.deepcopy(r) for r in ordered[offset : offset + limit]]

    def remember(self, app, item_type, item_key, *, title, payload=None):
        self.writes.append(item_key)
        return {"write_mode": "upsert"}


class ListingCase(unittest.TestCase):
    strict_limit = 200

    def setUp(self) -> None:
        self.cloud = PagingCloud()
        patches = [
            mock.patch("custom_song_library.cloud_enabled", return_value=True),
            mock.patch("suite_user.account_mode", return_value="cloud"),
            mock.patch("suite_user.last_account_error", return_value=""),
            mock.patch("suite_account.load_saved_items", side_effect=self.cloud.load),
            mock.patch("suite_account.remember_saved_item", side_effect=self.cloud.remember),
            mock.patch("custom_song_library.active_workspace_id", return_value="daniel"),
            mock.patch(
                "music_egress_config.saved_items_list_limit",
                side_effect=lambda default=50, st=None: min(default, self.strict_limit),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class TestPaging(ListingCase):
    strict_limit = 25  # MUSIC_EGRESS_STRICT page size

    def test_more_songs_than_the_page_size_are_all_listed(self) -> None:
        self.cloud.add(60)
        rows, err = lib.list_cloud_custom_songs()
        self.assertIsNone(err)
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({r["item_key"] for r in rows}), 60)
        self.assertFalse(lib.LAST_CLOUD_MERGE["truncated"])
        self.assertTrue(all(limit <= 25 for limit, _ in self.cloud.calls))

    def test_a_song_beyond_the_first_page_survives_a_restart(self) -> None:
        self.cloud.add(30)
        fresh: dict = {}
        self.assertTrue(lib.merge_custom_songs_from_cloud(fresh, force=True))
        self.assertIn("Song s0", fresh[CPL_SAVED_KEY])
        self.assertEqual(len(fresh[CPL_SAVED_KEY]), 30)

    def test_other_workspace_rows_do_not_use_up_the_page_budget(self) -> None:
        # The old code cut the list at the page size first and filtered by workspace after,
        # so 40 newer rows tagged for another workspace hid every daniel song.
        self.cloud.add(5, workspace="daniel", prefix="mine")
        self.cloud.add(40, workspace="ariel", prefix="theirs")
        rows, err = lib.list_cloud_custom_songs()
        self.assertIsNone(err)
        self.assertEqual(sorted(r["item_key"] for r in rows), [f"custom_mine{i}" for i in range(5)])
        self.assertEqual(lib.LAST_CLOUD_MERGE["other_workspace"], 40)

    def test_an_exact_page_boundary_does_not_loop_or_drop_rows(self) -> None:
        self.cloud.add(50)
        rows, _ = lib.list_cloud_custom_songs()
        self.assertEqual(len(rows), 50)

    def test_truncation_is_reported_not_silent(self) -> None:
        self.cloud.add(30)
        with mock.patch.object(lib, "MAX_LISTED_ROWS", 25):
            rows, err = lib.list_cloud_custom_songs()
        self.assertIsNone(err)
        self.assertTrue(lib.LAST_CLOUD_MERGE["truncated"])
        self.assertEqual(len(rows), 25)

    def test_backend_without_paging_degrades_to_one_page(self) -> None:
        self.cloud.add(30)

        def old_backend(*, app=None, item_type=None, limit=100):
            return self.cloud.load(limit=limit)

        with mock.patch("suite_account.load_saved_items", side_effect=old_backend):
            rows, err = lib.list_cloud_custom_songs()
        self.assertIsNone(err)
        self.assertEqual(len(rows), 25)
        self.assertTrue(lib.LAST_CLOUD_MERGE["truncated"])


class TestPushUnsynced(ListingCase):
    strict_limit = 25

    def test_songs_past_the_first_page_are_not_re_uploaded_over_the_cloud(self) -> None:
        self.cloud.add(60)
        store = {
            CPL_SAVED_KEY: {
                f"Song s{i}": {"id": f"s{i}", "name": f"Song s{i}", "updated_at": 9e9} for i in range(60)
            }
        }
        store[CPL_SAVED_KEY]["Offline"] = {"id": "offline-1", "name": "Offline", "updated_at": 1}
        uploaded, err = lib.push_unsynced_custom_songs(store)
        self.assertEqual((uploaded, err), (1, None))
        self.assertEqual(self.cloud.writes, ["custom_offline-1"])

    def test_a_song_tagged_for_another_workspace_is_never_overwritten(self) -> None:
        self.cloud.add(1, workspace="ariel", prefix="x")
        store = {CPL_SAVED_KEY: {"Song x0": {"id": "x0", "name": "Song x0", "updated_at": 5}}}
        uploaded, err = lib.push_unsynced_custom_songs(store)
        self.assertEqual((uploaded, err), (0, None))
        self.assertEqual(self.cloud.writes, [])

    def test_nothing_is_pushed_when_the_listing_is_incomplete(self) -> None:
        self.cloud.add(30)
        store = {CPL_SAVED_KEY: {"Local": {"id": "local-1", "name": "Local", "updated_at": 1}}}
        with mock.patch.object(lib, "MAX_LISTED_ROWS", 25):
            uploaded, err = lib.push_unsynced_custom_songs(store)
        self.assertEqual((uploaded, err), (0, "cloud_listing_truncated"))
        self.assertEqual(self.cloud.writes, [])


class TestSameTitleMerge(ListingCase):
    def test_two_songs_with_one_title_are_both_kept_when_merged(self) -> None:
        local = {CPL_SAVED_KEY: {"Blues": {"id": "local-id", "name": "Blues", "updated_at": 1}}}
        self.cloud.rows.append(
            {
                "item_key": "custom_cloud-id",
                "title": "Blues",
                "payload": {
                    "workspace_id": "daniel",
                    "progression": {"id": "cloud-id", "name": "Blues", "updated_at": 5, "bpm": 99},
                },
                "valid": True,
                "updated_at": "2026-11-01T00:00:00",
            }
        )
        lib.merge_custom_songs_from_cloud(local, force=True)
        songs = local[CPL_SAVED_KEY]
        self.assertEqual(len(songs), 2)
        self.assertEqual(songs["Blues"]["id"], "local-id")  # the local song is untouched
        self.assertEqual({v["id"] for v in songs.values()}, {"local-id", "cloud-id"})


class TestDiscovery(ListingCase):
    def test_reports_songs_in_other_workspaces_without_listing_their_content(self) -> None:
        with mock.patch(
            "suite_account.count_saved_items_by_storage_app",
            return_value={"music": 3, "music__ariel": 2, "music__guest": 0},
        ):
            self.assertEqual(lib.discover_other_workspace_songs(), {"ariel": 2})

    def test_active_workspace_is_not_reported_and_failures_are_quiet(self) -> None:
        with mock.patch("suite_account.count_saved_items_by_storage_app", return_value={"music": 3}):
            self.assertEqual(lib.discover_other_workspace_songs(), {})
        with mock.patch("suite_account.count_saved_items_by_storage_app", side_effect=RuntimeError("x")):
            self.assertEqual(lib.discover_other_workspace_songs(), {})


class TestStoragePagingParams(unittest.TestCase):
    def _run(self, fn):
        import suite_storage_supabase as sb

        seen: list[dict] = []

        def fake_request(method, path, *, params=None, **_k):
            seen.append(dict(params or {}))
            return fn(len(seen))

        with mock.patch.object(sb, "_request", side_effect=fake_request), mock.patch.object(
            sb, "_scoped_user_id", return_value="uid"
        ):
            yield sb, seen

    def test_request_carries_offset_and_a_stable_tiebreak(self) -> None:
        for sb, seen in self._run(lambda n: []):
            sb.load_saved_items(app="music", item_type="custom_song", limit=25, offset=50, stable_order=True)
        self.assertEqual(seen[0]["offset"], "50")
        self.assertEqual(seen[0]["limit"], "25")
        self.assertEqual(seen[0]["order"], "updated_at.desc,item_key.asc")

    def test_default_request_is_unchanged(self) -> None:
        for sb, seen in self._run(lambda n: []):
            sb.load_saved_items(app="music", item_type="custom_song", limit=10)
        self.assertNotIn("offset", seen[0])
        self.assertEqual(seen[0]["order"], "updated_at.desc")

    def test_count_only_selects_the_app_column_and_the_accounts_own_rows(self) -> None:
        rows = [{"app": "music"}, {"app": "music__ariel"}, {"app": "musicology"}]
        for sb, seen in self._run(lambda n: rows):
            counts = sb.count_valid_items_by_app("custom_song")
        self.assertEqual(counts, {"music": 1, "music__ariel": 1})
        self.assertEqual(seen[0]["select"], "app")
        self.assertEqual(seen[0]["user_id"], "eq.uid")


if __name__ == "__main__":
    unittest.main()
