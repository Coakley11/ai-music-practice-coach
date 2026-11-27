# Music billing: shared Daniel AI Suite readiness

**NO-GO for applying the existing Music migrations to the shared project.**
Next action is the read-only inspection below, followed by a namespaced install
proposal and permission review. No SQL was executed externally by this assignment.

## Verified input versus local evidence

The owner confirmed both deployed apps' Suite URL is
`https://qhprdlwoxjpkiukxhftp.supabase.co`, and reported seven existing RLS-enabled
Suite/Baseball tables. Treat this as deployment evidence supplied by the owner,
not a database inspection performed here. Existing Music objects were not reported.
The empty `smpyutzfktjgpdibdbqb` project is not the current deployed auth/data target.

Music's source migration set remains unchanged:
20260927_monetization_m2.sql -> 20261111_music_customer_ownership.sql ->
20261112_music_billing_lifecycle.sql. These describe dependency order, NOT approval
to apply them unchanged in a shared database. Both applications' current deployed
commits, token issuers and backend billing URLs remain to be verified.

## Compatibility and namespace decision

| Existing Music design | Shared-project finding / required decision |
| --- | --- |
| Four public.billing_* tables | Distinct from the seven reported objects, but generic and potentially owned by another app or future Suite billing. The incomplete inventory does not prove availability |
| M2 public.billing_claim_webhook_event, billing_apply_subscription, billing_save_entitlement | Generic functions are CREATE OR REPLACEd and later have service grants revoked. Could overwrite or disable unrelated functions with those signatures |
| billing_preserve_customer_owner and billing_customer_owner_immutable | Generic ownership function/trigger; safe only with proven Music ownership of their objects |
| Phase 2 music_billing_claim_delivery/complete_delivery/fail_delivery | Already Music-specific names, but bodies reference generic billing tables; names alone do not isolate writes |
| FKs to auth.users and JWT-own-row entitlement SELECT | Compatible with retaining existing Suite Auth in qhpr..., provided the actual Music login, billing verifier and entitlement reads agree |
| No references to public.subscriptions, private.baseball_* or Suite tables in the three Music migration bodies | No direct intended modification of the reported Baseball/Suite objects. This does not exclude colliding generic objects, indirect triggers or privileged access |
| CREATE/ADD IF NOT EXISTS and fixed grants | Do not validate existing types, owner, policies, defaults or overloads. M2 replay after Phase 2 restores obsolete RPC grants |

**Recommendation: explicit Music namespacing before shared installation.** Proposed
physical tables are public.music_billing_customers, music_billing_subscriptions,
music_billing_webhook_events and music_billing_entitlements. Retain the three
music_billing_* Phase 2 lifecycle RPC names, with explicitly namespaced table
references. Name the ownership function/trigger and all new indexes/constraints
music_billing_*. Do not rename, attach to, migrate, grant on, or revoke from existing
Baseball/Suite objects. Do not reuse public.subscriptions for Music paid access.

For this apparently fresh Music install, prepare one new reviewed transactional
final-schema migration derived from the three existing phases; do not create and
then revoke the obsolete generic M2 RPCs. Preserve the original migration files as
history/reference. Abort if any proposed Music object already exists until it has
been reconciled; do not silently adopt it. Update the adapter/read provider and
SQL tests to the same names in a later implementation assignment. None of those
code/migration changes is implemented or authorized by this readiness report.

## Next exact read-only SQL step

1. Open **the qhprdlwoxjpkiukxhftp project** in Supabase SQL Editor. Confirm the
   project in the dashboard; SQL's database name alone is not a project-ref proof.
2. Run the entire file:
   `supabase/preflight/music_billing_shared_suite_preflight.sql`.
   It starts a repeatable-read READ ONLY transaction, uses 15-second statement and
   3-second lock limits, and ends with ROLLBACK. It never calls a billing function
   or performs DDL/DML. It is not a migration.
3. Review sections 01-08 for the generic Music migration contract, and 09-15 for
   the protected shared objects, proposed namespace availability, columns,
   constraints, policies, effective permissions, default grants, role memberships,
   definer/RPC body hashes, auth signup triggers and seven aggregate row counts.
4. If the editor shows only the final grid, execute a whole numbered section with
   its WITH clause enclosed in the same read-only BEGIN/timeouts/ROLLBACK in one
   execution. Do not assume a transaction survives separate editor requests.
   Permission/timeout errors or SKIPPED checks are unresolved evidence, never zero.
5. Share only sanitized results/flags/counts. No credentials, identities, Stripe
   IDs, payloads, subscription contents or install-marker contents are output.
   The private.baseball_auth_project_billing_install table is inspected only for
   metadata and total row count. Its meaning/version cannot be inferred from its
   name alone; an authorized owner should reconcile it with the deployed install.

Expected: all seven reported protected tables present with RLS on; proposed Music
names absent; no unexplained generic Music table/function collisions; reviewed
ownership policies and client-denied writes; no untrusted schema CREATE rights.
The script hashes rather than prints function bodies. Changed definitions or broad
RPC execution need private owner review. It cannot discover all dynamic SQL links.

## Cross-application permission and event risks

- RLS enabled on seven tables is not a sufficient permission verdict. Review every
  policy, table/column grant, inherited role and executable SECURITY DEFINER RPC.
  A client must not be able to edit either application's paid status or invoke
  privileged mutations through an unrelated callable function.
- Shared authenticated roles identify users, not applications. A Suite user might
  legitimately SELECT their own Baseball subscription as allowed by its policy.
  Music must derive access exclusively from Music's entitlement table. A Baseball
  Pro row must never grant Music Pro, or vice versa.
- A project service-role credential can bypass RLS and may access both apps' data.
  Prefixes and separate processes are logical isolation, not a credential boundary.
  Scope the Music writer to its required objects/RPCs where practicable; current
  code assumes service-role access, so least-privilege credentials require a
  separate implementation/provisioning review. Do not claim hard isolation until
  effective privileges and actual API behavior have been verified.
- Do not alter global default privileges, the authenticated/service_role roles,
  public.subscriptions policies, existing auth.users triggers or Baseball RPCs to
  make Music work. Existing signup triggers may create a Baseball Free row for
  every new Suite user: inspect that behavior before creating synthetic accounts.
- Preserve separate Music Stripe prices, customer mappings, signing secret and
  endpoint. A shared Stripe account can send Baseball events to a Music endpoint;
  current Music unknown-customer handling returns 503. Before broad shared-account
  testing, implement/test deliberate foreign-app event routing without discarding
  Music retries. Use an isolated Stripe sandbox for initial test coverage.
- If a Stripe Customer is shared across apps, its Portal may manage both sets of
  subscriptions. Do not reuse Baseball customer mappings or default Portal settings
  without review; use Music-specific customers and an approved Portal configuration.

## Remaining Baseball deployment verification

The matching Suite URL alone does not verify these settings:

- Deployed Streamlit/frontend and Render backend repo, branch and commit.
- SUITE_AUTH_ENABLED or suite_activity.suite_auth_enabled; effective auth URL after
  all environment/Streamlit-secret precedence; public key's project; an actual
  session's issuer project (compare privately, do not disclose the JWT).
- BASEBALL_BILLING_SUPABASE_URL and its matching anon/server keys on Render.
  Backend falls back to SUITE_SUPABASE_URL. Verify the actual selected URL, not
  just a fallback or the presence of tables in qhpr....
- BASEBALL_BILLING_SUPABASE_SECRET_KEY or its legacy
  BASEBALL_BILLING_SUPABASE_SERVICE_ROLE_KEY alternative: key identity/project and
  intended role privately; no values should be shared.
- Baseball client entitlement-read URL and anon key. In the reviewed client loader,
  suite_activity secrets can override the environment billing URL. Confirm deployed
  source and effective values, not merely both configured variables.
- BASEBALL_BILLING_SERVICE_URL / baseball_billing.service_url,
  BASEBALL_PUBLIC_BASE_URL, BASEBALL_BILLING_ROLLOUT and BASEBALL_STRIPE_MODE;
  Stripe account/sandbox, expected Baseball Price, webhook destination/signing
  secret and Portal configuration (verify secret settings without disclosing them).
- Actual public.subscriptions policies, effective RPC grants, auth signup trigger,
  private install-marker metadata/version and any cross-project bridge. The local
  historical przcoiazzgsadiyrgrou config is not evidence of today's deployment.

Music's SUITE_SUPABASE_URL, SUITE_SUPABASE_KEY, SUITE_SUPABASE_ANON_KEY and its
MUSIC_BILLING_SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY settings also need to be
consistent. Existing login/data must remain at the Suite project. Neither copying
user UUIDs nor redirecting a billing URL alone establishes cross-project Auth trust.

## Safest execution plan after review and separate approval

1. Collect the preflight results and effective deployment matrix. Resolve namespace,
   privileges, marker/trigger and shared Stripe routing questions first. Keep NO-GO
   while any result is absent or unexplained.
2. Prepare/review the new Music-only final-schema migration and matching code/tests
   on an isolated branch. Restore/clone the relevant schema into a non-production
   test environment with synthetic users; rehearse there before shared application.
3. Back up protected shared schema/grants/function hashes and all relevant data;
   capture aggregate baselines. Inventory triggers/dependencies/default grants.
   Review every mutation target in the proposed migration against an explicit
   Music-only allowlist. No protected-table data backfill or auth trigger changes.
4. Following explicit migration approval, apply the new Music install atomically
   with lock/statement limits and fail-closed collision assertions. Only the Music
   billing writer should be quiesced; no planned Baseball/Suite outage or credential
   change. Abort on unexpected locks or ownership instead of forcing execution.
5. Reinspect protected schemas, policies, grants, indexes, triggers and body hashes;
   they must remain unchanged. Compare counts with concurrent legitimate activity
   accounted for (counts may increase while apps remain active). A row count alone
   does not prove that existing rows were preserved.
6. With separate test-write approval, use two users to prove own-row reads, denied
   paid edits/RPCs, atomic retry/lease behavior and app-independent entitlement:
   Baseball Pro/Music Free and the reverse must both work. Check signup-trigger
   side effects and reconcile preexisting Baseball state before and after tests.
7. If migration fails, roll back the transaction. After successful installation,
   preserve all records/ledger and repair forward; never restore an old database
   over newer subscriptions, delete auth users, regrant generic RPCs, or drop shared
   tables. The original Music three-file sequence is not an approved fallback.

## Validation and stop point

Only documentation and a new read-only preflight were created. Local parsing
validated 31 top-level statements, seven nested aggregate queries and two fixed
SELECT templates; AST checks found no mutations, row locks or billing RPC calls.
Git whitespace checks passed; no browser/server/test suite was launched. All older
Music code/migrations and unrelated work remain untouched. External SQL was not run.
RAM initially measured about 0.4 GB available with CPU around 86%; the final check
showed 2.93 GB available, CPU 57.4% and 147.26 GB disk free. Keep execution
limited to review until laptop resources recover. This report does not authorize
migration, credentials, deployment, push or any billing-record change.
