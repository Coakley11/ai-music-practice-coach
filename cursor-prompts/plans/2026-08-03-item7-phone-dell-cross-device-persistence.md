# Phase 1 Item 7 — Phone → Dell cross-device persistence

**Last updated:** 2026-08-03  
**Status:** **LIVE-ACCEPTED — FROZEN** on Streamlit Cloud `dev` (sign-off rev **319**, 2026-08-03)  
**Contract doc:** `4c3ce81` (Item 7 contract; **no production code** required for live pass)

**Do not redesign** phone→Dell cross-device read paths or Item 5 reader certification without `?dev=1` regression proof and explicit unfreeze.

**Prerequisites (frozen — do not redesign):**

| Layer | Live-accept / freeze anchor |
|-------|-----------------------------|
| Items 1–5 Creative stack + refresh/cold reboot | Through `b989516`; doc `cc00cda` / `2ec5015` |
| Item 6 Dell → phone | **LIVE-ACCEPTED — FROZEN** @ rev **317** |
| Item 7 phone → Dell | **LIVE-ACCEPTED — FROZEN** @ rev **319** (this contract) |

Item **8** (stale-device revision protection) and **Phase 2** are **out of scope** for Item 7.

---

## Purpose

Prove that a **user-initiated save on phone** at authoritative cloud revision **R′** produces a **network pull on Dell** (same account, Streamlit Cloud `dev`) that restores the **same Phase 1 Creative workspace document** as Item 6’s reader checklist—without requiring a second save on Dell and without Dell applying a **stale pre-phone** session over newer cloud.

Item 7 is the **reverse-direction integration gate** to Item 6. Same envelope, same latest-save-wins apply path, same frozen Items 1–6 semantics. **No new sync channel.**

---

## Distinction from Item 6

| Item | Writer | Reader | Primary risk under test |
|------|--------|--------|-------------------------|
| **6** | Dell | Phone | Phone cold-start network hydrate @ **R** |
| **7** | Phone | Dell | Dell may hold **older local/session state** from before phone save; must **network win** @ **R′** without spurious Dell write on open |

Item 7 is **not** satisfied by Item 6 alone: writer/reader roles swap and the Dell reader often has a **warm browser profile** (hard refresh or new tab) that must still authoritative-hydrate from cloud.

---

## “Dell matches phone post-save” — authoritative checklist

After phone save completes (upsert confirmed, refetch @ **R′**), open or refresh Dell with **network hydration** before any user edit. Capture certification with **`?dev=1`**.

### Cloud / fetch discipline (Dell reader)

| Signal | Expected on Dell |
|--------|-------------------|
| `fetch_source` / certification fetch | `network` (`authoritative_current_run_startup_network_hydration`) |
| `loaded_revision` / `current_cloud_revision` | **R′** (same as phone post-save) |
| `revision_unchanged` on Dell read-only startup | `true` if Dell did not write in this run |
| Revision reservation / upsert on Dell **before any user edit** | All `false` |

Record `session_start_kind` (`hard_refresh` vs `cold_reboot`) for diagnostics only — **not** a certification failure if persistence matches.

### Global controls

| Field | Match phone |
|-------|-------------|
| `display_key`, `instrument`, `level`, `focus` | Exact |

### Item 1 — selectors

| Field | Match phone |
|-------|-------------|
| `improv_intelligence_tab`, entry/lab modes | Exact |

### Item 2 — mission config + target tuple

| Field | Match phone |
|-------|-------------|
| Section, chord index, chord, label, metric IDs | **Atomic tuple** unchanged |

### Item 3 — artifacts

| Field | Match phone |
|-------|-------------|
| Motif / example / practice lick | Present; motif notes and lick `key_center` unchanged; mission title if scripted |

### Item 4 — context snapshots

| Field | Match phone |
|-------|-------------|
| `harmony_map_section`, `harmony_map_chord` | Exact (reflects **phone writer** save — e.g. post–Item 6 state or a **new** deliberate Harmony Map / mission change) |
| `creative_session.tool_type`, display-key snapshot | Exact |

### Passive / violations (Dell read startup)

| Signal | Expected |
|--------|----------|
| Item 1–4 `violations` | `[]` |
| `certification_failures` | `[]` |
| `certification_passed` | `true` (Item 5 panel on Dell reader) |
| Passive semantic drift keys | `[]` or suppressed per frozen passive audit |

---

## Save / write contract (Item 7 adds no new save reasons)

**Phone (writer device):**

- Only **existing frozen user save reasons** (e.g. `creative_context_section_change`, `creative_mission_target_change`, metrics change, display-key flush when scripted).
- Must observe: `cloud_save_requested` → `cloud_confirmed` @ **R′**; strict egress trace unchanged from Item 6 Dell writer bar.
- **Recommended:** one deliberate change **distinct from Item 6 sign-off** (e.g. Harmony Map chord **G7** after Item 6 left **Ab**, or mission target tile) so **R′ > 317** and Dell cannot pass by stale **317** memory alone.

**Dell (reader device):**

- **Read path only** until checklist captured—no sidebar/globals/Creative taps that trigger persist.
- Prefer: **hard refresh** or **new tab** on existing Dell Chrome profile (exercises `hard_refresh` lifecycle) **or** Incognito Dell session (exercises `cold_reboot`) — document which was used.
- Latest cloud wins via frozen hydrate apply — **no** Creative-only channel.

**Forbidden:**

- Dell startup write or upsert that bumps revision when opening after phone save.
- Session cache or pre-phone widget state overriding network @ **R′** (Item 5 fetch precedence frozen).
- Item **8** conflict UX (explicit stale block) — out of scope; Item 7 only requires **correct read** when Dell opens **after** phone confirmed write.

---

## Focused live-test plan (Item 7 only)

**Goal:** One manual **phone → Dell** sign-off; code changes **only if** live or automated gap is proven.

### Step 1 — Live runbook (manual) — **primary gate**

**Environment:** Streamlit Cloud `dev`, Daniel workspace, **`?dev=1`** on both devices.

1. **Baseline:** Confirm cloud @ **317** (or current) matches frozen Item 6 end state on at least one device.
2. **Phone — deliberate user save** (frozen reason only). Record: `save_reason`, changed fields, `current_cloud_revision=R′`, egress flags, `violations=[]`.
3. **Phone — optional:** Item 5 certification snapshot @ **R′** as writer evidence.
4. **Dell — open app** (script: hard refresh **or** cold session). **Do not edit** until capture complete.
5. **Dell — verify checklist** via Phase 1 expander (Item 4 + Item 5 certification): **R′**, network fetch, no write flags, Items 1–4 parity with phone writer record.
6. UI spot-check: Harmony Map, mission tuple, example notation notes, mission title if applicable.
7. Sign off: date, **R′**, writer/reader `session_start_kind`, `certification_passed=true` on Dell.

### Step 2 — Read-only diagnostics (optional)

Only if live failure is ambiguous:

- Reuse Item 5 certification on Dell reader; optional session-only `writer_revision=R′` query param for manual compare (**never** persist to Supabase/workspace).
- Do **not** add cross-device channels or new save paths.

### Step 3 — Automated regression (target)

- `test_item7_dell_apply_matches_phone_payload_after_writer_bump` — simulate phone-writer payload @ **R′** applied into empty Dell session; assert Items 1–4 + globals parity (mirror Item 6 double-apply test).
- Extend only if live failure isolates a specific projection field.

### Step 4 — Fix policy

- Smallest hydrate/project/gather fix; no Items 1–6 or Phase C A–E redesign.
- Separate commit from runbook/doc updates; re-run Item 5 + Item 6 frozen regression before re-accept.

### Step 5 — Sign-off artifact

Mark Item 7 ✅ in [phase1 remaining](./2026-08-02-phase1-creative-state-persistence-remaining.md); summary in [completed features](../music_app_completed_features.md). **Do not** start Item **8** until Item 7 passes.

---

## Out of scope

| Topic | Item |
|-------|------|
| Stale-device overwrite block / retry UX | **8** |
| Style Identity engine | Phase 2 |
| Upload/multitrack media | [media sprint](./2026-06-27-uploads-multitrack-persistence-sprint.md) |
| `main` merge | Forbidden unless explicit release |

---

## Code map (read / test unless gap found)

Same as Item 6 — `suite_cloud_state`, `apply_music_disk_state`, `creative_workspace_state_persistence`, `phase1_item5_refresh_certification` (reader evidence), `music_phase1_dev_diagnostics`, [mission workspace contract](./2026-07-30-mission-workspace-contract.md).

---

## Live acceptance (Item 7) — **PASSED 2026-08-03**

| Role | Evidence |
|------|----------|
| **Phone writer** | Harmony Map **Ab → G7**; `creative_context_section_change`; Item 2 tuple **Ab** unchanged; strict egress @ **R′=319** |
| **Dell stale reader** | Pre-phone tab hard-refreshed; `session_start_kind=hard_refresh`; network @ **319**; no Dell write; **G7** restored; `certification_passed=true` |

**Phase 1 gate (Item 8):** **Live-accepted & frozen** @ **`8ef698e`** — [contract](./2026-08-03-item8-stale-device-revision-protection.md).
