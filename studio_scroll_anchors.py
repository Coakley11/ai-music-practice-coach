"""Scroll-to-section helpers for internal page-jump buttons.

When a button on one studio page wants the user to land on a specific
working area of another page (not the top), it queues an *anchor id*
in session_state. The destination page then renders:

1. An invisible ``<div id="...">`` marker right before that working area.
2. A small one-shot JS script that scrolls the parent document to the
   anchor and clears the queued flag.

This module is intentionally tiny - no Streamlit imports at module
level, no song-catalog logic - so it can be imported from any UI
surface (active-song card, improv lab, practice page, etc.) without
pulling in heavy dependencies.

Usage
-----

Source button::

    set_pending_anchor(st.session_state, ANCHOR_BACKING_MAIN_CONTROLS)
    navigate_studio_page(st.session_state, "backing")
    st.rerun()

Destination page (somewhere near the working section)::

    render_scroll_anchor_marker(st, ANCHOR_BACKING_MAIN_CONTROLS)
    # ... the actual UI for that section ...

Once per page (anywhere - the script polls so order doesn't matter)::

    render_pending_scroll_script(st)

The script consumes the queued flag, so subsequent reruns of the
same page don't keep re-scrolling.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Anchor ids - one per "land here on jump" target across the app.
# Keep these short, lowercase, underscore-separated. They become DOM
# element ids on the destination pages, so they must be HTML-id-safe.
# ---------------------------------------------------------------------------

ANCHOR_CHOOSE_ACTIVE_SONG = "anchor_choose_active_song"
"""Song Selection page → just above the ``### Choose active song`` block."""

ANCHOR_LYRICS_EDITOR = "anchor_lyrics_editor"
"""Song Selection page → just above the Lyrics & Cues editor card."""

ANCHOR_CHART_EDITOR = "anchor_chart_editor"
"""Song Selection page → Edit Song Chart panel (chord bar editor)."""

ANCHOR_BACKING_MAIN_CONTROLS = "anchor_backing_main_controls"
"""Backing Track page → just above the Generate / Play / Stop card."""

ANCHOR_PRACTICE_COACH = "anchor_practice_coach"
"""Practice page → just above the practice setup + section/jump bar."""

ANCHOR_CHORD_COACH = "anchor_chord_coach"
"""Practice page → just above the Chord Coach / Chord Finder expander."""

ANCHOR_UPLOAD_ANALYSIS = "anchor_upload_analysis"
"""Upload Analysis page → main analysis controls area."""

ANCHOR_METRICS_AI = "anchor_metrics_ai"
"""Metrics & AI page → main metrics dashboard area."""

# All known anchors. Used by `set_pending_anchor` to validate values.
KNOWN_ANCHORS: frozenset[str] = frozenset(
    {
        ANCHOR_CHOOSE_ACTIVE_SONG,
        ANCHOR_LYRICS_EDITOR,
        ANCHOR_CHART_EDITOR,
        ANCHOR_BACKING_MAIN_CONTROLS,
        ANCHOR_PRACTICE_COACH,
        ANCHOR_CHORD_COACH,
        ANCHOR_UPLOAD_ANALYSIS,
        ANCHOR_METRICS_AI,
    }
)

PENDING_SCROLL_ANCHOR_KEY = "_pending_scroll_anchor"
"""Session-state key holding the queued anchor id (a string) or None."""


__all__ = (
    "ANCHOR_CHOOSE_ACTIVE_SONG",
    "ANCHOR_LYRICS_EDITOR",
    "ANCHOR_BACKING_MAIN_CONTROLS",
    "ANCHOR_PRACTICE_COACH",
    "ANCHOR_CHORD_COACH",
    "ANCHOR_UPLOAD_ANALYSIS",
    "ANCHOR_METRICS_AI",
    "KNOWN_ANCHORS",
    "PENDING_SCROLL_ANCHOR_KEY",
    "set_pending_anchor",
    "consume_pending_anchor",
    "peek_pending_anchor",
    "clear_pending_anchor",
    "render_scroll_anchor_marker",
    "render_pending_scroll_script",
)


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------


def set_pending_anchor(session_state: Any, anchor_id: str | None) -> None:
    """Queue ``anchor_id`` so the next page render scrolls to it.

    Passing ``None`` (or an empty string) clears the queue, which is
    handy when a navigation should land at the top of the destination.
    Unknown anchor ids are accepted silently - they just won't match
    any rendered marker, so the script will be a no-op.
    """
    if not anchor_id:
        clear_pending_anchor(session_state)
        return
    session_state[PENDING_SCROLL_ANCHOR_KEY] = str(anchor_id)


def peek_pending_anchor(session_state: Any) -> str | None:
    """Return the queued anchor id without consuming it."""
    val = session_state.get(PENDING_SCROLL_ANCHOR_KEY)
    return str(val) if val else None


def consume_pending_anchor(session_state: Any) -> str | None:
    """Return *and clear* the queued anchor id."""
    val = session_state.pop(PENDING_SCROLL_ANCHOR_KEY, None)
    return str(val) if val else None


def clear_pending_anchor(session_state: Any) -> None:
    session_state.pop(PENDING_SCROLL_ANCHOR_KEY, None)


# ---------------------------------------------------------------------------
# UI helpers (Streamlit only imported lazily so the module stays import-light)
# ---------------------------------------------------------------------------


def render_scroll_anchor_marker(st: Any, anchor_id: str) -> None:
    """Emit an invisible ``<div id="anchor_id">`` near a section header.

    ``scroll-margin-top`` is set so the smooth-scroll lands a bit below
    the sticky top bar instead of hiding the target behind it.
    """
    if not anchor_id:
        return
    st.markdown(
        f'<div id="{anchor_id}" '
        'style="position:relative;height:1px;width:1px;'
        'scroll-margin-top:5.5rem;"></div>',
        unsafe_allow_html=True,
    )


def render_pending_scroll_script(st: Any) -> None:
    """Inject a one-shot scroll script that targets the queued anchor.

    Safe to call once per page render even when nothing is queued
    (no-op in that case). The script:

    * runs inside a tiny invisible Streamlit ``components.html`` iframe
      and uses ``window.parent.document`` to reach the Streamlit app
      DOM (where the anchor markers live);
    * polls for up to ~3 seconds because Streamlit can render content
      asynchronously after the initial mount;
    * consumes the queued flag *before* injection so a subsequent
      rerun of the same page (e.g. user clicks a widget) doesn't keep
      re-scrolling.
    """
    anchor_id = consume_pending_anchor(getattr(st, "session_state", {}))
    if not anchor_id:
        return
    # Defence in depth: only allow HTML-id-safe characters so a future
    # caller can't inject script via the anchor id.
    safe = "".join(ch for ch in str(anchor_id) if ch.isalnum() or ch in "-_")
    if not safe:
        return
    try:
        import streamlit.components.v1 as components
    except ImportError:  # pragma: no cover - Streamlit always available in app
        return

    components.html(
        f"""
        <script>
        (function() {{
          const target = "{safe}";
          const tryScroll = () => {{
            try {{
              const doc = window.parent ? window.parent.document : document;
              const el = doc.getElementById(target);
              if (el) {{
                el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                return true;
              }}
            }} catch (e) {{ /* parent doc may be inaccessible during init */ }}
            return false;
          }};
          if (tryScroll()) return;
          let attempts = 0;
          const handle = setInterval(() => {{
            if (tryScroll() || ++attempts >= 30) {{
              clearInterval(handle);
            }}
          }}, 100);
        }})();
        </script>
        """,
        height=0,
    )
