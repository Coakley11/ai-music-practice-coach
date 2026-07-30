"""Deep Harmonic Analyzer — single guided-lesson UI for all app entry points."""

from __future__ import annotations

import html
from typing import Any

from improvisation_intelligence import ImprovSessionContext


def _render_deep_harmonic_callout(st: Any, kind: str, body: str) -> None:
    labels = {
        "goal": "🎯 Today's Goal",
        "try": "🎹 Try This",
        "listen": "👂 Listen For",
        "mistake": "⭐ Common Beginner Mistake",
        "tip": "💡 Pro Tip",
    }
    title = labels.get(kind, "💡 Note")
    st.markdown(
        f'<div class="dh-callout dh-{kind}">'
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{body}</p></div>",
        unsafe_allow_html=True,
    )


def _render_go_deeper_section(
    st: Any,
    deep: list[dict],
    *,
    expanded: bool = False,
    expander_key: str = "dh_go_deeper_root",
) -> None:
    """Single expander; nested expanders are unreliable in Streamlit."""
    with st.expander("Go deeper", expanded=expanded, key=expander_key):
        st.caption(
            "Harmonic character, instrument playbook, tension maps, scale pools, "
            "and section reference."
        )
        if not deep:
            st.info(
                "Load a song with chord changes to unlock the reference sections here."
            )
            return
        for block in deep:
            title = str(block.get("title") or "Detail")
            md = str(block.get("markdown") or "").strip()
            if not md:
                continue
            st.markdown(f"#### {html.escape(title)}")
            st.markdown(md)


def render_deep_harmonic_lesson(st: Any, session_state: dict, lesson: dict) -> None:
    st.markdown(
        """
<style>
.dh-callout{border-radius:12px;padding:0.75rem 0.95rem;margin:0.55rem 0 0.85rem;
  border:1px solid rgba(99,102,241,0.25);background:#f8fafc;}
.dh-callout p{margin:0.35rem 0 0;font-size:0.9rem;line-height:1.5;color:#334155;}
.dh-callout.dh-goal{background:#eff6ff;border-color:#93c5fd;}
.dh-callout.dh-try{background:#f0fdf4;border-color:#86efac;}
.dh-callout.dh-mistake{background:#fffbeb;border-color:#fcd34d;}
.dh-priority-list{margin:0.25rem 0 0.85rem;padding-left:1.15rem;}
.dh-priority-list li{margin:0.35rem 0;line-height:1.45;}
.dh-step-meta{font-size:0.82rem;color:#64748b;margin-bottom:0.35rem;}
</style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"*{lesson.get('greeting', '')}*")
    st.caption(str(lesson.get("meta") or ""))

    st.markdown("##### Start here — the ideas that matter most")
    st.markdown("<ul class='dh-priority-list'>", unsafe_allow_html=True)
    for line in lesson.get("priorities") or []:
        st.markdown(f"<li>{line}</li>", unsafe_allow_html=True)
    st.markdown("</ul>", unsafe_allow_html=True)

    steps = list(lesson.get("steps") or [])
    total = len(steps)
    step_key = "deep_harmony_lesson_step"
    step_idx = int(session_state.get(step_key) or 0)
    step_idx = max(0, min(step_idx, max(0, total - 1)))
    session_state[step_key] = step_idx
    show_bottom_go_deeper = True

    if total:
        st.markdown("##### Learn step by step")
        c_prev, c_mid, c_next = st.columns([1, 2, 1])
        with c_prev:
            if st.button("← Previous", key="dh_step_prev", disabled=step_idx <= 0, use_container_width=True):
                session_state[step_key] = step_idx - 1
                st.rerun()
        with c_mid:
            st.markdown(
                f"<p class='dh-step-meta'>Step {step_idx + 1} of {total}</p>",
                unsafe_allow_html=True,
            )
        with c_next:
            if st.button(
                "Next →",
                key="dh_step_next",
                disabled=step_idx >= total - 1,
                use_container_width=True,
            ):
                session_state[step_key] = step_idx + 1
                st.rerun()

        cur = steps[step_idx]
        st.markdown(f"**{cur.get('title', 'Step')}**")
        st.markdown(str(cur.get("body") or ""))
        for co in cur.get("callouts") or []:
            _render_deep_harmonic_callout(st, str(co.get("kind") or "tip"), str(co.get("body") or ""))

        deep = list(lesson.get("deep_dive") or [])
        step_text = f"{cur.get('title', '')} {cur.get('body', '')}".lower()
        if "go deeper" in step_text:
            _render_go_deeper_section(st, deep, expanded=True, expander_key="dh_go_deeper_inline")
            show_bottom_go_deeper = False

    loop = lesson.get("loop") or {}
    if loop.get("chords"):
        chips = " · ".join(html.escape(c) for c in loop["chords"])
        rep = " (repeats across the form)" if loop.get("repeating") else ""
        st.caption(f"Main loop: **{chips}**{rep}")

    if show_bottom_go_deeper:
        deep = list(lesson.get("deep_dive") or [])
        st.markdown("---")
        _render_go_deeper_section(st, deep, expanded=False, expander_key="dh_go_deeper_footer")


def render_deep_harmonic_analyzer_tab(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    song_data: dict,
    genre: str,
    key_prefix: str = "improv_deep_harmony",
) -> None:
    """Canonical Deep Harmonic Analyzer UI — Creative Lab, II Deep Harmony, and future entry points."""
    from deep_harmonic_analyzer import HarmonicAnalysisInput, build_deep_harmonic_lesson
    from practice_setup_controls import (
        DEFAULT_INSTRUMENT_OPTIONS,
        render_setup_quick_controls,
    )

    st.markdown("#### Deep Harmonic Analyzer")
    st.caption("A guided lesson — one step at a time, like a private teacher.")

    live_inst, live_level, live_focus = render_setup_quick_controls(
        st,
        session_state=session_state,
        key_prefix=key_prefix,
        instrument_options=DEFAULT_INSTRUMENT_OPTIONS,
        label="",
        show_sync_caption=True,
    )

    ext = song_data.get("extensions") or {}
    lesson = build_deep_harmonic_lesson(
        HarmonicAnalysisInput(
            song_title=improv_ctx.song_title,
            artist=improv_ctx.artist,
            key_center=improv_ctx.key_center,
            display_key=improv_ctx.display_key,
            sections=improv_ctx.sections,
            section_order=list(improv_ctx.section_order or []),
            instrument=live_inst,
            level=live_level,
            focus=live_focus,
            genre=genre or improv_ctx.style_label,
            bpm=improv_ctx.bpm,
            time_signature=str(ext.get("time_signature") or ""),
            arrangement_notes=str(ext.get("arrangement_notes") or ""),
            progression_flat=list(improv_ctx.progression_flat or []),
        )
    )
    render_deep_harmonic_lesson(st, session_state, lesson)


__all__ = [
    "render_deep_harmonic_analyzer_tab",
    "render_deep_harmonic_lesson",
]
