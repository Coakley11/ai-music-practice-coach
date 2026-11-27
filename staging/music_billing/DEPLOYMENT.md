# Music billing staging frontend - deployment handoff

## Local preparation outcome

Branch: feature/music-billing-frontend-20261127, based on committed billing baseline
c15ac8443a431edf73e2e981951f13c803a057d5. Existing billing setup worktree and pending
Stripe/Portal documents/scripts were preserved. No existing Music source/config file
was changed; only the new staging frontend, tests and this handoff were added.

146 focused tests passed in 9.64s, including 46 frontend tests and headless
Streamlit AppTest sign-in, Free display, sign-out, return-page and configuration
checks. Tests cover mocked Pro/expiry/payment-failure states, foreign JWT/project,
service-role credentials, forbidden settings, cross-user rows, redirects/proxies,
secret-safe errors and absent payment calls. No browser, hosted request, identity
creation, payment, Stripe operation, push or deployment ran. RAM available sampled
4.41 GiB. Local Python 3.13.7, Streamlit 1.59.1. Actual Community Cloud Python 3.12
build remains to be verified after approval; package metadata supports that version.

## What the frontend does

Entry: staging/music_billing/app.py; title Music Practice Coach - Billing Staging
(the visible title uses the requested en dash). User signs in with a PRE-CREATED
synthetic email ending @example.invalid. Password flow targets only
https://smpyutzfktjgpdibdbqb.supabase.co/auth/v1/token?grant_type=password; a server
GET /auth/v1/user verifies the JWT after local issuer/role/expiry guards. JWT decoding
alone is not treated as signature verification. No signup/reset/OAuth/email-link
or user creation path exists.

Entitlement reads reuse SupabaseEntitlementProvider and Music's existing projection,
status and expiry rules. A pinned read-only transport uses isolated anon key plus
user JWT, exact owner filter and row-ownership assertions. No raw subscription table,
backend write RPC or Suite cloud data is used. Failed authentication/read clears
local auth; there is no stale paid-state cache or query-driven plan override.

Passwords/refresh tokens are not saved in the auth record. Password form clears
on submit. Access token remains only in server-side Streamlit session memory.
Sign-out clears frontend auth/form state. There is no browser/local-storage/cookie
or URL sign-in restore; session expiry/reload can require signing in again. Local
sign-out does not perform a hosted token revocation call.

Return queries are cleared without reading/rendering their values. A success query
never grants Pro. A neutral return message instructs users to verify subscription
state by signing in. Do not share initial browser URLs containing session IDs.

Checkout and Customer Portal buttons are hard-disabled, including when signed in.
They reference the existing Music billing client functions but never call them.
Configuration changes alone cannot activate these UI controls; later enablement
requires explicitly reviewed frontend code. Backend is fixed to the Music staging
origin for any future integration, not configurable to another host in this build.
No full Music app/Suite modules are imported, verified in a fresh process test.

This is a billing staging interface, not a clone of full practice/Composition UI.
It verifies auth/subscription state and later billing journey; full Pro feature
acceptance remains a separate full-app staging check.

## Exact deployment instructions - STOP pending separate approval

1. Review local commit (git rev-parse HEAD) and approve pushing ONLY
   feature/music-billing-frontend-20261127. Do not merge into dev/main or alter
   Music Dev/backend branches. This branch must stay isolated; Community Cloud
   updates apps from linked branch changes, so subsequent pushes require review.
2. Confirm available FREE Streamlit Community Cloud capacity. Stop if unavailable;
   do not upgrade, replace or reuse Music Dev/production.
3. After separate push/deployment approval: share.streamlit.io -> Create app ->
   existing GitHub repo -> Coakley11/ai-music-practice-coach.
   Branch: feature/music-billing-frontend-20261127
   Main file path: staging/music_billing/app.py
   Optional proposed subdomain: music-practice-coach-billing-staging, ONLY if
   available. The actual assigned URL is not yet known or verified.
4. Advanced settings -> Python 3.12. Confirm minimal requirements from
   staging/music_billing/requirements.txt are selected. Community Cloud searches
   the entrypoint directory before repository root, avoiding full audio/AI Python
   requirements. Existing root packages.txt may install ffmpeg; the frontend does
   not launch it or import the audio engine. No package install ran locally.
5. Enter ONLY the following top-level TOML into the NEW app's private Secrets panel:

```toml
MUSIC_BILLING_ROLLOUT = "test"
MUSIC_STRIPE_MODE = "test"
MUSIC_BILLING_SUPABASE_URL = "https://smpyutzfktjgpdibdbqb.supabase.co"
MUSIC_BILLING_SUPABASE_ANON_KEY = "<isolated project's public anon JWT>"
```

No [suite_activity] block, Suite settings, server-role key, Stripe secret/signing
secret, AI key or inherited env group. Guard rejects unapproved secrets, conflicting
settings, wrong project/role and activation/dev-control environment variables.
Keep MUSIC_PUBLIC_BASE_URL AND MUSIC_BILLING_SERVICE_URL UNSET here and leave
Render's six-entry health-only environment unchanged. Do not copy Dev secrets.
6. STOP before Deploy until deployment approval is explicit. Creating the hosted
   app is itself a deployment. Capture exact approved commit and assigned URL.

## Hosted verification after approval

- New customer-facing HTTPS URL and staging banner; verify deployed branch/commit
  and actual Python version from private app logs without exposing credentials.
- Correct isolated project and anon-only configuration; invalid config shows a
  generic blocked screen before any network call. Do not test by inserting real
  production credentials; use offline guard tests for rejection.
- Sign in using only known pre-created synthetic users with available passwords;
  no password resets or account creation without explicit approval. Compare JWT
  identity/own subscription read in isolated project. Keep prior Phase 6 records.
- Free/Pro render follows existing entitlement status/expiry rules, never query
  flags. Do not write subscription fixtures or run payment tests to get Pro under
  the frontend deployment approval; use existing suitable isolated evidence only.
- Sign-out removes display/state; return visit asks to sign in. No user A data
  appears for user B. Checkout/Portal buttons remain disabled throughout.
- Visit ?billing=success&session_id=nonsecret_test_marker: neutral message, cleared
  query, no automatic sign-in/Pro grant/provider calls. No actual Checkout session.
- Recheck Music backend health remains checkout_enabled=false,
  client_enabled=false, webhook_enabled=false. No new Stripe destination exists.

Only after the real URL passes these checks should it be proposed for the new
Music Portal's default_return_url and backend MUSIC_PUBLIC_BASE_URL. Do not edit
Stripe/Render or fill that variable now. Backend URL remains distinct:
https://music-billing-staging.onrender.com. No production frontend substitute.

## Rollback

Before any hosted work, rollback is simply leaving this local branch unpushed.
After an approved deployment, stop/remove ONLY the newly named Streamlit staging
app if unsafe or broken; leave Music Dev, production, backend, Stripe and Supabase
unchanged. Remove only that app's private secrets when retiring it. Do not delete
synthetic users, billing records or shared resources. Any later Portal/Render
activation needs its own rollback/approval; it is not part of this deployment.

Official references checked:
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
