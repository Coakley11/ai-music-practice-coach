# Practice Melody Slice D — My Uploaded Melody: BLOCKED

**Status: blocked on trustworthy per-user authentication/storage isolation.**
Not implemented. Do not build private-upload persistence on the identity/
storage architecture as it exists today without first resolving the items
below.

This document preserves the Gate D0 findings from the Practice Melody
feature work (`feature/practice-melody` branch) so they survive past that
branch and inform the account/commercialization project directly. It is a
dependency record, not a task list for the Practice Melody feature itself.

## Why this is blocked

Gate D0 asked seven concrete questions about the current auth/storage
architecture before any "My Uploaded Melody" persistence was implemented.
The findings, each grounded in specific files/lines rather than inference:

1. **Real-auth identity is a coarse profile slug, not a per-account id.**
   `suite_auth.resolve_auth_external_id()` maps a signed-in email through
   `_infer_external_id_from_email()` — a **substring match** ("ariel" in
   email -> `"ariel"`; "daniel" in email -> `"daniel"`; otherwise the
   email's local-part). `suite_auth.py:140-147`. The suite is architected
   around a small fixed set of named household profiles, not per-signup
   multi-tenancy.

2. **Two different authenticated users can resolve to the same storage
   owner**, two independent ways:
   - Substring collision by design (e.g. `notdaniel@example.com` maps to
     the same profile as the real Daniel).
   - `suite_user._resolve_account_user_id()` is `@lru_cache(maxsize=1)`
     with **zero parameters** (`suite_user.py:124-142`). Streamlit serves
     all concurrent sessions from one process via threads; this cache is
     shared process-wide, not session-scoped. It is only invalidated by an
     explicit `reset_account_cache()` call at the moment of a fresh login
     (`suite_auth.py:347-352`) — never on ordinary reruns for already-
     authenticated sessions. Under concurrent sessions, one user's
     resolved UUID can leak into another's `get_account_user_id()` calls.
     (`workspace_isolation_diagnostics.py` exists specifically to debug
     this class of bug — an acknowledged, tracked risk area already.)

3. **Unauthenticated/disabled-auth behavior is "everyone is one shared
   user."** `suite_auth.is_authenticated()` returns `True`
   unconditionally when `is_auth_enabled()` is `False`
   (`suite_auth.py:82-85`). This is the exact state of the deployment
   used to build and test Slices A-C: the UI shows *"Shared suite profile
   (no individual sign-in on this deploy)"* and the server log repeatedly
   prints *"Supabase is not configured."* The app's own diagnostic states
   the root cause directly: *"suite_auth_enabled is false — all users
   share legacy daniel workspace + secrets identity."*

4. **Bytes vs. metadata**: both exist and are cleanly separated already —
   `media_persistence.py`'s own docstring: *"metadata only, no blobs in
   envelope."* Metadata lives in a workspace-scoped local JSON file
   (optionally mirrored to a `suite_saved_items` row); bytes go to local
   disk and, when cloud is enabled, to Supabase Storage
   (`media_storage.py`). In the current local/no-cloud deployment,
   "storage" means a local file under a shared `daniel` workspace folder
   on one machine — not private to any specific person.

5. **No per-user security boundary on cloud storage.** The Supabase
   Storage client uses **one static shared API key for every user**
   (`media_storage._service_storage_client()` ->
   `create_client(cfg.url, cfg.key)`), not a per-user JWT. Enforcement
   that User B cannot fetch User A's object depends entirely on (a) the
   app never leaking another user's `storage_ref` string through its own
   UI, and (b) server-side bucket policy — neither verifiable from this
   codebase.

6. **No version-controlled schema for the tables in question.** The repo
   has exactly one SQL migration file
   (`supabase/migrations/20260927_monetization_m2.sql`, unrelated to any
   `suite_*` table, and containing no RLS/policy statements). The
   `suite_users` / `suite_saved_items` / `suite_app_current_state` /
   `suite_user_settings` tables used throughout
   `suite_storage_supabase.py`, and the `music-media` Storage bucket, have
   **zero tracked migrations** — they were created directly in a Supabase
   dashboard outside version control. Whether RLS is enabled on any of
   these tables, or whether the bucket has path-scoped access policies,
   cannot be determined from the code; it must be verified against the
   live Supabase project directly.

## Prerequisites before private user uploads (or any genuinely private
customer data) can be trusted

1. Replace the coarse email/profile-slug identity mapping with a real
   unique per-account identity model suitable for arbitrary outside users
   (not a fixed household-profile set).
2. Remove/fix the process-wide zero-argument `@lru_cache(maxsize=1)`
   account-ID resolution pattern. Account identity must be session/user
   scoped and must never be capable of crossing concurrent Streamlit
   sessions.
3. Define safe unauthenticated behavior. A public deployment must not
   silently treat all unauthenticated visitors as one shared user for
   private data.
4. Put the relevant Supabase schema/security configuration under
   auditable/version-controlled infrastructure where practical, including
   the tables used for user state/saved items.
5. Verify and test RLS rather than assuming it exists.
6. Verify Storage bucket policies and object-path ownership rather than
   relying solely on Python application filtering.
7. Ensure cloud storage access uses an appropriate security boundary for
   the architecture; do not assume a shared static API credential plus
   application-side path filtering constitutes user isolation.
8. Add adversarial multi-user tests before trusting this for private data:
   - User A cannot enumerate/read/update/delete User B's data.
   - Simultaneous A/B sessions never resolve the same account accidentally.
   - Logout/login/session switching cannot retain the previous user's
     identity.
   - Unauthenticated/default mode cannot access private authenticated
     data.
   - Guessed storage references cannot cross the user boundary.

## Scope note

This is an account/commercialization-infrastructure dependency, not a
Practice Melody feature task, and is explicitly **not** being solved on
`feature/practice-melody`. "My Uploaded Melody" continues to appear in the
Practice page's Chart & Melody tool as an explicit "coming soon" /
unavailable placeholder (added in Slice C) that makes no persistence
claim — it is not described anywhere as private storage that works today.
