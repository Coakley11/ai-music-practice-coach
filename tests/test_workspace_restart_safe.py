"""The active workspace survives an app restart without widening anyone's access.

The local workspace files live on the app server's disk, which a hosted restart wipes. The last
explicitly chosen workspace is also remembered in the signed-in account's own cloud rows.
No network: the cloud is an in-memory fake keyed by account, like the real ``user_id`` filter.
"""

from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import suite_workspace as sw
from suite_workspace import init_suite_workspace, set_active_workspace_id


class _FakeSt:
    def __init__(self, session: dict | None = None, *, query: dict | None = None) -> None:
        self.session_state: dict = dict(session or {})
        self.query_params = dict(query or {})


def _auth(email: str, ext: str) -> dict:
    return {
        "_suite_auth_session": True,
        "_suite_auth_user_id": f"uuid-{ext}",
        "_suite_auth_user_email": email,
        "_suite_auth_external_id": ext,
    }


class FakeAccountCloud:
    """suite_saved_items for many accounts; every call is filtered by the *current* identity."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str, str], dict] = {}
        self.fail_reads = False
        self.writes: list[tuple[str, str]] = []
        self.identity = lambda: "default"

    def remember(self, app, item_type, item_key, *, title, payload=None):
        self.writes.append((self.identity(), (payload or {}).get("workspace_id", "")))
        self.rows[(self.identity(), app, item_type, item_key)] = {
            "item_key": item_key,
            "payload": dict(payload or {}),
        }
        return {"write_mode": "upsert"}

    def load(self, *, app=None, item_type=None, limit=100, **_k):
        if self.fail_reads:
            raise RuntimeError("cloud down")
        who = self.identity()
        return [
            dict(v)
            for (u, a, t, _k2), v in self.rows.items()
            if u == who and a == app and t == item_type
        ][:limit]


class RestartCase(unittest.TestCase):
    auth = False

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data = Path(self.tmp.name)
        self.data = data
        self.cloud = FakeAccountCloud()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for target, value in (
            ("suite_workspace.DATA_DIR", data),
            ("suite_workspace._PERSISTED_FILE", data / "suite_active_workspace.json"),
            ("suite_workspace_registry.DATA_DIR", data),
            ("suite_workspace_registry.REGISTRY_FILE", data / "workspaces" / "_ownership_registry.json"),
            ("suite_workspace_registry.ACTIVE_DIR", data / "workspaces" / "_active"),
        ):
            stack.enter_context(mock.patch(target, value))
        stack.enter_context(mock.patch("suite_auth.is_auth_enabled", return_value=self.auth))
        stack.enter_context(
            mock.patch("custom_song_library.cloud_storage_status", return_value={"durable": True, "state": "durable"})
        )
        stack.enter_context(mock.patch("suite_account.remember_saved_item", side_effect=self.cloud.remember))
        stack.enter_context(mock.patch("suite_account.load_saved_items", side_effect=self.cloud.load))
        self.who = "default"
        self.cloud.identity = lambda: self.who
        stack.enter_context(mock.patch("suite_user.get_external_user_id", side_effect=lambda: self.who))

    def restart(self) -> None:
        """A hosted restart: the server's disk is wiped (the cloud is not)."""
        for f in self.data.rglob("*.json"):
            f.unlink()

    def boot(self, session: dict | None = None, query: dict | None = None) -> tuple[_FakeSt, str]:
        st = _FakeSt(session, query=query)
        return st, init_suite_workspace(st)


class TestAuthDisabled(RestartCase):
    def test_the_chosen_workspace_survives_a_restart(self) -> None:
        st, ws = self.boot()
        self.assertEqual(ws, "daniel")
        set_active_workspace_id(st, "ariel")
        self.assertEqual(self.cloud.writes[-1], ("default", "ariel"))
        self.restart()
        _st2, ws2 = self.boot()
        self.assertEqual(ws2, "ariel")

    def test_without_a_remembered_choice_nothing_is_written_or_invented(self) -> None:
        self.restart()
        _st, ws = self.boot()
        self.assertEqual(ws, "daniel")
        self.assertEqual(self.cloud.writes, [])

    def test_a_failed_cloud_read_never_overwrites_the_remembered_choice(self) -> None:
        st, _ = self.boot()
        set_active_workspace_id(st, "ariel")
        self.restart()
        self.cloud.fail_reads = True
        st2, ws = self.boot()
        self.assertEqual(ws, "daniel")  # cannot know, falls back as before
        self.assertEqual([w for _u, w in self.cloud.writes], ["ariel"])  # no write of "daniel"
        self.cloud.fail_reads = False
        _st3, ws3 = self.boot()
        self.assertEqual(ws3, "ariel")  # recovered once the cloud is back
        self.assertTrue(st2)

    def test_an_explicit_url_workspace_wins_and_becomes_the_remembered_one(self) -> None:
        st, _ = self.boot()
        set_active_workspace_id(st, "ariel")
        self.restart()
        st2, ws = self.boot(query={"suite_workspace": "guest"})
        self.assertEqual(ws, "guest")
        self.assertEqual(self.cloud.writes[-1][1], "guest")
        self.restart()
        self.assertEqual(self.boot()[1], "guest")
        self.assertTrue(st2)

    def test_booting_does_not_rewrite_an_unchanged_choice(self) -> None:
        st, _ = self.boot()
        set_active_workspace_id(st, "ariel")
        before = len(self.cloud.writes)
        self.restart()
        self.boot()
        self.boot()
        self.assertEqual(len(self.cloud.writes), before)

    def test_without_cloud_the_local_file_still_works(self) -> None:
        with mock.patch(
            "custom_song_library.cloud_storage_status", return_value={"durable": False, "state": "not_configured"}
        ):
            st, _ = self.boot()
            set_active_workspace_id(st, "ariel")
            self.assertEqual(self.boot()[1], "ariel")
        self.assertEqual(self.cloud.writes, [])


class TestAuthEnabled(RestartCase):
    auth = True

    def test_an_admin_switch_survives_a_restart(self) -> None:
        self.who = "daniel"
        session = _auth("daniel.cohen11@example.com", "daniel")
        st, ws = self.boot(session)
        self.assertEqual(ws, "daniel")
        set_active_workspace_id(st, "ariel")
        self.restart()
        _st2, ws2 = self.boot(_auth("daniel.cohen11@example.com", "daniel"))
        self.assertEqual(ws2, "ariel")

    def test_a_single_workspace_account_can_never_be_moved_by_a_remembered_value_or_the_url(self) -> None:
        self.who = "ariel"
        # a stale/forged remembered value for another workspace under this very account
        self.cloud.remember("_workspace_pref__global", "workspace_pref", "active_workspace", title="x", payload={"workspace_id": "daniel"})
        self.restart()
        _st, ws = self.boot(_auth("ariel@example.com", "ariel"), query={"suite_workspace": "daniel"})
        self.assertEqual(ws, "ariel")

    def test_one_accounts_remembered_workspace_is_never_read_by_another(self) -> None:
        self.who = "daniel"
        st, _ = self.boot(_auth("daniel.cohen11@example.com", "daniel"))
        set_active_workspace_id(st, "guest")
        self.restart()
        self.who = "ariel"
        _st2, ws = self.boot(_auth("ariel@example.com", "ariel"))
        self.assertEqual(ws, "ariel")

    def test_a_preference_read_before_sign_in_is_not_reused_after_it(self) -> None:
        self.who = "daniel"
        st, _ = self.boot(_auth("daniel.cohen11@example.com", "daniel"))
        set_active_workspace_id(st, "guest")
        self.restart()
        session: dict = {}
        self.who = "default"  # signed out: a different (here: empty) identity
        self.assertEqual(sw.cloud_workspace_pref_allowed(session), "")
        self.who = "daniel"
        session.update(_auth("daniel.cohen11@example.com", "daniel"))
        self.assertEqual(sw.cloud_workspace_pref_allowed(session), "guest")

    def test_a_new_account_with_no_file_and_no_preference_gets_its_owned_workspace(self) -> None:
        self.who = "coakley11"
        self.restart()
        _st, ws = self.boot(_auth("coakley11@example.com", "coakley11"))
        self.assertEqual(ws, "coakley11")


class TestNothingExistingMoves(RestartCase):
    def test_the_remembered_choice_is_stored_outside_every_song_namespace(self) -> None:
        self.assertNotIn(sw._CLOUD_PREF_APP, sw.workspace_storage_app_keys("daniel"))
        self.assertNotIn(sw._CLOUD_PREF_APP, sw.workspace_storage_app_keys("ariel"))
        self.assertFalse(sw._CLOUD_PREF_APP.startswith("music"))
        # the app key a workspace's songs use is unchanged
        self.assertEqual(sw.scoped_cloud_app_id("music", "daniel"), "music")
        self.assertEqual(sw.scoped_cloud_app_id("music", "ariel"), "music__ariel")

    def test_the_preference_is_never_written_through_a_song_save_path(self) -> None:
        st, _ = self.boot()
        set_active_workspace_id(st, "ariel")
        keys = {k[1:] for k in self.cloud.rows}
        self.assertEqual(keys, {("_workspace_pref__global", "workspace_pref", "active_workspace")})


if __name__ == "__main__":
    unittest.main()
