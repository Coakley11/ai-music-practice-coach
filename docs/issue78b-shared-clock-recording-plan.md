# Slice 78B — Record with Count-In on one clock, and overdubbing

Design only. Nothing in this document is implemented. It is written against
`origin/dev` `b8704315` with Slice 78A applied.

## Why there is nothing new to invent

The Mission recorder already solves the hard half. `mission_recorder.py` with
`mission_recorder_component/index.html` runs microphone capture and backing playback on
**one** `AudioContext`: the mic goes through an `AudioWorkletNode` (`mission-capture`) and
the backing is a buffer source scheduled on that same clock, so the backing's position
inside the take is a frame count rather than an estimate:

```js
const s = c.createBufferSource(); s.buffer = backingBuf; s.connect(c.destination); s.start(t0);
rec.source = s; rec.scheduledFrame = Math.round(t0 * c.sampleRate);
...
const scheduledOffset = (r.scheduledFrame - r.firstFrame) / sr;
backing_offset_sec = scheduledOffset + outLat + inLat;
```

`firstFrame` is the worklet's first captured frame. The difference is exact. The only
estimated part is `outLat + inLat`, and that is labelled as latency rather than folded in
silently.

So 78B is an adaptation, not a second engine. Two things the Mission recorder does not do
and Multitrack needs:

1. **No count-in.** Nothing in the component schedules clicks.
2. **One backing buffer, not N layers.** It schedules a single generated backing. Multitrack
   has to play the backing *and* every previously saved layer while recording the next one.

## What changes, and where

### 1. A count-in inside the recorder's own clock

Add count-in to the component, scheduled from the same `t0` the backing uses:

```
t0           = ctx.currentTime + scheduleLead(ctx)     // same lead rule as Slice 78A
countInBeats = countInBars * beatsPerBar
musicStart   = t0 + countInBeats * beatSec
```

Clicks at `t0 + i*beatSec`; backing and every monitored layer at `musicStart`. Capture
starts when the worklet does, which is before `t0`, so the take contains the count-in.

The take's timing payload gains two fields beside the existing ones:

| field | meaning |
|---|---|
| `count_in_sec` | the count-in's length, so it can be shown and skipped |
| `music_start_frame` | the captured frame that **is** musical bar 1 |

`music_start_frame - firstFrame` is the authoritative frames-to-bar-1 number Phase C item 3
asks for. It is a frame count from one clock, not a difference between two button presses.

### 2. Monitoring N existing layers

The component takes a list of monitor sources instead of one backing URL:

```python
monitors = [
    {"url": ..., "gain": 0.75, "start_delay_sec": 0.0, "buffer_offset_sec": 0.0},  # backing
    {"url": ..., "gain": 1.0,  "start_delay_sec": ..., "buffer_offset_sec": ...},   # guitar
    {"url": ..., "gain": 1.0,  "start_delay_sec": ..., "buffer_offset_sec": ...},   # sax
]
```

Each monitor's two offset numbers come from `multitrack_align_contract.transport_payload`,
the same function Slice 78A gave the transport. One contract, three consumers.

All monitors are decoded **before** `t0` is chosen — the Slice 78A rule, for the same
reason. With capture and playback on one context this is now load-bearing rather than
merely tidy: a late `t0` would misplace the recording too, not just the playback.

### 3. Keeping monitored audio out of the recorded WAV

The worklet reads **only** the `MediaStreamAudioSourceNode`. Monitors connect to
`ctx.destination`; the capture chain is a separate branch that never touches them, so
monitored audio cannot enter the take through the graph. Two further points:

- `echoCancellation: false` is already set by `mission_music_capture`. That is correct for
  instrument capture but it also means the browser will **not** remove speaker bleed.
  Acoustic bleed through a real microphone is a room problem, not a graph problem, so the
  recorder recommends headphones in the panel rather than claiming to prevent it.
- **Live microphone monitoring stays off.** Routing the mic to `destination` would give the
  musician a delayed copy of themselves at the output latency. It is not offered by default;
  if it is ever added it belongs behind an explicit control with the latency stated.

### 4. Feeding the existing Multitrack workflow

The new control replaces the per-slot `st.audio_input` **for the slot being recorded**. What
it returns goes through exactly the path a take goes through today:

```
render_multitrack_recorder(...) -> {take_id, wav, timing}
    -> st.session_state.mt_tracks[slot]           (unchanged)
    -> mt_track_filenames[slot]                   (unchanged)
    -> note_layer_recorded(...)                   (unchanged: stamps the recording key)
    -> mark_take_unsaved(...)                     (unchanged: Save Layer / Discard Take)
    -> timing stored beside the take               (new, additive)
```

No new project format. `multitrack_takes`, `multitrack_recording_identity`,
`multitrack_mixer_state`, `multitrack_session_persistence` and the export path are untouched.
The timing record is additive, so a project saved before 78B simply has no timing for its
layers and keeps behaving exactly as it does now — which is also what keeps previously
recorded 16 kHz and 48 kHz layers working.

Where the timing is stored needs one decision I would rather make with you than guess:
beside the layer in the existing per-slot structures, or in its own keyed record. The
existing structures are already persisted and restored, which argues for the former.

### 5. What the timing is then used for

With `music_start_frame` known, the Align slider stops being the primary repair and becomes
a fine adjustment. The take's default Align can be derived: a take whose bar 1 sits
`n` frames in wants `buffer_offset_sec = n / sr`, which is a **negative** Align in the
Slice 78A contract. That is precisely why 78A had to come first — the contract it
established is what makes a derived offset expressible at all.

I would make that derivation visible rather than automatic at first: show the measured
offset and offer to apply it, so a wrong measurement is correctable rather than invisible.

## What this cannot establish

- A frame count proves the **scheduling** is exact. It does not prove the sound left the
  speaker and reached the microphone at that instant. `outputLatency` and the input
  latency are device estimates. So the claim is "aligned to the frame on one clock, with a
  stated latency estimate", never "sample-accurate end to end".
- A fake capture device cannot establish instrument audio quality or real acoustic
  alignment. Both need a real microphone and listening.
- The permission grant for a `srcdoc` component iframe was measured as working in headless
  Chromium with auto-grant. Whether a real browser re-prompts per render on an opaque
  origin is **not** established and must be checked on the deployed app before acceptance.

## Order of work

1. Count-in inside the component, with `count_in_sec` and `music_start_frame` in the timing.
2. Monitor list in place of the single backing, offsets from the shared contract.
3. Multitrack wiring into the existing take path, timing stored additively.
4. Minimal panel wording per Phase E; the old two-button path clearly marked as the
   fallback with its limitation stated.
5. Phase D integrity harness: three layers, deterministic transients, record / save /
   discard / re-record / export / reopen.
6. Confirm Mission recording still behaves, since the component is shared.

Step 6 is the risk that most wants watching: the component is live for Missions, so every
change to it is a change to a working feature. If a change cannot be made additive, the
honest alternative is a Multitrack-specific entry point in the same file rather than a
forked copy of the worklet.
