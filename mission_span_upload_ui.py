"""MC4 — Upload Analysis UI for 2/3-chord Mission takes: alignment panel + Mission result.

Shown only when the take being analyzed is a span take (mission_span_take). The alignment
panel comes before any chord-by-chord feedback: a detected start the player can move by a
beat or a bar and confirm. Nudges re-assign the already-detected notes (no new pitch
detection). Live takes start from the app's own alignment (bar 1 after the count-in).
"""

from __future__ import annotations

import html
from typing import Any

PANEL_KEY = "mission_span_align"


def _esc(text: Any) -> str:
    return html.escape(str(text or ""))


def _span_and_alignment(session: dict[str, Any], audio: bytes, name: str):
    from mission_span_take import analysis_span_take, resolve_alignment, set_current_audio
    from mission_span_transcription import session_transcription

    fp = set_current_audio(session, audio)
    take = analysis_span_take(session, fp)
    if take is None:
        return None, None, None
    take = dict(take)
    take["audio_fp"] = fp
    transcription = session_transcription(session, audio, name, instrument=str(take["span"].get("instrument") or ""))
    alignment = resolve_alignment(session, take, transcription)
    return take, transcription, alignment


def _apply(session: dict[str, Any], fp: str, span: dict[str, Any], action: str) -> None:
    from mission_span_recording_alignment import build_grid, confirm, nudge, reset
    from mission_span_take import get_alignment, set_alignment, sync_alignment_to_envelope

    al = get_alignment(session, fp, span)
    if al is None:
        return
    grid = build_grid(span["timeline"], bpm=int(span.get("bpm") or 100), meter=str(span.get("meter") or "4/4"))
    moves = {"minus_bar": (0, -1), "minus_beat": (-1, 0), "plus_beat": (1, 0), "plus_bar": (0, 1)}
    if action in moves:
        beats, bars = moves[action]
        al = nudge(al, grid, beats=beats, bars=bars)
    elif action == "reset":
        al = reset(al)
    elif action == "confirm":
        al = confirm(al)
    set_alignment(session, fp, al, span)
    sync_alignment_to_envelope(session, fp)  # survives refresh


def render_span_alignment_panel(st: Any, session: dict[str, Any], audio_obj: Any) -> dict[str, Any] | None:
    """Detected start + nudges + confirm, for a span take. Returns the take (or None)."""
    if audio_obj is None:
        return None
    audio = bytes(audio_obj.getvalue())
    name = str(getattr(audio_obj, "name", None) or "take.wav")
    with st.spinner("Listening for the notes in your take…"):
        take, transcription, alignment = _span_and_alignment(session, audio, name)
    if take is None:
        return None
    from mission_span_recording_alignment import SOURCE_LIVE, build_grid, format_time
    from mission_span_recording_context import span_summary_rows
    from span_motif_explain import pretty

    span = take["span"]
    fp = str(take["audio_fp"])
    grid = build_grid(span["timeline"], bpm=int(span.get("bpm") or 100), meter=str(span.get("meter") or "4/4"))
    starts = []
    for slot, t in zip(grid.slots, span["timeline"]):
        starts.append((pretty(str(t.get("chart_chord") or t.get("chord"))), alignment.offset_sec + slot.start_beat * grid.pulse_sec))
    with st.container(key=f"{PANEL_KEY}_panel", border=True):
        st.markdown("##### Span take — line up bar 1")
        rows = " · ".join(f"<strong>{_esc(k)}:</strong> {_esc(v)}" for k, v in span_summary_rows(span)[:2] if v)
        st.markdown(f'<div style="overflow-wrap:anywhere;">{rows}</div>', unsafe_allow_html=True)
        if alignment.source == SOURCE_LIVE:
            after = "after the count-in" if float(alignment.detail.get("count_in_sec") or 0) > 0 else "no count-in"
            head = f"Live take — bar 1 starts at **{format_time(alignment.offset_sec)}** ({after})."
        elif alignment.source in ("user_confirmed", "user_adjusted"):
            head = f"Bar 1 set at **{format_time(alignment.offset_sec)}**."
        else:
            head = f"Detected first bar at **{format_time(alignment.offset_sec)}**."
        st.markdown(head)
        chord_times = " · ".join(f"{_esc(c)} starts at {format_time(t)}" for c, t in starts)
        st.markdown(f'<div style="font-size:0.9rem;overflow-wrap:anywhere;">{chord_times}</div>', unsafe_allow_html=True)
        notes = len(transcription.get("notes") or [])
        if alignment.source == "detected":
            pct = round(alignment.confidence * 100)
            if alignment.trusted:
                st.success(f"Confident alignment ({pct}%). Chord-by-chord feedback is on — you can still adjust it.")
            else:
                st.warning(
                    f"Alignment confidence is low ({pct}%). Check that chord 1 starts here — nudge it if needed, "
                    "then press **Use this alignment** for chord-by-chord feedback."
                )
        elif alignment.source == SOURCE_LIVE:
            st.caption("Started recording late? Nudge bar 1 to where you actually began.")
        else:
            st.success("Alignment confirmed — chord-by-chord feedback is on.")
        st.caption(f"{notes} notes detected in this take.")
        with st.container(key=f"{PANEL_KEY}_nudges"):
            cols = st.columns(4)
            for col, (label, action) in zip(cols, (("−1 bar", "minus_bar"), ("−1 beat", "minus_beat"), ("+1 beat", "plus_beat"), ("+1 bar", "plus_bar"))):
                with col:
                    st.button(label, key=f"{PANEL_KEY}_{action}", use_container_width=True,
                              on_click=_apply, args=(session, fp, span, action))
        with st.container(key=f"{PANEL_KEY}_confirm_row"):
            c1, c2 = st.columns(2)
            with c1:
                st.button("Use this alignment", key=f"{PANEL_KEY}_confirm", type="primary", use_container_width=True,
                          on_click=_apply, args=(session, fp, span, "confirm"),
                          disabled=alignment.source in ("user_confirmed", "user_adjusted"))
            with c2:
                st.button("Reset detection", key=f"{PANEL_KEY}_reset", use_container_width=True,
                          on_click=_apply, args=(session, fp, span, "reset"),
                          disabled=alignment.source in ("detected", SOURCE_LIVE))
    return take


def span_take_analysis_ctx(session: dict[str, Any], audio: bytes, name: str) -> dict[str, Any] | None:
    """Span result + metric overrides for the analysis run (None for non-span takes)."""
    from mission_span_take import analysis_span_take, run_span_take_analysis, set_current_audio
    from mission_span_take_evaluation import span_metric_overrides

    fp = set_current_audio(session, audio)
    take = analysis_span_take(session, fp)
    if take is None:
        return None
    take = dict(take)
    take["audio_fp"] = fp
    result = run_span_take_analysis(session, take, audio, name)
    return {"result": result, "overrides": span_metric_overrides(result), "take": take}


def refresh_span_result(session: dict[str, Any], last: dict[str, Any]) -> dict[str, Any] | None:
    """Re-score the shown span result with the current alignment (cheap; notes are cached)."""
    if not isinstance(last, dict) or not isinstance(last.get("span_mission"), dict):
        return None
    audio = session.get("last_analysis_audio")
    if not isinstance(audio, (bytes, bytearray)) or not audio:
        return last["span_mission"]
    try:
        out = span_take_analysis_ctx(session, bytes(audio), str(session.get("last_analysis_source_label") or "take.wav"))
    except Exception:
        out = None
    if out is None:
        return last["span_mission"]
    last["span_mission"] = out["result"]
    return out["result"]


def render_span_take_result(st: Any, result: dict[str, Any]) -> None:
    """Mission result · What worked · Try next · (optional) chord detail."""
    if not isinstance(result, dict):
        return
    with st.container(key="mission_span_result", border=True):
        score = result.get("score")
        st.markdown("#### Mission Compliance" + (f": {int(score)}%" if score is not None else ""))
        st.markdown(f"**{_esc(result.get('headline'))}**")
        st.caption("The primary result for this Mission take. The broader performance coaching below "
                   "(timing, pitch, tone, expression, groove) is scored separately.")
        meta = " · ".join(
            x for x in (
                f"Practice key {result.get('practice_key')}" if result.get("practice_key") else "",
                f"{result.get('bpm')} BPM" if result.get("bpm") else "",
                str(result.get("meter") or ""),
                str(result.get("level") or ""),
            ) if x
        )
        if meta:
            st.caption(meta)
        if result.get("message"):
            (st.info if not result.get("aligned") else st.caption)(str(result["message"]))
        if result.get("what_worked"):
            st.markdown("**What worked**")
            st.markdown("\n".join(f"- {_esc(t)}" for t in result["what_worked"]))
        if result.get("try_next"):
            st.markdown("**Try next**")
            st.markdown("\n".join(f"- {_esc(t)}" for t in dict.fromkeys(result["try_next"]) if t))
        if result.get("general"):
            st.markdown("**What I heard**")
            st.markdown("\n".join(f"- {_esc(t)}" for t in result["general"]))
        detail = [d for d in result.get("chord_detail") or [] if d.get("covered", True)]
        if detail and result.get("aligned"):
            with st.expander("Chord detail", expanded=False):
                for d in detail:
                    if not d.get("notes"):
                        st.markdown(f"**{_esc(d['chord'])}** — no notes")
                        continue
                    st.markdown(
                        f"**{_esc(d['chord'])}** — {d['notes']} notes · {d.get('chord_tone_pct')}% chord tones · "
                        f"{d.get('guide_tone_pct')}% guide tones · first {_esc(d.get('first_note'))} · "
                        f"last {_esc(d.get('last_note'))}"
                    )


__all__ = [
    "refresh_span_result",
    "render_span_alignment_panel",
    "render_span_take_result",
    "span_take_analysis_ctx",
]
