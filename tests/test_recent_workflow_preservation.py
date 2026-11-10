from types import SimpleNamespace
from unittest.mock import patch
from home_recent_session import verified_recent_session
from home_activity_history import practice_entry_from_event
from music_conflict_notice import show_workspace_conflict_once


def test_conflicts_render_once_per_run_identity_and_remain_actionable():
    messages=[];state={'_script_run_seq':1,'_suite_active_workspace_id':'test','_music_stale_write_blocked':True,'_suite_persist_local_dirty::music':True}
    st=SimpleNamespace(session_state=state,warning=messages.append)
    for _ in range(4):show_workspace_conflict_once(st)
    assert len(messages)==1 and 'Refresh' in messages[0]
    assert state['_music_stale_write_blocked'] and state['_suite_persist_local_dirty::music']
    state['_script_run_seq']=2;show_workspace_conflict_once(st)
    state['_suite_active_workspace_id']='another';show_workspace_conflict_once(st)
    assert len(messages)==3


def test_verified_workflows_name_destinations_without_borrowing_live_context():
    for event,proof,kind,page in [('mission_started','progress_activity_id','mission practice','creative'),
                                  ('song_coaching_used','progress_activity_id','song-aware coaching','creative'),
                                  ('composition_saved','progress_activity_id','composition practice','composer'),
                                  ('multitrack_export_saved','export_id','multitrack/upload','multitrack'),
                                  ('audio_uploaded','recording_id','upload analysis','analysis')]:
        row={'app':'music','event':event,'timestamp':'2026-11-05T12:00:00Z',
             'metrics':{'activity_schema_version':3,proof:'verified-id','workspace_id':'test','song':'Saved song'}}
        entry=practice_entry_from_event(row)
        recent=verified_recent_session({'workspace_id':'test'},entries=[],activities=[row])
        assert entry['practice_type']==kind and recent.page==page
        assert recent.action_label().startswith('Go to ')
        assert not recent.instrument and not recent.key_parts
        row['metrics'].pop(proof)
        assert practice_entry_from_event(row) is None


def test_backing_record_retains_safe_saved_context():
    from home_practice_resume import prepare_restore, restore_recent_practice
    from song_catalog import format_pick_key
    catalog={'Jazz':{'All the Things You Are':{'title':'All the Things You Are','artist':'Kern','key':'Ab','sections':{'A':['Fm7','Bbm7']}}}}
    pick=format_pick_key('Jazz','All the Things You Are')
    record={'session_id':'backing-1','practice_type':'backing track','song_id':pick,'practice_concert_key':'Ab',
            'instrument':'Tenor Saxophone','workspace_id':'test',
            'resume_payload':{'workspace_id':'test','pick_key':pick,'backing_track_bpm':108,'backing_track_loops':3}}
    state={'workspace_id':'test','studio_page':'home','_music_workspace_blob_hydrated':True}
    plan,why=prepare_restore(record,state,catalog)
    assert plan is not None,why
    assert plan.payload['resume_kind']=='backing' and plan.payload['studio_page']=='backing'
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        ok,why=restore_recent_practice(state,record,catalog)
    assert ok,why
    assert state['studio_page']=='backing' and state['display_key']=='Ab'
    assert not state.get('_backing_autoplay')
    assert state['backing_track_bpm']==108


def test_multitrack_queue_uses_existing_loader_only_after_whole_workspace_hydrates():
    from home_practice_resume import queue_recent_project
    record={'session_id':'saved-export','practice_type':'multitrack/upload',
            'workspace_id':'test','multitrack_id':'durable-project'}
    state={'workspace_id':'test','_music_workspace_resume_context_confirmed':True}
    with patch('media_multitrack_catalog.queue_multitrack_project_catalog_load') as queue:
        assert not queue_recent_project(state,record)
        queue.assert_not_called()
        state['_music_workspace_blob_hydrated']=True
        assert queue_recent_project(state,record)
        queue.assert_called_once_with(state,'durable-project')
        assert not queue_recent_project(state,dict(record,workspace_id='other'))


def test_cloud_row_lookup_cannot_grant_write_authority_without_hydration():
    from copy import deepcopy
    from music_workspace_conditional_cloud_write import prepare_music_conditional_write
    from workspace_revision import APPLIED_REVISION_KEY
    state={'workspace_id':'test','_suite_persist_local_dirty::music':True}
    before=deepcopy(state)
    stored={'workspace_revision':5,'full_session':{'workspace_revision':5}}
    resolution={'device_applied_revision':0,'expected_revision':0,'create_path_allowed':False,'violations':[]}
    with patch('music_device_applied_revision.resolve_device_applied_revision_for_cas',return_value=resolution), \
         patch('music_workspace_conditional_cloud_write._authoritative_stored_metrics',return_value=(True,5,stored)):
        prep=prepare_music_conditional_write(state,{'workspace_revision':6})
    assert prep['blocked_precheck'] and prep['expected_revision']==0
    assert not state.get(APPLIED_REVISION_KEY)
    assert state==before


def test_incomplete_hydration_is_not_mislabeled_as_another_device_edit():
    from music_workspace_conditional_cloud_write import ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY, VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED
    state={ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY:[VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED]}
    messages=[]
    show_workspace_conflict_once(SimpleNamespace(session_state=state,warning=messages.append))
    assert 'not finished restoring' in messages[0] and 'another device' not in messages[0]
