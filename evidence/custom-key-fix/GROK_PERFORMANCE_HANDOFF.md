Performance handoff for Grok

This branch changes Custom preview key isolation only. music_persistent_state.py and suite_user_persistence.py are unchanged. No navigation performance or save-path edits.

Performance findings

Earlier 20.8-38.3 second navigation timings are not a clean production baseline: the observation harness used runpy.run_path, recompiling the 1.26 MB app on every rerun, while RAM was extremely low and CPU frequently 100%. A separate compile measured 3.791 seconds. The corrected observer caches the same compiled app code (like Streamlit); its cold compile measured 4.364 seconds. The normal navigation path still issues a rerun: 11 rerun requests plus 14 completed app runs were recorded. Completed-run wall median 2.165 seconds and CPU median 1.914 seconds show substantial local execution work; this is not solely cloud wait. Do not claim the key correction accelerated navigation.

Cached observer warm click-to-completion range 4.235-9.995 seconds, median 5.086 seconds; cold load 22.842 seconds. CPU during the warm sample was 43.4% with 1.52 GB RAM available, so this comparison is confounded by machine load as well as harness changes. Guest cloud diagnostics measured 0.05-0.13 ms per full-session path and Supabase was not configured. They cannot measure live authenticated cloud cost or Grok's eligible skip path. Existing cloud-read tests verify the safety contracts with mocked services. Strict end-of-run flusher samples median 367.5 ms, max 735 ms; these do not measure every blocking page-change save. Preserve those mechanisms and share these observations with Grok rather than changing them in this key fix.

