# Checkpoint — focused key-cycle proofs (8510)

- **When:** 2026-09-24 (local)
- **Worktree:** `ai-music-practice-coach-backing-key-cycle` @ `79dcc09` + uncommitted fixes in `backing_key_cycle.py`, `backing_track_state.py`, `streamlit_music_practice_app.py`, and related tests/proofs
- **Port:** 8510 left running; cycling Off; `KC_SHORT_PASS_*` unset; no leftover proof jobs

## Uncommitted product fixes in this revision

1. **Scope auto-apply** — `_kc_user_arrangement_edit` bypasses remount early-return; fingerprint `_unapplied` path; seal fingerprint only when applied matches.
2. **Seed must not re-invent Verse+Chorus** after user edits (`seed_backing_multi_sections_for_widget` + canon fallback).
3. **CONTINUE + sticky URL** — force regenerate when `needs_regen` / sig mismatch (do not treat prior Verse WAV as ready).
4. **Prepared neighbor timeline** — `store_prepared_cycle_audio(timeline=…)`; do not copy audible-key timeline onto neighbors; prefetch passes `_cached_backing_timeline`.
5. **Handoff JS** — clear follow timeline when neighbor timeline missing (no stale prior-key Current/Next).

## Browser proofs (separate from unit)

| Check | Result | Evidence |
|-------|--------|----------|
| 1 Pop→Bossa no Play | PASS | `pop_to_bossa_auto_8510.json` |
| 2 Verse→V+C no Play | PASS | `verse_to_vc_auto_8510.json` |
| 3 Chord sync natural handoff | FAIL (remaining) | `chord_sync_handoff_8510.json` — one Bm→Am capture looked correct; later runs still miss first-key land / show mismatched chord labels vs sounding |
| 4 Final-key stop + Next | NOT RUN (blocked on 3) | — |
| 5 Pending until Play | NOT RUN (blocked on 3) | — |

## Unit (separate)

- `tests/test_backing_key_cycle_temporary_session.py` — passed (incl. scope-only auto-apply, wrong-key timeline guard)
- `tests/test_backing_track_state.py -k seed_multi` — passed

## Remaining product failure (plain)

**Current/Next Chord across a natural handoff** is still not reliable enough to pass the focused browser proof. Neighbor prepared timelines are improved and Bm→Am once looked right, but the proof still fails (often cannot stay on Bm long enough to sample, or chord labels disagree with the sounding key). Checks 4–5 were not started.

Preserved from earlier work (not re-broken here): loop-start→both Resumes, transport labels, auto BPM; Pop→Bossa and Verse→V+C no-Play auto-apply now pass.
