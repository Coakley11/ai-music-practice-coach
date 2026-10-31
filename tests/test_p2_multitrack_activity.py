import io
import wave
from types import SimpleNamespace
from unittest.mock import patch
from multitrack_activity import capture_mix, saved_mix_facts, retain_project_source, report_export_saved
from multitrack_session_persistence import reset_multitrack_working_session


def wav():
    f=io.BytesIO()
    with wave.open(f,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
    return f.getvalue()


def test_project_owner_is_bound_once_and_unknown_legacy_fails_closed():
    s={'mt_tracks':{}}
    with patch('music_progress_activity._context',return_value={'source_type':'composition','source_id':'river','song':'River Sketch'}),patch('music_progress_activity.mission_activity_context'):
        assert retain_project_source(s)['source_id']=='river'
    s.update(song='Unrelated catalog',mt_tracks={'Guitar':b'a'})
    assert retain_project_source(s)['source_id']=='river'
    assert retain_project_source({'mt_tracks':{'Guitar':b'legacy'}})=={}


def test_mix_facts_are_immutable_and_count_audible_layers():
    s={'mt_activity_source_context':dict(source_type='composition',source_id='river',song='River Sketch')}
    audio=wav()
    capture_mix(s,audio,[{'slot':'Guitar'},{'slot':'Piano'},{'slot':'Bass','mute':True}],include_backing=False)
    s.update(song='Catalog',instrument='Flute',mt_tracks={})
    facts=saved_mix_facts(s,audio)
    assert (facts['song'],facts['source_id'],facts['track_count'],facts['duration_seconds'])==('River Sketch','river',2,1)
    assert saved_mix_facts(s,audio+b'changed')=={}
    assert not {'audio_bytes','included_tracks','tracks'} & facts.keys()


def test_export_allowlist_and_reporting_failure():
    s={};st=SimpleNamespace(session_state=s)
    row=dict(export_id='e',export_name='QA River Mix',source_id='river',source_type='composition',song='River Sketch',track_count=2,duration_seconds=1,format='wav',audio_bytes=b'secret',included_tracks=[b'secret'])
    with patch('suite_activity_client.record_activity') as record:
        assert report_export_saved(st,s,row)
    m=record.call_args.kwargs['metrics']
    assert not {'audio_bytes','included_tracks','resume_payload'} & m.keys()
    assert m['source_id']=='river'
    with patch('suite_activity_client.record_activity',side_effect=OSError('offline')):
        assert not report_export_saved(st,s,row)


def test_reset_clears_prior_owner_and_render_facts():
    s={'mt_activity_source_context':{'source_id':'old'},'mt_activity_mix_snapshot':{'song':'old'}}
    reset_multitrack_working_session(s)
    assert 'mt_activity_source_context' not in s and 'mt_activity_mix_snapshot' not in s


def test_layer_save_is_not_an_upload_milestone():
    from music_activity import log_media_upload
    with patch('suite_activity_client.record_activity') as record:
        log_media_upload(SimpleNamespace(session_state={}),media_type='audio',filename='same.wav',page='Multitrack')
    record.assert_not_called()


def test_failed_audio_storage_emits_no_saved_export():
    from media_multitrack_export_catalog import save_multitrack_export_from_session
    with patch('media_multitrack_export_catalog.add_multitrack_export',return_value={'export_id':'e'}),patch('media_multitrack_export_catalog.persist_mix_export_audio',return_value={'ok':False}),patch('multitrack_activity.report_export_saved') as report:
        save_multitrack_export_from_session({},wav(),export_name='QA River Mix')
    report.assert_not_called()


def test_source_and_mix_facts_survive_page_snapshot():
    from studio_page_persistence import capture_page_snapshot, restore_page_snapshot
    source={'source_type':'composition','source_id':'river','song':'River Sketch'}
    s={'studio_page':'multitrack','mt_activity_source_context':source}
    capture_mix(s,wav(),[{'slot':'Guitar'},{'slot':'Bass'}],include_backing=False)
    snapshot=capture_page_snapshot(s,'multitrack')
    assert snapshot['mt_activity_source_context']==source
    assert snapshot['mt_activity_mix_snapshot']['track_count']==2


def test_distinct_uploads_get_distinct_shared_resource_ids():
    from recording_activity import capture_upload
    with patch('recording_analysis_context.build_analysis_context_snapshot',return_value={}):
        first=capture_upload({},filename='same.wav');second=capture_upload({},filename='same.wav')
    assert first['recording_id']!=second['recording_id']


def test_catalog_normalizers_preserve_only_safe_project_and_export_ownership():
    from media_state import migrate_multitrack_session, migrate_multitrack_export
    source=dict(source_type='composition',source_id='composition::river',song='River Sketch',instrument='Guitar',practice_key='Eb',audio_bytes=b'private',document={'lyrics':'private'})
    project=migrate_multitrack_session(dict(multitrack_id='p',activity_source_context=source))
    assert project['activity_source_context']=={k:v for k,v in source.items() if k not in {'audio_bytes','document'}}
    export=migrate_multitrack_export(dict(export_id='e',multitrack_id='p',source_type='composition',source_id='composition::river',song='River Sketch'))
    assert (export['source_type'],export['source_id'])==('composition','composition::river')
    assert migrate_multitrack_session(dict(multitrack_id='legacy'))['activity_source_context']=={}
