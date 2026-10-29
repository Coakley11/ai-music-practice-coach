"""A Play remount marker must never overwrite stopped/paused user settings."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from backing_transport_intent import transport_intent,note_playback_settings_changed

@pytest.mark.parametrize('intent',['stopped','paused'])
def test_first_explicit_style_edit_after_play_uses_the_live_selection(intent):
    source=ast.parse(Path('streamlit_music_practice_app.py').read_text(encoding='utf-8'))
    node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_on_backing_filter_change')
    ss={'_backing_transport_intent':intent,'_kc_settings_applied_this_play':True,'backing_groove_style':'Pop groove'}
    scope={'st':SimpleNamespace(session_state=ss),'transport_intent':transport_intent,
           'note_playback_settings_changed':note_playback_settings_changed,'_sync_canonical_backing_after_edit':lambda:None}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<filter callback>','exec'),scope)
    with patch('backing_track_state.canonical_backing_filters',return_value={'backing_groove_style':'Ballad'}):
        scope['_on_backing_filter_change']()
    assert ss['backing_groove_style']=='Pop groove'
    assert transport_intent(ss)==intent


def test_cycle_radio_off_retains_pause_but_explicit_stop_is_terminal():
    from backing_key_cycle import start_key_cycle, stop_key_cycle
    from backing_transport_intent import begin_playback, pause_playback, transport_intent, playback_allowed, restart_on_resume
    ss={'active_music_source':'custom_progression','active_catalog_pick_key':'custom::trial',
        'display_key':'D','concert_key':'D','practice_key_by_source':{'custom::trial':'D'}}
    start_key_cycle(ss)
    begin_playback(ss);pause_playback(ss)
    stop_key_cycle(ss,preserve_pause=True)
    assert transport_intent(ss)=='paused' and not playback_allowed(ss)
    assert restart_on_resume(ss)
    start_key_cycle(ss)
    assert transport_intent(ss)=='paused' and not playback_allowed(ss)
    stop_key_cycle(ss)
    assert transport_intent(ss)=='stopped' and not playback_allowed(ss)


@pytest.mark.parametrize('intent,singing,requested',[
    ('stopped',False,False),('paused',False,False),('playing',False,True),
    ('playing',True,False),('paused',True,False)])
def test_normal_key_rebuild_requires_existing_play_permission(intent,singing,requested):
    from songs.key_state import _request_normal_key_rebuild_if_playing
    ss={'studio_page':'backing','_backing_transport_intent':intent,
        'active_catalog_pick_key':'Jazz\x1fBlue Bossa','display_key':'Ebm'}
    with patch('karaoke_mode.is_karaoke_session_active',return_value=singing):
        _request_normal_key_rebuild_if_playing(ss)
    assert bool(ss.get('_backing_play_request'))==requested
    assert bool(ss.get('_backing_autoplay'))==requested
    assert transport_intent(ss)==intent
    assert ss['active_catalog_pick_key']=='Jazz\x1fBlue Bossa'
