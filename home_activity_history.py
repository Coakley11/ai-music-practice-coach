"""Read persisted, workspace-scoped Music practice events, never live song state."""
import json
from pathlib import Path


def load_practice_events(session_state):
    from music_resume_payload import _resolve_workspace_id
    from suite_activity_client import _fallback_path
    workspace = _resolve_workspace_id(session=session_state)
    rows = []
    try:
        from suite_storage_config import cloud_storage_enabled
        if cloud_storage_enabled():
            from suite_storage import load_events
            rows.extend(load_events(limit=500))
    except Exception:
        pass
    try:
        path = _fallback_path('music', {'workspace_id': workspace})
        local = json.loads(Path(path).read_text(encoding='utf8'))
        if isinstance(local, list):
            rows.extend(local)
    except (OSError, ValueError):
        pass
    return [row for row in rows if isinstance(row, dict)
            and row.get('app') == 'music'
            and isinstance(row.get('metrics'), dict)
            and row['metrics'].get('workspace_id') == workspace]


def practice_entry_from_event(event):
    """Accept only versioned practice-context records; navigation is not practice."""
    from activity_time import parse_activity_timestamp, to_display_local
    if not isinstance(event, dict):
        return None
    if event.get('event') != 'practice_session_started':
        return workflow_entry_from_event(event)
    m = event.get('metrics')
    if not isinstance(m, dict) or m.get('activity_schema_version') != 2:
        return None
    timestamp = parse_activity_timestamp(event.get('timestamp'))
    if not timestamp or not m.get('practice_context_id') or not str(m.get('song') or '').strip():
        return None
    return {
        'session_id': 'activity:' + str(m['practice_context_id']),
        'date': to_display_local(timestamp).date().isoformat(),
        'created_at': event['timestamp'],
        'active_song': m['song'], 'artist': m.get('artist', ''),
        'song_id': m.get('pick_key') or m.get('source_id', ''),
        'source_type': m.get('source_type', ''), 'workspace_id': m.get('workspace_id', ''),
        'selected_transposing_instrument': m.get('selected_transposing_instrument', ''),
        **({'capo_fret': m['capo_fret']} if 'capo_fret' in m else
           {'capo_fret': m['guitar_capo_fret']} if 'guitar_capo_fret' in m else {}),
        'instrument': m.get('instrument', ''),
        'practice_concert_key': m.get('practice_key', ''),
        # These keys are shown only if actually captured by the record.
        'written_key': m.get('written_key', ''), 'original_key': m.get('original_key', ''),
        'guitar_shape_key': m.get('guitar_shape_key') or m.get('guitar_capo_shape_key', ''),
        'practice_type': 'backing track' if m.get('backing_active') else 'song practice',
        'focus_area': m.get('focus') or m.get('practice_mode', ''),
        'section_name': m.get('practice_focus_section', ''),
        'resume_payload': dict(m['resume_payload']) if isinstance(m.get('resume_payload'), dict) else {},
    }


def workflow_entry_from_event(event):
    """Known persisted milestones only; navigation or prepared audio is not activity."""
    from activity_time import parse_activity_timestamp, to_display_local
    known = {'backing_track_started': ('backing track', 'resume_payload'),
             'backing_track_completed': ('backing track', 'resume_payload'),
             'mission_started': ('mission practice', 'progress_activity_id'),
             'song_coaching_used': ('song-aware coaching', 'progress_activity_id'),
             'composition_saved': ('composition practice', 'progress_activity_id'),
             'multitrack_export_saved': ('multitrack/upload', 'export_id'),
             'audio_uploaded': ('upload analysis', 'recording_id'),
             'video_uploaded': ('upload analysis', 'recording_id'),
             'recording_reviewed': ('upload analysis', 'recording_id')}
    spec = known.get(event.get('event'))
    m = event.get('metrics')
    stamp = parse_activity_timestamp(event.get('timestamp'))
    if not spec or not isinstance(m, dict) or not stamp or not m.get('workspace_id') or not m.get(spec[1]):
        return None
    if spec[1]=='progress_activity_id' and m.get('activity_schema_version')!=3:
        return None
    payload = dict(m.get('resume_payload') or {}) if isinstance(m.get('resume_payload'), dict) else {}
    return dict(session_id='activity:'+str(m.get('progress_activity_id') or m.get('export_id') or m.get('recording_id') or event.get('id') or event['timestamp']),
                date=to_display_local(stamp).date().isoformat(), created_at=event['timestamp'],
                active_song=m.get('song') or m.get('export_name') or 'Saved recording',
                artist=m.get('artist',''), song_id=m.get('source_id') or payload.get('pick_key',''),
                source_type=m.get('source_type',''), workspace_id=m['workspace_id'],
                instrument=m.get('instrument') or payload.get('instrument',''),
                practice_concert_key=m.get('practice_key') or payload.get('display_key') or m.get('display_key',''),
                practice_type=spec[0], resume_payload=payload,
                multitrack_id=m.get('multitrack_id',''))
