# Resume handoff — 2026-09-22 (after pause resume)

## Repo
- Worktree: `C:\Users\danie\Documents\GitHub\ai-music-practice-coach-backing-key-cycle`
- Branch: `feature/backing-advanced-key-cycling`
- Base WIP: `60d0095` (still HEAD until new checkpoint commit)
- Dirty product fixes on top of `60d0095` (uncommitted at handoff write time)
- No push / PR / merge

## 8510
- Left running for review (restart recipe unchanged in PAUSE_HANDOFF_2026-09-20.md)
- Data dir: `_runtime_key_cycle_8510`
- Cycling: **Off** on disk
- `KC_SHORT_PASS_*`: unset

## Caption stale-writer (fixed in code; browser partial)

**Root cause:** `store_prepared_cycle_audio` defaulted `bpm=100` / `groove_style="Pop groove"`, so
`bpm or session[...]` never consulted session/signature. Dual-buffer then injected a
prepared lead sheet caption of **100 BPM / Pop** over the live chart while generate
was already **Blues + 140**.

**Also fixed:**
- Pass explicit bpm/groove from Play generate into `store_prepared_cycle_audio`
- Stable `arrangement_fingerprint_from_signature` (exclude volatile profile mood)
- Avoid spurious Off remount wiping WAV when still on saved PK
- Reseed cycle UI On after generate remount
- Consume pending + fingerprint after generate; strip Pending pill when applied
- Debounce `note_key_cycle_arrangement_settings_changed` while already pending

## Browser evidence

### Units
- `tests/test_musician_coaching.py` + `TestPreparedChartTempoFeel` — passed (19)

### `proof_kc_caption_pending_8510.py` — run9 (`caption_pending_8510.json`)
Revision note: WIP after 60d0095 — prepared-chart Tempo/Feel from signature
- PASS: baseline working line at 96/Pop
- PASS: pending after BPM 140
- PASS: pending after Blues
- PASS: after Play caption **140 BPM (4/4, Blues)** — **no longer reseals to 100/Pop**
- FAIL: `pending_marker_not_cleared_after_play` (caption still appended Pending)

### Later runs
- run10/run11: hung / thrash during BPM commit + dual-buffer waits; killed
- Pending-clear + debounce fixes **not** re-browser-verified after run9

## Still open (finish_five not started this resume)
1. Pending marker clears after Play (code ready; needs re-proof)
2. BPM audible timing + highlight for clearly different tempos
3. Pause/Resume both surfaces, labels match, no fallback
4. Natural handoff retain tempo/feel/scope/repeats; one audible player
5. Refresh after natural → Held/Resume, first chord, no autoplay
6. Full Verse+Chorus plays/highlights before advance

## Exact next step
1. Confirm 8510 has latest dirty code (restart if unsure).
2. Re-run `python -u scripts/proof_kc_caption_pending_8510.py` — expect 140/Blues **and** pending cleared.
3. Then `python -u scripts/proof_kc_finish_five_8510.py` (no SHORT env).
4. Checkpoint verified; leave cycling Off.
