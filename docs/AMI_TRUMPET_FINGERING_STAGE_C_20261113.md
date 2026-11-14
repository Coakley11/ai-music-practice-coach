# Yamaha YTR-2330 fingering pilot — local Stage C

This milestone follows verified Stage B remote integration
`68ed8964f6e64444ef4ef23ffcbb4c44cdb5eadc`. It is local-only and requires
separate approval before any push, merge or deployment.

## Source and model boundary

Standard factory Yamaha YTR-2330, three-piston Bb trumpet only. Model
identification is explicit and conversation-scoped; an Alto Saxophone sidebar
is unchanged by a trumpet request. Other trumpet keys/models, rotary or
modified instruments, other brass, alternate fingerings, pedals, extreme range
and specialized embouchure methods are outside this milestone.

The model-linked [Yamaha downloads page](https://usa.yamaha.com/products/musical_instruments/winds/trumpets/bb_trumpets/ytr-2330/downloads.html)
provides the [owner manual](https://usa.yamaha.com/files/download/other_assets/8/326908/trumpet_en_om_b0.pdf),
VDE1660 / POCP-B0, 03/2022, printed fingering chart p.14. Retrieved PDF SHA256:
`a791635c53276d10b83f4861cbad13542c9d61744e7f724dbd9b9c91d8382e92`.
[Yamaha's harmonic-series charts](https://www.yamaha.com/en/musical_instrument_guide/trumpet/mechanism/mechanism002.html)
independently locate the targets for open, valve 1 and valve 2.
[UNSW brass acoustics, Joe Wolfe](https://newt.phys.unsw.edu.au/jw/brassacoustics.html)
corroborates transposition, the open C4/G4 second/third harmonics and the
fundamental convention. Manual p.14 and all three charts were visually inspected.
The permanent oracle is a separate source transcription, not derived from
`trumpet_technique.HARMONICS` or from generated exercises.

## Nine verified written targets

| Valve setting | Partial 2 → concert | Partial 3 → concert | Partial 4 → concert |
| --- | --- | --- | --- |
| Open, all released | C4 → Bb3 | G4 → F4 | C5 → Bb4 |
| 1 pressed, 2/3 released | Bb3 → Ab3 | F4 → Eb4 | Bb4 → Ab4 |
| 2 pressed, 1/3 released | B3 → A3 | F#4 → E4 | B4 → A4 |

Partial 1 denotes the nominal theoretical fundamental/pedal reference, not an
enabled normal note. The first ordinary played slot in this pilot is partial 2.
Nominal fundamental written MIDIs are 48/46/47; partial targets sit 12/19/24
semitones above them. Ratios 2:3:4 imply a 3:2 fifth then a 4:3 fourth, returning
to a 2:1 octave between partials 2 and 4. Equal-tempered staff targets approximate
those resonances; no exact intonation or measured acoustic claim is made.

All nine targets fit the existing Beginner trumpet range. Status is
manufacturer/reference-supported, **not teacher-reviewed or physically tested**.
The same valves select a tube length with multiple resonances; valve state alone
does not identify or produce one pitch. Guidance stays conservative: comfortable
tone, lip vibration/airflow coordinated with resonance, notated breath rests,
no forcing or excessive pressure. No specialized embouchure prescription.

## Runtime behavior

Original three-piston P/R diagrams come directly from validated records and
show partial and ordinary-slot numbers, written/sounding labels, accessible
titles/descriptions, focusable figures and source links. Real ABC staff notation
uses the existing writer/verifier; no raster reference chart is shipped.
Saxophone controls retain their separate representation and renderer path.

Unnumbered C/Bb/B show explicitly labelled supported octaves. High C is not
silently assigned C5; C6 is unsupported. Instrument-key phrases such as
"Bb trumpet" are removed before note parsing. "Without changing valves" does
not imply open: F4/Bb4 uses valve 1. Mixed-setting lookups can be read-only;
a fixed-valve handoff requires one verified series.

Read-only lookup changes only conversation lookup context, preserving the
current practice plan and exact version history. Explicit instrument/model
lookups select the matching lookup owner; ordinary instrument requests retain
their engines. Owner stamps use the existing account/workspace purge mechanism.

Exercise handoffs reuse `trumpet_technique.build`, its actual fixed-valve
harmonic pitches, slur groups, rests, notation and shared version history.
The model adapter validates the selected partials before build/commit. C4-G4
can add C5, then refuses an unverified next partial. A C4/C5 handoff discloses
and includes the adjacent G4 partial. Slower, easier, repetition, read-only
per-note valves/explanation and exact Undo/Redo use the canonical stored plan.
The broad existing trumpet engine remains available outside this model pilot.

## Validation

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112`.
Source review: `trumpet-fingering-source-review-20261113/`.
Python: `D:/AMIWorktrees/ami-python3128/venv/Scripts/python.exe`, exactly 3.12.8.

Acceptance passed on frozen application source:

- Focused owner/notation preflight: **422 passed, 10 subtests**, 78.72 seconds.
- Complete real-app browser: **33 requests, 21 desktop/390-pixel visual scenarios**, exit 0. Every one of the nine written notes was checked against independent native staff position/accidental and valve/partial fixtures, at both widths. All open notes were also compared with the same valves and different partials. Keyboard focus, source links, readable fonts, inner score scrolling and no horizontal page overflow passed.
- Browser conversation covered model clarification, explicit model, ambiguous C, open harmonic slice, handoff, C4-G4 start, adding C5, refusal beyond partial 4, slower, repeat, easier, read-only per-note valves/explanation, exact Undo/Redo, unsupported combination/note/model, valve 1/2 handoffs, preserved saxophone G5 lookup and ordinary trumpet owner.
- Full 73-file regression, Python **3.12.8**: **3,278 passed**, six unchanged known failures, **2,743 passing subtests**, 13 warnings, 462.67 seconds. All **3,221 shared IDs unchanged**, all **63 new IDs passed**, no missing IDs, collection errors or frozen-source hash changes. Exact terminal failure ledger and executable match the integrated Stage B baseline.
- Known failures remain the two backing-context cases, backing-handoff refresh, canonical insight metric, song-card guidance HTML and TAB-missions rendering cases. None was introduced or reclassified by this work; exact IDs are preserved in the acceptance JSON.
- Browser launcher hard-blocked paid Anthropic access; no forbidden-call evidence was produced. No billing change or deployment. Heavy browser/test jobs ran sequentially, resource monitoring retained other agents' processes and all worktrees/evidence.

Evidence folders: `trumpet-fingering-browser-accepted/`, `trumpet-fingering-regression.{json,log}`, `trumpet-fingering-comparison.json`, `trumpet-fingering-source-freeze-final.json` (97 hashed files). Earlier failed preflight/browser runs are retained. The first browser stalled on a consecutive identical submission; distinct wording exercised the boundary successfully. Another browser harness lacked the sax G5 position at the final owner check; its expected-position table was corrected without application changes. The complete accepted browser run passed afterward.

Review artifacts: [mobile valve 2 / F-sharp4](fingering-stage-c/mobile-Fsharp4.png), [desktop written C4 staff and valves](fingering-stage-c/desktop-C4-staff-diagram.png), [machine-readable acceptance](fingering-stage-c/acceptance.json).
The matching Stage C baseline is the just-validated Stage B integration candidate
`3e574dfc19558e924910a8c41632dfe23c8bf193`; integrated dev differs only by its
acceptance receipt. All 72 prior test files are retained, plus the Stage C file.
No baseline failure is accepted as a new Stage C regression.

## Next milestone recommendation

A separate model-verified standard Boehm clarinet pilot, for example Yamaha
YCL-255, should begin with a small independently checked fingering set and one
register-key/twelfth pair. Validate register-break transitions and actual staff
before enabling exercise handoffs. Flute octave/flexibility comes separately;
advanced sax altissimo/overtones/alternates still require source/model validation
and suitable expert review. None are implemented here.

Original diagram examples: [C4](fingering-stage-c/C4.svg), [G4](fingering-stage-c/G4.svg), [C5](fingering-stage-c/C5.svg), [valve 1 Bb3](fingering-stage-c/Bb3.svg), [valve 2 F-sharp4](fingering-stage-c/Fsharp4.svg).
