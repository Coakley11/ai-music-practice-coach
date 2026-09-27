"""Supabase persistence adapters for Monetization M2.

Server writes require the dedicated billing service-role environment variable.
The Streamlit app may only read the current user's derived entitlement through
their verified Supabase JWT and row-level security.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import requests

from monetization_billing import (
    BillingError,
    CustomerRecord,
    DerivedEntitlement,
    EventClaim,
    SubscriptionRecord,
)
from monetization_config import BillingConfig
from monetization_entitlements import (
    Entitlement,
    EntitlementSubject,
    Plan,
    SubscriptionStatus,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


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
                "billing_customers",
                params={"app_user_id": f"eq.{app_user_id}", "select": "*", "limit": "1"},
            )
        )
        return self._customer(row)

    def customer_by_stripe_id(self, stripe_customer_id: str) -> CustomerRecord | None:
        row = _first(
            self.client.request(
                "GET",
                "billing_customers",
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
        self.client.request(
            "POST",
            "billing_customers",
            json_body={
                "app_user_id": customer.app_user_id,
                "stripe_customer_id": customer.stripe_customer_id,
                "email": customer.email or None,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def claim_event(
        self,
        event_id: str,
        event_type: str,
        created: int,
        payload: Mapping[str, Any],
    ) -> EventClaim:
        value = self.client.request(
            "POST",
            "rpc/billing_claim_webhook_event",
            json_body={
                "p_event_id": event_id,
                "p_event_type": event_type,
                "p_event_created": created,
                "p_payload": dict(payload),
            },
        )
        if isinstance(value, list) and value:
            value = value[0]
        if isinstance(value, Mapping):
            value = value.get("claim") or value.get("billing_claim_webhook_event")
        return EventClaim(str(value).strip('"'))

    def apply_subscription_if_newer(self, subscription: SubscriptionRecord) -> bool:
        value = self.client.request(
            "POST",
            "rpc/billing_apply_subscription",
            json_body={
                "p_app_user_id": subscription.app_user_id,
                "p_customer_id": subscription.stripe_customer_id,
                "p_subscription_id": subscription.stripe_subscription_id,
                "p_product_id": subscription.stripe_product_id or None,
                "p_price_id": subscription.stripe_price_id or None,
                "p_status": subscription.provider_status,
                "p_current_period_end": _iso(subscription.current_period_end),
                "p_cancel_at_period_end": subscription.cancel_at_period_end,
                "p_trial_end": _iso(subscription.trial_end),
                "p_event_id": subscription.latest_event_id,
                "p_event_created": subscription.latest_event_created,
            },
        )
        return bool(value[0] if isinstance(value, list) and value else value)

    def save_entitlement(self, entitlement: DerivedEntitlement) -> None:
        self.client.request(
            "POST",
            "rpc/billing_save_entitlement",
            json_body={
                "p_app_user_id": entitlement.app_user_id,
                "p_plan": entitlement.plan.value,
                "p_status": entitlement.status.value,
                "p_current_period_end": _iso(entitlement.current_period_end),
                "p_subscription_id": entitlement.source_subscription_id,
                "p_event_id": entitlement.source_event_id,
                "p_event_created": entitlement.source_event_created,
                "p_reason": entitlement.reason,
            },
            prefer="return=minimal",
        )

    def mark_event_processed(self, event_id: str) -> None:
        self.client.request(
            "PATCH",
            "billing_webhook_events",
            params={"stripe_event_id": f"eq.{event_id}"},
            json_body={"processing_state": "processed", "last_error": None},
            prefer="return=minimal",
        )

    def mark_event_failed(self, event_id: str, error: str) -> None:
        self.client.request(
            "PATCH",
            "billing_webhook_events",
            params={"stripe_event_id": f"eq.{event_id}"},
            json_body={"processing_state": "failed", "last_error": error[:1000]},
            prefer="return=minimal",
        )

    def entitlement_for_user(self, app_user_id: str) -> DerivedEntitlement | None:
        row = _first(
            self.client.request(
                "GET",
                "billing_entitlements",
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
                "billing_entitlements",
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
