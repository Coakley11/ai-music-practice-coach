"""Practice Key control through the real application and existing ownership router."""
import json,os
from pathlib import Path
import pytest

@pytest.fixture(scope='module')
def app(tmp_path_factory):
    from contextlib import ExitStack
    from unittest.mock import patch
    from streamlit.testing.v1 import AppTest
    data=tmp_path_factory.mktemp('card_key')
    os.environ['MUSIC_APP_DATA_DIR']=str(data)
    os.environ['SUITE_AUTH_ENABLED']='0'
    # The data dir is resolved once at import: in a full-suite process those
    # modules are already loaded on the suite's shared dir, where
    # test_practice_guitar_key_sync left a fixed E guitar shape (the card then
    # opened Blue Bossa in C#m, not Cm).
    with ExitStack() as stack:
        for target in ('suite_workspace.DATA_DIR','suite_user_persistence.DATA_DIR','music_workspace_paths.DATA_DIR'):
            stack.enter_context(patch(target,data))
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'streamlit_music_practice_app.py'),default_timeout=180).run()
        nav(at,'picker')
        dropdown=at.selectbox(key='matching_song_dropdown')
        dropdown.set_value(next(x for x in dropdown.options if x.startswith('Blue Bossa'))).run()
        yield at


def nav(at,page):
    for _ in range(3):
        if at.session_state['studio_page']==page:break
        at.button(key='studio_quick_nav_btn_'+page).click().run()
    assert not at.exception
    assert at.session_state['studio_page']==page


def card(at):
    controls=[w for w in at.selectbox if str(w.key).startswith('card_practice_key::')]
    assert len(controls)==1
    assert controls[0].label=='Practice / Concert Key'
    return controls[0]


def change(at,key,intent):
    from songs.practice_key_state import get_practice_concert_key
    at.session_state['_backing_transport_intent']=intent
    widget=card(at);pick=widget.key.split('::',1)[1]
    widget.set_value(key).run()
    assert not at.exception
    assert at.session_state['_backing_transport_intent']==intent
    assert get_practice_concert_key(at.session_state.filtered_state,pick_key=pick)==key, {
        k:v for k,v in at.session_state.filtered_state.items()
        if k in ('practice_key_by_source','practice_key_user_override_picks','_practice_key_write_router','_pk_user_commit_pick','_pk_user_commit_token','active_catalog_pick_key','cpl_active_progression','display_key','concert_key')
    }
    assert card(at).value==key
    return pick


def test_catalog_row_and_stopped_paused_key_changes(app):
    at=app
    assert card(at).value=='Cm'
    change(at,'Dm','stopped')
    change(at,'Ebm','paused')
    nav(at,'practice');nav(at,'picker')
    assert card(at).value=='Ebm'


def test_custom_row_uses_own_key_and_sidebar(app):
    at=app
    r=at.radio(key='song_picker_active_source')
    r.set_value(next(o for o in r.options if 'Custom' in o)).run()
    from custom_progression_lab import apply_cpl_session_progression
    ss=at.session_state.filtered_state
    apply_cpl_session_progression(ss,json.loads(Path('tests/fixtures/continuation_trial_song.json').read_text()),reset_display_key=True)
    for k,v in ss.items():
        at.session_state[k]=v
    at.run()
    assert card(at).value=='D'
    change(at,'E','stopped')
    assert at.session_state['cpl_active_progression']['original_key_center']=='D'
    from custom_progression_lab import CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET
    assert at.session_state[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET]=='E'


def test_composition_row_and_source_return(app):
    at=app
    r=at.radio(key='song_picker_active_source');r.set_value(next(o for o in r.options if 'Composition' in o)).run()
    original=at.session_state['composer_active_document']['key'] if 'key' in at.session_state['composer_active_document'] else None
    control=card(at);new=next(x for x in control.options if x!=control.value)
    change(at,new,'paused')
    if original is not None:assert at.session_state['composer_active_document']['key']==original
    r=at.radio(key='song_picker_active_source');r.set_value(next(o for o in r.options if 'catalog' in o.lower())).run()
    assert card(at).value=='Ebm'


def test_custom_return_can_select_original_again(app):
    at=app
    r=at.radio(key='song_picker_active_source')
    r.set_value(next(o for o in r.options if 'Custom' in o)).run()
    assert card(at).value=='E', {k:v for k,v in at.session_state.filtered_state.items() if k in ('active_music_source','active_catalog_pick_key','practice_key_by_source','cpl_active_progression','_last_custom_song_state','_practice_key_write_router')}
    change(at,'D','stopped')
    change(at,'E','paused')
