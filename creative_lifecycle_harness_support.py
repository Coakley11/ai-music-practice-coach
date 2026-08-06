"""Shared helpers for Creative lifecycle corruption harness (production paths only)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from song_catalog.catalog import format_pick_key

HEVENU_PICK = format_pick_key("Jewish", "Hevenu Shalom Aleichem — Traditional")
HEVENU_TITLE = "Hevenu Shalom Aleichem"
HEVENU_ORIGINAL_TONIC = "D"
HEVENU_ORIGINAL_MODE = "minor"
HEVENU_PRACTICE_TONIC = "Eb"
HEVENU_PRACTICE_MODE = "minor"

HEVENU_SECTIONS: dict[str, list[str]] = {
    "Verse": ["Dm", "Gm", "A7", "Dm"],
    "Chorus": ["F", "C", "Dm", "Am"],
}

STALE_GENERATOR_SECTIONS: dict[str, list[str]] = {
    "Jewish ballad": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
}

STYLE_JAM_STYLE = "Jazz Swing"
GEN_JAM_STYLE = "Latin Fusion"

HARNESS_TRACE_KEY = "_creative_lifecycle_harness_trace"

PK_SAY_POP = format_pick_key("Pop", "Say — John Mayer")


def append_trace(session: dict[str, Any], step: str, **payload: Any) -> None:
    bucket = session.get(HARNESS_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"step": step, **payload})
    session[HARNESS_TRACE_KEY] = bucket[-64:]


def seed_hevenu_catalog_session(session: dict[str, Any]) -> None:
    """Active catalog song Hevenu D minor with full section map (production keys)."""
    payload = {
        "active_catalog_pick_key": HEVENU_PICK,
        "selected_song": {
            "pick_key": HEVENU_PICK,
            "title": HEVENU_TITLE,
            "artist": "Traditional",
            "key": "Dm",
            "genre": "Jewish",
            "sections": copy.deepcopy(HEVENU_SECTIONS),
        },
        "song": HEVENU_TITLE,
        "home_sections": copy.deepcopy(HEVENU_SECTIONS),
        "original_key": "Dm",
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
    }
    try:
        from session_widget_safe import safe_session_assign

        for key, value in payload.items():
            safe_session_assign(session, key, value, widget_safe=True)
        safe_session_assign(session, "display_key", "Dm", widget_safe=True)
        safe_session_assign(session, "concert_key", "Dm", widget_safe=True)
    except ImportError:
        payload["display_key"] = "Dm"
        payload["concert_key"] = "Dm"
        session.update(payload)
    append_trace(session, "seed_hevenu", pick=HEVENU_PICK)


def apply_hevenu_practice_eb_minor(session: dict[str, Any]) -> None:
    """Set saved practice key Eb minor via song improv sync (production)."""
    try:
        from session_widget_safe import safe_session_assign

        safe_session_assign(session, "display_key", "Ebm", widget_safe=True)
        safe_session_assign(session, "concert_key", "Ebm", widget_safe=True)
    except ImportError:
        session["display_key"] = "Ebm"
        session["concert_key"] = "Ebm"
    try:
        from workflow_musical_authority import save_workflow_snapshot
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sections = sync_song_improv_sections_to_practice_key(session)
        save_workflow_snapshot(session, "song_based_improvisation")
        append_trace(
            session,
            "practice_eb_minor",
            chord_count=sum(len(v) for v in (sections or {}).values()),
        )
    except ImportError:
        append_trace(session, "practice_eb_minor", error="sync_unavailable")


def simulate_style_jam_backing_open_with_entry_widget_lag(session: dict[str, Any]) -> None:
    """Continuous-session state at Style Jam → Backing click when entry radio lags on Song-Based."""
    session["improv_intelligence_tab"] = "Entry & Jam"
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["improv_style"] = STYLE_JAM_STYLE
    session["improv_style_key"] = "E"
    session["improv_mood"] = "Bright"
    session["improv_groove"] = "Light"
    session["improv_style_bpm"] = 120
    style_sections = {
        f"{STYLE_JAM_STYLE} · A": ["Emaj7", "C#m7", "F#m7", "B7"],
    }
    session["improv_generated_sections"] = copy.deepcopy(style_sections)
    try:
        from music_workflow_generated_session import commit_style_jam_generation

        commit_style_jam_generation(
            session,
            key_center="E",
            style=STYLE_JAM_STYLE,
            section_map=style_sections,
            mood="Bright",
            groove="Light",
            tempo_bpm=120,
            new_session=True,
        )
    except ImportError:
        pass
    session["improv_mood"] = "Bright"
    session["improv_groove"] = "Light"
    session.pop("improv_generated_sections", None)
    session["display_key"] = "C"
    session["concert_key"] = "C"
    append_trace(session, "style_jam_entry_lag", display_key="C")


def apply_style_jam_backing_open_entry_lag(session: dict[str, Any]) -> None:
    """Entry-radio / sidebar lag overlay after a successful Style Jam generate (blob already committed)."""
    session["improv_intelligence_tab"] = "Entry & Jam"
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["display_key"] = "C"
    session["concert_key"] = "C"
    session.pop("improv_generated_sections", None)
    append_trace(session, "style_jam_entry_lag_overlay", display_key="C")


def seed_stale_generator_artifact(session: dict[str, Any], *, gen_id: str = "stale-gen-eb-harness") -> None:
    """Stale Generator blob + legacy jam session (simulates prior session before Style Jam attempt)."""
    session["improv_jam_session"] = {
        "id": gen_id,
        "sections": copy.deepcopy(STALE_GENERATOR_SECTIONS),
    }
    session["improv_jam_key"] = "Eb"
    session["improv_jam_style"] = "Jewish ballad"
    session["improv_jam_mood"] = "Mellow"
    session.setdefault("display_key", "C")
    session.setdefault("concert_key", "C")
    append_trace(session, "seed_stale_generator", gen_id=gen_id)


def mission_select_single_chord(session: dict[str, Any], *, chord: str = "Dm", section: str = "Verse") -> None:
    try:
        from workflow_musical_authority import save_workflow_snapshot

        save_workflow_snapshot(session, "song_based_improvisation")
    except ImportError:
        pass
    session["improv_intelligence_tab"] = "Missions"
    session["ii_selected_chord"] = chord
    session["II_SELECTED_CHORD"] = chord
    session["ii_selected_section"] = section
    session["II_SELECTED_SECTION"] = section
    session["improv_mission_progression"] = [chord]
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, "Missions")
    except ImportError:
        pass
    append_trace(session, "mission_focus", chord=chord, section=section)


def harmony_map_focus_chord(session: dict[str, Any], *, chord: str = "Gm", section: str = "Verse") -> None:
    session["improv_intelligence_tab"] = "Harmony Map"
    session["creative_improv_intelligence_tab"] = "Harmony Map"
    session["harmony_map_chord"] = chord
    session["harmony_map_section"] = section
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, "Harmony Map")
    except ImportError:
        pass
    append_trace(session, "harmony_focus", chord=chord, section=section)


def restore_song_based_tab(session: dict[str, Any]) -> None:
    session["improv_intelligence_tab"] = "Entry & Jam"
    session["creative_improv_intelligence_tab"] = "Entry & Jam"
    session["improv_entry_mode"] = "Song-Based Improvisation"
    try:
        from music_workflow_creative_nav import (
            ensure_creative_tab_workflow_before_widgets,
            sync_workflow_for_creative_tab,
        )
        from workflow_musical_authority import restore_workflow_snapshot

        sync_workflow_for_creative_tab(session, "Entry & Jam")
        restore_workflow_snapshot(session, "song_based_improvisation")
        ensure_creative_tab_workflow_before_widgets(session)
    except ImportError:
        pass
    append_trace(session, "restore_song_based")


def song_based_progression_chord_count(session: dict[str, Any]) -> int:
    try:
        from backing_context import _song_improv_sections_dict

        sec = _song_improv_sections_dict(session)
        return sum(len(v) for v in sec.values())
    except ImportError:
        raw = session.get("improv_song_concert_sections") or session.get("home_sections") or {}
        if isinstance(raw, dict):
            return sum(len(v) for v in raw.values() if isinstance(v, list))
        return 0


def open_backing_entry_jam_production(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    from backing_context import open_backing_from_creative

    sync_creative_before_open(session)
    ctx = open_backing_from_creative(session, source="entry_jam", st_like=st_like)
    append_trace(session, "open_backing_entry_jam", source=ctx.source, entry_mode=ctx.entry_mode)
    return ctx


def sync_creative_before_open(session: dict[str, Any]) -> None:
    try:
        from creative_key_sync import sync_creative_style_jam_meta
        from creative_session_state import sync_creative_session_from_session

        sync_creative_style_jam_meta(session)
        sync_creative_session_from_session(session)
    except ImportError:
        pass


def return_to_creative_production(session: dict[str, Any], *, st_like: Any | None = None) -> bool:
    try:
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            prepare_return_to_backing_source,
            rehydrate_creative_from_backing_context,
        )

        session.setdefault("studio_page", "backing")
        prepare_return_to_backing_source(session)
        session["studio_page"] = "creative"
        if session.get(CREATIVE_RESTORE_FROM_BACKING_KEY):
            rehydrate_creative_from_backing_context(session, st_like=st_like)
        try:
            from studio_page_state import ensure_improv_entry_mode_restored

            ensure_improv_entry_mode_restored(session)
        except ImportError:
            pass
        append_trace(session, "return_creative", ok=True)
        return True
    except ImportError:
        append_trace(session, "return_creative", ok=False)
        return False


def resolved_backing_workflow_type(session: dict[str, Any], ctx: Any) -> str:
    try:
        from workflow_musical_authority import workflow_type_from_backing_source

        return workflow_type_from_backing_source(
            str(getattr(ctx, "source", "") or ""),
            entry_mode=str(getattr(ctx, "entry_mode", "") or session.get("improv_entry_mode") or ""),
        )
    except ImportError:
        return ""


def resolve_entry_mode_for_backing(session: dict[str, Any], ctx: Any | None = None) -> str:
    try:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        return resolve_entry_jam_entry_mode(session, ctx=ctx)
    except ImportError:
        return str(session.get("improv_entry_mode") or "")


@dataclass
class OwnerIntegrityExpectation:
    workflow_owner: Literal["style_jam", "jam_session_generator", "song_based_improvisation"]
    practice_tonic: str = ""
    practice_mode: str = ""
    mood: str = ""
    style: str = ""
    min_progression_chords: int = 1
    forbid_catalog_tokens: tuple[str, ...] = ("jewish", "hevenu", "ballad")
    forbid_stale_generator_sections: bool = False


@dataclass
class OwnerIntegrityResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)


def analyze_backing_context_integrity(
    session: dict[str, Any],
    ctx: Any,
    *,
    expect: OwnerIntegrityExpectation,
) -> OwnerIntegrityResult:
    """Assert single-owner backing card contract (target behavior — fails on current hybrid builds)."""
    violations: list[str] = []
    sources: dict[str, str] = {}

    entry_resolved = resolve_entry_mode_for_backing(session, ctx)
    wf_type = resolved_backing_workflow_type(session, ctx)
    sources["entry_mode_resolved"] = entry_resolved
    sources["workflow_type_from_ctx"] = wf_type
    sources["ctx.entry_mode"] = str(getattr(ctx, "entry_mode", "") or "")
    sources["ctx.concert_key"] = str(getattr(ctx, "concert_key", "") or "")
    sources["ctx.display_key"] = str(getattr(ctx, "display_key", "") or "")
    sources["session.display_key"] = str(session.get("display_key") or "")
    sources["ctx.mood"] = str(getattr(ctx, "mood", "") or "")
    sources["ctx.style"] = str(getattr(ctx, "style", "") or "")
    sources["ctx.groove"] = str(getattr(ctx, "groove", "") or "")
    sources["ctx.bound_pick_key"] = str(getattr(ctx, "bound_pick_key", "") or "")
    sources["progression_head"] = ",".join(list(getattr(ctx, "progression", None) or [])[:4])
    sources["section_labels"] = ",".join(list(getattr(ctx, "section_labels", None) or [])[:3])

    bound_pick = str(getattr(ctx, "bound_pick_key", "") or "")
    if expect.workflow_owner in {"style_jam", "jam_session_generator"} and bound_pick:
        if "hevenu" in bound_pick.lower() or bound_pick.startswith("Jewish|"):
            violations.append(
                f"bound_pick_owner=catalog_song actual={bound_pick} (build_entry_jam_context._current_pick_key)"
            )

    if expect.workflow_owner == "style_jam":
        if wf_type != "style_jam":
            violations.append(f"WORKFLOW_OWNER_INTEGRITY_FAILURE expected_owner=style_jam actual_card_owner={wf_type}")
        if entry_resolved != "Style Jam Mode":
            violations.append(
                f"entry_mode_resolved={entry_resolved} (stale improv_jam_session heuristic may force Generator)"
            )
    elif expect.workflow_owner == "jam_session_generator":
        if wf_type != "jam_session_generator":
            violations.append(
                f"WORKFLOW_OWNER_INTEGRITY_FAILURE expected_owner=jam_session_generator actual_card_owner={wf_type}"
            )

    concert = str(getattr(ctx, "concert_key", "") or getattr(ctx, "display_key", "") or "")
    if expect.practice_tonic and expect.practice_tonic.upper() not in concert.upper().replace("M", ""):
        if concert in {"C", "C major"} or str(session.get("display_key") or "").strip() in {"C", "C major"}:
            violations.append(
                f"key_owner=legacy_compatibility/global display_key C actual_concert={concert} expected_tonic={expect.practice_tonic}"
            )

    if expect.mood and expect.mood.lower() not in str(getattr(ctx, "mood", "") or "").lower():
        violations.append(f"mood expected={expect.mood} actual={getattr(ctx, 'mood', '')} (default Mellow leak)")

    style_blob = f"{getattr(ctx, 'style', '')}|{getattr(ctx, 'groove', '')}|{sources['section_labels']}".lower()
    for token in expect.forbid_catalog_tokens:
        if token in style_blob and token not in str(session.get("improv_style") or "").lower():
            violations.append(f"metadata_owner=catalog_song token={token} in backing card fields")

    prog = list(getattr(ctx, "progression", None) or [])
    if expect.forbid_stale_generator_sections and prog:
        head = " ".join(prog[:4]).upper()
        if "EBMAJ7" in head or "FM7" in head:
            violations.append(f"progression_owner=old_generator_artifact chords={head[:40]}")

    if expect.min_progression_chords and len(prog) < expect.min_progression_chords:
        violations.append(f"progression too short len={len(prog)}")

    try:
        from workflow_musical_authority import validate_workflow_consistency

        diag = validate_workflow_consistency(session, ctx)
        for v in diag.get("violations") or []:
            violations.append(str(v))
    except ImportError:
        pass

    return OwnerIntegrityResult(ok=not violations, violations=violations, field_sources=sources)


def assert_owner_integrity(
    session: dict[str, Any],
    ctx: Any,
    *,
    expect: OwnerIntegrityExpectation,
) -> None:
    result = analyze_backing_context_integrity(session, ctx, expect=expect)
    if not result.ok:
        msg = "\n".join(result.violations + [f"  {k}={v}" for k, v in result.field_sources.items()])
        raise AssertionError(msg)


def seed_say_song_based_creative_state(
    session: dict[str, Any],
    *,
    say_pick: str = PK_SAY_POP,
    section_count: int = 144,
) -> None:
    """Prior Creative session saved on Say — John Mayer (song-based workflow blob + pointer)."""
    from music_workflow_state_store import (
        ActiveWorkflowPointer,
        KeyAuthority,
        WorkflowStateBlob,
        save_workflow_blob,
        set_active_workflow_pointer,
    )

    sections = {"Full Song": ["G"] * section_count}
    session.update(
        {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Entry & Jam",
            "active_catalog_pick_key": say_pick,
            "selected_song": {
                "pick_key": say_pick,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            "song": "Say",
            "display_key": "G",
            "concert_key": "G",
            "improv_song_concert_sections": copy.deepcopy(sections),
        }
    )
    blob = WorkflowStateBlob(
        workflow_owner="song_based_improvisation",
        workflow_session_id=say_pick,
        keys=KeyAuthority(practice_tonic="G", practice_mode="major", original_tonic="G", original_mode="major"),
        section_map=copy.deepcopy(sections),
        song_id=say_pick,
        song_title="Say",
    )
    save_workflow_blob(session, blob, source="harness_say_seed")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="song_based_improvisation", workflow_session_id=say_pick),
        source="harness_say_seed",
    )
    try:
        from workflow_musical_authority import save_workflow_snapshot

        save_workflow_snapshot(session, "song_based_improvisation")
    except ImportError:
        pass
    append_trace(session, "seed_say_creative", pick=say_pick, chords=section_count)


def simulate_picker_to_creative_handoff(
    session: dict[str, Any],
    *,
    catalog: dict[str, dict[str, dict]],
    new_pick: str,
    song_library: dict | None = None,
) -> dict[str, Any]:
    """Production-order path: Song Selection pick → navigate Creative (pre-widget + canonical)."""
    from unittest.mock import MagicMock, patch

    from music_persistent_state import prepare_canonical_music_page_state
    from music_workflow_pending_activation import queue_workflow_activation_for_entry_mode
    from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
    from songs.state import apply_pick_key
    from studio_page_persistence import _ACTIVE_PAGE_TRACKER, handle_studio_page_transition

    session["studio_page"] = "picker"
    session[_ACTIVE_PAGE_TRACKER] = "picker"
    st = MagicMock(session_state=session)
    with patch("songs.state.persist_music_local_state"):
        apply_pick_key(st, new_pick, catalog, song_library=song_library)
    try:
        from songs.music_source import resolve_catalog_song_for_pick

        _sel, _ok = resolve_catalog_song_for_pick(
            session,
            new_pick,
            song_picker_catalog=catalog,
            authoritative_transport=True,
        )
        if isinstance(_sel, dict) and _sel.get("sections"):
            session["home_sections"] = copy.deepcopy(_sel.get("sections"))
    except ImportError:
        pass
    session["studio_page"] = "creative"
    session["_script_run_seq"] = int(session.get("_script_run_seq") or 0) + 1
    session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
    session.pop("_music_canonical_prepared_for_run", None)
    queue_workflow_activation_for_entry_mode(session)
    handle_studio_page_transition(session)
    phases = run_pre_widget_application_consumers(session)
    prepare_canonical_music_page_state(
        session,
        song_picker_catalog=catalog,
        song_library=song_library,
        force=True,
    )
    try:
        from creative_session_state import (
            apply_creative_session_to_session,
            creative_session_is_active,
            get_creative_session,
        )

        sess = get_creative_session(session)
        if sess is not None and creative_session_is_active(session):
            apply_creative_session_to_session(session, sess, widget_safe=False)
    except ImportError:
        pass
    append_trace(
        session,
        "picker_to_creative",
        pick=session.get("active_catalog_pick_key"),
        song=session.get("song"),
        phases=phases,
    )
    return phases

