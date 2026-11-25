"""The controls of Backing's Practice Melody: another one, the earlier ones, the kept ones.

They only choose which melody is shown. Nothing here touches the song, jam, key, groove, settings or playback.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import practice_melody_library as library
from practice_melody_model import PracticeMelody

ANOTHER_KEY = "backing_practice_melody_another"


def _label(row: Mapping[str, Any]) -> str:
    focus = str(row.get("focus") or "").strip()
    parts = [str(row.get("style") or "").strip(), str(row.get("level") or "").strip(), focus]
    return "★ " + " · ".join(p for p in parts if p) + f" · #{int(row.get('alt') or 0) + 1}"


def render_melody_controls(
    st: Any,
    *,
    identity: str,
    recipe: str,
    melody: PracticeMelody,
    sections: Mapping[str, Sequence[str]],
    section_order: Sequence[str],
    sections_key: str,
    choose: Callable[..., Any],
) -> None:
    """``choose(another=True)`` composes one more; ``choose(step=±1)`` moves between the existing ones."""
    session = st.session_state
    at, count = library.alternatives(session, identity, recipe)
    watching = library.viewing(session, identity)
    kept = library.kept_melodies(session, identity)
    cols = st.columns([2.2, 1, 1, 1.6])
    with cols[0]:
        if st.button("🎵 Generate Another Melody", key=ANOTHER_KEY, type="primary", use_container_width=True):
            choose(another=True)
            st.rerun()
    with cols[1]:
        if st.button("◀ Previous", key="backing_practice_melody_prev", use_container_width=True, disabled=bool(watching) or at == 0):
            choose(step=-1)
            st.rerun()
    with cols[2]:
        if st.button("Next ▶", key="backing_practice_melody_next", use_container_width=True, disabled=bool(watching) or at >= count - 1):
            choose(step=1)
            st.rerun()
    with cols[3]:
        if watching:
            if st.button("Remove from kept", key="backing_practice_melody_unkeep", use_container_width=True):
                library.drop_kept(session, identity, watching)
                st.rerun()
        elif st.button("☆ Keep this melody", key="backing_practice_melody_keep", use_container_width=True):
            library.keep(session, identity, melody, sections=sections, section_order=section_order, sections_key=sections_key)
            st.rerun()
    if kept:
        options = [""] + [str(k["id"]) for k in kept]
        labels = {"": "The melody for the current settings", **{str(k["id"]): _label(k) for k in kept}}
        key = f"backing_practice_melody_kept::{identity}"
        session[key] = watching if watching in options else ""
        st.selectbox(
            "Kept melodies", options, key=key, format_func=lambda v: labels.get(v, v),
            on_change=_view, args=(identity, key),
        )
    shown = next((k for k in kept if str(k.get("id")) == watching), None)
    if shown is not None:
        if not library.fits(shown, sections, [n for n in section_order if n in sections], sections_key):
            st.caption("⚠️ This kept melody was written for an earlier progression of this song; its chords are its own.")
        else:
            st.caption("This kept melody stays as it is; the current settings have their own.")


def _view(identity: str, key: str) -> None:
    import streamlit as st

    library.view_kept(st.session_state, identity, str(st.session_state.get(key) or ""))


__all__ = ("ANOTHER_KEY", "render_melody_controls")
