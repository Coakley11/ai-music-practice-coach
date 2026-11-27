# Phase 7 staging handoff after sandbox inspection

This report supersedes the unknown Price and configuration status in the original
Phase 7 preparation report. No push, deployment, payment, Portal creation, SQL
execution or external configuration change was performed during this continuation.

## Decision and next dashboard action

Ready for an explicitly approved branch push and **health-only Free deployment**.
NO-GO for billing-enabled deployment or payment until sandbox provenance, owner SQL,
Portal, signing secret, actual runtime and hosted endpoint checks pass.

Next: Stripe account picker -> Sandboxes -> open **Music Practice Coach Staging**.
Confirm it is a separate general sandbox, not the shared legacy test-mode sandbox.
Verify its displayed account ID against acct_1Ub8HEGSM5yahQur, locate Price
price_1Ub8MiGSM5yahQursL7MlBcs and Portal bpc_1Ub8nFGSM5yahQurK0dnmcGe there,
and confirm Baseball is configured for a different sandbox/account. Report only
these nonsecret facts; never copy keys. A sandbox name alone is insufficient.
Baseball's deployed credentials/settings cannot be inspected from local Music files.
No claim of exclusive provider isolation is made without this evidence.

Stripe documents isolation across general sandboxes. A sk_test prefix, livemode=false,
product name, account ID or untagged default alone does not prove which named sandbox
or application uses it. Local inspection established availability in the supplied
key scope, not Baseball's deployed key scope. No live/Baseball settings were changed.

## Portal decision

The existing default Portal remains **unselected** in the ignored private JSON.
Once exclusive general-sandbox ownership is verified, reuse its ID explicitly as
MUSIC_STRIPE_PORTAL_CONFIGURATION_ID; it need not be renamed or edited. Current
features match cancellation at period end, invoice history and payment-method updates.
Do not configure it based only on its name or default flag.

Alternative prepared, NOT executed: create a non-default configuration named
Music Practice Coach Staging with app=music/environment=staging metadata, invoice
history and payment-method updates enabled, period-end cancellation without proration,
subscription updates and hosted login page disabled. Exact proposed feature payload:
deploy/stripe.music-sandbox.template.json -> portal_configuration. Creation endpoint:
POST /v1/billing_portal/configurations, API version 2026-10-28.endive. Use only the
confirmed Music sandbox key, a stable creation idempotency key and explicit approval;
never edit/set the account default. Verify returned active=true, livemode=false,
is_default=false and metadata before selecting the new ID. A separate Portal config
is an app-selection boundary, not a substitute for dedicated sandbox credentials.
Approval is requested before any such creation; no creation is needed if the existing
Portal's exclusive scope is confirmed.

## Verified local credential boundaries

Guarded --check-config passed for .music-phase6-blank.local.json. Both legacy JWT
keys name smpyutzfktjgpdibdbqb with the expected anon/service_role claims. Actual
GET-only Auth settings/admin acceptance checks also passed. No identities or key
values were printed. This validates the current local file, not future Render entry.
The startup wrapper validates the exact isolated URL and key project/role claims,
rejects SUITE_* variables and live Stripe keys. Supabase performs key authentication;
local JWT decoding is not cryptographic verification.

The Stripe file passed the preceding real GET inspection under the test key. Stripe
keys have no Supabase project association: the isolated database boundary comes from
separate Supabase URL/keys. No Render service currently exists as verified evidence;
its eventual environment remains UNVERIFIED. Protected Suite project
qhprdlwoxjpkiukxhftp must never appear in the new service's configuration.

## Exact Render manual setup (after separate push/deployment approval)

1. Push only feature/music-billing-staging-20261112 after explicit approval; no dev/main
   merge. Confirm the approved commit is visible on GitHub before connecting Render.
2. Render -> New -> Web Service -> Coakley11/ai-music-practice-coach. Create a new
   service named music-billing-staging; do not reuse Music/Baseball services or attach
   shared environment groups. Branch: feature/music-billing-staging-20261112.
3. Runtime Python; repository root directory (no subdirectory); Free instance only.
   Stop if Free is unavailable. Check workspace quota/spend settings first; Free
   compute does not guarantee absence of workspace usage overages.
4. Build: pip install -r requirements-billing.txt
   Start: python -m uvicorn monetization_staging:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
   Health check: /billing/health. Auto-deploy: Off.
5. Add ONLY these first-boot environment variables:
   PYTHON_VERSION=3.12.8
   MUSIC_BILLING_ROLLOUT=test
   MUSIC_STRIPE_MODE=test
   MUSIC_BILLING_SUPABASE_URL=https://smpyutzfktjgpdibdbqb.supabase.co
   MUSIC_BILLING_SUPABASE_ANON_KEY (isolated legacy anon key, private dashboard field)
   MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY (isolated legacy service_role key, private field)
   Render supplies PORT. Omit every STRIPE_* variable,
   MUSIC_STRIPE_PORTAL_CONFIGURATION_ID, MUSIC_PUBLIC_BASE_URL and
   MUSIC_BILLING_SERVICE_URL on this first health-only boot. No SUITE_* or dev controls.
6. Review deploy/render.music-staging-health-only.yaml as the equivalent minimal
   specification. Original render.music-staging.yaml is the later billing-ready
   template, not the health-only bootstrap. Do not apply both.
7. STOP before Create/Deploy until deployment approval. Initial creation deploys even
   with automatic deploys disabled. After approval verify build actually uses Python
   3.12.8 and GET https://<assigned-host>/billing/health returns 200 with rollout=test,
   stripe_mode=test, checkout_enabled=false, webhook_enabled=false,
   credentials_match_mode=false, monthly_price_configured=false and
   supabase_configured=true. Health is configuration evidence, not a database probe.
   Do not treat a 200 alone as a payment readiness result. Free instances can sleep.

Python 3.12.8 is explicitly pinned; prior local tests ran on Python 3.13.7. Actual
Render build/runtime and platform validation remain unverified until approved deploy.

## Webhook and later billing enablement (not yet authorized)

Code route: POST /billing/webhooks/stripe on the new staging HTTPS origin; no redirect,
production URL or Baseball endpoint. Gateway pins 2026-10-28.endive. Create a Music-only
snapshot destination, Your account, with that exact API version and exactly:
checkout.session.completed, customer.subscription.created,
customer.subscription.updated, customer.subscription.deleted,
invoice.paid, invoice.payment_failed.

Use its own revealed whsec_ signing secret as STRIPE_WEBHOOK_SECRET, not a CLI
forwarding secret. Signature verification uses the raw body, timestamp tolerance
300 seconds and constant-time HMAC comparison. Provider reads reconcile current state
under leases; duplicate delivery is acknowledged without repeating writes; processing
failures remain retryable. Reordering cannot be tested by health inspection alone.

After separate approval and all payment gates, securely add STRIPE_SECRET_KEY,
STRIPE_WEBHOOK_SECRET, STRIPE_PRO_MONTHLY_PRICE_ID=price_1Ub8MiGSM5yahQursL7MlBcs,
MUSIC_STRIPE_PORTAL_CONFIGURATION_ID (confirmed/new ID), MUSIC_PUBLIC_BASE_URL
(approved staging-only return destination), MUSIC_BILLING_SERVICE_URL (new origin).
STRIPE_PRO_ANNUAL_PRICE_ID stays omitted. Never put secret values in the Blueprint,
commands, screenshots or Git. Never change account-wide API defaults or deployed apps.
No endpoint signing secret or delivery has been verified yet.

## Hosted owner SQL gate and recovery

Pending scripts/sql_tests/music_billing_shared_roles.sql and
scripts/sql_tests/music_billing_lifecycle_rehearsal.sql were reviewed. Both end in
ROLLBACK, require owner/SET ROLE capabilities and fresh synthetic auth.users. Existing
Phase 6C users have immutable fake Stripe mappings; preserve them and use two new
accounts. The role harness temporarily adds a constraint to prove atomic failure
rollback. These are test-only writes, not a read-only inspection; they were not run
in this continuation. Local PostgreSQL success and hosted REST success are separate
evidence and do not replace the pending owner harness.

Use the isolated project owner connection via private psql password prompt (do not
put a database password in a command). Independently confirm project reference before
connecting. For the roles file run psql with ON_ERROR_STOP, user_a/user_b UUID variables
and -f scripts/sql_tests/music_billing_shared_roles.sql. For lifecycle use a NEW psql
session with ON_ERROR_STOP, BEGIN then SET LOCAL music_test.user_a/user_b to the same
fresh UUIDs, include the lifecycle file using \i, and confirm its final ROLLBACK.
Its nested BEGIN only emits PostgreSQL's already-in-transaction warning and its final
ROLLBACK rolls back that test session; never wrap other work in the same transaction.
Disconnect/ROLLBACK on any failure. No permission weakening or service-role DDL.

Before either script verify fixed cus_music_role_fixture_*, evt_music_role_fixture_*,
cus_music_lifecycle and evt_music_lifecycle_* IDs are absent. Pause staging writes
while running. Afterwards confirm temporary constraint music_billing_test_reject_reason
is absent and both users still have zero billing records across all four Music tables.
Do not drop/reinstall billing objects or delete prior records to recover.

Any unexpected client writes/TRUNCATE, cross-user visibility, backend raw-table access,
RPC grants, ownership changes, stale lease completion, duplicate side effects or failed
atomic rollback blocks payments. Setup privilege/fixture failures also block completion
until corrected. No such new failure was observed; hosted owner coverage is pending.

## Sources

- https://docs.stripe.com/sandboxes
- https://docs.stripe.com/api/customer_portal/configurations/create
- https://docs.stripe.com/webhooks
- https://render.com/docs/python-version
- https://render.com/docs/free

## Validation in this continuation

33 focused tests passed in 2.57 seconds (test_music_staging and
test_music_stripe_inspection). Actual local Supabase credentials passed staging
startup validation and hosted GET-only acceptance checks. The local Stripe config
passes the test-key guard; Portal remains blank. No credential values were printed.
The initial restricted-network GET failed, then the identical guarded read-only
check succeeded with approved network access. No new hosted lifecycle/owner SQL,
Stripe mutations, Portal session or Render build was attempted.

Resources: available RAM 2.40 GB before checks and 1.91 GB after; final sampled CPU
73.6%; disk free 140.78 GB. No browser, background server, installation or concurrent
heavy tests were started. No process was stopped. Unrelated debug.log is preserved.
