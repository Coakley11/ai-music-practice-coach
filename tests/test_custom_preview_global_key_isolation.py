"""Custom preview must not mutate the active Catalog/Composition key or identity."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app_ui import navigate_studio_page
from custom_progression_lab import (
    CPL_ACTIVE_KEY, CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
    default_active_progression, prepare_custom_workspace_sidebar_display_key,
    sync_custom_workspace_practice_key,
)
from home_destinations import apply_home_navigation, destination_by_key
from songs.music_source import custom_pick_key_for

PROTECTED = ('selected_song', 'active_catalog_pick_key', 'active_music_source',
             'instrument', 'display_key', 'concert_key', 'concert_practice_key',
             'active_song_state', '_pending_display_key')

def session_for(source, entry):
    pick = 'Pop\x1fSay' if source == 'catalog_song' else 'composition::score-1'
    song = {'title': 'Say' if source == 'catalog_song' else 'My score', 'key': 'G', 'pick_key': pick}
    return dict(studio_page=entry, selected_song=song, active_catalog_pick_key=pick,
                active_music_source=source, instrument='Guitar', display_key='G',
                concert_key='G', concert_practice_key='G', _pending_display_key='G',
                active_song_state={'source':source, 'pick_key':pick, 'original_key':'G'},
                practice_key_by_source={pick:'G'})

@pytest.mark.parametrize('source', ['catalog_song','composition_song'])
@pytest.mark.parametrize('entry', ['home','practice','picker'])
def test_custom_visit_and_preview_edits_preserve_global_owner(source, entry):
    s=session_for(source,entry);before={k:deepcopy(s[k]) for k in PROTECTED}
    if entry=='home': apply_home_navigation(s,destination_by_key('more_custom'))
    else: navigate_studio_page(s,'custom')
    st=SimpleNamespace(session_state=s)
    prepare_custom_workspace_sidebar_display_key(st,s)
    assert {k:s[k] for k in PROTECTED}==before
    assert s[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET]=='C'
    assert not s.get('_custom_page_sidebar_overlay')
    # Editing the preview is not Set Active Song, including a deferred widget update.
    s['_streamlit_widgets_locked_this_run']=True
    sync_custom_workspace_practice_key(s,practice_key='Eb',active=s.get(CPL_ACTIVE_KEY))
    s['_streamlit_widgets_locked_this_run']=False
    prepare_custom_workspace_sidebar_display_key(st,s)
    assert s[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET]=='Eb'
    assert {k:s[k] for k in PROTECTED}==before
    for destination in ('practice','backing'):
        navigate_studio_page(s,destination)
        assert {k:s[k] for k in PROTECTED}==before

@pytest.mark.parametrize('page', ['custom','practice','backing'])
def test_custom_global_active_still_projects_its_own_key(page):
    active=default_active_progression();active['name']='Explicit Custom'
    pick=custom_pick_key_for(active)
    s=dict(studio_page=page,active_music_source='custom_progression',
           active_catalog_pick_key=pick,selected_song={'title':'Explicit Custom','pick_key':pick},
           cpl_active_progression=active,display_key='C',concert_key='C',
           practice_key_by_source={pick:'C'})
    sync_custom_workspace_practice_key(s,practice_key='Eb',active=active)
    prepare_custom_workspace_sidebar_display_key(SimpleNamespace(session_state=s),s)
    assert s['display_key']=='Eb'
    assert s['concert_key']=='Eb'
    assert s['active_music_source']=='custom_progression'
    assert s['active_catalog_pick_key']==pick

@pytest.mark.parametrize('source', ['catalog_song', 'composition_song'])
def test_loading_another_custom_draft_preserves_external_pending_key(source):
    from custom_progression_lab import apply_cpl_session_progression
    s = session_for(source, 'custom')
    before = {k:deepcopy(s[k]) for k in PROTECTED}
    draft = default_active_progression()
    draft['name'] = 'Previously saved Custom'
    draft['original_key_center'] = 'Eb'
    apply_cpl_session_progression(s, draft, reset_display_key=True)
    prepare_custom_workspace_sidebar_display_key(SimpleNamespace(session_state=s), s)
    assert {k:s[k] for k in PROTECTED} == before
    assert s[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] == 'Eb'

@pytest.mark.parametrize('source', ['catalog_song', 'composition_song'])
def test_only_explicit_set_active_song_promotes_custom(source, monkeypatch):
    from songs.music_source import commit_custom_active_song
    import songs.state
    monkeypatch.setattr(songs.state, 'persist_music_local_state', lambda *a, **kw: None)
    s = session_for(source, 'custom')
    draft = default_active_progression()
    draft['name'] = 'Explicitly promoted Custom'
    draft['original_key_center'] = 'Eb'
    draft['original_sections']['Verse'] = [{'chord':'Eb','bars':1}]
    s[CPL_ACTIVE_KEY] = draft
    st = SimpleNamespace(session_state=s)
    prepare_custom_workspace_sidebar_display_key(st, s)
    assert s['active_music_source'] == source
    assert s['display_key'] == 'G'
    commit_custom_active_song(st, draft, invalidate_backing=lambda *args: None)
    assert s['active_music_source'] == 'custom_progression'
    assert s['active_catalog_pick_key'].startswith('custom::')
    assert s['selected_song']['title'] == 'Explicitly promoted Custom'
    assert s['display_key'] == 'Eb'
    for page in ('practice', 'backing'):
        navigate_studio_page(s, page)
        prepare_custom_workspace_sidebar_display_key(st, s)
        assert s['active_music_source'] == 'custom_progression'
        assert s['display_key'] == 'Eb'
