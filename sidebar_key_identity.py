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
                "Metrics & AI",
            }
        )


def resolve_sidebar_key_identity(session: dict[str, Any]) -> SidebarKeyIdentity:
    """Canonical tonic/mode for sidebar — not legacy display_key authority."""
    from music_theory import format_key_label_from_parts, key_center_token, split_key_center

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
        except ImportError:
            pass

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

    ident = resolve_sidebar_key_identity(session)
    token = ident.selector_token
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    # Catalog song surfaces: prefer per-source sticky over a stale SBI/mission blob.
    if page in {"", "picker", "practice", "songs"} or page not in {"creative", "backing", "custom"}:
        if str(ident.owner or "") in {"song_based_improvisation", "mission_jam"}:
            sticky = ""
            try:
                from songs.practice_key_state import (
                    get_practice_concert_key,
                    resolve_practice_source_pick,
                )

                pick = str(resolve_practice_source_pick(session) or "").strip()
                if pick:
                    sticky = str(get_practice_concert_key(session, pick) or "").strip()
            except ImportError:
                sticky = ""
            protect_catalog = sticky or live
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

    pending_tok = ""
    try:
        from music_workflow_pending_song_practice_key_edit import pending_selected_practice_key_token

        pending_tok = str(pending_selected_practice_key_token(session) or "").strip()
    except ImportError:
        pending_tok = str(session.get("_pending_display_key") or "").strip()
    protect = pending_tok or live
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
