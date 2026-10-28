from copy import deepcopy
from unittest.mock import patch

import pytest

from backing_take_identity import capture_take_request, take_install_allowed
from backing_transport_intent import begin_playback, stop_playback
from backing_owner_envelope import stamp_backing_owner_envelope
from backing_key_cycle import BACKING_KEY_CYCLE_SESSIONS_KEY, BACKING_KEY_CYCLE_PREPARED_KEY, store_prepared_cycle_audio


def trial():
    ss = {'studio_page': 'backing', 'active_music_source': 'custom_progression',
          'active_catalog_pick_key': 'custom::trial',
          'practice_key_by_source': {'custom::trial': 'D'},
          '_explicit_custom_activation_epoch': 1}
    stamp_backing_owner_envelope(ss, source='sbi_custom', identity='custom::trial', practice_key='D', original_key='D')
    begin_playback(ss)
    return ss


def publish(ss, request):
    # Exercise the actual prepared-take writer, without generating music or files.
    store_prepared_cycle_audio(ss, sounding_key='D', signature=('Trial Song', 'D'),
                              static_url='/trial.wav', chart_html='<p>D G A</p>',
                              chords=['D', 'G', 'A'], take_request=request)


def catalog(ss):
    ss.update(active_music_source='catalog', active_catalog_pick_key='Jazz\x1fBlue Bossa',
              _explicit_catalog_selection_epoch=2)
    ss['practice_key_by_source']['Jazz\x1fBlue Bossa'] = 'Cm'
    stamp_backing_owner_envelope(ss, source='catalog', identity='Jazz\x1fBlue Bossa',
                               practice_key='Cm', original_key='Cm')


def test_fence_1_source_race_discards_trial_without_touching_blue_bossa():
    ss=trial(); request=capture_take_request(ss); catalog(ss); before=deepcopy(ss)
    assert not take_install_allowed(ss, request)
    publish(ss, request)
    assert ss == before
    assert ss['active_catalog_pick_key'].endswith('Blue Bossa')


def test_fence_2_saved_practice_key_race():
    ss=trial(); request=capture_take_request(ss)
    ss['practice_key_by_source']['custom::trial']='Eb'
    publish(ss, request)
    assert BACKING_KEY_CYCLE_PREPARED_KEY not in ss


def test_fence_3_position_two_cannot_publish_as_position_four():
    ss=trial()
    with patch('backing_key_cycle.resolve_cycle_owner', return_value='custom'):
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY]={'custom': {'cycle_id':'cycle-1', 'position_seq':2, 'current_playback_key':'Eb', 'offset_semitones':1}}
        request=capture_take_request(ss)
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY]['custom'].update(position_seq=4,current_playback_key='F',offset_semitones=3)
        publish(ss, request)
        assert BACKING_KEY_CYCLE_PREPARED_KEY not in ss
        assert ss[BACKING_KEY_CYCLE_SESSIONS_KEY]['custom']['position_seq']==4


def test_fence_4_stop_during_render_cannot_publish():
    ss=trial(); request=capture_take_request(ss); stop_playback(ss)
    publish(ss, request)
    assert BACKING_KEY_CYCLE_PREPARED_KEY not in ss


def test_fence_5_same_source_after_roundtrip_requires_current_generation():
    ss=trial(); old=capture_take_request(ss); catalog(ss)
    ss.update(active_music_source='custom_progression',active_catalog_pick_key='custom::trial',_explicit_custom_activation_epoch=3)
    stamp_backing_owner_envelope(ss,source='sbi_custom',identity='custom::trial',practice_key='D',original_key='D')
    current=capture_take_request(ss)
    publish(ss,old)
    assert BACKING_KEY_CYCLE_PREPARED_KEY not in ss
    publish(ss,current)
    assert ss[BACKING_KEY_CYCLE_PREPARED_KEY]['D']['static_url']=='/trial.wav'


def test_read_is_immutable_and_pause_does_not_discard_valid_preparation():
    from backing_transport_intent import pause_playback, playback_allowed
    ss=trial(); before=deepcopy(ss); request=capture_take_request(ss)
    assert ss==before
    pause_playback(ss)
    assert take_install_allowed(ss,request)
    publish(ss,request)
    assert not playback_allowed(ss)


def test_prefetch_survives_navigation_but_not_cycle_generation_or_stop():
    ss=trial()
    with patch('backing_key_cycle.resolve_cycle_owner', return_value='custom'):
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY]={'custom':{'cycle_id':'a','position_seq':2,'current_playback_key':'Eb'}}
        request=capture_take_request(ss,prefetch=True)
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY]['custom'].update(position_seq=4,current_playback_key='F')
        assert take_install_allowed(ss,request), 'neighbors remain useful by their own key'
        ss[BACKING_KEY_CYCLE_SESSIONS_KEY]['custom']['cycle_id']='b'
        assert not take_install_allowed(ss,request)
    stop_playback(ss)
    assert not take_install_allowed(ss,request)

def test_prepared_content_cannot_be_reused_after_source_switch():
    from backing_key_cycle import prepared_cycle_chart_html, prepared_cycle_follow_timeline, promote_prepared_cycle_audio, prepared_cycle_static_url
    ss=trial();publish(ss,capture_take_request(ss));catalog(ss)
    assert prepared_cycle_chart_html(ss,'D')==''
    assert prepared_cycle_follow_timeline(ss,'D')==[]
    assert prepared_cycle_static_url(ss,'D')==''
    assert not promote_prepared_cycle_audio(ss,'D')
    assert '_last_backing_signature' not in ss


def test_unstamped_take_fails_closed():
    from backing_key_cycle import prepared_cycle_chart_html
    ss=trial();ss[BACKING_KEY_CYCLE_PREPARED_KEY]={'D':{'chart_html':'wrong owner'}}
    assert prepared_cycle_chart_html(ss,'D')==''


def test_completed_preparation_never_grants_playback_permission():
    from backing_transport_intent import pause_playback,playback_allowed
    for paused in (False,True):
        ss=trial()
        if paused:pause_playback(ss)
        else:stop_playback(ss)
        publish(ss,capture_take_request(ss))
        assert not playback_allowed(ss)

def test_karaoke_take_belongs_to_now_singing_not_now_editing():
    import karaoke_mode as km
    ss=trial();ss['instrument']='Voice'
    km.add_to_queue(ss,'Jazz\x1fBlue Bossa',title='Blue Bossa',artist='',practice_key='Cm',bpm=135)
    km.start_session(ss)
    request=capture_take_request(ss)
    catalog(ss)
    assert take_install_allowed(ss,request)
    assert request.practice_key=='Cm'
