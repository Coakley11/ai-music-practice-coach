# Phase 1 — Remaining Creative-state & cross-device persistence

**Last updated:** 2026-08-03  
**Prerequisite (done):** Studio **page** persistence Backing → Creative → hard refresh @ rev **193** (`ad68e71`, 2026-08-02)

---

## Accepted baseline (do not regress)

| Step | Evidence |
|------|----------|
| Queued page startup release | Pre-aligned path; `startup_revision_final` stays **191** through release |
| Authoritative page_change save | Reserved/upsert/refetch **193**; all page fields **creative** |
| Fresh network hydration | `fetch_source=network`, `used_session_cache=false`, rev **193**, all pages **creative** |
| New session durability journal | Empty transactions / `authoritative_page_change_cloud_confirmed=false` expected until next nav |

**Revision ladder (diagnostics only — do not change reservation yet):**

- `startup_revision_loaded` = **191**
- `canonical_revision_before_reservation` = **192**
- `reserved_revision` = **193**

Keep visible in Page cloud durability trace for later analysis of whether **192** was necessary.

**Deferred diagnostics-only (later):** `fresh_hydration` may report **network** while `last_cloud_fetch` still shows **session_cache** — must not drive behavior changes to the passing save/hydration path.

---

## Remaining manual acceptance (same account, Streamlit Cloud `dev`, `?dev=1`)

Contract reference: [2026-07-30-mission-workspace-contract.md](./2026-07-30-mission-workspace-contract.md)

1. **Creative tool and tab selections** — ✅ live @ `549578d` (Daniel/music rev **203**, cold session, `startup_write_attempted=false`, `violations=[]`).
2. **Mission configuration and selected mission** — ✅ live @ `c6c2f41` (2026-08-02).
3. **Motif / lick and generated-example state** — ✅ **live-accepted** @ `616f4e4` (2026-08-03) — [Item 3 contract](./2026-08-02-item3-mission-artifact-persistence.md).
4. **Key, section, and Creative context snapshots** — ✅ **live-accepted & frozen** @ `c72a879` (rev **315**, 2026-08-03) — [Item 4 contract](./2026-08-03-item4-key-section-creative-context-snapshots.md).
5. **Refresh and cold-reboot persistence** — ✅ **live-accepted & frozen** @ `e36fd40`–`b989516` (rev **315**, 2026-08-03) — [Item 5 contract](./2026-08-03-item5-refresh-cold-reboot-persistence.md) | [runbook](./2026-08-03-item5-live-runbook.md).
6. **Dell → phone synchronization** — ✅ **live-accepted & frozen** (rev **317**, 2026-08-03) — [Item 6 contract](./2026-08-03-item6-dell-phone-cross-device-persistence.md).
7. **Phone → Dell synchronization** — ✅ **live-accepted & frozen** (rev **319**, 2026-08-03) — [Item 7 contract](./2026-08-03-item7-phone-dell-cross-device-persistence.md).
8. **Stale-device / revision protection** — **next** — [Item 8 contract](./2026-08-03-item8-stale-device-revision-protection.md); older device cannot silently overwrite newer cloud revision.

---

## Implementation notes (when a check fails)

- Save path: `sync_creative_workspace_before_persist`, `creative_workspace_state`, page snapshots (`creative` / `backing`).
- Apply path: `apply_cloud_creative_state_if_allowed`, envelope apply in `apply_music_disk_state`.
- Do **not** fork a separate Creative-only cloud channel.
- Do **not** reopen Tests A–E page/global/AMI restore without `?dev=1` regression proof.

---

## Phase 2 gate

**Style Identity & Creative Engine Phase 2** ([plan](./2026-07-03-style-identity-phase-2.md)) starts only after items **1–8** above are checked on live `dev`.
