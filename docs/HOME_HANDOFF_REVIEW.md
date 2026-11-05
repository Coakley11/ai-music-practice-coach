# Homepage handoff review — November 4, 2026

No push, merge or deployment was performed. All edits are in the isolated
`.worktrees/home-phase1` worktree; the original worktree and Claude's worktrees
were preserved. The ZIP was used as a visual reference, not as instructions.

## 1. Claude handoff

- Fetched origin/dev; its head was `ea12085d`. The Option A integration was already
  present and was not repeated.
- Preserved Claude's first-run fix `7edf982e` and his untracked worktree evidence.
- Phase 1 branch: `codex/home-handoff-phase1-20261104`, validation SHA `074605da`.
- The fix removes only the first-launch recovery notice. Default-song seeding,
  restoration, hydration and other recovery warnings are unchanged.
- Behavioral checks confirm Home emits no practice activity. Practice Log writes
  remain explicit Log-page actions. Browser checks confirmed a fresh guest Home,
  Say by John Mayer in G, no misleading warning, and Home after refresh.

## 2. Artwork and responsive layout

Branch: `codex/home-improvements-20261104`.

- `1ff1e791`: SVG/CSS workflow illustrations and canonical button icons.
- All requested destinations have artwork, including Pop/Jazz discovery and all
  six additional tools. No new runtime bitmap artwork or external image fetches.
- Retained the verified repository MPC emblem, an optimized crop of the same
  identity shown in the prototype, plus purple/yellow/blue illustration colors.
- Corrected CSS scope to a real Streamlit Home container. At 390 px, the card
  measures 366 px, no horizontal overflow occurs, and all 13 card buttons have
  width/height at least 44 px. Art is decorative and labels remain readable.

Matching renderer comparison (baseline `ea12085d` Home renderer versus current,
with shared deterministic empty-history data):

| Width | Before | After |
| --- | --- | --- |
| Desktop, 1440 px | [Before](../evidence/home-handoff/before-comparison-desktop.png) | [After](../evidence/home-handoff/after-comparison-desktop.png) |
| Mobile, 390 px | [Before](../evidence/home-handoff/before-comparison-mobile.png) | [After](../evidence/home-handoff/after-comparison-mobile.png) |

Integrated app evidence: [Desktop](../evidence/home-handoff/after-desktop.png),
[Mobile](../evidence/home-handoff/after-mobile.png).

## 3. Navigation and Catalog filtering

`f5ae38b9` adds explicit Home Catalog browsing requests without switching music
sources. `0f631fa6` corrects current Creative tool selection, repeated
navigation, responsive scope and Recent Practice destination icons. Browser assertions passed for all seven requested actions:

| Action | Observed result |
| --- | --- |
| Pop | Catalog browsing; 50 Pop matches |
| Jazz | Catalog browsing; 25 Jazz matches, replacing the prior Pop request |
| Entire Catalog | Catalog browsing; all 119 matches |
| Missions | Actual Missions instructions for Say, Practice Key G |
| Song-Aware Coaching | Dedicated coaching tab; Build My Coaching Plan workflow |
| Upload Analysis | Recording uploader and Run AI coach analysis controls |
| Key Cycling | Advanced playback controls expanded; audio paused; cycle Off |

See [recorded assertions](../evidence/home-handoff/navigation-results.json).
The browser matrix used the catalog song Say. Tests separately exercise Custom
and Composition preservation through the real navigation helper. Browsing bypasses
source-toggle hydration and stale dropdown reconciliation; explicit result
selection continues through the normal Catalog activation callback.

Home requests clear stale Search/Genres/Favorites-only/exclusions. Favorites
records are retained. Ordinary filtering still composes Search union Genres union
Favorites; Clear Filters still gives an empty discovery list. Existing picker,
additive-filter and persistence lifecycle tests pass.

Two real defects were found during browser checks and fixed: repeated Home-to-
Songs clicks could trip the automatic-rerun guard; and the old Coaching route
could restore Missions instead of opening the current dedicated Coaching tab.
Explicit Home clicks now reset the guard, and tool selections use canonical
Creative selectors. An old pending history destination is discarded on explicit
Home tool navigation. No song/key/backing ownership is changed by these requests.

The matrix's final, post-assertion return-to-Home wait timed out under load. Server
logs confirmed Home finished, and the independent final desktop/mobile Home
capture passed. The reproduction script now uses longer readiness waits and
writes results before its final cleanup navigation.

## 4. Recent Practice and Resume

`70ecbc16` combines saved Practice Log history with version-2 practice-context
activity records. Reads are workspace scoped; navigation, uploads and legacy
unversioned events are excluded. The newest usable historical record supplies
song, recorded artist, instrument and captured keys. Unknown historical keys are
omitted; current song metadata is never borrowed. Practice date takes priority
over later edits; day labels use America/New_York.

Home retains navigation-only "Go to [destination]" wording with a destination
icon. Visiting Home does not apply a resume payload. `apply_music_resume_payload`
can restore a verified source, but older Practice Log entries do not contain a
complete payload and source-specific Custom/Composition artifacts may be missing.
A transactional state-changing Home Resume is therefore not implemented in this
slice; it needs its own source/workspace/failure-path tests.

## 5. Validation and remaining concerns

Final focused suite: **157 passed, 107 subtests passed**. See [test output](../evidence/home-handoff/focused-tests.txt).
After the final destination-icon adjustment, 56 renderer/history tests and 15
subtests also passed, with explicit Practice/Missions icon checks. Python
compilation and git diff whitespace checks passed.

The broader pre-existing restoration/source suite has **10 baseline failures**
(71 passed). Loading origin/dev's `songs/state.py` and running the same tests
produced the identical failures: two in test_pick_key, one in
active_pick_key_reconciliation and seven in cpl_set_active_song. These remain
outside this Home slice. `scripts/verify_home_baseline.py` reproduces that baseline
comparison without editing the production file.

The last Windows resource sample was approximately 0.68 GB available RAM,
39.21 / 41.33 GB committed memory, 100% CPU, and 192 GB free disk. Earlier free
RAM was 1.25 GB and CPU 36–89%. Workloads were kept small and serial. All task
Streamlit servers and headless browsers were closed. Other agents' processes,
worktrees, evidence, Cursor databases and backups were not modified.

Reproduction helpers:
- scripts/verify_home_navigation_browser.py (full app on port 8527)
- scripts/capture_home_artwork.py (integrated desktop/mobile art/touch checks)
- scripts/home_artwork_preview.py and scripts/capture_home_component_comparison.py
  (isolated matching renderer comparison on port 8528)

The final branch contains local review commits only. Integration still requires
the user's approval.
