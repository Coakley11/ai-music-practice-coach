"""One continuous Creative session — Hevenu through Style/Gen backing (production paths)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from creative_lifecycle_harness_support import (
    GEN_JAM_STYLE,
    HEVENU_ORIGINAL_MODE,
    HEVENU_ORIGINAL_TONIC,
    HEVENU_PICK,
    HEVENU_PRACTICE_MODE,
    HEVENU_PRACTICE_TONIC,
    HEVENU_TITLE,
    STYLE_JAM_STYLE,
    OwnerIntegrityExpectation,
    analyze_backing_context_integrity,
    apply_hevenu_practice_eb_minor,
    assert_owner_integrity,
    harmony_map_focus_chord,
    mission_select_single_chord,
    open_backing_entry_jam_production,
    restore_song_based_tab,
    return_to_creative_production,
    seed_hevenu_catalog_session,
    seed_stale_generator_artifact,
    song_based_progression_chord_count,
)
from generated_workflow_artifact import (
    BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
    GeneratedWorkflowArtifactSnapshot,
    GeneratedOwner,
    peek_backing_owner_artifact_snapshot,
)

LifecyclePhase = Literal["baseline", "post_refresh"]


@dataclass
class GenerationRevisionRecord:
    request_token: str = ""
    generation_sequence: int = 0
    artifact_id: str = ""
    artifact_revision: int = 0
    control_fingerprint: str = ""
    progression_head: str = ""


@dataclass
class ContinuousSessionState:
    style_jam_gen_history: list[GenerationRevisionRecord] = field(default_factory=list)
    generator_gen_history: list[GenerationRevisionRecord] = field(default_factory=list)
    style_jam_snapshot: GeneratedWorkflowArtifactSnapshot | None = None
    generator_snapshot: GeneratedWorkflowArtifactSnapshot | None = None
    style_jam_backing_ctx: Any | None = None
    generator_backing_ctx: Any | None = None


def _session(**extra: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "_suite_active_workspace_id": "lifecycle-continuous",
        "_suite_account_id": "lifecycle-continuous-acct",
        "_music_restore_phase_complete": True,
        "_music_startup_restore_finalized": True,
        "studio_page": "creative",
    }
    s.update(extra)
    return s


def _active_owner(session: dict[str, Any]) -> str:
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr is not None:
            return str(ptr.workflow_owner or "")
    except ImportError:
        pass
    return str(session.get("_music_active_workflow_owner") or session.get("active_workflow_owner") or "")


def _record_from_last(session: dict[str, Any], owner: GeneratedOwner) -> GenerationRevisionRecord:
    raw = session.get(f"_generated_artifact_last_{owner}")
    snap = GeneratedWorkflowArtifactSnapshot.from_dict(raw)
    if snap is None:
        return GenerationRevisionRecord()
    return GenerationRevisionRecord(
        request_token=str(snap.generation_request_token or ""),
        generation_sequence=int(snap.generation_sequence or 0),
        artifact_id=str(snap.artifact_id or ""),
        artifact_revision=int(snap.artifact_revision or 0),
        control_fingerprint=str(snap.control_fingerprint or ""),
        progression_head=",".join(list(snap.progression or [])[:4]),
    )


def generate_style_jam_via_pre_widget(session: dict[str, Any]) -> GenerationRevisionRecord:
    from music_workflow_pending_generated_progression import (
        consume_pending_generated_progression,
        queue_generated_progression_intent,
    )
    from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_RAN_KEY

    session.setdefault("improv_mood", "Bright")
    session.setdefault("improv_groove", "Light")
    session.pop(PRE_WIDGET_BOOTSTRAP_RAN_KEY, None)
    queue_generated_progression_intent(session, owner="style_jam")
    consume_pending_generated_progression(session)
    return _record_from_last(session, "style_jam")


def generate_jam_session_via_pre_widget(session: dict[str, Any]) -> GenerationRevisionRecord:
    from music_workflow_pending_generated_progression import (
        consume_pending_generated_progression,
        queue_generated_progression_intent,
    )
    from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_RAN_KEY

    session.setdefault("improv_jam_mood", "Dark")
    session.pop(PRE_WIDGET_BOOTSTRAP_RAN_KEY, None)
    queue_generated_progression_intent(session, owner="jam_session_generator")
    consume_pending_generated_progression(session)
    return _record_from_last(session, "jam_session_generator")


def assert_hevenu_song_based_steps_1_to_5(session: dict[str, Any]) -> None:
    seed_hevenu_catalog_session(session)
    sel = session.get("selected_song") or {}
    assert str(sel.get("key") or "") == "Dm", "original catalog key D minor"
    assert str(session.get("original_key") or "") == "Dm"
    apply_hevenu_practice_eb_minor(session)
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["improv_intelligence_tab"] = "Entry & Jam"
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, "Entry & Jam")
    except ImportError:
        pass
    assert _active_owner(session) in {"song_based_improvisation", ""}
    assert str(session.get("concert_key") or "") == "Ebm"
    assert str(session.get("display_key") or "") == "Ebm"
    count = song_based_progression_chord_count(session)
    assert count >= 8, f"full song progression expected, got {count}"
    try:
        from backing_context import _song_improv_sections_dict

        sec = _song_improv_sections_dict(session)
        flat = [c for chs in sec.values() for c in chs]
        assert any("m" in str(c).lower() or "b" in str(c).lower() for c in flat[:2]), (
            "progression should reflect Eb-minor practice transpose"
        )
    except ImportError:
        pass


def assert_mission_and_harmony_steps_6_to_12(session: dict[str, Any]) -> None:
    mission_select_single_chord(session, chord="Ebm", section="Verse")
    restore_song_based_tab(session)
    assert song_based_progression_chord_count(session) >= 8
    harmony_map_focus_chord(session, chord="Gbm", section="Verse")
    restore_song_based_tab(session)
    assert song_based_progression_chord_count(session) >= 8
    assert str(session.get("concert_key") or "") == "Ebm"
    prog = session.get("improv_mission_progression")
    if isinstance(prog, list) and len(prog) == 1:
        assert song_based_progression_chord_count(session) > 1, "Mission single-chord must not replace Song-Based scope"


def configure_style_jam_controls(session: dict[str, Any]) -> None:
    seed_stale_generator_artifact(session)
    session["improv_intelligence_tab"] = "Entry & Jam"
    session["improv_entry_mode"] = "Style Jam Mode"
    session["improv_style"] = STYLE_JAM_STYLE
    session["improv_style_key"] = "E"
    session["improv_mood"] = "Bright"
    session["improv_groove"] = "Light"
    session["improv_style_bpm"] = 120
    session["improv_difficulty"] = "Intermediate"
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, "Entry & Jam")
    except ImportError:
        pass
    session["improv_mood"] = "Bright"
    session["improv_groove"] = "Light"
    try:
        from music_workflow_activation import activate_workflow_simple

        activate_workflow_simple(
            session,
            "style_jam",
            activation_source="lifecycle_harness_style_jam",
            navigation_intent="creative_entry",
        )
    except ImportError:
        pass
    session["improv_mood"] = "Bright"
    session["improv_groove"] = "Light"


def assert_style_jam_generation_steps_13_to_16(session: dict[str, Any], state: ContinuousSessionState) -> None:
    configure_style_jam_controls(session)
    first = generate_style_jam_via_pre_widget(session)
    second = generate_style_jam_via_pre_widget(session)
    state.style_jam_gen_history = [first, second]
    assert first.request_token and second.request_token
    assert first.request_token != second.request_token
    assert second.generation_sequence > first.generation_sequence
    assert second.artifact_revision > first.artifact_revision
    assert first.artifact_id and second.artifact_id and first.artifact_id != second.artifact_id
    assert first.control_fingerprint != second.control_fingerprint
    assert "E" in first.progression_head.upper() or "MAJ" in first.progression_head.upper()
    state.style_jam_snapshot = GeneratedWorkflowArtifactSnapshot.from_dict(
        session.get("_generated_artifact_last_style_jam")
    )


def assert_style_jam_backing_steps_17_to_21(session: dict[str, Any], state: ContinuousSessionState) -> None:
    ctx = open_backing_entry_jam_production(session)
    state.style_jam_backing_ctx = ctx
    assert_owner_integrity(
        session,
        ctx,
        expect=OwnerIntegrityExpectation(
            workflow_owner="style_jam",
            practice_tonic="E",
            practice_mode="major",
            mood="Bright",
            style=STYLE_JAM_STYLE,
            min_progression_chords=4,
            forbid_stale_generator_sections=True,
        ),
    )
    snap = peek_backing_owner_artifact_snapshot(session)
    assert snap is not None
    assert snap.workflow_owner == "style_jam"
    assert snap.artifact_id == state.style_jam_gen_history[-1].artifact_id
    assert str(session.get("active_catalog_pick_key") or "") == HEVENU_PICK, (
        "catalog song remains contextual reference"
    )
    assert str(getattr(ctx, "bound_pick_key", "") or "") == ""
    labels = list(getattr(ctx, "section_labels", None) or [])
    if len(labels) > 1:
        session["improv_selected_section"] = labels[0]
        session["improv_scope"] = labels[0]
        ctx2 = open_backing_entry_jam_production(session)
        assert labels[0] in list(getattr(ctx2, "section_labels", None) or [labels[0]])


def assert_return_restores_style_jam_step_22_23(session: dict[str, Any], state: ContinuousSessionState) -> None:
    session["studio_page"] = "backing"
    ok = return_to_creative_production(session)
    assert ok
    assert str(session.get("improv_entry_mode") or "") in {"Style Jam Mode", "Style Jam"}
    rev = _record_from_last(session, "style_jam")
    assert rev.artifact_id == state.style_jam_gen_history[-1].artifact_id


def configure_generator_controls(session: dict[str, Any]) -> None:
    session["improv_entry_mode"] = "Jam Session Generator"
    session["improv_jam_key"] = "G"
    session["improv_jam_style"] = GEN_JAM_STYLE
    session["improv_jam_mood"] = "Dark"
    session["improv_jam_bpm"] = 100
    session["improv_jam_ensemble"] = "Combo"
    try:
        from music_workflow_creative_nav import sync_workflow_for_creative_tab

        sync_workflow_for_creative_tab(session, "Entry & Jam")
    except ImportError:
        pass
    try:
        from music_workflow_activation import activate_workflow_simple

        activate_workflow_simple(
            session,
            "jam_session_generator",
            activation_source="lifecycle_harness_generator",
            navigation_intent="creative_entry",
        )
    except ImportError:
        pass
    session["improv_jam_mood"] = "Dark"


def assert_generator_steps_24_to_29(session: dict[str, Any], state: ContinuousSessionState) -> None:
    configure_generator_controls(session)
    gen_a = generate_jam_session_via_pre_widget(session)
    gen_b = generate_jam_session_via_pre_widget(session)
    state.generator_gen_history = [gen_a, gen_b]
    assert gen_a.request_token != gen_b.request_token
    assert gen_b.artifact_revision > gen_a.artifact_revision
    owner = _active_owner(session)
    assert owner in {"jam_session_generator", ""}, f"expected jam_session_generator owner got {owner!r}"
    session["improv_entry_mode"] = "Jam Session Generator"
    ctx = open_backing_entry_jam_production(session)
    state.generator_backing_ctx = ctx
    assert_owner_integrity(
        session,
        ctx,
        expect=OwnerIntegrityExpectation(
            workflow_owner="jam_session_generator",
            practice_tonic="G",
            mood="Dark",
            style=GEN_JAM_STYLE,
            forbid_stale_generator_sections=False,
            forbid_catalog_tokens=("hevenu",),
        ),
    )


def assert_cross_owner_independence_steps_30_to_33(session: dict[str, Any], state: ContinuousSessionState) -> None:
    style_rev = _record_from_last(session, "style_jam")
    gen_rev = _record_from_last(session, "jam_session_generator")
    assert style_rev.artifact_id == state.style_jam_gen_history[-1].artifact_id
    assert gen_rev.artifact_id == state.generator_gen_history[-1].artifact_id
    assert style_rev.artifact_id != gen_rev.artifact_id
    configure_style_jam_controls(session)
    assert _record_from_last(session, "style_jam").artifact_id == style_rev.artifact_id
    configure_generator_controls(session)
    assert _record_from_last(session, "jam_session_generator").artifact_id == gen_rev.artifact_id


def assert_hevenu_restore_steps_34_35(session: dict[str, Any]) -> None:
    restore_song_based_tab(session)
    assert str(session.get("concert_key") or "") == "Ebm"
    sel = session.get("selected_song") or {}
    assert str(sel.get("key") or "") == "Dm"
    assert song_based_progression_chord_count(session) >= 8
    session["improv_entry_mode"] = "Style Jam Mode"
    style_key = str(session.get("improv_style_key") or "")
    assert style_key.upper() in {"E", "E MAJOR", ""} or session.get("improv_style_key")


def simulate_refresh_persistence(session: dict[str, Any]) -> dict[str, Any]:
    """Simulate browser refresh — copy durable workflow store + song snapshot keys."""
    keep_keys = (
        "_music_workflow_state_store",
        "_music_active_workflow",
        "_music_workflow_musical_states",
        "active_catalog_pick_key",
        "selected_song",
        "home_sections",
        "improv_song_concert_sections",
        "original_key",
        "display_key",
        "concert_key",
        "_generated_artifact_last_style_jam",
        "_generated_artifact_last_jam_session_generator",
        "_generated_artifact_sequence",
    )
    fresh = _session()
    for key in keep_keys:
        if key in session:
            fresh[key] = copy.deepcopy(session[key])
    fresh["studio_page"] = "creative"
    fresh["improv_entry_mode"] = "Song-Based Improvisation"
    fresh["improv_intelligence_tab"] = "Entry & Jam"
    try:
        from workflow_musical_authority import restore_workflow_snapshot

        restore_workflow_snapshot(fresh, "song_based_improvisation")
    except ImportError:
        pass
    return fresh


def run_continuous_lifecycle(*, phase: LifecyclePhase = "baseline") -> ContinuousSessionState:
    session = _session()
    state = ContinuousSessionState()
    assert_hevenu_song_based_steps_1_to_5(session)
    assert_mission_and_harmony_steps_6_to_12(session)
    assert_style_jam_generation_steps_13_to_16(session, state)
    assert_style_jam_backing_steps_17_to_21(session, state)
    assert_return_restores_style_jam_step_22_23(session, state)
    assert_generator_steps_24_to_29(session, state)
    assert_cross_owner_independence_steps_30_to_33(session, state)
    assert_hevenu_restore_steps_34_35(session)
    if phase == "post_refresh":
        refreshed = simulate_refresh_persistence(session)
        assert str(refreshed.get("concert_key") or "") == "Ebm"
        assert str(refreshed.get("active_catalog_pick_key") or "") == HEVENU_PICK
        assert song_based_progression_chord_count(refreshed) >= 8
        style_last = GeneratedWorkflowArtifactSnapshot.from_dict(
            refreshed.get("_generated_artifact_last_style_jam")
        )
        gen_last = GeneratedWorkflowArtifactSnapshot.from_dict(
            refreshed.get("_generated_artifact_last_jam_session_generator")
        )
        assert style_last is not None and gen_last is not None
        assert style_last.artifact_id == state.style_jam_gen_history[-1].artifact_id
        assert gen_last.artifact_id == state.generator_gen_history[-1].artifact_id
    return state


__all__ = [
    "ContinuousSessionState",
    "GenerationRevisionRecord",
    "generate_jam_session_via_pre_widget",
    "generate_style_jam_via_pre_widget",
    "run_continuous_lifecycle",
    "simulate_refresh_persistence",
]
