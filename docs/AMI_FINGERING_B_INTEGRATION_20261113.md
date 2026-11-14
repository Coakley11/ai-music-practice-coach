# Saxophone Fingering Stage B integration receipt

Approved source: d33021404e6db10a6de298ad64221f373bea9545.
Fresh dev baseline: f6450c48604caadcfc6fd31c9b6a5e632ad75452.
Clean merge candidate: 3e574dfc19558e924910a8c41632dfe23c8bf193.
Branch: integration/ami-fingering-b-20261113, isolated D: worktree.

The merge retains all four newer recording/QA commits after Stage A's 18ee27b3:
5e8b7805, 19a552ee, 12764ddf and f6450c48. No conflict or discarded commit.
All Stage B fingering source/data/tests remain identical to the approved commit.

Fresh clean baseline, Python 3.12.8: 3,154 passed, six known failures,
2,743 passing subtests, 13 warnings, 1090.47 seconds. The manifest includes the
original 67 regression files, later jazz/capability/Stage A modules, and the new
81-case Issue 78B recorder file (71 files total). The candidate adds Stage B's
permanent module (72 files total). Both run sequentially with the same executable.

The two deliberate boundary replacements preserve unsupported A6/G6 refusals
instead of newly supported A5/high G. Independent positive tests cover A5/G5;
B5 remains a tested in-range but unregistered-note refusal. The comparison allows
exactly those two renamed parameter IDs, verifies both replacements pass, and
requires all other shared phase outcomes, terminal failures/subtests and Python
to match. No other missing/new failure or collection error is accepted.

Candidate: 3,215 passed, the same six failures, 2,743 passing subtests, 13 warnings, 1329.80 seconds. All 3,158 shared IDs retain identical phase outcomes; 63 added IDs pass (61 Stage B plus the two reviewed replacements). The exact terminal failure ledger and Python executable match; no collection errors. Native browser retry passed: 35 real-app requests and 26 desktop/390-pixel diagram scenarios; staff positions, source-backed control states, all added notes, G/A comparisons, handoffs, revisions, read-only preservation, exact Undo/Redo and ordinary trumpet owner passed. No blocked Anthropic call occurred. The first browser closed under low available RAM; its evidence is retained separately. The successful retry used unchanged application source after RAM recovered.
Evidence root: D:/AMIWorktrees/flexible-evidence-20261112.
- fingering-b-current-baseline.{json,log}
- fingering-b-integrated-regression.{json,log}
- fingering-b-integrated-comparison.json
- fingering-b-integrated-browser/ (incomplete resource-related run)
- fingering-b-integrated-browser-retry/ (complete, exit 0)

The 12 Yamaha YAS-280 standard-keywork records, five true octave pairs, written/
sounding pitches, original data-driven controls, model clarification, read-only
answers, bounded canonical handoffs, owner isolation and exact Undo/Redo retain
manufacturer/reference-supported status, not teacher review or physical testing.
No unsupported saxophone model or specialized technique is enabled.
No force push, deployment, paid Anthropic call or billing change is authorized.
