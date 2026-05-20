"""Shared Streamlit UI theme and layout helpers for the music practice coach."""

from __future__ import annotations

import html
from typing import Any, Optional

__all__ = [
    "STUDIO_PAGES",
    "app_hero",
    "compact_page_title",
    "ensure_studio_page",
    "follow_along_status_html",
    "inject_app_theme",
    "page_header",
    "render_global_studio_bar",
    "render_studio_nav",
    "session_badges",
    "sidebar_section",
    "sidebar_source_banner",
]


def inject_app_theme() -> None:
    """Global CSS: studio feel, cards, sidebar sections, responsive charts."""
    import streamlit as st

    st.markdown(
        """
<style>
:root {
  --studio-ink: #0f172a;
  --studio-muted: #64748b;
  --studio-line: rgba(15, 23, 42, 0.10);
  --studio-card: #ffffff;
  --studio-soft: #f8fafc;
  --studio-radius: 14px;
}
.block-container { padding-top: 0.65rem; max-width: 1180px; }
[data-testid="stVerticalBlock"] > div:empty { display: none; }
header[data-testid="stHeader"] { background: rgba(255,255,255,0.92); backdrop-filter: blur(8px); }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f172a 0%, #111827 42%, #1e293b 100%);
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #cbd5e1 !important; }
[data-testid="stSidebar"] .stMarkdown h1, [data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 { color: #f8fafc !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
  background: rgba(255,255,255,0.08) !important;
  border-color: rgba(255,255,255,0.18) !important;
}
.ui-sb-section {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94a3b8 !important;
  margin: 1.1rem 0 0.35rem 0;
  padding-top: 0.65rem;
  border-top: 1px solid rgba(255,255,255,0.10);
}
.ui-sb-section:first-of-type { border-top: none; padding-top: 0; margin-top: 0.2rem; }
.ui-hero {
  border: 1px solid var(--studio-line);
  border-radius: 18px;
  padding: 1.1rem 1.25rem 1rem 1.25rem;
  margin-bottom: 0.85rem;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 38%, #312e81 100%);
  color: #f8fafc;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.14);
}
.ui-hero-title {
  font-size: 1.55rem;
  font-weight: 850;
  letter-spacing: -0.02em;
  margin: 0 0 0.25rem 0;
  line-height: 1.15;
}
.ui-hero-sub {
  color: #cbd5e1;
  font-size: 0.95rem;
  margin: 0;
  line-height: 1.45;
}
.ui-page-head {
  border: 1px solid var(--studio-line);
  border-radius: var(--studio-radius);
  padding: 0.95rem 1.05rem;
  margin: 0 0 1rem 0;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
.ui-page-title {
  font-size: 1.35rem;
  font-weight: 850;
  color: var(--studio-ink);
  margin: 0;
  line-height: 1.2;
}
.ui-page-sub {
  color: var(--studio-muted);
  font-size: 0.92rem;
  margin: 0.35rem 0 0 0;
  line-height: 1.45;
}
.ui-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.65rem;
}
.ui-badge {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--studio-line);
  border-radius: 999px;
  padding: 0.28rem 0.62rem;
  background: #fff;
  color: #334155;
  font-size: 0.78rem;
  font-weight: 700;
  white-space: nowrap;
}
.ui-badge.accent { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
.ui-badge.green { background: #f0fdf4; border-color: #bbf7d0; color: #15803d; }
.ui-badge.purple { background: #f5f3ff; border-color: #ddd6fe; color: #6d28d9; }
.ui-badge.amber { background: #fffbeb; border-color: #fde68a; color: #b45309; }
.ui-card {
  border: 1px solid var(--studio-line);
  border-radius: var(--studio-radius);
  padding: 0.85rem 0.95rem;
  margin-bottom: 0.85rem;
  background: var(--studio-card);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.ui-card.soft { background: var(--studio-soft); }
.ui-card-title {
  font-size: 0.98rem;
  font-weight: 800;
  color: var(--studio-ink);
  margin: 0 0 0.35rem 0;
}
.ui-card-sub {
  color: var(--studio-muted);
  font-size: 0.86rem;
  margin: 0 0 0.55rem 0;
}
.ui-source-banner {
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
  margin-bottom: 0.55rem;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.14);
  font-size: 0.88rem;
  line-height: 1.4;
}
.ui-source-banner strong { color: #f8fafc; }
.ui-follow-strip {
  border: 1px solid var(--studio-line);
  border-radius: var(--studio-radius);
  padding: 0.75rem 0.85rem;
  margin: 0.5rem 0 0.85rem 0;
  background: linear-gradient(180deg, #f0fdf4, #ffffff);
}
.ui-follow-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(110px, 1fr));
  gap: 0.5rem;
}
.ui-follow-tile {
  border: 1px solid rgba(22, 163, 74, 0.18);
  border-radius: 12px;
  padding: 0.55rem 0.65rem;
  background: #fff;
}
.ui-follow-label {
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}
.ui-follow-value {
  font-size: 1.02rem;
  font-weight: 850;
  color: #14532d;
  margin-top: 0.15rem;
  word-break: break-word;
}
@media (max-width: 760px) {
  .ui-follow-grid { grid-template-columns: repeat(2, minmax(110px, 1fr)); }
  .ui-hero-title { font-size: 1.28rem; }
}
div[data-testid="stTabs"] [data-baseweb="tab-list"] { flex-wrap: wrap; gap: 0.25rem; }
.ui-studio-nav {
  border: 1px solid var(--studio-line);
  border-radius: var(--studio-radius);
  padding: 0.45rem 0.5rem;
  margin-bottom: 0.55rem;
  background: #fff;
}
.ui-studio-nav .nav-btn button {
  font-size: 0.78rem !important;
  padding: 0.35rem 0.5rem !important;
  min-height: 2rem !important;
}
.ui-global-bar {
  border: 1px solid #bfdbfe;
  border-radius: var(--studio-radius);
  padding: 0.55rem 0.65rem 0.45rem 0.65rem;
  margin-bottom: 0.65rem;
  background: linear-gradient(180deg, #eff6ff, #ffffff);
  position: sticky;
  top: 0.35rem;
  z-index: 99;
}
.ui-global-bar .stSelectbox label, .ui-global-bar .stSlider label {
  font-size: 0.78rem !important;
  font-weight: 700 !important;
}
.ui-compact-title {
  font-size: 1.12rem;
  font-weight: 850;
  color: var(--studio-ink);
  margin: 0 0 0.5rem 0;
  line-height: 1.25;
}
.ui-compact-sub {
  color: var(--studio-muted);
  font-size: 0.84rem;
  margin: -0.25rem 0 0.65rem 0;
}
@media (max-width: 900px) {
  .ui-global-bar { position: relative; top: 0; }
  .lead-grid { grid-template-columns: repeat(2, minmax(88px, 1fr)) !important; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def app_hero(title: str, subtitle: str) -> None:
    import streamlit as st

    st.markdown(
        f"""
<div class="ui-hero">
  <div class="ui-hero-title">{html.escape(title)}</div>
  <p class="ui-hero-sub">{html.escape(subtitle)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "", badges: Optional[list[tuple[str, str]]] = None) -> None:
    import streamlit as st

    badge_html = ""
    if badges:
        pills = []
        for label, variant in badges:
            cls = f"ui-badge {variant}".strip() if variant else "ui-badge"
            pills.append(f'<span class="{cls}">{html.escape(label)}</span>')
        badge_html = f'<div class="ui-badge-row">{"".join(pills)}</div>'
    sub_html = f'<p class="ui-page-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f"""
<div class="ui-page-head">
  <h2 class="ui-page-title">{html.escape(icon)} {html.escape(title)}</h2>
  {sub_html}
  {badge_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def session_badges(
    *,
    source_label: str,
    song: str,
    original_key: str,
    display_key: str,
    instrument: str,
    level: str,
    focus: str,
    genre: str = "",
) -> list[tuple[str, str]]:
    badges = [
        (source_label, "accent"),
        (f"🎵 {song}", ""),
        (f"Key {display_key}", "green"),
    ]
    if display_key != original_key:
        badges.append((f"Home {original_key}", "amber"))
    if genre:
        badges.append((genre, "purple"))
    badges.extend([(instrument, ""), (level, ""), (focus, "")])
    return badges


def sidebar_section(title: str, *, icon: str = "") -> None:
    import streamlit as st

    label = f"{icon} {title}".strip() if icon else title
    st.sidebar.markdown(f'<p class="ui-sb-section">{html.escape(label)}</p>', unsafe_allow_html=True)


def sidebar_source_banner(markdown_text: str) -> None:
    import streamlit as st

    st.sidebar.markdown(
        f'<div class="ui-source-banner">{markdown_text}</div>',
        unsafe_allow_html=True,
    )


STUDIO_PAGES: list[tuple[str, str]] = [
    ("practice", "🎯 Practice"),
    ("picker", "📚 Songs"),
    ("backing", "🎧 Backing"),
    ("custom", "✏️ Custom"),
    ("creative", "🧠 Creative"),
    ("multitrack", "🎚️ Multi"),
    ("analysis", "🎙️ Analysis"),
    ("log", "📓 Log"),
]


def ensure_studio_page(session_state: dict[str, Any], default: str = "practice") -> str:
    return session_state.setdefault("studio_page", default)


def render_studio_nav(session_state: Any, *, rerun_fn: Any) -> str:
    """Horizontal workspace navigation (replaces tall tab strip)."""
    import streamlit as st

    current = ensure_studio_page(session_state)
    st.markdown('<div class="ui-studio-nav">', unsafe_allow_html=True)
    cols = st.columns(len(STUDIO_PAGES))
    for col, (page_id, label) in zip(cols, STUDIO_PAGES):
        with col:
            st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
            if st.button(
                label,
                key=f"nav_{page_id}",
                use_container_width=True,
                type="primary" if page_id == current else "secondary",
            ):
                if page_id != current:
                    session_state["studio_page"] = page_id
                    rerun_fn()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return session_state.get("studio_page", current)


def render_global_studio_bar(
    *,
    song: str,
    genre: str,
    source_label: str,
    original_key: str,
    display_key_options: list[str],
    instrument_options: list[str],
    focus_options: list[str],
    show_bpm: bool = False,
    bpm_key: str = "backing_track_bpm",
    backing_ready: bool = False,
    on_display_key_change: Optional[Any] = None,
    is_custom_source: bool = False,
    custom_progression_name: str = "",
    genre_options: list[str] | None = None,
    current_genre: str = "",
    song_pick_options: list[str] | None = None,
    format_pick_label: Optional[Any] = None,
    on_source_change: Optional[Any] = None,
    on_genre_change: Optional[Any] = None,
    on_song_change: Optional[Any] = None,
    session_state: Optional[Any] = None,
    rerun_fn: Optional[Any] = None,
) -> None:
    """Primary controls — visible above every page (song, key, level, instrument)."""
    import streamlit as st

    ss = session_state if session_state is not None else st.session_state
    st.markdown('<div class="ui-global-bar">', unsafe_allow_html=True)
    row1 = st.columns([2.0, 1.35, 1.0, 1.0, 1.0, 0.9])
    with row1[0]:
        genre_bit = f" · {genre}" if genre else ""
        st.markdown(f"**{html.escape(song)}**{html.escape(genre_bit)}")
        st.caption(f"{source_label} · home **{original_key}**")
    with row1[1]:
        st.selectbox(
            "Display / practice key",
            display_key_options,
            key="display_key",
            help="Transpose charts and backing audio.",
            on_change=on_display_key_change,
        )
    with row1[2]:
        st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"], key="level")
    with row1[3]:
        st.selectbox("Instrument", instrument_options, key="instrument")
    with row1[4]:
        st.selectbox("Focus", focus_options, key="focus")
    with row1[5]:
        if show_bpm:
            st.slider("BPM", 50, 180, 100, 5, key=bpm_key)
        elif backing_ready:
            st.caption("🟢 Backing ready")
        else:
            st.caption("Backing idle")

    row2 = st.columns([1.05, 1.0, 2.35, 0.55, 0.55, 0.55])
    with row2[0]:
        st.selectbox(
            "Active source",
            ["Catalog song", "Custom progression"],
            index=1 if is_custom_source else 0,
            key="global_source_mode",
            on_change=on_source_change,
        )
    with row2[1]:
        if is_custom_source:
            st.caption("Custom")
            st.markdown(f"**{html.escape(custom_progression_name or 'Progression')}**")
        elif genre_options:
            _gopts = genre_options
            _gidx = _gopts.index(current_genre) if current_genre in _gopts else 0
            if ss.get("global_quick_genre") not in _gopts:
                ss["global_quick_genre"] = current_genre if current_genre in _gopts else _gopts[0]
            st.selectbox(
                "Genre",
                _gopts,
                index=_gopts.index(ss["global_quick_genre"])
                if ss.get("global_quick_genre") in _gopts
                else _gidx,
                key="global_quick_genre",
                on_change=on_genre_change,
            )
        else:
            st.caption("Genre")
            st.markdown(f"**{html.escape(genre)}**")
    with row2[2]:
        if is_custom_source:
            st.caption("Edit chords in **Custom** page · transpose with **Display / practice key** above.")
        elif song_pick_options and format_pick_label:
            _sopts = song_pick_options
            if ss.get("global_quick_song") not in _sopts:
                ss["global_quick_song"] = _sopts[0]
            st.selectbox(
                "Song",
                _sopts,
                format_func=format_pick_label,
                key="global_quick_song",
                on_change=on_song_change,
            )
        else:
            st.caption("Song")
            st.markdown(f"**{html.escape(song)}**")
    with row2[3]:
        if rerun_fn and st.button("📚", key="global_nav_picker", help="Song Picker"):
            ss["studio_page"] = "picker"
            rerun_fn()
    with row2[4]:
        if rerun_fn and st.button("🎯", key="global_nav_practice", help="Practice"):
            ss["studio_page"] = "practice"
            rerun_fn()
    with row2[5]:
        if rerun_fn and st.button("🎧", key="global_nav_backing", help="Backing Track"):
            ss["studio_page"] = "backing"
            rerun_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def compact_page_title(icon: str, title: str, subtitle: str = "") -> None:
    import streamlit as st

    sub = f'<p class="ui-compact-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'<p class="ui-compact-title">{html.escape(icon)} {html.escape(title)}</p>{sub}',
        unsafe_allow_html=True,
    )


def follow_along_status_html(pos: dict[str, Any]) -> str:
    if not pos:
        return ""
    return f"""
<div class="ui-follow-strip">
  <div class="ui-follow-grid">
    <div class="ui-follow-tile">
      <div class="ui-follow-label">Section</div>
      <div class="ui-follow-value">{html.escape(str(pos.get("section", "")))}</div>
    </div>
    <div class="ui-follow-tile">
      <div class="ui-follow-label">Current chord</div>
      <div class="ui-follow-value">{html.escape(str(pos.get("chord", "")))}</div>
    </div>
    <div class="ui-follow-tile">
      <div class="ui-follow-label">Bar</div>
      <div class="ui-follow-value">{html.escape(str(pos.get("bar_in_section", "")))} / {html.escape(str(pos.get("section_bars", "")))}</div>
    </div>
    <div class="ui-follow-tile">
      <div class="ui-follow-label">Next</div>
      <div class="ui-follow-value">{html.escape(str(pos.get("next_chord", "—")))}</div>
    </div>
  </div>
</div>
"""
