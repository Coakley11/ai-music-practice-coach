# Music Practice Coach — Acceptance Matrix (Draft)

**Last updated:** 2026-06-09  
**Status:** Phase C manual cross-device Tests **A–D passed** on `dev` (frozen)  
**Baseline:** [MUSIC_PERSISTENCE_BASELINE.md](./MUSIC_PERSISTENCE_BASELINE.md)  
**Reference:** Baseball `docs/BASEBALL_ACCEPTANCE_MATRIX.md`  
**Full audit:** `docs/MUSIC_PHASE_A_AUDIT.md`

Legend: **PASS** · **PARTIAL** · **FAIL** · **N/A** · **PLANNED**

Cross-cutting goals A–E match Baseball acceptance tests.

---

## Per-page matrix (current baseline)

| Page ID | Product name | A Local | B Phone↔Dell | C Cloud | D Nav | E AMI | Canonical module | Status |
|---------|--------------|---------|--------------|---------|-------|-------|------------------|--------|
| `practice` | Practice | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `practice_state.py` | Snapshot + core; no dirty flag |
| `picker` | Songs | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `song_picker_state.py` + `active_song_state` | Chart files separate |
| `backing` | Backing Track Studio | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `backing_track_state.py` | WAV not persisted |
| `custom` | Creative Progression | PASS | PARTIAL | PARTIAL | PASS | N/A | `creative_state.py` (CPL) | CPL export works |
| `creative` | Creative Lab | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `creative_state.py` | Large improv key set |
| `analysis` | Upload Analysis | PARTIAL | FAIL | PARTIAL | PASS | N/A | `upload_state.py` | Analysis results ephemeral |
| `multitrack` | Multitrack | PARTIAL | FAIL | PARTIAL | PASS | N/A | `upload_state.py` | Audio blobs local-only |
| `log` | Practice Log | PASS | PARTIAL | PARTIAL | PASS | N/A | `practice_log_state.py` | JSON file + session |
| `openai` | OpenAI Hub | N/A | N/A | N/A | PASS | N/A | — | Conditional page |

### Sub-features

| Feature | Host | A | B | C | D | E | Module |
|---------|------|---|---|---|---|---|--------|
| Karaoke | `backing` + global | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `karaoke_state.py` |
| Performance Setlist | `picker` | PARTIAL | PARTIAL | PARTIAL | PASS | N/A | `karaoke_state.py` |

**PARTIAL** = persistence works for core keys via `restore_once` + snapshots, but lacks Baseball-style canonical modules, dirty ownership, and `sync_workspace_protocol`.

---

## Cross-cutting verification (current)

| Goal | Status | Evidence / gap |
|------|--------|----------------|
| 1. Page inventory | PASS | 9 sidebar + 2 sub-features documented |
| 2. Canonical ownership | **FAIL** | No `{page}_state.py`; snapshots + `_PERSIST_KEYS` only |
| 3. Phone ↔ Dell sync | **PARTIAL** | Cloud via `restore_once`; manual sign-off on non-core song PASS (2026-06-08) |
| 4. Cloud restore | **PARTIAL** | `pick_restore_session`; no per-page `apply_cloud_*_if_allowed` |
| 5. Manual nav ownership | **PARTIAL** | Page snapshots preserve globals; no `claim_user_page_ownership` for `studio_page` |
| 6. AMI source_state + return | **FAIL** | Not wired; no `music_applied_math_context.py` |
| 7. Insight page scoping | **FAIL** | No `INSIGHT_ELIGIBLE_PAGES["music"]` |
| 8. Dismiss behavior | **PLANNED** | Suite module present, unused |
| 9. No page bounce | **PARTIAL** | Nav history OK; cloud page overwrite risk remains |

---

## Target matrix (post Phase C — draft targets)

| Page | A | B | C | D | E |
|------|---|---|---|---|---|
| All pages | PASS | PASS | PASS | PASS | PASS (if AMI enabled per page) |

---

## Remaining bugs (ranked) — Music-specific

### P0 (block suite port for Music)

| ID | Issue |
|----|-------|
| P0-1 | No `sync_workspace_protocol` / `prepare_music_workspace` — uses `restore_once` only |
| P0-2 | No canonical `{page}_state.py` modules or dirty flags |
| P0-3 | No AMI integration (`applied_math_context`, eligible pages, hydrate/render) |

### P1

| ID | Issue |
|----|-------|
| P1-1 | `claim_user_page_ownership` not wired to `studio_page` |
| P1-2 | `suite_deep_links` aliases incomplete (`picker`, `creative`, `multitrack`, `log`) |
| P1-3 | Analysis/multitrack cross-device — metadata only, blobs fail B |
| P1-4 | No `test_page_navigation_ownership` equivalent for music |
| P1-5 | `sync_suite_cloud_modules` can strip music-specific `suite_user_persistence` bypass reasons |

### P2

| ID | Issue |
|----|-------|
| P2-1 | Dual persistence (snapshots + `_PERSIST_KEYS` + core) — consolidate in Phase C |
| P2-2 | `openai` page not in `STUDIO_PAGE_IDS` resume normalization edge cases |
| P2-3 | Draft Room-style debug: some pages lack dedicated `render_*_state_debug` |

---

## Phase checklist (Sprint 7 Music)

### Phase A — Audit ✅
- [x] Page inventory
- [x] State inventory
- [x] Navigation inventory
- [x] AMI inventory
- [x] Migration plan
- [x] Acceptance matrix draft
- [x] Protocol draft

### Phase B — Shared suite modules
- [x] `prepare_music_workspace()` + `studio_page` ownership (Tests A–D)
- [x] Verify force-save / post-restore bypass list
- [ ] Sync from Command Center (ongoing suite maintenance)
- [ ] AMI sidebar + hydrate wiring (minimal) — **Test E**

### Phase C — Canonical modules
- [x] `active_song_state.py` (Test D)
- [x] `practice_state.py` (Test B)
- [x] `backing_track_state.py` (Test C)
- [x] `studio_nav_state.py` (Test A)
- [ ] `song_picker_state.py`, `creative_state.py`, `upload_state.py`, `karaoke_state.py` (full matrix)
- [ ] `music_applied_math_context.py`
- [x] Manual Tests A–D per persistence baseline
- [ ] Test E (AMI return)

### Phase D — Manual acceptance (frozen)
- [x] Test A — studio page sync (phone ↔ Dell)
- [x] Test B — Practice field sync
- [x] Test C — Backing content sync (v18)
- [x] Test D — active song + display key + instrument + page + written-key + transposing subtype (v25 `f153204`, 2026-06-09)
- [ ] Test E — AMI return (if enabled)
- [ ] Final per-page matrix all PASS (analysis/multitrack blobs remain PARTIAL)

---

## Verification (post-migration)

```bash
python -m pytest tests/test_*_state.py tests/test_music_persistence*.py -q
```

Manual: `?dev=1` persistence trace + cross-device non-core song + page nav no-bounce.
