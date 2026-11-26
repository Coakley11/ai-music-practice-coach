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
    "<style>.st-key-backing_practice_melody_nav{gap:.4rem!important;flex-wrap:wrap;margin:-.2rem 0 .1rem;align-items:center}"
    ".st-key-backing_practice_melody_nav button{min-height:30px!important;height:30px;padding:0 .65rem!important;"
    "border-radius:999px!important;font-size:.84rem!important;line-height:1}"
    ".st-key-backing_practice_melody_nav button p{font-size:.84rem!important}"
    ".st-key-backing_practice_melody_nav [data-testid='stElementContainer']{width:auto!important;flex:0 0 auto}"
    # ◀ 2 / 3 ▶ is one control: a pill with the count between its arrows, set apart from New melody
    ".st-key-backing_practice_melody_steps{gap:0!important;flex:0 0 auto;border:1px solid rgba(100,116,139,.35);border-radius:999px;"
    "padding:0 2px;margin-right:.35rem}"
    ".st-key-backing_practice_melody_steps button{border:0!important;background:transparent!important;min-width:30px;padding:0 .45rem!important}"
    ".st-key-backing_practice_melody_nav .pm-nav-count{font-size:.8rem;font-weight:800;color:#475569;white-space:nowrap;padding:0 .25rem;"
    "font-variant-numeric:tabular-nums}</style>"
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
    # Three distinct acts (user, 2026-11-26): ◀ / ▶ move between the melodies already made for these settings (▶
    # never makes one: at the newest it is disabled); "🪄 New melody", apart from them, is the one deliberate way to
    # compose another (the earlier ones stay in the history); Keep holds the one on screen.
    last = max(count, at + 1)
    with st.container(key="backing_practice_melody_nav", horizontal=True, vertical_alignment="center", gap="small"):
        with st.container(key="backing_practice_melody_steps", horizontal=True, vertical_alignment="center", gap=None):
            st.button("◀", key="backing_practice_melody_prev",
                      help="Previous melody" if at > 0 and not watching else "This is the first melody for these settings",
                      disabled=bool(watching) or at == 0, on_click=_choose, args=(choose,), kwargs={"step": -1})
            where = "Kept" if watching else f"{at + 1} / {last}"
            st.markdown(f'<span class="pm-nav-count" title="Melody {at + 1} of {last} for these settings">{where}</span>',
                        unsafe_allow_html=True)
            st.button("▶", key="backing_practice_melody_next",
                      help=("Next melody" if at < count - 1 and not watching
                            else "This is the newest melody: 🪄 New melody composes another"),
                      disabled=bool(watching) or at >= count - 1, on_click=_choose, args=(choose,), kwargs={"step": 1})
        st.button(f"{semantic_action_icon('generate') or '🎵'} New melody", key=ANOTHER_KEY, type="primary",
                  help="Compose a new melody for these settings; the earlier ones stay (◀ ▶)",
                  on_click=_choose, args=(choose,), kwargs={"another": True})
        if watching:
            st.button("★ Kept", key="backing_practice_melody_unkeep", help="Kept. Press to remove it from your kept melodies",
                      on_click=library.drop_kept, args=(session, identity, watching))
        else:
            st.button("☆ Keep", key="backing_practice_melody_keep", help="Keep this melody: it stays as it is",
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
