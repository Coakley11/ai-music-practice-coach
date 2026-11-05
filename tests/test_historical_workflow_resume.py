from copy import deepcopy
from unittest.mock import patch

import pytest
from music_resume_payload import apply_music_resume_payload
from tests.test_music_resume_finalize import _mini_catalog


@pytest.mark.parametrize('marker', [True, False])
@pytest.mark.parametrize('key_mode', ['standard', 'fixed'])
@pytest.mark.parametrize('destination', ['missions', 'coaching'])
def test_explicit_workflow_restores_exact_old_owner_without_global_contamination(marker, destination, key_mode):
    catalog, library = _mini_catalog()
    category = next(iter(catalog))
    name = next(iter(catalog[category]))
    catalog[category][name]['key'] = 'Bm'
    from song_catalog import format_pick_key
    pick = format_pick_key(category, name)
    session = dict(workspace_id='daniel', active_catalog_pick_key='custom::newer',
                   active_music_source='custom_progression', instrument='Flute', display_key='F#',
                   practice_key_mode=key_mode,
                   improv_active_mission='Target only guide tones (3rds & 7ths)')
    payload = dict(version=1, workspace_id='daniel', pick_key=pick, source_id=pick,
                   source_type='catalog', resume_kind='creative', studio_page='creative',
                   activity_destination=destination, instrument='Guitar', display_key='Gm',
                   mission='Improvise using only chord tones')
    if marker:
        payload['progress_activity_id'] = 'historical'
    with patch('songs.state.persist_music_local_state'), patch('suite_activity_client.record_activity'):
        assert apply_music_resume_payload(session, payload, song_picker_catalog=catalog, song_library=library)
    from songs.practice_key_state import get_practice_concert_key
    assert session['active_catalog_pick_key'] == pick
    assert session['instrument'] == 'Guitar'
    assert get_practice_concert_key(session, pick) == 'Gm'
    assert session['studio_page'] == 'creative'
    assert session['improv_intelligence_tab'] == ('Missions' if destination == 'missions' else 'Song-Aware Coaching')
    if destination == 'missions':
        assert session['improv_active_mission'] == payload['mission']


@pytest.mark.parametrize('mission', ['', 'deleted mission', None])
def test_invalid_mission_fails_before_changing_active_owner(mission):
    session = dict(workspace_id='daniel', active_catalog_pick_key='newer', song='Newer', instrument='Flute')
    before = deepcopy(session)
    payload = dict(resume_kind='creative', studio_page='creative', activity_destination='missions',
                   pick_key='Pop\x1fAttention', mission=mission)
    assert not apply_music_resume_payload(session, payload)
    assert {k: session[k] for k in before} == before
    assert session['_suite_resume_failure_reason_music'] == 'mission_unavailable'
