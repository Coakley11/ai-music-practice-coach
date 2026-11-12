# Proposed next AMI instrument-technique slices

This is a proposal, not a claim of implemented technique support. Keep each instrument independently reviewable. Continue using the existing instrument specs, notation profiles, exact sounding offsets, note writer and account-scoped exercise history.

## Shared prerequisite

Reconcile each supported instrument's overall range, level comfort windows and low/middle/high registers in the current authoritative profiles. Record which model/extension is assumed. Store any technique-specific constraints as profile capabilities; unsupported capabilities must yield a clear refusal, never a substitute instrument. Test fixed musical examples with an independent pitch/rhythm/ABC reader, plus live notation and sounding playback checks. Preserve exact notes during rhythm-only edits and exact snapshots during undo/redo.

## Clarinet

Separate ordinary octave-pair exercises from register-break drills and the instrument's twelfth overblowing relationship. Obtain reviewed written-pitch/fingering/register-transition tables before generating break or alternate-fingering claims. Start with a few validated pitch-pair patterns per level, conservative tempo, rests and the existing Bb transposition. Acceptance must distinguish an octave from a twelfth and explicitly reject unsupported requested fingerings.

## Flute

Extend the verified register selector into tone-development patterns: sustained notes, breath rests, dynamics and gradual register transitions. Keep beginner comfort separate from an advanced high-register request. Review register/embouchure advice with an authoritative pedagogy source; do not label generic permutations as specialized fingering guidance. First small deliverable: low/middle/high tone pairs and bounded octave-jump exercises with independent octave checks.

## Trumpet

Create a reviewed table of written harmonic partials for each supported valve combination, linked to the existing Bb pitch convention. Generate a lip slur only by moving between permitted partials with a fixed valve combination, within the player's level window. Begin with a narrow open-valve pattern, explicit rests and conservative repetitions. Mutation tests must reject an arbitrary interval that is not in the selected harmonic ladder. Do not infer alternate fingerings or pedagogically suitable high partials from pitch-class membership alone.

## Bass guitar

Complete the missing exercise-adaptation spec and exact octave-transposition/range entries before enabling generation. Link conventional written bass-clef notation to actual sounding pitch. Model standard tuning, string/fret feasibility and bounded shifts separately from a generic guitar profile. Review tuning and notation against authoritative sources and an independent fixed-pitch oracle. Begin with low-register octaves and short position-bound coordination patterns; expanded tunings and extended-range basses remain explicit future capabilities.

## Saxophones

Keep soprano, alto, tenor and baritone as distinct profiles with exact octave offsets and explicit extension assumptions. Extend permutations into instrument-reviewed articulation/coordination patterns, realistic register transitions and capped leap/tempo combinations. Test the same concert harmony through every saxophone's written key and octave. Alternate fingerings and altissimo remain unsupported until their required tables and level constraints are verified.

## Proposed sequence

1. Profile reconciliation and shared note-preserving revision contract.
2. Flute tone/register patterns and ordinary clarinet octave pairs.
3. Reviewed clarinet break patterns and narrow trumpet open-valve slurs.
4. Bass profile, string/fret realization and first low-register exercises.
5. Reviewed saxophone articulation and register-transition studies.

Each stage needs focused musical mutation tests, account/workspace isolation, exact undo/redo, and real-app acceptance before local sign-off. No paid interpretation calls, push, merge or deployment are part of this proposal.
