# Test E — AMI return validation protocol

**Last updated:** 2026-06-09  
**Status:** IN PROGRESS (v26 trace + AMI transposing round-trip)  
**Deploy marker:** `page-change-save-stamp-v26-test-e-ami-return-trace`  
**Frozen:** Tests A–D — do not modify A–D persistence unless `?dev=1` trace proves regression.

---

## Goal

Confirm returning from Applied Math / insight flow restores the correct Music state **without overwriting**:

- active song
- display key
- instrument
- written-key / transposing subtype
- studio page (Practice or Backing)
- Practice / Backing filter state

---

## Setup (known state)

| Field | Value |
|-------|--------|
| Song | Photograph or Shape of You |
| Display key | Db or Ebm |
| Instrument | Saxophone |
| Subtype | Tenor or Alto |
| Written-key | ON |
| Studio page | Practice **or** Backing |

Open Music with `?dev=1` → expand **Music persistence trace** → copy **Test E compare** block (**before**).

---

## Steps

1. Set state above on Dell (or primary device).
2. Send Music Coach / AMI insight (Applied Math return flow).
3. On Applied Math, open return link back to Music.
4. After insight card renders, copy **Test E compare** block (**after**).
5. Visually confirm song, key, written charts, subtype, and page unchanged.

---

## Pass criteria

| Check | Expected |
|-------|----------|
| `final_pick_key` | Same song (not default catalog pick) |
| `final_display_key` | Db / Ebm unchanged |
| `final_instrument` | Saxophone |
| `written_key_mode_widget` / `canonical` | True |
| `transposing_subtype_widget` / `canonical` | Tenor or Alto (not wrong default) |
| `final_studio_page` | Practice or Backing (sent page) |
| `restored_studio_page` | Matches sent `studio_page` in source_state |
| `ami_return_detected` | True on return load |
| `page_forced_by_ami_return` | True until resume consumed |
| `active_song_dirty` | False after restore |
| `page_overwrite_source` | Empty / not cloud overwrite |
| `active_song_restore_skipped` | Empty (no cloud clobber during AMI) |

**Fail signals:**

- Default song fallback
- Picker / wrong studio page
- Written-key OFF or Alto when Tenor was sent
- `workspace_restore_source` = cloud during AMI window (should be `ami_return`)

---

## Trace panel fields (Test E compare)

- `ami_return_detected`, `source_app_normalized`, `ami_resume_consumed`
- `current_studio_page`, `final_page`, `page_forced_by_ami_return`, `manual_nav_after_ami_return`
- `active_song_state` (summary)
- `written_key_mode_*`, `transposing_subtype_*`
- `cloud_fetch_studio_page`, `restored_studio_page`, `final_studio_page`
- `final_pick_key`, `final_display_key`, `final_instrument`

Insight sync trace (sidebar) also shows AMI return diagnostics.

---

## v26 code changes (AMI scope only)

- `build_source_state` includes written-key + transposing subtype in `widget_params`
- `apply_active_song_source_state_from_ami` restores transposing fields + rehydrates sidebar
- `record_ami_return_restore_trace` on Music `apply_return_source_state`
- **Test E compare** panel in Music persistence trace

---

## After pass

1. Mark Test E **PASSED** in this file and `docs/MUSIC_PERSISTENCE_BASELINE.md`
2. Freeze AMI return path (same policy as A–D)
3. UI polish in a **separate commit** (Practice scroll, chart/TAB, badges, etc.)

---

## Sign-off

| Device | Before copy | After copy | Pass? | Notes |
|--------|-------------|------------|-------|-------|
| Dell | | | | |
| Phone | N/A (return on same device first) | | | |
