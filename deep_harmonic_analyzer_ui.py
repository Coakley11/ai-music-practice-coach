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


def _lesson_styles() -> str:
    return """
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
.dh-chord-row{display:flex;flex-wrap:wrap;gap:0.35rem;margin:0.5rem 0 0.75rem;}
.dh-chord-chip{display:inline-block;padding:0.2rem 0.55rem;border-radius:8px;
  background:linear-gradient(145deg,#6366f1,#4f46e5);color:#fff;font-weight:650;font-size:0.82rem;}
.dh-homework{border-radius:12px;padding:0.85rem 1rem;margin:1rem 0 0;
  border:1px solid #86efac;background:#f0fdf4;}
.dh-homework li{margin:0.35rem 0;line-height:1.45;}
.dh-section-nav button[kind="secondary"]{font-size:0.85rem;}
</style>
    """


def _render_chord_row(st: Any, chords: list[str]) -> None:
    if not chords:
        return
    try:
        from deep_harmonic_personalization import chord_tone_visual_html

        chips = "".join(chord_tone_visual_html(c) for c in chords[:8])
    except ImportError:
        chips = "".join(
            f'<span class="dh-chord-chip">{html.escape(str(c))}</span>' for c in chords[:8]
        )
    st.markdown(f'<div class="dh-chord-row">{chips}</div>', unsafe_allow_html=True)


def _render_reference_cards(
    st: Any,
    session_state: dict,
    cards: list[dict[str, Any]],
    *,
    key_prefix: str,
    expanded_inline: bool = False,
) -> None:
    if not cards:
        st.info("Load a song with chord changes to unlock reference sections here.")
        return

    for i, card in enumerate(cards):
        kind = str(card.get("kind") or "detail")
        title = str(card.get("title") or "Detail")
        exp_key = f"{key_prefix}_dh_card_{kind}_{i}"
        default_expanded = expanded_inline and kind == "character"

        if kind == "sections":
            sections = list(card.get("sections") or [])
            with st.expander(title, expanded=default_expanded, key=exp_key):
                st.caption("Pick one section — we'll focus there instead of dumping the whole form.")
                nav_key = f"{key_prefix}_dha_section_idx"
                idx = int(session_state.get(nav_key) or 0)
                idx = max(0, min(idx, max(0, len(sections) - 1)))
                session_state[nav_key] = idx
                if sections:
                    cols = st.columns(min(len(sections), 4))
                    for j, sec in enumerate(sections[:8]):
                        name = str(sec.get("name") or f"Section {j + 1}")
                        with cols[j % len(cols)]:
                            if st.button(
                                name,
                                key=f"{key_prefix}_dha_sec_{j}",
                                use_container_width=True,
                                type="primary" if j == idx else "secondary",
                            ):
                                session_state[nav_key] = j
                                st.rerun()
                    cur = sections[idx]
                    st.markdown(f"**{html.escape(str(cur.get('name') or ''))}**")
                    chord_line = str(cur.get("chords") or "")
                    if chord_line:
                        _render_chord_row(st, [c.strip() for c in chord_line.split("·")])
                    st.markdown(str(cur.get("markdown") or ""))
            continue

        md = str(card.get("markdown") or "").strip()
        if not md:
            continue
        with st.expander(title, expanded=default_expanded, key=exp_key):
            if kind == "tension":
                st.caption("Colored chips = chords in the loop; listen for pull vs. rest.")
                loop_chords = [
                    part.strip()
                    for part in md.replace("**", "").split()
                    if part.strip() and part.strip()[0].isalpha()
                ][:6]
                if loop_chords:
                    _render_chord_row(st, loop_chords)
            st.markdown(md)


def _render_homework(st: Any, homework: dict[str, Any]) -> None:
    title = str(homework.get("title") or "Today's Assignment")
    tasks = list(homework.get("tasks") or [])
    if not tasks:
        return
    items = "".join(f"<li>✓ {html.escape(str(t))}</li>" for t in tasks)
    st.markdown(
        f'<div class="dh-homework"><strong>{html.escape(title)}</strong>'
        f"<ul>{items}</ul></div>",
        unsafe_allow_html=True,
    )


def render_deep_harmonic_lesson(st: Any, session_state: dict, lesson: dict) -> None:
    st.markdown(_lesson_styles(), unsafe_allow_html=True)

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
    show_go_deeper = False
    inline_go_deeper = False

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

        step_text = f"{cur.get('title', '')} {cur.get('body', '')}".lower()
        if "go deeper" in step_text:
            inline_go_deeper = True
            show_go_deeper = True
        if step_idx >= total - 1:
            show_go_deeper = True

    loop = lesson.get("loop") or {}
    if loop.get("chords"):
        st.caption("Main loop — chord tones to feel under your fingers:")
        _render_chord_row(st, list(loop["chords"]))
        rep = " (repeats across the form)" if loop.get("repeating") else ""
        if rep:
            st.caption(rep.strip(" ()"))

    ref_cards = list(lesson.get("reference_cards") or [])
    if not ref_cards:
        ref_cards = [
            {"kind": "legacy", "title": str(d.get("title") or ""), "markdown": d.get("markdown") or ""}
            for d in (lesson.get("deep_dive") or [])
        ]

    if show_go_deeper:
        st.markdown("---")
        st.markdown("##### Go deeper")
        st.caption("Open only what you need — each card is optional reference.")
        _render_reference_cards(
            st,
            session_state,
            ref_cards,
            key_prefix=str(session_state.get("_dha_ui_prefix") or "dha"),
            expanded_inline=inline_go_deeper,
        )

    homework = lesson.get("homework") or {}
    if homework and step_idx >= max(0, total - 1):
        _render_homework(st, homework)


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

    session_state["_dha_ui_prefix"] = key_prefix

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
