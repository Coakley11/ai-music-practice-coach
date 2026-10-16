"""Exact-chord backing controls for mission recording and upload capture."""

from __future__ import annotations

import html
from typing import Any

from mission_exact_chord_backing import generate_exact_chord_backing_wav, invalidate_exact_chord_backing_cache
from mission_practice_context import (
    MISSION_CAPTURE_BLOCK_MESSAGE_KEY,
    MISSION_EXACT_BACKING_ARMED_KEY,
    authoritative_mission_type,
    ensure_mission_practice_context,
    mark_mission_practice_context_dirty,
    recording_context_stale_warning,
    ui_backing_chord_mismatch,
)


def _on_mission_tempo_change(session: dict[str, Any], widget_key: str) -> None:
    """Slider moved: the new tempo becomes the Mission tempo before the page redraws."""
    from mission_practice_context import set_mission_tempo

    value = session.get(widget_key)
    if value is not None:
        set_mission_tempo(session, int(value))


def _on_mission_passes_change(session: dict[str, Any], widget_key: str) -> None:
    """Passes changed: the new count becomes the Mission's before the page redraws."""
    from mission_practice_context import set_mission_passes

    value = session.get(widget_key)
    if value is not None:
        set_mission_passes(session, int(value))


def _esc(text: Any) -> str:
    return html.escape(str(text or ""))


def should_show_exact_chord_panel(session: dict[str, Any]) -> bool:
    ctx = ensure_mission_practice_context(session)
    if ctx and (ctx.mission_type or ctx.chord.symbol):
        return True
    return bool(authoritative_mission_type(session))


def render_exact_chord_mission_backing_panel(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_exact",
    compact: bool = False,
    play_label: str | None = None,
) -> None:
    if not should_show_exact_chord_panel(session):
        return

    ctx = ensure_mission_practice_context(session)
    if not ctx:
        return

    mismatch, mismatch_msg = ui_backing_chord_mismatch(session)
    stale = recording_context_stale_warning(session)
    block = str(session.get(MISSION_CAPTURE_BLOCK_MESSAGE_KEY) or "")
    armed = bool(session.get(MISSION_EXACT_BACKING_ARMED_KEY))

    chord_only = ctx.chord.symbol or "—"
    play_caption = play_label or f"Backing for {chord_only}"
    if ctx.chord.section and not compact:
        chord_display = f"{ctx.chord.section} · {chord_only}"
    else:
        chord_display = chord_only
    quality = ctx.chord.quality_label
    if ctx.span:
        # 2/3-chord Mission: the backing loops the whole span as charted.
        chord_display = " → ".join(
            str(t.get("chart_chord") or t.get("chord") or "") for t in ctx.span.get("timeline") or []
        ) or chord_display
        bars = int(ctx.span.get("loop_bars") or 0)
        play_caption = play_label or f"The span ({bars} bar{'s' if bars != 1 else ''} per loop)"
        quality = str(ctx.span.get("relationship_label") or "")

    st.markdown(
        f'<div style="border:1px solid #e2e8f0;border-radius:12px;padding:0.75rem 1rem;margin:0.5rem 0;'
        f'background:linear-gradient(145deg,#faf5ff,#f8fafc);">'
        f'<div style="font-size:0.78rem;font-weight:700;color:#6b21a8;text-transform:uppercase;letter-spacing:.04em;">'
        f'Backing for this mission</div>'
        f'<div style="font-size:1.65rem;font-weight:800;color:#0f172a;margin:0.15rem 0;overflow-wrap:anywhere;">{_esc(chord_display)}</div>'
        f'<div style="font-size:0.85rem;color:#475569;">{_esc(play_caption)}'
        f'{" · " + _esc(quality) if quality else ""}'
        f'<br><span style="font-size:0.82rem;">Improvise freely while focusing on your selected mission.</span></div></div>',
        unsafe_allow_html=True,
    )

    if mismatch and mismatch_msg:
        st.error(mismatch_msg.replace("**", ""))
    elif armed:
        st.success("Backing armed — matches this span." if ctx.span else "Backing armed — matches selected chord.")
    if stale:
        st.warning(stale)
    if block and not mismatch:
        st.warning(block.replace("**", ""))

    bpm_key = f"{key_prefix}_bpm"
    if session.get(bpm_key) is not None and int(session[bpm_key]) != int(ctx.tempo_bpm):
        # The Mission tempo changed elsewhere (song, refresh): the slider shows it, it does
        # not push its old value back.
        session[bpm_key] = int(ctx.tempo_bpm)
    col_a, col_b = st.columns(2)
    with col_a:
        bpm = st.slider(
            "Tempo (BPM)",
            min_value=50,
            max_value=200,
            value=int(ctx.tempo_bpm),
            key=bpm_key,
            on_change=_on_mission_tempo_change,
            args=(session, bpm_key),
        )
    with col_b:
        session.setdefault("mission_exact_backing_volume", ctx.volume)
        volume = st.slider(
            "Volume",
            min_value=0.1,
            max_value=1.0,
            value=float(session.get("mission_exact_backing_volume") or ctx.volume),
            step=0.05,
            key=f"{key_prefix}_volume",
        )

    col_c, col_d, col_e = st.columns(3)
    with col_c:
        loop = st.checkbox(
            "Loop",
            value=bool(session.get("mission_exact_backing_loop", ctx.loop)),
            key=f"{key_prefix}_loop",
        )
    with col_d:
        count_in = st.checkbox(
            "Count-in (1 bar)",
            value=bool(session.get("mission_exact_backing_count_in")),
            key=f"{key_prefix}_count_in",
        )
    loops_key = f"{key_prefix}_loops"
    if session.get(loops_key) is not None and int(session[loops_key]) != int(ctx.loops):
        session[loops_key] = int(ctx.loops)  # changed elsewhere (song, refresh): show it
    with col_e:
        loops = st.number_input(
            "Passes of the span" if ctx.span else "Loop bars",
            min_value=1,
            max_value=16,
            value=int(ctx.loops),
            key=loops_key,
            on_change=_on_mission_passes_change,
            args=(session, loops_key),
        )

    if int(bpm) != int(ctx.tempo_bpm):  # on_change normally did this already
        from mission_practice_context import set_mission_tempo

        set_mission_tempo(session, int(bpm))
        ctx = ensure_mission_practice_context(session)
    if int(loops) != int(ctx.loops):  # on_change normally did this already
        from mission_practice_context import set_mission_passes

        set_mission_passes(session, int(loops))
        ctx = ensure_mission_practice_context(session)
    transport_changed = (
        float(volume) != float(ctx.volume)
        or bool(loop) != bool(ctx.loop)
        or bool(count_in) != bool(ctx.count_in_bars)
    )
    session["mission_exact_backing_volume"] = float(volume)
    session["mission_exact_backing_loop"] = bool(loop)
    session["mission_exact_backing_count_in"] = bool(count_in)
    if transport_changed:
        mark_mission_practice_context_dirty(session)
        ctx = ensure_mission_practice_context(session)

    # Mission recording: no separate backing transport. "Generate Backing" renders the exact
    # accompaniment once; Record (the Mission recorder) plays that asset in sync with the mic.
    from mission_generated_backing import current_generated_backing, generate_mission_backing

    if st.button("Generate Backing", key=f"{key_prefix}_generate", use_container_width=True, type="primary"):
        with st.spinner("Generating the accompaniment…"):
            rec = generate_mission_backing(session)
        if rec is None:
            st.warning("Select a mission chord first.")
        elif ctx.span and mismatch:
            st.rerun()  # the sync warning above was computed before this render
    gen, stale_reason = current_generated_backing(session)
    if gen and not stale_reason:
        st.success(
            f"Backing generated: {gen.get('label') or chord_display} · {gen.get('bpm')} BPM · "
            f"{gen.get('loops')} pass{'es' if int(gen.get('loops') or 1) != 1 else ''} · "
            f"{float(gen.get('duration_sec') or 0):.1f}s. Record plays it with your take."
        )
    elif gen and stale_reason:
        st.warning("The Mission settings changed since the backing was generated — Generate Backing again.")

    if not compact:
        st.caption("Generate Backing renders the exact accompaniment; Record plays it together with your take.")
