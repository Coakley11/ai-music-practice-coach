"""Detached project ownership and facts about an actually rendered mix."""
from __future__ import annotations

import hashlib
from typing import Any


def retain_project_source(session: Any) -> dict:
    """Bind once when the first layer arrives; an unknown legacy owner stays unknown."""
    if 'mt_activity_source_context' not in session:
        session['mt_activity_source_context'] = {}
        try:
            from music_progress_activity import _context, mission_activity_context
            # Existing layers without an owner predate this contract.
            if not any((session.get('mt_tracks') or {}).values()):
                session['mt_activity_source_context'] = _context(session, mission_activity_context(session))
        except Exception:
            pass  # Reporting metadata must not prevent a layer from being saved.
    return dict(session.get('mt_activity_source_context') or {})


def capture_mix(session: Any, audio: bytes, tracks: list[dict], *, include_backing: bool) -> None:
    """Freeze small factual metadata at rendering, without retaining layer/audio payloads."""
    from media_multitrack_catalog import active_catalog_multitrack_id
    from media_multitrack_export_catalog import wav_duration_seconds
    audible = [t for t in tracks if not t.get('mute')]
    if any(t.get('solo') for t in tracks):
        audible = [t for t in audible if t.get('solo')]
    session['mt_activity_mix_snapshot'] = dict(
        retain_project_source(session),
        multitrack_id=active_catalog_multitrack_id(session) or None,
        audio_digest=hashlib.sha256(audio).hexdigest(),
        track_count=len(audible) + int(include_backing),
        duration_seconds=wav_duration_seconds(audio), format='wav')


def saved_mix_facts(session: Any, audio: bytes) -> dict:
    facts = session.get('mt_activity_mix_snapshot') or {}
    if facts.get('audio_digest') != hashlib.sha256(audio).hexdigest():
        return {}  # A legacy or replaced WAV has no verified ownership snapshot.
    return dict(facts)


def report_export_saved(st: Any, session: Any, row: dict) -> bool:
    """Only a durable export is a milestone. Activity storage must never block media."""
    try:
        from music_resume_payload import _resolve_workspace_id
        from suite_activity_client import record_activity
        safe = {k: row.get(k) for k in ('export_id', 'multitrack_id', 'export_name',
                'source_type', 'source_id', 'song', 'track_count', 'duration_seconds', 'format')}
        if not safe['export_id']:
            return False
        safe['workspace_id'] = _resolve_workspace_id(st=st, session=session)
        # No generic source/Resume inference for an unverified old mix.
        if not safe.get('source_id'):
            safe.update(source_type='', source_id='', song='')
        record_activity('music', 'multitrack_export_saved', page='Multitrack', metrics=safe,
                        summary='Saved multitrack mix ' + str(safe.get('export_name') or 'Untitled mix'))
        return True
    except Exception:
        return False
