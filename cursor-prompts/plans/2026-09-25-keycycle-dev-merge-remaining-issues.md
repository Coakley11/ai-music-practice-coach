# Remaining issues after key-cycle → local dev merge

## Integration

- **Local `dev` SHA (merge):** `b586d85`
- Feature: `5b13d2e` (`feature/backing-advanced-key-cycling`)
- Base: `e5444de` (prior local/origin `dev`)
- Creative Cursor worktree left on `feature/creative-practice-focus-icons` @ `db5b698` (untouched)

## Post-merge fix checkpoint (transport / chord) — this commit lineage

1. **Back to loop start** — seeks first chord of the *current* repetition in the *current* cycle key and plays immediately (`__kcSeekAndPlay`). Does not reset cycle to first key.
2. **Transport labels** — Playing: cycle `Pause` / Live `Stop playback`. Held: cycle `Resume` / Live `Resume playback`. Audible playback clears stale pause latches.
3. **Current / Next Chord** — Prefer `__kcTimelineByKey[audible]` over a lagging parent `__kcFollowTimeline`; refuse empty timeline wipes; push timeline into live-follow iframes on adopt.

## Audio-ready after spill (follow-on checkpoint)

- **Bug:** after Play, WAV was spilled to `_last_backing_wav_path` and bytes popped; `_session_backing_audio_ready` still required in-memory bytes, so the cycle dual-buffer never mounted (label showed Pause, buffers empty).
- **Fix:** treat path / on-disk static URL as ready; `ensure_cycle_current_static_url` spills+publishes when needed; explicit Play forces regen when nothing publishable.
- **Browser:** `diag_cycle_off_on_play` OK (dual-buffer playing). Full transport/chord sheet+label proof still open (live-follow shell / sheet remount).

## Still open

4. **Written-key / guitar-shape display** — sounding stays concert; strip/chart/Current/Next follow written/shape projection; mid-cycle mode change preserves concert audio + cycle position. Separate checkpoint after transport/chord browser settles.
5. **Browser transport/chord (sheet open)** — re-verify loop-start + Pause/Stop labels + chord agree with lead sheet open after the audio-ready fix.
