# AMI Bass Guitar TAB — Slice 2

Parent / final Bass Slice 1 integration: `d258b3b27418e8d9d325789e4fcee07e8d4fda57`.
Local-only branch: `feature/ami-bass-tab-20261112`.

## Integration receipt

Fetched dev at `95af04d4eb49160cf7a7b1313723cba263d81b2f`, preserved its newer
chart/fingering work, and merged approved Bass Slice 1 commit `751231ae` without
conflicts. Matched Python 3.12.8 checks: candidate 2288 passed, five existing
failures, 2379 passing subtests; all 2212 shared IDs unchanged. This included the
newer Ipanema and song-coach tests. All 22 real-app bass browser cases passed in
one completed run, including the final Blue Bossa chart. Verified normal dev
push at `54461933d125f6958e4e4eeea03f96eb27dee259`.

The expanded TAB audit then exposed 22 legacy bass-line routing regressions
missed by that initial suite: a song bass-line role was incorrectly treated as
a bass-guitar exercise override. Correction `54e1ea73` restores the established
Song Coach route while preserving explicit bass-guitar exercises and chart
drills. Four permanent instrument-boundary tests were added. Newly fetched dev
Original Key commits through `a185b996` were preserved in final integration
`d258b3b27418e8d9d325789e4fcee07e8d4fda57`. Matched checks against that current
dev baseline found no new failures: candidate 304 passed, four existing
failures, 275 passing subtests. All 22 final real-app bass scenarios passed,
including Blue Bossa. A driver race was corrected by waiting for the actual
notation iframe before inspecting it; the earlier failed run is preserved.
Normal push and remote dev SHA were verified at `d258b3b2`. No deployment.

## One passage, two views

The same `Built.notes` sent to the existing staff writer are projected through
`warmup_engine.to_events`. Each stored TAB event retains exact rational onset
and duration, bar/beat, rest status, tempo-derived seconds, chord label,
articulation, written/sounding MIDI and the engine's already validated string
and fret. Rests occupy events; repeated pitches remain separate attacks.

TAB is stored in each row's `meta.bass_tab`, with the exact ABC binding. It
travels through normal AMI response diagnostics, stored insight payloads and
warmup navigation. Display does not choose another fingering or reconstruct
music from a fret-number list. Undo/Redo restore the complete stored version.

The existing ABCJS 6.4.4 component still renders the standard staff. A bass-only
SVG companion puts numbers at its actual note coordinates and duplicates its
actual barline coordinates. Four lines are ordered G, D, A, E, top to bottom.
The score is rendered once, not transcribed into a second independently
created musical score. Normal notation markup for other instruments is retained.

Per-system SVG viewports keep each staff/TAB pair together. Viewports crop to
their own real content to avoid cumulative-coordinate whitespace. Long titles
wrap as normal text. Runtime and browser checks reject overlapping systems,
count/duration/rest mismatches, stale ABC bindings, polyphonic voices and ties.
A failure leaves the original staff available with a TAB-unavailable message.

## Rhythm and example

Supported bass events remain in the existing 4/4 warmup model: whole, half,
quarter, eighth and sixteenth notes, the same rest values, repeats, barlines,
sustains within a measure, tempo and actual split-measure chord changes.
Values printed below TAB are fractions of a whole note. Standard notation
remains authoritative for articulation marks; TAB tooltips retain those marks.

An E natural-minor scale uses these identical events in both views:

| Bar, beat | Written staff pitch | Sounding pitch | TAB string/fret | Value |
|---|---|---|---|---|
| 1, 1 | E2 | E1 | E / 0 | quarter |
| 1, 2 | F#2 | F#1 | E / 2 | quarter |
| 1, 3 | G2 | G1 | E / 3 | quarter |
| 1, 4 | A2 | A1 | A / 0 | quarter |
| 2, 1 | B2 | B1 | A / 2 | quarter |
| 2, 2 | C3 | C2 | A / 3 | quarter |
| 2, 3 | D3 | D2 | D / 0 | quarter |
| 2, 4 | E3 | E2 | D / 2 | quarter |

This is conventional written bass pitch, one octave above sounding. The TAB
maps sounding E1 to E-string fret 0 and sounding E2 to D-string fret 2; no extra
octave shift is applied to the rendered staff.

## Fingering and conversation

The existing bass path solver remains authoritative. Defaults are unchanged.
Selected valid fingerings are retained when pitches and constraints still fit;
a rhythm-only change does not select a new alternative just because one exists.
String/position requests add constraints to that same solver rather than
introducing a separate TAB fretboard model.

- `Show me the TAB` is read-only and returns the stored passage.
- `Play this on a different string` changes at least one note's string when a
  complete valid alternative exists. Notes with only one usable string remain.
- `On the E string` / `on string 4` constrains the passage to that string.
- `In position 5` means a hand window beginning at fret 5, with the level's
  declared width. It does not prescribe finger numbers or a universal hand shape.
- Fresh coordination cells can be generated inside that requested window or on
  the requested string, while retaining the named key's pitches.
- `Use more string crossings` seeks a feasible path with more crossings; if no
  improvement exists, the previous version is retained.
- `Use the open strings` prefers usable open strings without changing pitches.
  `Only open strings` is a hard constraint and can be refused.
- `Make the rhythm faster` advances a standalone drill's supported note value
  while preserving pitches and selected fingering. Beginner speed limits remain.
- Existing harder/lower/descending/tempo revisions update the same passage and
  both views. Fingering-only revisions preserve standard notation pitches.

A multi-item warmup requires selecting an item before a targeted fingering
revision. Full-warmup/chart requests with explicit string/position constraints
must still satisfy them; unavailable variants are refused or reported by the
existing allocator. Chart rhythm is not rescaled independently of its harmony.

| Proficiency | Frets | Hand window width | Maximum shift per attack |
|---|---|---|---|
| Beginner | 0–5 | 3 frets | 1 fret |
| Intermediate | 0–7 | 4 frets | 3 frets |
| Advanced | 0–12 | 4 frets | 5 frets |

These are conservative exercise policies, not ergonomic guarantees. All notes
also stay within the existing level register and tempo limits. If a requested
string cannot play a pitch, no octave substitution or dropped note is used.

## Mobile and playback boundaries

At narrow widths the paired score keeps a readable minimum width and scrolls
horizontally inside its own container. The page is not widened by the TAB.
Charts reflow to shorter staff systems. Warmup navigation keeps the selected
staff and its TAB together. Mobile acceptance uses a 390×844 touch viewport.
Catalog selection for the mobile chart test uses the existing desktop picker
helper at a wider viewport, then returns to the phone viewport for TAB checks;
this does not claim to repair the unrelated mobile catalog-picker workflow.

The current AMI card is a notation renderer; it exposes no reliable exercise
transport/playhead callback. No new timer, audio transport or simulated cursor
is introduced. A future cursor should subscribe to the actual playback event
clock and use these same event IDs, not start an independent interval timer.

## Explicit limits

Standard four-string fretted E–A–D–G only, and the existing 0–12 fret envelope.
No five/six-string, alternate tuning, capo, fretless, upright bass, slap,
harmonics, tapping, ghost-note or extended-technique notation is added.

The current canonical bass event model has no tie field, and its writer rejects
notes crossing a barline. Ties are explicitly refused, not inferred from equal
pitches or faked as repeated attacks. Unsupported tuplets, swing, other meters,
polyphony and arbitrary articulation are not expanded in this slice.

Legacy stored versions without canonical timing remain exact snapshots. A TAB
request for one asks for a fresh exercise instead of inventing timing or
rewriting that version. Account/workspace state continues through the existing
AMI owner-scoped plan/history machinery; there is no extra global TAB state.

## Sources and validation

Primary references:

- [StudyBass: reading bass TAB](https://www.studybass.com/lessons/reading-music/how-to-read-bass-tab/)
- [Ariane Cap: bass octave convention](https://arisbassblog.com/bass-is-a-transposing-instrument/)
- [ABCJS tablature interface](https://docs.abcjs.net/visual/tablature)
- [ABCJS render options](https://docs.abcjs.net/visual/render-abc-options.html)

ABCJS's automatic TAB fingering is not used, because AMI's selected positions
must remain authoritative. The app's pinned library was not upgraded.

Permanent checks: `tests/bass_tab_oracle.py` independently tokenizes actual ABC
onsets, values, rests, pitches and bars, then combines that with the independent
frequency/fret oracle. `tests/test_ami_bass_tab.py` includes mutations, note values,
open-E/D-string-E examples, level constraints, selected positions, exact history,
legacy state, selected warmup navigation and Satin Doll split-measure harmony.

Real-app driver: `scripts/verify_ami_flexible_browser.py --bass-tab-only`, with
`--mobile` for the phone viewport. It inspects actual SVG fret text, string
ordering, rests, rhythmic positions, native staff pitches, barline coordinates,
contained scrolling and non-overlapping staff/TAB/system geometry. Visual QA
caught and corrected a multi-system overlap that numeric timing checks alone
had missed. All artifact logs and screenshots are preserved outside Git under
`D:/AMIWorktrees/flexible-evidence-20261112`.

Final Python 3.12.8 comparison against exact corrected parent `d258b3b2`:

- Parent: 2456 passed, six failed, 2654 passing subtests, eight deselected.
- TAB candidate: 2487 passed, the same six failed, 2654 passing subtests,
  eight deselected. All 31 new TAB tests passed.
- All 2462 shared test IDs have identical outcomes, no baseline IDs disappeared,
  and terminal failure/subtest ledgers match exactly. No collection errors.
- The six baseline failures are two custom-progression Backing context tests,
  Backing refresh ownership, canonical insight metrics, Song Card guidance,
  and the Missions render stub lacking `st.empty`. They are not TAB regressions.
- The eight expensive unchanged arpeggio/approach oracle matrix cases were
  deselected in both final runs; this is not a claim of a full repository run.
- Earlier final focused coverage: 755 passed; subsequent full comparison also
  verifies the final refusal-response change and restored legacy routing.

Desktop acceptance: 15/15, including revisions, exact Undo/Redo, explicit string
and position, open strings, warmups and Blue Bossa. Mobile acceptance: 6/6 at
390?844, including selected-warmup navigation and Satin Doll split-bar harmony;
one additional polish probe verifies readable frets and last-event scroll
reachability. These completed before the final metadata-only refusal patch
and base advancement; the final mobile probe separately verifies that patch.

Final mobile refusal/display probe: 3/3 passed on the final corrected base.
Actual staff/TAB SVGs remain present after refusing ties and after read-only
Show TAB; plan and history are unchanged. No failure or paid-API marker.

Logs: `bass-tab-corrected-parent`, `bass-tab-corrected-final`,
`bass-tab-corrected-comparison.json`, `bass-tab-desktop-final`,
`bass-tab-mobile-verified`, `bass-tab-mobile-polish`,
`bass-tab-final-refusal-browser`. Earlier failed attempts remain preserved.
Paid Anthropic transport is blocked by the local launcher; no billing changes
or deployment. Heavy checks ran sequentially. System monitoring found about
1.3 GiB available RAM and 141/99 GiB free on C:/D: during final validation.
Only the test launcher's own process trees are closed.

The TAB feature remains a local commit on `feature/ami-bass-tab-20261112`.
No TAB push or merge into dev is authorized or performed. The explicit-file
checkpoint stash `d5ad2f127bea66de5a024254cb5c9e30e2ebc24a` is preserved,
as are unrelated worktrees and the four pre-existing runtime trace files.

## Recommended next instrument milestone

Saxophone articulation and interval technique: bounded tongued/slurred rhythmic
cells using the verified written ranges and existing history/notation checks.
For bass, a playback-linked cursor is a separate follow-up after a reliable
transport event interface is available. Neither requires another unverified
pitch or fingering model.
