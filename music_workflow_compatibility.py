"""Compatibility adapters — read legacy session keys without making them authoritative."""

from __future__ import annotations

from typing import Any

from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    record_compat_fallback,
    record_legacy_field_read,
)


def _read_display_key(session: dict[str, Any]) -> str:
    record_legacy_field_read(session, "display_key", adapter="compat_keys")
    return str(session.get("display_key") or "").strip()


def _read_concert_key(session: dict[str, Any]) -> str:
    record_legacy_field_read(session, "concert_key", adapter="compat_keys")
    return str(session.get("concert_key") or "").strip()


def _tonic_mode_from_token(key: str) -> tuple[str, str]:
    try:
        from music_theory import split_key_center

        tonic, mode = split_key_center(str(key or "C"))
        return tonic, mode
    except ImportError:
        pass
    try:
        from music_theory import key_is_minor, normalize_root, split_chord

        text = str(key or "C").strip() or "C"
        root, _ = split_chord(text)
        tonic = normalize_root(root) or "C"
        mode = "minor" if key_is_minor(text) else "major"
        return tonic, mode
    except ImportError:
        low = str(key or "").lower()
        return str(key or "C")[:1], "minor" if "m" in low and "maj" not in low else "major"


def build_key_authority_from_legacy(session: dict[str, Any], *, owner: str) -> KeyAuthority:
    record_compat_fallback(session, "key_authority_from_legacy", owner)
    practice_raw = _read_display_key(session) or _read_concert_key(session) or "C"
    try:
        from musical_context_authority import resolve_authoritative_practice_key

        pk = resolve_authoritative_practice_key(session)
        return KeyAuthority(
            original_tonic=pk.original_tonic,
            original_mode=pk.original_mode,
            practice_tonic=pk.practice_tonic,
            practice_mode=pk.practice_mode,
            written_tonic=str(session.get("written_key") or "").strip(),
            written_mode="",
            instrument=str(session.get("instrument") or ""),
            key_owner=owner,
        )
    except ImportError:
        pt, pm = _tonic_mode_from_token(practice_raw)
        ot, om = _tonic_mode_from_token(practice_raw)
        return KeyAuthority(
            original_tonic=ot,
            original_mode=om,
            practice_tonic=pt,
            practice_mode=pm,
            written_tonic=str(session.get("written_key") or "").strip(),
            instrument=str(session.get("instrument") or ""),
            key_owner=owner,
        )


def legacy_session_id_for_owner(session: dict[str, Any], owner: str) -> str:
    record_compat_fallback(session, "legacy_session_id", owner)
    if owner == "song_based_improvisation":
        record_legacy_field_read(session, "active_catalog_pick_key", adapter="session_id")
        return str(session.get("active_catalog_pick_key") or session.get("song") or "song").strip() or "song"
    if owner == "mission_jam":
        try:
            from music_workflow_mission_session import mission_blob_session_id

            record_legacy_field_read(session, "active_catalog_pick_key", adapter="session_id")
            return mission_blob_session_id(session)
        except ImportError:
            pass
        record_legacy_field_read(session, "active_catalog_pick_key", adapter="session_id")
        pick = str(session.get("active_catalog_pick_key") or session.get("song") or "song").strip()
        return f"mission|catalog|{pick}"
    if owner == "style_jam":
        record_legacy_field_read(session, "improv_style", adapter="session_id")
        return str(session.get("improv_style") or "style_jam").strip() or "style_jam"
    if owner == "jam_session_generator":
        record_legacy_field_read(session, "improv_jam_session", adapter="session_id")
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and jam.get("id"):
            return str(jam.get("id"))
        record_legacy_field_read(session, "improv_jam_style", adapter="session_id")
        return str(session.get("improv_jam_style") or "jam_gen").strip() or "jam_gen"
    if owner == "pending_upload_analysis":
        try:
            from mission_pending_upload_analysis import envelope_from_session_or_canonical

            env = envelope_from_session_or_canonical(session) or {}
            return str(env.get("take_id") or "pending_upload").strip()
        except ImportError:
            return "pending_upload"
    if owner == "regular_custom_backing":
        return str(session.get("active_catalog_pick_key") or "custom").strip()
    return str(session.get("active_catalog_pick_key") or "catalog").strip() or "catalog"


def build_workflow_blob_from_legacy(session: dict[str, Any], owner: str) -> WorkflowStateBlob:
    """Construct a blob snapshot from legacy keys — does not write session or store."""
    sid = legacy_session_id_for_owner(session, owner)
    keys = build_key_authority_from_legacy(session, owner=owner)
    blob = WorkflowStateBlob(
        workflow_owner=owner,
        workflow_session_id=sid,
        keys=keys,
    )
    if owner in {"song_based_improvisation", "mission_jam"}:
        record_legacy_field_read(session, "improv_song_concert_sections", adapter="sections")
        sec = session.get("improv_song_concert_sections")
        if isinstance(sec, dict):
            blob.section_map = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}
            blob.progression_owner = "improv_song_concert_sections"
        blob.song_id = str(session.get("active_catalog_pick_key") or "").strip()
        blob.song_title = str(session.get("song") or "").strip()
        blob.source_type = "catalog"
    if owner == "mission_jam":
        record_legacy_field_read(session, "ii_selected_chord", adapter="mission")
        blob.selected_chord_symbol = str(session.get("ii_selected_chord") or "").strip()
        blob.selected_section = str(session.get("ii_selected_section") or "").strip()
        try:
            blob.selected_chord_index = int(session.get("ii_selected_chord_index") or 0)
        except (TypeError, ValueError):
            blob.selected_chord_index = 0
        blob.mission_type = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
        blob.mission_id = blob.mission_type
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY

            raw = session.get(MISSION_EXAMPLE_KEY)
            if isinstance(raw, dict):
                blob.example_fingerprint = str(raw.get("material_fp") or raw.get("output_fp") or "")[:24]
                if not blob.selected_chord_symbol:
                    blob.selected_chord_symbol = str(raw.get("chord") or "")
        except ImportError:
            pass
    if owner == "style_jam":
        record_legacy_field_read(session, "improv_style", adapter="style")
        record_legacy_field_read(session, "improv_generated_sections", adapter="sections")
        record_legacy_field_read(session, "improv_style_key", adapter="style_key")
        style_key = str(session.get("improv_style_key") or "").strip()
        if style_key:
            pt, pm = _tonic_mode_from_token(style_key)
            blob.keys.practice_tonic = pt
            blob.keys.practice_mode = pm
            blob.keys.original_tonic = pt
            blob.keys.original_mode = pm
        blob.style = str(session.get("improv_style") or "").strip()
        blob.source_type = "generated"
        blob.generated_session_id = sid
        blob.style_owner = sid
        gen = session.get("improv_generated_sections")
        if isinstance(gen, dict):
            blob.section_map = {str(k): list(v) for k, v in gen.items() if isinstance(v, list)}
            blob.progression_owner = "improv_generated_sections"
        meta = session.get("improv_style_meta")
        if isinstance(meta, dict):
            blob.groove = str(meta.get("groove") or "")
            blob.mood = str(meta.get("mood") or "")
            try:
                blob.tempo_bpm = int(meta.get("bpm") or 0)
            except (TypeError, ValueError):
                pass
            blob.meter = str(meta.get("meter") or "4/4")
    if owner == "jam_session_generator":
        record_legacy_field_read(session, "improv_jam_session", adapter="sections")
        record_legacy_field_read(session, "improv_jam_key", adapter="jam_key")
        jam_key = str(session.get("improv_jam_key") or "").strip()
        if jam_key:
            pt, pm = _tonic_mode_from_token(jam_key)
            blob.keys.practice_tonic = pt
            blob.keys.practice_mode = pm
        blob.source_type = "generated"
        blob.generated_session_id = sid
        blob.style = str(session.get("improv_jam_style") or "").strip()
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            sections = jam.get("sections")
            if isinstance(sections, dict):
                blob.section_map = {str(k): list(v) for k, v in sections.items() if isinstance(v, list)}
                blob.progression_owner = "improv_jam_session"
    if owner == "pending_upload_analysis":
        blob.source_type = "pending"
        try:
            from mission_pending_upload_analysis import envelope_from_session_or_canonical

            env = envelope_from_session_or_canonical(session) or {}
            blob.pending_analysis_take_id = str(env.get("take_id") or "")
            blob.page_route = "analysis"
        except ImportError:
            pass
    blob.page_route = str(session.get("studio_page") or blob.page_route or "").strip()
    record_legacy_field_read(session, "improv_intelligence_tab", adapter="route")
    record_legacy_field_read(session, "improv_entry_mode", adapter="route")
    return blob


def peek_legacy_inferred_owner(session: dict[str, Any]) -> str:
    """Non-authoritative hint for dev panel only."""
    record_compat_fallback(session, "peek_legacy_inferred_owner", "dev_only")
    page = str(session.get("studio_page") or "").strip().lower()
    tab = str(session.get("improv_intelligence_tab") or "").strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if page == "analysis":
        return "pending_upload_analysis"
    if tab == "Missions":
        return "mission_jam"
    if entry == "Jam Session Generator":
        return "jam_session_generator"
    if entry == "Style Jam Mode":
        return "style_jam"
    if entry == "Song-Based Improvisation":
        return "song_based_improvisation"
    try:
        from backing_context import get_backing_context
        from workflow_musical_authority import workflow_type_from_backing_source

        ctx = get_backing_context(session)
        if ctx is not None:
            return workflow_type_from_backing_source(
                str(ctx.source or ""),
                entry_mode=str(ctx.entry_mode or entry),
            )
    except ImportError:
        pass
    return ""


COMPAT_ADAPTER_REGISTRY: tuple[str, ...] = (
    "key_authority_from_legacy",
    "legacy_session_id",
    "peek_legacy_inferred_owner",
    "build_workflow_blob_from_legacy",
)


__all__ = [
    "COMPAT_ADAPTER_REGISTRY",
    "build_key_authority_from_legacy",
    "build_workflow_blob_from_legacy",
    "legacy_session_id_for_owner",
    "peek_legacy_inferred_owner",
]
