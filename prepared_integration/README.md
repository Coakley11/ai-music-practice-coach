# Issue 62 — `streamlit_music_practice_app.py` integration (APPLIED)

The capture patch that was held back in the first pass is now **applied on this branch**.
It was held back because three of the other agent's branches edit this file; re-checking
before applying showed none of them touch the regions involved:

| Branch | Hunks in the app file | Multitrack region (27000–28500) | Upload region (25900–26800) |
| --- | --- | --- | --- |
| `integrate/backing-controls-20261109` | 9 | 0 | 0 |
| `integrate/chord-tone-hints-levels-20261109` | 3 | 0 | 0 |
| `feature/backing-loudness-match` | 1 | 0 | 0 |
| `fix/backing-context-card-alias` | 0 (different file) | 0 | 0 |

No worktree had uncommitted changes to the file at the time of applying, and `origin/dev`
was still `3326a87e`.

`issue62-multitrack-capture-quality.patch` is kept as the record of the first two hunks.
It no longer needs applying — `git diff origin/dev -- streamlit_music_practice_app.py` is
the authoritative view, and it is larger than the patch because of the three additions
described below.

## What is now in the app file

All five changes are additive and confined to two blocks: `elif _studio_page ==
"multitrack":` and the Multitrack branch of `elif _studio_page == "analysis":`.

1. **Music-grade capture rate.** `st.audio_input(..., sample_rate=capture_sample_rate())`
   (48 kHz) instead of Streamlit's `sample_rate=16000` speech default. Passed through a
   kwargs dict, and a `TypeError` falls back to a plain `st.audio_input` call, so an older
   Streamlit records at its own default rather than losing the recorder entirely.
2. **Instrument-friendly microphone constraints.** `install_multitrack_music_capture(...)`
   reuses the existing `mission_music_capture` script for the Multitrack mics, so
   `echoCancellation / noiseSuppression / autoGainControl` are requested as `false`.
3. **Per-layer key stamping.** `note_layer_recorded(st.session_state, slot,
   concert_key=concert_key)` as each layer's audio is stored, so the key a layer was played
   in travels with that layer.
4. **Key-conflict warning.** `key_conflict_warning(...)` shown above the layers when the
   Practice Key no longer matches the layers already recorded.
5. **Ensemble handoff is consumable.** The Multitrack branch of Step 2 now shows the
   handed-off export (banner + preview) and analyses it when the uploader is empty. Without
   this, fixing the workflow created a new dead end: the correct Multitrack branch reads its
   own uploader, so the musician was asked to upload the file they had just sent.

## Verified in the running app

Driven with Playwright against a local server on `127.0.0.1:8511`, with
`MUSIC_APP_DATA_DIR` pointed at a scratch directory inside this worktree (storage resolves
to `…/ai-music-issue62/data/workspaces/daniel`, so none of the real recordings were
touched).

Confirmed: the Multitrack page renders with no exception; all 6 `st.audio_input` recorders
render with the 48 kHz request and **no** "Recording unavailable in this build" caption;
the mic-constraint script installs and registers 15 widget-key candidates; the Export
Library shows `Recorded in: G major`, `Recorded instruments: Guitar, Bass`, `Level when
recorded: Intermediate`; Step 2 switches to the Multitrack ensemble branch after the
handoff; 390 px renders with no horizontal scroll; 0 console errors.

## Still not verified

- **Real microphone capture.** This machine has no microphone and no instrument. Layers
  were supplied by file upload, which is the same code path once the bytes exist. Whether a
  device actually grants 48 kHz, and how a real flute sounds through it, is unverified.
- **Which `st-key-*` spelling the browser produces.** `widget_key_class_candidates` offers
  four spellings per key so one matches, and the script registered all of them, but no
  recording was started through a real microphone to confirm the match fires.
  `window.__mcMusicCapture.takes[-1].settings` in the browser console reports what the
  track actually received and is the quickest confirmation.
- **Loop-boundary chord sync.** Blocked on Issue 59 (`0b39addc`, still not in origin/dev).
