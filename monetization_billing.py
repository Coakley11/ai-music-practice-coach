"""Trusted test-mode subscription lifecycle and customer boundaries.

The Streamlit application consumes derived entitlements only. Stripe objects are
handled behind this module's server-side checkout and webhook boundaries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from monetization_config import BillingConfig
from monetization_entitlements import (
    Entitlement,
    EntitlementSubject,
    Plan,
    SubscriptionStatus,
)


class BillingError(RuntimeError):
    """Base class for safe billing-boundary failures."""


class AuthenticationRequired(BillingError):
    pass


class BillingUnavailable(BillingError):
    pass


class WebhookBusy(BillingUnavailable):
    pass


class InvalidWebhookSignature(BillingError):
    pass


@dataclass(frozen=True)
class VerifiedUser:
    """Identity returned by a trusted Supabase token verification call."""

    user_id: str
    email: str = ""

    @property
    def valid(self) -> bool:
        return bool(self.user_id.strip())


@dataclass(frozen=True)
class CustomerRecord:
    app_user_id: str
    stripe_customer_id: str
    email: str = ""


@dataclass(frozen=True)
class SubscriptionRecord:
    app_user_id: str
    stripe_customer_id: str
    stripe_subscription_id: str
    stripe_product_id: str
    stripe_price_id: str
    provider_status: str
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_end: datetime | None
    latest_event_id: str
    latest_event_created: int


@dataclass(frozen=True)
class DerivedEntitlement:
    app_user_id: str
    plan: Plan
    status: SubscriptionStatus
    current_period_end: datetime | None
    source_subscription_id: str
    source_event_id: str
    source_event_created: int
    reason: str

    def as_product_entitlement(self) -> Entitlement:
        return Entitlement(
            plan=self.plan,
            status=self.status,
            source="billing_database",
            subject=EntitlementSubject(self.app_user_id, authenticated=True),
            current_period_end=self.current_period_end,
        )


class BillingStore(Protocol):
    def customer_for_user(self, app_user_id: str) -> CustomerRecord | None: ...

    def customer_by_stripe_id(self, stripe_customer_id: str) -> CustomerRecord | None: ...

    def upsert_customer(self, customer: CustomerRecord) -> None: ...

    def reserve_checkout(self, user_id: str, price_id: str) -> Mapping[str, Any]: ...

    def claim_delivery(self, event: Mapping[str, Any], customer_id: str) -> str: ...

    def complete_delivery(self, event_id: str, token: str, record: SubscriptionRecord,
                          entitlement: DerivedEntitlement) -> None: ...

    def fail_delivery(self, event_id: str, token: str) -> None: ...

    def entitlement_for_user(self, app_user_id: str) -> DerivedEntitlement | None: ...


class StripeGateway(Protocol):
    def create_customer(self, *, app_user_id: str, email: str) -> str: ...

    def create_subscription_checkout(
        self,
        *,
        customer_id: str,
        price_id: str,
        app_user_id: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
        expires_at: int,
    ) -> Mapping[str, Any]: ...

    def has_open_subscription(self, customer_id: str) -> bool: ...

    def create_portal(self, *, customer_id: str, return_url: str) -> Mapping[str, Any]: ...

    def retrieve_subscription(self, subscription_id: str) -> Mapping[str, Any]: ...


def event_fingerprint(event: Mapping[str, Any]) -> str:
    """Hash immutable event identity, excluding delivery bookkeeping counters."""
    identity = {key: event.get(key) for key in
                ("id", "type", "created", "livemode", "account", "api_version", "data")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


class InMemoryBillingStore:
    """Deterministic store used by tests; mirrors durable-store ordering rules."""

    def __init__(self) -> None:
        self.customers_by_user: dict[str, CustomerRecord] = {}
        self.customers_by_stripe: dict[str, CustomerRecord] = {}
        self.subscriptions: dict[str, SubscriptionRecord] = {}
        self.entitlements: dict[str, DerivedEntitlement] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.projections: dict[str, DerivedEntitlement] = {}
        self.checkouts: dict[str, dict[str, Any]] = {}

    def customer_for_user(self, app_user_id: str) -> CustomerRecord | None:
        return self.customers_by_user.get(app_user_id)

    def customer_by_stripe_id(self, stripe_customer_id: str) -> CustomerRecord | None:
        return self.customers_by_stripe.get(stripe_customer_id)

    def upsert_customer(self, customer: CustomerRecord) -> None:
        if not customer.app_user_id.strip() or not customer.stripe_customer_id.strip():
            raise BillingError("Customer ownership requires nonempty identifiers")
        owner = self.customers_by_stripe.get(customer.stripe_customer_id)
        if owner and owner.app_user_id != customer.app_user_id:
            raise BillingError("Stripe customer already belongs to another user")
        prior = self.customers_by_user.get(customer.app_user_id)
        if prior and prior.stripe_customer_id != customer.stripe_customer_id:
            raise BillingError("A user may not be rebound to a different Stripe customer")
        self.customers_by_user[customer.app_user_id] = customer
        self.customers_by_stripe[customer.stripe_customer_id] = customer

    def reserve_checkout(self, user_id: str, price_id: str) -> Mapping[str, Any]:
        if not self.customer_for_user(user_id):
            raise BillingError("Missing customer mapping")
        if any(r.app_user_id == user_id and r.provider_status not in {"canceled", "incomplete_expired"}
               for r in self.subscriptions.values()):
            raise BillingError("Use subscription management for an existing subscription")
        prior = self.checkouts.get(user_id)
        if prior and prior["expires_at"] > time.time():
            if prior["price_id"] != price_id:
                raise BillingUnavailable("Another Checkout is pending")
            return dict(prior)
        value = dict(token=str(uuid.uuid4()), expires_at=int(time.time()) + 3600, price_id=price_id)
        self.checkouts[user_id] = value
        return dict(value)

    def claim_delivery(self, event: Mapping[str, Any], customer_id: str) -> str:
        now = time.time()
        fingerprint = event_fingerprint(event)
        prior = self.events.get(event["id"])
        if prior and prior["fingerprint"] != fingerprint:
            raise BillingError("Webhook event identity conflict")
        if prior and prior["state"] == "processed":
            return ""
        for row in self.events.values():
            if row["customer"] == customer_id and row["state"] == "processing" and row["expires"] > now:
                raise WebhookBusy("Billing reconciliation is already running")
        token = str(uuid.uuid4())
        self.events[event["id"]] = dict(fingerprint=fingerprint, customer=customer_id,
            state="processing", token=token, expires=now + 300, created=event["created"])
        return token

    def _owned(self, event_id: str, token: str) -> dict[str, Any]:
        row = self.events[event_id]
        if row["state"] != "processing" or row["token"] != token or row["expires"] <= time.time():
            raise WebhookBusy("Webhook lease expired or ownership lost")
        return row

    def complete_delivery(self, event_id: str, token: str, record: SubscriptionRecord,
                          entitlement: DerivedEntitlement) -> None:
        row = self._owned(event_id, token)
        owner = self.customer_by_stripe_id(record.stripe_customer_id)
        if not owner or owner.app_user_id != record.app_user_id or row["customer"] != record.stripe_customer_id:
            raise BillingError("Customer ownership conflict")
        if record.latest_event_id != event_id or record.latest_event_created != row["created"]:
            raise BillingError("Event identity conflict")
        prior = self.subscriptions.get(record.stripe_subscription_id)
        if prior and (prior.app_user_id != record.app_user_id or prior.stripe_customer_id != record.stripe_customer_id):
            raise BillingError("Subscription ownership conflict")
        # Commit the snapshot and projection together. A user lease serializes
        # provider reads, so event timestamps and opaque IDs never order state.
        projections = self.projections | {record.stripe_subscription_id: entitlement}
        candidates = [e for e in projections.values() if e.app_user_id == record.app_user_id
                      and e.as_product_entitlement().grants_pro]
        chosen = max(candidates, key=lambda e: (e.current_period_end, e.source_subscription_id)) if candidates else entitlement
        self.subscriptions[record.stripe_subscription_id] = record
        self.projections = projections
        self.entitlements[record.app_user_id] = chosen
        row.update(state="processed", token="", expires=0)

    def fail_delivery(self, event_id: str, token: str) -> None:
        try:
            row = self._owned(event_id, token)
        except WebhookBusy:
            return
        row.update(state="failed", token="", expires=0)

    def entitlement_for_user(self, app_user_id: str) -> DerivedEntitlement | None:
        value = self.entitlements.get(app_user_id)
        if value and value.plan is Plan.PRO and not value.as_product_entitlement().grants_pro:
            return replace(value, plan=Plan.FREE, status=SubscriptionStatus.EXPIRED, reason="period_expired")
        return value


class CheckoutService:
    """Create subscription checkout using only verified identity and trusted prices."""

    def __init__(self, config: BillingConfig, store: BillingStore, stripe: StripeGateway):
        self.config = config
        self.store = store
        self.stripe = stripe

    def create(self, user: VerifiedUser, *, interval: str) -> Mapping[str, Any]:
        if not user.valid:
            raise AuthenticationRequired("A verified account is required for checkout")
        if not self.config.test_mode or not self.config.checkout_enabled:
            raise BillingUnavailable("Subscription checkout is not enabled")
        price_id = self.config.price_for_interval(interval)
        if not price_id or price_id not in self.config.known_price_ids:
            raise BillingError("Unknown subscription interval or price")
        customer = self.store.customer_for_user(user.user_id)
        if customer is None:
            customer = CustomerRecord(
                app_user_id=user.user_id,
                stripe_customer_id=self.stripe.create_customer(
                    app_user_id=user.user_id,
                    email=user.email,
                ),
                email=user.email,
            )
            if not customer.stripe_customer_id.strip():
                raise BillingError("Stripe customer creation failed")
            self.store.upsert_customer(customer)
        if customer.app_user_id != user.user_id or not customer.stripe_customer_id.strip():
            raise BillingError("Invalid customer ownership mapping")
        if self.stripe.has_open_subscription(customer.stripe_customer_id):
            raise BillingError("Use subscription management for an existing subscription")
        reservation = self.store.reserve_checkout(user.user_id, price_id)
        base = self.config.public_base_url
        return self.stripe.create_subscription_checkout(
            customer_id=customer.stripe_customer_id,
            price_id=price_id,
            app_user_id=user.user_id,
            success_url=f"{base}?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}?billing=cancelled",
            idempotency_key="music-checkout-v1-" + str(reservation["token"]),
            expires_at=int(reservation["expires_at"]),
        )

    def portal(self, user: VerifiedUser) -> Mapping[str, Any]:
        if not user.valid:
            raise AuthenticationRequired("A verified account is required")
        if not self.config.test_mode or not self.config.checkout_enabled:
            raise BillingUnavailable("Test billing is not enabled")
        customer = self.store.customer_for_user(user.user_id)
        if not customer or customer.app_user_id != user.user_id or not customer.stripe_customer_id.startswith("cus_"):
            raise BillingError("No valid billing customer exists")
        reverse = self.store.customer_by_stripe_id(customer.stripe_customer_id)
        if not reverse or reverse.app_user_id != user.user_id:
            raise BillingError("Customer ownership conflict")
        session = self.stripe.create_portal(customer_id=customer.stripe_customer_id,
                                            return_url=self.config.public_base_url)
        url = urlparse(str(session.get("url") or ""))
        if url.scheme != "https" or url.hostname != "billing.stripe.com":
            raise BillingError("Invalid portal session response")
        return {"url": session["url"]}


def verify_stripe_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    *,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Stripe's timestamped v1 HMAC against the untouched body bytes."""
    if not secret:
        raise InvalidWebhookSignature("Webhook secret is not configured")
    parts: dict[str, list[str]] = {}
    for item in str(signature_header or "").split(","):
        key, separator, value = item.partition("=")
        if separator:
            parts.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(parts.get("t", [""])[0])
    except ValueError as exc:
        raise InvalidWebhookSignature("Invalid signature timestamp") from exc
    current = int(time.time()) if now is None else int(now)
    if abs(current - timestamp) > tolerance_seconds:
        raise InvalidWebhookSignature("Webhook timestamp is outside the tolerance")
    signed = str(timestamp).encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in parts.get("v1", [])):
        raise InvalidWebhookSignature("Webhook signature mismatch")


def _unix_datetime(value: Any) -> datetime | None:
    try:
        stamp = int(value or 0)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc) if stamp > 0 else None


def _object_id(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(value.get("id") or "").strip()
    return str(value or "").strip()


def _subscription_terms(subscription: Mapping[str, Any], known_prices: frozenset[str]) -> tuple[str, str, datetime | None]:
    items = subscription.get("items") or {}
    if not isinstance(items, Mapping):
        raise BillingError("Malformed subscription items")
    rows = items.get("data", [])
    if items.get("has_more"):
        raise BillingError("Subscription items require pagination")
    for item in rows:
        if not isinstance(item, Mapping):
            raise BillingError("Malformed subscription item")
        price = item.get("price") or {}
        if isinstance(price, Mapping) and _object_id(price) in known_prices:
            end = _unix_datetime(item.get("current_period_end") or subscription.get("current_period_end"))
            if subscription.get("status") == "trialing":
                end = _unix_datetime(subscription.get("trial_end")) or end
            cancel_at = _unix_datetime(subscription.get("cancel_at"))
            if cancel_at and end:
                end = min(end, cancel_at)
            return _object_id(price.get("product")), _object_id(price), end
    return "", "", None


def derive_entitlement(
    subscription: SubscriptionRecord,
    *,
    known_price_ids: frozenset[str],
) -> DerivedEntitlement:
    raw = subscription.provider_status.strip().lower()
    known_price = bool(subscription.stripe_price_id in known_price_ids)
    plan = Plan.FREE
    status = SubscriptionStatus.AUTHENTICATED_FREE
    reason = "unknown_price"
    if known_price and raw == "trialing":
        plan, status, reason = Plan.PRO, SubscriptionStatus.TRIALING, "trialing"
    elif known_price and raw == "active" and subscription.cancel_at_period_end:
        plan, status, reason = (
            Plan.PRO,
            SubscriptionStatus.CANCELED_PERIOD_END,
            "active_until_period_end",
        )
    elif known_price and raw == "active":
        plan, status, reason = Plan.PRO, SubscriptionStatus.ACTIVE, "active"
    elif known_price and raw == "past_due":
        plan, status, reason = Plan.FREE, SubscriptionStatus.PAST_DUE, "past_due_fail_closed"
    elif known_price and raw in {
        "unpaid",
        "canceled",
        "incomplete",
        "incomplete_expired",
        "paused",
    }:
        plan, status, reason = Plan.FREE, SubscriptionStatus.EXPIRED, raw
    end = subscription.current_period_end
    if plan is Plan.PRO and (end is None or end.tzinfo is None or end <= datetime.now(timezone.utc)):
        plan, status, reason = Plan.FREE, SubscriptionStatus.EXPIRED, "period_expired"
    return DerivedEntitlement(
        app_user_id=subscription.app_user_id,
        plan=plan,
        status=status,
        current_period_end=subscription.current_period_end,
        source_subscription_id=subscription.stripe_subscription_id,
        source_event_id=subscription.latest_event_id,
        source_event_created=subscription.latest_event_created,
        reason=reason,
    )


SUPPORTED_WEBHOOK_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid",
        "invoice.payment_failed",
    }
)


class WebhookProcessor:
    """Persist, deduplicate, order, and derive entitlements from Stripe events."""

    def __init__(self, config: BillingConfig, store: BillingStore, stripe: StripeGateway):
        self.config = config
        self.store = store
        self.stripe = stripe

    def process(self, event: Mapping[str, Any]) -> str:
        event_id = str(event.get("id") or "").strip()
        event_type = str(event.get("type") or "").strip()
        try:
            created = int(event.get("created") or 0)
        except (TypeError, ValueError) as exc:
            raise BillingError("Malformed Stripe event") from exc
        if not event_id or not event_type or created <= 0 or event.get("livemode") is not False:
            raise BillingError("Malformed or non-test Stripe event")
        if not self.config.test_mode or not self.config.webhook_enabled:
            raise BillingUnavailable("Test webhooks are not enabled")
        if event_type not in SUPPORTED_WEBHOOK_EVENTS:
            return "ignored"
        obj = (event.get("data") or {}).get("object")
        if not isinstance(obj, Mapping):
            raise BillingError("Malformed Stripe object")
        app = (obj.get("metadata") or {}).get("app")
        if app and app != "music":
            return "ignored"  # Explicit foreign-app signed event; unknown untagged owners still retry.
        customer_id = _object_id(obj.get("customer"))
        owner = self.store.customer_by_stripe_id(customer_id)
        if not owner:
            raise BillingError("Stripe customer has no trusted owner")
        for claimed_user in (obj.get("client_reference_id"), (obj.get("metadata") or {}).get("app_user_id")):
            if claimed_user and claimed_user != owner.app_user_id:
                raise BillingError("Event metadata conflicts with customer ownership")
        if event_type.startswith("customer.subscription."):
            sub_id = _object_id(obj.get("id"))
        else:
            parent = obj.get("parent") or {}
            sub_id = _object_id(obj.get("subscription") or (parent.get("subscription_details") or {}).get("subscription"))
            if not sub_id:
                for line in (obj.get("lines") or {}).get("data", []):
                    sub_id = _object_id(line.get("subscription") or
                        ((line.get("parent") or {}).get("subscription_item_details") or {}).get("subscription"))
                    if sub_id:
                        break
        if not sub_id:
            if event_type.startswith("invoice."):
                return "ignored"  # One-off invoice has no subscription entitlement.
            raise BillingError("Subscription id is required")
        token = self.store.claim_delivery(event, customer_id)
        if not token:
            return "duplicate"
        try:
            # Fetch while holding the customer lease, including for old deliveries
            # and deletions. Stripe retains canceled subscription resources.
            subscription = self.stripe.retrieve_subscription(sub_id)
            if subscription.get("livemode") is not False or _object_id(subscription.get("id")) != sub_id:
                raise BillingError("Stripe subscription identity or mode mismatch")
            if _object_id(subscription.get("customer")) != customer_id:
                raise BillingError("Subscription customer ownership conflict")
            record = self._record(subscription, event_id=event_id, created=created)
            self.store.complete_delivery(event_id, token, record,
                derive_entitlement(record, known_price_ids=self.config.known_price_ids))
            return "processed"
        except Exception:
            self.store.fail_delivery(event_id, token)
            raise

    def _record(
        self,
        subscription: Mapping[str, Any],
        *,
        event_id: str,
        created: int,
    ) -> SubscriptionRecord:
        customer_id = _object_id(subscription.get("customer"))
        subscription_id = _object_id(subscription.get("id"))
        metadata = subscription.get("metadata") or {}
        user_id = str(metadata.get("app_user_id") or "").strip() if isinstance(metadata, Mapping) else ""
        if isinstance(metadata, Mapping) and metadata.get("app") not in (None, "", "music"):
            raise BillingError("Subscription belongs to another application")
        customer = self.store.customer_by_stripe_id(customer_id)
        if customer is not None:
            if user_id and user_id != customer.app_user_id:
                raise BillingError("Subscription metadata conflicts with customer ownership")
            user_id = customer.app_user_id
        if not user_id or not customer_id or not subscription_id:
            raise BillingError("Subscription cannot be bound to a verified application user")
        if customer is None:
            raise BillingError("Stripe customer has no trusted owner")
        product_id, price_id, period_end = _subscription_terms(subscription, self.config.known_price_ids)
        return SubscriptionRecord(
            app_user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_product_id=product_id,
            stripe_price_id=price_id,
            provider_status=str(subscription.get("status") or "").strip().lower(),
            current_period_end=period_end,
            cancel_at_period_end=bool(subscription.get("cancel_at_period_end")),
            trial_end=_unix_datetime(subscription.get("trial_end")),
            latest_event_id=event_id,
            latest_event_created=created,
        )


def parse_verified_event(raw_body: bytes, signature: str, secret: str) -> Mapping[str, Any]:
    verify_stripe_signature(raw_body, signature, secret)
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BillingError("Webhook body is not valid JSON") from exc
    if not isinstance(event, Mapping):
        raise BillingError("Webhook JSON must be an object")
    return event


__all__ = (
    "AuthenticationRequired",
    "BillingError",
    "BillingStore",
    "BillingUnavailable",
    "CheckoutService",
    "CustomerRecord",
    "DerivedEntitlement",
    "InMemoryBillingStore",
    "InvalidWebhookSignature",
    "StripeGateway",
    "SubscriptionRecord",
    "SUPPORTED_WEBHOOK_EVENTS",
    "VerifiedUser",
    "WebhookProcessor",
    "WebhookBusy",
    "derive_entitlement",
    "parse_verified_event",
    "verify_stripe_signature",
)
