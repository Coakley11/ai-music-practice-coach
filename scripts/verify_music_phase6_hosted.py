"""Explicitly opt-in synthetic Auth/PostgREST rehearsal; isolated project ONLY.

Does not install SQL, contact Stripe, or delete records. No tokens/response bodies
are printed. Run only AFTER dashboard preflight and standalone installation pass.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import uuid

import requests

PROJECT = "smpyutzfktjgpdibdbqb"
ORIGIN = f"https://{PROJECT}.supabase.co"
INSTALL_SHA256 = "35c2d92f76d5b6012bfff4efc59d47893153c7660268e76c2086673e71b3c577"
CONFIG_NAMES = ("MUSIC_PHASE6_TEST_URL", "MUSIC_PHASE6_TEST_ANON_KEY",
                "MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY")


def load_credentials(config: Path | None = None) -> tuple[str, str]:
    if config is None:
        values = {name: os.environ.get(name, "").strip() for name in CONFIG_NAMES}
        values[CONFIG_NAMES[0]] = values[CONFIG_NAMES[0]] or ORIGIN
    else:
        try:
            values = json.loads(config.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ValueError("Cannot read valid local configuration JSON; contents suppressed") from None
        if not isinstance(values, dict) or set(values) != set(CONFIG_NAMES):
            raise ValueError("Local config must contain exactly the three documented MUSIC_PHASE6_TEST fields")
        if not all(isinstance(value, str) for value in values.values()):
            raise ValueError("Local config values must be strings")
        values = {name: value.strip() for name, value in values.items()}
        # Never silently mix local-file keys with stale shell credentials.
        if any(os.environ.get(name) and os.environ[name].strip() != values[name]
               for name in CONFIG_NAMES):
            raise ValueError("Local config conflicts with shell settings; clear stale MUSIC_PHASE6_TEST variables")
    if values[CONFIG_NAMES[0]] != ORIGIN:
        raise ValueError("Configured URL is not the isolated Music project; no requests made")
    anon, service = (values[name] for name in CONFIG_NAMES[1:])
    validate_key(anon, "anon")
    validate_key(service, "service_role")
    return anon, service


def validate_key(key: str, role: str) -> None:
    # Identity guard only, NOT cryptographic JWT verification. Supabase verifies it.
    try:
        claims = json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "=="))
    except Exception:
        raise ValueError("Requires this isolated project's legacy JWT API keys") from None
    if claims.get("ref") != PROJECT or claims.get("role") != role:
        raise ValueError("API key project/role mismatch; no requests made")


def check(condition: bool, label: str) -> None:
    if not condition:
        raise RuntimeError(label + " failed (response/credentials intentionally omitted)")


class Client:
    def __init__(self, anon: str, service: str):
        validate_key(anon, "anon")
        validate_key(service, "service_role")
        self.anon, self.service = anon, service

    def call(self, method: str, path: str, *, bearer: str | None = None,
             backend: bool = False, body=None):
        if not path.startswith(("/auth/v1/", "/rest/v1/")) or "://" in path or ".." in path:
            raise ValueError("Invalid test endpoint")
        key = self.service if backend else self.anon
        headers = {"apikey": key, "Authorization": "Bearer " + (bearer or key)}
        # No shared Session across concurrency workers, no inherited proxy settings,
        # no redirect following (a response can never move requests to another host).
        with requests.Session() as session:
            session.trust_env = False
            try:
                return session.request(method, ORIGIN + path, headers=headers,
                                       json=body, timeout=20, allow_redirects=False)
            except requests.RequestException:
                raise RuntimeError("Isolated Supabase request failed; details suppressed") from None

    def rpc(self, name: str, body, **kwargs):
        return self.call("POST", "/rest/v1/rpc/music_billing_" + name, body=body, **kwargs)


def verify_access(client: Client) -> None:
    # Read-only API acceptance checks before any synthetic Auth/data writes.
    check(client.call("GET", "/auth/v1/settings").status_code == 200, "Isolated anon key accepted")
    check(client.call("GET", "/auth/v1/admin/users?page=1&per_page=1", backend=True).status_code == 200,
          "Isolated service-role key accepted")
    print("PASS: isolated Supabase accepted both keys (read-only checks; no identities logged)")


def write_probe_path(table: str, user_id: str, event_id: str) -> str:
    # Hosted safe-update guards can reject an unfiltered PATCH before ACL checks.
    # Always target an existing synthetic fixture, never the entire table.
    if table == "webhook_events":
        selector = "stripe_event_id=eq." + event_id
    elif table in ("customers", "subscriptions", "entitlements"):
        selector = "app_user_id=eq." + str(uuid.UUID(user_id))
    else:
        raise ValueError("Invalid write-denial probe table")
    return "/rest/v1/music_billing_" + table + "?" + selector


def assert_released_lease(client: Client, event: str, token: str, user: str,
                          customer: str, subscription: str, created: int) -> None:
    # Use a complete, otherwise-valid projection so a NOT NULL/check violation
    # cannot masquerade as successful lease protection.
    rejected = client.rpc("complete_delivery", {"p_event_id": event, "p_token": token,
        "p_record": {"app_user_id": user, "stripe_customer_id": customer,
                     "stripe_subscription_id": subscription, "stripe_price_id": "price_synthetic_fixture",
                     "provider_status": "canceled", "cancel_at_period_end": False,
                     "current_period_end": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                     "latest_event_id": event, "latest_event_created": created},
        "p_entitlement": {"plan": "free", "status": "expired", "reason": "stale_lease"}}, backend=True)
    check(rejected.status_code == 400 and rejected.json().get("code") == "P0001"
          and rejected.json().get("message") == "Customer lease ownership lost",
          "Released lease rejected specifically by ownership guard")


def run(client: Client, pause_for_sql: bool = False) -> None:
    run_id = secrets.token_hex(6)
    print("Synthetic rehearsal run:", run_id)
    users = []
    for suffix in ("a", "b"):
        email = f"music-phase6-{run_id}-{suffix}@example.invalid"
        password = secrets.token_urlsafe(32)
        response = client.call("POST", "/auth/v1/admin/users", backend=True,
                               body={"email": email, "password": password, "email_confirm": True,
                                     "user_metadata": {"music_phase6_synthetic": run_id}})
        check(response.status_code in (200, 201), "Synthetic Auth creation")
        user_id = str(uuid.UUID(response.json()["id"]))
        login = client.call("POST", "/auth/v1/token?grant_type=password",
                            body={"email": email, "password": password})
        check(login.status_code == 200, "Password sign-in")
        jwt = login.json()["access_token"]
        identity = client.call("GET", "/auth/v1/user", bearer=jwt)
        check(identity.status_code == 200 and identity.json().get("id") == user_id, "Auth JWT identity")
        users.append((user_id, jwt))
    a, b = users
    print("PASS: two synthetic Auth accounts signed in; real JWT identity checks passed")
    if pause_for_sql:
        print("Two synthetic Auth accounts created. Find their UUIDs in Auth by this run identifier.")
        print("Run the rollback-only SQL role and lifecycle harnesses NOW, before persistent fixtures.")
        check(input("Type SQL_HARNESSES_PASSED to continue: ").strip() == "SQL_HARNESSES_PASSED", "SQL harness checkpoint")
    for uid, jwt in users:
        free = client.call("GET", "/rest/v1/music_billing_entitlements?select=plan,status", bearer=jwt)
        check(free.status_code == 200 and free.json() == [], "Initially Free")
    # Two competing customer bindings for the SAME user: exactly one wins.
    customers = [f"cus_music_phase6_{run_id}_{i}" for i in (1, 2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda customer: client.rpc("attach_customer",
                       {"p_user_id": a[0], "p_customer_id": customer}, backend=True), customers))
    check(sum(r.status_code in (200, 204) for r in replies) == 1 and
          sum(r.status_code in (400, 409) for r in replies) == 1, "Concurrent immutable binding")
    mapping = client.call("GET", f"/rest/v1/music_billing_customers?app_user_id=eq.{a[0]}&select=stripe_customer_id", backend=True)
    check(mapping.status_code == 200 and len(mapping.json()) == 1, "Customer readback")
    customer = mapping.json()[0]["stripe_customer_id"]
    conflict = client.rpc("attach_customer", {"p_user_id": b[0], "p_customer_id": customer}, backend=True)
    check(conflict.status_code in (400, 409), "Cross-owner customer rejection")
    check(client.rpc("attach_customer", {"p_user_id": b[0], "p_customer_id": f"cus_music_phase6_{run_id}_b"}, backend=True).status_code in (200, 204), "Second owner binding")
    with ThreadPoolExecutor(max_workers=2) as pool:
        reservations = list(pool.map(lambda _: client.rpc("reserve_checkout",
            {"p_user_id": a[0], "p_price_id": "price_synthetic_fixture"}, backend=True), range(2)))
    check(all(r.status_code == 200 for r in reservations) and
          reservations[0].json() == reservations[1].json(), "Concurrent stable Checkout reservation")
    claim_args = lambda event, created: {"p_event_id": event, "p_event_type": "customer.subscription.updated",
        "p_created": created, "p_fingerprint": hashlib.sha256(event.encode()).hexdigest(), "p_customer_id": customer}
    events = [f"evt_music_phase6_{run_id}_race_{i}" for i in (1, 2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda event: client.rpc("claim_delivery", claim_args(event, 100), backend=True), events))
    check(all(r.status_code == 200 for r in replies), "Concurrent claims transport")
    values = [r.json() for r in replies]
    check(values.count("busy") == 1, "Exclusive reconciliation lease")
    winner = next(i for i, value in enumerate(values) if value != "busy")
    uuid.UUID(values[winner])
    check(client.rpc("fail_delivery", {"p_event_id": events[winner], "p_token": values[winner]}, backend=True).status_code in (200, 204), "Lease release")
    assert_released_lease(client, events[winner], values[winner], a[0], customer,
                          f"sub_music_phase6_{run_id}", 100)
    print("PASS: concurrent ownership, Checkout reservation and event leases; released token rejected")
    for step, provider in enumerate(("active", "active", "active", "canceled", "active", "canceled", "active", "past_due", "active", "active"), 1):
        event = f"evt_music_phase6_{run_id}_{step}"
        created = 50 if step == 10 else 200 + step  # Old notification, fresh provider snapshot.
        args = claim_args(event, created)
        claim = client.rpc("claim_delivery", args, backend=True)
        check(claim.status_code == 200, "Claim delivery")
        token = str(uuid.UUID(claim.json()))
        paid, scheduled = provider == "active", step == 3
        status = "canceled_period_end" if scheduled else "active" if paid else "past_due" if provider == "past_due" else "expired"
        record = {"app_user_id": a[0], "stripe_customer_id": customer,
                  "stripe_subscription_id": f"sub_music_phase6_{run_id}", "stripe_price_id": "price_synthetic_fixture",
                  "provider_status": provider, "cancel_at_period_end": scheduled,
                  "current_period_end": (datetime.now(timezone.utc) + timedelta(days=-1 if step == 4 else step)).isoformat(),
                  "latest_event_id": event, "latest_event_created": created}
        complete = client.rpc("complete_delivery", {"p_event_id": event, "p_token": token,
            "p_record": record, "p_entitlement": {"plan": "pro" if paid else "free", "status": status, "reason": "phase6_synthetic"}}, backend=True)
        check(complete.status_code in (200, 204), "Atomic completion")
        own = client.call("GET", "/rest/v1/music_billing_entitlements?select=plan,status", bearer=a[1])
        check(own.status_code == 200 and own.json() == [{"plan": "pro" if paid else "free", "status": status}], "Owner entitlement")
        other = client.call("GET", f"/rest/v1/music_billing_entitlements?app_user_id=eq.{a[0]}&select=plan", bearer=b[1])
        check(other.status_code == 200 and other.json() == [], "Other-user RLS")
        duplicate = client.rpc("claim_delivery", args, backend=True)
        check(duplicate.status_code == 200 and duplicate.json() == "", "Duplicate ignored")
    print("PASS: ten lifecycle projections, duplicate deliveries and cross-user entitlement reads")
    for actor, bearer in (("anon", None), ("user_a", a[1]), ("user_b", b[1])):
        for name, body in (("attach_customer", {"p_user_id": a[0], "p_customer_id": customer}),
                           ("reserve_checkout", {"p_user_id": a[0], "p_price_id": "price_fixture"}),
                           ("claim_delivery", claim_args("evt_denied", 999)),
                           ("complete_delivery", {"p_event_id": "evt_denied", "p_token": str(uuid.uuid4()), "p_record": {}, "p_entitlement": {}}),
                           ("fail_delivery", {"p_event_id": "evt_denied", "p_token": str(uuid.uuid4())})):
            check(client.rpc(name, body, bearer=bearer).status_code in (401, 403), "Unprivileged RPC denied")
        for table in ("customers", "subscriptions", "webhook_events", "entitlements"):
            path = "/rest/v1/music_billing_" + table
            if table != "entitlements" or bearer is None:
                check(client.call("GET", path + "?select=*", bearer=bearer).status_code in (401, 403), "Raw table read denied")
            denied = client.call("PATCH", write_probe_path(table, a[0], f"evt_music_phase6_{run_id}_10"),
                                 bearer=bearer, body={"updated_at": datetime.now(timezone.utc).isoformat()})
            check(denied.status_code in (401, 403), f"Direct write denied ({actor}/{table}, HTTP {denied.status_code})")
        check(client.call("PATCH", f"/rest/v1/music_billing_entitlements?app_user_id=eq.{a[0]}", bearer=bearer,
                          body={"plan": "pro", "status": "active"}).status_code in (401, 403), "Self-upgrade denied")
    print("PASS: Auth JWTs, PostgREST RLS/RPC denials, lifecycle, retries and two-worker concurrency")
    print("Synthetic records retained; use run identifier for dashboard review. No cleanup/deletion performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-project", required=True, choices=[PROJECT])
    parser.add_argument("--preflight-and-installation-verified", action="store_true")
    parser.add_argument("--pause-for-sql-role-harness", action="store_true")
    parser.add_argument("--config", type=Path, help="Ignored local JSON configuration; never printed")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-config", action="store_true", help="Check URL/key claims only; no network")
    modes.add_argument("--verify-access", action="store_true", help="Read-only hosted key acceptance checks")
    args = parser.parse_args()
    if not (args.check_config or args.verify_access) and not args.preflight_and_installation_verified:
        parser.error("Stop until Stage A and installation verification have passed")
    installer = Path(__file__).resolve().parents[1] / "supabase/install/20261112_music_billing_shared_install.sql"
    # Git may check out CRLF on Windows; SQL text must otherwise be identical.
    check(hashlib.sha256(installer.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == INSTALL_SHA256, "Installer hash")
    anon, service = load_credentials(args.config)
    client = Client(anon, service)
    print("MATCH: isolated URL and both legacy key project/role claims; signature acceptance requires hosted checks")
    if args.check_config:
        return
    verify_access(client)
    if not args.verify_access:
        run(client, args.pause_for_sql_role_harness)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error)) from None
