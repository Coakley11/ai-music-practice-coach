# Hosted Supabase recheck — November 27, 2026

Branch: feature/music-billing-resume-20261127.
Committed baseline: 70ecd90007460ad44d106e96f3a8417cdaaefaff.

The isolated project smpyutzfktjgpdibdbqb accepted both existing API keys after
being resumed: GET Auth settings and GET admin users returned HTTP 200.
The same guarded checks had failed before resumption. This is consistent with
the paused project causing the connectivity failure, not a demonstrated invalid
key/JWT defect. The earlier exception was deliberately suppressed, so exact
historical network failure attribution cannot be proved.

The exact URL and both legacy key project/role claims were checked before any
requests. The client pins the isolated HTTPS origin, disables redirects and
inherited proxies, and keeps TLS validation enabled. No production Suite key or
URL was used. Render specs and staging guards point only to the isolated project;
existing production Music/Suite authentication settings were not modified.

Existing synthetic accounts were inventoried using read-only admin access.
Their passwords were ephemeral in the old harness and were not retained; no
password reset or email-link action was performed to reuse them. The hosted
rehearsal therefore uses two fresh synthetic accounts under run 93531926c52e.
Retained customer and entitlement records are compared in memory before/after;
no identifiers, credentials or raw payloads are logged by the added wrapper.
The wrapper reuses the existing tested Phase 6 implementation without reinstalling
schema. No Stripe request is made. New synthetic fixtures remain retained.

## Hosted result - PASS

Run 93531926c52e completed with exit code 0 against the existing installed schema:

- Two fresh synthetic password sign-ins and real JWT identity checks passed.
- Concurrent immutable customer binding produced one winner; cross-owner reuse failed.
- Concurrent Checkout reservations were identical; event leases were exclusive.
- Released lease token completion failed specifically with the ownership guard.
- Ten lifecycle projections passed: activation, renewal, scheduled cancellation,
  expiration, recovery, immediate cancellation, failed payment, recovery and an
  older notification reconciled from a fresh snapshot.
- Every owner entitlement read and cross-user RLS denial matched expectations.
- Duplicate events were ignored; all five backend RPCs rejected anon and both users.
- Raw private-table reads, scoped writes and self-upgrade attempts were denied.
- All pre-existing synthetic Auth accounts still exist; retained customer and
  entitlement records were unchanged. Raw subscription/event snapshots are not
  available to the restricted service role; no mutation request targeted old fixtures.

Owner-level coverage was subsequently completed as recorded below.

## Owner SQL review and successful hosted verification

Reviewed scripts/sql_tests/music_billing_shared_roles.sql and
music_billing_lifecycle_rehearsal.sql in full. Both end in ROLLBACK and limit their
objects to Music billing tables/functions plus simulated Auth claims. No DROP,
reinstallation, Auth deletion, Suite/Baseball table operation, grant change or
production connection is present. They contain deliberate permission-denial
INSERT/UPDATE/DELETE/TRUNCATE attempts under anon/authenticated/service_role.
An unexpected success raises an exception and aborts the transaction; these are
not cleanup statements. The role test temporarily adds a failure-injection
constraint, also rolled back, to verify atomic completion failure.

Owner execution subsequently PASSED, as reported by the user from the isolated
project SQL Editor on November 27. The user confirmed project smpyutzfktjgpdibdbqb
and returned the exact result from music_billing_sql_editor_owner.sql:

    PASS: owner harnesses completed; rollback left no test fixtures or constraint

This is owner-reported hosted evidence, not an execution observed by this agent.
The combined SQL Editor script adapts the reviewed role/lifecycle harnesses, checks
fresh synthetic UUIDs and fixture collisions, tests roles and atomic completion,
rolls back the role fixtures to a savepoint, runs lifecycle tests, then ROLLBACKs
and checks no fixture identifiers/temporary constraint remain. The owner-SQL gate
is now satisfied on this evidence; do not repeat it or reset retained records.

## Local validation

133 focused billing/SQL-preparation/security tests passed in 9.59 seconds.
Wrapper compiled successfully. Available RAM sampled at 2.60 and 2.37 GiB.
No browser session, server, package installation or heavy test suite was started.
No branch push, merge, deployment, Stripe change or production modification ran.
The reports and scripts are being committed as a separate staging-preparation commit. Existing tracked application code and other agents' work are untouched.

## Recommendation

GO for a separately approved push of the tested baseline and preparation of a
health-only Render deployment. Health-only must omit all Stripe/return URL settings,
use isolated Supabase keys, test rollout/mode and require Checkout/webhook disabled.
Actual deployment is not authorized by this assignment and was not begun.

NO-GO for billing-enabled deployment or sandbox payment:
exclusive Music-vs-Baseball sandbox provenance, endpoint signing secret, actual
Render Python 3.12.8 build and hosted health/webhook verification remain pending.

Next owner action: approve the exact staging-only push after final local commit
verification. Render deployment requires separate approval. No payments are enabled.
