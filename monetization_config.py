"""Server-owned configuration and rollout policy for Monetization M2."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class BillingRolloutMode(str, Enum):
    """Commercial rollout stages.

    ``off`` is deliberately the default and leaves premium workspaces open.  A
    deployment must explicitly opt into enforcement.
    """

    OFF = "off"
    PREVIEW = "preview"
    TEST = "test"
    LIVE = "live"


ROLLOUT_ENV = "MUSIC_BILLING_ROLLOUT"
STRIPE_MODE_ENV = "MUSIC_STRIPE_MODE"
STRIPE_SECRET_KEY_ENV = "STRIPE_SECRET_KEY"
STRIPE_WEBHOOK_SECRET_ENV = "STRIPE_WEBHOOK_SECRET"
STRIPE_MONTHLY_PRICE_ENV = "STRIPE_PRO_MONTHLY_PRICE_ID"
STRIPE_ANNUAL_PRICE_ENV = "STRIPE_PRO_ANNUAL_PRICE_ID"
PUBLIC_BASE_URL_ENV = "MUSIC_PUBLIC_BASE_URL"
BILLING_SERVICE_URL_ENV = "MUSIC_BILLING_SERVICE_URL"
SUPABASE_URL_ENV = "MUSIC_BILLING_SUPABASE_URL"
SUPABASE_SERVICE_KEY_ENV = "MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_ANON_KEY_ENV = "MUSIC_BILLING_SUPABASE_ANON_KEY"


def _clean(value: object) -> str:
    return str(value or "").strip()


def rollout_mode(environ: Mapping[str, str] | None = None) -> BillingRolloutMode:
    env = os.environ if environ is None else environ
    raw = _clean(env.get(ROLLOUT_ENV)).lower() or BillingRolloutMode.OFF.value
    try:
        return BillingRolloutMode(raw)
    except ValueError:
        return BillingRolloutMode.OFF


def billing_enforcement_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return BillingConfig.from_environ(environ).enforcement_enabled


@dataclass(frozen=True)
class BillingConfig:
    rollout: BillingRolloutMode
    stripe_mode: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    monthly_price_id: str
    annual_price_id: str
    public_base_url: str
    billing_service_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str

    @classmethod
    def from_environ(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "BillingConfig":
        env = os.environ if environ is None else environ
        return cls(
            rollout=rollout_mode(env),
            stripe_mode=_clean(env.get(STRIPE_MODE_ENV)).lower() or "test",
            stripe_secret_key=_clean(env.get(STRIPE_SECRET_KEY_ENV)),
            stripe_webhook_secret=_clean(env.get(STRIPE_WEBHOOK_SECRET_ENV)),
            monthly_price_id=_clean(env.get(STRIPE_MONTHLY_PRICE_ENV)),
            annual_price_id=_clean(env.get(STRIPE_ANNUAL_PRICE_ENV)),
            public_base_url=_clean(env.get(PUBLIC_BASE_URL_ENV)).rstrip("/"),
            billing_service_url=_clean(env.get(BILLING_SERVICE_URL_ENV)).rstrip("/"),
            supabase_url=_clean(
                env.get(SUPABASE_URL_ENV) or env.get("SUITE_SUPABASE_URL")
            ).rstrip("/"),
            supabase_service_role_key=_clean(env.get(SUPABASE_SERVICE_KEY_ENV)),
            supabase_anon_key=_clean(
                env.get(SUPABASE_ANON_KEY_ENV) or env.get("SUITE_SUPABASE_ANON_KEY")
            ),
        )

    @property
    def enforcement_enabled(self) -> bool:
        if self.rollout is BillingRolloutMode.OFF:
            return False
        # Preview/test are explicit non-production validation modes. Live must
        # not create a dead-end paywall unless both trusted boundaries are ready.
        if self.rollout is BillingRolloutMode.LIVE:
            return self.checkout_enabled and self.webhook_enabled
        return True

    @property
    def test_mode(self) -> bool:
        return self.rollout is BillingRolloutMode.TEST and self.stripe_mode == "test"

    @property
    def live_mode(self) -> bool:
        return self.rollout is BillingRolloutMode.LIVE and self.stripe_mode == "live"

    @property
    def known_price_ids(self) -> frozenset[str]:
        return frozenset(
            price for price in (self.monthly_price_id, self.annual_price_id) if price
        )

    @property
    def credentials_match_mode(self) -> bool:
        if self.test_mode:
            return self.stripe_secret_key.startswith("sk_test_")
        if self.live_mode:
            return self.stripe_secret_key.startswith("sk_live_")
        return False

    @property
    def checkout_enabled(self) -> bool:
        if not (self.test_mode or self.live_mode):
            return False
        return self.credentials_match_mode and bool(self.known_price_ids) and all(
            (
                self.stripe_secret_key,
                self.public_base_url,
                self.supabase_url,
                self.supabase_service_role_key,
                self.supabase_anon_key,
            )
        )

    @property
    def webhook_enabled(self) -> bool:
        return (
            (self.test_mode or self.live_mode)
            and self.credentials_match_mode
            and self.stripe_webhook_secret.startswith("whsec_")
            and bool(self.known_price_ids)
            and bool(self.supabase_url)
            and bool(self.supabase_service_role_key)
        )

    def price_for_interval(self, interval: str) -> str:
        value = _clean(interval).lower()
        if value == "monthly":
            return self.monthly_price_id
        if value == "annual":
            return self.annual_price_id
        return ""

    def public_status(self) -> dict[str, object]:
        """Safe diagnostics without secret or token values."""
        return {
            "rollout": self.rollout.value,
            "stripe_mode": self.stripe_mode,
            "enforcement_enabled": self.enforcement_enabled,
            "checkout_enabled": self.checkout_enabled,
            "webhook_enabled": self.webhook_enabled,
            "credentials_match_mode": self.credentials_match_mode,
            "monthly_price_configured": bool(self.monthly_price_id),
            "annual_price_configured": bool(self.annual_price_id),
            "public_base_url_configured": bool(self.public_base_url),
            "billing_service_url_configured": bool(self.billing_service_url),
            "supabase_configured": bool(
                self.supabase_url and self.supabase_service_role_key
            ),
        }


__all__ = (
    "BILLING_SERVICE_URL_ENV",
    "BillingConfig",
    "BillingRolloutMode",
    "PUBLIC_BASE_URL_ENV",
    "ROLLOUT_ENV",
    "STRIPE_ANNUAL_PRICE_ENV",
    "STRIPE_MODE_ENV",
    "STRIPE_MONTHLY_PRICE_ENV",
    "STRIPE_SECRET_KEY_ENV",
    "STRIPE_WEBHOOK_SECRET_ENV",
    "SUPABASE_ANON_KEY_ENV",
    "SUPABASE_SERVICE_KEY_ENV",
    "SUPABASE_URL_ENV",
    "billing_enforcement_enabled",
    "rollout_mode",
)
