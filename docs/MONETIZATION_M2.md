# Monetization M2: trusted subscriptions

M2 keeps the M1 product API (`access_decision` / `can_use`) and moves Stripe
state behind a trusted service and database boundary. The checked-in defaults do
not enable billing or lock existing users out of Composition Studio.

## Trust boundaries

- Paid identity is `auth.users.id` from a Supabase access token verified at the
  server. Workspace IDs, external/profile IDs, browser flags, query parameters,
  and local JSON are never billing identity.
- Streamlit receives only a user-scoped derived entitlement through Supabase RLS.
  It has no Stripe secret and cannot write billing tables.
- `monetization_service:app` is a separate Starlette ASGI service. It owns the
  Stripe secret, webhook secret, and Supabase service-role key.
- Checkout accepts only `monthly` or `annual`. The server maps those values to
  configured price IDs. It never accepts a price, plan, entitlement, customer,
  or application user ID from the client.
- Checkout success/cancel redirects are navigation only. Access changes only
  after a signature-verified webhook has been durably processed.

## Persistence

Apply `supabase/migrations/20260927_monetization_m2.sql` through the normal
Supabase migration pipeline. It creates:

| Record | Purpose |
| --- | --- |
| `billing_customers` | One verified application user to Stripe customer mapping |
| `billing_subscriptions` | Provider subscription/product/price/status, period and cancellation state, plus latest applied event ordering |
| `billing_webhook_events` | Durable raw event, unique Stripe event ID, processing state, retry count and error |
| `billing_entitlements` | Provider-independent application plan/status consumed by M1 |

All write tables deny `anon` and `authenticated`. The only client-visible table
is `billing_entitlements`, with a select policy requiring
`app_user_id = auth.uid()`. The three mutation RPCs are service-role only.

## Webhook processing

`POST /billing/webhooks/stripe` reads the untouched request bytes, verifies the
Stripe timestamped HMAC, and only then parses JSON. The event record and payload
are inserted before derivation. A unique event ID makes completed duplicates a
no-op and lets failed/incomplete attempts retry. Subscription and entitlement
updates compare `(event_created, event_id)`, so an older delivery cannot replace
newer state. Invoice events retrieve the current subscription rather than
assuming delivery order.

Handled events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Unknown event types are durably recorded and acknowledged without affecting
entitlement. Unknown/unconfigured price IDs always derive Free.

## Lifecycle policy

| Stripe state | Application state | Pro access |
| --- | --- | --- |
| `trialing` | `trialing` | Yes |
| `active` | `active` | Yes |
| `active` + cancel at period end | `canceled_period_end` through current period end | Yes |
| `past_due` | `past_due` | No (conservative M2 policy) |
| `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `paused` | `expired` | No |
| Unknown price | authenticated Free | No |

The `past_due` choice is intentionally conservative and can be changed later in
the derivation policy without exposing Stripe concepts to product pages.

## Rollout and environment

`MUSIC_BILLING_ROLLOUT` defaults to `off`. In that mode premium workspaces remain
open, preserving pre-commerce behavior. `preview` exercises locked UI without
checkout. `test` enables configured Stripe test-mode boundaries. `live` requires
an explicit live mode and configuration. Development Free/Pro simulation remains
limited to the existing local/test server gate.

Configuration is environment-only; no values below are committed:

- `MUSIC_BILLING_ROLLOUT=off|preview|test|live`
- `MUSIC_STRIPE_MODE=test|live`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRO_MONTHLY_PRICE_ID`
- `STRIPE_PRO_ANNUAL_PRICE_ID`
- `MUSIC_PUBLIC_BASE_URL`
- `MUSIC_BILLING_SERVICE_URL`
- `MUSIC_BILLING_SUPABASE_URL`
- `MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY`
- `MUSIC_BILLING_SUPABASE_ANON_KEY`

Run the isolated service only after test configuration is present:

```text
uvicorn monetization_service:app --host 127.0.0.1 --port 8502
```

Live mode remains disabled until the schema is deployed, the public service is
hosted over HTTPS, the exact Stripe webhook endpoint is registered, sandbox
checkout/webhook replay is accepted, and commercial policy decisions are made.

## Decisions required before live activation

1. Final monthly/annual products, prices, currency, tax behavior, trial policy,
   and whether both intervals launch together.
2. Whether `past_due` gets a grace period instead of M2's immediate Free policy.
3. Refund/dispute policy and whether additional Stripe events should revoke or
   flag access.
4. Production billing-service host, region, observability, alerting, retry/dead
   letter process, and operator reconciliation procedure.
5. Customer self-service/portal flow, cancellation UX, support contacts, legal
   copy, terms/privacy, and receipt/support messaging.
6. The staged rollout sequence (`preview` -> `test` -> `live`) and explicit owner
   authorized to change the production flag.
