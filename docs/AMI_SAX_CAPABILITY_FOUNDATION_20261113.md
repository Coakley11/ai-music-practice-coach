# Saxophone capability foundation: scope and compatibility contract

This local milestone follows successful advanced-jazz integration. No specialized
exercise engine is enabled. The common profile reads the existing make_player,
playable_written_range, exact_offset and Player.window authorities; it does not
replace their values or infer optional hardware from Advanced level.

| Type | Written common cap | Written minus sounding | Sounding cap | Written C4 sounds |
|---|---|---:|---|---|
| Soprano | Bb3-F6 | 2 | Ab3-Eb6 | Bb3 |
| Alto | Bb3-F6 | 9 | Db3-Ab5 | Eb3 |
| Tenor | Bb3-F6 | 14 | Ab2-Eb5 | Bb2 |
| Baritone | Bb3-F6 | 21 | Db2-Ab4 | Eb2 |

Scientific pitch notation uses C4=MIDI 60. These are the app's conservative,
verified generation caps, not a guarantee about every historical instrument's
hardware. Documented model features are separate claims with provenance, region,
snapshot date and exact revision/applicability limits. Generic high-F#, high-G,
low-A and front-F availability remain unknown. Absence from a specification is
not definitive evidence of absence.

The published YSS-875EX table distinguishes EX high F#/front F from HG high G;
YAS-26 lists front F only; YAS-280 and YTS-62 document high F#/front F; YBS-62II
has low A, high F# and front F. The archived US YBS-62II page identifies Eb and
agrees with the earlier UK/JP evidence. Do not conflate it with the newer similarly
named page that had contradictory key identity. Optional low A3 on that baritone
would sound C2, and keyed F#6 or G6 are model endpoints, not automatic altissimo
readiness. No current generator range is expanded by looking up a model.

Source facts and fetch limitations are in sax-foundation-sources.json. The earlier
audit's identifier _EXACT_OFFSETS should read scale_pattern_harmony._OFFSETS,
accessed through exact_offset; no duplicate transposition table is needed.

## Future study and evidence requirements

A study definition must distinguish written target, sounding projection,
fingered fundamental, intended harmonic partial, exact instrument/model/system,
setup and a reviewed fingering reference. Partial number alone is theoretical
harmonic information, not proof of a player's attainable pitch or 12-TET
intonation. No overtone sequence or fingering recipe is generated here.

Validation must require a matched model/revision and system, primary/authorized
source with locator, independent qualified reviewer, recorded setup, response,
intonation and transition observations, pedagogical prerequisites, independent
written/concert/octave/notation checks and real browser accessibility. A filled
metadata record must not itself enable a missing specialized engine.

Altissimo, overtone and alternate-fingering requests receive explicit
not-supported guidance with a supported ordinary-exercise alternative, leaving
current notes and Undo/Redo versions unchanged. This must work with and without
a current plan and must not intercept other instruments' verified technique
owners. Account/workspace changes still pass through existing ownership guards.

## Recommended first specialized implementation

After separate approval and expert/source evidence, pilot one bounded
fundamental-to-second-partial preparation study on a specified alto model and
setup. Validate prerequisites and actual response/intonation; retain fundamental
and played partial as separate event facts. Test exact written/sounding pitches,
independent harmonic relationships, honest refusal, range policy, notation,
selected-item targeting, Undo/Redo and owner isolation. No altissimo G or universal
alternate fingering should be inferred from this pilot.

See the interactive fingering roadmap for the separate Stage A standard-note
lookup/diagram pilot. Both proposals reuse AMI engines rather than adding a
competing exercise or notation engine.


## Implemented local foundation

Base: remotely verified dev e605eea4722e0ad2bb0aafb32bb1c0b60a54e4a3.
Local branch: feature/ami-sax-capabilities-20261113. This milestone is not
approved for push, merge or deployment.

sax_capabilities.profile reads existing make_player values. Frozen common
profiles expose exact octave transposition, written/sounding generation caps,
clef and level windows. Seven frozen documentary model scopes cover the four
saxophones. Missing hardware stays unknown, including high F# on YAS-26 and
high G on the ordinary YSS-875EX. model_scope rejects unknown/mismatched types
and never mutates or selects a generator profile. Keyed endpoints describe
listed keywork, not a physical upper limit on all possible techniques.

SourceReference records retain URLs, retrieval dates and evidence limitations.
The source catalog is music_coach_ami/sax_capability_sources.json. Some pages
were available only through the official search index or the preceding accepted
audit because direct requests intermittently returned 403; those limits are
explicit. No independent horn/teacher validation has been performed, and no
published specification is presented as expert validation of a fingering.

StudyTarget keeps the fingered fundamental, intended partial and written target
separate; written spelling/octave must match through the existing pitch helper.
FingeringReference is only a scoped source/variant reference, with system,
locator and permission fields; there are no populated key/hole/valve recipes.
ReviewEvidence records model/revision, system, setup, primary source, permissions,
independent reviewer/date, prerequisites, response/intonation/context and the
required independent checks. ValidationGate reports missing requirements. Even
a synthetically complete record cannot enable generation: a separately approved,
independently verified specialized engine is always still required. Completeness
checking is not truth certification or automatic expert approval.

The deterministic specialized-request guard runs after existing ownership
validation and before exercise generation. It covers altissimo, overtones and
alternate fingerings for saxophones, including requests without an exercise
noun. It explicitly says the technique is unsupported and any displayed score
is the old exercise. It offers an ordinary articulation/interval request without
generating it. Existing standalone and timed/song-score response contracts are
preserved; other instruments retain their owners. No profile selector, diagram
engine, fingering database or specialized study generator was implemented.

The interactive fingering roadmap in AMI_INTERACTIVE_FINGERING_ROADMAP.md captures
the additional future request, generic data-model requirements, source and
license validation strategy, and a bounded three-note Stage A proposal. It is
planning only and requires separate implementation approval.

## Verification receipt

Completed local evidence is recorded below. Earlier failed development runs
remain preserved separately and are not counted as release passes.


Final 69-file regression under Python 3.12.8: 3,027 passed, six unchanged known
failures, 2,743 passing subtests. All 2,991 shared IDs are unchanged against the
verified integrated-dev application source at e605eea4; all 42 new tests pass.
No collection errors or deselections; exact terminal failure/subtest ledger
matches. The baseline application source is the completed integrated run before
its receipt commit; that commit added no subsequent application changes.

Focused development compatibility passed 504 tests after fixing the legacy
standalone response contract; the final subtype-ambiguity preflight passed all
42 capability tests. The full final-source regression above includes both.

Exact unchanged failures:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`

Evidence under D:/AMIWorktrees/flexible-evidence-20261112:
sax-capability-regression.{json,log}, sax-capability-comparison.json,
sax-capability-final-preflight.{json,log}, and sax-capability-resources.json.
The clean integrated baseline is jazz-integrated-regression.{json,log}.
Only owned runners are cleaned up; other worktrees, runtime traces, branches
and processes are preserved. The source catalog performs no network access.


Final real-app acceptance: sax-capability-browser, CAPABILITY_BROWSER_EXIT=0,
10/10 requests. A real Blue Bossa warmup and selected second-item revision were
followed by the three exact requested specialized questions. Each explicitly
refused generation, retained the exact plan/history and rendered existing native
notation. Explain remained read-only; Undo/Redo restored exact pre/post edit
plans. Ordinary sax articulation and verified beginner trumpet lip slurs still
generated correctly. All before/after sidebar settings match; no paid-transport
marker, browser failure or Streamlit exception occurred. Owned server/browser
cleanup completed. No specialized engine, fingering recipe, diagram engine,
paid API call, billing change or deployment was added. This new branch remains
local-only; only the preceding verified jazz integration was pushed to dev.

The integrated notation application code is inherited unchanged from e605eea4;
its twelve desktop/mobile visual scenarios and 26 jazz browser requests remain
applicable. The capability run additionally verifies actual existing native
scores through the new unsupported-request path. See sax-capability-evidence-summary.json
in the evidence directory for the final machine-readable receipt.
