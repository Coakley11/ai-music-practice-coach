"""Local-only staging startup guards; never use Suite configuration fallbacks."""
import base64
import json
from typing import Mapping

ISOLATED_SUPABASE_URL = "https://smpyutzfktjgpdibdbqb.supabase.co"


def validate_staging_environment(env: Mapping[str, str]) -> None:
    if env.get("MUSIC_BILLING_ROLLOUT") != "test" or env.get("MUSIC_STRIPE_MODE") != "test":
        raise RuntimeError("Music staging requires explicit test rollout and Stripe mode")
    if env.get("MUSIC_BILLING_SUPABASE_URL") != ISOLATED_SUPABASE_URL:
        raise RuntimeError("Music staging requires the explicit isolated Supabase URL")
    # Prevent shared app settings from accidentally being introduced into this service.
    if any(name.startswith("SUITE_") for name in env):
        raise RuntimeError("Suite configuration must not be attached to Music staging")
    for name, role in (("MUSIC_BILLING_SUPABASE_ANON_KEY", "anon"),
                       ("MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY", "service_role")):
        try:
            token = env.get(name, "")
            claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
            valid = claims.get("ref") == "smpyutzfktjgpdibdbqb" and claims.get("role") == role
        except Exception:
            valid = False
        if not valid:
            raise RuntimeError("Music staging Supabase key project/role mismatch (values suppressed)")
    key = env.get("STRIPE_SECRET_KEY", "")
    if key and not key.startswith("sk_test_"):
        raise RuntimeError("Music staging accepts only Stripe sandbox/test keys")
    # Missing Stripe settings are allowed for the first health-only bootstrap.
    # Existing BillingConfig keeps Checkout/webhooks disabled until configured.
