"""Minimum Composition → Songs / Karaoke ownership bridge.

Keeps Composition Studio documents (UUID library) as a first-class music
source without converting them into Catalog or Custom songs.

Scope: pick_key identity, Songs listing/activation, chart/backing projection,
Karaoke activation. Not a Composition Studio editor rewrite.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from composition_document import (
    deep_copy_document,
    document_summary_line,
    harmony_edit_target,
    ordered_sections,
    playback_globals,
    touch_composition,
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_LIBRARY_KEY,
    get_active_document,
    list_library_documents,
    load_library_document,
    save_document_to_library,
    set_active_document,
)

SOURCE_COMPOSITION = "composition_song"
SONG_PICKER_SOURCE_COMPOSITION = "Composition"
GENERIC_COMPOSITION_TITLE = "My Composition"
GENERIC_COMPOSITION_KEY = "C"
COMPOSITION_PICK_PREFIX = "composition::"
COMPOSITION_RECENT_IDS_KEY = "composition_recent_active_ids"
PENDING_COMPOSITION_ACTIVE_SONG_KEY = "_pending_composition_active_song_activation"
COMPOSITION_SONGS_SOURCE_READY_KEY = "_composition_songs_source_ready"


def composition_pick_key_for(doc: dict[str, Any] | None) -> str:
    """Stable pick_key for a Composition document (UUID-owned)."""
    if not isinstance(doc, dict):
        return ""
    doc_id = str(doc.get("id") or "").strip()
    if not doc_id:
        return ""
    return f"{COMPOSITION_PICK_PREFIX}{doc_id}"


def composition_id_from_pick_key(pick_key: str) -> str:
    pk = str(pick_key or "").strip()
    if not pk.startswith(COMPOSITION_PICK_PREFIX):
        return ""
    return pk.removeprefix(COMPOSITION_PICK_PREFIX).strip()


def is_composition_pick_key(pick_key: str) -> bool:
    return bool(composition_id_from_pick_key(pick_key))


def mark_composition_songs_source_ready(session_state: dict[str, Any]) -> None:
    session_state[COMPOSITION_SONGS_SOURCE_READY_KEY] = True


def composition_songs_source_ready(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get(COMPOSITION_SONGS_SOURCE_READY_KEY, True))


def ensure_composition_library_hydrated(session_state: dict[str, Any]) -> dict[str, Any]:
    """Ensure ``composer_saved_compositions`` is available outside Composition Studio.

    Prefer live session library; else hydrate from the composer page snapshot
    (persisted with workspace) without fully restoring composer UI widgets.
    """
    lib = session_state.get(COMPOSER_LIBRARY_KEY)
    if isinstance(lib, dict) and lib:
        mark_composition_songs_source_ready(session_state)
        return lib

    store = session_state.get("_studio_page_snapshots") or {}
    snap = store.get("composer") if isinstance(store, dict) else None
    if isinstance(snap, dict):
        snap_lib = snap.get(COMPOSER_LIBRARY_KEY)
        if isinstance(snap_lib, dict) and snap_lib:
            session_state[COMPOSER_LIBRARY_KEY] = copy.deepcopy(snap_lib)
            if COMPOSER_ACTIVE_KEY not in session_state or not isinstance(
                session_state.get(COMPOSER_ACTIVE_KEY), dict
            ):
                snap_active = snap.get(COMPOSER_ACTIVE_KEY)
                if isinstance(snap_active, dict):
                    session_state[COMPOSER_ACTIVE_KEY] = copy.deepcopy(snap_active)
            mark_composition_songs_source_ready(session_state)
            return session_state[COMPOSER_LIBRARY_KEY]

    session_state.setdefault(COMPOSER_LIBRARY_KEY, {})
    mark_composition_songs_source_ready(session_state)
    return session_state[COMPOSER_LIBRARY_KEY] if isinstance(session_state.get(COMPOSER_LIBRARY_KEY), dict) else {}


def find_composition_document(
    session_state: dict[str, Any],
    pick_key_or_id: str,
) -> dict[str, Any] | None:
    """Resolve a composition document by pick_key or raw UUID."""
    ensure_composition_library_hydrated(session_state)
    token = str(pick_key_or_id or "").strip()
    doc_id = composition_id_from_pick_key(token) or token
    if not doc_id:
        return None

    active = get_active_document(session_state)
    if isinstance(active, dict) and str(active.get("id") or "").strip() == doc_id:
        return deep_copy_document(active)

    lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
    if isinstance(lib, dict):
        doc = lib.get(doc_id)
        if isinstance(doc, dict):
            return deep_copy_document(doc)
    return None


def composition_home_key(doc: dict[str, Any]) -> str:
    pg = playback_globals(doc)
    return str(pg.get("key_center") or "C").strip() or "C"


def ensure_generic_composition_document(session_state: dict[str, Any]) -> dict[str, Any]:
    """Stable first-pass Composition identity: ``My Composition`` in C.

    Used when Composition is the active music source but no document is
    resolvable — never fall back to Catalog/Custom by title matching.
    """
    from composition_document import apply_section_chords, new_composition_document, parse_chord_paste

    ensure_composition_library_hydrated(session_state)
    active = get_active_document(session_state)
    if isinstance(active, dict) and str(active.get("title") or "").strip() == GENERIC_COMPOSITION_TITLE:
        g = active.get("global") if isinstance(active.get("global"), dict) else {}
        if str((g or {}).get("original_key_center") or "").strip() in ("", GENERIC_COMPOSITION_KEY):
            return deep_copy_document(active)

    lib = session_state.get(COMPOSER_LIBRARY_KEY) or {}
    if isinstance(lib, dict):
        for doc in lib.values():
            if not isinstance(doc, dict):
                continue
            if str(doc.get("title") or "").strip() != GENERIC_COMPOSITION_TITLE:
                continue
            prepared = deep_copy_document(doc)
            set_active_document(session_state, prepared)
            return prepared

    doc = new_composition_document(title=GENERIC_COMPOSITION_TITLE)
    doc["global"]["original_key_center"] = GENERIC_COMPOSITION_KEY
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        try:
            apply_section_chords(doc, order[0], parse_chord_paste("C Am F G"))
        except Exception:
            pass
    prepared = touch_composition(doc)
    save_document_to_library(session_state, prepared)
    set_active_document(session_state, prepared)
    return deep_copy_document(prepared)


def composition_title(doc: dict[str, Any]) -> str:
    return str(doc.get("title") or "Untitled Song").strip() or "Untitled Song"


def composition_artist(_doc: dict[str, Any] | None = None) -> str:
    return "Composition"


def composition_selected_song_record(doc: dict[str, Any]) -> dict[str, Any]:
    pick_key = composition_pick_key_for(doc)
    home = composition_home_key(doc)
    return {
        "pick_key": pick_key,
        "title": composition_title(doc),
        "artist": composition_artist(doc),
        "key": home,
        "source": SOURCE_COMPOSITION,
        "is_custom": False,
        "is_composition": True,
        "composition_id": str(doc.get("id") or "").strip(),
    }


def composition_original_sections(doc: dict[str, Any]) -> dict[str, list]:
    """Project Composition form sections into CPL-shaped ``original_sections``.

    Keys are musician-facing section labels. Chord entries keep Composition
    entry shape so ``sections_to_chord_lists`` / expand helpers work.
    """
    out: dict[str, list] = {}
    used_labels: dict[str, int] = {}
    for sec in ordered_sections(doc):
        sid = str(sec.get("id") or "")
        _, resolved = harmony_edit_target(doc, sid)
        target = resolved if isinstance(resolved, dict) else sec
        label = str(target.get("label") or sec.get("label") or "Section").strip() or "Section"
        count = used_labels.get(label, 0) + 1
        used_labels[label] = count
        key = label if count == 1 else f"{label} {count}"
        chords = copy.deepcopy(target.get("chords") or [])
        if chords:
            out[key] = chords
    return out


def composition_as_chart_active(doc: dict[str, Any]) -> dict[str, Any]:
    """CPL-shaped projection for chart/backing — identity stays Composition."""
    pg = playback_globals(doc)
    return {
        "id": str(doc.get("id") or "").strip(),
        "name": composition_title(doc),
        "artist": composition_artist(doc),
        "original_key_center": composition_home_key(doc),
        "user_locked_home_key": True,
        "original_sections": composition_original_sections(doc),
        "bpm": int(pg.get("bpm") or 96),
        "time_signature": str(pg.get("time_signature") or "4/4"),
        "progression_style": str(pg.get("style") or "Pop"),
        "groove_style": str(pg.get("groove") or "Auto"),
        "loops": 2,
        "source": SOURCE_COMPOSITION,
    }


def composition_display_title_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_title: str = "",
) -> str:
    doc = find_composition_document(session_state, pick_key)
    if doc:
        return composition_title(doc)
    fb = str(fallback_title or "").strip()
    if fb:
        return fb
    return "Composition song"


def composition_display_artist_for_pick_key(
    session_state: dict[str, Any],
    pick_key: str,
    *,
    fallback_artist: str = "",
) -> str:
    _ = (session_state, pick_key)
    return str(fallback_artist or "").strip() or composition_artist()


def _push_recent_composition_id(session_state: dict[str, Any], doc_id: str) -> None:
    sid = str(doc_id or "").strip()
    if not sid:
        return
    recent = [str(x) for x in (session_state.get(COMPOSITION_RECENT_IDS_KEY) or []) if str(x).strip()]
    recent = [sid] + [x for x in recent if x != sid]
    session_state[COMPOSITION_RECENT_IDS_KEY] = recent[:20]


def set_composition_source(session_state: dict[str, Any]) -> None:
    from songs.music_source import (
        ACTIVE_MUSIC_SOURCE_KEY,
        EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
        SOURCE_COMPOSITION as _SRC_COMPOSITION,
        USER_CATALOG_SOURCE_CHOICE_KEY,
        explicit_music_source_choice,
    )

    session_state.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
    if explicit_music_source_choice(session_state) != _SRC_COMPOSITION:
        session_state[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = _SRC_COMPOSITION
    mark_composition_songs_source_ready(session_state)
    # Drop stale Custom Backing preference so Songs→Backing cannot revive Custom.
    try:
        from backing_context import (
            BACKING_PREF_CUSTOM,
            clear_backing_source_preference,
            get_backing_source_preference,
        )

        pref = str(get_backing_source_preference(session_state) or "").strip()
        if pref == BACKING_PREF_CUSTOM or pref == "custom":
            clear_backing_source_preference(session_state)
    except Exception:
        session_state.pop("_backing_source_preference", None)
        session_state.pop("backing_source_preference", None)

def is_composition_source(session_state: dict[str, Any]) -> bool:
    from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY
    from songs.state import ACTIVE_CATALOG_PICK_KEY

    if session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_COMPOSITION:
        return True
    pick = str(session_state.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if is_composition_pick_key(pick):
        return True
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        if str(meta.get("music_source") or "") == SOURCE_COMPOSITION:
            return True
        if is_composition_pick_key(str(meta.get("pick_key") or "")):
            return True
    return False


def prepare_composition_backing_handoff(
    session_state: dict[str, Any],
    doc: dict[str, Any],
) -> None:
    try:
        from backing_context import (
            apply_backing_context_to_session,
            build_composition_song_context,
            set_backing_context,
        )

        ctx = build_composition_song_context(session_state, doc=doc)
        set_backing_context(session_state, ctx)
        apply_backing_context_to_session(session_state, ctx)
    except ImportError:
        pass


def commit_composition_active_song(
    st: Any,
    doc: dict[str, Any],
    *,
    invalidate_backing: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    """Promote a saved Composition document to the global active song."""
    from songs.music_source import (
        note_active_source_change,
        on_active_song_identity_changed,
        sync_song_picker_source_widget,
    )
    from songs.playback_defaults import (
        active_song_sync_id,
        playback_song_id,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    ensure_composition_library_hydrated(session)
    prepared = touch_composition(deep_copy_document(doc))
    ensure_workflow = None
    try:
        from composition_document import ensure_workflow as _ensure_workflow

        ensure_workflow = _ensure_workflow
    except ImportError:
        pass
    if ensure_workflow is not None:
        ensure_workflow(prepared)

    # Keep library + active document in sync without inventing a new song.
    set_active_document(session, prepared)
    save_document_to_library(session, prepared)

    integration = prepared.setdefault("integration", {})
    if isinstance(integration, dict):
        integration["practice_ready"] = True

    selected = composition_selected_song_record(prepared)
    pick_key = str(selected.get("pick_key") or "")
    home_key = composition_home_key(prepared)
    practice_key = home_key
    try:
        from practice_key_mode import resolve_practice_concert_key_for_song

        practice_key = resolve_practice_concert_key_for_song(
            session,
            home_key,
            pick_key=pick_key,
            fallback=home_key,
        )
    except ImportError:
        pass

    set_composition_source(session)
    try:
        from songs.music_source import (
            assign_song_picker_source_widget,
            song_picker_composition_option_label,
        )

        assign_song_picker_source_widget(session, song_picker_composition_option_label())
    except Exception:
        session["song_picker_active_source"] = "🪶 Composition"

    try:
        sync_song_picker_source_widget(session, force=True)
    except Exception:
        pass

    pg = playback_globals(prepared)
    default_bpm = int(pg.get("bpm") or 96)
    default_groove = str(pg.get("groove") or "Auto")
    default_meter = str(pg.get("time_signature") or "4/4")
    song_id = playback_song_id(
        is_custom=False,
        song_title=composition_title(prepared),
        song_artist=composition_artist(prepared),
        custom_revision=str(prepared.get("id") or ""),
    )
    sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=song_id, is_custom=False)

    def _invalidate(st_like: Any) -> None:
        if invalidate_backing is not None:
            invalidate_backing(st_like)
        else:
            try:
                from songs.key_state import invalidate_backing_cache

                invalidate_backing_cache(st_like)
            except ImportError:
                pass

    on_active_song_identity_changed(
        st,
        pick_key=pick_key,
        title=str(selected.get("title") or ""),
        artist=str(selected.get("artist") or ""),
        original_key=home_key,
        is_custom=False,
        sync_id=sync_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        default_meter=default_meter,
        display_key=practice_key,
        custom_revision=str(prepared.get("id") or ""),
        song_data=composition_as_chart_active(prepared),
        invalidate_backing=_invalidate,
        force_reset=True,
    )
    note_active_source_change(st, invalidate_backing=_invalidate)

    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key
    _push_recent_composition_id(session, str(prepared.get("id") or ""))

    prepare_composition_backing_handoff(session, prepared)

    try:
        from active_song_state import write_canonical_active_song_state
        from global_active_song_state import sync_active_song_to_canonical

        ctx = {
            "pick_key": pick_key,
            "display_key": practice_key,
            "instrument": str(session.get("instrument") or "").strip(),
            "level": str(session.get("level") or "").strip(),
            "focus": str(session.get("focus") or "").strip(),
            "selected_song": selected,
            "music_source": SOURCE_COMPOSITION,
            "composition_id": str(prepared.get("id") or ""),
            "composition_title": composition_title(prepared),
            "composition_home_key": home_key,
        }
        write_canonical_active_song_state(
            session,
            ctx,
            reason="composition_active_song",
            local_edit=True,
        )
        sync_active_song_to_canonical(session)
    except ImportError:
        pass

    try:
        from songs.state import persist_music_local_state

        # Must bypass startup song_edit suppression so Custom→Composition
        # ownership survives refresh / next-run disk restore.
        persist_music_local_state(st, save_reason="music_source_switch")
    except TypeError:
        try:
            from songs.state import persist_music_local_state

            st.session_state["_music_persist_save_reason"] = "music_source_switch"
            persist_music_local_state(st)
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(session)
    except ImportError:
        pass

    return prepared


def activate_composition_by_pick_key(
    st: Any,
    pick_key: str,
    *,
    invalidate_backing: Callable[[Any], None] | None = None,
) -> bool:
    doc = find_composition_document(st.session_state, pick_key)
    if not doc:
        return False
    commit_composition_active_song(st, doc, invalidate_backing=invalidate_backing)
    return True


def queue_composition_active_song_activation(st: Any, doc_id: str) -> None:
    st.session_state[PENDING_COMPOSITION_ACTIVE_SONG_KEY] = str(doc_id or "").strip()


def apply_pending_composition_active_song_activation_before_widgets(st: Any) -> bool:
    pending = str(st.session_state.pop(PENDING_COMPOSITION_ACTIVE_SONG_KEY, "") or "").strip()
    if not pending:
        return False
    try:
        from songs.key_state import invalidate_backing_cache

        invalidate = invalidate_backing_cache
    except ImportError:
        invalidate = None
    return activate_composition_by_pick_key(st, pending, invalidate_backing=invalidate)


def list_composition_songs_for_picker(session_state: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_composition_library_hydrated(session_state)
    rows = list_library_documents(session_state)
    recent = [str(x) for x in (session_state.get(COMPOSITION_RECENT_IDS_KEY) or []) if str(x)]
    by_id = {str(d.get("id") or ""): d for d in rows if str(d.get("id") or "")}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rid in recent:
        doc = by_id.get(rid)
        if doc:
            ordered.append(doc)
            seen.add(rid)
    for doc in rows:
        sid = str(doc.get("id") or "")
        if sid and sid not in seen:
            ordered.append(doc)
    return ordered


def composition_row_summary(doc: dict[str, Any]) -> str:
    try:
        return document_summary_line(doc)
    except Exception:
        return composition_home_key(doc)


def navigate_new_composition_song(st: Any) -> None:
    """Open Composition Studio for a new song (no fake Songs-page object)."""
    from composition_document import new_composition_document
    from composition_session_state import COMPOSER_NEEDS_SEED_KEY

    ensure_composition_library_hydrated(st.session_state)
    # Leave an empty seed state; Studio owns creation UX.
    st.session_state.pop(COMPOSER_ACTIVE_KEY, None)
    st.session_state[COMPOSER_NEEDS_SEED_KEY] = True
    # Soft-touch a placeholder only if Studio requires an object; prefer seed flow.
    _ = new_composition_document
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(st.session_state, "composer")
    except ImportError:
        st.session_state["studio_page"] = "composer"
