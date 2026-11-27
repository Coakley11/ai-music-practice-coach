# Phase 6: hosted Supabase rehearsal package

## Decision and observed evidence

**Hosted Stage A: UNVERIFIED. Hosted Stage B: NOT EXECUTED.** No hosted database,
Auth, PostgREST, Stripe, Render or protected Suite request was made. No production
configuration was changed. Dashboard access and usable Supabase credentials were
not available through the checked local configuration/environment or a Supabase
connector. The task's manual-instructions fallback therefore applies.

**GO for the operator to perform isolated read-only Stage A. NO-GO for installation
until every Stage A criterion below passes. NO-GO for Stripe integration until the
hosted installation, role, JWT/PostgREST and concurrency checks pass.** No conclusion
about hosted success can be inferred from local tests.

Base branch/commit verified: feature/music-billing-db-rehearsal-20261112,
42988c4694383b2a30eeedb02c853094ad0db40d; initially clean.
The standalone installer is unchanged from the locally rehearsed version:

- File: `supabase/install/20261112_music_billing_shared_install.sql`
- SHA256, existing Windows CRLF bytes:
  `bc635078cd234c21c61e3228d587087cbe70374dcb4933e31902d8ceec422ce4`
- SHA256 after CRLF-to-LF normalization (used by the portable API harness):
  `35c2d92f76d5b6012bfff4efc59d47893153c7660268e76c2086673e71b3c577`

The different line-ending hashes do not represent a SQL change. Do not edit the
installer or substitute the historical three generic migrations.

## Stage A: operator-only read-only procedure

1. Open the Supabase dashboard project. Independently compare its URL/project
   reference with Settings > API's Project URL: both must identify
   **smpyutzfktjgpdibdbqb**, `https://smpyutzfktjgpdibdbqb.supabase.co`.
   SQL's current_database() often says postgres and is NOT independent identity.
   Never run installation or synthetic tests in **qhprdlwoxjpkiukxhftp**.
2. Check Auth Users and Storage in this isolated project. Expected before this
   rehearsal: zero users, stored objects and application records. Prior reports of
   an empty project are historical evidence, not a current verification.
3. Run the entire `supabase/preflight/music_billing_isolated_phase6.sql` in this
   project's SQL Editor. It uses a repeatable-read, read-only transaction, returns
   **14 rows in one export grid**, and never invokes billing RPCs. Export that grid.
   It reports counts and metadata, not user identities or row contents.
4. Review all sections. Required pass criteria:
   - 01: read_only is on; inspector bypasses RLS so empty counts are trustworthy.
   - 02: auth.users exists with zero rows; storage.objects/buckets, if present,
     contain zero rows; every public/private application table is absent/empty.
     No UNVERIFIED_PERMISSION or incomplete/timed-out inspection.
   - 03: all dependencies true, including a single-column UUID auth.users.id
     primary/unique key, auth.uid(), core UUID support and public CREATE for owner.
   - 04: all three roles exist. anon/authenticated have no superuser, BYPASSRLS,
     public CREATE, or membership in service_role. service_role is backend-only.
     API roles need public USAGE; authenticated needs auth USAGE/auth.uid EXECUTE.
     Inspect any inherited roles if effective privileges are unexpected.
   - 05: record hosted PostgreSQL/extension versions. The installer requires only
     core PG functions plus Supabase auth; no new extension installation is needed.
   - 06: empty Music namespace across relations/types/functions/constraints/triggers.
   - 07: record broad defaults; installer cleans only its own new object ACLs.
   - 08/09: no unreviewed event or application signup trigger capable of modifying
     other apps or forwarding synthetic data. Stop for review if one is present.
   - 10-14: review existing app columns/functions/policies and all schemas/relations.
     Standard Supabase internal tables can contain platform metadata; do not delete
     them. Unknown custom schemas/tables/views/foreign tables require a separate
     read-only count/dependency inspection before proceeding. Any unexpected app
     object or real data means STOP, even if the Music namespace is available.
5. Confirm the exact installer hash locally with Get-FileHash. Save the preflight
   export, target confirmation, platform version and backup/recovery point. Review
   owner/extension/event-trigger differences from local PostgreSQL 17.9. Stage A
   must be reviewed before marking the API harness's confirmation flag.

STOP on target uncertainty, nonzero/unexpected data, namespace collision, missing
dependency or unreadable evidence. Do not fix these by deleting records, changing
roles, disabling triggers or weakening installer assertions.

## Stage B: conditional isolated installation

The user's Phase 6 authorization covers this test project only after Stage A passes.
It does not authorize any protected Suite, Stripe, Render or deployment change.

1. In the verified isolated project's SQL Editor, run the complete unchanged
   standalone installer once as the approved database owner. Keep BEGIN/COMMIT and
   every assertion. Do not paste/run selected statements or retry after success.
2. In a fresh SQL Editor query run all of
   `supabase/preflight/music_billing_phase6_postinstall.sql`. Export its **8 rows**.
   A fresh-query view of the four tables proves committed transaction visibility.
3. Check exact object/permission contract:
   - Four public tables: music_billing_customers, music_billing_subscriptions,
     music_billing_webhook_events, music_billing_entitlements. RLS enabled on all.
     Owner is the approved installer owner, never anon/authenticated/service_role.
   - Six functions: preserve_customer_owner (trigger, invoker), attach_customer,
     reserve_checkout, claim_delivery, complete_delivery, fail_delivery (the latter
     five SECURITY DEFINER). All have empty search_path and Music-prefixed names.
   - anon: no table SELECT or direct mutations or function EXECUTE.
   - authenticated: own entitlements SELECT only, one owner-read SELECT policy
     using auth.uid(); no direct mutations or billing RPC EXECUTE.
   - service_role: SELECT customers/entitlements and EXECUTE five checked RPCs.
     No direct INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER or column writes,
     no SELECT subscriptions/events, no trigger-function EXECUTE.
   - Three unique indexes on customers (PK, customer ID, ownership pair), one
     subscription PK plus user index, one webhook PK, one entitlement PK: seven
     indexes total. All constraints/indexes/application triggers are Music-prefixed;
     all constraints validated. Review the full definitions in the output.
   - One immutable customer-owner application trigger. Auth FK internal triggers
     are expected; no existing application/signup trigger is replaced.
4. Review before/after metadata. This empty test project's catalog will differ
   from the shared Suite catalog; do not infer shared-project compatibility from it.

## Auth, SQL roles, PostgREST and concurrency: exact operator procedure

The new `scripts/verify_music_phase6_hosted.py` is prepared, **not run against a
hosted project in this assignment**. It accepts no host/database URL, rejects API
keys with a different project reference/role, disables redirects and inherited
proxy settings, uses TLS and bounded timeouts, and prints no credentials or raw
responses. JWT key decoding is an identity guard; Supabase performs signature
verification. It deliberately accepts only this project's legacy JWT anon/service
keys; do not substitute a production key or weaken the guard for newer key formats.
If legacy keys are unavailable, stop and adapt/review the harness first.

Load keys in a trusted local shell via your secret manager or hidden prompts. Do
not paste values into source, shell history, screenshots or committed files. For
PowerShell, for example (each prompt is hidden):

```powershell
$env:MUSIC_PHASE6_TEST_ANON_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Isolated anon key' -AsSecureString)).Password
$env:MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Isolated service-role key' -AsSecureString)).Password
python scripts/verify_music_phase6_hosted.py --approved-project smpyutzfktjgpdibdbqb --preflight-and-installation-verified --pause-for-sql-role-harness
```

The confirmation arguments are an operator attestation, not an automatic proof of
empty data. Do not run the command before Stage A/B inspection passes. It creates
exactly two synthetic Auth users with random passwords, confirmed example.invalid
emails and music_phase6_synthetic metadata; no emails/payment calls are requested.
It signs both in and validates both real JWTs via /auth/v1/user. The unique printed
run identifier lets you find those two UUIDs in the isolated Auth dashboard without
printing credentials or identities in logs. At the pause:

1. Find the A and B UUIDs by that run identifier. In a local copy of
   `scripts/sql_tests/music_billing_shared_roles.sql`, delete only the psql
   `\set ON_ERROR_STOP on` line and replace `:'user_a'`/`:'user_b'` with the quoted
   synthetic UUIDs. Leave every SQL assertion and ROLLBACK intact. Run the whole
   copy in the isolated SQL Editor as owner. It must complete without exceptions;
   it checks real SET ROLE denials, RLS, immutable ownership and atomic persistence.
   Do not commit the UUID-substituted copy. If a statement fails, issue ROLLBACK
   before any other work and stop to investigate.
2. Run this prefix, followed by the entire contents of
   `scripts/sql_tests/music_billing_lifecycle_rehearsal.sql`, in one SQL Editor run:

   ```sql
   select set_config('music_test.user_a','<synthetic A UUID>',false);
   select set_config('music_test.user_b','<synthetic B UUID>',false);
   ```

   UUIDs are synthetic; still keep exports free of identities. This harness also
   ends in ROLLBACK. Do not run its statements piecemeal.
3. Verify both harnesses left Music tables empty with an owner-only count query:

   ```sql
   select 'customers' as object, count(*) as rows from public.music_billing_customers
   union all select 'subscriptions', count(*) from public.music_billing_subscriptions
   union all select 'events', count(*) from public.music_billing_webhook_events
   union all select 'entitlements', count(*) from public.music_billing_entitlements;
   ```

4. Only after successful SQL results, type SQL_HARNESSES_PASSED in the paused local
   harness. The JWTs remain in memory, so finish promptly; expired JWTs fail closed.

The API harness then tests:

- Free initially, service-only immutable mappings, cross-owner rejection.
- Two simultaneous competing customer bindings: one success and one conflict.
- Two simultaneous Checkout reservations: same token/expiry.
- Two simultaneous event claims: one lease and one busy; release/recovery.
  A completion using the released token must be rejected.
- Ten synthetic current-provider projections: Pro creation/renewal, scheduled
  cancellation keeping Pro, expiration to Free, recovery, immediate termination,
  activation, failed payment to Free, recovery, and older notification reconciled
  from a fresh supplied snapshot. Every completion checks actual JWT owner reads,
  other-user isolation and duplicate delivery.
- Anonymous and both users denied raw billing reads, all five service RPCs and
  direct writes/self-upgrades. SQL harness checks TRUNCATE and full role matrix;
  PostgREST does not expose a generic TRUNCATE endpoint.

The script stops on the first failure and retains synthetic records for inspection.
It does not call Stripe; supplied snapshots/price/customer IDs are fixtures, not
verified Stripe entities. It does not prove that the backend retrieves fresh Stripe
state. Period expiry is exercised with an expired/canceled snapshot; read-time
expiration without a webhook remains an application test. Lease exclusion is real
two-worker HTTP concurrency; this is not a load test or exhaustive race proof.

Remove the two key variables from the shell afterward:

```powershell
Remove-Item Env:MUSIC_PHASE6_TEST_ANON_KEY,Env:MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY
```

## Failure and recovery

- Preflight failure: no writes authorized; preserve findings and investigate.
- Installer statement failure: transaction rolls back. If the client leaves an
  aborted transaction, issue ROLLBACK, then inspect Music namespace again. Never
  bypass collision checks or overwrite unknown objects. Local late-failure and
  collision rollback already passed; hosted SQL Editor behavior is still unverified.
- Successful install: do not rerun the installer. Inspect committed objects using
  the post-install script, not a destructive reset.
- SQL harness failure: ROLLBACK; review exact failed assertion without exporting
  secrets. New synthetic Auth accounts remain outside its transaction.
- API harness failure: retain the printed run ID and HTTP stage label, not response
  bodies/keys. Lease expiry is five minutes. A new run creates a new synthetic pair;
  do not pretend the project is empty after any run. Review counts and provenance
  before an explicitly scoped rerun. Do not reset customer mappings.
- Preserve fixture data for review. Cleanup, if later approved, must be scoped to
  the run's two Auth users and their synthetic Music records, after confirming no
  unexpected signup side effects. No broad deletes, schema drops or production
  restore are part of this package.

## Remaining shared-project and Stripe prerequisites

The protected Suite project has real Suite users/activity/saved state and Baseball
subscription/event/version/install records, broad defaults and existing privilege
risks. The isolated project's empty initial state cannot validate those dependencies,
concurrent production traffic, existing auth triggers, or broad shared service-key
authority. Keep shared hardening separate; RLS does not constrain TRUNCATE or a
BYPASSRLS service key. Re-run the shared preflight/backup/checklist from Phase 5
only under separate shared-install approval. This assignment authorizes no such write.

Before Stripe test integration: successful hosted evidence above, actual Music
recurring test Price ID, test secret/signing key, explicit Music bpc_ Portal config,
and approved Music backend URL/runtime/env. Snapshot webhook route is
`/billing/webhooks/stripe`; events are checkout.session.completed,
customer.subscription.created/updated/deleted, invoice.paid, invoice.payment_failed;
match the code's `2026-10-28.endive` API pin. Confirm Render service, Python 3.12.8,
the matching backend commit, `/billing/health` and matching test Auth/billing
authority. Health alone is not integration proof. No changes to Stripe, Render or
deployed Streamlit apps are requested here. See Phase 5 for exact env names.

## Local validation (not hosted evidence)

Both new SQL inspection scripts executed in disposable PostgreSQL 17.9, returning
14 preflight and 8 post-install sections. Protected fixture snapshots stayed equal;
installer, role/RLS, ten lifecycle transitions, ownership and collision/late-failure
rollback passed again. Temporary server shutdown was confirmed. Free RAM at run
start/end was 2.82/2.77 GB; initial monitoring was 3.36 GB, CPU 89.5%, disk 143.99 GB.
The final preflight-permission recheck also passed at 3.28/3.26 GB with confirmed
server shutdown. Final monitoring: 3.14 GB free RAM, CPU 59.3%, disk 143.90 GB.
No browser suites or concurrent heavy jobs were used. One local execution permission
review timed out; the permitted retry succeeded. No unrelated process was stopped.

Offline Python validation: **119 passed in 10.77 seconds**, including 14 new guard
and SQL-parser tests, with no skips or unresolved test failures. Guard tests make
no network requests. One initial guard test caught a CRLF/LF hash mismatch in the
new harness; the normalized hash was corrected without changing installer SQL.
Command:

```powershell
python -m pytest -q tests/test_music_phase6_preparation.py tests/test_music_billing_shared_install.py tests/test_monetization_customer_ownership.py tests/test_monetization_m2.py tests/test_monetization_entitlements.py tests/test_monetization_phase2.py
```

Record hosted results in a separate review update after execution: target evidence,
14-row preflight export, installation/8-row post-install export, both SQL harness
outcomes, real JWT/REST outcome, concurrency outcome, any failures and synthetic run
identifier. Until then every hosted outcome remains UNVERIFIED/NOT EXECUTED.
