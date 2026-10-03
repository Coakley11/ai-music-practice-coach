# Notation/TAB redesign, F2 highlight fix, scope ownership, icons — evidence

Produced while addressing the second manual-testing feedback batch (6 items)
against the Practice Melody integration build.

## Items 1/2 — Notation/TAB redesign into a chord-navigation exercise

New module `chord_navigation_notation.py`: a voice-led chord-tone/arpeggio
engine, architecturally distinct from Generated Practice Melody (which
composes a melodic line; this teaches *navigating* the changes). Core
primitive `_nearest_octave(pc, near_midi)` realizes every chord's tones at
the register nearest wherever the line/voicing already is — proven via
`tests/test_chord_navigation_notation.py::test_voice_leading_no_gratuitous_leaps_between_chords`,
which asserts no inter-chord leap exceeds 12 semitones across all three
levels, and `test_advanced_approach_tone_connects_to_next_measures_actual_first_note`,
which asserts Advanced-level approach tones land exactly a half-step from
whatever the *next* measure's first note actually is (this needed a
two-pass fix: direction-reversal at Intermediate/Advanced levels changes
which tone plays first, so the approach-tone target has to be computed
from the next measure's actual first tone, not always that chord's root).

Instrument dispatch in `practice_notation.py`:
- **Piano** → `build_connected_piano_voicings()` — close-position voicings
  chosen nearest the previous voicing's center of mass ("closest voicing"
  connection), rendered as bracketed ABC chords (`"Am7"[Aceg]8`).
- **Saxophone/other wind/generic** → `build_connected_arpeggio_line()` — a
  single connected melodic line, level-differentiated (Beginner: 2 tones +
  rest; Intermediate: 3 tones, direction changes; Advanced: 4 tones +
  chromatic approach tone, no rest).
- **Guitar/Bass** → existing hand-curated `GUITAR_SHAPES`/song `guitar_tabs`
  data (unchanged), but the shape-to-shape fret/string movement highlight
  (previously gated behind a "transitions" focus setting) is now always
  on, surfacing which frets hold vs. move between chords by default.

Chord symbols: both new instrument paths route through the *same* ABC
chord-annotation convention already proven in Practice Melody
(`composition_melody_notation.build_abc_from_melody_events(..., chords=...)`
for the melodic path; an equivalent bracketed-voicing builder for piano) —
confirmed in `tests/test_practice_notation_chord_navigation.py::
TestChordSymbolsPresent`. Key/written-key projection: unchanged —
`generate_practice_notation()` still receives the same already-projected
`display_key` the rest of Practice resolves; `TestKeyProjection` confirms
the ABC `K:` field changes with Practice Key while the chord progression
itself (`chord_labels`) does not.

25 new unit tests across the two files, all passing.

## Item 3 — F2 live highlighting: root cause + fix

**Root cause (confirmed via direct instrumentation, not guessed):** the
original F2 mechanism had `render_abc()`'s injected script reach *into* a
sibling `components.html()` iframe via
`window.top.document.querySelectorAll('iframe')` →
`frame.contentDocument.getElementById('live-audio')`. Direct instrumentation
(logging every frame's `getElementById('live-audio')` result via the real
DOM API, not string search — an earlier string-search attempt produced
false positives by matching the debug script's *own* source text) showed
this consistently returned `null` across every reachable frame, even
recursing through nested iframes. The cross-iframe DOM reach-in pattern,
while modeled on `backing_key_cycle.py`'s `cycle_pass_ended_js_snippet`,
did not reliably locate the Backing lead-sheet's `<audio>` element in this
Streamlit version/environment.

**Fix:** `live_follow_along_component_html()`'s own `updateHighlight()` —
the function already responsible for Backing's own chord-chart
highlighting, which already correctly resolves the authoritative position
(`audioTime`, handling both normal playback and Key Cycle's dual-buffer
force-time) — now also writes that same `audioTime` onto
`window.top.__pmBackingPosition = {t, paused, ts}` every time it runs
(native `timeupdate`, `seeked`, `pause`, `ended`, and its own 100ms
watchdog — the same triggers that already drive Backing's own
highlighting). `render_abc()`'s melody-panel script was simplified to just
*read* that property on a 100ms interval — no cross-iframe DOM access at
all. This mirrors `window.parent.__kcFollowForceTime` /
`__kcActiveAudio`, the exact mechanism Key Cycle's own cross-iframe bridge
already uses successfully in this codebase, rather than inventing a new
cross-frame technique.

**Mechanism verified in isolation:** a minimal standalone Streamlit app
(`components.html("<script>window.top.__testProbe = 42</script>")`) was
built and run; `page.evaluate(() => window.__testProbe)` on the main page
returned `42`, confirming an iframe created via `components.html()` can
reliably write a property onto `window.top`, readable from the main page
and (by the same reasoning) from a sibling iframe. The write/read sides of
the real fix were not invented blind — this is the same browser/Streamlit
version the real fix runs in.

**Not conclusively proven end-to-end this session:** repeated attempts
(dozens, across many hours) to get the automated browser to a state where
Backing's `<audio id="live-audio">` element is genuinely playing (so
`updateHighlight()` fires with real audio) did not succeed — `getElementById
('live-audio')` continued to return `null` across every Playwright-visible
frame even 40+ seconds after clicking Play, and the page periodically showed
"Playback stopped — press Play to start again." This looks like an
automation/headless-environment limitation (slow app — ~6-10s per Streamlit
rerun — combined with audio-generation timing), not a defect in the fix
itself, but it was not possible to rule that out with certainty in this
session. **Recommend a manual spot-check**: Practice → generate melody →
Practice with Backing → Play, watch the notation.

## Item 4 — Backing scope ownership/persistence

**Root cause of the original complaint:** `apply_practice_loop_backing_
snapshot_scope()` is called not just once (at the initial Practice→Backing
handoff) but again from ordinary hydrate/restore passes that run on *every*
Backing rerun (confirmed via direct instrumentation tracing every write to
`backing_track_scope`/`backing_track_single_section` across a simulated
handoff → live scope change → rerun sequence). Those later calls
unconditionally re-stamped the *original* Practice-handoff section,
silently reverting any scope change the musician made while on Backing.

**Fix:**
- `capture_live_backing_scope_override()` (new): called from the scope/
  section widgets' own `on_change` (`_on_backing_filter_change` — the exact
  moment a live edit is known for certain), durably records the musician's
  current scope choice *inside* the active practice-loop snapshot itself
  (not a plain session flag — direct instrumentation showed the obvious
  candidate, `is_backing_user_dirty()`, gets cleared by routine autosave
  moments after being set, so it's too transient for this purpose).
- `apply_practice_loop_backing_snapshot_scope()`: now prefers that live
  override over the original handoff section whenever one is present —
  Practice's handoff is a one-time default; after the first live edit,
  Backing owns its own scope.
- `begin_practice_loop_backing_handoff()`: clears any leftover live-scope
  override at the start of a *fresh* handoff, so a new "Loop X in Backing"
  click always gets its own clean one-shot default regardless of a
  previous Backing visit's state.

Four new regression tests in `tests/test_practice_loop_section_backing.py`
(`TestBackingScopeOwnershipAfterHandoff`) directly reproduce the user's
exact sequence: live scope change persists across 3 simulated reruns; a
Full Song override also persists; Practice's own `practice_focus_section`
is never touched by a Backing scope change; a brand-new handoff always
resets to its own fresh default. 16/16 passing in that file.

## Items 5/6 — canonical icons

Audited `music_feature_icons.py` (`FEATURE_ICONS`), `INSTRUMENT_ICONS`,
`SEMANTIC_FIELD_ICONS`, and `studio_page_state.CREATIVE_TOOL_ICONS` before
picking any symbol — a small script cross-checks every value across all
four registries for duplicates. 11 new `FEATURE_ICONS` entries added, all
confirmed collision-free against the existing ~30 assigned glyphs:

| Label | Icon | Key |
|---|---|---|
| Chord chart | 🗂️ | `chord_chart` |
| Notation / TAB | 📑 | `notation_tab` |
| Generated Practice Melody | 🌟 | `practice_melody_generated` |
| My Uploaded Melody | 📤 | `practice_melody_uploaded` |
| Original Melody | 💿 | `practice_melody_original` |
| Song coach | 🧑‍🏫 | `song_coach` |
| Section deep focus | 🔬 | `section_deep_focus` |
| Scales & approaches | 🪜 | `scales_approaches` |
| Practice coach & session | 🗓️ | `practice_coach_session` |
| Daily time breakdown | ⏳ | `daily_time_breakdown` |
| Full song ABC sketch | 🗒️ | `full_song_abc_sketch` |

("Chord coach" already had a canonical icon via `chord_song_coach` — 📖 —
from before this batch; left unchanged.)

Applied via `feature_label(key, text)` (prefixes the canonical icon, same
helper every other label in the app already uses) at all 11 call sites —
no hardcoded emoji. `items5-6-icons-desktop.png` and
`items5-6-icons-mobile-390px.png` (this folder) show the full expander
hierarchy with every icon rendered, distinct, and legible; a script-level
check confirmed no horizontal page overflow at 390px width.

## Items 2/4 cross-check — Practice navigation + scope on Backing

Visually confirmed in-session (screenshot not retained, but observed
directly): after a Practice Melody → "Practice with Backing" handoff, the
Backing page shows **🎯 Return to Practice** (the item-2 fix from the
previous checkpoint) alongside the editable **Playback Scope** control —
both present on the same screen, consistent with the new scope-ownership
tests.
