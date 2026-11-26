"""The controls of Backing's Practice Melody: another one, the earlier ones, the kept ones.

They only choose which melody is shown. Nothing here touches the song, jam, key, groove, settings or playback.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import practice_melody_library as library
from practice_melody_model import PracticeMelody

ANOTHER_KEY = "backing_practice_melody_another"

# The row's buttons are small: arrows and stars as squares, the generate action a pill.
_NAV_CSS = (
    "<style>.st-key-backing_practice_melody_nav{gap:.35rem!important;flex-wrap:wrap;margin:-.2rem 0 .1rem}"
    ".st-key-backing_practice_melody_nav button{min-height:30px!important;height:30px;padding:0 .6rem!important;"
    "border-radius:999px!important;font-size:.85rem!important;line-height:1}"
    ".st-key-backing_practice_melody_nav button p{font-size:.85rem!important}"
    ".st-key-backing_practice_melody_nav .pm-nav-count{font-size:.8rem;font-weight:700;color:#475569;white-space:nowrap}"
    ".st-key-backing_practice_melody_nav [data-testid='stElementContainer']{width:auto!important;flex:0 0 auto}</style>"
)


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
    # Labels: Key Cycling's page script takes any button labelled just "Previous" / "Next" for its own transport
    # (backing_key_cycle __kcStepBtnHandler label fallback) and cancels the click; bare arrows are not taken.
    # Callbacks, not `if st.button(...): ...; st.rerun()`: a press made while that rerun was still running was
    # dropped (browser 2026-11-25: Previous right after Generate Another did nothing), as on the Key Cycling buttons.
    # Compact (user, 2026-11-26: the three big buttons took too much room): one slim row of small controls,
    #   ◀  Melody 2 of 3  ▶   🪄 Another   ☆   [★ Kept]
    # each with its full name as a tooltip; the kept melodies in a small popover.
    from music_feature_icons import semantic_action_icon

    st.markdown(_NAV_CSS, unsafe_allow_html=True)
    with st.container(key="backing_practice_melody_nav", horizontal=True, vertical_alignment="center", gap="small"):
        st.button("◀", key="backing_practice_melody_prev", help="Previous melody",
                  disabled=bool(watching) or at == 0, on_click=_choose, args=(choose,), kwargs={"step": -1})
        where = "Kept melody" if watching else f"Melody {at + 1} of {max(count, at + 1)}"
        st.markdown(f'<span class="pm-nav-count">{where}</span>', unsafe_allow_html=True)
        st.button("▶", key="backing_practice_melody_next", help="Next melody",
                  disabled=bool(watching) or at >= count - 1, on_click=_choose, args=(choose,), kwargs={"step": 1})
        st.button(f"{semantic_action_icon('generate') or '🎵'} Another", key=ANOTHER_KEY, type="primary",
                  help="Generate another melody for these settings (the ones before stay: ◀ ▶)",
                  on_click=_choose, args=(choose,), kwargs={"another": True})
        if watching:
            st.button("★", key="backing_practice_melody_unkeep", help="Remove this melody from your kept melodies",
                      on_click=library.drop_kept, args=(session, identity, watching))
        else:
            st.button("☆", key="backing_practice_melody_keep", help="Keep this melody",
                      on_click=_keep, args=(identity, melody, dict(sections), list(section_order), sections_key))
        if kept:
            options = [""] + [str(k["id"]) for k in kept]
            labels = {"": "The melody for the current settings", **{str(k["id"]): _label(k) for k in kept}}
            key = f"backing_practice_melody_kept::{identity}"
            session[key] = watching if watching in options else ""
            with st.popover(f"★ Kept ({len(kept)})", help="Your kept melodies"):
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


def _choose(choose: Callable[..., Any], **kw: Any) -> None:
    choose(**kw)


def _keep(identity: str, melody: PracticeMelody, sections: dict, order: list, sections_key: str) -> None:
    import streamlit as st

    library.keep(st.session_state, identity, melody, sections=sections, section_order=order, sections_key=sections_key)


def _view(identity: str, key: str) -> None:
    import streamlit as st

    library.view_kept(st.session_state, identity, str(st.session_state.get(key) or ""))


__all__ = ("ANOTHER_KEY", "render_melody_controls")
