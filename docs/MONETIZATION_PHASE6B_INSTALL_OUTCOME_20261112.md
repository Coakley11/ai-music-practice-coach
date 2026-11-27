# Phase 6B isolated hosted installation outcome

Date: 2026-11-12 (America/New_York).

## Outcome

**Installation succeeded in smpyutzfktjgpdibdbqb.** The unchanged standalone
installer ran in the existing authenticated Supabase SQL Editor. The dashboard
reported `Success. No rows returned`. A separate, fresh read-only query then
returned all eight prepared post-install sections and confirmed committed objects.

Immediately before execution the visible dashboard address and project links
identified `smpyutzfktjgpdibdbqb` / music-practice-coach. The protected project
`qhprdlwoxjpkiukxhftp` was never selected or modified. The dashboard labels this
isolated project's main branch PRODUCTION; the authorization boundary was the
explicit project reference, not that generic branch label.

This report supersedes Phase 6's NOT EXECUTED status for installation and catalog
inspection only. It does **not** establish hosted subscription lifecycle, cross-user
runtime behavior, real JWT/PostgREST behavior, concurrency or Stripe integration.

## Exact installer and evidence

- Installer: `supabase/install/20261112_music_billing_shared_install.sql`.
- Source baseline: d684f87ec35b5760095fef123d0f1a021ce8635e (Phase 6 preparation).
- Original CRLF byte SHA256:
  `bc635078cd234c21c61e3228d587087cbe70374dcb4933e31902d8ceec422ce4`.
- LF-normalized SHA256:
  `35c2d92f76d5b6012bfff4efc59d47893153c7660268e76c2086673e71b3c577`.
- Installer was loaded directly from that file and checked against the validated
  normalized hash before pasting; no SQL was edited or assertions bypassed.
- Hosted install query: `/dashboard/project/smpyutzfktjgpdibdbqb/sql/5a70fafd-4ae4-46b1-aba1-1f7c84becdbe`.
- Hosted verification query: `/dashboard/project/smpyutzfktjgpdibdbqb/sql/a57483c4-0791-4dbb-9be2-fc48ef064579`.
- Verification used the unchanged
  `supabase/preflight/music_billing_phase6_postinstall.sql`.

The previously completed preflight recorded PostgreSQL 17.11, empty Auth/storage,
available dependencies/roles, no namespace collisions and broad public defaults.
The earlier read-only trigger inspection confirmed ensure_rls only enables RLS on
new public tables, compatible with the installer's explicit RLS commands. Other
event triggers cover extension changes or PostgREST notifications. No event trigger,
default privilege, existing function or Auth application trigger was modified.

## Observed post-install checks

All eight sections were inspected through the SQL Editor accessibility result grid:

1. Four tables owned by postgres, RLS enabled on each:
   music_billing_customers, music_billing_subscriptions,
   music_billing_webhook_events, music_billing_entitlements.
2. Effective privileges across all four tables and three API roles:
   - anon: no SELECT or mutation privileges.
   - authenticated: SELECT entitlements only.
   - service_role: SELECT customers and entitlements only.
   - All three roles: INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER,
     column INSERT and column UPDATE false on every Music table.
   Object ACLs also show no remaining broad default grantees or MAINTAIN grants
   to API roles. Existing schema defaults remain untouched.
3. Six functions owned by postgres, all with empty search_path. Five backend RPCs
   are SECURITY DEFINER; preserve_customer_owner is invoker/trigger-only.
4. Effective EXECUTE: anon/authenticated false on all six; service_role true only
   on attach_customer, reserve_checkout, claim_delivery, complete_delivery and
   fail_delivery, false on preserve_customer_owner.
5. Exactly one policy: authenticated SELECT on entitlements where
   app_user_id = auth.uid(). No user write policy exists.
6. Seven expected Music indexes, including unique customer/ownership keys.
7. All 21 Music constraints validated, including Auth UUID foreign keys,
   composite customer ownership, unique IDs, event fingerprints/leases and plan
   projection checks.
8. Immutable customer-owner trigger present, along with expected internal foreign
   key triggers. No custom Auth application trigger appears in the output.

The six hosted body_md5 values exactly match the original CRLF function bodies:

| Function suffix | Hosted/source MD5 |
| --- | --- |
| preserve_customer_owner | b98614db375ec74dfb3a54ada09cbde3 |
| attach_customer | edff5517b0f261db64430fed65001381 |
| reserve_checkout | c3a258dc21d92cc1cf34ed2e9996029e |
| claim_delivery | 321e6822eef0c4ab17d572e560cafa4a |
| complete_delivery | 2bcf6d073d0df1aa1027f5aea0e2bbe1 |
| fail_delivery | 44e52623590286c1c3d6ecf248e12f66 |

A first local comparison using universal-newline text reads mismatched these hashes;
comparing the original CRLF bytes resolved all six. No hosted SQL discrepancy or
installer change was found.

The installer ran as one BEGIN/COMMIT transaction, including collision guards,
ACL cleanup and effective-permission assertions. Local collision/late-failure
rollback was already verified in Phase 5; deliberate failure was not rerun hosted.

## Pending checks and exact next step

Neither required test credential was available in the checked process environment
or local configuration. No credentials were retrieved from the dashboard, printed
or committed. No synthetic Auth accounts were created and no fixture RPC was run.

Load this isolated project's keys locally using the hidden-prompt instructions in
`MONETIZATION_PHASE6_HOSTED_REHEARSAL_20261112.md`, then run:

```powershell
python scripts/verify_music_phase6_hosted.py --approved-project smpyutzfktjgpdibdbqb --preflight-and-installation-verified --pause-for-sql-role-harness
```

Required names: MUSIC_PHASE6_TEST_ANON_KEY and
MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY. The harness currently requires project-bound
legacy JWT API keys; it rejects newer opaque key formats and other projects.
Do not paste secret values into chat or source files.

At the pause, use the two newly created synthetic accounts for the prepared
rollback-only SQL role and lifecycle harnesses before continuing persistent REST
fixtures. See the Phase 6 runbook for exact SQL Editor substitutions and cleanup.
These checks remain pending:

- Actual SET ROLE denial attempts and cross-account RLS with fixture rows.
- Hosted creation/renewal/cancellation/expiration/failed-payment recovery RPCs.
- Duplicate/out-of-order delivery, atomic failure/recovery and ownership behavior.
- Real Auth JWTs and PostgREST schema-cache/API behavior.
- Two-worker mapping, Checkout-reservation and event-lease concurrency.

The visible organization banner warns that its grace period is over and requests
may stop when quota is exhausted. No billing/quota settings were changed. Confirm
API availability before the credentialed rehearsal; dashboard SQL success alone
does not establish Auth/REST availability.

**GO for the already-authorized credentialed synthetic rehearsal when keys are
available. Stripe end-to-end readiness remains unverified.** Stripe test Price ID,
Portal configuration, webhook signing/configuration and the matching Render backend
remain separate prerequisites. No Stripe, Render, Streamlit, Baseball or shared
Suite change was made. No push, merge or production application deployment occurred.

## Preservation and recovery

Do not rerun the fresh installer: its collision guard will reject installed objects.
Do not run the historical generic billing migrations. Preserve the installed schema
and evidence. Investigate API-test failures without resetting customer mappings or
dropping tables. Once test records exist, retain the synthetic run identifier and
follow the runbook's scoped recovery/reconciliation process.

No browsers or servers were launched in this resumed turn; the existing Chrome
session was used. No unrelated process was stopped. Resource sample after SQL
verification: 3.05 GB available RAM, CPU 25.2%, 143.65 GB free disk. No browser suite
or heavy concurrent test job ran. Application code and installer SQL are unchanged;
only this outcome report was added locally.
