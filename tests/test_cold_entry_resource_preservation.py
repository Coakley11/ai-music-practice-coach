"""Actual serialized resources survive URL context activation and subsequent writes."""
import copy
import json
from types import SimpleNamespace

import pytest

import suite_user_persistence as disk
import suite_workspace
from composition_document import new_composition_document
from custom_progression_lab import default_active_progression, ensure_original_structure
from music_entry_workspace import hydrate_entry_workspace, require_entry_workspace
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from suite_resume_launch import apply_suite_resume_launch, finalize_suite_resume_launch
from tests.test_music_resume_finalize import _mini_catalog
from song_catalog import format_pick_key
from music_resume_payload import encode_payload_b64


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(disk, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(disk, '_LEGACY_COMBINED_FILE', tmp_path/'legacy.json')
    monkeypatch.setattr(suite_workspace, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(suite_workspace, '_PERSISTED_FILE', tmp_path/'workspace.json')
    monkeypatch.setattr('suite_cloud_state.load_cloud_full_session', lambda app: ({}, None))
    monkeypatch.setattr('suite_storage_config.cloud_storage_enabled', lambda: False)
    return tmp_path


def seed():
    a=new_composition_document(title='First saved document')
    b=new_composition_document(title='Second saved document')
    custom=ensure_original_structure(default_active_progression())
    custom.update(id='custom-saved-uuid',name='Saved Custom',artist='',original_key_center='C',bpm=100,
                  user_locked_home_key=True)
    custom['original_sections']['Verse']=[{'chord':c,'bars':1} for c in ['C','Am','F','G']]
    ss={'_suite_active_workspace_id':'daniel','studio_page':'practice',
        'composer_active_document':copy.deepcopy(b),
        'composer_saved_compositions':{a['id']:a,b['id']:b},
        'cpl_saved_progressions':{'Saved Custom':copy.deepcopy(custom)},
        'cpl_active_progression':copy.deepcopy(custom),
        'catalog_favorite_pick_keys':['saved-favorite'],
        'karaoke_queue':[{'title':'Saved set entry','key':'D'}]}
    return build_music_disk_state(SimpleNamespace(session_state=ss))


def read():
    return json.loads(disk.state_file_path('music','daniel').read_text(encoding='utf-8'))['state']


def app(qp):
    return SimpleNamespace(session_state={'_suite_active_workspace_id':'daniel'},query_params=qp)


def apply(st, state):
    catalog, library=_mini_catalog()
    apply_music_disk_state(st,state,song_picker_catalog=catalog,song_library=library)


def assert_resources(before, after):
    assert after['composition_workspace_state']['library']==before['composition_workspace_state']['library']
    assert after['composition_workspace_state']['active_document']==before['composition_workspace_state']['active_document']
    for key in ['cpl_saved_progressions','cpl_active_progression','catalog_favorite_pick_keys','karaoke_queue']:
        assert after['session'][key]==before['session'][key]


@pytest.mark.parametrize('page',['practice','backing','creative','analysis'])
def test_catalog_entry_preserves_actual_disk_resources(storage,page):
    before=seed();assert disk.save_user_state('music',before,workspace_id='daniel')
    pick=format_pick_key('Pop','Turn the Lights Back On — Billy Joel')
    st=app({'suite_resume':'song:'+pick,'suite_pick_key':pick,'suite_song':'Turn the Lights Back On',
            'suite_page':page,'suite_display_key':'Cm','suite_instrument':'Flute'})
    apply_suite_resume_launch(st,'music')
    assert hydrate_entry_workspace(st,apply_state=apply)
    cat,lib=_mini_catalog();finalize_suite_resume_launch(st,'music',song_picker_catalog=cat,song_library=lib)
    assert st.session_state['song']=='Turn the Lights Back On'
    assert st.session_state['instrument']=='Flute'
    for _ in range(3):
        assert hydrate_entry_workspace(st,apply_state=apply)
        assert disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
        assert_resources(before,read())


def test_normal_entry_preserves_resources(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app({});apply(st,read());disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert_resources(before,read())


def test_resume_protocol_hydrates_before_context_only_skip(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app({'suite_page':'practice'});apply_suite_resume_launch(st,'music')
    disk.sync_workspace_protocol(st,'music',apply_state=apply)
    disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert_resources(before,read())


@pytest.mark.parametrize('qp',[{'suite_page':'practice'},
    {'suite_page':'practice','suite_resume_payload':'not-valid-base64'},
    {'suite_page':'practice','suite_pick_key':'custom::missing-uuid'},
    {'suite_page':'practice','suite_pick_key':'composition::missing-uuid'},
    {'suite_page':'practice','suite_resume_payload':encode_payload_b64({
        'practice_context_id':'missing','resume_kind':'practice','workspace_id':'daniel',
        'pick_key':'composition::missing-uuid'})}])
def test_incomplete_or_missing_source_cannot_erase(storage,qp):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app(qp);apply_suite_resume_launch(st,'music')
    assert hydrate_entry_workspace(st,apply_state=apply)
    cat,lib=_mini_catalog();finalize_suite_resume_launch(st,'music',song_picker_catalog=cat,song_library=lib)
    if st.session_state.get('_suite_resume_error_music'):
        with pytest.raises(RuntimeError,match='restoration failed'):build_music_disk_state(st)
    else:
        disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert_resources(before,read())


def test_failed_hydration_blocks_partial_and_nested_writes(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app({'suite_page':'practice'});require_entry_workspace(st.session_state)
    def broken(st,payload):
        with pytest.raises(RuntimeError,match='hydration is incomplete'):
            build_music_disk_state(st)
        raise ValueError('source hydrate failed')
    assert not hydrate_entry_workspace(st,apply_state=broken)
    with pytest.raises(RuntimeError,match='hydration is incomplete'):build_music_disk_state(st)
    assert_resources(before,read())


def test_cloud_selected_resources_use_same_hydration_boundary(storage,monkeypatch):
    before=seed();disk.save_user_state('music',{'core':{}},workspace_id='daniel')
    monkeypatch.setattr('suite_cloud_state.load_cloud_full_session',lambda app:(copy.deepcopy(before),'2099-01-01T00:00:00Z'))
    st=app({'suite_page':'practice'});apply_suite_resume_launch(st,'music')
    assert hydrate_entry_workspace(st,apply_state=apply)
    assert st.session_state['_music_entry_workspace_source']=='cloud'
    disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert_resources(before,read())


def test_unreadable_local_state_is_not_confirmed_empty(storage):
    disk._LEGACY_COMBINED_FILE.write_text(json.dumps({'music':{'state':seed()}}),encoding='utf-8')
    path=disk.state_file_path('music','daniel');path.write_text('unreadable-json',encoding='utf-8')
    st=app({'suite_page':'practice'});apply_suite_resume_launch(st,'music')
    assert not hydrate_entry_workspace(st,apply_state=apply)
    with pytest.raises(RuntimeError,match='hydration is incomplete'):build_music_disk_state(st)
    assert path.read_text(encoding='utf-8')=='unreadable-json'


def test_loaded_library_deletion_is_not_resurrected(storage):
    before=seed();disk.save_user_state('music',before,workspace_id='daniel')
    st=app({'suite_page':'practice'});apply_suite_resume_launch(st,'music')
    assert hydrate_entry_workspace(st,apply_state=apply)
    st.session_state['composer_saved_compositions'].clear()
    st.session_state['cpl_saved_progressions'].clear()
    assert hydrate_entry_workspace(st,apply_state=apply)  # no stale re-hydration
    disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert read()['composition_workspace_state']['library']=={}
    assert read()['session']['cpl_saved_progressions']=={}


@pytest.mark.parametrize("destination,tab", [("missions","Missions"),("coaching","Song-Aware Coaching")])
def test_activity_destination_survives_later_creative_hydration(storage,destination,tab):
    from creative_session_state import sync_creative_session_from_session, hydrate_creative_session_for_page
    from music_resume_payload import apply_music_resume_payload
    from improvisation_intelligence import PRACTICE_MISSIONS
    before=seed()
    st=app({})
    apply(st,before)
    ss=st.session_state
    ss.update(studio_page="creative",improv_entry_mode="Song-Based Improvisation",
              improv_intelligence_tab="Song-Aware Coaching")
    sync_creative_session_from_session(ss)
    from studio_page_persistence import save_page_snapshot, restore_current_page_snapshot_if_needed
    save_page_snapshot(ss,"creative")
    mission=next(m for m in PRACTICE_MISSIONS if "guide tones" in m)
    cat,lib=_mini_catalog()
    pick=format_pick_key("Pop",next(k for k in cat["Pop"] if k.startswith("Turn the Lights")))
    payload={"progress_activity_id":"saved-activity", "activity_destination":destination,
             "resume_kind":"creative", "studio_page":"creative", "pick_key":pick,
             "song":"Turn the Lights Back On", "instrument":"Flute", "display_key":"Cm",
             "mission":mission}
    cat,lib=_mini_catalog()
    assert apply_music_resume_payload(ss,payload,song_picker_catalog=cat,song_library=lib)
    restore_current_page_snapshot_if_needed(ss)
    hydrate_creative_session_for_page(ss)
    assert ss["improv_intelligence_tab"]==tab
    if destination=="missions":
        from creative_mission_config_persistence import project_mission_config_from_canonical_before_widgets
        project_mission_config_from_canonical_before_widgets(ss)
        assert ss["improv_mission_pick"]==mission
    disk.save_user_state('music',build_music_disk_state(st),workspace_id='daniel')
    assert_resources(before,read())
