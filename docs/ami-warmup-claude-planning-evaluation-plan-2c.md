# Claude-assisted warmup planning — focused evaluation PLAN (prepared, not executed)

Status: **a plan only.** Nothing in it has been run. It needs the owner's explicit approval before any billable request. It covers the next step after Slice 2b and is
not Slice 2c itself. The Claude interpretation layer stays off for ordinary users, unwired from the live warmup path, and developer-gated.

## Why

The 2026-11-02 direct-API evaluation (9 requests, $0.0356, confirmed in the Console as $99.83 → $99.79) showed Claude reads compound or soft intent the fixed rules miss
("something short for my fingers and tongue, not much on long tones"), but also that the closed vocabulary was too small (no item-level revision, no "short", no progression)
and the merge policy hid the benefit. Slice 2a/2b added song-aware exercises, sections, whole form, approach kinds and per-exercise level changes: the vocabulary must grow, and
the hard cases are now compound ones across turns ("make the second exercise harder but keep the first, then add approaches from below only in the bridge").

## Division of labour (unchanged)

Claude proposes a **closed-vocabulary request or revision**; deterministic code validates it and the same engines build, time, notate and verify every exercise. Claude never
supplies notes, pitches, durations, chords, keys, transpositions or chart facts, and may not override an explicit user constraint. Explicit validated constraints (a number, a level
word, a negation, a named section, an order) win; Claude fills only what the rules left empty or defaulted.

## Step 0 — mocked, non-billable (before any live call)

* Extend the planning schema (families incl. `guide_tones` / `chord_tones` / `approach_notes`; `section` chosen **from the chart's own section names**, `bars`, `whole_form`;
  `tones`; `start_tone`; `approach_kind` and `target`; `shape` / `direction`; `order` of exercises; `length_hint` short / normal / long; `progression`; `level`; `minutes`;
  `exclusions`; `emphasis`; `clarify`).
* Add a separate **revision** vocabulary: a list of operations `{op ∈ supported ops, target {index | kind | all}, params}` plus an explicit `preserve` list; the validator rejects any
  op the planner does not support and any target that does not exist in the stored plan.
* Fix the merge policy in mocked tests: explicit exclusions and explicit numbers are never overridden; a Claude exclusion still applies; defaults are replaced by Claude's reading.
* Build a recorded-response fixture set and run the full pipeline on it with the transport blocked (as in every current test).

## Step 1 — the live evaluation (needs approval)

* Direct Messages API through AMI's transport, the existing ledger and budget guard (preflight: key valid, organization `7f1b1c57…`, model available, over-budget refusal, call cap).
* **At most 12 requests and $0.25** (worst case about $0.0064 each; the last run averaged $0.0040). Abort on the first unexpected outcome. Request IDs recorded; the owner confirms the
  Console deduction afterwards.
* Corpus (12): the five sentences used on 2026-11-02 re-run against the improved rules as the control; plus compound requests ("an advanced jazz warmup, articulation heavy, no scales,
  guide tones first then approaches, ten minutes, over the bridge"); a soft-intent request; an ordering request; a named-other-song request (must be flagged, not served); two compound
  revisions given a stored plan summary ("make the second exercise harder but keep the first; add approaches from below"; "only the bridge but keep the arpeggios as they are");
  an unsupported request (triplets / pedal point / a chord the chart does not contain) that must be declined; an ambiguous one that must set `clarify`.

## Measures (deterministic, identical for rules-only and rules+Claude)

Instruction adherence (a check list per sentence on the **built** warmup: families, order, level, minutes, section, bars, exclusions, preserved exercises byte-identical);
useful variety (distinct exercises / families); unsupported or invented proposals (must be declined, never built); validation rejections; clarification when it should ask;
response time; tokens; recorded cost. Report rules-only, rules + Claude (as merged), and the effect of the merge policy separately. Nine to twelve sentences is a smoke test,
not a statistic: state it as such.

## Gates for ever enabling it for users

Developer-gated and default off; a measured, repeatable benefit on adherence; zero cases where Claude overrode an explicit constraint or produced an unbuildable plan; cost per
request and per session within the owner's limit; the deterministic fallback always available; the owner's explicit approval.
