Custom workspace Practice Key investigation and review candidate

Branch: fix/custom-preview-practice-key-20261104, based on d79f5a0e4420d82cf0cd883279cd42de4170890a. Changes are local and unintegrated. No push, merge, or deployment occurred.

Root cause and baseline attribution

prepare_custom_workspace_sidebar_display_key() unconditionally assigned the Custom preview selection to display_key and concert_key, and queued _pending_display_key. On a new workspace the Custom draft is C, so visiting Custom projected C while Catalog Say still owned the active song. The dedicated widget already existed; the shared-field mirror was unnecessary for a non-active Custom preview. sync_custom_workspace_practice_key() also mirrored preview edits into shared fields.

This was a real shared-field mutation, not only stale rendered text and not cloud hydration. The authoritative Catalog per-song Practice Key and concert_practice_key stayed G, causing the split. Custom was not implicitly activated; active source, pick, selected song, instrument, and original song key remained unchanged. Saving shared display fields while this overlay was present was an avoidable risk, even though Catalog sticky normally restored on leaving Custom.

The traced production navigation/prepare functions reproduce identical writes for Home, direct Practice, and direct Songs entry. Reproduction against pre-Home dev 9a9cb03d produces the same results. custom_progression_lab.py is byte-identical between that baseline and d79f5a0e. git blame attributes the unconditional assignments (baseline lines 1127-1128) to 96458202b, dated 2026-08-22. It predates the Home integration.

Correction

Keep preview key changes on the dedicated Custom widget and custom:: per-song store. Mirror into shared display/concert/pending keys only when Custom is Global Active, or when no song/source owns the workspace. Do not consume another source's pending key during Custom preparation or draft loading. Remove the now-unnecessary new Custom overlay/seal installation. Existing legacy overlay cleanup is unchanged. Label the non-active sidebar as Custom Original Key and Custom workspace Practice / Concert Key so C is clearly the preview's key. Set Active Song remains the explicit promotion boundary. No persistence module, page-change save mechanism, cloud-read optimization, or source activation function changed.

Exact states

| Transition | Active song/source | Instrument | Original | Concert Practice | display_key | Custom preview |
|---|---|---|---|---|---|---|
| Original Home/Practice/Songs -> Custom | Say / catalog_song | Guitar | G | G | G -> C | C |
| Corrected Home/Practice/Songs -> Custom | Say / catalog_song | Guitar | G | G | G -> G | C |
| Corrected Custom preview edit C -> Eb | Say / catalog_song | Guitar | G | G | G -> G | Eb |
| Corrected return to Practice/Backing | Say / catalog_song | Guitar | G | G | G | isolated |

Automated fixtures additionally cover Composition global ownership (G) with a Custom preview (C/Eb), Custom Global Active (Eb) across Custom/Practice/Backing, loading another draft without discarding pending G, and explicit Set Active Song promotion from Catalog or Composition to Custom. Composition/Custom activation coverage is automated; the live browser session uses Catalog, not a populated Composition document.

Validation

Final focused run: 161 passed, 60 subtests passed, 10 failures. The identical original suite on unchanged d79f5a0e has 133 passes, 60 subtests, and the same 10 failures with the same assertions. Those are seven existing CPL restore/source tests and three existing SBI split-brain tests; they are listed in verified-tests.txt and the baseline log. Two existing preview-projection assertions were updated to expect preservation of the global key while retaining independent Custom widget checks. All 13 new regression cases and all 15 navigation cloud-read safety cases pass.

Browser: one serial Chromium session, isolated MUSIC_APP_DATA_DIR, no production data. Traced SessionState assignments record all shared key/source/pick writes. Home -> Custom; Practice -> Custom; Songs -> Custom; returns to Practice and Backing; Custom preview edit to Eb all preserve Say/catalog/Guitar/original G/concert G/display G. Zero Streamlit exceptions. Desktop 1440 and mobile 390 screenshots inspected. Browser and server closed; port 8538 confirmed closed. Other agents' worktrees, processes, evidence, Cursor databases and backups preserved.

Performance findings

Earlier 20.8-38.3 second navigation timings are not a clean production baseline: the observation harness used runpy.run_path, recompiling the 1.26 MB app on every rerun, while RAM was extremely low and CPU frequently 100%. A separate compile measured 3.791 seconds. The corrected observer caches the same compiled app code (like Streamlit); its cold compile measured 4.364 seconds. The normal navigation path still issues a rerun: 11 rerun requests plus 14 completed app runs were recorded. Completed-run wall median 2.165 seconds and CPU median 1.914 seconds show substantial local execution work; this is not solely cloud wait. Do not claim the key correction accelerated navigation.

Cached observer warm click-to-completion range 4.235-9.995 seconds, median 5.086 seconds; cold load 22.842 seconds. CPU during the warm sample was 43.4% with 1.52 GB RAM available, so this comparison is confounded by machine load as well as harness changes. Guest cloud diagnostics measured 0.05-0.13 ms per full-session path and Supabase was not configured. They cannot measure live authenticated cloud cost or Grok's eligible skip path. Existing cloud-read tests verify the safety contracts with mocked services. Strict end-of-run flusher samples median 367.5 ms, max 735 ms; these do not measure every blocking page-change save. Preserve those mechanisms and share these observations with Grok rather than changing them in this key fix.

Evidence: before-reproduction.json; baseline-9a9-reproduction.json; after-reproduction.json; browser-key-writes.jsonl; browser-results.json; run-timings.jsonl; performance-summary.json; verified-tests.txt; custom-desktop.png; custom-mobile.png. Reproduction uses in-memory sessions; browser data is confined to browser-runtime. Intermediate logs are preserved but are not the final validation result.

Readiness: correction ready for review and separately approved integration. Deployment approval is still withheld pending integration acceptance; the known baseline failures and live authenticated cloud validation limits remain visible.
