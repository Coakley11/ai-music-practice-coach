"""Access-control containment: ownership comes from the immutable Auth user id and an explicit operator policy.

Each case reproduces an attack found on the isolated QA project: any address containing "daniel"/"ariel"
became the personal account, the same email local part at two domains shared one account, a signed-in user was
allowed every preset workspace, admin was decided by the email local part, and a stale registry record could
hand out a personal workspace. Missing or malformed configuration must grant nothing.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections.abc import MutableMapping
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import streamlit as st

import suite_access_policy as pol
import suite_auth
import suite_storage_supabase as sss
import suite_user
import suite_workspace_registry as reg

UID_OWNER = "6cfe63ee-4323-4e14-abd4-3ecd504c0789"
UID_B = "95a54d11-aaaa-4bbb-8ccc-0123456789ab"
UID_C = "11111111-2222-4333-8444-555555555555"
OWN_B = "u" + UID_B.replace("-", "")[:20]
OWN_C = "u" + UID_C.replace("-", "")[:20]


class Proxy(MutableMapping):  # Streamlit's session state: a mapping, not a dict
    def __init__(self):
        self._d = {}

    def __getitem__(self, k):
        return self._d[k]

    def __setitem__(self, k, v):
        self._d[k] = v

    def __delitem__(self, k):
        del self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)


def login(email, uid):
    ss = Proxy()
    suite_auth._apply_authenticated_user(ss, SimpleNamespace(id=uid, email=email))
    return ss


class Base(unittest.TestCase):
    CONFIG: dict = {}

    def setUp(self):
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        for k in (pol.PERSONAL_ENV, pol.ADMIN_ENV):
            os.environ.pop(k, None)
        os.environ.update(self.CONFIG)
        self._auth = mock.patch.object(suite_auth, "is_auth_enabled", return_value=True)
        self._auth.start()

    def tearDown(self):
        self._auth.stop()
        self._env.stop()

    def guard(self, ss, key):
        with mock.patch.object(st, "session_state", ss):
            return sss._enforce_owned_app_key(key)


class TestNoConfiguration(Base):
    """Nothing configured: nobody is admin and nobody gets a personal workspace (fail closed)."""

    def test_ordinary_user_gets_only_their_own_workspace(self):
        ss = login("first.last@example.com", UID_B)
        self.assertEqual(reg.list_owned_workspace_ids(session_state=ss), (OWN_B,))
        for preset in ("daniel", "ariel", "guest", "test_user"):
            self.assertFalse(reg.workspace_access_allowed(preset, session_state=ss), preset)
        self.assertEqual(ss["_suite_active_workspace_id"], OWN_B)

    def test_names_inside_an_email_grant_nothing(self):
        for email in ("daniel@example.com", "xdaniel.fan@evil.example", "ariel.x@evil.example", "Daniel.Cohen11@evil.example"):
            ss = login(email, UID_B)
            self.assertEqual(suite_auth.resolve_auth_external_id(ss), OWN_B, email)
            self.assertFalse(reg.workspace_access_allowed("daniel", session_state=ss), email)
            self.assertFalse(reg.workspace_access_allowed("ariel", session_state=ss), email)

    def test_same_local_part_at_two_domains_are_different_accounts(self):
        a = login("sam@one.example", UID_B)
        b = login("sam@two.example", UID_C)
        self.assertNotEqual(suite_auth.resolve_auth_external_id(a), suite_auth.resolve_auth_external_id(b))
        with self.assertRaises(PermissionError):
            self.guard(a, "music__" + OWN_C)

    def test_nobody_is_admin_by_email_or_name(self):
        for email in ("coakley11@attacker.example", "daniel.cohen11@attacker.example", "coakley11@aol.com"):
            ss = login(email, UID_B)
            self.assertFalse(reg.is_admin_user(session_state=ss), email)
            self.assertFalse(reg.can_switch_workspaces(session_state=ss), email)
        # the programmatic arguments are ignored while accounts exist
        self.assertFalse(reg.is_admin_user(session_state=login("x@y.example", UID_B), external_id="coakley11", email="coakley11@aol.com"))
        self.assertFalse(reg.is_admin_user(external_id="coakley11"))

    def test_own_key_allowed_foreign_shared_and_unscoped_keys_refused(self):
        ss = login("someone@example.com", UID_B)
        self.assertEqual(self.guard(ss, "music__" + OWN_B), "music__" + OWN_B)
        for foreign in ("music__" + OWN_C, "music__daniel", "music__ariel", "music__not_mine", "music"):
            with self.assertRaises(PermissionError, msg=foreign):
                self.guard(ss, foreign)

    def test_no_session_means_no_access_and_internal_apps_are_exempt(self):
        with self.assertRaises(PermissionError):
            self.guard(Proxy(), "music__anyone")
        self.assertEqual(self.guard(Proxy(), "_auth_browser"), "_auth_browser")

    def test_sign_in_disabled_is_untouched(self):
        with mock.patch.object(suite_auth, "is_auth_enabled", return_value=False):
            self.assertEqual(self.guard(Proxy(), "music"), "music")

    def test_user_id_missing_or_not_a_uuid_fails_closed(self):
        for bad in ("", "not-a-uuid", "../daniel", "daniel"):
            ss = login("daniel@example.com", bad)
            self.assertEqual(suite_auth.resolve_auth_external_id(ss), "", bad)
            self.assertEqual(suite_auth.allowed_workspaces_for_session(ss), ())
            self.assertEqual(reg.list_owned_workspace_ids(session_state=ss), ())
            with self.assertRaises(PermissionError):
                self.guard(ss, "music")
            with mock.patch.object(st, "session_state", ss):
                self.assertEqual(suite_user.get_external_user_id(), "unresolved_account")
                self.assertTrue(suite_user._cloud_identity_unverified("unresolved_account"))

    def test_forged_cached_session_fields_do_not_change_identity_or_grant_admin(self):
        ss = login("plain@example.com", UID_B)
        ss["_suite_auth_external_id"] = "daniel"
        ss["_suite_owned_workspace_id"] = "daniel"
        self.assertEqual(suite_auth.resolve_auth_external_id(ss), OWN_B)
        self.assertFalse(reg.is_admin_user(session_state=ss))
        self.assertNotIn("daniel", suite_auth.allowed_workspaces_for_session(ss))

    def test_email_change_keeps_identity(self):
        before = suite_auth.resolve_auth_external_id(login("old@one.example", UID_B))
        after = suite_auth.resolve_auth_external_id(login("brand.new@other.example", UID_B))
        self.assertEqual(before, after)

    def test_unauthenticated_cloud_identity_is_unverified(self):
        with mock.patch.object(st, "session_state", Proxy()):
            self.assertTrue(suite_user._cloud_identity_unverified("default"))


class TestExplicitPolicy(Base):
    CONFIG = {
        pol.PERSONAL_ENV: json.dumps({UID_OWNER: "daniel", UID_C: "ariel"}),
        pol.ADMIN_ENV: UID_OWNER,
    }

    def test_listed_owner_gets_the_legacy_workspace_whatever_their_email(self):
        ss = login("a.completely.different@address.example", UID_OWNER)
        self.assertEqual(suite_auth.resolve_auth_external_id(ss), "daniel")
        self.assertTrue(reg.workspace_access_allowed("daniel", session_state=ss))
        self.assertEqual(self.guard(ss, "music"), "music")  # legacy unscoped key = daniel

    def test_listed_ordinary_owner_of_ariel_does_not_gain_admin_or_daniel(self):
        ss = login("ariel@home.example", UID_C)
        self.assertEqual(suite_auth.allowed_workspaces_for_session(ss), ("ariel",))
        self.assertFalse(reg.is_admin_user(session_state=ss))

    def test_lookalikes_remain_ordinary(self):
        for email in ("xdaniel@evil.example", "coakley11@evil.example", "daniel.cohen11@evil.example"):
            ss = login(email, UID_B)
            self.assertEqual(suite_auth.allowed_workspaces_for_session(ss), (OWN_B,), email)
            self.assertFalse(reg.is_admin_user(session_state=ss), email)
            with self.assertRaises(PermissionError):
                self.guard(ss, "music")

    def test_only_the_listed_auth_user_is_admin(self):
        admin = login("anything@x.example", UID_OWNER)
        self.assertTrue(reg.is_admin_user(session_state=admin))
        self.assertTrue(reg.can_switch_workspaces(session_state=admin))
        self.assertTrue(reg.workspace_access_allowed("ariel", session_state=admin))
        self.assertEqual(self.guard(admin, "music__ariel"), "music__ariel")
        other = login("anything@x.example", UID_B)
        self.assertFalse(reg.can_switch_workspaces(session_state=other))
        with self.assertRaises(PermissionError):
            self.guard(other, "music__ariel")

    def test_list_queries_cover_only_authorised_keys(self):
        ss = login("someone@example.com", UID_B)
        with mock.patch.object(st, "session_state", ss), mock.patch(
            "suite_workspace.workspace_storage_app_keys", return_value=["music", "music__ariel", "music__" + OWN_B]
        ):
            self.assertEqual(sss._workspace_storage_app_keys(), ["music__" + OWN_B])


class TestAmbiguousOrMalformedPolicy(Base):
    def _ext(self, uid):
        return suite_auth.resolve_auth_external_id(login("x@y.example", uid))

    def test_two_auth_users_mapped_to_one_workspace_attach_to_nobody(self):
        os.environ[pol.PERSONAL_ENV] = json.dumps({UID_OWNER: "daniel", UID_B: "daniel"})
        self.assertEqual(self._ext(UID_OWNER), "u" + UID_OWNER.replace("-", "")[:20])
        self.assertEqual(self._ext(UID_B), OWN_B)

    def test_malformed_personal_map_grants_nothing(self):
        for raw in ("{not json", "[1,2,3]", '"daniel"', json.dumps({"coakley11@aol.com": "daniel"}),
                    json.dumps({UID_OWNER: "../daniel"}), json.dumps({UID_OWNER: "default"})):
            os.environ[pol.PERSONAL_ENV] = raw
            self.assertTrue(pol.is_own_workspace_id(self._ext(UID_OWNER)), raw)

    def test_malformed_or_email_admin_config_grants_nothing(self):
        for raw in ("coakley11@aol.com", "{oops", "daniel", "[]", ""):
            os.environ[pol.ADMIN_ENV] = raw
            self.assertEqual(pol.admin_user_ids(), frozenset(), raw)
            self.assertFalse(reg.is_admin_user(session_state=login("coakley11@aol.com", UID_OWNER)), raw)

    def test_admin_list_accepts_comma_separated_and_json_forms(self):
        os.environ[pol.ADMIN_ENV] = f"{UID_OWNER}, {UID_B}"
        self.assertEqual(pol.admin_user_ids(), frozenset({UID_OWNER, UID_B}))
        os.environ[pol.ADMIN_ENV] = json.dumps([UID_OWNER.upper()])
        self.assertEqual(pol.admin_user_ids(), frozenset({UID_OWNER}))


class TestStaleRegistryRecord(Base):
    CONFIG = {pol.PERSONAL_ENV: json.dumps({UID_OWNER: "daniel"})}

    def _owned(self, ss, record):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(reg, "get_registry_record", return_value=record), \
                mock.patch.object(reg, "_write_registry") as write, mock.patch(
                "suite_workspace.DATA_DIR", Path(tmp)):
            out = reg.ensure_owned_workspace_for_session(ss)
            return out, write

    def test_stale_record_pointing_an_ordinary_account_at_daniel_is_ignored_and_not_rewritten(self):
        ss = login("xdaniel@example.net", UID_B)
        out, write = self._owned(ss, {"workspace_id": "daniel", "label": "Daniel"})
        self.assertEqual(out["workspace_id"], OWN_B)
        write.assert_not_called()  # existing ownership records are never modified automatically
        self.assertEqual(ss["_suite_owned_workspace_id"], OWN_B)
        self.assertEqual(reg.get_owned_workspace_id(ss), OWN_B)

    def test_the_listed_owner_keeps_the_personal_workspace_with_a_matching_record(self):
        ss = login("owner@example.com", UID_OWNER)
        out, _ = self._owned(ss, {"workspace_id": "daniel", "label": "Daniel"})
        self.assertEqual(out["workspace_id"], "daniel")

    def test_unresolvable_identity_owns_nothing(self):
        ss = login("a@b.example", "")
        out, write = self._owned(ss, {"workspace_id": "daniel"})
        self.assertEqual(out["workspace_id"], "")
        write.assert_not_called()


class TestSessionStateDoesNotCrossAccounts(Base):
    """Streamlit session state lives as long as the browser tab: the next account must not inherit it."""

    def _load_library(self, ss):
        ss["composition_library_cache"] = ["Legacy Daniel Song"]
        ss["composition_workspace"] = {"title": "Legacy Daniel Song"}

    def test_logout_purges_everything_the_account_loaded(self):
        ss = login("owner@example.com", UID_OWNER)
        self._load_library(ss)
        with mock.patch.object(suite_auth, "_auth_api", side_effect=RuntimeError("no network")):
            suite_auth.logout(ss, st=None)
        self.assertEqual(dict(ss), {})

    def test_a_different_account_taking_over_the_tab_inherits_nothing(self):
        ss = login("owner@example.com", UID_OWNER)
        self._load_library(ss)
        suite_auth._apply_authenticated_user(ss, SimpleNamespace(id=UID_B, email="other@example.com"))
        self.assertNotIn("composition_library_cache", ss)
        self.assertNotIn("composition_workspace", ss)
        self.assertEqual(suite_auth.resolve_auth_external_id(ss), OWN_B)

    def test_the_same_account_signing_in_again_keeps_its_state(self):
        ss = login("owner@example.com", UID_OWNER)
        self._load_library(ss)
        suite_auth._apply_authenticated_user(ss, SimpleNamespace(id=UID_OWNER, email="owner@example.com"))
        self.assertIn("composition_library_cache", ss)

    def test_leftover_state_stamped_by_another_account_is_purged_even_after_auth_keys_were_lost(self):
        ss = login("owner@example.com", UID_OWNER)
        self._load_library(ss)
        for key in (suite_auth.AUTH_USER_ID_KEY, suite_auth.AUTH_SESSION_KEY):
            ss.pop(key, None)
        suite_auth._apply_authenticated_user(ss, SimpleNamespace(id=UID_B, email="other@example.com"))
        self.assertNotIn("composition_library_cache", ss)


class TestPersistedWorkspaceIsClamped(Base):
    def test_a_remembered_foreign_workspace_is_not_returned(self):
        ss = login("someone@example.com", UID_B)
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            active = data / "workspaces" / "_active"
            active.mkdir(parents=True)
            with mock.patch("suite_workspace_registry.ACTIVE_DIR", active), mock.patch(
                "suite_workspace_registry.REGISTRY_FILE", data / "r.json"), mock.patch(
                "suite_workspace.DATA_DIR", data):
                ss["_suite_auth_user_id"] = UID_B
                (active / f"{UID_B}.json").write_text(json.dumps({"workspace_id": "daniel"}), encoding="utf-8")
                got = reg.load_persisted_workspace_for_account(session_state=ss)
                self.assertNotEqual(got, "daniel")


if __name__ == "__main__":
    unittest.main()
