"""One selectable-button control for every "choose one of these" bar in the app.

Entry & Jam / Phrase-Motif / Missions already look like this (``creative_mode_nav``, Issue 60).
These bars still looked like a form - a row of radio dots:

  * Creative: Song-Based Improvisation / Style Jam Mode / Jam Session Generator (``improv_entry_mode``)
  * Practice: Section Focus - Full Song, Verse, Chorus, ... (``practice_focus_section``)
  * Backing:  Playback scope - Full Song or a group of sections (``backing_track_scope``)

They now draw the same way, through this one function. What it is careful NOT to change:

* **The widget key.** Every reader of these keys - persistence, restore traces, the page sync
  that follows a section pick - still finds the value it expects, in the same key.
* **The labels and icons.** ``format_func`` is passed straight through, so the three purple
  notes, the saxophone and the dice (``creative_tool_display_label``) and the section names are
  the ones the app already uses.
* **The on_change callback**, untouched.
* **"Always one selected".** A radio always has a selection; a segmented control can be clicked
  off. ``required=True`` stops that, and this module's own per-widget memory restores the last
  real choice if a runtime without ``required`` deselects anyway - the two failure modes Issue 60
  measured in the full app (an empty bar after reload, a reset to the first option on a click of
  the active segment). Unlike ``creative_mode_nav``'s single module-wide memory, each widget here
  has its own, so two bars on one page cannot overwrite each other's choice.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

__all__ = ["memory_key", "render_segmented_selector", "resolve_selection", "selector_css"]


def memory_key(key: str) -> str:
    return f"_segmented_last::{key}"


def selector_css(key: str) -> str:
    """Wrap rather than shrink or scroll sideways on a phone; scoped to this widget's key."""
    return f"""
<style>
.st-key-{key} [data-testid="stButtonGroup"] {{
  flex-wrap: wrap;
  gap: 0.25rem;
}}
.st-key-{key} [data-testid="stButtonGroup"] > div {{
  flex: 0 1 auto;
}}
.st-key-{key} [data-testid="stButtonGroup"] button {{
  min-height: 2.5rem;
}}
</style>
"""


def resolve_selection(selected: Any, previous: Any, options: Sequence[str]) -> str:
    """The active choice: what was clicked, else the last real choice, else the first option."""
    choice = str(selected or "").strip()
    if choice and choice in options:
        return choice
    kept = str(previous or "").strip()
    if kept and kept in options:
        return kept
    return str(options[0]) if options else ""


def _get(session_state: Any, key: str) -> str:
    try:
        return str(session_state.get(key) or "").strip()
    except Exception:
        return ""


def _set(session_state: Any, key: str, value: str) -> None:
    try:
        session_state[key] = value
    except Exception:
        pass


def render_segmented_selector(
    st: Any,
    session_state: Any,
    *,
    label: str,
    options: Sequence[str],
    key: str,
    format_func: Callable[[str], str] = str,
    on_change: Callable[..., Any] | None = None,
) -> str:
    """Draw ``options`` as selectable buttons under ``key`` and return the active one (never None).

    Falls back to ``st.radio`` - the control these bars used before - on a Streamlit without
    ``segmented_control``.
    """
    choices = [str(o) for o in options]
    if not choices:
        return ""
    previous = _get(session_state, memory_key(key)) or _get(session_state, key)
    if previous not in choices:
        previous = choices[0]

    control = getattr(st, "segmented_control", None)
    if control is None:
        return str(st.radio(label, choices, horizontal=True, key=key, format_func=format_func,
                            label_visibility="collapsed", on_change=on_change) or previous)
    try:
        st.markdown(selector_css(key), unsafe_allow_html=True)
    except Exception:
        pass
    # Seed the widget's own state before it is created (how a keyed widget gets its value): a
    # segmented control with no stored value would start with nothing selected.
    if _get(session_state, key) not in choices:
        _set(session_state, key, previous)
    kwargs = {"key": key, "format_func": format_func, "label_visibility": "collapsed", "on_change": on_change}
    try:
        selected = control(label, choices, required=True, **kwargs)
    except TypeError:
        selected = control(label, choices, **kwargs)
    active = resolve_selection(selected, previous, choices)
    if not str(selected or "").strip():
        _set(session_state, key, active)
    _set(session_state, memory_key(key), active)
    return active
