# Design: retaining dry stems alongside the mixed Multitrack export

Status: **design only.** Nothing here is implemented, no storage migration is proposed, and
no per-instrument grade is invented. The goal is to show that stem persistence can be added
later as an additive slice, without reworking what Issue 62 just built.

## Why it is needed

A saved export is one blended WAV. `export_stem_info()` therefore reports
`has_isolated_stems: False`, and the coaching engine's existing
`_mixed_attribution_confidence()` correctly downgrades every per-instrument claim to
"limited attribution — one mixed ensemble file without isolated stems or source
separation". That is honest, but it is also a ceiling: *no* amount of prompt work can
separate a saxophone's intonation from a guitar sounding at the same time in one mono mix.
Independent per-instrument coaching needs independent audio.

The good news is that the audio already exists. During a session the layers live
individually in `st.session_state["mt_tracks"]` (`slot -> bytes`). The export step mixes
them down and only the mixdown is persisted. Stem persistence is therefore not a new
capture problem — it is a *retention* problem.

## What the engine already accepts

The analyzer is already stem-aware; it does not need a new contract:

- `_mix_has_isolated_stems(ctx)` returns True when `uploaded_track_count >= 2`, or when
  `ctx["has_isolated_stems"]` / `ctx["source_separated"]` is set.
- The Multitrack workflow's Step 2 already offers "2–6 separate stems for layer
  comparison", and `run_multitrack_upload_analysis(tracks, ctx)` already takes a *list* of
  tracks, each `{name, filename, bytes, instrument, ...}` from
  `prepare_multitrack_track_payload(...)`.
- `prune_instrument_focuses_to_project()` and `build_layer_arrangement_context()` already
  key coaching off `ctx["instruments"]` and `ctx["instrument_focuses"]`.

So a stem-carrying export would feed the *existing* multi-track path, with
`uploaded_track_count = len(stems)`. The honest-limits machinery then relaxes itself
automatically, because the premise it tests (one blended file) stops being true.

## Data model

Add one field to the export row, beside the existing `recording_identity`:

```python
"stems": [
  {
    "slot": "Sax / winds",          # canonical slot, ties back to included_tracks
    "instrument": "Alto saxophone (Eb)",   # from layer_recording_keys' sibling map
    "layer_name": "Alto lead",
    "recording_concert_key": "Em",  # per-layer, already captured by note_layer_recorded
    "practice_focuses": ["Tone"],   # editable later; seeded per instrument
    "delay_seconds": 0.0,           # mixer align offset, so stems re-align exactly
    "volume": 1.0,                  # mix contribution, NOT baked into the stem
    "muted": false, "soloed": false,
    "duration_seconds": 142.5,
    "sample_rate": 48000,
    "dry": true,                    # no reverb, no normalisation
    "storage_ref": "…", "local_path": "…",   # same two-tier storage as the mix
    "sha256": "…"                   # integrity, and lets a reload prove it is the same take
  }
]
```

Every field except the audio pointers already exists in session state at export time, so
the builder is a read, not a new capture.

### Per-layer key identity

Already solved by this branch. `MT_LAYER_RECORDING_KEYS_KEY` stamps each slot with the key
it was played in, and `_key_agreement()` flags a project whose layers disagree. Stems make
that *more* useful, not less: a mixed-key project cannot be labelled with one key, but each
**stem** can be labelled with its own correct key, and a per-stem analysis is then valid
even when a whole-mix key statement is not. This is the strongest argument for stems.

### Timing offsets

The mixer's per-layer `delay` is applied at mixdown (`np.concatenate` of zeros, or a head
trim for a negative delay). Stems must be stored **pre-delay** with the delay recorded as
metadata. Storing post-delay audio would bake an editing decision into the archive and make
a later re-align impossible. The analyzer does not need the offsets to grade one instrument,
but it needs them to say anything about ensemble timing.

### Dry stems vs the listening mix

`multitrack_audio_polish.apply_reverb` is applied *only* to the mixdown, and the recorded
layers are never touched — so dry stems are available today at zero cost. The rule to
encode: **stems are always dry and un-normalised; reverb and peak normalisation belong to
the listening mix only.** The mix already peak-normalises to 0.95, which rescales absolute
level; a dynamics assessment should read the stem, not the mix.

### Ownership and security

Reuse `persist_mix_export_audio` / `recording_local_abs_path(workspace_id, rel)` unchanged.
Stems are per-export children under the same `workspace_dir(workspace_id)`, so they inherit
the existing workspace scoping, the two-tier (local path + `storage_ref`) model and the
existing delete path. `delete_mix_export_files(row)` must be extended to remove stem files
with the export, or deleting an export would orphan them. No new credentials, no new bucket,
no production migration.

### Storage size

A 3-minute 16-bit mono WAV at 48 kHz is ~17 MB. Today one export costs ~17 MB; with four
stems it costs ~85 MB — a 5× increase, and it grows with layer count. Mitigations, in the
order worth doing:

1. **Opt-in per export.** A "Keep separate instrument tracks (for per-instrument coaching)"
   checkbox beside the existing reverb checkbox. Default off: nobody pays who does not ask.
2. **FLAC for stems.** Lossless, decodes through the same `librosa.load`, and roughly
   halves the size. Analysis accuracy is unaffected because it is lossless.
3. **Retain on the newest N exports** and drop stems from older ones, keeping the mix.

Without at least (1), stem retention would quietly multiply the user's disk use, which is
not acceptable as a default.

### Backward compatibility

Entirely additive, and the pattern is already proven on this branch:

- `migrate_multitrack_export` returns an explicit dict, so a new `"stems"` key must be
  added there or it is dropped on reload — exactly the trap `recording_identity` hit.
  A legacy row yields `"stems": []`.
- `export_stem_info(row)` becomes: if `row["stems"]` has ≥2 entries, report
  `has_isolated_stems: True`, `uploaded_track_count: len(stems)`; otherwise keep today's
  honest "one blended WAV" answer. Every existing export keeps today's behaviour with no
  migration.
- `multitrack_handoff_ensemble_tracks()` becomes the single place that decides what goes to
  the analyzer: the stem list when stems exist, else the one mixed WAV. The app-side call
  does not change at all.

## Proposed development slice

Small enough to land on its own branch after Issue 62, in this order:

1. **Capture and store** — `build_stem_rows(session_state, track_items)` in a new
   `multitrack_stem_catalog.py`; persist via the existing storage helpers behind the opt-in
   checkbox; teach `migrate_multitrack_export` and `delete_mix_export_files` about stems.
   Pure additive; unit-testable with byte fixtures.
2. **Honest capability flip** — `export_stem_info` reports real stems; verify the engine's
   existing limited-attribution text relaxes only when stems are genuinely present.
3. **Hand off stems** — `multitrack_handoff_ensemble_tracks` returns the stem list, so
   "Send to Upload Analysis" delivers 2–6 tracks into the path Step 2 already supports.
4. **Per-instrument coaching** — only now does per-instrument grading become defensible,
   each stem against its own Practice Focus and its own recorded key.

Slices 1–3 are mechanical. Slice 4 is the one that needs product judgement about what the
coach should say, and it should not start until a stem is actually reaching the analyzer.

## What this design deliberately does not do

- It does not add source separation. Separating a blended legacy mix is a different problem
  with different accuracy claims, and it would not fix any export already saved.
- It does not retroactively create stems for existing exports. They were never kept.
- It does not let a single mixed WAV produce per-instrument grades. That stays refused.
