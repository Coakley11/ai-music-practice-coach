from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from monetization_billing import (
    AuthenticationRequired,
    CheckoutService,
    CustomerRecord,
    InMemoryBillingStore,
    InvalidWebhookSignature,
    VerifiedUser,
    WebhookProcessor,
    verify_stripe_signature,
)
from monetization_config import BillingConfig, BillingRolloutMode
from monetization_entitlements import (
    DEV_CONTROLS_ENV,
    DEV_RUNTIME_ENV,
    DEV_SESSION_PLAN_KEY,
    Feature,
    Plan,
    SubscriptionStatus,
    access_decision,
)
from monetization_service import verify_supabase_user


def _config(*, known_price: str = "price_pro") -> BillingConfig:
    return BillingConfig(
        rollout=BillingRolloutMode.TEST,
        stripe_mode="test",
        stripe_secret_key="sk_test_placeholder",
        stripe_webhook_secret="whsec_placeholder",
        monthly_price_id=known_price,
        annual_price_id="price_pro_annual",
        public_base_url="https://music.example.test",
        billing_service_url="https://billing.example.test",
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role-placeholder",
        supabase_anon_key="anon-placeholder",
    )


class FakeStripe:
    def __init__(self) -> None:
        self.subscriptions: dict[str, Mapping[str, Any]] = {}
        self.checkout_calls: list[dict[str, Any]] = []

    def create_customer(self, *, app_user_id: str, email: str) -> str:
        return f"cus_{app_user_id}"

    def create_subscription_checkout(self, **kwargs: Any) -> Mapping[str, Any]:
        self.checkout_calls.append(dict(kwargs))
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/session"}

    def retrieve_subscription(self, subscription_id: str) -> Mapping[str, Any]:
        return self.subscriptions[subscription_id]


def _subscription(
    *,
    status: str,
    price: str = "price_pro",
    cancel_at_period_end: bool = False,
    user_id: str = "user-1",
) -> dict[str, Any]:
    return {
        "id": "sub_1",
        "customer": "cus_1",
        "status": status,
        "current_period_end": 1_900_000_000,
        "cancel_at_period_end": cancel_at_period_end,
        "trial_end": 1_800_000_000 if status == "trialing" else None,
        "metadata": {"app_user_id": user_id},
        "items": {"data": [{"price": {"id": price, "product": "prod_pro"}}]},
    }


def _event(subscription: Mapping[str, Any], *, event_id: str, created: int) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "created": created,
        "data": {"object": dict(subscription)},
    }


def test_checkout_requires_verified_authenticated_user() -> None:
    service = CheckoutService(_config(), InMemoryBillingStore(), FakeStripe())

    with pytest.raises(AuthenticationRequired):
        service.create(VerifiedUser(""), interval="monthly")


def test_server_auth_boundary_uses_verified_supabase_user(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        ok = True

        @staticmethod
        def json() -> Mapping[str, Any]:
            return {"id": "verified-user", "email": "verified@example.test"}

    def fake_get(url: str, **kwargs: Any) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("monetization_service.requests.get", fake_get)

    user = verify_supabase_user(_config(), "signed-user-jwt")

    assert user.user_id == "verified-user"
    assert captured["headers"]["Authorization"] == "Bearer signed-user-jwt"
    assert captured["url"].endswith("/auth/v1/user")


def test_live_rollout_rejects_test_secret() -> None:
    values = _config().__dict__ | {
        "rollout": BillingRolloutMode.LIVE,
        "stripe_mode": "live",
        "stripe_secret_key": "sk_test_not_live",
    }

    config = BillingConfig(**values)
    assert not config.checkout_enabled
    assert not config.enforcement_enabled


def test_checkout_uses_trusted_price_and_does_not_grant_entitlement() -> None:
    store = InMemoryBillingStore()
    stripe = FakeStripe()
    service = CheckoutService(_config(), store, stripe)

    result = service.create(VerifiedUser("user-1", "a@example.test"), interval="monthly")

    assert result["id"] == "cs_test_1"
    assert stripe.checkout_calls[0]["price_id"] == "price_pro"
    assert stripe.checkout_calls[0]["app_user_id"] == "user-1"
    assert store.entitlement_for_user("user-1") is None


@pytest.mark.parametrize(
    "provider_status,cancel_at_period_end,plan,status",
    [
        ("active", False, Plan.PRO, SubscriptionStatus.ACTIVE),
        ("active", True, Plan.PRO, SubscriptionStatus.CANCELED_PERIOD_END),
        ("trialing", False, Plan.PRO, SubscriptionStatus.TRIALING),
        ("past_due", False, Plan.FREE, SubscriptionStatus.PAST_DUE),
        ("unpaid", False, Plan.FREE, SubscriptionStatus.EXPIRED),
        ("canceled", False, Plan.FREE, SubscriptionStatus.EXPIRED),
        ("incomplete_expired", False, Plan.FREE, SubscriptionStatus.EXPIRED),
    ],
)
def test_subscription_lifecycle_mapping(
    provider_status: str,
    cancel_at_period_end: bool,
    plan: Plan,
    status: SubscriptionStatus,
) -> None:
    store = InMemoryBillingStore()
    processor = WebhookProcessor(_config(), store, FakeStripe())

    result = processor.process(
        _event(
            _subscription(status=provider_status, cancel_at_period_end=cancel_at_period_end),
            event_id=f"evt_{provider_status}_{cancel_at_period_end}",
            created=100,
        )
    )

    assert result == "processed"
    entitlement = store.entitlement_for_user("user-1")
    assert entitlement is not None
    assert entitlement.plan is plan
    assert entitlement.status is status


def test_unknown_price_fails_closed() -> None:
    store = InMemoryBillingStore()
    processor = WebhookProcessor(_config(), store, FakeStripe())

    processor.process(
        _event(_subscription(status="active", price="price_attacker"), event_id="evt_unknown", created=100)
    )

    entitlement = store.entitlement_for_user("user-1")
    assert entitlement is not None
    assert entitlement.plan is Plan.FREE
    assert entitlement.reason == "unknown_price"


def test_duplicate_event_is_idempotent() -> None:
    store = InMemoryBillingStore()
    processor = WebhookProcessor(_config(), store, FakeStripe())
    event = _event(_subscription(status="active"), event_id="evt_same", created=100)

    assert processor.process(event) == "processed"
    assert processor.process(event) == "duplicate"
    assert len(store.events) == 1


def test_out_of_order_event_cannot_restore_old_entitlement() -> None:
    store = InMemoryBillingStore()
    processor = WebhookProcessor(_config(), store, FakeStripe())

    processor.process(_event(_subscription(status="canceled"), event_id="evt_new", created=200))
    processor.process(_event(_subscription(status="active"), event_id="evt_old", created=100))

    entitlement = store.entitlement_for_user("user-1")
    assert entitlement is not None
    assert entitlement.status is SubscriptionStatus.EXPIRED
    assert entitlement.source_event_id == "evt_new"


def test_customer_ownership_conflict_fails_without_rebinding() -> None:
    store = InMemoryBillingStore()
    store.upsert_customer(CustomerRecord("real-user", "cus_1"))
    processor = WebhookProcessor(_config(), store, FakeStripe())

    with pytest.raises(Exception, match="conflicts"):
        processor.process(
            _event(_subscription(status="active", user_id="attacker"), event_id="evt_conflict", created=100)
        )
    assert store.customer_by_stripe_id("cus_1").app_user_id == "real-user"  # type: ignore[union-attr]
    assert store.entitlement_for_user("attacker") is None


def test_stripe_signature_requires_raw_body_hmac_and_fresh_timestamp() -> None:
    body = json.dumps({"id": "evt_1"}, separators=(",", ":")).encode()
    timestamp = 1_800_000_000
    digest = hmac.new(
        b"whsec_test",
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    verify_stripe_signature(body, f"t={timestamp},v1={digest}", "whsec_test", now=timestamp)
    with pytest.raises(InvalidWebhookSignature):
        verify_stripe_signature(body + b" ", f"t={timestamp},v1={digest}", "whsec_test", now=timestamp)


def test_rollout_off_preserves_existing_composition_access() -> None:
    decision = access_decision(Feature.COMPOSITION_STUDIO, session_state={}, environ={})

    assert decision.allowed
    assert decision.reason == "billing_rollout_disabled"


def test_preview_enforces_free_composition_lock() -> None:
    decision = access_decision(
        Feature.COMPOSITION_STUDIO,
        session_state={},
        environ={"MUSIC_BILLING_ROLLOUT": "preview"},
    )

    assert not decision.allowed
    assert decision.reason == "upgrade_required"


def test_local_dev_free_still_exercises_paywall_when_rollout_is_off() -> None:
    decision = access_decision(
        Feature.COMPOSITION_STUDIO,
        session_state={DEV_SESSION_PLAN_KEY: "free"},
        environ={DEV_CONTROLS_ENV: "1", DEV_RUNTIME_ENV: "test"},
    )

    assert not decision.allowed
