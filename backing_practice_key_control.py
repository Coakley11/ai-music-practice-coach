"""Backing Practice Key control — one widget identity per Backing owner.

The Streamlit selectbox key is the view of that owner's canonical concert
Practice Key. A leftover global ``display_key`` value from another owner must
not remount over the current owner.
"""

from __future__ import annotations

from typing import Any

# Stable Streamlit keys — never a per-rerun nonce.
WIDGET_CATALOG = "display_key_catalog_backing"
WIDGET_CUSTOM = "display_key_custom_backing"
WIDGET_SBI_ACTIVE = "display_key_sbi_active_backing"
WIDGET_SBI_CUSTOM = "display_key_sbi_custom"
WIDGET_STYLE_JAM = "display_key_style_jam_backing"
WIDGET_JAM_GENERATOR = "display_key_jam_generator_backing"
WIDGET_MISSION = "display_key_mission_backing"
WIDGET_COMPOSITION = "display_key_composition_backing"

OWNER_CATALOG = "catalog"
OWNER_CUSTOM = "custom"
OWNER_SBI_ACTIVE = "sbi_active"
OWNER_SBI_CUSTOM = "sbi_custom"
OWNER_STYLE_JAM = "style_jam"
OWNER_JAM_GENERATOR = "jam_generator"
OWNER_MISSION = "mission"
OWNER_COMPOSITION = "composition"

BACKING_PK_CONTROL_OWNER_KEY = "_backing_pk_control_owner"
STYLE_JAM_STICKY_SOURCE = "creative::entry_style_jam"
# Style Jam widgets remount to these Streamlit defaults. They are not user intent
# when a live F / sticky F / creative-session F is already sealed for this visit.
STYLE_JAM_REMOUNT_DEFAULTS = frozenset({"", "G", "Eb", "G major", "Eb major"})
# Jam Session Generator selectboxes remount to C. That is not user intent when
# pending/commit/sticky already sealed Db (or any non-C jam key) for this visit.
JAM_GENERATOR_REMOUNT_DEFAULTS = frozenset({"", "C", "C major"})


def _ctx_concert_if_owner(session: dict[str, Any], owner: str) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
    except Exception:
        return ""
    if ctx is None:
        return ""
    src = str(getattr(ctx, "source", "") or "").strip()
    entry = str(getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or "").strip()
    if owner == OWNER_CATALOG and src == "regular_song":
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    if owner == OWNER_CUSTOM and src == "custom_progression":
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    if owner == OWNER_MISSION and src == "mission":
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    if owner == OWNER_COMPOSITION and src == "composition_song":
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "display_key", "") or "").strip()
    if owner == OWNER_STYLE_JAM and src == "entry_jam" and "Style Jam" in entry:
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    if owner == OWNER_JAM_GENERATOR and src == "entry_jam" and "Style Jam" not in entry:
        return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    if owner in {OWNER_SBI_ACTIVE, OWNER_SBI_CUSTOM} and src == "song_improv":
        try:
            from source_session_state import get_sbi_preview_source

            preview = get_sbi_preview_source(session)
        except ImportError:
            preview = str(session.get("sbi_preview_source") or "").strip()
        if owner == OWNER_SBI_CUSTOM and preview == "Custom progression":
            return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
        if owner == OWNER_SBI_ACTIVE and preview != "Custom progression":
            return str(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "").strip()
    return ""

WIDGET_BY_OWNER: dict[str, str] = {
    OWNER_CATALOG: WIDGET_CATALOG,
    OWNER_CUSTOM: WIDGET_CUSTOM,
    OWNER_SBI_ACTIVE: WIDGET_SBI_ACTIVE,
    OWNER_SBI_CUSTOM: WIDGET_SBI_CUSTOM,
    OWNER_STYLE_JAM: WIDGET_STYLE_JAM,
    OWNER_JAM_GENERATOR: WIDGET_JAM_GENERATOR,
    OWNER_MISSION: WIDGET_MISSION,
    OWNER_COMPOSITION: WIDGET_COMPOSITION,
}

PERSISTED_WIDGET_KEYS: tuple[str, ...] = tuple(WIDGET_BY_OWNER.values())


def resolve_backing_pk_control_owner(session: dict[str, Any]) -> str:
    """Current Backing Practice Key owner (widget identity)."""
    page = str(session.get("studio_page") or "").strip().lower()
    src = ""
    try:
        from creative_key_sync import live_backing_source

        src = str(live_backing_source(session) or "").strip()
    except ImportError:
        src = ""
    if page == "backing":
        if src == "mission":
            return OWNER_MISSION
        if src == "custom_progression":
            return OWNER_CUSTOM
        if src == "entry_jam":
            entry = str(session.get("improv_entry_mode") or "").strip()
            try:
                from backing_context import get_backing_context

                ctx = get_backing_context(session)
                if ctx is not None:
                    entry = str(getattr(ctx, "entry_mode", "") or entry).strip()
            except Exception:
                pass
            if "Style Jam" in entry:
                return OWNER_STYLE_JAM
            return OWNER_JAM_GENERATOR
        if src == "song_improv":
            try:
                from source_session_state import get_sbi_preview_source

                if get_sbi_preview_source(session) == "Custom progression":
                    return OWNER_SBI_CUSTOM
            except ImportError:
                pass
            return OWNER_SBI_ACTIVE
        if src == "composition_song":
            return OWNER_COMPOSITION
        try:
            from songs.music_source import composition_song_is_active

            if composition_song_is_active(session):
                return OWNER_COMPOSITION
        except ImportError:
            pass
        if src in {"", "regular_song"} and (
            session.get("_nested_custom_sbi_backing")
            or session.get("_sbi_custom_sidebar_overlay")
        ):
            return OWNER_SBI_CUSTOM
        return OWNER_CATALOG
    if page == "custom":
        return OWNER_CUSTOM
    return OWNER_CATALOG


def backing_practice_key_widget_id(session: dict[str, Any]) -> str:
    return WIDGET_BY_OWNER[resolve_backing_pk_control_owner(session)]


def _token_is_style_jam_remount(token: str) -> bool:
    return str(token or "").strip() in STYLE_JAM_REMOUNT_DEFAULTS


def _catalog_concert_key_token(session: dict[str, Any]) -> str:
    """Catalog song Practice Key — not a Style Jam authority."""
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick and not pick.startswith("creative::") and not pick.startswith("custom::"):
            tok = str(get_practice_concert_key(session, pick) or "").strip()
            if tok:
                return tok
    except ImportError:
        pass
    cs = session.get("catalog_session")
    if isinstance(cs, dict):
        tok = str(cs.get("display_key") or "").strip()
        if tok:
            return tok
    return ""


def style_jam_authoritative_concert_key(session: dict[str, Any]) -> str:
    """Live Style Jam concert key. Leftover Generator Eb / generate-default G lose.

    Live walker split: banner/card F, ``improv_style_key`` F, sticky F, while
    ``backing_context`` / artifact snapshot stay G and ``improv_jam_key`` is Eb.
    Do not heal later from G — this token is the first authority.
    """
    live = str(session.get("improv_style_key") or "").strip()
    widget = str(session.get(WIDGET_STYLE_JAM) or "").strip()
    sticky = ""
    pks = session.get("practice_key_by_source")
    if isinstance(pks, dict):
        sticky = str(pks.get(STYLE_JAM_STICKY_SOURCE) or "").strip()
    creative = ""
    cs = session.get("creative_session")
    if isinstance(cs, dict):
        creative = str(cs.get("concert_key") or cs.get("display_key") or "").strip()
    ctx_tok = _ctx_concert_if_owner(session, OWNER_STYLE_JAM)
    pending = str(session.get("_pending_display_key") or "").strip()
    catalog = _catalog_concert_key_token(session)

    def _usable(tok: str) -> bool:
        if not tok or _token_is_style_jam_remount(tok):
            return False
        # Songs seed Cm must not steal Style Jam F through the jam sticky map.
        if catalog and tok == catalog:
            others = {live, widget, sticky, creative, pending, ctx_tok}
            if any(
                other and other != catalog and not _token_is_style_jam_remount(other)
                for other in others
            ):
                return False
        return True

    for tok in (live, pending, widget, sticky, creative, ctx_tok):
        if _usable(tok):
            return tok
    return live or pending or widget or sticky or creative or ctx_tok


def jam_generator_authoritative_concert_key(session: dict[str, Any]) -> str:
    """Live Jam Generator concert key. Mounted C / sealed ctx / Perfect G lose.

    FIRST incorrect field after a C→Db sidebar edit: ``improv_jam_key`` stays C
    while ``display_key`` / pending are Db. Guitar, card, and playback must
    follow this token — never leftover Catalog G or a remounted C widget.
    After refresh, prefer jam sticky / creative_session over Perfect catalog G.
    """
    pending = str(session.get("_pending_improv_jam_key") or "").strip()
    commit = str(session.get("_pk_user_commit_token") or "").strip()
    live = str(session.get("improv_jam_key") or "").strip()
    widget = str(session.get(WIDGET_JAM_GENERATOR) or "").strip()
    display = str(
        session.get("_pending_display_key") or session.get("display_key") or ""
    ).strip()
    ctx_tok = _ctx_concert_if_owner(session, OWNER_JAM_GENERATOR)
    catalog = _catalog_concert_key_token(session)
    generated = ""
    generated_owner = ""
    try:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

        raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
        if isinstance(raw, dict):
            generated = str(raw.get("practice_key_token") or "").strip()
            generated_owner = str(raw.get("key_owner") or "").strip()
        else:
            generated_owner = ""
    except Exception:
        generated = ""
        generated_owner = ""
    if generated_owner == "style_jam":
        generated = ""
    sticky = ""
    creative = ""
    try:
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, get_practice_concert_key

        sticky = str(get_practice_concert_key(session, CREATIVE_JAM_SESSION_PICK) or "").strip()
    except Exception:
        sticky = ""
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None and sess.tool_type == "jam_session_generator":
            creative = str(sess.concert_key or sess.display_key or "").strip()
    except Exception:
        creative = ""
    jam_blob = session.get("improv_jam_session")
    jam_key = ""
    if isinstance(jam_blob, dict):
        jam_key = str(jam_blob.get("key") or "").strip()

    remount = set(JAM_GENERATOR_REMOUNT_DEFAULTS)
    style_leftover = set(STYLE_JAM_REMOUNT_DEFAULTS) - remount
    owner_sealed = {tok for tok in (pending, commit, sticky, creative) if tok}

    def _is_style_leftover(tok: str) -> bool:
        """Style Jam remount Eb/G is not Jam Generator canonical.

        Sticky/creative/pending/commit may seal the same pitch later as a real edit.
        """
        if tok not in style_leftover:
            return False
        return tok not in owner_sealed

    def _usable(tok: str) -> bool:
        if not tok:
            return False
        if _is_style_leftover(tok):
            return False
        if catalog and tok == catalog:
            jam_explicit = {t for t in (pending, commit, sticky, creative, jam_key) if t}
            if tok not in jam_explicit:
                return False
        return True

    # Owner-sealed Jam Generator state first. Do not let leftover Style Jam
    # generated/blob Eb sort ahead of sticky/creative Db.
    jam_owned = (pending, sticky, creative, jam_key, generated)
    live_owned = (live, widget)

    for tok in jam_owned:
        if _usable(tok) and tok not in remount:
            return tok
    for tok in jam_owned:
        if tok in {"C", "C major"} and _usable(tok):
            return tok
    for tok in live_owned:
        if _usable(tok) and tok not in remount:
            others = {t for t in jam_owned if t}
            if others and tok not in others:
                continue
            return tok
    for tok in live_owned:
        if tok in {"C", "C major"} and _usable(tok):
            return tok
    jam_owns = False
    try:
        from creative_key_sync import jam_owns_left_panel_key

        jam_owns = bool(jam_owns_left_panel_key(session))
    except Exception:
        jam_owns = False
    if jam_owns:
        return "C"
    if _usable(commit) and commit not in remount:
        jam_evidence = {t for t in jam_owned + live_owned if t}
        if commit in jam_evidence:
            return commit
    for tok in (display, ctx_tok, commit):
        if _usable(tok) and tok not in remount:
            return tok
    for tok in jam_owned + live_owned + (ctx_tok, display, pending, commit, generated):
        if tok and _usable(tok):
            return tok
    return ""


def canonical_concert_key_for_owner(session: dict[str, Any], owner: str = "") -> str:
    """Authoritative concert Practice Key for one Backing owner."""
    kind = str(owner or resolve_backing_pk_control_owner(session) or "").strip()
    if kind == OWNER_MISSION:
        tok = str(session.get("improv_mission_concert_key") or "").strip()
        if tok:
            return tok
    if kind == OWNER_STYLE_JAM:
        tok = style_jam_authoritative_concert_key(session)
        if tok:
            return tok
    if kind == OWNER_JAM_GENERATOR:
        tok = jam_generator_authoritative_concert_key(session)
        if tok:
            return tok
    if kind == OWNER_CUSTOM:
        try:
            from source_session_state import resolve_sbi_custom_practice_key

            tok = str(resolve_sbi_custom_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
        ctx_tok = _ctx_concert_if_owner(session, kind)
        if ctx_tok:
            return ctx_tok
        return str(session.get("display_key") or session.get("concert_key") or "").strip()
    if kind == OWNER_SBI_CUSTOM:
        try:
            from source_session_state import resolve_sbi_custom_practice_key

            tok = str(resolve_sbi_custom_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
        tok = str(session.get("_sbi_custom_visit_pk") or "").strip()
        if tok:
            return tok
        ctx_tok = _ctx_concert_if_owner(session, kind)
        if ctx_tok:
            return ctx_tok
    if kind == OWNER_COMPOSITION:
        try:
            from composition_songs_bridge import resolve_composition_canonical_keys

            _orig, practice = resolve_composition_canonical_keys(session)
            tok = str(practice or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
        ctx_tok = _ctx_concert_if_owner(session, kind)
        if ctx_tok:
            return ctx_tok
        return str(session.get("display_key") or session.get("concert_key") or "").strip()
    if kind in {OWNER_CATALOG, OWNER_SBI_ACTIVE}:
        try:
            from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

            pick = str(resolve_practice_source_pick(session) or "").strip()
            if pick and not str(pick).startswith("custom::"):
                tok = str(get_practice_concert_key(session, pick) or "").strip()
                if tok:
                    return tok
        except ImportError:
            pass
        widget = WIDGET_BY_OWNER.get(kind, "")
        if widget:
            tok = str(session.get(widget) or "").strip()
            if tok:
                return tok
        ctx_tok = _ctx_concert_if_owner(session, kind)
        if ctx_tok:
            return ctx_tok
        return str(session.get("display_key") or session.get("concert_key") or "").strip()
    widget = WIDGET_BY_OWNER.get(kind, "")
    if widget:
        tok = str(session.get(widget) or "").strip()
        if tok:
            return tok
    ctx_tok = _ctx_concert_if_owner(session, kind)
    if ctx_tok:
        return ctx_tok
    return str(session.get("display_key") or session.get("concert_key") or "").strip()


def seed_backing_practice_key_widget(
    session: dict[str, Any],
    *,
    options: list[str] | None = None,
) -> str:
    """Initialize the current owner's widget from canonical. Never copy a foreign widget."""
    owner = resolve_backing_pk_control_owner(session)
    widget = WIDGET_BY_OWNER[owner]
    canonical = canonical_concert_key_for_owner(session, owner)
    prev = str(session.get(BACKING_PK_CONTROL_OWNER_KEY) or "").strip()
    switched = bool(prev and prev != owner)
    session[BACKING_PK_CONTROL_OWNER_KEY] = owner
    live_widget = str(session.get(widget) or "").strip()
    if options is not None:
        if canonical and canonical not in options:
            options.insert(0, canonical)
        if live_widget and live_widget not in options:
            live_widget = ""
    want = canonical
    remount_defaults = set(STYLE_JAM_REMOUNT_DEFAULTS)
    if owner == OWNER_JAM_GENERATOR:
        remount_defaults = set(JAM_GENERATOR_REMOUNT_DEFAULTS)
    if owner in {OWNER_STYLE_JAM, OWNER_JAM_GENERATOR}:
        if canonical and (not live_widget or live_widget in remount_defaults) and live_widget != canonical:
            want = canonical
            live_widget = canonical
            # Streamlit ignores later assignment once this widget has remounted
            # to Eb/G/C. Drop the remounted value before the selectbox instantiates.
            session.pop(widget, None)
        if owner == OWNER_STYLE_JAM:
            session.pop(WIDGET_JAM_GENERATOR, None)
            leftover_jam = str(session.get("improv_jam_key") or "").strip()
            if (
                leftover_jam in STYLE_JAM_REMOUNT_DEFAULTS
                and canonical
                and leftover_jam != canonical
            ):
                # Streamlit keeps displaying leftover Generator Eb even after
                # session_state already says F. Pop so the selectbox remounts.
                session.pop(widget, None)
                live_widget = canonical
                want = canonical
        if owner == OWNER_JAM_GENERATOR:
            leftover_jam = str(session.get("improv_jam_key") or "").strip()
            if (
                leftover_jam in JAM_GENERATOR_REMOUNT_DEFAULTS
                and canonical
                and leftover_jam != canonical
            ):
                session.pop(widget, None)
                session.pop("improv_jam_key", None)
                live_widget = canonical
                want = canonical
    if owner == OWNER_COMPOSITION and canonical:
        # Leftover Original G on the composition Backing widget must not outrank
        # the saved Composition Practice Key (canonical_display_key Db).
        want = canonical
        if live_widget and live_widget != canonical:
            session.pop(widget, None)
            live_widget = canonical
    elif switched or not live_widget:
        want = canonical or live_widget
    elif live_widget and canonical and live_widget != canonical:
        # Widget is this owner's stored value; canonical wins after cycle/commit.
        commit = str(session.get("_pk_user_commit_token") or "").strip()
        if owner == OWNER_STYLE_JAM and live_widget in remount_defaults:
            want = canonical
        elif owner == OWNER_JAM_GENERATOR and live_widget in remount_defaults:
            want = canonical
        elif commit == canonical:
            want = canonical
        elif (
            owner == OWNER_JAM_GENERATOR
            and str(session.get("_pending_improv_jam_key") or "").strip() == canonical
        ):
            want = canonical
        else:
            want = live_widget
    if want and options is not None and want not in options:
        options.insert(0, want)
    if want:
        session[widget] = want
        session["concert_key"] = want
        if owner == OWNER_COMPOSITION:
            session["_pending_display_key"] = want
            try:
                from composition_songs_bridge import hydrate_composition_practice_key

                hydrate_composition_practice_key(session, want)
            except ImportError:
                if not session.get("_streamlit_widgets_locked_this_run"):
                    session["display_key"] = want
        else:
            session["display_key"] = want
        if owner == OWNER_STYLE_JAM:
            session["_pending_display_key"] = want
        # Do not overwrite a cycle/commit pending token. The selectbox applies it next.
    return want


def commit_backing_practice_key(session: dict[str, Any], token: str) -> str:
    """Write the current owner's canonical concert key and its widget together."""
    new = str(token or "").strip()
    if not new:
        return ""
    owner = resolve_backing_pk_control_owner(session)
    widget = WIDGET_BY_OWNER[owner]
    session[widget] = new
    session[BACKING_PK_CONTROL_OWNER_KEY] = owner
    session["display_key"] = new
    session["concert_key"] = new
    session["_pending_display_key"] = new
    session["_pk_user_commit_token"] = new
    session["display_key_change_source"] = "backing_pk_control"
    try:
        import time as _time

        session["_pk_user_commit_at"] = _time.time()
    except Exception:
        pass
    if owner == OWNER_MISSION:
        try:
            from creative_key_sync import apply_specialized_mission_practice_key

            apply_specialized_mission_practice_key(session, new)
        except ImportError:
            session["improv_mission_concert_key"] = new
        session[WIDGET_MISSION] = new
        return new
    if owner in {OWNER_STYLE_JAM, OWNER_JAM_GENERATOR}:
        if owner == OWNER_STYLE_JAM:
            if not session.get("_improv_style_key_mounted_this_run"):
                session["improv_style_key"] = new
        elif not session.get("_improv_jam_key_mounted_this_run"):
            session["improv_jam_key"] = new
        try:
            from creative_key_sync import apply_specialized_jam_practice_key

            applied = str(apply_specialized_jam_practice_key(session, new) or "").strip()
            if applied:
                session[widget] = applied
                return applied
        except ImportError:
            pass
        return new
    if owner in {OWNER_CUSTOM, OWNER_SBI_CUSTOM}:
        if owner == OWNER_SBI_CUSTOM:
            session["_sbi_custom_visit_pk"] = new
        try:
            from custom_progression_lab import cpl_active_from_session, sync_custom_workspace_practice_key

            sync_custom_workspace_practice_key(
                session,
                practice_key=new,
                active=cpl_active_from_session(session),
                source="backing_pk_control",
            )
        except ImportError:
            pass
        return new
    if owner == OWNER_COMPOSITION:
        try:
            from composition_songs_bridge import commit_composition_owned_practice_key

            committed = str(commit_composition_owned_practice_key(session, new) or "").strip()
            if committed:
                session[widget] = committed
                session["display_key"] = committed
                session["concert_key"] = committed
                return committed
        except ImportError:
            pass
        return new
    try:
        from songs.practice_key_state import resolve_practice_source_pick, set_practice_concert_key

        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick and not str(pick).startswith("creative::"):
            set_practice_concert_key(session, new, pick_key=pick, allow_restore_original=True)
            # Seal live Practice onto BackingContext immediately so the blue card
            # cannot keep showing Original (Bm) after sidebar commits C#m.
            try:
                from backing_context import get_backing_context, set_backing_context

                ctx = get_backing_context(session)
                if ctx is not None and str(getattr(ctx, "source", "") or "") == "regular_song":
                    bound = str(
                        getattr(ctx, "bound_pick_key", "")
                        or getattr(ctx, "active_song_id", "")
                        or ""
                    ).strip()
                    if not bound or bound == pick:
                        ctx.concert_key = new
                        ctx.display_key = new
                        set_backing_context(session, ctx)
            except Exception:
                pass
    except ImportError:
        pass
    return new


def owner_widget_value(session: dict[str, Any], owner: str) -> str:
    widget = WIDGET_BY_OWNER.get(owner, "")
    if not widget:
        return ""
    return str(session.get(widget) or "").strip()


def backing_bpm_control_owner(session: dict[str, Any]) -> str:
    """BPM slider identity follows the same Backing owner as Practice Key."""
    return resolve_backing_pk_control_owner(session)
