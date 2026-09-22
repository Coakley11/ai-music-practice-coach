"""Explicit source state buckets — catalog, custom, creative preview, practice keys.

SBI preview reads/writes ``sbi_preview_source`` and session buckets only.
Global catalog/custom ownership changes happen on explicit Practice/Backing handoff.
"""

from __future__ import annotations

from typing import Any

SBI_PREVIEW_SOURCE_KEY = "sbi_preview_source"
CATALOG_SESSION_KEY = "catalog_session"
CUSTOM_SESSION_KEY = "custom_session"

SBI_SONG_SOURCE_ACTIVE = "Active song"
SBI_SONG_SOURCE_CUSTOM = "Custom progression"
SBI_SONG_SOURCE_COMPOSITION = "Composition"

IMPROV_SONG_SOURCES = (
    SBI_SONG_SOURCE_ACTIVE,
    SBI_SONG_SOURCE_CUSTOM,
    SBI_SONG_SOURCE_COMPOSITION,
)

SBI_MATERIAL_CATALOG = "catalog"
SBI_MATERIAL_CUSTOM = "custom"
SBI_MATERIAL_COMPOSITION = "composition"

SBI_MATERIAL_TYPE_LABELS = {
    SBI_MATERIAL_CATALOG: "Catalog song",
    SBI_MATERIAL_CUSTOM: "Custom progression",
    SBI_MATERIAL_COMPOSITION: "Composition",
}

SBI_WORKFLOW_LABEL = "Song-Based Improvisation"
# Explicit Songs catalog pick outranks a leftover nested SBI Custom radio.
SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY = "_sbi_follow_active_after_explicit_catalog"
# Set after Creative SBI radio has rendered under the follow-Active bind.
# Distinguishes leftover persisted Custom from a later explicit Custom click.
SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY = "_sbi_follow_active_widget_seen"
# Set only by the Song-source radio on_change this Streamlit run.
SBI_RADIO_ON_CHANGE_THIS_RUN_KEY = "_sbi_radio_on_change_this_run"
# Short-lived genuine Active-source leave. Survives the required st.rerun();
# session-only — never persist to disk, so remounts/refresh cannot fabricate it.
SBI_ACTIVE_LEAVE_INTENT_KEY = "_sbi_active_leave_intent"
SBI_ACTIVE_LEAVE_RESTORE_RERUN_KEY = "_sbi_active_leave_restore_rerun"
# One-run marker: a genuine Custom/Composition radio click this interaction.
EXPLICIT_SBI_SOURCE_CLICK_KEY = "_explicit_sbi_source_click"
# Durable Custom click — must survive refresh so Follow Active cannot reclaim.
RESTORE_SBI_CUSTOM_SOURCE_KEY = "_restore_sbi_custom_source"
# UUID of the Custom identity that matches a persisted Custom SBI preview.
SBI_CUSTOM_IDENTITY_PICK_KEY = "sbi_custom_identity_pick"
_PENDING_IMPROV_SONG_SOURCE_KEY = "_pending_improv_song_source"
_LAST_IMPROV_SONG_SOURCE_KEY = "_last_improv_song_source"
COMPOSITION_SBI_UNAVAILABLE_TITLE = "No composition source yet"
COMPOSITION_SBI_UNAVAILABLE_MESSAGE = (
    "Composition is not available as an SBI source yet. "
    "No composition progression is loaded."
)


def global_active_is_custom(session: dict[str, Any]) -> bool:
    """True when GLOBAL_ACTIVE_SOURCE currently resolves to Custom.

    Must not infer Custom from LAST_CUSTOM / CPL memory while Global Active
    remains Catalog (Shape + leftover Trial).
    """
    try:
        from songs.music_source import SOURCE_CUSTOM, custom_progression_is_active

        return bool(
            custom_progression_is_active(session)
            and str(session.get("active_music_source") or "") == SOURCE_CUSTOM
        )
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        return pick.startswith("custom::") or pick.startswith("custom\x1f")


def sbi_custom_identity_is_global_active(session: dict[str, Any]) -> bool:
    """True when SBI Custom is the same Custom song that is Global Active (CASE A).

    CASE A: Trial is Global Active → SBI Custom must use the active Custom Practice Key.
    CASE B: Catalog is Global Active → SBI Custom uses LAST_CUSTOM original lifecycle.

    A live ``custom::`` Global Active pick is enough even if ``active_music_source``
    lagged. LAST_CUSTOM / preview pick alone must not impersonate CASE A.
    """
    if global_active_is_custom(session):
        return True
    ga_pick = str(session.get("active_catalog_pick_key") or "").strip()
    return ga_pick.startswith("custom::") or ga_pick.startswith("custom\x1f")


def resolve_sbi_custom_practice_key(
    session: dict[str, Any],
    custom: dict[str, Any] | None = None,
) -> str:
    """Practice concert key for SBI Custom preview / sidebar.

    CASE A (Custom is also Global Active): current active Custom Practice Key.
    CASE B (non-active LAST_CUSTOM): Original / visit lifecycle, not Shape bleed.
    """
    blob = custom if isinstance(custom, dict) else (get_custom_session(session) or {})
    home = str(blob.get("original_key") or blob.get("original_key_center") or "C").strip() or "C"
    try:
        from creative_source_ownership_contract import resolve_custom_saved_original_key

        owned = str(resolve_custom_saved_original_key(session) or "").strip()
        if owned:
            home = owned
    except ImportError:
        pass
    pick = str(blob.get("pick_key") or "").strip()
    if not pick.startswith("custom::"):
        try:
            from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

            snap = session.get(LAST_CUSTOM_STATE_KEY)
            if isinstance(snap, dict):
                pick = str(snap.get("pick_key") or "").strip()
                active = snap.get("active") if isinstance(snap.get("active"), dict) else None
                if not pick.startswith("custom::") and isinstance(active, dict):
                    pick = str(custom_pick_key_for(active) or "").strip()
            if not pick.startswith("custom::"):
                from custom_progression_lab import CPL_ACTIVE_KEY

                live = session.get(CPL_ACTIVE_KEY)
                if isinstance(live, dict):
                    pick = str(custom_pick_key_for(live) or "").strip()
        except Exception:
            pick = str(pick or "").strip()
    sticky = ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        if pick.startswith("custom::"):
            sticky = str(get_practice_concert_key(session, pick, default="") or "").strip()
        if not sticky:
            ga = str(session.get("active_catalog_pick_key") or "").strip()
            if ga.startswith("custom::"):
                sticky = str(get_practice_concert_key(session, ga, default="") or "").strip()
    except ImportError:
        sticky = ""
    if sbi_custom_identity_is_global_active(session):
        if sticky:
            return sticky
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if live:
            return live
        return home
    try:
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override

        if (
            sticky
            and pick.startswith("custom::")
            and catalog_pick_has_user_practice_key_override(session, pick)
        ):
            return sticky
    except ImportError:
        pass
    visit = str(session.get("_sbi_custom_visit_pk") or "").strip()
    if visit:
        return visit
    widget = str(session.get("display_key_sbi_custom") or "").strip()
    if widget:
        return widget
    return home


def _resolve_sbi_custom_uuid_pick(session: dict[str, Any]) -> str:
    """Trial Song UUID for Custom SBI Practice Key writes and hydrate."""
    pick = str(session.get(SBI_CUSTOM_IDENTITY_PICK_KEY) or "").strip()
    if pick.startswith("custom::"):
        return pick
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        pick = str(blob.get(SBI_CUSTOM_IDENTITY_PICK_KEY) or "").strip()
        if pick.startswith("custom::"):
            return pick
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            pick = str(snap.get("pick_key") or "").strip()
            active = snap.get("active") if isinstance(snap.get("active"), dict) else None
            if not pick.startswith("custom::") and isinstance(active, dict):
                pick = str(custom_pick_key_for(active) or "").strip()
        if not pick.startswith("custom::"):
            live = session.get(CPL_ACTIVE_KEY)
            if isinstance(live, dict):
                pick = str(custom_pick_key_for(live) or "").strip()
        if not pick.startswith("custom::"):
            custom = get_custom_session(session) or {}
            pick = str(custom.get("pick_key") or "").strip()
    except Exception:
        pick = str(pick or "").strip()
    return pick if pick.startswith("custom::") else ""


def persist_sbi_custom_practice_key_edit(session: dict[str, Any], token: str) -> str:
    """Write a Custom SBI Practice Key onto the Custom UUID, never Original Key.

    Pre-widget hydrate reads this store. Catalog Perfect's saved Practice Key
    stays untouched. The genuine Custom PK callback must persist Custom + UUID +
    Practice together before a later remount or autosave can fall through.
    """
    tok = str(token or "").strip()
    if not tok:
        return ""
    pick = _resolve_sbi_custom_uuid_pick(session)
    session["_sbi_custom_visit_pk"] = tok
    session["display_key_sbi_custom"] = tok
    # Automatic original-D hydrate must not overwrite this user F on the same run.
    pending = str(session.get("_pending_display_key") or "").strip()
    if pending and pending != tok:
        session.pop("_pending_display_key", None)
        session.pop("_pending_display_key_pick", None)
        session.pop("_pending_display_key_source", None)
    if pick.startswith("custom::"):
        session[SBI_CUSTOM_IDENTITY_PICK_KEY] = pick
        try:
            from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

            mark_practice_key_user_override(session, pick)
            set_practice_concert_key(
                session,
                tok,
                pick_key=pick,
                allow_restore_original=True,
            )
        except ImportError:
            pass
    # PK edits happen while Custom is already selected. Reaffirm the submode +
    # UUID together so a later refresh cannot fall through to Global Active.
    session["_sbi_preview_write_via"] = "persist_sbi_custom_practice_key_edit"
    set_sbi_preview_source(session, SBI_SONG_SOURCE_CUSTOM)
    session[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
    clear_sbi_follow_active_after_explicit_catalog(session)
    stamp_sbi_custom_identity_pick(session)
    session["_sbi_custom_pk_force_save"] = True
    return tok


def last_custom_home_key(session: dict[str, Any]) -> str:
    """LAST_CUSTOM / live CPL original key — Custom mode, never Global Active Shape."""
    home = ""
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            home = str(snap.get("custom_home_key") or "").strip()
            active = snap.get("active")
            if isinstance(active, dict) and not home:
                home = str(
                    active.get("original_key_center") or active.get("original_key") or ""
                ).strip()
    except ImportError:
        home = ""
    if not home:
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY, cpl_draft_written_key

            active = session.get(CPL_ACTIVE_KEY)
            if isinstance(active, dict):
                home = str(cpl_draft_written_key(active) or "").strip()
        except Exception:
            home = ""
    return str(home or "").strip()


def coerce_token_to_custom_home_mode(session: dict[str, Any], token: str) -> str:
    """Keep tonic; apply LAST_CUSTOM/Custom mode so Shape minor cannot turn C into Cm."""
    text = str(token or "").strip()
    if not text:
        return text
    home = last_custom_home_key(session)
    if not home:
        return text
    try:
        from music_theory import coerce_key_to_mode, key_mode

        return coerce_key_to_mode(text, key_mode(home))
    except Exception:
        return text


def sbi_custom_visit_is_local_only(session: dict[str, Any]) -> bool:
    """Creative CASE B: SBI Custom PK is a visit overlay and must not mutate LAST_CUSTOM.

    Custom SBI Backing persist is left unchanged (separate owner / 17-gate).
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "creative":
        return False
    if get_sbi_preview_source(session) != SBI_SONG_SOURCE_CUSTOM:
        return False
    if sbi_custom_identity_is_global_active(session):
        return False
    try:
        from songs.music_source import custom_progression_is_active

        if custom_progression_is_active(session):
            return False
    except ImportError:
        pass
    return True


def composition_sbi_source_available(session: dict[str, Any]) -> bool:
    """True when a distinct Composition progression exists for SBI.

    Future source owner — never fall back to Catalog, Custom, or My Progression.
    """
    del session
    return False


def resolve_sbi_material_kind(
    session: dict[str, Any] | None = None,
    *,
    ctx: Any | None = None,
    owner: str | None = None,
) -> str:
    """Return catalog | custom | composition from SBI owner, never from title.

    SBI Active Source → dereference GLOBAL_ACTIVE (catalog or custom).
    SBI Custom Progression → LAST_CUSTOM (always custom).
    SBI Composition → composition (future owner; currently unavailable).
    """
    sealed = ""
    if ctx is not None:
        sealed = str(getattr(ctx, "sbi_material_kind", "") or "").strip().lower()
        if sealed in SBI_MATERIAL_TYPE_LABELS:
            return sealed
        sealed_owner = str(getattr(ctx, "sbi_source_owner", "") or "").strip()
        if sealed_owner == SBI_SONG_SOURCE_COMPOSITION:
            return SBI_MATERIAL_COMPOSITION
        if sealed_owner == SBI_SONG_SOURCE_CUSTOM:
            return SBI_MATERIAL_CUSTOM
        if sealed_owner == SBI_SONG_SOURCE_ACTIVE:
            bound = str(
                getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
            ).strip()
            if bound.startswith("custom::") or bound.startswith("custom\x1f"):
                return SBI_MATERIAL_CUSTOM
            return SBI_MATERIAL_CATALOG
    src = str(owner or "").strip()
    if not src and session is not None:
        src = get_sbi_preview_source(session)
    if src == SBI_SONG_SOURCE_COMPOSITION:
        return SBI_MATERIAL_COMPOSITION
    if src == SBI_SONG_SOURCE_CUSTOM:
        return SBI_MATERIAL_CUSTOM
    if src == SBI_SONG_SOURCE_ACTIVE:
        if session is not None and global_active_is_custom(session):
            return SBI_MATERIAL_CUSTOM
        bound = ""
        if ctx is not None:
            bound = str(
                getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
            ).strip()
        if bound.startswith("custom::") or bound.startswith("custom\x1f"):
            return SBI_MATERIAL_CUSTOM
        return SBI_MATERIAL_CATALOG
    if ctx is not None:
        bound = str(
            getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
        ).strip()
        if bound.startswith("custom::") or bound.startswith("custom\x1f"):
            return SBI_MATERIAL_CUSTOM
    return SBI_MATERIAL_CATALOG


def sbi_source_type_label(
    session: dict[str, Any] | None = None,
    *,
    ctx: Any | None = None,
    owner: str | None = None,
) -> str:
    """Musician-facing third-segment label for the SBI Backing blue card."""
    kind = resolve_sbi_material_kind(session, ctx=ctx, owner=owner)
    return SBI_MATERIAL_TYPE_LABELS.get(kind, SBI_MATERIAL_TYPE_LABELS[SBI_MATERIAL_CATALOG])


def format_sbi_backing_blue_card_subtitle(
    session: dict[str, Any] | None = None,
    *,
    ctx: Any | None = None,
    owner: str | None = None,
) -> str:
    """``Song-Based Improvisation · {source type}`` — never a repeated workflow name."""
    return f"{SBI_WORKFLOW_LABEL} · {sbi_source_type_label(session, ctx=ctx, owner=owner)}"


def sbi_composition_source_selected(
    session: dict[str, Any] | None = None,
    *,
    ctx: Any | None = None,
) -> bool:
    return resolve_sbi_material_kind(session, ctx=ctx) == SBI_MATERIAL_COMPOSITION


def resolve_composition_sbi_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Isolated Composition preview — empty until a real composition source exists."""
    available = composition_sbi_source_available(session)
    if available:
        return {
            "source": SBI_SONG_SOURCE_COMPOSITION,
            "title": "Composition",
            "artist": "",
            "display_key": "",
            "original_key": "",
            "sections": {},
            "pick_key": "",
            "available": True,
        }
    return {
        "source": SBI_SONG_SOURCE_COMPOSITION,
        "title": COMPOSITION_SBI_UNAVAILABLE_TITLE,
        "artist": "",
        "display_key": "",
        "original_key": "",
        "sections": {},
        "pick_key": "",
        "available": False,
        "unavailable_reason": COMPOSITION_SBI_UNAVAILABLE_MESSAGE,
    }


def adopt_restore_sbi_custom_stamp(session: dict[str, Any]) -> bool:
    """Copy a persisted Custom restore stamp from the Creative blob onto session."""
    if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
        return True
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict) and blob.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        return True
    return False


def clear_restore_sbi_custom_source(session: dict[str, Any]) -> None:
    """Drop a Custom restore stamp from session, blob, and page snapshots.

    An explicit later Active Source click must clear every persisted copy.
    Leaving a Creative-blob or page-snapshot stamp lets refresh re-arm Custom.
    Persist False (not omit) so a later envelope merge cannot revive True.
    """
    session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
    session.pop("_sbi_custom_radio_restore_rerun", None)
    _strip_custom_restore_from_page_snapshots(session)


def _strip_custom_restore_from_page_snapshots(session: dict[str, Any]) -> None:
    store = session.get("_studio_page_snapshots")
    if not isinstance(store, dict):
        return
    for page_id in ("creative", "backing"):
        snap = store.get(page_id)
        if not isinstance(snap, dict):
            continue
        snap[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
        snap.pop("_sbi_custom_radio_restore_rerun", None)


def persist_sbi_active_leave_authority(session: dict[str, Any]) -> None:
    """Atomically persist a genuine Active Source leave before rerun/refresh.

    Writes ``sbi_preview_source = Active song``, clears Custom restore stamps
    and nested Custom rehydrate tokens, and rewrites the Creative page snapshot
    so refresh cannot re-apply Custom D/F. Trial UUID Practice Key is untouched.
    """
    _sbi_gc(session, "persist_sbi_active_leave_authority:before")
    session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
    session[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    session["_improv_song_source_user_touched"] = True
    session["_nested_custom_sbi_backing"] = False
    session["_creative_visit_source"] = "sbi_active"
    session.pop(_PENDING_IMPROV_SONG_SOURCE_KEY, None)
    session.pop("PENDING_IMPROV_SONG_SOURCE", None)
    session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
    session.pop("_sbi_custom_radio_restore_rerun", None)
    visit_left = str(session.get("_sbi_custom_visit_pk") or "").strip()
    session.pop("_sbi_custom_visit_pk", None)
    session.pop("display_key_sbi_custom", None)
    session.pop("_sbi_custom_sidebar_overlay", None)
    clear_restore_sbi_custom_source(session)
    blob = session.get("creative_workspace_state")
    if not isinstance(blob, dict):
        blob = {}
        session["creative_workspace_state"] = blob
    blob[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    blob["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
    blob[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
    blob["_nested_custom_sbi_backing"] = False
    blob.pop("_sbi_custom_visit_pk", None)
    blob.pop("display_key_sbi_custom", None)
    blob.pop("_sbi_custom_sidebar_overlay", None)
    session.pop("_pk_user_commit_token", None)
    session.pop("_pk_user_commit_pick", None)
    catalog_pick, _sel, catalog_orig = resolve_sbi_active_catalog_identity(session)
    catalog_pk = ""
    if catalog_pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            catalog_pk = str(get_practice_concert_key(session, catalog_pick) or "").strip()
        except ImportError:
            catalog_pk = ""
    if catalog_pk:
        session["display_key"] = catalog_pk
        session["concert_key"] = catalog_pk
    if catalog_orig and catalog_pick:
        cat = session.get(CATALOG_SESSION_KEY)
        if not isinstance(cat, dict):
            cat = {}
            session[CATALOG_SESSION_KEY] = cat
        cat["pick_key"] = catalog_pick
        cat["original_key"] = catalog_orig
        if catalog_pk:
            cat["display_key"] = catalog_pk
        blob[CATALOG_SESSION_KEY] = dict(cat)
    raw = session.get("creative_session")
    if isinstance(raw, dict):
        raw["song_source"] = SBI_SONG_SOURCE_ACTIVE
    store = session.get("_studio_page_snapshots")
    if isinstance(store, dict):
        for page_id in ("creative", "backing"):
            snap = store.get(page_id)
            if not isinstance(snap, dict):
                continue
            snap[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
            snap["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
            snap[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
            snap[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
            snap["_nested_custom_sbi_backing"] = False
            snap.pop(_PENDING_IMPROV_SONG_SOURCE_KEY, None)
            snap.pop("PENDING_IMPROV_SONG_SOURCE", None)
            snap.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
            snap.pop("_sbi_custom_visit_pk", None)
            snap.pop("display_key_sbi_custom", None)
            snap.pop("_sbi_custom_sidebar_overlay", None)
            pending_src = str(snap.get("_pending_display_key_source") or "").strip()
            pending_pick = str(snap.get("_pending_display_key_pick") or "").strip()
            if pending_src in _CUSTOM_PENDING_HYDRATE_SOURCES or pending_pick.startswith("custom::"):
                snap.pop("_pending_display_key", None)
                snap.pop("_pending_display_key_pick", None)
                snap.pop("_pending_display_key_source", None)
            catalog_pick, _sel, catalog_orig = resolve_sbi_active_catalog_identity(session)
            catalog_pk = ""
            if catalog_pick:
                try:
                    from songs.practice_key_state import get_practice_concert_key

                    catalog_pk = str(get_practice_concert_key(session, catalog_pick) or "").strip()
                except ImportError:
                    catalog_pk = ""
            if not catalog_pk:
                cat_snap = session.get(CATALOG_SESSION_KEY)
                if isinstance(cat_snap, dict):
                    catalog_pk = str(cat_snap.get("display_key") or "").strip()
            live_pk = str(catalog_pk or session.get("display_key") or "").strip()
            if catalog_pk:
                snap["display_key"] = catalog_pk
                snap["concert_key"] = catalog_pk
            elif live_pk and live_pk != visit_left:
                snap["display_key"] = live_pk
                snap["concert_key"] = live_pk
            if catalog_orig and catalog_pick:
                cat_blob = snap.get(CATALOG_SESSION_KEY)
                if not isinstance(cat_blob, dict):
                    cat_blob = session.get(CATALOG_SESSION_KEY)
                if isinstance(cat_blob, dict):
                    cat_blob = dict(cat_blob)
                    cat_blob["pick_key"] = catalog_pick
                    cat_blob["original_key"] = catalog_orig
                    if catalog_pk:
                        cat_blob["display_key"] = catalog_pk
                    snap[CATALOG_SESSION_KEY] = cat_blob
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session, "creative")
        page = str(session.get("studio_page") or "").strip().lower()
        if page == "backing":
            save_page_snapshot(session, "backing")
    except Exception:
        pass
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass
    _sbi_gc(session, "persist_sbi_active_leave_authority:after")


def sbi_active_leave_intent_pending(session: dict[str, Any]) -> bool:
    """True when a genuine Active-source click armed a leave across a rerun."""
    return bool(session.get(SBI_ACTIVE_LEAVE_INTENT_KEY))


def genuine_sbi_active_leave(session: dict[str, Any]) -> bool:
    """Genuine Active Source click — not a Streamlit remount default.

    The radio ``on_change`` this-run flag is popped before some restore paths
    finish. A short-lived session intent (and pending Active) must still count.
    Automatic remounts set none of these.
    """
    if session.get(SBI_ACTIVE_LEAVE_INTENT_KEY):
        return True
    if str(session.get(SBI_RADIO_ON_CHANGE_THIS_RUN_KEY) or "").strip() == SBI_SONG_SOURCE_ACTIVE:
        return True
    pending = str(
        session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
        or session.get("PENDING_IMPROV_SONG_SOURCE")
        or ""
    ).strip()
    return pending == SBI_SONG_SOURCE_ACTIVE


def genuine_sbi_custom_click(session: dict[str, Any]) -> bool:
    """Genuine Custom/Composition radio click — not a remount leftover.

    Streamlit runs the radio ``on_change`` at the start of the rerun, before
    sidebar hydrate. Remounts never set pending / explicit / this-run flags.
    """
    pending = str(
        session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
        or session.get("PENDING_IMPROV_SONG_SOURCE")
        or ""
    ).strip()
    if pending in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return True
    explicit = str(session.get(EXPLICIT_SBI_SOURCE_CLICK_KEY) or "").strip()
    if explicit in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return True
    clicked = str(session.get(SBI_RADIO_ON_CHANGE_THIS_RUN_KEY) or "").strip()
    return clicked in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}


def consume_sbi_active_leave_intent(session: dict[str, Any]) -> None:
    """Drop the leave intent after Active + Perfect G/C have committed."""
    session.pop(SBI_ACTIVE_LEAVE_INTENT_KEY, None)
    session.pop(SBI_ACTIVE_LEAVE_RESTORE_RERUN_KEY, None)
    if str(session.get(SBI_RADIO_ON_CHANGE_THIS_RUN_KEY) or "").strip() == SBI_SONG_SOURCE_ACTIVE:
        session.pop(SBI_RADIO_ON_CHANGE_THIS_RUN_KEY, None)
    pending = str(
        session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
        or session.get("PENDING_IMPROV_SONG_SOURCE")
        or ""
    ).strip()
    if pending == SBI_SONG_SOURCE_ACTIVE:
        session.pop(_PENDING_IMPROV_SONG_SOURCE_KEY, None)
        session.pop("PENDING_IMPROV_SONG_SOURCE", None)


_CUSTOM_PENDING_HYDRATE_SOURCES = frozenset(
    {
        "sbi_custom",
        "custom",
        "sbi_custom_home",
        "sbi_custom_sidebar_overlay",
        "sbi_custom_visit",
        "leave_sbi_custom_overlay",
        "sbi_custom_sidebar",
    }
)


def sbi_should_install_active_catalog_identity(session: dict[str, Any]) -> bool:
    """True when Active Perfect must own sidebar identity before widgets mount."""
    if genuine_sbi_custom_click(session):
        return False
    if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
        return False
    if genuine_sbi_active_leave(session):
        return True
    try:
        stored = stored_sbi_preview_source(session) or get_sbi_preview_source(session)
    except Exception:
        stored = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    return stored == SBI_SONG_SOURCE_ACTIVE


def _catalog_blob_is_usable(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    pick = str(raw.get("pick_key") or "").strip()
    return bool(pick) and not pick.startswith("custom::") and not pick.startswith("composition::")


def _iter_sbi_active_catalog_blobs(session: dict[str, Any]):
    yield session.get(CATALOG_SESSION_KEY)
    yield session.get("_catalog_before_custom_state")
    yield session.get("_last_catalog_song_state")
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        yield blob.get(CATALOG_SESSION_KEY)
        yield blob.get("_catalog_before_custom_state")
        yield blob.get("_last_catalog_song_state")


def resolve_sbi_active_catalog_identity(
    session: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    """Exact Perfect catalog pick, selected song, and immutable Original Key.

    Original Key is catalog identity / library spelling. Never ``display_key``
    (Perfect Practice C must not become Original C).
    """
    cat = None
    pick = ""
    for raw in _iter_sbi_active_catalog_blobs(session):
        if not _catalog_blob_is_usable(raw):
            continue
        blob_orig = str(raw.get("original_key") or "").strip()
        if blob_orig and blob_orig not in {"C", "C major"}:
            cat = raw
            pick = str(raw.get("pick_key") or "").strip()
            break
        if cat is None:
            cat = raw
            pick = str(raw.get("pick_key") or "").strip()
    if not pick:
        recent = session.get("catalog_recent_pick_keys") or []
        if isinstance(recent, (list, tuple)):
            for raw_pk in recent:
                cand = str(raw_pk or "").strip()
                if cand and not cand.startswith("custom::") and not cand.startswith("composition::"):
                    pick = cand
                    break
    if not pick:
        store = session.get("practice_key_by_source") or {}
        if isinstance(store, dict):
            for raw_pk in store:
                cand = str(raw_pk or "").strip()
                if cand and not cand.startswith("custom::") and not cand.startswith("composition::"):
                    pick = cand
                    break
    if not pick:
        return "", {}, ""
    sel = dict(cat.get("selected_song") or {}) if isinstance(cat, dict) and isinstance(cat.get("selected_song"), dict) else {}
    orig = str((cat or {}).get("original_key") or "").strip() if isinstance(cat, dict) else ""
    try:
        from songs.music_source import ensure_song_picker_catalog, resolve_catalog_song_for_pick

        ensure_song_picker_catalog(session)
        resolved, lib_orig = resolve_catalog_song_for_pick(session, pick)
        lib = str(lib_orig or "").strip()
        if lib and lib not in {"C", "C major"}:
            orig = lib
            if isinstance(resolved, dict) and resolved.get("title"):
                sel = dict(resolved)
        elif orig in {"", "C", "C major"} and lib:
            orig = lib
            if isinstance(resolved, dict) and resolved.get("title"):
                sel = dict(resolved)
        elif isinstance(resolved, dict) and resolved.get("title") and not sel.get("title"):
            sel = dict(resolved)
    except Exception:
        pass
    if orig in {"", "C", "C major"}:
        for raw in _iter_sbi_active_catalog_blobs(session):
            if not _catalog_blob_is_usable(raw):
                continue
            alt = str(raw.get("original_key") or "").strip()
            if alt and alt not in {"", "C", "C major"}:
                orig = alt
                break
    if orig:
        sel["key"] = orig
    if pick:
        sel["pick_key"] = pick
    _sbi_gc(session, "resolve_sbi_active_catalog_identity", resolved_pick=pick, resolved_orig=orig)
    return pick, sel, orig


def clear_sbi_custom_pending_widget_hydrates(session: dict[str, Any]) -> None:
    """Drop every Custom-only pending widget hydrate, including Trial F."""
    session.pop("_sbi_custom_sidebar_overlay", None)
    session.pop("_sbi_custom_visit_pk", None)
    session.pop("display_key_sbi_custom", None)
    session.pop("_sbi_custom_radio_restore_rerun", None)
    _drop_nested_custom_sbi_visit(session)
    try:
        clear_sbi_custom_sidebar_overlay_if_needed(session)
    except Exception:
        pass
    src = str(session.get("_pending_display_key_source") or "").strip()
    pending_pick = str(session.get("_pending_display_key_pick") or "").strip()
    if src in _CUSTOM_PENDING_HYDRATE_SOURCES or pending_pick.startswith("custom::"):
        session.pop("_pending_display_key", None)
        session.pop("_pending_display_key_pick", None)
        session.pop("_pending_display_key_source", None)


def restore_sbi_active_catalog_identity_before_widgets(session: dict[str, Any]) -> str:
    """Atomically install Active Perfect Original G + Practice C before widgets.

    Resolves the exact catalog pick, writes immutable Original Key from catalog
    identity, writes pick-scoped Practice Key from the catalog store, and
    suspends Custom-only pending hydrates (Trial F) so they cannot remount.
    """
    _sbi_gc(session, "restore_sbi_active_catalog_identity:before")
    try:
        from sbi_active_catalog_practice_key import (
            SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY,
            sbi_active_canonical_practice_key,
            sbi_active_live_is_foreign_leftover,
        )

        live_now = str(session.get("display_key") or "").strip()
        canonical_now = str(sbi_active_canonical_practice_key(session, "") or "").strip()
        if live_now and canonical_now and sbi_active_live_is_foreign_leftover(
            session, canonical_now
        ):
            # Allow one refresh remount after a prior Active-click fingerprint.
            clears = int(session.get("_sbi_active_refresh_pk_fp_clears") or 0)
            if clears < 1:
                session.pop(SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY, None)
                session["_sbi_active_refresh_pk_fp_clears"] = clears + 1
    except Exception:
        pass
    clear_sbi_custom_pending_widget_hydrates(session)
    pick, sel, orig = resolve_sbi_active_catalog_identity(session)
    if pick and orig:
        try:
            from songs.music_source import _sync_catalog_session_surface_keys

            _sync_catalog_session_surface_keys(
                session,
                pick_key=pick,
                selected_song=sel,
            )
        except Exception:
            session["active_catalog_pick_key"] = pick
            session["selected_song"] = sel
            title = str(sel.get("title") or "").strip()
            if title:
                session["song"] = title
                session["active_song_title"] = title
        cat = session.get(CATALOG_SESSION_KEY)
        if not isinstance(cat, dict):
            cat = {}
            session[CATALOG_SESSION_KEY] = cat
        cat["pick_key"] = pick
        cat["original_key"] = orig
        cat["selected_song"] = sel
        session["catalog_original_key"] = orig
        sections = cat.get("sections") or sel.get("sections")
        if isinstance(sections, dict) and sections:
            session["home_sections"] = sections
            session["improv_song_concert_sections"] = sections
            cat["sections"] = sections
    catalog_pk = ""
    try:
        from studio_page_state import _restore_sbi_active_catalog_practice_key

        catalog_pk = str(
            _restore_sbi_active_catalog_practice_key(
                session,
                force_widget_write=True,
            )
            or ""
        ).strip()
    except ImportError:
        catalog_pk = ""
    cat = session.get(CATALOG_SESSION_KEY)
    if isinstance(cat, dict) and orig:
        cat["original_key"] = orig
        live_sel = cat.get("selected_song")
        if isinstance(live_sel, dict):
            live_sel["key"] = orig
        session_sel = session.get("selected_song")
        if isinstance(session_sel, dict) and str(session_sel.get("pick_key") or "").strip() == pick:
            session_sel["key"] = orig
        if catalog_pk:
            cat["display_key"] = catalog_pk
    _sbi_gc(
        session,
        "restore_sbi_active_catalog_identity:after",
        restored_pick=pick,
        restored_orig=orig,
        restored_pk=catalog_pk,
    )
    return catalog_pk


def sbi_active_catalog_fields_installed(session: dict[str, Any], catalog_pk: str = "") -> bool:
    """True when catalog Original and Practice are both installed (and distinct)."""
    pick, _sel, orig = resolve_sbi_active_catalog_identity(session)
    pk = str(catalog_pk or session.get("display_key") or "").strip()
    if pick and not pk:
        try:
            from songs.practice_key_state import get_practice_concert_key

            pk = str(get_practice_concert_key(session, pick) or "").strip()
        except ImportError:
            pk = ""
    return bool(pick and orig and pk)


def stamp_sbi_active_leave_intent(session: dict[str, Any]) -> None:
    """Arm a genuine Active-source leave so it survives the required rerun."""
    _sbi_gc(session, "stamp_sbi_active_leave_intent:before")
    session[SBI_ACTIVE_LEAVE_INTENT_KEY] = True
    session[SBI_RADIO_ON_CHANGE_THIS_RUN_KEY] = SBI_SONG_SOURCE_ACTIVE
    session[_PENDING_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    session["PENDING_IMPROV_SONG_SOURCE"] = SBI_SONG_SOURCE_ACTIVE
    session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
    session["_improv_song_source_user_touched"] = True
    clear_restore_sbi_custom_source(session)
    session["_sbi_preview_write_via"] = "stamp_sbi_active_leave_intent"
    set_sbi_preview_source(session, SBI_SONG_SOURCE_ACTIVE)
    session[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
        blob.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
    restore_sbi_active_catalog_identity_before_widgets(session)
    persist_sbi_active_leave_authority(session)
    session["_sbi_active_leave_force_save"] = True
    session.pop("_sbi_active_refresh_pk_fp_clears", None)
    _sbi_gc(session, "stamp_sbi_active_leave_intent:after")
    _sbi_source_click_trace(
        session,
        "stamp_sbi_active_leave_intent",
        clicked=SBI_SONG_SOURCE_ACTIVE,
        intent=True,
    )


def note_explicit_sbi_source_selection(session: dict[str, Any], source: str) -> None:
    """Stamp a genuine Custom/Composition click so Follow Active cannot heal it."""
    src = str(source or "").strip()
    if src not in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
        return
    session[EXPLICIT_SBI_SOURCE_CLICK_KEY] = src
    session[_PENDING_IMPROV_SONG_SOURCE_KEY] = src
    session["_improv_song_source_user_touched"] = True
    if src == SBI_SONG_SOURCE_CUSTOM:
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        blob = session.get("creative_workspace_state")
        if isinstance(blob, dict):
            blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
            blob.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)
        try:
            from creative_workspace_persistence import mark_creative_workspace_dirty

            mark_creative_workspace_dirty(session)
        except ImportError:
            pass
    else:
        session.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
        blob = session.get("creative_workspace_state")
        if isinstance(blob, dict):
            blob.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
    clear_sbi_follow_active_after_explicit_catalog(session)


def seed_sbi_custom_radio_before_render(session: dict[str, Any]) -> str:
    """Seed ``improv_song_source`` immediately before ``st.radio`` on refresh.

    Streamlit's Song Source radio defaults to Active on a new session even when
    persist already has Custom. Flush may run hundreds of lines earlier; this
    write is the last assignment before the widget instantiates.

    Persisted ``sbi_preview_source`` is the selected SBI submode. A leftover
    Custom restore stamp must not reopen Custom when the user refreshed on
    Active or Composition.
    """
    adopt_restore_sbi_custom_stamp(session)
    stored = stored_sbi_preview_source(session)
    live = str(session.get("improv_song_source") or "").strip()
    if sbi_must_follow_global_active(session):
        return live
    if genuine_sbi_active_leave(session):
        if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
            clear_restore_sbi_custom_source(session)
        if live != SBI_SONG_SOURCE_ACTIVE:
            session.pop("improv_song_source", None)
            session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
        return SBI_SONG_SOURCE_ACTIVE
    if stored == SBI_SONG_SOURCE_ACTIVE:
        if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
            clear_restore_sbi_custom_source(session)
        if live != SBI_SONG_SOURCE_ACTIVE:
            session.pop("improv_song_source", None)
            session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
        return SBI_SONG_SOURCE_ACTIVE
    if stored == SBI_SONG_SOURCE_COMPOSITION:
        if live != SBI_SONG_SOURCE_COMPOSITION:
            session.pop("improv_song_source", None)
            session["improv_song_source"] = SBI_SONG_SOURCE_COMPOSITION
        session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_COMPOSITION
        return SBI_SONG_SOURCE_COMPOSITION
    if stored != SBI_SONG_SOURCE_CUSTOM and not session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
        return live
    seen = bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    genuine_active = genuine_sbi_active_leave(session)
    # Flush may already have rewritten `_last_improv_song_source` to Active
    # on this same run. Widget-seen (Custom radio already mounted this
    # session) distinguishes a real Active click from a remount leftover.
    _sbi_source_click_trace(
        session,
        "seed_sbi_custom_radio_before_render",
        live=live,
        seen=seen,
        last=last,
        restore=True,
        stored=stored,
        genuine_active=genuine_active,
        intent=bool(session.get(SBI_ACTIVE_LEAVE_INTENT_KEY)),
    )
    if genuine_active:
        if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
            clear_restore_sbi_custom_source(session)
        if live != SBI_SONG_SOURCE_ACTIVE:
            session.pop("improv_song_source", None)
            session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
        return SBI_SONG_SOURCE_ACTIVE
    if live == SBI_SONG_SOURCE_ACTIVE and seen:
        # Preserve the click-run widget value so on_change can stamp intent.
        session.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
        blob = session.get("creative_workspace_state")
        if isinstance(blob, dict):
            blob.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
        return live
    if live != SBI_SONG_SOURCE_CUSTOM:
        session.pop("improv_song_source", None)
        session["improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
    session[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
    return SBI_SONG_SOURCE_CUSTOM


def apply_sbi_radio_live_against_restore_stamp(session: dict[str, Any], live_src: str) -> str:
    """Durable Custom stamp beats a remounted Active radio; a later Active click wins.

    Refresh remounts Streamlit's ``improv_song_source`` widget as Active even when
    persist still has Custom. That remount must not pop the stamp or write Active.
    A real later Active click (Custom was already hydrated this run) may leave.
    """
    src = str(live_src or "").strip() or SBI_SONG_SOURCE_ACTIVE
    adopt_restore_sbi_custom_stamp(session)
    restore = bool(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    seen = bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))
    leftover_a = (
        bool(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        and not restore
        and not seen
        and last != SBI_SONG_SOURCE_ACTIVE
        and src in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}
    )
    if src == SBI_SONG_SOURCE_CUSTOM:
        if leftover_a:
            return src
        note_explicit_sbi_source_selection(session, src)
        return src
    if src == SBI_SONG_SOURCE_COMPOSITION:
        if leftover_a:
            return src
        note_explicit_sbi_source_selection(session, src)
        return src
    if src == SBI_SONG_SOURCE_ACTIVE and restore:
        stored = stored_sbi_preview_source(session)
        if stored == SBI_SONG_SOURCE_ACTIVE:
            clear_restore_sbi_custom_source(session)
            return SBI_SONG_SOURCE_ACTIVE
        if stored == SBI_SONG_SOURCE_COMPOSITION:
            return SBI_SONG_SOURCE_COMPOSITION
        genuine_leave = genuine_sbi_active_leave(session)
        if genuine_leave:
            clear_restore_sbi_custom_source(session)
            return SBI_SONG_SOURCE_ACTIVE
        return SBI_SONG_SOURCE_CUSTOM
    if src == SBI_SONG_SOURCE_ACTIVE:
        stored = stored_sbi_preview_source(session)
        genuine_leave = genuine_sbi_active_leave(session)
        # Fresh-session remount of the radio as Active must not pop a valid
        # persisted Custom/Composition selection or look like a user leave.
        if stored in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION} and not genuine_leave:
            return stored
        session.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
        blob = session.get("creative_workspace_state")
        if isinstance(blob, dict):
            blob.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
    return src


def stored_sbi_preview_source(session: dict[str, Any]) -> str:
    """Persisted SBI submode. Widget remounts must not outrank this value."""
    adopt_restore_sbi_custom_stamp(session)
    val = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    blob_val = ""
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob_val = str(blob.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    seen = bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))
    # A remounted Active default must not beat a Creative-blob Custom/Composition
    # selection that has not yet been confirmed by a mounted radio.
    if (
        blob_val in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}
        and val in {"", SBI_SONG_SOURCE_ACTIVE}
        and not seen
    ):
        return blob_val
    if val in IMPROV_SONG_SOURCES:
        return val
    if blob_val in IMPROV_SONG_SOURCES:
        return blob_val
    return ""


def _explicit_sbi_source_outranks_follow(session: dict[str, Any]) -> bool:
    """True when this run has a new Custom/Composition click, not leftover persist."""
    pending = str(
        session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
        or session.get("PENDING_IMPROV_SONG_SOURCE")
        or ""
    ).strip()
    if pending in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return True
    explicit = str(session.get(EXPLICIT_SBI_SOURCE_CLICK_KEY) or "").strip()
    if explicit in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return True
    preview = stored_sbi_preview_source(session) or str(
        session.get(SBI_PREVIEW_SOURCE_KEY) or session.get("improv_song_source") or ""
    ).strip()
    if adopt_restore_sbi_custom_stamp(session):
        # Leftover Custom stamp must not look like a click while persisted mode is Active.
        if preview not in {SBI_SONG_SOURCE_ACTIVE, SBI_SONG_SOURCE_COMPOSITION}:
            return True
    if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY) and preview == SBI_SONG_SOURCE_CUSTOM:
        return True
    live = str(session.get("improv_song_source") or "").strip()
    if live not in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return False
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    preview = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    # After Follow Active rendered Active, a live Custom/Composition radio is a click.
    # Preview still Active while the widget already says Custom is the same-run click
    # before on_change (sidebar hydrates first).
    if (
        session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY)
        or last == SBI_SONG_SOURCE_ACTIVE
        or (preview == SBI_SONG_SOURCE_ACTIVE and live == SBI_SONG_SOURCE_CUSTOM)
    ):
        return True
    return False


def sbi_must_follow_global_active(session: dict[str, Any]) -> bool:
    """True after an explicit catalog pick until the user chooses Custom/Composition.

    Leftover persisted Custom is forced back to Active. An explicit later click
    (pending Custom/Composition, one-run marker, or live radio after the Active
    bind already rendered) outranks the follow flag.

    A cold hydrate of an explicit Custom/Composition selection is different:
    Streamlit remounts ``improv_song_source`` as Active. That remount must not
    let a stale follow-active leftover steal the persisted SBI view. Same-run
    leftover Custom widgets after a catalog pick still have live Custom and
    are flushed to Active.
    """
    adopt_restore_sbi_custom_stamp(session)
    if not session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY):
        return False
    if _explicit_sbi_source_outranks_follow(session):
        return False
    stored = stored_sbi_preview_source(session)
    live = str(session.get("improv_song_source") or "").strip()
    seen = bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY))
    if (
        stored in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}
        and live in {"", SBI_SONG_SOURCE_ACTIVE}
        and not seen
    ):
        return False
    return True


def bind_sbi_preview_to_active_after_explicit_catalog(session: dict[str, Any]) -> None:
    """SBI Active Source follows the new Global Active catalog song.

    Style Jam / SBI Custom leftover radios must not keep LAST_CUSTOM as the
    preview after an explicit Songs pick. CASE B is a later explicit Custom click.
    """
    session[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
    session.pop(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY, None)
    session.pop(EXPLICIT_SBI_SOURCE_CLICK_KEY, None)
    session.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)
    session.pop("_pending_improv_song_source", None)
    session["_improv_song_source_user_touched"] = True
    session["_sbi_song_source_hydrated"] = True
    session["_sbi_preview_write_via"] = "bind_sbi_preview_to_active_after_explicit_catalog"
    set_sbi_preview_source(session, SBI_SONG_SOURCE_ACTIVE)
    session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
    session["creative_backing_song_source"] = SBI_SONG_SOURCE_ACTIVE
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        blob["sbi_preview_source"] = SBI_SONG_SOURCE_ACTIVE
        blob[SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY] = True
        blob.pop(RESTORE_SBI_CUSTOM_SOURCE_KEY, None)


def clear_sbi_follow_active_after_explicit_catalog(session: dict[str, Any]) -> None:
    # Keep widget-seen. Custom/Composition radio already mounted this session;
    # popping seen made the next Active click look like a remount leftover and
    # let the Custom restore stamp eat it before widgets hydrated.
    session.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)


def _sbi_gc(session: dict[str, Any], tag: str, **extra: Any) -> None:
    try:
        from sbi_gc_lifecycle_trace import emit_sbi_gc

        emit_sbi_gc(session, tag, **extra)
    except Exception:
        pass


def _sbi_source_click_trace(session: dict[str, Any], stage: str, **extra: Any) -> None:
    """Append one SBI source snapshot when SBI_SOURCE_CLICK_TRACE=1."""
    import json
    import os
    import time

    if str(os.environ.get("SBI_SOURCE_CLICK_TRACE") or "").strip() not in {"1", "true", "True"}:
        return
    root = str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
    if not root:
        return
    ga_title = ""
    last_custom_title = ""
    last_custom_key = ""
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            last_custom_title = str(snap.get("name") or "").strip()
            active = snap.get("active")
            if isinstance(active, dict):
                last_custom_title = last_custom_title or str(
                    active.get("title") or active.get("name") or ""
                ).strip()
                last_custom_key = str(active.get("key") or active.get("original_key") or "").strip()
    except Exception:
        pass
    try:
        sel = session.get("selected_song")
        if isinstance(sel, dict):
            ga_title = str(sel.get("title") or "").strip()
        ga_title = ga_title or str(session.get("song") or "").strip()
    except Exception:
        pass
    row = {
        "ts": time.time(),
        "stage": stage,
        "follow_active": bool(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY)),
        "widget_seen": bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY)),
        "explicit_click": str(session.get(EXPLICIT_SBI_SOURCE_CLICK_KEY) or ""),
        "pending": str(
            session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
            or session.get("PENDING_IMPROV_SONG_SOURCE")
            or ""
        ),
        "live": str(session.get("improv_song_source") or ""),
        "preview": str(session.get(SBI_PREVIEW_SOURCE_KEY) or ""),
        "last": str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or ""),
        "must_follow": sbi_must_follow_global_active(session),
        "ga_title": ga_title,
        "ga_source": str(session.get("active_music_source") or ""),
        "last_custom_title": last_custom_title,
        "last_custom_key": last_custom_key,
    }
    row.update(extra)
    try:
        path = os.path.join(root, "_sbi_source_click.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def get_sbi_preview_source(session: dict[str, Any]) -> str:
    """Read SBI preview source (never reads handoff-only keys).

    Do **not** infer Custom from ``cpl_session_is_active``: a live CPL draft /
    LAST_CUSTOM memory can exist while Global Active stays Catalog and the user
    is on Creative → SBI → Active. That inference collapsed nested SBI Custom
    into “we’re on Custom” semantics and helped reboot land on top-level Custom.
    """
    adopt_restore_sbi_custom_stamp(session)
    if sbi_must_follow_global_active(session):
        return SBI_SONG_SOURCE_ACTIVE
    stored = stored_sbi_preview_source(session)
    if stored in IMPROV_SONG_SOURCES:
        return stored
    if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY):
        return SBI_SONG_SOURCE_CUSTOM
    val = str(session.get("improv_song_source") or "").strip()
    if val in IMPROV_SONG_SOURCES:
        return val
    return "Active song"


def stamp_sbi_custom_identity_pick(session: dict[str, Any]) -> str:
    """Persist the Custom UUID that belongs with a Custom SBI preview."""
    pick = str(session.get(SBI_CUSTOM_IDENTITY_PICK_KEY) or "").strip()
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            snap_pick = str(snap.get("pick_key") or "").strip()
            active = snap.get("active")
            if isinstance(active, dict):
                snap_pick = str(custom_pick_key_for(active) or snap_pick or "").strip()
            if snap_pick.startswith("custom::"):
                pick = snap_pick
    except Exception:
        pass
    if not pick.startswith("custom::"):
        return ""
    session[SBI_CUSTOM_IDENTITY_PICK_KEY] = pick
    blob = session.get("creative_workspace_state")
    if not isinstance(blob, dict):
        blob = {}
        session["creative_workspace_state"] = blob
    blob[SBI_CUSTOM_IDENTITY_PICK_KEY] = pick
    return pick


_ACTIVE_PREVIEW_WRITE_ALLOW_VIA = frozenset(
    {
        "flush_pending_improv_song_source_follow_active",
        "bind_sbi_preview_to_active_after_explicit_catalog",
        "after_sbi_source_radio_active",
        "install_sbi_custom_identity_genuine_active",
        "ensure_improv_song_source_follow_active",
        "stamp_sbi_active_leave_intent",
        "apply_improv_song_source_active",
    }
)


def _emit_sbi_preview_active_write_log(session: dict[str, Any], row: dict[str, Any]) -> None:
    """Always land Active-song writes on disk when MUSIC_APP_DATA_DIR is set."""
    import json
    import os

    if str(row.get("to") or "") != SBI_SONG_SOURCE_ACTIVE and not row.get("refused"):
        return
    root = str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
    if not root:
        return
    try:
        path = os.path.join(root, "_sbi_preview_source_writes.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def _should_refuse_active_preview_write(session: dict[str, Any], prev: str, via: str) -> bool:
    """Block remount/hydrate Active writes that would steal a live Custom view.

    Genuine Active clicks and the owner-checked leave vias may persist Active.
    Default ``set_sbi_preview_source`` / init remounts must not.
    """
    if genuine_sbi_active_leave(session):
        return False
    if via in _ACTIVE_PREVIEW_WRITE_ALLOW_VIA:
        return False
    blob_val = ""
    blob = session.get("creative_workspace_state")
    if isinstance(blob, dict):
        blob_val = str(blob.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    held = prev or blob_val or last
    if held in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return True
    if session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY) and held != SBI_SONG_SOURCE_ACTIVE:
        return True
    return False


def _should_refuse_custom_preview_write(session: dict[str, Any], prev: str, via: str) -> bool:
    """Block remounted Custom leftovers from overwriting a persisted Active leave."""
    if via in {
        "persist_sbi_custom_practice_key_edit",
        "install_sbi_custom_identity_before_widgets",
        "restore_sbi_song_source_from_backing_context",
        "capo_seal_temporary_custom",
    }:
        return False
    if genuine_sbi_custom_click(session):
        return False
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    if last in {SBI_SONG_SOURCE_CUSTOM, SBI_SONG_SOURCE_COMPOSITION}:
        return False
    stored = ""
    try:
        stored = stored_sbi_preview_source(session) or prev
    except Exception:
        stored = prev
    if (stored or prev) != SBI_SONG_SOURCE_ACTIVE:
        return False
    return True


def _record_sbi_preview_source_write(
    session: dict[str, Any],
    prev: str,
    src: str,
    via: str,
    *,
    refused: bool = False,
) -> None:
    if prev == src and not refused and src != SBI_SONG_SOURCE_ACTIVE:
        return
    rec = session.get("_sbi_preview_source_writes")
    if not isinstance(rec, list):
        rec = []
        session["_sbi_preview_source_writes"] = rec
    row: dict[str, Any] = {"from": prev, "to": src, "via": via, "refused": refused}
    if src == SBI_SONG_SOURCE_ACTIVE or refused:
        try:
            import traceback

            row["stack"] = [ln.strip() for ln in traceback.format_stack(limit=12)[-8:]]
        except Exception:
            row["stack"] = []
    rec.append({k: v for k, v in row.items() if k != "stack"})
    _sbi_source_click_trace(
        session,
        "set_sbi_preview_source",
        prev=prev,
        src=src,
        via=via,
        refused=refused,
    )
    _emit_sbi_preview_active_write_log(session, row)


def set_sbi_preview_source(session: dict[str, Any], source: str) -> None:
    src = str(source or "Active song").strip() or "Active song"
    if src not in IMPROV_SONG_SOURCES:
        src = "Active song"
    prev = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    via = str(session.pop("_sbi_preview_write_via", None) or "set_sbi_preview_source").strip()
    if src == SBI_SONG_SOURCE_ACTIVE and _should_refuse_active_preview_write(session, prev, via):
        _record_sbi_preview_source_write(session, prev, src, via, refused=True)
        return
    if src == SBI_SONG_SOURCE_CUSTOM and _should_refuse_custom_preview_write(session, prev, via):
        _record_sbi_preview_source_write(session, prev, src, via, refused=True)
        return
    session[SBI_PREVIEW_SOURCE_KEY] = src
    blob = session.get("creative_workspace_state")
    if not isinstance(blob, dict):
        blob = {}
        session["creative_workspace_state"] = blob
    blob[SBI_PREVIEW_SOURCE_KEY] = src
    blob["improv_song_source"] = src
    if src == SBI_SONG_SOURCE_CUSTOM:
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        session[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
        blob[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
        blob.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)
        clear_sbi_follow_active_after_explicit_catalog(session)
        stamp_sbi_custom_identity_pick(session)
        try:
            from active_song_transition import mark_temporary_workflow_owner

            mark_temporary_workflow_owner(session, "sbi_custom")
        except ImportError:
            pass
    elif src == "Composition":
        try:
            from active_song_transition import mark_temporary_workflow_owner

            mark_temporary_workflow_owner(session, "sbi_composition")
        except ImportError:
            pass
    elif src == SBI_SONG_SOURCE_ACTIVE:
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
        blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = False
        try:
            from active_song_transition import clear_temporary_workflow_owner

            clear_temporary_workflow_owner(session)
        except ImportError:
            pass
    tab_now = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    entry_now = str(session.get("improv_entry_mode") or "").strip()
    if (
        src in {SBI_SONG_SOURCE_ACTIVE, SBI_SONG_SOURCE_CUSTOM, "Composition"}
        and tab_now != "Entry & Jam"
        and entry_now in {"Style Jam Mode", "Jam Session Generator"}
    ):
        session["improv_entry_mode"] = SBI_WORKFLOW_LABEL
        blob["improv_entry_mode"] = SBI_WORKFLOW_LABEL
    # Nested SBI source tab must survive refresh/reboot with Creative page.
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        pass
    _record_sbi_preview_source_write(session, prev, src, via)
    try:
        from active_song_transition import capture_owner_key_boundary

        session["_owner_key_boundary"] = capture_owner_key_boundary(session, surface="sbi_preview")
    except ImportError:
        pass
    # Opening SBI → Custom must install LAST_CUSTOM Trial Song into the preview
    # shell when live CPL / custom_session is still the empty My Progression draft.
    # Do not clobber an already-good Trial Song custom_session bucket.
    if src == "Custom progression":
        try:
            from songs.music_source import install_last_custom_into_live_cpl

            install_last_custom_into_live_cpl(
                session,
                reset_practice_key_to_original=False,
                ignore_new_song_skip=True,
                prefer_last_custom=True,
            )
            try:
                sync_custom_session(session)
            except Exception:
                pass
        except ImportError:
            pass
        stamp_sbi_custom_identity_pick(session)


def install_sbi_custom_identity_before_widgets(session: dict[str, Any]) -> bool:
    """Switch SBI owner to Custom and install LAST_CUSTOM before sidebar widgets.

    Perfect follow-active must not keep a generic My Progression C shell when
    the user (or persisted restore) selected Custom. Disk Trial Song D/D is
    the canonical Custom identity.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page not in {"creative", "backing"}:
        return False
    live = str(session.get("improv_song_source") or "").strip()
    pending = str(
        session.get(_PENDING_IMPROV_SONG_SOURCE_KEY)
        or session.get("PENDING_IMPROV_SONG_SOURCE")
        or ""
    ).strip()
    adopt_restore_sbi_custom_stamp(session)
    preview = stored_sbi_preview_source(session) or str(
        session.get(SBI_PREVIEW_SOURCE_KEY) or ""
    ).strip()
    restore = bool(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
    last = str(session.get(_LAST_IMPROV_SONG_SOURCE_KEY) or "").strip()
    _sbi_source_click_trace(
        session,
        "install_sbi_custom_identity_before_widgets",
        live=live,
        pending=pending,
        preview=preview,
        restore=restore,
        last=last,
        seen=bool(session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY)),
        page=page,
    )
    if genuine_sbi_active_leave(session):
        # Genuine Active click, including after the required restore rerun
        # where the this-run on_change flag is already gone. Remounts do not
        # arm leave intent and must not take this path.
        _sbi_gc(session, "install_sbi_custom_identity:genuine_active:before")
        try:
            session.pop("improv_song_source", None)
            session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        except Exception:
            session["improv_song_source"] = SBI_SONG_SOURCE_ACTIVE
        session.pop(_PENDING_IMPROV_SONG_SOURCE_KEY, None)
        session.pop("PENDING_IMPROV_SONG_SOURCE", None)
        clear_restore_sbi_custom_source(session)
        session["_sbi_preview_write_via"] = "install_sbi_custom_identity_genuine_active"
        set_sbi_preview_source(session, SBI_SONG_SOURCE_ACTIVE)
        session[_LAST_IMPROV_SONG_SOURCE_KEY] = SBI_SONG_SOURCE_ACTIVE
        catalog_pk = restore_sbi_active_catalog_identity_before_widgets(session)
        persist_sbi_active_leave_authority(session)
        # Consume only after both catalog Original and Practice are installed
        # and persisted. Remounts must not look like another leave.
        if sbi_active_catalog_fields_installed(session, catalog_pk):
            consume_sbi_active_leave_intent(session)
        _sbi_gc(
            session,
            "install_sbi_custom_identity:genuine_active:after",
            restored_pk=catalog_pk,
        )
        return False
    if live == SBI_SONG_SOURCE_ACTIVE and bool(
        session.get(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY)
    ):
        persisted_active = (
            preview == SBI_SONG_SOURCE_ACTIVE
            and not restore
            and not genuine_sbi_custom_click(session)
        )
        if persisted_active or genuine_sbi_active_leave(session):
            # Persisted Active leave — drop leftover Custom overlay PK and
            # restore Perfect's pick-scoped Practice Key before widgets mount.
            session.pop("_sbi_custom_sidebar_overlay", None)
            clear_sbi_custom_sidebar_overlay_if_needed(session)
            restore_sbi_active_catalog_identity_before_widgets(session)
            return False
        # Remounted Active default while Custom is still the persisted owner.
        # Fall through so Custom identity reinstalls; do not treat this as leave.
    genuine_click = genuine_sbi_custom_click(session)
    if genuine_click:
        note_explicit_sbi_source_selection(session, SBI_SONG_SOURCE_CUSTOM)
    if sbi_must_follow_global_active(session) and not genuine_click:
        return False
    custom_intent = genuine_click or (
        not sbi_must_follow_global_active(session)
        and (
            preview == SBI_SONG_SOURCE_CUSTOM
            or (
                restore
                and preview not in {SBI_SONG_SOURCE_ACTIVE, SBI_SONG_SOURCE_COMPOSITION}
            )
        )
    )
    if not custom_intent:
        if (
            preview == SBI_SONG_SOURCE_ACTIVE
            and not restore
            and not genuine_sbi_custom_click(session)
        ):
            restore_sbi_active_catalog_identity_before_widgets(session)
        return False
    note_explicit_sbi_source_selection(session, SBI_SONG_SOURCE_CUSTOM)
    session["improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
    session["_last_improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        catalog_pick = str(resolve_practice_source_pick(session) or "").strip()
        if catalog_pick and not catalog_pick.startswith("custom::") and not session.get(
            "_sbi_custom_sealed_catalog_pk"
        ):
            existing = str(get_practice_concert_key(session, catalog_pick) or "").strip()
            if existing:
                session["_sbi_custom_sealed_catalog_pk"] = existing
                session["_sbi_custom_sealed_catalog_pick"] = catalog_pick
    except ImportError:
        pass
    session["_sbi_custom_sidebar_overlay"] = True
    set_sbi_preview_source(session, SBI_SONG_SOURCE_CUSTOM)
    session["creative_backing_song_source"] = SBI_SONG_SOURCE_CUSTOM
    session["_nested_custom_sbi_backing"] = True
    session["_backing_explicit_handoff_source"] = "song_improv"
    # Entry & Jam / Song-Based leave-mission stamps released=True. Nested Custom
    # Pages→Backing must still rebuild song_improv Trial, not catalog Perfect.
    session.pop("_backing_released_specialized_context", None)
    try:
        from backing_context import BACKING_PREF_CREATIVE, set_backing_source_preference

        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
    except ImportError:
        session["_backing_source_preference"] = "creative"
    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, install_last_custom_into_live_cpl
        from custom_progression_lab import CPL_ACTIVE_KEY

        # Install Trial identity into live CPL only. Do not reset shared
        # display_key / concert_key — that stamps Trial D onto parked Catalog
        # Perfect when Global Active is still the catalog pick.
        install_last_custom_into_live_cpl(
            session,
            reset_practice_key_to_original=False,
            ignore_new_song_skip=True,
            prefer_last_custom=True,
        )
        snap = session.get(LAST_CUSTOM_STATE_KEY)
        active = snap.get("active") if isinstance(snap, dict) else None
        home = ""
        if isinstance(active, dict):
            home = str(active.get("original_key_center") or snap.get("custom_home_key") or "").strip()
        live_cpl = session.get(CPL_ACTIVE_KEY)
        if isinstance(live_cpl, dict) and not home:
            home = str(live_cpl.get("original_key_center") or "").strip()
        if home:
            pick = ""
            if isinstance(snap, dict):
                pick = str(snap.get("pick_key") or "").strip()
            if not str(pick).startswith("custom::"):
                pick = ""
            if not pick:
                try:
                    from songs.music_source import custom_pick_key_for

                    live_for_pick = active if isinstance(active, dict) else live_cpl
                    if isinstance(live_for_pick, dict):
                        pick = str(custom_pick_key_for(live_for_pick) or "").strip()
                except ImportError:
                    pick = ""
            token = home
            if pick.startswith("custom::"):
                try:
                    from songs.practice_key_state import (
                        catalog_pick_has_user_practice_key_override,
                        get_practice_concert_key,
                        mark_practice_key_user_override,
                        set_practice_concert_key,
                    )

                    saved = str(get_practice_concert_key(session, pick) or "").strip()
                    has_override = catalog_pick_has_user_practice_key_override(session, pick)
                    widget = str(session.get("display_key_sbi_custom") or "").strip()
                    visit = str(session.get("_sbi_custom_visit_pk") or "").strip()
                    live_edit = widget or visit
                    if has_override and saved:
                        token = saved
                    elif live_edit and live_edit != home:
                        token = live_edit
                        mark_practice_key_user_override(session, pick)
                        set_practice_concert_key(
                            session,
                            token,
                            pick_key=pick,
                            allow_restore_original=True,
                        )
                    elif saved:
                        token = saved
                    else:
                        token = home
                        set_practice_concert_key(
                            session,
                            home,
                            pick_key=pick,
                            allow_restore_original=True,
                        )
                except ImportError:
                    token = home
            session["_sbi_custom_visit_pk"] = token
            # Pre-widget seed only. Never rewrite a live user Practice Key edit.
            if "display_key_sbi_custom" not in session:
                session["display_key_sbi_custom"] = token
        try:
            sync_custom_session(session)
        except Exception:
            pass
        try:
            from music_workflow_song_practice import ensure_song_practice_blob_for_active_song

            ensure_song_practice_blob_for_active_song(
                session,
                practice_key=str(session.get("_sbi_custom_visit_pk") or home),
                original_key=home,
            )
        except Exception:
            pass
    except ImportError:
        pass
    return True


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
            if not pk or pk.startswith("custom::") or pk.startswith("composition::"):
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
    if not pick or pick.startswith("custom::") or pick.startswith("composition::"):
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
        if not pick.startswith("custom::") and not pick.startswith("composition::"):
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
            if (
                live_pick
                and not live_pick.startswith("custom::")
                and not live_pick.startswith("composition::")
                and live_pick != pick
            ):
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

    # Prefer LAST_CUSTOM over empty My Progression / leftover Composition shells.
    try:
        install_last_custom_into_live_cpl(
            session,
            reset_practice_key_to_original=False,
            prefer_last_custom=True,
        )
    except Exception:
        pass

    live = session.get(CPL_ACTIVE_KEY)
    existing = session.get(CUSTOM_SESSION_KEY)
    existing_title = ""
    if isinstance(existing, dict):
        existing_title = str(existing.get("title") or existing.get("name") or "").strip()
    generic_titles = {
        "",
        "My Progression",
        "My progression",
        "Custom progression",
        "Custom Progression",
    }
    if not cpl_active_is_substantive(live):
        if (
            isinstance(existing, dict)
            and existing_title not in generic_titles
            and (existing.get("sections") or existing.get("pick_key"))
        ):
            return existing
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
        title = str(raw.get("title") or "").strip()
        # Stale My Progression bucket must not outrank LAST_CUSTOM Trial Song.
        if title in {"", "My Progression", "My progression", "Custom progression"}:
            try:
                from songs.music_source import LAST_CUSTOM_STATE_KEY, cpl_active_is_substantive

                snap = session.get(LAST_CUSTOM_STATE_KEY)
                active = snap.get("active") if isinstance(snap, dict) else None
                snap_name = ""
                if isinstance(active, dict):
                    snap_name = str(active.get("name") or snap.get("name") or "").strip()
                if (
                    snap_name
                    and snap_name not in {"My Progression", "My progression"}
                    and cpl_active_is_substantive(active)
                ):
                    return sync_custom_session(session)
            except ImportError:
                pass
        return raw
    return sync_custom_session(session)


def practice_key_inherits_source_mode(practice: str, original: str) -> bool:
    """Shape / catalog Practice Key must keep the song's major/minor family."""
    from music_theory import practice_key_inherits_source_mode as _inherit

    return _inherit(practice, original)


def _catalog_display_key(session: dict[str, Any], catalog: dict[str, Any]) -> str:
    pick = str(catalog.get("pick_key") or "").strip()
    sel = catalog.get("selected_song")
    original = "C"
    if isinstance(sel, dict):
        original = str(catalog.get("original_key") or sel.get("key") or "C").strip() or "C"
    else:
        original = str(catalog.get("original_key") or "C").strip() or "C"
    try:
        from songs.music_source import _catalog_original_key_for_session

        lib_orig = str(_catalog_original_key_for_session(session) or "").strip()
        if lib_orig and lib_orig not in {"C", "C major"}:
            original = lib_orig
    except Exception:
        pass
    saved = ""
    if pick and not pick.startswith("custom::") and not pick.startswith("composition::"):
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = str(get_practice_concert_key(session, pick) or "").strip()
        except ImportError:
            saved = ""
    preview = str(session.get(SBI_PREVIEW_SOURCE_KEY) or "").strip()
    visit = str(session.get("_sbi_custom_visit_pk") or session.get("display_key_sbi_custom") or "").strip()
    if preview == SBI_SONG_SOURCE_ACTIVE or genuine_sbi_active_leave(session):
        if saved and saved != visit:
            return saved
        dk = str(catalog.get("display_key") or "").strip()
        if dk and dk != visit:
            return dk
        if saved:
            return saved
    # Prefer live Practice/Concert Key for the active catalog pick — never catalog.original.
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live and visit and live == visit:
        live = ""
    ctx_pick = str(session.get("active_catalog_pick_key") or "").strip()
    pick_active = bool(pick) and (not ctx_pick or ctx_pick == pick)
    jam_tokens: set[str] = set()
    try:
        from generated_jam_key_context import generated_jam_practice_key_tokens

        jam_tokens = generated_jam_practice_key_tokens(session)
    except ImportError:
        jam_tokens = set()
    user_override = False
    try:
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override

        user_override = bool(pick and catalog_pick_has_user_practice_key_override(session, pick))
    except ImportError:
        user_override = False
    if jam_tokens and live in jam_tokens and not user_override:
        live = ""
    if pick_active and live:
        try:
            from songs.practice_key_state import get_practice_concert_key, sbi_uses_custom_progression_preview

            # SBI Active must not inherit Custom overlay live (Trial E on Shape Bm).
            if not sbi_uses_custom_progression_preview(session):
                sealed = str(session.get("_sbi_custom_sealed_catalog_pk") or "").strip()
                saved = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
                if jam_tokens and sealed in jam_tokens and not user_override:
                    sealed = ""
                if jam_tokens and saved in jam_tokens and not user_override:
                    saved = ""
                catalog_pk = sealed or saved
                if catalog_pk and not practice_key_inherits_source_mode(catalog_pk, original):
                    catalog_pk = ""
                if catalog_pk:
                    return catalog_pk
        except ImportError:
            pass
        if live and not practice_key_inherits_source_mode(live, original):
            live = ""
        if live:
            return live
        return original
    if pick:
        # SBI "Active song" preview can resolve a catalog bucket while global ownership
        # is Custom. Do not let the custom live key overlay that catalog snapshot.
        if pick_active or not ctx_pick.startswith("custom::"):
            try:
                from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key

                dest = overlay_destination_practice_key(session)
                if dest and not (jam_tokens and str(dest).strip() in jam_tokens and not user_override):
                    if practice_key_inherits_source_mode(str(dest), original):
                        return dest
            except ImportError:
                pass
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = get_practice_concert_key(session, pick)
            if saved and not (jam_tokens and str(saved).strip() in jam_tokens and not user_override):
                if practice_key_inherits_source_mode(str(saved), original):
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


def _custom_preview_concert_sections(
    session: dict[str, Any],
    custom: dict[str, Any],
) -> dict[str, list[str]]:
    """SBI Custom card uses concert-pitch sections at the Custom Practice Key."""
    try:
        from workflow_musical_authority import resolve_custom_concert_sections_at_practice_key

        projected = resolve_custom_concert_sections_at_practice_key(session)
        if projected:
            return {str(k): list(v) for k, v in projected.items()}
    except ImportError:
        pass
    base = custom.get("sections") if isinstance(custom, dict) else {}
    if not isinstance(base, dict):
        base = {}
    return {str(k): list(v) for k, v in base.items()}


def _projected_custom_preview_sections(
    session: dict[str, Any],
    fallback: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Alias — SBI Custom chords in the current Custom Practice Key, not Original."""
    return _custom_preview_concert_sections(session, {"sections": fallback or {}})


def resolve_sbi_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Authoritative SBI card — title/key/progression from one source only."""
    source = get_sbi_preview_source(session)
    if source == SBI_SONG_SOURCE_COMPOSITION:
        return resolve_composition_sbi_preview(session)
    if source == "Custom progression":
        try:
            from songs.music_source import install_last_custom_into_live_cpl

            install_last_custom_into_live_cpl(
                session,
                reset_practice_key_to_original=False,
                ignore_new_song_skip=True,
                prefer_last_custom=True,
            )
            try:
                sync_custom_session(session)
            except Exception:
                pass
        except ImportError:
            pass
        custom = get_custom_session(session) or sync_custom_session(session)
        owned_orig = ""
        try:
            from creative_source_ownership_contract import resolve_custom_saved_original_key

            owned_orig = str(resolve_custom_saved_original_key(session) or "").strip()
        except ImportError:
            owned_orig = ""
        if custom:
            preview = {
                "source": source,
                "title": str(custom.get("title") or "Custom progression"),
                "artist": str(custom.get("artist") or "Custom progression"),
                "display_key": resolve_sbi_custom_practice_key(session, custom),
                "original_key": owned_orig or str(custom.get("original_key") or "C"),
                "sections": _custom_preview_concert_sections(session, custom),
                "pick_key": str(custom.get("pick_key") or ""),
            }
            _sbi_gc(
                session,
                "resolve_sbi_preview:custom",
                preview_title=preview["title"],
                preview_orig=preview["original_key"],
                preview_dk=preview["display_key"],
            )
            return preview
        _sbi_gc(session, "resolve_sbi_preview:custom_empty")
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
        pick, _id_sel, identity_orig = resolve_sbi_active_catalog_identity(session)
        if identity_orig:
            original = identity_orig
            if _id_sel.get("title"):
                sel = _id_sel
        elif isinstance(sel, dict):
            original = str(catalog.get("original_key") or sel.get("key") or "C").strip() or "C"
        else:
            original = str(catalog.get("original_key") or "C").strip() or "C"
        if isinstance(sel, dict):
            title = str(sel.get("title") or "Active song").strip()
            artist = str(sel.get("artist") or "").strip()
        else:
            title = "Active song"
            artist = ""
        preview = {
            "source": source,
            "title": title,
            "artist": artist,
            "display_key": _catalog_display_key(session, catalog),
            "original_key": original,
            "sections": _catalog_sections(session, catalog),
            "pick_key": pick or str(catalog.get("pick_key") or ""),
        }
        _sbi_gc(
            session,
            "resolve_sbi_preview:catalog",
            preview_title=title,
            preview_orig=original,
            preview_dk=preview["display_key"],
            preview_pick=preview["pick_key"],
            preview_source=source,
        )
        return preview

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
        if sbi_composition_source_selected(session, ctx=ctx):
            return False
        if src == "custom_progression":
            return True
        if src == "song_improv":
            try:
                if str(resolve_sbi_material_kind(session, ctx=ctx) or "").strip().lower() == "custom":
                    return True
            except Exception:
                pass
            if bound.startswith("custom::"):
                return True
        if session.get("_nested_custom_sbi_backing") and src in {
            "",
            "regular_song",
            "song_improv",
            "custom_progression",
        }:
            return True
        if session.get("_backing_released_specialized_context"):
            return False
        if src in {"mission", "entry_jam"}:
            return False
        return False
    # Creative: SBI tab on Custom progression preview — except Missions / Live Coach /
    # Motif with catalog Global Active, which must use catalog PK. Leftover Custom
    # overlay E is not in Shape's Bm family, so the sidebar widget went blank and
    # embargo gate 6 could not set Em.
    live_radio = str(session.get("improv_song_source") or "").strip()
    preview_now = ""
    try:
        preview_now = stored_sbi_preview_source(session) or get_sbi_preview_source(session)
    except Exception:
        preview_now = get_sbi_preview_source(session)
    if live_radio == SBI_SONG_SOURCE_ACTIVE and preview_now != SBI_SONG_SOURCE_CUSTOM:
        return False
    try:
        stored = stored_sbi_preview_source(session) or get_sbi_preview_source(session)
    except Exception:
        stored = get_sbi_preview_source(session)
    # Remounted Custom radio must not keep Trial overlay PK after a persisted
    # Active leave. A genuine Custom click still owns the sidebar.
    if (
        stored == SBI_SONG_SOURCE_ACTIVE
        and not session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY)
        and not genuine_sbi_custom_click(session)
    ):
        return False
    if get_sbi_preview_source(session) == SBI_SONG_SOURCE_COMPOSITION:
        return False
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if tab in {"Missions", "Live Coach"}:
        try:
            from songs.music_source import custom_progression_is_active

            if not custom_progression_is_active(session):
                return False
        except ImportError:
            pass
    if tab in {"Phrase / Motif", "Motif", "Harmony Map", "Harmony", "Missions"}:
        visit_src = str(session.get("_creative_visit_source") or "").strip()
        if visit_src in {"missions", "sbi_active"}:
            return False
        if get_sbi_preview_source(session) != "Custom progression":
            try:
                from songs.music_source import custom_progression_is_active

                if not custom_progression_is_active(session):
                    return False
            except ImportError:
                pass
    if tab in {
        "Phrase / Motif",
        "Motif",
        "Harmony Map",
        "Harmony",
        "Live Coach",
        "Deep Harmony",
    }:
        entry = str(session.get("improv_entry_mode") or "").strip()
        explicit_sbi_custom = (
            entry == "Song-Based Improvisation"
            and tab in {"", "Song-Based Improvisation", "Entry & Jam"}
            and get_sbi_preview_source(session) == "Custom progression"
        )
        if not explicit_sbi_custom:
            try:
                from songs.music_source import SOURCE_CATALOG, custom_progression_is_active

                ga_catalog = str(session.get("active_music_source") or "").strip() == SOURCE_CATALOG
                if ga_catalog or not custom_progression_is_active(session):
                    return False
            except ImportError:
                return False
    if get_sbi_preview_source(session) == "Custom progression":
        return True
    if src == "custom_progression":
        return True
    if src == "song_improv" and bound.startswith("custom::"):
        return True
    return False


def prepare_sbi_custom_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Creative SBI → Custom progression: sidebar PK uses Trial/Custom sticky + home mode.

    Seals an *existing* catalog sticky (Shape Dm) so leave can restore it, then
    projects Custom sticky/home into ``display_key`` for the sidebar widget.
    Never writes Custom live into the catalog pick — empty catalog sticky stays empty.
    """
    overlay_already = bool(session.get("_sbi_custom_sidebar_overlay"))
    from songs.key_state import PENDING_DISPLAY_KEY, display_key_options

    # Overlay owns the sidebar: live CPL may still be the empty My Progression
    # shell while LAST_CUSTOM is Trial Song D. Install before Original/Practice
    # widgets read identity.
    try:
        from songs.music_source import install_last_custom_into_live_cpl

        install_last_custom_into_live_cpl(
            session,
            reset_practice_key_to_original=False,
            ignore_new_song_skip=True,
            prefer_last_custom=True,
        )
        try:
            sync_custom_session(session)
        except Exception:
            pass
    except ImportError:
        pass

    # Seal catalog sticky once on enter. Never copy Custom live into the catalog
    # slot — including when that slot is empty. Empty Shape sticky is not a
    # license to adopt Trial D / visit E; leave would then heal D major onto
    # Catalog Shape. Only a real existing catalog sticky (Shape Dm) is sealed.
    try:
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_source_pick,
        )

        catalog_pick = str(resolve_practice_source_pick(session) or "").strip()
        if not session.get("_sbi_custom_sidebar_overlay"):
            if catalog_pick and not catalog_pick.startswith("custom::"):
                existing = str(get_practice_concert_key(session, catalog_pick) or "").strip()
                if existing:
                    session["_sbi_custom_sealed_catalog_pk"] = existing
                    session["_sbi_custom_sealed_catalog_pick"] = catalog_pick
            session["_sbi_custom_sidebar_overlay"] = True
    except ImportError:
        catalog_pick = ""

    custom = sync_custom_session(session) or get_custom_session(session) or {}
    # Always prefer saved Custom Original Key (Trial D), never remount C or Catalog G.
    home = str(custom.get("original_key") or "C").strip() or "C"
    try:
        from creative_source_ownership_contract import resolve_custom_saved_original_key

        owned = str(resolve_custom_saved_original_key(session) or "").strip()
        if owned:
            home = owned
    except ImportError:
        pass
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
    if overlay_already:
        sbi_widget = str(session.get("display_key_sbi_custom") or "").strip()
        if sbi_widget:
            session["_sbi_custom_visit_pk"] = sbi_widget
    # CASE A: Custom is also Global Active — current active Custom Practice Key.
    # Do not reset to Original merely because the selector says Custom Progression.
    # Reject leftover Catalog sticky (Perfect G) when Custom home is Trial D.
    if sbi_custom_identity_is_global_active(session):
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if live and catalog_sticky and live == catalog_sticky and live != home:
            live = ""
        case_a = sticky or live or home
        if not session.get("_sbi_custom_case_a_key_bound"):
            selected = case_a
            session["_sbi_custom_case_a_key_bound"] = True
        else:
            selected = str(session.get("_sbi_custom_visit_pk") or "").strip() or case_a
        session["_sbi_custom_visit_pk"] = selected
    else:
        selected = str(session.get("_sbi_custom_visit_pk") or "").strip() or home
        try:
            from songs.practice_key_state import catalog_pick_has_user_practice_key_override

            if (
                sticky
                and pick.startswith("custom::")
                and catalog_pick_has_user_practice_key_override(session, pick)
            ):
                selected = sticky
        except ImportError:
            pass
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
    # Only heal on non-Custom surfaces (Songs / Practice / picker) while Catalog
    # still owns Global Active. When Custom is GA, a leftover SBI catalog seal
    # (Perfect G) must not overwrite Embargo Trial D.
    try:
        from workflow_musical_authority import custom_owns_active_song_material

        if custom_owns_active_song_material(session):
            return ""
    except ImportError:
        pass
    # Do not use custom_sbi_owns_sidebar_practice_key here — SBI preview can remain
    # "Custom progression" after leave, which would skip the heal forever.
    # Heal on Songs/Practice/picker, and on Creative/Backing when SBI Active
    # (not Custom overlay). Skipping Creative left Shape as Trial's C-minor.
    if not sealed or not sealed_pick or page == "custom":
        return ""
    if page in {"creative", "backing"}:
        try:
            if custom_sbi_owns_sidebar_practice_key(session):
                return ""
        except Exception:
            pass
    # Songs/Practice after Set as Active: Custom *is* Global Active. Treating
    # its live PK as catalog-bleed (token in custom_tokens) slammed Perfect G
    # onto Embargo Trial (gate 14). Only heal while Catalog still owns GA.
    try:
        from songs.music_source import custom_progression_is_active

        if custom_progression_is_active(session):
            return ""
    except ImportError:
        pass
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
    last_visit = str(session.get("_sbi_custom_last_visit_pk") or "").strip()
    if last_visit:
        custom_tokens.add(last_visit)
        try:
            from music_theory import coerce_key_to_mode

            custom_tokens.add(coerce_key_to_mode(last_visit, "minor"))
            custom_tokens.add(coerce_key_to_mode(last_visit, "major"))
        except Exception:
            pass
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


def _drop_nested_custom_sbi_visit(session: dict[str, Any]) -> None:
    session.pop("_nested_custom_sbi_backing", None)
    session.pop("_sbi_custom_visit_pk", None)
    session.pop("_sbi_custom_case_a_key_bound", None)
    session.pop("display_key_sbi_custom", None)
    if str(session.get("_backing_explicit_handoff_source") or "").strip() == "song_improv":
        session.pop("_backing_explicit_handoff_source", None)


def clear_sbi_custom_sidebar_overlay_if_needed(session: dict[str, Any]) -> None:
    """Restore catalog sticky into live PK when leaving SBI Custom preview."""
    page = str(session.get("studio_page") or "").strip().lower()
    live_src = str(session.get("improv_song_source") or "").strip()
    if not session.get("_sbi_custom_sidebar_overlay") and not session.get(
        "_custom_page_sidebar_overlay"
    ):
        # Flush Active pops overlay first; nested/handoff must still drop so
        # Pages→Backing from Perfect cannot reopen Trial.
        if session.get("_nested_custom_sbi_backing"):
            if page == "backing":
                return
            if page == "creative" and live_src == SBI_SONG_SOURCE_CUSTOM:
                return
            _drop_nested_custom_sbi_visit(session)
        return
    if session.get("_sbi_custom_sidebar_overlay"):
        # Keep overlay on Custom SBI Backing even if the Creative radio is absent
        # this run (Streamlit remounts improv_song_source as Active).
        owns = custom_sbi_owns_sidebar_practice_key(session)
        if page == "backing" and owns:
            return
        if page == "creative" and owns and live_src != SBI_SONG_SOURCE_ACTIVE:
            return
        session.pop("_sbi_custom_sidebar_overlay", None)
        _drop_nested_custom_sbi_visit(session)
    if session.get("_custom_page_sidebar_overlay"):
        if page == "custom":
            return
        if page == "backing" and custom_sbi_owns_sidebar_practice_key(session):
            return
        try:
            from workflow_musical_authority import custom_owns_active_song_material

            if page in {"picker", "creative", "practice", "songs"} and custom_owns_active_song_material(
                session
            ):
                session.pop("_custom_page_sidebar_overlay", None)
                return
        except ImportError:
            pass
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


def bind_sidebar_practice_key_to_backing_owner(st: Any, session: dict[str, Any]) -> str:
    """Catalog / specialized Backing owner writes the live sidebar Practice Key.

    Custom-page overlay D and leftover jam/catalog stickies must not remain sidebar
    authority after ordinary Catalog Backing (or another backing owner) is current.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return ""
    if session.get("_nested_custom_sbi_backing"):
        try:
            from backing_context import (
                clear_backing_context,
                creative_nested_backing_should_override_catalog,
                ensure_backing_context_from_creative_session,
                get_backing_context,
            )

            ctx_now = get_backing_context(session)
            src_now = str(getattr(ctx_now, "source", "") or "").strip() if ctx_now is not None else ""
            if src_now == "regular_song" and creative_nested_backing_should_override_catalog(session):
                clear_backing_context(session)
                ensure_backing_context_from_creative_session(session)
        except Exception:
            pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
    except Exception:
        ctx = None
    if ctx is None:
        return ""
    src = str(getattr(ctx, "source", "") or "").strip()
    if src == "regular_song" and custom_sbi_owns_sidebar_practice_key(session):
        # Lagged catalog blob must not stamp Perfect G/C over nested Trial D.
        return ""
    rebound = ""
    try:
        from songs.key_state import (
            apply_display_key_owner_transition_if_needed,
            canonical_token_for_owner_transition,
            note_display_key_widget_owner,
        )

        if src != "mission":
            try:
                from backing_practice_key_control import backing_practice_key_widget_id

                # Per-owner Backing widgets are the live control. Do not remount
                # the legacy global display_key selectbox over them.
                _ = backing_practice_key_widget_id(session)
            except ImportError:
                apply_display_key_owner_transition_if_needed(session, st_like=st)
                rebound = canonical_token_for_owner_transition(session)
            else:
                rebound = canonical_token_for_owner_transition(session)
    except Exception:
        rebound = ""
    token = ""
    if src == "regular_song":
        if not custom_sbi_owns_sidebar_practice_key(session):
            session.pop("_custom_page_sidebar_overlay", None)
            session.pop("_sbi_custom_sidebar_overlay", None)
            session.pop("_sbi_custom_visit_pk", None)
            session.pop("display_key_sbi_custom", None)
        token = str(
            getattr(ctx, "display_key", "")
            or getattr(ctx, "concert_key", "")
            or getattr(ctx, "key", "")
            or ""
        ).strip()
        leaving = str(session.get("_specialized_practice_token_leaving") or "").strip()
        sealed = str(session.get("_specialized_leave_catalog_pk") or "").strip()
        if rebound:
            token = rebound
        elif leaving and token == leaving:
            token = sealed
        if not token:
            try:
                from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

                pick = str(
                    session.get("_specialized_leave_catalog_pick")
                    or resolve_practice_source_pick(session)
                    or ""
                ).strip()
                if pick and not pick.startswith("custom::"):
                    token = str(get_practice_concert_key(session, pick) or "").strip()
                if leaving and token == leaving:
                    token = sealed
            except Exception:
                token = ""
    elif src == "entry_jam":
        token = ""
        try:
            from backing_context import build_entry_jam_context

            live_ctx = build_entry_jam_context(session)
            token = str(
                getattr(live_ctx, "display_key", "")
                or getattr(live_ctx, "concert_key", "")
                or getattr(live_ctx, "key", "")
                or ""
            ).strip()
        except Exception:
            token = ""
        try:
            from creative_key_sync import creative_entry_concert_key

            entry = str(
                getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or ""
            ).strip()
            widget = str(creative_entry_concert_key(session) or "").strip()
            # Entry Style Jam: leftover Jam Generator key/snapshot must not keep
            # the sidebar on Eb after the user set Style Practice Key to F.
            if widget and "Style Jam" in entry:
                token = widget
        except Exception:
            pass
        if not token:
            try:
                from workflow_key_identity import resolve_practice_key_identity_for_ui

                ident = resolve_practice_key_identity_for_ui(session)
                if ident is not None and str(ident.practice_key_token or "").strip():
                    token = str(ident.practice_key_token).strip()
            except Exception:
                token = ""
        if not token:
            try:
                from backing_context import get_backing_context
                from creative_key_sync import creative_entry_concert_key

                ctx_entry = str(getattr(ctx, "entry_mode", "") or "").strip()
                entry = ctx_entry or str(session.get("improv_entry_mode") or "").strip()
                token = str(creative_entry_concert_key(session) or "").strip()
                if not token:
                    if "Style Jam" in entry:
                        token = str(session.get("improv_style_key") or "").strip()
                    else:
                        token = str(session.get("improv_jam_key") or "").strip()
            except Exception:
                token = str(
                    session.get("improv_style_key")
                    or session.get("improv_jam_key")
                    or ""
                ).strip()
        if not token:
            try:
                from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

                raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
                if isinstance(raw, dict):
                    token = str(raw.get("practice_key_token") or "").strip()
            except Exception:
                token = ""
        token = token or str(
            getattr(ctx, "display_key", "")
            or getattr(ctx, "concert_key", "")
            or getattr(ctx, "key", "")
            or ""
        ).strip()
    elif src == "mission":
        token = str(
            session.get("improv_mission_concert_key")
            or session.get("display_key")
            or session.get("concert_key")
            or getattr(ctx, "display_key", "")
            or getattr(ctx, "concert_key", "")
            or getattr(ctx, "key", "")
            or ""
        ).strip()
        rebound = ""
    else:
        return ""
    if rebound:
        try:
            from songs.key_state import owner_transition_record, resolve_display_key_widget_owner_id

            rec = owner_transition_record(session)
            current = resolve_display_key_widget_owner_id(session)
            style_jam_live = False
            if src == "entry_jam":
                entry_now = str(
                    getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or ""
                ).strip()
                style_jam_live = "Style Jam" in entry_now
            if rec and str(rec.get("to") or "").strip() == current and not style_jam_live:
                token = rebound
        except Exception:
            if src == "regular_song":
                token = rebound
    if not token:
        return ""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if src == "regular_song" or src == "entry_jam" or live != token:
        try:
            from h3_live_key_trace import emit_display_key_write

            emit_display_key_write(
                session, token, source=f"bind_sidebar_backing_owner_{src}"
            )
        except Exception:
            pass
        session["display_key"] = token
        session["concert_key"] = token
        try:
            from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget
            from session_widget_safe import widgets_likely_instantiated

            session[PENDING_DISPLAY_KEY] = token
            if st is not None and not widgets_likely_instantiated(session):
                _apply_display_key_before_widget(
                    st, token, source=f"bind_sidebar_backing_owner_{src}"
                )
        except Exception:
            session["_pending_display_key"] = token
    try:
        from h3_live_key_trace import emit

        emit(session, "bind_sidebar_done", bind_token=token, bind_src=src)
    except Exception:
        pass
    try:
        from songs.key_state import note_display_key_widget_owner

        note_display_key_widget_owner(session)
    except Exception:
        pass
    return token


def sync_specialized_leave_catalog_widget(
    session: dict[str, Any],
    *,
    widget_key: str = "display_key",
    allow_clear: bool = False,
) -> None:
    """Keep Catalog PK widget from inheriting the leftover Jam/Mission token.

    Do not clear the owner-transition / leave markers until the widget actually
    returns the new owner's canonical key (after selectbox).

    Mission Backing uses display_key_mission_backing as a mirror of
    improv_mission_concert_key. Catalog leave-sync must not write that widget.
    """
    try:
        from creative_key_sync import (
            MISSION_BACKING_PRACTICE_KEY_WIDGET,
            mission_backing_owns_left_panel_key,
        )

        if str(widget_key or "") == MISSION_BACKING_PRACTICE_KEY_WIDGET:
            return
        if mission_backing_owns_left_panel_key(session):
            return
        try:
            from backing_practice_key_control import WIDGET_STYLE_JAM

            if str(widget_key or "") == WIDGET_STYLE_JAM:
                return
            from backing_practice_key_control import WIDGET_COMPOSITION

            if str(widget_key or "") == WIDGET_COMPOSITION:
                return
        except ImportError:
            if str(widget_key or "") == "display_key_style_jam_backing":
                return
            if str(widget_key or "") == "display_key_composition_backing":
                return
    except Exception:
        if str(widget_key or "").startswith("display_key_mission_backing"):
            return
    try:
        from songs.key_state import (
            apply_display_key_owner_transition_if_needed,
            canonical_token_for_owner_transition,
            clear_display_key_owner_transition,
            stale_widget_token_for_owner_transition,
        )

        apply_display_key_owner_transition_if_needed(session)
        rebound = canonical_token_for_owner_transition(session)
        stale = stale_widget_token_for_owner_transition(session)
    except Exception:
        rebound = ""
        stale = str(session.get("_specialized_practice_token_leaving") or "").strip()
    sealed = str(session.get("_specialized_leave_catalog_pk") or rebound or "").strip()
    leaving = str(session.get("_specialized_practice_token_leaving") or stale or "").strip()
    if not sealed and not rebound:
        return
    target = rebound or sealed
    live = str(session.get(widget_key) or session.get("display_key") or "").strip()
    if (leaving and live == leaving) or (stale and live == stale) or (
        target and live and live != target and (leaving or stale or rebound)
    ):
        session[widget_key] = target
        session["display_key"] = target
        session["concert_key"] = target
        session["_pending_display_key"] = target
        return
    if allow_clear and target and live == target:
        try:
            clear_display_key_owner_transition(session)
        except Exception:
            session.pop("_specialized_practice_token_leaving", None)
            session.pop("_specialized_leave_catalog_pk", None)
            session.pop("_specialized_leave_catalog_pick", None)


__all__ = [
    "CATALOG_SESSION_KEY",
    "COMPOSITION_SBI_UNAVAILABLE_MESSAGE",
    "COMPOSITION_SBI_UNAVAILABLE_TITLE",
    "CUSTOM_SESSION_KEY",
    "IMPROV_SONG_SOURCES",
    "SBI_MATERIAL_TYPE_LABELS",
    "SBI_PREVIEW_SOURCE_KEY",
    "SBI_SONG_SOURCE_ACTIVE",
    "SBI_SONG_SOURCE_COMPOSITION",
    "SBI_SONG_SOURCE_CUSTOM",
    "SBI_WORKFLOW_LABEL",
    "clear_sbi_custom_sidebar_overlay_if_needed",
    "composition_sbi_source_available",
    "custom_sbi_owns_sidebar_practice_key",
    "format_sbi_backing_blue_card_subtitle",
    "get_catalog_session",
    "get_custom_session",
    "EXPLICIT_SBI_SOURCE_CLICK_KEY",
    "RESTORE_SBI_CUSTOM_SOURCE_KEY",
    "SBI_CUSTOM_IDENTITY_PICK_KEY",
    "SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY",
    "SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY",
    "SBI_RADIO_ON_CHANGE_THIS_RUN_KEY",
    "SBI_ACTIVE_LEAVE_INTENT_KEY",
    "SBI_ACTIVE_LEAVE_RESTORE_RERUN_KEY",
    "adopt_restore_sbi_custom_stamp",
    "clear_restore_sbi_custom_source",
    "consume_sbi_active_leave_intent",
    "genuine_sbi_active_leave",
    "genuine_sbi_custom_click",
    "restore_sbi_active_catalog_identity_before_widgets",
    "sbi_active_leave_intent_pending",
    "stamp_sbi_active_leave_intent",
    "persist_sbi_active_leave_authority",
    "apply_sbi_radio_live_against_restore_stamp",
    "seed_sbi_custom_radio_before_render",
    "stored_sbi_preview_source",
    "persist_sbi_custom_practice_key_edit",
    "bind_sbi_preview_to_active_after_explicit_catalog",
    "bind_sidebar_practice_key_to_backing_owner",
    "clear_sbi_follow_active_after_explicit_catalog",
    "note_explicit_sbi_source_selection",
    "get_sbi_preview_source",
    "global_active_is_custom",
    "sbi_must_follow_global_active",
    "heal_sealed_catalog_sidebar_if_needed",
    "prepare_sbi_custom_sidebar_display_key",
    "resolve_sbi_custom_practice_key",
    "sbi_custom_identity_is_global_active",
    "resolve_composition_sbi_preview",
    "resolve_improv_song_source_for_handoff",
    "resolve_sbi_material_kind",
    "resolve_sbi_preview",
    "sbi_composition_source_selected",
    "sbi_source_type_label",
    "set_sbi_preview_source",
    "stamp_sbi_custom_identity_pick",
    "install_sbi_custom_identity_before_widgets",
    "sync_catalog_session",
    "sync_custom_session",
]
