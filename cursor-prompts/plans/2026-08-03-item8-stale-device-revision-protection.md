# Phase 1 Item 8 — Stale-device revision protection & overwrite prevention

**Last updated:** 2026-08-03  
**Status:** **Next** — contract + live-test plan only (no implementation until gap proven or live failure)  
**Prerequisites (frozen — do not redesign):**

| Layer | Live-accept / freeze anchor |
|-------|-----------------------------|
| Items 1–5 | Through `b989516`; doc `cc00cda` |
| Item 6 Dell → phone | **FROZEN** @ **317** |
| Item 7 phone → Dell (stale reader hydrate) | **FROZEN** @ **319** — [contract](./2026-08-03-item7-phone-dell-cross-device-persistence.md) |
| Monotonic `workspace_revision`, strict egress, startup suppression, Items 1–4 save reasons | Accepted architecture — no fork |

**Phase 2** Style Identity engine starts only after Item **8** live-accept (Phase 1 items **1–8** complete).

---

## Purpose

Prove that a device holding **stale local workspace state** at revision **L** (where **L < cloud R**) **cannot silently upsert** and clobber a **newer cloud document** at **R** written by another device or session.

Item 8 is the **write-side** cross-device gate. Items **6–7** proved **read** paths (network hydrate wins). Item 8 proves **save** paths reject or defer stale writes until the device reconciles with cloud.

---

## Distinction from Items 6–7

| Item | Question answered |
|------|-------------------|
| **6–7** | After remote save @ **R**, does the other device **read** **R** correctly without spurious startup write? |
| **8** | With local state still at **L < R**, does a **local user save attempt** **fail closed** (no confirmed upsert @ stale revision) and leave cloud @ **R** intact? |

Item 7’s Dell hard refresh **without edit** is **not** Item 8. Item 8 requires the stale device to **attempt a user-initiated persist** while still logically behind cloud (or immediately after hydrate skip without full resync — see live script).

---

## Authoritative failure / success signals

### Stale writer attempt (device behind cloud)

Precondition: cloud authoritative @ **R** (e.g. **319** from Item 7 phone write). Stale device session believes or carries canonical aligned to **L < R** (e.g. Dell tab **never refreshed** after phone save, Harmony Map still **Ab** locally).

User triggers **one frozen save reason** on stale device (e.g. Harmony Map tap, mission target, display-key flush).

| Signal | Expected (pass) |
|--------|-----------------|
| `cloud_save_requested` | May be true (attempt entered pipeline) |
| `cloud_write_succeeded` / `cloud_confirmed` | **false** OR save **blocked before upsert** with documented reason |
| `cloud_write_attempted` | **false** if blocked pre-egress; **true** only if strict path rejects without applying stale payload to cloud |
| Authoritative **cloud revision after attempt** | Still **R** (unchanged) |
| Stale device must not publish payload with `workspace_revision` ≤ **L** that replaces cloud **R** | Verified by refetch or second-device read |

### Trace / diagnostics (`?dev=1`)

Document at least one of:

- `conflict_detected` / `conflict_resolution_result` (`workspace_revision.collect_workspace_revision_diagnostics`)
- Explicit block reason in save transaction / egress trace (e.g. cloud newer than local, revision mismatch, resync required)
- `music_creative_cloud_drift` / content resync path forcing **network apply before save** (if product chooses reconcile-then-save — must not double-write stale)

**Pass:** cloud @ **R** unchanged; other device reader still sees **R** document.  
**Fail:** cloud drops to stale content or revision regresses / duplicate fork.

### After explicit reconcile (optional sub-test)

If UX requires **Refresh / pull latest** or automatic resync:

1. Stale device hydrates @ **R** (Item 5/7 bar).
2. **Then** user save bumps to **R+1** with confirmed upsert.

Reconcile path is **in scope** only if live stale-save attempt would otherwise trap user; must not weaken Item 8 fail-closed default.

---

## Live-test script (primary gate)

**Environment:** Streamlit Cloud `dev`, Daniel workspace, **`?dev=1`**.

### Setup

1. Establish cloud @ **R** (Item 7 end state: Harmony **G7**, rev **319** on phone + refreshed Dell).
2. **Stale device:** Dell (or phone) tab left open **without refresh** since **before** phone wrote **319**, local UI still shows pre-**319** state (e.g. Harmony **Ab**). Confirm session applied revision **L < 319** in dev revision diagnostics if visible.

### TEST A — Stale save blocked (required)

1. On stale tab only, one deliberate **frozen** user interaction (e.g. tap Harmony Map chord or mission tile).
2. Capture save transaction + workspace revision diagnostics + egress trace.
3. **Verify cloud still @ 319** (refresh other device or Supabase/dev panel `current_cloud_revision`).
4. **Verify** Harmony on authoritative reader still **G7**, Item 2 tuple unchanged, no silent regression to **Ab** cloud-wide.

### TEST B — Cloud unchanged on second reader (required)

1. Without saving on fresh device, open `?dev=1` on phone (or Dell hard refresh) **after** TEST A.
2. Expect network @ **319**, Item 5 `certification_passed=true`, Item 4 harmony **G7**.

### TEST C — Explicit retry after resync (recommended)

1. Hard refresh stale device → hydrate @ **319**.
2. One user save → **R+1** with `cloud_confirmed=true`.
3. Confirms stale block is not a dead-end.

---

## Save / write contract (Item 8 may extend diagnostics only)

**Allowed changes (minimal):**

- Pre-save guard: compare `workspace_revision_from_blob(local_canonical)` vs `_suite_cloud_workspace_revision` / last confirmed cloud revision.
- Set `_suite_workspace_conflict_detected` + `conflict_resolution_result` when blocking.
- Read-only Item 8 panel fields mirroring Item 5 pattern (`stale_write_blocked`, `local_revision`, `cloud_revision`, `block_reason`).

**Forbidden without unfreeze:**

- New Creative-only sync channel.
- Weakening Items 1–7 gather/suppression or strict egress confirmation.
- Silent “last writer wins” without monotonic revision check when cloud is ahead.

**Existing hooks (read first):**

- `workspace_revision.py` — `cloud_revision_newer_than_applied`, `collect_workspace_revision_diagnostics`
- `suite_user_persistence.py` — cloud newer apply paths, content resync
- `music_egress_strict_save.py` — fail-closed egress
- `music_workspace_cloud_save` / save transaction diagnostics

---

## Focused implementation plan

1. **Live TEST A/B first** on current `dev` — document pass/fail with traces (may already block via strict egress + revision; Item 8 names the acceptance bar).
2. If live **fail** (silent stale overwrite): smallest guard in save reservation or egress preflight; unit tests for `L < R` block.
3. Optional read-only `collect_phase1_item8_stale_write_certification(session)` — no Supabase persist.
4. Automated: `test_stale_local_revision_cannot_confirm_upsert_when_cloud_ahead` with mocked cloud @ **319**, local @ **317**.
5. Sign-off: update [phase1 remaining](./2026-08-02-phase1-creative-state-persistence-remaining.md), [completed features](../music_app_completed_features.md); **then** Phase 2 gate review — **do not** start Phase 2 until Item 8 ✅.

---

## Out of scope

- Phase 2 Style Identity engine (queued after Item 8)
- Upload/multitrack media sprint
- Full conflict-merge UX / version history (v1 = block or resync-then-save only)
- `main` merge unless explicit release

---

## Live acceptance (Item 8)

Stale-device user save with **L < R** does **not** confirm cloud upsert; cloud remains @ **R**; authoritative reader unchanged; trace documents block or resync. Optional TEST C proves recovery path. Document commit SHA at sign-off.
