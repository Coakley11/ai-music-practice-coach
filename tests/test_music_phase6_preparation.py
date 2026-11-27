"""Offline guards only: these tests make no hosted Supabase requests."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase6", ROOT / "scripts/verify_music_phase6_hosted.py")
phase6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase6)


def key(ref, role):
    claims = base64.urlsafe_b64encode(json.dumps({"ref": ref, "role": role}).encode()).decode().rstrip("=")
    return "fixture." + claims + ".not-a-real-signature"


@pytest.mark.parametrize("ref,role", [("qhprdlwoxjpkiukxhftp", "service_role"),
                                      (phase6.PROJECT, "anon"), ("unknown", "service_role")])
def test_wrong_credentials_rejected_without_network(ref, role):
    with pytest.raises(ValueError, match="mismatch"):
        phase6.Client(key(phase6.PROJECT, "anon"), key(ref, role))


@pytest.mark.parametrize("value", ["", "sb_secret_fixture", "malformed", "a.bad.c"])
def test_unsupported_credentials_fail_closed(value):
    with pytest.raises(ValueError):
        phase6.validate_key(value, "service_role")


def test_origin_and_installer_are_fixed():
    assert phase6.ORIGIN == "https://smpyutzfktjgpdibdbqb.supabase.co"
    source = (ROOT / "supabase/install/20261112_music_billing_shared_install.sql").read_bytes()
    assert hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest() == phase6.INSTALL_SHA256


@pytest.mark.parametrize("path", ["https://qhprdlwoxjpkiukxhftp.supabase.co", "/rest/v1/../auth", "/other"])
def test_external_paths_rejected(path):
    client = phase6.Client(key(phase6.PROJECT, "anon"), key(phase6.PROJECT, "service_role"))
    with pytest.raises(ValueError):
        client.call("GET", path)


def test_transport_pinned_and_redirects_disabled(monkeypatch):
    seen = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, method, url, **kwargs):
            seen.update(url=url, trust_env=self.trust_env, **kwargs)
            return object()

    monkeypatch.setattr(phase6.requests, "Session", FakeSession)
    phase6.Client(key(phase6.PROJECT, "anon"), key(phase6.PROJECT, "service_role")).call("GET", "/auth/v1/user")
    assert seen["url"].startswith(phase6.ORIGIN + "/")
    assert seen["allow_redirects"] is False
    assert seen["trust_env"] is False


def test_preflight_parses_and_is_read_only():
    pglast = pytest.importorskip("pglast")
    sql = (ROOT / "supabase/preflight/music_billing_isolated_phase6.sql").read_text(encoding="utf8")
    assert len(pglast.parse_sql(sql)) == 6
    assert "repeatable read read only" in sql
    assert "execute format('select count(*)" in sql
    assert "jsonb_build_object('kind','constraint'" in sql


def test_postinstall_parses_and_is_read_only():
    pglast = pytest.importorskip("pglast")
    sql = (ROOT / "supabase/preflight/music_billing_phase6_postinstall.sql").read_text(encoding="utf8")
    assert len(pglast.parse_sql(sql)) == 4
    assert "repeatable read read only" in sql


def write_config(tmp_path, **changes):
    values = {"MUSIC_PHASE6_TEST_URL": phase6.ORIGIN,
              "MUSIC_PHASE6_TEST_ANON_KEY": key(phase6.PROJECT, "anon"),
              "MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": key(phase6.PROJECT, "service_role")}
    values.update(changes)
    path = tmp_path / "private.json"
    path.write_text(json.dumps(values), encoding="utf8")
    return path


def test_local_config_does_not_export_secrets(tmp_path, monkeypatch):
    for name in phase6.CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    credentials = phase6.load_credentials(write_config(tmp_path))
    assert credentials == (key(phase6.PROJECT, "anon"), key(phase6.PROJECT, "service_role"))
    assert all(name not in phase6.os.environ for name in phase6.CONFIG_NAMES)


@pytest.mark.parametrize("changes", [
    {"MUSIC_PHASE6_TEST_URL": "https://qhprdlwoxjpkiukxhftp.supabase.co"},
    {"MUSIC_PHASE6_TEST_URL": phase6.ORIGIN + "/extra"},
    {"MUSIC_PHASE6_TEST_ANON_KEY": key("qhprdlwoxjpkiukxhftp", "anon")},
    {"MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": key("qhprdlwoxjpkiukxhftp", "service_role")},
    {"MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": key(phase6.PROJECT, "anon")},
    {"MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": ""},
    {"MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": 123},
    {"unexpected": "sensitive-value"},
])
def test_config_rejects_mixed_targets_and_malformed_values(tmp_path, monkeypatch, changes):
    for name in phase6.CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError) as error:
        phase6.load_credentials(write_config(tmp_path, **changes))
    assert "sensitive-value" not in str(error.value)


def test_stale_shell_credentials_cannot_override_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY", key("qhprdlwoxjpkiukxhftp", "service_role"))
    with pytest.raises(ValueError, match="conflicts"):
        phase6.load_credentials(write_config(tmp_path))


def test_read_only_access_checks_make_only_get_requests():
    calls = []

    class FakeClient:
        def call(self, method, path, **kwargs):
            calls.append((method, path))
            return type("Response", (), {"status_code": 200})()

    phase6.verify_access(FakeClient())
    assert calls == [("GET", "/auth/v1/settings"), ("GET", "/auth/v1/admin/users?page=1&per_page=1")]


def test_rejected_service_key_stops_before_test_writes():
    class FakeClient:
        def call(self, method, path, **kwargs):
            assert method == "GET"
            return type("Response", (), {"status_code": 401 if kwargs.get("backend") else 200})()

    with pytest.raises(RuntimeError, match="service-role key accepted"):
        phase6.verify_access(FakeClient())


def test_check_config_cli_never_requests_network_or_prints_keys(tmp_path, monkeypatch, capsys):
    import sys
    for name in phase6.CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    config = write_config(tmp_path)
    monkeypatch.setattr(sys, "argv", ["verify", "--approved-project", phase6.PROJECT,
                                     "--config", str(config), "--check-config"])
    monkeypatch.setattr(phase6, "verify_access", lambda client: pytest.fail("Network attempted"))
    monkeypatch.setattr(phase6, "run", lambda *args: pytest.fail("Writes attempted"))
    phase6.main()
    output = capsys.readouterr().out
    assert "MATCH" in output
    assert key(phase6.PROJECT, "anon") not in output
    assert key(phase6.PROJECT, "service_role") not in output


def test_failed_read_only_acceptance_prevents_synthetic_creation(tmp_path, monkeypatch):
    import sys
    for name in phase6.CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    config = write_config(tmp_path)
    monkeypatch.setattr(sys, "argv", ["verify", "--approved-project", phase6.PROJECT,
                                     "--config", str(config), "--preflight-and-installation-verified"])
    def deny(client):
        raise RuntimeError("Key rejected")
    monkeypatch.setattr(phase6, "verify_access", deny)
    monkeypatch.setattr(phase6, "run", lambda *args: pytest.fail("Synthetic writes attempted"))
    with pytest.raises(RuntimeError, match="Key rejected"):
        phase6.main()


@pytest.mark.parametrize("table", ["customers", "subscriptions", "entitlements", "webhook_events"])
def test_write_denial_probes_are_scoped_to_fixture_rows(table):
    from urllib.parse import urlsplit, parse_qs
    user = "00000000-0000-4000-8000-000000000001"
    event = "evt_music_phase6_fixture_10"
    path = phase6.write_probe_path(table, user, event)
    query = parse_qs(urlsplit(path).query)
    assert len(query) == 1
    assert query == ({"stripe_event_id": ["eq." + event]} if table == "webhook_events"
                     else {"app_user_id": ["eq." + user]})


def test_write_denial_probe_cannot_target_unrelated_table():
    with pytest.raises(ValueError):
        phase6.write_probe_path("suite_users", "00000000-0000-4000-8000-000000000001", "evt_fixture")


@pytest.mark.parametrize("error,accepted", [
    ({"code": "P0001", "message": "Customer lease ownership lost"}, True),
    ({"code": "23502", "message": "not-null violation"}, False),
    ({"code": "P0001", "message": "Unrelated validation failure"}, False),
])
def test_released_lease_must_fail_for_the_correct_reason(error, accepted):
    class FakeClient:
        def rpc(self, name, body, **kwargs):
            assert body["p_record"]["provider_status"] == "canceled"
            assert body["p_record"]["cancel_at_period_end"] is False
            assert body["p_record"]["current_period_end"]
            return type("Response", (), {"status_code": 400, "json": lambda self: error})()
    args = (FakeClient(), "evt_fixture", "token", "user", "cus_fixture", "sub_fixture", 100)
    if accepted:
        phase6.assert_released_lease(*args)
    else:
        with pytest.raises(RuntimeError):
            phase6.assert_released_lease(*args)
