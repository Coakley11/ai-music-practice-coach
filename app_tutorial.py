"""First-time user guided tour for the music practice studio."""

from __future__ import annotations

import html
from typing import Any, Callable

TUTORIAL_DISMISSED_KEY = "tutorial_dismissed"
TUTORIAL_OPEN_KEY = "tutorial_open"
TUTORIAL_STEP_KEY = "tutorial_step"
TUTORIAL_AUTO_PROMPTED_KEY = "tutorial_auto_prompted"

TOTAL_STEPS = 8

TUTORIAL_STEPS: list[dict[str, Any]] = [
    {
        "id": "picker",
        "page_id": "picker",
        "icon": "🎼",
        "title": "Song Selection",
        "bullets": [
            "Browse or search the catalog and **pick a song**.",
            "Check the **active song card** — genre, key, and chart level.",
            "Open **Practice** to work on chords, technique, and coaching tools.",
            "Open **Backing Track** when you are ready to play along.",
            "Optional: add **Lyrics & Cues** under the song card for practice and playback.",
        ],
        "tip": "Start with a song you know — familiarity helps you focus on the tools.",
    },
    {
        "id": "practice",
        "page_id": "practice",
        "icon": "🎯",
        "title": "Practice",
        "bullets": [
            "Set **instrument, level, and focus** in the sidebar or the quick controls in Practice Coach.",
            "Warm up with **Tuner & Tone Development**.",
            "Lock time with the **metronome** (full song or one section).",
            "Read the **full chord chart** for the song or section you are working on.",
            "Generate **notation / TAB** for focused reading.",
            "Use **Chord Finder / How to Play** and the chord coach for fingerings.",
            "Use **transpose / capo / instrument key** when you need a different key or guitar shapes.",
        ],
        "tip": "Use section focus (Verse, Chorus, etc.) to practice one part at a time.",
    },
    {
        "id": "backing",
        "page_id": "backing",
        "icon": "🎧",
        "title": "Backing Track",
        "bullets": [
            "Choose **full song** or a **single section** to loop.",
            "Check **BPM** and **groove** — they default from the active song.",
            "Press **Generate** to build the backing audio.",
            "Press **Play** to hear it (headphones recommended).",
            "Use **Stop Backing Track** when you are done.",
            "Adjust **Quick BPM** and section controls without leaving the page.",
        ],
        "tip": "Generate once, then tweak BPM in small steps (+4) when a section feels clean.",
    },
    {
        "id": "custom",
        "page_id": "custom",
        "icon": "✏️",
        "title": "Custom Progression",
        "bullets": [
            "Build **your own chord progression** from scratch.",
            "Choose **style and key** to match how you want to practice.",
            "Add chords to **verse, chorus, bridge**, and other sections.",
            "Press **Finish Song** when the form is ready.",
            "Open the result in **Backing Track** or **Practice** like any catalog song.",
        ],
        "tip": "Great for originals, exercises, or charts that are not in the library yet.",
    },
    {
        "id": "creative",
        "page_id": "creative",
        "icon": "🧠",
        "title": "Creative Lab",
        "bullets": [
            "Use your **active song** or **custom progression** as the harmony source.",
            "**Live Coach** — scales, chord tones, and tips for the chord you are on.",
            "**Phrase / Motif** — build and develop melodic ideas.",
            "Generate **sheet music / TAB** from motifs.",
            "**Transform motifs** — rhythm, inversion, and variation ideas.",
        ],
        "tip": "Open Improvisation Intelligence inside Creative Lab for the full improv workspace.",
    },
    {
        "id": "multitrack",
        "page_id": "multitrack",
        "icon": "🎚️",
        "title": "Multitrack",
        "bullets": [
            "Record or layer **multiple parts** (guitar, vocal, keys, etc.).",
            "Practice arranging ideas with more than one track.",
            "Review layers and balance before moving to **Upload Analysis**.",
        ],
        "tip": "Record the rhythm part first, then overdub melody or solo.",
    },
    {
        "id": "analysis",
        "page_id": "analysis",
        "icon": "🎙️",
        "title": "Upload Analysis",
        "bullets": [
            "**Upload a recording** (or use the mic if available).",
            "Run **AI coach analysis** on your take.",
            "Review **timing, pitch, tone, technique**, and musicality feedback.",
            "Read the **practice plan** the coach suggests for your next session.",
        ],
        "tip": "Results also feed **Practice Log** insights when you analyze your history.",
    },
    {
        "id": "log",
        "page_id": "log",
        "icon": "📓",
        "title": "Practice Log",
        "bullets": [
            "**Log practice sessions** — what you worked on and how it felt.",
            "Press **Analyze My Practice History** for AI-style patterns and trends.",
            "Get recommendations for **what to practice next**.",
        ],
        "tip": "Short notes after each session make the coach insights much smarter over time.",
    },
]

QUICK_START_STEPS: list[str] = [
    "Pick a song on **Song Selection**.",
    "Open **Practice** and set instrument, level, and focus.",
    "Open **Backing Track**.",
    "**Generate** the track, then **Play**.",
    "**Record** yourself and run **Upload Analysis** for feedback.",
]


def init_tutorial_state(session_state: dict) -> None:
    session_state.setdefault(TUTORIAL_DISMISSED_KEY, False)
    session_state.setdefault(TUTORIAL_OPEN_KEY, False)
    session_state.setdefault(TUTORIAL_STEP_KEY, 0)
    session_state.setdefault(TUTORIAL_AUTO_PROMPTED_KEY, False)


def maybe_auto_open_tutorial(session_state: dict) -> None:
    """Open the tour once for new users unless they dismissed it."""
    if session_state.get(TUTORIAL_DISMISSED_KEY):
        return
    if session_state.get(TUTORIAL_AUTO_PROMPTED_KEY):
        return
    session_state[TUTORIAL_AUTO_PROMPTED_KEY] = True
    session_state[TUTORIAL_OPEN_KEY] = True
    session_state[TUTORIAL_STEP_KEY] = 0


def open_tutorial(session_state: dict, *, step: int = 0) -> None:
    session_state[TUTORIAL_OPEN_KEY] = True
    session_state[TUTORIAL_STEP_KEY] = max(0, min(step, TOTAL_STEPS - 1))


def close_tutorial(session_state: dict) -> None:
    session_state[TUTORIAL_OPEN_KEY] = False


def dismiss_tutorial(session_state: dict) -> None:
    session_state[TUTORIAL_DISMISSED_KEY] = True
    session_state[TUTORIAL_OPEN_KEY] = False


def _clamp_step(step: int) -> int:
    return max(0, min(int(step), TOTAL_STEPS - 1))


def render_tutorial_sidebar_entry(
    sidebar: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Tutorial entry at the top of the sidebar."""
    import streamlit as st

    init_tutorial_state(session_state)
    sidebar.markdown(
        '<div class="tutorial-sidebar-entry">'
        '<p class="ui-sb-section tone-session">📖 Help</p></div>',
        unsafe_allow_html=True,
    )
    if sidebar.button(
        "First time here? Start Tutorial",
        key="tutorial_sidebar_start",
        use_container_width=True,
        type="primary",
    ):
        open_tutorial(session_state, step=0)
        rerun_fn()
    if sidebar.button(
        "Tutorial",
        key="tutorial_sidebar_open",
        use_container_width=True,
    ):
        open_tutorial(session_state, step=session_state.get(TUTORIAL_STEP_KEY, 0))
        rerun_fn()
    if not session_state.get(TUTORIAL_DISMISSED_KEY) and not session_state.get(TUTORIAL_OPEN_KEY):
        sidebar.caption("New here? The guided tour takes about 3 minutes.")


def _quick_start_html() -> str:
    return (
        "<ol class='tutorial-quick-start'>"
        "<li>Pick a song on <strong>Song Selection</strong>.</li>"
        "<li>Open <strong>Practice</strong> and set instrument, level, and focus.</li>"
        "<li>Open <strong>Backing Track</strong>.</li>"
        "<li><strong>Generate</strong> the track, then <strong>Play</strong>.</li>"
        "<li><strong>Record</strong> yourself and run <strong>Upload Analysis</strong> for feedback.</li>"
        "</ol>"
    )


def render_tutorial_walkthrough(
    st_module: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
    navigate_fn: Callable[[str], None] | None = None,
) -> None:
    """Full-page guided tour (call when tutorial_open is True)."""
    step = _clamp_step(session_state.get(TUTORIAL_STEP_KEY, 0))
    data = TUTORIAL_STEPS[step]
    progress_pct = int((step + 1) / TOTAL_STEPS * 100)

    st_module.markdown(
        f"""
<div class="tutorial-hero">
  <div class="tutorial-hero-head">
    <span class="tutorial-hero-icon">{data["icon"]}</span>
    <div>
      <p class="tutorial-kicker">Guided tour</p>
      <h2 class="tutorial-title">Welcome to your practice studio</h2>
      <p class="tutorial-sub">A friendly walkthrough — Step {step + 1} of {TOTAL_STEPS}</p>
    </div>
  </div>
  <div class="tutorial-progress-track" aria-hidden="true">
    <div class="tutorial-progress-fill" style="width:{progress_pct}%;"></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st_module.markdown(
        '<div class="tutorial-quick-card">'
        '<p class="tutorial-quick-title">⚡ Fastest way to start</p>'
        f"{_quick_start_html()}"
        "</div>",
        unsafe_allow_html=True,
    )

    st_module.markdown(
        f'<div class="tutorial-step-card">'
        f'<p class="tutorial-step-label">Step {step + 1} of {TOTAL_STEPS}</p>'
        f'<h3 class="tutorial-step-title">{data["icon"]} {html.escape(data["title"])}</h3>'
        f"</div>",
        unsafe_allow_html=True,
    )

    for bullet in data["bullets"]:
        st_module.markdown(f"- {bullet}")
    if data.get("tip"):
        st_module.info(data["tip"])

    nav1, nav2, nav3, nav4 = st_module.columns([1, 1, 1, 1])
    with nav1:
        if st_module.button(
            "← Back",
            key="tutorial_back",
            disabled=step <= 0,
            use_container_width=True,
        ):
            session_state[TUTORIAL_STEP_KEY] = step - 1
            rerun_fn()
    with nav2:
        _next_label = "Finish ✓" if step >= TOTAL_STEPS - 1 else "Next →"
        if st_module.button(
            _next_label,
            key="tutorial_next",
            type="primary",
            use_container_width=True,
        ):
            if step >= TOTAL_STEPS - 1:
                close_tutorial(session_state)
            else:
                session_state[TUTORIAL_STEP_KEY] = step + 1
            rerun_fn()
    with nav3:
        page_id = str(data.get("page_id") or "")
        if page_id and navigate_fn and st_module.button(
            f"Open {data['title']}",
            key="tutorial_go_page",
            use_container_width=True,
        ):
            navigate_fn(page_id)
    with nav4:
        if st_module.button(
            "Close",
            key="tutorial_close",
            use_container_width=True,
        ):
            close_tutorial(session_state)
            rerun_fn()

    st_module.divider()
    c1, c2 = st_module.columns(2)
    with c1:
        dismiss_key = "tutorial_dismiss_checkbox"
        if dismiss_key not in session_state:
            session_state[dismiss_key] = bool(session_state.get(TUTORIAL_DISMISSED_KEY))

        def _on_dismiss_toggle() -> None:
            session_state[TUTORIAL_DISMISSED_KEY] = bool(session_state.get(dismiss_key))

        st_module.checkbox(
            "Don't show again on startup",
            key=dismiss_key,
            on_change=_on_dismiss_toggle,
        )
    with c2:
        if st_module.button("Finish tour", key="tutorial_finish", use_container_width=True):
            close_tutorial(session_state)
            rerun_fn()

    st_module.caption(
        "Reopen anytime from the sidebar: **First time here? Start Tutorial** or **Tutorial**."
    )
