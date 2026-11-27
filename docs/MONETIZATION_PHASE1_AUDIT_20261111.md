# Music billing Phase 1 audit ? November 11, 2026

## Scope and evidence

Music base: remote dev verified by fetch and ls-remote at
`b25cafc1d8dd601093b0e2482e00fe3e840b47c0`.
Work isolated in `.worktrees/billing-phase1-20261111`, branch
`feature/music-billing-phase1-20261111`. Original workspace has extensive
untracked evidence; none was changed or committed.

Baseball Explorer located at `C:/Users/danie/Documents/GitHub/baseball-stat-app`,
confirmed by its origin repository URL. Reviewed its billing modules, runtime
migration, setup documentation and `fix/billing-lifecycle` (tip `2878b5c`).
Its unmerged code is reference only; no Baseball files were changed or executed.
Other available branches include `fix/billing-portal-completion` and billing
auth integration branches. Their existence is not evidence of deployed behavior.
Music has unmerged `codex/monetization-m3-sandbox` containing `cdacbb54`,
`c1a40e05`, and `69bfabcb`; these add lifecycle and sandbox hardening and should
be reviewed before a later increment. No branch was wholesale imported.

## Already implemented and locally verified

Music retains its existing Free/Pro catalog and monthly/annual configured price
IDs. No commercial price or entitlement was changed. M1 defines core practice,
logs, instrument tools and phrase tools as Free; Composition Studio, advanced
analysis/coaching/export/karaoke and Key Cycling are Pro features.

The 40 existing focused tests pass: authenticated Checkout identity, trusted
interval selection, signature validation, active/trialing activation,
unknown-price fail-closed behavior, conservative past-due downgrade, cancellation
state, duplicate and older events, identity conflict, Free and rollout behavior.
These are mocked domain tests, not actual Stripe payments or database tests.

## Implemented but not externally verified

`monetization_service:app` exposes GET `/billing/health`, POST
`/billing/checkout`, and POST `/billing/webhooks/stripe`. Supabase `/auth/v1/user`
verifies JWT identity. Stripe customer and subscription metadata use that
identity. Success redirects do not grant access. Webhook HMAC covers raw bytes.

M2 migration defines customer/subscription/event/entitlement tables, own-row
entitlement SELECT RLS, and service-only mutation RPCs. No client write grants
exist in the migration. Applied schema, deployed policies, Render settings,
dashboard settings, renewal and test payments were not queried or changed.
No checked-in Render blueprint was found. Billing runs as a separate uvicorn
service; Streamlit uses `streamlit_music_practice_app.py`.

## Missing or broken / production blockers

- Durable customer merge-upsert could replace an existing customer binding.
  This increment repairs that and adds a database immutability trigger.
- Checkout has no customer-creation idempotency key; concurrent initial requests
  can create an orphan Stripe customer. The losing binding now fails closed;
  a retry uses the persisted winner. Duplicate subscriptions still need prevention.
- Subscription and entitlement persistence are separate RPCs. A failure between
  them can make a replay skip entitlement repair. Claims have no exclusive lease;
  same-second event ID lexical order is not a causal Stripe ordering guarantee.
- Music accepts subscription metadata to establish unknown customer mappings;
  require existing trusted ownership in future webhook hardening.
- Webhooks do not explicitly reject livemode payloads; config supports live mode.
  No live configuration or API calls were used in this assignment.
- `Entitlement.grants_pro` does not compare current time with period end. Scheduled
  cancellation preserves access, but automatic expiration without a subsequent
  webhook is not guaranteed. Modern item-level period end and invoice subscription
  shapes need coverage. Failed invoice behavior relies on fetched subscription status.
- Customer Portal and Manage Subscription/cancellation UI are missing in Music.
  Owner-only Portal behavior therefore cannot yet pass acceptance.
- UI Checkout readiness requires server secret configuration via checkout_enabled;
  separate public UI readiness from service-only secrets before hosting.
- Python-side Composition Studio and Key Cycling gates exist, including the
  Key Cycling mutation guard; catalog-wide server enforcement is incomplete.
- Commercial prices remain external configuration; documentation leaves tax,
  trial, support and refund decisions open. Preserve established price IDs.

## Reusable Baseball components / Music requirements

Reuse design patterns after isolated review: immutable two-way customer mapping,
Checkout idempotency, owner-derived Portal sessions, event fingerprint/lease
handling, atomic entitlement reconciliation, item-level period parsing, test/live
separation, schema preflight and public client readiness. Baseball uses its own
price contract and runtime schema; do not copy its price IDs, table assumptions,
plan features or migration into Music. Music needs both existing intervals,
its own feature catalog and verified Supabase auth identity across workspaces.

## Implemented increment and verification

In-memory store now rejects sharing a customer across users and empty IDs.
Checkout rejects empty provider IDs and mismatched persisted ownership.
Supabase inserts ignore existing bindings and read back the persisted winner;
a race cannot start Checkout with a losing customer ID. New migration rejects
updates to either ownership identifier while allowing email updates and leaving
existing rows intact. Account deletion behavior is unchanged.

Six new focused cases cover two-way conflicts, repeated Checkout, empty provider
IDs, persistence success/race loss and mismatched owner lookup. Final command:
`python -m pytest tests/test_monetization_customer_ownership.py tests/test_monetization_m2.py tests/test_monetization_entitlements.py -q`
Result: **46 passed**. An initial test helper import failed collection and was
corrected before the passing run. `git diff --check` passed.

Lifecycle acceptance: Free, activation, duplicate, failed status and cancellation
mapping are locally covered. Real test-payment activation, invoice/renewal delivery,
period-boundary expiry, owner-only Portal and deployed RLS denial remain unverified
or incomplete as described above. No real payment or live billing action occurred.

Resources: psutil measured available RAM 1.85 then 1.50 GB, CPU 45 then 24.5%,
disk free about 149 GB. CIM monitoring was denied; psutil provided the fallback.
No browsers, development servers, heavy suites or background services were launched.

## Database and hosting checklist (test environment only)

Apply existing `20260927_monetization_m2.sql` if absent, followed by
`20261111_music_customer_ownership.sql`. New SQL was reviewed but not executed;
verify real service-role insert/race behavior and trigger rejection in a disposable
Supabase environment, plus authenticated/anon write and RPC denial. No credentials
were read. No new environment variable is introduced.

Render variable names for the service:
- MUSIC_BILLING_ROLLOUT
- MUSIC_STRIPE_MODE
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRO_MONTHLY_PRICE_ID
- STRIPE_PRO_ANNUAL_PRICE_ID
- MUSIC_PUBLIC_BASE_URL
- MUSIC_BILLING_SERVICE_URL
- MUSIC_BILLING_SUPABASE_URL
- MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY
- MUSIC_BILLING_SUPABASE_ANON_KEY

Use test rollout/mode and test credentials only. Keep service-role and Stripe
secrets exclusively on the billing service; repair UI readiness before enabling
Checkout there. Run `uvicorn monetization_service:app --host 0.0.0.0 --port $PORT`
on the separate Render service. Confirm HTTPS routing and restricted logs.

Stripe test dashboard: verify existing Music monthly/annual recurring Prices;
register the service HTTPS `/billing/webhooks/stripe` endpoint for Checkout
completion, subscription created/updated/deleted, invoice paid/payment_failed.
Use its test signing secret. Configure test Customer Portal only once its owner
endpoint is implemented. Complete real test Checkout, retry/out-of-order, renewal,
failure and expiration scenarios before requesting production launch approval.
No deployments, pushes or dashboard changes were made.
