# AMI Music Coach — routed architecture (vertical slice)

**Branch:** `feature/music-coach-ami-architecture`  
**Last updated:** 2026-08-08

## Goal

Replace single-prompt AMI answers with: normalize → classify → `CoachRequest` → solver registry → `CoachResponse` → composer → existing instant solver UI.

## Package

`music_coach_ami/` — types, context_reader (read-only), entities, router, app_knowledge, solvers, composer, pipeline.

## Integration

- `music_ami_instant_solver.solve_instant_music_insight` tries `run_coach_pipeline` first.
- Dev diagnostics: `music_ami_pages.build_music_send_diagnostics` adds coach intent/entities.

## Next

- Conversation follow-ups (`follow_up_ref` on `CoachRequest`)
- Richer theory with active chord context
- Legacy-only intents: transposition, practice history, chord_transition
- Pass live `session_state` into pipeline from instant solver (not only `ami_ctx`)
