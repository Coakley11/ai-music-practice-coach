"""Issue 60 - the Creative Studio's mode selector.

Eight modes used to be eight radio buttons in a row. They work, and they look like a
form rather than navigation. This draws them as segments instead.

What this module is careful about is everything it does *not* change. The widget keeps
its key, so every reader of ``improv_intelligence_tab`` - the hydration trace, the tool
persistence, the workflow sync - still finds what it expects. It keeps its ``on_change``
callback, which releases Missions ownership, sets the entry mode and syncs navigation
history; losing that would silently strand the Creative page's state when a musician
switched mode. It keeps ``creative_tool_display_label``, so the labels and icons are the
ones the rest of the app already uses rather than a second set invented here. The
Creative engine itself is untouched.

**The behaviour change a segmented control brings, and the reason this is a function
rather than a one-line substitution.** ``st.radio`` always has a selection. In
single-select mode ``st.segmented_control`` does not: clicking the active segment
deselects it and the widget returns ``None``. Everything downstream assumes a mode is
set - ``sync_workflow_for_creative_tab`` would be handed "", which resolves to no owner,
and the page would lose its workflow pointer because somebody clicked the mode they were
already in. So a ``None`` here means "stay where you are", and the session value is put
back before anything else reads it.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

__all__ = [
    "CREATIVE_NAV_CSS",
    "LAST_MODE_KEY",
    "render_creative_mode_nav",
    "resolve_mode_selection",
]

# Where the last mode that was actually chosen is remembered.
#
# The widget's own key cannot serve: on the rerun that follows a deselection, Streamlit
# has *already* written ``None`` into it before this code runs, so reading it back gives
# the cleared value rather than the previous one. Measured in a browser - clicking the
# active segment sent the page to the first mode in the list instead of staying put,
# while every unit test passed, because a test supplies the previous value by hand and
# the real runtime does not.
LAST_MODE_KEY = "_creative_mode_nav_last"

# Eight labels do not fit one row on a phone. Wrapping them is readable; shrinking them
# or scrolling sideways is not, so the container is told it may wrap and each segment is
# allowed to keep its full text. Scoped to this widget's own key so no other control
# inherits it.
CREATIVE_NAV_CSS = """
<style>
.st-key-improv_intelligence_tab [data-testid="stButtonGroup"] {
  flex-wrap: wrap;
  gap: 0.25rem;
}
.st-key-improv_intelligence_tab [data-testid="stButtonGroup"] > div {
  flex: 0 1 auto;
}
</style>
"""
# Deliberately no font-size rule. An earlier draft shrank the labels below 420px; the
# measurements say it is not needed and was not even taking effect - at 390 and 360 the
# segments wrap to four rows at the full 14px, nothing truncates and nothing scrolls
# sideways. Shrinking text that already fits only makes it harder to read.


def resolve_mode_selection(
    selected: Any,
    previous: Any,
    options: Sequence[str],
) -> str:
    """The mode that is actually active, given what the widget returned.

    ``selected`` is ``None`` when the musician clicked the segment that was already
    active. That is a deselection to the widget and a no-op to this page: the previous
    mode stays. Falls back to the first option only when there is no previous mode to
    keep, which is the first render.
    """
    choice = str(selected or "").strip()
    if choice:
        return choice
    kept = str(previous or "").strip()
    if kept and kept in options:
        return kept
    return str(options[0]) if options else ""


def render_creative_mode_nav(
    st: Any,
    session_state: Any,
    *,
    options: Sequence[str],
    key: str,
    format_func: Callable[[str], str],
    on_change: Callable[[], None] | None = None,
) -> str:
    """Draw the mode selector and return the active mode. Never returns ``None``.

    Falls back to ``st.radio`` when the installed Streamlit has no segmented control, so
    the page still renders on an older runtime rather than failing to draw at all.
    """
    choices = [str(o) for o in options]
    previous = _remembered(session_state, key, choices)

    control = getattr(st, "segmented_control", None)
    if control is None:
        return str(
            st.radio(
                "Improvisation section", choices, horizontal=True, key=key,
                format_func=format_func, label_visibility="collapsed",
                on_change=on_change,
            )
            or previous
        )

    try:
        st.markdown(CREATIVE_NAV_CSS, unsafe_allow_html=True)
    except Exception:
        pass

    # Seed the widget's own state *before* it is created, which is how a keyed
    # Streamlit widget is given its starting value. Two full-app failures came from
    # not doing this, and neither showed up in an isolated harness:
    #
    #   - after a reload no segment appeared selected at all, because a segmented
    #     control with no stored value starts empty where a radio starts on its first
    #     option;
    #   - clicking the active segment reset the page to Entry & Jam, because the
    #     deselection reached session state before this code ran and the restore
    #     afterwards was too late for anything that had already read the key.
    #
    # Seeding first makes a deselection simply not happen: the frontend clears the
    # value, this puts the remembered mode back, and the widget renders still on it.
    if _stored(session_state, key) not in choices:
        _restore(session_state, key, previous)

    # ``required`` stops the widget deselecting at all, which is the only fix that
    # works: repairing the value afterwards is too late, because the page's own
    # on_change callback and its hydration run against the cleared key before this
    # function sees it. Measured in the full app - with the repair alone, clicking the
    # active segment still landed the page on Entry & Jam.
    kwargs = {
        "key": key,
        "format_func": format_func,
        "label_visibility": "collapsed",
        "on_change": on_change,
    }
    try:
        selected = control("Improvisation section", choices, required=True, **kwargs)
    except TypeError:
        # An older Streamlit without ``required``: fall back and rely on the repair.
        selected = control("Improvisation section", choices, **kwargs)
    active = resolve_mode_selection(selected, previous, choices)
    if not str(selected or "").strip():
        # Put the kept mode back, because the widget has already written None into
        # session state and the next reader of this key is not this function.
        _restore(session_state, key, active)
    _restore(session_state, LAST_MODE_KEY, active)
    return active


def _stored(session_state: Any, key: str) -> str:
    try:
        return str(session_state.get(key) or "").strip()
    except Exception:
        return ""


def _remembered(session_state: Any, key: str, choices: Sequence[str]) -> str:
    """The mode to fall back on: this module's memory first, the widget second.

    Order matters. On a deselect rerun the widget's key already holds ``None``, so it
    has to be the second source, not the first.
    """
    for candidate in (LAST_MODE_KEY, key):
        try:
            value = str(session_state.get(candidate) or "").strip()
        except Exception:
            value = ""
        if value in choices:
            return value
    return str(choices[0]) if choices else ""


def _restore(session_state: Any, key: str, value: str) -> None:
    try:
        session_state[key] = value
    except Exception:
        pass
