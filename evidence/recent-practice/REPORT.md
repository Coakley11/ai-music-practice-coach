# Recent Practice restoration and acceptance

Base: fetched `origin/dev` at `c0e0383741a83c7e95bc8b1af8424f45af05ddf2`. Branch: `fix/recent-practice-and-purple-sidebar-20261105`. No push, merge or deployment.

## Cause and correction

Home intentionally used navigation-only `apply_home_navigation`; its verified historical card never activated the recorded source. A new `home_practice_resume.py` adapter accepts only resolvable resource IDs plus recorded concert key and supported instrument. Missing/deleted/ambiguous IDs, foreign workspaces and invalid key/instrument/capo data fail closed with an explanation and navigation-only wording. No title matching, historical-row edits or inferred live metadata.

The Home click queues a request; restoration occurs after workspace hydration and page restoration, before widgets. Existing `apply_music_resume_payload` dispatches to source-owner activation APIs and stops playback. The adapter stages mutable musical state, applies the pick-owned concert key, canonical instrument/subtype, supported focus/section and guitar shape/capo, and derives written pitch with the existing transposition resolver. It validates before publishing; failed activation/validation leaves live state unchanged. Temporary staging suppresses intermediate activation persistence and activity writes; the final complete state uses the existing save API once. Normal page-change saves and cloud-read logic are unchanged.

Browser testing exposed a stale canonical Say record projected by autosave after Jazz activation, and stale Custom/Composition Backing key snapshots. The adapter now reconciles selected-song identity through the existing activation API, explicitly commits the complete canonical context through `write_canonical_active_song_state`, refreshes the same owner's Backing context, and captures fresh Backing/Practice snapshots. Source ownership, Set Active Song boundaries and the Custom-preview isolation fix remain intact. Previewing Custom itself is not activation.

New activity events now capture existing subtype, focus, original key and available guitar metadata. This prevents a newly practiced saxophone event from becoming an incomplete latest record on Home. No backfill of incomplete older history. Existing canonical log focus categories are mapped only when the existing normalizer yields one valid control label.

## Validation

`accepted-tests.txt`: **157 passed, 74 subtests passed**, 45.25 seconds. Ten existing AST invalid-escape SyntaxWarnings, no failures. Focused Home, Catalog, destinations/navigation, historical workflow Resume, source lifecycle, Custom preview isolation, Practice activity and Command Center activity tests. New cases cover Catalog/Custom/Composition, alto/tenor, focus, capo, hydration deferral, staged failure rollback, stale snapshots/canonical state and repeat Resume.

Actual local Chromium/Streamlit checks used clearly named disposable fixtures and workspace data in this worktree; Supabase was not configured. Shallow fixture: Say/Piano/G -> Shallow/Alto/F, written D, original G. All the Things You Are fixture: Say/Piano/G -> Jazz/Tenor/Eb, written F, original Ab. Songs' selected dropdown, loaded-song panel, sidebar and Practice Key agree (`after-songs-synchronized.png`). Songs -> Practice -> Backing -> Home preserves source, pick, original/concert/display key, instrument and focus. Refresh/new browser session retains restored Jazz context; final mobile repeated Resume used an exact `Resume Practice` role/label assertion and preserved the full state. Browser state/timings are in `browser-results.json` and `browser-mobile-results.json`. Intermediate failed investigative runs remain local and excluded from Git.

Desktop 1440x1000; mobile 390x900 expanded/collapsed sidebar, expanded account controls and selected Practice Key dropdown. Separate sidebar commit reuses header purple `#312e81` with yellow/blue/white accents and scoped contrast/state styling. Rendered screenshots were visually reviewed.

Observed navigation in the corrected full-app Jazz pass: Songs 11.359s, Practice 4.165s, Backing 12.442s, Home 7.079s; final serial run Songs 5.340s, Practice 6.155s, Home 5.100s, mobile Resume 10.293s. Cold/fresh loads varied roughly 8.6-18.9s. These local checks used cached compilation and no configured cloud, so they are not a controlled comparison with the earlier 20.8-38.3s baseline. No performance/persistence mechanism was changed. CPU samples 90-91%, available RAM 1.44-2.12GB, commit about 33.8-35.3GB of 40.6GB, C: free about 201.8GB. Tests and browsers ran serially; only owned servers/browser contexts were closed.

## Limits and review

Complete restoration needs reliable IDs, source availability and captured musical setup. Generic Saxophone without subtype, missing IDs, unsupported focus or incomplete guitar setup retains explicit navigation-only fallback. Specialized Mission/recording engine configuration is not reconstructed by this musical Practice adapter. Browser checks cover Catalog; Custom/Composition ownership and return-to-Backing are focused regression tests. Authenticated cloud/cross-device restoration still needs an authenticated acceptance pass after integration approval. No database/auth/RLS/subscription changes. Deployment remains unapproved.

Final resource sample after closing the owned server: available RAM 2.78GB; commit 32.40GB / 40.51GB; CPU 32%; C: free 201.87GB; port 8541 has no listener.

Sidebar-only commit: `d002bf82`. Restoration is the following separate local commit.
