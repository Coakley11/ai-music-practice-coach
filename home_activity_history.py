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
    if not isinstance(event, dict) or event.get('event') != 'practice_session_started':
        return None
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
        'instrument': m.get('instrument', ''),
        'practice_concert_key': m.get('practice_key', ''),
        # These keys are shown only if actually captured by the record.
        'written_key': m.get('written_key', ''), 'original_key': m.get('original_key', ''),
        'guitar_shape_key': m.get('guitar_shape_key', ''),
        'practice_type': 'backing track' if m.get('backing_active') else 'song practice',
        'focus_area': m.get('practice_mode', ''),
    }
