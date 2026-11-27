# Separate Suite privilege hardening proposal - NOT APPLIED

The owner-run preflight reports broad public-schema defaults and effective
anon/authenticated TRUNCATE privileges on suite_activity_events and
suite_app_current_state. RLS being enabled does not restrict TRUNCATE. This is a
real privilege finding, but does not by itself prove a public REST TRUNCATE endpoint
exists: audit exposed RPCs and any SQL execution paths before describing exploitability.

The new Music installer does not change these tables, their grants, shared roles,
existing functions, auth triggers or global defaults. Its grant cleanup targets
only the newly created Music objects. This document is a separate work proposal,
not part of Music installation authorization.

## Proposed controlled sequence

1. Capture effective table AND column privileges, role memberships, PUBLIC/default
   ACLs, RLS policies, exposed RPC definitions/owners and application write paths.
   Establish the exact deployed commits for Music, Baseball and Command Center.
   Back up Suite data and schema/grants before any approved change.
2. Rehearse on an isolated schema/data clone with synthetic records. Verify normal
   activity append, current-state UPSERT/CAS, saved composition restore, session
   refresh, Command Center resume and Baseball saves using actual anon/user/server
   roles. Identify any legitimate maintenance function relying on elevated rights.
3. Prepare a separate, exact-role/table patch revoking TRUNCATE from PUBLIC, anon
   and authenticated on just these two Suite tables. Trace inherited TRUNCATE to
   its grant source and remove only the relevant table grant; avoid global role
   membership changes affecting Baseball. No application-user workflow should need
   TRUNCATE; prove that in staging before approval. Do not test TRUNCATE on production,
   even inside a rollback transaction (locks and other side effects can still occur).
4. Separately review unnecessary DELETE, REFERENCES, TRIGGER and column grants.
   Preserve required user-owned INSERT/UPDATE paths until RLS/API regression tests
   establish a safe replacement. Do not blindly REVOKE ALL on shared tables.
5. Review every actual object-creating role's default privileges. Default-ACL fixes
   govern FUTURE objects and do not repair existing tables. Scope any approved
   changes carefully and test other applications' future migrations. Music's
   installer independently strips defaults on its own objects, without changing
   the shared defaults.
6. Stage least-privilege server credentials/app-specific RPC access. A shared
   project service-role key can still bypass RLS on existing Suite/Baseball objects;
   the Music-only ACLs do not turn that credential into a project-isolated role.
   A dedicated Music runtime role/API trust configuration requires a separate
   implementation/provisioning review, not an unreviewed credential substitution.
7. After explicit hardening approval, apply the narrow patch in a controlled window,
   rerun effective-permission and real-user tests, and watch all three apps' saves.
   Recovery should restore only the specific necessary grant supported by evidence,
   not broad PUBLIC/TRUNCATE privileges or stale table data.

No proposed hardening SQL has been executed. Do not include this work in the Music
installer or use it as a reason to silently modify Baseball or existing Suite data.
