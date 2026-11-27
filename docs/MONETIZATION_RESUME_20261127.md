# Music billing resumption ? 2026-11-27

Current update: hosted Auth/JWT/PostgREST checks passed after project resumption.
The user subsequently confirmed the owner-SQL Editor harness PASS with rollback
and no retained test fixtures/constraint. See MONETIZATION_HOSTED_RECHECK_20261127.md
and MUSIC_RENDER_HEALTH_ONLY_READY_20261127.md for current gates and next actions.
The baseline recovery details below are historical as of initial reconciliation.

Decision: local reconciliation passes; no deployment or payment authorized/executed.

## Baseline and preservation

Recovered source: feature/music-billing-staging-20261112 at
98712cc23d0bf3e1671e3f5da06f236161035462, including the supplied Phase 6C,
Phase 7 and Stripe inspection checkpoints plus the later health-only handoff.
Its tracked worktree was clean. Private ignored configuration remains there;
no keys were copied into the resumed worktree.

Remote GET (git ls-remote) confirmed dev=db317f3f7c295f2abc197d5065203f7b12bac3b1
and main=377e7192fde5c6ba4ec618e91028c5c0202c6235. No remote staging branch
was returned. Local dev=b86c862a and main=5ef2dead are not the remote baseline.
The old staging branch has 16 unique commits; remote dev has 612 since their
common ancestor b25cafc1d8dd601093b0e2482e00fe3e840b47c0. All 16 billing
commits remain outside remote dev ancestry. Current remote refs contain no
newer changes to the audited monetization implementation since November 13.

New isolated branch: feature/music-billing-resume-20261127, based on remote dev.
Reapplied the exact existing billing delta from the common ancestor, without
merging branches. git apply --check passed and merge-tree compatibility calculation
reported no conflicts. Updated both Render specifications to the resumed branch.
The old branch, worktrees, synthetic records and ignored credentials are preserved.
No dev/main branch was changed. No push or branch merge occurred.

suite_auth_browser.py, suite_storage_supabase.py, suite_security_module_refresh.py
and streamlit_music_practice_app.py remain identical to remote dev. This preserves
f2e9e7fc (disable suite_sid URL restore), 1ac5e917 (refresh fixed modules in running
Cloud processes), d29b96dc (isolated module-refresh test), and later Music changes.
Do not deploy the old branch as a Streamlit app or merge it wholesale into dev.
The new backend remains monetization_staging:app wrapping monetization_service:app.

## Verification

- Original billing branch: 174 focused tests passed in 6.12s.
- Reconciled current-dev branch: 184 billing/security tests passed in 16.09s.
- Initial pytest default temporary directory caused 12 setup permission errors;
  rerun with workspace-local --basetemp passed. No code defect was indicated.
- Security/app files unchanged relative to remote dev; git diff --check passed
  for tracked modifications before report creation.
- Real read-only Stripe GET inspection succeeded under API 2026-10-28.endive:
  acct_1Ub8HEGSM5yahQur, active non-live monthly Price
  price_1Ub8MiGSM5yahQursL7MlBcs, usd 1499, licensed, monthly interval_count=1.
  Music Practice Coach Pro product is active/non-live; app metadata absent.
- Portal bpc_1Ub8nFGSM5yahQurK0dnmcGe remains active/non-live/default,
  unnamed and untagged. Period-end cancellation, payment-method updates and
  invoices enabled; subscription updates disabled. unique_music_portal_id=null.
  Exclusive Music sandbox ownership and Baseball separation remain unverified.
- Supabase ignored config passed exact isolated URL and anon/service_role JWT
  project/role checks. Hosted GET-only acceptance failed even with network access;
  response/credentials suppressed. This is not evidence of database corruption.
- No owner SQL connection configuration was established; psql was not found.
  Hosted owner regression scripts have NOT passed in this continuation.
- RAM available sampled at 2.50 and 2.41 GiB; no browser or server was started.

## Remaining gates

1. Restore/confirm access to authorized smpyutzfktjgpdibdbqb (check dashboard
   project status), establish private owner SQL access and use two fresh synthetic
   Auth users without billing records. Run scripts/sql_tests/music_billing_shared_roles.sql
   and music_billing_lifecycle_rehearsal.sql with ON_ERROR_STOP and confirm
   ROLLBACK, zero user billing fixtures and no temporary constraint. Preserve Phase 6
   records. Never use protected qhprdlwoxjpkiukxhftp or change Music Suite login.
2. Confirm acct_1Ub8HEGSM5yahQur is the exclusive Music general sandbox and
   Baseball uses a different scope. Only then select the existing Portal explicitly;
   otherwise obtain approval for a new non-default Music-only configuration.
3. Separately approve push of the reconciled branch, then a new Free health-only
   Render service. No shared env groups. autoDeployTrigger=off, Python 3.12.8,
   requirements-billing.txt, one worker, no access log, /billing/health. Render docs
   still support fully qualified released versions from 3.7.3 onward. Actual 3.12.8
   build, free quota, hosted URL and health response remain unverified.
4. First boot uses only test rollout/mode and isolated Supabase URL/anon/service-role
   secrets plus PYTHON_VERSION; omit Stripe/return URL settings. Health must show
   checkout/webhook disabled. Existing guard rejects live keys, production project
   claims and SUITE_* variables. Health does not prove provider reachability.
5. After approved deployment, configure a separate Music snapshot webhook at
   /billing/webhooks/stripe, version 2026-10-28.endive: checkout.session.completed,
   customer.subscription.created/updated/deleted, invoice.paid, invoice.payment_failed.
   Store endpoint-specific whsec privately. Do not alter account-wide API defaults.
6. Later secure environment: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
   STRIPE_PRO_MONTHLY_PRICE_ID, MUSIC_STRIPE_PORTAL_CONFIGURATION_ID,
   MUSIC_PUBLIC_BASE_URL, MUSIC_BILLING_SERVICE_URL. Annual stays omitted.
   Full environment contract remains in the Phase 7 report. No secrets in Git/logs.
7. Only after owner SQL, isolation, hosted runtime/health and signed delivery pass,
   separately approve sandbox transaction with fresh synthetic users: Free -> Checkout
   (repeat returns same reservation/session) -> test payment -> signed webhook ->
   subscription/Pro -> Portal -> period-end cancellation and renewal/retry checks.
   Verify cross-user denial, duplicate/reordered delivery and failed-payment access.

Checkout retains immutable customer ownership, per-user hashed customer idempotency,
persisted one-hour Checkout reservation, leases, provider reconciliation, signed raw
body HMAC with 300-second tolerance, and fail-closed unpaid/expired access. Local
regressions pass; end-to-end hosted behavior remains unproven.

Readiness: reconciled source is suitable for an approved staging-only push after
local commit verification; billing-enabled deployment and payment remain NO-GO.
No external state was changed by this continuation.

Single next owner action: open the isolated Supabase project dashboard and confirm
that smpyutzfktjgpdibdbqb is active/reachable (resume it if paused), enabling the
pending owner-SQL gate. Do not share database passwords or API keys in chat.

References checked: https://render.com/docs/python-version,
https://render.com/docs/blueprint-spec, https://docs.stripe.com/webhooks.
