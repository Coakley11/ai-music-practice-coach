# AMI Bass Guitar Technique — Slice 1

Local development branch: `feature/ami-bass-guitar-20261112`.
Parent and verified remote trumpet integration: `31887219726317cda5a83f2be3095d9a6d4f3ba6`.
No bass push, merge or deployment is authorized in this slice.

## Instrument and independent references

Standard fretted four-string electric bass only: low-to-high sounding E1, A1,
D2, G2 (MIDI 28,33,38,43); strings numbered 4,3,2,1 respectively.
Conventional bass-clef notation is one octave above sounding: written E2
(MIDI 40) sounds E1 (MIDI 28). Key pitch classes do not transpose. The writer
receives written notes once; there is no additional octave clef transformation.
The existing accompaniment profiles and audio engine are unchanged.

Primary educator references checked 2026-11-12:

- [StudyBass: standard tuning](https://www.studybass.com/gear/bass-tuning/bass-guitar-tunings/)
- [Ariane Cap: electric bass octave transposition](https://arisbassblog.com/bass-is-a-transposing-instrument/)
- [StudyBass: octave shapes](https://www.studybass.com/lessons/common-bass-patterns/octaves/)

The common higher octave is two strings higher and two frets higher. This
follows independently from the 5-semitone string spacing: 5+5+2=12.
Tests recover MIDI from open-string frequencies relative to A440, then apply
2^(fret/12), rather than importing the generator's tuning or solver.

## Bounded physical policy

These are conservative exercise policies, not universal ergonomic guarantees.
A real player should slow down, release tension and stop if uncomfortable.
Every pitched note has an absolute sounding pitch and a string/fret assignment.
No notes are silently omitted, moved by octaves or assigned negative frets.
The path solver retains a hand window as state, including during open strings.
Every fretted note must fit that window and each transition must fit the level's
shift limit. This is a sequential single-note model; it does not claim to model
individual finger anatomy, stretches, simultaneous chords or muting mechanics.

| Level | Frets | Written range | Sounding range | Hand window | Maximum shift/attack | Default subdivisions/BPM |
|---|---|---|---|---|---|---|
| Beginner | 0–5 | E2–C4 (40–60) | E1–C3 | 3 frets | 1 fret | quarter, 56; maximum 80 |
| Intermediate | 0–7 | E2–D4 (40–62) | E1–D3 | 4 frets | 3 frets | eighth, 72; maximum 112 |
| Advanced | 0–12 | E2–G4 (40–67) | E1–G3 | 4 frets | 5 frets | sixteenth, 88; maximum 144 |

Beginner explicit subdivisions faster than quarter notes are refused. A full
octave that does not fit (for example Beginner D major) is refused rather than
widening the level window. This 12-fret slice does not claim the complete range
of every commercial bass. Higher positions are a separate milestone.

## Capabilities and examples

- Single major/natural-minor scales, triad and seventh-chord arpeggios, genuine
  octave pairs, four-string coordination cells, advanced arpeggio permutations
  and finger-busters. A single request produces one exercise, not ten minutes.
- Coordination selects two real frets in the requested key on each E/A/D/G
  string, then alternates within that cell before crossing strings.
- Bass-specific timed warmups reuse Adaptive Warmups' allocation, navigation,
  item IDs and history. Sustain work uses controlled releases and silent rests;
  articulation uses plucked-note separation, without wind tonguing/breath claims.
- Practice Focus selects sensible default families. An explicit named bass
  exercise overrides an Alto sidebar without mutating the global selection.
  With no named instrument the actual sidebar remains authoritative.
- Harmony warmups use key-based arpeggios. Explicit song lines use the existing
  authoritative chart snapshot, section selection and harmonic timeline and
  independent chord-tone validation. Missing charts are refused.
- Revisions: harder, lower/higher, fifth start, octave jumps, descending/ascending,
  string crossings, slower/faster, supported note values, BPM and
  repetition counts. Fresh drills support ordinary articulation. Invalid revisions leave stored music/history intact.
  Explain is read-only; Undo/Redo restore exact stored plans.

E natural minor example:

| Written | Sounding | String / fret |
|---|---|---|
| E2 | E1 | E / 0 |
| F#2 | F#1 | E / 2 |
| G2 | G1 | E / 3 |
| A2 | A1 | A / 0 |
| B2 | B1 | A / 2 |
| C3 | C2 | A / 3 |
| D3 | D2 | D / 0 |
| E3 | E2 | D / 2 |

All supported bass rows contain `meta.positions`, including full warmups and
chart lines. Plain numbered instructions refer to each pitched note, excluding
rests, and distinguish string numbers from finger numbers.

## Integration boundaries and limits

Bass owns its bounded fresh prompts before other single-technique routing.
Flute, clarinet, saxophone, trumpet and explicit scale-pattern ownership remain
in their existing paths. Existing M1b conversions of arbitrary scale patterns
to bass are still unsupported: that path has no bass physical validator.
Song-line revisions continue through the existing chart-aware warmup engine;
they retain the authoritative chart. Bass-specific single-pattern revisions
are not advertised as transformations of a chart line.

Existing TAB code assumes six guitar strings. It is not reused as bass TAB.
The slice supplies correct bass staff notation and explicit positions; engraved
four-string TAB is a future feature. The staff card is notation, not a new bass
accompaniment or audio synthesis implementation. Stored sounding MIDI is tested;
no bass audio/accompaniment playback changes are made.

No slap/popping, tapping, harmonics, alternate tunings, capo, five/six-string,
fretless, upright/double bass, swing/triplets or arbitrary advanced techniques.

## Verification

Permanent tests: `tests/test_ami_bass_technique.py`, independent oracle
`tests/bass_oracle.py`. Browser cases: `scripts/ami_bass_browser_cases.py`, driven
by `scripts/verify_ami_flexible_browser.py --bass-only` against the real app.
The ABCJS original renderer runs unchanged; acceptance inspects its actual
parsed pitches, engraved note heads, bass-clef vertical positions and SVG.
No API solver is substituted, and paid Anthropic transport is blocked.

Evidence lives outside git in `D:/AMIWorktrees/flexible-evidence-20261112`.
Trumpet integration baseline: 2041 passed, 5 failed; candidate: 2088 passed,
5 failed; 2045 shared test IDs have unchanged setup/call/teardown outcomes.
Both have 666 passing subtests and 8 unchanged expensive matrix cases deselected
(the prior full matrix evidence is retained). All 22 current-merge trumpet
real-app browser cases passed before the normal, verified dev push.

The five baseline failures concern three Backing custom-context assertions,
canonical AMI insight metadata, and the new song-card HTML guidance assertion.
They are not introduced by trumpet or bass. Final bass results are recorded
below after the completed runs.

## Recommended next milestone

Bass Slice 2: timing-aware four-string TAB tied to the same validated events,
with a broader primary-source-reviewed position vocabulary and specific musical
rhythm studies. Keep alternate tunings, five-string and extended techniques as
separately declared capabilities. Saxophone articulation/interval technique is
an alternative independent milestone after review of this local bass slice.

### Final matched regression

Python 3.12.8, same executable/dependencies and isolated data as the clean
integration baseline. Final bass broad suite: **2168 passed, 5 known baseline
failures, 666 passing subtests, 8 unchanged expensive matrix cases deselected**.
All **2092 shared test IDs** have unchanged setup/call/teardown outcomes.
The retired bass-refusal ID is intentionally replaced by positive bass tests
and a still-unsupported guitar warmup refusal (81 candidate-only IDs total).
The final suite includes **80 bass-specific tests**. Before the browser-discovered
B-flat fix, the surrounding focused suite also passed all 712 tests; the final
broad rerun supersedes that earlier checkpoint.

The browser exposed an unavailable B-flat interval variant. Bass warmup intervals
now use small key-aware register segments, while other warmup scale/arpeggio
variants may use bounded segments when a tonic-to-tonic octave will not fit.
Standalone full-octave requests still refuse an octave outside the level window.
A permanent allocator guard converts exhausted unavailable-variant retries into
a safe refusal rather than a KeyError; a forced-failure test verifies exact
preservation of the previous exercise/history.

Real UI category labels: Saxophone **Scales** means Technique; Bass **Root
Motion** means Harmony. Browser acceptance uses those controls, without adding
parallel focus settings. No bass push, merge or deployment has occurred.

### Real application acceptance

**22 distinct bass browser scenarios passed**, with 19 successful cases in
`bass-browser-verified` and four context cases in `bass-browser-context`
(case 19 overlaps). This includes the exact requested prompts, real B-flat
Technique warmup, explicit override with Alto still selected, all requested
single-exercise revisions, read-only Explain, exact Undo/Redo, refusal stability,
Bass sidebar Root Motion/Harmony and Melody, actual Saxophone Articulation
focus with explicit Bass override, and a catalog-selected Blue Bossa chart line.

All saved plan pitches/frets and ABCJS actual engraved head positions were
independently rechecked together after both runs. The Blue Bossa line passes
the independent chord-tone oracle against its frozen chart snapshot/timeline.
The test server's port was confirmed closed. No forbidden API marker exists.
`bass-browser-acceptance-summary.json` records the per-case evidence.

The context run's PowerShell wrapper reported status 1 from NativeCommandError
on Streamlit bare-mode warnings caused by importing a pytest helper module;
all four PASS records and artifacts were present, with no failure artifact.
The independent complete artifact validation passed with exit 0. The browser
script now reads chart slots directly from warmup_song, avoiding that noisy
pytest-module import; its assertions and authoritative chart source are the same.
These are successful scenario assertions across two runs, not a claim that the
first whole browser invocation finished without a driver selector correction.

Remaining bounds: standard four-string, frets 0-12; conservative position and
speed policies; no engraved TAB or new audio synthesis; full warmups can use
bounded scale/interval segments, while a standalone scale requires its complete
octave. Specialized bass techniques and arbitrary M1b-to-bass conversions are
left for separate reviewed slices.
