# Phase 6C local credentials and hosted execution

The initial credential-blocked checkpoint below is historical. Hosted execution
has since passed; see [Phase 6C results](MONETIZATION_PHASE6C_HOSTED_RESULTS_20261112.md).

The hosted schema installation succeeded in Phase 6B. Do not run the installer
again. This phase changes only the local rehearsal harness/configuration workflow.

## Exact credential location

An empty local file was created, without overwriting any existing file:

`C:\Users\danie\Documents\GitHub\ai-music-practice-coach\.worktrees\billing-phase1-20261111\.music-phase6.local.json`

It contains these three fields:

```json
{
  "MUSIC_PHASE6_TEST_URL": "https://smpyutzfktjgpdibdbqb.supabase.co",
  "MUSIC_PHASE6_TEST_ANON_KEY": "",
  "MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY": ""
}
```

In the isolated Supabase dashboard, confirm the URL/project links contain
**smpyutzfktjgpdibdbqb**. Open Settings > API Keys and the legacy keys tab.
Copy the existing legacy anon JWT into MUSIC_PHASE6_TEST_ANON_KEY and the existing
legacy service_role JWT into MUSIC_PHASE6_TEST_SERVICE_ROLE_KEY. Save the file.
Do not use a JWT signing secret, database password, personal access token or Stripe
key. Do not regenerate/rotate/enable credentials or change production configuration.

The current harness intentionally requires legacy JWT API keys to check each key's
project reference and role locally before any request. New opaque sb_publishable_*
and sb_secret_* keys are unsupported. Supabase recommends migration away from legacy
keys; that requires a separate guarded client change, not bypassing validation here.
Official source: https://supabase.com/docs/guides/getting-started/api-keys

The exact file is ignored by the worktree's .gitignore and confirmed untracked with
git check-ignore/git ls-files. No secret is added to a commit, printed or placed in
process command arguments. The file is **plaintext**, not encrypted: keep it in a
private local folder, do not sync/share it, and restrict Windows file access to your
own account as appropriate. Do not paste credentials into chat. No Windows ACL,
credential, cloud role or production setting was changed by this preparation.

This is the billing worktree, not the main checkout. Creating a similarly named file
in the main checkout does not configure this command and may lack this ignore rule.

## Exact commands and verification boundaries

In a local PowerShell terminal:

```powershell
Set-Location 'C:\Users\danie\Documents\GitHub\ai-music-practice-coach\.worktrees\billing-phase1-20261111'
python scripts/verify_music_phase6_hosted.py --approved-project smpyutzfktjgpdibdbqb --config .music-phase6.local.json --check-config
```

This checks the URL and key project/role claims without making any network request.
It does not cryptographically verify signatures. A wrong/missing/malformed key,
wrong URL, extra config field or conflicting shell variable stops execution without
displaying values. File credentials are not exported to the shell environment.

Next, verify actual key acceptance read-only:

```powershell
python scripts/verify_music_phase6_hosted.py --approved-project smpyutzfktjgpdibdbqb --config .music-phase6.local.json --verify-access
```

This only issues GET /auth/v1/settings with the anon key and GET
/auth/v1/admin/users?page=1&per_page=1 with the service-role key, against the fixed
isolated origin. It reports status assertions, never response bodies/identities.
Successful HTTP acceptance is separate evidence from locally decoding key claims.

Once both checks pass, the already-authorized synthetic rehearsal command is:

```powershell
python scripts/verify_music_phase6_hosted.py --approved-project smpyutzfktjgpdibdbqb --config .music-phase6.local.json --preflight-and-installation-verified
```

The command automatically performs both local validation and read-only acceptance
checks before creating accounts. It creates two synthetic accounts, tests real Auth
JWTs, PostgREST entitlement isolation/denials, ten subscription projections,
duplicates, released-lease rejection and two-worker ownership/reservation/event
concurrency. No Stripe request is made; provider snapshots/IDs are synthetic.
It retains records and prints a synthetic run identifier for review. On failure,
retain that identifier and investigate before rerunning; each run creates a new pair.
No cleanup, Auth deletion, ownership reset or database reinstall is automatic.

For the additional rollback-only SQL harness checkpoint, add
--pause-for-sql-role-harness and follow the existing Phase 6 runbook. Without that
flag the JWT/REST suite runs uninterrupted, but the separate SET ROLE/SQL lifecycle
harnesses are not executed. Do not report them as passed from REST evidence.

All request URLs are pinned to the isolated origin regardless of configuration.
Redirects and inherited proxy settings are disabled. The protected Suite URL is
rejected before any request. Existing Suite/login/production app settings are not
inputs to this harness and must remain unchanged.

## Verification status at preparation checkpoint

- Hosted installation and catalog permissions: verified in Phase 6B.
- Config file URL: MATCH to the isolated project.
- Secret file: ignored and untracked; values not logged.
- Keys: both fields were still empty when checked after the first ready response.
  No network or synthetic writes occurred from that failed configuration check.
- Hosted key acceptance, accounts, JWT/REST, lifecycle and concurrency: pending
  until populated keys pass validation. Record actual execution separately.

Resource sample at start: 2.21 GB free RAM, CPU 15.1%, 143.55 GB disk free. No browser
or server was launched. Focused tests run sequentially. Initial tests hit an existing
Windows temp-directory permission error; an assignment-specific pytest basetemp
inside ignored .pytest_cache resolved it without altering other directories.

Local verification: **133 passed in 11.32 seconds**, including 28 configuration,
transport, target, ACL/parser and credential-redaction guard tests plus 105 existing
focused billing tests. No network requests are made by those tests. The new CLI
check-config test proves it does not call hosted verification or synthetic writes;
another test proves a failed read-only acceptance check prevents test writes.
