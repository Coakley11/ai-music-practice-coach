# Music billing Phase 3: integration readiness

**NO-GO for the first real end-to-end test today.** Local code checks pass, but
no target schema, Stripe account/Price, or hosted billing service has been verified.
The next gate is approval of an identified isolated test environment, not a charge.

Reviewed Phase 1 `f4d89eae7e7f2da3e67d2bb926d0e35b6dba7166` and Phase 2
`5cdd95b795047347c3df885811c29685140ea6b3`, including their billing diffs,
three migrations, RPC adapter, authentication, UI, fixture tests and Phase 2 report.
Both phases and all migrations are unchanged. This branch adds preparation only.

## 1. Defects and verification limits

- Corrected a **documentation omission**: environment-only Music login requires
  `SUITE_SUPABASE_KEY` as well as the URL/anon key. `get_cloud_config()` otherwise
  returns None before Auth client creation. For this isolated test UI, use the
  public anon key for SUITE_SUPABASE_KEY; do not copy the billing service-role key.
  Existing Streamlit secrets can also supply cloud configuration; avoid mixing
  projects across sources. A fresh project also needs existing Suite auth/profile
  storage and its RLS for full Music login/session persistence; billing migrations
  alone do not create suite_users or the other Suite tables.
- No newly reproduced billing code defect blocks a controlled single-user sandbox
  Checkout. Inherited gaps remain: customer/Checkout creation lacks idempotency
  keys and duplicate-subscription prevention; HTTP API version is not pinned;
  `/billing/health` always returns 200 and checks configuration only. Do not treat
  it as proof of valid keys, Price ownership, RPC access or database connectivity.
- Use one known recurring Music price per subscription, no multi-price or paginated
  item cases for the first test. Unknown prices fail closed; paginated items retry.
  Annual Checkout exists in the API; the UI offers monthly, so a monthly Price is
  required even though generic readiness accepts either configured Price.
- Subscription/entitlement/event completion is one SQL transaction. Customer and
  event locks, five-minute leases and fencing tokens protect concurrent processing.
  Duplicates are no-ops; old events retrieve current Stripe status. Subscription
  reads happen after the customer lease is acquired. Expiration is enforced at
  application read/access time; it does not physically rewrite the database row
  without reconciliation. No periodic reconciliation worker exists.
- Existing scheduled-cancellation access lasts through the exact period end;
  active/trialing paid status grants access within its known end; past_due is Free;
  canceled/unpaid/incomplete/paused is Free. An invoice failure alone does not
  override Stripe's current subscription status. Recovery to active restores Pro.
- Sequential focused verification: **85 passed in 3.37s**, Python **3.13.7** locally.
  Render is pinned by repo files to **3.12.8**: rerun on that runtime before rollout.
  SQL/PLpgSQL syntax parsing passes; no migrations or DB verification scripts were
  executed. No actual Stripe request, external schema or hosted service was checked.

## 2. Supabase sequence, preservation and rollback

Run `supabase/preflight/music_billing_readiness.sql` read-only in the intended
Music test project, then review its metadata before granting migration approval.
It inventories columns/types/defaults, constraints/indexes, RLS/policies, triggers,
RPC signatures/owners/grants and role/schema privileges without selecting user data.
**Safety against the existing schema cannot be certified until this is reviewed.**
`CREATE TABLE IF NOT EXISTS` does not repair incompatible existing tables. Extra
policies, PUBLIC grants, triggers and columns on an existing project must be reviewed.

Exact migration sequence, with each unapplied migration executed transactionally
by the approved migration runner (not statement-by-statement in a SQL editor):

1. `20260927_monetization_m2.sql` - only if absent.
2. `20261111_music_customer_ownership.sql` - Phase 1.
3. `20261112_music_billing_lifecycle.sql` - Phase 2.

Preserve **all** existing columns, rows, timestamps, identities, constraints, indexes
and payloads. The base contract is:

| Table | Existing fields that must remain |
| --- | --- |
| billing_customers | app_user_id UUID PK -> auth.users, unique stripe_customer_id, email, created_at, updated_at |
| billing_subscriptions | stripe_subscription_id PK, app_user_id, stripe_customer_id FK, stripe_product_id, stripe_price_id, provider_status, current_period_end, cancel_at_period_end, trial_end, latest_event_id, latest_event_created, created_at, updated_at |
| billing_webhook_events | stripe_event_id PK, event_type, event_created, payload JSONB, processing_state, attempt_count, last_error, received_at, processed_at, updated_at |
| billing_entitlements | app_user_id UUID PK -> auth.users, plan free/pro constraint, status, current_period_end, source_subscription_id, source_event_id, source_event_created, reason, updated_at |

Phase 1 adds the immutable-ownership trigger/function. Phase 2 adds only
customer reconciliation_token/reconciliation_expires, event fingerprint/lease_token,
and subscription projected_plan/projected_status/projected_reason; it backfills
only existing trusted source projections. No table/column/record is deleted.

Required new RPC signatures (EXECUTE to service_role only; deny PUBLIC/anon/authenticated):

- music_billing_claim_delivery(text,text,bigint,text,text,jsonb)
- music_billing_complete_delivery(text,uuid,jsonb,jsonb)
- music_billing_fail_delivery(text,uuid)

All four tables require RLS. Authenticated users get only own-row entitlement
SELECT via app_user_id = auth.uid(); no client billing writes/RPC execution.
Confirm service_role has required table privileges and its RPC execution rights;
the base migration assumes Supabase's service-role table defaults. Check effective
PUBLIC/inherited grants too. Definer RPCs use qualified tables and a fixed search
path; untrusted roles must not have CREATE on public. Phase 1 trigger applies to
service writes as well. Generic names must not collide with another app's schema.

Phase 2 revokes service_role execution of the three old M2 mutation RPCs. Do not
rerun M2 after Phase 2: it would restore old execution grants. Quiesce the test
billing writer during migration/cutover; do not run Phase 1 workers against Phase 2.
After approval, execute `scripts/sql_tests/music_billing_phase2.sql` with a dedicated
existing auth user without billing records; it rolls its fixture writes back and
checks atomic failure/retry, immutability, grants, leases and deduplication.

**Data-preserving rollback:** snapshot schema/grants and back up the four tables
before approved application. A failed migration must roll back its whole transaction.
After a successful cutover, pause test Checkout/webhook processing, retain all
billing tables, additive columns, ownership protection and ledger, and repair forward
on Phase 2. Do not drop tables, delete auth users (FK cascades), erase event history,
restore stale data, or blindly restore old RPC grants/code. Phase 1 is not a compatible
runtime rollback after Phase 2. Keep protected access enforced while paused; rollout
OFF deliberately opens premium features and is not a fail-closed incident setting.
Resume retries and reconcile current Stripe state after recovery.

## 3. Stripe dashboard actions (user/owner; sandbox only)

1. Select the intended Stripe test account/sandbox. Open **Product catalog** and
   find the existing Music Pro product and its active recurring monthly Price.
   Record its actual Price ID into STRIPE_PRO_MONTHLY_PRICE_ID. Check currency,
   amount and monthly recurrence against established commercial configuration.
   Do the same for STRIPE_PRO_ANNUAL_PRICE_ID if testing annual. **No verified actual Music
   Price ID or commercial amount is available from the reviewed configuration.**
   Free is the application's fallback plan and requires no Stripe Price. Do not
   invent prices or use Baseball IDs. If no existing Music Price exists, stop for
   the owner's approved catalog configuration.
2. In **Workbench -> Webhooks**, create the test endpoint only after the approved
   test host is available: `https://<verified-music-billing-test-host>/billing/webhooks/stripe`.
   Choose **snapshot** format and these six events: checkout.session.completed,
   customer.subscription.created, customer.subscription.updated,
   customer.subscription.deleted, invoice.paid, invoice.payment_failed. Store this
   endpoint's signing secret in STRIPE_WEBHOOK_SECRET on the billing service only.
   CLI listener secrets and hosted endpoint secrets are different configurations.
3. Record the account default API version used by GET subscription (the gateway
   sends no Stripe-Version header) and the webhook endpoint's snapshot version.
   Code supports legacy top-level and current item-level period ends, legacy
   invoice subscription and parent.subscription_details.subscription references.
   Verify actual fixtures for both recorded versions; do not silently change the
   account version. An explicit version pin is recommended before broader testing.
4. In **Settings -> Billing -> Customer portal**, save a test configuration enabling
   payment method management, invoice history and cancellation at period end.
   Initially disable plan switching; if later enabled, restrict it to existing Music
   prices. The backend supplies MUSIC_PUBLIC_BASE_URL as the return URL. No custom
   Portal configuration ID is currently sent; the test account's default is used.
5. Complete the first authenticated Checkout with Stripe's documented success test
   card and synthetic contact data. Verify the new Stripe customer was persisted
   before events and that a paid/active known-price subscription projects Pro.
   The success redirect is navigation only; it does not grant paid access.
6. In **Subscriptions**, use the test subscription's **Run simulation** workflow
   where supported to test renewal/failure/cancellation, and record the test clock
   context. Do not assume the Checkout-created customer is already clock-attached.
   Use a separately prepared trusted-mapped simulation account if needed; do not
   change an immutable mapping or rely on metadata to create one through a webhook.
   Test clocks advance Stripe, not the application wall clock: exact read-time
   expiry without a webhook is covered locally; real elapsed-time expiry requires
   a suitable short sandbox period. Verify delivered terminal events in simulations.
7. Use documented payment-failure fixtures, then replace with a success payment
   method and retry/pay the test invoice. In Workbench resend a processed event and
   an older event. Check persisted state, not event delivery order or invoice label.

Stripe behavior references: [Checkout](https://docs.stripe.com/api/checkout/sessions/create),
[webhooks](https://docs.stripe.com/webhooks), [Portal](https://docs.stripe.com/customer-management/integrate-customer-portal),
[subscription item periods](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end),
[Billing simulations](https://docs.stripe.com/billing/testing), [test payment fixtures](https://docs.stripe.com/testing).

## 4. Render configuration checklist

No render.yaml, Procfile, tracked Render service ID/hostname, or dashboard connector
is available. The **correct backend role** is a separate public web service running
`monetization_service:app`, not the existing Music Streamlit frontend. The exact
existing Render service/name/URL cannot be identified from repository evidence.
The owner must confirm service ID, repo/branch, region, URL and start command before
any configuration or deployment approval. Do not register a guessed webhook host.

| Service | Required approved test configuration |
| --- | --- |
| Billing backend | Python 3.12.8; build `python -m pip install -r requirements.txt`; start `python -m uvicorn monetization_service:app --host 0.0.0.0 --port "$PORT"`; health path `/billing/health` |
| Music frontend | Existing Streamlit app `streamlit_music_practice_app.py`; test-only URL; working verified Supabase login; matching public billing service URL |

Backend variables: MUSIC_BILLING_ROLLOUT, MUSIC_STRIPE_MODE, STRIPE_SECRET_KEY,
STRIPE_WEBHOOK_SECRET, STRIPE_PRO_MONTHLY_PRICE_ID, STRIPE_PRO_ANNUAL_PRICE_ID,
MUSIC_PUBLIC_BASE_URL, MUSIC_BILLING_SERVICE_URL, MUSIC_BILLING_SUPABASE_URL,
MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY, MUSIC_BILLING_SUPABASE_ANON_KEY.

Frontend variables: MUSIC_BILLING_ROLLOUT, MUSIC_STRIPE_MODE,
MUSIC_BILLING_SERVICE_URL, MUSIC_BILLING_SUPABASE_URL,
MUSIC_BILLING_SUPABASE_ANON_KEY, SUITE_AUTH_ENABLED, SUITE_AUTH_REDIRECT_URL,
SUITE_SUPABASE_URL, **SUITE_SUPABASE_KEY**, SUITE_SUPABASE_ANON_KEY.
Both rollout/mode must select test. UI must not receive Stripe/webhook secrets or
the billing service-role key. Disable local entitlement simulation in hosted tests: MUSIC_ENTITLEMENT_DEV_CONTROLS
must not enable overrides, and MUSIC_ENTITLEMENT_RUNTIME must not be local/test.
MUSIC_ENTITLEMENT_DEV_PLAN must not be used to simulate paid test evidence.

Use the **same Supabase authentication project** for both URL configurations and
keys; auth.users.id, not Suite profile/workspace ID, is billing identity. Add the
test frontend URL/redirect to Supabase Auth URL configuration; verify email-confirmed
users and refresh/login. Ensure necessary Suite storage/RLS already exists without
copying production user data.

Require health JSON showing test rollout/mode and checkout_enabled,
webhook_enabled, credentials_match_mode, monthly_price_configured and
supabase_configured true. Then verify actual authenticated endpoints and RPCs;
HTTP 200 health alone is insufficient. Public webhook POST must reach the backend
with original raw bytes and Stripe-Signature; no login proxy in front of it.
Expect unauthenticated Checkout/Portal to be rejected, invalid signatures to get
400, busy reconciliation to get 503, completed duplicates to get 200. Check service
cold starts/timeouts and dependencies on the pinned runtime before the first test.
[Render health-check semantics](https://render.com/docs/health-checks).

## 5. Two-user test plan and decision gate

Use separate confirmed auth accounts **A** and **B** in the isolated test project,
synthetic data, one initial Checkout each at most, and no production subscriptions.

| Test | Acceptance evidence |
| --- | --- |
| Baseline | A/B have distinct auth UUIDs; no paid row means Free; premium gates enforced |
| A Checkout | Verified JWT creates immutable A customer; one known-price test subscription; subscription/event/entitlement persisted atomically; A becomes Pro; B stays Free |
| Isolation | A SELECT sees only A entitlement; B sees only B; anon reads denied; both users' writes and all three mutation RPC calls denied; mismatched customer metadata rejected |
| Portal | A gets only A's fresh Portal session; missing/expired JWT rejected; a B customer ID in A's request is ignored; B cannot obtain A's session; Free B without mapping is denied |
| Retries | Replayed event stays processed without extra changes; older event fetches current state; concurrent delivery retries; killed worker lease is reclaimed; DB fault leaves no partial activation |
| Cancellation | A scheduled cancellation retains Pro strictly before end; end/deletion makes Free; immediate termination makes Free immediately; B unaffected |
| Renewal | New paid active period updates end and maintains Pro; trial/missing/unknown period behavior follows fail-closed policy |
| Failure/recovery | Actual past_due/unpaid yields Free; invoice failure while Stripe remains active does not force false downgrade; successful recovery to active restores Pro |
| Expiration | Missing terminal webhook still denies paid access at real period end; materialized row may be stale until reconciliation; simulated clock differences recorded |

Retain sanitized event IDs/statuses, timing, response codes and DB assertions;
exclude credentials and payment details. After migration approval run the existing
rollback SQL harness, then actual A/B JWT REST tests, then approve test hosting and
Stripe setup, then execute the above one scenario at a time. Stop on ownership,
RLS, atomicity, mode or state mismatch.

**GO only after** owner confirms the exact test Supabase project, schema preflight
review/backup, migration approval and DB/RLS checks, the actual existing Music test
Price(s), verified Render backend/frontend configuration, real auth/login, signing
and Portal settings, and Python 3.12 checks. Current recommendation remains
**NO-GO**; no external changes were made or authorized by this report.
