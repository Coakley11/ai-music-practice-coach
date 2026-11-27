# Music monetization Phase 2 - local review

## Branch and scope

Branch: `feature/music-billing-phase2-20261111`, based directly on verified
Phase 1 commit `f4d89eae7e7f2da3e67d2bb926d0e35b6dba7166`.
The Phase 1 branch and `20261111_music_customer_ownership.sql` are unchanged.
The existing isolated worktree was reused; unrelated Music work was untouched.
Nothing was pushed, deployed, or applied to a database. No Stripe API requests
were made. No secrets, customer records or payment details were read.

## Implemented behavior

- Creation, Checkout completion, renewal, payment failure/recovery and deletion
  reconcile the **current retrieved subscription**, not the delivered snapshot.
  Event timestamps and opaque IDs are audit fields, not causal ordering keys.
- Customer leases serialize provider reads across different subscription/event
  IDs for the same user. A busy lease returns HTTP 503 so Stripe can retry;
  abandoned leases expire after five minutes. Lease tokens fence stale workers.
- Event identity fingerprints detect conflicting reuse; completed events are
  no-ops. Delivery bookkeeping (`pending_webhooks`) is excluded from the hash.
  Legacy M2 payloads must match before adoption into the fingerprint ledger.
- One service-only RPC commits subscription state, the aggregate entitlement,
  processed-event state and lease release in one transaction. Failures roll back
  together. Provider/store failures are retriable. No raw error or new full event
  payload is stored in the ledger; legacy payloads are retained unchanged.
- Known Music prices are matched across subscription items; item-level period
  ends and legacy top-level ends are supported. Trial end and earlier cancel_at
  bound access. Paginated item lists fail closed pending explicit pagination.
- Scheduled cancellation preserves access until the exact end. Trusted paid
  entitlements are time-checked on access, including cached objects; database
  reads normalize expired plans to Free without requiring another webhook.
  This is an application downgrade: the materialized database row can remain
  Pro until the next reconciliation. There is no background database expiry job.
- Immediate cancellation/unpaid/incomplete/paused remove access. The existing
  conservative policy keeps past_due Free. A failed invoice does not itself
  override a subscription that Stripe still reports active. Recovery to active
  restores access within its current period.
- Deleting an obsolete subscription does not revoke another known valid paid
  subscription for the account. Migration backfills the previous trusted source
  projection; other preexisting subscriptions need provider reconciliation.
- Unknown customers cannot bootstrap paid ownership using metadata. Checkout's
  Phase 1 immutable binding remains the prerequisite.
- POST `/billing/portal` verifies the Supabase JWT and both directions of the
  persisted ownership mapping. Client body identifiers and return URLs are
  ignored. Stripe creates a fresh short-lived session; only its validated Stripe
  URL is returned with Cache-Control: no-store. The UI does not persist Portal
  URLs. Manage Subscription works for authenticated users, including Free users
  with an existing billing customer.
- Public UI readiness no longer requires Stripe or service-role secrets.
  Checkout, Portal and webhook paths are restricted to test mode; the HTTP
  gateway refuses live keys. Existing Music plans/prices/features are unchanged.

Baseball `fix/billing-lifecycle` supplied lease, owner-derived Portal and period
parsing patterns. Its unmerged branch was not imported. The Music transaction
also serializes provider reads per customer and reconciles multiple known
subscriptions rather than relying on event-ID ordering.

## Changed files

- `monetization_billing.py`: lease contract, reconciliation, policy and Portal.
- `monetization_supabase.py`: atomic RPC adapter and expiration normalization.
- `monetization_service.py`: test-only gateway, Portal route and webhook retries.
- `monetization_config.py`: separate public readiness and test-only API gates.
- `monetization_entitlements.py`: time-aware trusted access checks.
- `monetization_ui.py`: Manage Subscription and secret-free client readiness.
- `tests/test_monetization_m2.py`: explicit trusted customer/provider fixtures.
- `tests/test_monetization_phase2.py`: lifecycle, concurrency/retry and Portal tests.
- `supabase/migrations/20261112_music_billing_lifecycle.sql`: unapplied transaction RPCs.
- `scripts/sql_tests/music_billing_phase2.sql`: unexecuted, rollback-based DB checks.
- docs/MONETIZATION_M2.md: link to the superseding lifecycle/runbook.
- This report.

## Verification and limits

Sequential focused command:

```text
python -m pytest tests/test_monetization_phase2.py tests/test_monetization_customer_ownership.py tests/test_monetization_m2.py tests/test_monetization_entitlements.py -q
```

**85 passed**, final run 4.52 seconds. Coverage includes Free to Pro, renewal,
end-of-period cancellation/expiration without another event, immediate termination,
actual-status payment failure/recovery, duplicates, equal/older event timestamps,
conflicting payloads, concurrent different events, expired worker fencing,
pre-commit failure/retry, lost response after commit, old subscription deletion,
mode/ownership conflicts, owner-only Portal, forged body rejection and public UI
readiness. The signed HTTP webhook test proves busy deliveries get a retry status.

`git diff --check` passed. pglast parsed all 16 migration statements and all three
PL/pgSQL functions. The SQL verification script also parsed (four SQL statements,
one DO block, after substituting its psql parameter). Parsing validates syntax;
it does not establish database permissions, concurrency or runtime correctness.
The first parser pass prompted replacing composite-field assignments with scalar
variables. Initial Python checks exposed an import and old fixture assumptions;
these were corrected before the final passing suite. No unresolved local test
failures remain.

The single-RPC adapter and deterministic in-memory transaction behavior were
mock-tested. **No database transaction, RLS integration, real Stripe payment,
Portal session, test-clock renewal or deployed Render behavior is verified.**

RAM was checked with psutil: approximately 2.31-2.54 GB available, CPU 9-26%,
about 149 GB disk free. No browser, development server or heavy suite was started;
no unrelated process was stopped.

## Next steps - Supabase (approval required)

1. Confirm a test Music database and authentication authority. Billing token
   verification, Streamlit login and entitlement reads must use the same test
   Supabase project. Inspect existing generic billing table names before applying
   anything in a shared project. Do not use Baseball's migration/schema.
2. Review then approve application, in this order:
   - `20260927_monetization_m2.sql` if not already applied;
   - `20261111_music_customer_ownership.sql` (Phase 1, still unapplied here);
   - `20261112_music_billing_lifecycle.sql` (Phase 2, still unapplied here).
3. Coordinate the test service cutover: Phase 2 revokes service-role execution of
   the three obsolete non-atomic RPCs. Old billing service versions cannot remain
   active against the upgraded schema. Keep production untouched.
4. After migration approval/application, use a dedicated existing test auth user
   with no billing mapping to execute the rollback-only script:
   `psql <test-connection> -v test_user_id=<test-auth-uuid> -f scripts/sql_tests/music_billing_phase2.sql`.
   It checks immutable mapping, client privilege denial, exclusive lease, deliberate
   entitlement-constraint failure with no partial state, successful retry and
   duplicate/collision handling. It rolls all fixture writes back.
5. Verify actual anon/authenticated REST writes and mutation RPC calls are denied;
   user A can SELECT only A's entitlement and cannot access B's row. The existing
   RLS migration supplies this policy, but deployed policy behavior remains untested.
6. Replay current test subscriptions after cutover to refresh legacy projections.
   Confirm service-role execution through PostgREST, lease expiry/reclaim under
   concurrent requests, atomic rollback and processed replay in the real database.

## Next steps - Render (separate test services, approval required)

Billing service start command:
`python -m uvicorn monetization_service:app --host 0.0.0.0 --port "$PORT"`.
Use the repo's requirements and an HTTPS service URL. Keep rollout and Stripe mode
in test. Existing production billing/services remain untouched.

Billing service variable names:

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

Streamlit test service needs only the public billing rollout/mode, service URL,
Supabase URL/anon key and its existing Suite auth configuration. Relevant existing
auth variable names include SUITE_AUTH_ENABLED, SUITE_SUPABASE_URL,
SUITE_SUPABASE_ANON_KEY and SUITE_AUTH_REDIRECT_URL. It must not receive the Stripe
secret, webhook secret or billing service-role key. Check billing health, verified
login, public Checkout readiness, entitlement reads and Portal navigation. Ensure
the service is responsive within client timeouts; cold-start behavior is untested.

## Next steps - Stripe (sandbox/test mode only)

1. Confirm the existing Music monthly/annual recurring Price IDs and account;
   do not create replacement commercial pricing or reuse Baseball's price.
2. Register a snapshot webhook endpoint at the test billing service's
   `/billing/webhooks/stripe`, using that endpoint's test signing secret. Subscribe
   to checkout.session.completed, customer.subscription.created/updated/deleted,
   invoice.paid and invoice.payment_failed. Retain the configured snapshot API
   version and verify fixture compatibility with actual delivered payloads.
3. Configure the test Customer Portal for invoice/payment management and the
   intended cancellation policy. If plan switching is enabled, restrict it to the
   existing Music monthly/annual prices. Sessions use the configured Music return URL.
4. Complete Checkout from a new authenticated test user. Confirm the immutable
   customer binding precedes webhook processing and that the correct price activates
   Pro only through reconciliation. Exercise the annual interval through the
   authenticated API as well; existing UI still offers the monthly Checkout button.
5. With Stripe test clocks/test fixtures, verify renewal, scheduled cancellation
   and exact expiration, immediate termination, failed payment and recovery.
   Resend duplicate/older events and simulate an interrupted database response.
   Verify Portal ownership using two signed-in accounts. Do not interpret mocked
   tests or this runbook as proof that any real integration request succeeded.

## Remaining blockers

Before a real test subscription can complete: approved test schema application,
real database/RLS verification, matching auth configuration, responsive HTTPS test
billing/UI services, existing test prices, webhook signing/delivery and test Portal
configuration. No credentials or service state were inspected in this assignment.

Before production: review the above end-to-end evidence; implement customer and
Checkout idempotency/duplicate-subscription prevention (still inherited gaps),
operator reconciliation for permanently lost events, monitoring/retry procedures,
complete server entitlement enforcement across the catalog, any paginated or
multiple-known-price item policy, and commercial tax/refund/support decisions.
Read-time expiration fails closed if renewal events are lost; no periodic Stripe
reconciliation worker or automatic physical database expiry writer exists yet.
Live mode is deliberately unavailable in this local increment and requires a
separate reviewed change and launch approval.

References used for behavior review:
[Stripe webhooks](https://docs.stripe.com/webhooks),
[Customer Portal](https://docs.stripe.com/customer-management/integrate-customer-portal),
[item-level billing periods](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end).
