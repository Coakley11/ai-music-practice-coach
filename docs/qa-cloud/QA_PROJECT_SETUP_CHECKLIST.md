# Suite QA project setup checklist (proposal -- nothing here has been executed)

Purpose: provision an **isolated** Suite QA Supabase project so the cloud-backed active-context store
and real phone <-> Dell acceptance can run without touching production or the Baseball QA project
(`przcoiazzgsadiyrgrou`). No secret values belong in this file.

Security statement: the QA design keeps the Suite's existing server-side access model (server key,
RLS off, ownership enforced by the store contract on exact `user_id + workspace_id`). This is a
QA-development decision, **not** production security approval and **not** RLS acceptance. Moving the
whole Suite to user JWTs + RLS is a separate project.

## 1. Supabase project settings
- [ ] New project, new name (e.g. `suite-qa-isolated`), **new project ref** never used by any deployment.
- [ ] Region/plan: any; note the ref in the checklist owner's private notes, not in the repo.
- [ ] Auth: email provider on; "Confirm email" off, or use an inbox you control for the QA account.
- [ ] Auth redirect URLs: only the two QA Streamlit URLs (section 6). No production URL.
- [ ] API: note `URL`, `anon` key, `service_role` key privately (do not paste into chat/repo).
- [ ] Confirm the dashboard shows **no** existing data (empty project) before migrating.

## 2. Migrations to run (in order, SQL editor of the QA project only)
- [ ] `001_suite_activity.sql`
- [ ] `002_suite_account_memory.sql`
- [ ] `003_suite_account_memory_resume.sql`
- [ ] `004_suite_active_context.sql` (from `004_suite_active_context.sql.proposed`; review first)
- [ ] Verify: `select count(*) from public.suite_active_context;` returns 0.
- [ ] Verify grants (RLS is off, so grants are the guard):
      `select grantee, privilege_type from information_schema.role_table_grants where table_name='suite_active_context';`
      must NOT list `anon` or `authenticated`. Do the same check for the pre-existing suite tables and note
      the result (they share the same exposure class; out of scope to fix here).

## 3. QA account
- [ ] Create one synthetic user in Auth (Dashboard > Authentication > Users), e.g. `suite-qa+active-context@<a domain you control>`.
- [ ] Ensure a matching `suite_users` row exists (the app creates it on first login; otherwise insert with that `external_id`).
- [ ] Create two saved resources for that account through the app: one Custom, one Composition (needed for acceptance F and G).
- [ ] Never reuse a real person's account.

## 4. Music staging secret names (values stay in Streamlit Secrets only)
Same block as the existing template, QA values:
- `[suite_activity]` `supabase_url`, `supabase_key` (server key), `supabase_anon_key`
- `[suite_activity]` `suite_user_id`, `suite_user_email` (the QA account), optionally `suite_auth_enabled = true`
- Env/secret toggles for the future store: `MUSIC_ACTIVE_CONTEXT = "cloud"` (see section 8),
  `SUITE_QA_PROJECT_REF` (the QA ref; the store must refuse to run if the configured URL's ref differs)

## 5. Command Center staging secret names
- Identical `[suite_activity]` block (same QA URL/keys/user) -- the template already requires one block per suite app.
- No active-context flag needed: Command Center only triggers Resume; it does not read/write the record.

## 6. Streamlit staging deployment settings
- [ ] Two NEW non-production Streamlit Cloud apps (Music + Command Center), branch = the approved reconciled branch, not `main`/production.
- [ ] Secrets set per sections 4/5 on these apps only; the existing dev/production apps are not edited.
- [ ] Record the two URLs; add them to the QA project's Auth redirect list.

## 7. Prove neither deployment points at production (do all)
- [ ] The QA `supabase_url` host differs from the host in the production/dev apps' secrets (compare the ref segment privately; do not paste).
- [ ] Marker row: insert `suite_users.external_id = 'qa-marker'` in QA only; confirm it is absent in production/dev and present via both QA apps.
- [ ] Startup guard (to be built with the store): refuse `MUSIC_ACTIVE_CONTEXT=cloud` unless the URL's ref equals `SUITE_QA_PROJECT_REF`; log only `qa` / `refused`, never the ref or keys.
- [ ] Network check: during acceptance, the apps' only Supabase host is the QA host.

## 8. Verify both apps use the same QA Suite account
- [ ] Sign in on Music and Command Center with the QA account; both show the same `suite_user_id` hash prefix (compare first 6 chars of a hash, not the id).
- [ ] A saved item written in Music appears in Command Center's Continue list (and vice versa for resume items).
- [ ] Phone and Dell both log in as that account.

## 9. Enabling `MUSIC_ACTIVE_CONTEXT=cloud` later
- [ ] Only after the store implementation is approved and passes the unit/contract tests against the RPC.
- [ ] Set in the QA Music app only; default stays dark/`local`. Rollback = unset the variable (feature goes dark; no data change).

## 10. Rollback / cleanup
- [ ] Unset `MUSIC_ACTIVE_CONTEXT` in the QA Music app.
- [ ] `drop function ...; drop table ...;` (from the `.proposed` file) in the QA project if abandoning.
- [ ] Delete the two staging Streamlit apps; delete the QA project; remove the QA account.
- [ ] Nothing in production or Baseball QA needs reverting because nothing there is touched.

## 11. Tests to run once it exists
- Contract tests of the Supabase store against the RPC: initial insert, lost insert race, stale expected revision, concurrent writers (N threads -> unique consecutive revisions), `field_at` round trip, wrong user/workspace never visible, malformed record rejected.
- Acceptance A-J from the approved plan (phone 390px / Dell 1440px, genuine separate profiles), including a real Command Center card click for historical Continue, genuine saved Custom and Composition, simulated write failure with retry, and no spurious revisions.
