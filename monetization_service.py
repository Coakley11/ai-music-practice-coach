"""Small trusted ASGI boundary for Stripe Checkout and webhooks.

Run separately from Streamlit (for example with uvicorn). No route accepts a
client-supplied user id, price id, plan, or entitlement.
"""

from __future__ import annotations

from typing import Any, Mapping

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


class StripeHttpGateway:
    """Minimal server-only Stripe API client using form-encoded HTTPS calls."""

    def __init__(self, secret_key: str):
        if not secret_key:
            raise BillingUnavailable("Stripe secret key is not configured")
        self.secret_key = secret_key

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        response = requests.request(
            method,
            f"https://api.stripe.com/v1/{path.lstrip('/')}",
            auth=(self.secret_key, ""),
            data=dict(data or {}),
            timeout=15,
        )
        if not response.ok:
            raise BillingError(f"Stripe request failed ({response.status_code})")
        value = response.json()
        if not isinstance(value, Mapping):
            raise BillingError("Stripe returned an unexpected response")
        return value

    def create_customer(self, *, app_user_id: str, email: str) -> str:
        data: dict[str, Any] = {"metadata[app_user_id]": app_user_id}
        if email:
            data["email"] = email
        value = self._request("POST", "customers", data=data)
        return str(value.get("id") or "")

    def create_subscription_checkout(
        self,
        *,
        customer_id: str,
        price_id: str,
        app_user_id: str,
        success_url: str,
        cancel_url: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "checkout/sessions",
            data={
                "mode": "subscription",
                "customer": customer_id,
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": app_user_id,
                "metadata[app_user_id]": app_user_id,
                "subscription_data[metadata][app_user_id]": app_user_id,
            },
        )

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
    return config, SupabaseBillingStore(config), StripeHttpGateway(config.stripe_secret_key)


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
    except BillingError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Webhook processing failed"}, status_code=500)


app = Starlette(
    routes=[
        Route("/billing/health", health, methods=["GET"]),
        Route("/billing/checkout", checkout, methods=["POST"]),
        Route("/billing/webhooks/stripe", stripe_webhook, methods=["POST"]),
    ]
)


__all__ = ("StripeHttpGateway", "app", "verify_supabase_user")
