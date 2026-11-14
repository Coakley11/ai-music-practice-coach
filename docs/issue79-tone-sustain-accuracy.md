# Issue 79 — Tone Sustain Practice measures the playing, not the silence around it

Branch `feature/issue-79-tone-sustain-accuracy`, off `origin/dev` `f6450c48`.
**Not integrated. Integration needs separate review and approval.**

---

## What was wrong

Three defects, all in `tuner_tone.analyze_tone_practice`, which did its own frame handling inline.

**1. Volume consistency was measured over the whole recording, silence included.**

```python
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]   # the WHOLE clip
vol_score = max(0.0, min(100.0, 100.0 - (vol_std / vol_mean) * 120))
```

A second of silence at each end of a steady note is a third of the frames at zero amplitude, so
`vol_std / vol_mean` was dominated by the parts where the musician was not playing. Measured:
the same steady E5 scored **95.5%** trimmed and **4.1%** with silence around it.

**2. Pitch stability saturated at zero, and included the attack and release.**

```python
pitch_std = float(np.std(cents_series))          # every voiced frame, onset and release included
pitch_score = max(0.0, min(100.0, 100.0 - pitch_std * 4.5))
```

`100 - 4.5 × spread` reaches zero at a spread of 22 cents. Measured: irregular wandering **0.0%**,
a semitone change **0.0%**, an octave jump **0.0%** — three different musical events, one number,
no way to tell them apart. Worse, `cents_series` was measured against the *target*, so a note held
perfectly steady but 30 cents flat contributed 30 cents of "movement".

**3. The target octave was assumed.**

```python
DEFAULT_TONE_PRACTICE_OCTAVE = 4
def pitch_class_option_to_token(option, *, octave=DEFAULT_TONE_PRACTICE_OCTAVE):
    return f"{pitch_class_from_option(option)}{int(octave)}"
```

The selector offered pitch classes (C, C♯, D…) and octave 4 was stapled on. A flute's E5 was
therefore compared with E4. Measured on a synthesized E5 held 31 cents flat: the old analysis
reported **+1170 cents** while the readout said the detected note was **E5** — the user's reported
+1169. Nothing on screen mentioned an octave.

A fourth problem turned up while reproducing the first three: because the clip was peak-normalised
before anything was measured, **a tone 54 dB down scored 100% / 95.5%**. An inaudible recording was
reported as a flawless long tone.

## What was built

A new module, `tone_sustain_analysis.py` (no Streamlit, pure numpy, deterministic), measures four
separate things and says when it cannot measure them. `tuner_tone.analyze_tone_practice` is now a
thin adapter over it and keeps every field its callers already read.

### The sustained portion — where silence leaves the measurement

A frame is **usable** when pyin calls it voiced, pyin's own confidence is ≥ 0.5, its frequency is
finite, and it is within 25 dB of the loudest frame of the recording. The **held note** is the
longest run of usable frames, bridging gaps shorter than 80 ms (pitch-tracker dropouts) and joining
runs on either side of a longer gap when the pitch matches within 50 cents and the gap is under
1.2 s — a note whose sound failed for a moment is one note with a hole in it, and measuring it as
two clean halves is how a dropout disappears from the score.

The **attack and release are trimmed**: 150 ms from each end, or 12% of the run, whichever is
smaller, and nothing is trimmed if that would leave less than the minimum. Below **0.6 s** or
8 frames of held sound, nothing is scored at all.

### Pitch stability

Measured **around the note's own centre**, never against the target, so tuning cannot change it:

```
dev_i   = 1200 × log2(f_i / f_median)          cents, per usable sustained frame
spread  = trimmed_std(dev)                     most extreme 2% each side dropped, rescaled to σ
score   = interpolate(spread, PITCH_STABILITY_ANCHORS)   in log space
```

| spread | 0¢ | 3¢ | 6¢ | 12¢ | 25¢ | 50¢ | 100¢ | 200¢ | 400¢ | 1200¢ | 2400¢ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| score | 100 | 98 | 95 | 88 | 75 | 58 | 38 | 22 | 12 | 4 | 1 |

Interpolation is in log space because the musical meaning of a measurement is multiplicative: 6→12
cents matters as much as 600→1200. The curve **never reaches 0** — 0 is reserved for "not measured"
— and a semitone of movement (38) stays 34 points clear of an octave (4).

The spread estimator is a **trimmed standard deviation**, not the median absolute deviation. The
MAD was the first attempt and it has a trap: the MAD of 200 identical frames and one wild one is
exactly zero, so it needs a fallback for the case where more than half the frames agree exactly —
and that fallback (the plain standard deviation) let the one wild frame report **351 cents** of
movement from a note that never moved. Trimming has neither problem: a stray frame is trimmed away,
while a fifth of the note an octave off is far too much to trim and shows up in full (526 cents).

Reported alongside, so the score is never the only evidence: `pitch_spread_cents`,
`max_deviation_cents`, `pitch_drift_cents` (the least-squares trend across the sustain),
`pitch_centre_drift_cents` (the drift of a 400 ms moving median — what drifts *under* a vibrato),
`largest_step_cents` (the biggest change between consecutive 250 ms blocks),
`note_change_detected`, `vibrato_rate_hz`, `vibrato_depth_cents`, `detection_octave_frames`.

**Vibrato is identified, not removed.** It is real pitch movement and the requirement is that the
measurement preserve it, so it lowers the score — but the explanation names it, gives its rate and
depth, and quotes how far the *centre* of the vibrato moved, which is the musically meaningful
steadiness for a note played with vibrato. Depth read through a 93 ms analysis window is attenuated
relative to the true excursion; that is a property of the measurement chain and is stated rather
than corrected.

**False octave jumps are repaired, real ones are not.** A displaced run shorter than 250 ms is the
tracker, and is folded back only when folding lands it within half a semitone of the centre; a
longer displaced run is the musician, and is left exactly as it is.

### Volume consistency

```
db_i        = 20 × log10(rms_i / max_rms)      over the sustained window, dropouts included
trend_db    = total change of the least-squares line across the sustain
residual    = db − that line
fluctuation = std(residual)
score       = interpolate(fluctuation, VOLUME_CONSISTENCY_ANCHORS)
```

| fluctuation | 0 dB | 0.5 | 1 | 2 | 3 | 5 | 8 | 12 | 20 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| score | 100 | 97 | 92 | 82 | 72 | 55 | 35 | 18 | 5 | 1 |

Removing the trend first is what separates **shape from fault**: a deliberate crescendo or
decrescendo is reported as `volume_trend_db` and described in words, and barely moves the score
(a 9 dB crescendo scores 98.2). A dropout lands in the residual and pulls the score down (40.3 for
a 0.4 s dropout). The deepest excursion below the trend is reported as `volume_dip_db`.

This one is a **plain** standard deviation, deliberately. A robust estimator ignores a small
minority of frames by design, and a dropout *is* a small minority of frames — a note that fell
silent for 0.4 s out of 2.7 scored 99.9% for evenness until this changed. Unlike pitch, loudness
has no tracker artefacts to protect against: every frame is sound the musician really made.

Loudness itself is never scored: the curve is normalised by the recording's own peak, so the same
tone at a quarter of the amplitude scores the same.

### Tuning, and the octave stated as an octave

The target is now explicit. `resolve_target("E4")` is a note; `resolve_target("E")` is a
**pitch-class contract** — any octave of that note counts. The panel offers **Target note** and
**Target octave** (Any octave · 2 · 3 · 4 · 5 · 6) and prints which contract is in force.

```
raw_offset_cents  = (detected_midi − target_midi) × 100
octaves           = round(raw_offset_cents / 1200)
tuning_offset_cents = raw_offset_cents − octaves × 1200
octave_offset_semitones = octaves × 12
```

So the user's case reads **−30 cents, one octave above the reference E4** instead of +1170 cents,
and a pitch-class target reports the offset from whichever octave was played. `raw_offset_cents` is
kept as well, so nothing is hidden.

The default octave contract is **Any octave**, not 4. Until this selector existed no musician could
choose an octave and the analysis simply assumed one; a stored 4 records the app's assumption, not
a decision, and acting on it is the defect. A player who wants octave-specific practice says so,
and `practice_tone_octave_mode` remembers it.

Written-pitch and concert-pitch ownership is unchanged: a transposing instrument's written pitch
class still maps to its concert pitch through `resolve_tone_note_context`, and for a pitch-class
target the mapping is done through a reference octave which is then dropped (a bare letter name has
no transposition). A detected note matching the target's pitch class is spelled the way the player
chose it, so a tenor saxophonist asking for Bb3 is told Bb3, not A♯3.

### "Not enough reliable pitch detected" instead of 0%

Both scores are `float | None`. When the recording cannot be measured the result carries
`status="insufficient"`, no scores, and a reason in a musician's words:

* *The recording is too quiet to measure* — peak below −45 dBFS;
* *Not enough reliable pitch detected — no sustained note was found* — no usable frames;
* *Not enough steady sound to measure — hold one note for at least 0.6 seconds*.

The panel shows that warning, says what it did see (length, held sound, peak level), and states
that nothing was scored. Nothing stores a 0.

## What the numbers do now

Measured on synthesized signals whose pitch and loudness are known exactly
(`scripts/_issue79_signal_evidence.py`, fixtures in `tests/tone_test_signals.py`):

| signal | before: pitch / vol | after: pitch / vol | after also reports |
|---|---|---|---|
| steady E5, trimmed | 100.0 / 95.5 | 100.0 / 99.9 | spread 0.0¢ |
| **the same E5 with 1 s silence each side** | 92.2 / **4.1** | 100.0 / **99.9** | the silence is outside the sustain |
| even A4 with silence around it | 94.5 / **14.4** | 100.0 / **99.9** | fluctuation 0.0 dB |
| **E5 31¢ flat, reference E4** | 100.0 / 95.5, offset **+1170¢** | 100.0 / 99.9, offset **−30¢** | **1 octave above E4** |
| steady but 30¢ sharp | 100.0 / 95.6 | 100.0 / 99.9 | tuning +30¢, stability untouched |
| 20¢ drift | 68.1 | 93.0 | spread 7.4¢, drift +20¢ |
| 60¢ drift | **19.8** | 81.6 | spread 17.2¢, drift +60¢ |
| regular 5 Hz vibrato ±35¢ | **21.2** | 79.9 | vibrato 4.9 Hz / 25¢, named as intentional |
| irregular wandering ±45¢ | **0.0** | 67.6 | spread 33.9¢, step 70¢ |
| semitone change | **0.0** | 55.0 | step 90¢, "two notes rather than one" |
| octave jump | **0.0** | 8.2 | step 1200¢, "about an octave" |
| 9 dB crescendo | 100.0 / 66.4 | 100.0 / 98.2 | trend +7.9 dB, described as a shape |
| 9 dB decrescendo | 100.0 / 66.6 | 100.0 / 98.2 | trend −7.9 dB |
| 0.4 s dropout mid-note | 96.1 / 60.4 | 100.0 / **40.3** | fluctuation 7.1 dB; pitch unaffected |
| **a tone 54 dB down** | **100.0 / 95.5** | *not measured* | "too quiet to measure" |
| breath noise only | no result | *not measured* | "no sustained note was found" |
| 0.35 s of tone | no result | *not measured* | "hold one note for at least 0.6 s" |
| flute D5 | 100.0 | 100.0 | detected **D5** |
| tenor sax concert Bb3 | 96.1 | 100.0 | detected **Bb3**, spelled as chosen |
| bass-range E2 | 76.8 | 95.3 | detected **E2** |

## Tone History

Nothing stored is rewritten, recalculated or deleted.

* Every new row carries `scoring_version` (`tone-sustain-2026-11-v2`). A row without one was
  measured by the previous algorithm and the history labels it *"Legacy measurement: scored by the
  earlier tone analysis, before pitch stability, tuning and octave were measured separately. Kept
  exactly as it was recorded — it is not directly comparable with newer takes."*
* Recalculating old rows was considered and rejected: the audio may no longer be present, the old
  numbers are what the musician saw at the time, and silently reinterpreting them under a new
  formula would change their practice history without telling them.
* `tone_take_quality` has a fourth answer, `"unmeasured"`. It used to read `float(None or 0)` as 0
  and file an unmeasurable recording as badly played.
* Takes also store the separated measurements: `tuning_offset_cents`, `raw_offset_cents`,
  `octave_offset_semitones`, `pitch_spread_cents`, `volume_fluctuation_db`, `volume_trend_db`,
  `detection_confidence`, `analysis_status`, `analysis_reason`.
* Original recordings, notes, instrument settings, targets and timestamps are untouched.

## Verified

| | |
|---|---|
| Deterministic signal tests | **91** (`tests/test_issue79_tone_sustain.py`) |
| Real-app acceptance | **47/47** (`scripts/_accept_issue79_app.py`) |
| Tone History preservation | **PRESERVED** - two pre-Issue-79 rows, every field byte-identical, stored scores intact (including a stored 0.0), both labelled legacy, AMI sees the same numbers |
| Matched regression vs `f6450c48`, 311 shared files | **5428 test IDs both sides, 0 disappeared, 0 new, 0 outcome changes, 0 regressions** (80 failures + 1 error identical on both, pre-existing) |

The real-app run feeds Chromium a WAV as the microphone
(`--use-file-for-fake-audio-capture`), so `st.audio_input` records a tone whose pitch is known to
the cent. On the user's own case - E5 held 31 cents flat - the panel reports **E5**, **-30 cents**,
**1 octave above the reference E4**, pitch stability **100%** either way, and the octave difference
is explained in words. Changing **Target octave** between 5, 4 and Any octave re-reads the same
recording and the tuning figure stays at -30 cents throughout. The take saves, appears in Tone
History with its measurement, is not labelled legacy, and is still there after a full page reload.
Both target selectors are unclipped with no horizontal scroll at 390 px and 360 px, and there were
no uncaught JS errors.

### Two defects the browser run found that the unit tests had missed

* `media_state.migrate_tone_take` returns an explicit **whitelist** of fields and discards the rest,
  so `scoring_version` and every separated measurement were dropped the moment a row was
  normalised - and a take saved by this build came back labelled *"Legacy measurement"* in the
  musician's own history. The new fields are now on the whitelist, and five tests pin it.
* `row.get("a") or row.get("b")` discards a stored **0.0**, because zero is falsy. A legacy take
  genuinely scored 0% therefore came back as *"not measured"* - a different claim about someone's
  practice, made silently. **Pre-existing on `origin/dev`**, fixed here because requirement 6 is
  precisely about not reinterpreting old scores.

## Not verified

* **Physical microphone, real flute or saxophone, and listening acceptance — PENDING.** Every
  number here comes from synthesized audio or from a WAV file fed to Chromium as a fake capture
  device. Nothing here establishes how a real instrument in a real room measures.
* No Android browser was available; the 390 px and 360 px checks are Chromium viewport emulation.
* Cloud/cross-device behaviour of the new stored fields.
