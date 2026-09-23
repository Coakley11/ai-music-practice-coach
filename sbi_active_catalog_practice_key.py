"""Catalog SBI Active Practice Key — pre-widget restore, never mutate mounted display_key."""

from __future__ import annotations

from typing import Any

from songs.key_state import PENDING_DISPLAY_KEY, PENDING_DISPLAY_KEY_PICK, PENDING_DISPLAY_KEY_SOURCE

SBI_ACTIVE_PK_RESTORE_SOURCE = "sbi_active_catalog"
SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY = "_sbi_active_pk_restore_rerun_fp"

_SBI_CATALOG_SURFACES = {
    "Phrase / Motif",
    "Motif",
    "Live Coach",
    "Harmony Map",
    "Harmony",
    "Deep Harmony",
    "Missions",
    "Entry & Jam",
}


def _practice_keys_equal(a: str, b: str) -> bool:
    left = str(a or "").strip()
    right = str(b or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    try:
        from creative_key_sync import _practice_keys_semantically_equal

        return bool(_practice_keys_semantically_equal(left, right))
    except ImportError:
        return left.replace(" ", "").lower() == right.replace(" ", "").lower()


def sbi_active_catalog_owns_practice_key(session: dict[str, Any]) -> bool:
    """True when Catalog SBI Active owns the live Practice Key (not Custom/Jam/Mission)."""
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        if custom_sbi_owns_sidebar_practice_key(session):
            return False
    except ImportError:
        pass
    try:
        from creative_key_sync import mission_owns_left_panel_key

        if mission_owns_left_panel_key(session):
            return False
    except ImportError:
        pass

    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    jam_ui = tab in {"Entry & Jam", ""} and entry in {
        "Jam Session Generator",
        "Style Jam Mode",
    }
    if jam_ui:
        return False

    src = ""
    try:
        from source_session_state import get_sbi_preview_source

        src = str(get_sbi_preview_source(session) or "").strip()
    except ImportError:
        src = str(session.get("sbi_preview_source") or session.get("improv_song_source") or "").strip()
    if src in {"Custom progression", "Composition"}:
        return False
    if src not in {"", "Active song"}:
        return False

    pick = ""
    try:
        from songs.practice_key_state import resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or "").strip()
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
    if pick.startswith("custom::"):
        return False

    page = str(session.get("studio_page") or "").strip().lower()
    if page == "creative":
        return True
    if page == "backing":
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            src_ctx = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
            if src_ctx in {"entry_jam", "mission", "custom_progression", "composition_song"}:
                return False
            if src_ctx in {"song_improv", "regular_song", ""}:
                return True
        except ImportError:
            return True
    return False


def sbi_active_user_commit_outranks(session: dict[str, Any], *, pick: str = "") -> str:
    """Recent sidebar commit for this exact Catalog pick, else empty."""
    live_pick = str(pick or "").strip()
    if not live_pick:
        try:
            from songs.practice_key_state import resolve_practice_source_pick

            live_pick = str(resolve_practice_source_pick(session) or "").strip()
        except ImportError:
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override, get_practice_concert_key

        if catalog_pick_has_user_practice_key_override(session, live_pick):
            saved = str(get_practice_concert_key(session, live_pick) or "").strip()
            if saved:
                return saved
    except ImportError:
        pass
    commit = str(session.get("_pk_user_commit_token") or "").strip()
    if not commit:
        return ""
    try:
        import time as _time

        committed_at = float(session.get("_pk_user_commit_at") or 0.0)
        if not committed_at or (_time.time() - committed_at) >= 8.0:
            return ""
    except (TypeError, ValueError):
        return ""
    commit_pick = str(session.get("_pk_user_commit_pick") or "").strip()
    if commit_pick:
        return commit if commit_pick == live_pick else ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = str(get_practice_concert_key(session, live_pick) or "").strip()
        if saved and _practice_keys_equal(saved, commit):
            return commit
    except ImportError:
        pass
    return ""


def _token_matches_foreign_residue(session: dict[str, Any], token: str, pick: str, orig: str) -> bool:
    """True when ``token`` is another *catalog* pick's sticky, not this song's.

    Jam / visit keys sharing a tonic with this pick's own saved Practice Key
    must not invalidate the store (Perfect C must survive leftover Jam C).
    Live Jam leftovers are handled by ``sbi_active_live_is_foreign_leftover``.
    """
    tok = str(token or "").strip()
    if not tok:
        return False
    try:
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override

        if catalog_pick_has_user_practice_key_override(session, pick):
            return False
    except ImportError:
        pass
    orig_tok = str(orig or "").strip()
    if orig_tok and _practice_keys_equal(tok, orig_tok):
        return False
    try:
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        store = session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}
        if isinstance(store, dict):
            for other_pick, saved in store.items():
                other = str(other_pick)
                if other == pick:
                    continue
                # Custom / Composition / Jam keys sharing a tonic must not
                # invalidate this Catalog pick's own saved Practice Key.
                if other.startswith("custom::") or other.startswith("composition::") or other.startswith("creative::"):
                    continue
                if saved and _practice_keys_equal(tok, str(saved)):
                    return True
    except ImportError:
        pass
    return False


def sbi_active_canonical_practice_key(session: dict[str, Any], fallback: str = "") -> str:
    """Saved Practice Key for this Catalog pick, else song original.

    Leftover Shape / Custom / Mission / Jam tokens must not replace Perfect G
    when Perfect has no saved override. A genuine user edit for this pick wins.
    A D copied onto Perfect's store by a prior Shape/Say visit is not a valid
    override.
    """
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick
        from songs.music_source import _catalog_original_key_for_session

        pick = str(resolve_practice_source_pick(session) or "").strip()
        orig = str(_catalog_original_key_for_session(session) or "").strip()
        orig = orig or str(fallback or "C").strip() or "C"
        if pick.startswith("custom::"):
            return str(fallback or orig).strip() or orig
        user = sbi_active_user_commit_outranks(session, pick=pick)
        if user:
            return user
        saved = str(get_practice_concert_key(session, pick) or "").strip()
        try:
            from songs.practice_key_state import catalog_pick_has_user_practice_key_override

            if saved and catalog_pick_has_user_practice_key_override(session, pick):
                return saved
        except ImportError:
            pass
        if saved and _token_matches_foreign_residue(session, saved, pick, orig):
            return orig
        return saved or orig
    except ImportError:
        return str(fallback or session.get("display_key") or "C").strip() or "C"


def invalidate_automatic_sbi_active_restore_for_user_edit(
    session: dict[str, Any],
    token: str,
    *,
    pick: str = "",
) -> None:
    """Drop a pending original-key restore that would overwrite this user edit."""
    tok = str(token or "").strip()
    if not tok:
        return
    source = str(session.get(PENDING_DISPLAY_KEY_SOURCE) or "").strip()
    pending = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
    if source == SBI_ACTIVE_PK_RESTORE_SOURCE and pending and not _practice_keys_equal(pending, tok):
        _clear_owner_checked_pending_if_applied(session)
    elif pending and not _practice_keys_equal(pending, tok) and source in {"", SBI_ACTIVE_PK_RESTORE_SOURCE}:
        session.pop(PENDING_DISPLAY_KEY, None)
        session.pop(PENDING_DISPLAY_KEY_PICK, None)
        session.pop(PENDING_DISPLAY_KEY_SOURCE, None)
    session["_sbi_active_pk_restore_needs_rerun"] = False
    fp = str(session.get(SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY) or "")
    if fp and tok and f"|{tok}" not in fp:
        session.pop(SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY, None)


def note_sbi_active_user_practice_key_edit(
    session: dict[str, Any],
    token: str,
    *,
    pick: str = "",
) -> str:
    """Sidebar widget commit: this pick now owns ``token`` through refresh.

    Clears any pending automatic original-key restore for Catalog SBI Active.
    """
    tok = str(token or "").strip()
    if not tok:
        return ""
    live_pick = str(pick or "").strip()
    if not live_pick:
        try:
            from songs.practice_key_state import resolve_practice_source_pick

            live_pick = str(resolve_practice_source_pick(session) or "").strip()
        except ImportError:
            live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        if live_pick:
            mark_practice_key_user_override(session, live_pick)
            set_practice_concert_key(
                session,
                tok,
                pick_key=live_pick,
                allow_restore_original=True,
            )
    except ImportError:
        pass
    try:
        import time as _time

        session["_pk_user_commit_token"] = tok
        session["_pk_user_commit_pick"] = live_pick
        session["_pk_user_commit_at"] = _time.time()
    except Exception:
        pass
    session["concert_key"] = tok
    session["_creative_visit_practice_key"] = tok
    invalidate_automatic_sbi_active_restore_for_user_edit(session, tok, pick=live_pick)
    return tok


def _queue_owner_checked_pending(session: dict[str, Any], token: str, pick: str) -> None:
    session[PENDING_DISPLAY_KEY] = token
    session[PENDING_DISPLAY_KEY_PICK] = pick
    session[PENDING_DISPLAY_KEY_SOURCE] = SBI_ACTIVE_PK_RESTORE_SOURCE


def _clear_owner_checked_pending_if_applied(session: dict[str, Any]) -> None:
    if session.get(PENDING_DISPLAY_KEY_SOURCE) == SBI_ACTIVE_PK_RESTORE_SOURCE:
        session.pop(PENDING_DISPLAY_KEY, None)
        session.pop(PENDING_DISPLAY_KEY_PICK, None)
        session.pop(PENDING_DISPLAY_KEY_SOURCE, None)


def pending_sbi_active_restore_belongs_to_session(session: dict[str, Any]) -> bool:
    """True when queued SBI Active restore still matches this Catalog pick/session."""
    source = str(session.get(PENDING_DISPLAY_KEY_SOURCE) or "").strip()
    if source != SBI_ACTIVE_PK_RESTORE_SOURCE:
        return True
    if not sbi_active_catalog_owns_practice_key(session):
        return False
    pending_pick = str(session.get(PENDING_DISPLAY_KEY_PICK) or "").strip()
    if not pending_pick:
        return False
    live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import resolve_practice_source_pick

        live_pick = str(resolve_practice_source_pick(session) or live_pick).strip()
    except ImportError:
        pass
    return bool(live_pick) and pending_pick == live_pick


def _align_non_widget_keys(session: dict[str, Any], token: str, *, stamp_visit_source: bool = False) -> None:
    session["concert_key"] = token
    session["_creative_visit_practice_key"] = token
    if stamp_visit_source:
        session["_creative_visit_source"] = "sbi_active"


def sbi_active_live_is_foreign_leftover(session: dict[str, Any], canonical: str) -> bool:
    """True when live Practice Key is leftover from another pick/owner, not this song."""
    canonical_tok = str(canonical or "").strip()
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return True
    if canonical_tok and _practice_keys_equal(live, canonical_tok):
        return False
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or pick).strip()
    except ImportError:
        pass
    user_tok = sbi_active_user_commit_outranks(session, pick=pick)
    if user_tok and _practice_keys_equal(live, user_tok):
        return False
    router = session.get("_practice_key_write_router")
    if isinstance(router, dict):
        router_new = str(router.get("new") or "").strip()
        after = router.get("after") if isinstance(router.get("after"), dict) else {}
        after_dk = str((after or {}).get("display_key") or "").strip()
        if (router_new and _practice_keys_equal(live, router_new)) or (
            after_dk and _practice_keys_equal(live, after_dk)
        ):
            return False
    try:
        from songs.practice_key_state import get_practice_concert_key

        saved = str(get_practice_concert_key(session, pick) or "").strip()
        if saved and _practice_keys_equal(live, saved):
            if not _token_matches_foreign_residue(session, saved, pick, canonical_tok):
                return False
    except ImportError:
        pass
    jam = str(session.get("improv_jam_key") or session.get("improv_style_key") or "").strip()
    visit = str(session.get("_creative_visit_practice_key") or "").strip()
    if jam and _practice_keys_equal(live, jam) and not _practice_keys_equal(jam, canonical_tok):
        return True
    if visit and _practice_keys_equal(live, visit) and not _practice_keys_equal(visit, canonical_tok):
        return True
    try:
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        store = session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}
        if isinstance(store, dict):
            for other_pick, saved in store.items():
                other = str(other_pick)
                if other == pick:
                    continue
                if other.startswith("custom::") or other.startswith("composition::") or other.startswith("creative::"):
                    preview = str(session.get("sbi_preview_source") or "").strip()
                    if (
                        (
                            preview == "Active song"
                            or bool(session.get("_sbi_active_leave_intent"))
                        )
                        and saved
                        and _practice_keys_equal(live, str(saved))
                    ):
                        return True
                    continue
                if saved and _practice_keys_equal(live, str(saved)):
                    return True
    except ImportError:
        pass
    return False


def prepare_sbi_active_catalog_practice_key(
    session: dict[str, Any],
    *,
    st: Any | None = None,
    fallback: str = "",
) -> str:
    """Apply Catalog SBI Active Practice Key before the sidebar widget mounts.

    Only mutates when leftover Shape/Jam/visit keys contaminate this Catalog
    pick. Same-pick live user edits (Hevenu Dm→Ebm) are left for the sidebar.
    """
    if not sbi_active_catalog_owns_practice_key(session):
        return ""
    token = str(sbi_active_canonical_practice_key(session, fallback) or "").strip()
    try:
        from sbi_gc_lifecycle_trace import emit_sbi_gc

        emit_sbi_gc(
            session,
            "prepare_sbi_active_catalog_practice_key",
            prepared_token=token,
            live_dk=str(session.get("display_key") or ""),
        )
    except Exception:
        pass
    if not token:
        return ""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live and _practice_keys_equal(live, token):
        return token
    user = sbi_active_user_commit_outranks(session)
    if user and live and _practice_keys_equal(live, user):
        return live
    reclaim_sbi_active_catalog_keys(session, token, st_like=st)
    return token


def reclaim_sbi_active_catalog_keys(
    session: dict[str, Any],
    token: str,
    *,
    st_like: Any | None = None,
    stamp_visit_source: bool = False,
) -> str:
    """Align concert/visit with Catalog SBI canonical Practice Key.

    Never writes ``display_key`` after the sidebar widget has mounted. When the
    widget already exists, queue ``_pending_display_key`` bound to this pick
    and request at most one controlled rerun.
    """
    tok = str(token or "").strip()
    if not tok:
        return tok
    if not sbi_active_catalog_owns_practice_key(session):
        return tok

    pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or pick).strip()
    except ImportError:
        pass

    user = sbi_active_user_commit_outranks(session, pick=pick)
    if user and not _practice_keys_equal(user, tok):
        tok = user

    live = str(session.get("display_key") or "").strip()
    has_override = False
    try:
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override

        has_override = bool(pick and catalog_pick_has_user_practice_key_override(session, pick))
    except ImportError:
        has_override = False
    # Same-pick live user edits (Hevenu) stay. Refresh remount of Original G
    # must not hide a saved Perfect C override.
    if (
        live
        and not _practice_keys_equal(live, tok)
        and not sbi_active_live_is_foreign_leftover(session, tok)
        and not has_override
        and not (user and _practice_keys_equal(tok, user))
    ):
        return live

    _align_non_widget_keys(session, tok, stamp_visit_source=stamp_visit_source)
    locked = False
    try:
        from session_widget_safe import widgets_likely_instantiated

        locked = bool(widgets_likely_instantiated(session))
    except ImportError:
        locked = bool(session.get("_streamlit_widgets_locked_this_run"))

    if not locked:
        try:
            from session_widget_safe import safe_assign_display_key

            safe_assign_display_key(session, tok, widget_safe=True, st_like=st_like)
        except ImportError:
            session["display_key"] = tok
        _clear_owner_checked_pending_if_applied(session)
        return tok

    if _practice_keys_equal(live, tok):
        _clear_owner_checked_pending_if_applied(session)
        return tok

    _queue_owner_checked_pending(session, tok, pick)
    session["_sbi_active_pk_restore_needs_rerun"] = True
    return tok


def request_sbi_active_catalog_key_rerun(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    pick: str = "",
    token: str = "",
) -> bool:
    """One controlled rerun so pending restore can land before display_key mounts."""
    fp = f"sbi_active_pk_restore|{pick}|{token}"
    if str(session.get(SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY) or "") == fp:
        session["_sbi_active_pk_restore_needs_rerun"] = False
        return False
    session[SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY] = fp
    if st_like is None:
        return True
    try:
        from music_rerun_loop_guard import safe_rerun

        return bool(
            safe_rerun(
                st_like,
                session,
                reason="sbi_active_pk_restore",
                fingerprint=fp,
            )
        )
    except ImportError:
        rerun = getattr(st_like, "rerun", None)
        if callable(rerun):
            rerun()
            return True
        return True


def persist_sbi_active_sidebar_commit_before_render(session: dict[str, Any]) -> str:
    """If the sidebar callback already accepted a token, write pick-scoped store now.

    Presentation still uses canonical Practice Key, never a raw display_key copy.
    """
    try:
        from source_session_state import genuine_sbi_active_leave

        if genuine_sbi_active_leave(session):
            return ""
    except ImportError:
        pass
    try:
        from sbi_gc_lifecycle_trace import emit_sbi_gc

        emit_sbi_gc(session, "persist_sbi_active_sidebar_commit:enter")
    except Exception:
        pass
    if not sbi_active_catalog_owns_practice_key(session):
        return ""
    live = str(session.get("display_key") or "").strip()
    if not live:
        return ""
    router = session.get("_practice_key_write_router")
    router_new = ""
    after_dk = ""
    write_owner = ""
    if isinstance(router, dict):
        widget = str(router.get("widget_key") or "").strip()
        write_owner = str(router.get("write_owner") or "").strip()
        if widget in {"", "display_key"}:
            router_new = str(router.get("new") or "").strip()
        after = router.get("after") if isinstance(router.get("after"), dict) else {}
        after_dk = str((after or {}).get("display_key") or "").strip()
    if write_owner in {"entry_jam", "mission"}:
        return ""
    commit = str(session.get("_pk_user_commit_token") or "").strip()
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or pick).strip()
    except ImportError:
        pass
    commit_pick = str(session.get("_pk_user_commit_pick") or "").strip()
    if commit_pick and pick and commit_pick != pick:
        return ""
    accepted = (
        (commit and _practice_keys_equal(commit, live))
        or (
            write_owner in {"catalog", "song_improv"}
            and router_new
            and _practice_keys_equal(router_new, live)
        )
        or (
            after_dk
            and _practice_keys_equal(after_dk, live)
            and write_owner in {"catalog", "song_improv", ""}
        )
    )
    if not accepted:
        return ""
    return note_sbi_active_user_practice_key_edit(session, live, pick=pick)


def collect_sbi_active_render_trace(
    session: dict[str, Any],
    *,
    fallback: str = "",
    card_key: str = "",
    caption_key: str = "",
) -> dict[str, Any]:
    """Values used at SBI card / Practice concert key render time."""
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    try:
        from songs.practice_key_state import (
            catalog_pick_has_user_practice_key_override,
            get_practice_concert_key,
            resolve_practice_source_pick,
        )

        pick = str(resolve_practice_source_pick(session) or pick).strip()
        saved = str(get_practice_concert_key(session, pick) or "").strip()
        has_override = bool(catalog_pick_has_user_practice_key_override(session, pick))
    except ImportError:
        saved = ""
        has_override = False
    wf_owner = ""
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        wf_owner = str(getattr(ptr, "workflow_owner", "") or "") if ptr is not None else ""
    except ImportError:
        wf_owner = str(session.get("_active_workflow_owner") or "")
    backing_src = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        backing_src = str(getattr(ctx, "source", "") or "") if ctx is not None else ""
    except ImportError:
        backing_src = ""
    router = session.get("_practice_key_write_router")
    snapshot = {
        "pick": pick,
        "display_key": str(session.get("display_key") or ""),
        "pick_scoped_saved": saved,
        "has_user_override": has_override,
        "canonical": sbi_active_canonical_practice_key(session, fallback),
        "visit": str(session.get("_creative_visit_practice_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
        "pending": str(session.get(PENDING_DISPLAY_KEY) or ""),
        "pending_pick": str(session.get(PENDING_DISPLAY_KEY_PICK) or ""),
        "pending_source": str(session.get(PENDING_DISPLAY_KEY_SOURCE) or ""),
        "workflow_owner": wf_owner,
        "backing_source": backing_src,
        "router_new": str((router or {}).get("new") or "") if isinstance(router, dict) else "",
        "card_key": str(card_key or ""),
        "caption_key": str(caption_key or ""),
        "original_key": str((session.get("selected_song") or {}).get("key") or "")
        if isinstance(session.get("selected_song"), dict)
        else "",
    }
    try:
        from pathlib import Path
        import json
        import time

        path = (
            Path(__file__).resolve().parent
            / "scripts"
            / "evidence-creative-backing"
            / "sbi-card-render.jsonl"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), **snapshot}) + "\n")
    except Exception:
        pass
    session["_sbi_card_render_trace"] = snapshot
    return snapshot


def emit_sbi_active_render_trace_html(st: Any, snapshot: dict[str, Any]) -> None:
    import html as _html

    card = _html.escape(str(snapshot.get("card_key") or ""))
    caption = _html.escape(str(snapshot.get("caption_key") or ""))
    live = _html.escape(str(snapshot.get("display_key") or ""))
    saved = _html.escape(str(snapshot.get("pick_scoped_saved") or ""))
    canonical = _html.escape(str(snapshot.get("canonical") or ""))
    pending = _html.escape(str(snapshot.get("pending") or ""))
    st.markdown(
        f'<div id="sbi-pk-render-trace" data-sbi-card-key="{card}" '
        f'data-sbi-caption-key="{caption}" data-sbi-display-key="{live}" '
        f'data-sbi-saved-key="{saved}" data-sbi-canonical="{canonical}" '
        f'data-sbi-pending="{pending}" style="display:none!important" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def maybe_rerun_sbi_active_catalog_key_restore(st: Any, session: dict[str, Any]) -> bool:
    if not session.pop("_sbi_active_pk_restore_needs_rerun", False):
        return False
    pending = str(session.get(PENDING_DISPLAY_KEY) or "").strip()
    pick = str(session.get(PENDING_DISPLAY_KEY_PICK) or "").strip()
    if not pending:
        return False
    live = str(session.get("display_key") or "").strip()
    user = sbi_active_user_commit_outranks(session, pick=pick)
    if user and live and _practice_keys_equal(live, user) and not _practice_keys_equal(pending, live):
        _clear_owner_checked_pending_if_applied(session)
        return False
    return request_sbi_active_catalog_key_rerun(
        session,
        st_like=st,
        pick=pick,
        token=str(pending),
    )


__all__ = [
    "PENDING_DISPLAY_KEY_PICK",
    "PENDING_DISPLAY_KEY_SOURCE",
    "SBI_ACTIVE_PK_RESTORE_RERUN_FP_KEY",
    "SBI_ACTIVE_PK_RESTORE_SOURCE",
    "invalidate_automatic_sbi_active_restore_for_user_edit",
    "maybe_rerun_sbi_active_catalog_key_restore",
    "collect_sbi_active_render_trace",
    "emit_sbi_active_render_trace_html",
    "note_sbi_active_user_practice_key_edit",
    "pending_sbi_active_restore_belongs_to_session",
    "persist_sbi_active_sidebar_commit_before_render",
    "prepare_sbi_active_catalog_practice_key",
    "reclaim_sbi_active_catalog_keys",
    "request_sbi_active_catalog_key_rerun",
    "sbi_active_canonical_practice_key",
    "sbi_active_catalog_owns_practice_key",
    "sbi_active_live_is_foreign_leftover",
    "sbi_active_user_commit_outranks",
]
