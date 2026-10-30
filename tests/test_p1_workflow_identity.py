from types import SimpleNamespace
from unittest.mock import patch

from practice_log_state import _new_entry_fields
from practice_log_activity import report_practice_log_saved
from recording_activity import capture_upload, report_recording_fact

GLOBAL = dict(active_catalog_pick_key="catalog-a", selected_song={"title":"Song A", "artist":"Artist A"},
              instrument="Saxophone", display_key="Cm", studio_page="log")


def test_freeform_log_is_neutral_after_catalog():
    row = _new_entry_fields(GLOBAL, {"active_song":"QA History Entry", "instrument":"Flute"})
    assert row["active_song"] == "QA History Entry"
    assert row["instrument"] == "Flute"
    for key in ("song_id", "artist", "source_id", "display_key", "original_key"):
        assert not row.get(key)


def test_explicit_linked_log_keeps_its_owner():
    row = _new_entry_fields(GLOBAL, dict(active_song="Song B", song_id="catalog-b", artist="Artist B",
                                       instrument="Guitar", practice_concert_key="D"))
    assert row["song_id"] == "catalog-b"
    assert row["instrument"] == "Guitar"
    assert row["practice_concert_key"] == "D"


def test_log_activity_has_no_global_state_or_resume():
    st = SimpleNamespace(session_state=GLOBAL)
    with patch("suite_activity_client.record_activity") as record:
        assert report_practice_log_saved(st, dict(active_song="QA History Entry", instrument="Flute",session_id="log-b"))
    args, kw = record.call_args
    assert args == ("music", "practice_log_saved")
    assert kw["metrics"]["instrument"] == "Flute"
    assert not kw["metrics"]["pick_key"]
    assert "resume_key" not in kw and "local_state" not in kw


def test_log_reporting_failure_is_nonblocking():
    with patch("suite_activity_client.record_activity", side_effect=RuntimeError("offline")):
        assert not report_practice_log_saved(SimpleNamespace(session_state=GLOBAL), {"active_song":"B"})


def test_upload_snapshot_owns_later_review():
    session = dict(GLOBAL)
    snapshot = dict(song_source_type="Composed Song",song_source_id="river-id",song_source_name="River Sketch",
                    instruments=["Guitar"],recording_concert_key="Eb")
    with patch("recording_analysis_context.build_analysis_context_snapshot", return_value=snapshot):
        context = capture_upload(session, filename="river.wav")
    session.update(song="QA History Entry",instrument="Flute")
    with patch("suite_activity_client.record_activity") as record:
        assert report_recording_fact(SimpleNamespace(session_state=session), "recording_reviewed",context,page="Recording Analysis")
    m=record.call_args.kwargs["metrics"]
    assert (m["song"],m["instrument"],m["source_id"]) == ("River Sketch","Guitar","river-id")
    assert m["recording_id"] and m["review_status"] == "reviewed"


def test_upload_reporting_failure_is_nonblocking():
    with patch("suite_activity_client.record_activity", side_effect=RuntimeError("offline")):
        assert not report_recording_fact(SimpleNamespace(session_state=GLOBAL),"audio_uploaded",{},page="analysis")


def test_explicit_log_does_not_fill_missing_metadata_from_other_resource():
    row=_new_entry_fields(GLOBAL,dict(active_song="Song B",song_id="b",instrument="Flute"))
    assert not row.get("artist") and not row.get("display_key")


def test_analysis_handoff_owns_history_not_active_catalog():
    from practice_log_analysis_handoff import submit_practice_analysis_command_center_handoff
    from unittest.mock import MagicMock
    data=dict(practice_log_summary={"session_count":1},recent_sessions=[dict(session_id="b",active_song="QA History Entry",instrument="Flute")],safety_checks={})
    captured={}
    def send(**kwargs):
        captured.update(kwargs)
        return dict(handoff_success=False,context=kwargs["context"])
    with patch("practice_log_ami.build_practice_log_ami_payload",return_value=data),patch("practice_history_synthesis.store_latest_practice_analysis"),patch("suite_analytical_question.submit_practice_log_analysis_handoff",side_effect=send),patch("music_persistent_state.force_save_music_state"),patch("practice_log_analysis_handoff._command_center_activity_count",return_value=None):
        result=submit_practice_analysis_command_center_handoff(MagicMock(),dict(GLOBAL),entries=[])
    assert not result["handoff_success"]
    assert captured["context"]["recent_sessions"][0]["instrument"] == "Flute"
    assert "song" not in captured["context"] and "instrument" not in captured["context"]
    assert captured["source_state"] == {"studio_page":"log","page":"log"}


def test_analysis_report_survives_unexpected_reporting_exception():
    from practice_log_analysis_handoff import submit_practice_analysis_command_center_handoff
    from unittest.mock import MagicMock
    data=dict(practice_log_summary={},recent_sessions=[],safety_checks={})
    with patch("practice_log_ami.build_practice_log_ami_payload",return_value=data),patch("practice_history_synthesis.store_latest_practice_analysis") as store,patch("suite_analytical_question.submit_practice_log_analysis_handoff",side_effect=OSError("offline")),patch("music_persistent_state.force_save_music_state"),patch("practice_log_analysis_handoff._command_center_activity_count",return_value=None):
        result=submit_practice_analysis_command_center_handoff(MagicMock(),dict(GLOBAL),entries=[])
    assert store.call_count == 2
    assert not result["handoff_success"] and result["handoff_error"] == "offline"


def test_recording_review_does_not_read_new_global_instrument():
    from music_activity import log_recording_reviewed
    session=dict(GLOBAL,_activity_recording_context=dict(recording_id="river",song="River Sketch",instrument="Guitar",source_id="river-id"))
    with patch("recording_activity.report_recording_fact") as record:
        log_recording_reviewed(SimpleNamespace(session_state=session))
    assert record.call_args.args[2]["instrument"] == "Guitar"


def test_explicit_uuid_source_owner_is_preserved_in_log_event():
    with patch("suite_activity_client.record_activity") as record:
        assert report_practice_log_saved(SimpleNamespace(session_state=GLOBAL),dict(active_song="River Sketch",source_id="river-uuid",source_type="composition",instrument="Guitar"))
    m=record.call_args.kwargs["metrics"]
    assert (m["source_type"],m["source_id"]) == ("composition","river-uuid")


from tests.test_cold_entry_resource_preservation import storage


def test_analysis_save_after_cold_resume_preserves_new_context_and_libraries(storage):
    from tests.test_music_source_resume_lifecycle import seed,launch,finalize,preserved,apply,read
    from music_entry_workspace import hydrate_entry_workspace
    from music_persistent_state import force_save_music_state
    from practice_history_synthesis import store_latest_practice_analysis
    from suite_user_persistence import _autosave_block_key
    import suite_user_persistence as disk
    before=seed();disk.save_user_state("music",before,workspace_id="daniel")
    st,p=launch(before,"custom")
    from suite_resume_launch import apply_suite_resume_launch
    apply_suite_resume_launch(st,"music");assert hydrate_entry_workspace(st,apply_state=apply);assert finalize(st)
    st.session_state[_autosave_block_key("music")]=True
    store_latest_practice_analysis(st.session_state,dict(practice_log_summary=dict(entry_count_total=1,practice_time_by_instrument={"Flute":30},practice_time_by_song={"QA History Entry":30}),progress_report={"executive_summary":"QA History Entry with Flute"}))
    assert force_save_music_state(st,reason="practice_analysis"),st.session_state.get("_music_workspace_save_transaction")
    saved=read()
    assert saved["session"]["latest_practice_analysis_evidence_counts"]["top_instrument"] == "Flute"
    preserved(before,saved)
