from __future__ import annotations
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from composition_document import bootstrap_from_vision, apply_structure_template, ordered_sections, apply_section_chords, parse_chord_paste, apply_melody_events
from composition_session_state import set_active_document, save_document_to_library, delete_library_document, import_composer_widget_state, library_save_success_message
from composition_workspace_state_persistence import (default_composition_workspace_state, checkpoint_composition_workspace,
    gather_composition_workspace_from_session, apply_composition_workspace_from_payload, resolve_legacy_recovery,
    prepare_composition_workspace_for_render, COMPOSITION_RECOVERY_KEY)
from composition_save_verification import RESULT_KEY, content_fingerprint, save_feedback


def document():
    doc = bootstrap_from_vision(genre='Bossa', song_idea='Disposable regression', title='Complete disposable song', key='F minor', bpm=113, meter='6/8')
    apply_structure_template(doc, 'simple')
    sec = ordered_sections(doc)[0]
    apply_section_chords(doc, sec['id'], parse_chord_paste('Fm7 Bbm7 C7 Fm7'))
    apply_melody_events(doc, sec['id'], [{'pitch':'F4','midi':65,'duration_beats':1.5,'beat':0,'measure':1}], replace=True)
    sec['lyrics'] = {'raw_text':'Only disposable lyrics', 'lines':['Only disposable lyrics'], 'intent':{'language':'English'}}
    return doc


def session():
    ss = {'workspace_id':'guest', 'instrument':'Piano', 'practice_key_by_source':{'untouched':'Bb'},
          'cpl_saved_progressions':{'untouched':{'id':'other-song'}}, 'mt_tracks':{'A':b'untouched'}}
    doc = document()
    set_active_document(ss, doc, checkpoint=False)
    save_document_to_library(ss, force_disk=False)
    return ss


@pytest.mark.parametrize('result', [
    {}, {'disk_verified':False,'cloud_verified':False},
    {'disk_verified':True,'cloud_verified':False},
])
def test_no_confirmed_cloud_never_claims_durable_success(result):
    level, text = save_feedback(result)
    assert level != 'success'
    assert 'safe on this device' not in text
    if result.get('disk_verified'):
        assert 'app server' in text and 'restart' in text
    else:
        assert 'session' in text and 'No persistent save' in text


def test_memory_library_save_is_not_a_persistence_confirmation():
    ss=session()
    assert ss['_composer_last_library_save']['session_updated']
    assert library_save_success_message(ss) == ''
    assert ss[RESULT_KEY]['status'] == 'memory_only'
    assert ss['composition_workspace_state_dirty']


def test_actual_disk_and_mock_cloud_readbacks_verify_complete_workspace(tmp_path, monkeypatch):
    import suite_user_persistence as disk
    import suite_workspace
    monkeypatch.setattr(disk, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(suite_workspace, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(suite_workspace, 'resolve_workspace_id', lambda **kw:'guest')
    ss=session(); baseline=copy.deepcopy(ss['composer_saved_compositions']); cloud={}
    def persist(st, **kw):
        state={'composition_workspace_state':copy.deepcopy(st.session_state['composition_workspace_state'])}
        assert disk.save_user_state('music',state,workspace_id='guest')
        cloud.update(state)
        st.session_state['_suite_persist_last_save_disk']=True
        st.session_state['_suite_persist_last_save_cloud']=True
        return True
    with patch('music_persistent_state.force_save_music_state',side_effect=persist), patch('suite_storage_config.cloud_storage_enabled',return_value=True), patch('suite_user.account_mode',return_value='cloud'), patch('suite_cloud_state.load_cloud_full_session',side_effect=lambda app,force=False:(copy.deepcopy(cloud),'now')):
        result=checkpoint_composition_workspace(ss,force_disk=True)
    assert result['cloud_verified'] and result['disk_verified']
    assert save_feedback(result)[0]=='success'
    assert not ss.get('composition_workspace_state_dirty')
    # Fresh process/session shape, genuine JSON file envelope; no prior live keys.
    path=tmp_path/'workspaces'/'guest'/'music_user_state.json'
    stored=json.loads(path.read_text(encoding='utf-8'))['state']
    fresh={}; assert apply_composition_workspace_from_payload(fresh,stored,authoritative=True)
    assert fresh['composer_saved_compositions']==baseline
    assert content_fingerprint(fresh['composition_workspace_state'])==result['fingerprint']
    # Section/page navigation followed by another fresh hydrate keeps every field.
    for page in ('home','custom','backing','composer'):
        fresh['studio_page']=page
        prepare_composition_workspace_for_render(fresh)
        assert fresh['composer_saved_compositions']==baseline
    assert ss['practice_key_by_source']=={'untouched':'Bb'}
    assert ss['instrument']=='Piano' and ss['mt_tracks']=={'A':b'untouched'}


@pytest.mark.parametrize('damage', ['lyrics','chords','melody','key','document_metadata','library_missing'])
def test_cloud_ack_with_incomplete_document_fails_readback(damage):
    ss=session(); ws=copy.deepcopy(ss['composition_workspace_state']); broken=copy.deepcopy(ws)
    doc=next(iter(broken['library'].values())); sec=ordered_sections(doc)[0]
    if damage in ('lyrics','chords','melody'): sec[damage]={}
    elif damage=='key': doc['global']['original_key_center']='C'
    elif damage=='document_metadata': doc['metadata']['description']='truncated'
    else: broken['library']={}
    def persist(st,**kw):
        st.session_state['_suite_persist_last_save_cloud']=True
        return True
    with patch('music_persistent_state.force_save_music_state',side_effect=persist),patch('suite_storage_config.cloud_storage_enabled',return_value=True),patch('suite_user.account_mode',return_value='cloud'),patch('suite_cloud_state.load_cloud_full_session',return_value=({'composition_workspace_state':broken},'now')):
        r=checkpoint_composition_workspace(ss,force_disk=True)
    assert not r['cloud_verified'] and save_feedback(r)[0]=='error'
    assert ss['composition_workspace_state_dirty']


def test_failed_attempt_cannot_reuse_previous_success_flags():
    ss=session(); ss.update(_suite_persist_last_save_disk=True,_suite_persist_last_save_cloud=True,_music_force_save_ok=True)
    with patch('music_persistent_state.force_save_music_state',return_value=False),patch('suite_storage_config.cloud_storage_enabled',return_value=True),patch('suite_cloud_state.load_cloud_full_session') as read:
        r=checkpoint_composition_workspace(ss,force_disk=True)
    assert r['status']=='memory_only' and not r['cloud_verified']
    read.assert_not_called()


def test_disk_readback_only_is_temporary_and_retains_pending_cloud_dirty():
    ss=session()
    def persist(st,**kw):
        st.session_state['_suite_persist_last_save_disk']=True
        return False
    with patch('music_persistent_state.force_save_music_state',side_effect=persist),patch('suite_storage_config.cloud_storage_enabled',return_value=True),patch('composition_save_verification._read_disk_state',side_effect=lambda:{'composition_workspace_state':copy.deepcopy(ss['composition_workspace_state'])}):
        r=checkpoint_composition_workspace(ss,force_disk=True)
    assert r['status']=='server_local_only' and save_feedback(r)[0]=='warning'
    assert ss['composition_workspace_state_dirty']


def legacy_payload(doc, canonical):
    return {'composition_workspace_state':canonical, 'session':{'composer_saved_compositions':{doc['id']:copy.deepcopy(doc)},'composer_active_document':copy.deepcopy(doc)}}


def test_explicitly_uninitialized_new_block_restores_complete_legacy_document():
    doc=document(); payload=legacy_payload(doc,default_composition_workspace_state()); original=copy.deepcopy(payload)
    ss={}; assert apply_composition_workspace_from_payload(ss,payload,authoritative=True)
    assert ss['composer_saved_compositions'][doc['id']]==doc
    assert payload==original


def test_ambiguous_v1_empty_never_hides_or_silently_resurrects_legacy():
    doc=document(); empty=default_composition_workspace_state();empty.pop('library_initialized');empty['schema_version']=1
    ss={}; assert not apply_composition_workspace_from_payload(ss,legacy_payload(doc,empty),authoritative=True)
    assert ss[COMPOSITION_RECOVERY_KEY]['library'][doc['id']]==doc
    from music_persistent_state import build_music_disk_state
    with pytest.raises(RuntimeError,match='recovery choice pending'):
        build_music_disk_state(SimpleNamespace(session_state=ss))
    resolve_legacy_recovery(ss,recover=True)
    assert ss['composer_saved_compositions'][doc['id']]==doc
    assert ss['composer_active_document']==doc


def test_declining_ambiguous_legacy_prevents_stale_reappearance():
    doc=document(); empty=default_composition_workspace_state();empty.pop('library_initialized')
    payload=legacy_payload(doc,empty); ss={}
    apply_composition_workspace_from_payload(ss,payload,authoritative=True)
    resolve_legacy_recovery(ss,recover=False)
    assert doc['id'] in ss['composer_deleted_document_ids']
    apply_composition_workspace_from_payload(ss,payload,authoritative=True)
    assert not ss.get('composer_saved_compositions') and not ss.get('composer_active_document')


def test_confirmed_empty_library_preserves_legitimate_deletion():
    doc=document(); empty=default_composition_workspace_state();empty['library_initialized']=True
    ss={};assert apply_composition_workspace_from_payload(ss,legacy_payload(doc,empty),authoritative=True)
    assert not ss.get(COMPOSITION_RECOVERY_KEY) and not ss['composer_saved_compositions']


def test_delete_active_document_survives_fresh_hydration_and_stale_snapshots():
    ss=session();doc=copy.deepcopy(ss['composer_active_document']);old=copy.deepcopy(ss['composition_workspace_state'])
    with patch('music_persistent_state.force_save_music_state',return_value=False),patch('suite_storage_config.cloud_storage_enabled',return_value=True):
        delete_library_document(ss,doc['id'])
    assert not ss['composition_workspace_state']['active_document']
    assert not ss['composition_workspace_state']['library']
    fresh={};apply_composition_workspace_from_payload(fresh,json.loads(json.dumps({'composition_workspace_state':ss['composition_workspace_state']})),authoritative=True)
    import_composer_widget_state(fresh,{'composer_saved_compositions':{doc['id']:doc},'composer_active_document':doc})
    prepare_composition_workspace_for_render(fresh)
    assert not fresh.get('composer_active_document') and not fresh['composer_saved_compositions']
    apply_composition_workspace_from_payload(fresh,{'composition_workspace_state':old},authoritative=True)
    assert not fresh.get('composer_active_document') and not fresh['composer_saved_compositions']
    assert save_document_to_library(fresh,doc)=={}


def test_recovery_choice_does_not_overwrite_a_newer_live_document():
    doc=document(); newer=copy.deepcopy(doc);newer['title']='Keep newer content'
    ss={'composer_saved_compositions':{doc['id']:newer},'composer_active_document':newer,COMPOSITION_RECOVERY_KEY:{'library':{doc['id']:doc},'active_document':doc}}
    resolve_legacy_recovery(ss,recover=True)
    assert ss['composer_active_document']==newer and ss['composer_saved_compositions'][doc['id']]==newer


def test_songs_picker_cannot_resurrect_deleted_or_confirmed_empty_library():
    from composition_songs_bridge import ensure_composition_library_hydrated
    doc=document()
    for use_tombstone in (False,True):
        empty=default_composition_workspace_state();empty['library_initialized']=True
        if use_tombstone:empty['deleted_document_ids']=[doc['id']]
        ss={'composition_workspace_state':empty,'_studio_page_snapshots':{'composer':{'composer_saved_compositions':{doc['id']:doc},'composer_active_document':doc}}}
        assert ensure_composition_library_hydrated(ss)=={}
        assert not ss.get('composer_active_document')


def test_empty_new_top_level_falls_back_to_complete_nested_workspace():
    doc=document(); populated=default_composition_workspace_state()
    populated.update(active_document=copy.deepcopy(doc),library={doc['id']:copy.deepcopy(doc)},library_initialized=True)
    ss={};assert apply_composition_workspace_from_payload(ss,{'composition_workspace_state':default_composition_workspace_state(),'music_workspace_state':{'composition_workspace_state':populated}},authoritative=True)
    assert ss['composer_saved_compositions'][doc['id']]==doc


def test_unresolved_cloud_identity_cannot_confirm_readback():
    ss=session()
    def persist(st,**kw):
        st.session_state['_suite_persist_last_save_cloud']=True
        return True
    with patch('music_persistent_state.force_save_music_state',side_effect=persist),patch('suite_storage_config.cloud_storage_enabled',return_value=True),patch('suite_user.account_mode',return_value='local'),patch('suite_cloud_state.load_cloud_full_session') as read:
        r=checkpoint_composition_workspace(ss,force_disk=True)
    assert not r['cloud_verified'];read.assert_not_called()


def test_confirmed_result_for_previous_content_cannot_acknowledge_mutated_document():
    ss=session(); from composition_save_verification import content_fingerprint
    ss[RESULT_KEY]={'cloud_verified':True,'document_id':ss['composer_active_document']['id'],'fingerprint':content_fingerprint(ss['composition_workspace_state'])}
    assert library_save_success_message(ss)
    ss['composition_workspace_state']['library'][ss['composer_active_document']['id']]['title']='New unsaved revision'
    assert not library_save_success_message(ss)


def test_deleted_document_cannot_return_under_legacy_title_alias():
    doc=document(); blob=default_composition_workspace_state()
    blob.update(library={'old-title-key':doc},active_document=doc,deleted_document_ids=[doc['id']],library_initialized=True)
    ss={};assert apply_composition_workspace_from_payload(ss,{'composition_workspace_state':blob},authoritative=True)
    assert not ss['composer_saved_compositions'] and not ss.get('composer_active_document')


@pytest.mark.parametrize('reason',['explicit_library_save','library_save'])
def test_composition_save_is_recognized_intent_without_bypassing_strict_policy(reason):
    from music_egress_config import normalize_music_save_reason,is_intentional_user_save_reason
    from music_strict_egress_transaction import evaluate_strict_egress_transaction
    assert normalize_music_save_reason(reason)=='composer_edit'
    assert is_intentional_user_save_reason(reason)
    with patch('music_egress_config.music_egress_strict_enabled',return_value=True),patch('music_egress_strict_save.music_egress_strict_enabled',return_value=True),patch('music_strict_egress_transaction.music_egress_strict_enabled',return_value=True):
        tx=evaluate_strict_egress_transaction({},raw_save_reason=reason,payload_fp='composition-new-content')
    assert tx.save_reason_is_intentional and tx.strict_egress_approved
    assert not is_intentional_user_save_reason('autosave')


@pytest.mark.parametrize('field',['chords','lyrics','melody','label','global','deleted_document_ids'])
def test_canonical_save_fingerprint_includes_complete_composition(field):
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint
    ss=session();state={'composition_workspace_state':copy.deepcopy(ss['composition_workspace_state'])}
    before=workspace_canonical_content_fingerprint(state);changed=copy.deepcopy(state)
    blob=changed['composition_workspace_state'];doc=next(iter(blob['library'].values()));sec=ordered_sections(doc)[0]
    if field in ('chords','lyrics','melody'):sec[field]={}
    elif field=='label':sec['label']='Changed section label'
    elif field=='global':doc['global']['bpm']=137
    else:blob[field]=[doc['id']]
    assert workspace_canonical_content_fingerprint(changed)!=before
    timestamps=copy.deepcopy(state)
    for doc in timestamps['composition_workspace_state']['library'].values():doc['updated_at']='new timestamp only'
    assert workspace_canonical_content_fingerprint(timestamps)==before


def test_actual_page_snapshot_restore_cannot_resurrect_a_deleted_composition():
    from studio_page_persistence import restore_page_snapshot
    doc=document();blob=default_composition_workspace_state()
    blob.update(deleted_document_ids=[doc['id']],library_initialized=True)
    ss={'composition_workspace_state':blob,'composer_deleted_document_ids':[doc['id']],
        '_studio_page_snapshots':{'composer':{'composer_saved_compositions':{doc['id']:doc},'composer_active_document':doc}}}
    restore_page_snapshot(ss,'composer')
    assert not ss.get('composer_active_document') and not ss['composer_saved_compositions']


def test_declining_title_aliased_recovery_tombstones_the_real_document_id():
    doc=document();ss={COMPOSITION_RECOVERY_KEY:{'library':{'old-title':doc}}}
    resolve_legacy_recovery(ss,recover=False)
    assert doc['id'] in ss['composer_deleted_document_ids']
    assert not ss['composition_workspace_state']['library']


def test_recovery_alias_does_not_duplicate_a_newer_live_id():
    doc=document();newer=copy.deepcopy(doc);newer['title']='Keep latest revision'
    ss={'composer_saved_compositions':{doc['id']:newer},'composer_active_document':newer,COMPOSITION_RECOVERY_KEY:{'library':{'old-title':doc}}}
    resolve_legacy_recovery(ss,recover=True)
    assert ss['composer_saved_compositions']=={doc['id']:newer}
