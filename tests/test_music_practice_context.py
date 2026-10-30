from types import SimpleNamespace
from unittest.mock import patch
import pytest
import music_activity as activity
from backing_transport_intent import begin_playback, pause_playback, continue_playback, stop_playback


def state(source='catalog'):
    pick = {'catalog': 'Pop|Shape of You', 'custom': 'custom::trial', 'composition': 'composition::trial'}[source]
    return SimpleNamespace(session_state=dict(studio_page='backing', song='Shape of You',
        active_song_title='Shape of You', active_catalog_pick_key=pick,
        instrument='Saxophone', display_key='Cm', active_music_source=source))


@pytest.mark.parametrize('source', ['catalog', 'custom', 'composition'])
def test_context_upgrades_survive_transport_and_cycle_churn(source):
    st = state(source)
    cycle = {'key_cycling_active': False}
    with patch.object(activity, '_key_cycling_context', side_effect=lambda _: dict(cycle)), patch.object(activity, '_record') as record:
        activity.log_practice_session_started(st)
        first_id = record.call_args.kwargs['metrics']['practice_context_id']
        begin_playback(st.session_state)
        activity.log_practice_session_started(st, backing_active=True)
        cycle.update(key_cycling_active=True, key_cycling_start_key='Dm')
        activity.log_practice_session_started(st, backing_active=True)
        for key in ['Dm', 'Ebm', 'Em', 'Fm', 'F#m']:
            cycle['key_cycling_sounding_key'] = key
            assert not activity.log_practice_session_started(st, backing_active=True)
        for command in [pause_playback, continue_playback, stop_playback, begin_playback]:
            command(st.session_state)
            st.session_state['backing_track_bpm'] = 110
            st.session_state['backing_groove_style'] = 'Swing'
            assert not activity.log_practice_session_started(st, backing_active=True)
        cycle['key_cycling_active'] = False
        assert not activity.log_practice_session_started(st)
        cycle['key_cycling_active'] = True
        cycle['key_cycling_start_key'] = 'Fm'
        assert not activity.log_practice_session_started(st, backing_active=True)
    assert record.call_count == 3
    for call in record.call_args_list:
        m = call.kwargs['metrics']
        assert m['practice_context_id'] == first_id
        assert m['practice_key'] == 'Cm'
        assert 'duration' not in m and 'keys_practiced_count' not in m
    assert record.call_args.kwargs['metrics']['key_cycling_start_key'] == 'Dm'
    assert st.session_state['display_key'] == 'Cm'


def test_source_switch_and_instrument_key_changes_are_new_contexts():
    st = state()
    with patch.object(activity, '_record') as record:
        for change in [{}, {'active_catalog_pick_key':'custom::trial', 'active_music_source':'custom'},
                       {'active_catalog_pick_key':'composition::trial', 'active_music_source':'composition'},
                       {'instrument':'Piano'}, {'display_key':'Gm'}]:
            st.session_state.update(change)
            assert activity.log_practice_session_started(st)
    ids = [c.kwargs['metrics']['practice_context_id'] for c in record.call_args_list]
    assert len(set(ids)) == 5


def test_observer_is_async_and_failure_isolated():
    st = state()
    begin_playback(st.session_state)
    executor = SimpleNamespace(submit=lambda *a, **k: None)
    with patch.object(activity, '_ACTIVITY_EXECUTOR', executor), patch('backing_key_cycle.resolve_cycle_owner', return_value='catalog'), patch('backing_key_cycle.current_backing_owner_practice_key', return_value='Cm'):
        assert activity.observe_backing_practice(st)
        assert not activity.observe_backing_practice(st)
        pause_playback(st.session_state)
        assert not activity.observe_backing_practice(st)
    with patch('backing_transport_intent.playback_allowed', side_effect=RuntimeError('CC unavailable')):
        assert not activity.observe_backing_practice(st)
    assert st.session_state['display_key'] == 'Cm'


def test_resume_metadata_uses_canonical_key():
    st = state()
    with patch('suite_activity_client.record_activity') as record, patch('music_command_center.upsert_music_continue_card'):
        activity._record('practice_session_started', st=st, metrics=dict(
            practice_context_id='abc', source_type='catalog', source_id='Pop|Shape of You',
            practice_key='Cm', key_cycling_sounding_key='F#m'))
    payload = record.call_args.kwargs['metrics']['resume_payload']
    assert payload['display_key'] == 'Cm'
    assert 'key_cycling_sounding_key' not in payload


@pytest.mark.parametrize('source', ['catalog', 'custom', 'composition'])
def test_resume_uses_owner_dispatcher_and_stops_audio(source):
    from music_resume_payload import apply_music_resume_payload
    st = state(source)
    pick = st.session_state['active_catalog_pick_key']
    st.session_state.update(active_catalog_pick_key='stale', _backing_autoplay=True,
        _backing_play_request=True, _kc_restart_play=True,
        _backing_key_cycle_sessions={'catalog':{'current_playback_key':'F#m'}})
    begin_playback(st.session_state)
    def activate(proxy, selected, *args, **kwargs):
        proxy.session_state['active_catalog_pick_key'] = selected
        proxy.session_state['active_music_source'] = source
        return {'pick_key':selected}
    payload = dict(practice_context_id='abc', pick_key=pick, display_key='Cm',
        resume_kind='backing', studio_page='backing', instrument='Saxophone')
    with patch('songs.state.activate_active_song_by_pick_key', side_effect=activate) as dispatch, \
         patch('songs.state.resolve_pick_key',return_value=pick), \
         patch('songs.music_source.custom_progression_for_pick_key',return_value={'id':'trial'}), \
         patch('composition_songs_bridge.find_composition_document',return_value={'id':'doc'}):
        assert apply_music_resume_payload(st.session_state, payload, st=st)
    dispatch.assert_called_once()
    assert st.session_state['active_catalog_pick_key'] == pick
    assert st.session_state['_backing_transport_intent'] == 'stopped'
    assert not st.session_state.get('_backing_autoplay')
    assert not st.session_state['_backing_key_cycle_sessions']
    assert st.session_state['studio_page'] == 'backing'


def test_resume_missing_source_does_not_claim_success():
    from music_resume_payload import apply_music_resume_payload
    st = state()
    with patch('songs.state.activate_active_song_by_pick_key', return_value={}):
        assert not apply_music_resume_payload(st.session_state,
            dict(practice_context_id='abc', pick_key='custom::missing'))

def test_deferred_resume_ignores_stale_early_pick_and_waits_for_activation():
    from music_resume_payload import encode_payload_b64
    from suite_resume_launch import apply_suite_resume_launch, finalize_suite_resume_launch
    st = state()
    st.query_params = dict(suite_page='backing', suite_resume='backing:custom::trial',
        suite_resume_payload=encode_payload_b64(dict(practice_context_id='abc',
            pick_key='custom::trial', display_key='Dm', resume_kind='backing', studio_page='backing')))
    with patch('suite_workspace.init_suite_workspace'):
        assert apply_suite_resume_launch(st, 'music')
    assert st.session_state['active_catalog_pick_key'] == 'Pop|Shape of You'
    def activate(proxy, pick, *args, **kwargs):
        proxy.session_state['active_catalog_pick_key'] = pick
        return {'pick_key':pick}
    with patch('songs.state.activate_active_song_by_pick_key') as activate_before_hydration:
        assert not finalize_suite_resume_launch(st, 'music')
        activate_before_hydration.assert_not_called()
        assert '_suite_activity_resume_pending' in st.session_state
    st.session_state['_music_entry_workspace_ready'] = True
    with patch('songs.state.activate_active_song_by_pick_key', side_effect=activate), \
         patch('songs.music_source.custom_progression_for_pick_key',return_value={'id':'trial'}):
        assert finalize_suite_resume_launch(st, 'music')
    assert st.session_state['active_catalog_pick_key'] == 'custom::trial'
    assert st.session_state['_pending_display_key'] == 'Dm'
    assert st.session_state['_backing_transport_intent'] == 'stopped'

def test_background_activity_never_saves_source_snapshot():
    st = state()
    with patch('suite_activity_client.record_activity') as record, patch('music_command_center.upsert_music_continue_card'):
        activity._record('practice_session_started', st=st,
            metrics=dict(practice_context_id='abc',practice_key='Cm',source_id='song',source_type='catalog'))
    assert record.call_args.kwargs['local_state'] is None
    assert record.call_args.kwargs['metrics']['workspace_id']


def test_key_cycle_context_off_backing_does_not_reanimate_sticky_owner():
    st = state()
    st.session_state.update(studio_page='practice', _backing_key_cycle_sessions={
        'catalog':dict(enabled=True,status='running',current_playback_key='F#m')})
    assert activity._key_cycling_context(st) == {'key_cycling_active':False}

@pytest.mark.parametrize('condition,ready', [('_mounted and _page_autoplay',True),
    ('_mounted and _page_autoplay',False),('_ls_autoplay and _ls_take',True),
    ('_ls_autoplay and _ls_take',False),('not want_pause',True),('not want_pause',False)])
def test_production_audio_mount_guards(condition,ready):
    import ast
    from pathlib import Path
    filename = 'backing_key_cycle.py' if condition == 'not want_pause' else 'streamlit_music_practice_app.py'
    tree = ast.parse(Path(filename).read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n,ast.If)
        and ast.unparse(n.test) == condition and any(isinstance(x,ast.ImportFrom)
            and x.module == 'music_activity' for x in ast.walk(n)))
    st = state()
    env = dict(st=st,_mounted=ready,_page_autoplay=True,_ls_autoplay=True,
        _ls_take='audio' if ready else '',want_pause=not ready)
    with patch.object(activity,'observe_backing_practice') as observe:
        exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),env)
        assert observe.call_count == int(ready)
    if ready:
        with patch.object(activity,'observe_backing_practice',side_effect=RuntimeError('offline')):
            exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),env)

@pytest.mark.parametrize('prior_source', ['catalog_song', 'custom_progression', 'composition_song'])
def test_catalog_activity_resume_runs_real_activation_after_other_owner(prior_source):
    from song_catalog import format_pick_key
    from music_resume_payload import apply_music_resume_payload
    from songs.practice_key_state import get_practice_concert_key
    pick = format_pick_key('Pop', 'Shape of You — Ed Sheeran')
    catalog = {'Pop': {'Shape of You — Ed Sheeran': {
        'title':'Shape of You','artist':'Ed Sheeran','key':'Bm','bpm':96,
        'sections': {'Verse': {'chords':'Bm Em G A'}}}}}
    session = dict(active_music_source=prior_source,active_catalog_pick_key='custom::prior',
        selected_song={'title':'Prior custom','pick_key':'custom::prior','key':'C'},
        song='Prior custom',display_key='C',instrument='Piano')
    payload = dict(practice_context_id='actual-resume',pick_key=pick,source_type='catalog',
        display_key='Cm',instrument='Saxophone',resume_kind='backing',studio_page='backing')
    with patch('suite_activity_client.record_activity'), patch('songs.state.persist_music_local_state'):
        assert apply_music_resume_payload(session,payload,song_picker_catalog=catalog)
    assert session['active_catalog_pick_key'] == pick
    assert session['selected_song']['title'] == 'Shape of You'
    assert session['active_music_source'] == 'catalog_song'
    assert session['instrument'] == 'Saxophone'
    assert get_practice_concert_key(session,pick) == 'Cm'
    assert session['_backing_transport_intent'] == 'stopped'
    assert not session.get('_backing_autoplay')
