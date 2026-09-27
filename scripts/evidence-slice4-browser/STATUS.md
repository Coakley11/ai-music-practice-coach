# Slice 4 browser acceptance — status

**Base HEAD:** Journey E checkpoint `8ed8bd7`  
**Polluted evidence SHA:** `8ed8bd7` + Composition envelope `force_save` + polluted Chromium relaunch harness  
**Local checkpoint:** pending after this STATUS (polluted green)  
**Push:** none

## SLICE4_BROWSER_PASS

**True** — polluted five-owner gate green after A–E browser-green (accepted per-journey checkpoints A–E).

Evidence: `scripts/evidence-slice4-browser/summary.json`  
Runtime: `_runtime_slice4_polluted6` · URL `http://127.0.0.1:8682`

| Owner | Result | Envelope |
|-------|--------|----------|
| Catalog | PASS | `catalog` · Perfect · G/C |
| SBI Custom | PASS | `sbi_custom` · Trial · D/F |
| Jam | PASS | `entry_jam` · Jam Session Generator |
| Mission | PASS | `mission` · Trial |
| Composition | PASS | `composition::…` · My Composition · C/C# |

## Journey results (accepted)

| Journey | Result | Checkpoint |
|---------|--------|------------|
| A Catalog Perfect G/C→E | **PASS** | earlier |
| B SBI Custom Trial F→F# | **PASS** | `a3c2b67` |
| C Jam + Shape | **PASS** | `5fe65db` |
| D Mission PK F→E | **PASS** | `6a4f9a6` |
| E Composition C#→E | **PASS** | `8ed8bd7` |
| Polluted five-owner | **PASS** | this STATUS |

## Product fix for polluted Composition-after-Mission

Composition Backing UI could stamp in session while disk envelope stayed null (Mission lag / save race).  
`force_save_music_state(..., reason=composition_*_envelope)` after Composition stamp in:

- `streamlit_music_practice_app.py` (card/adopt)
- `backing_source_navigation.open_backing_for_practice_source` (composition + fallthrough)

Harness: Chromium relaunch between polluted owners; seed composition envelope on disk force; no wipe-refresh after reopen.

## Slice 4B — Back/Forward

**Accepted Slice 4 baseline:** `03769d2` (`SLICE4_BROWSER_PASS=True`)  
**Cursor handoff:** `cdfd6c6`  
**Codex remount seal:** `9cd645d`  
**Codex Gate 1 trace checkpoint:** `c182ee68`  
**`SLICE4B_BROWSER_PASS`:** **False** (full matrix not run)  
**`GATE1_FORWARD_BROWSER_PASS`:** **True** (Gate 1 only)

| Check | Result |
|-------|--------|
| Unit focused set (11) | **PASS** |
| Unit: pending-target remount keeps Forward | **PASS** |
| Unit: remount after deferred save keeps Forward | **PASS** |
| Unit: new nav after Back clears Forward | **PASS** |
| Unit: Creative workspaces as separate dests | **PASS** |
| Unit: envelope survives history Back/Forward | **PASS** |
| Gate 1 browser: A→B→C → Back → Forward enabled → Forward | **PASS** |
| Gate 1 browser: Back → D clears Forward | **PASS** |
| Browser matrix §§1–14 (Creative traversal, owners, Return loops, etc.) | **Not completed** |

Evidence: `scripts/evidence-slice4b-gate1/` · proof `scripts/_proof_slice4b_gate1.py`  
Trace: `_runtime_slice4b_gate1b/gate1-trace.jsonl`

### Gate 1 restoration-guard rule (canonical)

After history Back/Forward, keep `_studio_history_nav_remount_target` until a **genuine** navigation to a different destination. Matching remounts of that target must not clear Forward. One-shot `_studio_nav_from_history` and flushed `_studio_history_nav_pending_save` alone must not drop the seal.

### Do not

- Start Slice 5 until Slice 4B is green (`SLICE4B_BROWSER_PASS=True`)
- Push until Daniel verifies
- Reopen Slice 4 owner envelopes unless nav audit proves regression
- Broaden past Gate 1 until remaining matrix is intentionally resumed
