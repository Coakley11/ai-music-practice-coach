"""Explicit historical Practice restoration, staged before global widgets mount."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

REQUEST = '_home_recent_resume_request'
ERROR = '_home_recent_resume_error'
STAGING = '_home_recent_resume_staging'

@dataclass(frozen=True)
class RestorePlan:
    payload: dict
    instrument: str
    transposing_type: str
    focus: str
    shape: str
    capo: int


def prepare_restore(record: dict, session: Any, catalog: dict) -> tuple[RestorePlan | None, str]:
    """Fail closed: no title guessing, cross-workspace reads or missing source revival."""
    from music_resume_payload import _resolve_workspace_id, payload_workspace_matches
    from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS, focus_options_for_instrument
    from instrument_transposition import saxophone_type_for_display_name, options_for_instrument
    from music_theory import key_center_token, split_key_center
    if not isinstance(record, dict) or record.get('deleted'):
        return None, 'This historical record is unavailable.'
    saved = record.get('resume_payload')
    p = dict(saved) if isinstance(saved, dict) else {}
    ws = _resolve_workspace_id(session=session)
    for data in (record, p):
        if data.get('workspace_id') and not payload_workspace_matches(data, ws):
            return None, 'This session belongs to another workspace.'
    pick = str(p.get('pick_key') or record.get('song_id') or record.get('pick_key') or record.get('source_id') or '').strip()
    key = str(record.get('practice_concert_key') or (p.get('display_key') if p.get('key_kind') == 'concert' else '') or '').strip()
    instrument = str(record.get('instrument') or p.get('instrument') or '').strip()
    if not pick or not key or not instrument:
        return None, 'Full restoration is unavailable: this record lacks a reliable song ID, concert key or instrument.'
    try:
        import re
        if not re.fullmatch(r"[A-G](?:#|b|♯|♭)?(?:m| minor| major)?", key):
            raise ValueError("invalid key label")
        normalized_key = key_center_token(*split_key_center(key))
        if not normalized_key:
            raise ValueError('missing key')
        from music_theory import ENHARMONIC_MAJOR_KEYS, ENHARMONIC_MINOR_KEYS
        if normalized_key not in list(ENHARMONIC_MAJOR_KEYS)+list(ENHARMONIC_MINOR_KEYS):
            raise ValueError('invalid key')
    except (ValueError,TypeError):
        return None, 'The recorded concert key is not supported.'
    subtype = saxophone_type_for_display_name(instrument)
    if subtype:
        instrument = 'Saxophone'
    elif instrument not in DEFAULT_INSTRUMENT_OPTIONS:
        return None, 'The recorded instrument is not supported.'
    choices = options_for_instrument(instrument)
    if choices and not subtype:
        subtype = str(record.get('selected_transposing_instrument') or p.get('selected_transposing_instrument') or '')
        if not subtype and len(choices)==1:
            subtype = choices[0]
        if subtype not in choices:
            return None, 'This record does not identify the transposing instrument type.'
    focus = str(record.get('focus_area') or p.get('focus') or '').strip()
    options = focus_options_for_instrument(instrument)
    if focus and focus not in options:
        # Practice Log stores canonical categories (e.g. soloing/improv), whereas
        # global controls use instrument-specific labels. Accept only a unique
        # match through the existing log normalizer, never a guessed first option.
        from practice_log_state import _normalize_focus_area
        matches = [o for o in options if _normalize_focus_area(o) == focus]
        if focus == 'general':
            focus = ''
        elif len(matches) == 1:
            focus = matches[0]
        else:
            return None, 'The saved practice focus is unavailable for this instrument.'
    if pick.startswith('custom::'):
        from songs.music_source import custom_progression_for_pick_key
        if custom_progression_for_pick_key(session,pick) is None:
            return None, 'The saved Custom song is no longer available.'
        source = 'custom'
    elif pick.startswith('composition::'):
        from composition_songs_bridge import find_composition_document
        if not find_composition_document(session,pick):
            return None, 'The saved Composition document is no longer available.'
        source = 'composition'
    else:
        from songs.state import resolve_pick_key
        pick = resolve_pick_key(pick,song_picker_catalog=catalog)
        if not pick:
            return None, 'The recorded Catalog song is unavailable or ambiguous.'
        source = 'catalog'
    if p.get('source_id') and p['source_id'] != pick:
        return None, 'The saved source identifiers disagree.'
    if record.get('song_id') and p.get('pick_key') and record['song_id'] != p['pick_key']:
        return None, 'The saved song identifiers disagree.'
    declared = p.get('source_type') or record.get('source_type')
    declared = {'catalog_song':'catalog','custom_progression':'custom','composition_song':'composition'}.get(declared,declared)
    if declared and declared != source:
        return None, 'The saved song identity and source disagree.'
    try:
        capo = int(record.get('capo_fret',p.get('capo_fret',0)))
        if not 0 <= capo <= 12:raise ValueError('capo')
    except (ValueError,TypeError):
        return None, 'The recorded capo setup is invalid.'
    shape = str(record.get('guitar_shape_key') or p.get('guitar_shape_key') or '').strip()
    if instrument=='Guitar' and 'capo_fret' not in record and 'capo_fret' not in p:
        return None, 'The saved guitar capo setup is unavailable.'
    if instrument=='Guitar' and (capo or shape):
        from guitar_capo import capo_fret_for_shape
        if not shape or key_center_token(*split_key_center(shape)) not in list(ENHARMONIC_MAJOR_KEYS)+list(ENHARMONIC_MINOR_KEYS):
            return None, 'The saved guitar shape is incomplete.'
        if capo_fret_for_shape(normalized_key,shape) != capo:
            return None, 'The recorded shape, capo and concert key disagree.'
    # Home Resume restores a practice session; never import arbitrary tool/engine fields.
    payload = dict(version=1,workspace_id=ws,pick_key=pick,source_id=pick,source_type=source,
                   resume_kind='practice',studio_page='practice',key_kind='concert',
                   display_key=normalized_key,instrument=instrument)
    section = str(record.get('section_name') or p.get('practice_focus_section') or '').strip()
    if section:payload['practice_focus_section']=section
    return RestorePlan(payload,instrument,subtype,focus,shape,capo), ''


def _clone(value):
    """Clone musical containers, sharing opaque caches/audio objects rather than duplicating RAM."""
    if isinstance(value,dict):return {k:_clone(v) for k,v in value.items()}
    if isinstance(value,list):return [_clone(v) for v in value]
    if isinstance(value,tuple):return tuple(_clone(v) for v in value)
    if isinstance(value,set):return set(value)
    if hasattr(value,'__dataclass_fields__'):return deepcopy(value)
    return value


def restore_recent_practice(session: Any, record: dict, catalog: dict, library: dict | None=None) -> tuple[bool,str]:
    from music_resume_payload import apply_music_resume_payload
    plan,reason = prepare_restore(record,session,catalog)
    if plan is None:return False,reason
    try:
        stage = _clone(dict(session))
    except Exception:
        return False, 'This session could not be safely staged; your current setup is unchanged.'
    stage[STAGING]=True
    stage['_suite_active_workspace_id'] = plan.payload['workspace_id']
    # These are previous-run widget guards, not current widgets: this runs pre-widget.
    stage['_streamlit_widgets_locked_this_run']=False
    try:
        proxy=SimpleNamespace(session_state=stage)
        if not apply_music_resume_payload(stage,plan.payload,song_picker_catalog=catalog,song_library=library,st=proxy):
            return False,'The historical source could not be activated; your current setup is unchanged.'
        pick = plan.payload['pick_key']
        if not pick.startswith(('custom::', 'composition::')):
            # A source-owner switch can hydrate its former Catalog record during
            # activation. Reapply the now-committed pick through the same API;
            # never publish an ID paired with a different selected-song record.
            if (stage.get('selected_song') or {}).get('pick_key') != pick:
                from songs.state import activate_active_song_by_pick_key
                if not activate_active_song_by_pick_key(proxy, pick, catalog, song_library=library, origin='restore'):
                    return False, 'The historical song identity could not be synchronized.'
            if (stage.get('selected_song') or {}).get('pick_key') != pick:
                return False, 'The historical song identity could not be synchronized.'
        from practice_setup_globals import set_active_instrument,set_active_focus
        set_active_instrument(stage,plan.instrument,source='home_recent_resume')
        if plan.focus:set_active_focus(stage,plan.focus,source='home_recent_resume')
        if plan.transposing_type:
            from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY,PENDING_SELECTED_TRANSPOSING_INSTRUMENT
            stage[SELECTED_TRANSPOSING_INSTRUMENT_KEY]=plan.transposing_type
            stage.pop(PENDING_SELECTED_TRANSPOSING_INSTRUMENT,None)
        from songs.key_state import apply_display_key_for_active_song,song_display_identity
        rec=stage['selected_song'];pick=plan.payload['pick_key'];key=plan.payload['display_key']
        apply_display_key_for_active_song(proxy,str(rec.get('key') or stage.get('custom_home_key') or key),song_display_identity(rec.get('title',''),rec.get('artist',''),rec.get('key',''),pick_key=pick),pending_key=key)
        from songs.practice_key_state import mark_practice_key_user_override
        mark_practice_key_user_override(stage,pick)
        if pick.startswith('custom::'):
            from custom_progression_lab import sync_custom_workspace_practice_key
            sync_custom_workspace_practice_key(stage,practice_key=key,source='home_recent_resume')
            stage.pop('_cpl_force_pk_to_home',None)
        elif pick.startswith('composition::'):
            from composition_songs_bridge import commit_composition_owned_practice_key
            commit_composition_owned_practice_key(stage,key,user_choice=True)
        from guitar_capo import CAPO_ENABLED_KEY,CAPO_SHAPE_KEY,CAPO_SOUNDING_KEY,CAPO_LAST_CONCERT_KEY,sync_capo_widgets_from_canonical
        stage[CAPO_ENABLED_KEY]=bool(plan.instrument=='Guitar' and plan.shape)
        stage[CAPO_SHAPE_KEY]=plan.shape if plan.instrument=='Guitar' else ''
        stage[CAPO_SOUNDING_KEY]=key;stage[CAPO_LAST_CONCERT_KEY]=key
        stage['guitar_capo_fret']=plan.capo if plan.instrument=='Guitar' else 0
        sync_capo_widgets_from_canonical(stage)
        from instrument_transposition import resolve_practice_keys
        keys=resolve_practice_keys(stage,key,plan.instrument)
        if stage.get('active_catalog_pick_key')!=pick or stage.get('display_key')!=key or keys['concert_key']!=key:
            return False,'The saved setup could not be synchronized; your current setup is unchanged.'
        # Commit the explicit restored context through the existing canonical edit
        # boundary before autosave can project a previous canonical song.
        from active_song_state import gather_active_song_context, write_canonical_active_song_state
        restored_context = write_canonical_active_song_state(
            stage, gather_active_song_context(stage), reason='home_recent_resume', local_edit=True,
            mutate_display_key=False, mutate_written_key=False,
            mutate_transposing_subtype=False, apply_global_controls_to_session=False)
        if restored_context.get('pick_key') != pick or restored_context.get('display_key') != key:
            return False, 'The canonical historical context could not be synchronized.'
        # Source activation snapshots its original key. Rebuild that same owner's
        # Backing context only after the historical key/instrument are authoritative.
        from backing_context import (get_backing_context, refresh_backing_context_from_session,
                                     set_backing_context, sync_regular_song_backing_context_keys)
        ctx = get_backing_context(stage)
        expected_source = ('custom_progression' if pick.startswith('custom::') else
                           'composition_song' if pick.startswith('composition::') else 'regular_song')
        if ctx is not None and ctx.source == expected_source:
            if expected_source == 'regular_song':
                sync_regular_song_backing_context_keys(stage)
            else:
                refreshed = refresh_backing_context_from_session(stage)
                if refreshed is not None:
                    set_backing_context(stage, refreshed, trace_caller='home_recent_resume')
        # Explicit current values outrank prior per-page filters/widgets and snapshots.
        for name in ('_home_catalog_browse','_home_catalog_request','_pending_history_creative_dest'):
            stage.pop(name,None)
        from studio_page_persistence import sanitize_persisted_snapshots,save_page_snapshot
        sanitize_persisted_snapshots(stage)
        # Activation may have captured Backing before the historical key was applied.
        save_page_snapshot(stage,'backing')
        save_page_snapshot(stage,'practice')
        stage.pop(STAGING,None);stage.pop(REQUEST,None);stage.pop(ERROR,None)
    except Exception:
        return False,'The historical session could not be restored; your current setup is unchanged.'
    # All owner APIs, instrument/key derivation and validation succeeded before publishing.
    for name in tuple(session):
        if name not in stage:del session[name]
    for name,value in stage.items():
        old=session.get(name)
        if name in session and old is value:
            continue
        try:
            unchanged = name in session and bool(old == value)
        except (TypeError,ValueError):
            unchanged = False
        if not unchanged:
            session[name]=value
    return True,''


def finalize_recent_practice(st: Any, catalog: dict, library: dict | None=None) -> bool:
    session=st.session_state;request=session.get(REQUEST)
    if not request:return False
    from music_workspace_hydration import can_finalize_music_restore
    if not can_finalize_music_restore(session):return False
    session.pop(REQUEST,None)
    ok,reason=restore_recent_practice(session,request,catalog,library)
    if not ok:
        session[ERROR]=reason;return False
    from songs.state import persist_music_local_state
    persist_music_local_state(st,save_reason='music_source_switch')
    return True
