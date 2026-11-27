# Music health-only Render deployment handoff - November 27, 2026

GO for an explicitly approved staging-only push, followed by a separately approved
new Free health-only Render service. No push or deployment has occurred.
Billing-enabled deployment and payment testing remain NO-GO.

## Evidence and source

Branch: feature/music-billing-resume-20261127.
First staging-only commit: 70ecd90007460ad44d106e96f3a8417cdaaefaff.
The subsequent readiness commit records reports/scripts and final checks; obtain its
exact SHA with git rev-parse HEAD and the push range with git log origin/dev..HEAD.

Remote read on November 27 confirms dev remains db317f3f7c295f2abc197d5065203f7b12bac3b1
and main remains 377e7192fde5c6ba4ec618e91028c5c0202c6235; the staging branch does
not yet exist remotely. This branch descends from current remote dev. Security
commits f2e9e7fc and 1ac5e917 are ancestors; suite_auth_browser.py,
suite_storage_supabase.py, suite_security_module_refresh.py and the Music entry
point are unchanged relative to current remote dev. No dev/main merge is needed.

Hosted REST/JWT/lifecycle/concurrency passed, run 93531926c52e. User confirmed the
owner-SQL harness in smpyutzfktjgpdibdbqb returned:
PASS: owner harnesses completed; rollback left no test fixtures or constraint
This owner-reported result satisfies the pending SQL gate; no rerun is needed.

Final lightweight validation: 101 tests passed in 4.97s. Covers staging guards,
health, disabled Checkout/Portal/webhooks with no provider calls, Blueprint secret
omission, Stripe isolation, SQL preparation and session-link security. Initial new
Blueprint test used unavailable PyYAML; rewritten without adding dependencies and
rerun successfully. SQL Editor script parses as 38 SQL statements/10 PL/pgSQL blocks.

Only explicit report/script/test files are staged. Private config, JWT/API keys,
pytest fixture directories and test runtime artifacts are excluded. Do not use
`git add .`. No new hosted writes were needed for these final checks.

## Push checkpoint - approval required

Review `git log --oneline origin/dev..HEAD` and `git diff --stat origin/dev..HEAD`.
After approval, push only:

    git push origin HEAD:refs/heads/feature/music-billing-resume-20261127

Run from this branch/worktree. Do not use --all, --mirror, --force or push dev/main.
Verify the remote staging SHA matches the approved HEAD before Render creation.
If dev advances, reassess compatibility; do not merge branches without approval.

## Render settings - separate deployment approval required

Use deploy/render.music-staging-health-only.yaml as the configuration reference.
Do not apply deploy/render.music-staging.yaml (later billing-enabled template),
root render.yaml, or existing Suite/Music/Baseball services/environment groups.

1. Render Dashboard -> New -> Web Service -> connect
   Coakley11/ai-music-practice-coach, after approved branch push.
2. Name: music-billing-staging. Branch: feature/music-billing-resume-20261127.
   Root directory: blank (repository root). Runtime: Python 3.
3. Instance: Free. Stop if unavailable. Check workspace quotas/spend limits first;
   Free instances still consume included bandwidth/build usage. No disk or database.
4. Build: pip install -r requirements-billing.txt
5. Start: python -m uvicorn monetization_staging:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
6. Health check path: /billing/health. Auto-Deploy: Off/manual.
7. Add only these environment entries, using private fields for secrets:

| Name | Value/source |
| --- | --- |
| PYTHON_VERSION | 3.12.8 |
| MUSIC_BILLING_ROLLOUT | test |
| MUSIC_STRIPE_MODE | test |
| MUSIC_BILLING_SUPABASE_URL | https://smpyutzfktjgpdibdbqb.supabase.co |
| MUSIC_BILLING_SUPABASE_ANON_KEY | Existing isolated legacy anon key, private field |
| MUSIC_BILLING_SUPABASE_SERVICE_ROLE_KEY | Existing isolated legacy service_role key, private field |

Render supplies PORT. Do not attach a shared environment group. Omit all STRIPE_*
variables, MUSIC_STRIPE_PORTAL_CONFIGURATION_ID, MUSIC_PUBLIC_BASE_URL,
MUSIC_BILLING_SERVICE_URL, SUITE_* and entitlement development controls.
MUSIC_STRIPE_MODE=test is the only required Music Stripe setting for this boot.
The staging wrapper validates the exact isolated URL/key claims and rejects live
Stripe keys or Suite environment variables. Never change existing Music Suite auth.

8. STOP before Create/Deploy until separate deployment approval. Creation launches
   an initial deployment even when Auto-Deploy is Off.

## First deployed health verification

After approved creation, verify the build log reports Python 3.12.8 and that the
service deployed the exact approved staging SHA. Open:

    https://<assigned-render-host>/billing/health

Require HTTP 200 and JSON containing:

    rollout: test
    stripe_mode: test
    checkout_enabled: false
    client_enabled: false
    webhook_enabled: false
    credentials_match_mode: false
    monthly_price_configured: false
    annual_price_configured: false
    public_base_url_configured: false
    billing_service_url_configured: false
    supabase_configured: true

Enforcement may report true in test rollout; it does not enable payments. A health
200 proves runtime/configuration, not live provider connectivity or signed delivery.
Free services may take about a minute to wake after idle. Record URL, deployed SHA,
Python version, UTC observation time and sanitized health JSON. Never publish keys,
headers, session URLs or raw Auth responses. No payment or webhook setup is needed.

## Remaining gates

Health-only: exact push approval, separate deployment approval, available Free
capacity/quota, private environment entry, actual build and hosted health evidence.

Billing/payment later: exclusive Music-vs-Baseball sandbox confirmation, explicit
Portal selection, own signed snapshot webhook at /billing/webhooks/stripe with
API 2026-10-28.endive, private endpoint signing secret, and separately approved
billing enablement/payment test. Leave all of these disabled for the first deploy.

Official references checked:
- https://render.com/docs/free
- https://render.com/docs/python-version
- https://render.com/docs/blueprint-spec
- https://render.com/docs/deploy-flask (Web Service creation flow only; backend remains ASGI)
