"""The Home page - a welcome screen that points at every workspace.

Home renders in Streamlit and uses the app's own branding: the purple/indigo
lockup, the yellow primary call to action, the blue accents, and the real MPC
emblem. Each card additionally wears the canonical accent of the page it opens
(``app_ui.STUDIO_PAGE_ACCENTS``), so the colour a musician taps is the colour
that greets them when they arrive.

Every tap target is at least 44x44 CSS pixels. Navigation goes through
``home_destinations.apply_home_navigation``; the "Recent practice" card comes
from ``home_recent_session`` and shows only what the Practice Log has on record.
"""

from __future__ import annotations

import functools
import html
from pathlib import Path
from typing import Any

from home_destinations import (
    BROWSE_ALL,
    DISCOVER_CARDS,
    HERO_ACTIONS,
    HOME_PAGE_ID,
    JOURNEY_CARDS,
    MORE_CARDS,
    HomeDestination,
    apply_home_navigation,
)
from home_artwork import ART_CSS, card_art, destination_icon
from music_feature_icons import page_feature_icon

from home_recent_session import (
    ACTION_CAPTION,
    EMPTY_STATE_BODY,
    EMPTY_STATE_TITLE,
    SECTION_EYEBROW,
    VerifiedRecentSession,
    verified_recent_session,
)

HOME_TITLE = "Make room for better music."
HOME_KICKER = "Your music. Your journey."
HOME_SUBTITLE = (
    "Practice smarter. Play better. Create more. Everything you need to learn songs, "
    "find your sound, and keep growing - in one place."
)

#: Brand tokens, read from the existing lockup in ``app_ui``.
BRAND_PURPLE = "#312e81"
BRAND_INDIGO = "#4338ca"
BRAND_YELLOW = "#facc15"
BRAND_BLUE = "#93c5fd"
BRAND_INK = "#0f172a"

#: Minimum tap target, both axes.
MIN_TAP_PX = 44


@functools.lru_cache(maxsize=1)
def home_emblem_data_uri() -> str:
    """Optimized 256px MPC emblem, embedded.

    Same artwork as ``static/branding/mpc_logo_emblem.png``, downscaled from it.
    The full-size emblem is ~1.3 MB; Home shows it at 72px and 40px, so embedding
    the original would cost about 1.7 MB of base64 per page load for nothing.
    Embedding rather than linking is for the same reason as the main brand
    header: Streamlit Community Cloud does not reliably serve ``/app/static/``.
    """
    import base64

    png = Path(__file__).resolve().parent / "static" / "branding" / "mpc_logo_emblem_256.png"
    try:
        return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode("ascii")
    except OSError:
        return ""


def _accent(page_id: str) -> str:
    try:
        from app_ui import studio_page_accent

        return studio_page_accent(page_id)
    except ImportError:
        return "#64748b"


def home_page_css() -> str:
    """Home styles. Mobile-first stacking, 44px targets, per-card page accents."""
    card_accents = "\n".join(
        f".st-key-home_card_{d.key} {{ --home-accent: {_accent(d.page)}; }}"
        for d in JOURNEY_CARDS + DISCOVER_CARDS + MORE_CARDS + (BROWSE_ALL,)
    )
    return f"""
.home-wrap {{ --home-purple: {BRAND_PURPLE}; --home-indigo: {BRAND_INDIGO};
  --home-yellow: {BRAND_YELLOW}; --home-blue: {BRAND_BLUE}; --home-ink: {BRAND_INK}; }}

/* ---- Hero ---- */
.home-hero {{
  position: relative;
  border-radius: 18px;
  padding: 1.6rem 1.4rem 1.5rem 1.4rem;
  background: linear-gradient(128deg, #0f172a 0%, #1e3a5f 42%, #312e81 88%);
  color: #f8fafc;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.22);
  overflow: hidden;
}}
.home-hero::after {{
  content: "";
  position: absolute; inset: auto -70px -90px auto;
  width: 260px; height: 260px; border-radius: 50%;
  background: radial-gradient(circle, rgba(147,197,253,0.26) 0%, rgba(147,197,253,0) 70%);
  pointer-events: none;
}}
.home-hero-top {{ display: flex; align-items: center; gap: 0.85rem; margin-bottom: 1.1rem; }}
.home-hero-logo {{
  width: 72px; height: 72px; flex: 0 0 72px; border-radius: 18px; object-fit: contain;
  filter: drop-shadow(0 8px 18px rgba(79, 70, 229, 0.5));
}}
.home-hero-owner {{
  font-size: 0.7rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--home-blue); font-weight: 800; margin: 0;
}}
.home-hero-app {{ font-size: 1.05rem; font-weight: 800; color: #ffffff; margin: 0.1rem 0 0 0; }}
.home-hero-kicker {{
  font-size: 0.74rem; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--home-yellow); font-weight: 800; margin: 0 0 0.45rem 0;
}}
.home-hero h2 {{
  font-size: clamp(1.75rem, 6vw, 2.9rem); line-height: 1.08; font-weight: 900;
  margin: 0 0 0.6rem 0; color: #ffffff;
}}
.home-hero h2 .home-hero-accent {{ color: var(--home-yellow); display: block; }}
.home-hero p {{ margin: 0; max-width: 46rem; color: #dbeafe; font-size: 0.96rem; line-height: 1.5; }}

/* ---- Section headings ---- */
.home-eyebrow {{
  font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--home-indigo); font-weight: 800; margin: 1.6rem 0 0.2rem 0;
}}
.home-section-title {{ font-size: 1.5rem; font-weight: 900; color: var(--home-ink); margin: 0 0 0.15rem 0; }}
.home-section-sub {{ color: #475569; margin: 0 0 0.6rem 0; font-size: 0.93rem; }}

/* ---- Continue card ---- */
.home-continue {{
  border: 1px solid #e2e8f0; border-left: 5px solid var(--home-indigo);
  border-radius: 14px; padding: 0.95rem 1.1rem; background: #ffffff;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
}}
.home-continue-eyebrow {{
  font-size: 0.7rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--home-indigo); font-weight: 800; margin: 0 0 0.25rem 0;
}}
.home-continue h3 {{ font-size: 1.12rem; font-weight: 800; margin: 0 0 0.2rem 0; color: var(--home-ink); }}
.home-continue p {{ margin: 0; color: #475569; font-size: 0.9rem; line-height: 1.45; }}
.home-continue-keys {{ margin-top: 0.4rem; display: flex; flex-wrap: wrap; gap: 0.35rem; }}
.home-key-chip {{
  display: inline-flex; align-items: center; gap: 0.3rem;
  background: #eef2ff; border: 1px solid #c7d2fe; color: #312e81;
  border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.78rem; font-weight: 700;
}}
.home-key-chip span {{ font-weight: 500; color: #4338ca; }}

/* ---- Cards ---- */
[class*="st-key-home_card_"] {{
  --home-accent: #64748b;
  border: 1px solid #e2e8f0; border-radius: 14px; background: #ffffff;
  padding: 0.9rem 1rem 0.75rem 1rem; height: 100%;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
  border-top: 4px solid var(--home-accent);
}}
.home-card-kicker {{
  font-size: 0.68rem; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--home-accent); font-weight: 800; margin: 0 0 0.2rem 0;
}}
.home-card-title {{ font-size: 1.05rem; font-weight: 800; color: var(--home-ink); margin: 0 0 0.3rem 0; }}
.home-card-blurb {{ color: #475569; font-size: 0.88rem; line-height: 1.45; margin: 0 0 0.7rem 0; }}

/* ---- Buttons: 44px minimum, brand colours ---- */
[class*="st-key-home_nav_"] .stButton > button,
[class*="st-key-home_hero_"] .stButton > button,
[class*="st-key-home_resume"] .stButton > button {{
  min-height: {MIN_TAP_PX}px !important;
  min-width: {MIN_TAP_PX}px !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
}}
[class*="st-key-home_nav_"] .stButton > button {{
  background: #ffffff !important;
  color: var(--home-accent) !important;
  border: 1.5px solid var(--home-accent) !important;
}}
[class*="st-key-home_nav_"] .stButton > button:hover {{
  background: var(--home-accent) !important; color: #ffffff !important;
}}
.st-key-home_hero_practice .stButton > button {{
  background: {BRAND_YELLOW} !important; color: {BRAND_INK} !important;
  border: 1.5px solid #eab308 !important; font-weight: 800 !important;
}}
/* The hero buttons render below the hero card, on the page background, so the
   secondary one is an indigo outline rather than the white-on-dark it would be
   if it sat inside the hero. */
.st-key-home_hero_songs .stButton > button {{
  background: #ffffff !important; color: {BRAND_INDIGO} !important;
  border: 1.5px solid {BRAND_INDIGO} !important; font-weight: 800 !important;
}}
.st-key-home_hero_songs .stButton > button:hover {{
  background: {BRAND_INDIGO} !important; color: #ffffff !important;
}}
.st-key-home_hero_practice .stButton > button:hover {{
  background: #eab308 !important; color: {BRAND_INK} !important;
}}
.st-key-home_resume .stButton > button {{
  background: {BRAND_INDIGO} !important; color: #ffffff !important;
  border: 1.5px solid {BRAND_PURPLE} !important;
}}

/* ---- Footer ---- */
.home-footer {{
  margin-top: 1.8rem; padding-top: 0.9rem; border-top: 1px solid #e2e8f0;
  color: #64748b; font-size: 0.84rem;
}}

/* ---- Narrow screens ---- */
@media (max-width: 820px) {{
  .home-hero {{ padding: 1.25rem 1rem 1.2rem 1rem; }}
  .home-hero-logo {{ width: 56px; height: 56px; flex: 0 0 56px; }}
  .home-section-title {{ font-size: 1.3rem; }}
  [class*="st-key-home_card_"] {{ padding: 0.85rem 0.9rem 0.7rem 0.9rem; }}
}}
@media (max-width: 640px) {{
  .home-wrap [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; gap: 0.6rem; }}
  .home-wrap [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    flex: 1 1 100% !important; min-width: 100% !important;
  }}
  .home-hero h2 {{ font-size: 1.75rem; }}
}}

{card_accents}
{ART_CSS}
"""


def _card_body_html(dest: HomeDestination) -> str:
    kicker = (
        f'<p class="home-card-kicker">{html.escape(dest.kicker)}</p>' if dest.kicker else ""
    )
    return (
        f"{card_art(dest)}{kicker}"
        f'<p class="home-card-title">{html.escape(dest.title)}</p>'
        f'<p class="home-card-blurb">{html.escape(dest.blurb)}</p>'
    )


def _nav_button(st: Any, session_state: Any, dest: HomeDestination, rerun_fn: Any) -> None:
    if st.button(dest.cta, icon=destination_icon(dest), key=f"home_nav_{dest.key}", use_container_width=True):
        apply_home_navigation(session_state, dest)
        rerun_fn()


def _render_card_grid(
    st: Any,
    session_state: Any,
    cards: tuple[HomeDestination, ...],
    rerun_fn: Any,
    *,
    per_row: int,
) -> None:
    for start in range(0, len(cards), per_row):
        chunk = cards[start : start + per_row]
        cols = st.columns(len(chunk))
        for col, dest in zip(cols, chunk):
            with col, st.container(key=f"home_card_{dest.key}"):
                st.markdown(_card_body_html(dest), unsafe_allow_html=True)
                _nav_button(st, session_state, dest, rerun_fn)


def _render_hero(st: Any, session_state: Any, rerun_fn: Any, *, owner: str) -> None:
    emblem = home_emblem_data_uri()
    logo = (
        f'<img class="home-hero-logo" src="{emblem}" alt="Music Practice Coach logo" />'
        if emblem
        else ""
    )
    title_head, _, title_tail = HOME_TITLE.partition(" ")
    st.markdown(
        f"""
<div class="home-hero">
  <div class="home-hero-top">
    {logo}
    <div>
      <p class="home-hero-owner">{html.escape(owner)}</p>
      <p class="home-hero-app">Music Practice Coach AI</p>
    </div>
  </div>
  <p class="home-hero-kicker">{html.escape(HOME_KICKER)}</p>
  <h2>{html.escape(title_head)} <span class="home-hero-accent">{html.escape(title_tail)}</span></h2>
  <p>{html.escape(HOME_SUBTITLE)}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for col, dest in zip(cols, HERO_ACTIONS):
        with col, st.container(key=f"home_hero_{dest.key.split('_', 1)[1]}"):
            if st.button(dest.cta, icon=destination_icon(dest), key=f"home_hero_btn_{dest.key}", use_container_width=True):
                apply_home_navigation(session_state, dest)
                rerun_fn()


def _render_continue(st: Any, session_state: Any, rerun_fn: Any) -> None:
    recent: VerifiedRecentSession | None = verified_recent_session(session_state)
    if recent is None:
        st.markdown(
            f"""
<div class="home-continue">
  <p class="home-continue-eyebrow">{html.escape(SECTION_EYEBROW)}</p>
  <h3>{html.escape(EMPTY_STATE_TITLE)}</h3>
  <p>{html.escape(EMPTY_STATE_BODY)}</p>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    bits = [b for b in (recent.when_label, recent.instrument, recent.focus_area) if b]
    if recent.duration_minutes:
        bits.append(f"{recent.duration_minutes} min")
    if recent.section_label:
        bits.append(recent.section_label)
    chips = "".join(
        f'<span class="home-key-chip">{html.escape(label)} <span>{html.escape(value)}</span></span>'
        for label, value in recent.key_parts
    )
    heading = recent.song_title or "Your last practice session"
    st.markdown(
        f"""
<div class="home-continue">
  <p class="home-continue-eyebrow">{html.escape(SECTION_EYEBROW)}</p>
  <h3>{html.escape(heading)}</h3>
  <p>{html.escape(" · ".join(bits))}</p>
  <div class="home-continue-keys">{chips}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.container(key="home_resume"):
        label = recent.action_label()
        if st.button(label, icon=page_feature_icon(recent.page), key="home_resume_btn", use_container_width=False):
            dest = HomeDestination(
                key="resume",
                page=recent.page,
                title=label,
                blurb="",
                creative_dest=recent.creative_dest,
            )
            apply_home_navigation(session_state, dest)
            rerun_fn()
    st.caption(ACTION_CAPTION.format(destination=recent.destination_label()))


def render_home_page(
    st: Any,
    session_state: Any,
    *,
    rerun_fn: Any,
    owner: str = "Daniel Cohen",
) -> None:
    """Render Home. Reads state; writes nothing until a button is pressed."""
    st.markdown(f"<style data-home-page='1'>{home_page_css()}</style>", unsafe_allow_html=True)
    st.markdown('<div class="home-wrap">', unsafe_allow_html=True)

    _render_hero(st, session_state, rerun_fn, owner=owner)
    _render_continue(st, session_state, rerun_fn)

    st.markdown(
        '<p class="home-eyebrow">Find your flow</p>'
        '<p class="home-section-title">What would you like to do?</p>'
        '<p class="home-section-sub">Wherever you are in your musical journey, '
        "there's a place to start.</p>",
        unsafe_allow_html=True,
    )
    _render_card_grid(st, session_state, JOURNEY_CARDS, rerun_fn, per_row=2)

    st.markdown(
        '<p class="home-eyebrow">Find something to play</p>'
        '<p class="home-section-title">Let the music lead.</p>'
        '<p class="home-section-sub">Open Browse with a genre already selected, '
        "or start from the whole catalog.</p>",
        unsafe_allow_html=True,
    )
    _render_card_grid(st, session_state, DISCOVER_CARDS + (BROWSE_ALL,), rerun_fn, per_row=3)

    st.markdown(
        '<p class="home-eyebrow">Go deeper</p>'
        '<p class="home-section-title">More ways to grow.</p>',
        unsafe_allow_html=True,
    )
    _render_card_grid(st, session_state, MORE_CARDS, rerun_fn, per_row=3)

    st.markdown(
        '<div class="home-footer">Daniel Cohen Music Practice Coach AI'
        "<br/>Every session is a step forward.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ("HOME_PAGE_ID", "render_home_page", "home_page_css", "home_emblem_data_uri")
