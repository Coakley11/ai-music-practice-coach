"""Read-only Stripe inspection. Never creates/updates Stripe objects or payments."""
import argparse
import json
from pathlib import Path

import requests

API_ORIGIN = "https://api.stripe.com/v1"
API_VERSION = "2026-10-28.endive"
PRICE_ID = "price_1Ub8MiGSM5yahQursL7MlBcs"
FIELDS = {"STRIPE_SECRET_KEY", "STRIPE_PRO_MONTHLY_PRICE_ID", "MUSIC_STRIPE_PORTAL_CONFIGURATION_ID"}


def load_config(path):
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ValueError("Cannot read local Stripe JSON; contents suppressed") from None
    if not isinstance(config, dict) or set(config) != FIELDS or not all(isinstance(v, str) for v in config.values()):
        raise ValueError("Local Stripe configuration must contain exactly the three documented string fields")
    if not config["STRIPE_SECRET_KEY"].strip().startswith("sk_test_"):
        raise ValueError("Fill STRIPE_SECRET_KEY with the Music sandbox sk_test key; live/opaque keys rejected")
    if config["STRIPE_PRO_MONTHLY_PRICE_ID"] != PRICE_ID:
        raise ValueError("Price ID differs from the user-approved inspection target")
    return config


class StripeReadOnly:
    def __init__(self, key):
        if not key.startswith("sk_test_"):
            raise ValueError("Only Stripe test keys accepted")
        self.key = key

    def get(self, path, params=None):
        if path not in ("account", "prices/" + PRICE_ID, "billing_portal/configurations"):
            raise ValueError("Endpoint outside the read-only inspection allowlist")
        with requests.Session() as session:
            session.trust_env = False
            try:
                response = session.get(API_ORIGIN + "/" + path, params=params,
                    auth=(self.key, ""), headers={"Stripe-Version": API_VERSION},
                    timeout=20, allow_redirects=False)
            except requests.RequestException:
                raise RuntimeError("Stripe read-only connection failed; credentials/details suppressed") from None
        if response.status_code != 200:
            raise RuntimeError(f"Stripe read-only inspection failed (HTTP {response.status_code}); body suppressed")
        try:
            value = response.json()
        except ValueError:
            raise RuntimeError("Stripe response was not JSON; body suppressed") from None
        if not isinstance(value, dict):
            raise RuntimeError("Unexpected Stripe response type")
        return value


def inspect(client):
    account = client.get("account")
    price = client.get("prices/" + PRICE_ID, {"expand[]": "product"})
    recurring = price.get("recurring") or {}
    product = price.get("product")
    if (price.get("id") != PRICE_ID or price.get("livemode") is not False
            or price.get("active") is not True or price.get("type") != "recurring"
            or recurring.get("interval") != "month" or recurring.get("interval_count") != 1
            or not isinstance(product, dict) or product.get("livemode") is not False
            or product.get("active") is not True):
        raise RuntimeError("Price/product is not an active test-mode monthly recurring configuration")
    metadata_app = (product.get("metadata") or {}).get("app")
    if metadata_app not in (None, "", "music"):
        raise RuntimeError("Price product explicitly belongs to another application")
    music_identified = metadata_app == "music" or "music" in str(product.get("name", "")).lower()
    portals = []
    params = {"limit": 100}
    for _ in range(5):
        page = client.get("billing_portal/configurations", params)
        rows = page.get("data")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("Unexpected portal list response")
        for portal in rows:
            features = portal.get("features") or {}
            cancel = features.get("subscription_cancel") or {}
            portals.append({"id": portal.get("id"), "name": portal.get("name"),
                "active": portal.get("active"), "livemode": portal.get("livemode"),
                "is_default": portal.get("is_default"), "app": (portal.get("metadata") or {}).get("app"),
                "cancellation_enabled": cancel.get("enabled"), "cancellation_mode": cancel.get("mode"),
                "payment_method_update": (features.get("payment_method_update") or {}).get("enabled"),
                "invoice_history": (features.get("invoice_history") or {}).get("enabled"),
                "subscription_updates": (features.get("subscription_update") or {}).get("enabled")})
        if not page.get("has_more"):
            break
        if not rows or not rows[-1].get("id"):
            raise RuntimeError("Portal pagination incomplete; no configuration selected")
        params = {"limit": 100, "starting_after": rows[-1]["id"]}
    else:
        raise RuntimeError("Portal pagination limit reached; no configuration selected")
    candidates = [p for p in portals if p["active"] is True and p["livemode"] is False
                  and p["is_default"] is False and p["app"] == "music"
                  and str(p["id"]).startswith("bpc_")]
    return {"api_version": API_VERSION, "account_id": account.get("id"),
        "sandbox_display_name_verified": False,
        "price": {k: price.get(k) for k in ("id", "active", "livemode", "currency", "unit_amount", "tax_behavior")},
        "recurring": {k: recurring.get(k) for k in ("interval", "interval_count", "usage_type")},
        "product": {"id": product.get("id"), "name": product.get("name"), "app": metadata_app,
                    "music_identified": music_identified},
        "portal_configurations": portals,
        "unique_music_portal_id": candidates[0]["id"] if len(candidates) == 1 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    report = inspect(StripeReadOnly(config["STRIPE_SECRET_KEY"].strip()))
    print(json.dumps(report, indent=2))  # Only allowlisted non-secret configuration fields.


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
