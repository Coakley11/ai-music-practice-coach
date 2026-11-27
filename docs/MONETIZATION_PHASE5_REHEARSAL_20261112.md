# Phase 5 database installation rehearsal â€” 2026-11-12

## Scope and compatibility

Base: `a822cf84cc9b4032540187f0a1b344774ba7155b`. No hosted database,
Stripe, Render, secret, deployment, push or merge changes are authorized here.
The standalone file `supabase/install/20261112_music_billing_shared_install.sql`
replaces the historical three-migration sequence for a fresh shared-project install.
Do **not** run those generic migrations before or after this installer.

User-supplied shared-project preflight confirms the Music namespace is available,
Baseball/Suite records exist, and shared defaults are broad. That is compatibility
with the reported catalog, not independent verification of the complete live schema.
Before approval, obtain current preflight output, database version, auth.users UUID
primary/unique key, auth.uid(), API-role attributes/membership and public-schema
CREATE privileges. Custom event triggers, role inheritance, schema exposure and
managed Supabase restrictions remain hosted checks.

The installer wraps DDL, ACL cleanup and assertions in one transaction with an
advisory installation lock and short timeouts. It rejects existing Music objects
rather than adopting or replacing them. It creates four tables, six functions
(five service RPCs plus one trigger function), one application trigger and one
owner-read policy. All application object names have the Music prefix. The only
non-Music relation dependency is auth.users; new foreign keys create internal RI
triggers there. Existing application signup triggers are not replaced. No Baseball
or Suite table/function is a write target. Broad defaults are removed from the new
objects only; global defaults and existing Suite privileges stay unchanged.

## Reproduce locally

Use a disposable native PostgreSQL 17 installation and Python with psutil:

```powershell
$env:MUSIC_TEST_PG_BIN = 'C:\Program Files\PostgreSQL\17\bin'
python scripts/rehearse_music_billing_postgres.py
```

The runner accepts no database URL. It initializes a fresh temporary cluster,
listens on 127.0.0.1 with a dynamically selected port, uses 16 MB shared buffers
and five connections, runs serially, and stops its own cluster in finally.
Temporary cluster/log files remain for diagnosis; they contain only synthetic data.
Trust authentication is confined to this short-lived localhost rehearsal; do not
reuse its configuration for a persistent or network-accessible database.
It requires at least 1 GB free RAM; no browser suite is involved.

It simulates auth.uid() via request settings, two synthetic Auth UUIDs, anon,
authenticated and BYPASSRLS service_role, broad table/function defaults including
an extra grantee, and protected Baseball/Suite objects with RLS and synthetic rows.
The role harness executes real denied reads/writes/TRUNCATE/RPC attempts, owner-only
entitlement reads, service RPC completion, duplicate/collision handling and atomic
failure recovery. Extra checks exercise customer rebind, shared-customer rejection,
the immutable ownership trigger, early namespace collision, late injected failure,
and replay rejection. Protected rows, custom triggers, functions, ACLs, RLS,
policies and defaults are compared before/after. These are representative fixtures,
not a clone of the live schema.

## Isolated hosted test plan â€” approval required

1. Confirm the dashboard project reference is **smpyutzfktjgpdibdbqb**, not qhpr...
   Obtain explicit approval for test-project SQL and synthetic account writes.
2. Run the consolidated read-only preflight there. Verify roles/auth dependencies,
   namespace availability and installer-owner privileges. Save metadata/backup.
3. Create two synthetic Auth accounts through Supabase Auth only. Use no existing
   Music/Baseball identities, compositions, customer IDs or payment records.
4. Apply the exact standalone installer as a single transaction in SQL Editor.
   Stop on any failure; never skip a precondition or run partial statements.
5. Run scripts/sql_tests/music_billing_shared_roles.sql with those two UUIDs in
   psql as the approved database owner. It rolls back its fixture changes.
6. Separately use actual user JWTs and the backend service key through PostgREST:
   verify owner-only reads, denied paid-status writes/RPCs/TRUNCATE-equivalent SQL
   privileges, service-only atomic RPCs, and refreshed schema-cache signatures.
   JWT verification, Auth lifecycle and PostgREST are not simulated by local SQL.
7. Test concurrent Checkout/event claims, lease timeout/retry, provider refresh for
   out-of-order events, and all application lifecycle tests. SQL cannot independently
   establish that a provider projection is current; the trusted backend fetches it.
8. For browser/login tests use matching isolated Auth and billing URLs/keys plus
   approved test redirects. The empty project does not contain Suite app tables;
   prepare separately approved Suite dependencies or a billing-only test client.
   Do not redirect deployed Music or existing users to the empty project.

## Shared-project readiness checklist â€” separate approval required

- [ ] Successful isolated hosted tests and matching Python 3.12.8 runtime tests.
- [ ] Re-run all 27 preflight sections against **qhprdlwoxjpkiukxhftp**; save results.
- [ ] No Music prefix collisions; required roles, schema permissions, UUID key and
      auth.uid present; no untrusted CREATE, BYPASSRLS or service-role membership.
- [ ] Review complete auth triggers, dependencies and event triggers; confirm
      installer transaction permitted and public Music RPCs exposed as expected.
- [ ] Record protected object definitions, grants, policies, defaults, row counts
      and a recoverable backup/PITR point. Account for legitimate activity changes.
- [ ] Pause Music billing ingress/Checkout only; preserve Music saves and Baseball.
- [ ] Approve exact script/hash, owner, target project and maintenance window.
- [ ] Execute whole standalone transaction once. A collision means stop and review.
- [ ] Verify four RLS tables, six functions, five backend-only RPC grants, one owner
      SELECT policy, no ordinary direct writes/DELETE/TRUNCATE and expected backend
      SELECT only on customers/entitlements. Verify extra default grantees removed.
- [ ] Compare protected metadata/data, including existing signup trigger definitions.
      Distinguish expected internal auth FK triggers from application trigger changes.
- [ ] Use existing approved synthetic shared accounts for JWT A/B checks. Creating
      shared Auth users can invoke Baseball signup triggers; review separately.
- [ ] Confirm matching backend adapter and Auth authority, fail-closed entitlements,
      portal owner checks, provider reconciliation and read-time expiry.
- [ ] Complete one actual Stripe test-mode lifecycle before considering production.

Recovery: failed installation rolls back all new objects. Do not rerun after success.
After records exist, pause Music billing and fix forward while preserving customers,
subscriptions, event ledger and entitlements. Never drop billing tables, reset owner
bindings, delete Auth users or restore old billing snapshots over newer subscriptions.
Any restore needs an approved provider-event reconciliation/replay plan. Rollout OFF
opens premium access in the existing implementation; it is not a fail-closed rollback.

The reported Suite TRUNCATE/default-grant risk remains separate. RLS does not protect
TRUNCATE. Follow docs/SUITE_PRIVILEGE_HARDENING_PROPOSAL_20261112.md in an isolated
clone before requesting targeted shared-table privilege changes. The shared service
key still has broad project authority; Music table ACLs do not isolate that credential
from Baseball/Suite data.

## External prerequisites still unverified

Stripe: actual Music recurring monthly **test** Price ID (annual optional), matching
existing Pro commercial terms, sk_test key, Music-specific bpc_ Portal configuration,
and webhook signing secret. Configure the approved backend `/billing/webhooks/stripe`
for snapshot events checkout.session.completed, customer.subscription.created,
customer.subscription.updated, customer.subscription.deleted, invoice.paid and
invoice.payment_failed; match code's Stripe API version `2026-10-28.endive`.
No real Stripe test request was performed in this assignment.

Render: exact Music ASGI backend service/URL and deployed commit remain manual
checks. Start command: `python -m uvicorn monetization_service:app --host 0.0.0.0 --port "$PORT"`.
Confirm Python 3.12.8, requirements, HTTPS webhook route and `/billing/health` response;
health reports configuration, not successful database/Stripe integration.
Backend environment names:
MUSIC_BILLING_ROLLOUT, MUSIC_STRIPE_MODE, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
STRIPE_PRO_MONTHLY_PRICE_ID, STRIPE_PRO_ANNUAL_PRICE_ID, MUSIC_PUBLIC_BASE_URL,
MUSIC_BILLING_SERVICE_URL, MUSIC_BILLING_SUPABASE_URL,
MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY, MUSIC_BILLING_SUPABASE_ANON_KEY,
MUSIC_STRIPE_PORTAL_CONFIGURATION_ID. Use test mode only. Frontend Auth configuration
must match the billing authority: SUITE_AUTH_ENABLED, SUITE_SUPABASE_URL,
SUITE_SUPABASE_KEY, SUITE_SUPABASE_ANON_KEY, SUITE_AUTH_REDIRECT_URL. Keep service
secrets backend-only. Review disabled entitlement overrides.

## Observed results and decision

**GO for an explicitly approved isolated Supabase test. NO-GO for shared-project
installation or production launch at this checkpoint.** The installer required no
correction. Local engine execution is verified; hosted database execution is not.

PostgreSQL 17.9 executed the unchanged installer successfully. The role harness and
ten SQL lifecycle transitions passed, including scheduled cancellation retaining
Pro, expiration/termination removing it, failed payment removing it, recovery,
renewal, older-notification reconciliation using the current snapshot, duplicate
ignore and customer-lease exclusion. This is sequential lease contention simulation,
not a simultaneous multi-connection race test. Read-time expiration without a new
webhook is enforced in the application and covered by Python tests; stored Pro
rows do not automatically rewrite themselves just because wall time advances.

The late injected exception and early collision both rolled back installation;
a repeated installation was rejected without changing existing fixtures. Synthetic
Baseball/Suite/Auth rows, custom triggers, function definitions, table grants/RLS,
policies and default privileges matched before/after. This does not assert live
catalog equality, which must be checked on the hosted target.

Focused validation: **105 passed** (11.09 seconds, local Python 3.13.7):
`python -m pytest -q tests/test_music_billing_shared_install.py tests/test_monetization_customer_ownership.py tests/test_monetization_m2.py tests/test_monetization_entitlements.py tests/test_monetization_phase2.py`.
No skips or failing application tests. Python 3.12.8 remains a deployment check.

An initial Windows pipe-capture stall in the new runner was fixed, and only that
assignment-created cluster was stopped. A later attempt stopped before initialization
because free RAM fell below 1 GB; retry at 2.01 GB passed, ending at 2.01 GB.
Final runner recheck passed at 2.15 GB free RAM, ending at 1.99 GB, and confirmed
its disposable cluster stopped. Other resource samples: approximately 1.1?2.15 GB free RAM, CPU 14?98%, 144?147 GB
free disk. No browsers, heavy suites or external service calls were used. Existing
PostgreSQL services and unrelated processes were left untouched.

Remaining hosted differences: managed owner versus local superuser; real role
memberships/default grants and event triggers; actual auth.uid/JWT claims and Auth
signup triggers; PostgREST RPC exposure/cache, grants and error mapping; hosted
PostgreSQL version/extensions; network/service credentials; simultaneous concurrency;
Stripe's real responses, delivery ordering/retries, Portal and test payments.
The concrete next external step is approval to run the read-only consolidated
preflight in smpyutzfktjgpdibdbqb, then approve its synthetic Auth accounts and the
single standalone installation transaction. No shared-project write is the next step.
