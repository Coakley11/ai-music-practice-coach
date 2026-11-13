# Issue 78B — one Record arms the mic, counts in, and starts every part on one clock

Branch `feature/issue-78b-shared-clock-record`, off `origin/dev` `e605eea4`.
**Not integrated. Integration needs separate review and approval.**

The design was approved in `docs/issue78b-shared-clock-recording-plan.md`; this records what was
built, what was measured, and what is still unverified.

---

## What was wrong

A Multitrack overdub needed two separate human actions: press **Play** on the transport, press
**Record** on `st.audio_input`. Those two controls run on two different clocks — `st.audio_input`
lives in the Streamlit document, and the transport has its own `AudioContext` inside an iframe — so
the pre-roll a take carried was whatever gap there happened to be between the two clicks, plus
browser start-up latency. Nothing recorded that gap, so no later alignment could undo it. Slice 78A
fixed the transport's own timing; it could not fix this, because the microphone was never on the
transport's clock in the first place.

## What was built

The layer recorder is now the **shared Mission recorder component**
(`mission_recorder_component/index.html`) — the same `AudioWorkletProcessor` capture on the same
single `AudioContext`. No second recorder, no second capture architecture.

Three changes made that component serve both surfaces:

1. **The asset loader was generalised from one asset to N.** A request is now a list: Mission passes
   one generated backing; Multitrack passes the backing (when there is one) plus every saved layer
   the player is overdubbing against. The request is `ready` only once *every* asset has decoded,
   because a take recorded against a half-armed monitor set would be aligned to something the player
   never heard.
2. **Count-in moved inside the component**, synthesised with oscillators on that same clock, so a
   count-in never waits on an asset load and never depends on a separate transport.
3. **Musical zero is published.** `start()` arms capture, then chooses one future instant: the
   count-in starts there, musical zero is that plus the count-in's length, and each monitor starts at
   musical zero plus *its own* Align position. All of those are frame counters on the capture clock,
   so where bar 1 beat 1 sits inside the take is measured, not inferred.

### Mission compatibility

A one-asset request with no count-in is the path Mission has always taken:

* one asset's fingerprint **is** the request fingerprint, so the handshake is byte-for-byte the same;
* the acknowledgement describes the primary asset exactly as before (an additive `assets` count is
  the only new field);
* the per-asset trace steps are emitted in the same order, which a Mission test pins exactly;
* `backing_offset_sec` is still `null` when no backing was scheduled.

**All 52 Mission recorder tests pass unmodified.** That is the compatibility evidence, not an
assertion that nothing broke.

### The Align contract is reused, not re-decided

Each monitor carries `start_delay_sec` / `buffer_offset_sec` straight from
`multitrack_align_contract.transport_payload` — the same contract 78A gave the transport and the
exported mix. A player therefore hears each layer where the mix will put it. A negative Align skips
into the layer rather than moving nothing, and **the stored take is never modified**.

### Timing is kept additively

`multitrack_live_recorder.record_take_timing` stores the measurement beside the take. No project,
take, mixer, source-identity or export contract reads it, and a take without it behaves exactly as
takes always have. Two consistent sets are kept and never mixed:

| set | meaning |
|---|---|
| `scheduled_*_offset_sec` | the scheduling clock alone |
| `*_offset_sec` | the same plus the measured output and input latency |

Mixing them silently adds that latency to any difference — which is how a 2.000 s count-in first
measured as 2.052 s in the harness. An uploaded or fallback take **clears** the timing rather than
inheriting the last live take's, and discarding a take discards its measurement.

## Measured

Scheduling clock and captured file only. **No acoustic-latency claim.**

### Component harness — `scripts/_accept_issue78b_recorder.py`, 64/64, green on consecutive runs

| measurement | result |
|---|---|
| three monitors, count-in None | **0.0000 ms** start spread |
| scheduling lead into the future | **250 ms**, nothing at the clock's present value |
| claimed musical zero vs the instant they really started | within **one sample** |
| count-in 1 bar @ 120 bpm | musical zero **2.0000 s** after the first click |
| count-in 2 bars @ 90 bpm | **5.3333 s**; both bars accented on beat one |
| count-in in 3/4 | three clicks, 1.5 s |
| Align +0.5 / 0 / −0.5 | +500.000 ms / 0.0 ms / 0.0 ms with a 0.5 s buffer offset |
| capture rate | **48 000 Hz** |
| capture safeguards | echo cancellation, noise suppression and AGC all reported off |
| a 6 s take | 6.18 s of audio, every frame from capture start to Stop present |
| a monitor that 404s | Record refused, nothing left armed, plain explanation shown |

### Real-app acceptance - `scripts/_accept_issue78b_app.py`, 52/52

The whole workflow inside Streamlit, on "Let It Be" at 100 bpm (so one bar of count-in is 2.4 s -
an earlier gate hardcoded 120 bpm and failed the recorder for being right):

| measurement | result |
|---|---|
| guitar, then a saxophone overdub, then a flute overdub | one Record click each |
| what each overdub heard | the saxophone 1 saved layer, the flute 2 |
| monitor start alignment in the app | **0.0000 ms** spread, **2650 ms** future lead |
| musical zero after the first click | **2400.00 ms**, and one bar at this tempo is 2400.00 ms |
| Count-in None / 1 bar / 2 bars | 0 / 4 / 8 clicks; musical zero at 0 / 2400.00 / 4800.00 ms |
| what the take shows the player | "captured at 48.0 kHz; 2.4 s count-in; bar 1 beat 1 lands 2.701 s into the recording; 2 part(s) playing along" |
| discard one take | slot empties in 4.5 s, its measurement goes with it, the other two layers untouched, re-recording carries a fresh measurement |
| save, reload | 3 of 3 layers saved; all 3 still hold audio after a full page reload |
| mix and export | 2.43 s, peak 0.95, 44 100 Hz |
| 390 px and 360 px | Record button unclipped, no horizontal page scroll |
| page errors | none |

**A trap worth recording.** `MUSIC_APP_DATA_DIR` is read only by debug-dump code
(`backing_context`, `backing_key_cycle`); it is **not** the app's persistence root. The app writes
its state into the worktree's gitignored `data/`. An acceptance run therefore started with the
previous run's three takes already in place, which silently invalidated its monitor counts. The
launcher now clears only the ignored files under its own worktree's `data/` and refuses to run in
the main checkout, and the first gate asserts the slot is empty before counting anything.

### Deterministic tests — `tests/test_issue78b_live_recorder.py`, 58 tests

Which layers are monitored (the recording slot never plays back against itself; Mute removes a
layer; Solo narrows), the Align payload matching the contract's own answer for every sign, count-in
beats per meter, the ready text, the timing record and its disposal, the generated filename's safety
as a storage path, and the component's own ordering guarantees.

## Not verified

* **Physical microphone, real instrument and listening acceptance — PENDING.** Every number above
  comes from Chromium's fake capture device. Nothing here establishes how a real flute or saxophone
  take sounds, or what the true acoustic latency of any particular interface is.
* **In-app backing monitoring** is exercised only as a monitor asset; generating a backing first was
  not part of the app run.
* Cloud / cross-device behaviour of the stored timing.

## Cost noted honestly

Each monitored layer is fingerprinted by hashing its bytes on every rerun, so the recorder can never
be armed with a stale URL after a re-record. For ordinary takes this is a few milliseconds; for a
very long take it is proportionally more. A cheaper key (take nonce, length) was considered and
rejected: recording twice without discarding does not bump the nonce, so it would have let the
recorder monitor the previous take's audio.
