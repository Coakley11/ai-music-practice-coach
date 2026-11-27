# Music Stripe sandbox: private local configuration

Private file (created empty, without overwriting an existing file):

`C:\Users\danie\Documents\GitHub\ai-music-practice-coach\.worktrees\billing-phase1-20261111\.music-phase7.local.json`

Git ignore/untracked status was confirmed before requesting any key entry. The
file was opened in Cursor. Paste the existing Music Practice Coach Staging sandbox
sk_test key only into STRIPE_SECRET_KEY, between its empty JSON quotes, then Ctrl+S.
Do not paste it into chat. The file is plaintext: keep it private, unsynced and out
of shared backups. No key is placed in source, process arguments or logs.

STRIPE_PRO_MONTHLY_PRICE_ID is already set to the user-provided
`price_1Ub8MiGSM5yahQursL7MlBcs`. Leave MUSIC_STRIPE_PORTAL_CONFIGURATION_ID blank
until inspection identifies the correct existing configuration. Supabase credential
files, Baseball settings and deployed services remain unchanged.

After the user saves the key, run from this billing worktree:

```powershell
python scripts/inspect_music_stripe_sandbox.py --config .music-phase7.local.json
```

The script accepts only an sk_test key and the exact user-provided Price ID. Its
only API operations are GETs to the pinned Stripe origin/version:

- /v1/account (reports only account ID, no identity/billing fields)
- /v1/prices/price_1Ub8MiGSM5yahQursL7MlBcs with product expansion
- /v1/billing_portal/configurations, bounded pagination

Redirect following and inherited proxy configuration are disabled. Errors suppress
credentials and raw response bodies. API version matches the backend:
2026-10-28.endive. No Stripe POST/update/delete, payment or deployment operation is
implemented. No Supabase request is made.

The report checks active/test-mode monthly recurrence and product identity, and
returns allowlisted commercial configuration fields. Dashboard sandbox display-name
identity is not established by /account; object availability and livemode establish
test-key scope, with product Music metadata/name requiring review.

A unique active, non-live, explicitly Music-tagged, non-default Portal configuration
can be identified automatically. Empty, default-only, untagged or ambiguous results
require review; never silently adopt Baseball's/shared default or create a new
configuration. Inspect cancellation/payment-method/invoice features separately from
ID selection. The script does not write a Portal ID into the private config.

At the preparation checkpoint the key field was still empty. **Price and Portal
inspection have not run.** Offline regression result: **11 passed in 1.70 seconds**;
no external API request was made by these tests. The rest of Phase 7's deployment
and first-payment approval gates remain in force.

Official endpoint references:
https://docs.stripe.com/api/prices/retrieve
https://docs.stripe.com/api/customer_portal/configurations/list
