# Cross-owner authority stabilize (from Daniel manual test)

**Baseline (frozen product):** `dev` / `origin/dev` = `e5444de`  
**Working branch (local only, do not push):** `hotfix/cross-owner-authority-stabilize`  
**Slice 0 evidence:** `scripts/evidence-cross-owner-slice0/slice0_collisions.json`  
**Repro:** `scripts/_repro_cross_owner_slice0.py`

**Last updated:** 2026-09-24

---

## Goal

Stop Catalog / Custom / Jam / Missions / Composition state from leaking across owners so every visible surface tells the **same story** for the current context.

Do **not** redesign broadly or throw away existing ownership work. Prefer:

- one resolver per concept
- owner-aware eligibility
- explicit source envelopes
- per-song / per-UUID Practice Key persistence
- derived written / shape keys
- explicit Backing owner

Avoid late display overrides that hide a stale owner underneath.

---

## Slice 0 findings (first authority collisions)

Deterministic session seed at `e5444de` with **Perfect Global Active (G/C)** + **LAST_CUSTOM Trial Song (D/F)** + Jewish ballad residue.

### Collision A — Dual identity memory (root)

Global Active stays Catalog Perfect while `CPL_ACTIVE` / `LAST_CUSTOM` still hold Trial Song.

Any later surface may bind either identity. This is the substrate for Daniel’s “Perfect header / Trial progression” and “Songs Perfect / sidebar Trial” screenshots.

### Collision B — SBI Custom mixed header (**smoking gun**)

After `note_explicit_sbi_source_selection(Custom)` → `install_sbi_custom_identity_before_widgets` → `prepare_sbi_custom_sidebar_display_key`:

| Field | Observed | Expected for SBI Custom Trial |
|---|---|---|
| `selected_song.title` | Perfect | Trial Song (or clear visit-only label) |
| `active_music_source` | catalog | unchanged GA is OK **only if** visit envelope is exclusive |
| `cpl_name` | Trial Song | Trial Song |
| Practice Focus | SBI Custom · Trial Song | Trial Song |
| Sidebar Original | **D** | D |
| `get_practice_concert_key` | **C** (Perfect) | **F** (Trial saved) |
| `_sbi_custom_visit_pk` / `display_key_sbi_custom` | **F** | F |
| `resolve_active_song_keys` | G / C | must not win over visit PK on Custom visit |

**First wrong transition:** SBI Custom install correctly sets visit PK / focus / Original to Trial, but **does not bind sidebar Practice Key authority to the Custom visit**. Perfect’s per-pick Practice C remains eligible via `get_practice_concert_key` / Global Active, while Original caption flips to Trial D → **owner split in one render**.

### Collision C — Songs hub vs sidebar owner split

On picker with Perfect GA + leftover Custom overlay / `improv_song_source=Custom`:

- Hub / focus: Catalog · Perfect
- Sidebar Original caption: **D** (Trial)
- Practice Key: **C** (Perfect)

Matches Daniel’s “Active Song · Perfect” vs “Custom Progression — Trial Song” / F vs G family of bugs.

### Not yet forced in Slice 0 unit seed (still required in browser journeys)

- Perfect SBI Active C → Eb
- Mission Backing → SBI Custom / Jam + Return-to-Mission on Jam
- Live Coach Perfect Original D (needs overlay/path that hits `resolve_sidebar_original_key_for_caption` Custom branch while GA Perfect)
- Shape Key C with progression still D
- Written Key label E vs notes G
- Composition PK card/sidebar disagree; Backing reclaim G
- Jam Generator replacing GA with Trial / Jewish ballad residue on Backing

Jewish ballad string remains in `improv_jam_style` after SBI Custom (latent fuel for Practice Focus / Jam Backing leaks).

---

## Authority model (current intended map)

Confirmed by code map at `e5444de` ([Map key/owner resolvers](8c542c42-bd5c-4357-a282-1ec21c54d5cd)). Layered model:

| Layer | Role |
|---|---|
| **Global Active** | Songs-level Catalog / Custom / Composition identity |
| **Creative preview** | SBI radio + nested visit (must not flip Global Active) |
| **Backing owner** | `backing_context.source` + workflow envelope |
| **Per-owner PK store** | `practice_key_by_source[pick]` sticky |
| **Live sidebar widgets** | Projected from owner; must not invent identity |

| Concept | Intended SSOT | Competing / leak points |
|---|---|---|
| Active song identity | `global_active_song_state` + `songs.music_source` + `active_song_state` | `LAST_CUSTOM` + live CPL while GA Catalog; nested SBI Custom can *display* Trial while GA stays Perfect |
| Songs / Global source | `commit_explicit_music_source_choice` / `ACTIVE_MUSIC_SOURCE_KEY` | Radio widgets vs committed explicit; Composition pick vs catalog choice |
| SBI preview owner | `source_session_state` (`get/set_sbi_preview_source`, `resolve_sbi_preview`) | `improv_song_source` remount vs leave intent; overlay flags |
| Ownership transitions | `music_source_ownership` | Practice↔backing reconcile vs sticky creative intent |
| Original Key | `resolve_sidebar_original_key_for_caption` (+ catalog / Custom saved / Composition UUID) | Custom overlay / SBI Custom eligible while GA Catalog; card via `resolve_active_song_keys` |
| Practice Key | `songs.key_state` + `practice_key_state` sticky; sidebar via `sidebar_key_identity` → `workflow_key_identity` → `musical_context_authority` | GA pick store vs `_sbi_custom_visit_pk`; Mission / Jam keys; card sticky override; `bind_sidebar_practice_key_to_backing_owner` |
| Sounding | = Practice/Concert (`resolve_active_musical_key`) + capo sounding sync | Stale when PK authority split |
| Written key | `instrument_transposition` + `show_chart_in_instrument_key` | Labels from one owner, chords from another |
| Shape / Capo | `guitar_capo` | Parked catalog shape vs Custom/SBI visit; widget vs canonical |
| Chart display key | `resolve_active_musical_key.chart_key` / `build_active_chart_bundle` | Backing chart identity vs live PK |
| Progression transpose | `music_theory` + CPL / `creative_key_sync` / `workflow_musical_authority` | Sections at wrong owner PK |
| Practice Focus caption | `practice_focus_creative` | Leftover Custom / `improv_jam_style` residue until leave |
| Backing owner envelope | `backing_context` + `backing_workflow_context` | Nested Custom SBI override; Mission/Jam sticky handoff |
| Return destination | `mission_return_destination` + `backing_nav_actions` / `backing_source_navigation` | Return-to-Mission outside Mission Backing |

### Foreign sources that stay eligible (Slice 1–4 targets)

| Residue | Stays eligible via | Must reclaim / gate |
|---|---|---|
| Sticky `LAST_CUSTOM` | SBI Custom install, CASE B PK, CPL install | Must not imply Global Active Custom |
| SBI Custom overlay / visit PK | Sidebar OK + focus while nested | Clear on Active leave; bind sidebar PK to visit |
| Catalog park | `_catalog_before_custom_state` | Pin on return-to-Catalog |
| Mission latch | handoff source + sealed return + mission concert key | Retire on leave Backing / non-Mission surfaces |
| Jam residue | `improv_jam_*` / style keys / creative:: picks | Isolate from Catalog GA; clear focus when Jam not owner |
| Follow-Active restore stamp | `_restore_sbi_custom_source`, leave intents | Genuine click vs remount |

### Collision B mechanism (aligned with map)

Nested SBI Custom is **allowed** to display Trial without flipping Global Active (H5). The bug is not “GA still Perfect” alone — it is that **sidebar Practice Key keeps reading Perfect’s sticky pick** while Original caption + Focus already follow the Custom visit. Slice 1 must make sidebar PK (and sounding/written/shape derivation) use the same visit envelope as `resolve_sidebar_original_key_for_caption` / Practice Focus when `custom_sbi_owns_sidebar_practice_key` (or equivalent) is true — without promoting Trial to Global Active.

---

## First-wrong transitions (Daniel bugs → functions)

From eligibility trace at `e5444de` ([Find dual-owner eligibility paths](d1e2f8da-bbb5-4cb1-aee4-0758feddecc1)). Earliest failures are **handoff/owner stamps before the surface that should own identity**, not late labels.

| Rank | Collision | First wrong edge | Slice |
|---|---|---|---|
| **1** | Mission Backing stolen by SBI/Jam | `streamlit_music_practice_app` pops `improv_mission_backing_handoff` **before** entry_mode gate → leftover Song-Based / Jam / Style wins; `Return to Mission` can linger | 3–4 |
| **2** | SBI Custom visit stamps nested Backing | `install_sbi_custom_identity_before_widgets` sets `_nested_custom_sbi_backing` + `_backing_explicit_handoff_source="song_improv"` (`source_session_state` ~1755–1766) — preview pretends Backing handoff | 1–2, 4 |
| **3** | Dual presentation (sidebar Trial / hub Perfect) | `set_sbi_preview_source` → `mark_temporary_workflow_owner("sbi_custom")` → `active_source_labels` Custom banner while hub stays catalog | 1–2 |
| **4** | Live Coach Perfect + Original D | Leftover `_sbi_custom_sidebar_overlay` → `resolve_sidebar_original_key_for_caption` Custom branch | 1–2 |
| **5** | Practice → G on Custom open | Sidebar `restore_sbi_active_catalog_identity_before_widgets` races ahead of Custom install → PK falls to catalog Original G | 1–2 |
| **6** | Perfect Practice C → Eb | Jam default `improv_jam_key=Eb` + `sbi_active_catalog_owns_practice_key` False under leftover Jam entry | 2 |
| **7** | Jam under Perfect → Trial / Jewish Ballad | Stale `install_last_custom_into_live_cpl` + uncleared `improv_jam_style`; Jam entry forced without clearing LAST_CUSTOM | 2 |
| **8** | Mission Practice concert D vs sidebar F / written E | `resolve_sbi_custom_practice_key` returns **home D** when sticky F lacks override → labels/written from D, chords from F | 1, 3 |

**Shared root:** SBI Custom install is not preview-only — it marks temporary owner, installs LAST_CUSTOM, and stamps **Backing** nested/handoff flags. Mission open-backing then **consumes** the mission flag while leftover `improv_entry_mode` still says SBI/Jam. Dual banner, Original D, C→G/Eb, and D-vs-F are downstream.

**Slice 1 implication (narrow):** stop Custom visit from (a) leaving sidebar PK on GA Perfect while Original/Focus are Trial, and (b) stamping Backing handoff flags that later steal Mission/Jam opens — without redesigning Global Active H5.

---

## Work slices (do not parallelize product edits)

1. **Slice 1 — Core source + key authority**  
   Single context envelope: identity + Original + Practice + sounding + written/shape derivation. Fix Collision B/C first: when SBI Custom (or leftover Custom overlay) owns the visit, sidebar PK must follow Custom visit/UUID F, not Perfect C; when Songs hub presents Catalog Perfect, Custom overlay must not own Original caption.

2. **Slice 2 — SBI + Jam/Entry**  
   No active-song stealing; Jam local envelope; clear Jewish ballad unless current Jam owns it.

3. **Slice 3 — Missions + Mission Backing**  
   One Mission key resolver; Mission Backing owner; Return-to-Mission only there; user-facing melody copy.

4. **Slice 4 — Backing owner envelopes**  
   Catalog / Custom / Jam / Mission / Composition explicit launch owner.

5. **Slice 5 — Composition UI/nav + chord–notation alignment**

6. **Slice 6 — Phrase/Motif + icons + Transpose helpers + Practice written-chart toggle**

Checkpoint each slice locally. **Do not push** until Daniel verifies.

---

## Journeys (browser) — gate each slice

1. Trial Custom D/F across Custom → SBI → Creative → Motif → Missions → Mission Backing → return → Backing → Songs  
2. Perfect Catalog G/C across Songs → SBI → Creative → Live Coach → Missions → return → Songs  
3. Perfect + Jam (no Trial steal; Jam Backing owns Jam)  
4. Trial + Guitar Shape C (progression in C shapes)  
5. Trial Mission + Bb Clarinet written G  
6. Composition UUID PK consistency + Backing not Catalog G  

Final: clean runtime + polluted runtime full cross-owner matrix.

---

## Slice 1 status (local checkpoint)

**Landed on** `hotfix/cross-owner-authority-stabilize` (unpushed).

### Practice Key read collision

- **Wrong read:** bare `get_practice_concert_key(session)` → `resolve_practice_source_pick` → Global Active Perfect pick → sticky **C**
- **While:** Custom visit already had Original D, Focus Trial, `_sbi_custom_visit_pk` / Custom sticky **F**
- **First wrong function:** `songs.practice_key_state.get_practice_concert_key` (empty `pick_key` fallthrough to GA pick)

### Fix

When `custom_sbi_owns_sidebar_practice_key`, bare PK reads + `get_authoritative_display_key` use `resolve_sbi_custom_practice_key` (visit/override sticky). Explicit catalog picks still return Perfect C (preserved). Original caption on Songs/picker no longer follows leftover Custom overlay. SBI Custom install no longer stamps `_nested_custom_sbi_backing` / `song_improv` handoff (stamped on actual Backing launch).

### Validation

- `tests.test_slice1_custom_visit_practice_key` 5/5
- `test_origin_dev_sbi_ownership` + owner identity + sbi custom PK owner: OK
- practice key lifecycle + practice focus creative + Phase D + Capo: OK
- browser Slice 1: PASS (no mixed D/C; Perfect G/C ↔ Custom D/D roundtrip)
- **Slice 1 D/F clarification:** explicit Trial Practice F → Custom visit **D/F** browser PASS (`scripts/_proof_slice1_trial_df.py`, evidence `scripts/evidence-slice1-trial-df/`)

### Slice 2 — Jam / Entry ownership (local checkpoint)

**First C→Eb collision:** `sbi_active_catalog_owns_practice_key` treated empty `improv_intelligence_tab` + leftover `improv_entry_mode=Jam Session Generator` as Jam UI → Perfect SBI Active lost PK ownership while `improv_jam_key=Eb` / `_generated_jam_key_owner_active` remained sticky.

**Eligibility before:** Jam blob / sticky `_generated_jam_key_owner_active` / leftover entry_mode / empty tab could win over SBI Active Perfect C.

**Eligibility after:** Jam requires current semantic ownership — `improv_intelligence_tab == Entry & Jam` + Jam/Style entry (or explicit `entry_jam` Backing handoff). Stale Jewish ballad style string alone cannot own Focus or PK.

**Validation:** `tests.test_slice2_jam_entry_ownership` 9/9; Slice 1 units OK; startup IMPORT_OK. Pre-existing: `test_mission_catalog_ignores_stale_generated_display_key` (D# vs D) fails independently of Slice 2 edits.

**Next (Slice 3):** Missions + Mission Backing owner boundaries.
