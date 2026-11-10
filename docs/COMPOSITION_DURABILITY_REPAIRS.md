# Composition persistence repairs (local candidate)

Base:038fb0da, preserving the existing Home/sidebar/Continue/restoration/branding work.
No live data migration, database/schema change or automatic personal recovery is included.

## Save confirmation
A Composition checkpoint separates in-memory edits from disk and cloud results. Per-attempt flags are reset so another page's successful transaction cannot acknowledge a failed save. After the existing conditional workspace save, complete canonical Composition content is compared with disk JSON and account-scoped cloud readbacks. The fingerprint includes complete chords, melody, lyrics, section order, global key/BPM/meter, project metadata, workflow, library and deletion provenance. A title or row-count match is insufficient.

Only matching cloud content displays durable success. A verified server-local copy displays a warning: it is temporary hosted storage, not a backup on the user's device. Unverified/session-only work remains dirty and displays an error on Save. The ordinary draft UI also shows its current verification status. No automatic retry or unconditional cloud-write fallback is added. Composition save activity is reported only after verified cloud persistence.

Explicit Composition library-save reasons normalize to the already authorized composer_edit strict-egress intent. Passive autosaves remain unapproved, and all hydration/account/revision/CAS safeguards stay in place. This fixes the previous button reason being rejected in strict mode. Complete Composition content also participates in duplicate-save fingerprints, without discarding musical section labels; timestamps alone do not force a new document save.

## Restore and deletion
Composition workspace schema2 adds library_initialized and deleted_document_ids; the enclosing Music file format remains version1. Existing populated schema1 documents remain readable, and all document fields are copied intact.

An explicitly uninitialized new empty block can fall back to a populated legacy or nested Composition workspace. An old empty block without provenance is ambiguous: it could mean an earlier intentional deletion. Preserve its legacy document in session, block workspace persistence, and present Recover/Keep current choices. Do not silently replace a live document. The recovery choice fills missing library IDs, never overwrites an existing live ID. It does not claim to recover the user's missing cloud document.

Explicit deletion records document IDs and clears the active canonical reference. Tombstones survive canonical projection, widget/page snapshots and Songs-library hydration, including legacy title-key aliases. Confirmed empty libraries do not fall back to stale snapshots. Declining an ambiguous legacy recovery records that choice so it does not reappear as an automatic resurrection. Tombstones have no automatic expiry.

## Validation and remaining limits
Focused regression suite and actual Streamlit AppTest results are recorded in the external local evidence report; tests use disposable projects, credential-stripped environments and fake cloud boundaries. No test writes to a real account. Authenticating and hydrating a disposable remote workspace remains necessary before claiming live-cloud acceptance. Existing personal cloud data has no complete Composition blob; these repairs cannot invent the missing music.

## Safe integration plan
1. Preserve038fb0da and all recovery snapshots; keep this repair as a separate local commit descended from it.
2. Finish the remaining media backup and supported recovery assessment. Preserve the existing hosted session; no diagnostic deployment/reboot.
3. Configure a separately authorized disposable cloud workspace/project. Verify complete-document write/readback, reload/new session, stale revision conflict and deletion behavior without personal data.
4. Refresh origin/dev; reconcile any newer Claude changes in a separate integration candidate. Re-run affected focused tests and desktop/mobile acceptance sequentially under shared resource gates.
5. Present the exact candidate and recovery limitations for explicit push/redeployment approval. Do not push while approval is withheld. Main remains untouched.
6. A code rollback does not restore cloud data and older code may not understand deletion provenance; any recovery must preserve the then-current state and be reviewed separately.

## Hosted-session recovery limitation
Official Streamlit documentation ties Python Session State to its WebSocket connection. Community Cloud management documents logs/settings/reboot controls, not a general read-only session/filesystem export. No supported such access is available through the tools here, and the existing app has no verified complete-workspace download facility. Browser storage is not a substitute. Therefore the original hosted document remains unverified; do not inspect secrets, attach to private runtime internals, inject code, redeploy an exporter, press Save or reset/restart in an attempt to obtain it.

References:
https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state
https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
