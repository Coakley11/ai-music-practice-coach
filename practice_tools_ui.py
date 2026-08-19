"""Practice page — compact tool launcher and active-tool workspace chrome."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Callable

from music_feature_icons import FEATURE_ICONS

PRACTICE_ACTIVE_TOOL_KEY = "practice_active_tool"
PRACTICE_TIME_PITCH_TOOL_ID = "time_and_pitch"
PRACTICE_TIME_PITCH_VIEW_KEY = "practice_time_pitch_view"
# Legacy session key (metronome | tuner | tone) — read only for migration.
PRACTICE_TIME_PITCH_MODE_KEY = "practice_time_pitch_mode"

# Legacy Streamlit tab labels → tool ids (for one-time migration).
_LEGACY_TAB_TO_TOOL: dict[str, str] = {
    "Coach": "coach",
    "Timing": "time_and_pitch",
    "Chart / TAB": "chart",
    "Lyrics": "lyrics",
    "Transpose / Instrument": "transpose",
    "Transpose helpers": "transpose",
    "Tuner, Tone & Metronome": "time_and_pitch",
    "Tuner & tone": "time_and_pitch",
    "Metronome & rhythm": "time_and_pitch",
}

_LEGACY_TOOL_IDS: dict[str, str] = {
    "timing": "time_and_pitch",
    "tuner": "time_and_pitch",
}


@dataclass(frozen=True)
class PracticeToolDef:
    tool_id: str
    label: str
    icon: str
    group: str
    blurb: str


PRACTICE_TOOL_GROUPS: tuple[str, ...] = (
    "Harmony & technique",
    "Time & pitch",
    "Charts & lyrics",
    "Reference",
)

PRACTICE_TOOLS: tuple[PracticeToolDef, ...] = (
    PracticeToolDef(
        "coach",
        "Chord & song coach",
        FEATURE_ICONS["chord_song_coach"],
        "Harmony & technique",
        "Section focus, scales, chord coach, and session exercises.",
    ),
    PracticeToolDef(
        "time_and_pitch",
        "Metronome, Tuner & Tone",
        f"{FEATURE_ICONS['timing_tempo_metronome']} {FEATURE_ICONS['pitch_tone_tuner']}",
        "Time & pitch",
        "Metronome click, live tuner, and sustain-tone reference in one place.",
    ),
    PracticeToolDef(
        "chart",
        "Chart & notation",
        "📋",
        "Charts & lyrics",
        "Chord chart, generated notation, and TAB.",
    ),
    PracticeToolDef(
        "lyrics",
        "Lyrics & phrasing",
        "🎤",
        "Charts & lyrics",
        "Lyric sheets, learning video, and phrasing guide.",
    ),
    PracticeToolDef(
        "transpose",
        "Transpose helpers",
        FEATURE_ICONS["transpose_helpers"],
        "Reference",
        "Capo and transpose calculators — global key stays in Practice setup above.",
    ),
)

_TOOLS_BY_ID: dict[str, PracticeToolDef] = {t.tool_id: t for t in PRACTICE_TOOLS}


def normalize_practice_active_tool(session: dict[str, Any]) -> str:
    raw = str(session.get(PRACTICE_ACTIVE_TOOL_KEY) or "").strip()
    if raw in _LEGACY_TOOL_IDS:
        raw = _LEGACY_TOOL_IDS[raw]
        session[PRACTICE_ACTIVE_TOOL_KEY] = raw
    if raw in _TOOLS_BY_ID:
        return raw
    legacy = _LEGACY_TAB_TO_TOOL.get(raw)
    if legacy:
        session[PRACTICE_ACTIVE_TOOL_KEY] = legacy
        return legacy
    if raw:
        session.pop(PRACTICE_ACTIVE_TOOL_KEY, None)
    return ""


def inject_practice_tools_styles() -> str:
    return """
<style>
.st-key-practice_toolkit_panel{
  border:1px solid rgba(148,163,184,.26);border-radius:16px;
  background:linear-gradient(180deg,rgba(255,255,255,.97),rgba(248,250,252,.95));
  box-shadow:0 14px 30px rgba(15,23,42,.08);padding:.85rem .9rem .75rem;margin:.45rem 0 .65rem;
}
.ui-practice-tools-head{margin:0 0 .45rem;}
.ui-practice-tools-title{margin:0;font-size:1.02rem;font-weight:850;color:#0f172a;}
.ui-practice-tools-desc{margin:.2rem 0 0;font-size:.82rem;color:#64748b;line-height:1.45;}
.ui-practice-tools-group{margin:.55rem 0 .15rem;font-size:.72rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#94a3b8;}
.ui-practice-tool-launcher{display:flex;flex-wrap:wrap;gap:.4rem;margin:.35rem 0 .5rem;}
.ui-practice-tool-chip{
  display:inline-flex;align-items:center;gap:.35rem;border:1px solid rgba(148,163,184,.32);
  border-radius:12px;padding:.38rem .62rem;background:#fff;color:#1e293b;font-size:.78rem;font-weight:750;
  cursor:pointer;min-height:2.35rem;line-height:1.2;
}
.ui-practice-tool-chip-active{
  border-color:rgba(59,130,246,.55)!important;
  background:linear-gradient(140deg,rgba(59,130,246,.12),rgba(14,165,233,.08))!important;
  box-shadow:0 0 0 1px rgba(59,130,246,.15);
}
.ui-practice-tool-workspace{
  border:1px solid rgba(59,130,246,.22);border-radius:14px;background:rgba(255,255,255,.96);
  padding:.65rem .75rem .55rem;margin:.25rem 0 .35rem;
}
.ui-practice-tool-workspace-head{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:.5rem;margin-bottom:.45rem;}
.ui-practice-tool-workspace-title{margin:0;font-size:.95rem;font-weight:820;color:#0f172a;}
.ui-practice-tool-workspace-blurb{margin:.12rem 0 0;font-size:.78rem;color:#64748b;}
.ui-practice-tool-context{
  font-size:.76rem;color:#475569;line-height:1.45;margin:.35rem 0 .45rem;
  padding:.4rem .55rem;border-radius:10px;background:#f8fafc;border:1px solid rgba(148,163,184,.2);
}
@media (max-width: 640px){
  .ui-practice-tool-launcher{flex-direction:column;}
  .ui-practice-tool-chip{width:100%;justify-content:flex-start;}
  .st-key-practice_toolkit_panel [data-testid="column"]{width:100%!important;flex:1 1 100%!important;}
}
</style>
"""


def render_practice_tools_header(st_module: Any) -> None:
    st_module.markdown(
        '<div class="ui-practice-tools-head">'
        '<p class="ui-practice-tools-title">Practice tools</p>'
        "<p class=\"ui-practice-tools-desc\">"
        "Open a focused tool without leaving your current song and practice setup."
        "</p></div>",
        unsafe_allow_html=True,
    )


def render_practice_tools_launcher(
    st_module: Any,
    session: dict[str, Any],
    *,
    on_select: Callable[[], None] | None = None,
) -> str:
    """Compact launcher; returns active tool id (empty = none)."""
    active = normalize_practice_active_tool(session)
    current_group = ""
    cols_per_row = 2
    try:
        import streamlit as st

        if hasattr(st_module, "columns"):
            # Desktop: two columns of chips; mobile CSS stacks full width.
            pass
    except ImportError:
        pass

    for group in PRACTICE_TOOL_GROUPS:
        tools = [t for t in PRACTICE_TOOLS if t.group == group]
        if not tools:
            continue
        st_module.markdown(
            f'<p class="ui-practice-tools-group">{html.escape(group)}</p>',
            unsafe_allow_html=True,
        )
        row_tools = list(tools)
        for i in range(0, len(row_tools), cols_per_row):
            chunk = row_tools[i : i + cols_per_row]
            cols = st_module.columns(len(chunk))
            for col, tool in zip(cols, chunk):
                with col:
                    is_active = active == tool.tool_id
                    label = f"{tool.icon} {tool.label}"
                    if st_module.button(
                        label,
                        key=f"practice_tool_pick_{tool.tool_id}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        if active == tool.tool_id:
                            try:
                                from practice_workspace_persistence import persist_practice_tool_user_action

                                persist_practice_tool_user_action(st_module, "")
                            except ImportError:
                                session[PRACTICE_ACTIVE_TOOL_KEY] = ""
                        else:
                            try:
                                from practice_workspace_persistence import persist_practice_tool_user_action

                                persist_practice_tool_user_action(
                                    st_module,
                                    tool.tool_id,
                                )
                            except ImportError:
                                try:
                                    from practice_workspace_persistence import commit_practice_tool_selection

                                    commit_practice_tool_selection(session, tool.tool_id)
                                except ImportError:
                                    pass
                        if on_select:
                            on_select()
                        else:
                            st_module.rerun()
    return normalize_practice_active_tool(session)


def render_practice_tool_workspace_header(
    st_module: Any,
    session: dict[str, Any],
    *,
    tool_id: str,
    context_line: str,
    on_close: Callable[[], None] | None = None,
) -> None:
    tool = _TOOLS_BY_ID.get(tool_id)
    if not tool:
        return
    st_module.markdown('<div class="ui-practice-tool-workspace">', unsafe_allow_html=True)
    h1, h2 = st_module.columns([5, 1])
    with h1:
        st_module.markdown(
            f'<p class="ui-practice-tool-workspace-title">{html.escape(tool.icon)} '
            f"{html.escape(tool.label)}</p>"
            f'<p class="ui-practice-tool-workspace-blurb">{html.escape(tool.blurb)}</p>',
            unsafe_allow_html=True,
        )
    with h2:
        if st_module.button("Close", key="practice_tool_close_btn", use_container_width=True):
            session[PRACTICE_ACTIVE_TOOL_KEY] = ""
            try:
                from practice_workspace_persistence import persist_practice_tool_user_action

                persist_practice_tool_user_action(st_module, "")
            except ImportError:
                pass
            if on_close:
                on_close()
            else:
                st_module.rerun()
    if context_line.strip():
        st_module.markdown(
            f'<div class="ui-practice-tool-context">{context_line}</div>',
            unsafe_allow_html=True,
        )


def close_practice_tool_workspace(st_module: Any) -> None:
    st_module.markdown("</div>", unsafe_allow_html=True)


def practice_tool_context_line(
    *,
    song: str,
    section_label: str,
    instrument: str,
    level: str,
    focus: str,
    chart_key: str,
    bpm: int,
    concert_key: str = "",
    written_mode: bool = False,
) -> str:
    parts = [
        f"<strong>{html.escape(song)}</strong>",
        f"Section: {html.escape(section_label or 'Full song')}",
        f"{html.escape(instrument)} · {html.escape(level)} · {html.escape(focus)}",
        f"Chart key <strong>{html.escape(chart_key)}</strong>",
        f"{int(bpm)} BPM",
    ]
    if written_mode and concert_key:
        parts.append(f"Concert {html.escape(concert_key)}")
    return " · ".join(parts)


def render_practice_tools_shell(
    st_module: Any,
    session: dict[str, Any],
    *,
    context_line: str,
    render_tool_body: Callable[[str], None],
) -> None:
    """Header + launcher + optional workspace body for the active tool only."""
    with st_module.container(key="practice_toolkit_panel"):
        render_practice_tools_header(st_module)
        active = render_practice_tools_launcher(st_module, session)
        if not active:
            st_module.caption("Choose a tool above — your song, section, and setup stay as they are.")
            return
        render_practice_tool_workspace_header(
            st_module,
            session,
            tool_id=active,
            context_line=context_line,
        )
        render_tool_body(active)
        close_practice_tool_workspace(st_module)
