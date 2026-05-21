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
    "render_sidebar_studio_nav",
    "render_studio_nav",
    "STUDIO_PAGE_META",
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
.ui-studio-nav .nav-btn button {
  font-size: 0.72rem !important;
  font-weight: 700 !important;
  padding: 0.42rem 0.4rem !important;
  min-height: 2.15rem !important;
  border-radius: 10px !important;
  transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease !important;
}
.ui-studio-nav .nav-btn button:hover {
  transform: translateY(-1px);
  filter: brightness(1.04);
}
/* Page-colored navigation (inactive = soft tint, active = gradient) */
.nav-practice button { background: linear-gradient(180deg,#f0f9ff,#e0f2fe)!important; color:#0369a1!important; border:1px solid rgba(14,165,233,.35)!important; }
.nav-practice button[kind="primary"] { background:linear-gradient(135deg,#0ea5e9,#14b8a6)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(14,165,233,.35)!important; }
.nav-picker button { background:linear-gradient(180deg,#faf5ff,#f3e8ff)!important; color:#6d28d9!important; border:1px solid rgba(139,92,246,.35)!important; }
.nav-picker button[kind="primary"] { background:linear-gradient(135deg,#8b5cf6,#a855f7)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(139,92,246,.35)!important; }
.nav-backing button { background:linear-gradient(180deg,#f0fdf4,#dcfce7)!important; color:#15803d!important; border:1px solid rgba(34,197,94,.35)!important; }
.nav-backing button[kind="primary"] { background:linear-gradient(135deg,#22c55e,#10b981)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(34,197,94,.35)!important; }
.nav-creative button { background:linear-gradient(180deg,#fffbeb,#fef3c7)!important; color:#b45309!important; border:1px solid rgba(245,158,11,.4)!important; }
.nav-creative button[kind="primary"] { background:linear-gradient(135deg,#f59e0b,#fbbf24)!important; color:#422006!important; border:none!important; box-shadow:0 4px 14px rgba(245,158,11,.35)!important; }
.nav-custom button { background:linear-gradient(180deg,#eef2ff,#e0e7ff)!important; color:#4338ca!important; border:1px solid rgba(99,102,241,.35)!important; }
.nav-custom button[kind="primary"] { background:linear-gradient(135deg,#6366f1,#4f46e5)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(99,102,241,.35)!important; }
.nav-multitrack button { background:linear-gradient(180deg,#fff1f2,#ffe4e6)!important; color:#be123c!important; border:1px solid rgba(244,63,94,.35)!important; }
.nav-multitrack button[kind="primary"] { background:linear-gradient(135deg,#f43f5e,#fb7185)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(244,63,94,.35)!important; }
.nav-analysis button { background:linear-gradient(180deg,#ecfeff,#cffafe)!important; color:#0e7490!important; border:1px solid rgba(6,182,212,.35)!important; }
.nav-analysis button[kind="primary"] { background:linear-gradient(135deg,#06b6d4,#22d3ee)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(6,182,212,.35)!important; }
.nav-log button { background:linear-gradient(180deg,#f8fafc,#f1f5f9)!important; color:#475569!important; border:1px solid rgba(100,116,139,.35)!important; }
.nav-log button[kind="primary"] { background:linear-gradient(135deg,#64748b,#475569)!important; color:#fff!important; border:none!important; box-shadow:0 4px 14px rgba(71,85,105,.3)!important; }
/* Sidebar nav mirrors page colors */
.ui-sb-nav-wrap .sb-nav-practice button { background:linear-gradient(180deg,rgba(14,165,233,.22),rgba(20,184,166,.14))!important; color:#e0f2fe!important; border:1px solid rgba(56,189,248,.35)!important; }
.ui-sb-nav-wrap .sb-nav-practice button[kind="primary"] { background:linear-gradient(135deg,#0ea5e9,#14b8a6)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-picker button { background:linear-gradient(180deg,rgba(139,92,246,.22),rgba(168,85,247,.12))!important; color:#ede9fe!important; border:1px solid rgba(167,139,250,.35)!important; }
.ui-sb-nav-wrap .sb-nav-picker button[kind="primary"] { background:linear-gradient(135deg,#8b5cf6,#a855f7)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-backing button { background:linear-gradient(180deg,rgba(34,197,94,.2),rgba(16,185,129,.12))!important; color:#dcfce7!important; border:1px solid rgba(74,222,128,.35)!important; }
.ui-sb-nav-wrap .sb-nav-backing button[kind="primary"] { background:linear-gradient(135deg,#22c55e,#10b981)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-creative button { background:linear-gradient(180deg,rgba(245,158,11,.2),rgba(251,191,36,.12))!important; color:#fef3c7!important; border:1px solid rgba(251,191,36,.35)!important; }
.ui-sb-nav-wrap .sb-nav-creative button[kind="primary"] { background:linear-gradient(135deg,#f59e0b,#fbbf24)!important; color:#422006!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-custom button { background:linear-gradient(180deg,rgba(99,102,241,.22),rgba(79,70,229,.12))!important; color:#e0e7ff!important; border:1px solid rgba(129,140,248,.35)!important; }
.ui-sb-nav-wrap .sb-nav-custom button[kind="primary"] { background:linear-gradient(135deg,#6366f1,#4f46e5)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-multitrack button { background:linear-gradient(180deg,rgba(244,63,94,.2),rgba(251,113,133,.12))!important; color:#ffe4e6!important; border:1px solid rgba(251,113,133,.35)!important; }
.ui-sb-nav-wrap .sb-nav-multitrack button[kind="primary"] { background:linear-gradient(135deg,#f43f5e,#fb7185)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-analysis button { background:linear-gradient(180deg,rgba(6,182,212,.2),rgba(34,211,238,.12))!important; color:#cffafe!important; border:1px solid rgba(34,211,238,.35)!important; }
.ui-sb-nav-wrap .sb-nav-analysis button[kind="primary"] { background:linear-gradient(135deg,#06b6d4,#22d3ee)!important; color:#fff!important; border:none!important; }
.ui-sb-nav-wrap .sb-nav-log button { background:linear-gradient(180deg,rgba(100,116,139,.18),rgba(71,85,105,.1))!important; color:#e2e8f0!important; border:1px solid rgba(148,163,184,.3)!important; }
.ui-sb-nav-wrap .sb-nav-log button[kind="primary"] { background:linear-gradient(135deg,#64748b,#475569)!important; color:#fff!important; border:none!important; }
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
@media (max-width: 900px) {
  .ui-brand-header { border-radius: 12px 12px 0 0; padding: 0.6rem 0.75rem; }
  .ui-brand-main-title { font-size: 1.12rem; }
  .ui-brand-tagline { font-size: 0.78rem; }
  .ui-studio-deck { border-radius: 12px; }
  .ui-global-bar { position: relative; top: 0; padding: 0.55rem 0.6rem; }
  .ui-studio-nav { padding: 0.4rem 0.45rem; }
  .ui-studio-nav .nav-btn button { font-size: 0.68rem !important; padding: 0.32rem 0.2rem !important; }
  .ui-now-playing .np-title { font-size: 0.9rem; }
  .ui-section-jump { top: 0.25rem; }
  .lead-grid { grid-template-columns: repeat(2, minmax(88px, 1fr)) !important; }
}
</style>
        """,
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


def sidebar_source_banner(markdown_text: str) -> None:
    import streamlit as st

    st.sidebar.markdown(
        f'<div class="ui-source-banner">{markdown_text}</div>',
        unsafe_allow_html=True,
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
    key_prefix: str = "page",
) -> str:
    """Compact navigation bar at the top of each major page."""
    import streamlit as st

    current = ensure_studio_page(session_state, default=current_page)
    st.markdown(
        '<p class="ui-page-nav-label">Quick navigation</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ui-studio-nav ui-page-nav">', unsafe_allow_html=True)
    cols = st.columns(len(STUDIO_PAGES))
    for col, (page_id, label) in zip(cols, STUDIO_PAGES):
        nav_class = STUDIO_PAGE_META.get(page_id, {}).get("nav_class", page_id)
        with col:
            st.markdown(f'<div class="nav-btn nav-{nav_class}">', unsafe_allow_html=True)
            if st.button(
                label,
                key=f"{key_prefix}_nav_{page_id}",
                use_container_width=True,
                type="primary" if page_id == current else "secondary",
            ):
                if page_id != current:
                    session_state["studio_page"] = page_id
                    rerun_fn()
            st.markdown("</div>", unsafe_allow_html=True)
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
        st.sidebar.markdown(
            f'<div class="sb-nav-btn sb-nav-{nav_class}">',
            unsafe_allow_html=True,
        )
        if st.sidebar.button(
            label,
            key=f"sb_nav_{page_id}",
            use_container_width=True,
            type="primary" if page_id == current else "secondary",
        ):
            if page_id != current:
                session_state["studio_page"] = page_id
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
        with col:
            st.markdown(f'<div class="cross-{nav_class}">', unsafe_allow_html=True)
            if st.button(
                label,
                key=f"{key_prefix}_to_{page_id}",
                use_container_width=True,
            ):
                session_state["studio_page"] = page_id
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
            ss["studio_page"] = "picker"
            rerun_fn()
        st.markdown("</div>", unsafe_allow_html=True)
    with row2[4]:
        st.markdown('<div class="ui-quick-nav">', unsafe_allow_html=True)
        if rerun_fn and st.button("Practice", key="global_nav_practice", use_container_width=True, help="Practice page"):
            ss["studio_page"] = "practice"
            rerun_fn()
        st.markdown("</div>", unsafe_allow_html=True)
    with row2[5]:
        st.markdown('<div class="ui-quick-nav">', unsafe_allow_html=True)
        if rerun_fn and st.button("Backing", key="global_nav_backing", use_container_width=True, help="Backing track"):
            ss["studio_page"] = "backing"
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
    """Sticky quick-jump chips for verse / chorus / bridge / outro."""
    import streamlit as st

    names = [n for n in section_names if n]
    if not names:
        return None
    current = session_state.get(state_key)
    if current not in names:
        session_state[state_key] = names[0]
        current = names[0]
    st.markdown(
        '<div class="ui-section-jump"><p class="ui-bar-label">Form sections</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(min(len(names), 6))
    for col, name in zip(cols, names[:6]):
        with col:
            st.markdown('<div class="jump-btn">', unsafe_allow_html=True)
            if st.button(
                _short_section_label(name),
                key=f"sec_jump_{state_key}_{name}",
                use_container_width=True,
                type="primary" if name == current else "secondary",
                help=name,
            ):
                session_state[state_key] = name
                if rerun_fn:
                    rerun_fn()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return session_state.get(state_key)


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
