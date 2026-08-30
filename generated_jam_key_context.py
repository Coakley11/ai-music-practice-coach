"""Generated jam key authority — isolated from catalog song practice key."""

from __future__ import annotations

from typing import Any

GENERATED_JAM_KEY_CONTEXT_KEY = "_generated_jam_key_context"
SONG_PRACTICE_KEY_SNAPSHOT_KEY = "_song_practice_key_snapshot"


def _jam_session_id(session: dict[str, Any]) -> str:
    jam = session.get("improv_jam_session")
    if isinstance(jam, dict) and jam.get("id"):
        return str(jam.get("id"))
    style = str(session.get("improv_jam_style") or session.get("improv_style") or "").strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    return f"{entry}|{style}" if style or entry else entry or "generated_jam"


def _practice_key_from_blob(session: dict[str, Any]) -> tuple[str, str, str]:
    """Return (tonic, mode, sidebar token) from active generated workflow blob."""
    try:
        from music_theory import key_center_token
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if not ptr or str(ptr.workflow_owner or "") not in {"style_jam", "jam_session_generator"}:
            return "", "", ""
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            return "", "", ""
        pt = str(blob.keys.practice_tonic or "C").strip() or "C"
        pm = str(blob.keys.practice_mode or "major").strip().lower() or "major"
        return pt, pm, key_center_token(pt, pm)
    except ImportError:
        return "", "", ""


def refresh_generated_jam_key_context_from_blob(session: dict[str, Any]) -> None:
    """Keep generated-jam key ownership aligned with authoritative blob keys."""
    if not session.get(GENERATED_JAM_KEY_CONTEXT_KEY) and not session.get("_generated_jam_key_owner_active"):
        return
    pt, pm, token = _practice_key_from_blob(session)
    if not token:
        return
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    entry = str(session.get("improv_entry_mode") or (raw.get("entry_mode") if isinstance(raw, dict) else "") or "").strip()
    owner = "jam_session_generator" if "Generator" in entry else "entry_jam"
    session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
        "generated_session_id": _jam_session_id(session),
        "practice_tonic": pt,
        "practice_mode": pm,
        "practice_key_token": token,
        "key_owner": owner,
        "sidebar_key_list_mode": "major" if pm != "minor" else "minor",
        "entry_mode": entry,
    }


def generated_jam_practice_key_tokens(session: dict[str, Any]) -> set[str]:
    """Keys owned by generated Jam — never persist these into catalog Practice Key."""
    tokens: set[str] = set()
    for key in ("improv_jam_key", "improv_style_key"):
        tok = str(session.get(key) or "").strip()
        if tok:
            tokens.add(tok)
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    if isinstance(raw, dict):
        tok = str(raw.get("practice_key_token") or "").strip()
        if tok:
            tokens.add(tok)
    return tokens


def snapshot_song_practice_key_if_needed(session: dict[str, Any]) -> None:
    if isinstance(session.get(SONG_PRACTICE_KEY_SNAPSHOT_KEY), dict):
        return
    song_token = ""
    try:
        from music_workflow_song_practice import resolve_song_practice_key_token

        song_token = str(resolve_song_practice_key_token(session) or "").strip()
    except ImportError:
        pass
    if not song_token:
        try:
            from songs.practice_key_state import get_practice_concert_key

            pick = str(session.get("active_catalog_pick_key") or "").strip()
            if pick:
                song_token = str(get_practice_concert_key(session, pick) or "").strip()
        except ImportError:
            pass
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    token = song_token or live
    jam_tokens = generated_jam_practice_key_tokens(session)
    if token in jam_tokens:
        token = song_token if song_token and song_token not in jam_tokens else ""
        if not token:
            try:
                from songs.practice_key_state import get_practice_concert_key

                pick_live = str(session.get("active_catalog_pick_key") or "").strip()
                stored = str(get_practice_concert_key(session, pick_live) or "").strip() if pick_live else ""
                if stored and stored not in jam_tokens:
                    token = stored
            except ImportError:
                pass
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    session[SONG_PRACTICE_KEY_SNAPSHOT_KEY] = {
        "pick_key": pick,
        "display_key": token,
        "concert_key": token,
        "practice_concert_key": token,
    }
    if token:
        try:
            from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

            pick = str(session.get("active_catalog_pick_key") or "").strip()
            if pick and token not in jam_tokens:
                store = session.get(PRACTICE_KEY_BY_SOURCE_KEY)
                if not isinstance(store, dict):
                    store = {}
                if not str(store.get(pick) or "").strip():
                    store = dict(store)
                    store[pick] = token
                    session[PRACTICE_KEY_BY_SOURCE_KEY] = store
        except ImportError:
            pass


def activate_generated_jam_key_ownership(
    session: dict[str, Any],
    *,
    entry_mode: str = "",
    practice_key: str = "",
) -> None:
    """While generator/entry jam owns creative or backing route, practice key follows generated session."""
    entry = str(entry_mode or session.get("improv_entry_mode") or "").strip()
    if entry not in {"Style Jam Mode", "Jam Session Generator"}:
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is None or str(ctx.source or "") != "entry_jam":
                return
            entry = str(ctx.entry_mode or "").strip()
            if entry not in {"Style Jam Mode", "Jam Session Generator"}:
                return
        except ImportError:
            return

    snapshot_song_practice_key_if_needed(session)
    try:
        from music_source_ownership import trace_practice_key_owner

        trace_practice_key_owner(session, phase="jam_activate_before")
    except ImportError:
        pass
    pt, pm, blob_token = _practice_key_from_blob(session)
    token = blob_token
    if not token:
        try:
            from creative_key_sync import creative_entry_concert_key
            from music_theory import key_center_token, split_key_center

            raw = str(practice_key or creative_entry_concert_key(session) or "C").strip() or "C"
            pt, pm = split_key_center(raw)
            if entry in {"Style Jam Mode", "Jam Session Generator"} and pm != "minor":
                pm = "major"
            token = key_center_token(pt, pm)
        except ImportError:
            token = str(practice_key or "C").strip() or "C"
            pt, pm = token, "major"

    session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
        "generated_session_id": _jam_session_id(session),
        "practice_tonic": pt,
        "practice_mode": pm,
        "practice_key_token": token,
        "key_owner": "jam_session_generator" if "Generator" in entry else "entry_jam",
        "sidebar_key_list_mode": "major" if pm != "minor" else "minor",
        "entry_mode": entry,
    }
    session["_generated_jam_key_owner_active"] = True
    try:
        from creative_key_sync import apply_creative_concert_key

        apply_creative_concert_key(session, token, source="generated_jam_key_owner")
    except ImportError:
        if entry == "Jam Session Generator":
            session["improv_jam_key"] = token
        else:
            session["improv_style_key"] = token
    # Live concert follows the generated session while jam owns Creative/Backing.
    # Do not clobber ``display_key`` here — generation can keep a catalog leftover
    # until the jam sidebar/backing owner writes. Songs must still release jam tokens.
    session["concert_key"] = token


def deactivate_generated_jam_key_ownership(session: dict[str, Any], *, pre_widget: bool = False) -> bool:
    """Release generated-jam key ownership and restore song practice key snapshot.

    When sidebar widgets are already instantiated, widget-bound keys (``display_key``)
    are restored via ``_pending_display_key`` / ``concert_key`` — never direct assignment.

    Returns False only when ``pre_widget`` is false and widgets are locked (defer caller).
    """
    try:
        from session_widget_safe import reconcile_practice_key_fields, widgets_likely_instantiated

        locked = widgets_likely_instantiated(session)
    except ImportError:
        locked = bool(session.get("_streamlit_widgets_locked_this_run"))

    if locked and not pre_widget:
        return False

    snap = session.pop(SONG_PRACTICE_KEY_SNAPSHOT_KEY, None)
    session.pop(GENERATED_JAM_KEY_CONTEXT_KEY, None)
    session.pop("_generated_jam_key_owner_active", None)
    if not isinstance(snap, dict):
        return True

    authoritative = str(snap.get("display_key") or snap.get("concert_key") or "").strip()
    practice_concert = str(snap.get("practice_concert_key") or authoritative).strip()
    if authoritative:
        try:
            from session_widget_safe import reconcile_practice_key_fields

            reconcile_practice_key_fields(session, authoritative=authoritative)
        except ImportError:
            session["concert_key"] = authoritative
            if not locked:
                session["display_key"] = authoritative
            else:
                try:
                    from songs.key_state import PENDING_DISPLAY_KEY

                    session[PENDING_DISPLAY_KEY] = authoritative
                except ImportError:
                    session["_pending_display_key"] = authoritative
    if practice_concert:
        session["practice_concert_key"] = practice_concert
    pending = authoritative or practice_concert
    if pending and not locked:
        session["_pending_display_key"] = pending
    # Heal catalog Practice Key map from the snapshot — jam must not leave F#/empty.
    pick = str(snap.get("pick_key") or session.get("active_catalog_pick_key") or "").strip()
    heal = str(snap.get("practice_concert_key") or snap.get("display_key") or "").strip()
    if pick and heal:
        try:
            from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, is_song_source_pick

            if is_song_source_pick(pick):
                jam_tokens: set[str] = set()
                try:
                    jam_tokens = generated_jam_practice_key_tokens(session)
                except Exception:
                    jam_tokens = set()
                if heal not in jam_tokens:
                    try:
                        from music_theory import split_key_center
                        from songs.music_source import _catalog_original_key_for_session

                        original = str(_catalog_original_key_for_session(session) or "").strip()
                        _ot, orig_mode = split_key_center(original) if original else ("", "")
                        _ht, heal_mode = split_key_center(heal)
                        if orig_mode and heal_mode and orig_mode != heal_mode:
                            heal = ""
                    except Exception:
                        pass
                    if heal:
                        store = session.get(PRACTICE_KEY_BY_SOURCE_KEY)
                        if not isinstance(store, dict):
                            store = {}
                        store = dict(store)
                        store[pick] = heal
                        session[PRACTICE_KEY_BY_SOURCE_KEY] = store
        except ImportError:
            pass
    try:
        from music_source_ownership import trace_practice_key_owner

        trace_practice_key_owner(session, phase="jam_deactivate_after")
    except ImportError:
        pass
    return True


PENDING_CATALOG_FRESH_AFTER_SPECIALIZED = "_pending_catalog_fresh_activation_after_specialized"


def live_practice_key_is_generated_jam_token(session: dict[str, Any], token: str = "") -> bool:
    tok = str(token or session.get("display_key") or session.get("concert_key") or "").strip()
    if not tok:
        return False
    return tok in generated_jam_practice_key_tokens(session)


def release_generated_jam_key_for_catalog_surface(session: dict[str, Any]) -> bool:
    """Songs/Practice/explicit catalog pick: Style Jam must not own live Practice Key.

    Keeps ``improv_style_key`` / jam session for Return-to-Jam. Releases live
    display/pending/catalog-sticky jam tokens and specialized backing handoff.
    """
    tokens = generated_jam_practice_key_tokens(session)
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    jam_ctx = bool(session.get("_generated_jam_key_owner_active") or session.get(GENERATED_JAM_KEY_CONTEXT_KEY))
    handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
    specialized = handoff in {"mission", "song_improv", "entry_jam"}
    leaked = bool(tokens and live in tokens)
    if not jam_ctx and not leaked and not specialized:
        return False

    released_jam = bool(jam_ctx or leaked)
    released = False
    if jam_ctx or leaked:
        if deactivate_generated_jam_key_ownership(session, pre_widget=True):
            released = True
    if specialized:
        session.pop("_backing_explicit_handoff_source", None)
        session["_backing_released_specialized_context"] = True
        released = True

    tokens = generated_jam_practice_key_tokens(session)
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick.startswith("custom::") or pick.startswith("custom\x1f"):
        if released:
            session[PENDING_CATALOG_FRESH_AFTER_SPECIALIZED] = True
        return released

    saved = ""
    original = ""
    try:
        from songs.music_source import _catalog_original_key_for_session

        original = str(_catalog_original_key_for_session(session) or "").strip()
    except Exception:
        sel = session.get("selected_song")
        if isinstance(sel, dict):
            original = str(sel.get("key") or "").strip()
    try:
        from songs.practice_key_state import clear_practice_concert_key, get_practice_concert_key

        if pick:
            saved = str(get_practice_concert_key(session, pick, default="") or "").strip()
            if saved and saved in tokens:
                clear_practice_concert_key(session, pick)
                saved = ""
            if saved and original:
                try:
                    from music_theory import split_key_center

                    _ot, orig_mode = split_key_center(original)
                    _st, saved_mode = split_key_center(saved)
                    # Trial D snapshot must not become Shape sticky (D → Dm).
                    if orig_mode and saved_mode and orig_mode != saved_mode:
                        clear_practice_concert_key(session, pick)
                        saved = ""
                except Exception:
                    pass
    except ImportError:
        pass

    restore = ""
    if saved and saved not in tokens:
        restore = saved
    elif original and original not in tokens:
        restore = original
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    # Jam snapshot can restore a leftover Trial D onto Shape. Always re-apply
    # catalog original/sticky after releasing jam, even when live is not a jam token.
    if restore and (
        released_jam
        or not live
        or live in tokens
        or live != restore
    ):
        session["concert_key"] = restore
        session["display_key"] = restore
        try:
            from songs.key_state import PENDING_DISPLAY_KEY

            session[PENDING_DISPLAY_KEY] = restore
        except ImportError:
            session["_pending_display_key"] = restore
        try:
            from songs.practice_key_state import set_practice_concert_key

            if pick:
                set_practice_concert_key(
                    session,
                    restore,
                    pick_key=pick,
                    allow_restore_original=True,
                )
        except Exception:
            pass
        released = True
    if released:
        session[PENDING_CATALOG_FRESH_AFTER_SPECIALIZED] = True
        try:
            from songs.music_source import custom_progression_is_active

            custom_ga = custom_progression_is_active(session)
        except ImportError:
            custom_ga = str(pick).startswith("custom::")
        if not custom_ga:
            try:
                from source_session_state import bind_sbi_preview_to_active_after_explicit_catalog

                bind_sbi_preview_to_active_after_explicit_catalog(session)
            except ImportError:
                session["improv_song_source"] = "Active song"
                session["sbi_preview_source"] = "Active song"
    return released


def generated_jam_owns_practice_key(session: dict[str, Any]) -> bool:
    raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    if isinstance(raw, dict) and raw.get("key_owner"):
        page = str(session.get("studio_page") or "").strip().lower()
        if page in {"creative", "backing"}:
            try:
                from musical_context_authority import catalog_song_should_own_sidebar_practice_key

                if catalog_song_should_own_sidebar_practice_key(session):
                    return False
            except ImportError:
                pass
            entry = str(session.get("improv_entry_mode") or raw.get("entry_mode") or "").strip()
            if entry not in {"Style Jam Mode", "Jam Session Generator"}:
                return False
            try:
                from backing_workflow_context import workflow_is_generated

                if page == "backing" and not workflow_is_generated(session):
                    return False
            except ImportError:
                pass
            return True
    return False


__all__ = [
    "GENERATED_JAM_KEY_CONTEXT_KEY",
    "PENDING_CATALOG_FRESH_AFTER_SPECIALIZED",
    "SONG_PRACTICE_KEY_SNAPSHOT_KEY",
    "activate_generated_jam_key_ownership",
    "deactivate_generated_jam_key_ownership",
    "generated_jam_owns_practice_key",
    "generated_jam_practice_key_tokens",
    "live_practice_key_is_generated_jam_token",
    "refresh_generated_jam_key_context_from_blob",
    "release_generated_jam_key_for_catalog_surface",
    "snapshot_song_practice_key_if_needed",
]
