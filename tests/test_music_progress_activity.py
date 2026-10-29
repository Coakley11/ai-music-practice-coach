from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest

import music_progress_activity as progress
from composition_document import new_composition_document
from song_coach_context import SongCoachContext, global_song_identity, source_owner
from song_coach_plan import FOCUS_CHORD_TONE


def context(source):
    pick = {'catalog': 'Pop\x1fShape of You', 'custom': 'custom::trial', 'composition': 'composition::draft'}[source]
    session = dict(active_music_source={'catalog':'catalog_song','custom':'custom_progression','composition':'composition_song'}[source],
                   active_catalog_pick_key=pick, workspace_id='qa', song='STALE Catalog', display_key='F#m')
    if source == 'custom':
        session['cpl_active_progression'] = dict(id='trial',name='Own custom',original_key_center='C')
    if source == 'composition':
        doc = new_composition_document(title='Own composition'); doc['id']='draft'
        session['composer_active_document']=doc
    assert source_owner(session) == source
    ctx = SongCoachContext(available=True,identity=global_song_identity(session,source),source_kind=source,
                           song_title='Own title',instrument='Saxophone',concert_key='Cm',chart_key='Am')
    return session,ctx


@pytest.mark.parametrize('source',['catalog','custom','composition'])
def test_real_owner_metadata_and_session_dedup_without_content(source):
    session,ctx=context(source)
    session.update(prompt='PRIVATE PROMPT',response='PRIVATE RESPONSE',lyrics='PRIVATE LYRICS',
                   song_coach_session={'transcript':'PRIVATE TRANSCRIPT'})
    mission='Target only guide tones (3rds & 7ths)'
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert progress.report_mission_started(session,ctx,mission)
        assert not progress.report_mission_started(session,ctx,mission)
        assert progress.report_coaching_used(session,ctx,FOCUS_CHORD_TONE)
        assert not progress.report_coaching_used(session,ctx,FOCUS_CHORD_TONE)
    assert submit.call_count == 2
    for call in submit.call_args_list:
        event,kwargs=call.args
        assert event != 'mission_completed'  # app has no authoritative completion state
        m=kwargs['metrics']
        assert m['song']=='Own title' and m['source_type']==source
        assert m['practice_key']=='Cm'
        if source=='catalog':
            assert m['resume_payload']['display_key']=='Cm'
            assert m['resume_payload']['pick_key']==session['active_catalog_pick_key']
        else:
            assert 'resume_payload' not in m
        assert kwargs['local_state'] is None
        assert 'PRIVATE' not in json.dumps(kwargs)
        assert 'STALE' not in json.dumps(kwargs) and 'F#m' not in json.dumps(kwargs)



@pytest.mark.parametrize('source',['catalog','custom','composition'])
def test_stale_coaching_context_rejected_after_song_switch(source):
    session,ctx=context(source)
    session['active_catalog_pick_key']='Pop\x1fNew Song'
    session['active_music_source']='catalog_song'
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert not progress.report_coaching_used(session,ctx,FOCUS_CHORD_TONE)
    submit.assert_not_called()


def test_unknown_mission_focus_or_unavailable_context_never_emits():
    session,ctx=context('catalog')
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert not progress.report_mission_started(session,ctx,'Invented completion')
        assert not progress.report_coaching_used(session,ctx,'PRIVATE arbitrary focus')
        assert not progress.report_coaching_used(session,SongCoachContext(available=False),FOCUS_CHORD_TONE)
    submit.assert_not_called()


def test_composition_save_content_changes_only_and_no_stale_owner():
    session,_=context('catalog')
    doc=new_composition_document(title='River Sketch')
    sid=doc['form']['section_order'][0]
    doc['form']['sections'][sid]['lyrics']['raw_text']='PRIVATE LYRICS'
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert not progress.report_composition_saved(session,doc,durable=False)
        assert progress.report_composition_saved(session,doc,durable=True)
        doc['updated_at']='later';doc['workflow']={'current_phase':'lyrics'}
        assert not progress.report_composition_saved(session,doc,durable=True)
        doc['form']['sections'][sid]['melody']['events']=[{'pitch':67,'duration':1}]
        assert progress.report_composition_saved(session,doc,durable=True)
        newer=new_composition_document(title='New Song')
        assert progress.report_composition_saved(session,newer,durable=True)
    records=[c.args[1]['metrics'] for c in submit.call_args_list]
    assert [m['composition_milestone'] for m in records]==['saved','updated','saved']
    assert records[0]['source_id']=='composition::'+doc['id']
    assert records[2]['song']=='New Song'
    assert 'PRIVATE' not in json.dumps(records)
    assert 'melody' not in json.dumps(records) and 'pitch' not in json.dumps(records)
    assert all('resume_payload' not in m for m in records)
    assert session['active_music_source']=='catalog_song'  # reporting does not activate a document


def test_same_saved_document_has_stable_delivery_identity_after_refresh():
    doc=new_composition_document(title='River Sketch')
    with patch('music_activity.submit_activity_snapshot') as submit:
        progress.report_composition_saved({'workspace_id':'qa'},doc,durable=True)
        progress.report_composition_saved({'workspace_id':'qa'},deepcopy(doc),durable=True)
    assert submit.call_args_list[0].args[1]['metrics']['progress_activity_id']==submit.call_args_list[1].args[1]['metrics']['progress_activity_id']


@pytest.mark.parametrize('kind',['mission','coaching','composition'])
def test_submission_exception_is_contained(kind):
    session,ctx=context('catalog')
    with patch('music_activity.submit_activity_snapshot',side_effect=OSError('offline')):
        if kind=='mission':
            assert not progress.report_mission_started(session,ctx,'Improvise using only chord tones')
        elif kind=='coaching':
            assert not progress.report_coaching_used(session,ctx,FOCUS_CHORD_TONE)
        else:
            assert not progress.report_composition_saved(session,new_composition_document(),durable=True)
    assert session['active_catalog_pick_key'].startswith('Pop')


@pytest.mark.parametrize('destination',['missions','coaching'])
def test_progress_resume_real_dispatch_and_stopped_transport(destination):
    from music_resume_payload import apply_music_resume_payload
    from song_catalog import format_pick_key
    from songs.practice_key_state import get_practice_concert_key
    doc=new_composition_document(title='River Sketch')
    pick='composition::'+doc['id'] if destination=='composition' else format_pick_key('Pop','Shape of You — Ed Sheeran')
    session=dict(active_music_source='custom_progression',active_catalog_pick_key='custom::old',
                 composer_saved_compositions={doc['id']:doc},workspace_id='qa',
                 _backing_autoplay=True,_kc_restart_play=True,display_key='F#m')
    payload=dict(progress_activity_id='progress-1',activity_destination=destination,pick_key=pick,song='Old activity title',
                 resume_kind='creative' if destination!='composition' else 'practice',
                 studio_page='creative' if destination!='composition' else 'composer',
                 instrument='Saxophone',display_key='G' if destination=='composition' else 'Cm',workspace_id='qa',
                 mission='Target only guide tones (3rds & 7ths)')
    catalog={'Pop':{'Shape of You — Ed Sheeran':dict(title='Shape of You',artist='Ed Sheeran',key='Bm',sections={'Verse':['Bm','G','D','A']})}}
    with patch('songs.state.persist_music_local_state'),patch('suite_activity_client.record_activity'),patch('composition_workspace_state_persistence.checkpoint_composition_workspace'):
        assert apply_music_resume_payload(session,payload,song_picker_catalog=catalog)
    assert session['active_catalog_pick_key']==pick
    assert session['song']==('River Sketch' if destination=='composition' else 'Shape of You')
    assert session['studio_page']==payload['studio_page']
    assert get_practice_concert_key(session,pick)==payload['display_key']
    assert session['_backing_transport_intent']=='stopped'
    session.setdefault('_backing_autoplay', True)  # production Creative bootstrap default
    assert session['_backing_autoplay'] is False and not session.get('_kc_restart_play')
    from backing_track_state import _apply_filters_to_session_keys
    _apply_filters_to_session_keys(session, {'backing_autoplay': True})
    assert session['_backing_autoplay'] is False  # later snapshot hydration cannot re-arm it
    if destination=='composition':
        assert session['composer_active_document']['id']==doc['id']
    else:
        assert session['improv_intelligence_tab']==('Missions' if destination=='missions' else 'Song-Aware Coaching')


@pytest.mark.parametrize('source',['catalog','custom','composition'])
def test_mission_snapshot_uses_owner_document_not_collapsed_chart_or_sidebar_title(source):
    session,ctx=context(source)
    if source=='catalog':
        session['selected_song']=dict(pick_key=session['active_catalog_pick_key'],title='Own catalog',key='Cm')
    snapshot=progress.mission_activity_context(session)
    assert snapshot.source_kind==source
    assert snapshot.identity==ctx.identity
    assert 'STALE' not in snapshot.song_title
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert progress.report_mission_started(session,snapshot,'Improvise using only chord tones')
    assert submit.call_args.args[1]['metrics']['source_type']==source


def test_missing_source_resume_fails_without_selecting_stale_song():
    from music_resume_payload import apply_music_resume_payload
    session=dict(workspace_id='qa',active_catalog_pick_key='custom::prior')
    payload=dict(progress_activity_id='a',workspace_id='qa',pick_key='composition::missing',
                 activity_destination='composition',studio_page='composer',resume_kind='practice')
    with patch('suite_activity_client.record_activity'):
        assert not apply_music_resume_payload(session,payload,song_picker_catalog={})
    assert session['active_catalog_pick_key']=='custom::prior'


@pytest.mark.parametrize('source',['custom','composition'])
def test_editor_document_mismatch_cannot_attach_progress_to_previous_owner(source):
    session,ctx=context(source)
    key='cpl_active_progression' if source=='custom' else 'composer_active_document'
    session[key]['id']='different-document'
    with patch('music_activity.submit_activity_snapshot') as submit:
        assert not progress.report_coaching_used(session,ctx,FOCUS_CHORD_TONE)
        assert not progress.report_mission_started(session,progress.mission_activity_context(session),'Improvise using only chord tones')
    submit.assert_not_called()
