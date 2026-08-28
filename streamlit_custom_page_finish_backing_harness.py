"""Render-level Custom Finish Song + Custom-page Backing harness.

Clicks the real Streamlit Finish Song / Backing widgets, then runs the same
commit → hydrate → commit → hydrate → reconcile order as the live app.

Run: streamlit run streamlit_custom_page_finish_backing_harness.py
"""

from __future__ import annotations

import copy
from typing import Any

import streamlit as st

from backing_context import (
    BackingContext,
    format_backing_context_banner,
    get_backing_context,
    set_backing_context,
)
from backing_nav_actions import build_backing_nav_actions
from backing_source_navigation import simulate_production_backing_page_hydrate
from cpl_page_ui import render_custom_progression_lab_page
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    apply_cpl_session_progression,
    cpl_workspace_practice_key,
    sync_custom_workspace_practice_key,
)
from songs.music_source import (
    CATALOG_BEFORE_CREATIVE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    display_key_context,
    snapshot_last_custom_state,
)

PK_SHAPE = "Pop\x1fShape of You"
HARNESS_SEED_KEY = "_custom_finish_backing_harness_seeded"


def _trial_active() -> dict[str, Any]:
    return {
        "id": "trial-ah-1",
        "name": "Trial Song",
        "artist": "Your progression",
        "original_key_center": "D",
        "original_sections": {
            "Intro": [],
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ],
            "Pre-Chorus": [],
            "Chorus": [],
            "Bridge": [],
            "Solo": [],
            "Outro": [],
        },
        "bpm": 100,
        "time_signature": "4/4",
        "progression_style": "Pop",
        "groove_style": "Pop",
    }


def _seed_shape_ga_trial_custom(session: dict[str, Any]) -> None:
    trial = _trial_active()
    session.update(
        {
            "studio_page": "custom",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": PK_SHAPE,
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "display_key": "Bm",
            "concert_key": "Bm",
            "cpl_finished": False,
            "cpl_edit_section": "Verse",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "practice_key_by_source": {PK_SHAPE: "Bm"},
            "catalog_session": {
                "pick_key": PK_SHAPE,
                "selected_song": {
                    "pick_key": PK_SHAPE,
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                },
                "display_key": "Bm",
                "original_key": "Bm",
            },
            CATALOG_BEFORE_CREATIVE_KEY: {
                "pick_key": PK_SHAPE,
                "original_key": "Bm",
                "display_key": "Bm",
                "selected_song": {
                    "pick_key": PK_SHAPE,
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                },
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": "custom::trial-ah-1",
                "custom_home_key": "D",
                "active": copy.deepcopy(trial),
            },
            "_music_restore_phase_complete": True,
            "_music_startup_restore_finalized": True,
        }
    )
    apply_cpl_session_progression(session, trial, reset_display_key=False)
    sync_custom_workspace_practice_key(
        session,
        practice_key="D",
        active=session.get(CPL_ACTIVE_KEY),
        source="custom_page",
    )
    snapshot_last_custom_state(session)
    leftover = BackingContext(
        source="regular_song",
        source_label="Catalog song",
        active_song_id=PK_SHAPE,
        song_title="Shape of You",
        key="Bm",
        display_key="Bm",
        concert_key="Bm",
        bpm=100,
        style="Pop",
        groove="Pop",
        bound_pick_key=PK_SHAPE,
        progression=["Bm", "Em", "G", "D"],
    )
    set_backing_context(session, leftover)


def _stage_dump(session: dict[str, Any], stage: str) -> dict[str, Any]:
    ctx = get_backing_context(session)
    active = session.get(CPL_ACTIVE_KEY) if isinstance(session.get(CPL_ACTIVE_KEY), dict) else {}
    dump = {
        "stage": stage,
        "studio_page": str(session.get("studio_page") or ""),
        "ga_source": str(session.get("active_music_source") or ""),
        "ga_song": str(session.get("song") or ""),
        "pick": str(session.get("active_catalog_pick_key") or ""),
        "ctx_source": str(getattr(ctx, "source", "") or "") if ctx is not None else "",
        "ctx_title": str(getattr(ctx, "song_title", "") or "") if ctx is not None else "",
        "ctx_key": str(getattr(ctx, "concert_key", "") or "") if ctx is not None else "",
        "display_key": str(session.get("display_key") or ""),
        "workspace_pk": cpl_workspace_practice_key(session, active),
        "keep": bool(session.get("_custom_page_backing_keep_catalog_owner")),
        "handoff": str(session.get("_backing_explicit_handoff_source") or ""),
        "intent": str(session.get("_backing_open_intent") or ""),
        "entry_class": str(session.get("_backing_entry_class") or ""),
    }
    session.setdefault("_custom_finish_backing_stages", []).append(dump)
    return dump


def _render_backing_surface(session: dict[str, Any]) -> None:
    _stage_dump(session, "backing_before_production_hydrate")
    simulate_production_backing_page_hydrate(session, st_like=st)
    _stage_dump(session, "after_production_double_hydrate")
    ctx = get_backing_context(session)
    banner = format_backing_context_banner(ctx)
    st.markdown(banner or "Backing source: (empty)")
    if ctx is not None:
        st.markdown(
            f"BLUE_CARD source={ctx.source} title={ctx.song_title} "
            f"original={ctx.key} pk={ctx.concert_key or ctx.display_key}"
        )
    else:
        st.markdown("BLUE_CARD (none)")
    actions, _ = build_backing_nav_actions(session)
    for action in actions:
        if st.button(str(action.label), key=f"harness_{action.action_id}"):
            if str(getattr(action, "action_id", "") or "") in {
                "return_custom_page",
                "return_custom_songs",
            }:
                from custom_page_return_destination import consume_custom_page_return_destination

                consume_custom_page_return_destination(session)
                session["studio_page"] = "custom"
                st.rerun()
    original, _identity = display_key_context(
        session,
        catalog_song_data=session.get("selected_song") or {},
        cpl_active_key=CPL_ACTIVE_KEY,
    )
    active = session.get(CPL_ACTIVE_KEY) if isinstance(session.get(CPL_ACTIVE_KEY), dict) else {}
    title = str((active or {}).get("name") or "")
    st.markdown(f"SIDEBAR_TITLE {title}")
    st.markdown(f"SIDEBAR_ORIGINAL {original}")
    st.markdown(
        f"SIDEBAR_PK {cpl_workspace_practice_key(session, session.get(CPL_ACTIVE_KEY))}"
    )
    st.markdown(f"GA_OWNER {session.get('active_music_source')} {session.get('song')}")


def _render_songs_surface(session: dict[str, Any]) -> None:
    """First Songs render after leaving Custom — Shape must win before paint."""
    from songs.music_source import restore_catalog_live_practice_key

    restore_catalog_live_practice_key(session)
    _stage_dump(session, "songs_after_restore")
    original, _identity = display_key_context(
        session,
        catalog_song_data=session.get("selected_song") or {},
        cpl_active_key=CPL_ACTIVE_KEY,
    )
    st.markdown(f"SONGS_TITLE {session.get('song') or session.get('active_song_title')}")
    st.markdown(f"SONGS_SOURCE {session.get('active_music_source')}")
    st.markdown(f"SONGS_PK {session.get('display_key')}")
    st.markdown(f"SONGS_ORIGINAL {original}")
    st.markdown(f"GA_OWNER {session.get('active_music_source')} {session.get('song')}")


if not st.session_state.get(HARNESS_SEED_KEY):
    _seed_shape_ga_trial_custom(st.session_state)
    st.session_state[HARNESS_SEED_KEY] = True
    _stage_dump(st.session_state, "seed")

page = str(st.session_state.get("studio_page") or "custom").strip().lower()
if page == "backing":
    _stage_dump(st.session_state, "backing_entry_before_hydrate")
    _render_backing_surface(st.session_state)
elif page in {"picker", "songs"}:
    _render_songs_surface(st.session_state)
else:
    render_custom_progression_lab_page()
    _stage_dump(st.session_state, "custom_page_render")
