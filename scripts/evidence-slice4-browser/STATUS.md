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

## Slice 4B — Back/Forward (paused mid-slice for Codex handoff)

**Accepted Slice 4 baseline:** `03769d2` (`SLICE4_BROWSER_PASS=True`)  
**This checkpoint:** Forward-stack remount fix + Creative workspace history hooks + units (see commit)  
**`SLICE4B_BROWSER_PASS`:** **False** (browser matrix incomplete)

| Check | Result |
|-------|--------|
| Unit: pending-target remount keeps Forward | **PASS** |
| Unit: new nav after Back clears Forward | **PASS** (`test_new_nav_after_back_clears_forward`) |
| Unit: Creative workspaces as separate dests | **PASS** (unit) |
| Unit: envelope survives history Back/Forward | **PASS** |
| Browser: Composition envelope + ← Back | **PASS** (soft) |
| Browser: Forward → after Back remount | **Unit-fixed**; full browser re-verify still open |
| Browser matrix §§1–14 (Creative traversal, owners, Return loops, etc.) | **Not completed** |

Evidence: `scripts/evidence-slice4b-nav/` · proof `scripts/_proof_slice4b_back_forward.py`

## Do not

- Start Slice 5 until Slice 4B is green (`SLICE4B_BROWSER_PASS=True`)
- Push until Daniel verifies
- Reopen Slice 4 owner envelopes unless nav audit proves regression
