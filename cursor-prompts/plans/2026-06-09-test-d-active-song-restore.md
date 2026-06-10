# Test D — Active song + display key + instrument + studio page restore

**Last updated:** 2026-06-09  
**Baseline:** v18 (`fdf9800`) — `page-change-save-stamp-v18-backing-user-dirty`  
**Branch:** `dev`

## Frozen (accepted — do not reopen without trace regression)

| Test | Scope | Status |
|------|--------|--------|
| A | Studio page sync | **PASSED** |
| B | Practice field sync | **PASSED** |
| C | Backing content sync | **PASSED** (v18) |

**Policy:** Do not modify page sync, Practice sync, or Backing sync code unless a new `?dev=1` trace proves regression in that area.

---

## Test D protocol

### 1. Dell

- Select a **non-default** catalog song (prefer non-core / non-trusted-core).
- Change **display key**.
- Change **instrument**.
- Navigate to a **non-default** studio page (e.g. `backing`, `creative`).
- Wait **≥10 seconds** for cloud save.

### 2. Capture Dell `?dev=1` trace

Copy the **Test D compare** block (or note these fields):

- `pick_key` / `final_pick_key`
- `display_key` / `final_display_key`
- `instrument` / `final_instrument`
- `final_studio_page`
- `cloud_updated_at`
- `device_id`

### 3. Phone

- **Hard refresh** (no navigation, no widget interaction before trace).
- Open same app with `?dev=1`.
- Verify:

  - `final_pick_key` matches Dell
  - `final_display_key` matches Dell
  - `final_instrument` matches Dell
  - `final_studio_page` matches Dell
  - No trusted-core fallback (Say / Perfect / Turn the Lights Back On)
  - No default-song fallback

### 4. If failure

- Classify as **Test D only**.
- Investigate: `active_song_state`, workspace restore order, startup autosave, trusted-core pin.
- Do **not** reopen Test A/B/C workstreams without trace evidence of regression there.

---

## Acceptance criteria

- Song, display key, instrument, and studio page restore **identically** across devices after refresh.
- No fallback to defaults.
- No overwrite from startup autosave.
- No restore-order race between `active_song_state` and workspace restore.

---

## Trace fields (failure classification)

| Symptom | Likely cause | Trace signals |
|---------|--------------|----------------|
| Wrong song after refresh | Trusted-core pin / `ensure_master_song` | `final_pick_key` ≠ Dell; `restore_skip_reason` |
| Right song, wrong key | Display key not in cloud blob | `final_display_key` mismatch; check `core.display_key` |
| Right song, wrong instrument | Core restore skipped | `final_instrument` mismatch |
| Right song/key, wrong page | Page ownership / workspace race | `final_studio_page` ≠ Dell `cloud_fetch_studio_page` |
| Phone shows older cloud | Stale fetch | `cloud_updated_at` < Dell `local_updated_at` |
| Post-refresh autosave overwrite | End-of-run flush | `force_save_reason`, `last_save_cloud` on phone before user touch |

---

## Related code

- `active_song_state.py` — canonical song blob, `apply_cloud_active_song_state_if_allowed`
- `music_persistent_state.py` — `apply_music_disk_state`, `prepare_music_workspace`
- `studio_nav_state.py` — `studio_page` restore
- `streamlit_music_practice_app.py` — trusted-core pin guard (`_skip_master_song_init`)

---

## Verification

```bash
python -m pytest tests/test_active_song_state.py tests/test_music_phase_b.py -q
```

Manual: `?dev=1` → **Test D compare** copy block on Dell and phone.
