"""Per-song practice key identity — separate from generated workflow keys (Commit 4)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, get_workflow_blob, save_workflow_blob


def song_practice_storage_id(session: dict[str, Any]) -> tuple[str, str]:
    """Stable song identity: (source_type, song_id)."""
    pick = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    try:
        from studio_page_state import resolve_improv_song_source

        if str(resolve_improv_song_source(session) or "") == "Custom progression":
            custom = str(session.get("custom_progression_id") or session.get("cpl_active_id") or "custom").strip()
            return "custom", custom or "custom"
    except ImportError:
        pass
    if not pick:
        pick = "song"
    return "catalog", pick


def song_based_blob_session_id(session: dict[str, Any]) -> str:
    src, sid = song_practice_storage_id(session)
    return sid if src == "catalog" else f"custom|{sid}"


def mission_blob_session_id(session: dict[str, Any]) -> str:
    from music_workflow_mission_session import mission_blob_session_id as _canonical_mission_sid

    return _canonical_mission_sid(session)


def resolve_song_practice_key_token(session: dict[str, Any]) -> str:
    """Authoritative parent practice key from song_based blob (not mission/session projection)."""
    sid = song_based_blob_session_id(session)
    blob = get_workflow_blob(session, "song_based_improvisation", sid)
    if blob is None:
        return ""
    tonic = str(blob.keys.practice_tonic or "C").strip() or "C"
    mode = str(blob.keys.practice_mode or "major").strip().lower()
    if mode == "minor":
        return f"{tonic}m" if not tonic.lower().endswith("m") else tonic
    return tonic


def ensure_song_practice_blob_for_active_song(
    session: dict[str, Any],
    *,
    practice_key: str,
    original_key: str = "",
) -> str:
    """Bind the active catalog song blob to a complete Practice Key on the same rerun."""
    from music_theory import key_center_token, split_key_center

    token = str(practice_key or "").strip()
    if not token:
        return ""
    pt, pm = split_key_center(token)
    token = key_center_token(pt, pm)
    orig = str(original_key or "").strip()
    ot, om = split_key_center(orig) if orig else (pt, pm)
    sid = song_based_blob_session_id(session)
    src, song_id = song_practice_storage_id(session)
    blob = get_workflow_blob(session, "song_based_improvisation", sid)
    if blob is None:
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=sid,
            source_type=src,
            song_id=song_id,
            keys=KeyAuthority(
                original_tonic=ot,
                original_mode=om,
                practice_tonic=pt,
                practice_mode=pm,
                key_owner="song_based_improvisation",
            ),
        )
    else:
        blob.keys = KeyAuthority(
            original_tonic=ot or blob.keys.original_tonic,
            original_mode=om or blob.keys.original_mode,
            practice_tonic=pt,
            practice_mode=pm,
            written_tonic=blob.keys.written_tonic,
            written_mode=blob.keys.written_mode,
            instrument=blob.keys.instrument,
            key_owner="song_based_improvisation",
        )
        blob.song_id = song_id or blob.song_id
        blob.source_type = src or blob.source_type
    save_workflow_blob(session, blob, source="ensure_song_practice_blob_for_active_song")
    return token


def song_practice_blob(session: dict[str, Any]) -> WorkflowStateBlob | None:
    sid = song_based_blob_session_id(session)
    return get_workflow_blob(session, "song_based_improvisation", sid)


def seed_song_practice_blob_from_live_practice_key(session: dict[str, Any]) -> str:
    """When song/mission owns Practice Key but the song blob is missing, seed from live identity.

    Live ``display_key`` (full tonic + mode) is the owner — not catalog original C and not
    leftover jam / mission_jam blob keys. Never overwrite an existing song blob.
    """
    existing = song_practice_blob(session)
    if existing is not None:
        return resolve_song_practice_key_token(session)
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return ""
    try:
        from music_workflow_compatibility import _tonic_mode_from_token
    except ImportError:
        from music_theory import split_key_center

        def _tonic_mode_from_token(key: str) -> tuple[str, str]:
            return split_key_center(str(key or "C"))

    pt, pm = _tonic_mode_from_token(live)
    if pm not in {"major", "minor"}:
        pm = "major"
    sid = song_based_blob_session_id(session)
    src, song_id = song_practice_storage_id(session)
    blob = WorkflowStateBlob(
        workflow_owner="song_based_improvisation",
        workflow_session_id=sid,
        source_type=src,
        song_id=song_id,
        keys=KeyAuthority(
            original_tonic=pt,
            original_mode=pm,
            practice_tonic=pt,
            practice_mode=pm,
            key_owner="song_based_improvisation",
        ),
    )
    save_workflow_blob(session, blob, source="seed_live_practice_key")
    return resolve_song_practice_key_token(session)


def _section_map_total_chords(section_map: dict[str, list[str]] | None) -> int:
    if not isinstance(section_map, dict) or not section_map:
        return 0
    return sum(len(v) for v in section_map.values() if isinstance(v, list))


def rehydrate_full_song_concert_sections(session: dict[str, Any], *, source: str = "song_concert_rehydrate") -> dict[str, list[str]]:
    """Restore full catalog section progression — never a one-chord mission backing slice."""
    try:
        from backing_context import _song_improv_sections_dict

        resolved = _song_improv_sections_dict(session)
        if _section_map_total_chords(resolved) > 1:
            session["improv_song_concert_sections"] = copy.deepcopy(resolved)
            session["_music_song_concert_sections_source"] = source
            return copy.deepcopy(resolved)
    except ImportError:
        pass
    song = song_practice_blob(session)
    if song is not None and isinstance(song.section_map, dict) and _section_map_total_chords(song.section_map) > 1:
        session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
        session["_music_song_concert_sections_source"] = source
        return copy.deepcopy(song.section_map)
    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        out = sync_song_improv_sections_to_practice_key(session)
        if _section_map_total_chords(out) > 1:
            session["_music_song_concert_sections_source"] = source
            return copy.deepcopy(out)
    except ImportError:
        pass
    raw = session.get("improv_song_concert_sections")
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    return {}


def mirror_mission_keys_from_song_blob(session: dict[str, Any]) -> bool:
    """Before mission chord/example mutations — mission blob must not own practice key."""
    song = song_practice_blob(session)
    if song is None:
        return False
    mirror_song_practice_key_to_mission_blob(session, song)
    return True


def sync_session_practice_key_from_song_blob(session: dict[str, Any], *, source: str = "song_blob_sync") -> str:
    """Project display/concert key + concert sections from song_based blob only."""
    song = song_practice_blob(session)
    if song is None:
        return ""
    try:
        from music_workflow_legacy_projection import _practice_key_token

        token = _practice_key_token(song)
    except ImportError:
        token = resolve_song_practice_key_token(session)
    if song.section_map:
        session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
    try:
        from music_workflow_legacy_projection import _project_session_field

        _project_session_field(session, "display_key", token)
        _project_session_field(session, "concert_key", token)
        session["_pending_display_key"] = token
    except ImportError:
        session["display_key"] = token
        session["concert_key"] = token
        session["_pending_display_key"] = token
    session["_music_practice_key_sync_source"] = source
    return token


def mirror_song_practice_key_to_mission_blob(session: dict[str, Any], song_blob: WorkflowStateBlob) -> None:
    """Keep mission_jam blob practice key aligned with the active song blob."""
    sid = mission_blob_session_id(session)
    mission = get_workflow_blob(session, "mission_jam", sid)
    if mission is None:
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id=sid,
            song_id=song_blob.song_id,
            song_title=song_blob.song_title,
            source_type=song_blob.source_type,
        )
    mission.keys = KeyAuthority(
        original_tonic=song_blob.keys.original_tonic,
        original_mode=song_blob.keys.original_mode,
        practice_tonic=song_blob.keys.practice_tonic,
        practice_mode=song_blob.keys.practice_mode,
        written_tonic=song_blob.keys.written_tonic,
        written_mode=song_blob.keys.written_mode,
        instrument=song_blob.keys.instrument,
        key_owner="mission_jam",
    )
    if song_blob.section_map:
        mission.section_map = copy.deepcopy(song_blob.section_map)
    save_workflow_blob(session, mission, source="mirror_song_practice_key")


def reconcile_practice_key_after_active_source_change(
    session: dict[str, Any],
    *,
    pick_key: str = "",
    original_key: str = "",
    previous_pick_key: str = "",
    source: str = "active_source_change",
    force_source_change: bool = False,
) -> str:
    """Practice Key for a newly committed catalog source after an identity change.

    Precedence:
      1. pending sidebar Practice Key edit for this pick
      2. persisted override unique to this pick (not a cross-source leak)
      3. catalog/custom original key

    Never inherit the previous source live transport or a poisoned store slot that
    merely duplicates the prior pick's Practice Key (E4: Love Story C → Country Roads A).
    """
    pick = str(pick_key or session.get("active_catalog_pick_key") or "").strip()
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    original = str(original_key or (sel or {}).get("key") or "").strip() or "C"
    prev_pick = str(previous_pick_key or "").strip()
    if not prev_pick:
        try:
            from songs.music_source import _LAST_ACTIVE_PICK_KEY

            prev_pick = str(session.get(_LAST_ACTIVE_PICK_KEY) or "").strip()
        except ImportError:
            prev_pick = ""
    if not prev_pick:
        # Fall back to the identity we just invalidated (pre-hydrate source commit).
        invalidated_from = str(session.get("_backing_restore_invalidated_from") or "").strip()
        if invalidated_from.startswith("pk::"):
            prev_pick = invalidated_from[4:]
        elif invalidated_from.startswith("creative:"):
            # creative:mission:Country\x1fLove Story — …
            parts = invalidated_from.split(":", 2)
            if len(parts) >= 3 and "\x1f" in parts[2]:
                prev_pick = parts[2].split("|", 1)[0] if "|" in parts[2] else parts[2]
                if prev_pick.startswith("catalog|"):
                    prev_pick = prev_pick.split("|", 1)[-1]
    try:
        from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

        pending = str(pending_selected_practice_key_token(session) or "").strip()
    except ImportError:
        pending = ""
    try:
        from songs.practice_key_state import (
            clear_practice_concert_key,
            get_practice_concert_key,
            resolve_practice_concert_key_for_pick,
            set_practice_concert_key,
        )
    except ImportError:
        chosen = original
    else:
        source_changed = bool(force_source_change) or bool(prev_pick and pick and prev_pick != pick)
        prev_saved = str(get_practice_concert_key(session, prev_pick) or "").strip() if prev_pick else ""
        saved = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        # Treat live as prior-source residue when it matches another pick's saved key.
        if (
            not source_changed
            and live
            and original
            and live != original
            and isinstance(session.get("practice_key_by_source"), dict)
        ):
            for other_pk, other_key in session["practice_key_by_source"].items():
                if str(other_pk or "").strip() != pick and str(other_key or "").strip() == live:
                    source_changed = True
                    if not prev_pick:
                        prev_pick = str(other_pk).strip()
                        prev_saved = live
                    break
        if (
            not source_changed
            and live
            and original
            and live != original
            and not saved
        ):
            # Identity just changed but previous pick was unknown — do not keep foreign live key.
            if force_source_change or str(session.get("_backing_restore_invalidated_from") or "").strip():
                source_changed = True
                prev_saved = live
        # Cross-source leak signature: only when a source change is evident.
        shared_leak = False
        if (
            (source_changed or str(session.get("_backing_restore_invalidated_from") or "").strip())
            and saved
            and original
            and saved != original
            and pick
        ):
            try:
                store = session.get("practice_key_by_source")
                if isinstance(store, dict):
                    for other_pk, other_key in store.items():
                        if (
                            str(other_pk or "").strip()
                            and str(other_pk).strip() != pick
                            and str(other_key or "").strip() == saved
                        ):
                            shared_leak = True
                            if not prev_pick:
                                prev_pick = str(other_pk).strip()
                                prev_saved = saved
                            break
            except Exception:
                shared_leak = False
        if pending:
            chosen = pending
        elif saved and (source_changed or shared_leak) and (
            (prev_saved and saved == prev_saved) or shared_leak
        ) and original and saved != original:
            clear_practice_concert_key(session, pick)
            chosen = original
        elif saved and not (
            (source_changed or shared_leak) and prev_saved and saved == prev_saved
        ):
            chosen = saved
        elif source_changed or shared_leak:
            # Live transport still belongs to the previous song/jam — use catalog original.
            chosen = original
        elif live and original and live != original:
            chosen = live
        elif pick:
            chosen = resolve_practice_concert_key_for_pick(session, pick, original_key=original)
        else:
            chosen = original
        if pick and chosen and not pending:
            set_practice_concert_key(session, chosen, pick_key=pick)
    try:
        from music_source_ownership import trace_practice_key_owner

        trace_practice_key_owner(
            session,
            phase=f"source_change:{source}",
            extra={
                "pick": pick,
                "prev_pick": prev_pick,
                "chosen": chosen,
                "original": original,
                "pending": pending,
            },
        )
    except ImportError:
        pass
    if chosen:
        try:
            ensure_song_practice_blob_for_active_song(
                session,
                practice_key=chosen,
                original_key=original,
            )
        except Exception:
            pass
        try:
            from music_workflow_legacy_projection import _project_session_field

            _project_session_field(session, "display_key", chosen)
            _project_session_field(session, "concert_key", chosen)
            session["_pending_display_key"] = chosen
        except ImportError:
            session["display_key"] = chosen
            session["concert_key"] = chosen
            session["_pending_display_key"] = chosen
        session["_music_practice_key_sync_source"] = source
    return chosen


def reconcile_catalog_practice_key_owner(session: dict[str, Any], *, source: str = "practice_key_reconcile") -> str:
    """Authoritative Practice Key for an active catalog song.

    Precedence:
      1. live ``display_key`` when it differs from catalog original (user selection)
      2. persisted ``practice_key_by_source`` override for the pick
      3. song-practice blob token
      4. catalog original (initialization only)

    Never let a stale blob/original overwrite a live or persisted Practice override.
    Heals store + song blob to the chosen token.
    """
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    original = str((sel or {}).get("key") or "").strip()
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    prev_pick = ""
    try:
        from songs.music_source import _LAST_ACTIVE_PICK_KEY

        prev_pick = str(session.get(_LAST_ACTIVE_PICK_KEY) or "").strip()
    except ImportError:
        prev_pick = ""
    if prev_pick and pick and prev_pick != pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            prev_saved = str(get_practice_concert_key(session, prev_pick) or "").strip()
            if prev_saved and live == prev_saved and original and live != original:
                live = ""
        except ImportError:
            pass
    store = ""
    if pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            store = str(get_practice_concert_key(session, pick) or "").strip()
        except ImportError:
            store = ""
    try:
        from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

        pending = str(pending_selected_practice_key_token(session) or "").strip()
    except ImportError:
        pending = ""
    if pending:
        live = pending
    song_tok = resolve_song_practice_key_token(session)

    jam_tokens: set[str] = set()
    try:
        from generated_jam_key_context import generated_jam_practice_key_tokens

        jam_tokens = generated_jam_practice_key_tokens(session)
    except ImportError:
        leftover = str(session.get("improv_jam_key") or session.get("improv_style_key") or "").strip()
        if leftover:
            jam_tokens.add(leftover)

    def _is_jam_key(tok: str) -> bool:
        return bool(tok) and tok in jam_tokens

    snap_tok = ""
    try:
        from generated_jam_key_context import SONG_PRACTICE_KEY_SNAPSHOT_KEY

        snap = session.get(SONG_PRACTICE_KEY_SNAPSHOT_KEY)
        if isinstance(snap, dict):
            snap_pick = str(snap.get("pick_key") or "").strip()
            if not snap_pick or not pick or snap_pick == pick:
                snap_tok = str(snap.get("display_key") or snap.get("concert_key") or snap.get("practice_concert_key") or "").strip()
    except ImportError:
        snap_tok = ""

    # Generated Jam must never become the active-song Practice Key, including a
    # poisoned practice_key_by_source slot written on a prior leak.
    if _is_jam_key(live):
        if store and not _is_jam_key(store):
            live = store
        elif song_tok and not _is_jam_key(song_tok):
            live = song_tok
        elif snap_tok and not _is_jam_key(snap_tok):
            live = snap_tok
        elif original and not _is_jam_key(original):
            live = original
        else:
            live = ""
    if _is_jam_key(store):
        store = ""
    if _is_jam_key(song_tok):
        song_tok = ""

    if live and original and live != original and not _is_jam_key(live):
        chosen = live
    elif store and original and store != original:
        chosen = store
    elif store:
        chosen = store
    elif live and not _is_jam_key(live):
        chosen = live
    elif song_tok:
        chosen = song_tok
    elif snap_tok and not _is_jam_key(snap_tok):
        chosen = snap_tok
    elif original:
        chosen = original
    else:
        chosen = live or ""

    if _is_jam_key(chosen):
        chosen = snap_tok or original or ""

    try:
        from music_source_ownership import trace_practice_key_owner

        trace_practice_key_owner(
            session,
            phase=f"reconcile:{source}",
            extra={"chosen": chosen, "live": live, "store": store, "jam_tokens": sorted(jam_tokens)},
        )
    except ImportError:
        pass

    if not chosen:
        return ""

    try:
        from songs.practice_key_state import set_practice_concert_key

        if pick and not _is_jam_key(chosen):
            set_practice_concert_key(session, chosen, pick_key=pick)
    except ImportError:
        pass

    if song_tok != chosen or song_practice_blob(session) is None:
        ensure_song_practice_blob_for_active_song(
            session,
            practice_key=chosen,
            original_key=original,
        )
        mirror_mission_keys_from_song_blob(session)

    try:
        from music_workflow_legacy_projection import _project_session_field

        _project_session_field(session, "display_key", chosen)
        _project_session_field(session, "concert_key", chosen)
        session["_pending_display_key"] = chosen
    except ImportError:
        session["display_key"] = chosen
        session["concert_key"] = chosen
        session["_pending_display_key"] = chosen
    session["_music_practice_key_sync_source"] = source
    return chosen


def ensure_missions_parent_practice_key_hydrated(session: dict[str, Any]) -> str:
    """Keep song/mission Practice Key coherent — live/store override wins over stale blob."""
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        mission_active = tab == "Missions" or (ptr and str(ptr.workflow_owner or "") == "mission_jam")
    except ImportError:
        mission_active = tab == "Missions"
    if mission_active:
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session, pre_widget=True)
        except ImportError:
            pass
        seed_song_practice_blob_from_live_practice_key(session)
        mirror_mission_keys_from_song_blob(session)
        # Reconcile Practice Key *before* concert rehydrate so sync cannot transpose
        # using a stale blob token while live identity is already the destination.
        token = reconcile_catalog_practice_key_owner(session, source="missions_tab_song_blob_reconcile")
        rehydrate_full_song_concert_sections(session, source="missions_tab_song_blob_reconcile")
        try:
            from sidebar_key_identity import prime_sidebar_practice_key_from_identity

            prime_sidebar_practice_key_from_identity(session)
        except ImportError:
            pass
        return token or resolve_song_practice_key_token(session)
    try:
        from creative_key_sync import entry_jam_practice_key_authority_active

        if not entry_jam_practice_key_authority_active(session):
            mirror_mission_keys_from_song_blob(session)
            token = reconcile_catalog_practice_key_owner(session, source="missions_tab_song_blob_reconcile")
            rehydrate_full_song_concert_sections(session, source="missions_tab_song_blob_reconcile")
            try:
                from sidebar_key_identity import prime_sidebar_practice_key_from_identity

                prime_sidebar_practice_key_from_identity(session)
            except ImportError:
                pass
            return token or resolve_song_practice_key_token(session)
    except ImportError:
        pass
    token = resolve_song_practice_key_token(session)
    if not token:
        # Still reconcile live/store for catalog Practice Key even without a blob yet.
        return reconcile_catalog_practice_key_owner(session, source="missions_tab_parent_key_no_blob")
    return reconcile_catalog_practice_key_owner(session, source="missions_tab_parent_key")


__all__ = [
    "mirror_mission_keys_from_song_blob",
    "mirror_song_practice_key_to_mission_blob",
    "mission_blob_session_id",
    "reconcile_practice_key_after_active_source_change",
    "reconcile_catalog_practice_key_owner",
    "rehydrate_full_song_concert_sections",
    "resolve_song_practice_key_token",
    "seed_song_practice_blob_from_live_practice_key",
    "song_based_blob_session_id",
    "song_practice_blob",
    "song_practice_storage_id",
    "sync_session_practice_key_from_song_blob",
    "ensure_missions_parent_practice_key_hydrated",
    "ensure_song_practice_blob_for_active_song",
]
