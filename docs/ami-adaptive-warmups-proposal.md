# Proposal: adaptive musical warmups and intelligent exercise generation

Status: proposal only. No code for this milestone has been written.

## Goal

A player says what they want to warm up ("ten minutes of tone and articulation before Blue Bossa, I'm intermediate on alto") and AMI builds a short, ordered
warmup of real exercises. Each item is valid music for that instrument and level, can be played back and revised in conversation, and can be undone.

## Inputs the plan depends on

| Input | Source today | Use |
|---|---|---|
| Instrument (incl. sax type) | app selection / notation profile | range, written transposition, register limits, which items make sense (no articulation drill on a voice, no breath items for guitar) |
| Level (Beginner / Intermediate / Advanced) | app selection | tempo ceiling, interval vocabulary, rhythm density, length of each item |
| Practice Focus | app selection | which item families get time |
| Natural-language request | question box | duration, emphasis, exclusions ("no long tones", "more articulation") |
| Desired duration | request, else default 10 min | how many items and how long each lasts |
| Active song, section, harmony | chart snapshot | optional: key, chord tones, guide tones, an improvisation-preparation item that uses the real changes |

Anything not stated is defaulted from the first four rows and the answer says so ("Assumed: 10 minutes").

## Item families (all produced by deterministic engines)

1. Long tones: sustained pitches in the comfortable register, dynamic shapes, level-dependent length. New small engine; durations and ranges come from the notation profile.
2. Scale patterns: the existing scale-pattern engine (key based or chord following).
3. Intervals: seconds through octaves, ascending/descending, existing interval/fourths vocabulary.
4. Two-note drills: slurred and tongued pairs, register-crossing pairs. New small engine on top of the same event model.
5. Articulation: tongued, slurred, accented patterns through the existing expression layer.
6. Guide tones: the existing guide-tone engine over the active section.
7. Improvisation preparation: a short chord-tone and approach-note exercise over the active section, then a prompt to improvise.

Every item is an ordinary AMI exercise (same stored form, same ABC writer, same undo/redo), so everything shipped in M1c and M1b (revisions, instrument change, section change, explanations) already applies to it.

## Who decides what

* Deterministic code decides every note, rhythm, range and transposition. Nothing a language model writes is ever played or notated unvalidated.
* Rules plan the warmup (item families, order, durations) from the inputs table. This is enough for most requests and works with no network.
* Claude interpretation (developer-only, off by default, same gates and ledger as M1b) is used only where rules cannot read the request: free-form emphasis, mixed instructions, or a revision such as "make the middle part gentler". It returns a closed-vocabulary plan that the same validator checks. It never sends notes, chords or account data.

## Conversation model

A warmup is a list of exercise items plus a plan record. Revisions apply to the whole plan ("make it shorter", "drop the intervals", "more articulation", "harder") or to one item ("make item 3 slower", "change item 2 to thirds"). Undo and redo operate on the plan version. Explanations ("why this order?") read the stored plan.

## Guardrails

* Account and workspace isolation as in M1b (session-scope purge, stored-record reads only).
* Respect instrument range and written transposition; never silently change the app's instrument or Practice Key.
* No health or medical claims; warmups are practice suggestions.
* API use stays ledgered, budget capped and off by default.

## Recommended first slice (small, shippable, no API)

"Warmup v1, rules only": request parsing for duration, level and emphasis; a planner that picks 3 to 5 items from long tones, scale patterns, intervals and articulation; one new engine (long tones) plus reuse of the scale-pattern and interval engines; plan stored as a versioned record with undo/redo; plan-level revisions ("shorter", "drop X", "more X"). No song integration and no Claude in this slice.

Why first: it proves the plan record, the item model and the revision loop with the lowest musical risk. Guide-tone and improvisation-preparation items (song aware) are slice 2, and Claude planning is slice 3, only if rule-based reading proves insufficient in real use.

## Acceptance for slice 1

* Same request for flute, alto and tenor gives items that are in range and correctly written for each instrument.
* Duration is respected within one item.
* Every item renders on the staff at the stored pitch (the check used for the octave fix).
* Revisions and undo/redo never leave a plan in a half-changed state.
* No regressions against the dev baseline; all heavy suites run sequentially.

## Open questions for Daniel

1. Default warmup length when none is given (10 minutes suggested).
2. Whether the warmup should be one scrolling plan or a step-through "next item" flow.
3. Whether the warmup feeds into the practice log as one session or per item.
