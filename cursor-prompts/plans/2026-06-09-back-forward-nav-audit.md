# Back / Forward navigation audit

**Last updated:** 2026-06-09  
**Priority:** **P1 — later** (after P0 UI polish)  
**Status:** DEFERRED — manual audit when scheduled  
**Policy:** Separate from UI polish. Do **not** touch Tests A–E persistence unless `?dev=1` trace proves navigation crosses into sync.

**Frozen:** Tests **A–E** passed. See [MUSIC_PERSISTENCE_BASELINE.md](../../docs/MUSIC_PERSISTENCE_BASELINE.md).

**Not immediate** unless Back/Forward breakage blocks normal app use. Complete [UI polish phase](./2026-06-09-ui-polish-phase.md) first.

---

## Concern

After persistence architecture changes (Phase C, canonical modules, cloud-first restore), **← Back** and **Forward →** may need rebuild or re-validation. Audit **after** P0 UI polish, in a separate isolated commit if fixes are required.

---

## Goal

Confirm Back/Forward work correctly across Music Studio pages **without** breaking cloud/page sync or active song state.

---

## Pages to test

- Song Selection (`picker`)
- Practice (`practice`)
- Backing Track (`backing`)
- Creative / Custom Progression (`custom` / `creative`)
- Karaoke (voice mode on Backing or dedicated flow)
- Upload / Multitrack (`analysis` / `multitrack`)

---

## Expected behavior

| Check | Expected |
|-------|----------|
| Back | Returns to previous studio page in history stack |
| Forward | Returns to page after going back (forward stack) |
| Cloud state | Back/Forward do **not** incorrectly overwrite cloud state |
| `final_studio_page` | Updates correctly after each nav action |
| Stale overwrites | No stale picker/practice/backing page overwrites |
| Active song | pick_key, display_key, instrument preserved |
| Written-key / subtype | Unchanged across Back/Forward |
| Practice state | Section focus, groove, notation settings preserved |
| Backing state | BPM, scope, groove, meter preserved |

---

## Recommended order

0. Complete **P0 UI polish** first ([ui-polish-phase](./2026-06-09-ui-polish-phase.md)) — unless Back/Forward breakage blocks normal use today.
1. **Manual audit only** (this document) — no code changes until audit scheduled.
2. If buttons work → mark **Back/Forward navigation PASSED** and freeze.
3. If buttons fail → **small isolated navigation fix** commit (not mixed with UI polish or persistence).
4. Only touch A–E persistence if `?dev=1` trace proves the nav bug crosses into sync restore/save.

---

## Manual protocol

### Setup

1. Open Music `?dev=1` on `dev` deploy.
2. Set non-default state: song (e.g. Photograph), Db/Ebm, Saxophone, written-key ON, Tenor.
3. Set distinct Practice filters (section, groove) and Backing filters (BPM, scope).

### Path A — linear history

1. Song Selection → Practice → Backing → Creative.
2. Press **← Back** three times — should land Song Selection.
3. Press **Forward →** three times — should return to Creative.
4. Copy **Test D compare** + **Local nav (this run)** checkpoints after each step.

### Path B — cross-page state

1. From Practice, go Back to Song Selection — confirm active song unchanged.
2. Forward to Practice — confirm Practice filters unchanged.
3. Navigate to Backing — Back — Forward — confirm Backing BPM/scope unchanged.

### Path C — cloud touch

1. After manual Back/Forward sequence, wait 10s for autosave.
2. Hard refresh — confirm `final_studio_page` and Test D fields match pre-refresh.
3. Optional: phone hard refresh — Test A page + Test D song fields still match.

---

## Trace fields to inspect

**Existing (`?dev=1`):**

- **Local nav (this run)** — `local_nav_trace.py` checkpoints
- **Music persistence trace** — `final_studio_page`, `cloud_fetch_studio_page`, `restored_studio_page`, `page_owner_flag`, `page_overwrite_source`
- `studio_nav_state` / `last_write_reason` in active song / nav debug panels

**Session keys to watch:**

- `studio_nav_back`, `studio_nav_forward` (history stacks)
- `_suite_page_user_nav` (page owner)
- `_suite_user_owned_page`
- `force_save_reason` / `_suite_pending_save_reason`
- `cloud_payload_studio_page` / `final_payload_studio_page` (save trace)

**Add only if audit gaps found:**

- `nav_history_stack` (serialized back stack top)
- `nav_forward_stack`
- `back_button_clicked` / `forward_button_clicked`
- `previous_studio_page` / `next_studio_page`

Implement trace additions in `local_nav_trace.py` or `studio_nav_history.py` — **nav-only commit**, not persistence modules.

---

## Pass criteria

- [ ] Back returns correct previous page on all tested studio pages
- [ ] Forward restores forward stack correctly
- [ ] `final_studio_page` matches visible page after each click
- [ ] `_suite_page_user_nav` / page owner semantics correct (manual nav wins)
- [ ] No `page_overwrite_source` from stale cloud during Back/Forward-only session
- [ ] Test D fields unchanged after nav-only session (no refresh)
- [ ] Test D + Test A still pass after hard refresh post-nav

---

## Fail → fix scope

If audit fails, isolate fix to:

- `studio_nav_history.py` — push/pop stacks, `navigate_studio_page`
- `streamlit_music_practice_app.py` — floating button handlers
- `local_nav_trace.py` — diagnostics only

**Do not modify** unless trace proves cross-contamination:

- `music_persistent_state.py` workspace restore
- `active_song_state.py` / `practice_state.py` / `backing_track_state.py` cloud paths
- `apply_music_disk_state` / `build_music_disk_state`

---

## Sign-off

| Device | Path A | Path B | Path C | Pass? | Notes |
|--------|--------|--------|--------|-------|-------|
| Dell | | | | | |
| Phone | | | | | |

**Result:** PENDING / PASSED / FAILED (nav fix needed)
