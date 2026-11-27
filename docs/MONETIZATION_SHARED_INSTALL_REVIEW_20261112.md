# Shared Music billing install - local review and execution contract

**Code preparation complete; external installation NOT authorized or performed.**
Target architecture retains Suite Auth and existing Music data at
qhprdlwoxjpkiukxhftp. Existing Baseball/Suite tables remain authoritative and untouched.
Use a non-production schema clone and synthetic users for the first runtime verification.

## Exact installer and dependency decision

`supabase/install/20261112_music_billing_shared_install.sql`
SHA256: `bc635078cd234c21c61e3228d587087cbe70374dcb4933e31902d8ceec422ce4`

is the standalone,
transactional **fresh install**. It supersedes application of the three historical
generic Music migrations for this shared project. Do NOT run those three scripts
before/after it, and do NOT blindly use db push on the historical migration directory.
They remain unchanged as prior-phase reference. No existing Music data was reported
in the namespace; any target collision now aborts instead of being overwritten.

The owner must verify the intended project in the dashboard. SQL cannot safely
infer the Supabase project ref from the generic database name. Before approved
execution, rerun the consolidated shared preflight and retain sanitized evidence.

The installer begins one transaction, uses a 3-second lock timeout, 30-second
statement timeout and install advisory lock, and commits only after ACL assertions.
Preconditions require the API roles, compatible auth.users.id/auth.uid/UUID support,
a trusted installer with CREATE privileges, no untrusted schema CREATE/bypass roles,
and **no existing music_billing_* objects/overloads/types/triggers/constraints**.
CREATE has no OR REPLACE or IF NOT EXISTS escape hatch. A repeated run intentionally
fails without data changes; it is collision-safe, not a schema upgrade or replay.

## Objects and permissions

Four physical tables: public.music_billing_customers, music_billing_subscriptions,
music_billing_webhook_events and music_billing_entitlements. Every new constraint,
index, policy, trigger and function has a music_billing_ name. Customer/subscription
ownership is enforced by immutable binding plus a composite user/customer FK.
Auth foreign keys keep the prior cascade behavior; never delete auth users for recovery.
PostgreSQL adds internal RI triggers for these FKs; existing application Auth/signup
triggers and their definitions are not changed. FK creation takes brief locks on
auth.users; the lock timeout aborts rather than waiting through active signup traffic.

Public functions, all empty search_path and fully qualified application relations:

- music_billing_preserve_customer_owner() - invoker trigger function, no API execute.
- music_billing_attach_customer(uuid,text) - immutable insert/readback binding.
- music_billing_reserve_checkout(uuid,text) - serialized durable one-hour reservation.
- music_billing_claim_delivery(text,text,bigint,text,text) - exclusive customer/event lease.
- music_billing_complete_delivery(text,uuid,jsonb,jsonb) - atomic snapshot/projection/ledger.
- music_billing_fail_delivery(text,uuid) - fenced failure/release.

The last five are SECURITY DEFINER, executable only by service_role among API roles.
The trusted database owner retains inherent privileges. Functions accept no dynamic
SQL from request arguments. No raw event/payment payload or customer email is stored.
Default grantees (including unexpected ones) are stripped on ONLY new objects,
including default function PUBLIC execution. No ALTER DEFAULT PRIVILEGES occurs.

| API role | Music tables | Music RPCs |
| --- | --- | --- |
| anon | none, including no TRUNCATE | none |
| authenticated | own-row SELECT on entitlement only | none |
| service_role | SELECT on customers and entitlements; no direct mutations/TRUNCATE | five checked mutation RPCs |

All four Music tables have RLS; the only client policy binds app_user_id to auth.uid().
Effective inherited table/column/RPC permissions are checked before commit. BYPASSRLS
does not bypass ordinary object ACLs, so the backend must use RPCs to write Music.
However, a project service-role key may still access existing Suite/Baseball objects:
this is not a hard credential boundary between applications. See the separate Suite
hardening proposal; no existing shared grants are changed by the installer.

## Subscription and Stripe behavior

Existing Music Free/Pro plans, configured monthly/annual prices, past_due policy and
feature catalog are retained. Current subscription state is fetched while holding a
customer lease. Delayed/equal-timestamp deliveries never overwrite from stale payloads;
completed duplicates are no-ops and collisions fail. Database snapshot, aggregate
entitlement and event completion commit together. Another valid Music subscription
prevents obsolete-subscription deletion from revoking access. Trial/period end is
checked when deriving and reading entitlements, including cached paid checks.
Expiration can leave a stale materialized Pro row while application access is Free;
no new scheduled database rewrite/reconciliation job is introduced.

Customer creation uses a hashed, Music-scoped stable Stripe idempotency key and an
immutable metadata-only request (email changes do not change replay parameters).
Checkout reserves a token/price/expiry durably, passes the same Stripe key and exact
expiry on retries, and blocks a conflicting interval until expiry. Existing local
nonterminal subscriptions or current Stripe subscriptions require Portal management,
not another Checkout. Pagination and malformed Stripe responses fail closed. Sessions
expire after one hour; reservations are not forcibly cleared on transport errors.
The precheck plus persisted reservation prevents concurrent/normal replay duplicates;
actual provider behavior must still be tested, including payment at session expiry.

Stripe can prune idempotency records after 24 hours. A customer creation lost before
mapping persistence and retried after pruning can leave an orphan customer; no
subscription/charge is created by that operation. Do not claim eternal exactly-once
provider behavior. A delayed first Checkout attempt with insufficient remaining expiry
may fail closed until reservation expiry. Configuration changes mid-reservation can
cause a parameter-conflict response; do not clear reservations or invent a new key to
bypass that error. Reconcile, or allow expiry before starting another attempt.

All Stripe HTTP calls send **Stripe-Version: 2026-10-28.endive**. Match the dedicated
Music test snapshot endpoint to this version; actual network compatibility is not
claimed. Every new customer/Checkout/subscription is tagged app=music. Explicitly
tagged foreign events are ignored; unknown untagged customers still retry so missing
Music mappings are not silently discarded. Historical untagged Baseball events can
therefore cause retries if both endpoints share an account: use an isolated Stripe
sandbox for first testing and review routing before enabling a shared-account endpoint.

Portal requires MUSIC_STRIPE_PORTAL_CONFIGURATION_ID (bpc_...). A missing value fails
closed rather than using the account's default. Configure only Music's approved test
prices/actions. Customer mappings are not shared with Baseball. No live mode/keys are
accepted. No real Stripe request, payment, Portal session or dashboard change occurred.

## Tests and what remains unverified

Final focused suite: **105 passed in 10.20 seconds** (local Python 3.13.7).
The installer parsed as 33 SQL statements / nine PLpgSQL blocks/functions; its
23 embedded SQL statements were checked for Music-only mutation targets. The
prepared role harness parsed as 31 SQL statements / nine PLpgSQL blocks, without
execution. `git diff --check` passed.

Focused Python suite covers lifecycle, ownership, expiration, retries/collisions,
atomic adapter boundaries, namespace/DDL invariants, mutation targets, role-policy
contracts, stable idempotency parameters, active-subscription prevention, Stripe
headers and Portal configuration. SQL parsing checks both installer and fixture code.
These checks do not establish actual PostgreSQL ACL or concurrency behavior.
The security checks require the development-only pglast parser; do not accept parser
test skips as successful SQL security validation. Deployment does not need pglast.

Prepared runtime regression file: `scripts/sql_tests/music_billing_shared_roles.sql`.
After separate fixture-write approval, execute it **only in an isolated test clone**
with two existing synthetic auth users having no Music billing records. It uses actual
SET ROLE attempts for anon/authenticated/service_role, verifies A/B RLS, rejects direct
INSERT/UPDATE/DELETE/TRUNCATE and unauthorized RPCs, exercises backend attach/complete,
injects an entitlement constraint failure after subscription persistence, verifies
rollback/retry/duplicate/collision, then ROLLBACKs all fixtures and the test constraint.
It creates no auth users and modifies no auth trigger. It has not been executed here.
Real PostgREST user JWT tests must follow SQL-role tests; SQL Editor is not the client.

Run the focused suite sequentially:
`python -m pytest tests/test_music_billing_shared_install.py tests/test_monetization_customer_ownership.py tests/test_monetization_m2.py tests/test_monetization_entitlements.py tests/test_monetization_phase2.py -q`

## Later approved execution / deployment prerequisites

1. Review exact installer/code commit, SHA256 of the SQL file, complete shared
   preflight and protected schema/function/policy/grant baselines. Record backups
   and recoverability; identify installed roles/owners/default privileges.
2. Resolve the separate Suite TRUNCATE finding through its own approval track.
   Do not grant anonymous or user writes to Music to match existing Suite defaults.
3. Obtain explicit approval for test-clone install and fixture writes. Rehearse the
   installer and role harness, prove collision rollback on a second install, and run
   actual JWT A/B reads/denials and concurrent customer/event/Checkout requests.
4. Verify both login and backend verify /auth/v1/user against qhpr... (or the clone's
   matching test Auth authority). Music auth UUIDs are not Suite profile UUIDs.
   Confirm Supabase exposes the new public objects/RPCs through its schema cache;
   do not deploy this adapter against the old generic schema.
5. Only after a separate shared-install approval, apply the exact standalone file
   transactionally; pause the Music billing writer during cutover, not Baseball or
   existing Music data saves. Compare protected definitions/grants/triggers after
   installation and account for legitimate concurrent row-count changes. No shared
   table data, Baseball RPC, global role or existing auth signup trigger definition
   is a mutation target. New auth.users foreign keys necessarily create PostgreSQL
   internal referential-integrity triggers; no application signup trigger is replaced.
6. Separately approve test hosting. Backend command:
   `python -m uvicorn monetization_service:app --host 0.0.0.0 --port "$PORT"`.
   Use repo Python 3.12.8 and requirements; validate that runtime before deployment.
7. Backend variable names: MUSIC_BILLING_ROLLOUT, MUSIC_STRIPE_MODE,
   STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRO_MONTHLY_PRICE_ID,
   STRIPE_PRO_ANNUAL_PRICE_ID, MUSIC_PUBLIC_BASE_URL, MUSIC_BILLING_SERVICE_URL,
   MUSIC_BILLING_SUPABASE_URL, MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY,
   MUSIC_BILLING_SUPABASE_ANON_KEY, **MUSIC_STRIPE_PORTAL_CONFIGURATION_ID**.
   Keep rollout and mode test; secrets stay exclusively on the backend.
8. Frontend public billing URL/anon key must use the same Auth authority. Retain
   SUITE_AUTH_ENABLED, SUITE_SUPABASE_URL, SUITE_SUPABASE_KEY,
   SUITE_SUPABASE_ANON_KEY and SUITE_AUTH_REDIRECT_URL as required by current login;
   do not copy the billing service secret into frontend configuration. Keep hosted
   entitlement development overrides disabled.
9. Approve dedicated Music test recurring prices, pinned-version snapshot webhook
   for the existing six events, and explicit test Portal configuration. Health is
   configuration-only; HTTP 200 is not proof of database/API readiness. Complete one
   end-to-end test payment, renewal, failed payment/recovery, cancellation/expiry,
   owner-only Portal and replay test before any production launch proposal.

## Rollback and recovery

Before commit, any precondition/DDL/grant assertion failure rolls back the entire
install. Do not execute individual statements or manually skip assertions. Any
preexisting Music object requires a new ownership-aware upgrade proposal, not rerun.

After a successful install with records, preserve all Music/Suite/Baseball tables,
keys and ledgers. Pause Music billing ingress/Checkout and fix forward. Keep entitlement
checks fail closed; rollout OFF intentionally opens premium features. Do not run the
historical generic migrations, regrant direct writes, delete auth users, drop tables,
force-reset bindings, or overwrite newer subscriptions with an old backup. A restore
requires its own plan to replay provider events after the snapshot. The old backend
cannot safely run against this new contract; maintain the matching adapter while
reconciling. Recover abandoned events through lease expiry and identical request keys.

No external SQL, migrations, credential changes, pushes or deployments were performed.
Only small sequential tests/parser checks ran; no browser or dev server was started.
Resource checks recorded roughly 0.26-1.58 GB available RAM, CPU 74-100%, and
147 GB free disk. No unrelated process was stopped. The first adjusted baseline
passed 85 tests, then the expanded suite passed 104 and finally 105 tests.
Runtime database and Stripe integration remain explicitly unverified.
