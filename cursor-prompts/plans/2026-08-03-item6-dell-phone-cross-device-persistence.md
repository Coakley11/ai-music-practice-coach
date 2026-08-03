# Phase 1 Item 6 — Dell → phone cross-device persistence

**Last updated:** 2026-08-03  
**Status:** **Next** — contract + live-test plan only (no implementation until gap proven)  
**Prerequisites (frozen — do not redesign):**

| Layer | Live-accept / freeze anchor |
|-------|-----------------------------|
| Items 1–4 Creative stack | **FROZEN** through `c72a879`; doc anchor `cc00cda` |
| Global control ownership, display-key pipeline, startup queue | Through `616f4e4`, `2aff988`, `f87c1f9` |
| Studio page + Mission Backing handoff | `38664fc`–`ad68e71` |
| Strict egress, monotonic revisions, Supabase upsert confirmation, startup suppression | Accepted architecture — no fork |
| Item 5 refresh / cold reboot | **LIVE-ACCEPTED** `e36fd40`, `2156bb1`, `b989516` @ rev **315** |

Items **7** (phone → Dell) and **8** (stale-device revision protection) are **out of scope** for Item 6.

---

## Purpose

Prove that a **user-initiated save on Dell** at authoritative cloud revision **R** produces a **network pull on phone** (same account, Streamlit Cloud `dev`) that restores the **same Phase 1 Creative workspace document** as Item 5’s checklist—without requiring a second save on phone and without silent field drift.

Item 6 is an **integration acceptance gate** across **two physical browsers**, not a new sync channel. Reuse the existing music workspace envelope, latest-save-wins apply path, and frozen Items 1–5 semantics.

---

## Distinction from legacy Phase C Tests A–E

Phase C (2026-06-09) proved **field-level** cross-device sync for page, Practice, Backing, active song, and AMI return.  
Item 6 proves **full Creative workspace document parity** after Items 1–5: selectors, mission config + atomic tuple, artifacts, context snapshots, globals, studio navigation, and revision discipline—**Dell writer → phone reader**.

---

## “Phone matches Dell post-save” — authoritative checklist

After Dell save completes (upsert confirmed, refetch @ **R**), open phone with **network hydration** (fresh tab or cold session acceptable; record `session_start_kind` for diagnostics only).

### Cloud / fetch discipline

| Signal | Expected on phone |
|--------|-------------------|
| `fetch_source` / certification fetch | `network` (authoritative current-run startup hydration) |
| `loaded_revision` / `current_cloud_revision` | **R** (same as Dell post-save) |
| `revision_unchanged` on phone read-only startup | `true` if phone did not write |
| Revision reservation / upsert on phone **before any user edit** | All `false` |

### Global controls

| Field | Match Dell |
|-------|------------|
| `display_key`, `instrument`, `level`, `focus` | Exact (e.g. **Cm** / **Piano** / **Beginner** / **Left-Hand Patterns**) |

### Item 1 — selectors

| Field | Match Dell |
|-------|------------|
| `improv_intelligence_tab`, entry/lab modes | Exact |

### Item 2 — mission config + target tuple

| Field | Match Dell |
|-------|------------|
| Section, chord index, chord, label, metrics | **Atomic tuple** unchanged (e.g. Melody A · **Ab**, index **3**) |

### Item 3 — artifacts

| Field | Match Dell |
|-------|------------|
| Motif / example / practice lick | Present; motif notes unchanged (e.g. Ab, C, Eb, Bb, Gb); lick `key_center` unchanged |

### Item 4 — context snapshots

| Field | Match Dell |
|-------|------------|
| `harmony_map_section`, `harmony_map_chord` | Exact (e.g. Melody A / **G7**) |
| `creative_session.tool_type`, display-key snapshot | Exact; independent from Item 2 chord |

### Studio navigation (when in test script)

| Field | Match Dell pre-save navigation family |
|-------|----------------------------------------|
| `studio_page`, Mission Backing handoff | Per scripted scenario (Creative vs Backing mission subview) |

### Passive / violations (`?dev=1` on phone read startup)

| Signal | Expected |
|--------|----------|
| Item 1–4 `violations` | `[]` |
| Phone startup write flags | Same no-write bar as Item 5 cold reboot when user has not edited |

---

## Save / write contract (Item 6 adds no new save reasons)

**Dell (writer device):**

- Only **existing frozen user save reasons** (e.g. mission target change, harmony map, display key flush, page_change when scripted).
- Must observe: reserved revision → upsert succeeded → force network refetch @ **R** (existing strict egress trace).
- Record Dell panel: `current_cloud_revision`, Item 5 certification snapshot optional.

**Phone (reader device):**

- **Read path only** until checklist captured—no taps that trigger persist.
- Latest cloud wins via `apply_music_disk_state` / creative workspace apply—**no** Creative-only channel.

**Forbidden:**

- Phone silently overwriting newer cloud with stale session on open (Item **8** handles explicit stale protection UX).
- Treating phone session cache as authoritative when network hydrate @ **R** is available (Item 5 fetch precedence frozen).

---

## Focused implementation plan (Item 6 only)

**Goal:** Live sign-off on two devices; code changes **only if** live or automated gap is proven.

### Step 1 — Live runbook (manual) — **primary gate**

**Environment:** Streamlit Cloud `dev`, same account (Daniel workspace), **`?dev=1`** on both devices.

1. **Dell — establish state** at known revision (reuse Item 5 profile @ **315** or save one user event to bump **R**; record **R**).
2. **Dell — one intentional user save** (frozen reason only—e.g. harmony map tap or mission target if script requires fresh bump).
3. Confirm Dell: upsert OK, `current_cloud_revision=R`, Item 1–4 fields match script.
4. **Phone — open app** (normal Chrome; not required to be Incognito). Wait for load; **do not edit**.
5. **Phone — verify checklist** above via Phase 1 dev expander (Item 4 block + Item 5 certification panel for fetch/revision/no-write).
6. Optional: Creative UI spot-check (Harmony Map chord, mission tuple, example notation notes).
7. Sign off with date, **R**, Dell + phone screenshots, and `certification_passed` on phone if Item 5 panel used.

### Step 2 — Read-only diagnostics (optional, minimal)

If live failure is ambiguous, add **display-only** aggregator (no routing/persist changes):

- `collect_phase1_item6_cross_device_certification(session)` — compares session to `expected_revision` + frozen field snapshot captured on Dell (session-only or query param handoff for manual tests; **never** Supabase/workspace persist).
- Reuse Item 5 fetch evidence + lifecycle classification; add `writer_device_label` / `reader_device_label` manual tags only.

### Step 3 — Automated regression (target)

- `test_item6_phone_apply_matches_dell_payload_rev315` — apply authoritative fixture twice into empty sessions; assert parity on Items 1–4 + globals (simulates cross-device read).
- Extend existing `tests/test_music_phase_b.py` phone→Dell page patterns **only** if Item 6 live failure points to a specific field gap.

### Step 4 — Fix policy

- **Smallest** fix in apply/gather/project only; no redesign of Items 1–5 or Phase C A–E restore.
- Separate commit from runbook/doc updates.
- Re-run Item 5 frozen tests + Item 4 passive audit suite before re-accept.

### Step 5 — Sign-off artifact

Mark Item 6 ✅ in [phase1 remaining](./2026-08-02-phase1-creative-state-persistence-remaining.md); move summary to [completed features](../music_app_completed_features.md). **Do not** start Item 7 until Item 6 passes.

---

## Out of scope

| Item | Topic |
|------|--------|
| 7 | Phone → Dell (reverse direction) |
| 8 | Stale-device revision block / conflict UX |
| Phase 2 | Style Identity engine |
| Upload/multitrack media | Separate [media sprint](./2026-06-27-uploads-multitrack-persistence-sprint.md) |

Do **not** merge `main`.

---

## Code map (read / test unless gap found)

| Area | Role |
|------|------|
| `suite_cloud_state.py`, `suite_user_persistence.py` | Cloud fetch + save |
| `apply_music_disk_state`, `creative_workspace_state_persistence.py` | Hydrate + project Items 1–4 |
| `music_creative_cloud_drift` (if armed) | Resync when cloud differs |
| `phase1_item5_refresh_certification.py` | Reuse fetch/revision/no-write evidence on reader |
| `music_phase1_dev_diagnostics.py` | Live evidence panel |
| Mission workspace [contract](./2026-07-30-mission-workspace-contract.md) | Latest-save-wins semantics |

---

## Live acceptance (Item 6)

Single manual test **Dell → phone** passing the checklist with matching revision **R** and phone read startup showing **no spurious write**. Document commit SHA at sign-off (implementation commits, if any, separate from doc-only contract).
