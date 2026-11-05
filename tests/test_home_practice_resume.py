from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from home_practice_resume import prepare_restore,restore_recent_practice,finalize_recent_practice,REQUEST,STAGING
from song_catalog import format_pick_key

@pytest.fixture
def catalog():
    return {'Pop':{'Say — John Mayer':{'title':'Say','artist':'John Mayer','key':'G','sections':{'Verse':['G','C']}},'Shallow — Lady Gaga':{'title':'Shallow','artist':'Lady Gaga','key':'G','sections':{'Verse':['G','D']}}},'Jazz':{'All the Things You Are — Kern':{'title':'All the Things You Are','artist':'Kern','key':'Ab','sections':{'A':['Fm7','Bbm7']}}}}

def current():
    pick=format_pick_key('Pop','Say — John Mayer')
    return dict(workspace_id='guest',studio_page='home',active_music_source='catalog_song',active_catalog_pick_key=pick,selected_song={'title':'Say','artist':'John Mayer','key':'G','pick_key':pick},instrument='Piano',display_key='G',concert_key='G',concert_practice_key='G',_music_workspace_empty_confirmed=True)

def saved(pick=None,**kwargs):
    return dict(session_id='old-session',song_id=pick or format_pick_key('Pop','Shallow — Lady Gaga'),active_song='Shallow',workspace_id='guest',practice_concert_key='F',instrument='Alto Saxophone',practice_type='song practice',**kwargs)

@pytest.mark.parametrize('instrument,expected',[('Alto Saxophone','D'),('Tenor Saxophone','G')])
def test_restores_owner_and_calculates_written_key(catalog,instrument,expected):
    ss=current();entry=saved();entry['instrument']=instrument;before=deepcopy(entry)
    with patch('songs.state.persist_music_local_state') as persist,patch('suite_activity_client.record_activity') as activity:
        ok,why=restore_recent_practice(ss,entry,catalog)
    assert ok,why
    assert ss['selected_song']['title']=='Shallow'
    assert ss['active_catalog_pick_key']==entry['song_id']
    assert ss['active_music_source']=='catalog_song'
    assert ss['instrument']=='Saxophone'
    assert ss['display_key']=='F'
    assert ss['concert_practice_key']=='F'
    assert ss['selected_song']['key']=='G'
    from instrument_transposition import resolve_practice_keys
    assert resolve_practice_keys(ss,'F','Saxophone')['written_key']==expected
    assert ss.get(STAGING) is None
    assert entry==before
    assert not activity.called
    assert not persist.called

@pytest.mark.parametrize('patch_entry',[{'song_id':''},{'song_id':'missing::bad'},{'workspace_id':'ariel'},{'practice_concert_key':'garbage'},{'instrument':'Saxophone'},{'instrument':''},{'practice_concert_key':''},{'source_type':'custom'},{'deleted':True}])
def test_incomplete_missing_or_ambiguous_records_do_not_mutate(catalog,patch_entry):
    ss=current();before=deepcopy(ss);entry=saved();entry.update(patch_entry)
    assert restore_recent_practice(ss,entry,catalog)[0] is False
    assert ss==before

def test_all_the_things_focus_and_repeated_navigation(catalog):
    pick=format_pick_key('Jazz','All the Things You Are — Kern');entry=saved(pick,focus_area='Improvisation');ss=current()
    from app_ui import navigate_studio_page
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        assert restore_recent_practice(ss,entry,catalog)[0]
    for page in ['picker','practice','backing','home']:
        navigate_studio_page(ss,page)
        assert ss['active_catalog_pick_key']==pick
        assert ss['display_key']=='F'
        assert ss['focus']=='Improvisation'
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        assert restore_recent_practice(ss,entry,catalog)[0]

def test_failed_activation_rolls_back_before_publication(catalog):
    ss=current();before=deepcopy(ss)
    def failed(stage,*args,**kwargs):stage['display_key']='C';stage['instrument']='Guitar';return False
    with patch('music_resume_payload.apply_music_resume_payload',side_effect=failed):
        assert restore_recent_practice(ss,saved(),catalog)[0] is False
    assert ss==before

def test_finalization_waits_for_hydration_and_persists_once(catalog):
    ss=current();ss.pop('_music_workspace_empty_confirmed');ss[REQUEST]=saved();before=deepcopy(ss)
    with patch('songs.state.persist_music_local_state') as persist:
        assert not finalize_recent_practice(SimpleNamespace(session_state=ss),catalog)
        assert ss==before
        ss['_music_workspace_empty_confirmed']=True
        assert finalize_recent_practice(SimpleNamespace(session_state=ss),catalog)
        # Only the final, published state is saved; activation's staged write is suppressed.
        assert persist.call_count==1
        assert not finalize_recent_practice(SimpleNamespace(session_state=ss),catalog)

def test_guitar_shape_capo(catalog):
    ss=current();entry=saved();entry.update(instrument='Guitar',practice_concert_key='A',guitar_shape_key='G',capo_fret=2)
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        ok,why=restore_recent_practice(ss,entry,catalog)
    assert ok,why
    assert ss['display_key']=='A'
    assert ss['guitar_capo_shape_key']=='G'
    assert ss['guitar_capo_fret']==2
    from instrument_transposition import resolve_practice_keys
    assert resolve_practice_keys(ss,'A','Guitar')['chart_key']=='G'

@pytest.mark.parametrize('source',['custom','composition'])
def test_restore_saved_non_catalog_resource_through_owner_contract(catalog,source):
    ss=current()
    if source=='custom':
        from custom_progression_lab import default_active_progression
        from songs.music_source import custom_pick_key_for
        doc=default_active_progression();doc.update(id='saved-custom',name='Saved Custom',original_key_center='C',user_locked_home_key=True)
        doc['original_sections']['Verse']=[{'chord':'C','bars':1}]
        ss['cpl_saved_progressions']={'Saved Custom':doc}
        pick=custom_pick_key_for(doc)
    else:
        from composition_document import new_composition_document,ensure_workflow
        doc=new_composition_document(title='Saved Composition');ensure_workflow(doc)
        ss['composer_saved_compositions']={doc['id']:doc}
        pick='composition::'+doc['id']
    entry=saved(pick);entry.update(instrument='Piano',practice_concert_key='Eb')
    with patch('music_persistent_state.flush_active_song_edits_and_save') as flush,patch('suite_activity_client.record_activity'):
        ok,why=restore_recent_practice(ss,entry,catalog)
        assert not flush.called  # Nothing was persisted during staging.
    assert ok,why
    assert ss['active_catalog_pick_key']==pick
    assert ss['active_music_source']==('custom_progression' if source=='custom' else 'composition_song')
    assert ss['instrument']=='Piano'
    assert ss['display_key']=='Eb'
    from app_ui import navigate_studio_page
    from studio_page_persistence import handle_studio_page_transition
    for page in ['picker','practice','backing']:
        navigate_studio_page(ss,page);handle_studio_page_transition(ss)
        assert ss['active_catalog_pick_key']==pick
        assert ss['display_key']=='Eb'


def test_stale_page_snapshots_cannot_restore_an_old_song_or_key(catalog):
    ss=current();ss['_studio_page_snapshots']={'picker':{'selected_song':ss['selected_song'],'matching_song_dropdown':ss['active_catalog_pick_key'],'display_key':'G'},'backing':{'display_key':'G','instrument':'Guitar','display_key_catalog_backing':'G'}}
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        assert restore_recent_practice(ss,saved(),catalog)[0]
    from app_ui import navigate_studio_page
    from studio_page_persistence import handle_studio_page_transition,restore_current_page_snapshot_if_needed
    for page in ['picker','practice','backing']:
        navigate_studio_page(ss,page);handle_studio_page_transition(ss);restore_current_page_snapshot_if_needed(ss)
        assert ss['active_catalog_pick_key']==saved()['song_id']
        assert ss['display_key']=='F'
        assert ss['instrument']=='Saxophone'


def test_failure_after_activation_does_not_write_or_publish(catalog):
    ss=current();before=deepcopy(ss)
    with patch('music_persistent_state.flush_active_song_edits_and_save') as flush,patch('practice_setup_globals.set_active_instrument',side_effect=RuntimeError('injected validation failure')):
        assert not restore_recent_practice(ss,saved(),catalog)[0]
        assert not flush.called
    assert ss==before


def test_normalized_log_focus_maps_through_existing_registry(catalog):
    entry=saved(focus_area='soloing/improv');ss=current()
    plan,why=prepare_restore(entry,ss,catalog)
    assert plan is not None,why
    assert plan.focus=='Improvisation'


def test_real_catalog_with_existing_catalog_owner_restores_jazz_record():
    from song_catalog import load_song_catalog
    from songs.state import activate_active_song_by_pick_key
    lib,cat,*_=load_song_catalog();ss=current();proxy=SimpleNamespace(session_state=ss)
    say=format_pick_key('Pop','Say \u2014 John Mayer')
    jazz=next(format_pick_key(g,n) for g,rows in cat.items() for n,r in rows.items() if r.get('title')=='All the Things You Are')
    ss[STAGING]=True
    assert activate_active_song_by_pick_key(proxy,say,cat,song_library=lib,origin='user')
    ss.pop(STAGING)
    from active_song_state import gather_active_song_context,write_canonical_active_song_blob_only,commit_active_song_state_from_session
    write_canonical_active_song_blob_only(ss,gather_active_song_context(ss))
    entry=saved(jazz);entry.update(instrument='Tenor Saxophone',practice_concert_key='Eb',focus_area='soloing/improv')
    ok,why=restore_recent_practice(ss,entry,cat,lib)
    assert ok,why
    commit_active_song_state_from_session(ss)
    assert ss['active_song_state']['pick_key']==jazz
    assert ss['selected_song']['title']=='All the Things You Are'
    assert ss['selected_song']['pick_key']==jazz
    assert ss['selected_song']['key']=='Ab'
    from app_ui import navigate_studio_page
    from studio_page_persistence import handle_studio_page_transition
    for page in ['picker','practice','backing']:
        navigate_studio_page(ss,page);handle_studio_page_transition(ss)
        assert ss['selected_song']['pick_key']==jazz
        assert ss['display_key']=='Eb'


def test_new_activity_captures_sax_subtype_for_genuine_repeated_resume(catalog):
    import music_activity
    from home_activity_history import practice_entry_from_event
    ss=current()
    assert restore_recent_practice(ss,saved(focus_area='Improvisation'),catalog)[0]
    with patch('music_activity._record') as record:
        assert music_activity.log_practice_session_started(SimpleNamespace(session_state=ss))
    m={**music_activity._song_context(SimpleNamespace(session_state=ss)),**record.call_args.kwargs['metrics'], 'workspace_id':'guest'}
    event={'event':'practice_session_started','timestamp':'2026-11-05T12:00:00Z','metrics':m}
    entry=practice_entry_from_event(event)
    plan,why=prepare_restore(entry,ss,catalog)
    assert plan is not None,why
    assert plan.transposing_type=='Alto saxophone (Eb)'
    assert plan.focus=='Improvisation'
    assert plan.payload['display_key']=='F'


def test_recent_context_alone_cannot_replace_whole_workspace(catalog):
    ss=current();ss.pop('_music_workspace_empty_confirmed')
    ss['_music_workspace_resume_context_confirmed']=True
    ss[REQUEST]=saved();before=deepcopy(ss)
    with patch('songs.state.persist_music_local_state') as persist:
        assert not finalize_recent_practice(SimpleNamespace(session_state=ss),catalog)
    assert ss==before
    persist.assert_not_called()


def test_hydrated_rerun_does_not_clear_unsaved_user_changes():
    from music_workspace_restore_mode import prepare_music_cold_start_restore
    ss={'_music_workspace_blob_hydrated':True,'_music_user_edit_tracking_enabled':True,
        '_suite_persist_local_dirty::music':True,'_active_song_local_edit':True}
    before=deepcopy(ss);prepare_music_cold_start_restore(ss,'music')
    assert ss==before


def test_catalog_resume_preserves_saved_projects_and_inactive_source_selections(catalog):
    from custom_progression_lab import default_active_progression
    doc=default_active_progression();doc.update(id='trial',name='Trial Song',original_key_center='Eb')
    doc['original_sections']['Verse']=[{'chord':'Eb','bars':1}]
    protected={'cpl_saved_progressions':{'Trial Song':doc,'Other':dict(doc,id='other')},
               'cpl_active_progression':doc,'cpl_last_display_key':'Bb',
               'composer_saved_compositions':{'piece':{'id':'piece','title':'My piece','key':'D'}},
               'composer_active_document':{'id':'piece','title':'My piece','key':'D'},
               'mt_tracks':[{'id':'tenor-layer','audio':b'fixture-audio'}],
               'mt_track_filenames':['tenor.wav'],'mixed_track_wav':b'fixture-mix',
               'last_analysis_result':{'id':'take-1'},'practice_minutes':45}
    ss=current();ss.update(deepcopy(protected))
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'):
        ok,why=restore_recent_practice(ss,saved(),catalog)
    assert ok,why
    assert {key:ss.get(key) for key in protected}==protected
