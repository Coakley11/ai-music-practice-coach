"""Small trusted ASGI boundary for Stripe Checkout and webhooks.

Run separately from Streamlit (for example with uvicorn). No route accepts a
client-supplied user id, price id, plan, or entitlement.
"""

from __future__ import annotations

from typing import Any, Mapping
import hashlib

import requests
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from monetization_billing import (
    AuthenticationRequired,
    BillingError,
    BillingUnavailable,
    CheckoutService,
    InvalidWebhookSignature,
    VerifiedUser,
    WebhookProcessor,
    parse_verified_event,
)
from monetization_config import BillingConfig
from monetization_supabase import SupabaseBillingStore


STRIPE_API_VERSION = "2026-10-28.endive"


class StripeHttpGateway:
    """Minimal server-only Stripe API client using form-encoded HTTPS calls."""

    def __init__(self, secret_key: str, portal_configuration_id: str = ""):
        if not secret_key.startswith("sk_test_"):
            raise BillingUnavailable("Only Stripe test credentials are supported")
        self.secret_key = secret_key
        self.portal_configuration_id = portal_configuration_id

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: Mapping[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> Mapping[str, Any]:
        headers = {"Stripe-Version": STRIPE_API_VERSION}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = requests.request(
            method,
            f"https://api.stripe.com/v1/{path.lstrip('/')}",
            auth=(self.secret_key, ""),
            data=dict(data or {}) if method != "GET" else None,
            params=dict(data or {}) if method == "GET" else None,
            headers=headers,
            timeout=15,
        )
        if not response.ok:
            raise BillingError(f"Stripe request failed ({response.status_code})")
        value = response.json()
        if not isinstance(value, Mapping):
            raise BillingError("Stripe returned an unexpected response")
        return value

    def create_customer(self, *, app_user_id: str, email: str) -> str:
        # Immutable request body: email changes cannot invalidate a replay key.
        value = self._request("POST", "customers", data={
            "metadata[app_user_id]": app_user_id, "metadata[app]": "music"},
            idempotency_key="music-customer-v1-" + hashlib.sha256(app_user_id.encode()).hexdigest())
        return str(value.get("id") or "")

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
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "checkout/sessions",
            data={
                "mode": "subscription",
                "expires_at": expires_at,
                "metadata[app]": "music",
                "subscription_data[metadata][app]": "music",
                "customer": customer_id,
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": app_user_id,
                "metadata[app_user_id]": app_user_id,
                "subscription_data[metadata][app_user_id]": app_user_id,
            },
            idempotency_key=idempotency_key,
        )

    def has_open_subscription(self, customer_id: str) -> bool:
        self._require_music_customer(customer_id)
        value = self._request("GET", "subscriptions", data={"customer": customer_id, "status": "all", "limit": 100})
        if value.get("has_more"):
            raise BillingUnavailable("Subscription pagination requires reconciliation")
        rows = value.get("data")
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) or row.get("customer") != customer_id for row in rows):
            raise BillingError("Invalid subscription list response")
        return any(row.get("status") not in {"canceled", "incomplete_expired"} for row in rows)

    def create_portal(self, *, customer_id: str, return_url: str) -> Mapping[str, Any]:
        if not self.portal_configuration_id.startswith("bpc_"):
            raise BillingUnavailable("Music Portal configuration is required")
        self._require_music_customer(customer_id)
        return self._request("POST", "billing_portal/sessions", data={
            "customer": customer_id, "return_url": return_url,
            "configuration": self.portal_configuration_id})

    def _require_music_customer(self, customer_id: str) -> None:
        if not customer_id.startswith("cus_"):
            raise BillingError("Invalid Music customer")
        customer = self._request("GET", f"customers/{customer_id}")
        metadata = customer.get("metadata")
        if (customer.get("id") != customer_id or customer.get("livemode") is not False
                or customer.get("deleted") or not isinstance(metadata, Mapping)
                or metadata.get("app") != "music" or not metadata.get("app_user_id")):
            raise BillingError("Stripe customer is not a Music test customer")

    def retrieve_subscription(self, subscription_id: str) -> Mapping[str, Any]:
        if not subscription_id:
            raise BillingError("Subscription id is required")
        return self._request("GET", f"subscriptions/{subscription_id}")


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def verify_supabase_user(config: BillingConfig, access_token: str) -> VerifiedUser:
    """Resolve auth.users identity at the trusted boundary from a Supabase JWT."""
    if not access_token or not config.supabase_url or not config.supabase_anon_key:
        raise AuthenticationRequired("A verified Supabase session is required")
    response = requests.get(
        f"{config.supabase_url}/auth/v1/user",
        headers={
            "apikey": config.supabase_anon_key,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    if not response.ok:
        raise AuthenticationRequired("Supabase session verification failed")
    value = response.json()
    if not isinstance(value, Mapping):
        raise AuthenticationRequired("Supabase user response is invalid")
    user = VerifiedUser(str(value.get("id") or "").strip(), str(value.get("email") or "").strip())
    if not user.valid:
        raise AuthenticationRequired("Supabase user id is missing")
    return user


def _dependencies() -> tuple[BillingConfig, SupabaseBillingStore, StripeHttpGateway]:
    config = BillingConfig.from_environ()
    return config, SupabaseBillingStore(config), StripeHttpGateway(config.stripe_secret_key, config.portal_configuration_id)


async def health(_: Request) -> JSONResponse:
    return JSONResponse(BillingConfig.from_environ().public_status())


async def checkout(request: Request) -> JSONResponse:
    try:
        config, store, stripe = _dependencies()
        user = verify_supabase_user(config, _bearer(request))
        body = await request.json()
        interval = str(body.get("interval") or "monthly") if isinstance(body, Mapping) else "monthly"
        session = CheckoutService(config, store, stripe).create(user, interval=interval)
        return JSONResponse(
            {"checkout_session_id": session.get("id"), "url": session.get("url")},
            status_code=201,
        )
    except AuthenticationRequired as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)
    except (BillingUnavailable, BillingError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception:
        return JSONResponse({"error": "Checkout could not be created"}, status_code=503)


async def portal(request: Request) -> JSONResponse:
    try:
        config, store, stripe = _dependencies()
        user = verify_supabase_user(config, _bearer(request))
        # Request bodies cannot choose customer, user or return URL.
        session = CheckoutService(config, store, stripe).portal(user)
        return JSONResponse(session, status_code=201, headers={"Cache-Control": "no-store"})
    except AuthenticationRequired:
        return JSONResponse({"error": "Sign in is required"}, status_code=401)
    except BillingUnavailable:
        return JSONResponse({"error": "Test billing is unavailable"}, status_code=503)
    except BillingError:
        return JSONResponse({"error": "No accessible billing account"}, status_code=403)
    except Exception:
        return JSONResponse({"error": "Portal session could not be created"}, status_code=503)


async def stripe_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()  # Must precede JSON parsing for Stripe HMAC verification.
    try:
        config, store, stripe = _dependencies()
        if not config.webhook_enabled:
            raise BillingUnavailable("Stripe webhook processing is not enabled")
        event = parse_verified_event(
            raw_body,
            request.headers.get("stripe-signature", ""),
            config.stripe_webhook_secret,
        )
        result = WebhookProcessor(config, store, stripe).process(event)
        return JSONResponse({"received": True, "result": result})
    except InvalidWebhookSignature as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except BillingUnavailable as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except BillingError:
        # Retry ownership/store conflicts rather than acknowledge lost work.
        return JSONResponse({"error": "Webhook reconciliation failed"}, status_code=503)
    except Exception:
        return JSONResponse({"error": "Webhook processing failed"}, status_code=500)


app = Starlette(
    routes=[
        Route("/billing/health", health, methods=["GET"]),
        Route("/billing/checkout", checkout, methods=["POST"]),
        Route("/billing/portal", portal, methods=["POST"]),
        Route("/billing/webhooks/stripe", stripe_webhook, methods=["POST"]),
    ]
)


__all__ = ("StripeHttpGateway", "app", "verify_supabase_user")
