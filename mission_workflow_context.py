"""Mission workflow context isolation — no Entry Jam / stale jam section leaks."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Literal

WORKFLOW_MISSIONS = "mission_practice"
WORKFLOW_ENTRY_JAM = "entry_jam"

MISSION_CONTEXT_DIAG_KEY = "_mission_workflow_context_diag"
MISSION_IGNORE_GENERATED_SECTIONS_KEY = "_missions_ignore_improv_generated_sections"

Violation = Literal[
    "CREATIVE_SONG_CONTEXT_MISMATCH",
    "ENTRY_JAM_CONTEXT_LEAK",
    "MISSION_CONTEXT_LEAK",
    "STYLE_OWNER_MISMATCH",
    "PROGRESSION_OWNER_MISMATCH",
    "ARTIFACT_OWNER_MISMATCH",
    "MISSION_CHORD_CONTEXT_MISMATCH",
]


@dataclass
class MissionContextReport:
    ok: bool
    violations: list[str]
    cleared_keys: list[str]
    progression_owner: str
    style_owner: str
    workflow_type: str
    song_title: str
    pick_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _catalog_sections_from_session(
    session: dict[str, Any],
    improv_ctx: Any,
) -> list[tuple[str, list[str]]]:
    from improvisation_motif import (
        concert_song_sections_from_session,
        dedupe_sections_for_display,
        flatten_sections,
    )

    concert = concert_song_sections_from_session(session)
    if concert:
        order = list(getattr(improv_ctx, "section_order", None) or concert.keys())
        mapped = dedupe_sections_for_display(concert, section_names=order or None)
        if mapped:
            return mapped
    home = session.get("home_sections")
    if isinstance(home, dict) and home:
        order = list(getattr(improv_ctx, "section_order", None) or home.keys())
        mapped = dedupe_sections_for_display(home, section_names=order or None)
        if mapped:
            return mapped
    if improv_ctx.sections and isinstance(improv_ctx.sections, dict):
        order = list(getattr(improv_ctx, "section_order", None) or improv_ctx.sections.keys())
        mapped = dedupe_sections_for_display(improv_ctx.sections, section_names=order or None)
        if mapped:
            return mapped
    flat = list(getattr(improv_ctx, "progression_flat", None) or [])
    if not flat and improv_ctx.sections:
        flat = flatten_sections(improv_ctx.sections, section_names=list(improv_ctx.sections.keys()))
    if flat:
        return [("Progression", flat)]
    return []


def resolve_missions_section_map(
    session: dict[str, Any],
    improv_ctx: Any,
) -> tuple[list[tuple[str, list[str]]], str]:
    """Authoritative sections for Missions — never Entry Jam ``improv_generated_sections``."""
    session[MISSION_IGNORE_GENERATED_SECTIONS_KEY] = True
    mapped = _catalog_sections_from_session(session, improv_ctx)
    if mapped:
        return mapped, "catalog_song_sections"
    gen = session.get("improv_generated_sections")
    if gen:
        return [], "entry_jam_leak_blocked"
    return [], "none"


def _deactivate_entry_jam_transient_for_missions(session: dict[str, Any]) -> list[str]:
    cleared: list[str] = []
    session[MISSION_IGNORE_GENERATED_SECTIONS_KEY] = True
    for key in (
        "improv_jam_key",
        "improv_style_key",
        "improv_jam_session",
        "improv_mission_backing_handoff",
        "_backing_mission_ui_suppressed",
    ):
        if key in session:
            session.pop(key, None)
            cleared.append(key)
    try:
        from backing_session_route import clear_mission_ui_suppression

        clear_mission_ui_suppression(session)
    except ImportError:
        pass
    try:
        from mission_song_backing_style import on_mission_song_pick_changed

        on_mission_song_pick_changed(session)
    except ImportError:
        pass
    try:
        from generated_jam_key_context import deactivate_generated_jam_key_ownership

        deactivate_generated_jam_key_ownership(session, pre_widget=True)
        cleared.append("_generated_jam_key_context")
    except ImportError:
        pass
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry in ("Style Jam Mode", "Jam Session Generator"):
        session["improv_entry_mode"] = "Song-Based Improvisation"
        cleared.append("improv_entry_mode→Song-Based")
    return cleared


def _style_owner(session: dict[str, Any]) -> str:
    res = session.get("_mission_jam_style_resolution")
    if isinstance(res, dict) and res.get("source"):
        return str(res["source"])
    return "session_improv_style"


def validate_missions_render_context(
    session: dict[str, Any],
    improv_ctx: Any,
    *,
    section_map: list[tuple[str, list[str]]],
    cur_chord: str,
    section_label: str,
    mission: str,
) -> MissionContextReport:
    violations: list[str] = []
    song_title = str(getattr(improv_ctx, "song_title", "") or session.get("song") or "").strip()
    pick_key = str(session.get("active_catalog_pick_key") or session.get("_active_pick_key") or "").strip()
    prog_owner = "catalog_song_sections"
    gen = session.get("improv_generated_sections")
    if gen and section_map:
        for label, _ in section_map:
            low = str(label).lower()
            if "head (" in low or "bridge (" in low or "jazz swing" in low:
                if "melody" not in low and "hora" not in low and "prayer" not in low:
                    violations.append("ENTRY_JAM_CONTEXT_LEAK")
                    violations.append("PROGRESSION_OWNER_MISMATCH")
                    prog_owner = "entry_jam_leak_detected"
                    break
    session_song = str(session.get("song") or "").strip()
    if song_title and session_song and song_title != session_song:
        violations.append("CREATIVE_SONG_CONTEXT_MISMATCH")
    flat = [c for _l, chs in section_map for c in chs]
    if cur_chord and flat and cur_chord not in flat:
        violations.append("MISSION_CHORD_CONTEXT_MISMATCH")
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        raw = session.get(MISSION_EXAMPLE_KEY)
        if isinstance(raw, dict) and raw.get("chord"):
            if str(raw.get("chord")) != str(cur_chord):
                violations.append("ARTIFACT_OWNER_MISMATCH")
            if song_title and str(raw.get("song_title") or raw.get("song") or "").strip() not in ("", song_title):
                violations.append("ARTIFACT_OWNER_MISMATCH")
    except ImportError:
        pass
    style = str(session.get("improv_style") or session.get("improv_jam_style") or "")
    if style.lower() == "jazz swing":
        owner = _style_owner(session)
        if owner not in ("explicit_user_override",) and owner != "song_metadata":
            try:
                from mission_song_backing_style import resolve_mission_jam_backing_style

                resolved = resolve_mission_jam_backing_style(session)
                if resolved.groove.lower() != "jazz swing" and resolved.source == "song_metadata":
                    violations.append("STYLE_OWNER_MISMATCH")
            except ImportError:
                violations.append("STYLE_OWNER_MISMATCH")
    return MissionContextReport(
        ok=not violations,
        violations=violations,
        cleared_keys=[],
        progression_owner=prog_owner,
        style_owner=_style_owner(session),
        workflow_type=WORKFLOW_MISSIONS,
        song_title=song_title,
        pick_key=pick_key,
    )


def reconcile_missions_workflow_context(
    session: dict[str, Any],
    improv_ctx: Any,
    *,
    mission: str,
    cur_chord: str,
    section_label: str,
) -> tuple[list[tuple[str, list[str]]], MissionContextReport]:
    cleared = _deactivate_entry_jam_transient_for_missions(session)
    try:
        from sidebar_key_identity import prime_sidebar_practice_key_from_identity

        prime_sidebar_practice_key_from_identity(session)
    except ImportError:
        pass
    if improv_ctx.sections and isinstance(improv_ctx.sections, dict):
        session["home_sections"] = {k: list(v) for k, v in improv_ctx.sections.items() if isinstance(v, list)}
    section_map, prog_owner = resolve_missions_section_map(session, improv_ctx)
    report = validate_missions_render_context(
        session,
        improv_ctx,
        section_map=section_map,
        cur_chord=cur_chord,
        section_label=section_label,
        mission=mission,
    )
    report.cleared_keys = cleared
    report.progression_owner = prog_owner
    if not report.ok:
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY

            raw = session.get(MISSION_EXAMPLE_KEY)
            if isinstance(raw, dict):
                if str(raw.get("chord") or "") != str(cur_chord) or (
                    report.song_title
                    and str(raw.get("song_title") or "").strip() not in ("", report.song_title)
                ):
                    session.pop(MISSION_EXAMPLE_KEY, None)
                    cleared.append(MISSION_EXAMPLE_KEY)
        except ImportError:
            pass
        try:
            from mission_song_backing_style import sync_mission_style_from_song

            sync_mission_style_from_song(session, force=True)
        except ImportError:
            pass
        section_map, prog_owner = resolve_missions_section_map(session, improv_ctx)
        report.progression_owner = prog_owner
        report.cleared_keys = cleared
    session[MISSION_CONTEXT_DIAG_KEY] = report.to_dict()
    return section_map, report


def ensure_mission_handoff_aligned(
    session: dict[str, Any],
    *,
    mission: str,
    cur_chord: str,
    section_label: str,
    chord_idx: int,
    song_title: str,
    example: Any | None,
) -> None:
    try:
        from music_workflow_mutation import mutate_mission_handoff_aligned

        result = mutate_mission_handoff_aligned(
            session,
            mission=mission,
            cur_chord=cur_chord,
            section_label=section_label,
            chord_idx=chord_idx,
            example=example,
        )
        if result.ok:
            return
        return
    except ImportError:
        pass


def render_mission_context_dev_panel(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    diag = dict(session.get(MISSION_CONTEXT_DIAG_KEY) or {})
    style = session.get("_mission_jam_style_resolution") or {}
    deploy = str(session.get("_studio_ui_release_sha") or "—")
    st_module.caption(
        "DEV mission context · "
        f"song `{diag.get('song_title', session.get('song', '—'))}` · "
        f"pick `{diag.get('pick_key', '—')}` · "
        f"prog_owner `{diag.get('progression_owner', '—')}` · "
        f"style_owner `{diag.get('style_owner', style.get('source', '—'))}` · "
        f"groove `{style.get('groove', '—')}` · "
        f"violations `{diag.get('violations', [])}` · "
        f"cleared `{diag.get('cleared_keys', [])}` · "
        f"ok `{diag.get('ok')}` · "
        f"sha `{deploy[:7] if deploy else '—'}`"
    )


__all__ = [
    "MISSION_CONTEXT_DIAG_KEY",
    "ensure_mission_handoff_aligned",
    "reconcile_missions_workflow_context",
    "render_mission_context_dev_panel",
    "resolve_missions_section_map",
    "validate_missions_render_context",
]
