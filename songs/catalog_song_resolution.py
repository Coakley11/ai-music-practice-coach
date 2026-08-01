"""Canonical catalog song resolution for chart transpose (original key + identity)."""

from __future__ import annotations

from typing import Any

CHART_SONG_RESOLVE_DIAG_KEY = "_chart_song_resolve_diag"

CANONICAL_IDENTITY_KEYS: frozenset[str] = frozenset(
    {
        "pick_key",
        "title",
        "genre",
        "original_key",
        "source_type",
        "key",
    }
)


def resolve_original_song_key(
    record: dict[str, Any] | None,
    *,
    catalog_session: dict[str, Any] | None = None,
) -> str:
    """Read documented original key fields — never guess C or use display/practice key."""
    if not isinstance(record, dict):
        record = {}
    candidates: list[Any] = [
        record.get("key"),
        record.get("original_key"),
    ]
    if isinstance(catalog_session, dict):
        candidates.append(catalog_session.get("original_key"))
        candidates.append(catalog_session.get("key"))
        nested_sel = catalog_session.get("selected_song")
        if isinstance(nested_sel, dict):
            candidates.append(nested_sel.get("key"))
            candidates.append(nested_sel.get("original_key"))
    nested = record.get("song_data")
    if isinstance(nested, dict):
        candidates.extend((nested.get("key"), nested.get("original_key")))
    ext = record.get("extensions")
    if isinstance(ext, dict):
        candidates.extend((ext.get("key"), ext.get("original_key")))
    user = record.get("user_override")
    if isinstance(user, dict):
        candidates.extend((user.get("key"), user.get("original_key")))
    for raw in candidates:
        val = str(raw or "").strip()
        if val:
            return val
    return ""


def merge_chart_song_overlay(
    canonical: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    """Non-empty overlay merge; canonical identity fields cannot be wiped by empty values."""
    merged = dict(canonical)
    for key, val in overlay.items():
        if val is None:
            continue
        if key in CANONICAL_IDENTITY_KEYS and not str(val).strip():
            continue
        if key == "sections" and not val and merged.get("sections"):
            continue
        if key == "pick_key" and str(val).strip().startswith("custom::") and merged.get("pick_key"):
            if not str(merged.get("pick_key") or "").startswith("custom::"):
                continue
        merged[key] = val
    return merged


def _safe_keys(record: dict[str, Any] | None) -> list[str]:
    if not isinstance(record, dict):
        return []
    return sorted(str(k) for k in record.keys())


def _pick_in_catalog(pick_key: str, song_picker_catalog: dict | None) -> bool:
    if not pick_key or not isinstance(song_picker_catalog, dict):
        return False
    try:
        from songs.state import parse_pick_key

        genre, label = parse_pick_key(pick_key)
        return genre in song_picker_catalog and label in song_picker_catalog[genre]
    except Exception:
        return False


def collect_catalog_song_resolve_diagnostics(
    session_state: dict[str, Any],
    *,
    reconciled_pick_key: str,
    catalog_song_data: dict[str, Any],
    merged: dict[str, Any],
    canonical: dict[str, Any] | None,
    provenance: str,
    song_picker_catalog: dict | None,
    song_library: dict | None,
    catalog_session: dict[str, Any] | None,
    loaded_genre_title: tuple[str, str] | None = None,
) -> dict[str, Any]:
    sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    overlay = dict(catalog_song_data or {})
    source_type = "catalog"
    pk = str(reconciled_pick_key or "").strip()
    if pk.startswith("custom::"):
        source_type = "custom"
    elif not pk:
        source_type = "unknown"
    return {
        "reconciled_pick_key": pk or "(empty)",
        "source_type": source_type,
        "pick_key_in_song_picker_catalog": _pick_in_catalog(pk, song_picker_catalog),
        "pick_key_in_song_library": bool(
            pk and song_library is not None and canonical is not None
        ),
        "catalog_lookup_result_type": type(canonical).__name__ if canonical is not None else "None",
        "catalog_lookup_keys": _safe_keys(canonical),
        "merged_keys": _safe_keys(merged),
        "overlay_keys": _safe_keys(overlay),
        "selected_song_keys": _safe_keys(sel),
        "merged_top_level_key": str(merged.get("key") or "").strip() or "(missing)",
        "merged_top_level_original_key": str(merged.get("original_key") or "").strip() or "(missing)",
        "canonical_top_level_key": str((canonical or {}).get("key") or "").strip() or "(missing)",
        "canonical_top_level_original_key": str((canonical or {}).get("original_key") or "").strip()
        or "(missing)",
        "catalog_session_original_key": str((catalog_session or {}).get("original_key") or "").strip()
        or "(missing)",
        "title": str(merged.get("title") or sel.get("title") or "").strip() or "(missing)",
        "genre": str(merged.get("genre") or sel.get("genre") or "").strip() or "(missing)",
        "has_sections": bool(merged.get("sections")),
        "overlay_had_empty_key": "key" in overlay and not str(overlay.get("key") or "").strip(),
        "overlay_replaced_sections_only": bool(overlay.get("sections")) and not str(overlay.get("key") or "").strip(),
        "resolve_provenance": provenance or "(none)",
        "loaded_genre_title": loaded_genre_title,
    }


def resolve_catalog_song_for_chart(
    session_state: dict[str, Any],
    catalog_song_data: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> tuple[dict[str, Any], str]:
    """Return canonical song_data + original_key for chart transpose."""
    from music_theory import MissingOriginalSongKeyError
    from songs.state import (
        SELECTED_SONG_STATE_KEY,
        load_catalog_song_record_by_pick_key,
        reconcile_active_pick_key,
    )

    if song_picker_catalog is None:
        from songs.music_source import _catalog_picker_from_session

        song_picker_catalog = _catalog_picker_from_session(session_state)
    if song_library is None:
        from songs.music_source import _catalog_library_from_session

        song_library = _catalog_library_from_session(session_state)

    catalog_session = None
    try:
        from source_session_state import get_catalog_session

        catalog_session = get_catalog_session(session_state)
    except ImportError:
        catalog_session = session_state.get("catalog_session")
        if not isinstance(catalog_session, dict):
            catalog_session = None

    overlay = dict(catalog_song_data or {})
    sel = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    if isinstance(sel, dict) and sel:
        overlay = merge_chart_song_overlay(overlay, sel)
    if isinstance(catalog_session, dict):
        cs_sel = catalog_session.get("selected_song")
        if isinstance(cs_sel, dict) and cs_sel:
            overlay = merge_chart_song_overlay(overlay, cs_sel)
        if catalog_session.get("original_key"):
            overlay = merge_chart_song_overlay(
                overlay,
                {"original_key": catalog_session.get("original_key")},
            )

    reconciled_pk = ""
    if song_picker_catalog is not None:
        reconciled_pk = reconcile_active_pick_key(
            session_state,
            song_picker_catalog=song_picker_catalog,
        )
    pk = str(reconciled_pk or overlay.get("pick_key") or "").strip()

    canonical: dict[str, Any] | None = None
    provenance = "overlay_only"
    loaded_gt: tuple[str, str] | None = None

    if pk and not pk.startswith("custom::") and song_picker_catalog is not None and song_library is not None:
        loaded = load_catalog_song_record_by_pick_key(
            pk,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
        if loaded is not None:
            genre, title, canonical = loaded
            loaded_gt = (genre, title)
            provenance = "catalog_pick_key_load"
        else:
            provenance = "pick_key_load_failed"

    if canonical is None and song_picker_catalog is not None:
        title = str(overlay.get("title") or sel.get("title") or "").strip()
        genre = str(overlay.get("genre") or sel.get("genre") or "").strip()
        if genre and title:
            lib_row = (song_library or {}).get(genre, {}).get(title) if isinstance(song_library, dict) else None
            picker_label = None
            for lab, row in (song_picker_catalog.get(genre) or {}).items():
                if str(row.get("title") or "") == title:
                    picker_label = lab
                    canonical = dict(row)
                    if isinstance(lib_row, dict) and lib_row:
                        canonical = merge_chart_song_overlay(canonical, lib_row)
                    provenance = "title_genre_picker_library"
                    loaded_gt = (genre, title)
                    break

    if canonical:
        merged = merge_chart_song_overlay(canonical, overlay)
    else:
        merged = dict(overlay)

    if pk and not merged.get("pick_key"):
        merged["pick_key"] = pk
    if loaded_gt:
        merged.setdefault("genre", loaded_gt[0])
        merged.setdefault("title", loaded_gt[1])
    merged.setdefault("source_type", "catalog")

    original_key = resolve_original_song_key(merged, catalog_session=catalog_session)
    if not original_key:
        diag = collect_catalog_song_resolve_diagnostics(
            session_state,
            reconciled_pick_key=pk,
            catalog_song_data=catalog_song_data,
            merged=merged,
            canonical=canonical,
            provenance=provenance,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
            catalog_session=catalog_session,
            loaded_genre_title=loaded_gt,
        )
        session_state[CHART_SONG_RESOLVE_DIAG_KEY] = diag
        raise MissingOriginalSongKeyError(
            "Cannot transpose song sections because the original song key is missing."
        )

    merged["original_key"] = original_key
    merged["key"] = original_key
    session_state.pop(CHART_SONG_RESOLVE_DIAG_KEY, None)
    return merged, original_key
