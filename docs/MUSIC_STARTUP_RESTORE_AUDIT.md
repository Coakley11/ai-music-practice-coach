# Music startup restore audit (2026-06-17)

Short audit of **Music app reboot behavior** vs Baseball — investigation only, not a persistence project.

## User observation

After rebooting/restarting the Music app:

- Returns to **Practice** page
- Active song resets to **Say — John Mayer**

Baseball typically restores last page and workspace.

## Verdict

**Mostly expected fallback behavior**, not a single “restore disabled” flag — but it can **look like a bug** when cloud/disk restore fails or returns an empty/incomplete blob.

| Scenario | Song | Page | Expected? |
|----------|------|------|-----------|
| Cloud restore succeeds with saved song + workspace | Restored | Restored | Yes |
| Fresh session, no saved state | **Say** (first trusted-core record) | Practice (default nav) | Yes — intentional |
| Restore error (`_music_restore_error`) | Skips trusted init; may stay empty until user picks | Varies | Partial — avoids overwrite |
| Restore blob present but song apply fails | May fall through to **Say** if `_skip_master_song_init` is false | Workspace keys may still restore | Edge case — can feel wrong |
| AMI return navigation (`should_skip_workspace_restore_for_resume`) | Preserves current session | Preserves current | Yes — by design |

## Startup sequence (code path)

1. **`prepare_music_workspace()`** (`music_persistent_state.py`) — cloud-first via `sync_workspace_protocol`.
2. **`apply_music_disk_state()`** — applies blob; sets `SUITE_LOCAL_STATE_RESTORED_KEY = True` **only when** `apply_saved_music_context()` succeeds.
3. **`_skip_master_song_init`** (`streamlit_music_practice_app.py` ~1143):
   - True if saved song context exists, restore flag set, or restore error recorded.
   - False → **`ensure_master_song_initialized(DEFAULT_SONG_RECORDS)`** picks **`all_records[0]`** from trusted-core catalog → typically **Say — John Mayer**.
4. Default **`studio_page`** when nothing restored → Practice.

## Why Say / Practice specifically?

- **`TRUSTED_CORE_RECORDS`** filters verified/trusted-core songs; first entry is used as the safe default.
- **`ensure_master_song_initialized`** only runs when no restored pick_key and no restore flag — deliberate “cold start” behavior (documented in `cursor-prompts/plans/music-persistence-audit-2026-06-08.md`).
- Practice is the default coach/studio landing page when `studio_page` is absent from the restored blob.

## Is cloud restore failing?

Check on reboot (Developer Mode / `?dev=1`):

- `st.session_state.get("_music_restore_error")` — non-empty means restore threw.
- `music_persistence_trace` fields: `should_skip_workspace_restore_for_resume`, `ami_return_navigation_active`, `trusted_core_init_ran`.
- Supabase: `suite_workspace_state` row for app `music` should contain `active_song` / `studio_page` if saves are working.

If cloud is configured but blob is stale/empty, Music **will** cold-start to Say + Practice — same as a first visit.

## Comparison to Baseball

Baseball uses the same suite workspace protocol but:

- Has fewer “trusted default” overrides for core entities.
- Page restore is more visibly tied to resume items and current-state snapshots.

Music’s **trusted-core init** is an extra safety layer that Baseball does not mirror — so cold-start defaults are more noticeable on Music.

## Recommendations (deferred — not in scope now)

1. **Diagnostics banner** (dev only): show restore source (cloud/disk/none) and whether trusted-core init ran.
2. **Last-used song preference**: when restore fails, prefer last autosaved pick_key from local disk before Say.
3. **Page restore parity**: ensure `studio_page` is always in workspace save payload (already intended; verify on phone→Dell).

## Related docs

- `cursor-prompts/plans/music-persistence-audit-2026-06-08.md`
- `cursor-prompts/plans/2026-06-09-test-d-active-song-restore.md`
- Baseball: `docs/COMMAND_CENTER_AMI_HISTORY_AUDIT.md` (AMI history storage — separate from Music workspace)
