# Current-dev AMI navigation/beaming and flute integration - 2026-11-14

## Accepted changes and preserved current dev

Current dev baseline: `59e77f35c88a6b0ab421a84be2f7e8fb8f46d3e7`. Its four newer recorder commits and all nine changed file blobs are preserved exactly. The isolated candidate merges navigation/beaming first at `699ea72dff170627a86dbcea5e0feffe3d431f44`, then Flute Stage E at `3edef0772f31854fdd44400d9146d237008d99f7`. Both merges completed without conflicts. This receipt changes documentation only.

## Matched regression

Python 3.12.8, sequential isolated runs. Clean current dev: **3,824 passed, nine failed, one skipped, 3,116 passing subtests**, 13 warnings in 1,574.28 seconds (101 files). Combined candidate: **3,919 passed, the same nine failed and one skipped, 3,116 passing subtests**, 13 warnings in 1,306.25 seconds (103 files). All **3,834 shared IDs retain their phase outcomes** and all **95 new cases pass** (17 beaming, 78 flute). No missing IDs, collection errors, Python drift or changes to the frozen 2,150 baseline / 2,160 candidate source hashes. Pytest exits 1 for the existing failures; the strict comparator exits 0.

The same recorder browser test is skipped on both checkouts because its default bundled Chromium is unavailable. The real-app browser acceptance below uses installed Chrome. This skip is reported rather than treated as a pass.

The exact baseline failures remain:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_composition_activation_nav.py::TestNavButtonKeys::test_jam_sets_entry_mode`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_armed_renders_exactly_one_synced_score`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_unarmed_renders_exactly_one_static_score`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`

## Actual combined-source browser acceptance

Flute: **46 requests and 24 visual scenarios passed**. All YFL-222 E4/E5, F4/F5 and G4/G5 records, source-backed control states, actual native staff positions, written/sounding pitches, octave comparisons, model/keywork clarification, exercise revisions, read-only explanations, exact history and unsupported refusals passed. Other instrument owners and ordinary exercises remain available. Model scope remains covered-key/offset-G/C-foot/no-split-E YFL-222 only; no teacher or physical validation is claimed.

Notation/navigation: **eight actual requests and 24 native before/after conditions passed** at 1440px and 390px. Native ABCJS beam membership and beam levels, slur geometry and identical before/after events verify metrical grouping without changing pitches, durations, rests, articulation or playback timing. Generated flute scale, arpeggio, accented sax sixteenths, slurred passage, articulation warmup and catalog-linked jazz anticipation passed. Unsupported tuplets, broken rhythms and opaque syntax retain conservative spacing; unusual/additive grouping still requires explicit metadata.

Previous, Next and Whole warmup retain their labels and native actions; all measured 40px tall at both widths without clipping. Read-only Explain and Dismiss preserve the plan/history. The icons use the existing family. The conditional analysis link is absent when the card has no URL.

The same native component was additionally rendered with a supplied loopback analysis URL. Desktop and 390px icon/text, sizing, href preservation and actual click-to-destination passed. This is a conditional-component fixture, not a claim that normal cards supplied a URL. [Mobile analysis link](ami-ui-flute-integration/mobile-analysis-link.png).

[Desktop eighths](ami-ui-flute-integration/desktop-eight-eighths-before-after.png), [390px sixteenths](ami-ui-flute-integration/mobile-four-sixteenths-before-after.png), [slur with double beam](ami-ui-flute-integration/mobile-slur-and-double-beam-before-after.png), [mobile controls](ami-ui-flute-integration/mobile-navigation.png), [machine acceptance](ami-ui-flute-integration/acceptance.json).

## Publication boundary and follow-up

Both normal dev pushes are authorized by the user after the above gates. The UI merge is the first target; this documentation-only receipt commit is the final flute integration target. Exact post-push remote SHAs are recorded in external `ami-ef-remote-verification.json` after successful publication. No local note-name or Stage F feature is included in these pushes.

No force push, production deployment, paid Anthropic call or billing change. Other worktrees, active processes, runtime traces and evidence are preserved. The level-aware note-name fix is separate and local only. Stage F specialized saxophone instruction remains gated pending model/setup, expert and physical validation. Adaptive lick/interval sequencing is an audit/proposal, not a newly enabled feature.

External evidence: `D:/AMIWorktrees/flexible-evidence-20261112/ami-ef-*` and `compare_ami_ef_integration.py`.
