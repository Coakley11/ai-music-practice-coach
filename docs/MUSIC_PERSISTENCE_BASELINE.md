# Music Practice Coach — Persistence baseline (frozen)

**Last updated:** 2026-06-09  
**Branch:** `dev`  
**Current deploy marker:** `page-change-save-stamp-v26-test-e-ami-return-trace`  
**Latest commit (Test D sign-off):** `f153204`

---

## Frozen acceptance (Tests A–D)

Do **not** modify these persistence systems unless a new `?dev=1` trace proves regression.

| Test | Scope | Status | Baseline marker / commit |
|------|--------|--------|-------------------------|
| **A** | Studio **page** sync (phone ↔ Dell) | **PASSED** | v14 `454e0af` |
| **B** | **Practice** field sync | **PASSED** | `97fad4a` |
| **C** | **Backing** content sync | **PASSED** | v18 `fdf9800` |
| **D** | **Active song** + display key + instrument + page + written-key + transposing subtype | **PASSED** | v25 `f153204` |

### Test D sign-off (2026-06-09)

- **Core restore:** non-default song, display key, instrument, studio page match across devices.
- **Written-key:** checkbox ON on phone after hard refresh; charts in written key.
- **Transposing subtype:** Tenor Saxophone restored (not Alto default).
- **Save path:** v25 `save_*` trace + cloud readback confirm payload matches canonical (not restore-side inference).

---

## Trace panels (`?dev=1`)

| Panel | Use |
|-------|-----|
| **Test D compare** | Receive-side: `final_*`, `written_key_mode_*`, `transposing_subtype_*`, `active_song_dirty` |
| **Test E compare** | AMI return: `ami_return_detected`, `restored_studio_page`, `final_*`, transposing fields, `page_forced_by_ami_return` |
| **Transposing save (last cloud write)** | Save-side proof: `save_written_key_canonical/payload/cloud_readback`, `save_transposing_subtype_*`, `save_overwrite_detected` |
| **Workspace restore** | Page sync (Test A) |
| **Backing path** | Test C — frozen |

**Important:** `written_key_mode_cloud` on receive trace reflects session/restore inference. **Supabase truth** is `save_written_key_cloud_readback` after Dell save.

---

## Canonical modules (do not regress)

- `active_song_state.py` — song, display key, instrument, written-key, transposing subtype
- `studio_nav_state.py` — `studio_page`
- `practice_state.py` — practice filters
- `backing_track_state.py` — backing scope, BPM, groove, meter, loops

**Build / restore entry points:**

- `prepare_music_workspace()` → `sync_workspace_protocol` (cloud-first)
- `build_music_disk_state()` → `commit_*_from_session` before envelope
- `apply_music_disk_state()` — workspace restore (Test D receive path frozen at v24/v25 receive; save path v25)

---

## Save-path notes (Test D sub-bug resolution)

1. **v19–v24:** Written-key / subtype receive binding and trace visibility.
2. **v25:** Save payload — `gather_active_song_context` no longer defaults to Alto/False when canonical has Tenor/True at commit time; immediate cloud readback trace after write.
3. **Post-save overwrite:** `save_overwrite_detected` flags a second autosave in the same session that changes transposing payload.

---

## Next manual test (not frozen)

| Test | Scope | Status |
|------|--------|--------|
| **E** | AMI return restores song/key/instrument/written-key/subtype/page + practice/backing | **IN PROGRESS** (v26) — [protocol](../cursor-prompts/plans/2026-06-09-test-e-ami-return.md) |

---

## Verification commands

```bash
python -m pytest tests/test_active_song_state.py tests/test_studio_nav_state.py tests/test_practice_state.py tests/test_backing_track_state.py tests/test_music_phase_b.py -q
```

Manual: Dell save → **Transposing save** panel all match → phone hard refresh → **Test D compare** all match.
