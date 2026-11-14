# Interactive fingering instruction roadmap and bounded Stage A proposal

Planning only, 2026-11-13. The current assignment remains jazz integration and
local saxophone capability foundations. No fingering diagram, key recipe,
altissimo/overtone generator or billable transport is enabled by this proposal.

## Shared data contract

- Instrument identity: family, transposing subtype, exact model/revision and
  applicable serial/region, tuning and key system (including clarinet Boehm vs
  other systems and flute system/footjoint). Unknown identity stays unknown.
- Note identity: explicit written spelling and octave, concert projection using
  the existing exact-offset engine, register and intended technique. A bare
  A, high F or altissimo Bb without enough context triggers a targeted question.
- Capability: common application range separately from sourced physical model
  endpoints and optional keywork. Physical equipment does not prove player
  facility or pedagogical readiness. Metadata cannot widen existing generators.
- Fingering variant: stable reviewed key/hole/valve IDs, engaged/released/half-hole
  states, octave/register keys, model applicability, alternate/context label,
  provenance, license/permission, revision and review status. No invented keys.
- Technique link: intended note/transition or harmonic partial, prerequisites,
  suitable level, setup constraints and a verified source. Trumpet valve state
  and partial are separate; flute octave work is not brass lip-slur instruction.
  Clarinet ordinary octave exercises are distinct from register-key twelfths.
- Diagram: reviewed instrument geometry and labels mapped deterministically from
  verified states, accessible text equivalent, source attribution and selected
  variant. Do not use a language model or image generator to invent a fingering.
- Interaction: selected staff event and fingering ID share the same immutable
  note identity. Retain source item/version/workspace/account ownership. A request
  for an associated exercise uses the existing AMI build/revision/history engine;
  it must actually contain the taught note/transition and preserve untouched rows.

## Source and validation strategy

Prefer manufacturer manuals and authored licensed fingering methods. Record URL,
publication/edition/page, access date, exact applicability and quotation/data
permissions. A published table is documentary evidence, not independent
performance validation. A qualified reviewer must independently check each
mapping on the specified instrument/system and record model, setup, response,
intonation, transition context and limitations. Resolve contradictions rather
than automatically importing a convenient value. Unknown/withdrawn variants are
unavailable; an unreviewed alternative must never become a fallback.

Independent tests must cover written/concert/octave projection, note identity,
key states versus the reviewed source, diagram state and accessible labels,
ambiguity/refusal, model/system mismatches, staff click selection, actual
exercise targeting, exact Undo/Redo, untouched rows and owner isolation. Browser
acceptance includes desktop/390 px, full score/diagram accessibility and no
page-level overflow. Playback verifies represented pitches, not human technique.

## Stage A: a small independently valuable pilot

Propose one explicitly identified alto model/system and three ordinary written
notes (G4, A4, B4), only after licensed source mappings and independent qualified
review are obtained. This is a proposed boundary, not a claim the data is ready.
Answer a note-specific question with staff, written/concert pitch, one reviewed
fingering diagram, key-state text, short sourced explanation and applicability.
Ask for octave or instrument when missing. Allow selecting those supported notes
on the staff to reveal the same verified record. Other notes explicitly remain
unsupported in the pilot.

Offer a short related exercise; create it only when requested. Reuse existing
range, notation and history engines, and verify that it reaches the exact taught
note. Do not automatically play or replace the current exercise on a lookup.
Acceptance requires every mapping independently reviewed, exact diagram/state
checks, real desktop/mobile interaction, owner isolation and unchanged regression
outcomes. Separate approval is required before starting this pilot implementation.

## Later stages and boundaries

Stage B extends sourced ordinary techniques: flute octave/register work, clarinet
break transitions with system identity, and actual trumpet valve/partial lip
slurs. Preserve currently supported ordinary exercises; do not relabel them as
verified fingering instruction. Stage C adds saxophone altissimo, overtone and
alternate-fingering variants only after exact model/setup and expert evidence.
No arbitrary universal altissimo recipe or database of invented fingerings.

The first specialized saxophone pilot should be a teacher-reviewed, narrowly
bounded fundamental-to-second-partial preparation study. Its event must retain
the fingered fundamental separately from the intended sounding partial, exact
written/concert pitches and a licensed method/prerequisite reference. Require
instrument/setup-specific response and intonation observations, independent
notation checks and explicit user approval before generation. This foundation
must not infer readiness merely from Advanced level or optional high keywork.


## Stage A local implementation follow-up

AMI_FINGERING_STAGE_A_20261113.md records the subsequently authorized local
three-note Yamaha YAS-280 pilot. It is explicitly manufacturer/reference-supported,
not teacher-reviewed or instrument-performance validated. This distinction was
authorized in the Stage A assignment; the earlier proposal does not turn the
current source cross-check into a qualified teacher review. Advanced specialized
techniques retain the separate expert/evidence gates. Staff-click selection and
other instruments remain future work.


## Local Stage B follow-up (2026-11-13)

Stage A is integrated at 18ee27b3f61ea4057acbdd1efb993039f75044a4.
The isolated local Stage B pilot adds nine source-backed Yamaha YAS-280 notes
and five documented octave pairs, comparisons, and bounded canonical handoffs.
See AMI_FINGERING_STAGE_B_20261113.md for sources, exact applicability, acceptance
and limits. Manufacturer/reference-supported remains distinct from teacher review
and physical validation. Stage B requires separate approval before integration.
Recommend a small model-identified B-flat trumpet valve/partial pilot next;
clarinet register systems and flute octave-dependent fingerings remain separate
future records. No advanced specialized technique or other instrument is enabled.
