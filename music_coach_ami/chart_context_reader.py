"""Read-only active chart harmony for Music Coach — consumer only, no chart writes."""

from __future__ import annotations

from typing import Any


def _clean(text: object) -> str:
    return str(text or "").strip()


def _sections_dict(raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, chords in raw.items():
        if not isinstance(chords, list):
            continue
        cleaned = [_clean(c) for c in chords if _clean(c)]
        if cleaned:
            out[_clean(name)] = cleaned
    return out


def _pick_active_section(section_names: list[str], requested: str) -> str:
    req = _clean(requested)
    if req and req in section_names:
        return req
    if req:
        req_low = req.lower()
        for name in section_names:
            if name.lower() == req_low:
                return name
    return section_names[0] if section_names else ""


def _practice_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    snap = ctx.get("practice_snapshot")
    return snap if isinstance(snap, dict) else {}


def _catalog_handles(session: dict[str, Any]) -> tuple[dict[str, dict[str, dict]] | None, dict[str, dict[str, dict]] | None, str]:
    """Session catalog handles, else canonical load_song_catalog() — same owner as the app."""
    picker = None
    library = None
    source = "none"
    try:
        from songs.music_source import _catalog_library_from_session, _catalog_picker_from_session

        picker = _catalog_picker_from_session(session)
        library = _catalog_library_from_session(session)
        if picker and library:
            source = "session"
    except ImportError:
        pass
    if not picker or not library:
        try:
            from song_catalog.catalog import load_song_catalog

            library, picker, _, _ = load_song_catalog()
            source = "load_song_catalog"
        except ImportError:
            pass
    return picker, library, source


def resolve_authoritative_pick_key(
    session_state: dict[str, Any],
    *,
    ami_ctx: dict[str, Any] | None = None,
    pick_key_hint: str = "",
) -> tuple[str, dict[str, str]]:
    """Resolve catalog pick key from the same owners the app uses (never title lookup)."""
    ctx = dict(ami_ctx or {})
    session = session_state if isinstance(session_state, dict) else {}
    snap = _practice_snapshot(ctx)
    trace: dict[str, str] = {
        "param_pick_key": _clean(pick_key_hint),
        "ctx_pick_key": _clean(ctx.get("pick_key")),
        "snap_pick_key": _clean(snap.get("pick_key")),
        "session_active_catalog_pick_key": "",
        "selected_song_pick_key": "",
        "active_song_state_pick_key": "",
        "reconciled_pick_key": "",
    }
    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        trace["session_active_catalog_pick_key"] = _clean(session.get(ACTIVE_CATALOG_PICK_KEY))
        sel = session.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict):
            trace["selected_song_pick_key"] = _clean(sel.get("pick_key"))
        try:
            from active_song_state import ACTIVE_SONG_STATE_KEY

            meta = session.get(ACTIVE_SONG_STATE_KEY)
            if isinstance(meta, dict):
                trace["active_song_state_pick_key"] = _clean(
                    meta.get("pick_key") or meta.get("active_catalog_pick_key")
                )
        except ImportError:
            pass
    except ImportError:
        trace["session_active_catalog_pick_key"] = _clean(session.get("active_catalog_pick_key"))

    resolved = _clean(pick_key_hint)
    if not resolved:
        resolved = _clean(ctx.get("pick_key"))
    if not resolved:
        resolved = _clean(snap.get("pick_key"))
    if not resolved:
        resolved = trace["session_active_catalog_pick_key"]
    if not resolved:
        resolved = trace["selected_song_pick_key"]
    if not resolved:
        resolved = trace["active_song_state_pick_key"]
    if not resolved:
        try:
            from songs.state import SELECTED_SONG_STATE_KEY, _recover_pick_key_by_title

            picker, _, _ = _catalog_handles(session)
            sel = session.get(SELECTED_SONG_STATE_KEY) or session.get("selected_song")
            if isinstance(sel, dict) and isinstance(picker, dict) and picker:
                recovered = _recover_pick_key_by_title(sel, picker)
                if recovered:
                    resolved = _clean(recovered)
                    trace["recovered_pick_key_by_title"] = resolved
        except ImportError:
            pass
    if not resolved:
        try:
            from songs.state import reconcile_active_pick_key

            picker, _, _ = _catalog_handles(session)
            resolved = _clean(reconcile_active_pick_key(session, song_picker_catalog=picker))
            trace["reconciled_pick_key"] = resolved
        except ImportError:
            pass
    return resolved, trace


def trace_chart_candidate_sources(
    session_state: dict[str, Any],
    *,
    ami_ctx: dict[str, Any] | None = None,
    pick_key: str = "",
) -> dict[str, Any]:
    """Developer diagnostics: which chart sources had usable section maps."""
    ctx = dict(ami_ctx or {})
    session = session_state if isinstance(session_state, dict) else {}
    active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else {}

    def _count(raw: object) -> int:
        sections = _sections_dict(raw)
        return sum(len(v) for v in sections.values())

    blob_sections = 0
    try:
        from music_workflow_song_practice import song_practice_blob

        blob = song_practice_blob(session)
        if blob is not None and isinstance(blob.section_map, dict):
            blob_sections = _count(blob.section_map)
    except ImportError:
        pass

    catalog_sections = 0
    catalog_error = ""
    picker, library, catalog_source = _catalog_handles(session)
    if pick_key or isinstance(ctx.get("active_song"), dict) or session.get("selected_song"):
        try:
            from chart_level_arrangement import sections_for_level
            from songs.music_source import resolve_catalog_song_for_chart

            overlay: dict[str, Any] = {}
            active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else {}
            if active:
                overlay.update(active)
            sel = session.get("selected_song")
            if isinstance(sel, dict):
                overlay = {**overlay, **sel}
            if pick_key:
                overlay["pick_key"] = pick_key
            merged, _original = resolve_catalog_song_for_chart(
                session,
                overlay,
                song_picker_catalog=picker,
                song_library=library,
            )
            level = _clean(ctx.get("level") or session.get("level") or "Intermediate") or "Intermediate"
            catalog_sections = _count(sections_for_level(merged, level))
        except Exception as exc:
            catalog_error = f"{type(exc).__name__}: {exc}"

    return {
        "ami_ctx_chart_sections": _count(ctx.get("chart_sections")),
        "ami_ctx_active_song_chart_sections": _count(active.get("chart_sections")),
        "ami_ctx_active_song_sections_list": len(active.get("sections") or [])
        if isinstance(active.get("sections"), list)
        else 0,
        "song_practice_blob_section_map": blob_sections,
        "session_improv_song_concert_sections": _count(session.get("improv_song_concert_sections")),
        "session_home_sections": _count(session.get("home_sections")),
        "catalog_resolve_catalog_song_for_chart": catalog_sections,
        "catalog_resolve_error": catalog_error or None,
        "catalog_handle_source": catalog_source,
    }


def _catalog_overlay(session: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    overlay: dict[str, Any] = {}
    active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else {}
    if active:
        overlay.update(active)
    try:
        from songs.state import SELECTED_SONG_STATE_KEY

        sel = session.get(SELECTED_SONG_STATE_KEY)
    except ImportError:
        sel = session.get("selected_song")
    if isinstance(sel, dict):
        overlay = {**overlay, **sel}
    if ctx.get("pick_key"):
        overlay.setdefault("pick_key", ctx.get("pick_key"))
    return overlay


def _resolve_custom_sections(session: dict[str, Any]) -> tuple[dict[str, list[str]], str, str]:
    from custom_progression_lab import (
        default_active_progression,
        ensure_original_structure,
        sections_to_chord_lists,
    )
    from songs.music_source import custom_original_key

    active = ensure_original_structure(session.get("cpl_active_progression") or default_active_progression())
    sections = sections_to_chord_lists(active.get("original_sections") or {})
    original_key = _clean(custom_original_key(active)) or "C"
    return sections, original_key, "custom.original_sections"


def _resolve_catalog_sections(
    session: dict[str, Any],
    ctx: dict[str, Any],
    *,
    pick_key: str,
    harmony_level: str = "Advanced",
) -> tuple[dict[str, list[str]], str, str]:
    """Catalog sections for Coach musical ideas — full harmonic quality by default.

    Practice UI may show Beginner/Intermediate simplifications; AMI generators need
    the canonical effective chart qualities (maj7/m7/…), then Practice Key transpose.
    """
    from chart_level_arrangement import sections_for_level
    from songs.music_source import resolve_catalog_song_for_chart

    picker, library, _ = _catalog_handles(session)
    overlay = _catalog_overlay(session, ctx)
    if pick_key:
        overlay["pick_key"] = pick_key
    merged, original_key = resolve_catalog_song_for_chart(
        session,
        overlay,
        song_picker_catalog=picker,
        song_library=library,
    )
    # Full qualities for generation unless caller overrides.
    level = _clean(harmony_level) or "Advanced"
    sections = sections_for_level(merged, level)
    if not original_key:
        original_key = _clean(merged.get("key") or merged.get("original_key") or "C")
    return sections, original_key, "catalog.resolve_catalog_song_for_chart"


def resolve_coach_chart_snapshot(
    session_state: dict[str, Any],
    *,
    ami_ctx: dict[str, Any] | None = None,
    active_section: str = "",
    pick_key: str = "",
    song_original_key: str = "",
    practice_key: str = "",
) -> dict[str, Any]:
    """Layered read-only chart resolution aligned with visible Practice/Backing chart owners."""
    ctx = dict(ami_ctx or {})
    session = session_state if isinstance(session_state, dict) else {}
    snap = _practice_snapshot(ctx)
    resolved_pick_key, pick_trace = resolve_authoritative_pick_key(
        session,
        ami_ctx=ctx,
        pick_key_hint=pick_key,
    )
    candidate_trace = trace_chart_candidate_sources(session, ami_ctx=ctx, pick_key=resolved_pick_key)

    sections: dict[str, list[str]] = {}
    source = ""
    sections_source_key = ""
    original_key = _clean(song_original_key)
    meter = _clean(ctx.get("chart_meter") or ctx.get("time_signature") or "")
    bpm = ctx.get("bpm") or snap.get("bpm") or session.get("active_song_bpm")

    # 1) Explicit ami_ctx sections (tests / submit stamps).
    # Provenance: chart_sections_key if provided, else original song key (not Practice Key).
    if isinstance(ctx.get("chart_sections"), dict):
        sections = _sections_dict(ctx["chart_sections"])
        if sections:
            source = "ami_ctx.chart_sections"
            sections_source_key = _clean(ctx.get("chart_sections_key"))
            if not sections_source_key:
                active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else {}
                sections_source_key = _clean(
                    original_key
                    or active.get("key")
                    or active.get("default_key")
                    or ctx.get("original_key")
                )
            if bool(ctx.get("chart_sections_in_practice_key")):
                sections_source_key = _clean(practice_key or ctx.get("display_key") or sections_source_key)

    # 2) Catalog (full Advanced qualities) when pick key resolves — beats stale improv cache.
    if not sections and resolved_pick_key:
        try:
            cat_sections, catalog_original, catalog_source = _resolve_catalog_sections(
                session,
                ctx,
                pick_key=resolved_pick_key,
                harmony_level="Advanced",
            )
            if cat_sections:
                sections = cat_sections
                source = catalog_source
                if not original_key:
                    original_key = catalog_original
                sections_source_key = _clean(catalog_original) or sections_source_key
        except Exception:
            pass

    # 3) Song practice blob (keyed by blob practice tonic when available).
    if not sections:
        try:
            from music_workflow_song_practice import song_practice_blob

            blob = song_practice_blob(session)
            if blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
                candidate = _sections_dict(blob.section_map)
                if candidate:
                    sections = candidate
                    source = "song_practice_blob.section_map"
                    if blob.keys.original_tonic and not original_key:
                        ot = _clean(blob.keys.original_tonic)
                        om = _clean(blob.keys.original_mode).lower()
                        original_key = f"{ot}m" if om == "minor" and not ot.lower().endswith("m") else ot
                    pt = _clean(blob.keys.practice_tonic)
                    pm = _clean(blob.keys.practice_mode).lower()
                    practice_from_blob = (
                        f"{pt}m" if pm == "minor" and pt and not pt.lower().endswith("m") else pt
                    )
                    if practice_from_blob:
                        sections_source_key = practice_from_blob
        except ImportError:
            pass

    # 4) Custom progression originals.
    if not sections:
        try:
            from songs.music_source import custom_progression_is_active

            if custom_progression_is_active(session):
                sections, custom_original, custom_source = _resolve_custom_sections(session)
                if sections:
                    source = custom_source
                    if not original_key:
                        original_key = custom_original
                    sections_source_key = _clean(custom_original) or sections_source_key
        except ImportError:
            pass

    # 5) Session improv cache — only when catalog/blob unavailable (may be stale vs Practice Key).
    if not sections:
        stored = session.get("improv_song_concert_sections")
        candidate = _sections_dict(stored)
        if candidate:
            sections = candidate
            source = "session.improv_song_concert_sections"
            # Do NOT assume these match the current Practice Key — re-key via original below.
            sections_source_key = ""

    if not sections and isinstance(ctx.get("active_song"), dict):
        active = ctx["active_song"]
        sections = _sections_dict(active.get("chart_sections"))
        if sections:
            source = "ami_ctx.active_song.chart_sections"
            sections_source_key = _clean(active.get("key") or active.get("default_key"))
        if not original_key:
            original_key = _clean(active.get("key") or active.get("default_key"))

    if not sections:
        stored = session.get("home_sections")
        candidate = _sections_dict(stored)
        if candidate:
            sections = candidate
            source = "session.home_sections"
            sections_source_key = ""

    picker, library, catalog_handle_source = _catalog_handles(session)

    resolved_practice_key = _clean(practice_key or ctx.get("display_key") or session.get("display_key"))
    if not resolved_practice_key:
        try:
            from musical_context_authority import resolve_authoritative_practice_key

            auth = resolve_authoritative_practice_key(session)
            resolved_practice_key = auth.practice_key_token
            if not original_key:
                original_key = auth.original_key_token
        except ImportError:
            resolved_practice_key = resolved_practice_key or original_key or "C"

    if not original_key:
        original_key = _clean(ctx.get("original_key") or session.get("original_key") or resolved_practice_key or "C")

    # One authoritative transform: sections_source_key (or original) → Practice Key.
    from_key = _clean(sections_source_key) or _clean(original_key)
    sections_in_practice_key = bool(
        sections and from_key and resolved_practice_key and from_key == resolved_practice_key
    )
    transposed_this_resolve = False
    if (
        sections
        and not sections_in_practice_key
        and from_key
        and resolved_practice_key
        and from_key != resolved_practice_key
    ):
        try:
            from music_theory import transpose_sections_dict

            sections = transpose_sections_dict(sections, from_key, resolved_practice_key)
            source = f"{source}+transpose" if source else "transpose"
            sections_in_practice_key = True
            transposed_this_resolve = True
        except ImportError:
            pass

    if not meter and sections:
        try:
            from songs.meter import default_time_signature_for_record

            meter = _clean(default_time_signature_for_record({"sections": sections}, sections=sections)) or "4/4"
        except ImportError:
            meter = meter or "4/4"
    if not meter:
        meter = "4/4"

    section_names = list(sections.keys())
    chosen_section = _pick_active_section(section_names, active_section)
    active_chords = list(sections.get(chosen_section) or [])
    if not active_chords and section_names:
        chosen_section = section_names[0]
        active_chords = list(sections.get(chosen_section) or [])

    music_source = ""
    try:
        from active_song_state import gather_active_song_context

        song_ctx = gather_active_song_context(session)
        music_source = _clean(song_ctx.get("music_source"))
    except ImportError:
        pass

    return {
        "chart_sections": sections,
        "active_section": chosen_section,
        "active_section_chords": active_chords[:8],
        "chart_meter": meter,
        "practice_key": resolved_practice_key or "C",
        "original_key": original_key or resolved_practice_key or "C",
        "chart_source": source or "none",
        "chart_available": bool(active_chords),
        "resolved_pick_key": resolved_pick_key,
        "music_source": music_source or None,
        "bpm": int(bpm) if bpm else None,
        "pick_key_trace": pick_trace,
        "candidate_sources": candidate_trace,
        "section_names": section_names,
        "active_section_chord_count": len(active_chords),
        "sections_in_practice_key": sections_in_practice_key,
        "sections_source_key": from_key or None,
        "transposed_to_practice_key": transposed_this_resolve,
        "catalog_handle_source": catalog_handle_source,
    }
