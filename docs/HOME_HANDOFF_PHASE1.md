# Home handoff validation — Phase 1

Base: origin/dev ea12085d. Preserved Claude first-run commit 7edf982e unchanged.
Isolated branch: codex/home-handoff-phase1-20261104.

The notice removal changes no initialization, hydration or restoration calls.
Home's activity entry hook returns before recording any activity. Home render modules
only read Practice Log history; saving a log requires the Log page's explicit save.

Validation:
- Home suites: 106 passed, 107 subtests passed.
- Added behavioral tests: 3 passed (quiet default initialization, returning song/key,
  Home emits no activity).
- Real Streamlit/Chromium: isolated data directory and guest workspace land on Home,
  seed Say by John Mayer, omit the first-run notice, and preserve Home on refresh.
- Broader existing restore/source suite: 71 passed, 10 failed. Running the same tests
  with origin/dev songs/state.py loaded produces the identical ten failures.
  These are baseline failures, not fixed in this narrowly scoped slice.
- Available RAM approximately 1 GB / 16.9 GB; CPU 36%; disk free 205 GB.
  Test and browser workloads were sequential. Only this task's server is managed.

Browser evidence: evidence/home-handoff/before-desktop.png and before-mobile.png.
Mobile screenshot initially includes the open sidebar; later visual verification
must close it and wait for rerun completion before capturing the design.

No push, merge or deployment performed.
