# Shared-Suite preflight: one CSV export

The earlier CSV containing only `15_shared_row_counts` is a partial export, not a
failed inspection. The reported counts are a useful baseline but do not establish
namespace availability, permissions or policy safety. No migration is approved yet.

## Exact next step

1. Confirm the Supabase project is **qhprdlwoxjpkiukxhftp** in the dashboard.
2. Open a new SQL Editor query and paste the **entire** contents of
   `supabase/preflight/music_billing_shared_suite_export.sql`.
3. Run it once. There is one SELECT result grid with columns `section`, `row_count`
   and `findings`. The query uses a read-only repeatable-read transaction and ends
   with ROLLBACK. No billing function, migration or data mutation is executed.
4. Confirm **exactly 27 rows**, covering inspection blocks 01 through 15. Choose a
   result limit of at least 27 (100 or more is sufficient), then export that grid
   as CSV. A single CSV now contains all inspection blocks. Preserve the raw CSV;
   findings cells contain JSON arrays, so spreadsheet display may not expand them.
5. Keep metadata output private; share the exported file or sanitized findings for
   review, without adding credentials, raw function bodies or customer records.
   If the statement times out or fails, stop and report the error. Do not interpret
   an absent export as success. The 15-second timeout now covers the whole combined
   statement rather than each individual inspection query. If a transaction remains
   aborted, use ROLLBACK in that session before retrying.

The companion preserves all 27 SELECT queries from the existing multi-grid script.
Each query runs in a materialized CTE and becomes one export row. `row_count` is the
number of inspection results in that block, **not** necessarily a database table
row count. `findings` holds every result record, with the repeated section column
removed. In `15_shared_row_counts`, actual table counts are inside findings as
`rows`. Empty blocks still export `row_count=0, findings=[]`; a legitimately empty
PUBLIC ACL block is different from an omitted block. SKIPPED checks still need review.

## Completeness checklist

The CSV must contain these exact section labels:

```text
01_context
01_roles
02_columns
02_all_columns
03_constraints
03_indexes
03_named_index_collisions
04_rls
04_policies
04_privileges
05_expected_rpcs
05_all_rpc_permissions
05_public_rpc_acl
06_triggers
06_dependencies
07_migration_history
08_aggregate_integrity
09_shared_objects
10_shared_columns
10_shared_constraints
11_shared_policies
11_shared_effective_access
12_default_acl
12_memberships
13_function_boundary
14_shared_triggers
15_shared_row_counts
```

Review namespace availability in 09, function collisions/overloads in 05/13,
effective access/defaults/inheritance in 04/11/12, RLS policies in 04/11, and
triggers/dependencies in 06/14. The database inspector's privileged view does not
replace later real-user RLS/RPC tests. The main inspection and its existing safety
limits are documented in `MONETIZATION_SHARED_SUITE_READINESS_20261112.md`.

## Supplied baseline (owner-run inspection; not independently executed here)

| Protected table | Reported rows |
| --- | ---: |
| public.subscriptions | 1 |
| private.baseball_billing_webhook_events | 3 |
| private.baseball_billing_subscription_versions | 1 |
| private.baseball_auth_project_billing_install | 1 |
| public.suite_users | 7 |
| public.suite_activity_events | 6692 |
| public.suite_app_current_state | 15 |

Legitimate app traffic may change these counts between runs. A count alone cannot
prove that records or permissions were preserved. Do not reset data to match it.

## Validation / stop point

The export script was parsed locally, checked for mutation/row-lock/billing-function
calls, and its 27 CTE queries compared with the canonical multi-grid script. No SQL
was executed externally. Existing preflight, application code and migrations remain
unchanged. No browser, server, heavy test suite or external service was started.
**NO-GO for migrations remains until the complete inspection is reviewed.**
