from copy import deepcopy
from home_recent_session import verified_recent_session
from home_activity_history import practice_entry_from_event


def event(**changes):
    row={'app':'music','event':'practice_session_started','timestamp':'2026-11-04T14:00:00Z',
         'metrics':{'activity_schema_version':2,'practice_context_id':'p1',
                    'workspace_id':'guest','song':'Recorded song','artist':'Recorded artist',
                    'instrument':'Piano','practice_key':'F'}}
    row.update(changes)
    return row


def test_recent_compares_log_and_activity_and_never_borrows_live_metadata():
    state={'_suite_active_workspace_id':'guest','selected_song':{'title':'Live song','artist':'Live artist'},'display_key':'A','original_key':'C'}
    before=deepcopy(state)
    old={'session_id':'log1','date':'2026-11-03','active_song':'Old song'}
    result=verified_recent_session(state,entries=[old],activities=[event()])
    assert result.song_title=='Recorded song' and result.artist=='Recorded artist'
    assert dict(result.key_parts)=={'Practice/Concert key':'F'}
    assert state==before
    newer={**old,'date':'2026-11-05','active_song':'Later logged song'}
    assert verified_recent_session(state,entries=[newer],activities=[event()]).song_title=='Later logged song'


def test_navigation_upload_and_legacy_events_are_not_practice():
    assert practice_entry_from_event(event(event='studio_page_entered')) is None
    assert practice_entry_from_event(event(event='media_uploaded')) is None
    assert practice_entry_from_event(event(metrics={'song':'Unverified'})) is None
    assert practice_entry_from_event(event(timestamp='bad')) is None


def test_activity_reader_rejects_other_workspaces(tmp_path):
    import json
    from unittest.mock import patch
    from home_activity_history import load_practice_events
    path=tmp_path/'events.json'
    foreign=event(); foreign['metrics']['workspace_id']='daniel'
    path.write_text(json.dumps([event(),foreign]),encoding='utf8')
    with patch('suite_storage_config.cloud_storage_enabled',return_value=False), patch('suite_activity_client._fallback_path',return_value=path):
        assert len(load_practice_events({'_suite_active_workspace_id':'guest'}))==1
