# Claude-assisted warmup planning — live evaluation, 2026-11-02

Direct Anthropic Messages API (anthropic SDK 2.3.0, no retries), `claude-sonnet-5-5`, effort `low`, harness `scripts/ami_warmup_planning_experiment.py`, run outside
the app. Authorization: at most 10 requests and a $0.20 application ceiling. **Used: 9 requests, $0.035552 as recorded by AMI's own ledger.** Anthropic Console
has not been checked by AMI; the promotional-credit deduction is **unconfirmed** until the owner reads it there.

Preflight (no billing): key valid; organization header equals the expected organization; `claude-sonnet-5-5` retrievable; model priced in AMI; reserve/release
round-trip, over-budget refusal and call cap worked on a throwaway ledger.

## Result

All nine responses were `accepted` by the closed-vocabulary validator (0 rejections, 0 invalid JSON, 0 refusals, 0 API errors). Two were flagged
`unsupported_request` by Claude itself (the revision sentence; the Blue Bossa song request), both correctly. Mean 1.93 s per request (max 3.10 s). Tokens in total:
14,356 input / 684 output (about 1,600 in / 76 out each); cost $0.0038–$0.0042 each.

| | Rules only | Rules + Claude, rules-win merge (as built) | Rules + Claude, Claude fills what the rules only defaulted (offline re-merge, no new calls) |
|---|---|---|---|
| 8 plan sentences, deterministic checks | 21/28 | 21/28 | 26/28 |

* The five sentences the owner listed: the fixed rules, **after** this slice's fixes, already satisfy them (S1, S2, S4, S5 fully; S3 is a revision). Before those fixes the rules
  misread three of them ("but not scales" kept scales; "increasingly difficult intervals" set Advanced; "make the second exercise more challenging, but keep the first" made the
  whole warmup harder). Claude read S1, S2, S4 and S5 correctly as well, so on these it matched the repaired rules and did not exceed them. The rules were repaired *after* seeing
  these sentences, which favours the rules in this comparison.
* Where Claude added value: sentences with soft or compound intent the rules cannot parse — S6 ("get my fingers and tongue moving, not much on long tones": scales + articulation, no
  long tones), S7 ("double-tonguing and finger speed": articulation + scales), S8 ("a bit of everything, intervals wider than thirds": all four families, fourths to octaves).
  With a merge that lets Claude fill what the rules only defaulted, the built warmups meet 3/4, 2/3 and 4/4 of the checks instead of 1/4, 1/3 and 2/4. The merge as built keeps the
  rules' non-empty (here wrong) family list, so it hid that benefit. Claude never produced notes; the planner built and timed every exercise.
* What the vocabulary cannot say: S3 (item-level revision) — Claude correctly declined; a separate revision vocabulary is needed. "Something short/quick" produced no minutes
  (the schema says 0 when unsaid); "increasingly difficult" (a widening run) has no field. Both are proposed vocabulary additions for the next slice.
* Remaining deterministic gaps the evaluation exposed: a warmup of a single family cannot fill 15 minutes (variant cap × at most 6 plays — S8 rules-only reached 9:30 and says so).

Caveat: nine sentences, one run each, one model; no statistical claim. The corpus was chosen by the owner (S1–S5) and by me (S6–S9).

## Request ids (for the Console)

req_011CgfMzniG3dYxfuhXNcVxy, req_011CgfMzzqFxRZUZt9AVv2R9, req_011CgfN1CxXTvPrQyvFRFdZu, req_011CgfN1PbVMnh1SqFGamMea, req_011CgfN1a1oR9VPuPinx6iz9,
req_011CgfN1jPc1RZiwCb1bcAb4, req_011CgfN1u9VSdZC7Buvp6uKZ, req_011CgfN22WkAQX8Q8x3r7gQM, req_011CgfN2HPCHhgQ2LtAA5opu (plus the free model-metadata GET req_011CgfMsg3UJ3JTGSzpLhGMw).
