"""Tone & Tuner History UI on the Practice page."""

from __future__ import annotations

import html
import io
from typing import Any

from media_state import migrate_tone_take
from media_tone_catalog import (
    NOTE_FILTER_MODE_CONCERT,
    NOTE_FILTER_MODE_OPTIONS,
    NOTE_FILTER_MODE_PLAYER,
    TONE_HISTORY_NOTE_FILTER_OPTIONS,
    delete_tone_take_entry,
    list_tone_takes,
    load_tone_take_for_playback,
    pending_tone_take_ready,
    playback_label_for_row,
    save_pending_tone_take,
    tone_catalog_diagnostics,
    tone_history_note_filter_label,
    tone_improvement_card,
    tone_take_quality,
    tone_take_row_summary,
)


def _dev_mode(st: Any, session_state: dict[str, Any]) -> bool:
    try:
        from suite_workspace import can_show_developer_tools

        if can_show_developer_tools(st=st):
            return True
    except ImportError:
        pass
    return bool(session_state.get("developer_mode"))


def _active_instrument_label(session_state: dict[str, Any], fallback: str) -> str:
    try:
        from practice_setup_globals import get_active_instrument_display_name

        label = str(get_active_instrument_display_name(session_state) or "").strip()
        return label or fallback
    except ImportError:
        return fallback


def render_pending_tone_save(
    st_module: Any,
    session_state: dict[str, Any],
    *,
    key_prefix: str,
    instrument: str,
    display_key: str,
    transposing_type: str = "",
) -> None:
    if not pending_tone_take_ready(session_state):
        return

    st_module.markdown("---")
    st_module.success("Long-tone analysis ready — save this take to your Tone History library.")
    notes = st_module.text_area(
        "Notes (optional)",
        key=f"{key_prefix}::tone_save_notes",
        placeholder="What were you working on?",
    )
    if st_module.button("Save Tone Take", key=f"{key_prefix}::tone_save_btn", type="primary", use_container_width=True):
        ok, _tid, err = save_pending_tone_take(
            session_state,
            st=st_module,
            instrument=instrument,
            display_key=display_key,
            transposing_type=transposing_type,
            notes=str(notes or ""),
        )
        if ok:
            st_module.success("Tone take saved to your library.")
            st_module.rerun()
        else:
            st_module.error(f"Could not save tone take: {err or 'unknown error'}")


def render_tone_take_history_section(
    st_module: Any,
    session_state: dict[str, Any],
    *,
    key_prefix: str,
    instrument: str,
    display_key: str = "",
    transposing_type: str = "",
) -> None:
    active_label = _active_instrument_label(session_state, instrument)

    st_module.markdown("---")
    st_module.markdown("##### Tone History")

    view_options = [active_label, "All instruments"]
    view = st_module.radio(
        "Library view",
        view_options,
        horizontal=True,
        key=f"{key_prefix}::tone_history_view",
    )
    filter_inst = None if view == "All instruments" else active_label
    all_instruments_view = view == "All instruments"

    try:
        from instrument_transposition import is_transposing_instrument

        instrument_is_transposing = bool(is_transposing_instrument(instrument))
    except ImportError:
        instrument_is_transposing = bool(str(transposing_type or "").strip())

    note_filter_label = tone_history_note_filter_label(
        all_instruments_view=all_instruments_view,
        instrument_is_transposing=instrument_is_transposing,
    )

    c1, c2, c3 = st_module.columns([2, 2, 2])
    with c1:
        note_filter = st_module.selectbox(
            note_filter_label,
            TONE_HISTORY_NOTE_FILTER_OPTIONS,
            key=f"{key_prefix}::tone_note_filter",
        )
    with c2:
        quality = st_module.selectbox(
            "Show",
            ["All takes", "Best takes", "Needs work"],
            key=f"{key_prefix}::tone_quality_filter",
        )
    note_filter_mode = NOTE_FILTER_MODE_PLAYER
    if all_instruments_view:
        with c3:
            note_filter_mode = st_module.selectbox(
                "Note filter mode",
                NOTE_FILTER_MODE_OPTIONS,
                key=f"{key_prefix}::tone_note_filter_mode",
            )
    quality_key = ""
    if quality == "Best takes":
        quality_key = "best"
    elif quality == "Needs work":
        quality_key = "needs_work"

    rows = list_tone_takes(
        st=st_module,
        instrument=filter_inst,
        note_filter=str(note_filter or ""),
        note_filter_mode=note_filter_mode,
        current_instrument_is_transposing=instrument_is_transposing,
        all_instruments_view=all_instruments_view,
        quality_filter=quality_key,
    )

    if rows:
        st_module.info(tone_improvement_card(rows))
    else:
        st_module.caption("No saved tone takes yet — record a long tone and tap **Save Tone Take**.")

    for row in rows[:20]:
        row = migrate_tone_take(row)
        tid = str(row.get("tone_take_id") or "")
        summary = tone_take_row_summary(row)
        quality_tag = tone_take_quality(row)
        badge = {"best": "✓", "needs_work": "!", "steady": "·"}.get(quality_tag, "·")

        with st_module.expander(f"{badge} {summary}"):
            st_module.markdown(f"**Instrument:** {html.escape(str(row.get('instrument') or '—'))}")
            if row.get("target_note") or row.get("detected_note"):
                st_module.markdown(
                    f"**Target / detected:** "
                    f"{html.escape(str(row.get('target_note') or '—'))} / "
                    f"{html.escape(str(row.get('detected_note') or row.get('median_note') or '—'))}"
                )
            if row.get("written_note") or row.get("concert_note"):
                st_module.markdown(
                    f"**Written / concert:** "
                    f"{html.escape(str(row.get('written_note') or '—'))} / "
                    f"{html.escape(str(row.get('concert_note') or '—'))}"
                )
            st_module.markdown(
                f"**Pitch report:** {row.get('pitch_stability_score', row.get('pitch_stability', '—'))}% stability · "
                f"{row.get('mean_cents', row.get('average_cents', 0)):+.0f}¢ avg · "
                f"max drift {row.get('max_cents_drift', '—')}¢"
            )
            st_module.markdown(
                f"**Tone report:** volume {row.get('volume_stability_score', row.get('sustain_steadiness', '—'))}% · "
                f"sustain {row.get('sustain_seconds', '—')}s · "
                f"consistency {row.get('tone_consistency_score', '—')}"
            )
            if row.get("coach_summary") or row.get("coach_report"):
                st_module.markdown(
                    f"**Coach report:** {html.escape(str(row.get('coach_report') or row.get('coach_summary')))}"
                )
            if row.get("notes") or row.get("user_notes"):
                st_module.markdown(
                    f"**Your notes:** {html.escape(str(row.get('user_notes') or row.get('notes')))}"
                )
            has_audio = bool(row.get("storage_ref") or row.get("local_path"))
            st_module.markdown(
                f"**Playback:** {html.escape(playback_label_for_row(row, st=st_module))} · "
                f"audio {'available' if has_audio else 'metadata only'}"
            )
            if row.get("storage_error"):
                st_module.caption(f"Storage note: {html.escape(str(row.get('storage_error')))}")

            play_key = f"{key_prefix}::tone_play_{tid}"
            del_key = f"{key_prefix}::tone_del_{tid}"
            pc1, pc2 = st_module.columns(2)
            with pc1:
                if st_module.button("Play", key=play_key):
                    data, err, _ = load_tone_take_for_playback(tid, st=st_module)
                    if data:
                        st_module.audio(io.BytesIO(data), format="audio/wav")
                    else:
                        st_module.warning(f"Audio unavailable: {err or 'missing file'}")
            with pc2:
                if st_module.button("Delete", key=del_key):
                    if delete_tone_take_entry(st_module, tid, row=row):
                        st_module.success("Tone take deleted.")
                        st_module.rerun()
                    else:
                        st_module.error("Delete failed.")

    if _dev_mode(st_module, session_state):
        diag = tone_catalog_diagnostics(session_state, st=st_module, active_instrument=active_label)
        with st_module.expander("Tone history diagnostics (?dev=1)", expanded=False):
            for key, val in diag.items():
                st_module.markdown(f"**{key}:** `{html.escape(str(val))}`")
