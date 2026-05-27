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
    "render_studio_nav",
    "STUDIO_PAGE_META",
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
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid rgba(29, 78, 216, 0.2);
  border-radius: 8px;
  padding: 0.4rem 0.55rem;
  margin: 0 0 0.45rem 0;
  line-height: 1.4;
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
.ui-sb-nav-wrap .sb-nav-practice button { background:linear-gradient(180deg,rgba(14,165,233,.22),rgba(20,184,166,.14))!important; color:#e0f2fe!important; border-color:rgba(56,189,248,.35)!important; }
.ui-sb-nav-wrap .sb-nav-practice.nav-btn-active button { background:linear-gradient(135deg,#0ea5e9,#14b8a6)!important; color:#fff!important; border-color:rgba(56,189,248,.55)!important; }
.ui-sb-nav-wrap .sb-nav-picker button { background:linear-gradient(180deg,rgba(139,92,246,.22),rgba(168,85,247,.12))!important; color:#ede9fe!important; border-color:rgba(167,139,250,.35)!important; }
.ui-sb-nav-wrap .sb-nav-picker.nav-btn-active button { background:linear-gradient(135deg,#8b5cf6,#a855f7)!important; color:#fff!important; border-color:rgba(167,139,250,.55)!important; }
.ui-sb-nav-wrap .sb-nav-backing button { background:linear-gradient(180deg,rgba(34,197,94,.2),rgba(16,185,129,.12))!important; color:#dcfce7!important; border-color:rgba(74,222,128,.35)!important; }
.ui-sb-nav-wrap .sb-nav-backing.nav-btn-active button { background:linear-gradient(135deg,#22c55e,#10b981)!important; color:#fff!important; border-color:rgba(74,222,128,.55)!important; }
.ui-sb-nav-wrap .sb-nav-creative button { background:linear-gradient(180deg,rgba(245,158,11,.2),rgba(251,191,36,.12))!important; color:#fef3c7!important; border-color:rgba(251,191,36,.35)!important; }
.ui-sb-nav-wrap .sb-nav-creative.nav-btn-active button { background:linear-gradient(135deg,#f59e0b,#fbbf24)!important; color:#422006!important; border-color:rgba(251,191,36,.55)!important; }
.ui-sb-nav-wrap .sb-nav-custom button { background:linear-gradient(180deg,rgba(99,102,241,.22),rgba(79,70,229,.12))!important; color:#e0e7ff!important; border-color:rgba(129,140,248,.35)!important; }
.ui-sb-nav-wrap .sb-nav-custom.nav-btn-active button { background:linear-gradient(135deg,#6366f1,#4f46e5)!important; color:#fff!important; border-color:rgba(129,140,248,.55)!important; }
.ui-sb-nav-wrap .sb-nav-multitrack button { background:linear-gradient(180deg,rgba(244,63,94,.2),rgba(251,113,133,.12))!important; color:#ffe4e6!important; border-color:rgba(251,113,133,.35)!important; }
.ui-sb-nav-wrap .sb-nav-multitrack.nav-btn-active button { background:linear-gradient(135deg,#f43f5e,#fb7185)!important; color:#fff!important; border-color:rgba(251,113,133,.55)!important; }
.ui-sb-nav-wrap .sb-nav-analysis button { background:linear-gradient(180deg,rgba(6,182,212,.2),rgba(34,211,238,.12))!important; color:#cffafe!important; border-color:rgba(34,211,238,.35)!important; }
.ui-sb-nav-wrap .sb-nav-analysis.nav-btn-active button { background:linear-gradient(135deg,#06b6d4,#22d3ee)!important; color:#fff!important; border-color:rgba(34,211,238,.55)!important; }
.ui-sb-nav-wrap .sb-nav-log button { background:linear-gradient(180deg,rgba(100,116,139,.18),rgba(71,85,105,.1))!important; color:#e2e8f0!important; border-color:rgba(148,163,184,.3)!important; }
.ui-sb-nav-wrap .sb-nav-log.nav-btn-active button { background:linear-gradient(135deg,#64748b,#475569)!important; color:#fff!important; border-color:rgba(148,163,184,.55)!important; }
.cross-practice button { background:linear-gradient(135deg,#0ea5e9,#14b8a6)!important; color:#fff!important; border:none!important; }
.cross-picker button { background:linear-gradient(135deg,#8b5cf6,#a855f7)!important; color:#fff!important; border:none!important; }
.cross-backing button { background:linear-gradient(135deg,#22c55e,#10b981)!important; color:#fff!important; border:none!important; }
.cross-creative button { background:linear-gradient(135deg,#f59e0b,#fbbf24)!important; color:#422006!important; border:none!important; }
.cross-custom button { background:linear-gradient(135deg,#6366f1,#4f46e5)!important; color:#fff!important; border:none!important; }
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
  margin: 0 0 0.5rem 0;
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
.ui-section-jump .ui-bar-label { margin-bottom: 0.35rem; color: #15803d; }
.ui-section-jump .jump-btn button {
  font-size: 0.76rem !important;
  padding: 0.32rem 0.45rem !important;
  min-height: 1.85rem !important;
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
.ui-active-song-hub .ui-active-song-card {
  border: 2px solid rgba(37, 99, 235, 0.35);
  border-radius: 18px;
  padding: 1.1rem 1.15rem;
  margin: 0.25rem 0 0.65rem 0;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 40%, #eef2ff 100%);
  box-shadow: 0 6px 24px rgba(37, 99, 235, 0.14);
}
.ui-active-song-hub .ui-active-song-art {
  min-height: 120px;
  font-size: 2.35rem;
  border-radius: 16px;
}
.ui-active-song-hub .ui-active-song-kicker {
  font-size: 0.7rem;
  color: #4338ca;
}
.ui-active-song-hub .ui-active-song-title {
  font-size: 1.65rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.ui-active-song-hub .ui-active-song-artist {
  font-size: 0.95rem;
  color: #475569;
  margin-bottom: 0.45rem;
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
.ui-studio-history-nav {
  margin: 0.05rem 0 0.15rem 0;
  padding: 0;
  line-height: 1;
}
.ui-sb-nav-label {
  display: block;
  font-size: 0.58rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.09em !important;
  text-transform: uppercase !important;
  color: #94a3b8 !important;
  margin: 0 0 0.18rem 0 !important;
  padding: 0 !important;
  opacity: 0.9;
}
/* Compact [←] [→] row directly under the Navigate label */
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] {
  margin-top: -0.1rem !important;
  margin-bottom: 0.35rem !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
  gap: 0.28rem !important;
  width: auto !important;
  max-width: 4.6rem !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] div[data-testid="column"] {
  flex: 0 0 auto !important;
  width: auto !important;
  min-width: 0 !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] .stButton {
  margin: 0 !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] .stButton > button {
  min-height: 1.28rem !important;
  height: 1.28rem !important;
  width: 2.05rem !important;
  min-width: 2.05rem !important;
  max-width: 2.05rem !important;
  padding: 0 !important;
  margin: 0 !important;
  font-size: 0.88rem !important;
  font-weight: 700 !important;
  line-height: 1 !important;
  border-radius: 6px !important;
  border: 1px solid rgba(148, 163, 184, 0.35) !important;
  background: rgba(30, 41, 59, 0.55) !important;
  color: #e2e8f0 !important;
  box-shadow: none !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] .stButton > button:hover:not(:disabled) {
  background: rgba(51, 65, 85, 0.85) !important;
  border-color: rgba(148, 163, 184, 0.55) !important;
  color: #f8fafc !important;
}
[data-testid="stSidebar"] .ui-studio-history-nav + div[data-testid="stVerticalBlock"] .stButton > button:disabled {
  opacity: 0.35 !important;
  cursor: default !important;
}
[data-testid="stSidebar"] [class*="st-key-studio_nav_back_btn"] .stButton > button,
[data-testid="stSidebar"] [class*="st-key-studio_nav_forward_btn"] .stButton > button {
  min-height: 1.28rem !important;
  height: 1.28rem !important;
  width: 2.05rem !important;
  min-width: 2.05rem !important;
  max-width: 2.05rem !important;
  padding: 0 !important;
  font-size: 0.88rem !important;
  font-weight: 700 !important;
  border-radius: 6px !important;
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
  font-size: 0.82rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #475569;
  margin-bottom: 0.2rem;
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


_UI_POLISH_VERSION = "v2-2026-05-24"


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
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%) !important;
  color: #f8fafc !important;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06), 0 4px 12px rgba(15, 23, 42, 0.18) !important;
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
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.28) !important;
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
        """.replace("__UI_POLISH_VERSION__", _UI_POLISH_VERSION),
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
  <p class="ui-song-library-kicker">Catalog</p>
  <h3 class="ui-song-library-title">Song Library</h3>
  <p class="ui-song-library-sub">
    Find a song in the catalog, then open <strong>Practice</strong> or
    <strong>Backing Track</strong> — your chart, lyrics, and groove follow
    this selection everywhere in the studio.
  </p>
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
        "🎼 Song Selection",
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
    "creative": {"label": "Creative Lab", "icon": "🧠", "nav_class": "creative"},
    "multitrack": {"label": "Multitrack", "icon": "🎚️", "nav_class": "multitrack"},
    "analysis": {"label": "Upload Analysis", "icon": "🎙️", "nav_class": "analysis"},
    "log": {"label": "Practice Log", "icon": "📓", "nav_class": "log"},
}

STUDIO_PAGES: list[tuple[str, str]] = [
    (page_id, f"{meta['icon']} {meta['label']}")
    for page_id, meta in STUDIO_PAGE_META.items()
]

# Single source for top navigation — Practice is first, same widget as all others.
TOP_NAV_ITEMS: list[tuple[str, str]] = list(STUDIO_PAGES)
TOP_NAV_PAGE_IDS: list[str] = [page_id for page_id, _label in TOP_NAV_ITEMS]
STUDIO_PAGE_NAV_KEY = "studio_page_nav"


def navigate_studio_page(session_state: Any, page_id: str) -> bool:
    from studio_nav_history import navigate_studio_page as _nav

    return _nav(session_state, page_id)


_NAV_COMPACT_TITLE: dict[str, str] = {
    "practice": "Practice",
    "picker": "Songs",
    "backing": "Backing",
    "custom": "Custom",
    "creative": "Creative",
    "multitrack": "Multi",
    "analysis": "Upload",
    "log": "Log",
}


def nav_two_line_label(page_id: str) -> str:
    """Two-line labels — same structure on every segment (icon + title)."""
    meta = STUDIO_PAGE_META.get(page_id, {})
    icon = meta.get("icon", "")
    title = _NAV_COMPACT_TITLE.get(page_id, meta.get("label", page_id))
    return f"{icon}\n{title}" if icon else title


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
CROSS_PAGE_LINKS: list[tuple[str, str]] = [
    ("practice", "Go to Practice"),
    ("picker", "Go to Song Selection"),
    ("backing", "Go to Backing Track"),
    ("creative", "Go to Creative Lab"),
    ("custom", "Go to Custom Progression"),
]


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


def render_page_quick_nav(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
    key_prefix: str = "main_quick_nav",
) -> str:
    """Top navigation — one segmented_control row (equal segments, including Practice)."""
    import streamlit as st

    nav_widget_key = f"{key_prefix}_{current_page}_segmented_nav"
    current = ensure_studio_page(session_state, default=current_page)
    _sync_studio_page_nav_widget(session_state, current, nav_widget_key)

    def _on_nav_change() -> None:
        picked = session_state.get(nav_widget_key)
        if picked in TOP_NAV_PAGE_IDS and navigate_studio_page(session_state, picked):
            rerun_fn()

    st.markdown(
        '<p class="ui-page-nav-label">Quick navigation</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ui-studio-nav-segmented">', unsafe_allow_html=True)
    if hasattr(st, "segmented_control"):
        st.segmented_control(
            "Quick navigation",
            options=TOP_NAV_PAGE_IDS,
            format_func=nav_two_line_label,
            key=nav_widget_key,
            label_visibility="collapsed",
            on_change=_on_nav_change,
            width="stretch",
        )
    else:
        st.radio(
            "Quick navigation",
            TOP_NAV_PAGE_IDS,
            format_func=nav_two_line_label,
            key=nav_widget_key,
            horizontal=True,
            label_visibility="collapsed",
            on_change=_on_nav_change,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    return session_state.get("studio_page", current)


def render_sidebar_studio_nav(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
) -> str:
    """Colorful vertical studio navigation in the sidebar."""
    import streamlit as st

    current = ensure_studio_page(session_state, default=current_page)
    st.sidebar.markdown('<div class="ui-sb-nav-wrap">', unsafe_allow_html=True)
    for page_id, label in STUDIO_PAGES:
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
    return session_state.get("studio_page", current)


def render_cross_page_links(
    session_state: Any,
    *,
    current_page: str,
    rerun_fn: Any,
    key_prefix: str = "cross",
    pages: Optional[list[tuple[str, str]]] = None,
) -> None:
    """Small shortcut buttons to other workspaces (excludes current page)."""
    import streamlit as st

    link_pages = pages if pages is not None else CROSS_PAGE_LINKS
    targets = [(pid, label) for pid, label in link_pages if pid != current_page]
    if not targets:
        return
    st.markdown('<div class="ui-cross-links">', unsafe_allow_html=True)
    cols = st.columns(len(targets))
    for col, (page_id, label) in zip(cols, targets):
        nav_class = STUDIO_PAGE_META.get(page_id, {}).get("nav_class", page_id)
        button_key = f"{key_prefix}_to_{page_id}"
        with col:
            st.markdown(f'<div class="cross-{nav_class}">', unsafe_allow_html=True)
            if st.button(
                label,
                key=button_key,
                use_container_width=True,
            ):
                if navigate_studio_page(session_state, page_id):
                    rerun_fn()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_studio_nav(session_state: Any, *, rerun_fn: Any) -> str:
    """Legacy full-deck nav — delegates to per-page quick nav."""
    return render_page_quick_nav(
        session_state,
        current_page=ensure_studio_page(session_state),
        rerun_fn=rerun_fn,
        key_prefix="legacy",
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
            st.slider("Tempo", 50, 180, 100, 5, key=bpm_key, help="Backing track BPM")
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
    with row2[3]:
        st.markdown('<div class="ui-quick-nav">', unsafe_allow_html=True)
        if rerun_fn and st.button("Songs", key="global_nav_picker", use_container_width=True, help="Song library"):
            navigate_studio_page(ss, "picker")
            rerun_fn()
        st.markdown("</div>", unsafe_allow_html=True)
    with row2[4]:
        st.markdown('<div class="ui-quick-nav">', unsafe_allow_html=True)
        if rerun_fn and st.button("Practice", key="global_nav_practice", use_container_width=True, help="Practice page"):
            navigate_studio_page(ss, "practice")
            rerun_fn()
        st.markdown("</div>", unsafe_allow_html=True)
    with row2[5]:
        st.markdown('<div class="ui-quick-nav">', unsafe_allow_html=True)
        if rerun_fn and st.button("Backing", key="global_nav_backing", use_container_width=True, help="Backing track"):
            navigate_studio_page(ss, "backing")
            rerun_fn()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def compact_page_title(icon: str, title: str, subtitle: str = "") -> None:
    import streamlit as st

    sub = f'<p class="ui-compact-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'<p class="ui-compact-title">{html.escape(icon)} {html.escape(title)}</p>{sub}',
        unsafe_allow_html=True,
    )


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
) -> Optional[str]:
    """Section focus selector — first option should be Full Song when provided."""
    import streamlit as st

    options = [n for n in section_names if n]
    if not options:
        return None
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
