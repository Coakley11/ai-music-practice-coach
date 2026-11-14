# Trumpet Fingering Stage C integration receipt

Approved feature: `6e144670a6a96904f09192558689498bc81f9d2d`.
Fresh current-dev baseline: `4301efe191a67f813ae922c916b2368bd785dc52`.
Clean merge candidate: `1ba9c5df6e5db15c34f500d7e94f1d31232dc616`.
Isolated branch: `integration/ami-trumpet-fingering-c-20261114`.

The normal merge completed without conflicts and preserves all newer dev
commits. The approved AMI source, source-backed trumpet records, permanent
fixture/tests and browser harness are unchanged. Newer composition, song-card
and main application code remain identical to current dev. No newer work was
replaced by the older feature branch.

Python is exactly 3.12.8 at
`D:/AMIWorktrees/ami-python3128/venv/Scripts/python.exe`. Heavy gates run
sequentially. The baseline manifest retains all 72 prior files and adds all 23
new/changed dev test modules, for 95 files. The candidate adds the permanent
63-case trumpet module, for 96 files.

Fresh clean baseline: **3,510 passed, nine failed, 3,116 passing subtests**,
13 warnings, 831.50 seconds. The actual current failure ledger is:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_composition_activation_nav.py::TestNavButtonKeys::test_jam_sets_entry_mode`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_armed_renders_exactly_one_synced_score`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_unarmed_renders_exactly_one_static_score`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`

These are measured on clean current dev, rather than assuming the prior six
failures. The candidate comparison requires identical shared phase outcomes,
no missing IDs, all added cases passing, no collection errors, the same Python
and an exact match of terminal FAILED/SUBFAILED/ERROR entries.

Candidate regression: **3,573 passed, the same nine failures, 3,116 passing subtests**, 13 warnings, 953.51 seconds. All **3,519 shared IDs retain identical phase outcomes**; all **63 new IDs pass**; no missing IDs or collection errors. The exact terminal failure ledger and Python executable match the fresh clean baseline.

Desktop/mobile browser acceptance **passed, exit 0: 33 real-app requests and 21 visual scenarios**. All nine source-backed records, native staff positions/accidentals, valve states and partial labels passed at desktop and 390 pixels. Model and octave clarification, open-series slice, canonical handoffs/revisions, bounded partial refusal, read-only explanations, exact Undo/Redo and preserved saxophone/ordinary trumpet owners passed. Permanent tests also verify account/workspace isolation. No forbidden Anthropic call was recorded. The browser started after memory recovered to about 2.4 GB; completed servers/contexts were closed by their owning harness. All newer dev files were checked against current dev and remain unchanged.

Both conditional gates passed. Current dev was fetched again and remained at the validated baseline. A normal ancestry-checked push is authorized; no force push or deployment.

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112`:
`trumpet-c-current-baseline.{json,log}`,
`trumpet-c-integrated-regression.{json,log}`,
`trumpet-c-integrated-comparison.json`, `trumpet-c-integrated-browser/`.

This integration retains the bounded Yamaha YTR-2330 pilot: nine notes across
open/valve 1/valve 2, partials 2-4, separate written/sounding pitches, original
valve/partial diagrams, read-only lookups/explanations, model/register
clarification, canonical lip-slur handoffs and exact shared Undo/Redo, plus
account/workspace isolation and existing saxophone/ordinary exercise owners.
Theoretical partial 1, other valves/types, alternate fingerings and specialized
techniques remain unsupported. Source-supported does not mean teacher-reviewed
or physically tested. No force push, deployment, paid Anthropic call or billing
change is permitted.
