# Access-control hotfix: deployment checklist, configuration and rollback

Scope: closes the cross-account access defect that exists whenever sign-in (`SUITE_AUTH_ENABLED` /
`suite_auth_enabled`) is on. It changes no schema, migrates no data and never rewrites an existing ownership
record. It does not depend on `SUITE_IDENTITY_V2` (not part of this change).

## What the hotfix enforces (sign-in enabled)
| Rule | Behaviour |
|---|---|
| Identity | The account is the immutable Supabase **Auth user id**. The email (local part, "daniel"/"ariel" inside it, domain) is never an identity. |
| Own workspace | By default every account gets its own new workspace `u<first 20 hex of its id>`. |
| Legacy workspaces (`daniel`, `ariel`, an old local-part id) | Attached **only** to the Auth user ids listed in `SUITE_PERSONAL_ACCOUNTS`. Two ids listed for one workspace are ambiguous and attach to nobody. No first-come claiming. |
| Admin | **Only** Auth user ids in `SUITE_ADMIN_USER_IDS`. Email local part (`coakley11`, `daniel.cohen11`), full email, `external_id`, workspace name or any session field grants nothing. |
| Storage | Every workspace-scoped cloud key (read, write, CAS, delete, restore, list) is checked against the signed-in session; a foreign key or no session raises `PermissionError` before any request is built, so the service key cannot bypass it. |
| Stale records | A registry record or remembered workspace that names a workspace the account does not own is ignored (and left untouched on disk). |
| Account change | Logging out, or a different account taking over a browser tab, discards everything the previous account loaded into that session. |
| Bad configuration | Missing, empty or malformed settings grant **nothing** (fail closed). A malformed value is logged once. |

## Consequence you must plan for
Ordinary accounts that were using an old email-derived workspace (for example `sam` for `sam@x.example`) get a
**new, empty** workspace after this deployment. Their songs are not deleted or moved: they stay under the old key. To give
one back, add that person's Auth user id to `SUITE_PERSONAL_ACCOUNTS` (value = the old workspace id).
Do this only for accounts you can positively identify.

## Configuration (never put real ids in source code or chat)
Set as environment variables or in the Streamlit secrets block `[suite_auth]` (`personal_accounts`, `admin_user_ids`).
```toml
[suite_auth]
admin_user_ids = ["<auth user uuid of the administrator>"]
[suite_auth.personal_accounts]
"<auth user uuid of the daniel account>" = "daniel"
"<auth user uuid of the ariel account>"  = "ariel"
```
Environment form: `SUITE_ADMIN_USER_IDS="<uuid>,<uuid>"` and `SUITE_PERSONAL_ACCOUNTS='{"<uuid>":"daniel","<uuid>":"ariel"}'`.

How to get the ids without posting them anywhere: Supabase dashboard -> Authentication -> Users -> open the user
(identified by the email shown there) -> copy **User UID**. Paste it directly into the Streamlit Cloud
Settings -> Secrets box. Check the result with `python scripts/check_access_policy.py` (prints counts only).
Do not use emails here; entries that are not UUIDs are ignored.

## Deployment checklist
1. Before anything: confirm which deployments have sign-in on (see "Existing deployments" in the report); keep the
   others unchanged.
2. Supabase dashboard -> Authentication -> Users: review the list for accounts you do not recognise (read only).
3. Stage: deploy this commit to a staging copy of the app, with the two settings, against a non-production Supabase.
   Sign in as each owner and confirm their songs, Custom Progressions and settings load; sign in as an ordinary
   account and confirm it cannot see them.
4. Production: set the two settings first, run `scripts/check_access_policy.py`, then deploy.
5. Immediately afterwards: sign in as each owner; confirm songs/compositions are present and a save succeeds.
6. Watch for `PermissionError` / malformed-policy log lines for a day.

## Rollback (must keep the protection)
Removing the settings or redeploying the old code is **not** a safe rollback: the old code restores the vulnerable
mapping. Use, in this order:
1. **Fix forward in settings.** Locked-out owner: correct or add their Auth user id. Takes effect on the next run,
   touches no data, and is reversible.
2. **Go back to a previous hotfix commit**, never to a pre-hotfix one, if the new code misbehaves.
3. **Restrict instead of reopen.** If an owner cannot be re-attached quickly, leave them on their empty workspace:
   data is intact under the old key and nobody else can reach it.
4. Only a deployment that was already running with sign-in **off** (the documented default) may run pre-hotfix code,
   and only with sign-in still off.
The hotfix writes nothing that needs undoing: no migration, no ownership change. New accounts may get a new
`suite_users` row and an empty workspace; these are harmless and can stay.

## Verified vs assumed (read before deploying)
* **Observed** (anonymous page load of the Music app's public URL named in `suite_deep_links.py`, no interaction):
  the app shows "Sign in to continue" with **Log in / Create account / Reset password**. Sign-in is therefore
  enabled on that deployment. Which branch/commit it runs, and whether Supabase accepts public sign-ups, were **not**
  verified (testing sign-up would create an account in the shared Suite project; not done).
* **Assumed from the repository only:** `suite_auth_enabled` defaults off and the secrets template says to leave it
  off in production. The observation above contradicts that default for the URL checked.
* If Create account works there, the legacy defect is reachable now: treat as a priority security issue.
* Authentication settings of the shared Suite and Baseball projects were not read or changed.

## Auth-disabled mode (unchanged by this hotfix)
With sign-in off nothing here applies: the storage guard returns early, identity comes from the existing
`suite_user_id`/`default` profile, and no account is required. Staging results: no login gate, all pages load, an
anonymous profile with no `suite_user_id` sees no one's cloud data (separate `default` account row). A deployment that
sets `suite_user_id = "daniel"` is, by design, Daniel for every visitor: do not run such a deployment and a
sign-in deployment against the same database rows without understanding that they share the `music` row.

## Obtaining the account ids (the legacy accounts may have no Auth identity)
1. Supabase dashboard -> Authentication -> Users. Find the Daniel and Ariel people by the email shown there.
2. If a person has no Auth user, they must create one (Create account / invite) first; until then they cannot be mapped.
   Never create or edit an account on their behalf and never guess an id.
3. Open the user, copy **User UID**, paste straight into the Streamlit Cloud Secrets box (not chat, not a file in the repo).
4. Run `python scripts/check_access_policy.py` (counts only). Then sign in as that person on staging.
5. Before production, copy the existing `suite_users` / `suite_app_current_state` rows for `daniel` and `ariel` (export, no edits)
   so a mapping mistake can be compared against the original.

## `suite_sid` capability URL (separate, not fixed here)
After sign-in the URL carries `?suite_sid=<uuid>`; whoever holds that URL can restore the session (bearer secret, stored
server side with the refresh token; the hotfix authorises everything *after* restore, so it cannot help if the URL is
shared). Not release-blocking for this change because it is an existing mechanism and needs the victim's URL.
Near-term mitigations that keep recovery working: (1) tell users to log out on shared devices (logout now invalidates the
row and clears the tab); (2) follow-up change: refuse stored sessions older than N days using the row's `updated_at`
(already selected by the query) and drop `suite_sid` from the address bar once restored; (3) the token-encryption redesign
stays on the separate QA branch.
