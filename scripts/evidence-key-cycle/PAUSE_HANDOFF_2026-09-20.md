# Pause handoff — 2026-09-20

## Repo
- Worktree: `C:\Users\danie\Documents\GitHub\ai-music-practice-coach-backing-key-cycle`
- Branch: `feature/backing-advanced-key-cycling`
- Base SHA: `a0beb97` (HEAD still a0beb97; local dirty / WIP commit may sit on top)
- `KC_SHORT_PASS_*`: unset
- No push / PR / merge. `dev` and Creative untouched.

## 8510
- Left running: http://127.0.0.1:8510 (python streamlit PID was live at pause)
- Data dir: `_runtime_key_cycle_8510`
- Cycling forced Off on disk (`backing_key_cycle_enabled=False`)
- Restart if needed:
  ```
  cd C:\Users\danie\Documents\GitHub\ai-music-practice-coach-backing-key-cycle
  $env:MUSIC_APP_DATA_DIR = (Resolve-Path "_runtime_key_cycle_8510").Path
  $env:PYTHONPATH = (Get-Location).Path
  foreach ($k in @("KC_SHORT_PASS_BARS","KC_SHORT_PASS_LOOPS","KC_SHORT_PASS_FORCE","KC_SHORT_PASS_SECS")) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
  python -m streamlit run streamlit_music_practice_app.py --server.port 8510 --server.headless true --browser.gatherUsageStats false --server.address 127.0.0.1
  ```

## Units (passed)
- `tests/test_musician_coaching.py` — 17 passed (caption helpers + pending line)
- BPM resolve / owner gather / persist-stale / seed Verse+Chorus related units — passed in focused runs
- See `scripts/evidence-key-cycle/unit_caption_bpm.txt`, `unit_remaining.txt`

## Browser — caption (partial)
Evidence: `scripts/evidence-key-cycle/caption_pending_8510.json` (run4; run5 interrupted)
- PASS: baseline working line (`You're working in B minor at 96 BPM (4/4, Pop).`)
- PASS: BPM 140 commit (slider/widget/canon 140)
- PASS: pending marker after BPM + after Blues feel
- FAIL: after Play, pending clears but caption reseals to `100 BPM (4/4, Pop)` even though generate_saved / disk show Blues+140
- Fix in progress (unverified): force session bpm/groove into chart build; clear frozen audible chart + chart cache after generate

## Browser — key-cycle remaining (not re-proven on final code)
Prior `finish_five_8510.json` (older code): Verse+Chorus + Feel Blues had passed earlier; BPM/Pause-click/refresh incomplete.
Outstanding product targets still open:
1. BPM sticks through Play → audible timing + highlight (generate already 140/Blues; caption/chart paint lagged)
2. Pause/Resume via visible controls without handler fallback (double-toggle fix in bridge, bind ver 4 — browser not re-verified after last pause fix)
3. Natural handoff → one audible player; persist; refresh Held/Resume; Resume plays restored key
4. Final Verse+Chorus + natural check on final code

## Exact next step on resume
1. Confirm 8510 serves latest dirty/WIP code (restart if unsure).
2. Re-run `python -u scripts/proof_kc_caption_pending_8510.py` — expect pending clear **and** caption stays 140/Blues after Play.
3. If caption passes: run `python -u scripts/proof_kc_finish_five_8510.py` (no SHORT env) for BPM audio, Pause/Resume, natural, refresh.
4. Checkpoint verified passes; leave cycling Off.
