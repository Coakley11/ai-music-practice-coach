# Remaining issues after key-cycle → local dev merge

Recorded at integration (not yet fixed in this merge commit).

1. **Back to loop start** — Must seek to the FIRST CHORD of the CURRENT repetition in the CURRENT cycle key and immediately play (even if paused/stopped). Must NOT reset the cycle to its first key.

2. **Transport labels** — Keep synchronized:
   - Playing: cycle controls "Pause"; Live Follow-Along "Stop playback"
   - Paused/stopped: cycle "Resume"; Live Follow-Along "Resume playback"
   After loop-start, Resume, manual key changes, natural handoffs, arrangement updates.

3. **Current Chord / Next Chord** — Still incorrect in manual review; treat as unresolved. Trace audible buffer + active timeline + status panel + sheet highlight; fix stale data source across manual/natural key changes and section/repeat boundaries.

4. **Written-key / guitar-shape display** — Deferred to a later dedicated checkpoint after 1–3.

Merge parents: local `dev` @ e5444de + `feature/backing-advanced-key-cycling` @ 5b13d2e.
Creative Cursor worktree (`feature/creative-practice-focus-icons` @ db5b698, ancestor of origin/dev) was not checked out or overwritten; ports 8511/8561/8564 left alone.
