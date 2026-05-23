"""Compact sidebar hints — short contextual tips only (not in-page tutorials)."""

from __future__ import annotations

from typing import Any


def _tuner_in_use(session_state: dict, key_prefix: str) -> bool:
    return any(str(k).startswith(key_prefix) for k in session_state)


def _practice_focus_is_section(session_state: dict) -> bool:
    focus = str(session_state.get("practice_focus_section") or "").strip().lower()
    return bool(focus) and focus not in ("full song", "full form")


def sidebar_context_hints(
    *,
    studio_page: str,
    session_state: dict,
    instrument: str,
) -> list[str]:
    """Return up to two short hint lines for the left sidebar."""
    page = str(studio_page or "practice").strip()

    if page == "practice":
        if _tuner_in_use(session_state, "practice_tuner"):
            return ["Play a sustained note and keep the pitch centered."]
        try:
            from instrument_transposition import (
                CHART_IN_INSTRUMENT_KEY_KEY,
                is_transposing_instrument,
            )

            if is_transposing_instrument(instrument):
                if session_state.get(CHART_IN_INSTRUMENT_KEY_KEY):
                    return ["Charts use your written instrument key."]
                return [
                    "Enable “Show charts in my instrument key” to transpose all charts.",
                ]
        except ImportError:
            pass
        if _practice_focus_is_section(session_state):
            return [
                "Loop the section with Metronome at a slow tempo first.",
                "Use Tuner & Tone to warm up pitch and tone.",
            ]
        return [
            "Open Chord Chart to review the song.",
            "Use Tuner & Tone to warm up pitch and tone.",
        ]

    if page == "backing":
        if session_state.get("_last_backing_wav"):
            return [
                "Use Quick BPM to adjust speed while practicing.",
                "Press Stop Backing Track to stop playback.",
            ]
        return [
            "Press Generate and Play to start playback.",
            "Use Quick BPM to adjust speed while practicing.",
        ]

    if page == "picker":
        return [
            "Choose a song, then open Practice or Backing Track.",
            "You can add lyrics or performance cues below the song card.",
        ]

    if page == "custom":
        return [
            "Add chords to build your progression.",
            "Press Finish Song when sections are ready.",
        ]

    if page == "analysis":
        if session_state.get("last_analysis_result"):
            return ["Review scores below and try the suggested practice plan."]
        return ["Upload a recording and run AI coach analysis."]

    if page == "creative":
        return ["Explore ideas here, then try them on the Practice page."]

    if page == "multitrack":
        return ["Record a layer, then review on Upload Analysis."]

    if page == "log":
        return ["Log sessions to track progress over time."]

    return []


def render_sidebar_context_hint(
    st: Any,
    *,
    studio_page: str,
    session_state: dict,
    instrument: str,
) -> None:
    """Small sidebar tip box — below Active Source, above Practice key."""
    import html

    hints = sidebar_context_hints(
        studio_page=studio_page,
        session_state=session_state,
        instrument=instrument,
    )
    if not hints:
        return
    body = "<br>".join(html.escape(line) for line in hints[:2])
    st.sidebar.markdown(
        f'<div class="ui-sidebar-hint">'
        f'<p class="ui-sidebar-hint-title">Tip</p>'
        f'<p class="ui-sidebar-hint-body">{body}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
