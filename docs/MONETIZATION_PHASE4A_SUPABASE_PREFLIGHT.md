# Phase 4A - Supabase billing approval checkpoint

**Ready for read-only inspection; NO-GO for migration application until results are reviewed.**
No external database was contacted. All three migrations and prior phases are unchanged.
This checkpoint prepares evidence; it does not certify an unseen schema or authorize writes.
Base: Phase 3 `2d7f00339f4a9c6967b9eae45d2273c751486883`.

## Run the read-only preflight

1. In the Supabase dashboard confirm the intended **Music test project** and its
   authentication authority. Do not choose a shared/production project by assumption.
2. Open SQL Editor under its database administrator role (normally postgres).
   Copy **all** of `supabase/preflight/music_billing_phase4a_preflight.sql` into a
   new query and run it. It uses one repeatable-read, read-only transaction and ends
   with ROLLBACK. No migration, billing RPC, DDL, DML or row lock is executed.
3. Review sections 01-08. If the editor exposes only one result grid, run a complete
   numbered section (including its WITH clause) enclosed in the same BEGIN READ ONLY,
   timeout settings and ROLLBACK **in a single execution**. Do not rely on a transaction
   carrying between editor runs. Keep results private and share only sanitized findings.
4. If a timeout/permission error aborts the transaction, execute ROLLBACK in that
   session if needed and stop. Counts are bounded by a 30-second statement timeout
   and a 3-second lock timeout. Do not automatically raise timeouts or retry a large
   production scan. Missing/incompatible prerequisites return SKIPPED, not zero.
5. For changed/unexpected RPC bodies, privately inspect
   `supabase/preflight/music_billing_phase4a_rpc_review.sql`. It SELECTs definitions
   without invoking functions. Do not paste full existing definitions into chat or
   reports: custom code may contain sensitive literals. Main preflight outputs only
   function source hashes. Formatting differences also change a hash and need review.

The main script emits schema metadata and fixed aggregate counts only: no auth UUIDs,
emails, Stripe identifiers, tokens, raw webhook payloads, last_error text or payment
information. Dynamic SQL consists solely of fixed SELECT aggregate/history queries;
it is guarded against absent tables/columns/types. Each customer/subscription/
entitlement/event aggregate scans only the billing/auth relations it needs. RLS or
restricted inspection privileges can hide rows; a zero count is not reliable unless
inspection coverage is confirmed. A successful parse is not a database execution test.

## Expected results and red flags

| Section | Expected / interpretation |
| --- | --- |
| 01 | transaction_read_only on; auth.users, auth.uid(), UUID, hash, advisory-lock and JSON record functions exist; anon/authenticated/service_role exist; trusted owner can manage target objects; untrusted roles cannot CREATE in public |
| 02 | Existing columns match types, nullability and defaults below; partitioned/foreign/view replacements need explicit review. Missing M2 tables is normal only for a confirmed fresh install. Missing Phase 2 columns is normal before Phase 2. Extra NOT NULL columns without defaults, generated fields or incompatible types block inserts/migration |
| 03 | Valid PK/unique/FK/check constraints and indexes match the contract. No conflicting named indexes; no invalid/unvalidated constraints or indexes without review |
| 04 | All four existing tables have RLS. Only own-row authenticated entitlement SELECT is allowed; effective client writes and other table reads must be false. Review every extra policy and column grant; policies combine and can widen access |
| 05 | Missing RPCs before their migration is expected. Existing signatures/returns/owners/language/search_path match; exact source hashes or reviewed equivalent code. No client/PUBLIC execution, including overloads. Phase 2 service execution true for new RPCs and false for old M2 RPCs |
| 06 | Expected enabled ownership trigger; any other triggers/dependencies reviewed for side effects, ownership or cutover assumptions. Catalog dependencies do not reveal every dynamic PL/pgSQL dependency |
| 07 | Version presence corroborates schema only; missing history means UNKNOWN. SQL Editor changes may not be recorded. An eight-digit version could belong to another same-day migration; do not infer content from version alone |
| 08 | Integrity conflicts should be zero. Zero rows is valid for fresh tables. SKIPPED is incomplete evidence, never a pass |

**Block approval:** duplicate IDs, orphaned auth users/customer mappings, subscription
owner mismatch, entitlement source owner mismatch, conflicting definitions/returns,
unsafe grants/policies, missing dependencies, a generic billing schema owned by another
app, or unexplained partial deployment. Independent user/customer FKs do **not** enforce
that a subscription's user owns its customer; the aggregate ownership check is essential.

**Require a reconciliation decision:** multiple paid subscriptions per user; missing or
expired paid periods; past-end materialized Pro rows; failed/stale-processing events;
active/expired/incomplete lease pairs; legacy events without fingerprints/original
envelopes; unprojected subscriptions. These can be legacy/recovery states rather than
corruption, but must not be silently deleted or called clean. Customer IDs do not reveal
Stripe account or test/live mode; that compatibility needs separate Stripe evidence.

## Exact schema contract

All four tables are public, with the columns below. NN includes implicit PK NOT NULL;
blank defaults mean no default. Preserve all preexisting columns/rows, including extras
that pass review. Phase 2 adds seven nullable columns, listed after the base tables.

### billing_customers

| Column | Type | NN | Default |
| --- | --- | --- | --- |
| app_user_id | uuid | yes |  |
| stripe_customer_id | text | yes |  |
| email | text | no |  |
| created_at | timestamptz | yes | now() |
| updated_at | timestamptz | yes | now() |

### billing_subscriptions

| Column | Type | NN | Default |
| --- | --- | --- | --- |
| stripe_subscription_id | text | yes |  |
| app_user_id | uuid | yes |  |
| stripe_customer_id | text | yes |  |
| stripe_product_id | text | no |  |
| stripe_price_id | text | no |  |
| provider_status | text | yes |  |
| current_period_end | timestamptz | no |  |
| cancel_at_period_end | boolean | yes | FALSE |
| trial_end | timestamptz | no |  |
| latest_event_id | text | yes |  |
| latest_event_created | bigint | yes |  |
| created_at | timestamptz | yes | now() |
| updated_at | timestamptz | yes | now() |

### billing_webhook_events

| Column | Type | NN | Default |
| --- | --- | --- | --- |
| stripe_event_id | text | yes |  |
| event_type | text | yes |  |
| event_created | bigint | yes |  |
| payload | jsonb | yes |  |
| processing_state | text | yes |  |
| attempt_count | integer | yes | 1 |
| last_error | text | no |  |
| received_at | timestamptz | yes | now() |
| processed_at | timestamptz | no |  |
| updated_at | timestamptz | yes | now() |

### billing_entitlements

| Column | Type | NN | Default |
| --- | --- | --- | --- |
| app_user_id | uuid | yes |  |
| plan | text | yes |  |
| status | text | yes |  |
| current_period_end | timestamptz | no |  |
| source_subscription_id | text | no |  |
| source_event_id | text | yes |  |
| source_event_created | bigint | yes |  |
| reason | text | yes |  |
| updated_at | timestamptz | yes | now() |

Phase 2 additions (all nullable, no defaults):

- billing_customers: reconciliation_token UUID, reconciliation_expires timestamptz.
- billing_webhook_events: fingerprint text, lease_token UUID.
- billing_subscriptions: projected_plan text, projected_status text, projected_reason text.

Constraints on a clean install (equivalent reviewed names are acceptable):

- Each table has a primary key: customers/entitlements on app_user_id, subscriptions
  on stripe_subscription_id, events on stripe_event_id.
- billing_customers.stripe_customer_id is UNIQUE, with its unique backing index.
- customers.app_user_id, subscriptions.app_user_id and entitlements.app_user_id
  reference auth.users(id) ON DELETE CASCADE.
- subscriptions.stripe_customer_id references customers.stripe_customer_id with
  default NO ACTION deletion/update behavior. Deleting an auth user with dependent
  billing rows can cascade/block; never use auth deletion for rollback.
- events.processing_state CHECK permits processing/processed/failed only.
- entitlements.plan CHECK permits free/pro only. Status/reason have no CHECK enum.
- Four PK indexes, the customer Stripe-ID unique index, and
  billing_subscriptions_user_idx on (app_user_id): six explicit/constraint indexes.
  There is no trigger maintaining updated_at automatically in M2.
- Phase 1 function billing_preserve_customer_owner() RETURNS trigger rejects changes
  to either ownership identifier. Enabled BEFORE UPDATE FOR EACH ROW trigger:
  billing_customer_owner_immutable. Email-only updates remain possible.
- Phase 2 adds no CHECK constraint on projected fields and no new index. Its initial
  backfill changes only null projected_plan rows with a matching trusted source
  entitlement/user. Other legacy subscriptions still need provider reconciliation.

## RPC and access contract

| Function signature in public | Return | Required effective execution after Phase 2 |
| --- | --- | --- |
| billing_claim_webhook_event(text,text,bigint,jsonb) | text | no service/client/PUBLIC execution |
| billing_apply_subscription(uuid,text,text,text,text,text,timestamptz,boolean,timestamptz,text,bigint) | boolean | no service/client/PUBLIC execution |
| billing_save_entitlement(uuid,text,text,timestamptz,text,text,bigint,text) | void | no service/client/PUBLIC execution |
| billing_preserve_customer_owner() | trigger | client/PUBLIC denied; invoked through trigger |
| music_billing_claim_delivery(text,text,bigint,text,text,jsonb) | text | service_role only |
| music_billing_complete_delivery(text,uuid,jsonb,jsonb) | void | service_role only |
| music_billing_fail_delivery(text,uuid) | void | service_role only |

The six mutation RPCs are PL/pgSQL SECURITY DEFINER with search_path=public.
The ownership trigger function is PL/pgSQL SECURITY INVOKER (default), same path.
Function owner retains inherent rights: 'only' above describes application/client
roles, not the trusted owner/superuser. Changed owner/return/signature, an untrusted
owner, or an unexpected executable overload requires review before CREATE OR REPLACE.

M2 REVOKEs all table privileges from anon/authenticated, then grants authenticated
SELECT on billing_entitlements and installs the sole intended policy
billing_entitlements_read_own, FOR SELECT TO authenticated, USING app_user_id=auth.uid().
No INSERT/UPDATE/DELETE policy is intended. RLS is enabled, not forced: trusted owners
and BYPASSRLS service role are expected to bypass it. Confirm service_role table
SELECT/INSERT/UPDATE privileges; the scripts rely on Supabase default table grants.
M2 does not revoke PUBLIC or inherited/column grants, or remove other policies;
effective permission and policy inspection is mandatory on an existing schema.

## Idempotency and migration safety

| Migration | Replay behavior / compatibility |
| --- | --- |
| 20260927_monetization_m2.sql | IF NOT EXISTS skips existing tables/indexes without validating shape. Replaces three functions and named policy, reapplies grants/RLS. Existing records are retained. NOT safe to rerun after Phase 2: it restores obsolete service RPC execution |
| 20261111_music_customer_ownership.sql | Replaces its function, drops/recreates its named trigger; retains records. Must run after M2. Transaction required to avoid a trigger gap or partial failure; review existing same-name trigger/function first |
| 20261112_music_billing_lifecycle.sql | Additive IF NOT EXISTS columns, guarded projection backfill, CREATE OR REPLACE RPCs and grant/revoke cutover. Repeat-safe only against the exact compatible contract with writers paused; no automatic data reset. Replaces custom definitions if allowed |

CREATE OR REPLACE cannot change an existing function's return type and may reject
changed input-parameter names; source/signature review is required. Existing index
names can collide with other tables. IF NOT EXISTS on a column does not validate its
type. None of the files contains an outer BEGIN/COMMIT: a transactional approved runner
is required. A sequence of autocommitted editor statements is not an atomic migration.
Each Phase 2 completion RPC itself is a database transaction, but only a real DB test
can prove its runtime rollback/grant behavior. Do not execute it during this preflight.

## Supabase configuration and identity

| Process | Environment-variable names |
| --- | --- |
| Music Streamlit login/cloud | SUITE_AUTH_ENABLED, SUITE_AUTH_REDIRECT_URL, SUITE_SUPABASE_URL, SUITE_SUPABASE_KEY, SUITE_SUPABASE_ANON_KEY |
| Billing backend | MUSIC_BILLING_SUPABASE_URL, MUSIC_BILLING_SUPABASE_ANON_KEY, MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY |
| Music entitlement reads | MUSIC_BILLING_SUPABASE_URL, MUSIC_BILLING_SUPABASE_ANON_KEY, plus authenticated session JWT |

Billing URL/anon settings fall back to SUITE_SUPABASE_URL/SUITE_SUPABASE_ANON_KEY.
The service-role key has no such fallback. Shared get_cloud_config requires a URL
and SUITE_SUPABASE_KEY (or existing suite_activity secrets), even when an anon key is
present. For isolated RLS-enforced testing, SUITE_SUPABASE_KEY can be the public anon
key. Stripe secrets and the dedicated billing service-role key belong only to the
billing service. Never use a service-role key as evidence of user-scoped RLS.

Login, backend token verification at /auth/v1/user, auth.users foreign keys and
entitlement JWT reads must use the **same Supabase Auth project**. Code supports this
contract; configured URLs/keys/project were not inspected externally. Billing identity
is verified auth.users.id; suite_users.id, email, external ID and workspace/profile IDs
are not interchangeable. Preserve required Suite tables/auth session behavior in the
test environment; the billing migrations do not provision the Suite storage schema.

## Approval checkpoint and later execution (not authorized here)

Before approving writes, capture: intended test project confirmation, sanitized
preflight sections/results, migration history/schema reconciliation, existing data
counts/backup, approved exact migration file hashes, and the A/B user test plan below.
Do not paste keys or row identifiers into the report. Missing evidence keeps NO-GO.

Only after a separate explicit migration approval:

1. Back up the four tables and schema/grants/functions/policies; verify restore
   availability. Preserve Stripe mappings and webhook ledger. Pause test billing
   writers/Checkout during the cutover; do not change production.
2. Apply only unapplied, reviewed migrations in order: M2 -> Phase 1 -> Phase 2,
   each transactionally through the approved process. Review history conflicts
   before marking anything applied. Do not reapply M2 after the Phase 2 grant cutover.
3. Rerun this read-only preflight. Require valid final schema/grants/ownership trigger,
   no unresolved conflicts, and a decision for legacy/in-flight events/projections.
4. With separate approval for test fixture writes, run the existing rollback-only
   scripts/sql_tests/music_billing_phase2.sql against a dedicated existing test auth
   user with no billing mapping. This is NOT a preflight: it invokes mutating RPCs
   and exercises rollback; it has deliberately not been run by this assignment.

Post-migration verification using two isolated test users A and B:

- With A's anon-key + JWT, SELECT only A's entitlement; with B's JWT, SELECT only B's.
  A querying B's UUID and B querying A's must see no rows. Anonymous SELECT must be
  denied. Even an authenticated filter omitting user_id must remain own-row only.
- Both users and anon must fail table INSERT/UPDATE/DELETE, including direct paid
  plan edits and column-only grants; all three new RPCs and every old RPC/overload
  must reject those roles. Use the actual application roles/JWTs, not SQL Editor's
  administrator context. Keep JWTs and UUIDs out of shared reports.
- The billing service role must create two distinct immutable mappings. Attempts to
  rebind user or customer must fail. Mismatched subscription owner must not commit.
- Run service-only atomic success, deliberate entitlement constraint failure, retry,
  duplicate, changed-event collision, simultaneous same-user events, expired lease
  fencing, and lost response after commit. Check no partial subscription/entitlement/
  processed-state update. Verify actual PostgREST response shapes, not SQL alone.
- Verify A's renewal/cancellation/failure/recovery never changes B's entitlement.
  Check exact read-time expiry separately from stale materialized DB plan. Do not
  rely on arbitrary metadata or fake ledger rows to bootstrap trusted ownership.

## Recovery preserving subscriptions

If an unapplied migration fails inside its transaction, roll that transaction back;
inspect the error and rerun preflight before proposing a corrected migration. Do not
edit customer/subscription rows to make the script pass.

After successful Phase 2 application, stop test billing processing, retain tables,
columns, ownership trigger, event ledger and subscription records, then repair forward
with separately reviewed code/schema. Phase 1 code cannot safely run against Phase 2's
revoked old RPC grants. Do not drop additive columns, delete auth users, truncate the
ledger, restore a stale backup over newer billing state or blindly regrant old RPCs.
Maintain fail-closed paid access while paused; rollout OFF opens premium features.
Resume Stripe retries and reconcile current subscriptions after recovery. Any restore
requires a separate plan accounting for events received after the backup.

## Local validation and limitations

Validation passed for 21 statements in the main script, four in the private RPC
review, seven nested fixed aggregate SELECTs, all 44 expected columns and seven
migration function-source hashes. All three unchanged migrations also parsed (45
SQL statements / seven PLpgSQL functions). AST checks rejected mutation statements,
SELECT INTO, row-locking clauses and billing-function invocations; git diff --check
passed. Resource checks measured 2.36-2.61 GB available RAM, about 14% CPU and 148.6 GB
free disk. No existing Python code changed, so billing suites were not rerun.

Only local SQL parsing/static read-only checks were performed; no schema counts or
permission results from Supabase are claimed. The preflight is designed to be safely
rerunnable, including on empty/unmigrated projects, but runtime execution remains
unverified. RAM stayed below 3 GB available, so no browser suite or server was launched.
All committed changes are new SQL preflight files and this documentation.

References: [PostgreSQL CREATE TABLE / IF NOT EXISTS](https://www.postgresql.org/docs/current/sql-createtable.html),
[PostgreSQL query-to-XML functions](https://www.postgresql.org/docs/current/functions-xml.html),
[Supabase migration history](https://supabase.com/docs/guides/deployment/database-migrations).
