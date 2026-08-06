# Broad Creative owner / workflow regression gate (safety branch).
# Target: >=339 passed, identical pass/skip on two consecutive runs.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$TestFiles = @(
    "tests/test_creative_lifecycle_continuous_session.py",
    "tests/test_creative_return_from_backing_widget_lifecycle.py",
    "tests/test_streamlit_creative_lifecycle_harness_apptest.py",
    "tests/test_streamlit_creative_full_production_harness_apptest.py",
    "tests/test_streamlit_generated_key_harness_apptest.py",
    "tests/test_generated_key_validation_and_key_labels.py",
    "tests/test_generated_key_streamlit_lifecycle.py",
    "tests/test_generated_jam_key_change_callback_integration.py",
    "tests/test_generated_key_projection_defer_canonical.py",
    "tests/test_music_workflow_commit4.py",
    "tests/test_music_workflow_commit5.py",
    "tests/test_music_workflow_commit6.py",
    "tests/test_music_workflow_commit7.py",
    "tests/test_music_workflow_activation.py",
    "tests/test_music_workflow_mutation.py",
    "tests/test_music_workflow_state_store.py",
    "tests/test_creative_page_dispatch_workflow_rerun.py",
    "tests/test_backing_workflow_context.py",
    "tests/test_backing_source_navigation.py",
    "tests/test_backing_track_state.py",
    "tests/test_backing_context.py",
    "tests/test_workflow_musical_authority.py",
    "tests/test_mission_backing_pre_widget_activation.py",
    "tests/test_mission_backing_envelope_orchestration.py",
    "tests/test_mission_return_from_backing_handoff.py",
    "tests/test_practice_in_backing_jam_handoff.py",
    "tests/test_mission_generate_example_no_backing_navigation.py",
    "tests/test_backing_nav_and_mission_spelling.py",
    "tests/test_mission_backing_alignment_and_rollback.py",
    "tests/test_mission_backing_handoff_navigation_persistence.py",
    "tests/test_missions_workflow_hotfix.py",
    "tests/test_display_key_sidebar_creative_projection.py",
    "tests/test_creative_artifact_global_key_guard.py",
    "tests/test_creative_session_state.py",
    "tests/test_creative_catalog_handoff_picker.py",
    "tests/test_creative_key_sync.py",
    "tests/test_suite_user_persistence.py",
    "tests/test_music_deploy_verification.py"
)

Write-Host "=== Creative owner regression run 1 ==="
python -m pytest @TestFiles -q -k "not test_entry_jam_context_from_style_meta and not test_resolve_sections_for_playback and not test_analysis_mode_default_when_unset and not test_hydrate_does_not_overwrite_live_mood_when_widget_safe"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "=== Creative owner regression run 2 ==="
python -m pytest @TestFiles -q -k "not test_entry_jam_context_from_style_meta and not test_resolve_sections_for_playback and not test_analysis_mode_default_when_unset and not test_hydrate_does_not_overwrite_live_mood_when_widget_safe"
exit $LASTEXITCODE
