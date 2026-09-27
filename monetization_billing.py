"""Trusted subscription domain for Monetization M2.

The Streamlit application consumes derived entitlements only. Stripe objects are
handled behind this module's server-side checkout and webhook boundaries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol

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


class InvalidWebhookSignature(BillingError):
    pass


class EventClaim(str, Enum):
    NEW = "new"
    RETRY = "retry"
    DUPLICATE = "duplicate"


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

    def claim_event(
        self,
        event_id: str,
        event_type: str,
        created: int,
        payload: Mapping[str, Any],
    ) -> EventClaim: ...

    def apply_subscription_if_newer(self, subscription: SubscriptionRecord) -> bool: ...

    def save_entitlement(self, entitlement: DerivedEntitlement) -> None: ...

    def mark_event_processed(self, event_id: str) -> None: ...

    def mark_event_failed(self, event_id: str, error: str) -> None: ...

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
    ) -> Mapping[str, Any]: ...

    def retrieve_subscription(self, subscription_id: str) -> Mapping[str, Any]: ...


class InMemoryBillingStore:
    """Deterministic store used by tests; mirrors durable-store ordering rules."""

    def __init__(self) -> None:
        self.customers_by_user: dict[str, CustomerRecord] = {}
        self.customers_by_stripe: dict[str, CustomerRecord] = {}
        self.subscriptions: dict[str, SubscriptionRecord] = {}
        self.entitlements: dict[str, DerivedEntitlement] = {}
        self.events: dict[str, dict[str, Any]] = {}

    def customer_for_user(self, app_user_id: str) -> CustomerRecord | None:
        return self.customers_by_user.get(app_user_id)

    def customer_by_stripe_id(self, stripe_customer_id: str) -> CustomerRecord | None:
        return self.customers_by_stripe.get(stripe_customer_id)

    def upsert_customer(self, customer: CustomerRecord) -> None:
        prior = self.customers_by_user.get(customer.app_user_id)
        if prior and prior.stripe_customer_id != customer.stripe_customer_id:
            raise BillingError("A user may not be rebound to a different Stripe customer")
        self.customers_by_user[customer.app_user_id] = customer
        self.customers_by_stripe[customer.stripe_customer_id] = customer

    def claim_event(
        self,
        event_id: str,
        event_type: str,
        created: int,
        payload: Mapping[str, Any],
    ) -> EventClaim:
        prior = self.events.get(event_id)
        if prior is not None:
            return EventClaim.DUPLICATE if prior["state"] == "processed" else EventClaim.RETRY
        self.events[event_id] = {
            "type": event_type,
            "created": created,
            "payload": dict(payload),
            "state": "processing",
            "error": "",
        }
        return EventClaim.NEW

    def apply_subscription_if_newer(self, subscription: SubscriptionRecord) -> bool:
        prior = self.subscriptions.get(subscription.stripe_subscription_id)
        if prior and prior.latest_event_created > subscription.latest_event_created:
            return False
        if (
            prior
            and prior.latest_event_created == subscription.latest_event_created
            and prior.latest_event_id >= subscription.latest_event_id
        ):
            return False
        self.subscriptions[subscription.stripe_subscription_id] = subscription
        return True

    def save_entitlement(self, entitlement: DerivedEntitlement) -> None:
        prior = self.entitlements.get(entitlement.app_user_id)
        if prior and prior.source_event_created > entitlement.source_event_created:
            return
        self.entitlements[entitlement.app_user_id] = entitlement

    def mark_event_processed(self, event_id: str) -> None:
        self.events[event_id]["state"] = "processed"
        self.events[event_id]["error"] = ""

    def mark_event_failed(self, event_id: str, error: str) -> None:
        self.events[event_id]["state"] = "failed"
        self.events[event_id]["error"] = error[:1000]

    def entitlement_for_user(self, app_user_id: str) -> DerivedEntitlement | None:
        return self.entitlements.get(app_user_id)


class CheckoutService:
    """Create subscription checkout using only verified identity and trusted prices."""

    def __init__(self, config: BillingConfig, store: BillingStore, stripe: StripeGateway):
        self.config = config
        self.store = store
        self.stripe = stripe

    def create(self, user: VerifiedUser, *, interval: str) -> Mapping[str, Any]:
        if not user.valid:
            raise AuthenticationRequired("A verified account is required for checkout")
        if not self.config.checkout_enabled:
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
            self.store.upsert_customer(customer)
        base = self.config.public_base_url
        return self.stripe.create_subscription_checkout(
            customer_id=customer.stripe_customer_id,
            price_id=price_id,
            app_user_id=user.user_id,
            success_url=f"{base}?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}?billing=cancelled",
        )


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


def _subscription_price(subscription: Mapping[str, Any]) -> tuple[str, str]:
    items = subscription.get("items") or {}
    data = items.get("data") if isinstance(items, Mapping) else []
    first = data[0] if isinstance(data, list) and data else {}
    price = first.get("price") if isinstance(first, Mapping) else {}
    if not isinstance(price, Mapping):
        return "", ""
    product = price.get("product")
    return _object_id(product), _object_id(price)


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
        created = int(event.get("created") or 0)
        if not event_id or not event_type or created <= 0:
            raise BillingError("Malformed Stripe event envelope")
        claim = self.store.claim_event(event_id, event_type, created, event)
        if claim is EventClaim.DUPLICATE:
            return "duplicate"
        try:
            if event_type not in SUPPORTED_WEBHOOK_EVENTS:
                self.store.mark_event_processed(event_id)
                return "ignored"
            subscription = self._subscription_from_event(event)
            if subscription is None:
                self.store.mark_event_processed(event_id)
                return "ignored"
            record = self._record(subscription, event_id=event_id, created=created)
            if self.store.apply_subscription_if_newer(record):
                self.store.save_entitlement(
                    derive_entitlement(record, known_price_ids=self.config.known_price_ids)
                )
            self.store.mark_event_processed(event_id)
            return "processed"
        except Exception as exc:
            self.store.mark_event_failed(event_id, str(exc))
            raise

    def _subscription_from_event(self, event: Mapping[str, Any]) -> Mapping[str, Any] | None:
        event_type = str(event.get("type") or "")
        data = event.get("data") or {}
        obj = data.get("object") if isinstance(data, Mapping) else {}
        if not isinstance(obj, Mapping):
            return None
        if event_type.startswith("customer.subscription."):
            return obj
        if event_type == "checkout.session.completed":
            subscription_id = _object_id(obj.get("subscription"))
        else:
            subscription_id = _object_id(obj.get("subscription"))
            if not subscription_id:
                lines = obj.get("lines") or {}
                rows = lines.get("data") if isinstance(lines, Mapping) else []
                first = rows[0] if isinstance(rows, list) and rows else {}
                subscription_id = _object_id(
                    first.get("subscription") if isinstance(first, Mapping) else ""
                )
        return self.stripe.retrieve_subscription(subscription_id) if subscription_id else None

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
        customer = self.store.customer_by_stripe_id(customer_id)
        if customer is not None:
            if user_id and user_id != customer.app_user_id:
                raise BillingError("Subscription metadata conflicts with customer ownership")
            user_id = customer.app_user_id
        if not user_id or not customer_id or not subscription_id:
            raise BillingError("Subscription cannot be bound to a verified application user")
        if customer is None:
            self.store.upsert_customer(CustomerRecord(user_id, customer_id))
        product_id, price_id = _subscription_price(subscription)
        return SubscriptionRecord(
            app_user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_product_id=product_id,
            stripe_price_id=price_id,
            provider_status=str(subscription.get("status") or "").strip().lower(),
            current_period_end=_unix_datetime(subscription.get("current_period_end")),
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
    "EventClaim",
    "InMemoryBillingStore",
    "InvalidWebhookSignature",
    "StripeGateway",
    "SubscriptionRecord",
    "SUPPORTED_WEBHOOK_EVENTS",
    "VerifiedUser",
    "WebhookProcessor",
    "derive_entitlement",
    "parse_verified_event",
    "verify_stripe_signature",
)
