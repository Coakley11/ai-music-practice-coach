# Music cleanup sprint — performance report

**Date:** 2026-07-03  
**Scope:** Developer UI audit + first performance pass (no restore/routing changes)

## Executive summary

Normal-mode users now see a clean product UI: all debug/trace/probe panels require explicit Developer Mode (`?dev=1` or session dev toggle). A developer-only **Music performance (dev)** sidebar reports per-run timing for the top slow paths.

This sprint reduces redundant work on typical page navigations by skipping duplicate workspace sync and canonical reconcile when AMI return did not apply new state.

---

## Top slow paths (ranked)

| Rank | Path | Typical cost | Notes |
|------|------|--------------|-------|
| 1 | **Backing synthesis** (`synthesize_chords_to_numpy`) | 200–800+ ms | CPU-bound; mitigated by session + module WAV cache. Dominant on Backing page generate. |
| 2 | **Workspace sync** (`sync_workspace_protocol` → `load_cloud_full_session`) | 50–200 ms × passes | Supabase meta GET + disk JSON read per pass. **Reduced:** second pass skipped unless AMI applied. |
| 3 | **Canonical reconcile** (`prepare_canonical_music_page_state`) | 20–80 ms × passes | Active song + practice + backing blob reconcile. **Reduced:** deduped per `_script_run_seq` unless AMI force. |
| 4 | **Chart bundle** (`build_active_chart_bundle`) | 10–50 ms on cache miss | Session-cached via `session_cache_get_or_set`; only rebuilds when pick/key/level signature changes. |
| 5 | **Autosave build** (`build_music_disk_state` before fingerprint) | 15–40 ms | Runs end-of-script when autosave not blocked. Future: dirty-flag short-circuit. |
| 6 | **Monolithic script import/parse** | Baseline 100–300 ms | 14k-line entry file; future: lazy page imports / `st.fragment`. |
| 7 | **HRI humanize** (backing page) | 10–30 ms | Cached in `studio_cache` bucket `hri_sections`. |
| 8 | **Bootstrap workspace** ×3 calls | 5–15 ms | **Reduced:** `bootstrap_suite_workspace` once per run after auth restore. |

Measure live with `?dev=1` → sidebar **Music performance (dev)** and **Supabase egress (dev)**.

---

## Changes shipped this sprint

### Developer UI

- Central gate: `music_dev_ui.py` → `music_dev_mode_enabled()` (`?dev=1` or dev session flags)
- Ungated leaks fixed:
  - `creative_session_state.render_creative_session_diagnostic`
  - `song_chart_editor` override debug blocks
  - Daniel **Developer / Library Info** sidebar (now dev-only)
- Internal gates added: `widget_control_debug`, `render_quick_nav_dev_diagnostics`
- Unified dev gate across persistence trace, deploy probe, isolation diagnostics, practice log / multitrack / tone diagnostics
- `?simple_nav=1` requires dev mode

### Performance

- Skip second `prepare_music_workspace` cloud/disk I/O unless `_ami_return_source_applied`
- Dedupe `prepare_canonical_music_page_state` per script run (`_music_canonical_prepared_for_run`)
- `bootstrap_suite_workspace` init once per `_script_run_seq` (auth restore still every run)
- `music_perf_diagnostics.py` — dev-only span recording + top-slow-path sidebar
- Workspace sync timing recorded in `prepare_music_workspace`

### Not changed (frozen / deferred)

- `apply_music_disk_state`, `sync_workspace_protocol` apply logic, nav routing, AMI return
- Backing timbre/recipe depth (Phase 1 backing work remains uncommitted)
- `st.fragment` / lazy page modules (architectural — next sprint)
- Autosave dirty-flag short-circuit (next sprint)

---

## Verification checklist

**Normal mode (no `?dev=1`):**

- [ ] No persistence trace, deploy probe, widget debug, isolation, or performance sidebars
- [ ] No creative session commit captions on Backing/Creative
- [ ] No chart override debug paths after save
- [ ] No Developer / Library Info expander

**Developer mode (`?dev=1`):**

- [ ] Music performance sidebar shows workspace_sync / canonical spans
- [ ] Page nav: `workspace_sync_post_ami` ≈ 0 ms when AMI did not apply (skipped)
- [ ] Backing generate: `_backing_last_gen_profile` synthesis_ms on cache miss

---

## Next sprint candidates

1. Autosave dirty-flag before `build_music_disk_state`
2. Per-run disk read cache in `_load_raw` (mtime-keyed)
3. `st.fragment` for sidebar + page bodies
4. Lazy imports per `studio_page` branch
5. Audio fingerprint regression for backing style work (when Phase 1 commits)
