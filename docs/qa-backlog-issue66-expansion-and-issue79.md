# QA backlog: Issue 66 expansion, and new Issue 79 — Tone Sustain measurement accuracy

Added 2026-11-13 from mobile screenshots. **Nothing here is implemented.** Each item was
checked against `origin/dev` `083698a2` before being written down, and the status recorded.
Kept isolated from the Issue 78 Multitrack work.

---

## Issue 66 expansion — consistent action icons

The central helpers already exist and should be the only source of these glyphs:
`music_feature_icons.ACTION_ICONS` with `action_label()`, plus `page_feature_icon()` for
page identities. Current `ACTION_ICONS`:

| key | icon | | key | icon |
|---|---|---|---|---|
| `accept` | ✔️ | | `idea` | 💡 |
| `add` / `new` | ➕ | | `load` | 📂 |
| `analyze` | 🎯 | | `play` / `preview` | ▶️ |
| `apply_text` | 📝 | | `reset` | ↩️ |
| `continue` | → | | `save` | 💾 |
| `create_mix` | 🎛️ | | `upload` | ⬆️ |
| `delete` | 🗑️ | | `easier` | 🌱 |
| `download` | ⬇️ | | `harder` | 🧠 |
| `edit` | ✏️ | | `generate` | 🪄 |
| `feel` | ✨ | | | |

### 66.1 Close buttons — OUTSTANDING, and needs a new key

There is **no `close` key in `ACTION_ICONS`**, so this cannot be done by reuse alone; the
key has to be added centrally first, then applied. Confirmed plain-label instance:
`practice_tools_ui.py:256` renders `st_module.button("Close", …)` for the Metronome /
Tuner & Tone panel. Keep the text label.

### 66.2 Save Tone Take — OUTSTANDING

`tone_take_history_ui.py:69` renders `st_module.button("Save Tone Take", …)` with no
icon and no `action_label`. Should use the `save` key (💾), matching Save Lyrics & Cues,
Save Layer and Save to This Song. Note `tests/test_tone_take_save_flow.py:198` asserts
the literal string `"Save Tone Take"`, so that assertion needs updating with the label.

### 66.3 Missions — Optional Example Idea — OUTSTANDING (labels differ from the report)

The screenshot's wording and the code's wording are not the same, so the work must start
from the code. Found in `improvisation_intelligence_ui.py`:

- `:2615` `st.button("Harder motif", …)` — lower-case "motif", not "Harder Example"
- `:2631` `st.button("Easier motif", …)`

`improvisation_missions.py:910-911` describes "New Idea", "Easier Example" and "Harder
Example" as drawing from one idea-index sequence, so those labels exist somewhere in the
Missions surface and need locating by rendering the page rather than by grep. Intended
mapping: Generate Example → `generate` 🪄, Easier → `easier` 🌱, Harder → `harder` 🧠,
New Idea → `idea` 💡.

### 66.4 Creative Lab — Motif and Phrase Development — OUTSTANDING

These bypass `action_label` entirely and carry **hand-written arrow glyphs inside the
label**, which is a competing convention of exactly the kind to remove:

- `improvisation_intelligence_ui.py:2682` `"Sequence Up ↑"`
- `:2684` `"Reverse Order ⇄"`
- `:2685`, `:2911`, `:3358`, `:6172` `"Change Rhythm"`
- `:3363` `"Sequence Up ↑"`, `"Sequence Down ↓"`, `"Reverse Order ⇄"`
- `:6153` `"Sequence Up ↑"`, `:6165` `"Reverse Order ⇄"`

Preserve each handler key (`improv_xform_up`, `improv_span_seq_up`,
`improv_mission_invert`, …) — the keys carry the behaviour.

### 66.5 Multitrack — Send to Upload Analysis — OUTSTANDING, and the report is right

`multitrack_export_ui.py:210` uses `action_label("analyze", "Send to Upload Analysis")`,
and `ACTION_ICONS["analyze"]` is **🎯** — the target/practice glyph in the screenshot.
The Upload Analysis page's own identity is different:

```
page_feature_icon("analysis")   == 🎙️
page_feature_icon("multitrack") == 🎚️
```

So the established Upload Analysis symbol is **🎙️** and it already exists; nothing new
needs inventing. The open design question to settle first: `analyze` is a generic *action*
key used elsewhere, so either a new key (e.g. `send_to_analysis`) points at the page icon,
or `analyze` is repointed and every other `analyze` call site reviewed.
`tests/test_action_icons_61.py:123` pins `("analyze", "Send to Upload Analysis")` and
`:132` asserts the label text, so both need updating together. The handoff behaviour must
keep working — `tests/test_multitrack_export_identity_handoff.py:276` covers the entry
point.

### 66.6 App-wide audit — OUTSTANDING

Raw `st.button("…")` calls that bypass `action_label`, by file: `composition_studio_page.py`
84, `cpl_page_ui.py` 19, `streamlit_music_practice_app.py` 12,
`improvisation_intelligence_ui.py` 11, `suite_auth.py` 9, `practice_log_ui.py` 9. Not all
need icons, but that is the surface to audit. Labels stay visible; verify 390 px and 360 px.

---

## Issue 79 — Tone Sustain Practice measurement accuracy

**Next free number is 79** (existing issues run to 78).

The reported reading was: Pitch Stability 0%, Volume Consistency 0%, Sustain 3.5 s,
Detected Center E5, Mean Offset +1169 cents, clip 7.7 s, flute, described as "Stable flute
Middle E".

### Preliminary root cause — measured, not inferred

I reproduced the reading with deterministic synthesised tones through the real
`analyze_tone_practice` (`tuner_tone.py:231`). A steady E5 with 2.0 s and 2.2 s of silence
either side, total 7.7 s:

```
steady E5, 2.0s+3.5s+2.2s silence   target=E4  -> pitch 96.4%  vol 0.0%  sustain 3.6s
                                                  centre E5  mean +1200.1c  clip 7.7s
steady E5, NO surrounding silence   target=E4  -> pitch 100.0% vol 83.9%  sustain 3.5s
```

**1. Volume Consistency 0% is a confirmed defect, and it is reproduced exactly.** The RMS
series is computed over the **whole clip including silence**:

```python
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]   # all of y
vol_score = max(0.0, min(100.0, 100.0 - (vol_std / vol_mean) * 120))
```

The voiced `mask` is never applied to it. The score hits 0 once the coefficient of
variation reaches 0.833, which ~4 s of silence in a 7.7 s clip guarantees. Removing the
silence takes the same perfectly steady note from **0% to 83.9%**. So this metric currently
measures *how much silence the clip contains*, not how evenly the note was held — exactly
the distinction the report asks for.

**2. Pitch Stability 0% is a confirmed mechanism, though not reproduced by silence alone.**
A steady tone scored 96.4% with long silence and 100% with none — but with only 0.3 s of
silence either side it collapsed to **2.7%, reporting 268 cents of drift on a dead-steady
tone**. Unvoiced and ramp-edge frames leak into the series as outliers. A real flute take
has breath onset, decay and room noise, which is the same condition. Compounding it, the
mapping

```python
pitch_score = max(0.0, min(100.0, 100.0 - pitch_std * 4.5))
```

saturates at 0 once the standard deviation passes ~22 cents, so these all score 0% and
are indistinguishable:

```
gradual 60c drift over the note  -> pitch  0.0%
sudden semitone jump mid-note    -> pitch  0.0%
sudden OCTAVE jump mid-note      -> pitch  0.0%
very quiet but steady note       -> pitch  6.3%
```

**3. The +1169 cents is an octave-selection artifact, and it did NOT cause the 0%.** This
corrects one hypothesis in the report. The target selector offers a **pitch class only**,
and the analysis target is hard-pinned to octave 4:

```
media_tone_catalog.py:91   DEFAULT_TONE_PRACTICE_OCTAVE = 4
pitch class "E" -> token "E4" -> MIDI 64;   E5 is MIDI 76;   difference = 1200 cents
```

So selecting "E" meant E4 while the flute sounded E5. The reported +1169 is 1200 − 31,
i.e. **the note was about 31 cents flat of E5 — essentially in tune**. And because
`pitch_std` is the standard deviation of a constant-offset series, it is offset-invariant:
measured 96.4% with target E4 and 96.4% with target E5. **The octave mismatch changes only
the reported offset, never the stability score.** There is no separate tuning-accuracy
metric; `mean_cents` is printed raw at `tuner_tone_ui.py:465` with no interpretation of
"an octave out" versus "slightly flat".

**4. Pure silence is already refused** (`analyze_tone_practice` returns `None` when fewer
than 5 voiced frames are found, and the UI shows a warning) — so the "insufficient data"
path exists but its threshold is far too low: anything above 5 frames yields a confident
0% instead.

### Proposed correction, for approval before any audio-analysis change

1. Compute amplitude consistency over the **sustained/voiced region only**, not the whole
   clip; report it over the same window the Sustain figure already uses.
2. Reject or trim outlier pitch frames (confidence gate plus an octave-jump guard) so
   edge frames cannot pass as instability, and report `max_cents_drift` from the cleaned
   series.
3. Replace the saturating linear map with one that still discriminates above ~22 cents of
   deviation, so a 60-cent drift and an octave jump do not read identically.
4. Split the two ideas the report asks to separate: **Pitch Stability** (steadiness,
   offset-invariant — already correct in principle) and **Tuning Accuracy** (closeness to
   target, where an octave difference is reported as an octave, not as 1169 cents).
5. Let the musician choose the target octave, or infer it from the detected centre and say
   which was used; octave 4 for every instrument is wrong for flute long tones.
6. Show an explicit unavailable / insufficient-data state instead of 0% when the usable
   frame count or signal confidence is too low.
7. Add a one-line explanation beside each metric, and make the written feedback cite the
   measurement that produced it.

### Acceptance to run (none of it done yet)

Deterministic synthesised signals first — constant pitch, gradual drift, vibrato, sudden
jumps, octave changes, very quiet notes, breath noise, silence, wrong target, insufficient
data — asserting that the graph, the number and the words agree. Then flute, alto and
tenor saxophone, trumpet, clarinet, piano and guitar where supported, respecting written
versus concert pitch and instrument range. Then real recordings, Android mobile browser if
available. Check Save Tone Take preserves recording, target, measurements, instrument,
timestamp and notes in Tone History without overwriting earlier takes, and treat the
musician's own note ("Stable flute Middle E") as commentary, never as evidence the
analysis was right.

**Standing limitation:** no real-instrument audio was used for the diagnosis above — every
number here comes from synthesised tones. Real flute recordings and listening acceptance
remain pending.
