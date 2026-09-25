# TargetClosed diagnosis (8510 proofs)

**Date:** 2026-09-24  
**Context:** finish_five / transport / Feel proofs on `feature/backing-advanced-key-cycling`

## Observed

`playwright._impl._errors.TargetClosedError: Page.wait_for_timeout|evaluate|goto: Target page, context or browser has been closed`

## Causes identified

1. **Harness / cleanup killing Chromium mid-run (primary for early crashes)**  
   Shell wrappers used broad process kills matching `chromium|playwright|chrome-headless` *while* or *just before* a new proof launched. That closes Playwright’s browser process → immediate TargetClosed on the next page API call.  
   Evidence: Feel run17–20 died on first `goto` / early boot after such kills; 8510 itself briefly went `ERR_CONNECTION_REFUSED` when the Streamlit PID was collateral damage.

2. **Aggressive Chromium launch flags**  
   `args=['--no-sandbox','--disable-gpu',...]` caused instant browser death on this Windows host. Plain `chromium.launch(headless=True)` is stable.

3. **Long-matrix exhaustion (finish_five_run15)**  
   After ~28 minutes of BPM slider retries + Feel commits, TargetClosed on `wait_for_timeout` with **no concurrent kill**. Script’s `browser.close()` only runs in `finally` after the exception — so the browser/context died underneath (Chromium crash / OOM / renderer kill), not an intentional harness close.  
   Timeline: boot OK → many failed `bpm_commit` attempts → Feel thrash → TargetClosed. Not classified as a product Pause/Resume failure.

4. **Normal harness close**  
   Proofs call `browser.close()` / `context.close()` in `finally`. That is expected and only surfaces as TargetClosed if later code still touches the page.

## Mitigation for remaining checks

- Never kill `chromium`/`playwright` while a proof is running; only stop named `proof_kc_*` PIDs if restarting.
- Prefer **short, single-purpose proofs** (BPM / refresh-Resume / V+C natural) instead of full `finish_five`.
- Save each report to its own JSON/log so a later failure cannot overwrite earlier evidence.
- Leave orphan headless shells only after confirming no live `proof_kc_*` parent.
