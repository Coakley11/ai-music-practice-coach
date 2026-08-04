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
    play_caption = play_label or f"Play backing for {chord_only}"
    if ctx.chord.section and not compact:
        chord_display = f"{ctx.chord.section} · {chord_only}"
    else:
        chord_display = chord_only

    st.markdown(
        f'<div style="border:1px solid #e2e8f0;border-radius:12px;padding:0.75rem 1rem;margin:0.5rem 0;'
        f'background:linear-gradient(145deg,#faf5ff,#f8fafc);">'
        f'<div style="font-size:0.78rem;font-weight:700;color:#6b21a8;text-transform:uppercase;letter-spacing:.04em;">'
        f'Backing for this mission</div>'
        f'<div style="font-size:1.65rem;font-weight:800;color:#0f172a;margin:0.15rem 0;">{_esc(chord_display)}</div>'
        f'<div style="font-size:0.85rem;color:#475569;">{_esc(play_caption)}'
        f'{" · " + _esc(ctx.chord.quality_label) if ctx.chord.quality_label else ""}'
        f'<br><span style="font-size:0.82rem;">Improvise freely while focusing on your selected mission.</span></div></div>',
        unsafe_allow_html=True,
    )

    if mismatch and mismatch_msg:
        st.error(mismatch_msg.replace("**", ""))
    elif armed:
        st.success("Backing armed — matches selected chord.")
    if stale:
        st.warning(stale)
    if block and not mismatch:
        st.warning(block.replace("**", ""))

    col_a, col_b = st.columns(2)
    with col_a:
        bpm = st.slider(
            "Tempo (BPM)",
            min_value=50,
            max_value=200,
            value=int(ctx.tempo_bpm),
            key=f"{key_prefix}_bpm",
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
    with col_e:
        loops = st.number_input(
            "Loop bars",
            min_value=1,
            max_value=16,
            value=int(session.get("backing_track_loops") or ctx.loops),
            key=f"{key_prefix}_loops",
        )

    transport_changed = (
        int(bpm) != int(ctx.tempo_bpm)
        or float(volume) != float(ctx.volume)
        or bool(loop) != bool(ctx.loop)
        or bool(count_in) != bool(ctx.count_in_bars)
        or int(loops) != int(ctx.loops)
    )
    session["backing_track_bpm"] = int(bpm)
    session["mission_exact_backing_volume"] = float(volume)
    session["mission_exact_backing_loop"] = bool(loop)
    session["mission_exact_backing_count_in"] = bool(count_in)
    session["backing_track_loops"] = int(loops)
    if transport_changed:
        mark_mission_practice_context_dirty(session)
        ctx = ensure_mission_practice_context(session)

    btn_play, btn_stop = st.columns(2)
    with btn_play:
        if st.button("▶ Play", key=f"{key_prefix}_play", use_container_width=True, type="primary"):
            invalidate_exact_chord_backing_cache(session)
            import time

            session["_mission_backing_play_start_mono"] = time.monotonic()
            wav, sounding = generate_exact_chord_backing_wav(session)
            if not wav:
                st.warning("Select a mission chord first.")
            else:
                session[MISSION_EXACT_BACKING_ARMED_KEY] = True
                session["mission_exact_backing_play_nonce"] = int(
                    session.get("mission_exact_backing_play_nonce") or 0
                ) + 1
                st.caption(f"Sounding: **{sounding}** at {int(bpm)} BPM")
    with btn_stop:
        if st.button("■ Stop", key=f"{key_prefix}_stop", use_container_width=True):
            session.pop("mission_exact_backing_wav", None)
            session["mission_exact_backing_play_nonce"] = 0

    wav = session.get("mission_exact_backing_wav")
    if wav:
        st.audio(wav, format="audio/wav")
        sounding = session.get("_mission_backing_sounding_chord") or ctx.chord.symbol
        st.caption(f"Currently sounding: **{_esc(sounding)}**")

    if not compact:
        st.caption("Play is optional for uploads; use it when you want to hear the chord while recording live.")
