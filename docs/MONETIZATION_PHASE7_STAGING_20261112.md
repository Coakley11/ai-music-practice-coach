# Phase 7: Music Stripe sandbox and Render staging preparation

Date: 2026-11-12 (America/New_York). Base: be4a2a3a80ef2fce71641517e225ab0907de6184.

## Decision

**NO-GO for deploying now or performing Checkout:** there is no deployment/push
approval, confirmed Music sandbox Price/Portal configuration, hosted owner-SQL
regression result, or verified staging URL/runtime. This assignment prepares local
code/specifications only; no Stripe/Render dashboard was changed or account API used.

**Ready to review for a separately approved, free, health-only staging deployment.**
The startup guard requires isolated Supabase keys/URL and explicit test modes. With
Stripe settings absent, health works and existing configuration disables Checkout
and webhooks. Billing-enabled Checkout remains gated by the checklist below.

The Phase 6C Auth/JWT/PostgREST synthetic suite remains valid evidence, not a real
Stripe payment. This phase ran local mocks/ASGI tests only. No database installation,
hosted SQL write, production service modification, push, merge or deployment ran.

## Existing commercial and technical contract

- Existing tier names: **Free** and **Pro**. Monthly Checkout is the current UI
  path; annual is supported by configuration but optional. No authoritative
  commercial amount, currency or tax treatment exists in the audited code/UI/docs.
  Do not invent a nominal test amount, annual discount or extra tier.
- Free includes core practice, songs, backing, custom progressions, Entry & Jam,
  Missions, Phrase/Motif, instruments and Practice Log. Pro adds Composition Studio,
  advanced uploads, multitrack/export, advanced AI/analytics, karaoke/setlists and
  Key Cycling. No entitlement changes were made.
- All Stripe requests pin **2026-10-28.endive**. Stripe's current versioning docs
  confirm it; configure this exact version on the new snapshot webhook destination.
  Do not upgrade the account-wide default used by Baseball.
- Six events: checkout.session.completed; customer.subscription.created;
  customer.subscription.updated; customer.subscription.deleted; invoice.paid;
  invoice.payment_failed. Use account sandbox snapshot events, not thin events or
  live/Connect events.
- Existing raw-body timestamped HMAC verification (300-second tolerance), test-only
  mode checks, immutable Music customer RPC, customer/event leases, fresh-provider
  subscription reconciliation, duplicates and read-time expiry remain intact.
- Customer creation uses music-customer-v1- plus a hash of the Auth UUID; Checkout
  uses a persisted one-hour music-checkout-v1- reservation with stable expiry. Stripe
  idempotency is bounded; do not blindly retry after its retention window or reset
  ownership. Open/nonterminal subscriptions block a second Checkout.
- Failed payment access policy stays fail closed: past_due/unpaid/incomplete/paused
  do not grant Pro. Active scheduled cancellation keeps Pro until period end.
  A redirect or successful Checkout page never grants access by itself.

## Stripe sandbox configuration checklist (not executed)

1. Select/create a **dedicated Music sandbox** after approval, separate from
   Baseball billing. Confirm its name/account identity and that it is not live.
   Keep account ID as review evidence; keep its sk_test key only in the staging
   service's secret environment. No production key, real card or real identity.
2. Inspect the selected sandbox's existing Music products/prices first. Reuse a
   matching Music Pro recurring price only after verifying its amount, currency,
   interval, active flag, tax behavior and app metadata against approved Music
   terms. If none exists, prepare/create the Music-only Pro product and one monthly
   recurring Price using those exact approved terms. Free needs no paid Stripe plan.
3. The required value is the actual sandbox **price_...** for monthly Pro, stored in
   STRIPE_PRO_MONTHLY_PRICE_ID. It is **not known or created in this phase**.
   The currency/amount are deliberately null in the review-only
   deploy/stripe.music-sandbox.template.json. Stop until the owner supplies existing
   approved pricing. Annual stays unset unless an approved annual price exists.
4. Set product/price metadata app=music. Confirm price.recurring.interval=month,
   interval_count=1, active=true and livemode=false. A sandbox ID cannot be inferred
   from its prefix alone; verify it using that sandbox's dashboard/API credentials.
5. Create a **separate** portal configuration named Music staging. Do not edit or
   use an existing account-default/Baseball configuration. The template contains
   its API feature payload: payment-method updates, invoice history, cancellation
   at period end, no plan/quantity switching. Keep pause, coupons, retention offers,
   trials and other unimplemented flows disabled for the first test.
   Configure approved test return/branding URLs. Save its actual **bpc_...** value
   as MUSIC_STRIPE_PORTAL_CONFIGURATION_ID; verify livemode=false/active=true.
   If the dashboard cannot create a separate configuration, use the documented
   configuration-create API after approval, not the shared/default editor.
6. After the staging backend URL is reserved/deployed under separate approval,
   create a Music-only event destination at
   `https://<actual-staging-host>/billing/webhooks/stripe`. Choose the six events
   above and snapshot API version 2026-10-28.endive. Store its own whsec secret in
   STRIPE_WEBHOOK_SECRET. A Stripe CLI forwarding secret is not this endpoint's
   signing secret. Do not redirect/reuse Baseball's destination or secret.
7. Confirm the staging key resolves to the intended sandbox account using a
   read-only API/account inspection, and that product/Price/Portal/webhook all
   resolve under that same key. Do not log the key, session URLs, JWTs or payment
   payloads. No such authenticated Stripe request was performed in this phase.

## Customer and app isolation

Music persists only music_billing_* objects in smpyutzfktjgpdibdbqb. It never adopts
Baseball's public.subscriptions or private ledgers. Requests cannot supply user,
customer, Price or return URL; Auth UUID and server config determine them. Customer
bindings are immutable and unique in Music's tables, with Portal forward/reverse
ownership checks. Dedicated sandbox credentials provide the cross-app provider
boundary; metadata alone is not credential isolation.

A new gateway check retrieves the Stripe customer before subscription lookup and
Portal creation and rejects non-Music/untagged/deleted/live/mismatched customers.
Existing Music customers must have metadata app=music and app_user_id; never patch
Baseball customers to pass this check. New customer creation already sets these.
Existing signed foreign-app events are ignored; untagged unknown customers fail
closed/retry. A shared all-events Stripe account can therefore generate unwanted
retries; do not attach Baseball events to this Music destination.

**Use fresh synthetic Auth users for the real Checkout.** Phase 6C's four retained
users have fake cus_ identifiers and cannot be used with actual Stripe. Their
immutable mappings must not be reset/replaced. Keep the old run records for review.

## Dedicated Render service specification (not applied)

Review `deploy/render.music-staging.yaml`; it is deliberately not root render.yaml.
Select that file explicitly only after approval. Do not bind/import existing Music,
Suite or Baseball services or shared environment groups.

| Field | Prepared value |
| --- | --- |
| Service | new Music-only web service, proposed name music-billing-staging |
| Repository | Coakley11/ai-music-practice-coach |
| Branch | feature/music-billing-staging-20261112 (local until approved push) |
| Plan | free; no database, disk or autoscaling resources |
| Runtime | Python 3.12.8 via PYTHON_VERSION |
| Build | pip install -r requirements-billing.txt |
| Start | python -m uvicorn monetization_staging:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log |
| Health | GET /billing/health |
| Automatic deploys | off |

The existing **monetization_service:app** remains the ASGI application. The new
**monetization_staging:app** imports/exports that same object after the startup
guard. Do not bypass the guard in staging. It requires explicit isolated URL,
legacy key project/role claims, test rollout and test Stripe mode; rejects SUITE_*
variables and a non-test Stripe key. Claim checking is not signature verification;
Supabase must still accept the actual keys. No production application uses the wrapper.

requirements-billing.txt contains only Starlette, Uvicorn and requests, excluding
audio/Streamlit/AI dependencies. Installed package metadata supports Python 3.12;
local tests ran on Python 3.13.7, so an actual 3.12.8 build is still unverified.
Render documents support for released Python versions including 3.12.8; do not
accept its newer default runtime accidentally. No package/runtime install was run.

Creation can trigger the first deployment even with auto-deploy off: do not click
Create/Apply before explicit approval. First deploy can be health-only with the
Stripe fields left blank; Checkout/webhook readiness must be false. Then reserve
the actual URL, create/configure the sandbox destination and fill the remaining
settings before a separately approved billing-enabled restart/deploy. A configured
health HTTP 200 is not proof of Stripe/Supabase reachability or Portal readiness.

Free compute still consumes shared workspace quotas and can incur bandwidth/build
overages depending on account settings. Verify quotas/spend limits before creation;
if Free is unavailable, stop rather than selecting a paid plan. Cold starts can
delay deliveries; warm health before testing and verify Stripe retry outcomes.
The synchronous provider calls in the existing async handlers also need observed
latency/health behavior in staging. This small service is not a load-tested design.

## Exact staging environment names

Enter secret values only in the **new service's private environment**, never in Git,
Blueprint value fields, build/start commands or logs. Do not attach a shared env group.

| Name | Source/requirement |
| --- | --- |
| PYTHON_VERSION | 3.12.8 |
| MUSIC_BILLING_ROLLOUT | test (off opens premium access) |
| MUSIC_STRIPE_MODE | test |
| MUSIC_BILLING_SUPABASE_URL | https://smpyutzfktjgpdibdbqb.supabase.co |
| MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY | isolated project's legacy service_role JWT; backend-only |
| MUSIC_BILLING_SUPABASE_ANON_KEY | same isolated project's legacy anon JWT |
| STRIPE_SECRET_KEY | dedicated Music sandbox sk_test key |
| STRIPE_WEBHOOK_SECRET | Music staging destination signing secret |
| STRIPE_PRO_MONTHLY_PRICE_ID | actual approved Music monthly sandbox price_ ID |
| STRIPE_PRO_ANNUAL_PRICE_ID | optional, omit until approved/configured |
| MUSIC_STRIPE_PORTAL_CONFIGURATION_ID | separate Music sandbox bpc_ ID |
| MUSIC_PUBLIC_BASE_URL | approved HTTPS staging-only Checkout/Portal return URL |
| MUSIC_BILLING_SERVICE_URL | actual new HTTPS backend origin |
| PORT | supplied by Render, not a committed fixed port |

For an API-only rehearsal, the staging backend's /billing/health URL can serve as
a temporary technical return destination; it displays configuration status, not
payment success. Prefer an approved static test return page when available. Never
return synthetic users to deployed production Music. Access logging is disabled to
avoid application logs recording the Checkout session query parameter; review any
platform-level request logs before sharing screenshots/exports.

Keep MUSIC_ENTITLEMENT_DEV_CONTROLS and MUSIC_ENTITLEMENT_DEV_RUNTIME disabled/unset.
No SUITE_* setting belongs on this service. Do not change any deployed Streamlit
login/settings. A later separate staging UI, if approved, must use the same isolated
Auth URL and anon key; production Suite JWTs must fail authentication here.

## Pending hosted owner-run SQL harness: release gate

Reviewed scripts/sql_tests/music_billing_shared_roles.sql and
music_billing_lifecycle_rehearsal.sql. They run in transactions and ROLLBACK. The
role harness deliberately adds a test constraint, requires owner-level execution
and SET ROLE, two distinct existing synthetic Auth UUIDs **without Music billing
records**, and no leftover fixed fixture IDs. Existing Phase 6C users fail this
precondition by design. Never delete/reset them to make a test pass.

Before billing-enabled Checkout, create two fresh synthetic users in the isolated
project, pause Music staging writes and run these harnesses using Phase 6's exact
SQL Editor/psql instructions. They may briefly lock Music tables; no shared Suite
or production app operation is involved. Finish/confirm ROLLBACK, then verify zero
Music records for those two users. They can then be the real payment-test accounts.

Blocking failures: self/cross-user entitlement visibility or write access; effective
INSERT/UPDATE/DELETE/TRUNCATE or client RPC grants; immutable-owner failure; invalid
lease/retry/duplicate behavior; atomic failure leaving a changed subscription or
entitlement; failed payment granting Pro; cancellation/expiry incorrectly granting
or removing access. Any such failure is NO-GO for billing tests until corrected.

Missing owner privileges, inability to SET ROLE, stale fixtures or a missing Auth
user are setup blockers, not permission to bypass assertions. Stop/ROLLBACK and
review. Do not add service-role DDL, loosen RLS or change project role memberships.
Health-only staging can be reviewed independently; it performs no fixture writes.

## First real sandbox payment test (execute only after staging approval)

Keep identifiers/tokens in private local test notes, not Git or console dumps. Use
the isolated Auth password flow to obtain JWT A/B in memory. Reuse the existing
guarded Phase 6 client approach; never use its fake customer mappings for Checkout.
Call HTTPS backend endpoints from a private CLI/server client, not production UI.

| Step | Action | Required actual-service evidence |
| --- | --- | --- |
| 1 | GET /billing/health; validate test flags and readiness | actual staging commit/runtime/URL, not just 200 |
| 2 | A/B initially read own entitlements through JWT REST | Free, no imported synthetic paid state |
| 3 | POST /billing/checkout with Bearer JWT A, JSON interval=monthly | 201, Stripe-hosted test Checkout; no client-supplied Price/customer accepted |
| 4 | Repeat same Checkout request before payment | same reservation/session, no extra subscription; retain stable parameters |
| 5 | Complete Checkout using Stripe's documented sandbox test payment method | Stripe sandbox payment/invoice succeeded; never real card; don't enter fixture card data on other sites |
| 6 | Observe six-event endpoint deliveries | valid signed event receives 2xx only after persistence; latency/retries inspected |
| 7 | Read Music rows as approved owner and own entitlement via JWT A | correct real cus/sub/Price mapping, active Pro with future period; B cannot read A |
| 8 | POST /billing/portal with JWT A | 201 no-store, correct Music customer and explicit bpc config; B cannot select A's customer via body |
| 9 | Cancel at period end through Portal | active/cancel_at_period_end => Pro through real period end; no immediate revocation |
| 10 | Cancel immediately on a separate sandbox scenario | provider canceled => Free after signed deletion/update |
| 11 | Test renewal, past_due failure and recovery | provider active renewal keeps Pro; actual past_due removes Pro; successful recovery restores it |
| 12 | Resend an already processed Stripe event | no extra records; duplicate safely acknowledged |
| 13 | Deliver an older event/retry after a newer state | backend retrieves current subscription under lease; does not restore obsolete access |
| 14 | Invalid/missing signature and isolated-user auth failures | 400 webhook without valid signature; no mutations; 401/403 ownership failures |
| 15 | Period expires; verify server entitlement decision | no Pro after wall time, even if final notification is delayed |

The current customer-creation code does not attach a test clock. Stripe's Dashboard
documents a Run simulation action for eligible existing subscriptions; inspect its
availability before choosing that workflow. For an explicitly clock-controlled API
test, use a **separate** fresh clock-associated sandbox customer created with Music
app/user metadata, map it to
a separate fresh isolated Auth user through the approved immutable attach RPC,
and create its subscription through Stripe's supported clock workflow. This does
not replace step 5's real Checkout payment. Do not reset existing bindings or add
a production clock flag just for tests. Clock movement changes Stripe's simulated
time, not Render's wall clock: inspect actual period/status events and test local
wall-clock expiry separately rather than claiming the two clocks are identical.

Prepare a deliberately failing renewal method in that clock scenario, observe
Stripe's actual status (a decline alone is not necessarily past_due), then restore
a successful test method/pay the invoice and verify recovery. Poll/inspect retries
without broadening grants. Leave cancellation-at-period-end as Portal default;
test immediate cancellation through an explicit separate sandbox operation.

For a retry test, use a controlled test-only transient failure or existing busy
lease, confirm a non-2xx, restore readiness and resend the same event. Do not change
production secrets, corrupt tables or deliberately disable the shared database.

## Code changes, validation and unresolved checks

Added staging-only guard/wrapper, a lightweight backend requirements file, the
review-only free-service Blueprint, and Stripe configuration template. Added
Stripe customer app/mode validation before Checkout lookup/Portal. Existing account
ownership, Price selection, API pin, Checkout idempotency, signature verification,
SQL installation and entitlement catalog were preserved. Updated two gateway mocks
to return the newly required Customer read without weakening their original checks.

Final focused local result: **163 passed in 11.66 seconds** (Python 3.13.7). Includes
22 staging tests plus the 141 Phase 6 tests. First run had one expected stale Portal
mock failure; corrected mock and rerun passed. No real Stripe API, Render build,
dashboard object creation, SQL owner harness or sandbox payment ran in this phase.
Blueprint fields were reviewed against official docs; no hosted schema validation
API was called, and the blueprint is not claimed platform-validated/applied.

Resource samples: available RAM 1.34 GB at start and 1.04 GB after tests; CPU 85.1%
and 65.5%; disk 141.22/140.99 GB. No browser/server or heavy concurrent job launched.
Unrelated debug.log and all private ignored key files are preserved and excluded
from commits. No process outside this assignment was stopped.

## Approval checkpoint and next exact actions

1. Review the local commit/specification. Supply/confirm existing approved Music
   Pro amount, currency/tax treatment and sandbox account identity; no invented price.
2. Approve a push of the isolated branch if desired; nothing is pushed automatically.
3. Separately approve creation/deployment of the new Free Render service with its
   spend/quota settings. Health-only bootstrap can precede Stripe configuration.
4. Complete owner SQL regression checks in the isolated database, using fresh users.
5. Approve the Music-only sandbox product/Price/Portal/webhook configuration and
   securely enter actual IDs/secrets in that service. Do not expose them in Git.
6. Verify 3.12.8 build/hosted key acceptance/readiness, then explicitly approve the
   first actual sandbox Checkout/lifecycle rehearsal. Record actual evidence.

## Official references checked

- Stripe API pin and endpoint versioning: https://docs.stripe.com/api/versioning
- Products/prices: https://docs.stripe.com/products-prices/manage-prices
- Separate Portal config API: https://docs.stripe.com/api/customer_portal/configurations/create
- Portal options: https://docs.stripe.com/customer-management/configure-portal
- Signatures/retries: https://docs.stripe.com/webhooks
- Billing simulations: https://docs.stripe.com/billing/testing
- Explicit test clocks: https://docs.stripe.com/billing/testing/test-clocks/api-advanced-usage
- Render Python support: https://render.com/docs/python-version
- Blueprint fields: https://render.com/docs/blueprint-spec
- Free-instance limits: https://render.com/docs/free
