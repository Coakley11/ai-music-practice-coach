"""Owner-aware sidebar practice/concert key identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SidebarKeyIdentity:
    owner: str
    concert_tonic: str
    concert_mode: str
    practice_tonic: str
    practice_mode: str
    written_tonic: str
    written_mode: str
    selector_token: str
    label: str


def _saved_custom_original_key(active: dict[str, Any]) -> str:
    """The musician's saved Custom Original Key — never inferred from chords."""
    try:
        from songs.music_source import custom_original_key

        return str(custom_original_key(active) or "").strip()
    except Exception:
        return str((active or {}).get("original_key_center") or "").strip()


def _live_key_is_foreign_to_custom_owner(session: dict[str, Any], live: str) -> bool:
    """True when ``live`` cannot be attributed to the active Custom song.

    It is foreign when this Custom pick has no saved Practice Key at all (so
    nothing the musician chose for this song can explain it) and the key does
    match the Practice Key of the Catalog/other source we just left.
    """
    tok = str(live or "").strip()
    if not tok:
        return False
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure
        from songs.music_source import custom_pick_key_for
        from songs.practice_key_state import get_practice_concert_key
    except ImportError:
        return False
    try:
        pick = str(
            custom_pick_key_for(ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})) or ""
        ).strip()
    except Exception:
        pick = ""
    if not pick.startswith("custom::"):
        return False
    try:
        saved = str(get_practice_concert_key(session, pick, default="") or "").strip()
    except Exception:
        saved = ""
    if saved:
        # The musician has a Practice Key for this Custom song; honour it.
        return False
    # No saved Custom Practice Key. Treat the live token as foreign when it is
    # the key of the source we came from rather than this Custom song's.
    for snap_key in ("_catalog_before_custom_state", "_last_catalog_song_state", "catalog_session"):
        snap = session.get(snap_key)
        if not isinstance(snap, dict):
            continue
        cand = str(
            snap.get("display_key")
            or (snap.get("selected_song") or {}).get("key")
            or ""
        ).strip()
        if cand and cand == tok:
            return True
    return False


def _owning_source_practice_token(session: dict[str, Any]) -> str:
    """The Practice Key of whichever source globally owns the app.

    One answer per owning source, independent of page or Creative tab: its own
    saved Practice Key, falling back to its Original Key when it has none.
    """
    try:
        from source_session_state import global_music_source_owner

        kind = global_music_source_owner(session)
    except ImportError:
        return ""
    try:
        from songs.practice_key_state import get_practice_concert_key
    except ImportError:
        return ""

    if kind == "composition":
        try:
            from composition_songs_bridge import resolve_composition_canonical_keys

            home, practice = resolve_composition_canonical_keys(session)
            return str(practice or home or "").strip()
        except Exception:
            return ""
    if kind == "custom":
        try:
            from creative_source_ownership_contract import resolve_custom_saved_original_key
            from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure
            from songs.music_source import custom_pick_key_for

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
            pick = str(custom_pick_key_for(active) or "").strip()
            home = str(resolve_custom_saved_original_key(session, active) or "").strip()
            if not pick:
                return home
            return str(get_practice_concert_key(session, pick, default=home) or home).strip()
        except Exception:
            return ""
    try:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if not pick or pick.startswith(("custom::", "composition::")):
            return ""
        sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        home = str(sel.get("key") or "").strip()
        return str(get_practice_concert_key(session, pick, default=home) or home).strip()
    except Exception:
        return ""


def _song_catalog_owner(session: dict[str, Any]) -> bool:
    try:
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key

        return catalog_song_should_own_sidebar_practice_key(session)
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        tab = str(session.get("improv_intelligence_tab") or "").strip()
        return bool(
            pick
            and tab
            in {
                "Song-Based Improvisation",
                "Missions",
                "Phrase / Motif",
                "Harmony Map",
                "Live Coach",
                "Song-Aware Coaching",
                "Metrics & AI",
                "Entry & Jam",
            }
        )


def _explicit_sidebar_owner(session: dict[str, Any]) -> str:
    """Page-owned sidebar identity — leftover Global Active / CPL must not win."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "composer":
        return "composition"
    if page == "custom":
        return "custom"
    try:
        from practice_focus_creative import (
            explicit_sbi_custom_owns_creative,
            leftover_custom_must_not_own_creative,
        )

        if leftover_custom_must_not_own_creative(session) and not explicit_sbi_custom_owns_creative(
            session
        ):
            return "catalog"
        if explicit_sbi_custom_owns_creative(session):
            return "custom"
    except ImportError:
        pass
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        if custom_sbi_owns_sidebar_practice_key(session):
            return "custom"
    except ImportError:
        pass
    try:
        from songs.music_source import SOURCE_COMPOSITION, explicit_music_source_choice, picker_composition_mode

        if picker_composition_mode(session) or explicit_music_source_choice(session) == SOURCE_COMPOSITION:
            if page in {"picker", "songs", "practice", "backing", "composer", ""}:
                return "composition"
    except ImportError:
        pass
    # A Custom progression that is the Global Active source owns the sidebar
    # Practice Key even off the Custom page and outside an SBI Custom overlay.
    # Without this, Trial Song (Original Key D) fell through to the generic
    # workflow branch, which reported owner "unknown" and carried the previous
    # Catalog song's key (Satin Doll's C) into the sidebar.
    try:
        from songs.music_source import (
            custom_progression_is_active,
            explicit_catalog_selection_is_authoritative,
            is_custom_progression,
        )

        if not explicit_catalog_selection_is_authoritative(session) and (
            custom_progression_is_active(session) or is_custom_progression(session)
        ):
            return "custom"
    except ImportError:
        pass
    return "catalog"


def resolve_sidebar_key_identity(session: dict[str, Any]) -> SidebarKeyIdentity:
    """Canonical tonic/mode for sidebar — not leftover display_key / CPL authority."""
    from music_theory import format_key_label_from_parts, key_center_token, split_key_center

    owner_kind = _explicit_sidebar_owner(session)

    try:
        from songs.music_source import (
            SOURCE_COMPOSITION,
            composition_song_is_active,
            explicit_music_source_choice,
            picker_composition_mode,
        )

        if owner_kind == "composition" and (
            composition_song_is_active(session)
            or picker_composition_mode(session)
            or explicit_music_source_choice(session) == SOURCE_COMPOSITION
            or owner_kind == "composition"
        ):
            home = "C"
            try:
                from composition_session_state import get_active_document
                from composition_songs_bridge import (
                    find_composition_document,
                    resolve_composition_canonical_keys,
                )

                doc = get_active_document(session)
                if not isinstance(doc, dict):
                    pick = str(session.get("active_catalog_pick_key") or "")
                    doc = find_composition_document(session, pick) if pick.startswith("composition::") else None
                if isinstance(doc, dict):
                    _home, saved = resolve_composition_canonical_keys(session, doc)
                    pt, pm = split_key_center(str(saved or _home or home))
                else:
                    pt, pm = split_key_center(home)
            except ImportError:
                pt, pm = split_key_center("C")
            token = key_center_token(pt, pm)
            label = format_key_label_from_parts(pt, pm)
            return SidebarKeyIdentity(
                owner="composition_song",
                concert_tonic=pt,
                concert_mode=pm,
                practice_tonic=pt,
                practice_mode=pm,
                written_tonic="",
                written_mode="",
                selector_token=token,
                label=label,
            )
    except ImportError:
        pass

    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if owner_kind == "custom":
            home = "C"
            pick = ""
            try:
                from creative_source_ownership_contract import resolve_last_custom_snapshot
                from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure, written_home_key
                from songs.music_source import custom_pick_key_for
                from songs.practice_key_state import get_practice_concert_key

                active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
                generic = {"", "My Progression", "My progression", "Custom", "Custom Progression"}
                snap = resolve_last_custom_snapshot(session)
                if str(active.get("name") or "").strip() in generic and snap is not None:
                    remembered = getattr(snap, "active", None)
                    if isinstance(remembered, dict) and remembered:
                        active = ensure_original_structure(remembered)
                    elif getattr(snap, "title", ""):
                        home = str(getattr(snap, "original_key", "") or home).strip() or home
                # Saved Original Key is authoritative for the Custom home. The
                # inferred tonal centre (written_home_key) can report a chord
                # analysis result for a Trial Song whose saved Original Key is D,
                # which is the key the sidebar must show absent a saved override.
                home = str(
                    _saved_custom_original_key(active)
                    or written_home_key(active)
                    or active.get("original_key_center")
                    or home
                ).strip() or "C"
                pick = custom_pick_key_for(active) or str(getattr(snap, "pick_key", "") or "")
                saved = get_practice_concert_key(session, pick, default=home) if pick else home
                pt, pm = split_key_center(str(saved or home))
            except ImportError:
                live = str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
                pt, pm = split_key_center(live)
            token = key_center_token(pt, pm)
            label = format_key_label_from_parts(pt, pm)
            return SidebarKeyIdentity(
                owner="custom_progression",
                concert_tonic=pt,
                concert_mode=pm,
                practice_tonic=pt,
                practice_mode=pm,
                written_tonic="",
                written_mode="",
                selector_token=token,
                label=label,
            )
    except ImportError:
        pass

    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident = resolve_practice_key_identity_for_ui(session)
        if ident is not None:
            return SidebarKeyIdentity(
                owner=ident.workflow_owner or "unknown",
                concert_tonic=ident.practice_tonic,
                concert_mode=ident.practice_mode,
                practice_tonic=ident.practice_tonic,
                practice_mode=ident.practice_mode,
                written_tonic="",
                written_mode="",
                selector_token=ident.practice_key_token,
                label=ident.practice_label,
            )
    except ImportError:
        pass

    owner = ""
    pt, pm = "C", "major"
    wt = ""
    song_catalog = _song_catalog_owner(session)
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr:
            owner = str(ptr.workflow_owner or "")
    except ImportError:
        pass

    if song_catalog or owner in {
        "song_based_improvisation",
        "mission_jam",
        "regular_catalog_backing",
        "regular_custom_backing",
    }:
        try:
            from musical_context_authority import resolve_authoritative_practice_key

            pk = resolve_authoritative_practice_key(session)
            if not owner or owner in {"style_jam", "jam_session_generator", "unknown"}:
                owner = "song_based_improvisation"
            pt = str(pk.practice_tonic or "C").strip() or "C"
            pm = str(pk.practice_mode or "major").strip().lower() or "major"
        except ImportError:
            live = str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
            pt, pm = split_key_center(live)
    else:
        resolved_from_blob = False
        try:
            from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

            ptr = get_active_workflow_pointer(session)
            if ptr:
                owner = str(ptr.workflow_owner or "")
                blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
                if blob is not None:
                    pt = str(blob.keys.practice_tonic or "C").strip() or "C"
                    pm = str(blob.keys.practice_mode or "major").strip().lower() or "major"
                    wt = str(blob.keys.written_tonic or "").strip()
                    resolved_from_blob = True
        except ImportError:
            pass
        if not resolved_from_blob:
            # Nothing answered, so pt/pm would stay at the hardcoded C default.
            # catalog_song_should_own_sidebar_practice_key is False on some
            # surfaces -- Deep Harmony, Entry & Jam, and an unset tab -- so the
            # sidebar reported C while the owning source's Practice Key was A
            # (Perfect) or Eb (My Composition) and the chord map was already
            # projected there. The owning source answers instead of a default.
            owned = _owning_source_practice_token(session)
            if owned:
                pt, pm = split_key_center(owned)
                if not owner:
                    owner = "source_owned_practice_key"

    token = key_center_token(pt, pm)
    label = format_key_label_from_parts(pt, pm)
    return SidebarKeyIdentity(
        owner=owner or "unknown",
        concert_tonic=pt,
        concert_mode=pm,
        practice_tonic=pt,
        practice_mode=pm,
        written_tonic=wt,
        written_mode="",
        selector_token=token,
        label=label,
    )


def prime_sidebar_practice_key_from_identity(session: dict[str, Any], st: Any | None = None) -> SidebarKeyIdentity:
    """Set display_key / concert_key pending values from canonical identity before sidebar widgets.

    Never overwrite a live or queued user Practice Key with a stale song-blob token
    (Mission Backing Dm→Em regression: prime wrote blob Dm after the sidebar chose Em).

    Custom page owns priming via ``prepare_custom_workspace_sidebar_display_key`` —
    skip force-apply here so React Aria Practice Key clicks can commit.

    Songs / Practice / picker: never force-apply a leftover Song-Based Improvisation
    blob key (Dm) over the catalog sticky / live Practice Key (Bm restore).
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "custom":
        return resolve_sidebar_key_identity(session)
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        if session.get("_sbi_custom_sidebar_overlay") or custom_sbi_owns_sidebar_practice_key(
            session
        ):
            return resolve_sidebar_key_identity(session)
    except ImportError:
        if session.get("_sbi_custom_sidebar_overlay"):
            return resolve_sidebar_key_identity(session)

    ident = resolve_sidebar_key_identity(session)
    token = ident.selector_token
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    try:
        from h3_live_key_trace import emit

        emit(
            session,
            "prime_sidebar",
            ident_owner=ident.owner,
            ident_token=token,
            live_before=live,
        )
    except Exception:
        pass
    pending_tok = ""
    try:
        from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

        pending_tok = str(pending_selected_practice_key_token(session) or "").strip()
    except ImportError:
        pending_tok = str(session.get("_pending_display_key") or "").strip()
    # Composition canonical Practice Key outranks leftover live Original G.
    # Protecting live G here remounts the Backing widget over saved Db.
    if str(ident.owner or "") == "composition_song" and token:
        # Composer page shows an inactive Composition's identity, but only a
        # genuine activation may write its key into the global Practice Key
        # (Trial Song D must not become C# while it is still Global Active).
        try:
            from songs.music_source import composition_song_is_active

            if not composition_song_is_active(session):
                session["_sidebar_key_identity_label"] = ident.label
                return ident
        except ImportError:
            pass
        pending_comp = pending_tok
        pending_source = str(session.get("_pending_display_key_source") or "").strip()
        if (
            pending_comp
            and pending_comp != token
            and pending_source == "composition"
        ):
            session["concert_key"] = pending_comp
            session["_sidebar_key_identity_label"] = ident.label
            return ident
        try:
            from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget

            if st is not None:
                _apply_display_key_before_widget(
                    st, token, source="sidebar_key_identity:composition_song"
                )
            else:
                session[PENDING_DISPLAY_KEY] = token
            session["concert_key"] = token
            session["_sidebar_key_identity_label"] = ident.label
        except ImportError:
            session["concert_key"] = token
            session["display_key"] = token
        return ident
    # Catalog song surfaces: prefer per-source sticky over a stale SBI/mission blob.
    catalog_surface = page in {"", "picker", "practice", "songs"} or page not in {
        "creative",
        "backing",
        "custom",
    }
    if page == "backing":
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None and str(getattr(ctx, "source", "") or "") == "regular_song":
                catalog_surface = True
        except Exception:
            pass
        if str(ident.owner or "") == "composition_song":
            catalog_surface = False
    if catalog_surface:
        if str(ident.owner or "") in {
            "song_based_improvisation",
            "mission_jam",
            "jam_session_generator",
        } or page == "backing":
            sticky = ""
            try:
                from songs.practice_key_state import (
                    get_practice_concert_key,
                    resolve_practice_source_pick,
                )

                pick = str(
                    session.get("_specialized_leave_catalog_pick")
                    or resolve_practice_source_pick(session)
                    or ""
                ).strip()
                if pick:
                    sticky = str(get_practice_concert_key(session, pick) or "").strip()
            except ImportError:
                sticky = ""
            leaving = str(session.get("_specialized_practice_token_leaving") or "").strip()
            sealed = str(session.get("_specialized_leave_catalog_pk") or "").strip()
            if leaving and sticky == leaving:
                sticky = ""
            protect_catalog = sealed or sticky or live
            if leaving and protect_catalog == leaving:
                protect_catalog = sealed or sticky or ""
            if protect_catalog:
                session["concert_key"] = protect_catalog
                if live != protect_catalog:
                    try:
                        from songs.key_state import _apply_display_key_before_widget

                        if st is not None:
                            _apply_display_key_before_widget(
                                st,
                                protect_catalog,
                                source="sidebar_key_identity:catalog_sticky",
                            )
                    except ImportError:
                        session["display_key"] = protect_catalog
                session["_sidebar_key_identity_label"] = ident.label
                return ident

    protect = pending_tok or live
    # A live key is only worth protecting when it belongs to the owner that is
    # now authoritative. After Catalog -> Custom the live key is still the
    # Catalog song's (Satin Doll's C) while the Custom identity token is Trial
    # Song's D, and protecting it wrote C into the sidebar. A queued user edit
    # (pending_tok) and a genuinely saved Practice Key both still win: a saved
    # override is already reflected in the identity token itself.
    if (
        protect
        and token
        and protect != token
        and not pending_tok
        and str(ident.owner or "") == "custom_progression"
        and _live_key_is_foreign_to_custom_owner(session, protect)
    ):
        protect = token
    if protect and token and protect != token:
        try:
            from music_source_ownership import trace_practice_key_owner

            trace_practice_key_owner(
                session,
                phase="prime_sidebar_skip_stale_blob",
                extra={
                    "blob_token": token,
                    "protect": protect,
                    "pending": pending_tok,
                    "live": live,
                    "reason": "user_or_pending_practice_key_outranks_identity",
                },
            )
        except ImportError:
            pass
        session["concert_key"] = protect
        session["_sidebar_key_identity_label"] = ident.label
        return ident
    try:
        from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget, display_key_options

        options = display_key_options(token)
        if token not in options:
            options = [token] + list(options)
        if st is not None:
            _apply_display_key_before_widget(st, token, source=f"sidebar_key_identity:{ident.owner}")
        else:
            session[PENDING_DISPLAY_KEY] = token
        session["concert_key"] = token
        session["_sidebar_key_identity_label"] = ident.label
    except ImportError:
        session["concert_key"] = token
        session["display_key"] = token
    return ident


__all__ = ["SidebarKeyIdentity", "prime_sidebar_practice_key_from_identity", "resolve_sidebar_key_identity"]
