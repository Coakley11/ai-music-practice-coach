"""Streamlit hook for the Custom Progressions "Suggested Next Chord" assistance area.

Logic lives in :mod:`custom_chord_suggest`; this module only gathers the editing context from the
CPL session and renders. "Use" buttons go through ``cpl_on_pick_chord_callback`` (an ``on_click``
callback), so no session-state key of an instantiated widget is ever assigned. The chord becomes the
section's PENDING chord (the editor's existing step 2 "Choose duration" commits it), so an existing
chord is never overwritten and no duration is guessed.
"""

from __future__ import annotations

import html
from typing import Any

SUGGEST_BUTTON_PREFIX = "cpl_pick_suggest_"  # ephemeral widget prefix (see CPL_EPHEMERAL_WIDGET_PREFIXES)
_ORDER = ("Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Solo", "Outro")
_INTENT_LABEL = {"continue": "keeps the harmony moving", "tension": "builds tension", "resolve": "resolves"}


def gather_suggestion_context(active: dict, practice_key: str, edit_section: str,
                              pending: str | None = None) -> dict[str, Any]:
    """Practice-Key chords of the edited section (+ pending), bars entered and preceding sections."""
    from custom_progression_lab import display_entries_for_section, is_repeat_entry

    entries = display_entries_for_section(active, practice_key, edit_section)
    chords = [str(e.get("chord") or "") for e in entries if not is_repeat_entry(e) and e.get("chord")]
    bars = sum(max(1, int(e.get("bars", 1) or 1)) for e in entries)
    if pending:
        chords.append(str(pending))
        bars += 1
    previous: list[tuple[str, list[str]]] = []
    if edit_section in _ORDER:
        for name in _ORDER[: _ORDER.index(edit_section)]:
            prev_entries = display_entries_for_section(active, practice_key, name)
            prev_chords = [str(e.get("chord") or "") for e in prev_entries if not is_repeat_entry(e) and e.get("chord")]
            if prev_chords:
                previous.append((name, prev_chords))
    return {"chords": chords, "bars": bars, "previous": previous}


def compute_suggestion(active: dict, practice_key: str, edit_section: str, style: str,
                       pending: str | None = None) -> dict[str, Any]:
    from custom_chord_suggest import suggest_next_chord

    ctx = gather_suggestion_context(active, practice_key, edit_section, pending)
    return suggest_next_chord(
        practice_key, None, style, edit_section, ctx["chords"], ctx["previous"], bars=ctx["bars"] or None
    )


def suggest_label(chord: Any) -> str:
    return f"🎼 Suggested Next Chord: {chord}" if chord else "🎼 Suggested Next Chord"


def render_next_chord_suggestion(st: Any, *, active: dict, practice_key: str, edit_section: str,
                                 style: str, pending_chord: str | None) -> dict[str, Any] | None:
    """Render the suggestion area; returns the suggestion dict (None if the engine fails)."""
    from custom_progression_lab import cpl_on_pick_chord_callback

    try:
        sug = compute_suggestion(active, practice_key, edit_section, style, pending_chord)
    except Exception:  # never break the editor over an assistance widget
        return None
    with st.container(key="cpl_suggest_next"):
        chord = sug.get("chord")
        # Collapsed by default (compact on phones); the label carries the answer so the
        # explanation and the insert controls are one tap away, not on screen all the time.
        with st.expander(suggest_label(chord), expanded=False):
            if pending_chord:
                st.caption(
                    f"Pending chord **{html.escape(str(pending_chord))}** is waiting for a duration "
                    "(step 2 below). The suggestion after it:"
                )
            if chord:
                roman = html.escape(str(sug.get("roman") or ""))
                st.markdown(
                    f'<div class="cpl-suggest-line"><strong style="font-size:1.35rem">{html.escape(chord)}</strong> '
                    f'<span class="cpl-roman-label">{roman}</span> '
                    f'<span class="cpl-suggest-intent">· {_INTENT_LABEL.get(sug.get("intent"), "")}</span></div>',
                    unsafe_allow_html=True,
                )
            st.caption(str(sug.get("reason") or ""))
            alts = list(sug.get("alternatives") or [])[: (3 if chord else 2)]
            cols = st.columns((2 if chord else 0) + len(alts)) if (chord or alts) else []
            idx = 0
            if chord:
                with cols[0]:
                    st.button(
                        f"Use {chord}",
                        key=f"{SUGGEST_BUTTON_PREFIX}use_{edit_section}",
                        on_click=cpl_on_pick_chord_callback,
                        args=(chord,),
                        type="primary",
                        use_container_width=True,
                        disabled=bool(pending_chord),
                        help="Adds it as the pending chord; you choose the duration.",
                    )
                idx = 2
            for i, alt in enumerate(alts):
                with cols[idx + i]:
                    st.button(
                        str(alt["chord"]),
                        key=f"{SUGGEST_BUTTON_PREFIX}alt_{edit_section}_{i}",
                        on_click=cpl_on_pick_chord_callback,
                        args=(str(alt["chord"]),),
                        use_container_width=True,
                        disabled=bool(pending_chord),
                        help=f"Alternative ({alt.get('roman', '')})",
                    )
    return sug
