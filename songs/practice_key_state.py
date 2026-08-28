"""Per-source practice settings — concert key and BPM survive refresh per pick_key."""

from __future__ import annotations

from typing import Any

PRACTICE_KEY_BY_SOURCE_KEY = "practice_key_by_source"
BPM_BY_SOURCE_KEY = "bpm_by_source"
FORCE_BPM_SYNC_ONCE_KEY = "_force_bpm_sync_once"
CREATIVE_STYLE_JAM_PICK = "creative::entry_style_jam"
CREATIVE_JAM_SESSION_PICK = "creative::jam_session_generator"
CREATIVE_SBI_PICK = "creative::song_improv"
PK_USER_COMMIT_TOKEN_KEY = "_pk_user_commit_token"
PK_USER_COMMIT_AT_KEY = "_pk_user_commit_at"
PK_USER_COMMIT_PICK_KEY = "_pk_user_commit_pick"


def _practice_key_store(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(PRACTICE_KEY_BY_SOURCE_KEY)
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(k).strip() and str(v).strip()}


def _bpm_store(session: dict[str, Any]) -> dict[str, int]:
    raw = session.get(BPM_BY_SOURCE_KEY)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        pk = str(k).strip()
        if not pk:
            continue
        try:
            bpm = int(v)
        except (TypeError, ValueError):
            continue
        if bpm > 0:
            out[pk] = bpm
    return out


def pick_key_from_bpm_sync_id(sync_id: str) -> str:
    """Extract catalog/custom pick_key from a playback sync id."""
    sid = str(sync_id or "").strip()
    if sid.startswith("pk::"):
        return sid[4:].strip()
    if sid.startswith("custom::"):
        return sid
    return ""


def is_song_source_pick(pick_key: str) -> bool:
    """True for catalog/custom picks — not creative-only namespace keys."""
    pk = str(pick_key or "").strip()
    if not pk:
        return False
    return not pk.startswith("creative::")


def resolve_creative_settings_pick(session: dict[str, Any]) -> str:
    """Stable pick_key for Style Jam / Jam Session / SBI creative settings."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        return CREATIVE_STYLE_JAM_PICK
    if entry == "Jam Session Generator":
        return CREATIVE_JAM_SESSION_PICK
    if entry == "Song-Based Improvisation":
        return CREATIVE_SBI_PICK
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            if sess.tool_type == "entry_style_jam":
                return CREATIVE_STYLE_JAM_PICK
            if sess.tool_type == "jam_session_generator":
                return CREATIVE_JAM_SESSION_PICK
            if sess.tool_type == "song_based_improvisation":
                return CREATIVE_SBI_PICK
    except ImportError:
        pass
    return ""


def creative_jam_owns_practice_settings(session: dict[str, Any]) -> bool:
    """Style Jam / Jam Session must not write catalog/custom per-source maps."""
    try:
        from creative_key_sync import is_creative_major_jam_active

        if is_creative_major_jam_active(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if page == "creative" and entry in {"Style Jam Mode", "Jam Session Generator"}:
        return True
    if page == "backing":
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None and str(ctx.source or "") == "entry_jam":
                return True
        except ImportError:
            pass
    try:
        from creative_session_state import creative_session_is_active, get_creative_session

        if creative_session_is_active(session):
            sess = get_creative_session(session)
            if sess is not None and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
                return True
    except ImportError:
        pass
    return False


def should_write_song_source_settings(session: dict[str, Any], pick_key: str = "") -> bool:
    """True when practice_key_by_source / bpm_by_source may receive this pick_key."""
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return False
    if pk.startswith("custom::"):
        return True
    if not is_song_source_pick(pk):
        return True
    return not creative_jam_owns_practice_settings(session)


def resolve_settings_pick_for_write(
    session: dict[str, Any],
    pick_key: str = "",
) -> str:
    """Target pick_key for set_practice_concert_key / set_source_bpm."""
    explicit = str(pick_key or "").strip()
    if explicit.startswith("custom::"):
        return explicit

    # SBI Custom preview/backing: sticky Practice Key belongs to LAST_CUSTOM / CPL,
    # never Global Active catalog (P5 / Global Active vs LAST_CUSTOM separation).
    # Only auto-redirect when the caller did not name a destination — sealing the
    # catalog sticky under a Custom overlay must still write the explicit catalog pick.
    custom_sbi_pick = _custom_sbi_settings_pick(session)
    if custom_sbi_pick and not explicit:
        return custom_sbi_pick

    if creative_jam_owns_practice_settings(session):
        if explicit.startswith("creative::"):
            return explicit
        if explicit and is_song_source_pick(explicit):
            cp = resolve_creative_settings_pick(session)
            return cp or ""
        cp = resolve_creative_settings_pick(session)
        if cp:
            return cp
        return ""
    if explicit:
        return explicit
    return resolve_practice_source_pick(session)


def _custom_sbi_settings_pick(session: dict[str, Any]) -> str:
    """When SBI is on Custom progression, return the custom pick_key for PK writes."""
    page = str(session.get("studio_page") or "").strip().lower()
    entry = str(session.get("improv_entry_mode") or "").strip()
    ctx_src = ""
    bound = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_src = str(getattr(ctx, "source", "") or "").strip()
            bound = str(
                getattr(ctx, "bound_pick_key", "")
                or getattr(ctx, "active_song_id", "")
                or ""
            ).strip()
    except ImportError:
        pass
    custom_preview = sbi_uses_custom_progression_preview(session)
    # Custom SBI Backing may keep source=song_improv with custom:: bound pick.
    if (
        not custom_preview
        and ctx_src != "custom_progression"
        and not (ctx_src == "song_improv" and bound.startswith("custom::"))
    ):
        return ""
    # Leftover Custom SBI preview on Missions / Motif must not steal PK writes
    # from the catalog-owned Creative tab (same surface rule as sidebar owner).
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        if (
            custom_preview
            and page == "creative"
            and not custom_sbi_owns_sidebar_practice_key(session)
        ):
            return ""
    except ImportError:
        tab = str(
            session.get("improv_intelligence_tab")
            or session.get("creative_improv_intelligence_tab")
            or ""
        ).strip()
        if custom_preview and page == "creative" and tab not in {"", "Entry & Jam"}:
            return ""
    # Songs / Practice / picker must write the Global Active catalog pick — leftover
    # SBI Custom entry/source flags must not redirect catalog Practice Key writes.
    sbi_surface = page in {"creative", "backing"} or (
        page == ""
        and (
            entry == "Song-Based Improvisation"
            or ctx_src in {"song_improv", "custom_progression"}
        )
    )
    picker_custom = False
    if page in {"picker", "creative", "practice", "songs", ""}:
        try:
            from workflow_musical_authority import custom_owns_active_song_material

            picker_custom = custom_owns_active_song_material(session)
        except ImportError:
            picker_custom = False
    if not sbi_surface and not picker_custom:
        return ""
    if bound.startswith("custom::"):
        return bound

    try:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

        snap = session.get(LAST_CUSTOM_STATE_KEY)
        if isinstance(snap, dict):
            active = snap.get("active")
            if isinstance(active, dict):
                pk = str(custom_pick_key_for(active) or "").strip()
                if pk.startswith("custom::"):
                    return pk
    except ImportError:
        pass
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = session.get(CPL_ACTIVE_KEY)
        if isinstance(active, dict):
            pk = str(custom_pick_key_for(active) or "").strip()
            if pk.startswith("custom::"):
                return pk
    except ImportError:
        pass
    return ""


def resolve_practice_source_pick(session: dict[str, Any]) -> str:
    """Stable pick_key for catalog or custom progression practice-key storage."""
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY
    except ImportError:
        ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"  # type: ignore[misc,assignment]
        SELECTED_SONG_STATE_KEY = "selected_song"  # type: ignore[misc,assignment]

    pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    if pick:
        return pick
    sel = session.get(SELECTED_SONG_STATE_KEY)
    if isinstance(sel, dict):
        pick = str(sel.get("pick_key") or "").strip()
        if pick:
            return pick
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for, ensure_custom_active_song_identity

        ensure_custom_active_song_identity(session, cpl_active_key=CPL_ACTIVE_KEY)
        pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
        if pick:
            return pick
        active = session.get(CPL_ACTIVE_KEY)
        if isinstance(active, dict):
            return custom_pick_key_for(active)
    except ImportError:
        pass
    return ""


def _practice_pick_aliases(pick_key: str) -> list[str]:
    """Legacy ``Genre::Label`` and canonical ``Genre\\x1fLabel`` forms for one pick."""
    pk = str(pick_key or "").strip()
    if not pk:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        v = str(value or "").strip()
        if not v or v in seen:
            return
        seen.add(v)
        out.append(v)

    def _expand_label_forms(genre: str, label: str) -> None:
        g = str(genre or "").strip()
        lab = str(label or "").strip()
        if not g or not lab:
            return
        _add(f"{g}\x1f{lab}")
        _add(f"{g}::{lab}")
        # Title-only vs "Title — Artist" both appear in the wild.
        for sep in (" — ", " - ", " – "):
            if sep in lab:
                short = lab.split(sep, 1)[0].strip()
                if short and short != lab:
                    _add(f"{g}\x1f{short}")
                    _add(f"{g}::{short}")
                break

    _add(pk)
    if "\x1f" in pk:
        genre, _, label = pk.partition("\x1f")
        _expand_label_forms(genre, label)
    elif "::" in pk and not pk.startswith("custom::") and not pk.startswith("creative::"):
        genre, _, label = pk.partition("::")
        _expand_label_forms(genre, label)
    try:
        from songs.music_source import normalize_catalog_pick_key

        norm = str(normalize_catalog_pick_key(pk) or "").strip()
        _add(norm)
        if norm and "\x1f" in norm:
            genre, _, label = norm.partition("\x1f")
            _expand_label_forms(genre, label)
    except ImportError:
        pass
    return out


def get_practice_concert_key(
    session: dict[str, Any],
    pick_key: str = "",
    *,
    default: str = "",
) -> str:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return str(default or "").strip()
    store = _practice_key_store(session)
    for alias in _practice_pick_aliases(pk):
        saved = store.get(alias, "").strip()
        if saved:
            return saved
    # Last resort: any store key that shares an alias with this pick.
    aliases = set(_practice_pick_aliases(pk))
    for stored_pk, saved in store.items():
        if not saved:
            continue
        if aliases.intersection(_practice_pick_aliases(stored_pk)):
            return str(saved).strip()
    return str(default or "").strip()


def stamp_practice_key_user_commit(
    session: dict[str, Any],
    concert_key: str,
    *,
    pick_key: str = "",
) -> None:
    """Restamp the 5s remount guard to *concert_key* — never leave it empty.

    When *pick_key* is set, later writes for a *different* song source are not
    blocked (Custom D must not freeze Shape's first-click Dm).
    """
    key = str(concert_key or "").strip()
    if not key:
        return
    try:
        import time as _time

        session[PK_USER_COMMIT_TOKEN_KEY] = key
        session[PK_USER_COMMIT_AT_KEY] = float(_time.time())
        pk = str(pick_key or "").strip()
        if pk:
            session[PK_USER_COMMIT_PICK_KEY] = pk
    except Exception:
        pass


def apply_authoritative_practice_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    pick_key: str = "",
    sync_display: bool = True,
    sync_custom_widgets: bool = False,
) -> str:
    """Write Practice Key once and restamp the user-commit guard to the new key.

    Fresh Catalog→Custom activation must replace a leftover Catalog token
    (Perfect G) with the new Custom key. Popping the guard without restamping
    leaves a window where a stale remount can overwrite Original D.
    """
    key = str(concert_key or "").strip()
    if not key:
        return ""
    if sync_display:
        session["display_key"] = key
        session["concert_key"] = key
    if sync_custom_widgets:
        try:
            from custom_progression_lab import (
                CPL_LAST_DISPLAY_KEY,
                CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            )

            session[CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET] = key
            session[CPL_LAST_DISPLAY_KEY] = key
            session["_cpl_force_pk_to_home"] = key
        except ImportError:
            pass
    set_practice_concert_key(
        session,
        key,
        pick_key=pick_key,
        allow_restore_original=True,
    )
    stamp_practice_key_user_commit(session, key, pick_key=pick_key)
    return key


def set_practice_concert_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    pick_key: str = "",
    allow_catalog_during_sbi_custom: bool = False,
    allow_restore_original: bool = False,
) -> None:
    pk = resolve_settings_pick_for_write(session, pick_key)
    key = str(concert_key or "").strip()
    if not pk or not key:
        return
    # Protect a recent explicit user Practice Key commit from stale remount /
    # pending / identity writes that land 1–2s later (Bm → Dm rollback).
    try:
        import time as _time

        commit = str(session.get(PK_USER_COMMIT_TOKEN_KEY) or "").strip()
        committed_at = float(session.get(PK_USER_COMMIT_AT_KEY) or 0.0)
        commit_pick = str(session.get(PK_USER_COMMIT_PICK_KEY) or "").strip()
        same_pick = True
        if commit_pick and pk:
            same_pick = commit_pick == pk
            if not same_pick:
                commit_aliases = set(_practice_pick_aliases(commit_pick))
                write_aliases = set(_practice_pick_aliases(pk))
                same_pick = bool(commit_aliases & write_aliases)
        if (
            commit
            and committed_at
            and (_time.time() - committed_at) < 5.0
            and key != commit
            and not allow_restore_original
            and same_pick
        ):
            return
    except Exception:
        pass
    # Stale SBI/mission identity prime must not write blob Dm over a live Bm
    # (or any live Practice Key that already differs).
    try:
        from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

        src = str(session.get(DISPLAY_KEY_CHANGE_SOURCE_KEY) or "").strip()
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if (
            src.startswith("sidebar_key_identity:")
            and "catalog_sticky" not in src
            and live
            and live != key
        ):
            return
        # During an explicit sidebar commit, never write a different token than the
        # live widget value unless this call is the allow_restore_original commit.
        if (
            src in {"sidebar_on_change", "sidebar", "display_key_widget", "display_key_change"}
            and live
            and live != key
            and not allow_restore_original
        ):
            return
        # Stale pending remount (Dm) must not overwrite a live Bm commit.
        if src == "pending_display_key" and live and live != key:
            return
    except ImportError:
        pass
    # Hard isolation: while Creative/Backing SBI is on Custom progression, never
    # write the Global Active catalog sticky (Shape Dm must not become Eb/D#m).
    # Exception: explicit seal of catalog sticky when entering the Custom overlay.
    if (
        not allow_catalog_during_sbi_custom
        and is_song_source_pick(pk)
        and not str(pk).startswith("custom::")
    ):
        try:
            page = str(session.get("studio_page") or "").strip().lower()
            # Any active Custom overlay means catalog sticky is sealed — do not
            # overwrite Shape with Custom live (E / Eb / C#).
            if page in {"creative", "backing", "custom"} and (
                session.get("_sbi_custom_sidebar_overlay")
                or session.get("_custom_page_sidebar_overlay")
            ):
                return
            if page in {"creative", "backing"} and sbi_uses_custom_progression_preview(session):
                return
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            bound = str(
                getattr(ctx, "bound_pick_key", "")
                or getattr(ctx, "active_song_id", "")
                or ""
            ).strip() if ctx is not None else ""
            src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
            if page in {"creative", "backing"} and (
                src == "custom_progression"
                or (src == "song_improv" and bound.startswith("custom::"))
            ):
                return
            # After leaving Custom SBI, refuse remount writes of the Custom sticky
            # token onto the sealed catalog pick (Shape Dm must not become E).
            sealed = str(session.get("_sbi_custom_sealed_catalog_pk") or "").strip()
            sealed_pick = str(session.get("_sbi_custom_sealed_catalog_pick") or "").strip()
            if sealed and sealed_pick and key != sealed:
                same_pick = str(pk) == sealed_pick
                if not same_pick:
                    try:
                        from songs.music_source import normalize_catalog_pick_key

                        same_pick = str(
                            normalize_catalog_pick_key(pk, session_state=session) or ""
                        ).strip() == str(
                            normalize_catalog_pick_key(sealed_pick, session_state=session)
                            or ""
                        ).strip()
                    except Exception:
                        same_pick = False
                if same_pick:
                    custom_tok = ""
                    try:
                        custom_write = str(_custom_sbi_settings_pick(session) or "").strip()
                        if not custom_write.startswith("custom::"):
                            from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for

                            snap = session.get(LAST_CUSTOM_STATE_KEY)
                            if isinstance(snap, dict):
                                active = snap.get("active")
                                if isinstance(active, dict):
                                    custom_write = str(
                                        custom_pick_key_for(active) or snap.get("pick_key") or ""
                                    ).strip()
                        if custom_write.startswith("custom::"):
                            custom_tok = str(
                                get_practice_concert_key(session, custom_write) or ""
                            ).strip()
                    except Exception:
                        custom_tok = ""
                    if custom_tok and key == custom_tok:
                        return
        except Exception:
            pass
    # Generated Jam / Style Jam keys must never land in a catalog song slot.
    if is_song_source_pick(pk) and not str(pk).startswith("custom::"):
        try:
            from generated_jam_key_context import generated_jam_practice_key_tokens

            if key in generated_jam_practice_key_tokens(session):
                return
        except ImportError:
            pass
        jam_widget = str(session.get("improv_jam_key") or session.get("improv_style_key") or "").strip()
        if jam_widget and key == jam_widget and creative_jam_owns_practice_settings(session):
            return
        # Streamlit sidebar reseeds to catalog Original on page change; that must
        # not wipe a sticky Practice Key (C#m → Bm on leave Backing→Practice, H2).
        # Explicit user Practice Key commits (Dm → Bm return to Original) MUST write.
        user_restore = bool(allow_restore_original)
        if not user_restore:
            try:
                from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

                src = str(session.get(DISPLAY_KEY_CHANGE_SOURCE_KEY) or "").strip().lower()
                if src in {
                    "sidebar_on_change",
                    "sidebar",
                    "display_key_widget",
                    "display_key_change",
                    "user",
                    "user_navigation",
                }:
                    user_restore = True
            except ImportError:
                pass
        if not user_restore:
            existing = str(get_practice_concert_key(session, pk) or "").strip()
            if existing and existing != key:
                orig = ""
                try:
                    from songs.music_source import _catalog_original_key_for_session

                    probe = dict(session)
                    probe["active_catalog_pick_key"] = pk
                    orig = str(_catalog_original_key_for_session(probe) or "").strip()
                except Exception:
                    orig = ""
                if orig and key == orig and existing != orig:
                    try:
                        from pathlib import Path
                        import json
                        import time

                        _dbg = (
                            Path(__file__).resolve().parents[1]
                            / "scripts"
                            / "evidence-creative-backing"
                            / "pk-restore-refuse.jsonl"
                        )
                        _dbg.parent.mkdir(parents=True, exist_ok=True)
                        with _dbg.open("a", encoding="utf-8") as fh:
                            fh.write(
                                json.dumps(
                                    {
                                        "t": time.time(),
                                        "pk": pk,
                                        "key": key,
                                        "existing": existing,
                                        "orig": orig,
                                        "allow_restore_original": allow_restore_original,
                                        "change_source": str(
                                            session.get("display_key_change_source") or ""
                                        ),
                                        "studio_page": str(session.get("studio_page") or ""),
                                    }
                                )
                                + "\n"
                            )
                    except Exception:
                        pass
                    return
    store = _practice_key_store(session)
    # Prefer canonical catalog form; drop legacy aliases for the same pick.
    write_pk = pk
    try:
        from songs.music_source import normalize_catalog_pick_key

        norm = str(normalize_catalog_pick_key(pk, session_state=session) or "").strip()
        if norm:
            write_pk = norm
    except ImportError:
        pass
    for alias in _practice_pick_aliases(pk) + _practice_pick_aliases(write_pk):
        if alias != write_pk:
            store.pop(alias, None)
    store[write_pk] = key
    session[PRACTICE_KEY_BY_SOURCE_KEY] = store
    try:
        if key in {"Bm", "Dm", "Cm"} or str(key).endswith("m"):
            from pathlib import Path
            import json
            import time

            _dbg = (
                Path(__file__).resolve().parents[1]
                / "scripts"
                / "evidence-creative-backing"
                / "pk-write.jsonl"
            )
            _dbg.parent.mkdir(parents=True, exist_ok=True)
            with _dbg.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "write_pk": write_pk,
                            "key": key,
                            "allow_restore_original": allow_restore_original,
                            "change_source": str(session.get("display_key_change_source") or ""),
                            "display_key": str(session.get("display_key") or ""),
                            "studio_page": str(session.get("studio_page") or ""),
                        }
                    )
                    + "\n"
                )
    except Exception:
        pass
    # Intentional catalog write refreshes isolation seals (Shape Dm → user F, etc.).
    if not str(write_pk).startswith("custom::"):
        for seal_pick_key, seal_pk_key in (
            ("_sbi_custom_sealed_catalog_pick", "_sbi_custom_sealed_catalog_pk"),
            ("_custom_page_sealed_catalog_pick", "_custom_page_sealed_catalog_pk"),
        ):
            sealed_pick = str(session.get(seal_pick_key) or "").strip()
            if not sealed_pick:
                continue
            sealed_aliases = set(_practice_pick_aliases(sealed_pick) + [sealed_pick])
            if write_pk in sealed_aliases or pk in sealed_aliases:
                session[seal_pk_key] = key


def clear_practice_concert_key(session: dict[str, Any], pick_key: str) -> None:
    pk = str(pick_key or "").strip()
    if not pk:
        return
    store = _practice_key_store(session)
    removed = False
    for alias in _practice_pick_aliases(pk):
        if alias in store:
            store.pop(alias, None)
            removed = True
    if not removed and pk in store:
        store.pop(pk, None)
    session[PRACTICE_KEY_BY_SOURCE_KEY] = store


def mark_force_bpm_sync(session: dict[str, Any], sync_id: str) -> None:
    sid = str(sync_id or "").strip()
    if sid:
        session[FORCE_BPM_SYNC_ONCE_KEY] = sid


def consume_force_bpm_sync(session: dict[str, Any], sync_id: str) -> bool:
    forced = str(session.get(FORCE_BPM_SYNC_ONCE_KEY) or "").strip()
    if forced and forced == str(sync_id or "").strip():
        session.pop(FORCE_BPM_SYNC_ONCE_KEY, None)
        return True
    return False


def sbi_uses_custom_progression_preview(session: dict[str, Any]) -> bool:
    """True when Song-Based Improvisation is previewing custom without global custom ownership."""
    try:
        from source_session_state import get_sbi_preview_source

        return get_sbi_preview_source(session) == "Custom progression"
    except ImportError:
        try:
            from studio_page_state import resolve_improv_song_source

            return str(resolve_improv_song_source(session) or "").strip() == "Custom progression"
        except ImportError:
            return False


def resolve_practice_concert_key_for_pick(
    session: dict[str, Any],
    pick_key: str,
    *,
    original_key: str = "",
) -> str:
    """Saved practice key for one source, else catalog/custom original."""
    original = str(original_key or "").strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return resolve_practice_concert_key_for_song(
                session,
                original,
                pick_key=pick_key,
            )
    except ImportError:
        pass
    saved = get_practice_concert_key(session, pick_key)
    if saved:
        return saved
    return original


def get_source_bpm(
    session: dict[str, Any],
    pick_key: str = "",
    *,
    default: int = 0,
) -> int:
    pk = str(pick_key or resolve_practice_source_pick(session) or "").strip()
    if not pk:
        return int(default or 0)
    saved = _bpm_store(session).get(pk)
    if saved and saved > 0:
        return int(saved)
    return int(default or 0)


def set_source_bpm(
    session: dict[str, Any],
    bpm: int,
    *,
    pick_key: str = "",
) -> None:
    pk = resolve_settings_pick_for_write(session, pick_key)
    try:
        val = int(bpm)
    except (TypeError, ValueError):
        return
    if not pk or val <= 0:
        return
    store = _bpm_store(session)
    store[pk] = val
    session[BPM_BY_SOURCE_KEY] = store


def clear_source_bpm(session: dict[str, Any], pick_key: str) -> None:
    pk = str(pick_key or "").strip()
    if not pk:
        return
    store = _bpm_store(session)
    if pk not in store:
        return
    store.pop(pk, None)
    session[BPM_BY_SOURCE_KEY] = store


def resolve_source_bpm_for_pick(
    session: dict[str, Any],
    pick_key: str,
    *,
    default_bpm: int,
) -> int:
    """Saved BPM for one source, else song default."""
    saved = get_source_bpm(session, pick_key, default=0)
    if saved > 0:
        return saved
    return int(default_bpm or 100)


__all__ = [
    "BPM_BY_SOURCE_KEY",
    "CREATIVE_JAM_SESSION_PICK",
    "CREATIVE_SBI_PICK",
    "CREATIVE_STYLE_JAM_PICK",
    "FORCE_BPM_SYNC_ONCE_KEY",
    "PK_USER_COMMIT_AT_KEY",
    "PK_USER_COMMIT_PICK_KEY",
    "PK_USER_COMMIT_TOKEN_KEY",
    "PRACTICE_KEY_BY_SOURCE_KEY",
    "apply_authoritative_practice_key",
    "clear_practice_concert_key",
    "clear_source_bpm",
    "consume_force_bpm_sync",
    "creative_jam_owns_practice_settings",
    "get_practice_concert_key",
    "get_source_bpm",
    "is_song_source_pick",
    "mark_force_bpm_sync",
    "pick_key_from_bpm_sync_id",
    "resolve_creative_settings_pick",
    "resolve_practice_concert_key_for_pick",
    "resolve_practice_source_pick",
    "resolve_settings_pick_for_write",
    "resolve_source_bpm_for_pick",
    "should_write_song_source_settings",
    "sbi_uses_custom_progression_preview",
    "set_practice_concert_key",
    "set_source_bpm",
    "stamp_practice_key_user_commit",
]
