# Phase 6C hosted synthetic rehearsal results

Date: 2026-11-12 (America/New_York).

## Outcome

**PASS: the guarded hosted Auth/JWT/PostgREST, entitlement projection, lifecycle,
retry and two-worker concurrency rehearsal completed against the isolated project
smpyutzfktjgpdibdbqb.** This supersedes the credential-blocked checkpoint in
MONETIZATION_PHASE6C_LOCAL_CONFIG_20261112.md. The Phase 6B schema was reused;
no installation, database migration, production service change or Stripe call ran.

The protected qhprdlwoxjpkiukxhftp Suite project was never a request destination.
Baseball, Render and deployed Streamlit applications were not modified. No push,
merge, live charge or subscription modification occurred.

## Configuration verified without credential disclosure

The user populated the new private file in the billing worktree:
`.music-phase6-blank.local.json`. The original `.music-phase6.local.json` was
preserved after a copying mistake. Both files are Git-ignored and untracked.
The additional ignore rule covers new blank configuration siblings. No key value,
Auth password, access JWT or raw Auth/billing response was logged or committed.

Verification proceeded in this order:

1. --check-config passed: exact isolated URL plus both legacy JWT project/role
   claims matched. File credentials were not exported as shell variables.
2. --verify-access passed: Supabase accepted the anon key on GET /auth/v1/settings
   and the service-role key on GET /auth/v1/admin/users. These were read-only calls.
3. The synthetic suite repeated both checks before any account creation.

Initial sandbox networking was blocked; the same authorized pinned-origin command
succeeded outside the sandbox. TLS validation stayed enabled, redirects remained
disabled and no proxy override or alternate project URL was introduced.

Private config is local plaintext, not encrypted. Keep it private and out of shared
or synced folders. Do not paste keys into chat. The harness accepts only legacy JWT
API keys; support for Supabase's newer opaque keys remains a separate future change.
See https://supabase.com/docs/guides/getting-started/api-keys for their lifecycle.

## Hosted executions and correction

Initial synthetic run: **8254ab8cbaf9**. It completed account/JWT, concurrent
ownership/reservation/lease, ten lifecycle projections, duplicate delivery and
cross-user read checks, then stopped at the anonymous webhook-table PATCH denial
assertion. It was **not** reported as a full pass.

Diagnostics returned only table names, HTTP status and SQL error code:

| Anonymous PATCH probe | HTTP | SQL code |
| --- | --- | --- |
| customers, nonexistent UUID filter | 401 | 42501 |
| subscriptions, nonexistent UUID filter | 401 | 42501 |
| webhook_events, no row filter | 400 | 21000 |
| webhook_events, synthetic event filter | 401 | 42501 |
| entitlements, nonexistent UUID filter | 401 | 42501 |

The hosted unfiltered-update guard preempted the expected ACL-specific response.
The harness now scopes every PATCH to a synthetic fixture; webhook_events uses
the run's existing final event ID. The assertion still requires 401/403. No grant,
RLS policy, SQL function, installed object or application entitlement rule was
weakened or changed. Failure labels now identify actor/table/status without secrets.

Successful full rerun: **bb34d5f5e536**, exit code 0. Observed stages:

- Both isolated keys accepted in read-only checks.
- Two synthetic Auth accounts created, password sign-in succeeded, and real access
  JWTs resolved to the expected account through GET /auth/v1/user.
- Both users initially read no entitlement record (Free fallback).
- Two simultaneous competing bindings for the same user produced exactly one
  successful immutable mapping and one conflict. Sharing the winner's customer
  with the second user was rejected.
- Two simultaneous Checkout reservation RPCs returned the same token/expiry.
- Two simultaneous event claims produced one lease and one busy response.
  Lease release succeeded and stale completion was rejected.
- Ten subscription snapshots persisted via actual hosted PostgREST RPCs: activation,
  renewal, scheduled cancellation retaining Pro, expired/canceled snapshot to Free,
  activation, immediate cancellation to Free, activation, past_due to Free,
  recovery to Pro and an older notification reconciled from a supplied current
  snapshot. Owner JWT reads matched each expected plan/status.
- The other account could not read the owner's entitlement at every transition.
- Every completed event replay returned the duplicate/ignore result.
- Anonymous and both authenticated actors were denied execution of all five
  backend RPCs, raw billing reads, scoped PATCH writes and paid-status changes.

The released-lease test was additionally strengthened: its projection is now fully
valid and must fail with P0001 / Customer lease ownership lost, not merely any HTTP
400. A dedicated supplemental hosted probe used the successful run's existing
synthetic account/subscription and a new synthetic event. It passed this exact
guard check and confirmed that the current Pro/active entitlement was unchanged.
It created no additional Auth account. The complete suite ran before this assertion
strengthening; the changed assertion was separately executed hosted afterward.

## Retained data and recovery

Aggregate Auth inspection confirmed **two synthetic accounts for each run**, four
total from this assignment. All are marked with music_phase6_synthetic metadata
and use random credentials/example.invalid emails. Both runs' synthetic Music
records were preserved; no account/record deletion or owner rebinding was attempted.
The supplemental lease event is `evt_music_phase6_bb34d5f5e536_lease_guard_probe`.

Keep these run IDs for review. Do not rerun blindly: another run creates another
pair. Cleanup requires explicit, run-scoped review of the synthetic accounts and
their Music records; do not drop tables, rerun the installer, reset mappings or use
broad deletes. Failed claims can recover by the established lease/retry mechanism.

## Verified boundaries and remaining work

**Verified hosted:** real Supabase key acceptance, Auth sign-in/JWT identity,
PostgREST RPC exposure and persistence, owner-only entitlement reads, ordinary-role
RPC/PATCH denials, customer conflicts, scoped concurrency, synthetic subscription
projections, duplicate suppression and specific released-lease enforcement.

**Still untested hosted in this phase:**

- Actual Stripe Checkout/payment/renewal/cancellation, signing verification,
  Customer Portal and fetching fresh provider state. All provider IDs and snapshots
  above are fixtures; no real Stripe request or card was used.
- Deployed Music backend endpoints, UI/login integration, Render configuration,
  actual premium-feature enforcement and wall-clock expiry without a new snapshot.
- The separate owner-run SET ROLE/SQL harnesses and deliberate hosted installation
  rollback/failure injection. These remain locally verified from prior phases;
  REST evidence does not replace those SQL checks.
- Actual INSERT/DELETE/TRUNCATE attempts through hosted owner SQL. PATCH/RPC
  denials were executed through REST; table privilege inspection was Phase 6B.
  PostgREST does not provide a generic TRUNCATE endpoint.
- Load/stress testing, every possible interleaving, and compatibility with the
  protected Suite project's existing data/defaults/auth triggers.

**GO for the next separately scoped Stripe test-mode/backend integration step.**
No production/shared-project installation or production launch is approved by this
result. Remaining prerequisites include the actual Music recurring test Price ID,
explicit test Portal configuration, six-event snapshot webhook/signing secret,
matching Stripe API pin and approved backend hosting with the same isolated Auth
authority. Preserve the shared Suite and Baseball architecture until separately
reviewed and approved.

## Local validation and resources

The denial-filter fix and strengthened error-specific lease test have focused local
regression coverage. Final verification: **141 passed in 8.00 seconds**, no skips
or unresolved failures, using the six focused test files listed in the Phase 6C
configuration report and an assignment-specific ignored pytest basetemp.
Resource samples: 2.62 GB free RAM / CPU 66.6% before hosted execution; 2.01 GB /
CPU 16.4% afterward, 141.37 GB free disk. Local Python is 3.13.7; the deployment's
Python 3.12.8 runtime remains a separate integration check.
No browser or server was launched. HTTP concurrency was limited to two workers;
focused Python tests and hosted runs were sequential. A scratch diagnostic file
could not be written into a sandbox-owned cache from the external process, so the
sanitized probe ran directly without creating that file. Unrelated debug.log was
left untouched and excluded from commits. No secrets file was staged.
