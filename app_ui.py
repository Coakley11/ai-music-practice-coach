"""Shared Streamlit UI theme and layout helpers for the music practice coach."""

from __future__ import annotations

import html
from typing import Any, Optional

__all__ = [
    "STUDIO_PAGES",
    "app_hero",
    "render_studio_brand_header",
    "compact_page_title",
    "ensure_studio_page",
    "navigate_studio_page",
    "follow_along_status_html",
    "inject_app_theme",
    "page_header",
    "begin_studio_control_deck",
    "close_control_section",
    "end_studio_control_deck",
    "open_control_section",
    "render_global_studio_bar",
    "render_section_jump_bar",
    "render_cross_page_links",
    "render_page_quick_nav",
    "TOP_NAV_ITEMS",
    "STUDIO_PAGE_NAV_KEY",
    "render_sidebar_studio_nav",
    "render_main_sidebar_nav_expand_chip",
    "render_studio_nav",
    "SIDEBAR_NAV_COLLAPSED_KEY",
    "ensure_sidebar_nav_defaults",
    "sidebar_nav_is_collapsed",
    "sync_sidebar_nav_body_dataset",
    "STUDIO_PAGE_META",
    "nav_icon_button_label",
    "nav_compact_button_label",
    "session_badges",
    "sidebar_section",
    "sidebar_source_banner",
    "sidebar_goto_song_selection",
    "studio_card_modifier_classes",
]


_GENRE_TOKENS: tuple[str, ...] = (
    "jazz",
    "bossa",
    "blues",
    "rock",
    "funk",
    "soul",
    "pop",
    "classical",
    "folk",
    "jewish",
    "country",
    "latin",
)

_INSTRUMENT_TOKENS: tuple[str, ...] = (
    "guitar",
    "piano",
    "saxophone",
    "trumpet",
    "bass",
    "drums",
    "violin",
    # "voice" must precede "vocal" so the canonical "Voice" instrument
    # value (set by practice_setup_controls.py) emits `.inst-voice`.
    "voice",
    "vocal",
    "singer",
)


def studio_card_modifier_classes(
    *,
    genre: str = "",
    instrument: str = "",
) -> str:
    """Compact CSS modifier string for tasteful genre/instrument-aware accents.

    Returns a space-prefixed string so it can be appended directly to existing
    card class strings (or `""` when neither token matches).
    """
    bits: list[str] = []
    g = (genre or "").lower()
    for token in _GENRE_TOKENS:
        if token in g:
            bits.append(f"genre-{token}")
            break
    i = (instrument or "").lower()
    for token in _INSTRUMENT_TOKENS:
        if token in i:
            bits.append(f"inst-{token}")
            break
    return (" " + " ".join(bits)) if bits else ""


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
.block-container {
  padding-top: 0.65rem;
  max-width: 1180px;
  background: linear-gradient(180deg, #fafbff 0%, #ffffff 120px);
}
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
/* Sidebar form fields — dark text on white (readable on phone + desktop) */
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stTextArea textarea,
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] input[type="text"],
[data-testid="stSidebar"] textarea {
  background: #ffffff !important;
  color: #111827 !important;
  -webkit-text-fill-color: #111827 !important;
  border-color: rgba(15, 23, 42, 0.14) !important;
}
[data-testid="stSidebar"] .stTextInput input::placeholder,
[data-testid="stSidebar"] .stTextArea textarea::placeholder {
  color: #6b7280 !important;
  -webkit-text-fill-color: #6b7280 !important;
  opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: #ffffff !important;
  color: #111827 !important;
  border-color: rgba(15, 23, 42, 0.14) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div *,
[data-testid="stSidebar"] [data-baseweb="select"] > div * {
  color: #111827 !important;
  -webkit-text-fill-color: #111827 !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"],
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stCheckbox"],
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
  pointer-events: auto !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
  cursor: pointer !important;
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
.ui-sb-section.tone-source { color: #c4b5fd !important; }
.ui-sb-section.tone-key { color: #7dd3fc !important; }
.ui-sb-section.tone-library { color: #a5b4fc !important; }
.ui-sb-section.tone-session { color: #fcd34d !important; }
.ui-sb-section.tone-lyrics { color: #f9a8d4 !important; }
.ui-sb-section.tone-ai { color: #67e8f9 !important; }
.ui-sb-section.tone-nav { color: #e2e8f0 !important; }
.ui-source-banner {
  border-radius: 10px;
  padding: 0.5rem 0.6rem;
  margin-bottom: 0.35rem;
  background: rgba(167, 139, 250, 0.12);
  border: 1px solid rgba(167, 139, 250, 0.28);
  font-size: 0.82rem;
  line-height: 1.4;
}
.ui-sb-nav-panel { margin: 0.1rem 0 0.75rem 0; }
.ui-sb-nav-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  margin: 0 0 0.35rem 0;
}
.ui-sb-nav-panel-header .ui-sb-section {
  margin: 0 !important;
  padding-top: 0 !important;
  border-top: none !important;
  flex: 1 1 auto;
}
.ui-sb-nav-panel[data-collapsed="true"] .ui-sb-nav-wrap { display: none !important; }
.ui-sb-nav-panel[data-collapsed="false"] .ui-sb-nav-collapsed-rail { display: none !important; }
.ui-sb-nav-collapsed-rail {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.35rem;
  padding: 0.35rem 0.2rem 0.5rem;
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
}
.ui-sb-nav-current-pill {
  text-align: center;
  font-size: 1.35rem;
  line-height: 1.2;
  padding: 0.25rem 0;
  opacity: 0.95;
}
.ui-sb-nav-collapsed-rail .stButton > button {
  min-height: 2.35rem !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
}
/* Main-area ☰ Pages chip removed — Pages menu lives in sidebar only */
.ui-main-nav-expand-chip,
section[data-testid="stMain"] [class*="st-key-main_sidebar_nav_expand"] {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
body[data-sidebar-nav-collapsed="true"] [data-testid="stSidebar"] .ui-sb-section.tone-nav {
  margin-bottom: 0.15rem !important;
}
body[data-sidebar-nav-collapsed="true"] section[data-testid="stMain"] .block-container {
  max-width: min(1320px, calc(100vw - 17.5rem)) !important;
}
body[data-sidebar-nav-collapsed="true"] [data-testid="stSidebar"] .ui-sb-nav-panel {
  margin-bottom: 0.35rem !important;
}
body[data-sidebar-nav-collapsed="true"] [data-testid="stSidebar"] .ui-sb-nav-collapsed-rail {
  margin-bottom: 0.25rem !important;
}
/* Hide Streamlit blocks for page nav buttons when collapsed (not rendered, but guard legacy DOM) */
body[data-sidebar-nav-collapsed="true"] [data-testid="stSidebar"] [class*="st-key-sb_nav_"] {
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}
.ui-sb-nav-wrap {
  margin: 0.25rem 0 0.85rem 0;
  padding: 0.45rem 0.4rem;
  border-radius: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
}
.ui-sb-nav-wrap .sb-nav-btn { margin-bottom: 0.28rem; }
.ui-sb-nav-wrap .sb-nav-btn:last-child { margin-bottom: 0; }
.ui-sb-nav-wrap .stButton > button {
  width: 100% !important;
  text-align: left !important;
  justify-content: flex-start !important;
  font-size: 0.78rem !important;
  font-weight: 700 !important;
  padding: 0.42rem 0.55rem !important;
  min-height: 2.05rem !important;
  border-radius: 10px !important;
  transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease !important;
}
.ui-sb-nav-wrap .stButton > button:hover {
  transform: translateY(-1px);
  filter: brightness(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.18) !important;
}
.ui-key-global-hint {
  font-size: 0.76rem;
  color: #bae6fd !important;
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.28);
  border-radius: 8px;
  padding: 0.4rem 0.55rem;
  margin: 0 0 0.5rem 0;
  line-height: 1.4;
}
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
.ui-brand-header {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px 16px 0 0;
  padding: 0.7rem 1rem 0.65rem 1rem;
  margin-bottom: 0;
  background: linear-gradient(128deg, #0f172a 0%, #1e3a5f 42%, #312e81 88%);
  color: #f8fafc;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.12);
}
.ui-brand-header + .ui-studio-deck {
  border-radius: 0 0 16px 16px;
  margin-top: 0;
  border-top: none;
}
.ui-brand-row {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
}
.ui-brand-icon {
  font-size: 1.55rem;
  line-height: 1;
  margin-top: 0.12rem;
  filter: drop-shadow(0 2px 8px rgba(147, 197, 253, 0.45));
}
.ui-brand-note {
  font-size: 1.05em;
  margin-right: 0.2rem;
  filter: drop-shadow(0 1px 4px rgba(147, 197, 253, 0.5));
}
.ui-brand-name {
  color: #fef08a;
  font-weight: 900;
}
.ui-brand-byline {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #93c5fd;
  margin: 0 0 0.12rem 0;
  line-height: 1.2;
}
.ui-brand-main-title {
  font-size: 1.48rem;
  font-weight: 900;
  letter-spacing: -0.025em;
  color: #f8fafc;
  margin: 0;
  line-height: 1.15;
}
.ui-brand-tagline {
  font-size: 0.84rem;
  color: #cbd5e1;
  margin: 0.4rem 0 0 0;
  line-height: 1.45;
  max-width: 52rem;
}
.ui-ctrl-section {
  border: 1px solid var(--studio-line);
  border-radius: 12px;
  margin-bottom: 0.55rem;
  background: #fff;
  overflow: hidden;
}
.ui-ctrl-section-head {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.45rem 0.7rem;
  background: linear-gradient(180deg, #f8fafc, #ffffff);
  border-bottom: 1px solid var(--studio-line);
}
.ui-ctrl-letter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.55rem;
  height: 1.55rem;
  border-radius: 8px;
  background: #1e3a5f;
  color: #fff;
  font-size: 0.72rem;
  font-weight: 850;
  flex-shrink: 0;
}
.ui-ctrl-section-title {
  font-size: 0.82rem;
  font-weight: 850;
  color: var(--studio-ink);
  margin: 0;
  line-height: 1.25;
}
.ui-ctrl-section-sub {
  font-size: 0.74rem;
  color: var(--studio-muted);
  margin: 0.12rem 0 0 0;
  line-height: 1.35;
}
.ui-ctrl-section-body {
  padding: 0.55rem 0.7rem 0.6rem 0.7rem;
}
.ui-key-global-hint {
  font-size: 0.78rem;
  color: #0f172a !important;
  background: #f8fafc;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  padding: 0.4rem 0.55rem;
  margin: 0 0 0.45rem 0;
  line-height: 1.4;
}
.ui-sidebar-key-caption {
  font-size: 0.82rem;
  color: #0f172a !important;
  margin: 0.35rem 0 0.55rem 0;
  line-height: 1.45;
}
.ui-transposing-recap,
.ui-transposing-recap strong {
  color: #0f172a !important;
}
.ui-transposing-recap-meta {
  color: #1e293b !important;
}
[data-testid="stSidebar"] .ui-key-global-hint {
  color: #cbd5e1 !important;
  background: rgba(255, 255, 255, 0.06) !important;
  border-color: rgba(255, 255, 255, 0.14) !important;
}
[data-testid="stSidebar"] .ui-key-global-hint * {
  color: inherit !important;
  background: transparent !important;
}
[data-testid="stSidebar"] .ui-sidebar-key-caption,
[data-testid="stSidebar"] .ui-sidebar-key-caption *,
[data-testid="stSidebar"] .ui-sidebar-key-caption strong {
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .ui-sidebar-key-caption strong {
  color: #f8fafc !important;
}
[data-testid="stSidebar"] .ui-transposing-recap.ui-card.soft {
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid rgba(255, 255, 255, 0.14) !important;
}
[data-testid="stSidebar"] .ui-transposing-recap,
[data-testid="stSidebar"] .ui-transposing-recap *,
[data-testid="stSidebar"] .ui-transposing-recap strong,
[data-testid="stSidebar"] .ui-transposing-recap-meta {
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .ui-transposing-recap strong {
  color: #f8fafc !important;
}
.ui-ctrl-section-body .stSelectbox label,
.ui-ctrl-section-body .stSlider label,
.ui-ctrl-section-body .stRadio label {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  color: #475569 !important;
}
.ui-ctrl-hint {
  font-size: 0.78rem;
  color: #475569;
  line-height: 1.4;
  margin: 0 0 0.45rem 0;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
}
.ui-ctrl-hint.key {
  background: #fffbeb;
  border-color: #fde68a;
}
.ui-workspace-panel {
  padding: 0.55rem 0.65rem 0.65rem 0.65rem;
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
.ui-source-kind {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  margin-bottom: 0.2rem;
}
.ui-source-detail {
  font-size: 0.92rem;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.35;
}
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
.ui-studio-deck {
  border: 1px solid rgba(15, 23, 42, 0.11);
  border-radius: 16px;
  margin-bottom: 0.75rem;
  background: linear-gradient(168deg, #ffffff 0%, #f8fafc 55%, #f1f5f9 100%);
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}
.ui-studio-nav {
  border: none;
  border-radius: 0;
  padding: 0;
  margin-bottom: 0.55rem;
  background: transparent;
}
/* Top nav — st.segmented_control (equal segments; no column/button grid) */
.ui-studio-nav-segmented {
  border: 1px solid var(--studio-line);
  border-radius: 12px;
  padding: 0.45rem 0.5rem 0.55rem 0.5rem;
  margin-bottom: 0.75rem;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}
.ui-studio-nav-segmented [data-testid="stButtonGroup"],
.ui-studio-nav-segmented [data-baseweb="button-group"] {
  width: 100% !important;
  min-height: 64px !important;
  display: flex !important;
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
}
.ui-studio-nav-segmented [data-testid="stButtonGroup"] > div {
  flex: 1 1 0 !important;
  min-width: 0 !important;
}
.ui-studio-nav-segmented [data-testid="stBaseButton-segmented_control"],
.ui-studio-nav-segmented [data-testid="stBaseButton-segmented_controlActive"] {
  flex: 1 1 0 !important;
  min-width: 0 !important;
  min-height: 64px !important;
  height: 64px !important;
  max-height: 64px !important;
  padding: 8px 6px !important;
  box-sizing: border-box !important;
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  line-height: 1.15 !important;
  white-space: pre-line !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
}
.ui-studio-nav-segmented [data-testid="stRadio"] {
  width: 100% !important;
}
.ui-studio-nav-segmented [data-testid="stRadio"] label {
  min-height: 64px !important;
  padding: 8px 10px !important;
  white-space: pre-line !important;
  line-height: 1.2 !important;
  font-weight: 700 !important;
  font-size: 0.72rem !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}
/* Sidebar nav mirrors page colors (same active sizing as top bar) */
.ui-sb-nav-wrap .studio-nav-item button {
  box-sizing: border-box !important;
  min-height: 2.1rem !important;
  height: 2.1rem !important;
  max-height: 2.1rem !important;
  font-weight: 700 !important;
  border-width: 1px !important;
  border-style: solid !important;
}
.ui-sb-nav-wrap .studio-nav-item button {
  background: rgba(255, 255, 255, 0.06) !important;
  color: #e2e8f0 !important;
  border-color: rgba(148, 163, 184, 0.28) !important;
}
.ui-sb-nav-wrap .nav-btn-active button {
  background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
  color: #fff !important;
  border-color: rgba(220, 38, 38, 0.65) !important;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.35) !important;
}
.ui-global-bar {
  border: none;
  border-radius: 0;
  padding: 0.65rem 0.75rem 0.6rem 0.75rem;
  margin-bottom: 0;
  background: transparent;
  position: sticky;
  top: 0.35rem;
  z-index: 99;
}
.ui-global-bar .stSelectbox label,
.ui-global-bar .stSlider label,
.ui-global-bar .stRadio label {
  font-size: 0.7rem !important;
  font-weight: 750 !important;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b !important;
  margin-bottom: 0.15rem !important;
}
.ui-global-bar [data-baseweb="select"] > div,
.ui-global-bar .stSlider > div {
  min-height: 2.15rem;
}
.ui-bar-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.4rem 0;
  line-height: 1.2;
}
.ui-bar-label.session { color: #1d4ed8; }
.ui-bar-label.library { color: #6d28d9; margin-top: 0.55rem; }
.ui-bar-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(15,23,42,0.12), transparent);
  margin: 0.5rem 0 0.45rem 0;
}
.ui-now-playing {
  border: 1px solid rgba(29, 78, 216, 0.15);
  border-radius: 12px;
  padding: 0.5rem 0.65rem;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
  min-height: 3.1rem;
}
.ui-now-playing .np-title {
  font-size: 0.98rem;
  font-weight: 850;
  color: #0f172a;
  line-height: 1.25;
  margin: 0;
}
.ui-now-playing .np-meta {
  font-size: 0.76rem;
  color: #64748b;
  margin: 0.2rem 0 0 0;
  line-height: 1.35;
}
.ui-backing-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.35rem 0.65rem;
  font-size: 0.72rem;
  font-weight: 750;
  border: 1px solid var(--studio-line);
  background: #f8fafc;
  color: #64748b;
  margin-top: 0.35rem;
}
.ui-backing-pill.ready {
  background: #f0fdf4;
  border-color: #86efac;
  color: #15803d;
}
.ui-playback-setup {
  background: linear-gradient(145deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid var(--studio-line);
  border-radius: 14px;
  padding: 1rem 1.15rem 1.1rem;
  margin: 0.65rem 0 1rem;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.ui-playback-setup-header {
  margin-bottom: 0.85rem;
}
.ui-playback-setup-title {
  font-size: 1.35rem;
  font-weight: 850;
  color: var(--studio-ink);
  margin: 0;
  line-height: 1.2;
}
.ui-playback-setup-artist {
  font-size: 0.92rem;
  color: var(--studio-muted);
  margin: 0.15rem 0 0;
}
.ui-playback-setup-defaults {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0.35rem 0 0;
}
.ui-playback-setup-label {
  font-size: 0.72rem;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  margin: 0 0 0.25rem;
}
.ui-playback-setup-bpm {
  font-size: 2rem;
  font-weight: 850;
  color: var(--studio-ink);
  line-height: 1;
  margin: 0 0 0.35rem;
}
.ui-playback-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.45rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 750;
  border: 1px solid var(--studio-line);
  background: #fff;
  color: #64748b;
}
.ui-playback-status-badge.ready {
  background: #ecfdf5;
  border-color: #6ee7b7;
  color: #047857;
}
.ui-quick-nav .stButton > button {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  padding: 0.4rem 0.35rem !important;
  min-height: 2.1rem !important;
  border-radius: 10px !important;
}
.ui-compact-title {
  font-size: 1.12rem;
  font-weight: 850;
  color: var(--studio-ink);
  margin: -0.25rem 0 0.5rem 0;
  line-height: 1.25;
}
.ui-compact-sub {
  color: var(--studio-muted);
  font-size: 0.84rem;
  margin: -0.25rem 0 0.65rem 0;
}
.ui-section-jump {
  border: 1px solid var(--studio-line);
  border-radius: var(--studio-radius);
  padding: 0.5rem 0.6rem;
  margin: 0 0 0.65rem 0;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  position: sticky;
  top: 5.5rem;
  z-index: 88;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.05);
}
.ui-section-jump .ui-bar-label { margin-bottom: 0.35rem; color: #64748b; }
.ui-section-jump .jump-btn button {
  font-size: 0.76rem !important;
  padding: 0.32rem 0.45rem !important;
  min-height: 1.85rem !important;
}
.ui-section-jump [data-testid="stRadio"] label[data-baseweb="radio"] {
  border-radius: 999px !important;
  padding: 0.28rem 0.55rem !important;
  font-size: 0.74rem !important;
  font-weight: 700 !important;
  border: 1px solid rgba(148, 163, 184, 0.35) !important;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease !important;
}
.ui-section-jump [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
.ui-section-jump [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background: rgba(220, 38, 38, 0.1) !important;
  border-color: rgba(220, 38, 38, 0.55) !important;
  color: #dc2626 !important;
}
.ui-practice-top {
  border: 1px solid rgba(109, 40, 217, 0.12);
  border-radius: var(--studio-radius);
  padding: 0.7rem 0.8rem 0.75rem 0.8rem;
  margin-bottom: 0.7rem;
  background: linear-gradient(180deg, #ffffff 0%, #faf5ff 100%);
  box-shadow: 0 1px 8px rgba(109, 40, 217, 0.06);
}
.ui-practice-top-title {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #6d28d9;
  margin: 0 0 0.55rem 0;
}
.ui-practice-top .stCaption, .ui-practice-top p[data-testid="stCaptionContainer"] {
  font-size: 0.8rem !important;
  color: #64748b !important;
}
.ui-practice-top [data-baseweb="select"] > div {
  border-radius: 10px !important;
}
.ui-page-nav-label {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.35rem 0;
}
.ui-studio-nav.ui-page-nav {
  border: 1px solid var(--studio-line);
  border-radius: 12px;
  padding: 0.45rem 0.5rem;
  margin-bottom: 0.75rem;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}
.ui-cross-links {
  margin: 0.35rem 0 0.75rem 0;
}
.ui-cross-links .stButton > button {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  min-height: 2rem !important;
  border-radius: 10px !important;
}
.ui-song-card-grid {
  margin: 0.5rem 0 1rem 0;
}
.ui-song-card {
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 14px;
  padding: 0.85rem 0.9rem 0.75rem 0.9rem;
  margin-bottom: 0.65rem;
  background: linear-gradient(145deg, #ffffff 0%, #f8fafc 55%, #f1f5f9 100%);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
  min-height: 11.5rem;
}
.ui-song-card.trusted {
  border-color: rgba(34, 197, 94, 0.35);
  background: linear-gradient(145deg, #f0fdf4 0%, #ffffff 60%, #f8fafc 100%);
}
.ui-song-card.active {
  border-color: rgba(29, 78, 216, 0.45);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.18);
}
.ui-song-card.active .ui-song-card-title::after {
  content: " · Active";
  font-size: 0.72rem;
  font-weight: 700;
  color: #2563eb;
}
.ui-song-card-title {
  font-size: 1.05rem;
  font-weight: 850;
  color: #0f172a;
  margin: 0 0 0.15rem 0;
  line-height: 1.25;
}
.ui-song-card-artist {
  font-size: 0.82rem;
  color: #64748b;
  margin: 0 0 0.55rem 0;
}
.ui-song-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.55rem;
}
.ui-song-pill {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  border: 1px solid rgba(99, 102, 241, 0.15);
}
.ui-song-pill.key { background: #ecfdf5; color: #047857; border-color: rgba(16, 185, 129, 0.2); }
.ui-song-pill.genre { background: #faf5ff; color: #6d28d9; border-color: rgba(139, 92, 246, 0.2); }
.ui-song-pill.bpm { background: #fff7ed; color: #c2410c; border-color: rgba(249, 115, 22, 0.2); }
.ui-song-card-actions .stButton > button {
  font-size: 0.7rem !important;
  font-weight: 700 !important;
  min-height: 1.85rem !important;
  border-radius: 8px !important;
}
.ui-active-song-card {
  display: grid;
  grid-template-columns: 108px 1fr;
  gap: 0.95rem;
  border: 1px solid rgba(29, 78, 216, 0.28);
  border-radius: 16px;
  padding: 0.95rem 1rem;
  margin: 0.35rem 0 0.75rem 0;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 48%, #eff6ff 100%);
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.08);
}
.ui-active-song-card.trusted {
  border-color: rgba(34, 197, 94, 0.35);
  background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 55%, #eff6ff 100%);
}
.ui-active-song-art {
  border-radius: 14px;
  min-height: 108px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #f8fafc;
  font-size: 2rem;
  font-weight: 900;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
}
.ui-active-song-art small {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.92;
}
.ui-active-song-kicker {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #2563eb;
  margin: 0 0 0.2rem 0;
}
.ui-active-song-title {
  font-size: 1.22rem;
  font-weight: 900;
  color: #0f172a;
  margin: 0 0 0.1rem 0;
  line-height: 1.2;
}
.ui-active-song-artist {
  font-size: 0.88rem;
  color: #64748b;
  margin: 0 0 0.55rem 0;
}
.ui-active-song-meta-row {
  margin: 0.35rem 0 0.5rem;
  font-size: 0.8rem;
  color: #475569;
  line-height: 1.45;
}
.ui-active-song-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem 0.65rem;
  margin: 0 0 0.55rem 0;
  font-size: 0.78rem;
  color: #334155;
}
.ui-active-song-facts dt {
  font-weight: 800;
  color: #64748b;
  margin: 0;
}
.ui-active-song-facts dd {
  margin: 0;
  font-weight: 650;
}
.ui-active-song-blurb {
  font-size: 0.8rem;
  color: #475569;
  line-height: 1.45;
  margin: 0 0 0.45rem 0;
}
.ui-active-song-goals {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.76rem;
  color: #334155;
  line-height: 1.4;
}
.ui-active-song-goals li { margin-bottom: 0.2rem; }
@media (max-width: 720px) {
  .ui-active-song-card { grid-template-columns: 1fr; }
  .ui-active-song-art { min-height: 84px; flex-direction: row; gap: 0.5rem; font-size: 1.6rem; }
}
/* Active Song Hub — centerpiece control on Song Selection */
.st-key-active_song_hub {
  border: 1px solid rgba(30, 64, 175, 0.22);
  border-radius: 20px;
  padding: 0.15rem 0.85rem 0.85rem 0.85rem;
  margin: 0.5rem 0 1rem 0;
  background: linear-gradient(165deg, #ffffff 0%, #f8fafc 42%, #eff6ff 100%);
  box-shadow: 0 10px 36px rgba(30, 64, 175, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.ui-active-song-hub-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  margin: 0.55rem 0 0.35rem 0;
  flex-wrap: wrap;
}
.ui-active-song-hub-label {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #1d4ed8;
}
.ui-active-song-hub-label::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.28);
  animation: ui-active-song-pulse 1.8s ease-in-out infinite;
}
@keyframes ui-active-song-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.65; transform: scale(0.88); }
}
.ui-active-song-hub-sub {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0;
}
.ui-active-song-hub .ui-active-song-genre-line {
  font-size: 0.8rem;
  font-weight: 700;
  color: #6d28d9;
  margin: 0 0 0.5rem 0;
}
.ui-active-song-meta-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0 0 0.65rem 0;
}
.ui-active-song-meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 750;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(15, 23, 42, 0.1);
  color: #334155;
}
.ui-active-song-meta-pill strong { color: #0f172a; font-weight: 850; }
.ui-active-song-key-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem 0.55rem;
  margin: 0.45rem 0 0.55rem;
  padding: 0.5rem 0.62rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: linear-gradient(135deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.92));
}
.ui-active-song-key-row.is-shifted {
  border-color: rgba(99, 102, 241, 0.35);
  background: linear-gradient(135deg, rgba(238, 242, 255, 0.95), rgba(224, 231, 255, 0.55));
}
.ui-active-song-key-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 0.12rem;
  min-width: 5.5rem;
}
.ui-active-song-key-chip.practice .ui-active-song-key-value {
  color: #4338ca;
}
.ui-active-song-key-row.is-shifted .ui-active-song-key-chip.practice .ui-active-song-key-value {
  font-weight: 900;
}
.ui-active-song-key-label {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}
.ui-active-song-key-value {
  font-size: 1.02rem;
  font-weight: 850;
  color: #0f172a;
  line-height: 1.15;
}
.ui-active-song-key-arrow {
  font-size: 1rem;
  font-weight: 700;
  color: #94a3b8;
  padding: 0 0.15rem;
}
.ui-active-song-hero-strip .ui-active-song-key-row {
  margin: 0.35rem 0 0.5rem;
  max-width: 28rem;
}
.ui-backing-active-song .ui-active-song-key-row {
  margin: 0.5rem 0 0.65rem;
  max-width: 100%;
}
.ui-backing-active-song .ui-active-song-key-label {
  color: #93c5fd;
}
.ui-backing-active-song .ui-active-song-key-value {
  color: #0f172a;
}
.ui-backing-active-source {
  font-size: 0.82rem;
  font-weight: 700;
  color: #bfdbfe;
}
.ui-active-song-hub-actions .stButton > button {
  font-weight: 750 !important;
  min-height: 2.1rem !important;
}
.ui-active-song-recent {
  margin: 0.35rem 0 0.15rem 0;
  padding-top: 0.45rem;
  border-top: 1px dashed rgba(15, 23, 42, 0.12);
}
.ui-active-song-recent-label {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.35rem 0;
}
.ui-last-catalog-shortcut {
  margin: 0.35rem 0 0;
  padding-top: 0.45rem;
  border-top: 1px dashed rgba(15, 23, 42, 0.12);
}
.ui-last-catalog-kicker {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.35rem 0;
}
.st-key-custom_hub_restore_last_catalog button,
.st-key-catalog_hub_restore_last_catalog button {
  font-weight: 700 !important;
  color: #0f172a !important;
  background: rgba(255, 255, 255, 0.55) !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  text-align: left !important;
  justify-content: flex-start !important;
}
.ui-custom-library-label {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.35rem 0;
}
.st-key-active_song_hub .ui-active-song-hero-title {
  font-size: clamp(1.75rem, 4vw, 2.35rem);
  font-weight: 900;
  letter-spacing: -0.04em;
  color: #0f172a;
  margin: 0;
  line-height: 1.1;
}
.st-key-active_song_hub .ui-active-song-hero-strip {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 1rem;
  align-items: center;
  padding: 0.85rem 1rem;
  margin: 0.65rem 0 0.75rem 0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(37, 99, 235, 0.22);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}
.st-key-active_song_hub .ui-active-song-hero-art {
  border-radius: 14px;
  min-height: 88px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #f8fafc;
  font-size: 2rem;
  font-weight: 900;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}
.st-key-active_song_hub .ui-active-song-hero-art small {
  font-size: 0.58rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 0.25rem;
}
.st-key-active_song_hub .ui-active-song-hero-artist {
  font-size: 0.92rem;
  color: #475569;
  margin: 0.15rem 0 0 0;
}
.st-key-active_song_hub .ui-active-song-picker-label {
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #1e40af;
  margin: 0.35rem 0 0.25rem 0;
}
.st-key-active_song_hub [data-testid="stSelectbox"] > div > div {
  border: 2px solid rgba(37, 99, 235, 0.35) !important;
  border-radius: 12px !important;
  background: #ffffff !important;
  color: #111827 !important;
  font-weight: 700 !important;
  min-height: 2.65rem !important;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.1) !important;
}
.st-key-active_song_hub [data-testid="stSelectbox"] > div > div * {
  color: #111827 !important;
  -webkit-text-fill-color: #111827 !important;
}
.st-key-active_song_hub [data-testid="stSelectbox"] > div > div:focus-within {
  border-color: #2563eb !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18) !important;
}
.st-key-song_library_panel .ui-song-library-genre-chips-label {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0.45rem 0 0.35rem 0;
}
.st-key-song_library_panel .ui-genre-filter-active-summary {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0.35rem 0 0.15rem 0;
  line-height: 1.4;
}
.st-key-song_library_panel .ui-genre-filter-active-summary strong {
  color: #b91c1c;
  font-weight: 800;
}
.st-key-song_library_panel [class*="st-key-genre_pill_"] .stButton > button,
.st-key-song_library_panel [class*="st-key-genre_more_"] .stButton > button {
  border-radius: 999px !important;
  font-size: 0.78rem !important;
  font-weight: 750 !important;
  letter-spacing: 0.02em !important;
  min-height: 2rem !important;
  padding: 0.28rem 0.65rem !important;
  border: 1px solid rgba(148, 163, 184, 0.55) !important;
  background: rgba(255, 255, 255, 0.92) !important;
  color: #334155 !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease !important;
}
.st-key-song_library_panel [class*="st-key-genre_pill_"] .stButton > button:hover,
.st-key-song_library_panel [class*="st-key-genre_more_"] .stButton > button:hover {
  transform: translateY(-1px);
  border-color: rgba(220, 38, 38, 0.45) !important;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.12) !important;
}
.st-key-song_library_panel [class*="st-key-genre_pill_"] .stButton > button[kind="primary"],
.st-key-song_library_panel [class*="st-key-genre_more_"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 55%, #b91c1c 100%) !important;
  border-color: rgba(220, 38, 38, 0.85) !important;
  color: #ffffff !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.15) inset, 0 4px 16px rgba(220, 38, 38, 0.38) !important;
}
.st-key-song_library_panel .st-key-genre_clear_filters .stButton > button {
  border-radius: 999px !important;
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  min-height: 1.85rem !important;
  border: 1px dashed rgba(148, 163, 184, 0.65) !important;
  background: transparent !important;
  color: #64748b !important;
}
.st-key-song_library_panel .st-key-genre_clear_filters .stButton > button:hover {
  border-color: rgba(220, 38, 38, 0.55) !important;
  color: #b91c1c !important;
  background: rgba(254, 226, 226, 0.35) !important;
}
.ui-active-song-hub.source-custom,
.st-key-active_song_hub .ui-active-song-hub.source-custom {
  border: 2px solid rgba(234, 88, 12, 0.45);
  box-shadow: 0 8px 28px rgba(234, 88, 12, 0.18);
}
.ui-active-song-hub.source-custom .ui-active-song-hero-title,
.st-key-active_song_hub .source-custom .ui-active-song-hero-title {
  color: #fff7ed;
}
.ui-backing-active-song {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 0.9rem;
  border: 1px solid rgba(30, 64, 175, 0.45);
  border-radius: 16px;
  padding: 0.9rem 1rem;
  margin: 0.25rem 0 0.85rem 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 38%, #1e40af 72%, #172554 100%);
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.22);
  color: #f8fafc;
}
.ui-backing-active-art {
  border-radius: 14px;
  min-height: 96px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 1.85rem;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.15);
}
.ui-backing-active-art small {
  display: block;
  margin-top: 0.3rem;
  font-size: 0.58rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  opacity: 0.9;
}
.ui-backing-active-kicker {
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #93c5fd;
  margin: 0 0 0.25rem 0;
}
.ui-backing-active-title {
  font-size: 1.15rem;
  font-weight: 900;
  margin: 0 0 0.5rem 0;
  line-height: 1.25;
  color: #f8fafc;
}
.ui-backing-active-dash { font-weight: 500; color: #94a3b8; }
.ui-backing-active-badges { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.ui-backing-badge {
  font-size: 0.68rem;
  font-weight: 800;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.1);
}
.ui-backing-badge.genre { background: rgba(139, 92, 246, 0.35); border-color: rgba(167, 139, 250, 0.45); }
.ui-backing-badge.bpm { background: rgba(249, 115, 22, 0.28); border-color: rgba(251, 146, 60, 0.45); }
.ui-backing-badge.groove { background: rgba(34, 197, 94, 0.22); border-color: rgba(74, 222, 128, 0.4); }
.ui-backing-badge.badge-style { background: rgba(37, 99, 235, 0.24); border-color: rgba(96, 165, 250, 0.45); color: #eff6ff; }
.ui-backing-badge.badge-mood { background: rgba(124, 58, 237, 0.24); border-color: rgba(167, 139, 250, 0.45); color: #f5f3ff; }
.ui-backing-badge.badge-groove { background: rgba(234, 88, 12, 0.24); border-color: rgba(251, 146, 60, 0.45); color: #fff7ed; }
.ui-backing-badge.badge-key { background: rgba(14, 165, 233, 0.22); border-color: rgba(56, 189, 248, 0.42); color: #f0f9ff; }
.ui-backing-badge.badge-meta { background: rgba(100, 116, 139, 0.28); border-color: rgba(148, 163, 184, 0.45); color: #f8fafc; }
.mode-creative-backing {
  border-left: 4px solid var(--creative-accent, #5b21b6);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
}
.ui-creative-jam-card {
  background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.92) 100%);
  border-radius: 14px;
  overflow: hidden;
}
.ui-creative-jam-body {
  background: linear-gradient(180deg, rgba(255,255,255,0.0) 0%, rgba(99,102,241,0.04) 100%);
}
.ui-backing-badge.badge-groove-light { background: rgba(45, 212, 191, 0.22); border-color: rgba(45, 212, 191, 0.45); }
.ui-backing-badge.badge-groove-heavy { background: rgba(220, 38, 38, 0.24); border-color: rgba(248, 113, 113, 0.5); }
.ui-backing-locked-setting {
  margin: 0.15rem 0 0.35rem;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.18);
  font-size: 0.82rem;
  color: #1e293b;
}
.ui-backing-locked-setting small { color: #64748b; }
.ui-instrument-strip {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  border-left: 3px solid #64748b;
  padding: 0.45rem 0.65rem;
  margin: -0.15rem 0 0.75rem 0;
  background: linear-gradient(90deg, rgba(248, 250, 252, 0.95) 0%, rgba(255, 255, 255, 0) 100%);
  border-radius: 0 10px 10px 0;
  font-size: 0.78rem;
  color: #475569;
  line-height: 1.4;
}
.ui-instrument-strip-icon { font-size: 1.05rem; line-height: 1.2; }
.ui-instrument-strip-body strong { color: #0f172a; font-weight: 800; }
.ui-instrument-strip-muted { color: #64748b; }
.ui-instrument-pitch-family {
  margin: -0.35rem 0 0.75rem 0;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  display: inline-block;
  background: #eef2ff;
  color: #3730a3;
  font-size: 0.82rem;
  font-weight: 700;
}
/* Temporary deploy verification — remove after confirming Streamlit Cloud runs dev */
.ui-nav-deploy-marker {
  position: fixed !important;
  bottom: max(0.5rem, env(safe-area-inset-bottom, 0px)) !important;
  left: 50% !important;
  transform: translateX(-50%) !important;
  z-index: 9600 !important;
  margin: 0 !important;
  padding: 0.4rem 0.9rem !important;
  border-radius: 8px !important;
  background: #15803d !important;
  color: #f0fdf4 !important;
  font-size: 0.78rem !important;
  font-weight: 800 !important;
  letter-spacing: 0.02em !important;
  line-height: 1.3 !important;
  text-align: center !important;
  box-shadow: 0 6px 18px rgba(21, 128, 61, 0.45) !important;
  border: 1px solid #86efac !important;
  pointer-events: none !important;
}
/* Floating back / forward — mid-viewport, gutter-safe (JS sets --studio-history-*) */
[data-testid="stSidebar"] [class*="st-key-studio_nav_back_btn"],
[data-testid="stSidebar"] [class*="st-key-studio_nav_forward_btn"] {
  display: none !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"],
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] {
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: visible !important;
  pointer-events: none !important;
  border: none !important;
  background: transparent !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton,
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton {
  position: fixed !important;
  top: 50vh !important;
  transform: translateY(-50%) !important;
  z-index: 99990 !important;
  margin: 0 !important;
  width: auto !important;
  pointer-events: auto !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton {
  left: var(--studio-history-back-left, 12rem) !important;
  right: auto !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton {
  right: var(--studio-history-fwd-right, 1rem) !important;
  left: auto !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button,
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button,
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] button[kind="secondary"],
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] button[kind="secondary"],
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] [data-testid="stBaseButton-secondary"],
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] [data-testid="stBaseButton-secondary"] {
  pointer-events: auto !important;
  z-index: 99991 !important;
  min-height: 2.65rem !important;
  height: auto !important;
  min-width: 2.65rem !important;
  padding: 0.4rem 0.65rem !important;
  margin: 0 !important;
  font-size: 0.82rem !important;
  font-weight: 700 !important;
  line-height: 1.15 !important;
  letter-spacing: 0.01em !important;
  border-radius: 999px !important;
  border: 1px solid rgba(148, 163, 184, 0.42) !important;
  background: rgba(15, 23, 42, 0.52) !important;
  color: #e2e8f0 !important;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.22) !important;
  opacity: 0.58 !important;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  transition: opacity 0.16s ease, background 0.16s ease, border-color 0.16s ease,
    box-shadow 0.16s ease, transform 0.12s ease !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button:hover:not(:disabled),
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button:hover:not(:disabled) {
  opacity: 1 !important;
  background: rgba(30, 41, 59, 0.92) !important;
  border-color: rgba(148, 163, 184, 0.62) !important;
  color: #f8fafc !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.32) !important;
  transform: translateY(-50%) scale(1.03) !important;
}
section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button:disabled,
section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button:disabled {
  opacity: 0.28 !important;
  cursor: default !important;
  box-shadow: none !important;
  transform: translateY(-50%) !important;
}
@media (max-width: 640px) {
  section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button,
  section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button {
    min-height: 2.85rem !important;
    min-width: 2.85rem !important;
    padding: 0.45rem 0.55rem !important;
    font-size: 1.05rem !important;
  }
}
@media (max-width: 420px) {
  section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button,
  section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button {
    font-size: 0 !important;
  }
  section[data-testid="stMain"] [class*="st-key-studio_nav_back_btn"] .stButton > button::after {
    content: "←" !important;
    font-size: 1.15rem !important;
  }
  section[data-testid="stMain"] [class*="st-key-studio_nav_forward_btn"] .stButton > button::after {
    content: "→" !important;
    font-size: 1.15rem !important;
  }
}
.live-player-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.live-stop-btn {
  border: 1px solid #b91c1c;
  background: #fef2f2;
  color: #b91c1c;
  font-weight: 800;
  border-radius: 10px;
  padding: 8px 14px;
  cursor: pointer;
}
.live-stop-btn:hover { background: #fee2e2; }
/* Practice notation / TAB output */
.notation-output {
  border: 2px solid #0f172a;
  border-radius: 12px;
  background: #fffef5;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 1rem 0;
}
.notation-output .notation-title {
  font-size: 1rem;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 0.35rem;
}
.notation-output .notation-chords {
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  color: #1e40af;
}
.notation-output .notation-tab-pre {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 0.95rem;
  line-height: 1.35;
  background: #0f172a;
  color: #f8fafc;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0;
  white-space: pre;
}
.notation-output .notation-rhythm {
  font-size: 0.82rem;
  margin-top: 0.5rem;
  color: #475569;
}
/* Guitar TAB lesson layout */
.notation-output.notation-tab .tab-lesson {
  font-family: "Consolas", "Courier New", "Liberation Mono", monospace;
  font-size: 1.05rem;
  line-height: 1.45;
  color: #0f172a;
}
.tab-legend {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  margin-bottom: 0.75rem;
  font-size: 0.78rem;
}
.tab-legend-title {
  display: block;
  font-weight: 800;
  font-size: 0.82rem;
  margin-bottom: 0.25rem;
  color: #1e3a8a;
}
.tab-legend-list {
  margin: 0;
  padding-left: 1.1rem;
  columns: 2;
  column-gap: 1.25rem;
}
.tab-legend-list li { margin: 0.12rem 0; }
.tab-section-badge {
  display: inline-block;
  font-weight: 800;
  font-size: 0.88rem;
  color: #1e40af;
  background: #dbeafe;
  border-radius: 6px;
  padding: 0.15rem 0.55rem;
  margin-bottom: 0.35rem;
}
.tab-progression {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.65rem;
  font-size: 0.92rem;
}
.tab-prog-chord {
  font-weight: 800;
  padding: 0.2rem 0.55rem;
  border: 2px solid #1e40af;
  border-radius: 8px;
  background: #eff6ff;
  color: #1e3a8a;
}
.tab-cues {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 0.82rem;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 10px;
  padding: 0.45rem 0.7rem;
  margin-bottom: 0.75rem;
}
.tab-cues ul { margin: 0.25rem 0 0 1rem; padding: 0; }
.tab-cues li { margin: 0.15rem 0; }
.tab-scroll-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 0.35rem;
  margin: 0 -0.25rem;
}
.tab-measures-row {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 1.25rem;
  min-width: min-content;
  padding: 0.25rem 0.15rem 0.5rem 0.15rem;
}
.tab-measure {
  flex: 0 0 auto;
  min-width: 11.5rem;
  padding: 0.65rem 0.75rem 0.55rem 0.75rem;
  border: 2px solid #334155;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
}
.tab-measure-transition {
  border-color: #ea580c;
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 40%);
  box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.15);
}
.tab-measure-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.4rem;
}
.tab-chord-name {
  font-size: 1.35rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: 0.02em;
}
.tab-bar-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
}
.tab-transition-badge {
  font-size: 0.7rem;
  font-weight: 800;
  color: #c2410c;
  background: #ffedd5;
  border-radius: 6px;
  padding: 0.1rem 0.4rem;
}
.tab-count-row,
.tab-strum-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.15rem;
  margin-left: 1.35rem;
  margin-bottom: 0.12rem;
  font-size: 0.78rem;
}
.tab-strum-row { margin-bottom: 0.35rem; color: #475569; }
.tab-count-cell,
.tab-strum-cell {
  display: inline-flex;
  justify-content: center;
  min-width: 1.65rem;
  font-weight: 700;
}
.tab-strum-accent { color: #1d4ed8; font-size: 1rem; }
.tab-string-line {
  display: flex;
  align-items: center;
  white-space: nowrap;
  margin: 0.06rem 0;
}
.tab-str-label {
  display: inline-block;
  width: 1.1rem;
  font-weight: 800;
  color: #64748b;
  flex-shrink: 0;
}
.tab-str-track {
  display: inline-flex;
  gap: 0.1rem;
  letter-spacing: 0.02em;
}
.tab-str-low .tab-str-label { color: #0f172a; font-weight: 900; }
.tab-beat {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 1.65rem;
  height: 1.55rem;
  border-bottom: 2px solid #cbd5e1;
  color: #94a3b8;
  font-size: 0.85rem;
}
.tab-beat-fret {
  color: #0f172a;
  font-weight: 900;
  font-size: 1.05rem;
  border-bottom-color: #1e40af;
}
.tab-beat-hi .tab-beat-fret,
.tab-beat-hi {
  color: #b45309;
  background: #fef3c7;
  border-radius: 4px;
  border-bottom-color: #f59e0b;
}
.tab-beat-muted { color: #cbd5e1; }
@media (max-width: 768px) {
  .notation-output.notation-tab .tab-lesson { font-size: 1.15rem; }
  .tab-measure { min-width: 13rem; padding: 0.75rem 0.85rem; }
  .tab-measures-row { gap: 1.5rem; }
  .tab-chord-name { font-size: 1.5rem; }
  .tab-beat { min-width: 1.85rem; height: 1.75rem; font-size: 0.95rem; }
  .tab-beat-fret { font-size: 1.15rem; }
  .tab-count-cell, .tab-strum-cell { min-width: 1.85rem; }
  .tab-legend-list { columns: 1; }
}
/* Practice setup pills */
.practice-setup-card {
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 0.65rem 0.85rem 0.35rem 0.85rem;
  margin-bottom: 0.75rem;
}
.setup-field-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
  margin-top: 0.15rem;
}
.setup-quick-row {
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.35rem 0.5rem 0.15rem 0.5rem;
  margin: 0.35rem 0 0.65rem 0;
}
.setup-quick-row [data-testid="stCaptionContainer"] p {
  font-size: 0.78rem;
  margin-bottom: 0.2rem;
}
.setup-quick-row [data-testid="column"] .stSelectbox label {
  font-size: 0.78rem;
  font-weight: 600;
}
/* Guided tutorial */
.tutorial-sidebar-entry {
  margin: 0 0 0.65rem 0;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid #e2e8f0;
}
.tutorial-hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 45%, #312e81 100%);
  color: #f8fafc;
  border-radius: 16px;
  padding: 1.25rem 1.35rem 1rem 1.35rem;
  margin-bottom: 1rem;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
}
.tutorial-hero-head {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}
.tutorial-hero-icon {
  font-size: 2.4rem;
  line-height: 1;
}
.tutorial-kicker {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #93c5fd;
}
.tutorial-title {
  margin: 0.15rem 0 0.25rem 0;
  font-size: 1.45rem;
  font-weight: 800;
  color: #fff;
}
.tutorial-sub {
  margin: 0;
  font-size: 0.92rem;
  color: #cbd5e1;
}
.tutorial-progress-track {
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  margin-top: 1rem;
  overflow: hidden;
}
.tutorial-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  border-radius: 999px;
  transition: width 0.25s ease;
}
.tutorial-quick-card {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 0.85rem 1rem;
  margin-bottom: 1rem;
}
.tutorial-quick-title {
  margin: 0 0 0.45rem 0;
  font-weight: 800;
  color: #92400e;
  font-size: 0.95rem;
}
.tutorial-quick-start {
  margin: 0;
  padding-left: 1.15rem;
  color: #78350f;
  font-size: 0.9rem;
  line-height: 1.55;
}
.tutorial-step-card {
  margin-bottom: 0.35rem;
}
.tutorial-step-label {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.tutorial-step-title {
  margin: 0.2rem 0 0.5rem 0;
  font-size: 1.25rem;
  color: #0f172a;
}
/* Custom progression steps */
.cpl-step-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin: 1rem 0 0.65rem 0;
  padding: 0.5rem 0;
  border-bottom: 2px solid #e2e8f0;
}
.cpl-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.65rem;
  height: 1.65rem;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  font-size: 0.85rem;
  font-weight: 800;
}
.cpl-step-title {
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
}
.cpl-chord-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0.65rem 0 0.85rem 0;
}
.cpl-chord-row.empty {
  color: #64748b;
  font-style: italic;
  padding: 0.5rem;
}
.cpl-chord-tile {
  min-width: 4.75rem;
  padding: 0.7rem 0.9rem;
  border-radius: 12px;
  border: 2px solid #93c5fd;
  background: linear-gradient(180deg, #ffffff 0%, #eff6ff 100%);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.12);
  text-align: center;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
}
.cpl-chord-tile-hold {
  border-color: #6366f1;
  background: linear-gradient(180deg, #ffffff 0%, #eef2ff 100%);
}
.cpl-chord-mult {
  font-size: 0.72rem;
  font-weight: 800;
  color: #4338ca;
  letter-spacing: 0.03em;
}
.cpl-chord-name {
  font-size: 1.05rem;
  font-weight: 900;
  color: #1e3a8a;
  letter-spacing: 0.02em;
}
.cpl-section-card {
  margin: 0.65rem 0;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.cpl-section-card.cpl-section-active {
  border-color: #2563eb;
  background: #f8fbff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}
.cpl-finish-panel {
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 1.25rem 1.35rem;
  margin: 1rem 0;
}
.cpl-style-hint {
  font-size: 0.88rem;
  color: #64748b;
  margin: 0.25rem 0 0.75rem 0;
}
.cpl-custom-chord-row {
  margin: 0.5rem 0 1rem 0;
}
.cpl-title-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin: 0.5rem 0 1rem 0;
}
.cpl-steps-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.75rem 0 1.1rem 0;
}
.cpl-step-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 0.82rem;
  font-weight: 700;
  color: #64748b;
}
.cpl-step-pill.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}
.cpl-step-pill.done {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}
.cpl-step-pill .cpl-step-n {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: #e2e8f0;
  color: #334155;
  font-size: 0.72rem;
  font-weight: 800;
}
.cpl-step-pill.active .cpl-step-n {
  background: #2563eb;
  color: #fff;
}
.cpl-step-pill.done .cpl-step-n {
  background: #22c55e;
  color: #fff;
}
.cpl-lead-grid,
.lead-grid.cpl-lead-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 10px 12px;
  margin: 0.35rem 0 0.15rem 0;
}
.cpl-measures {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin: 0.15rem 0;
}
.cpl-measure-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  padding: 0.35rem 0;
}
.cpl-measure-bar {
  font-size: 1.35rem;
  font-weight: 300;
  color: #94a3b8;
  line-height: 1;
  user-select: none;
}
.cpl-bar-chart-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.45rem;
  padding: 0.2rem 0;
  font-family: "Consolas", "Courier New", monospace;
}
.cpl-bar-chart-block {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0.15rem 0;
}
.cpl-bar-chord-cell {
  font-size: 1.15rem;
  font-weight: 800;
  color: #1e3a8a;
  padding: 0.1rem 0.35rem;
  min-width: 2rem;
  text-align: center;
}
.cpl-live-progression {
  min-height: 3.5rem;
  padding: 0.65rem 0.75rem;
  background: #f8fafc;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  margin: 0.5rem 0 0.85rem 0;
}
.cpl-pending-hint {
  font-size: 0.92rem;
  font-weight: 700;
  color: #2563eb;
  margin: 0 0 0.65rem 0;
}
.cpl-lead-sheet-form {
  margin: 0.25rem 0;
}
.cpl-form-label {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0.15rem 0.45rem;
  margin-bottom: 0.35rem;
}
.cpl-lead-section {
  border-left: 4px solid #6366f1;
}
.cpl-repeat-cell {
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important;
  border-style: dashed !important;
  border-color: #94a3b8 !important;
}
.cpl-repeat-cell .chord-symbol {
  font-size: 1.15rem;
  font-weight: 800;
  color: #64748b;
}
.cpl-lead-measure-row {
  background: #fafbfc;
  border-radius: 8px;
  padding: 0.25rem 0.15rem;
}
.cpl-chord-cell,
.chord-cell.cpl-chord-cell {
  min-height: 64px;
  border: 1.5px solid rgba(15, 23, 42, 0.18);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
}
.cpl-chord-cell .chord-symbol,
.chord-cell.cpl-chord-cell .chord-symbol {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 1.2rem;
  font-weight: 900;
  color: #1e3a8a;
  letter-spacing: -0.02em;
}
.cpl-builder-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin: 0.65rem 0;
}
.cpl-now-editing {
  font-size: 1.55rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0.35rem 0 0.85rem 0;
  letter-spacing: -0.02em;
}
.cpl-song-title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #1e3a8a;
  margin: 0 0 0.65rem 0;
}
.cpl-section-heading {
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 0.35rem 0;
}
.cpl-key-line {
  font-size: 0.9rem;
  color: #64748b;
  margin: 0 0 0.75rem 0;
}
.cpl-preset-block {
  margin: 0.75rem 0 0.25rem 0;
}
.cpl-flow-hint {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 12px;
  padding: 0.75rem 1rem;
  margin: 0.5rem 0 1rem 0;
  font-size: 0.92rem;
  line-height: 1.5;
  color: #0f172a;
}
.cpl-progression-line {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 1.35rem;
  font-weight: 700;
  color: #1e3a8a;
  background: #f8fafc;
  border: 2px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  margin: 0.35rem 0 0.75rem 0;
}
.cpl-progression-line.cpl-empty {
  color: #94a3b8;
  font-weight: 600;
  font-style: italic;
  font-size: 1.1rem;
}
.cpl-slot-row {
  margin: 0.15rem 0 0.25rem 0;
}
.cpl-slot-chord {
  display: inline-block;
  font-size: 1.2rem;
  font-weight: 900;
  color: #1e40af;
  background: #eff6ff;
  border: 2px solid #93c5fd;
  border-radius: 8px;
  padding: 0.25rem 0.65rem;
}
.cpl-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1rem 1.1rem;
  margin: 0.75rem 0;
}
.cpl-panel-muted {
  background: #f8fafc;
}
.cpl-song-map {
  margin: 0.5rem 0;
}
.cpl-song-flow {
  font-size: 0.95rem;
  line-height: 1.55;
  color: #334155;
  margin: 0 0 0.85rem 0;
  padding: 0.55rem 0.75rem;
  background: #f1f5f9;
  border-radius: 10px;
  border-left: 4px solid #2563eb;
}
.cpl-section-block {
  margin: 0.45rem 0;
  padding: 0.5rem 0.65rem;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fafafa;
}
.cpl-section-block.cpl-section-active {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.cpl-section-label {
  font-size: 0.95rem;
  font-weight: 800;
  text-transform: none;
  letter-spacing: normal;
  color: #334155;
  margin-bottom: 0.35rem;
}
.cpl-section-bars {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1e3a8a;
}
.cpl-edit-slot {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
  margin: 0.5rem 0;
  background: #fff;
}
.practice-worksheet-removed {
  display: none;
}
@media (max-width: 900px) {
  .ui-brand-header { border-radius: 12px 12px 0 0; padding: 0.6rem 0.75rem; }
  .ui-brand-main-title { font-size: 1.12rem; }
  .ui-brand-tagline { font-size: 0.78rem; }
  .ui-studio-deck { border-radius: 12px; }
  .ui-global-bar { position: relative; top: 0; padding: 0.55rem 0.6rem; }
  .ui-studio-nav { padding: 0.4rem 0.45rem; }
  .ui-studio-nav-segmented [data-testid="stBaseButton-segmented_control"],
  .ui-studio-nav-segmented [data-testid="stBaseButton-segmented_controlActive"] {
    font-size: 0.66rem !important;
    min-height: 58px !important;
    height: 58px !important;
    max-height: 58px !important;
  }
  .ui-now-playing .np-title { font-size: 0.9rem; }
  .ui-section-jump { top: 0.25rem; }
  .lead-grid { grid-template-columns: repeat(2, minmax(88px, 1fr)) !important; }
}
</style>
        """,
        unsafe_allow_html=True,
    )
    _inject_app_theme_polish()
    _inject_studio_history_nav_pin_script()


def _inject_studio_history_nav_pin_script() -> None:
    """Pin back/forward in the sidebar/main gutter (stable — no full-DOM mutation loop)."""
    import streamlit as st

    st.markdown(
        """
<script>
(function () {
  if (window.__studioHistoryNavPinInit) return;
  window.__studioHistoryNavPinInit = true;
  var scheduled = false;
  function gutterBackLeft(sidebar, mainRect) {
    if (!sidebar) return Math.max(12, mainRect.left + 8);
    var sR = sidebar.getBoundingClientRect().right;
    var gap = mainRect.left - sR;
    if (gap < 20) return Math.max(8, sR + 6);
    return Math.round(sR + Math.min(56, Math.max(10, gap * 0.42)));
  }
  function pinStudioHistoryNav() {
    scheduled = false;
    var main = document.querySelector('section[data-testid="stMain"]');
    if (!main) return;
    var sidebar = document.querySelector('[data-testid="stSidebar"]');
    var mainRect = main.getBoundingClientRect();
    var backLeft = gutterBackLeft(sidebar, mainRect);
    var fwdRight = Math.max(12, Math.round(window.innerWidth - mainRect.right + 14));
    document.documentElement.style.setProperty('--studio-history-back-left', backLeft + 'px');
    document.documentElement.style.setProperty('--studio-history-fwd-right', fwdRight + 'px');
    var btnBase =
      'position:fixed!important;top:50vh!important;' +
      'transform:translateY(-50%)!important;z-index:99990!important;' +
      'margin:0!important;width:auto!important;pointer-events:auto!important;';
    main.querySelectorAll('[class*="st-key-studio_nav_back_btn"] .stButton').forEach(function (btn) {
      btn.style.cssText = btnBase + 'left:' + backLeft + 'px!important;right:auto!important;';
    });
    main.querySelectorAll('[class*="st-key-studio_nav_forward_btn"] .stButton').forEach(function (btn) {
      btn.style.cssText = btnBase + 'right:' + fwdRight + 'px!important;left:auto!important;';
    });
  }
  function schedulePin() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(pinStudioHistoryNav);
  }
  pinStudioHistoryNav();
  window.addEventListener('resize', schedulePin, { passive: true });
  window.addEventListener('scroll', schedulePin, { passive: true });
  if (typeof ResizeObserver !== 'undefined') {
    var ro = new ResizeObserver(schedulePin);
    var sidebar = document.querySelector('[data-testid="stSidebar"]');
    var main = document.querySelector('section[data-testid="stMain"]');
    if (sidebar) ro.observe(sidebar);
    if (main) ro.observe(main);
  }
})();
</script>
        """,
        unsafe_allow_html=True,
    )


_UI_POLISH_VERSION = "v10-2026-06-09-history-nav-live-fix"


def _backing_studio_panel_css() -> str:
    """Backing Track studio panels — targets inner shell divs (reliable in Streamlit 1.49+)."""
    return """
/* ---------- Backing Track studio panels (shell + keyed container) ---------- */
.st-key-backing_playback_setup,
.st-key-backing_quick_playback,
.st-key-backing_transport {
  border: none !important;
  padding: 0 !important;
  margin: 0.65rem 0 1rem !important;
  background: transparent !important;
  box-shadow: none !important;
}
.st-key-backing_playback_setup::before,
.st-key-backing_quick_playback::before,
.st-key-backing_transport::before {
  display: none !important;
  content: none !important;
}
.ui-backing-panel-shell {
  border: 1px solid rgba(16, 185, 129, 0.34);
  border-radius: 14px;
  padding: 0.72rem 0.85rem 0.78rem;
  margin: 0 0 0.15rem;
  background:
    radial-gradient(120% 90% at 6% -10%, rgba(16, 185, 129, 0.16) 0%, transparent 55%),
    radial-gradient(100% 80% at 98% 110%, rgba(34, 197, 94, 0.1) 0%, transparent 52%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 58%, #f1f5f9 100%);
  box-shadow:
    0 18px 44px -24px rgba(15, 23, 42, 0.34),
    0 2px 10px rgba(15, 23, 42, 0.07),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
  position: relative;
  overflow: hidden;
}
.ui-backing-panel-shell::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.75), rgba(34, 197, 94, 0.65), transparent);
}
.ui-backing-panel-shell.is-quick {
  border-color: rgba(14, 165, 233, 0.38);
  background:
    radial-gradient(120% 90% at 8% -8%, rgba(14, 165, 233, 0.14) 0%, transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}
.ui-backing-panel-shell.is-quick::before {
  background: linear-gradient(90deg, transparent, rgba(14, 165, 233, 0.7), rgba(56, 189, 248, 0.55), transparent);
}
.ui-backing-panel-shell.is-transport {
  border-color: rgba(99, 102, 241, 0.38);
  background:
    radial-gradient(120% 90% at 92% -10%, rgba(99, 102, 241, 0.14) 0%, transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}
.ui-backing-panel-shell.is-transport::before {
  background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.7), rgba(139, 92, 246, 0.55), transparent);
}
.ui-backing-panel-shell.is-scope {
  border-color: rgba(79, 70, 229, 0.42);
  padding: 0.85rem 0.95rem 0.82rem;
  margin-bottom: 0.35rem;
  background:
    radial-gradient(120% 90% at 4% -8%, rgba(79, 70, 229, 0.12) 0%, transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}
.ui-backing-panel-shell.is-scope::before {
  height: 5px;
  background: linear-gradient(90deg, transparent, rgba(79, 70, 229, 0.85), rgba(99, 102, 241, 0.65), transparent);
}
.ui-backing-panel-shell.is-compact {
  border-color: rgba(148, 163, 184, 0.28);
  padding: 0.45rem 0.65rem 0.5rem;
  margin-bottom: 0.35rem;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 8px 24px -20px rgba(15, 23, 42, 0.28);
}
.ui-backing-panel-shell.is-compact::before {
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.55), rgba(100, 116, 139, 0.45), transparent);
}
.ui-backing-panel-shell.is-compact .ui-backing-panel-head {
  margin-bottom: 0.35rem;
  padding-bottom: 0.35rem;
}
.ui-backing-panel-shell.is-compact .ui-backing-panel-title {
  font-size: 0.98rem;
}
.ui-backing-panel-shell.is-scope .ui-backing-panel-kicker { color: #4338ca; }
.ui-backing-panel-shell.is-compact .ui-backing-panel-kicker { color: #64748b; }
.ui-backing-feel-inline {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.55rem 0.75rem;
  align-items: end;
}
.ui-backing-inline-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
  margin: 0 0 0.2rem;
}
.ui-backing-action-controls {
  margin-bottom: 0.35rem;
}
.ui-backing-transport-feedback {
  margin: 0.35rem 0 0.45rem;
  padding: 0.45rem 0.65rem;
  border-radius: 9px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(248, 250, 252, 0.95);
  font-size: 0.78rem;
  font-weight: 650;
  color: #475569;
  line-height: 1.35;
}
.ui-backing-transport-feedback.is-ready {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(236, 253, 245, 0.95);
  color: #047857;
}
.ui-backing-transport-feedback.is-active {
  border-color: rgba(34, 197, 94, 0.45);
  background: rgba(240, 253, 244, 0.98);
  color: #15803d;
}
.ui-backing-transport-feedback.is-warn {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(255, 251, 235, 0.98);
  color: #b45309;
}
.ui-backing-transport-feedback.is-stopped {
  border-color: rgba(100, 116, 139, 0.35);
  background: rgba(241, 245, 249, 0.98);
  color: #64748b;
}
.st-key-backing_step1_range,
.st-key-backing_step2_action {
  margin: 0.25rem 0 0.35rem !important;
}
.ui-backing-panel-shell .ui-backing-panel-kicker { color: #059669; }
.ui-backing-panel-shell.is-quick .ui-backing-panel-kicker { color: #0284c7; }
.ui-backing-panel-shell.is-transport .ui-backing-panel-kicker { color: #4f46e5; }
.ui-backing-panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem 1rem;
  margin: 0 0 0.9rem;
  padding-bottom: 0.8rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.32);
}
.ui-backing-panel-head-compact {
  margin-bottom: 0.35rem;
  padding-bottom: 0.35rem;
  gap: 0.35rem 0.65rem;
}
.ui-backing-panel-head-compact .ui-backing-panel-title {
  font-size: 0.98rem;
}
.ui-backing-panel-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 0 0 0.3rem;
}
.ui-backing-panel-title {
  margin: 0;
  font-size: 1.02rem;
  font-weight: 850;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.2;
}
.ui-backing-panel-sub {
  margin: 0.18rem 0 0;
  font-size: 0.76rem;
  color: #64748b;
  line-height: 1.35;
  max-width: 40rem;
}
.ui-backing-panel-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.32rem 0.7rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: rgba(255, 255, 255, 0.95);
  color: #64748b;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
}
.ui-backing-panel-badge.ready {
  color: #047857;
  border-color: rgba(110, 231, 183, 0.7);
  background: rgba(236, 253, 245, 0.98);
}
.ui-backing-field-label {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #475569;
  margin: 0 0 0.28rem;
}
.ui-backing-field-hint {
  font-size: 0.74rem;
  color: #94a3b8;
  margin: 0 0 0.45rem;
  line-height: 1.35;
}
.ui-backing-scope-divider {
  margin: 0.75rem 0 0.55rem;
  padding-top: 0.65rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.4);
}
.ui-backing-setup-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem 1rem;
  margin: 0 0 0.25rem;
}
@media (max-width: 900px) {
  .ui-backing-setup-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.ui-backing-panel-shell .ui-playback-setup-bpm {
  font-size: 2.1rem;
  font-weight: 900;
  color: #0f172a;
  line-height: 1;
  margin: 0.15rem 0 0.25rem;
}
.ui-backing-panel-shell .ui-playback-setup-bpm span {
  font-size: 0.92rem;
  font-weight: 650;
  color: #64748b;
}
.ui-backing-transport-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  padding: 0.42rem 0.58rem;
  margin: 0 0 0.55rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.38);
  background: rgba(248, 250, 252, 0.98);
}
.ui-backing-transport-strip.ready {
  border-color: rgba(110, 231, 183, 0.6);
  background: linear-gradient(135deg, rgba(236, 253, 245, 0.98), rgba(240, 253, 250, 0.92));
}
.ui-backing-transport-dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  background: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.22);
}
.ui-backing-transport-strip.ready .ui-backing-transport-dot {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.28);
  animation: ui-backing-pulse 1.8s ease-in-out infinite;
}
@keyframes ui-backing-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.65; transform: scale(0.9); }
}
.ui-backing-transport-state {
  font-size: 0.8rem;
  font-weight: 800;
  color: #334155;
  margin-right: 0.2rem;
}
.ui-backing-transport-strip.ready .ui-backing-transport-state { color: #047857; }
.ui-backing-transport-meta {
  font-size: 0.7rem;
  font-weight: 750;
  padding: 0.18rem 0.52rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.38);
  color: #475569;
}
.ui-backing-transport-meta.scope {
  color: #0369a1;
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(224, 242, 254, 0.75);
}
.ui-backing-transport-hint {
  font-size: 0.82rem;
  color: #64748b;
  margin: 0.5rem 0 0;
  line-height: 1.45;
}
.ui-backing-transport-actions { margin-top: 0.35rem; }
.ui-backing-panel-shell [data-testid="stSelectbox"] label,
.ui-backing-panel-shell [data-testid="stRadio"] label,
.ui-backing-panel-shell [data-testid="stSlider"] label,
.ui-backing-panel-shell [data-testid="stMultiSelect"] label,
.ui-backing-panel-shell [data-testid="stButton"] label {
  display: none !important;
}
.ui-backing-panel-shell [data-testid="stSelectbox"] > div > div,
.ui-backing-panel-shell [data-testid="stMultiSelect"] > div > div,
.ui-backing-panel-shell [data-testid="stSlider"] > div > div {
  border-radius: 10px !important;
  border-color: rgba(148, 163, 184, 0.55) !important;
  background: #fff !important;
  min-height: 2.5rem !important;
}
.ui-backing-panel-shell [data-testid="stRadio"] > div {
  gap: 0.45rem !important;
  padding: 0.45rem 0.55rem !important;
  border-radius: 12px !important;
  border: 1px solid rgba(148, 163, 184, 0.35) !important;
  background: rgba(255, 255, 255, 0.92) !important;
}
.ui-playback-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 0.7rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 750;
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: #fff;
  color: #64748b;
}
.ui-playback-status-badge.ready {
  background: #ecfdf5;
  border-color: #6ee7b7;
  color: #047857;
}
.ui-backing-panel-shell.is-transport .st-key-gen_backing_btn button,
.ui-backing-panel-shell.is-transport .st-key-gen_backing_btn [data-testid="stBaseButton-primary"],
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn button,
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn [data-testid="stBaseButton-primary"],
.st-key-backing_transport .st-key-gen_backing_btn button,
.st-key-backing_transport .st-key-play_backing_btn button {
  min-height: 2.55rem !important;
  font-size: 0.88rem !important;
  font-weight: 800 !important;
  border-radius: 10px !important;
  letter-spacing: 0.02em !important;
}
.ui-backing-panel-shell.is-transport .st-key-gen_backing_btn button,
.ui-backing-panel-shell.is-transport .st-key-gen_backing_btn [data-testid="stBaseButton-primary"],
.st-key-backing_transport .st-key-gen_backing_btn button {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 8px 22px rgba(220, 38, 38, 0.35) !important;
}
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn button,
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn [data-testid="stBaseButton-primary"],
.st-key-backing_transport .st-key-play_backing_btn button {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 50%, #15803d 100%) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 8px 22px rgba(34, 197, 94, 0.38) !important;
}
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn button:disabled,
.ui-backing-panel-shell.is-transport .st-key-play_backing_btn [data-testid="stBaseButton-primary"]:disabled,
.st-key-backing_transport .st-key-play_backing_btn button:disabled {
  background: rgba(226, 232, 240, 0.95) !important;
  border: 1px solid rgba(148, 163, 184, 0.45) !important;
  color: #94a3b8 !important;
  box-shadow: none !important;
  opacity: 0.85 !important;
}
.ui-backing-panel-shell.is-transport .st-key-stop_backing_btn button,
.ui-backing-panel-shell.is-transport .st-key-stop_backing_btn [data-testid="stBaseButton-secondary"],
.st-key-backing_transport .st-key-stop_backing_btn button {
  min-height: 2.55rem !important;
  font-weight: 750 !important;
  border-radius: 10px !important;
  border: 2px solid rgba(51, 65, 85, 0.35) !important;
  background: rgba(248, 250, 252, 0.98) !important;
  color: #334155 !important;
  box-shadow: none !important;
}
.ui-backing-panel-shell.is-transport .st-key-dl_backing_btn button,
.st-key-backing_transport .st-key-dl_backing_btn button {
  min-height: 2.35rem !important;
  font-size: 0.82rem !important;
  font-weight: 700 !important;
  border-radius: 9px !important;
  border: 1px dashed rgba(99, 102, 241, 0.5) !important;
  background: rgba(238, 242, 255, 0.85) !important;
  color: #4338ca !important;
}
.ui-backing-studio-deck-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem 0.85rem;
  margin: 0 0 0.55rem 0;
  padding: 0.48rem 0.72rem;
  border-radius: 11px;
  border: 1px solid rgba(16, 185, 129, 0.28);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(14, 165, 233, 0.06) 100%);
  box-shadow: 0 4px 14px -10px rgba(15, 23, 42, 0.28);
}
.ui-backing-studio-deck-main { flex: 1 1 12rem; min-width: 0; }
.ui-backing-studio-kicker {
  display: inline-block;
  font-size: 0.58rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #059669;
  margin: 0 0 0.12rem;
}
.ui-backing-studio-title {
  margin: 0;
  font-size: 1.02rem;
  font-weight: 850;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.2;
}
.ui-backing-studio-sub {
  margin: 0;
  font-size: 0.72rem;
  color: #64748b;
  line-height: 1.35;
  max-width: 36rem;
}
.ui-backing-studio-steps {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.28rem;
  align-items: center;
}
.ui-backing-studio-step {
  font-size: 0.66rem;
  font-weight: 750;
  padding: 0.16rem 0.42rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.88);
  color: #475569;
}
.ui-backing-setup-group {
  margin: 0 0 0.5rem;
  padding: 0.45rem 0.55rem 0.5rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.72);
}
.ui-backing-setup-group-title {
  margin: 0 0 0.12rem;
  font-size: 0.68rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #334155;
}
.ui-backing-setup-group-hint {
  margin: 0 0 0.38rem;
  font-size: 0.72rem;
  color: #94a3b8;
  line-height: 1.3;
}
.ui-backing-setup-key-row { margin: 0.1rem 0 0; }
body.backing-studio-page .ui-chart-key-mode-badge,
body.backing-studio-page .ui-studio-meta-badges .tone-key,
body.backing-studio-page .ui-studio-meta-badges .tone-display {
  display: none !important;
}
body.backing-studio-page .ui-active-song-card,
body.backing-studio-page .ui-active-song-hub {
  display: none !important;
}
/* Hide Songs-page active song hub only on non-picker studio pages (never default-hide). */
body.backing-studio-page .st-key-active_song_hub,
body.backing-studio-page .st-key-picker_active_song_hub,
body.backing-studio-page .st-key-song_library_panel,
body.practice-page .st-key-active_song_hub,
body.practice-page .st-key-picker_active_song_hub,
body.practice-page .st-key-song_library_panel,
body.custom-builder-page .st-key-active_song_hub,
body.custom-builder-page .st-key-picker_active_song_hub,
body.custom-builder-page .st-key-song_library_panel,
body[data-studio-page="backing"] .st-key-active_song_hub,
body[data-studio-page="backing"] .st-key-picker_active_song_hub,
body[data-studio-page="backing"] .st-key-song_library_panel,
body[data-studio-page="practice"] .st-key-active_song_hub,
body[data-studio-page="practice"] .st-key-picker_active_song_hub,
body[data-studio-page="practice"] .st-key-song_library_panel,
body[data-studio-page="custom"] .st-key-active_song_hub,
body[data-studio-page="custom"] .st-key-picker_active_song_hub,
body[data-studio-page="custom"] .st-key-song_library_panel,
body[data-studio-page="creative"] .st-key-active_song_hub,
body[data-studio-page="creative"] .st-key-picker_active_song_hub,
body[data-studio-page="creative"] .st-key-song_library_panel,
body[data-studio-page="multitrack"] .st-key-active_song_hub,
body[data-studio-page="multitrack"] .st-key-picker_active_song_hub,
body[data-studio-page="multitrack"] .st-key-song_library_panel,
body[data-studio-page="analysis"] .st-key-active_song_hub,
body[data-studio-page="analysis"] .st-key-picker_active_song_hub,
body[data-studio-page="analysis"] .st-key-song_library_panel,
body[data-studio-page="upload"] .st-key-active_song_hub,
body[data-studio-page="upload"] .st-key-picker_active_song_hub,
body[data-studio-page="upload"] .st-key-song_library_panel,
body[data-studio-page]:not([data-studio-page="picker"]) .ui-song-card-grid {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}
body[data-studio-page="picker"] .st-key-active_song_hub,
body[data-studio-page="picker"] .st-key-picker_active_song_hub,
body[data-studio-page="picker"] .st-key-song_library_panel,
body[data-song-picker-ui] .st-key-active_song_hub,
body[data-song-picker-ui] .st-key-picker_active_song_hub {
  display: block !important;
  visibility: visible !important;
}
.ui-backing-badge.bpm-default {
  background: rgba(249, 115, 22, 0.22);
  border-color: rgba(251, 146, 60, 0.42);
}
.ui-backing-setup-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.32rem 0.4rem;
  margin: 0 0 0.65rem;
  padding: 0.42rem 0.48rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(255, 255, 255, 0.92));
}
.ui-backing-ctx-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.2rem 0.48rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 650;
  color: #334155;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: #fff;
  white-space: nowrap;
}
.ui-backing-ctx-badge strong { font-weight: 850; color: #0f172a; }
.ui-backing-ctx-ico { font-size: 0.78rem; line-height: 1; opacity: 0.92; }
.ui-backing-ctx-badge.key-orig { border-color: rgba(99, 102, 241, 0.4); background: rgba(238, 242, 255, 0.95); }
.ui-backing-ctx-badge.key-practice { border-color: rgba(16, 185, 129, 0.45); background: rgba(236, 253, 245, 0.95); }
.ui-backing-ctx-badge.key-written { border-color: rgba(245, 158, 11, 0.45); background: rgba(255, 251, 235, 0.95); }
.ui-backing-ctx-badge.meter { border-color: rgba(14, 165, 233, 0.4); background: rgba(224, 242, 254, 0.9); }
.ui-backing-ctx-badge.groove { border-color: rgba(245, 158, 11, 0.45); background: rgba(255, 251, 235, 0.95); }
.ui-backing-ctx-badge.range { border-color: rgba(79, 70, 229, 0.4); background: rgba(238, 242, 255, 0.92); }
.ui-backing-ctx-badge.bpm { border-color: rgba(100, 116, 139, 0.35); background: rgba(248, 250, 252, 0.98); color: #64748b; }
.ui-backing-setup-section {
  margin: 0 0 0.55rem;
  padding: 0 0 0.5rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.28);
}
.ui-backing-setup-section:last-of-type { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.ui-backing-setup-section-title {
  margin: 0 0 0.42rem;
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.ui-backing-setup-section-icon { font-size: 0.85rem; line-height: 1; }
.ui-backing-setup-fields-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem 0.75rem;
}
@media (max-width: 720px) {
  .ui-backing-setup-fields-row { grid-template-columns: 1fr; }
}
.ui-backing-quick-controls {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 0.55rem 0.75rem;
  align-items: start;
}
@media (max-width: 720px) {
  .ui-backing-quick-controls { grid-template-columns: 1fr; }
}
.ui-backing-transport-toolbar {
  display: grid;
  grid-template-columns: 1.4fr 0.7fr 1fr;
  gap: 0.45rem;
  align-items: stretch;
  margin: 0.15rem 0 0.35rem;
}
@media (max-width: 720px) {
  .ui-backing-transport-toolbar { grid-template-columns: 1fr 1fr; }
}
.st-key-backing_playback_setup,
.st-key-backing_quick_playback,
.st-key-backing_transport,
.st-key-backing_step1_range,
.st-key-backing_step2_action {
  margin: 0.25rem 0 0.35rem !important;
}
body[data-backing-studio-ui] .ui-backing-studio-deck-head {
  outline: none;
}
"""


def _backing_scope_panel_css() -> str:
    """Scope & loop panel — keyed container + inner shell (Streamlit 1.49+)."""
    return """
/* Scope & loop control — styles the keyed container (widgets live here) */
.st-key-backing_scope_panel,
.ui-backing-scope-panel {
  margin: 0.4rem 0 0.25rem !important;
  padding: 1rem 1.1rem 0.85rem !important;
  border-radius: 16px !important;
  border: 2px solid rgba(99, 102, 241, 0.4) !important;
  background: transparent !important;
  box-shadow: none !important;
  position: relative !important;
  overflow: visible !important;
}
.st-key-backing_scope_panel::before,
.ui-backing-scope-panel::before {
  display: none !important;
  content: none !important;
}
.ui-backing-scope-panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 0.75rem;
  margin: 0 0 0.65rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-backing-scope-panel-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 850;
  letter-spacing: -0.01em;
  color: #0f172a;
}
.ui-backing-scope-panel-sub {
  margin: 0.2rem 0 0;
  font-size: 0.76rem;
  color: #64748b;
  line-height: 1.35;
}
.ui-backing-scope-summary-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.65rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  color: #0369a1;
  border: 1px solid rgba(56, 189, 248, 0.45);
  background: linear-gradient(135deg, rgba(224, 242, 254, 0.95), rgba(240, 249, 255, 0.9));
  white-space: nowrap;
}
.ui-backing-scope-summary-badge strong { color: #0c4a6e; font-weight: 900; }
.ui-backing-scope-segment {
  margin: 0 0 0.65rem;
}
.st-key-backing_scope_panel [data-testid="stRadio"] > div,
.ui-backing-scope-panel [data-testid="stRadio"] > div {
  display: flex !important;
  flex-wrap: wrap;
  gap: 0.35rem !important;
  padding: 0.35rem !important;
  border-radius: 12px !important;
  border: 1px solid rgba(148, 163, 184, 0.32) !important;
  background: rgba(241, 245, 249, 0.95) !important;
}
.st-key-backing_scope_panel [data-testid="stRadio"] label,
.ui-backing-scope-panel [data-testid="stRadio"] label {
  flex: 1 1 auto !important;
  min-width: 7.5rem;
  margin: 0 !important;
  padding: 0.42rem 0.65rem !important;
  border-radius: 9px !important;
  font-size: 0.78rem !important;
  font-weight: 750 !important;
  text-align: center;
  border: 1px solid transparent !important;
  background: transparent !important;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.st-key-backing_scope_panel [data-testid="stRadio"] label:hover,
.ui-backing-scope-panel [data-testid="stRadio"] label:hover {
  background: rgba(255, 255, 255, 0.85) !important;
  border-color: rgba(148, 163, 184, 0.35) !important;
}
.st-key-backing_scope_panel [data-testid="stRadio"] label[data-checked="true"],
.st-key-backing_scope_panel [data-testid="stRadio"] label:has(input:checked),
.ui-backing-scope-panel [data-testid="stRadio"] label[data-checked="true"],
.ui-backing-scope-panel [data-testid="stRadio"] label:has(input:checked) {
  background: #ffffff !important;
  border-color: rgba(16, 185, 129, 0.55) !important;
  color: #047857 !important;
  font-weight: 850 !important;
  box-shadow: 0 2px 10px rgba(16, 185, 129, 0.14) !important;
}
.ui-backing-scope-field {
  margin: 0 0 0.55rem;
  padding: 0.55rem 0.65rem;
  border-radius: 11px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.88);
}
.ui-backing-scope-loops-row {
  margin: 0.15rem 0 0.5rem;
  padding: 0.55rem 0.65rem;
  border-radius: 11px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.88);
}
.st-key-backing_scope_panel [data-testid="stSlider"] > div > div,
.ui-backing-scope-panel [data-testid="stSlider"] > div > div {
  padding-top: 0.15rem !important;
}
.st-key-backing_scope_panel .ui-backing-scope-field,
.st-key-backing_scope_panel .ui-backing-scope-loops-row {
  margin-left: 0;
  margin-right: 0;
}
.ui-backing-scope-handoff {
  margin: 0.35rem 0 0.45rem !important;
  padding: 0.45rem 0.65rem !important;
  font-size: 0.78rem !important;
  border-radius: 10px !important;
}
.st-key-backing_scope_panel [data-testid="stSelectbox"] > div > div,
.st-key-backing_scope_panel [data-testid="stMultiSelect"] > div > div {
  border-radius: 10px !important;
  border-color: rgba(99, 102, 241, 0.45) !important;
  background: #fff !important;
  min-height: 2.45rem !important;
}
"""


def _practice_control_panel_css() -> str:
    """Practice Control Center — keyed container (Streamlit 1.49+)."""
    return """
/* Practice Control Center */
.ui-practice-studio-deck-head {
  margin: 0.2rem 0 0.85rem 0;
  padding: 0.9rem 1rem 0.95rem;
  border-radius: 16px;
  border: 1px solid rgba(14, 165, 233, 0.35);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14) 0%, rgba(249, 115, 22, 0.08) 55%, rgba(99, 102, 241, 0.08) 100%);
  box-shadow: 0 10px 28px -18px rgba(14, 165, 233, 0.35);
}
.ui-practice-studio-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #0284c7;
  margin: 0 0 0.35rem;
}
.ui-practice-studio-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #0f172a;
  line-height: 1.15;
}
.ui-practice-studio-sub {
  margin: 0.35rem 0 0;
  font-size: 0.86rem;
  color: #475569;
  line-height: 1.45;
  max-width: 42rem;
}
body[data-practice-setup-ui] .ui-practice-studio-deck-head {
  outline: 2px solid rgba(14, 165, 233, 0.22);
  outline-offset: 2px;
}
.st-key-practice_control_panel {
  margin: 0.35rem 0 0.85rem !important;
  padding: 1.05rem 1.15rem 0.9rem !important;
  border-radius: 18px !important;
  border: 2px solid rgba(14, 165, 233, 0.48) !important;
  background:
    radial-gradient(110% 80% at 0% -15%, rgba(14, 165, 233, 0.16) 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 105%, rgba(249, 115, 22, 0.1) 0%, transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 62%, #f1f5f9 100%) !important;
  box-shadow:
    0 14px 36px -22px rgba(14, 165, 233, 0.28),
    0 2px 8px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
  position: relative !important;
  overflow: hidden !important;
}
.st-key-practice_control_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(14, 165, 233, 0.75), rgba(249, 115, 22, 0.55), transparent);
}
.ui-practice-control-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem 0.75rem;
  margin: 0 0 0.7rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-practice-control-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0284c7;
  margin: 0 0 0.3rem;
}
.ui-practice-control-title {
  margin: 0;
  font-size: 1.28rem;
  font-weight: 900;
  letter-spacing: -0.025em;
  color: #0f172a;
  line-height: 1.15;
}
body[data-practice-setup-ui] .st-key-practice_control_panel {
  outline: 2px solid rgba(14, 165, 233, 0.18);
  outline-offset: 2px;
}
.ui-practice-control-sub {
  margin: 0.28rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
  max-width: 40rem;
}
.ui-practice-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.5rem;
  margin: 0 0 0.65rem;
}
.st-key-practice_control_panel .setup-field-pill,
.ui-practice-meta-row .setup-field-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  font-weight: 800;
  color: #0c4a6e;
  background: linear-gradient(135deg, rgba(224, 242, 254, 0.98), rgba(255, 255, 255, 0.95));
  border: 1px solid rgba(56, 189, 248, 0.45);
  border-radius: 999px;
  padding: 0.32rem 0.72rem;
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.1);
}
.ui-practice-summary-badge {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  padding: 0.32rem 0.7rem;
  margin: 0 0 0.7rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 750;
  color: #334155;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.95);
  line-height: 1.45;
}
.ui-practice-summary-badge strong {
  color: #0369a1;
  font-weight: 900;
}
.ui-practice-controls-grid {
  margin: 0 0 0.5rem;
}
.ui-practice-control-field {
  padding: 0.55rem 0.65rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.9);
  margin-bottom: 0.5rem;
}
.ui-practice-groove-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.35rem;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 800;
  color: #c2410c;
  border: 1px solid rgba(251, 146, 60, 0.5);
  background: linear-gradient(135deg, rgba(255, 237, 213, 0.95), rgba(255, 247, 237, 0.9));
}
.ui-practice-panel-hint {
  margin: 0.15rem 0 0.55rem;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.45;
}
.st-key-practice_control_panel [data-testid="stSelectbox"] label,
.st-key-practice_control_panel [data-testid="stSlider"] label {
  display: none !important;
}
.st-key-practice_control_panel [data-testid="stSelectbox"] > div > div,
.st-key-practice_control_panel [data-testid="stSlider"] > div > div {
  border-radius: 10px !important;
  border-color: rgba(14, 165, 233, 0.4) !important;
  background: #fff !important;
  min-height: 2.45rem !important;
}
.st-key-practice_control_panel [data-testid="column"] {
  padding: 0 0.35rem !important;
}
/* Legacy plain card — hide if old markup ever renders */
.practice-setup-card:has(.ui-page-nav-label:only-child) {
  display: none !important;
}
/* P0 UI polish — tighter Practice vertical rhythm */
body.practice-page .block-container {
  padding-top: 0.45rem !important;
}
body.practice-page .st-key-practice_control_panel {
  margin-top: 0.2rem !important;
  padding: 0.85rem 1rem 0.75rem !important;
}
body.practice-page .ui-studio-script-header {
  margin-bottom: 0.55rem !important;
  padding: 0.75rem 0.95rem 0.8rem !important;
}
body.practice-page .notation-output {
  margin-top: 0.35rem !important;
}
"""


def _backing_studio_all_css() -> str:
    return _backing_studio_panel_css() + _backing_scope_panel_css()


def _creative_studio_panel_css() -> str:
    """Creative Lab / Improvisation Intelligence studio panel."""
    return """
/* Creative Studio — card on keyed container */
.st-key-creative_song_source_panel {
  border: none !important;
  padding: 0 !important;
  margin: 0 0 0.45rem !important;
  background: transparent !important;
  box-shadow: none !important;
}
.st-key-creative_studio_panel {
  margin: 0.2rem 0 0.85rem !important;
  padding: 1rem 1.1rem 0.9rem !important;
  border-radius: 18px !important;
  border: 2px solid rgba(139, 92, 246, 0.42) !important;
  background:
    radial-gradient(110% 80% at 0% -12%, rgba(139, 92, 246, 0.16) 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 108%, rgba(99, 102, 241, 0.1) 0%, transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #faf5ff 58%, #f8fafc 100%) !important;
  box-shadow:
    0 14px 36px -22px rgba(124, 58, 237, 0.28),
    0 2px 8px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
  position: relative !important;
  overflow: hidden !important;
}
.st-key-creative_studio_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(139, 92, 246, 0.75), rgba(99, 102, 241, 0.6), transparent);
}
.st-key-creative_studio_panel > div[data-testid="stVerticalBlock"] {
  gap: 0.4rem !important;
}
body[data-creative-studio-ui] .st-key-creative_studio_panel {
  outline: 2px solid rgba(139, 92, 246, 0.16);
  outline-offset: 2px;
}
.st-key-creative_studio_panel .ui-creative-studio-shell {
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}
.st-key-creative_studio_panel .ui-creative-studio-shell::before {
  display: none !important;
}
.ui-creative-studio-shell {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  position: relative;
}
.ui-creative-studio-shell::before {
  display: none;
}
.ui-creative-studio-head {
  margin: 0 0 0.65rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-creative-studio-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #7c3aed;
  margin: 0 0 0.28rem;
}
.ui-creative-studio-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ui-creative-studio-sub {
  margin: 0.28rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
}
.ui-creative-mode-segment {
  margin: 0 0 0.7rem;
}
.st-key-creative_studio_panel [data-testid="stRadio"] > div,
.ui-creative-mode-segment [data-testid="stRadio"] > div {
  display: flex !important;
  flex-wrap: wrap;
  gap: 0.35rem !important;
  padding: 0.35rem !important;
  border-radius: 12px !important;
  border: 1px solid rgba(167, 139, 250, 0.35) !important;
  background: rgba(245, 243, 255, 0.95) !important;
}
.st-key-creative_studio_panel [data-testid="stRadio"] label,
.ui-creative-mode-segment [data-testid="stRadio"] label {
  flex: 1 1 auto !important;
  min-width: 6.5rem;
  margin: 0 !important;
  padding: 0.38rem 0.55rem !important;
  border-radius: 9px !important;
  font-size: 0.74rem !important;
  font-weight: 750 !important;
  text-align: center;
  border: 1px solid transparent !important;
}
.st-key-creative_studio_panel [data-testid="stRadio"] label[data-checked="true"],
.st-key-creative_studio_panel [data-testid="stRadio"] label:has(input:checked),
.ui-creative-mode-segment [data-testid="stRadio"] label[data-checked="true"],
.ui-creative-mode-segment [data-testid="stRadio"] label:has(input:checked) {
  background: #fff !important;
  border-color: rgba(139, 92, 246, 0.55) !important;
  color: #6d28d9 !important;
  font-weight: 850 !important;
  box-shadow: 0 2px 10px rgba(139, 92, 246, 0.14) !important;
}
.ui-creative-section-label {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #475569;
  margin: 0 0 0.4rem;
}
.ui-creative-entry-segment {
  margin: 0 0 0.65rem;
}
.ui-creative-song-card {
  padding: 0.65rem 0.75rem;
  margin: 0.5rem 0 0.55rem;
  border-radius: 12px;
  border: 1px solid rgba(139, 92, 246, 0.32);
  background: linear-gradient(135deg, rgba(245, 243, 255, 0.98), rgba(255, 255, 255, 0.95));
}
.ui-creative-song-card.custom {
  border-color: rgba(249, 115, 22, 0.35);
  background: linear-gradient(135deg, rgba(255, 247, 237, 0.95), rgba(255, 255, 255, 0.95));
}
.ui-creative-song-kicker {
  font-size: 0.68rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7c3aed;
  margin: 0 0 0.25rem;
}
.ui-creative-song-title {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
  font-weight: 850;
  color: #0f172a;
}
.ui-creative-song-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
}
.ui-creative-song-meta span {
  font-size: 0.7rem;
  font-weight: 750;
  padding: 0.16rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.9);
  color: #475569;
}
.ui-creative-source-panel {
  padding: 0.55rem 0.65rem;
  margin: 0.45rem 0 0.5rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.88);
}
.ui-creative-progression-preview {
  font-size: 0.76rem;
  color: #64748b;
  margin: 0.35rem 0 0.45rem;
  line-height: 1.45;
}
.ui-creative-quick-actions .stButton > button {
  font-size: 0.72rem !important;
  font-weight: 750 !important;
  min-height: 2rem !important;
  border-radius: 999px !important;
  padding: 0.28rem 0.75rem !important;
}
.st-key-creative_studio_panel [data-testid="stSelectbox"] label,
.st-key-creative_studio_panel [data-testid="stSlider"] label,
.st-key-creative_studio_panel [data-testid="stTextInput"] label {
  font-size: 0.78rem !important;
  font-weight: 700 !important;
}
"""


def _custom_builder_panel_css() -> str:
    """Custom Song Builder — keyed container + step cards."""
    return """
/* Custom Song Builder — card on keyed container (Streamlit 1.49+) */
.st-key-custom_song_builder_panel {
  margin: 0.25rem 0 0.85rem !important;
  padding: 1rem 1.1rem 0.9rem !important;
  border-radius: 18px !important;
  border: 2px solid rgba(16, 185, 129, 0.42) !important;
  background:
    radial-gradient(110% 80% at 0% -12%, rgba(16, 185, 129, 0.14) 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 108%, rgba(14, 165, 233, 0.1) 0%, transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #f0fdf4 58%, #f8fafc 100%) !important;
  box-shadow:
    0 14px 36px -22px rgba(5, 150, 105, 0.22),
    0 2px 8px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
  position: relative !important;
  overflow: hidden !important;
}
.st-key-custom_song_builder_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.75), rgba(14, 165, 233, 0.55), transparent);
}
.st-key-custom_song_builder_panel > div[data-testid="stVerticalBlock"] {
  gap: 0.42rem !important;
}
body[data-custom-builder-ui] .st-key-custom_song_builder_panel {
  outline: 2px solid rgba(16, 185, 129, 0.16);
  outline-offset: 2px;
}
.ui-custom-builder-shell {
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}
.ui-custom-builder-shell::before {
  display: none !important;
}
.ui-custom-builder-head {
  margin: 0 0 0.55rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-custom-builder-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #059669;
  margin: 0 0 0.25rem;
}
.ui-custom-builder-title {
  margin: 0;
  font-size: 1.22rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ui-custom-builder-sub {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
}
.ui-custom-step-card {
  margin: 0.55rem 0 0.35rem;
  padding: 0.75rem 0.85rem 0.65rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05);
}
.ui-custom-step-head {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  margin: 0 0 0.55rem;
  padding-bottom: 0.45rem;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}
.ui-custom-step-num {
  flex: 0 0 auto;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  font-weight: 900;
  color: #fff;
  background: linear-gradient(135deg, #10b981 0%, #0ea5e9 100%);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.35);
}
.ui-custom-step-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 850;
  color: #0f172a;
  line-height: 1.25;
}
.ui-custom-step-sub {
  margin: 0.15rem 0 0;
  font-size: 0.74rem;
  color: #64748b;
  line-height: 1.35;
}
.ui-custom-preview-card {
  margin: 0.45rem 0 0.35rem;
  padding: 0.7rem 0.85rem;
  border-radius: 14px;
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%);
  box-shadow: 0 4px 14px rgba(5, 150, 105, 0.1);
}
.ui-custom-preview-kicker {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #047857;
  margin: 0 0 0.25rem;
}
.ui-custom-preview-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 900;
  color: #0f172a;
}
.ui-custom-preview-meta {
  margin: 0.35rem 0 0;
  font-size: 0.76rem;
  color: #475569;
  line-height: 1.45;
}
.ui-custom-preview-meta strong { color: #0f172a; }
.ui-custom-preview-empty {
  margin: 0.35rem 0 0;
  font-size: 0.76rem;
  color: #64748b;
  font-style: italic;
}
.ui-custom-active-pill {
  display: inline-block;
  margin-top: 0.35rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #065f46;
  background: rgba(16, 185, 129, 0.18);
  border: 1px solid rgba(16, 185, 129, 0.35);
}
.ui-custom-action-row {
  margin: 0.35rem 0 0.15rem;
}
.st-key-custom_song_builder_panel .cpl-title-panel,
.st-key-custom_song_builder_panel .cpl-builder-panel {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
}
.st-key-custom_song_builder_panel .cpl-steps-strip {
  margin: 0.15rem 0 0.35rem !important;
}
.st-key-custom_song_builder_panel [data-testid="stTextInput"] input,
.st-key-custom_song_builder_panel [data-testid="stNumberInput"] input {
  border-radius: 10px !important;
  border-color: rgba(148, 163, 184, 0.45) !important;
}
.st-key-custom_song_builder_panel [data-testid="stButton"] button[kind="primary"] {
  border-radius: 11px !important;
  font-weight: 800 !important;
}
.st-key-custom_song_builder_panel .cpl-now-editing {
  margin: 0.25rem 0 0.45rem !important;
  font-size: 0.78rem !important;
  color: #64748b !important;
}
.st-key-custom_song_builder_panel .cpl-now-editing span {
  color: #047857 !important;
  font-weight: 800 !important;
}
.st-key-custom_song_builder_panel .cpl-live-progression {
  margin: 0.35rem 0 !important;
  padding: 0.55rem !important;
  border-radius: 12px !important;
  border: 1px dashed rgba(16, 185, 129, 0.35) !important;
  background: rgba(240, 253, 244, 0.65) !important;
}
body[data-custom-builder-ui] .ui-custom-builder-shell + div .cpl-steps-strip,
body[data-custom-builder-ui] .cpl-builder-panel,
body[data-custom-builder-ui] .cpl-finish-panel {
  margin-top: 0.35rem;
}
body[data-custom-builder-ui] .cpl-steps-strip {
  margin-bottom: 0.45rem !important;
}
body[data-custom-builder-ui] [data-testid="stVerticalBlock"] {
  gap: 0.45rem !important;
}
body[data-custom-builder-ui] .ui-instrument-strip {
  margin-bottom: 0.35rem !important;
}
body[data-studio-page]:not([data-studio-page="custom"]) .st-key-custom_song_builder_panel {
  display: none !important;
  visibility: hidden !important;
  max-height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
  opacity: 0 !important;
  pointer-events: none !important;
  border: none !important;
  box-shadow: none !important;
}
body.custom-builder-page .st-key-custom_song_builder_panel {
  display: block !important;
  visibility: visible !important;
  max-height: none !important;
  overflow: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}
.ui-studio-meta-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.4rem 0 0.55rem;
}
.ui-studio-meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 750;
  line-height: 1.2;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: #f8fafc;
  color: #334155;
}
.ui-studio-meta-badge-ico {
  font-size: 0.82rem;
  line-height: 1;
}
.ui-studio-meta-badge-label {
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.62rem;
}
.ui-studio-meta-badge-value {
  font-weight: 850;
  color: #0f172a;
}
.ui-studio-meta-badge.tone-key {
  border-color: rgba(37, 99, 235, 0.35);
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-display {
  border-color: rgba(16, 185, 129, 0.35);
  background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-written {
  border-color: rgba(168, 85, 247, 0.35);
  background: linear-gradient(180deg, #faf5ff 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-tempo {
  border-color: rgba(234, 88, 12, 0.3);
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-meter {
  border-color: rgba(14, 165, 233, 0.32);
  background: linear-gradient(180deg, #f0f9ff 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-style {
  border-color: rgba(236, 72, 153, 0.28);
  background: linear-gradient(180deg, #fdf2f8 0%, #ffffff 100%);
}
.ui-studio-meta-badge.tone-source {
  border-color: rgba(100, 116, 139, 0.35);
  background: linear-gradient(180deg, #f1f5f9 0%, #ffffff 100%);
}
.ui-custom-setup-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.35rem;
}
.ui-custom-setup-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.32rem 0.55rem;
  border-radius: 9px;
  font-size: 0.72rem;
  font-weight: 750;
  color: #0f766e;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  text-decoration: none;
}
"""


def _upload_studio_panel_css() -> str:
    """Audio Upload Studio — upload / recording analysis page."""
    return """
/* Upload Studio */
.st-key-upload_studio_panel {
  margin: 0.25rem 0 0.85rem !important;
  padding: 1rem 1.1rem 0.9rem !important;
  border-radius: 18px !important;
  border: 2px solid rgba(244, 63, 94, 0.4) !important;
  background:
    radial-gradient(110% 80% at 0% -12%, rgba(244, 63, 94, 0.12) 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 108%, rgba(236, 72, 153, 0.1) 0%, transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #fff1f2 58%, #f8fafc 100%) !important;
  box-shadow:
    0 14px 36px -22px rgba(225, 29, 72, 0.22),
    0 2px 8px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
  position: relative !important;
  overflow: hidden !important;
}
.st-key-upload_studio_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(244, 63, 94, 0.8), rgba(236, 72, 153, 0.6), transparent);
}
.st-key-upload_studio_panel > div[data-testid="stVerticalBlock"] {
  gap: 0.45rem !important;
}
body[data-upload-studio-ui] .st-key-upload_studio_panel {
  outline: 2px solid rgba(244, 63, 94, 0.14);
  outline-offset: 2px;
}
.ui-upload-studio-head {
  margin: 0 0 0.55rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-upload-studio-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #e11d48;
  margin: 0 0 0.25rem;
}
.ui-upload-studio-title {
  margin: 0;
  font-size: 1.22rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ui-upload-studio-sub {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
}
.ui-upload-session-card {
  margin: 0.35rem 0 0.55rem;
  padding: 0.55rem 0.75rem;
  border-radius: 12px;
  border: 1px solid rgba(244, 63, 94, 0.28);
  background: rgba(255, 241, 242, 0.75);
  font-size: 0.76rem;
  color: #475569;
  line-height: 1.45;
}
.ui-upload-session-card strong { color: #0f172a; }
.ui-upload-format-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.35rem 0 0.55rem;
}
.ui-upload-format-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #9f1239;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(244, 63, 94, 0.3);
}
.ui-upload-step-kicker {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #be123c;
  margin: 0 0 0.35rem;
}
.st-key-upload_mode_segment,
.st-key-upload_capture_panel,
.st-key-upload_results_panel {
  margin: 0.35rem 0 !important;
  padding: 0.75rem 0.85rem !important;
  border-radius: 14px !important;
  border: 1px solid rgba(148, 163, 184, 0.28) !important;
  background: rgba(255, 255, 255, 0.92) !important;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05) !important;
}
.st-key-upload_capture_panel [data-testid="stFileUploader"] {
  border-radius: 14px !important;
  border: 2px dashed rgba(244, 63, 94, 0.38) !important;
  background: linear-gradient(180deg, #fffbfb 0%, #ffffff 100%) !important;
  padding: 0.35rem !important;
}
.st-key-upload_capture_panel [data-testid="stFileUploader"] section {
  padding: 0.85rem 0.65rem !important;
}
.st-key-upload_capture_panel [data-testid="stFileUploader"] small {
  color: #64748b !important;
  font-size: 0.76rem !important;
}
.st-key-upload_studio_panel [data-testid="stRadio"] > div {
  display: flex !important;
  flex-wrap: wrap;
  gap: 0.35rem !important;
  padding: 0.35rem !important;
  border-radius: 12px !important;
  border: 1px solid rgba(244, 63, 94, 0.25) !important;
  background: rgba(255, 241, 242, 0.65) !important;
}
.st-key-upload_studio_panel [data-testid="stRadio"] label {
  flex: 1 1 auto !important;
  min-width: 8rem;
  margin: 0 !important;
  padding: 0.4rem 0.55rem !important;
  border-radius: 9px !important;
  font-size: 0.78rem !important;
  font-weight: 750 !important;
  text-align: center;
  border: 1px solid transparent !important;
}
.st-key-upload_studio_panel [data-testid="stRadio"] label[data-checked="true"],
.st-key-upload_studio_panel [data-testid="stRadio"] label:has(input:checked) {
  background: #fff !important;
  border-color: rgba(244, 63, 94, 0.45) !important;
  color: #be123c !important;
  font-weight: 850 !important;
  box-shadow: 0 2px 10px rgba(244, 63, 94, 0.12) !important;
}
.st-key-upload_studio_panel [data-testid="stButton"] button[kind="primary"] {
  border-radius: 11px !important;
  font-weight: 850 !important;
  min-height: 2.65rem !important;
}
.st-key-upload_results_panel {
  border-color: rgba(244, 63, 94, 0.35) !important;
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%) !important;
}
"""


def _multitrack_studio_panel_css() -> str:
    """Multitrack Studio — session / layers / transport / export."""
    return """
/* Multitrack Studio */
.st-key-multitrack_studio_panel {
  margin: 0.25rem 0 0.85rem !important;
  padding: 1rem 1.1rem 0.9rem !important;
  border-radius: 18px !important;
  border: 2px solid rgba(245, 158, 11, 0.45) !important;
  background:
    radial-gradient(110% 80% at 0% -12%, rgba(245, 158, 11, 0.14) 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 108%, rgba(249, 115, 22, 0.1) 0%, transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #fffbeb 58%, #f8fafc 100%) !important;
  box-shadow:
    0 14px 36px -22px rgba(217, 119, 6, 0.24),
    0 2px 8px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
  position: relative !important;
  overflow: hidden !important;
}
.st-key-multitrack_studio_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, rgba(245, 158, 11, 0.85), rgba(249, 115, 22, 0.65), transparent);
}
.st-key-multitrack_studio_panel > div[data-testid="stVerticalBlock"] {
  gap: 0.5rem !important;
}
body[data-multitrack-studio-ui] .st-key-multitrack_studio_panel {
  outline: 2px solid rgba(245, 158, 11, 0.16);
  outline-offset: 2px;
}
.ui-multitrack-studio-head {
  margin: 0 0 0.55rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.ui-multitrack-studio-kicker {
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #d97706;
  margin: 0 0 0.25rem;
}
.ui-multitrack-studio-title {
  margin: 0;
  font-size: 1.22rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ui-multitrack-studio-sub {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
}
.ui-multitrack-session-card {
  margin: 0.35rem 0 0.5rem;
  padding: 0.55rem 0.75rem;
  border-radius: 12px;
  border: 1px solid rgba(245, 158, 11, 0.32);
  background: rgba(255, 251, 235, 0.85);
  font-size: 0.76rem;
  color: #475569;
  line-height: 1.45;
}
.ui-multitrack-session-card strong { color: #0f172a; }
.ui-multitrack-step-kicker {
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #b45309;
  margin: 0 0 0.4rem;
}
.st-key-multitrack_session_panel,
.st-key-multitrack_layers_panel,
.st-key-multitrack_transport_panel,
.st-key-multitrack_export_panel {
  margin: 0.4rem 0 !important;
  padding: 0.8rem 0.9rem !important;
  border-radius: 14px !important;
  border: 1px solid rgba(148, 163, 184, 0.28) !important;
  background: rgba(255, 255, 255, 0.94) !important;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05) !important;
}
.st-key-multitrack_layers_panel [data-testid="stExpander"] {
  border: 1px solid rgba(245, 158, 11, 0.22) !important;
  border-radius: 12px !important;
  background: #fff !important;
  margin-bottom: 0.4rem !important;
  overflow: hidden;
}
.st-key-multitrack_layers_panel [data-testid="stExpander"] summary {
  font-weight: 800 !important;
  color: #0f172a !important;
  padding: 0.55rem 0.75rem !important;
}
.st-key-multitrack_layers_panel [data-testid="stExpander"] summary:hover {
  background: rgba(255, 251, 235, 0.9) !important;
}
.ui-mt-layer-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-left: 0.35rem;
}
.ui-mt-layer-badge.ready {
  color: #166534;
  background: rgba(34, 197, 94, 0.14);
  border: 1px solid rgba(34, 197, 94, 0.35);
}
.ui-mt-layer-badge.empty {
  color: #64748b;
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.35);
}
.st-key-multitrack_studio_panel [data-testid="stButton"] button[kind="primary"] {
  border-radius: 11px !important;
  font-weight: 850 !important;
}
.st-key-multitrack_export_panel {
  border-color: rgba(245, 158, 11, 0.35) !important;
  background: linear-gradient(180deg, #fffbeb 0%, #ffffff 100%) !important;
}
.st-key-multitrack_session_panel {
  padding: 0.55rem 0.7rem 0.5rem !important;
  border-color: rgba(245, 158, 11, 0.32) !important;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 251, 235, 0.55)) !important;
}
.ui-mt-session-setup-head {
  margin: 0 0 0.38rem;
  padding-bottom: 0.32rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.28);
}
.ui-mt-session-setup-kicker {
  display: inline-block;
  font-size: 0.6rem;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #d97706;
  margin: 0 0 0.15rem;
}
.ui-mt-session-setup-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 850;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.ui-mt-session-setup-sub {
  margin: 0.2rem 0 0;
  font-size: 0.74rem;
  color: #64748b;
  line-height: 1.35;
}
.ui-mt-session-context {
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem 0.35rem;
  margin: 0 0 0.38rem;
  padding: 0.32rem 0.4rem;
  border-radius: 10px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  background: linear-gradient(180deg, rgba(255, 251, 235, 0.95), rgba(255, 255, 255, 0.92));
}
.ui-mt-ctx-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.18rem 0.48rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 650;
  color: #334155;
  border: 1px solid rgba(148, 163, 184, 0.32);
  background: #fff;
  white-space: nowrap;
}
.ui-mt-ctx-badge strong { font-weight: 850; color: #0f172a; }
.ui-mt-ctx-ico { font-size: 0.76rem; line-height: 1; }
.ui-mt-ctx-badge.song { border-color: rgba(245, 158, 11, 0.45); background: rgba(255, 251, 235, 0.95); max-width: 100%; }
.ui-mt-ctx-badge.key-orig { border-color: rgba(99, 102, 241, 0.4); background: rgba(238, 242, 255, 0.95); }
.ui-mt-ctx-badge.key-practice { border-color: rgba(16, 185, 129, 0.42); background: rgba(236, 253, 245, 0.95); }
.ui-mt-ctx-badge.bpm { border-color: rgba(234, 88, 12, 0.4); background: rgba(255, 237, 213, 0.9); }
.ui-mt-ctx-badge.meter { border-color: rgba(14, 165, 233, 0.38); background: rgba(224, 242, 254, 0.9); }
.ui-mt-ctx-badge.scope { border-color: rgba(79, 70, 229, 0.38); background: rgba(238, 242, 255, 0.92); }
.ui-mt-ctx-badge.groove { border-color: rgba(217, 119, 6, 0.4); background: rgba(254, 243, 199, 0.92); }
.ui-mt-setup-section {
  margin: 0 0 0.38rem;
  padding: 0 0 0.32rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.22);
}
.ui-mt-setup-section:last-of-type { border-bottom: none; margin-bottom: 0.08rem; padding-bottom: 0; }
.ui-mt-setup-section-title {
  margin: 0 0 0.28rem;
  font-size: 0.68rem;
  font-weight: 850;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 0.32rem;
}
.ui-mt-setup-section-icon { font-size: 0.82rem; }
.ui-mt-setup-fields-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem 0.65rem;
}
.ui-mt-setup-fields-row.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 900px) {
  .ui-mt-setup-fields-row { grid-template-columns: 1fr; }
}
.ui-mt-field-label {
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #475569;
  margin: 0 0 0.22rem;
}
.ui-mt-target-line {
  margin: 0.22rem 0 0.35rem;
  padding: 0.3rem 0.45rem;
  border-radius: 8px;
  font-size: 0.74rem;
  color: #475569;
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.25);
}
.ui-mt-target-line strong { color: #0f172a; }
.st-key-multitrack_session_panel [data-testid="stHorizontalBlock"] {
  gap: 0.35rem 0.45rem !important;
  align-items: flex-start !important;
}
.st-key-multitrack_session_panel [data-testid="stWidgetLabel"] p,
.st-key-multitrack_session_panel label[data-testid="stWidgetLabel"] p {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  color: #475569 !important;
  margin-bottom: 0.12rem !important;
}
.st-key-multitrack_session_panel [data-testid="stSelectbox"] > div > div,
.st-key-multitrack_session_panel [data-testid="stMultiSelect"] > div > div {
  border-radius: 9px !important;
  min-height: 2.05rem !important;
}
.st-key-multitrack_session_panel [data-testid="stSlider"] > div > div {
  border-radius: 9px !important;
}
.st-key-multitrack_session_panel [data-testid="stCheckbox"] {
  margin: 0 !important;
  padding: 0.28rem 0.42rem !important;
  border-radius: 9px !important;
  border: 1px solid rgba(148, 163, 184, 0.32) !important;
  background: rgba(248, 250, 252, 0.95) !important;
  min-height: 2.35rem !important;
  display: flex !important;
  align-items: center !important;
}
.st-key-multitrack_session_panel [data-testid="stCheckbox"]:has(input:checked) {
  border-color: rgba(34, 197, 94, 0.55) !important;
  background: rgba(220, 252, 231, 0.65) !important;
  box-shadow: inset 0 0 0 1px rgba(34, 197, 94, 0.2) !important;
}
.st-key-multitrack_session_panel [data-testid="stCheckbox"] label,
.st-key-multitrack_session_panel [data-testid="stCheckbox"] label p {
  display: flex !important;
  font-size: 0.74rem !important;
  font-weight: 650 !important;
  color: #334155 !important;
  line-height: 1.25 !important;
  margin: 0 !important;
}
.st-key-multitrack_session_panel [data-testid="stCheckbox"]:has(input:checked) label p {
  color: #14532d !important;
  font-weight: 750 !important;
}
.st-key-multitrack_session_panel [data-testid="stRadio"] > div {
  gap: 0.28rem !important;
  padding: 0.28rem 0.38rem !important;
  border-radius: 9px !important;
  border: 1px solid rgba(148, 163, 184, 0.28) !important;
  background: rgba(255, 255, 255, 0.92) !important;
}
.st-key-multitrack_session_panel [data-testid="stRadio"] label p {
  font-size: 0.72rem !important;
}
.st-key-multitrack_session_panel .st-key-mt_prepare_backing button {
  min-height: 2.5rem !important;
  font-weight: 800 !important;
  border-radius: 10px !important;
  background: linear-gradient(135deg, #f59e0b 0%, #ea580c 55%, #c2410c 100%) !important;
  color: #fff !important;
  border: none !important;
  box-shadow: 0 6px 18px rgba(234, 88, 12, 0.32) !important;
}
"""


def _decorative_studio_header_css() -> str:
    return """
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&display=swap');

.ui-studio-script-header {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  margin: 0.15rem 0 0.65rem 0;
  padding: 0.75rem 1rem 0.85rem;
  border-radius: 14px;
  border: 1px solid var(--ui-studio-header-border, rgba(148, 163, 184, 0.35));
  background: var(--ui-studio-header-wash, linear-gradient(135deg, #f8fafc 0%, #ffffff 100%));
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.06);
}
.ui-studio-script-header-icon {
  font-size: 2.05rem;
  line-height: 1;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.12));
}
.ui-studio-script-header-kicker {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ui-studio-header-accent, #64748b);
  margin: 0 0 0.12rem 0;
}
.ui-studio-script-header-script {
  font-family: "Caveat", "Segoe Script", "Bradley Hand", cursive !important;
  font-size: 2.1rem !important;
  font-weight: 700 !important;
  line-height: 1.05 !important;
  margin: 0 !important;
  color: var(--ui-studio-header-accent, #0f172a) !important;
  letter-spacing: 0.01em !important;
}
.ui-studio-script-header-title {
  font-size: 1.05rem !important;
  font-weight: 800 !important;
  letter-spacing: -0.02em !important;
  line-height: 1.25 !important;
  margin: 0.12rem 0 0 !important;
  color: #0f172a !important;
}
.ui-studio-script-header-sub {
  margin: 0.22rem 0 0 !important;
  font-size: 0.84rem !important;
  line-height: 1.4 !important;
  color: #475569 !important;
}
.ui-studio-script-header--practice {
  --ui-studio-header-accent: #dc2626;
  --ui-studio-header-wash: linear-gradient(135deg, #fff5f5 0%, #ffffff 72%);
  --ui-studio-header-border: #fecaca;
}
.ui-studio-script-header--picker {
  --ui-studio-header-accent: #4f46e5;
  --ui-studio-header-wash: linear-gradient(135deg, #eef2ff 0%, #ffffff 72%);
  --ui-studio-header-border: #c7d2fe;
}
.ui-studio-script-header--backing {
  --ui-studio-header-accent: #2563eb;
  --ui-studio-header-wash: linear-gradient(135deg, #eff6ff 0%, #ffffff 72%);
  --ui-studio-header-border: #bfdbfe;
}
.ui-studio-script-header--custom {
  --ui-studio-header-accent: #059669;
  --ui-studio-header-wash: linear-gradient(135deg, #ecfdf5 0%, #ffffff 72%);
  --ui-studio-header-border: #a7f3d0;
}
.ui-studio-script-header--creative {
  --ui-studio-header-accent: #7c3aed;
  --ui-studio-header-wash: linear-gradient(135deg, #f5f3ff 0%, #ffffff 72%);
  --ui-studio-header-border: #ddd6fe;
}
.ui-studio-script-header--analysis {
  --ui-studio-header-accent: #ea580c;
  --ui-studio-header-wash: linear-gradient(135deg, #fff7ed 0%, #ffffff 72%);
  --ui-studio-header-border: #fed7aa;
}
.ui-studio-script-header--multitrack {
  --ui-studio-header-accent: #c2410c;
  --ui-studio-header-wash: linear-gradient(135deg, #fff7ed 0%, #ffffff 72%);
  --ui-studio-header-border: #fdba74;
}
.ui-studio-script-header--log {
  --ui-studio-header-accent: #0d9488;
  --ui-studio-header-wash: linear-gradient(135deg, #f0fdfa 0%, #ffffff 72%);
  --ui-studio-header-border: #99f6e4;
}
.ui-studio-script-header--openai {
  --ui-studio-header-accent: #0891b2;
  --ui-studio-header-wash: linear-gradient(135deg, #ecfeff 0%, #ffffff 72%);
  --ui-studio-header-border: #a5f3fc;
}
.ui-chart-key-mode-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin: 0.45rem 0 0.65rem 0;
  padding: 0.32rem 0.62rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  border: 1px solid transparent;
}
.ui-chart-key-mode-badge.is-written-on {
  color: #9a3412;
  background: linear-gradient(135deg, #ffedd5 0%, #fff7ed 100%);
  border-color: #fdba74;
}
.ui-chart-key-mode-badge.is-concert {
  color: #1e40af;
  background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
  border-color: #93c5fd;
}
.ui-script-word {
  font-family: "Caveat", "Segoe Script", "Bradley Hand", cursive !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em !important;
}
.ui-song-library-title .ui-script-word,
.ui-practice-control-title .ui-script-word,
.ui-backing-studio-title .ui-script-word {
  font-size: 1.65em;
  color: var(--ui-studio-header-accent, #dc2626);
}
.ui-practice-control-head { --ui-studio-header-accent: #dc2626; }
.ui-backing-studio-deck-head { --ui-studio-header-accent: #2563eb; }
.ui-song-library-head { --ui-studio-header-accent: #4f46e5; }
"""


def _ui_polish_phase2_css() -> str:
    """Phase-2 visual polish: charts/TAB, song cards, active song, readability."""
    return """
/* ---- UI polish P2: readability (darker labels, higher contrast) ---- */
:root {
  --studio-muted: #475569;
  --ui-muted: #475569;
}
.ui-page-nav-label,
.ui-active-song-recent-label,
.ui-practice-top .stCaption,
.ui-practice-top p[data-testid="stCaptionContainer"] {
  color: #334155 !important;
}
.ui-song-card-artist,
.ui-active-song-artist {
  color: #334155 !important;
}
.ui-active-song-facts dt,
.tab-bar-label,
.tab-str-label {
  color: #475569 !important;
}
.notation-output .notation-rhythm {
  color: #334155 !important;
}
[data-testid="stSidebar"] .ui-sb-section {
  color: #e2e8f0 !important;
  font-weight: 800 !important;
}
[data-testid="stSidebar"] .ui-sb-section.tone-nav {
  color: #f1f5f9 !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] p[data-testid="stCaptionContainer"] {
  color: #0f172a !important;
}
[data-testid="stSidebar"] .ui-ctrl-section-body .stSelectbox label,
[data-testid="stSidebar"] .ui-ctrl-section-body .stSlider label,
[data-testid="stSidebar"] .ui-ctrl-section-body .stRadio label {
  color: #1e293b !important;
}
.block-container .stCaption,
.block-container p[data-testid="stCaptionContainer"] {
  color: #334155 !important;
}
.ui-song-library-foot,
.ui-song-library-sub,
.ui-genre-filter-active-summary {
  color: #334155 !important;
}
.ui-section-jump .ui-bar-label,
.ui-bar-label,
.ui-instrument-strip-muted,
.ui-practice-setup-kicker,
.ui-backing-panel-kicker,
.ui-practice-control-kicker,
.ui-song-library-kicker,
.ui-multitrack-studio-kicker,
.ui-upload-studio-kicker {
  color: #334155 !important;
}
.block-container label[data-testid="stWidgetLabel"] p,
.block-container .stSelectbox label p,
.block-container .stSlider label p,
.block-container .stRadio label p {
  color: #1e293b !important;
}

/* ---- Chart / TAB — music-sheet presentation ---- */
.notation-output {
  border: 1px solid rgba(15, 23, 42, 0.14) !important;
  border-radius: 16px !important;
  background:
    repeating-linear-gradient(
      180deg,
      transparent 0,
      transparent 27px,
      rgba(15, 23, 42, 0.04) 27px,
      rgba(15, 23, 42, 0.04) 28px
    ),
    linear-gradient(180deg, #fffef8 0%, #fffdf5 55%, #faf8f0 100%) !important;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.85),
    0 10px 28px rgba(15, 23, 42, 0.08) !important;
  padding: 1rem 1.15rem 1.1rem 1.15rem !important;
}
.notation-output .notation-title {
  font-size: 1.05rem !important;
  font-weight: 900 !important;
  letter-spacing: -0.02em !important;
  border-bottom: 2px solid rgba(30, 64, 175, 0.18);
  padding-bottom: 0.35rem;
  margin-bottom: 0.55rem !important;
}
.notation-output .notation-chords {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(3.25rem, 1fr));
  gap: 0.3rem 0.45rem;
  font-size: 0.92rem !important;
  font-weight: 800 !important;
  color: #1e3a8a !important;
  margin-bottom: 0.65rem !important;
  padding: 0.45rem 0.55rem;
  border-radius: 10px;
  background: rgba(219, 234, 254, 0.35);
  border: 1px solid rgba(59, 130, 246, 0.2);
}
.notation-output.notation-tab .tab-lesson {
  background: rgba(255, 255, 255, 0.55);
  border-radius: 12px;
  padding: 0.35rem 0.15rem;
}
.tab-section-badge {
  font-size: 0.82rem !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  color: #1e3a8a !important;
  background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%) !important;
  border: 1px solid rgba(59, 130, 246, 0.35) !important;
  border-radius: 999px !important;
  padding: 0.22rem 0.72rem !important;
  margin: 0.55rem 0 0.45rem 0 !important;
  box-shadow: 0 2px 6px rgba(30, 64, 175, 0.1);
}
.tab-progression {
  gap: 0.45rem !important;
  margin-bottom: 0.75rem !important;
}
.tab-prog-chord {
  font-size: 0.95rem !important;
  padding: 0.28rem 0.62rem !important;
  border-radius: 10px !important;
  box-shadow: 0 2px 5px rgba(30, 64, 175, 0.08);
}
.tab-measure {
  border-radius: 14px !important;
  border-width: 1px !important;
  border-color: rgba(51, 65, 85, 0.35) !important;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.07) !important;
}
.tab-chord-name {
  font-size: 1.42rem !important;
}
.tab-beat {
  border-bottom-width: 2px !important;
  color: #64748b !important;
}
@media (max-width: 768px) {
  .notation-output {
    padding: 0.85rem 0.75rem !important;
    margin-left: -0.15rem;
    margin-right: -0.15rem;
  }
  .notation-output .notation-chords {
    grid-template-columns: repeat(auto-fill, minmax(2.75rem, 1fr));
    font-size: 0.98rem !important;
  }
  .tab-scroll-wrap {
    margin: 0 -0.5rem;
    padding-bottom: 0.5rem;
  }
}

/* ---- Song browse cards (Song Selection grid) ---- */
.ui-song-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.75rem;
  margin: 0.85rem 0 0.35rem 0;
}
.ui-song-card-grid-title {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #334155;
  margin: 0.25rem 0 0.15rem 0;
}
.ui-song-card-cell {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.ui-song-card {
  border: 1px solid rgba(99, 102, 241, 0.22) !important;
  border-radius: 16px !important;
  padding: 0.95rem 1rem 0.85rem 1rem !important;
  margin-bottom: 0 !important;
  min-height: 10.5rem !important;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.07) !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.ui-song-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.1) !important;
}
.ui-song-card.trusted {
  border-color: rgba(22, 163, 74, 0.42) !important;
  background: linear-gradient(145deg, #ecfdf5 0%, #ffffff 52%, #f8fafc 100%) !important;
  box-shadow: 0 4px 18px rgba(22, 163, 74, 0.12) !important;
}
.ui-song-card.trusted::before {
  content: "Trusted core";
  display: inline-block;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #166534;
  background: #dcfce7;
  border: 1px solid rgba(22, 163, 74, 0.25);
  border-radius: 999px;
  padding: 0.12rem 0.45rem;
  margin-bottom: 0.35rem;
}
.ui-song-card.active {
  border-color: rgba(37, 99, 235, 0.55) !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.16), 0 8px 24px rgba(37, 99, 235, 0.14) !important;
  background: linear-gradient(145deg, #eff6ff 0%, #ffffff 55%, #f8fafc 100%) !important;
}
.ui-song-card.active .ui-song-card-title::after {
  content: " · Active now";
  font-size: 0.68rem;
  font-weight: 800;
  color: #1d4ed8;
}
.ui-song-card-title {
  font-size: 1.08rem !important;
  font-weight: 900 !important;
}
.ui-song-pill {
  font-size: 0.7rem !important;
  padding: 0.22rem 0.5rem !important;
}
.ui-song-pill.level {
  background: #f1f5f9;
  color: #334155;
  border-color: rgba(100, 116, 139, 0.25);
}
.ui-song-card-cell .stButton > button {
  font-size: 0.72rem !important;
  font-weight: 800 !important;
  min-height: 2rem !important;
  border-radius: 10px !important;
}
@media (max-width: 720px) {
  .ui-song-card-grid {
    grid-template-columns: 1fr;
    gap: 0.55rem;
  }
}

"""


def _studio_panels_css() -> str:
    return (
        _backing_studio_all_css()
        + _practice_control_panel_css()
        + _creative_studio_panel_css()
        + _custom_builder_panel_css()
        + _upload_studio_panel_css()
        + _multitrack_studio_panel_css()
        + _simple_nav_css()
        + _decorative_studio_header_css()
        + _ui_polish_phase2_css()
    )


def _inject_app_theme_polish() -> None:
    """Layer of refinements on top of the base theme — keeps existing classes intact.

    Loaded AFTER the base style block so equal-specificity rules win on cascade.
    Goals: cleaner typography, consistent radii/shadows, subtler hover/focus,
    polished tabs/expanders, and tasteful genre/instrument accent classes.
    """
    import streamlit as st

    st.markdown(
        """
<style data-ui-polish="__UI_POLISH_VERSION__">
/* ===========================================================
   UI POLISH __UI_POLISH_VERSION__ — refined design tokens & component finishing
   Marker class .ui-polish-loaded is appended so we can confirm via DOM.
   =========================================================== */

:root {
  --ui-font: -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", "Segoe UI", system-ui, sans-serif;
  --ui-font-mono: "JetBrains Mono", "SF Mono", "Cascadia Code", ui-monospace, Menlo, Monaco, Consolas, monospace;
  --ui-ink: #0b1220;
  --ui-text: #1e293b;
  --ui-muted: #64748b;
  --ui-faint: #94a3b8;
  --ui-line: rgba(15, 23, 42, 0.08);
  --ui-line-2: rgba(15, 23, 42, 0.14);
  --ui-accent: #4f46e5;
  --ui-accent-soft: #eef2ff;
  --r-xs: 6px;
  --r-sm: 10px;
  --r-md: 14px;
  --r-lg: 18px;
  --r-xl: 22px;
  --shadow-1: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-2: 0 2px 8px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-3: 0 8px 24px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.04);
  --shadow-4: 0 16px 40px rgba(15, 23, 42, 0.10), 0 4px 12px rgba(15, 23, 42, 0.05);
  --ease: cubic-bezier(0.2, 0.7, 0.2, 1);
}

/* ---- Global typography polish ---- */
html, body, .block-container, [data-testid="stSidebar"] {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
.block-container {
  padding-top: 0.75rem;
  padding-bottom: 2.5rem;
}
.ui-page-title,
.ui-brand-main-title,
.ui-hero-title,
.ui-active-song-title,
.ui-backing-active-title,
.ui-card-title,
.ui-compact-title,
.ui-playback-setup-title,
.ui-now-playing .np-title {
  font-feature-settings: "ss01", "cv11";
  letter-spacing: -0.018em;
}
.block-container h1, .block-container h2, .block-container h3, .block-container h4 {
  letter-spacing: -0.015em;
}

/* ---- Cards & panels — consistent transitions / soft hover ---- */
.ui-card,
.ui-page-head,
.ui-ctrl-section,
.ui-song-card,
.ui-active-song-card,
.ui-backing-active-song,
.ui-playback-setup,
.ui-now-playing,
.ui-follow-strip,
.ui-section-jump,
.cpl-section-card,
.cpl-builder-panel,
.cpl-finish-panel,
.cpl-panel,
.cpl-section-block,
.tutorial-quick-card,
.notation-output {
  transition: transform 180ms var(--ease), box-shadow 180ms var(--ease), border-color 180ms var(--ease);
}
.ui-card:hover,
.ui-song-card:hover:not(.active),
.cpl-section-card:hover:not(.cpl-section-active),
.cpl-section-block:hover:not(.cpl-section-active) {
  box-shadow: var(--shadow-2);
  border-color: var(--ui-line-2);
}
.ui-active-song-card { box-shadow: var(--shadow-3); }
.ui-backing-active-song {
  box-shadow: 0 14px 38px rgba(30, 64, 175, 0.20), 0 2px 8px rgba(15, 23, 42, 0.06);
}

/* ---- Badge — uniform sizing/weight, less shouty ---- */
.ui-badge {
  font-size: 0.74rem;
  letter-spacing: 0.01em;
  padding: 0.26rem 0.6rem;
  font-weight: 700;
  transition: background-color 160ms var(--ease), border-color 160ms var(--ease);
}
.ui-backing-badge {
  font-weight: 750;
  letter-spacing: 0.02em;
}

/* ---- Buttons — softer corners, subtle lift, smoother feel ---- */
.block-container .stButton > button,
.block-container .stDownloadButton > button {
  border-radius: 10px !important;
  font-weight: 700 !important;
  transition: transform 140ms var(--ease), box-shadow 140ms var(--ease), filter 140ms var(--ease) !important;
}
.block-container .stButton > button:hover:not(:disabled),
.block-container .stDownloadButton > button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(15, 23, 42, 0.10);
}
.block-container .stButton > button:active:not(:disabled) {
  transform: translateY(0);
}
.block-container .stButton > button:disabled {
  opacity: 0.55 !important;
}

/* ---- Better focus rings ---- */
.block-container button:focus-visible,
.block-container [data-baseweb="select"] > div:focus-within,
.block-container input:focus-visible,
.block-container textarea:focus-visible {
  outline: 2px solid rgba(99, 102, 241, 0.45) !important;
  outline-offset: 2px !important;
}

/* ---- Selectbox / inputs — refined border + hover ---- */
.block-container [data-baseweb="select"] > div,
.block-container .stTextInput > div > div,
.block-container .stTextArea > div > div,
.block-container .stNumberInput > div > div {
  border-radius: 10px !important;
  border-color: rgba(15, 23, 42, 0.12) !important;
  transition: border-color 140ms var(--ease), box-shadow 140ms var(--ease);
}
.block-container [data-baseweb="select"] > div:hover {
  border-color: rgba(15, 23, 42, 0.22) !important;
}

/* ---- Slider — softer thumb shadow + accent ---- */
.block-container [data-baseweb="slider"] [role="slider"] {
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18) !important;
}

/* ---- Tabs — modern, focused active indicator ---- */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--ui-line);
  gap: 0.15rem;
  margin-bottom: 0.85rem;
}
div[data-testid="stTabs"] [data-baseweb="tab"] {
  font-weight: 700 !important;
  font-size: 0.86rem !important;
  padding: 0.55rem 0.85rem !important;
  color: var(--ui-muted) !important;
  border-radius: 10px 10px 0 0 !important;
  transition: background-color 140ms var(--ease), color 140ms var(--ease);
}
div[data-testid="stTabs"] [data-baseweb="tab"]:hover {
  color: var(--ui-text) !important;
  background: rgba(15, 23, 42, 0.04);
}
div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
  color: var(--ui-ink) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
  background: var(--ui-accent) !important;
  height: 2px !important;
  border-radius: 2px;
}

/* ---- Expanders — flatter, more modern ---- */
.block-container [data-testid="stExpander"] {
  border: 1px solid var(--ui-line) !important;
  border-radius: var(--r-md) !important;
  background: #ffffff !important;
  box-shadow: var(--shadow-1);
  margin-bottom: 0.6rem;
  overflow: hidden;
}
.block-container [data-testid="stExpander"] summary {
  padding: 0.6rem 0.85rem !important;
  font-weight: 750 !important;
  font-size: 0.92rem !important;
  color: var(--ui-text) !important;
  transition: background-color 140ms var(--ease);
}
.block-container [data-testid="stExpander"] summary:hover {
  background: rgba(15, 23, 42, 0.025);
}
.block-container [data-testid="stExpander"][open] summary {
  border-bottom: 1px solid var(--ui-line) !important;
}

/* ---- Top nav — calmer surface, clearer active state ---- */
.ui-studio-nav-segmented {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-color: var(--ui-line) !important;
  box-shadow: var(--shadow-1);
}
.ui-studio-nav-segmented [data-testid="stBaseButton-segmented_control"],
.ui-studio-nav-segmented [data-testid="stBaseButton-segmented_controlActive"] {
  border-radius: 10px !important;
  transition: background 140ms var(--ease), color 140ms var(--ease), box-shadow 140ms var(--ease) !important;
}
.ui-studio-nav-segmented [data-testid="stBaseButton-segmented_controlActive"] {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
  color: #fff !important;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08), 0 4px 12px rgba(220, 38, 38, 0.28) !important;
}

/* ---- Sidebar — slightly cleaner gradient + spacing ---- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0b1220 0%, #111827 50%, #1e293b 100%);
  border-right: 1px solid rgba(255,255,255,0.04);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0.75rem; }
[data-testid="stSidebar"] .stButton > button {
  border-radius: 9px !important;
}

/* ---- Sidebar nav items — calmer when inactive, clearer when active ---- */
.ui-sb-nav-wrap .studio-nav-item button {
  font-size: 0.79rem !important;
  letter-spacing: 0.01em;
}
.ui-sb-nav-wrap .studio-nav-item:not(.nav-btn-active) button {
  opacity: 0.88;
}
.ui-sb-nav-wrap .nav-btn-active button {
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.35) !important;
}

/* ---- Page header — calmer top spacing ---- */
.ui-page-head {
  padding: 0.85rem 1.05rem 0.95rem;
  box-shadow: var(--shadow-1);
}
.ui-page-title {
  font-size: 1.3rem;
  font-weight: 800;
}
.ui-compact-title {
  font-weight: 800;
  letter-spacing: -0.018em;
}

/* ---- Quick navigation label — tighter rhythm ---- */
.ui-page-nav-label {
  letter-spacing: 0.1em;
  color: var(--ui-faint);
  margin-bottom: 0.3rem;
}

/* ---- Now-playing strip — cleaner edge ---- */
.ui-now-playing {
  border-color: rgba(15, 23, 42, 0.10);
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  box-shadow: var(--shadow-1);
}
.ui-now-playing .np-title { font-weight: 800; }

/* ---- Active song card — cleaner hierarchy ---- */
.ui-active-song-card {
  border-color: rgba(15, 23, 42, 0.12);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 55%, #f1f5f9 100%);
}
.ui-active-song-card.trusted {
  border-color: rgba(34, 197, 94, 0.32);
  background: linear-gradient(135deg, #ffffff 0%, #f6fdf9 55%, #ecfdf5 100%);
}
.ui-active-song-card.active::before { display: none; }
.ui-active-song-kicker { color: var(--ui-accent); }
.ui-active-song-title { font-weight: 850; letter-spacing: -0.022em; }
.ui-active-song-facts dd { font-weight: 700; color: var(--ui-text); }

/* ---- Backing active song — softer, less heavy ---- */
.ui-backing-active-song {
  background: linear-gradient(135deg, #0b1220 0%, #1e3a8a 38%, #312e81 72%, #1e1b4b 100%);
}
.ui-backing-active-title { letter-spacing: -0.022em; }
.ui-backing-active-kicker { letter-spacing: 0.1em; }

/* ---- Card row rhythm ---- */
.ui-card + .ui-card { margin-top: 0.75rem; }

/* ---- Notation / TAB display — cleaner background, better spacing ---- */
.notation-output {
  border: 1px solid rgba(15, 23, 42, 0.18);
  background: #fdfdf6;
  box-shadow: var(--shadow-1);
  padding: 1rem 1.15rem;
}
.notation-output .notation-title {
  font-size: 0.92rem;
  font-weight: 800;
  letter-spacing: 0.02em;
}
.tab-measure {
  border: 1.5px solid rgba(15, 23, 42, 0.2);
  background: #fdfdf6;
  box-shadow: var(--shadow-1);
}
.tab-measure:hover { box-shadow: var(--shadow-2); }
.tab-prog-chord {
  border-color: rgba(30, 64, 175, 0.55);
  background: linear-gradient(180deg, #ffffff 0%, #eff6ff 100%);
}

/* ---- Scrollbars — subtle, slim ---- */
.block-container *::-webkit-scrollbar,
[data-testid="stSidebar"] *::-webkit-scrollbar {
  width: 10px; height: 10px;
}
.block-container *::-webkit-scrollbar-track,
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: transparent; }
.block-container *::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.18);
  border-radius: 999px;
  border: 2px solid transparent;
  background-clip: padding-box;
}
.block-container *::-webkit-scrollbar-thumb:hover {
  background: rgba(15, 23, 42, 0.32);
  background-clip: padding-box;
}
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 999px;
}

/* ---- Captions / helper text — softer, less attention-grabbing ---- */
.block-container .stCaption,
.block-container p[data-testid="stCaptionContainer"],
.block-container p[data-testid="stCaptionContainer"] p {
  color: var(--ui-muted) !important;
  line-height: 1.5;
}

/* ---- Section jump bar — calmer ---- */
.ui-section-jump {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: var(--shadow-1);
}

/* ---- Quick BPM card (Backing Track Quick Playback) ---- */
.ui-card.soft {
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border-color: var(--ui-line);
}
.ui-card.soft .ui-card-title {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ui-muted);
  font-weight: 800;
  margin-bottom: 0.55rem;
}

/* ---- Playback setup — tidier label/value hierarchy ---- */
.ui-playback-setup {
  background: linear-gradient(160deg, #ffffff 0%, #f8fafc 60%, #f1f5f9 100%);
  box-shadow: var(--shadow-1);
}
.ui-playback-setup-label {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
}
.ui-playback-setup-bpm {
  font-feature-settings: "tnum";
  font-size: 2.05rem;
  letter-spacing: -0.04em;
}

/* ---- Genre-aware accents on backing active card ---- */
.ui-backing-active-song.genre-jazz {
  background: linear-gradient(135deg, #0b1220 0%, #312e81 38%, #4c1d95 72%, #1e1b4b 100%);
}
.ui-backing-active-song.genre-bossa {
  background: linear-gradient(135deg, #052e2b 0%, #064e3b 38%, #115e59 72%, #0c2723 100%);
}
.ui-backing-active-song.genre-rock {
  background: linear-gradient(135deg, #0b1220 0%, #1e3a8a 38%, #1e40af 72%, #172554 100%);
}
.ui-backing-active-song.genre-blues {
  background: linear-gradient(135deg, #0b1220 0%, #1e3a8a 38%, #312e81 72%, #1c1917 100%);
}
.ui-backing-active-song.genre-funk {
  background: linear-gradient(135deg, #1c1917 0%, #7c2d12 38%, #b45309 72%, #422006 100%);
}
.ui-backing-active-song.genre-soul {
  background: linear-gradient(135deg, #1c0a2e 0%, #3b0764 38%, #6b21a8 72%, #831843 100%);
}
.ui-backing-active-song.genre-pop {
  background: linear-gradient(135deg, #0b1220 0%, #075985 38%, #1d4ed8 72%, #0c4a6e 100%);
}
.ui-backing-active-song.genre-classical {
  background: linear-gradient(135deg, #0f172a 0%, #1f2937 38%, #334155 72%, #0b1220 100%);
}
.ui-backing-active-song.genre-jewish {
  background: linear-gradient(135deg, #0b1220 0%, #1e3a8a 38%, #4c1d95 55%, #854d0e 100%);
}
.ui-active-song-card.genre-jewish {
  box-shadow: inset 4px 0 0 #ca8a04, 0 6px 24px rgba(37, 99, 235, 0.14);
}

/* ---- Instrument-aware accent line on the active song card ---- */
.ui-active-song-card { border-left-width: 1px; }
.ui-active-song-card.inst-guitar { box-shadow: inset 4px 0 0 #a16207, var(--shadow-3); }
.ui-active-song-card.inst-piano { box-shadow: inset 4px 0 0 #0e7490, var(--shadow-3); }
.ui-active-song-card.inst-bass { box-shadow: inset 4px 0 0 #6b21a8, var(--shadow-3); }
.ui-active-song-card.inst-saxophone { box-shadow: inset 4px 0 0 #a21caf, var(--shadow-3); }
.ui-active-song-card.inst-trumpet { box-shadow: inset 4px 0 0 #b45309, var(--shadow-3); }
.ui-active-song-card.inst-violin { box-shadow: inset 4px 0 0 #7c2d12, var(--shadow-3); }
.ui-active-song-card.inst-drums { box-shadow: inset 4px 0 0 #475569, var(--shadow-3); }
.ui-active-song-card.inst-vocal { box-shadow: inset 4px 0 0 #be185d, var(--shadow-3); }

/* ---- Small decorative musical accent on Active Song kicker ---- */
.ui-active-song-kicker::before {
  content: "\\266A  ";
  font-weight: 800;
  margin-right: 0.05rem;
  opacity: 0.7;
}
.ui-backing-active-kicker::before {
  content: "\\266A  ";
  margin-right: 0.05rem;
  opacity: 0.7;
}

/* ---- Studio deck — calmer surface ---- */
.ui-studio-deck {
  background: linear-gradient(170deg, #ffffff 0%, #f8fafc 60%, #f1f5f9 100%);
  border-color: var(--ui-line);
  box-shadow: var(--shadow-1);
}

/* ---- Source banner (sidebar) — slightly cleaner ---- */
[data-testid="stSidebar"] .ui-source-banner {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.10);
}

/* ---- Markdown content — calmer rhythm ---- */
.block-container .stMarkdown p { line-height: 1.55; }
.block-container .stMarkdown h2 { margin-top: 1.1rem; }
.block-container .stMarkdown h3 { margin-top: 0.9rem; }

/* ---- Reduce vertical noise from empty containers ---- */
[data-testid="stVerticalBlock"] > div:empty { display: none; }
.block-container hr { border-color: var(--ui-line); margin: 1rem 0; }

/* ---- Animations: subtle fade for newly rendered cards ---- */
@keyframes ui-fade-in {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}
.ui-active-song-card,
.ui-backing-active-song,
.ui-page-head,
.ui-backing-leadsheet-card {
  animation: ui-fade-in 240ms var(--ease) both;
}

/* ---- Backing track lead-sheet card (auto-opens after Generate) ---- */
.ui-backing-leadsheet-card {
  border: 1px solid rgba(22, 163, 74, 0.30);
  border-radius: var(--r-md);
  padding: 0.85rem 0.95rem 0.95rem 0.95rem;
  margin: 0.85rem 0 1.1rem 0;
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
  box-shadow: 0 4px 18px rgba(22, 163, 74, 0.10), var(--shadow-1);
}
.ui-backing-leadsheet-card .ui-bar-label {
  letter-spacing: 0.08em;
}

/* ---- Responsive trims ---- */
@media (max-width: 1100px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
@media (max-width: 760px) {
  .ui-active-song-title { font-size: 1.08rem; }
  .ui-backing-active-title { font-size: 1.02rem; }
  .ui-playback-setup-bpm { font-size: 1.7rem; }
  .ui-page-title { font-size: 1.15rem; }
  .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
}

/* =========================================================================
   Voice / Vocal Performance Mode
   ------------------------------------------------------------------------
   Applied when the active instrument is "Voice" (modifier class `.inst-voice`
   on the active-song cards). Karaoke session mode layers `.mode-karaoke`
   on top - subtle, warm, performance-ready - never gimmicky.
   ========================================================================= */

/* Soft rose/amber accent on the cards in voice mode */
.ui-active-song-card.inst-voice,
.ui-active-song-card.inst-singer { box-shadow: inset 4px 0 0 #be185d, var(--shadow-3); }
.ui-backing-active-song.inst-voice,
.ui-backing-active-song.inst-singer {
  background: linear-gradient(135deg, #1c0a14 0%, #831843 38%, #be185d 72%, #4a044e 100%);
}

/* Karaoke session: subtle warm halo + slightly elevated card */
.ui-active-song-card.mode-karaoke,
.ui-backing-active-song.mode-karaoke {
  box-shadow:
    0 0 0 1px rgba(190, 24, 93, 0.20),
    0 14px 38px rgba(190, 24, 93, 0.18),
    var(--shadow-3);
}
.ui-backing-active-song.mode-karaoke .ui-backing-active-kicker {
  color: #fbcfe8 !important;
  letter-spacing: 0.10em;
}

/* ---------- Karaoke setlist (Song Selection) ---------------------
   Vocal-stage / neon-lounge aesthetic: deep purple card, magenta
   accents, soft pink glow on hover, neon-magenta highlight on the
   "Now Singing" row, warm pink on the "Editing" row. Scoped to the
   keyed container so it does NOT leak onto the rest of the page.
   The wrapper class ``.st-key-karaoke_stage`` is emitted by
   ``st.container(key="karaoke_stage")`` in karaoke_ui.py. */

.st-key-karaoke_stage .ui-karaoke-setlist {
  border: 1px solid rgba(244, 114, 182, 0.30);
  border-radius: 18px;
  padding: 1.20rem 1.30rem 1.10rem 1.30rem;
  margin: 0.85rem 0 0.70rem 0;
  background:
    radial-gradient(140% 110% at 12% -10%, rgba(236, 72, 153, 0.18) 0%, rgba(236, 72, 153, 0) 60%),
    radial-gradient(140% 110% at 92% 110%, rgba(168, 85, 247, 0.20) 0%, rgba(168, 85, 247, 0) 60%),
    linear-gradient(180deg, #1a0b2e 0%, #2a0f3f 55%, #1f0a36 100%);
  color: #fce7f3;
  box-shadow:
    0 22px 50px -20px rgba(8, 4, 28, 0.85),
    0 4px 14px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.07);
  position: relative;
  overflow: hidden;
}
.st-key-karaoke_stage .ui-karaoke-setlist::before {
  /* neon-pink top sheen */
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 2px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(244, 114, 182, 0.55) 30%,
    rgba(216, 180, 254, 0.55) 50%,
    rgba(244, 114, 182, 0.55) 70%,
    transparent 100%);
  filter: blur(0.5px);
}
.st-key-karaoke_stage .ui-karaoke-setlist-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #f9a8d4;
  margin: 0 0 0.30rem 0;
  text-shadow: 0 0 12px rgba(244, 114, 182, 0.45);
}
.st-key-karaoke_stage .ui-karaoke-setlist-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f472b6;
  box-shadow: 0 0 10px rgba(244, 114, 182, 0.9);
  animation: ui-karaoke-pulse 1.6s ease-in-out infinite;
}
@keyframes ui-karaoke-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.45; transform: scale(0.85); }
}
.st-key-karaoke_stage .ui-karaoke-setlist-title {
  font-size: 1.20rem;
  font-weight: 800;
  letter-spacing: 0;
  color: #ffffff;
  margin: 0 0 0.55rem 0;
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.55);
}
.st-key-karaoke_stage .ui-karaoke-setlist-count {
  font-weight: 700;
  color: #f9a8d4;
  margin-left: 0.35rem;
  letter-spacing: 0.05em;
  opacity: 0.95;
}
.st-key-karaoke_stage .ui-karaoke-setlist-empty {
  color: #f5d0fe;
  opacity: 0.8;
  font-size: 0.95rem;
  font-style: italic;
}

/* Captions inside the stage container (the "click a song..." help
   text and the "Karaoke set in progress" footer) need to lift off
   the dark purple. Streamlit renders captions as small grey text - we
   override so they read clearly on the dark vocal-stage card. */
.st-key-karaoke_stage [data-testid="stCaptionContainer"],
.st-key-karaoke_stage .stCaption,
.st-key-karaoke_stage small {
  color: #f5d0fe !important;
  opacity: 0.95;
}
.st-key-karaoke_stage [data-testid="stCaptionContainer"] strong,
.st-key-karaoke_stage .stCaption strong {
  color: #ffffff;
}

/* Toggle / slider / selectbox labels on the dark card. */
.st-key-karaoke_stage label,
.st-key-karaoke_stage [data-testid="stWidgetLabel"] p {
  color: #fbcfe8 !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em;
}

/* Default karaoke-stage button look (used by the action row at the
   bottom: Start Set / Stop / Clear Setlist). Dark plum panel with a
   thin magenta border; hover = soft pink glow; primary type (Start
   Set, currently-editing pick) = magenta neon gradient. The compact
   *setlist row* buttons override this further down via the
   ``.ui-karaoke-pick-wrap`` and ``.ui-karaoke-ctrl-wrap`` hooks so
   each row sits tighter and reads more like a live setlist than a
   stack of bulky Streamlit primary buttons. */
.st-key-karaoke_stage .stButton > button {
  background: rgba(46, 20, 75, 0.72) !important;
  color: #fce7f3 !important;
  border: 1px solid rgba(244, 114, 182, 0.22) !important;
  border-radius: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em;
  transition:
    background 160ms ease,
    border-color 160ms ease,
    box-shadow 200ms ease,
    transform 160ms ease,
    filter 160ms ease !important;
}
.st-key-karaoke_stage .stButton > button:hover:not(:disabled) {
  background: rgba(76, 29, 113, 0.62) !important;
  border-color: rgba(244, 114, 182, 0.50) !important;
  box-shadow:
    0 8px 22px -8px rgba(236, 72, 153, 0.42),
    inset 0 0 0 1px rgba(244, 114, 182, 0.16) !important;
  transform: translateY(-1px);
  filter: brightness(1.04);
}
.st-key-karaoke_stage .stButton > button:disabled {
  background: rgba(46, 20, 75, 0.32) !important;
  color: rgba(252, 231, 243, 0.40) !important;
  border-color: rgba(244, 114, 182, 0.12) !important;
}
/* Primary-typed buttons in the stage: the currently-editing song's
   pick button and the "Start Karaoke Set" button. */
.st-key-karaoke_stage .stButton > button[kind="primary"] {
  background: linear-gradient(180deg, #ec4899 0%, #be185d 100%) !important;
  color: #ffffff !important;
  border-color: rgba(251, 207, 232, 0.55) !important;
  box-shadow:
    0 12px 28px -6px rgba(236, 72, 153, 0.55),
    0 0 0 1px rgba(251, 207, 232, 0.35) inset !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.40);
}
.st-key-karaoke_stage .stButton > button[kind="primary"]:hover:not(:disabled) {
  background: linear-gradient(180deg, #f472b6 0%, #db2777 100%) !important;
  box-shadow:
    0 16px 36px -6px rgba(236, 72, 153, 0.75),
    0 0 0 1px rgba(251, 207, 232, 0.55) inset !important;
}

/* ------- Compact setlist rows ------------------------------------
   The pick button (queue # + title — artist) used to render as a
   chunky full-width Streamlit button. The wrapper div emitted by
   ``karaoke_ui.render_karaoke_setlist_panel`` lets us scope a much
   tighter, professional "live setlist row" look just to those
   buttons - while leaving the action row (Start / Stop / Clear) and
   the broader app's buttons untouched. */
.st-key-karaoke_stage .ui-karaoke-pick-wrap {
  /* Reserve a tiny strip of space above the pick button so the
     marker pill (when present) reads as status, not as a separate
     row. The min-height keeps every row aligned even when no marker
     is rendered, so the setlist looks like a clean tabular list. */
  min-height: 14px;
  display: flex;
  align-items: center;
  margin: 0.30rem 0 0.10rem 0.05rem;
  position: relative;
}
.st-key-karaoke_stage .ui-karaoke-pick-wrap.is-idle {
  /* No marker — collapse the strip a touch tighter. */
  min-height: 6px;
  margin-top: 0.10rem;
}
/* The button that immediately follows the pick wrap = the song
   title row. Tighter typography, smaller height, monospaced queue
   number, soft gradient that lifts active rows without screaming. */
.st-key-karaoke_stage .ui-karaoke-pick-wrap + div .stButton > button {
  min-height: 36px !important;
  height: 36px !important;
  padding: 0.30rem 0.85rem !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  letter-spacing: 0.005em;
  text-align: left !important;
  /* Subtle setlist-row gradient: slightly lighter at the top so each
     row reads as a discrete pill against the deep purple panel. */
  background: linear-gradient(180deg,
    rgba(64, 28, 102, 0.70) 0%,
    rgba(40, 14, 70, 0.85) 100%) !important;
  border: 1px solid rgba(216, 180, 254, 0.16) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.03),
    0 1px 0 rgba(0, 0, 0, 0.25);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.st-key-karaoke_stage .ui-karaoke-pick-wrap + div .stButton > button > div,
.st-key-karaoke_stage .ui-karaoke-pick-wrap + div .stButton > button p {
  /* Streamlit wraps button text in a <div><p> sometimes. Make sure
     the inner text inherits our compact styling and doesn't overflow
     vertically with extra padding. */
  margin: 0 !important;
  padding: 0 !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.005em;
  line-height: 1.25 !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.st-key-karaoke_stage .ui-karaoke-pick-wrap + div .stButton > button:hover:not(:disabled) {
  background: linear-gradient(180deg,
    rgba(91, 41, 142, 0.85) 0%,
    rgba(60, 21, 99, 0.95) 100%) !important;
  border-color: rgba(244, 114, 182, 0.45) !important;
  box-shadow:
    0 6px 18px -8px rgba(236, 72, 153, 0.45),
    inset 0 0 0 1px rgba(244, 114, 182, 0.14) !important;
  transform: translateY(-1px);
}
/* "Editing" row (the master selection) = primary-type Streamlit
   button. Reuse the magenta gradient but at the same compact size,
   and add a soft left-border accent stripe so the active row is
   instantly identifiable from across the room. */
.st-key-karaoke_stage .ui-karaoke-pick-wrap.is-editing + div .stButton > button,
.st-key-karaoke_stage .ui-karaoke-pick-wrap + div .stButton > button[kind="primary"] {
  background: linear-gradient(180deg, #db2777 0%, #9d174d 100%) !important;
  border: 1px solid rgba(251, 207, 232, 0.55) !important;
  color: #ffffff !important;
  box-shadow:
    0 8px 22px -8px rgba(236, 72, 153, 0.55),
    inset 0 0 0 1px rgba(251, 207, 232, 0.30),
    inset 4px 0 0 0 rgba(251, 207, 232, 0.85) !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.40);
  padding-left: 1.05rem !important;  /* leave room for the inset accent stripe */
}
/* "Now Singing" row (live karaoke session). Even brighter neon
   accent than "Editing" so the performer can spot it on stage. */
.st-key-karaoke_stage .ui-karaoke-pick-wrap.is-singing + div .stButton > button {
  background: linear-gradient(180deg, #f472b6 0%, #be185d 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.40) !important;
  color: #ffffff !important;
  box-shadow:
    0 10px 30px -6px rgba(236, 72, 153, 0.75),
    0 0 0 1px rgba(251, 207, 232, 0.45) inset,
    inset 4px 0 0 0 #ffffff !important;
  padding-left: 1.05rem !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
}

/* Square icon controls (up / down / remove). One thin pill per
   action, centered glyph, clearly distinct from the title row. */
.st-key-karaoke_stage .ui-karaoke-ctrl-wrap {
  /* Match the pick wrap height so the controls vertically align
     with the pick button below, not floating above it. */
  min-height: 6px;
  margin: 0.30rem 0 0.10rem 0;
}
.st-key-karaoke_stage .ui-karaoke-ctrl-wrap + div .stButton > button {
  min-height: 36px !important;
  height: 36px !important;
  padding: 0 !important;
  border-radius: 9px !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  background: rgba(46, 20, 75, 0.55) !important;
  border: 1px solid rgba(216, 180, 254, 0.18) !important;
  color: #f5d0fe !important;
  letter-spacing: 0;
}
.st-key-karaoke_stage .ui-karaoke-ctrl-wrap + div .stButton > button:hover:not(:disabled) {
  background: rgba(91, 41, 142, 0.70) !important;
  border-color: rgba(244, 114, 182, 0.50) !important;
  color: #ffffff !important;
  box-shadow:
    0 4px 14px -6px rgba(236, 72, 153, 0.50) !important;
}
/* The remove (✕) control gets a slightly cooler hover so it reads
   as a destructive action without screaming red against the magenta
   palette. */
.st-key-karaoke_stage .ui-karaoke-ctrl-wrap[data-action="remove"]
  + div .stButton > button:hover:not(:disabled) {
  background: rgba(159, 18, 57, 0.70) !important;
  border-color: rgba(251, 113, 133, 0.55) !important;
  color: #ffe4e6 !important;
  box-shadow:
    0 4px 14px -6px rgba(244, 63, 94, 0.50) !important;
}
.st-key-karaoke_stage .ui-karaoke-ctrl-wrap + div .stButton > button:disabled {
  background: rgba(46, 20, 75, 0.20) !important;
  color: rgba(245, 208, 254, 0.30) !important;
  border-color: rgba(216, 180, 254, 0.10) !important;
}

/* Toggle (st.toggle) and selectbox/slider widgets inherit from the
   site-wide controls. Add a magenta tint on the toggle thumb so the
   karaoke-only prefs feel cohesive with the rest of the card. */
.st-key-karaoke_stage [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"],
.st-key-karaoke_stage [data-baseweb="checkbox"] [role="switch"][aria-checked="true"] {
  background: linear-gradient(180deg, #ec4899 0%, #be185d 100%) !important;
}

/* Status pill that sits above each clickable setlist row's pick
   button. "Now Singing" (active karaoke session) or "Editing"
   (master selection) - tiny chip so it reads as status metadata,
   not as part of the song title. */
.st-key-karaoke_stage .ui-karaoke-row-marker {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  font-size: 0.60rem;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 1px 8px 1px 8px;
  border-radius: 999px;
  line-height: 1.55;
}
.st-key-karaoke_stage .ui-karaoke-row-marker.marker-singing {
  color: #ffffff;
  background: linear-gradient(180deg, #ec4899 0%, #be185d 100%);
  box-shadow:
    0 0 0 1px rgba(251, 207, 232, 0.55),
    0 0 12px rgba(236, 72, 153, 0.50);
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.40);
}
.st-key-karaoke_stage .ui-karaoke-row-marker.marker-singing::before {
  content: "";
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 7px rgba(255, 255, 255, 0.9);
  animation: ui-karaoke-pulse 1.4s ease-in-out infinite;
}
.st-key-karaoke_stage .ui-karaoke-row-marker.marker-editing {
  color: #fdf4ff;
  background: rgba(168, 85, 247, 0.30);
  border: 1px solid rgba(216, 180, 254, 0.40);
  box-shadow: inset 0 0 0 1px rgba(216, 180, 254, 0.10);
}

/* Restyle Streamlit's native selectbox + slider chrome on the stage
   to match the magenta theme (without overriding upstream behaviour). */
.st-key-karaoke_stage [data-baseweb="select"] > div,
.st-key-karaoke_stage [data-baseweb="input"] > div {
  background: rgba(76, 29, 113, 0.45) !important;
  border-color: rgba(244, 114, 182, 0.32) !important;
  color: #fce7f3 !important;
}
.st-key-karaoke_stage [data-baseweb="select"] svg {
  fill: #f9a8d4 !important;
}
.st-key-karaoke_stage [data-testid="stSlider"] [data-baseweb="slider"] > div:nth-child(2) {
  background: rgba(244, 114, 182, 0.30) !important;
}
.st-key-karaoke_stage [data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
  background: linear-gradient(180deg, #ec4899 0%, #be185d 100%) !important;
  border-color: rgba(251, 207, 232, 0.55) !important;
}

/* Karaoke transition card on Backing Track page */
.ui-karaoke-transition {
  border-radius: var(--r-md);
  border: 1px solid rgba(190, 24, 93, 0.28);
  background: linear-gradient(135deg, #831843 0%, #be185d 60%, #f472b6 100%);
  color: #ffffff;
  padding: 1.10rem 1.30rem;
  margin: 0.75rem 0 0.85rem 0;
  box-shadow: 0 14px 36px rgba(190, 24, 93, 0.28), var(--shadow-3);
  display: flex;
  align-items: center;
  gap: 1.10rem;
}
.ui-karaoke-transition .ui-karaoke-transition-icon {
  font-size: 1.80rem;
  line-height: 1;
  opacity: 0.95;
}
.ui-karaoke-transition .ui-karaoke-transition-kicker {
  font-size: 0.70rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.85;
  margin: 0 0 0.20rem 0;
}
.ui-karaoke-transition .ui-karaoke-transition-title {
  font-size: 1.20rem;
  font-weight: 800;
  margin: 0 0 0.15rem 0;
}
.ui-karaoke-transition .ui-karaoke-transition-meta {
  font-size: 0.92rem;
  opacity: 0.90;
}

/* Voice-mode lyric panel: larger, calmer, vertically generous - the
   singer's primary instrument is the lyric, so make it the focal point. */
.mode-karaoke .ui-lyrics-panel,
.inst-voice + .ui-lyrics-panel,
[data-vocal-focus="true"] .ui-lyrics-panel {
  border-radius: var(--r-md);
  border: 1px solid rgba(190, 24, 93, 0.18);
  background: linear-gradient(180deg, #ffffff 0%, #fff7fb 100%);
  box-shadow: 0 6px 20px rgba(190, 24, 93, 0.06), var(--shadow-1);
}

/* Larger lyric typography in voice mode (applied via body wrapper) */
[data-vocal-focus="true"] .lyric-line,
[data-vocal-focus="true"] .section-card .lyric-text,
[data-vocal-focus="true"] .ui-bar-lyric {
  font-size: 1.10rem !important;
  line-height: 1.55 !important;
  letter-spacing: 0.005em;
}
[data-vocal-focus="true"] .ui-bar-label {
  opacity: 0.55;
}

/* Karaoke "Now Singing" banner pill */
.ui-karaoke-now-singing {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.30rem 0.80rem;
  border-radius: 999px;
  background: linear-gradient(135deg, #831843, #be185d);
  color: #ffffff;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  box-shadow: 0 4px 12px rgba(190, 24, 93, 0.30);
  margin: 0 0 0.40rem 0;
}
.ui-karaoke-now-singing::before {
  content: "\\266B";
  font-size: 0.95rem;
  opacity: 0.95;
}

/* ---------- Karaoke queue preview (Backing Track page) ---------- */
.ui-karaoke-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  margin: 10px 0;
  border: 1px solid rgba(190, 24, 93, 0.18);
  border-radius: var(--r-md);
  background: linear-gradient(180deg, #fffafc 0%, #ffffff 100%);
  box-shadow: 0 4px 14px rgba(190, 24, 93, 0.06);
}
.ui-karaoke-preview-header {
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #831843;
  margin-bottom: 2px;
}
.ui-karaoke-preview-row {
  display: grid;
  grid-template-columns: 110px 1fr auto;
  align-items: baseline;
  gap: 10px;
  padding: 4px 0;
  border-top: 1px dashed rgba(15, 23, 42, 0.06);
}
.ui-karaoke-preview-row:first-of-type { border-top: 0; }
.ui-karaoke-preview-row.current {
  background: linear-gradient(90deg, rgba(190, 24, 93, 0.08), transparent 75%);
  border-radius: 8px;
  padding-left: 8px;
  padding-right: 8px;
  margin: 0 -8px;
}
.ui-karaoke-preview-label {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
}
.ui-karaoke-preview-row.current .ui-karaoke-preview-label {
  color: #be185d;
}
.ui-karaoke-preview-title {
  font-size: 1.00rem;
  font-weight: 750;
  color: #0f172a;
}
.ui-karaoke-preview-row.current .ui-karaoke-preview-title {
  font-weight: 850;
}
.ui-karaoke-preview-artist {
  font-size: 0.86rem;
  color: #64748b;
}

/* ---------- Karaoke missing-lyrics CTA ---------- */
.ui-karaoke-missing-lyrics {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  margin: 12px 0;
  border: 1px solid rgba(190, 24, 93, 0.24);
  border-radius: var(--r-md);
  background: linear-gradient(120deg, #fff1f5 0%, #fff7fb 100%);
}
.ui-karaoke-missing-lyrics .ui-karaoke-missing-icon {
  font-size: 1.6rem;
  background: rgba(190, 24, 93, 0.12);
  border-radius: 999px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ui-karaoke-missing-lyrics .ui-karaoke-missing-kicker {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #be185d;
  margin: 0 0 2px 0;
}
.ui-karaoke-missing-lyrics .ui-karaoke-missing-title {
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 2px 0;
}
.ui-karaoke-missing-lyrics .ui-karaoke-missing-meta {
  font-size: 0.88rem;
  color: #64748b;
  margin: 0;
}

/* ---------- Karaoke voice mode: lyrics primary, chords secondary ----------
   Applies whenever the page is rendered in karaoke / voice mode
   (driven by `document.body.dataset.vocalFocus` set in the main app). */
[data-vocal-focus="true"] .ui-bar {
  background: rgba(255, 255, 255, 0.90);
}
[data-vocal-focus="true"] .ui-bar .chord-cell,
[data-vocal-focus="true"] .chord-cell {
  opacity: 0.78;
  filter: saturate(0.92);
}
[data-vocal-focus="true"] .chord-cell.current-chord {
  opacity: 1 !important;
  filter: none !important;
}
[data-vocal-focus="true"] .lyric-line,
[data-vocal-focus="true"] .section-card .lyric-text,
[data-vocal-focus="true"] .ui-bar-lyric {
  font-size: 1.18rem !important;
  font-weight: 600;
  color: #0f172a;
}
[data-vocal-focus="true"] .section-card.current .lyric-line,
[data-vocal-focus="true"] .section-card.current .lyric-text {
  font-size: 1.32rem !important;
  font-weight: 700;
}
[data-vocal-focus="true"] .section-card { padding-block: 16px; }

/* ---------- Song library panel (Song Selection page) ---------------
   Scoped to ``st.container(key="song_library_panel")`` so the
   polished search/filter card does not leak onto other pages. */
.st-key-song_library_panel {
  border: 1px solid rgba(99, 102, 241, 0.22);
  border-radius: 16px;
  padding: 1.05rem 1.15rem 1.10rem 1.15rem;
  margin: 0.35rem 0 1.05rem 0;
  background:
    radial-gradient(120% 90% at 8% -8%, rgba(99, 102, 241, 0.10) 0%, rgba(99, 102, 241, 0) 55%),
    radial-gradient(110% 90% at 96% 108%, rgba(14, 165, 233, 0.08) 0%, rgba(14, 165, 233, 0) 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 58%, #f1f5f9 100%);
  box-shadow:
    0 14px 36px -22px rgba(15, 23, 42, 0.28),
    0 2px 8px rgba(15, 23, 42, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  position: relative;
  overflow: hidden;
}
.st-key-song_library_panel::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 2px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(99, 102, 241, 0.45) 28%,
    rgba(56, 189, 248, 0.40) 50%,
    rgba(99, 102, 241, 0.45) 72%,
    transparent 100%);
}
.st-key-song_library_panel .ui-song-library-head {
  margin: 0 0 0.85rem 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.28);
}
.st-key-song_library_panel .ui-song-library-kicker {
  display: inline-block;
  margin: 0 0 0.35rem 0;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #4f46e5;
}
.st-key-song_library_panel .ui-song-library-title {
  margin: 0;
  font-size: 1.22rem;
  font-weight: 850;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.2;
}
.st-key-song_library_panel .ui-song-library-sub {
  margin: 0.35rem 0 0 0;
  font-size: 0.84rem;
  color: #64748b;
  line-height: 1.45;
  max-width: 42rem;
}
.st-key-song_library_panel .ui-song-library-count {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.55rem;
  padding: 0.22rem 0.62rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  color: #3730a3;
  background: rgba(99, 102, 241, 0.10);
  border: 1px solid rgba(99, 102, 241, 0.22);
}
.st-key-song_library_panel .ui-song-library-field-label {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #475569;
  margin: 0 0 0.28rem 0;
}

__BACKING_STUDIO_PANEL_CSS__
.st-key-song_library_panel .ui-song-library-field-hint {
  font-size: 0.74rem;
  color: #94a3b8;
  margin: 0 0 0.35rem 0;
  line-height: 1.35;
}
.st-key-song_library_panel .ui-song-library-selected {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem 0.75rem;
  margin: 0.65rem 0 0.15rem 0;
  padding: 0.62rem 0.75rem;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(56, 189, 248, 0.06) 100%);
  border: 1px solid rgba(99, 102, 241, 0.24);
}
.st-key-song_library_panel .ui-song-library-selected-label {
  font-size: 0.68rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6366f1;
  flex: 0 0 auto;
}
.st-key-song_library_panel .ui-song-library-selected-title {
  font-size: 0.95rem;
  font-weight: 850;
  color: #0f172a;
  line-height: 1.25;
}
.st-key-song_library_panel .ui-song-library-selected-meta {
  font-size: 0.78rem;
  font-weight: 650;
  color: #64748b;
}
.st-key-song_library_panel .ui-song-library-genre-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.14rem 0.55rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  color: #3730a3;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(99, 102, 241, 0.28);
}
.st-key-song_library_panel .ui-song-library-source {
  margin: 0 0 0.85rem 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}
.st-key-song_library_panel .ui-song-library-source .ui-page-nav-label {
  margin-bottom: 0.35rem;
}
.st-key-song_library_panel [data-testid="stSelectbox"] label,
.st-key-song_library_panel [data-testid="stTextInput"] label {
  display: none !important;
}
.st-key-song_library_panel [data-testid="stSelectbox"] > div > div,
.st-key-song_library_panel [data-testid="stTextInput"] input {
  border-radius: 10px !important;
  border-color: rgba(148, 163, 184, 0.55) !important;
  min-height: 2.45rem !important;
  font-size: 0.88rem !important;
}
.st-key-song_library_panel [data-testid="stSelectbox"] > div > div:focus-within,
.st-key-song_library_panel [data-testid="stTextInput"] input:focus {
  border-color: rgba(99, 102, 241, 0.65) !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.14) !important;
}
.st-key-song_library_panel [data-testid="stRadio"] label {
  font-size: 0.84rem !important;
  font-weight: 650 !important;
}
.st-key-song_library_panel [data-baseweb="radio"] {
  gap: 0.35rem !important;
}
.st-key-song_library_panel .ui-song-library-active-row {
  margin-top: 0.55rem;
}
.st-key-song_library_panel .ui-song-library-foot {
  margin: 0.55rem 0 0 0;
  font-size: 0.76rem;
  color: #64748b;
  line-height: 1.4;
}

/* ---------- YouTube integration (Song Selection + Practice page) ---------- */
.ui-youtube-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1.1rem;
  margin: 0.5rem 0 0.25rem 0;
  background: linear-gradient(135deg, #ff0000, #c4302b);
  color: #ffffff !important;
  font-weight: 700;
  font-size: 0.96rem;
  letter-spacing: 0.01em;
  text-decoration: none !important;
  border-radius: 999px;
  box-shadow: 0 4px 12px rgba(196, 48, 43, 0.30);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.ui-youtube-link-btn:hover {
  transform: translateY(-1px);
  background: linear-gradient(135deg, #ff2424, #d24238);
  box-shadow: 0 6px 18px rgba(196, 48, 43, 0.40);
  color: #ffffff !important;
}
.ui-youtube-link-btn:active {
  transform: translateY(0);
}
.ui-youtube-thumb {
  display: block;
  max-width: 360px;
  width: 100%;
  height: auto;
  margin: 0.4rem 0;
  border-radius: var(--r-md);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.16);
}
.ui-youtube-embed {
  position: relative;
  width: 100%;
  padding-top: 56.25%;
  margin: 0.5rem 0 0.25rem 0;
  border-radius: var(--r-md);
  overflow: hidden;
  background: #000;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.20);
}
.ui-youtube-embed iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

/* The polish stylesheet keeps a `data-ui-polish` attribute on its <style>
   element so its presence can be confirmed via DOM inspection if needed,
   without showing any visible debug UI to the user. */
</style>
        """
        .replace("__UI_POLISH_VERSION__", _UI_POLISH_VERSION)
        .replace("__BACKING_STUDIO_PANEL_CSS__", _studio_panels_css()),
        unsafe_allow_html=True,
    )


def _brand_title_html(title: str) -> str:
    if title.startswith("Daniel Cohen"):
        rest = title[len("Daniel Cohen") :].strip()
        return (
            '<span class="ui-brand-note" aria-hidden="true">🎵</span> '
            f'<span class="ui-brand-name">Daniel Cohen</span>'
            f"{html.escape(' ' + rest if rest else '')}"
        )
    return html.escape(title)


def render_studio_brand_header(
    *,
    title: str = "Daniel Cohen Music Practice Coach AI",
    tagline: str = (
        "AI-powered practice studio for songs, backing tracks, harmony, "
        "improvisation, recording, and instrument-specific coaching."
    ),
) -> None:
    """Compact branded title block — visible above workspace controls."""
    import streamlit as st

    st.markdown(
        f"""
<div class="ui-brand-header">
  <div class="ui-brand-row">
    <span class="ui-brand-icon" aria-hidden="true">♪</span>
    <div>
      <h1 class="ui-brand-main-title">{_brand_title_html(title)}</h1>
      <p class="ui-brand-tagline">{html.escape(tagline)}</p>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def open_control_section(letter: str, title: str, subtitle: str = "") -> None:
    """Open a labeled control group card (call close_control_section after widgets)."""
    import streamlit as st

    sub = (
        f'<p class="ui-ctrl-section-sub">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f'<div class="ui-ctrl-section">'
        f'<div class="ui-ctrl-section-head">'
        f'<span class="ui-ctrl-letter">{html.escape(letter)}</span>'
        f"<div><p class=\"ui-ctrl-section-title\">{html.escape(title)}</p>{sub}</div>"
        f"</div><div class=\"ui-ctrl-section-body\">",
        unsafe_allow_html=True,
    )


def close_control_section() -> None:
    import streamlit as st

    st.markdown("</div></div>", unsafe_allow_html=True)


def chart_key_mode_badge_html(session: dict) -> str:
    """Display-only written-key / concert charts badge HTML (reads session; no writes)."""
    try:
        from instrument_transposition import (
            chart_in_instrument_key,
            is_transposing_instrument,
            written_key_for_instrument,
        )
    except ImportError:
        return ""
    instrument = str(session.get("instrument") or "").strip()
    if not is_transposing_instrument(instrument):
        return ""
    concert_key = str(session.get("display_key") or "C").strip() or "C"
    written_on = bool(chart_in_instrument_key(session))
    if written_on:
        written_key = written_key_for_instrument(concert_key, instrument, session)
        label = "Written charts ON"
        detail = f"Charts in {written_key}"
        variant = "is-written-on"
        glyph = "📝"
    else:
        label = "Concert charts"
        detail = f"Charts in {concert_key}"
        variant = "is-concert"
        glyph = "🎼"
    return (
        f'<div class="ui-chart-key-mode-badge {variant}" role="status">'
        f'<span aria-hidden="true">{glyph}</span>'
        f"<strong>{html.escape(label)}</strong>"
        f'<span> · {html.escape(detail)}</span>'
        f"</div>"
    )


def active_song_status_strip_html(session: dict) -> str:
    """Read-only strip: instrument, practice key, optional chart-key badge."""
    instrument = str(session.get("instrument") or "Piano").strip() or "Piano"
    display_key = str(session.get("display_key") or "C").strip() or "C"
    chart_badge = chart_key_mode_badge_html(session)
    return (
        '<div class="ui-active-song-status-strip" role="status">'
        f'<span class="ui-active-song-status-pill is-instrument">'
        f"<strong>Instrument</strong> {html.escape(instrument)}</span>"
        f'<span class="ui-active-song-status-pill is-key">'
        f"<strong>Key</strong> {html.escape(display_key)}</span>"
        f"{chart_badge}"
        "</div>"
    )


def render_active_song_status_strip(st: Any) -> None:
    """Show instrument, key, and chart-key mode for the loaded session."""
    block = active_song_status_strip_html(st.session_state)
    if block:
        st.markdown(block, unsafe_allow_html=True)


def catalog_song_card_html(
    *,
    title: str,
    artist: str,
    genre: str,
    key_display: str,
    bpm: int | None,
    level: str = "",
    trusted: bool = False,
    active: bool = False,
) -> str:
    """Single browse card markup for Song Selection grid (display only)."""
    classes = ["ui-song-card"]
    if trusted:
        classes.append("trusted")
    if active:
        classes.append("active")
    bpm_val = int(bpm) if bpm else 100
    level_pill = (
        f'<span class="ui-song-pill level">{html.escape(level)}</span>'
        if str(level or "").strip()
        else ""
    )
    return (
        f'<div class="{" ".join(classes)}">'
        f'<p class="ui-song-card-title">{html.escape(title)}</p>'
        f'<p class="ui-song-card-artist">{html.escape(artist)}</p>'
        f'<div class="ui-song-card-meta">'
        f'<span class="ui-song-pill genre">{html.escape(genre)}</span>'
        f'<span class="ui-song-pill key">{html.escape(key_display)}</span>'
        f'<span class="ui-song-pill bpm">{bpm_val} BPM</span>'
        f"{level_pill}"
        f"</div></div>"
    )


def render_catalog_song_card_grid(
    st: Any,
    records: list[dict],
    *,
    active_pick_key: str,
    song_meta_fn: Any,
    pick_key_for_record_fn: Any,
    on_load_pick_key: Any,
    max_cards: int = 18,
) -> None:
    """Browse grid with Load buttons — display wiring only; callback owns state."""
    if not records:
        return
    shown = records[: max(1, int(max_cards))]
    st.markdown(
        '<p class="ui-song-card-grid-title">Browse matching songs</p>',
        unsafe_allow_html=True,
    )
    cols_per_row = 3
    for row_start in range(0, len(shown), cols_per_row):
        row_recs = shown[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_recs))
        for col_idx, (col, rec) in enumerate(zip(cols, row_recs)):
            pk = str(pick_key_for_record_fn(rec) or "").strip()
            if not pk:
                continue
            meta = song_meta_fn(rec) or {}
            with col:
                st.markdown(
                    '<div class="ui-song-card-cell">'
                    + catalog_song_card_html(
                        title=str(meta.get("title") or rec.get("title") or "Song"),
                        artist=str(meta.get("artist") or rec.get("artist") or ""),
                        genre=str(meta.get("genre") or rec.get("genre") or "Song"),
                        key_display=str(meta.get("key") or rec.get("key") or "C"),
                        bpm=meta.get("bpm") or rec.get("bpm"),
                        level=str(meta.get("difficulty") or rec.get("difficulty") or ""),
                        trusted=bool(meta.get("trusted")),
                        active=pk == active_pick_key,
                    )
                    + "</div>",
                    unsafe_allow_html=True,
                )
                btn_label = "Active" if pk == active_pick_key else "Load song"
                st.button(
                    btn_label,
                    key=f"catalog_card_load_{row_start}_{col_idx}",
                    use_container_width=True,
                    disabled=pk == active_pick_key,
                    on_click=on_load_pick_key,
                    kwargs={"pick_key": pk},
                )


def render_active_song_hub_open(st: Any, *, extra_class: str = "") -> None:
    """Open the Active Song command-center wrapper (pairs with hub_close)."""
    _cls = "ui-active-song-hub"
    if extra_class:
        _cls = f"{_cls} {html.escape(extra_class.strip())}"
    st.markdown(f'<div class="{_cls}">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="ui-active-song-hub-head">
  <span class="ui-active-song-hub-label">Current active song</span>
</div>
        """,
        unsafe_allow_html=True,
    )

def render_active_song_hub_hero(
    st: Any,
    *,
    title: str,
    artist: str,
    genre: str,
    key_display: str,
    bpm: int,
    groove: str,
    time_signature: str,
    section_count: int,
    emoji: str = "🎵",
    gradient: str = "linear-gradient(145deg, #0f172a 0%, #334155 55%, #475569 100%)",
    original_key: str | None = None,
    practice_key: str | None = None,
) -> None:
    """Large hero strip showing the currently loaded song at a glance."""
    _orig = str(original_key or key_display or "C")
    _practice = str(practice_key or key_display or _orig)
    key_row = active_song_key_row_html(_orig, _practice)
    pills = (
        f'<span class="ui-active-song-meta-pill"><strong>Genre</strong> {html.escape(genre)}</span>'
        f'<span class="ui-active-song-meta-pill"><strong>BPM</strong> {int(bpm)}</span>'
        f'<span class="ui-active-song-meta-pill"><strong>Time</strong> {html.escape(time_signature)}</span>'
        f'<span class="ui-active-song-meta-pill"><strong>Sections</strong> {int(section_count)}</span>'
        f'<span class="ui-active-song-meta-pill"><strong>Feel</strong> {html.escape(groove)}</span>'
    )
    st.markdown(
        f"""
<div class="ui-active-song-hero-strip">
  <div class="ui-active-song-hero-art" style="background:{html.escape(gradient)};">
    {html.escape(emoji)}<small>{html.escape(genre)}</small>
  </div>
  <div>
    <p class="ui-active-song-hero-title">{html.escape(title)}</p>
    <p class="ui-active-song-hero-artist">{html.escape(artist)}</p>
    {key_row}
    <div class="ui-active-song-meta-pills">{pills}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_active_song_hub_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_song_library_panel_header(
  st: Any,
  *,
  result_count: int,
  filtered_count: int | None = None,
) -> None:
    """Header block for the Song Selection library card (inside keyed container)."""
    shown = filtered_count if filtered_count is not None else result_count
    count_html = (
        f'<span class="ui-song-library-count">'
        f"{shown} song{'s' if shown != 1 else ''} in this list"
        f"</span>"
    )
    st.markdown(
        f"""
<div class="ui-song-library-head">
  <p class="ui-song-library-kicker">Browse Library</p>
  <p class="ui-song-library-sub">Browse, search, or filter songs below.</p>
  {count_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def render_song_library_selection_chip(
  st: Any,
  *,
  title: str,
  artist: str,
  genre: str,
) -> None:
    """Highlight the currently active song inside the library panel."""
    safe_title = html.escape(str(title or "Song"))
    safe_artist = html.escape(str(artist or ""))
    safe_genre = html.escape(str(genre or "Song"))
    artist_html = (
        f'<span class="ui-song-library-selected-meta">— {safe_artist}</span>'
        if safe_artist
        else ""
    )
    st.markdown(
        f"""
<div class="ui-song-library-selected" role="status" aria-live="polite">
  <span class="ui-song-library-selected-label">Now selected</span>
  <span class="ui-song-library-selected-title">{safe_title}{artist_html}</span>
  <span class="ui-song-library-genre-pill">{safe_genre}</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_song_library_field_label(st: Any, label: str, hint: str = "") -> None:
    """Compact field label for library panel columns (widgets use collapsed labels)."""
    hint_html = (
        f'<p class="ui-song-library-field-hint">{html.escape(hint)}</p>'
        if hint
        else ""
    )
    st.markdown(
        f'<p class="ui-song-library-field-label">{html.escape(label)}</p>{hint_html}',
        unsafe_allow_html=True,
    )


def render_backing_panel_shell_open(st: Any, variant: str) -> None:
    """Open inner card shell (pairs with shell_close) — reliable styling vs st-key alone."""
    v = html.escape(str(variant or "setup").strip().lower())
    st.markdown(
        f'<div class="ui-backing-panel-shell is-{v}" data-backing-panel="{v}">',
        unsafe_allow_html=True,
    )


def render_backing_panel_shell_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_backing_panel_header(
    st: Any,
    *,
    kicker: str,
    title: str,
    subtitle: str = "",
    badge_html: str = "",
    compact: bool = False,
) -> None:
    """Header for Backing Track setup / quick / transport cards."""
    badge_block = badge_html if badge_html else ""
    sub = (
        f'<p class="ui-backing-panel-sub">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    head_cls = " ui-backing-panel-head-compact" if compact else ""
    st.markdown(
        f'<div class="ui-backing-panel-head{head_cls}">'
        f'<div><span class="ui-backing-panel-kicker">{html.escape(kicker)}</span>'
        f'<p class="ui-backing-panel-title">{html.escape(title)}</p>{sub}</div>'
        f"{badge_block}</div>",
        unsafe_allow_html=True,
    )


def active_song_key_row_html(
    original_key: str,
    practice_key: str,
) -> str:
    """Compact Original vs Display/practice key row for Active Song cards."""
    orig = html.escape(str(original_key or "C").strip() or "C")
    practice = html.escape(str(practice_key or original_key or "C").strip() or orig)
    shifted = practice != orig
    shift_cls = " is-shifted" if shifted else ""
    return (
        f'<div class="ui-active-song-key-row{shift_cls}">'
        f'<span class="ui-active-song-key-chip original">'
        f'<span class="ui-active-song-key-label">Original key</span>'
        f'<span class="ui-active-song-key-value">{orig}</span></span>'
        f'<span class="ui-active-song-key-arrow" aria-hidden="true">→</span>'
        f'<span class="ui-active-song-key-chip practice">'
        f'<span class="ui-active-song-key-label">Practice / Concert Key</span>'
        f'<span class="ui-active-song-key-value">{practice}</span></span>'
        f"</div>"
    )


def render_active_song_key_row(
    st: Any,
    *,
    original_key: str,
    practice_key: str,
) -> None:
    st.markdown(
        active_song_key_row_html(original_key, practice_key),
        unsafe_allow_html=True,
    )


STUDIO_UI_RELEASE = "2026-06-22-ui-lite-no-song-dump-v1"

BACKING_STUDIO_UI_VERSION = "2026-05-29-studio-v11"
SONG_PICKER_UI_VERSION = "2026-05-28-picker-v3"
PRACTICE_SETUP_UI_VERSION = "2026-05-28-practice-v3"
CREATIVE_STUDIO_UI_VERSION = "2026-05-28-creative-v2"
CUSTOM_BUILDER_UI_VERSION = "2026-05-28-custom-v2"
UPLOAD_STUDIO_UI_VERSION = "2026-05-28-upload-v1"
MULTITRACK_STUDIO_UI_VERSION = "2026-05-28-multitrack-v3"

PRACTICE_QUICK_LINKS: list[str] = ["picker", "backing", "creative", "custom"]


def inject_backing_studio_styles(st: Any) -> None:
    """Re-inject backing studio CSS on the backing page (belt + suspenders with global theme)."""
    st.markdown(
        f"""
<style data-backing-studio-ui="{BACKING_STUDIO_UI_VERSION}">
{_backing_studio_all_css()}
</style>
<script>try{{document.body.dataset.backingStudioUi="{BACKING_STUDIO_UI_VERSION}";document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";document.body.classList.remove("practice-page");document.body.classList.add("backing-studio-page");}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_song_picker_page_styles(st: Any) -> None:
    """Marker + layout helpers for Song Selection (confirms deploy revision)."""
    st.markdown(
        f"""
<style data-song-picker-ui="{SONG_PICKER_UI_VERSION}">
/* Song Selection — no separate footer metadata block (genre/levels live on Active Song card) */
body[data-song-picker-ui] .ui-active-song-card .ui-active-song-facts dt:first-child {{ color: #4f46e5; }}
</style>
<script>try{{
document.body.dataset.songPickerUi="{SONG_PICKER_UI_VERSION}";
document.body.dataset.studioPage = "picker";
["custom-builder-page","upload-studio-page","backing-studio-page","multitrack-studio-page","practice-page"].forEach(function(c) {{
  document.body.classList.remove(c);
}});
}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_practice_page_styles(st: Any) -> None:
    """Re-inject Practice Control Center CSS on the Practice page."""
    st.markdown(
        f"""
<style data-practice-setup-ui="{PRACTICE_SETUP_UI_VERSION}">
{_practice_control_panel_css()}
</style>
<script>try{{document.body.dataset.practiceSetupUi="{PRACTICE_SETUP_UI_VERSION}";document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";document.body.classList.remove("backing-studio-page");document.body.classList.add("practice-page");}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def practice_setup_summary_text(
    *,
    instrument: str,
    level: str,
    focus: str,
    groove: str,
    minutes: int,
) -> str:
    """One-line session summary for the practice setup badge."""
    parts = [
        (instrument or "Piano").strip(),
        (level or "Intermediate").strip(),
        (focus or "General").strip(),
        (groove or "Auto").strip(),
        f"{max(10, int(minutes or 30))} min",
    ]
    return " · ".join(html.escape(p) for p in parts if p)


def practice_setup_summary_badge_html(summary: str) -> str:
    text = summary or ""
    return (
        f'<span class="ui-practice-summary-badge" title="Current practice session setup">'
        f"<strong>Session</strong> {text}</span>"
    )


def inject_creative_studio_styles(st: Any) -> None:
    """Inject Creative Lab studio CSS."""
    st.markdown(
        f"""
<style data-creative-studio-ui="{CREATIVE_STUDIO_UI_VERSION}">
{_creative_studio_panel_css()}
</style>
<script>try{{document.body.dataset.creativeStudioUi="{CREATIVE_STUDIO_UI_VERSION}";document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_custom_builder_styles(st: Any) -> None:
    """Inject Custom Song Builder panel CSS."""
    st.markdown(
        f"""
<style data-custom-builder-ui="{CUSTOM_BUILDER_UI_VERSION}">
{_custom_builder_panel_css()}
</style>
<script>try{{
document.body.dataset.customBuilderUi="{CUSTOM_BUILDER_UI_VERSION}";
document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";
}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_upload_studio_styles(st: Any) -> None:
    """Inject Audio Upload Studio CSS on the analysis page."""
    st.markdown(
        f"""
<style data-upload-studio-ui="{UPLOAD_STUDIO_UI_VERSION}">
{_upload_studio_panel_css()}
</style>
<script>try{{
document.body.dataset.uploadStudioUi="{UPLOAD_STUDIO_UI_VERSION}";
document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";
document.body.classList.add("upload-studio-page");
}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_multitrack_studio_styles(st: Any) -> None:
    """Inject Multitrack Studio CSS on the multitrack page."""
    st.markdown(
        f"""
<style data-multitrack-studio-ui="{MULTITRACK_STUDIO_UI_VERSION}">
{_multitrack_studio_panel_css()}
</style>
<script>try{{
document.body.dataset.multitrackStudioUi="{MULTITRACK_STUDIO_UI_VERSION}";
document.body.dataset.studioUiRelease="{STUDIO_UI_RELEASE}";
document.body.classList.add("multitrack-studio-page");
}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def render_upload_studio_panel_header(
    st: Any,
    *,
    song_title: str,
    artist: str = "",
) -> None:
    """Context only — page title is in the script header above."""
    _ = song_title, artist


def upload_session_context_html(
    *,
    song_title: str,
    artist: str,
    display_key: str,
    instrument: str,
) -> str:
    return (
        f'<div class="ui-upload-session-card" data-upload-session-ui="{UPLOAD_STUDIO_UI_VERSION}">'
        f"<strong>{html.escape(song_title or 'Your song')}</strong>"
        f"{(' · ' + html.escape(artist.strip())) if (artist or '').strip() else ''}"
        f" · Key <strong>{html.escape(display_key or 'C')}</strong>"
        f" · {html.escape(instrument or 'Instrument')}</div>"
    )


def upload_format_chips_html() -> str:
    formats = ("WAV", "MP3", "M4A", "MP4", "MOV", "OGG", "FLAC")
    chips = "".join(
        f'<span class="ui-upload-format-chip">{html.escape(fmt)}</span>' for fmt in formats
    )
    return f'<div class="ui-upload-format-row">{chips}</div>'


def render_multitrack_studio_panel_header(st: Any, *, song_title: str) -> None:
    """Context only — page title is in the script header above."""
    _ = song_title


def multitrack_session_context_html(
    *,
    song_title: str,
    scope_label: str,
    bpm: int,
    time_signature: str,
    layer_count: int,
) -> str:
    return (
        f'<div class="ui-multitrack-session-card" data-mt-session-ui="{MULTITRACK_STUDIO_UI_VERSION}">'
        f"<strong>{html.escape(song_title or 'Song')}</strong> · "
        f"{html.escape(scope_label or 'session')} · "
        f"<strong>{int(bpm)}</strong> BPM · {html.escape(time_signature or '4/4')} · "
        f"<strong>{int(layer_count)}</strong> layer(s) saved</div>"
    )


def multitrack_layer_badge_html(*, ready: bool) -> str:
    if ready:
        return '<span class="ui-mt-layer-badge ready" title="Recorded or uploaded audio saved for this slot">● Has audio</span>'
    return '<span class="ui-mt-layer-badge empty" title="No recorded or uploaded audio yet">○ Empty</span>'


def render_multitrack_session_setup_header(st: Any) -> None:
    st.markdown(
        f"""
<div class="ui-mt-session-setup-head" data-mt-setup-ui="{MULTITRACK_STUDIO_UI_VERSION}">
  <span class="ui-mt-session-setup-kicker">Step 1</span>
  <p class="ui-mt-session-setup-title">Session Setup</p>
  <p class="ui-mt-session-setup-sub">Song, tempo, range, and recording options in one compact panel.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_multitrack_session_context_strip(
    st: Any,
    *,
    song_title: str,
    original_key: str,
    practice_key: str,
    bpm: int,
    meter: str,
    groove: str,
    scope_label: str,
) -> None:
    _song = html.escape(str(song_title or "Active song").strip())
    _orig = html.escape(str(original_key or "C").strip() or "C")
    _practice = html.escape(str(practice_key or original_key or "C").strip() or "C")
    _meter = html.escape(str(meter or "4/4").strip() or "4/4")
    _groove = html.escape(str(groove or "Auto").strip() or "Auto")
    _scope = html.escape(str(scope_label or "full song").strip())
    st.markdown(
        f'<div class="ui-mt-session-context" role="group" aria-label="Session context">'
        f'<span class="ui-mt-ctx-badge song" title="Active song">'
        f'<span class="ui-mt-ctx-ico">🎵</span> <strong>{_song}</strong></span>'
        f'<span class="ui-mt-ctx-badge key-orig" title="Original key">'
        f'<span class="ui-mt-ctx-ico">🎹</span> Orig <strong>{_orig}</strong></span>'
        f'<span class="ui-mt-ctx-badge key-practice" title="Practice key">'
        f'<span class="ui-mt-ctx-ico">🎼</span> Practice <strong>{_practice}</strong></span>'
        f'<span class="ui-mt-ctx-badge bpm" title="Session tempo">'
        f'<span class="ui-mt-ctx-ico">⏱</span> <strong>{int(bpm)}</strong> BPM</span>'
        f'<span class="ui-mt-ctx-badge meter" title="Time signature">'
        f'<span class="ui-mt-ctx-ico">🥁</span> <strong>{_meter}</strong></span>'
        f'<span class="ui-mt-ctx-badge groove" title="Groove feel">'
        f'<span class="ui-mt-ctx-ico">✨</span> {_groove}</span>'
        f'<span class="ui-mt-ctx-badge scope" title="Record range">'
        f'<span class="ui-mt-ctx-ico">🔁</span> {_scope}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_multitrack_setup_section_open(st: Any, title: str, *, icon: str = "") -> None:
    _icon = (
        f'<span class="ui-mt-setup-section-icon" aria-hidden="true">{html.escape(icon)}</span>'
        if icon
        else ""
    )
    st.markdown(
        f'<div class="ui-mt-setup-section">'
        f'<p class="ui-mt-setup-section-title">{_icon}{html.escape(title)}</p>',
        unsafe_allow_html=True,
    )


def render_multitrack_setup_section_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_multitrack_field_label(st: Any, label: str) -> None:
    st.markdown(
        f'<p class="ui-mt-field-label">{html.escape(label)}</p>',
        unsafe_allow_html=True,
    )


def inject_studio_ui_release_marker(st: Any, *, page: str) -> None:
    """Hidden deploy marker — confirms Streamlit is serving the latest UI bundle."""
    page_slug = html.escape(str(page or "").strip())
    st.markdown(
        f"""
<div id="studio-ui-release-marker" data-studio-ui-release="{html.escape(STUDIO_UI_RELEASE)}"
     data-studio-page="{page_slug}" style="display:none!important" aria-hidden="true"></div>
<script>try{{
const page = "{page_slug}";
document.body.dataset.studioUiRelease = "{STUDIO_UI_RELEASE}";
document.body.dataset.studioPage = page;
["custom-builder-page","upload-studio-page","backing-studio-page","multitrack-studio-page","practice-page"].forEach(function(c) {{
  document.body.classList.remove(c);
}});
const pageClass = {{
  custom: "custom-builder-page",
  upload: "upload-studio-page",
  backing: "backing-studio-page",
  multitrack: "multitrack-studio-page",
}}[page];
if (pageClass) document.body.classList.add(pageClass);
}}catch(e){{}}</script>
        """,
        unsafe_allow_html=True,
    )


def inject_studio_page_marker_sync(st: Any, *, page: str) -> None:
    """Unified studio page marker — sets data-studio-page and page body classes."""
    inject_studio_ui_release_marker(st, page=page)


def studio_meta_badge(
    label: str,
    value: str,
    *,
    tone: str = "neutral",
    icon: str = "",
) -> str:
    ico = (
        f'<span class="ui-studio-meta-badge-ico" aria-hidden="true">{html.escape(icon)}</span>'
        if icon
        else ""
    )
    return (
        f'<span class="ui-studio-meta-badge tone-{html.escape(tone)}">'
        f"{ico}"
        f'<span class="ui-studio-meta-badge-label">{html.escape(label)}</span>'
        f'<span class="ui-studio-meta-badge-value">{html.escape(value)}</span>'
        f"</span>"
    )


def studio_song_meta_badges_html(
    *,
    original_key: str = "",
    display_key: str = "",
    written_key: str = "",
    written_key_label: str = "Written Key",
    charts_key: str = "",
    bpm: int | None = None,
    meter: str = "",
    style: str = "",
    source: str = "",
) -> str:
    """Professional pill badges for CPL preview and Songs page cards."""
    badges: list[str] = []
    if original_key:
        badges.append(studio_meta_badge("Original Key", original_key, tone="key", icon="🎹"))
    if display_key:
        badges.append(
            studio_meta_badge("Practice / Concert Key", display_key, tone="display", icon="🎼")
        )
    if written_key and written_key != display_key:
        badges.append(
            studio_meta_badge(written_key_label, written_key, tone="written", icon="🎷")
        )
    if charts_key and charts_key != display_key:
        badges.append(
            studio_meta_badge("Charts shown in", charts_key, tone="written", icon="📊")
        )
    if bpm is not None:
        badges.append(studio_meta_badge("BPM", str(int(bpm)), tone="tempo", icon="⏱"))
    if meter:
        badges.append(studio_meta_badge("Meter", meter, tone="meter", icon="🥁"))
    if style:
        badges.append(studio_meta_badge("Style", style, tone="style", icon="✨"))
    if source:
        badges.append(studio_meta_badge("Source", source, tone="source", icon="📀"))
    if not badges:
        return ""
    return f'<div class="ui-studio-meta-badges">{"".join(badges)}</div>'


def custom_builder_step_open_html(step: int, title: str, subtitle: str = "") -> str:
    sub = (
        f'<p class="ui-custom-step-sub">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    return (
        f'<div class="ui-custom-step-card" data-custom-step="{int(step)}">'
        f'<div class="ui-custom-step-head">'
        f'<span class="ui-custom-step-num">{int(step)}</span>'
        f"<div><p class=\"ui-custom-step-title\">{html.escape(title)}</p>{sub}</div>"
        f"</div>"
    )


def custom_builder_step_close_html() -> str:
    return "</div>"


def custom_song_preview_card_html(
    *,
    title: str,
    artist: str,
    key_label: str,
    bpm: int,
    time_signature: str,
    style: str,
    sections_line: str,
    has_chords: bool,
    is_active: bool,
    display_key_label: str = "",
) -> str:
    artist_bit = (
        f" · {html.escape(artist.strip())}" if (artist or "").strip() else ""
    )
    badges = studio_song_meta_badges_html(
        bpm=int(bpm),
        meter=str(time_signature or "4/4"),
        style=str(style or "Pop"),
        source="Custom Progression",
    )
    key_line = (
        f'<p class="ui-custom-preview-key-row">'
        f"Original key <strong>{html.escape(key_label)}</strong>"
        f" · Practice / Concert Key <strong>{html.escape(display_key_label or key_label)}</strong>"
        f"</p>"
    )
    body = (
        f"{key_line}{badges}"
        f'<p class="ui-custom-preview-meta">{html.escape(sections_line)}</p>'
        if has_chords
        else (
            f"{key_line}{badges}"
            f'<p class="ui-custom-preview-empty">Add chords in step 2 to see your song structure here.</p>'
        )
    )
    active_pill = (
        '<span class="ui-custom-active-pill">Active song</span>'
        if is_active
        else ""
    )
    return (
        f'<div class="ui-custom-preview-card" data-custom-preview-ui="{CUSTOM_BUILDER_UI_VERSION}">'
        f'<div class="ui-custom-preview-kicker">Preview</div>'
        f'<p class="ui-custom-preview-title">{html.escape(title or "Untitled")}{artist_bit}</p>'
        f"{body}{active_pill}</div>"
    )


def render_custom_builder_panel_header(st: Any, *, working_title: str) -> None:
    title = (working_title or "My Progression").strip() or "My Progression"
    st.markdown(
        f"""
<div class="ui-custom-builder-head" data-custom-builder-ui="{CUSTOM_BUILDER_UI_VERSION}">
  <span class="ui-custom-builder-kicker">Custom song builder</span>
  <p class="ui-custom-builder-title">Create Your Own Song</p>
  <p class="ui-custom-builder-sub">Build a chord chart, set it as your active song, then practice with backing or karaoke.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_creative_studio_panel_header(
    st: Any,
    *,
    instrument: str,
    level: str,
    song_title: str,
) -> None:
    """Compact session context — page title lives in the script header above."""
    st.markdown(
        f"""
<p class="ui-creative-studio-sub ui-creative-studio-sub--compact" data-creative-panel-ui="{CREATIVE_STUDIO_UI_VERSION}">
  Working from <strong>{html.escape(song_title or "your song")}</strong>
  · {html.escape(instrument or "Instrument")} · {html.escape(level or "Intermediate")}
</p>
        """,
        unsafe_allow_html=True,
    )


def render_creative_song_context_card(
    st: Any,
    *,
    title: str,
    artist: str,
    display_key: str,
    chord_count: int,
    source_label: str,
    variant: str = "active",
) -> None:
    cls = "custom" if variant == "custom" else "active"
    st.markdown(
        f'<div class="ui-creative-song-card {cls}">'
        f'<p class="ui-creative-song-kicker">{html.escape(source_label)}</p>'
        f'<p class="ui-creative-song-title">{html.escape(title)}'
        f' <span style="font-weight:600;color:#64748b;">— {html.escape(artist)}</span></p>'
        f'<div class="ui-creative-song-meta">'
        f'<span>Key {html.escape(display_key)}</span>'
        f"<span>{int(chord_count)} chords</span>"
        f'<span>{html.escape(source_label)}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_practice_control_panel_header(st: Any) -> None:
    """Compact hint for the Practice Control Center panel (page title lives in script header)."""
    st.markdown(
        f"""
<div class="ui-practice-control-head ui-practice-control-head--compact" data-practice-panel-ui="{PRACTICE_SETUP_UI_VERSION}">
  <p class="ui-practice-control-sub">Instrument, level, and focus sync with the sidebar. Groove and length shape coaching below.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_backing_studio_deck_header(st: Any) -> None:
    """Compact workflow steps for the backing deck (page title lives in script header)."""
    st.markdown(
        """
<div class="ui-backing-studio-deck-head ui-backing-studio-deck-head--compact">
  <div class="ui-backing-studio-steps" aria-label="Workflow steps">
    <span class="ui-backing-studio-step">1 Range</span>
    <span class="ui-backing-studio-step">2 Tempo &amp; play</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_backing_transport_feedback(
    st: Any,
    *,
    message: str,
    state: str = "idle",
) -> None:
    """Visible playback status line under transport controls."""
    msg = html.escape(str(message or "").strip())
    if not msg:
        return
    cls = "ui-backing-transport-feedback"
    state_norm = str(state or "idle").strip().lower()
    if state_norm in {"ready", "active", "warn", "stopped"}:
        cls += f" is-{state_norm}"
    st.markdown(f'<p class="{cls}" role="status">{msg}</p>', unsafe_allow_html=True)


def render_backing_setup_group_open(st: Any, title: str, hint: str = "") -> None:
    """Grouped block inside Playback Setup (range / feel / key)."""
    hint_html = (
        f'<p class="ui-backing-setup-group-hint">{html.escape(hint)}</p>' if hint else ""
    )
    st.markdown(
        f'<div class="ui-backing-setup-group">'
        f'<p class="ui-backing-setup-group-title">{html.escape(title)}</p>'
        f"{hint_html}",
        unsafe_allow_html=True,
    )


def render_backing_setup_group_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_backing_setup_section_open(st: Any, title: str, *, icon: str = "") -> None:
    """Sub-section inside the unified Playback Setup card."""
    _icon = f'<span class="ui-backing-setup-section-icon" aria-hidden="true">{html.escape(icon)}</span>' if icon else ""
    st.markdown(
        f'<div class="ui-backing-setup-section">'
        f'<p class="ui-backing-setup-section-title">{_icon}{html.escape(title)}</p>',
        unsafe_allow_html=True,
    )


def render_backing_setup_section_close(st: Any) -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_backing_setup_context_strip(
    st: Any,
    *,
    original_key: str,
    practice_key: str,
    meter: str,
    groove: str,
    range_summary: str,
    default_bpm: int,
    written_key: str = "",
    source_kind: str = "",
) -> None:
    """At-a-glance playback context row (keys, meter, feel, range)."""
    _orig = html.escape(str(original_key or "C").strip() or "C")
    _practice = html.escape(str(practice_key or original_key or "C").strip() or "C")
    _written = html.escape(str(written_key or "").strip())
    _orig_title = (
        "Custom progression original key"
        if str(source_kind or "").strip().lower() == "custom"
        else "Original / home key"
    )
    _meter = html.escape(str(meter or "4/4").strip() or "4/4")
    _groove = html.escape(str(groove or "Auto").strip() or "Auto")
    _range = html.escape(str(range_summary or "Full song ×2").strip())
    written_badge = ""
    if _written and _written != _practice:
        written_badge = (
            f'<span class="ui-backing-ctx-badge key-written" title="Written chart key">'
            f'<span class="ui-backing-ctx-ico">🎷</span> Written <strong>{_written}</strong></span>'
        )
    st.markdown(
        f'<div class="ui-backing-setup-context" role="group" aria-label="Playback context">'
        f'<span class="ui-backing-ctx-badge key-orig" title="{html.escape(_orig_title)}">'
        f'<span class="ui-backing-ctx-ico">🎹</span> Original Key <strong>{_orig}</strong></span>'
        f'<span class="ui-backing-ctx-badge key-practice" title="Practice / Concert Key">'
        f'<span class="ui-backing-ctx-ico">🎼</span> Practice / Concert Key <strong>{_practice}</strong></span>'
        f"{written_badge}"
        f'<span class="ui-backing-ctx-badge meter" title="Time signature">'
        f'<span class="ui-backing-ctx-ico">🥁</span> <strong>{_meter}</strong></span>'
        f'<span class="ui-backing-ctx-badge groove" title="Rhythm feel">'
        f'<span class="ui-backing-ctx-ico">✨</span> <strong>{_groove}</strong></span>'
        f'<span class="ui-backing-ctx-badge range" title="Playback range &amp; loops">'
        f'<span class="ui-backing-ctx-ico">🔁</span> {_range}</span>'
        f'<span class="ui-backing-ctx-badge bpm" title="Song default tempo — adjust in Quick Playback">'
        f'<span class="ui-backing-ctx-ico">⏱</span> Default <strong>{int(default_bpm)}</strong> BPM</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_backing_field_label(st: Any, label: str, hint: str = "") -> None:
    """Field label inside backing playback cards."""
    hint_html = (
        f'<p class="ui-backing-field-hint">{html.escape(hint)}</p>' if hint else ""
    )
    st.markdown(
        f'<p class="ui-backing-field-label">{html.escape(label)}</p>{hint_html}',
        unsafe_allow_html=True,
    )


def backing_scope_loop_summary_text(
    scope: str,
    *,
    single_section: str = "",
    multi_sections: list[str] | None = None,
    loops: int = 2,
) -> str:
    """Human-readable loop summary for the scope control badge."""
    loops = max(1, int(loops or 1))
    scope = (scope or "Full song").strip()
    norm = scope
    try:
        from backing_track_state import normalize_backing_scope

        norm = normalize_backing_scope(scope)
    except ImportError:
        if "single" in scope.lower() or "multiple" in scope.lower() or "selected" in scope.lower():
            norm = "Selected sections"
    if norm == "Selected sections":
        parts = [s for s in (multi_sections or []) if s]
        if not parts and single_section:
            parts = [single_section.strip()]
        if not parts:
            return f"Selected sections ×{loops}"
        if len(parts) <= 2:
            joined = " + ".join(parts)
        else:
            joined = f"{parts[0]} + {parts[1]} +{len(parts) - 2}"
        return f"Looping: {joined} ×{loops}"
    if scope == "Single section":
        sec = (single_section or "Section").strip() or "Section"
        return f"Looping: {sec} ×{loops}"
    if scope == "Multiple selected sections":
        parts = [s for s in (multi_sections or []) if s]
        if not parts:
            return f"Custom sections ×{loops}"
        if len(parts) <= 2:
            joined = " + ".join(parts)
        else:
            joined = f"{parts[0]} + {parts[1]} +{len(parts) - 2}"
        return f"Looping: {joined} ×{loops}"
    return f"Full song ×{loops}"


def backing_scope_loop_summary_badge_html(summary: str) -> str:
    text = html.escape((summary or "Full song ×2").strip())
    return (
        f'<span class="ui-backing-scope-summary-badge" title="Current playback range">'
        f"<strong>Range</strong> {text}</span>"
    )


def render_backing_scope_panel_header(st: Any, *, summary_html: str = "") -> None:
    """Title row for the Scope & Loop Control sub-panel."""
    badge = summary_html or ""
    st.markdown(
        f'<div class="ui-backing-scope-panel-head" data-scope-panel-ui="{BACKING_STUDIO_UI_VERSION}">'
        f'<span class="ui-backing-panel-kicker" style="color:#4f46e5;">Playback range</span>'
        f"<div><p class=\"ui-backing-scope-panel-title\">Scope &amp; Loop Control</p>"
        f'<p class="ui-backing-scope-panel-sub">Choose what to generate and how many times to loop it.</p></div>'
        f"{badge}</div>",
        unsafe_allow_html=True,
    )


def render_backing_transport_status(
    st: Any,
    *,
    ready: bool,
    bpm: int,
    groove: str,
    meter: str,
    scope_label: str,
) -> None:
    """Mini transport readout strip (Quick Playback card)."""
    state_cls = "ready" if ready else "idle"
    state_label = "Ready to play" if ready else "Not generated"
    st.markdown(
        f'<div class="ui-backing-transport-strip {state_cls}">'
        f'<span class="ui-backing-transport-dot" aria-hidden="true"></span>'
        f'<span class="ui-backing-transport-state">{html.escape(state_label)}</span>'
        f'<span class="ui-backing-transport-meta">{int(bpm)} BPM</span>'
        f'<span class="ui-backing-transport-meta">{html.escape(groove)}</span>'
        f'<span class="ui-backing-transport-meta">{html.escape(meter)}</span>'
        f'<span class="ui-backing-transport-meta scope">{html.escape(scope_label)}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def app_hero(title: str, subtitle: str) -> None:
    """Legacy hero — delegates to compact brand header when title matches studio app."""
    import streamlit as st

    if "Daniel Cohen" in title and "Music Practice Coach" in title:
        render_studio_brand_header(
            title=title.strip(),
            tagline=subtitle.split("\n")[0] if subtitle else "",
        )
        return
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


def sidebar_section(title: str, *, icon: str = "", tone: str = "") -> None:
    import streamlit as st

    label = f"{icon} {title}".strip() if icon else title
    tone_cls = f" tone-{tone}" if tone else ""
    st.sidebar.markdown(
        f'<p class="ui-sb-section{tone_cls}">{html.escape(label)}</p>',
        unsafe_allow_html=True,
    )


def sidebar_source_banner(source_kind: str, detail: str) -> None:
    import streamlit as st

    st.sidebar.markdown(
        f'<div class="ui-source-banner">'
        f'<div class="ui-source-kind">{html.escape(source_kind)}</div>'
        f'<div class="ui-source-detail">{html.escape(detail)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def sidebar_goto_song_selection(*, on_navigate: Any) -> None:
    """Small sidebar shortcut to Song Selection (preserves global session state)."""
    import streamlit as st

    st.sidebar.button(
        nav_icon_button_label("picker"),
        key="sidebar_goto_song_selection",
        use_container_width=True,
        help="Jump to Song Selection — keeps instrument, level, key, and active song settings.",
        on_click=on_navigate,
    )


STUDIO_PAGE_META: dict[str, dict[str, str]] = {
    "practice": {"label": "Practice", "icon": "🎯", "nav_class": "practice"},
    "picker": {"label": "Song Selection", "icon": "🎼", "nav_class": "picker"},
    "backing": {"label": "Backing Track", "icon": "🎧", "nav_class": "backing"},
    "custom": {"label": "Custom Progression", "icon": "✏️", "nav_class": "custom"},
    "composer": {"label": "Composition Studio", "icon": "🎹", "nav_class": "composer"},
    "creative": {"label": "Creative Lab", "icon": "🎨", "nav_class": "creative"},
    "multitrack": {"label": "Multitrack", "icon": "🎚️", "nav_class": "multitrack"},
    "analysis": {"label": "Upload Analysis", "icon": "🎙️", "nav_class": "analysis"},
    "log": {"label": "Practice Log", "icon": "📓", "nav_class": "log"},
    "openai": {"label": "OpenAI", "icon": "✨", "nav_class": "openai"},
}

OPENAI_PAGE_ID = "openai"

STUDIO_PAGES: list[tuple[str, str]] = [
    (page_id, f"{meta['icon']} {meta['label']}")
    for page_id, meta in STUDIO_PAGE_META.items()
]

# Top quick nav — core workspaces only (OpenAI lives in the sidebar when configured).
TOP_NAV_ITEMS: list[tuple[str, str]] = [
    (page_id, label) for page_id, label in STUDIO_PAGES if page_id != OPENAI_PAGE_ID
]
TOP_NAV_PAGE_IDS: list[str] = [page_id for page_id, _label in TOP_NAV_ITEMS]

# Single stable quick-nav widget tree (do not vary keys per page or deploy).
STUDIO_QUICK_NAV_PANEL_KEY = "studio_quick_nav_panel"
STUDIO_QUICK_NAV_KEY_PREFIX = "studio_quick_nav"
_STUDIO_QUICK_NAV_OPEN_LABEL = "Open"

# Diagnostic fallback — plain Streamlit buttons only (?simple_nav=1 or dev toggle).
USE_SIMPLE_MUSIC_NAV_KEY = "use_simple_music_nav"
STUDIO_SIMPLE_NAV_KEY_PREFIX = "studio_simple_nav"
QUICK_NAV_DIAG_KEY = "_quick_nav_render_diag"
_QUICK_NAV_RENDERED_THIS_EXEC = False
_MUSIC_INSIGHT_RENDERED_THIS_EXEC = False
SIMPLE_NAV_PAGE_IDS: list[str] = [
    "practice",
    "picker",
    "backing",
    "custom",
    "composer",
    "creative",
    "analysis",
    "multitrack",
    "log",
]

QUICK_NAV_ROW_PRIMARY: list[str] = ["practice", "picker", "backing", "custom"]
QUICK_NAV_ROW_SECONDARY: list[str] = ["composer", "creative", "analysis", "multitrack", "log"]


def sidebar_studio_page_items(*, ai_enabled: bool) -> list[tuple[str, str]]:
    """Sidebar page list — includes OpenAI only when the API key is configured."""
    items = list(TOP_NAV_ITEMS)
    if ai_enabled:
        meta = STUDIO_PAGE_META[OPENAI_PAGE_ID]
        items.append((OPENAI_PAGE_ID, f"{meta['icon']} {meta['label']}"))
    return items
STUDIO_PAGE_NAV_KEY = "studio_page_nav"
SIDEBAR_NAV_COLLAPSED_KEY = "studio_sidebar_nav_collapsed"


def sidebar_nav_is_collapsed(session_state: dict) -> bool:
    """Default True — Music App page list starts collapsed on first load."""
    if SIDEBAR_NAV_COLLAPSED_KEY not in session_state:
        return True
    return bool(session_state[SIDEBAR_NAV_COLLAPSED_KEY])


def ensure_sidebar_nav_defaults(session_state: dict) -> bool:
    """Initialize Music App sidebar page nav as collapsed when the key is unset."""
    if SIDEBAR_NAV_COLLAPSED_KEY not in session_state:
        session_state[SIDEBAR_NAV_COLLAPSED_KEY] = True
    return sidebar_nav_is_collapsed(session_state)


def sync_sidebar_nav_body_dataset(session_state: dict, st_module: Any) -> None:
    """Drive layout CSS in the main area (Music App only — call from streamlit_music_practice_app)."""
    collapsed = sidebar_nav_is_collapsed(session_state)
    flag = "true" if collapsed else "false"
    st_module.markdown(
        f"""
        <script>
          try {{
            document.body.dataset.sidebarNavCollapsed = "{flag}";
          }} catch (e) {{}}
        </script>
        """,
        unsafe_allow_html=True,
    )


def navigate_studio_page(session_state: Any, page_id: str) -> bool:
    from studio_nav_history import navigate_studio_page as _nav

    changed = _nav(session_state, page_id)
    if changed:
        try:
            from studio_nav_state import mark_studio_nav_local_edit

            mark_studio_nav_local_edit(session_state)
        except ImportError:
            pass
    return changed


_NAV_COMPACT_TITLE: dict[str, str] = {
    "practice": "Practice",
    "picker": "Songs",
    "backing": "Backing",
    "custom": "Custom",
    "composer": "Compose",
    "creative": "Creative",
    "multitrack": "Multitrack",
    "analysis": "Upload",
    "log": "Log",
    "openai": "OpenAI",
}

_NAV_COMPACT_ICON: dict[str, str] = {
    "practice": "🎯",
    "picker": "🎼",
    "backing": "🎧",
    "custom": "✏️",
    "composer": "🎹",
    "creative": "🎨",
    "multitrack": "🎚️",
    "analysis": "🎙️",
    "log": "📓",
    "openai": "✨",
}


def nav_compact_button_label(page_id: str) -> str:
    """Short script label for quick-nav art faces."""
    return _NAV_COMPACT_TITLE.get(
        page_id, STUDIO_PAGE_META.get(page_id, {}).get("label", page_id)
    )


def nav_icon_button_label(page_id: str) -> str:
    """Icon + compact label for standard Streamlit buttons."""
    icon = _nav_compact_icon(page_id)
    label = nav_compact_button_label(page_id)
    return f"{icon} {label}" if icon else label


def _nav_compact_icon(page_id: str) -> str:
    return _NAV_COMPACT_ICON.get(
        page_id, STUDIO_PAGE_META.get(page_id, {}).get("icon", "")
    )


def nav_two_line_label(page_id: str) -> str:
    """Two-line labels — same structure on every segment (icon + title)."""
    meta = STUDIO_PAGE_META.get(page_id, {})
    icon = meta.get("icon", "")
    title = _NAV_COMPACT_TITLE.get(page_id, meta.get("label", page_id))
    return f"{icon}\n{title}" if icon else title


def init_simple_music_nav_from_query(st: Any) -> None:
    """Enable plain nav diagnostic mode via ?simple_nav=1 (persists in session)."""
    import os

    try:
        if os.environ.get("MUSIC_SIMPLE_NAV", "").strip().lower() in {"1", "true", "yes", "on"}:
            st.session_state[USE_SIMPLE_MUSIC_NAV_KEY] = True
            return
        raw = st.query_params.get("simple_nav")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        if str(raw or "").strip().lower() in {"1", "true", "yes", "on"}:
            try:
                from music_dev_ui import music_dev_mode_enabled

                if music_dev_mode_enabled(st=st):
                    st.session_state[USE_SIMPLE_MUSIC_NAV_KEY] = True
            except ImportError:
                st.session_state[USE_SIMPLE_MUSIC_NAV_KEY] = True
        elif str(raw or "").strip().lower() in {"0", "false", "no", "off"}:
            st.session_state[USE_SIMPLE_MUSIC_NAV_KEY] = False
    except Exception:
        pass


def use_simple_music_nav(session_state: Any) -> bool:
    """Plain Streamlit quick nav — diagnostic fallback (?simple_nav=1)."""
    return bool(session_state.get(USE_SIMPLE_MUSIC_NAV_KEY))


def _studio_quick_nav_button_key(page_id: str) -> str:
    return f"{STUDIO_QUICK_NAV_KEY_PREFIX}_btn_{page_id}"


def _studio_simple_nav_button_key(page_id: str) -> str:
    return f"{STUDIO_SIMPLE_NAV_KEY_PREFIX}_btn_{page_id}"


def _resolve_quick_nav_current_page(session_state: Any, current_page: str) -> str:
    """Authoritative active page for quick-nav highlighting."""
    studio = str(session_state.get("studio_page") or current_page or "practice")
    if studio in TOP_NAV_PAGE_IDS:
        return studio
    return current_page if current_page in TOP_NAV_PAGE_IDS else "practice"


def _nav_art_face_html(page_id: str, *, active: bool) -> str:
    """Visible nav face: emoji icon + Caveat script word (pre-regression look)."""
    icon = html.escape(_nav_compact_icon(page_id))
    title = html.escape(nav_compact_button_label(page_id))
    active_cls = " is-active" if active else ""
    return (
        f'<div class="ui-nav-art-face{active_cls}" data-nav-page="{html.escape(page_id)}">'
        f'<span class="ui-nav-icon" aria-hidden="true">{icon}</span>'
        f'<span class="ui-nav-script-label">{title}</span>'
        f"</div>"
    )


def _simple_nav_css() -> str:
    """Diagnostic nav — active red button only (no art/HTML styling)."""
    return """
[class*="st-key-studio_simple_nav_btn_"] .stButton > button[kind="primary"],
[class*="st-key-studio_simple_nav_btn_"] .stButton > button[data-testid="baseButton-primary"] {
  background: #dc2626 !important;
  color: #ffffff !important;
  border-color: #b91c1c !important;
  font-weight: 700 !important;
}
"""


def _quick_nav_artistic_css() -> str:
    """Quick nav — icon + Caveat script label, visible Open button (no overlay ghosts)."""
    return _simple_nav_css() + """
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&display=swap');

[class*="st-key-studio_quick_nav_panel"] {
  margin: 0 0 0.45rem !important;
  padding: 0.28rem 0.45rem 0.32rem !important;
  border-radius: 10px !important;
  border: 1px solid rgba(15, 23, 42, 0.1) !important;
  background: linear-gradient(180deg, #fffdf9 0%, #ffffff 100%) !important;
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05) !important;
}
[class*="st-key-studio_quick_nav_panel"] [data-testid="stHorizontalBlock"] {
  gap: 0.12rem 0.18rem !important;
  align-items: flex-start !important;
  flex-wrap: wrap !important;
}
[class*="st-key-studio_quick_nav_panel"] [data-testid="column"] {
  min-width: 0 !important;
  flex: 1 1 auto !important;
}
.ui-nav-art-cell {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.1rem;
  min-width: 0;
}
.ui-nav-art-face {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.26rem;
  min-height: 2rem;
  padding: 0.14rem 0.28rem 0.16rem;
  border-radius: 7px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  pointer-events: none;
  user-select: none;
}
.ui-nav-icon {
  font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif !important;
  font-size: 1.02rem;
  line-height: 1;
  flex-shrink: 0;
}
.ui-nav-script-label {
  font-family: "Caveat", "Segoe Script", "Bradley Hand", cursive !important;
  font-size: 1.18rem !important;
  font-weight: 600 !important;
  color: #475569 !important;
  letter-spacing: 0.02em !important;
  line-height: 1.05 !important;
  white-space: nowrap !important;
}
.ui-nav-art-cell.is-active .ui-nav-art-face {
  background: rgba(124, 58, 237, 0.08);
  border-bottom-color: rgba(220, 38, 38, 0.85);
}
.ui-nav-art-cell.is-active .ui-nav-script-label {
  font-weight: 700 !important;
  color: #dc2626 !important;
}
.ui-nav-art-cell.ui-nav-compact {
  gap: 0.08rem;
}
.ui-nav-art-cell.ui-nav-compact .ui-nav-art-face {
  min-height: 1.75rem;
  padding: 0.1rem 0.2rem 0.12rem;
  gap: 0.18rem;
}
.ui-nav-art-cell.ui-nav-compact .ui-nav-icon {
  font-size: 0.92rem;
}
.ui-nav-art-cell.ui-nav-compact .ui-nav-script-label {
  font-size: 1.02rem !important;
}
[class*="st-key-studio_quick_nav_btn_"] .stButton > button,
[class*="st-key-global_nav_"] .stButton > button,
[class*="st-key-cross_to_"] .stButton > button {
  min-height: 1.55rem !important;
  padding: 0.2rem 0.32rem !important;
  font-size: 0.72rem !important;
  font-weight: 600 !important;
  line-height: 1.1 !important;
  border-radius: 6px !important;
  box-shadow: none !important;
}
[class*="st-key-studio_quick_nav_btn_"] .stButton > button[kind="secondary"],
[class*="st-key-studio_quick_nav_btn_"] .stButton > button[data-testid="baseButton-secondary"],
[class*="st-key-global_nav_"] .stButton > button[kind="secondary"],
[class*="st-key-global_nav_"] .stButton > button[data-testid="baseButton-secondary"],
[class*="st-key-cross_to_"] .stButton > button[kind="secondary"],
[class*="st-key-cross_to_"] .stButton > button[data-testid="baseButton-secondary"] {
  border: 1px solid rgba(148, 163, 184, 0.42) !important;
  background: #ffffff !important;
  color: #475569 !important;
}
[class*="st-key-studio_quick_nav_btn_"] .stButton > button[kind="primary"],
[class*="st-key-studio_quick_nav_btn_"] .stButton > button[data-testid="baseButton-primary"],
[class*="st-key-global_nav_"] .stButton > button[kind="primary"],
[class*="st-key-global_nav_"] .stButton > button[data-testid="baseButton-primary"],
[class*="st-key-cross_to_"] .stButton > button[kind="primary"],
[class*="st-key-cross_to_"] .stButton > button[data-testid="baseButton-primary"] {
  border: 2px solid #7c3aed !important;
  background: #dc2626 !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}
.ui-cross-nav-art {
  margin: 0.35rem 0 0.75rem 0;
}
.ui-cross-nav-art [data-testid="stHorizontalBlock"] {
  gap: 0.12rem 0.18rem !important;
  align-items: flex-start !important;
  flex-wrap: wrap !important;
}
.ui-cross-nav-art [data-testid="column"] {
  min-width: 0 !important;
  flex: 1 1 auto !important;
}
.ui-practice-quicklinks.ui-cross-nav-art,
.ui-backing-scope-quicklinks.ui-cross-nav-art {
  margin-top: 0.45rem !important;
  padding-top: 0.5rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.32);
}
@media (max-width: 720px) {
  .ui-nav-script-label { font-size: 1.05rem !important; }
  [class*="st-key-studio_quick_nav_panel"] [data-testid="stHorizontalBlock"] {
    gap: 0.08rem !important;
  }
}
[class*="st-key-music_coach_insight_panel"] {
  margin: 0.4rem 0 0.55rem 0 !important;
  clear: both;
}
"""


def _render_nav_art_cell(
    st: Any,
    session_state: Any,
    *,
    page_id: str,
    current: str | None,
    rerun_fn: Any,
    button_key: str,
    compact: bool = False,
) -> None:
    """Icon + script label above a small Open button — no duplicate page-name text."""
    is_active = current is not None and page_id == current
    nav_class = STUDIO_PAGE_META.get(page_id, {}).get("nav_class", page_id)
    help_text = STUDIO_PAGE_META.get(page_id, {}).get("label", page_id) or nav_compact_button_label(
        page_id
    )
    active_cls = " is-active" if is_active else ""
    compact_cls = " ui-nav-compact" if compact else ""

    st.markdown(
        f'<div class="ui-nav-art-cell nav-{html.escape(nav_class)}{active_cls}{compact_cls}">'
        f"{_nav_art_face_html(page_id, active=is_active)}",
        unsafe_allow_html=True,
    )
    if st.button(
        _STUDIO_QUICK_NAV_OPEN_LABEL,
        key=button_key,
        type="primary" if is_active else "secondary",
        use_container_width=True,
        help=f"Open {help_text}",
    ):
        if (current is None or page_id != current) and navigate_studio_page(
            session_state, page_id
        ):
            rerun_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_quick_nav_row(
    st: Any,
    session_state: Any,
    *,
    page_ids: list[str],
    current: str,
    rerun_fn: Any,
) -> None:
    cols = st.columns(len(page_ids))
    for col, page_id in zip(cols, page_ids):
        with col:
            _render_nav_art_cell(
                st,
                session_state,
                page_id=page_id,
                current=current,
                rerun_fn=rerun_fn,
                button_key=_studio_quick_nav_button_key(page_id),
            )


def _render_simple_nav_row(
    st: Any,
    session_state: Any,
    *,
    current: str,
    rerun_fn: Any,
) -> None:
    """Plain Streamlit nav buttons — Practice, Songs, Backing, Custom, Multitrack."""
    cols = st.columns(len(SIMPLE_NAV_PAGE_IDS))
    for col, page_id in zip(cols, SIMPLE_NAV_PAGE_IDS):
        with col:
            is_active = page_id == current
            if st.button(
                nav_compact_button_label(page_id),
                key=_studio_simple_nav_button_key(page_id),
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                if page_id != current and navigate_studio_page(session_state, page_id):
                    rerun_fn()


def _sync_studio_page_nav_widget(
    session_state: Any,
    current_page: str,
    nav_widget_key: str,
) -> None:
    """Keep segmented_control value aligned with studio_page (before widget builds)."""
    if session_state.get(nav_widget_key) not in TOP_NAV_PAGE_IDS:
        session_state[nav_widget_key] = current_page
    studio = session_state.get("studio_page", current_page)
    if studio in TOP_NAV_PAGE_IDS and studio != session_state.get(nav_widget_key):
        session_state[nav_widget_key] = studio


# Compact cross-page shortcuts (subset for inline link rows).
CROSS_PAGE_LINKS: list[str] = ["practice", "picker", "backing", "creative", "custom"]

BACKING_SCOPE_QUICK_LINKS: list[str] = ["practice", "picker", "creative", "custom"]


def _resolve_nav_page_ids(
    pages: list[str] | list[tuple[str, str]] | None,
    *,
    exclude: str | None = None,
) -> list[str]:
    raw = pages if pages is not None else CROSS_PAGE_LINKS
    page_ids: list[str] = []
    for item in raw:
        page_ids.append(item if isinstance(item, str) else item[0])
    if exclude:
        page_ids = [page_id for page_id in page_ids if page_id != exclude]
    return page_ids


def ensure_studio_page(session_state: dict[str, Any], default: str = "practice") -> str:
    return session_state.setdefault("studio_page", default)


def begin_studio_control_deck() -> None:
    """Open unified top control card (nav + grouped sections)."""
    import streamlit as st

    st.markdown(
        '<div class="ui-studio-deck"><div class="ui-workspace-panel">',
        unsafe_allow_html=True,
    )


def end_studio_control_deck() -> None:
    import streamlit as st

    st.markdown("</div></div>", unsafe_allow_html=True)


def reset_quick_nav_render_diagnostics(session_state: Any) -> None:
    """Clear per-script-run quick nav counters (call once at top of each Streamlit run)."""
    global _QUICK_NAV_RENDERED_THIS_EXEC, _MUSIC_INSIGHT_RENDERED_THIS_EXEC

    _QUICK_NAV_RENDERED_THIS_EXEC = False
    _MUSIC_INSIGHT_RENDERED_THIS_EXEC = False
    session_state.pop("_ami_insight_card_rendered", None)
    session_state["quick_nav_render_count"] = 0
    session_state["quick_nav_render_locations"] = []
    session_state["quick_nav_render_stack"] = []
    session_state["quick_nav_container_keys"] = []
    session_state.pop(QUICK_NAV_DIAG_KEY, None)


def _quick_nav_caller_label() -> str:
    import inspect
    from pathlib import Path

    for frame in inspect.stack()[2:10]:
        path = Path(frame.filename)
        if path.name == "app_ui.py" and frame.function in {
            "render_page_quick_nav",
            "_render_page_quick_nav",
            "_render_canonical_studio_quick_nav",
        }:
            continue
        return f"{frame.function} ({path.name}:{frame.lineno})"
    return "unknown"


def _record_quick_nav_render(
    session_state: Any,
    *,
    current_page: str,
    key_prefix: str,
    container_key: str | None,
    skipped: bool = False,
) -> None:
    import traceback

    stack_tail = [
        line.strip()
        for line in traceback.format_stack(limit=10)[:-1]
        if "site-packages" not in line
    ][-5:]
    entry = {
        "caller": _quick_nav_caller_label(),
        "page": current_page,
        "key_prefix": key_prefix,
        "container_id": container_key,
        "skipped_duplicate": skipped,
        "stack_tail": stack_tail,
    }
    diag = session_state.get(QUICK_NAV_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {"count": 0, "locations": [], "container_keys": []}
    if not skipped:
        diag["count"] = int(diag.get("count") or 0) + 1
    diag.setdefault("locations", []).append(entry)
    if container_key and not skipped:
        diag.setdefault("container_keys", []).append(container_key)
    session_state[QUICK_NAV_DIAG_KEY] = diag
    session_state["quick_nav_render_count"] = diag["count"]
    session_state["quick_nav_render_locations"] = list(diag.get("locations") or [])
    session_state["quick_nav_render_stack"] = stack_tail
    session_state["quick_nav_container_keys"] = list(diag.get("container_keys") or [])


def render_quick_nav_dev_diagnostics(st: Any) -> None:
    """?dev=1 — show quick nav render count, callers, and container keys."""
    try:
        from music_dev_ui import music_dev_mode_enabled

        if not music_dev_mode_enabled(st=st):
            return
    except ImportError:
        if not st.session_state.get("developer_mode"):
            return
    ss = st.session_state
    count = int(ss.get("quick_nav_render_count") or 0)
    locations = ss.get("quick_nav_render_locations") or []
    stack = ss.get("quick_nav_render_stack") or []
    keys = ss.get("quick_nav_container_keys") or []
    with st.sidebar.expander("Quick nav diagnostics", expanded=False):
        st.caption(f"**quick_nav_render_count:** `{count}`")
        if locations:
            st.caption("**quick_nav_render_locations:**")
            for idx, loc in enumerate(locations, start=1):
                if not isinstance(loc, dict):
                    continue
                skipped = " (skipped duplicate)" if loc.get("skipped_duplicate") else ""
                st.caption(
                    f"{idx}. `{loc.get('caller', '?')}` page=`{loc.get('page', '')}` "
                    f"key_prefix=`{loc.get('key_prefix', '')}` "
                    f"container=`{loc.get('container_id') or 'none'}`{skipped}"
                )
        if stack:
            with st.expander("quick_nav_render_stack", expanded=False):
                st.code("\n".join(str(line) for line in stack))
        if keys:
            st.caption(f"**quick_nav_container_keys:** `{', '.join(keys)}`")


def render_page_quick_nav(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
    key_prefix: str = STUDIO_QUICK_NAV_KEY_PREFIX,
) -> str:
    """Top navigation — script-style art row (Upload/Multitrack visible) or plain diagnostic row."""
    import streamlit as st

    global _QUICK_NAV_RENDERED_THIS_EXEC

    ensure_studio_page(session_state, default=current_page)
    current = _resolve_quick_nav_current_page(session_state, current_page)

    if _QUICK_NAV_RENDERED_THIS_EXEC:
        _record_quick_nav_render(
            session_state,
            current_page=current,
            key_prefix=key_prefix,
            container_key=None,
            skipped=True,
        )
        return session_state.get("studio_page", current)
    _QUICK_NAV_RENDERED_THIS_EXEC = True
    _record_quick_nav_render(
        session_state,
        current_page=current,
        key_prefix=key_prefix,
        container_key=STUDIO_QUICK_NAV_PANEL_KEY,
    )

    st.markdown(
        f"<style>{_quick_nav_artistic_css()}</style>",
        unsafe_allow_html=True,
    )
    if use_simple_music_nav(session_state):
        _render_simple_nav_row(
            st,
            session_state,
            current=current,
            rerun_fn=rerun_fn,
        )
    else:
        with st.container(key=STUDIO_QUICK_NAV_PANEL_KEY):
            _render_quick_nav_row(
                st,
                session_state,
                page_ids=QUICK_NAV_ROW_PRIMARY,
                current=current,
                rerun_fn=rerun_fn,
            )
            _render_quick_nav_row(
                st,
                session_state,
                page_ids=QUICK_NAV_ROW_SECONDARY,
                current=current,
                rerun_fn=rerun_fn,
            )
    _render_music_coach_insight_below_quick_nav(st, current_page=current)

    return session_state.get("studio_page", current)


def _render_music_coach_insight_below_quick_nav(st: Any, *, current_page: str) -> bool:
    """Music Coach insight — canonical render slot below quick nav."""
    global _MUSIC_INSIGHT_RENDERED_THIS_EXEC

    if _MUSIC_INSIGHT_RENDERED_THIS_EXEC:
        return False
    ss = getattr(st, "session_state", st)
    try:
        from suite_analytical_question import render_suite_applied_math_insight

        ok = bool(
            render_suite_applied_math_insight(
                st,
                source_app="music",
                source_page=current_page,
            )
        )
        if ok:
            _MUSIC_INSIGHT_RENDERED_THIS_EXEC = True
        return ok
    except Exception as exc:
        ss["_ami_insight_render_error"] = str(exc)
        return False


def render_deferred_music_coach_insight(st: Any, *, studio_page: str) -> bool:
    """Render pending insight after page body (main-panel submit runs after quick nav)."""
    global _MUSIC_INSIGHT_RENDERED_THIS_EXEC

    if _MUSIC_INSIGHT_RENDERED_THIS_EXEC:
        return False
    ss = getattr(st, "session_state", st)
    if ss.get("_ami_insight_card_rendered"):
        return False
    try:
        from applied_math_return_insight import _pending_insight_valid

        if not _pending_insight_valid(st):
            return False
    except Exception:
        return False
    return _render_music_coach_insight_below_quick_nav(st, current_page=studio_page)


def render_sidebar_studio_nav(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
    ai_enabled: bool = False,
) -> str:
    """Colorful vertical studio navigation in the sidebar (collapsible, default collapsed)."""
    import streamlit as st

    current = ensure_studio_page(session_state, default=current_page)
    ensure_sidebar_nav_defaults(session_state)
    collapsed = sidebar_nav_is_collapsed(session_state)
    collapsed_attr = "true" if collapsed else "false"

    st.sidebar.markdown(
        f'<div class="ui-sb-nav-panel" data-collapsed="{collapsed_attr}">',
        unsafe_allow_html=True,
    )

    if collapsed:
        st.sidebar.markdown('<div class="ui-sb-nav-collapsed-rail">', unsafe_allow_html=True)
        if st.sidebar.button(
            "☰  Pages",
            key="sidebar_nav_expand_rail",
            use_container_width=True,
            type="primary",
            help="Show full page list (Practice, Backing Track, Song Selection, …)",
        ):
            session_state[SIDEBAR_NAV_COLLAPSED_KEY] = False
            rerun_fn()
        st.sidebar.markdown("</div>", unsafe_allow_html=True)
        st.sidebar.markdown("</div>", unsafe_allow_html=True)
        return session_state.get("studio_page", current)

    _header = st.sidebar.columns([5, 1])
    with _header[0]:
        sidebar_section("Pages", icon="🧭", tone="nav")
    with _header[1]:
        if st.sidebar.button(
            "◀",
            key="sidebar_nav_collapse_toggle",
            help="Collapse page navigation for more chart and practice space",
            use_container_width=True,
        ):
            session_state[SIDEBAR_NAV_COLLAPSED_KEY] = True
            rerun_fn()

    st.sidebar.markdown('<div class="ui-sb-nav-wrap">', unsafe_allow_html=True)
    for page_id, label in sidebar_studio_page_items(ai_enabled=ai_enabled):
        nav_class = STUDIO_PAGE_META.get(page_id, {}).get("nav_class", page_id)
        active_cls = " nav-btn-active" if page_id == current else ""
        st.sidebar.markdown(
            f'<div class="sb-nav-btn studio-nav-item sb-nav-{nav_class}{active_cls}">',
            unsafe_allow_html=True,
        )
        if st.sidebar.button(
            label,
            key=f"sb_nav_{page_id}",
            use_container_width=True,
            type="secondary",
        ):
            if page_id != current and navigate_studio_page(session_state, page_id):
                rerun_fn()
        st.sidebar.markdown("</div>", unsafe_allow_html=True)
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
    return session_state.get("studio_page", current)


def render_main_sidebar_nav_expand_chip(
    session_state: Any,
    *,
    rerun_fn: Any,
) -> None:
    """Fixed chip in the main area when sidebar page nav is collapsed."""
    import streamlit as st

    if not sidebar_nav_is_collapsed(session_state):
        return
    st.markdown('<div class="ui-main-nav-expand-chip">', unsafe_allow_html=True)
    if st.button(
        "☰ Pages",
        key="main_sidebar_nav_expand",
        help="Expand page navigation in the sidebar",
    ):
        session_state[SIDEBAR_NAV_COLLAPSED_KEY] = False
        rerun_fn()
    st.markdown("</div>", unsafe_allow_html=True)


def render_cross_page_links(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
    key_prefix: str = "cross",
    pages: list[str] | list[tuple[str, str]] | None = None,
    wrapper_class: str = "ui-cross-nav-art",
    compact: bool = True,
) -> None:
    """Icon + label shortcuts to other workspaces (excludes current page)."""
    import streamlit as st

    if _QUICK_NAV_RENDERED_THIS_EXEC:
        _record_quick_nav_render(
            session_state,
            current_page=current_page,
            key_prefix=key_prefix,
            container_key=None,
            skipped=True,
        )
        return

    targets = _resolve_nav_page_ids(pages, exclude=current_page)
    if not targets:
        return
    st.markdown(f'<div class="{html.escape(wrapper_class)}">', unsafe_allow_html=True)
    cols = st.columns(len(targets))
    for col, page_id in zip(cols, targets):
        with col:
            _render_nav_art_cell(
                st,
                session_state,
                page_id=page_id,
                current=None,
                rerun_fn=rerun_fn,
                button_key=f"{key_prefix}_to_{page_id}",
                compact=compact,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def render_studio_nav(session_state: Any, *, rerun_fn: Any) -> str:
    """Legacy full-deck nav — delegates to per-page quick nav."""
    return render_page_quick_nav(
        session_state,
        current_page=ensure_studio_page(session_state),
        rerun_fn=rerun_fn,
    )


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
    st.markdown('<p class="ui-bar-label session">Practice session</p>', unsafe_allow_html=True)

    try:
        from songs.key_state import apply_display_key_for_active_song, song_display_identity

        sel = ss.get("selected_song") if isinstance(ss.get("selected_song"), dict) else {}
        song_identity = song_display_identity(
            song,
            str(sel.get("artist") or ""),
            original_key,
        )
        apply_display_key_for_active_song(st, original_key, song_identity)
    except Exception:
        pass

    row1 = st.columns([1.55, 1.15, 0.95, 1.05, 1.0, 0.85])
    with row1[0]:
        genre_bit = f'<span style="color:#6d28d9;font-weight:700;">{html.escape(genre)}</span>' if genre else ""
        st.markdown(
            f'<div class="ui-now-playing">'
            f'<p class="np-title">{html.escape(song)}</p>'
            f'<p class="np-meta">{html.escape(source_label)} · written key <strong>{html.escape(original_key)}</strong>'
            f"{(' · ' + genre_bit) if genre else ''}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with row1[1]:
        st.selectbox(
            "Practice key",
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
            from songs.playback_defaults import BACKING_BPM_MAX, BACKING_BPM_MIN

            st.slider(
                "Tempo",
                BACKING_BPM_MIN,
                BACKING_BPM_MAX,
                100,
                5,
                key=bpm_key,
                help="Backing track BPM (20–180)",
            )
        elif backing_ready:
            st.markdown(
                '<span class="ui-backing-pill ready">● Backing ready</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="ui-backing-pill">○ Backing idle</span>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="ui-bar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<p class="ui-bar-label library">Song & quick navigation</p>', unsafe_allow_html=True)

    row2 = st.columns([1.0, 0.95, 2.5, 0.72, 0.72, 0.72])
    with row2[0]:
        st.selectbox(
            "Source",
            ["Catalog song", "Custom progression"],
            index=1 if is_custom_source else 0,
            key="global_source_mode",
            on_change=on_source_change,
        )
    with row2[1]:
        if is_custom_source:
            st.markdown(
                f'<p class="ui-bar-label" style="margin-top:1.4rem;">Custom</p>'
                f'<p style="font-weight:800;font-size:0.88rem;margin:0;">{html.escape(custom_progression_name or "Progression")}</p>',
                unsafe_allow_html=True,
            )
        elif genre_options:
            _gopts = genre_options
            _gidx = _gopts.index(current_genre) if current_genre in _gopts else 0
            if ss.get("global_quick_genre") not in _gopts:
                ss["global_quick_genre"] = current_genre if current_genre in _gopts else _gopts[0]
            st.selectbox(
                "Genre filter",
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
            st.caption("Edit in **Custom** tab · transpose with **Practice key** above.")
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
                help="Changes the active chart everywhere in the app.",
            )
        else:
            st.caption("Song")
            st.markdown(f"**{html.escape(song)}**")
    _studio = ensure_studio_page(ss)
    with row2[3]:
        if rerun_fn:
            _render_nav_art_cell(
                st,
                ss,
                page_id="picker",
                current=_studio,
                rerun_fn=rerun_fn,
                button_key="global_nav_picker",
                compact=True,
            )
    with row2[4]:
        if rerun_fn:
            _render_nav_art_cell(
                st,
                ss,
                page_id="practice",
                current=_studio,
                rerun_fn=rerun_fn,
                button_key="global_nav_practice",
                compact=True,
            )
    with row2[5]:
        if rerun_fn:
            _render_nav_art_cell(
                st,
                ss,
                page_id="backing",
                current=_studio,
                rerun_fn=rerun_fn,
                button_key="global_nav_backing",
                compact=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


_DECORATIVE_HEADER_SCRIPT: dict[str, str] = {
    "practice": "Practice",
    "picker": "Songs",
    "backing": "Backing",
    "custom": "Custom",
    "composer": "Compose",
    "creative": "Creative",
    "analysis": "Upload",
    "multitrack": "Multitrack",
    "log": "Log",
    "openai": "Coach",
}

_DECORATIVE_HEADER_KICKER: dict[str, str] = {
    "practice": "Music studio",
    "picker": "Song catalog",
    "backing": "Audio studio",
    "custom": "Progression lab",
    "composer": "Songwriting workspace",
    "creative": "Improvisation lab",
    "analysis": "Recording coach",
    "multitrack": "Layer studio",
    "log": "Session history",
    "openai": "AI coaching",
}


def _resolve_decorative_header_page_id(icon: str, title: str, *, page_id: str | None = None) -> str:
    if page_id:
        return str(page_id).strip().lower()
    text = str(title or "").strip().lower()
    if "practice" in text and "log" not in text:
        return "practice"
    if "backing" in text:
        return "backing"
    if "song" in text or "selection" in text or "library" in text:
        return "picker"
    if "custom" in text or "progression" in text:
        return "custom"
    if "creative" in text:
        return "creative"
    if "upload" in text or "analysis" in text:
        return "analysis"
    if "multitrack" in text:
        return "multitrack"
    if "log" in text:
        return "log"
    if "openai" in text or "coaching" in text:
        return "openai"
    icon_map = {
        "🎯": "practice",
        "🎼": "picker",
        "📚": "picker",
        "🎧": "backing",
        "🎤": "backing",
        "🎨": "creative",
        "🎙️": "analysis",
        "🎚️": "multitrack",
        "📓": "log",
        "✨": "openai",
    }
    return icon_map.get(str(icon or "").strip(), "practice")


def render_chart_key_mode_status_badge(st: Any) -> None:
    """Display-only written-key / concert charts badge (reads session; no writes)."""
    block = chart_key_mode_badge_html(st.session_state)
    if block:
        st.markdown(block, unsafe_allow_html=True)


def compact_page_title(
    icon: str,
    title: str,
    subtitle: str = "",
    *,
    page_id: str | None = None,
    skip_chart_key_badge: bool = False,
) -> None:
    """Single branded page header: icon, script accent, page title, optional subtitle."""
    import streamlit as st

    resolved_page_id = _resolve_decorative_header_page_id(icon, title, page_id=page_id)
    script_word = _DECORATIVE_HEADER_SCRIPT.get(
        resolved_page_id, title.split()[0] if title else "Studio"
    )
    kicker = _DECORATIVE_HEADER_KICKER.get(resolved_page_id, "Music studio")
    sub = (
        f'<p class="ui-studio-script-header-sub">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f'<div class="ui-studio-script-header ui-studio-script-header--{html.escape(resolved_page_id)}">'
        f'<span class="ui-studio-script-header-icon" aria-hidden="true">{html.escape(icon)}</span>'
        f"<div>"
        f'<p class="ui-studio-script-header-kicker">{html.escape(kicker)}</p>'
        f'<p class="ui-studio-script-header-script">{html.escape(script_word)}</p>'
        f'<p class="ui-studio-script-header-title">{html.escape(title)}</p>'
        f"{sub}"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    if not skip_chart_key_badge:
        render_chart_key_mode_status_badge(st)


def _short_section_label(name: str) -> str:
    low = name.lower()
    if "verse" in low:
        return "Verse"
    if "pre" in low and "chorus" in low:
        return "Pre"
    if "chorus" in low:
        return "Chorus"
    if "bridge" in low:
        return "Bridge"
    if "outro" in low:
        return "Outro"
    if "intro" in low:
        return "Intro"
    return name.split("/")[0].split("(")[0].strip()[:12] or name


def render_section_jump_bar(
    section_names: list[str],
    session_state: Any,
    *,
    state_key: str = "practice_focus_section",
    rerun_fn: Optional[Any] = None,
    on_change: Optional[Any] = None,
) -> Optional[str]:
    """Section focus selector — first option should be Full Song when provided."""
    import streamlit as st

    options = [n for n in section_names if n]
    if not options:
        return None
    try:
        from practice_state import normalize_practice_focus_section

        current = normalize_practice_focus_section(session_state.get(state_key))
        if current:
            session_state[state_key] = current
    except ImportError:
        current = session_state.get(state_key)
    if current not in options:
        session_state[state_key] = options[0]
        current = options[0]

    def _label(name: str) -> str:
        if name.strip().lower() in ("full song", "full form"):
            return "Full Song"
        short = _short_section_label(name)
        return short if short != name[:12] else name

    st.markdown(
        '<div class="ui-section-jump"><p class="ui-bar-label">Section focus</p>',
        unsafe_allow_html=True,
    )
    picked = st.radio(
        "Section focus",
        options,
        horizontal=True,
        key=state_key,
        format_func=_label,
        label_visibility="collapsed",
        on_change=on_change,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return picked


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
