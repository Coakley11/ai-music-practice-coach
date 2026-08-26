"""Explicit source state buckets — catalog, custom, creative preview, practice keys.

SBI preview reads/writes ``sbi_preview_source`` and session buckets only.
Global catalog/custom ownership changes happen on explicit Practice/Backing handoff.
"""

from __future__ import annotations

from typing import Any

SBI_PREVIEW_SOURCE_KEY = "sbi_preview_source"
CATALOG_SESSION_KEY = "catalog_session"
CUSTOM_SESSION_KEY = "custom_session"

IMPROV_SONG_SOURCES = ("Active song", "Custom progression")


def get_sbi_preview_source(session: dict[str, Any]) -> str:
    """Read SBI preview source (never reads handoff-only keys).

    Do **not** infer Custom from ``cpl_session_is_active``: a live CPL draft /
    LAST_CUSTOM memory can exist while Global Active stays Catalog and the user
    is on Creative → SBI → Active. That inference collapsed nested SBI Custom
    into “we’re on Custom” semantics and helped reboot land on top-level Custom.
    """
    val = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    val = str(session.get("improv_song_source") or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    return "Active song"


def set_sbi_preview_source(session: dict[str, Any], source: str) -> None:
    src = str(source or "Active song").strip() or "Active song"
    if src not in IMPROV_SONG_SOURCES:
        src = "Active song"
    session[SBI_PREVIEW_SOURCE_KEY] = src
    # Nested SBI source tab must survive refresh/reboot with Creative page.
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass


def sync_catalog_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture live catalog identity into the catalog_session bucket."""
    try:
        from songs.music_source import _catalog_snapshot_from_session, _catalog_title_matches_live

        snap = _catalog_snapshot_from_session(session)
    except ImportError:
        snap = None
        _catalog_title_matches_live = None  # type: ignore[assignment]
    live_title = str(session.get("song") or session.get("active_song_title") or "").strip()
    if not snap:
        for fallback_key in ("_catalog_before_custom_state", "_last_catalog_song_state"):
            raw = session.get(fallback_key)
            if not isinstance(raw, dict):
                continue
            pk = str(raw.get("pick_key") or "").strip()
            if not pk or pk.startswith("custom::"):
                continue
            # Never rehydrate Say into catalog_session when Global Active title is Shape.
            if live_title and not live_title.lower().startswith("my progression"):
                fb_title = str((raw.get("selected_song") or {}).get("title") or "").strip()
                if not fb_title:
                    label = pk.split("\x1f", 1)[-1] if "\x1f" in pk else pk
                    fb_title = label.split(" — ", 1)[0].strip()
                if fb_title and _catalog_title_matches_live is not None:
                    if not _catalog_title_matches_live(fb_title, live_title):
                        continue
            snap = dict(raw)
            break
    if not snap:
        return None
    pick = str(snap.get("pick_key") or "").strip()
    if not pick or pick.startswith("custom::"):
        return None
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = get_practice_concert_key(session, pick)
        if saved:
            snap["display_key"] = saved
    except ImportError:
        pass
    session[CATALOG_SESSION_KEY] = dict(snap)
    return session[CATALOG_SESSION_KEY]


def get_catalog_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Read catalog_session bucket, syncing from live state when missing."""
    raw = session.get(CATALOG_SESSION_KEY)
    if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
        pick = str(raw.get("pick_key") or "").strip()
        if not pick.startswith("custom::"):
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
            if live_pick and not live_pick.startswith("custom::") and live_pick != pick:
                return sync_catalog_session(session)
            try:
                from songs.practice_key_state import get_practice_concert_key

                saved = get_practice_concert_key(session, pick)
                if saved and str(raw.get("display_key") or "").strip() != saved:
                    raw = dict(raw)
                    raw["display_key"] = saved
                    session[CATALOG_SESSION_KEY] = raw
            except ImportError:
                pass
            return raw
    return sync_catalog_session(session)


def sync_custom_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Capture live custom progression into the custom_session bucket."""
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
            written_home_key,
        )
        from songs.music_source import (
            cpl_active_is_substantive,
            custom_pick_key_for,
            install_last_custom_into_live_cpl,
        )
    except ImportError:
        return None

    # Prefer LAST_CUSTOM over empty My Progression shell before syncing the bucket.
    try:
        install_last_custom_into_live_cpl(session, reset_practice_key_to_original=False)
    except Exception:
        pass

    live = session.get(CPL_ACTIVE_KEY)
    if not cpl_active_is_substantive(live):
        active = ensure_original_structure(live or default_active_progression())
    else:
        active = ensure_original_structure(live)
    pick = custom_pick_key_for(active)
    home = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
    try:
        from songs.practice_key_state import get_practice_concert_key

        display_key = get_practice_concert_key(session, pick, default="") or ""
        if not display_key:
            display_key = home
        else:
            # Drop Shape Dm bleed onto Trial D-major sticky.
            try:
                from music_theory import split_key_center

                _ht, hm = split_key_center(home)
                _dt, dm = split_key_center(display_key)
                if _ht and _ht == _dt and hm != dm:
                    display_key = home
            except Exception:
                pass
    except ImportError:
        display_key = home
    sections_raw = active.get("original_sections")
    if not isinstance(sections_raw, dict) or not sections_raw:
        sections_raw = active.get("sections") if isinstance(active.get("sections"), dict) else {}
    # CPL stores [{chord, bars}, ...] — expand to plain symbols for SBI/Creative display.
    try:
        from custom_progression_lab import sections_to_chord_lists

        sections = sections_to_chord_lists(sections_raw)
    except Exception:
        sections = {}
        for sec, chords in (sections_raw or {}).items():
            if not isinstance(chords, list):
                continue
            out: list[str] = []
            for c in chords:
                if isinstance(c, dict):
                    sym = str(c.get("chord") or "").strip()
                    bars = max(1, int(c.get("bars") or 1) or 1)
                    if sym:
                        out.extend([sym] * bars)
                else:
                    sym = str(c or "").strip()
                    if sym and not sym.startswith("{"):
                        out.append(sym)
            sections[str(sec)] = out
    blob = {
        "pick_key": pick,
        "title": str(active.get("name") or "Custom progression").strip(),
        "artist": "Custom progression",
        "original_key": home,
        "display_key": display_key,
        "sections": sections,
        "progression_id": str(active.get("id") or "").strip(),
    }
    session[CUSTOM_SESSION_KEY] = blob
    return blob


def get_custom_session(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(CUSTOM_SESSION_KEY)
    if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip().startswith("custom::"):
        return raw
    return sync_custom_session(session)


def _catalog_display_key(session: dict[str, Any], catalog: dict[str, Any]) -> str:
    pick = str(catalog.get("pick_key") or "").strip()
    sel = catalog.get("selected_song")
    original = "C"
    if isinstance(sel, dict):
        original = str(sel.get("key") or catalog.get("original_key") or "C").strip() or "C"
    else:
        original = str(catalog.get("original_key") or "C").strip() or "C"
    # Prefer live Practice/Concert Key for the active catalog pick — never catalog.original.
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
    pick_active = bool(pick) and (not ctx_pick or ctx_pick == pick)
    if pick_active and live:
        return live
    if pick:
        # SBI "Active song" preview can resolve a catalog bucket while global ownership
        # is Custom. Do not let the custom live key overlay that catalog snapshot.
        if pick_active or not ctx_pick.startswith("custom::"):
            try:
                from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key

                dest = overlay_destination_practice_key(session)
                if dest:
                    return dest
            except ImportError:
                pass
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = get_practice_concert_key(session, pick)
            if saved:
                return saved
        except ImportError:
            pass
    if pick_active and live:
        return live
    dk = str(catalog.get("display_key") or "").strip()
    return dk or original


def _sections_overlay_pending_practice_key(
    session: dict[str, Any],
    sections: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Retranspose catalog sections toward the effective Practice Key on the same rerun."""
    if not isinstance(sections, dict) or not sections:
        return sections
    try:
        from music_workflow_pending_song_practice_key_edit import (
            overlay_sections_with_pending_practice_key,
        )
        from music_workflow_song_practice import resolve_song_practice_key_token

        spelled = resolve_song_practice_key_token(session) or str(
            session.get("concert_key") or ""
        )
        return overlay_sections_with_pending_practice_key(
            session,
            sections,
            spelled_in_key=spelled,
        )
    except ImportError:
        return sections


def _catalog_sections(session: dict[str, Any], catalog: dict[str, Any]) -> dict[str, list[str]]:
    pick = str(catalog.get("pick_key") or "").strip()
    ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
    live_is_catalog = bool(ctx_pick) and not ctx_pick.startswith("custom::")
    if live_is_catalog and pick and ctx_pick != pick:
        return {}
    if live_is_catalog and (not pick or pick == ctx_pick):
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            synced = sync_song_improv_sections_to_practice_key(session)
            if isinstance(synced, dict) and synced:
                cleaned = {
                    str(name): [str(c) for c in chords if str(c).strip()]
                    for name, chords in synced.items()
                    if isinstance(chords, list)
                }
                return _sections_overlay_pending_practice_key(session, cleaned)
        except ImportError:
            pass
    stored = session.get("improv_song_concert_sections")
    if live_is_catalog and isinstance(stored, dict) and stored:
        if not pick or pick == ctx_pick:
            cleaned = {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in stored.items()
                if isinstance(chords, list)
            }
            return _sections_overlay_pending_practice_key(session, cleaned)
    bucket = catalog.get("sections")
    if isinstance(bucket, dict) and bucket:
        cleaned = {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in bucket.items()
            if isinstance(chords, list)
        }
        return _sections_overlay_pending_practice_key(session, cleaned)
    return {}


def resolve_sbi_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Authoritative SBI card — title/key/progression from one source only."""
    source = get_sbi_preview_source(session)
    if source == "Custom progression":
        custom = get_custom_session(session)
        if custom:
            return {
                "source": source,
                "title": str(custom.get("title") or "Custom progression"),
                "artist": str(custom.get("artist") or "Custom progression"),
                "display_key": str(custom.get("display_key") or custom.get("original_key") or "C"),
                "original_key": str(custom.get("original_key") or "C"),
                "sections": dict(custom.get("sections") or {}),
                "pick_key": str(custom.get("pick_key") or ""),
            }
        return {
            "source": source,
            "title": "Custom progression",
            "artist": "Custom progression",
            "display_key": "C",
            "original_key": "C",
            "sections": {},
            "pick_key": "",
        }

    catalog = get_catalog_session(session)
    if not catalog:
        try:
            from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY

            for key in (CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY):
                raw = session.get(key)
                if isinstance(raw, dict) and str(raw.get("pick_key") or "").strip():
                    if not str(raw.get("pick_key") or "").strip().startswith("custom::"):
                        catalog = raw
                        break
        except ImportError:
            pass

    if catalog:
        sel = catalog.get("selected_song")
        if isinstance(sel, dict):
            title = str(sel.get("title") or "Active song").strip()
            artist = str(sel.get("artist") or "").strip()
            original = str(sel.get("key") or catalog.get("original_key") or "C").strip() or "C"
        else:
            title = "Active song"
            artist = ""
            original = str(catalog.get("original_key") or "C").strip() or "C"
        return {
            "source": source,
            "title": title,
            "artist": artist,
            "display_key": _catalog_display_key(session, catalog),
            "original_key": original,
            "sections": _catalog_sections(session, catalog),
            "pick_key": str(catalog.get("pick_key") or ""),
        }

    return {
        "source": source,
        "title": "Active song",
        "artist": "",
        "display_key": "C",
        "original_key": "C",
        "sections": {},
        "pick_key": "",
    }


def resolve_improv_song_source_for_handoff(session: dict[str, Any]) -> str:
    """Song source for Practice/Backing open — preview bucket first, then widget."""
    return get_sbi_preview_source(session)


def custom_sbi_owns_sidebar_practice_key(session: dict[str, Any]) -> bool:
    """True when Creative/Backing sidebar Practice Key must use Custom sticky/home.

    Covers SBI → Custom progression preview and Custom-bound song_improv /
    custom_progression Backing — never Global Active catalog (Shape Dm).
    On Backing, only the active backing context may claim Custom — leftover
  SBI preview flags must not steal Mission Backing PK after reboot.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page not in {"creative", "backing"}:
        return False
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
    except Exception:
        ctx = None
    src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    bound = str(
        getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
    ).strip() if ctx is not None else ""
    if page == "backing":
        if src == "custom_progression":
            return True
        if src == "song_improv" and bound.startswith("custom::"):
            return True
        return False
    # Creative: SBI tab on Custom progression preview.
    if get_sbi_preview_source(session) == "Custom progression":
        return True
    if src == "custom_progression":
        return True
    if src == "song_improv" and bound.startswith("custom::"):
        return True
    return False


def prepare_sbi_custom_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Creative SBI → Custom progression: sidebar PK uses Trial/Custom sticky + home mode.

    Seals the current catalog live Practice Key into the catalog sticky first so
    Shape Dm survives, then projects Custom sticky/home into ``display_key`` for
    the sidebar widget without writing the Custom token onto the catalog pick.
    """
    from songs.key_state import PENDING_DISPLAY_KEY, display_key_options

    # Seal catalog sticky once on enter. Never overwrite an existing catalog sticky
    # with Custom live (Eb → Shape D#m bleed when the overlay flag flickers).
    # Remember the sealed catalog token so leave can restore it even if live Custom
    # PK (E) briefly poisoned the catalog sticky via Streamlit widget remount.
    try:
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_source_pick,
            resolve_settings_pick_for_write,
            set_practice_concert_key,
        )

        catalog_pick = str(resolve_practice_source_pick(session) or "").strip()
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if not session.get("_sbi_custom_sidebar_overlay"):
            if catalog_pick and not catalog_pick.startswith("custom::"):
                existing = str(get_practice_concert_key(session, catalog_pick) or "").strip()
                if not existing and live:
                    set_practice_concert_key(
                        session,
                        live,
                        pick_key=catalog_pick,
                        allow_catalog_during_sbi_custom=True,
                    )
                    existing = live
                if existing:
                    session["_sbi_custom_sealed_catalog_pk"] = existing
                    session["_sbi_custom_sealed_catalog_pick"] = catalog_pick
            session["_sbi_custom_sidebar_overlay"] = True
    except ImportError:
        catalog_pick = ""

    custom = sync_custom_session(session) or get_custom_session(session) or {}
    # Always prefer Original Key as the Custom home (never contaminated display_key).
    home = str(custom.get("original_key") or "C").strip() or "C"
    pick = str(custom.get("pick_key") or "").strip()
    sticky = ""
    catalog_sticky = ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        if catalog_pick and not catalog_pick.startswith("custom::"):
            catalog_sticky = str(get_practice_concert_key(session, catalog_pick) or "").strip()
        if pick.startswith("custom::"):
            sticky = str(get_practice_concert_key(session, pick, default="") or "").strip()
        if not sticky:
            from songs.practice_key_state import resolve_settings_pick_for_write

            write_pick = str(resolve_settings_pick_for_write(session) or "").strip()
            if write_pick.startswith("custom::"):
                pick = write_pick
                sticky = str(get_practice_concert_key(session, write_pick, default="") or "").strip()
    except ImportError:
        sticky = ""
    selected = sticky or home
    # Reject Shape/catalog sticky bleed onto Custom (Dm on Trial D major).
    # Same tonic with different mode, or exact equality with catalog sticky while
    # home differs, means contamination — fall back to Custom Original Key.
    try:
        from music_theory import split_key_center

        _h_tonic, home_mode = split_key_center(home)
        _s_tonic, sticky_mode = split_key_center(sticky) if sticky else ("", "")
        contaminated = False
        if sticky and catalog_sticky and sticky == catalog_sticky and sticky != home:
            contaminated = True
        elif sticky and home and sticky != home and _h_tonic and _h_tonic == _s_tonic and home_mode != sticky_mode:
            contaminated = True
        if contaminated:
            selected = home
            if pick.startswith("custom::"):
                try:
                    from songs.practice_key_state import set_practice_concert_key

                    set_practice_concert_key(session, home, pick_key=pick)
                except Exception:
                    pass
    except Exception:
        if sticky and catalog_sticky and sticky == catalog_sticky and sticky != home:
            selected = home
    options = list(display_key_options(home) or [home])
    if selected not in options:
        options = [selected] + [k for k in options if k != selected]
    session.pop(PENDING_DISPLAY_KEY, None)
    session["display_key"] = selected
    session["concert_key"] = selected
    session[PENDING_DISPLAY_KEY] = selected
    try:
        from songs.key_state import _apply_display_key_before_widget

        _apply_display_key_before_widget(st, selected, source="sbi_custom_sidebar_overlay")
    except Exception:
        pass
    return options


def heal_sealed_catalog_sidebar_if_needed(st: Any, session: dict[str, Any]) -> str:
    """After Custom SBI leave, keep sealed catalog PK in the sidebar widget.

    Streamlit may remount the Practice Key widget with leftover Custom live (E);
    refuse that as the catalog display while the isolation seal is active.
    """
    sealed = str(session.get("_sbi_custom_sealed_catalog_pk") or "").strip()
    sealed_pick = str(session.get("_sbi_custom_sealed_catalog_pick") or "").strip()
    page = str(session.get("studio_page") or "").strip().lower()
    # Only heal on non-Custom surfaces (Songs / Practice / picker). Do not use
    # custom_sbi_owns_sidebar_practice_key here — SBI preview can remain
    # "Custom progression" after leave, which would skip the heal forever.
    if not sealed or not sealed_pick or page in {"creative", "backing", "custom"}:
        return ""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    custom_tokens: set[str] = set()
    store = session.get("practice_key_by_source")
    if isinstance(store, dict):
        for pk, val in store.items():
            if str(pk).startswith("custom::"):
                v = str(val or "").strip()
                if v:
                    custom_tokens.add(v)
    leftover = str(session.get("cpl_last_display_key") or "").strip()
    if leftover:
        custom_tokens.add(leftover)
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for
        from songs.practice_key_state import get_practice_concert_key

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        custom_pick = ""
        if isinstance(snap, dict):
            custom_pick = str(snap.get("pick_key") or "").strip()
            active = snap.get("active")
            if isinstance(active, dict):
                custom_pick = str(custom_pick_for(active) or custom_pick or "").strip()
        if custom_pick.startswith("custom::"):
            tok = str(get_practice_concert_key(session, custom_pick) or "").strip()
            if tok:
                custom_tokens.add(tok)
    except Exception:
        pass
    # Force sealed whenever live still equals a Custom sticky token (bleed).
    if live == sealed or (live and live in custom_tokens):
        try:
            from songs.practice_key_state import set_practice_concert_key

            set_practice_concert_key(
                session,
                sealed,
                pick_key=sealed_pick,
                allow_catalog_during_sbi_custom=True,
            )
        except Exception:
            pass
        session["display_key"] = sealed
        session["concert_key"] = sealed
        try:
            from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget

            session[PENDING_DISPLAY_KEY] = sealed
            _apply_display_key_before_widget(st, sealed, source="heal_sealed_catalog_sidebar")
        except Exception:
            pass
        session["display_key"] = sealed
        session["concert_key"] = sealed
        return sealed
    return ""


def clear_sbi_custom_sidebar_overlay_if_needed(session: dict[str, Any]) -> None:
    """Restore catalog sticky into live PK when leaving SBI Custom preview."""
    if not session.get("_sbi_custom_sidebar_overlay") and not session.get(
        "_custom_page_sidebar_overlay"
    ):
        return
    page = str(session.get("studio_page") or "").strip().lower()
    if session.get("_sbi_custom_sidebar_overlay"):
        # Keep overlay on Creative *and* Custom SBI Backing — clearing on open
        # restored Shape Dm into the sidebar while progression stayed at Trial D.
        if page in {"creative", "backing"} and custom_sbi_owns_sidebar_practice_key(session):
            return
        session.pop("_sbi_custom_sidebar_overlay", None)
    if session.get("_custom_page_sidebar_overlay"):
        if page == "custom":
            return
        if page == "backing" and custom_sbi_owns_sidebar_practice_key(session):
            return
        session.pop("_custom_page_sidebar_overlay", None)
    sealed = str(session.get("_sbi_custom_sealed_catalog_pk") or "").strip()
    sealed_pick = str(session.get("_sbi_custom_sealed_catalog_pick") or "").strip()
    try:
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_source_pick,
            set_practice_concert_key,
        )

        pick = sealed_pick or str(resolve_practice_source_pick(session) or "").strip()
        sticky = sealed
        if not sticky and pick and not pick.startswith("custom::"):
            sticky = str(get_practice_concert_key(session, pick) or "").strip()
        if pick and not pick.startswith("custom::") and sticky:
            # Heal catalog sticky if Custom live (E) poisoned it during leave.
            # Keep the seal so a later Streamlit remount write of Custom E is refused.
            set_practice_concert_key(
                session,
                sticky,
                pick_key=pick,
                allow_catalog_during_sbi_custom=True,
            )
            session["display_key"] = sticky
            session["concert_key"] = sticky
            try:
                from songs.key_state import PENDING_DISPLAY_KEY

                session[PENDING_DISPLAY_KEY] = sticky
            except ImportError:
                session["_pending_display_key"] = sticky
    except ImportError:
        pass


__all__ = [
    "CATALOG_SESSION_KEY",
    "CUSTOM_SESSION_KEY",
    "IMPROV_SONG_SOURCES",
    "SBI_PREVIEW_SOURCE_KEY",
    "clear_sbi_custom_sidebar_overlay_if_needed",
    "custom_sbi_owns_sidebar_practice_key",
    "get_catalog_session",
    "get_custom_session",
    "get_sbi_preview_source",
    "heal_sealed_catalog_sidebar_if_needed",
    "prepare_sbi_custom_sidebar_display_key",
    "resolve_improv_song_source_for_handoff",
    "resolve_sbi_preview",
    "set_sbi_preview_source",
    "sync_catalog_session",
    "sync_custom_session",
]
