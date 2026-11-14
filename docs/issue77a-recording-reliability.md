# Issue 77A — Record with Count-In was visible and unusable

After Issue 78C the Record control could be seen. It still could not be used: the musician reported

> "Record with Count-In is now visible, but it is disabled or unavailable because an audio asset
> cannot be decoded. One of the parts to play along with could not be loaded. Unable to decode
> audio data."

Three different failures produced that one sentence, it named none of them, and each disabled
Record on **every** layer — because `loadAssets` aborts on the first failing asset, and a recorder
will not arm while any part it was asked to play along with is missing. That refusal is correct:
recording against parts the player cannot hear, while the take is aligned as though they could, is
worse than not recording. Everything around it was wrong.

## Cause 1 — the expected duration was a prediction the renderer could never match

The component refuses any asset whose decoded duration differs from what Python said to expect by
more than `DURATION_TOL_SEC = 0.6`. "Expected" was a formula —
`len(mt_events) * bar_seconds * max(1, loops)` — and `synthesize_chords_to_numpy` deliberately
leaves a second of decay after the music. Measured through the real render path:

| Section repeats | predicted | rendered | difference | rejected |
|---|---|---|---|---|
| 1 | 16.000 s | 17.000 s | +1.0 s | yes |
| 2 | 32.000 s | 33.000 s | +1.0 s | yes |
| 3 | 48.000 s | 49.000 s | +1.0 s | yes |

A constant 1.0 s against a 0.6 s tolerance. **Every prepared monitor backing was refused, for every
song and every loop count** — and pressing *Prepare backing* is the normal path, so this is the one
that stopped the musician. The audio itself was perfect: 40.4 MB, HTTP 200, `audio/wav`, decoding to
457.585 s at 44100 Hz.

## Cause 2 — the prediction also counted different bars from the render

The page said

> Target: full song · 4/4 @ 82 BPM · **72 bars** × 2 ≈ 421.5s

while the recorder decoded 457.59 s. The arithmetic closes exactly at **78** bars:
`78 × 2 × (4×60/82) + 1.0 = 457.585 s`. The estimate counts the chart on screen; *Prepare backing*
renders from `concert_sections_for_backing(...)`, which returns `concert_song_sections_from_session`
wholesale — a different section map, and level variants differ in length. So the "≈ 421.5s" line
does not describe the audio it is about to make.

A different explanation was tested first and **disproved**: dropping `song_data` from
`chord_events_for_selected_sections` (the render omits it, the estimate passes it) changes the bar
count for **0 of 121** catalog songs.

## Cause 3 — a file no decoder can read became a layer

The uploader accepts a file on its extension and the landing path only rejects bytes under 512. A
916-byte file named `.wav` was therefore adopted as a take, served back as `audio/wav`, and refused
by `decodeAudioData`. Measured, with the asymmetry that explains how a musician gets stuck:

| recorder | Record | status |
|---|---|---|
| Guitar | disabled | "One of the parts … could not be loaded. Unable to decode audio data" |
| Sax / winds | disabled | same |
| Extra layer *(owner of the bad audio)* | **enabled** | "Record starts a 4-beat count-in and your 2 other layers together with your take, on one clock." |

| asset | HTTP | type | bytes | first 16 | decode |
|---|---|---|---|---|---|
| …b589.wav | 200 | audio/wav | 32044 | `RIFF$}..WAVEfmt ` | ok, 1.000 s, 44100 |
| …19f9.wav (backing) | 200 | audio/wav | 40359072 | `RIFF..g.WAVEfmt ` | **ok**, 457.585 s |
| …5eb5.wav | 200 | audio/wav | **916** | `RIFF....WAVEjunk` | **FAILED** |

## Why nothing was ever named

The component already reports which asset failed: `ackPayload()` carries the error, byte count,
content type, attempt count and a trace, and Issue 77A adds `failed_asset` to it. Python threw it
away — `render_layer_recorder` returns early for any component value without a take, and the
acknowledgement went with it. Mission records the same payload (`record_backing_ack`); Multitrack
did not.

## What changed

* **The duration is measured, not predicted.** `multitrack_monitor_assets.wav_duration_sec` reads
  the real length from the WAV header — walking the chunk list, so a `LIST`/`fact`/`JUNK` chunk
  before `data` does not hide the audio, and using the bytes actually present when a declared size
  runs past the end. Both the recorder and the transport are told that number, so the tolerance goes
  back to doing its real job: catching an asset that is **not** the one this project means.
* **The acknowledgement is kept**, per layer, and turned into one sentence that names the part —
  "the generated backing track", or "your Rhythm guitar layer" using the name the musician gave it —
  says why in plain words, and says what to do. The browser's own line
  (`decoded 457.59 s, expected 421.46 s`) is kept for a *Technical detail* expander, not used as the
  message.
* **Recovery.** *↻ Try loading again* re-fetches and re-decodes. *Record without &lt;layer&gt;*
  removes that part from the **request** rather than silencing it during playback, so the take's
  `monitors_expected` matches what actually started and `sync_state` keeps reporting the truth — it
  already fails a take with "N part(s) should have played along but M did". What is being recorded
  without is stated on the page, never applied silently.
* **Incoming audio is decoded before it is adopted** (`multitrack_audio_validation`): `soundfile`
  first, then `librosa` for the compressed containers the uploader also accepts. Three deliberate
  rules: it **fails open** when no decoder is installed, it judges by decoding rather than by sample
  rate or container (so a 22.05 kHz mono WAV or a phone's m4a is never turned away), and it
  **deletes nothing** — a file that fails is simply not adopted, and the layer keeps what it had.
* **A cached backing is checked before use**, but only when it *claims* to be a WAV and cannot be
  parsed. The first attempt was broader and broke
  `test_resolve_backing_bytes_from_local_disk_when_session_empty`, which stores `b"disk-backing"` —
  a reminder that this check must not start judging containers.

## What was NOT broken, after measuring

**Free Layering.** An earlier note of mine said the free-layering guard ran too late to matter for
Step 2's recorder. It does not: `apply_multitrack_free_layering_guard` is called in Step 1
immediately after the scope radio, before the recorder is built. With the scope actually set to
*Free layering (no backing)* — confirmed from the radio's checked state — the page fetched only the
layer assets and **not** the 40 MB backing. Count-in-only recording is not blocked by a stale
backing. It was still blocked in that session, by the undecodable *layer*, which is Cause 3.

## Harness lessons, each of which cost a run

* **`MUSIC_APP_DATA_DIR` is the app's persistence root.** `suite_workspace._resolve_data_dir()`
  reads it at import. An earlier note claiming it was only read by debug-dump code is wrong.
  Clearing the worktree's `data/` alone does not produce a fresh session.
* **Windows lets several processes bind the same port.** Three of my own servers were listening on
  8607 at once, and probes read whichever answered. `scripts/run_issue77a_app.sh` refuses to start
  when the port is busy and refuses to continue unless its own PID is the only listener.
* **A fixed sleep is not synchronisation.** Reads taken mid-rerun showed a layer panel with *two*
  Discard rows, and a take whose own Discard control was disabled. Verdicts now wait on
  `[data-testid="stStatusWidget"]` and require the panel to be internally consistent.
* **Assert the starting state.** One reproduction was contaminated by layers restored from a
  previous run, which turned an unsaved take into a *saved layer* and made the control under test
  read "Delete layer".

## Tests

`tests/test_issue77a_recording_reliability.py` — 34 tests. The headline one builds audio shaped
exactly like a real render (music plus the one-second tail) and asserts the number handed to the
recorder now matches what the browser measures, where the predicted number was always outside the
tolerance. The rest pin the header reader against unusual sample rates, stereo, 24-bit, a chunk
before `data` and truncation; the acknowledgement store and its trace fallback; the wording (names
the part, never a raw exception); the exclusion changing the request; `sync_state` still failing a
take that lost a part; validation accepting legacy formats and failing open; and the component
sending the asset identity at all.

`scripts/_accept_issue77a_recording.py` + `scripts/run_issue77a_app.sh` — the browser acceptance.
