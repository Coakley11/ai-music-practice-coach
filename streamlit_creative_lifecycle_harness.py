"""Continuous Creative lifecycle harness — Hevenu → SBI → Mission → Harmony → Style/Gen → Backing.

Uses production Creative tabs, backing_context, and navigation helpers (not direct blob mutation).
Run: streamlit run streamlit_creative_lifecycle_harness.py
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import streamlit as st

from creative_lifecycle_harness_support import (
    HEVENU_SECTIONS,
    STALE_GENERATOR_SECTIONS,
    STYLE_JAM_STYLE,
    append_trace,
    apply_hevenu_practice_eb_minor,
    harmony_map_focus_chord,
    mission_select_single_chord,
    open_backing_entry_jam_production,
    restore_song_based_tab,
    return_to_creative_production,
    seed_hevenu_catalog_session,
    seed_stale_generator_artifact,
    song_based_progression_chord_count,
)
from music_theory import ENHARMONIC_MAJOR_KEYS
from streamlit_creative_full_production_harness import (
    _lock_widgets_like_sidebar,
    _simulate_authenticated_bootstrap,
)

LIFECYCLE_STAGE_KEY = "_creative_lifecycle_stage"


def _bump_stage(session: dict[str, Any], name: str) -> None:
    session[LIFECYCLE_STAGE_KEY] = name
    append_trace(session, name)


def _improv_ctx(session: dict[str, Any]) -> Any:
    from improvisation_intelligence import ImprovSessionContext

    sections = copy.deepcopy(session.get("home_sections") or HEVENU_SECTIONS)
    return ImprovSessionContext(
        song_title=str(session.get("song") or "Hevenu Shalom Aleichem"),
        artist="Traditional",
        key_center=str(session.get("concert_key") or "Dm"),
        display_key=str(session.get("display_key") or "Dm"),
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=100,
        style_label="Jewish",
        progression_flat=[c for chs in sections.values() for c in chs],
        section_order=list(sections.keys()),
    )


def _open_backing_handler(session: dict[str, Any]) -> Callable[[], None]:
    def _go() -> None:
        open_backing_entry_jam_production(session, st_like=st)
        session["studio_page"] = "backing"
        _bump_stage(session, "backing_opened")

    return _go


def _return_from_backing_click() -> None:
    from backing_source_navigation import prepare_return_to_backing_source

    session = st.session_state
    session.setdefault("studio_page", "backing")
    prepare_return_to_backing_source(session)
    session["studio_page"] = "creative"
    session["_lifecycle_pending_return_hydrate"] = True
    _bump_stage(session, "return_creative_queued")


def _render_lifecycle_controls(session: dict[str, Any]) -> None:
    st.markdown("### Lifecycle driver (production paths)")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("1–3 Hevenu + Eb practice", key="lc_hevenu_eb"):
            apply_hevenu_practice_eb_minor(session)
            seed_stale_generator_artifact(session)
            _bump_stage(session, "hevenu_eb_practice")
    with c2:
        if st.button("4–11 Song / Mission / Harmony", key="lc_sbi_mission_harmony"):
            restore_song_based_tab(session)
            _bump_stage(session, "song_based")
            mission_select_single_chord(session)
            restore_song_based_tab(session)
            _bump_stage(session, "after_mission_return")
            harmony_map_focus_chord(session)
            restore_song_based_tab(session)
            _bump_stage(session, "after_harmony_return")
    with c3:
        if st.button(
            "Return from backing",
            key="lc_return_creative",
            on_click=_return_from_backing_click,
        ):
            pass


def _render_creative_production_shell(session: dict[str, Any]) -> None:
    from improvisation_intelligence_ui import render_improvisation_intelligence_lab

    sections = copy.deepcopy(session.get("home_sections") or HEVENU_SECTIONS)
    song_data = dict(session.get("selected_song") or {})
    ctx = {
        "song_title": str(session.get("song") or "Hevenu Shalom Aleichem"),
        "artist": "Traditional",
        "practice_concert_key": str(session.get("concert_key") or "Dm"),
        "concert_key": str(session.get("concert_key") or "Dm"),
        "focus": "Improvisation",
    }
    render_improvisation_intelligence_lab(
        st,
        ctx=ctx,
        session_state=session,
        chart_key=str(session.get("display_key") or "Dm"),
        sections=sections,
        song_data=song_data,
        bpm=100,
        genre="Jewish",
        is_custom=False,
        on_open_backing=_open_backing_handler(session),
        on_open_practice=None,
        on_song_source_change=None,
        apply_style_to_playback=None,
        on_go_song_selection=None,
        on_go_custom_progression=None,
    )


st.set_page_config(page_title="Creative lifecycle harness", layout="wide")
st.title("Creative lifecycle — cross-workflow corruption repro")

bootstrap = _simulate_authenticated_bootstrap(st.session_state)
_run_seq = int(st.session_state.get("_script_run_seq") or 1)
if not st.session_state.get("_lifecycle_hevenu_seeded") and _run_seq <= 1:
    seed_hevenu_catalog_session(st.session_state)
    seed_stale_generator_artifact(st.session_state)
    st.session_state["_lifecycle_hevenu_seeded"] = True
    _bump_stage(st.session_state, "initial_seed")
elif not st.session_state.get("_lifecycle_hevenu_seeded"):
    st.session_state["_lifecycle_hevenu_seeded"] = True

if st.session_state.pop("_lifecycle_pending_return_hydrate", None):
    try:
        from backing_source_navigation import rehydrate_creative_from_backing_context
        from studio_page_state import ensure_improv_entry_mode_restored

        rehydrate_creative_from_backing_context(st.session_state, st_like=st)
        ensure_improv_entry_mode_restored(st.session_state)
        _bump_stage(st.session_state, "return_creative_hydrated")
    except ImportError:
        pass

_render_lifecycle_controls(st.session_state)

if not st.session_state.get("display_key") or str(st.session_state.get("display_key")).endswith("m"):
    st.session_state["display_key"] = "C"

st.sidebar.markdown("### Sidebar (catalog + generated collision)")
st.sidebar.selectbox(
    "Practice / Concert Key (harness collision)",
    ENHARMONIC_MAJOR_KEYS,
    key="lifecycle_harness_display_key",
)
_lock_widgets_like_sidebar(st.session_state)

try:
    _render_creative_production_shell(st.session_state)
except Exception as exc:
    st.error(f"Creative panel error: {exc}")

with st.expander("Lifecycle diagnostics"):
    st.json(
        {
            "bootstrap": bootstrap,
            "stage": st.session_state.get(LIFECYCLE_STAGE_KEY),
            "song_based_chords": song_based_progression_chord_count(st.session_state),
            "trace": st.session_state.get("_creative_lifecycle_harness_trace"),
        }
    )
