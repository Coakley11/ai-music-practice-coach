"""Small, read-only progress snapshots for Command Center; never creative documents."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _workspace(session: Any) -> str:
    from music_resume_payload import _resolve_workspace_id
    return _resolve_workspace_id(session=session)


def _context(session: Any, ctx: Any) -> dict[str, str]:
    from song_coach_context import global_song_identity, source_owner
    if not ctx.available or not ctx.identity or ctx.source_kind != source_owner(session):
        return {}
    if ctx.identity != global_song_identity(session, ctx.source_kind):
        return {}
    source, separator, pick = ctx.identity.partition('|')
    if not separator or not pick or source not in {'catalog', 'custom', 'composition'}:
        return {}
    # An editing document can differ from the global active song. Fail closed.
    if source == 'composition':
        from composition_session_state import get_active_document
        from composition_songs_bridge import composition_pick_key_for
        if composition_pick_key_for(get_active_document(session) or {}) != pick.replace('composition\x1f', 'composition::', 1):
            return {}
    elif source == 'custom':
        from songs.music_source import custom_pick_key_for
        if custom_pick_key_for(session.get('cpl_active_progression') or {}) != pick.replace('custom\x1f', 'custom::', 1):
            return {}
    return dict(source_type=source, source_id=pick, song=str(ctx.song_title or '')[:160],
                instrument=str(ctx.instrument or '')[:80], practice_key=str(ctx.concert_key or '')[:16])


def mission_activity_context(session: Any) -> Any:
    """Read the Mission's underlying song owner, independent of its collapsed chord map."""
    from types import SimpleNamespace
    from song_coach_context import (source_owner, global_song_identity, live_catalog_record,
                                    _active_custom, _active_composition)
    from songs.practice_key_state import get_practice_concert_key
    from mission_owner_contract import resolve_mission_underlying_practice_key
    owner = source_owner(session)
    identity = global_song_identity(session, owner)
    pick = identity.partition('|')[2]
    record = (live_catalog_record(session) if owner == 'catalog' else
              _active_custom(session) if owner == 'custom' else _active_composition(session))
    title = str(record.get('title') or record.get('name') or '')
    key = get_practice_concert_key(session, pick) or resolve_mission_underlying_practice_key(session)
    return SimpleNamespace(available=bool(pick and record), identity=identity, source_kind=owner,
                           song_title=title, instrument=session.get('instrument', ''), concert_key=key)


def _emit(session: Any, event: str, metrics: dict, *, identity: Any, destination: str,
          stable: bool = False) -> bool:
    """Deduplicate user milestones before submitting a detached, allowlisted snapshot."""
    from music_activity import submit_activity_snapshot
    workspace = _workspace(session)
    signature = _digest([workspace, event, identity])
    seen = session.setdefault('_progress_activity_seen', {})
    if signature in seen:
        return False
    activity_id = signature if stable else uuid.uuid4().hex
    metrics = dict(metrics, activity_schema_version=3, progress_activity_id=activity_id,
                   workspace_id=workspace)
    page = 'composer' if destination == 'composition' else 'creative'
    if destination in {'missions', 'coaching'} and metrics['source_type'] == 'catalog':
        payload = dict(version=1, progress_activity_id=activity_id, workspace_id=workspace,
                       resume_kind='creative', studio_page=page, activity_destination=destination,
                       pick_key=metrics['source_id'], source_type=metrics['source_type'],
                       source_id=metrics['source_id'], song=metrics.get('song', ''),
                       instrument=metrics.get('instrument', ''), display_key=metrics.get('practice_key', ''))
        if destination == 'missions':
            payload['mission'] = metrics['mission']
        metrics['resume_payload'] = payload
    # The worker receives no session state, local-state snapshot, document or plan.
    submit_activity_snapshot(event, dict(page=page, metrics=metrics,
                                        local_state=None))
    seen[signature] = activity_id
    return True


def report_mission_started(session: Any, ctx: Any, mission: str) -> bool:
    """A generated Mission example is a start, never proof of completion."""
    try:
        from improvisation_intelligence import PRACTICE_MISSIONS
        context = _context(session, ctx)
        if not context or mission not in PRACTICE_MISSIONS:
            return False
        return _emit(session, 'mission_started', dict(context, mission=mission),
                     identity=[context, mission], destination='missions')
    except Exception:
        return False


def report_coaching_used(session: Any, ctx: Any, focus: str) -> bool:
    """Once per song/instrument/concert-key visit, after a successful plan build."""
    try:
        from song_coach_plan import FOCUS_LABELS
        context = _context(session, ctx)
        if not context or focus not in FOCUS_LABELS:
            return False
        return _emit(session, 'song_coaching_used', dict(context, coaching_focus=FOCUS_LABELS[focus]),
                     identity=context, destination='coaching')
    except Exception:
        return False


def report_composition_saved(session: Any, doc: dict, *, durable: bool) -> bool:
    """Only an explicit, confirmed library save calls this; autosaves never do."""
    try:
        if not durable or not doc.get('id'):
            return False
        from composition_document import ordered_sections
        from composition_songs_bridge import composition_home_key
        # Hash only musical/document content locally. Never send this material.
        sections = []
        for section in ordered_sections(doc):
            melody, lyrics = section.get('melody') or {}, section.get('lyrics') or {}
            sections.append({k: section.get(k) for k in ('id', 'label', 'label_variant', 'bars', 'chords')}
                            | dict(melody=melody.get('events'), lyrics=lyrics.get('raw_text') or lyrics.get('lines')))
        fingerprint = _digest([doc.get('title'), doc.get('global'), sections])
        pick = 'composition::' + str(doc['id'])
        from songs.practice_key_state import get_practice_concert_key
        previous = session.setdefault('_progress_composition_saved', {})
        metrics = dict(source_type='composition', source_id=pick,
                       song=str(doc.get('title') or 'Untitled Song')[:160],
                       practice_key=get_practice_concert_key(session, pick) or composition_home_key(doc),
                       composition_milestone='updated' if pick in previous else 'saved')
        sent = _emit(session, 'composition_saved', metrics, identity=[pick, fingerprint],
                     destination='composition', stable=True)
        if sent:
            previous[pick] = fingerprint
        return sent
    except Exception:
        return False
