"""Cold source identity, one-shot URL handling and actual persisted resources."""
import pytest
from tests.test_cold_entry_resource_preservation import storage,seed as raw_seed,app,apply,read
from tests.test_music_resume_finalize import _mini_catalog
import suite_user_persistence as disk
from music_persistent_state import build_music_disk_state
from music_entry_workspace import hydrate_entry_workspace
from music_launch_state import ERROR,render_music_resume_failure
from music_resume_payload import encode_payload_b64
from suite_resume_launch import apply_suite_resume_launch,finalize_suite_resume_launch
from songs.practice_key_state import get_practice_concert_key
from songs.music_source import (SOURCE_CATALOG,SOURCE_CUSTOM,SOURCE_COMPOSITION,
    SONG_PICKER_ACTIVE_SOURCE_KEY,SONG_PICKER_SOURCE_CATALOG,SONG_PICKER_SOURCE_CUSTOM,
    SONG_PICKER_SOURCE_COMPOSITION,on_song_picker_source_change,prepare_song_picker_source_radio)


def seed():
    from composition_document import ensure_workflow
    state=raw_seed()
    for doc in state['composition_workspace_state']['library'].values():ensure_workflow(doc)
    return state


def payload(before,source,key='Eb'):
    pick='custom::custom-saved-uuid' if source=='custom' else 'composition::'+list(before['composition_workspace_state']['library'])[-1]
    return dict(practice_context_id='saved-context',resume_kind='practice',workspace_id='daniel',
                pick_key=pick,song='Saved target',display_key=key,instrument='Flute',studio_page='practice')


def launch(before,source,key='Eb'):
    p=payload(before,source,key)
    return app({'suite_resume_payload':encode_payload_b64(p),'suite_page':'practice','suite_workspace':'daniel'}),p


def finalize(st):
    cat,lib=_mini_catalog()
    return finalize_suite_resume_launch(st,'music',song_picker_catalog=cat,song_library=lib)


def preserved(before,after):
    for uid,doc in before['composition_workspace_state']['library'].items():
        saved=after['composition_workspace_state']['library'][uid]
        assert {k:v for k,v in saved.items() if k!='updated_at'}=={k:v for k,v in doc.items() if k!='updated_at'}
    for key in ['cpl_saved_progressions','catalog_favorite_pick_keys','karaoke_queue']:
        assert after['session'][key]==before['session'][key]


@pytest.mark.parametrize('source,owner',[('custom',SOURCE_CUSTOM),('composition',SOURCE_COMPOSITION)])
def test_cold_owner_finalizes_once_and_preserves_disk(storage,source,owner):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,source)
    assert apply_suite_resume_launch(st,'music');assert not finalize(st)
    assert st.session_state.get('active_catalog_pick_key') is None
    assert hydrate_entry_workspace(st,apply_state=apply)
    st.session_state.update(display_key='F#',_kc_last_playing_confirm={'display_key':'A'})
    assert finalize(st);ss=st.session_state
    assert ss['active_catalog_pick_key']==p['pick_key'];assert ss['active_music_source']==owner
    assert ss['instrument']=='Flute';assert get_practice_concert_key(ss,p['pick_key'])=='Eb'
    assert ss['_backing_transport_intent']=='stopped';assert ss['_backing_autoplay'] is False
    for _ in range(4):
        assert not apply_suite_resume_launch(st,'music');assert not finalize(st)
        assert not ss.get('_suite_activity_resume_pending')
        assert disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel');preserved(before,read())
        assert get_practice_concert_key(ss,p['pick_key'])=='Eb'


def test_distinct_activity_url_starts_new_transaction(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,'custom')
    apply_suite_resume_launch(st,'music');hydrate_entry_workspace(st,apply_state=apply);assert finalize(st)
    target=payload(before,'composition','D');st.query_params['suite_resume_payload']=encode_payload_b64(target)
    assert apply_suite_resume_launch(st,'music');assert finalize(st)
    assert st.session_state['active_catalog_pick_key']==target['pick_key']
    assert get_practice_concert_key(st.session_state,target['pick_key'])=='D'


@pytest.mark.parametrize('source',['custom','composition'])
def test_missing_source_is_terminal_without_fallback_or_write(storage,source):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,source)
    p['pick_key']=source+'::missing';st.query_params['suite_resume_payload']=encode_payload_b64(p)
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply)
    prior=st.session_state.get('active_catalog_pick_key');assert not finalize(st)
    assert st.session_state[ERROR];assert st.session_state.get('active_catalog_pick_key')==prior
    assert not st.session_state.get('_suite_activity_resume_pending');assert not apply_suite_resume_launch(st,'music')
    with pytest.raises(RuntimeError,match='restoration failed'):build_music_disk_state(st)
    assert read()==before


@pytest.mark.parametrize('raw',['not-base64',encode_payload_b64({})])
def test_invalid_payload_does_not_fall_through_to_legacy_source(storage,raw):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app({'suite_resume_payload':raw,'suite_pick_key':'custom::custom-saved-uuid','suite_page':'practice'})
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply)
    assert st.session_state[ERROR];assert not finalize(st)
    with pytest.raises(RuntimeError):build_music_disk_state(st)
    assert read()==before


def test_generic_workstream_ignores_old_resume_and_does_not_reapply_page(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,'composition')
    st.query_params.update(suite_entry_mode='workstream',suite_page='picker')
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply)
    prior=st.session_state.get('active_catalog_pick_key');assert finalize(st)
    assert not str(prior or '').startswith('composition::');assert st.session_state['studio_page']=='picker'
    assert not st.session_state.get('_suite_activity_resume_pending')
    st.session_state['studio_page']='custom';st.query_params['suite_resume_payload']=encode_payload_b64(payload(before,'custom','G'))
    assert not apply_suite_resume_launch(st,'music');assert st.session_state['studio_page']=='custom'
    disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel');preserved(before,read())


def test_source_switch_sequence_after_resume_owns_each_rerun(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,'composition')
    apply_suite_resume_launch(st,'music');hydrate_entry_workspace(st,apply_state=apply);assert finalize(st)
    cat,lib=_mini_catalog();st.rerun=lambda:None
    for choice,owner in [(SONG_PICKER_SOURCE_CATALOG,SOURCE_CATALOG),(SONG_PICKER_SOURCE_CUSTOM,SOURCE_CUSTOM),
                         (SONG_PICKER_SOURCE_COMPOSITION,SOURCE_COMPOSITION),(SONG_PICKER_SOURCE_CATALOG,SOURCE_CATALOG)]:
        ss=st.session_state;ss['studio_page']='picker';ss[SONG_PICKER_ACTIVE_SOURCE_KEY]=choice
        on_song_picker_source_change(st,song_picker_catalog=cat,song_library=lib,invalidate_backing=lambda st:None,in_callback=True)
        assert not apply_suite_resume_launch(st,'music')
        prepare_song_picker_source_radio(st,song_picker_catalog=cat,song_library=lib,invalidate_backing=lambda st:None)
        assert ss['active_music_source']==owner;assert __import__("songs.music_source",fromlist=["picker_label_to_music_source"]).picker_label_to_music_source(ss[SONG_PICKER_ACTIVE_SOURCE_KEY])==owner
        assert not ss.get('_suite_activity_resume_pending')
        disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel');preserved(before,read())


def test_failure_action_chooses_source_without_reusing_activity(storage):
    st=app({'suite_resume_payload':'bad','suite_page':'practice','suite_workspace':'daniel','auth_hint':'keep'})
    apply_suite_resume_launch(st,'music');st.title=lambda text:None;st.error=lambda text:None
    st.button=lambda *a,**kw:True;st.rerun=lambda:None;st.stop=lambda:None
    render_music_resume_failure(st)
    assert st.query_params==dict(suite_workspace='daniel',suite_entry_mode='workstream',suite_page='picker',auth_hint='keep')
    assert not st.session_state.get(ERROR)


@pytest.mark.parametrize('source',['custom','composition'])
def test_legacy_named_sources_use_owner_api(storage,source):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');p=payload(before,source,'D')
    st=app(dict(suite_pick_key=p['pick_key'],suite_resume='song:'+p['pick_key'],suite_page='practice',suite_display_key='D',suite_instrument='Flute'))
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply);assert finalize(st)
    assert st.session_state['active_catalog_pick_key']==p['pick_key']
    assert get_practice_concert_key(st.session_state,p['pick_key'])=='D'
    assert st.session_state['_backing_autoplay'] is False


def test_owner_exception_preserves_disk_and_exits_pending(storage,monkeypatch):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,'custom')
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply)
    def fail(*args,**kwargs):raise RuntimeError('unavailable owner')
    monkeypatch.setattr('songs.state.activate_active_song_by_pick_key',fail)
    assert not finalize(st);assert st.session_state[ERROR]
    assert not st.session_state.get('_suite_activity_resume_pending')
    with pytest.raises(RuntimeError):build_music_disk_state(st)
    assert read()==before


@pytest.mark.parametrize('change',[{'version':2},{'pick_key':''},{'source_type':'catalog'}])
def test_incomplete_or_mismatched_named_payload_is_safe(storage,change):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,'custom');p.update(change)
    st.query_params['suite_resume_payload']=encode_payload_b64(p)
    apply_suite_resume_launch(st,'music');assert hydrate_entry_workspace(st,apply_state=apply)
    assert not finalize(st);assert st.session_state[ERROR]
    with pytest.raises(RuntimeError):build_music_disk_state(st)
    assert read()==before


@pytest.mark.parametrize('source',['custom','composition'])
def test_encoded_legacy_context_defers_and_uses_named_owner(storage,source):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel');st,p=launch(before,source)
    p.pop('practice_context_id');st.query_params['suite_resume_payload']=encode_payload_b64(p)
    apply_suite_resume_launch(st,'music');assert not finalize(st)
    assert hydrate_entry_workspace(st,apply_state=apply);assert finalize(st)
    assert st.session_state['active_catalog_pick_key']==p['pick_key']
    assert get_practice_concert_key(st.session_state,p['pick_key'])=='Eb'


def test_sidebar_identity_does_not_resurrect_editor_after_new_composition():
    from copy import deepcopy
    from unittest.mock import patch
    from sidebar_key_identity import resolve_sidebar_key_identity
    from composition_songs_bridge import apply_pending_composer_new_song
    ss=deepcopy(seed()['session'])
    ws=deepcopy(seed()['composition_workspace_state'])
    ss.update(composition_workspace_state=ws, composer_saved_compositions=deepcopy(ws['library']),
              active_catalog_pick_key='composition::'+list(ws['library'])[-1],
              _pending_composer_new_song=True, _composition_songs_source_ready=True)
    apply_pending_composer_new_song(ss)
    before=deepcopy(ss)
    with patch('sidebar_key_identity._explicit_sidebar_owner',return_value='composition'):
        resolve_sidebar_key_identity(ss)
    assert ss==before
    assert not ss.get('composer_active_document')
    assert ss['composer_needs_seed'] is True


def test_entry_finalizes_after_bootstrap_restore_before_sidebar_widgets():
    import ast
    from pathlib import Path
    tree=ast.parse((Path(__file__).parents[1]/'streamlit_music_practice_app.py').read_text(encoding='utf-8'))
    names=('finalize_suite_resume_launch','handle_studio_page_transition',
           'run_post_nav_music_startup_init','finalize_music_startup_restore',
           'prime_sidebar_practice_key_from_identity')
    calls={name:[] for name in names}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in calls:
            calls[node.func.id].append(node.lineno)
    assert len(calls['finalize_suite_resume_launch'])==1
    commit=calls['finalize_suite_resume_launch'][0]
    for name in names[1:4]:assert calls[name] and max(calls[name])<commit
    assert commit<min(calls['prime_sidebar_practice_key_from_identity'])


def test_unexpected_resource_resolution_failure_is_terminal(storage):
    from unittest.mock import patch
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st,p=launch(before,'composition');apply_suite_resume_launch(st,'music')
    assert hydrate_entry_workspace(st,apply_state=apply)
    with patch('composition_songs_bridge.find_composition_document',side_effect=RuntimeError('unavailable')):
        assert not finalize(st)
    assert st.session_state[ERROR]=='saved_context_unavailable'
    assert not st.session_state.get('_suite_activity_resume_pending')
    with pytest.raises(RuntimeError):build_music_disk_state(st)
    preserved(before,read())


def test_workstream_page_wins_after_bootstrap_restores_previous_page():
    st=app({'suite_entry_mode':'workstream','suite_page':'picker','suite_workspace':'daniel'})
    apply_suite_resume_launch(st,'music')
    st.session_state.update(_music_entry_workspace_ready=True,studio_page='practice')
    assert finalize(st)
    assert st.session_state['studio_page']=='picker'
    st.session_state['studio_page']='composer'
    assert not apply_suite_resume_launch(st,'music')
    assert not finalize(st)
    assert st.session_state['studio_page']=='composer'


def test_payload_only_url_preserves_launch_flag_and_full_hydration(storage):
    from unittest.mock import patch
    from suite_user_persistence import sync_workspace_protocol
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st,p=launch(before,'composition');st.query_params.pop('suite_page',None)
    apply_suite_resume_launch(st,'music')
    from suite_cloud_state import list_active_resume_query_params,reconcile_stale_resume_session_flags
    assert 'suite_resume_payload' in list_active_resume_query_params(st,'music')
    assert not reconcile_stale_resume_session_flags(st,'music')
    assert st.session_state['_suite_resume_launch_music'] is True
    sync_workspace_protocol(st,'music',apply_state=apply)
    assert st.session_state['_music_entry_workspace_ready'] is True
    assert finalize(st)
    assert st.session_state['active_catalog_pick_key']==p['pick_key']
    preserved(before,read())


def test_composition_vision_fields_follow_document_uuid_and_keep_same_document_edits():
    from copy import deepcopy
    from composition_studio_page import prepare_vision_widget_state
    docs=list(seed()['composition_workspace_state']['library'].values())
    first,second=docs
    first['title']='First saved composition';second['title']='Second saved composition'
    ss={'composer_vision_title':'stale title','composer_vision_key':'F#'}
    prepare_vision_widget_state(ss,first)
    assert ss['composer_vision_title']==first['title']
    ss['composer_vision_title']='My unsaved field edit'
    prepare_vision_widget_state(ss,first)
    assert ss['composer_vision_title']=='My unsaved field edit'
    prepare_vision_widget_state(ss,second)
    assert ss['composer_vision_title']==second['title']
    assert ss['composer_vision_document_id']==second['id']
