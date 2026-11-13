# Conditional advanced jazz integration receipt

The approved advanced-jazz candidate is 8b75a6ec33c3110c26012a2773dc71346b4017ae.
It merged cleanly onto fetched dev 083698a21ada1dcdb6a4dddca5e335ae66b29723,
preserving newer Issue 78A transport work. No force push or deployment is used.

## Score investigation and scoped correction

The earlier horizontally clipped panel screenshot was not proof of missing
native notes. A fresh actual-card probe at 1440 px found page scrollWidth 1440,
iframe width 948 and score width about 932. At 390 px, page scrollWidth remained
390 and the iframe was 334 px wide, but responsive scaling squeezed the entire
1315.8-unit score into about 318 px. Chord labels measured approximately 4 px
high. This is a genuine mobile readability defect even without page overflow.

The correction retains ABCJS 6.4.4 and its native engraving and responsive SVG.
Ordinary Music Coach score papers use at least 720 px and their actual native
SVG viewBox width; each sits inside a locally scrollable labelled keyboard-focus
region. A short navigation hint explains the arrow keys. Bass TAB keeps its
existing renderer, staff/TAB geometry and 420 px minimum; its wrapper gains the
same keyboard access. Other app panels and exercise generation are unchanged.
Long plans retain existing iframe vertical scrolling rather than hiding later
scores. No competing notation renderer was introduced.

Before evidence: D:/AMIWorktrees/flexible-evidence-20261112/jazz-layout-before,
including desktop/mobile geometry, score and viewport images. The independent
native-note functional checks are separate from visual readability acceptance.

## Acceptance gates

The clean same-current-dev baseline lives in jazz-current-baseline-20261113 at
083698a2. Heavy jobs run sequentially under Python 3.12.8. The shared manifest
includes the existing AMI/notation/owner suites and newer transport alignment
checks. Exact per-test outcomes and terminal FAILED/SUBFAILED/ERROR ledgers are
compared; elapsed times and unrelated failures are not silently normalized away.

The completed release gates are recorded below.


## Completed visual acceptance

jazz-layout-accepted completed with LAYOUT_EXIT=0: six real-app requests, each
checked at desktop 1440 px and narrow 390 px (12 geometry/screenshot scenarios).
Coverage: soprano sixteenth anticipation, a long eight-item jazz warmup, flute,
clarinet, trumpet and bass staff/TAB. Every page scrollWidth equals its viewport.
Ordinary score text is at least 10 px; soprano chord labels are 17 px. All glyph
bounds fit the local content area, all vertical content fits its region, keyboard
ArrowRight moves the region, and scrolling reaches its exact horizontal end.
Long-plan iframe scrolling reaches later scores. Screenshots of the corrected
soprano start/end and long-plan end were inspected visually.

The first attempted wrapper exposed ABCJS's percentage-padding containing-block
contract; that failed run is retained as jazz-layout-after. A separate full-width
inner holder fixes its vertical aspect ratio. Native SVG title overhang is
measured and accommodated with bounded padding without changing engraved notes,
chords or musical timing. jazz-layout-final exposed the title overhang. The next
run, jazz-layout-release, passed all ordinary scores but applied an inappropriate
10 px chord-label threshold to existing TAB duration fractions. The accepted
harness uses TAB's own staff/fret separation and success contract instead; the
TAB renderer and geometry code are byte-for-byte unchanged. No failed attempt is
counted as a completed release pass.

Before/after evidence is retained under D:/AMIWorktrees/flexible-evidence-20261112.
Functional native-note checks remain separate from this visual acceptance.

## Completed matched regression

Clean current dev: 2,869 passed, six known failed, 2,743 passing subtests.
Final integrated application source: 2,985 passed, six known failed, 2,743 passing
subtests across 68 files. All 2,875 shared IDs are unchanged; all 116 additions
pass. No collection errors or deselections; Python 3.12.8 is identical. The
terminal FAILED/SUBFAILED/ERROR ledger matches exactly. Account/workspace
isolation and existing notation lifecycle suites are included.

Exact unchanged failure IDs:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`

Evidence: jazz-latestdev-baseline.{json,log}, jazz-integrated-regression.{json,log}
and jazz-integrated-comparison.json in the existing D: evidence directory.


## Final integrated browser acceptance

jazz-integrated-browser completed with JAZZ_BROWSER_EXIT=0, 26/26 requests.
All four real charts, four saxophones, harmonic permutations/extensions,
chromatic targets, anticipations, intervals, rhythm, slurs/accents, selected-row
isolation, read-only Explain and exact Undo/Redo passed. All before/after sidebar
settings are equal; no paid-transport marker or browser failure exists. The
owned server and browser exited through runner cleanup. The new capability
foundation and fingering roadmap remain separate local-only work after this
integration; they are not part of this authorized dev push.
