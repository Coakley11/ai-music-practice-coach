"""Supabase persistence adapters for Monetization M2.

Server writes require the dedicated billing service-role environment variable.
The Streamlit app may only read the current user's derived entitlement through
their verified Supabase JWT and row-level security.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from dataclasses import asdict

import requests

from monetization_billing import (
    BillingError,
    event_fingerprint,
    CustomerRecord,
    DerivedEntitlement,
    WebhookBusy,
    SubscriptionRecord,
)
from monetization_config import BillingConfig
from monetization_entitlements import (
    Entitlement,
    EntitlementSubject,
    Plan,
    SubscriptionStatus,
)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        return value[0]
    if isinstance(value, Mapping):
        return value
    return None


class _RestClient:
    def __init__(self, url: str, api_key: str, bearer: str | None = None):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.bearer = bearer or api_key

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
        prefer: str = "return=representation",
    ) -> Any:
        response = requests.request(
            method,
            f"{self.url}/rest/v1/{path.lstrip('/')}",
            params=dict(params or {}),
            json=dict(json_body) if json_body is not None else None,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.bearer}",
                "Content-Type": "application/json",
                "Prefer": prefer,
            },
            timeout=12,
        )
        if not response.ok:
            raise BillingError(f"Supabase billing request failed ({response.status_code})")
        if not response.content:
            return None
        return response.json()


class SupabaseBillingStore:
    """Trusted write-side store; instantiate only inside the billing service."""

    def __init__(self, config: BillingConfig):
        if not config.supabase_url or not config.supabase_service_role_key:
            raise BillingError("Billing Supabase service configuration is incomplete")
        self.client = _RestClient(config.supabase_url, config.supabase_service_role_key)

    def customer_for_user(self, app_user_id: str) -> CustomerRecord | None:
        row = _first(
            self.client.request(
                "GET",
                "music_billing_customers",
                params={"app_user_id": f"eq.{app_user_id}", "select": "*", "limit": "1"},
            )
        )
        return self._customer(row)

    def customer_by_stripe_id(self, stripe_customer_id: str) -> CustomerRecord | None:
        row = _first(
            self.client.request(
                "GET",
                "music_billing_customers",
                params={
                    "stripe_customer_id": f"eq.{stripe_customer_id}",
                    "select": "*",
                    "limit": "1",
                },
            )
        )
        return self._customer(row)

    @staticmethod
    def _customer(row: Mapping[str, Any] | None) -> CustomerRecord | None:
        if row is None:
            return None
        return CustomerRecord(
            app_user_id=str(row.get("app_user_id") or ""),
            stripe_customer_id=str(row.get("stripe_customer_id") or ""),
            email=str(row.get("email") or ""),
        )

    def upsert_customer(self, customer: CustomerRecord) -> None:
        self.client.request("POST", "rpc/music_billing_attach_customer", json_body={
            "p_user_id": customer.app_user_id,
            "p_customer_id": customer.stripe_customer_id,
        })

        # A concurrent request may have inserted a different binding. Never
        # continue Checkout with a customer that did not win persistence.
        stored = self.customer_for_user(customer.app_user_id)
        if stored is None or stored.stripe_customer_id != customer.stripe_customer_id:
            raise BillingError("Customer ownership conflict")

    def reserve_checkout(self, user_id: str, price_id: str) -> Mapping[str, Any]:
        value = self.client.request("POST", "rpc/music_billing_reserve_checkout", json_body={
            "p_user_id": user_id, "p_price_id": price_id})
        if not isinstance(value, Mapping) or not value.get("token") or not value.get("expires_at"):
            raise BillingError("Invalid Checkout reservation")
        return value

    def claim_delivery(self, event: Mapping[str, Any], customer_id: str) -> str:
        fingerprint = event_fingerprint(event)
        value = self.client.request("POST", "rpc/music_billing_claim_delivery", json_body={
            "p_event_id": event["id"], "p_event_type": event["type"],
            "p_created": event["created"], "p_fingerprint": fingerprint,
            "p_customer_id": customer_id})
        if value == "busy":
            raise WebhookBusy("Billing reconciliation is already running")
        if value == "collision":
            raise BillingError("Webhook event identity conflict")
        if value == "":
            return ""
        from uuid import UUID
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError) as exc:
            raise BillingError("Invalid webhook lease response") from exc

    def complete_delivery(self, event_id: str, token: str, record: SubscriptionRecord,
                          entitlement: DerivedEntitlement) -> None:
        def serial(value: Any) -> Any:
            return value.isoformat() if isinstance(value, datetime) else value
        self.client.request("POST", "rpc/music_billing_complete_delivery", json_body={
            "p_event_id": event_id, "p_token": token,
            "p_record": {k: serial(v) for k, v in asdict(record).items()},
            "p_entitlement": {k: serial(v) for k, v in asdict(entitlement).items()},
        })

    def fail_delivery(self, event_id: str, token: str) -> None:
        self.client.request("POST", "rpc/music_billing_fail_delivery", json_body={
            "p_event_id": event_id, "p_token": token})

    def entitlement_for_user(self, app_user_id: str) -> DerivedEntitlement | None:
        row = _first(
            self.client.request(
                "GET",
                "music_billing_entitlements",
                params={"app_user_id": f"eq.{app_user_id}", "select": "*", "limit": "1"},
            )
        )
        return _derived(row)


def _derived(row: Mapping[str, Any] | None) -> DerivedEntitlement | None:
    if row is None:
        return None
    try:
        plan = Plan(str(row.get("plan") or "free"))
        status = SubscriptionStatus(str(row.get("status") or "authenticated_free"))
    except ValueError:
        return None
    end = _parse_datetime(row.get("current_period_end"))
    if plan is Plan.PRO and (end is None or end.tzinfo is None or end <= datetime.now(timezone.utc)):
        plan, status = Plan.FREE, SubscriptionStatus.EXPIRED
    return DerivedEntitlement(
        app_user_id=str(row.get("app_user_id") or ""),
        plan=plan,
        status=status,
        current_period_end=_parse_datetime(row.get("current_period_end")),
        source_subscription_id=str(row.get("source_subscription_id") or ""),
        source_event_id=str(row.get("source_event_id") or ""),
        source_event_created=int(row.get("source_event_created") or 0),
        reason=str(row.get("reason") or ""),
    )


class SupabaseEntitlementProvider:
    """Read-side provider constrained by the user's JWT and database RLS."""

    def __init__(self, config: BillingConfig, access_token: str):
        if not config.supabase_url or not config.supabase_anon_key or not access_token:
            raise BillingError("Trusted entitlement read configuration is incomplete")
        self.client = _RestClient(config.supabase_url, config.supabase_anon_key, access_token)

    def entitlement_for(self, subject: EntitlementSubject) -> Entitlement:
        if not subject.authenticated or not subject.user_id:
            return Entitlement(Plan.FREE, SubscriptionStatus.ANONYMOUS, "billing_database", subject)
        row = _first(
            self.client.request(
                "GET",
                "music_billing_entitlements",
                params={"app_user_id": f"eq.{subject.user_id}", "select": "*", "limit": "1"},
            )
        )
        derived = _derived(row)
        if derived is None or derived.app_user_id != subject.user_id:
            return Entitlement(
                Plan.FREE,
                SubscriptionStatus.AUTHENTICATED_FREE,
                "billing_database",
                subject,
            )
        return derived.as_product_entitlement()


__all__ = ("SupabaseBillingStore", "SupabaseEntitlementProvider")
