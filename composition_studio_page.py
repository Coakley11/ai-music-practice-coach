"""Composition Studio — guided six-phase songwriting workspace (CS-B0+)."""

from __future__ import annotations

import html
import time
from typing import Any

import streamlit as st

from composition_review import (
    build_readiness_checklist,
    coach_line_for_review,
    readiness_glyph,
    song_is_ready,
)
from composition_chord_suggestions import (
    SECTION_HARMONY_FEELINGS,
    coach_line_for_section,
    default_feeling_for_section,
    guided_chord_vocabulary,
    suggest_progressions,
)
from composition_chord_refinements import (
    CHORD_REFINEMENT_INTENTS,
    propose_chord_refinement,
    refinement_intent_label,
)
from composition_lyric_suggestions import (
    LYRIC_EMOTIONS,
    LYRIC_SECTION_ROLES,
    coach_line_for_lyrics,
    default_role_for_section,
    suggest_lyric_brainstorm_ideas,
    suggest_lyric_prompts,
)
from composition_melody_suggestions import (
    MELODY_FEELINGS,
    MELODY_STYLES,
    coach_line_for_melody,
    default_melody_feel_for_section,
    suggest_melody_concepts,
    MELODY_REFINEMENTS,
    apply_melody_refinement_to_section,
)
from composition_document import (
    COMPOSITION_ENERGY_LEVELS,
    COMPOSITION_GENRES,
    COMPOSITION_METER_CUSTOM,
    COMPOSITION_METERS,
    COMPOSITION_PHASE_LABELS,
    COMPOSITION_PHASES,
    COMPOSER_SECTION_LABELS,
    add_section,
    add_melody_phrase,
    advance_workflow,
    apply_melody_concept,
    apply_lyric_prompt_to_section,
    apply_lyrics_text,
    section_lyric_alignment,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    break_chord_link,
    chord_link_display,
    chords_for_playback,
    coerce_composition_bpm,
    coerce_composition_key_choice,
    coerce_composition_meter,
    complete_workflow_phase,
    composition_key_choice_labels,
    composition_key_label_from_token,
    composition_key_token_from_choice,
    document_summary_line,
    duplicate_section,
    ensure_workflow,
    get_workflow_phase,
    harmonized_section_count,
    harmony_edit_target,
    lyrics_section_count,
    melodized_section_count,
    move_section,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    playback_globals,
    remove_section,
    neighbor_section_after_remove,
    remove_melody_phrase,
    section_by_id,
    section_css_type,
    section_has_resolved_chords,
    section_has_chords,
    section_has_lyrics,
    section_has_melody,
    insert_section_chord,
    move_section_chord,
    remove_section_chord,
    replace_section_chord,
    section_melody_events,
    section_playback_bars,
    apply_melody_events,
    apply_accepted_melody_edits,
    align_lyrics_to_melody,
    section_lane_status,
    set_workflow_phase,
    suggest_musical_defaults,
    sync_linked_chord_sections,
    touch_composition,
)
from composition_preview import (
    invalidate_composer_preview,
    play_composer_preview,
    render_composer_playback,
)
from composition_hum_transcription import (
    apply_record_origin,
    delete_melody_event,
    prepare_armed_record_transport,
    duration_choice_labels,
    hum_analysis_available,
    insert_melody_event,
    nudge_event_pitch,
    set_event_duration,
    shift_event_onset,
    transcribe_hum_audio,
)
from composition_melody_notation import (
    build_section_score_model,
    render_abc_html,
)
from composition_session_state import (
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_ARRANGEMENT_PREVIEW_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_NEEDS_SEED_KEY,
    COMPOSER_PREVIEW_SIG_KEY,
    COMPOSER_PREVIEW_WAV_KEY,
    delete_library_document,
    get_active_document,
    init_composer_page_state,
    list_library_documents,
    load_library_document,
    save_document_to_library,
    set_active_document,
)
from composition_snapshot import build_composition_snapshot, snapshot_invalidate_token
from custom_progression_lab import (
    CPL_PROGRESSION_STYLES,
    cpl_progression_bar_chart_html,
    expand_entries_to_chords,
    format_entries_bar_line,
    normalize_chord_symbol,
)

_COMPOSER_QUICK_CHORDS: tuple[str, ...] = (
    "C",
    "Am",
    "F",
    "G",
    "Dm",
    "Em",
    "D",
    "A",
    "E",
    "Bm",
    "Bb",
    "Eb",
    "Ab",
    "Db",
    "G7",
    "Cmaj7",
    "Dm7",
    "G7",
    "Am7",
    "Fmaj7",
)


def inject_composition_studio_styles() -> None:
    st.markdown(
        """
<style>
body[data-studio-page="composer"] .block-container {
  max-width: 1280px;
}
.composer-hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 45%, #312e81 100%);
  color: #f8fafc;
  border-radius: 16px;
  padding: 1.35rem 1.5rem 1.15rem;
  margin-bottom: 0.85rem;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
}
.composer-hero h2 {
  margin: 0 0 0.4rem 0;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.composer-hero p {
  margin: 0;
  color: #cbd5e1;
  font-size: 0.94rem;
  line-height: 1.5;
}
.composer-journey-wrap {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 0.65rem 0.75rem 0.55rem;
  margin-bottom: 0.85rem;
}
.composer-journey-title {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  font-weight: 700;
  margin: 0 0 0.45rem 0.15rem;
}
.composer-phase-card {
  background: #f8fafc;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.5rem;
}
.composer-phase-card h3 {
  margin: 0 0 0.35rem 0;
  font-size: 1.05rem;
  color: #0f172a;
}
.composer-phase-card p {
  margin: 0;
  color: #475569;
  font-size: 0.9rem;
  line-height: 1.45;
}
.composer-snapshot-strip {
  background: #f8fafc;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 0.65rem 0.85rem;
  font-size: 0.82rem;
  color: #475569;
  margin-bottom: 0.65rem;
}
.composer-snapshot-strip strong { color: #0f172a; }
.composer-beside-panel {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  min-height: 120px;
}
.composer-beside-kicker {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  margin: 0 0 0.35rem 0;
  font-weight: 700;
}
.composer-beside-body {
  font-size: 0.88rem;
  color: #334155;
  line-height: 1.55;
  margin: 0;
}
.composer-suggest-strip {
  background: #eef2ff;
  border: 1px solid rgba(79, 70, 229, 0.15);
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.82rem;
  color: #3730a3;
  margin: 0.5rem 0 0.75rem 0;
}
.composer-section-status {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.35rem 0 0.65rem 0;
}
.composer-section-status-chip {
  font-size: 0.72rem;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  background: #f1f5f9;
  color: #475569;
  border: 1px solid rgba(15, 23, 42, 0.08);
}
.composer-section-status-chip.is-done {
  background: #ecfdf5;
  color: #047857;
  border-color: rgba(4, 120, 87, 0.2);
}
.composer-section-status-chip.is-na {
  background: #f8fafc;
  color: #94a3b8;
}
.composer-coming-soon {
  background: #fff7ed;
  border: 1px solid rgba(234, 88, 12, 0.2);
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.82rem;
  color: #9a3412;
  margin: 0.35rem 0 0.65rem 0;
}
.composer-structure-scroll {
  overflow-x: auto;
  padding: 0.35rem 0.15rem 0.75rem;
  margin-bottom: 0.35rem;
}
.composer-structure-track {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 0;
  min-width: min-content;
}
.composer-structure-arrow {
  display: flex;
  align-items: center;
  color: #94a3b8;
  font-size: 1.1rem;
  padding: 0 0.15rem;
  user-select: none;
}
.composer-section-block {
  min-width: 108px;
  max-width: 132px;
  border-radius: 12px;
  padding: 0.65rem 0.7rem 0.55rem;
  border: 2px solid transparent;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
  text-align: center;
}
.composer-section-block.is-selected {
  border-color: #312e81;
  box-shadow: 0 6px 18px rgba(49, 46, 129, 0.22);
  transform: translateY(-2px);
}
.composer-section-type {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: 0.85;
  font-weight: 700;
}
.composer-section-name {
  font-size: 0.92rem;
  font-weight: 700;
  margin-top: 0.15rem;
  line-height: 1.25;
}
.composer-section-link {
  display: block;
  font-size: 0.68rem;
  margin-top: 0.3rem;
  opacity: 0.9;
}
.composer-section-intro { background: linear-gradient(160deg, #e2e8f0, #cbd5e1); color: #0f172a; }
.composer-section-verse { background: linear-gradient(160deg, #dbeafe, #93c5fd); color: #1e3a8a; }
.composer-section-prechorus { background: linear-gradient(160deg, #ede9fe, #c4b5fd); color: #4c1d95; }
.composer-section-chorus { background: linear-gradient(160deg, #fef3c7, #fcd34d); color: #92400e; }
.composer-section-bridge { background: linear-gradient(160deg, #d1fae5, #6ee7b7); color: #065f46; }
.composer-section-solo { background: linear-gradient(160deg, #fee2e2, #fca5a5); color: #991b1b; }
.composer-section-interlude { background: linear-gradient(160deg, #f3e8ff, #d8b4fe); color: #6b21a8; }
.composer-section-outro { background: linear-gradient(160deg, #e2e8f0, #94a3b8); color: #0f172a; }
.composer-structure-empty {
  border: 2px dashed rgba(99, 102, 241, 0.35);
  border-radius: 14px;
  padding: 1.5rem 1rem;
  text-align: center;
  color: #475569;
  background: #f8fafc;
}
.composer-structure-empty strong { color: #312e81; }
.composer-structure-hint {
  font-size: 0.85rem;
  color: #475569;
  margin: 0 0 0.65rem 0;
  line-height: 1.45;
}
.composer-structure-actions {
  background: #f8fafc;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
  margin: 0.5rem 0 0.85rem;
}
.composer-melody-notation {
  font-family: ui-monospace, "Cascadia Code", monospace;
  font-size: 0.88rem;
  color: #1e3a8a;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 0.45rem 0.6rem;
  margin: 0.35rem 0 0.5rem;
}
.composer-score-wrap {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 0.55rem 0.65rem 0.75rem;
  margin: 0.45rem 0 0.75rem;
}
.composer-score-chords {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.15rem;
  padding: 0 0.35rem 0.15rem;
}
.composer-score-chord {
  flex: 1 1 0;
  text-align: center;
  font-weight: 700;
  font-size: 0.95rem;
  color: #0f172a;
}
.composer-score-lyrics {
  margin-top: 0.55rem;
  padding: 0.45rem 0.55rem;
  white-space: pre-wrap;
  color: #334155;
  font-size: 0.92rem;
  line-height: 1.45;
  border-top: 1px dashed rgba(15, 23, 42, 0.12);
}
.composer-score-empty {
  color: #64748b;
  font-size: 0.88rem;
  padding: 0.35rem 0.15rem;
}
.composer-chords-first-banner {
  background: #fffbeb;
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.86rem;
  color: #92400e;
  margin-bottom: 0.65rem;
}
.composer-chords-section-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.65rem 0 0.85rem;
}
.composer-suggestion-card {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  padding: 0.75rem 0.85rem;
  margin-bottom: 0.55rem;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}
.composer-suggestion-card h4 {
  margin: 0 0 0.25rem 0;
  font-size: 0.95rem;
  color: #0f172a;
}
.composer-suggestion-chords {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.88rem;
  color: #312e81;
  font-weight: 600;
  margin: 0.25rem 0 0.35rem;
}
.composer-suggestion-why {
  font-size: 0.82rem;
  color: #475569;
  line-height: 1.45;
  margin: 0;
}
.composer-review-cover {
  background: linear-gradient(145deg, #0f172a 0%, #1e3a5f 55%, #4338ca 100%);
  color: #f8fafc;
  border-radius: 16px;
  padding: 1.35rem 1.45rem 1.2rem;
  margin-bottom: 0.85rem;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}
.composer-review-cover h2 {
  margin: 0 0 0.35rem 0;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.composer-review-cover .composer-review-meta {
  font-size: 0.88rem;
  color: #cbd5e1;
  line-height: 1.55;
  margin: 0.35rem 0 0;
}
.composer-review-cover .composer-review-idea {
  margin-top: 0.75rem;
  font-size: 0.92rem;
  color: #e2e8f0;
  line-height: 1.5;
  font-style: italic;
}
.composer-review-block {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.65rem;
}
.composer-review-block h4 {
  margin: 0 0 0.45rem 0;
  font-size: 0.95rem;
  color: #0f172a;
}
.composer-readiness-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.composer-readiness-list li {
  display: flex;
  gap: 0.55rem;
  align-items: flex-start;
  padding: 0.35rem 0;
  font-size: 0.88rem;
  color: #334155;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.composer-readiness-list li:last-child { border-bottom: none; }
.composer-readiness-glyph {
  font-weight: 800;
  min-width: 1.1rem;
  color: #4f46e5;
}
.composer-readiness-glyph.is-missing { color: #94a3b8; }
.composer-readiness-glyph.is-partial { color: #d97706; }
.composer-readiness-glyph.is-skipped { color: #64748b; }
.composer-review-section-row {
  font-size: 0.85rem;
  color: #475569;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.05);
}
.composer-review-section-row strong { color: #0f172a; }
.composer-linked-banner {
  background: #fffbeb;
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
  font-size: 0.84rem;
  color: #92400e;
  margin-bottom: 0.65rem;
}
.composer-harmony-progress {
  font-size: 0.82rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _pending_chord_key(section_id: str) -> str:
    return f"composer_pending_chord_{section_id}"


def _save_doc(session_state: dict, doc: dict[str, Any]) -> None:
    """Persist the working draft. Does not add the song to the Composition Library."""
    touch_composition(doc)
    set_active_document(session_state, doc)
    try:
        from composition_workspace_state_persistence import checkpoint_composition_workspace

        # Meaningful mutation boundary — durable draft for reboot (preserve nav page).
        checkpoint_composition_workspace(
            session_state,
            reason="composer_edit",
            force_disk=True,
            st=st,
        )
    except Exception:
        pass


def _composer_navigate(
    session_state: dict,
    doc: dict[str, Any],
    phase: str,
    *,
    section_id: str | None = None,
) -> None:
    set_workflow_phase(doc, phase)
    if section_id:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = section_id
    invalidate_composer_preview(session_state)
    _save_doc(session_state, doc)
    st.rerun()


def _readiness_glyph_class(status: str) -> str:
    if status in ("missing", "current"):
        return "composer-readiness-glyph is-missing"
    if status == "partial":
        return "composer-readiness-glyph is-partial"
    if status == "skipped":
        return "composer-readiness-glyph is-skipped"
    return "composer-readiness-glyph"


def _render_phase_review(session_state: dict, doc: dict[str, Any]) -> None:
    _ensure_active_section(session_state, doc)
    wf = ensure_workflow(doc)
    skip_lyrics = bool(wf.get("skip_lyrics"))
    meta = doc.get("metadata") or {}
    origin = doc.get("origin") or {}
    pg = playback_globals(doc)
    idea = str(meta.get("description") or origin.get("seed_summary") or "").strip()
    genre = str(meta.get("style") or "—")
    mood = str(meta.get("mood") or "—")
    title = str(doc.get("title") or "Untitled Song")
    vocal_label = "Instrumental" if skip_lyrics else "Vocal"

    sections = ordered_sections(doc)
    selected_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    if sections and selected_id not in [str(s.get("id")) for s in sections]:
        selected_id = str(sections[0].get("id") or "")
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = selected_id

    center, side = st.columns([2.3, 1])
    with center:
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Review</h3>
  <p>Step back and experience your song as one complete piece. Is it ready?</p>
</div>
            """,
            unsafe_allow_html=True,
        )

        idea_html = (
            f'<p class="composer-review-idea">"{html.escape(idea[:280])}{"…" if len(idea) > 280 else ""}"</p>'
            if idea
            else ""
        )
        st.markdown(
            f"""
<div class="composer-review-cover">
  <h2>{html.escape(title)}</h2>
  <p class="composer-review-meta">
    <strong>{html.escape(genre)}</strong> · {html.escape(mood)} · {html.escape(str(pg.get("key_label") or pg["key_center"]))} · {pg["bpm"]} BPM · {html.escape(str(pg["time_signature"]))} · {vocal_label}
  </p>
  {idea_html}
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Return to editing**")
        edit_cols = st.columns(6)
        jump_phases = [p for p in COMPOSITION_PHASES if p != "review"]
        for col, phase in zip(edit_cols, jump_phases):
            label = COMPOSITION_PHASE_LABELS.get(phase, phase)
            if phase == "lyrics" and skip_lyrics:
                label = "Lyrics · skip"
            with col:
                disabled = phase == "lyrics" and skip_lyrics
                if st.button(
                    label,
                    key=f"composer_review_edit_{phase}",
                    use_container_width=True,
                    disabled=disabled,
                ):
                    _composer_navigate(session_state, doc, phase)

        st.markdown("---")
        st.markdown('<div class="composer-review-block"><h4>Structure</h4></div>', unsafe_allow_html=True)
        if sections:
            st.markdown(
                f'<div class="composer-structure-scroll">{_structure_timeline_html(doc, selected_id)}</div>',
                unsafe_allow_html=True,
            )
            sec_labels = [str(s.get("label_variant") or s.get("label") or "Section") for s in sections]
            sec_ids = [str(s.get("id") or "") for s in sections]
            j1, j2, j3 = st.columns([2, 2, 1])
            with j1:
                sec_idx = st.selectbox(
                    "Section",
                    range(len(sec_ids)),
                    format_func=lambda i: sec_labels[i],
                    key="composer_review_jump_section",
                )
            with j2:
                target_phase = st.selectbox(
                    "Open in phase",
                    ["structure", "chords", "melody"] + ([] if skip_lyrics else ["lyrics"]),
                    format_func=lambda p: COMPOSITION_PHASE_LABELS.get(p, p),
                    key="composer_review_jump_phase",
                )
            with j3:
                st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
                if st.button("Go", key="composer_review_jump_go", use_container_width=True):
                    _composer_navigate(session_state, doc, target_phase, section_id=sec_ids[sec_idx])
        else:
            st.info("No sections yet — start in **Song Structure**.")

        st.markdown(
            '<div class="composer-review-block"><h4>Section scores</h4></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Same musical view everywhere: staff above, chords underneath"
            + (", lyrics when present." if not skip_lyrics else " (instrumental — no lyrics required).")
        )
        if not sections:
            st.info("No sections yet — start in **Song Structure**.")
        for sec in sections:
            variant = str(sec.get("label_variant") or sec.get("label") or "Section")
            has_ch = bool(sec.get("chords"))
            has_mel = bool(section_melody_events(sec))
            has_ly = bool(_section_lyrics_text(sec)) and not skip_lyrics
            if has_ch and has_mel and (has_ly or skip_lyrics):
                badge = "Complete"
            elif has_ch and has_mel:
                badge = "Chords + melody"
            elif has_ch:
                badge = "Chords only"
            elif has_mel:
                badge = "Melody started"
            else:
                badge = "Empty"
            with st.expander(f"{variant} — {badge}", expanded=has_ch or has_mel):
                if not has_ch and not has_mel:
                    st.caption("Nothing written yet for this section.")
                else:
                    _render_section_score_view(
                        session_state,
                        doc,
                        sec,
                        play_key=f"composer_review_play_{sec.get('id')}",
                    )
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        if st.button("Edit chords", key=f"composer_review_ed_ch_{sec.get('id')}", use_container_width=True):
                            _composer_navigate(session_state, doc, "chords", section_id=str(sec.get("id") or ""))
                    with e2:
                        if st.button("Edit melody", key=f"composer_review_ed_mel_{sec.get('id')}", use_container_width=True):
                            _composer_navigate(session_state, doc, "melody", section_id=str(sec.get("id") or ""))
                    with e3:
                        if skip_lyrics:
                            st.caption("Instrumental")
                        elif st.button("Edit lyrics", key=f"composer_review_ed_ly_{sec.get('id')}", use_container_width=True):
                            _composer_navigate(session_state, doc, "lyrics", section_id=str(sec.get("id") or ""))

        st.markdown("---")
        st.markdown("**Playback**")
        playback_mode = st.radio(
            "Playback",
            ["Instrumental melody", "Vocal / sing lyrics"],
            horizontal=True,
            key="composer_review_playback_mode",
            label_visibility="collapsed",
        )
        arrangement = str(session_state.get(COMPOSER_ARRANGEMENT_PREVIEW_KEY) or "").strip()
        with st.expander("Advanced playback settings", expanded=False):
            st.caption(
                f"Original composition style: **{(doc.get('metadata') or {}).get('style') or 'Pop'}**. "
                "Previewing another style changes backing only — not chords, melody, or lyrics."
            )
            style_choices = ["Original", "Pop", "Jazz", "Rock", "Funk"]
            current = arrangement if arrangement in style_choices else "Original"
            picked = st.selectbox("Preview arrangement", style_choices, index=style_choices.index(current) if current in style_choices else 0, key="composer_review_arrangement")
            session_state[COMPOSER_ARRANGEMENT_PREVIEW_KEY] = "" if picked == "Original" else picked
            arrangement = str(session_state.get(COMPOSER_ARRANGEMENT_PREVIEW_KEY) or "").strip()

        st.markdown("**Full song playthrough**")
        st.caption("Hear the entire composition in order — your first listen as a finished piece.")
        p1, p2, p3 = st.columns([2, 2, 3])
        with p1:
            loops = st.slider("Loops", 1, 3, int(session_state.get("composer_review_loops") or 1), key="composer_review_loops")
        with p2:
            st.markdown("<div style='height:1.65rem'></div>", unsafe_allow_html=True)
        with p3:
            play_full = st.button(
                "▶ Play full song",
                type="primary",
                key="composer_review_play_full",
                use_container_width=True,
            )
        if play_full:
            if playback_mode.startswith("Vocal"):
                from composition_vocal_render import build_vocal_render_plan, render_vocal_audio

                plan = build_vocal_render_plan(doc, scope="song")
                result = render_vocal_audio(plan)
                st.info(str(result.get("message") or "Sung lyrics are not available yet."))
            elif not chords_for_playback(doc, scope="song"):
                st.warning("Add chords to at least one section before playing.")
            else:
                result = play_composer_preview(
                    session_state,
                    doc,
                    scope="song",
                    loops=loops,
                    include_melody=True,
                    arrangement_style=arrangement or None,
                )
                if not result.get("ok"):
                    st.warning(str(result.get("reason") or "Could not generate playback."))
        _render_active_preview(session_state, stop_key="composer_review_preview_stop")

        st.markdown("---")
        st.markdown('<div class="composer-review-block"><h4>Readiness</h4></div>', unsafe_allow_html=True)
        checklist = build_readiness_checklist(doc, current_phase="review")
        items_html: list[str] = ['<ul class="composer-readiness-list">']
        for row in checklist:
            glyph = readiness_glyph(str(row["status"]))
            gclass = _readiness_glyph_class(str(row["status"]))
            items_html.append(
                f'<li><span class="{gclass}">{glyph}</span>'
                f"<span><strong>{html.escape(str(row['label']))}</strong> — {html.escape(str(row['note']))}</span></li>"
            )
        items_html.append("</ul>")
        st.markdown("".join(items_html), unsafe_allow_html=True)

        ready = song_is_ready(doc)
        if ready:
            st.success("Core phases look complete — refine anything that doesn't feel true, then mark the song ready.")
        else:
            st.info("Some areas still need attention — use the checklist and jump back to any phase.")

        m1, m2, m3 = st.columns(3)
        with m1:
            if st.button("Mark song ready", type="primary", key="composer_review_mark_ready", disabled=not ready):
                doc["status"] = "ready"
                complete_workflow_phase(doc, "review")
                _save_doc(session_state, doc)
                st.rerun()
        with m2:
            if st.button("Save to Composition Library", key="composer_review_save_library", use_container_width=True):
                save_document_to_library(session_state, doc)
                st.success("Saved to Composition Library.")
                st.rerun()
        with m3:
            if st.button("Keep refining", key="composer_review_keep_refining", use_container_width=True):
                set_workflow_phase(doc, "chords")
                _save_doc(session_state, doc)
                st.rerun()

        if str(doc.get("status") or "") == "ready":
            st.caption("This song is marked **ready**. Use Save to Composition Library to keep a named library copy.")
        else:
            st.caption("Working drafts are kept automatically. Save to Composition Library is the explicit finished-song action.")

    with side:
        _render_coach_panel(doc, lead=coach_line_for_review(doc))
        st.markdown(
            f'<p style="font-size:0.82rem;color:#64748b;margin-top:0.5rem;">{document_summary_line(doc)}</p>',
            unsafe_allow_html=True,
        )
        _render_library_sidebar(session_state)


def _vision_coach_html(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    g = doc.get("global") or {}
    genre = str(meta.get("style") or "your genre")
    mood = str(meta.get("mood") or "the feeling you're chasing")
    idea = str(meta.get("description") or "").strip()
    refs = str(meta.get("references") or "").strip()
    ref_bit = f" I hear shades of <em>{html.escape(refs)}</em> in this." if refs else ""
    idea_bit = f' "{html.escape(idea[:160])}"' if idea else ""
    pg = playback_globals(doc)
    key_label = str(
        pg.get("key_label")
        or g.get("original_key_label")
        or composition_key_label_from_token(g.get("original_key_center") or "C")
    )
    return (
        f"So we're writing a <strong>{html.escape(genre)}</strong> song with a "
        f"<strong>{html.escape(mood.lower())}</strong> feel"
        f"{ref_bit}.{idea_bit}<br><br>"
        f"Song settings you own: <strong>{html.escape(key_label)}</strong> · "
        f"<strong>{pg['bpm']} BPM</strong> · <strong>{html.escape(str(pg['time_signature']))}</strong>. "
        f"Change them anytime — they stay with this composition. "
        f"Next, shape the song's structure, then freely work any section's chords, melody, or lyrics."
    )


def _render_coach_panel(doc: dict[str, Any], *, lead: str, body_html: str = "") -> None:
    st.markdown(
        f"""
<div class="composer-beside-panel">
  <p class="composer-beside-kicker">Your songwriting partner</p>
  <p class="composer-beside-body">{lead}</p>
  {f'<p class="composer-beside-body" style="margin-top:0.55rem;">{body_html}</p>' if body_html else ""}
  <p class="composer-beside-body" style="margin-top:0.55rem;font-size:0.8rem;color:#64748b;">
    AI suggestions arrive in a later sprint — for now, take your time and follow the journey.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_library_sidebar(session_state: dict) -> None:
    if st.button("Save to Composition Library", key="composer_save_btn", use_container_width=True):
        doc = get_active_document(session_state)
        if doc:
            save_document_to_library(session_state, doc)
            st.success("Saved to Composition Library. The working draft was already being kept automatically.")
    with st.expander("Composition Library"):
        for row in list_library_documents(session_state):
            rid = str(row.get("id") or "")
            label = str(row.get("title") or "Untitled")
            c1, c2 = st.columns([3, 1])
            with c1:
                if st.button(label, key=f"composer_lib_open_{rid}", use_container_width=True):
                    load_library_document(session_state, rid)
                    st.rerun()
            with c2:
                if st.button("🗑", key=f"composer_lib_del_{rid}"):
                    delete_library_document(session_state, rid)
                    st.rerun()
    if st.button("Start new song", key="composer_new_song", use_container_width=True):
        session_state.pop("composer_active_document", None)
        session_state[COMPOSER_NEEDS_SEED_KEY] = True
        invalidate_composer_preview(session_state)
        st.rerun()


def _render_journey_rail(session_state: dict, doc: dict[str, Any]) -> None:
    wf = ensure_workflow(doc)
    current = get_workflow_phase(doc)
    st.markdown(
        '<p class="composer-journey-title">Guided path · jump freely after structure exists</p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(COMPOSITION_PHASES))
    for col, phase in zip(cols, COMPOSITION_PHASES):
        label = COMPOSITION_PHASE_LABELS[phase]
        if phase == "lyrics" and wf.get("skip_lyrics"):
            label = "Lyrics · N/A"
        with col:
            is_current = phase == current
            reachable = phase_is_reachable(doc, phase)
            if phase == "lyrics" and wf.get("skip_lyrics"):
                reachable = False
            btn_type = "primary" if is_current else "secondary"
            if st.button(
                label,
                key=f"composer_journey_{phase}",
                type=btn_type,
                use_container_width=True,
                disabled=not reachable,
            ):
                set_workflow_phase(doc, phase)
                _save_doc(session_state, doc)
                st.rerun()


def _section_status_html(doc: dict[str, Any], section_id: str) -> str:
    status = section_lane_status(doc, section_id)
    chips: list[str] = []
    for lane, label in (("chords", "Chords"), ("melody", "Melody"), ("lyrics", "Lyrics")):
        state = status.get(lane) or "incomplete"
        if state == "complete":
            chips.append(f'<span class="composer-section-status-chip is-done">{label} ✓</span>')
        elif state == "not_applicable":
            chips.append(f'<span class="composer-section-status-chip is-na">{label} N/A</span>')
        else:
            chips.append(f'<span class="composer-section-status-chip">{label} ○</span>')
    return f'<div class="composer-section-status">{"".join(chips)}</div>'


def _render_section_lane_switcher(session_state: dict, doc: dict[str, Any], *, active_lane: str) -> None:
    """Work on Chords / Melody / Lyrics for the selected section — free movement."""
    wf = ensure_workflow(doc)
    skip_lyrics = bool(wf.get("skip_lyrics"))
    st.markdown("**Work on**")
    lanes = [("chords", "Chords"), ("melody", "Melody")]
    if not skip_lyrics:
        lanes.append(("lyrics", "Lyrics"))
    cols = st.columns(len(lanes))
    for col, (lane, label) in zip(cols, lanes):
        with col:
            btn_type = "primary" if lane == active_lane else "secondary"
            if st.button(label, key=f"composer_section_lane_{lane}", type=btn_type, use_container_width=True):
                session_state[COMPOSER_FOCUS_LANE_KEY] = lane
                set_workflow_phase(doc, lane)
                _save_doc(session_state, doc)
                st.rerun()


def _render_active_preview(session_state: dict, *, stop_key: str = "composer_preview_stop") -> None:
    """Always-available audition dock — click path must remount playable autoplay audio."""
    render_composer_playback(st, session_state, stop_key=stop_key)


def _play_chord_idea(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    chord_syms: list[str],
    *,
    loops: int = 2,
) -> bool:
    """Generate transient chord preview. Returns True if a playable payload was armed."""
    result = play_composer_preview(
        session_state,
        doc,
        section_id=section_id,
        loops=loops,
        chord_override=chord_syms,
        include_melody=False,
    )
    return bool(result.get("ok"))


def _compare_queue_key(section_id: str) -> str:
    return f"composer_compare_{section_id}"


def _render_compare_tray(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    suggestions: list[dict[str, Any]],
) -> None:
    """Visible comparison set — Compare must not be an invisible queue."""
    queue_key = _compare_queue_key(section_id)
    queue = [q for q in list(session_state.get(queue_key) or []) if q]
    if not queue:
        return
    by_id = {str(s.get("id") or ""): s for s in suggestions}
    visible = [(qid, by_id[qid]) for qid in queue if qid in by_id]
    if not visible:
        session_state[queue_key] = []
        return
    names = ", ".join(str(s.get("name") or qid) for qid, s in visible)
    st.markdown(f"**Comparing:** {names}")
    for qid, sug in visible:
        line = str(sug.get("line") or "")
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            st.caption(f"{sug.get('name') or qid}: `{line}`")
        with c2:
            if st.button("▶", key=f"composer_cmp_tray_prev_{section_id}_{qid}", help="Preview"):
                chord_syms = expand_entries_to_chords(list(sug.get("chords") or []))
                if _play_chord_idea(session_state, doc, section_id, chord_syms):
                    st.rerun()
                else:
                    st.warning("Could not preview that progression.")
        with c3:
            if st.button("Use", key=f"composer_cmp_tray_use_{section_id}_{qid}", type="primary"):
                apply_section_chords(doc, section_id, list(sug.get("chords") or []))
                invalidate_composer_preview(session_state)
                _save_doc(session_state, doc)
                st.rerun()
        with c4:
            if st.button("✕", key=f"composer_cmp_tray_rm_{section_id}_{qid}", help="Remove from compare"):
                session_state[queue_key] = [x for x in queue if x != qid]
                st.rerun()


def _render_compact_song_settings(session_state: dict, doc: dict[str, Any], *, key_prefix: str) -> None:
    """Keep Key/BPM/Meter editable but out of the way while composing."""
    pg = playback_globals(doc)
    summary = (
        f"{pg.get('key_label') or pg.get('key_center')} · "
        f"{pg['bpm']} BPM · {pg['time_signature']} · "
        f"{(doc.get('metadata') or {}).get('style') or 'Song'}"
    )
    with st.expander(f"Song settings — {summary}", expanded=False):
        g = doc.setdefault("global", {})
        key_labels = composition_key_choice_labels()
        current_label = coerce_composition_key_choice(
            str(g.get("original_key_label") or "")
            or composition_key_label_from_token(str(g.get("original_key_center") or "C"))
        )
        key_widget = f"{key_prefix}_key"
        if key_widget not in session_state:
            session_state[key_widget] = current_label
        picked = st.selectbox("Key", key_labels, key=key_widget)
        bpm_val = st.number_input(
            "Tempo (BPM)",
            min_value=40,
            max_value=240,
            value=coerce_composition_bpm(g.get("bpm")),
            step=1,
            key=f"{key_prefix}_bpm",
        )
        meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]
        stored_meter = coerce_composition_meter(str(g.get("time_signature") or "4/4"))
        meter_key = f"{key_prefix}_meter"
        custom_key = f"{key_prefix}_meter_custom"
        if meter_key not in session_state:
            if stored_meter in COMPOSITION_METERS:
                session_state[meter_key] = stored_meter
                session_state[custom_key] = ""
            else:
                session_state[meter_key] = COMPOSITION_METER_CUSTOM
                session_state[custom_key] = stored_meter
        st.selectbox("Meter", meter_options, key=meter_key)
        if str(session_state.get(meter_key) or "") == COMPOSITION_METER_CUSTOM:
            st.text_input("Custom meter", key=custom_key, placeholder="11/8")
        if st.button("Apply song settings", key=f"{key_prefix}_apply"):
            label = coerce_composition_key_choice(str(picked or current_label))
            g["original_key_label"] = label
            g["original_key_center"] = composition_key_token_from_choice(label)
            g["bpm"] = coerce_composition_bpm(bpm_val)
            meter_choice = str(session_state.get(meter_key) or "4/4")
            if meter_choice == COMPOSITION_METER_CUSTOM:
                meter_choice = str(session_state.get(custom_key) or "").strip()
            g["time_signature"] = coerce_composition_meter(meter_choice)
            _save_doc(session_state, doc)
            st.rerun()


def _render_section_workspace_header(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    lane: str,
) -> None:
    """Make selected section + lane obvious."""
    variant = str(section.get("label_variant") or section.get("label") or "Section")
    lane_title = {"chords": "CHORDS", "melody": "MELODY", "lyrics": "LYRICS"}.get(lane, lane.upper())
    st.markdown(f"### {lane_title} — {variant}")
    st.markdown(
        _section_status_html(doc, str(section.get("id") or "")),
        unsafe_allow_html=True,
    )


def _render_section_nav_strip(
    session_state: dict,
    doc: dict[str, Any],
    *,
    button_prefix: str,
) -> None:
    """Prominent song-section navigation."""
    sections = ordered_sections(doc)
    if not sections:
        st.info("Add sections in Song Structure first.")
        return
    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    st.markdown("**Song sections**")
    cols = st.columns(min(len(sections), 8))
    for i, sec in enumerate(sections):
        sid = str(sec.get("id") or "")
        label = str(sec.get("label_variant") or sec.get("label") or "Section")
        with cols[i % len(cols)]:
            btn_type = "primary" if sid == active_id else "secondary"
            if st.button(
                label,
                key=f"{button_prefix}_{sid}",
                type=btn_type,
                use_container_width=True,
            ):
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = sid
                invalidate_composer_preview(session_state)
                st.rerun()
    if active_id:
        active = section_by_id(doc, active_id)
        if active:
            st.caption(f"Selected: **{active.get('label_variant') or active.get('label')}**")


# Pending suggestion bags — applied in prepare_* BEFORE widgets are created.
COMPOSER_WELCOME_PENDING_SUGGEST_KEY = "composer_welcome_pending_suggest"
COMPOSER_VISION_PENDING_SUGGEST_KEY = "composer_vision_pending_suggest"

WELCOME_WIDGET_KEYS: tuple[str, ...] = (
    "composer_welcome_key",
    "composer_welcome_bpm",
    "composer_welcome_meter",
    "composer_welcome_meter_custom",
    "composer_welcome_genre",
    "composer_welcome_idea",
    "composer_welcome_title",
    "composer_welcome_mood",
    "composer_welcome_energy",
    "composer_welcome_refs",
    "composer_welcome_instrumental",
)


def queue_welcome_starting_values(
    session_state: dict,
    *,
    genre: str,
    song_idea: str,
) -> dict[str, Any]:
    """Build a pending suggest payload — never write widget keys here."""
    hints = suggest_musical_defaults(genre=str(genre or "Pop"), song_idea=str(song_idea or ""))
    suggested_meter = coerce_composition_meter(hints.get("meter"))
    payload: dict[str, Any] = {
        "key": coerce_composition_key_choice(hints.get("key_label") or hints.get("key") or "C major"),
        "bpm": coerce_composition_bpm(hints.get("bpm")),
        "mood": str(hints.get("mood") or ""),
        "energy": str(hints.get("energy") or ""),
    }
    if suggested_meter in COMPOSITION_METERS:
        payload["meter"] = suggested_meter
        payload["meter_custom"] = ""
    else:
        payload["meter"] = COMPOSITION_METER_CUSTOM
        payload["meter_custom"] = suggested_meter
    session_state[COMPOSER_WELCOME_PENDING_SUGGEST_KEY] = payload
    return payload


def prepare_welcome_widget_state(session_state: dict) -> None:
    """Normalize Welcome widget keys BEFORE any Welcome widgets are instantiated.

    Applies pending \"Suggest starting values\" payloads here (next-rerun safe path).
    Must not be called after Welcome widgets exist in the same run.
    """
    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]

    pending = session_state.pop(COMPOSER_WELCOME_PENDING_SUGGEST_KEY, None)
    if isinstance(pending, dict):
        session_state["composer_welcome_key"] = coerce_composition_key_choice(
            pending.get("key") or "C major"
        )
        session_state["composer_welcome_bpm"] = coerce_composition_bpm(pending.get("bpm"))
        meter = str(pending.get("meter") or "4/4")
        if meter == COMPOSITION_METER_CUSTOM or meter not in COMPOSITION_METERS:
            session_state["composer_welcome_meter"] = COMPOSITION_METER_CUSTOM
            session_state["composer_welcome_meter_custom"] = coerce_composition_meter(
                pending.get("meter_custom") or meter
            )
        else:
            session_state["composer_welcome_meter"] = meter
            session_state["composer_welcome_meter_custom"] = ""
        mood = str(pending.get("mood") or "").strip()
        if mood and not str(session_state.get("composer_welcome_mood") or "").strip():
            session_state["composer_welcome_mood"] = mood

    if "composer_welcome_key" not in session_state:
        hints0 = suggest_musical_defaults(genre="Pop", song_idea="")
        session_state["composer_welcome_key"] = coerce_composition_key_choice(
            hints0.get("key_label") or "C major"
        )
        session_state["composer_welcome_bpm"] = coerce_composition_bpm(hints0.get("bpm"))
        session_state["composer_welcome_meter"] = coerce_composition_meter(hints0.get("meter"))
        session_state["composer_welcome_meter_custom"] = ""

    # Coerce legacy / invalid values before selectbox instantiation.
    session_state["composer_welcome_key"] = coerce_composition_key_choice(
        session_state.get("composer_welcome_key")
    )
    if session_state["composer_welcome_key"] not in key_labels:
        session_state["composer_welcome_key"] = key_labels[0]

    session_state["composer_welcome_bpm"] = coerce_composition_bpm(
        session_state.get("composer_welcome_bpm")
    )

    meter_now = str(session_state.get("composer_welcome_meter") or "4/4")
    if meter_now not in meter_options:
        coerced = coerce_composition_meter(meter_now)
        if coerced in COMPOSITION_METERS:
            session_state["composer_welcome_meter"] = coerced
            session_state["composer_welcome_meter_custom"] = ""
        else:
            session_state["composer_welcome_meter"] = COMPOSITION_METER_CUSTOM
            session_state["composer_welcome_meter_custom"] = coerced
    elif meter_now == COMPOSITION_METER_CUSTOM:
        session_state.setdefault("composer_welcome_meter_custom", "")

    if "composer_welcome_genre" in session_state:
        genre = str(session_state.get("composer_welcome_genre") or "Pop")
        if genre not in COMPOSITION_GENRES:
            session_state["composer_welcome_genre"] = "Other"


def queue_vision_mood_energy_suggest(session_state: dict, *, genre: str, song_idea: str) -> dict[str, Any]:
    """Pending mood/energy only — never mutates Key/BPM/Meter widget keys."""
    hints = suggest_musical_defaults(genre=str(genre or "Pop"), song_idea=str(song_idea or ""))
    payload = {
        "mood": str(hints.get("mood") or ""),
        "energy": str(hints.get("energy") or COMPOSITION_ENERGY_LEVELS[1]),
    }
    session_state[COMPOSER_VISION_PENDING_SUGGEST_KEY] = payload
    return payload


def prepare_vision_widget_state(session_state: dict, doc: dict[str, Any]) -> None:
    """Sync + normalize Vision widget keys BEFORE Vision widgets are created."""
    meta = doc.setdefault("metadata", {})
    g = doc.setdefault("global", {})
    wf = ensure_workflow(doc)
    origin_payload = (doc.get("origin") or {}).get("seed_payload") or {}
    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]

    pending = session_state.pop(COMPOSER_VISION_PENDING_SUGGEST_KEY, None)
    if isinstance(pending, dict):
        # Only mood/energy — Key/BPM/Meter remain user-owned.
        if str(pending.get("mood") or "").strip():
            session_state["composer_vision_mood"] = str(pending.get("mood") or "")
        energy = str(pending.get("energy") or "")
        if energy in COMPOSITION_ENERGY_LEVELS:
            session_state["composer_vision_energy"] = energy

    if "composer_vision_genre" not in session_state:
        genre = str(meta.get("style") or "Pop")
        session_state["composer_vision_genre"] = genre if genre in COMPOSITION_GENRES else "Other"
    if "composer_vision_idea" not in session_state:
        session_state["composer_vision_idea"] = str(meta.get("description") or "")
    if "composer_vision_title" not in session_state:
        session_state["composer_vision_title"] = str(doc.get("title") or "")
    if "composer_vision_mood" not in session_state:
        session_state["composer_vision_mood"] = str(meta.get("mood") or "")
    if "composer_vision_energy" not in session_state:
        energy = str(meta.get("energy") or origin_payload.get("energy") or COMPOSITION_ENERGY_LEVELS[1])
        session_state["composer_vision_energy"] = (
            energy if energy in COMPOSITION_ENERGY_LEVELS else COMPOSITION_ENERGY_LEVELS[1]
        )
    if "composer_vision_refs" not in session_state:
        session_state["composer_vision_refs"] = str(meta.get("references") or "")
    if "composer_vision_instrumental" not in session_state:
        session_state["composer_vision_instrumental"] = bool(wf.get("skip_lyrics"))
    if "composer_vision_key" not in session_state:
        stored_label = str(g.get("original_key_label") or "").strip()
        token = str(g.get("original_key_center") or "C")
        session_state["composer_vision_key"] = coerce_composition_key_choice(
            stored_label or composition_key_label_from_token(token)
        )
    if "composer_vision_bpm" not in session_state:
        session_state["composer_vision_bpm"] = coerce_composition_bpm(g.get("bpm"))
    if "composer_vision_meter" not in session_state:
        meter = coerce_composition_meter(str(g.get("time_signature") or "4/4"))
        if meter in COMPOSITION_METERS:
            session_state["composer_vision_meter"] = meter
            session_state["composer_vision_meter_custom"] = ""
        else:
            session_state["composer_vision_meter"] = COMPOSITION_METER_CUSTOM
            session_state["composer_vision_meter_custom"] = meter
    elif "composer_vision_meter_custom" not in session_state:
        session_state["composer_vision_meter_custom"] = ""

    if session_state.get("composer_vision_genre") not in COMPOSITION_GENRES:
        session_state["composer_vision_genre"] = "Other"

    session_state["composer_vision_key"] = coerce_composition_key_choice(
        session_state.get("composer_vision_key")
    )
    if session_state["composer_vision_key"] not in key_labels:
        session_state["composer_vision_key"] = key_labels[0]

    session_state["composer_vision_bpm"] = coerce_composition_bpm(
        session_state.get("composer_vision_bpm")
    )

    if session_state.get("composer_vision_meter") not in meter_options:
        session_state["composer_vision_meter"] = coerce_composition_meter(
            str(session_state.get("composer_vision_meter") or "4/4")
        )
        if session_state["composer_vision_meter"] not in COMPOSITION_METERS:
            custom = session_state["composer_vision_meter"]
            session_state["composer_vision_meter"] = COMPOSITION_METER_CUSTOM
            session_state["composer_vision_meter_custom"] = custom


def _render_welcome_entry(session_state: dict) -> None:
    st.markdown(
        """
<div class="composer-hero">
  <h2>What kind of song do you want to create?</h2>
  <p>Choose the genre, key, tempo, and meter — then write a sentence about your idea.
  You remain the composer; the coach helps you decide, never silently decides for you.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    # PREPARE before any widgets — pending suggest + coerce invalid values.
    prepare_welcome_widget_state(session_state)

    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]

    center, side = st.columns([2.3, 1])
    with center:
        genre = st.selectbox("Genre / style", COMPOSITION_GENRES, key="composer_welcome_genre")
        song_idea = st.text_area(
            "Describe your song idea",
            key="composer_welcome_idea",
            height=100,
            placeholder='e.g. "A hopeful pop song about finding your way home after a long trip."',
        )

        st.markdown("**Song settings** — you choose these")
        k1, k2, k3 = st.columns(3)
        with k1:
            st.selectbox("Key", key_labels, key="composer_welcome_key")
        with k2:
            st.number_input("BPM", min_value=40, max_value=240, step=1, key="composer_welcome_bpm")
        with k3:
            st.selectbox("Meter", meter_options, key="composer_welcome_meter")
        if str(session_state.get("composer_welcome_meter") or "") == COMPOSITION_METER_CUSTOM:
            st.text_input(
                "Custom meter (e.g. 11/8)",
                key="composer_welcome_meter_custom",
                placeholder="11/8",
            )

        if st.button("Suggest starting values from genre / idea", key="composer_welcome_suggest"):
            # Streamlit-safe: queue for next rerun prepare — do NOT write widget keys now.
            queue_welcome_starting_values(
                session_state,
                genre=str(genre or "Pop"),
                song_idea=str(song_idea or ""),
            )
            st.rerun()

        with st.expander("Optional details"):
            st.text_input("Working title", key="composer_welcome_title")
            st.text_input("Mood / emotion", key="composer_welcome_mood")
            st.selectbox("Energy", COMPOSITION_ENERGY_LEVELS, key="composer_welcome_energy")
            st.text_input("Artists or songs that inspire this", key="composer_welcome_refs")
            st.checkbox("This is an instrumental piece (skip lyrics later)", key="composer_welcome_instrumental")

        c1, c2 = st.columns(2)
        with c1:
            begin = st.button("Begin your song →", type="primary", use_container_width=True)
        with c2:
            lib = list_library_documents(session_state)
            resume = bool(lib) and st.button("Resume last composition", use_container_width=True)

        if begin:
            idea = str(session_state.get("composer_welcome_idea") or "").strip()
            if not idea:
                st.error("Tell us your song idea in a sentence or two — that's all we need to begin.")
            else:
                meter_choice = str(session_state.get("composer_welcome_meter") or "4/4")
                if meter_choice == COMPOSITION_METER_CUSTOM:
                    meter_choice = str(session_state.get("composer_welcome_meter_custom") or "").strip()
                doc = bootstrap_from_vision(
                    genre=str(session_state.get("composer_welcome_genre") or "Pop"),
                    song_idea=idea,
                    title=str(session_state.get("composer_welcome_title") or ""),
                    mood=str(session_state.get("composer_welcome_mood") or ""),
                    energy=str(session_state.get("composer_welcome_energy") or ""),
                    references=str(session_state.get("composer_welcome_refs") or ""),
                    instrumental=bool(session_state.get("composer_welcome_instrumental")),
                    key=str(session_state.get("composer_welcome_key") or ""),
                    bpm=session_state.get("composer_welcome_bpm"),
                    meter=meter_choice,
                )
                set_active_document(session_state, doc)
                save_document_to_library(session_state, doc)
                st.rerun()

        if resume:
            load_library_document(session_state, str(lib[0].get("id") or ""))
            st.rerun()

    with side:
        _render_coach_panel(
            {},
            lead=(
                "Think of this as the first minutes with a songwriter in the room. "
                "Pick the key, tempo, and meter yourself — then we'll build structure and sections together."
            ),
        )


def _apply_vision_widgets_to_doc(doc: dict[str, Any]) -> None:
    meta = doc.setdefault("metadata", {})
    g = doc.setdefault("global", {})
    wf = ensure_workflow(doc)
    origin = doc.setdefault("origin", {"seed_type": "vision", "seed_summary": "", "seed_payload": {}})

    genre = str(st.session_state.get("composer_vision_genre") or "Pop")
    idea = str(st.session_state.get("composer_vision_idea") or "").strip()
    meta["style"] = genre
    meta["description"] = idea
    meta["mood"] = str(st.session_state.get("composer_vision_mood") or "").strip()
    meta["energy"] = str(st.session_state.get("composer_vision_energy") or "").strip()
    meta["references"] = str(st.session_state.get("composer_vision_refs") or "").strip()
    doc["title"] = str(st.session_state.get("composer_vision_title") or "").strip() or "Untitled Song"

    key_label = coerce_composition_key_choice(str(st.session_state.get("composer_vision_key") or ""))
    g["original_key_label"] = key_label
    g["original_key_center"] = composition_key_token_from_choice(key_label)
    g["bpm"] = coerce_composition_bpm(st.session_state.get("composer_vision_bpm"))
    meter_choice = str(st.session_state.get("composer_vision_meter") or "4/4")
    if meter_choice == COMPOSITION_METER_CUSTOM:
        meter_choice = str(st.session_state.get("composer_vision_meter_custom") or "").strip()
    g["time_signature"] = coerce_composition_meter(meter_choice)
    g["progression_style"] = genre if genre in CPL_PROGRESSION_STYLES else g.get("progression_style") or "Pop"
    wf["skip_lyrics"] = bool(st.session_state.get("composer_vision_instrumental"))
    origin["seed_summary"] = idea[:500]
    origin.setdefault("seed_payload", {})["genre"] = genre
    origin["seed_payload"]["energy"] = meta["energy"]
    origin["seed_payload"]["references"] = meta["references"]
    origin["seed_payload"]["key_label"] = key_label
    origin["seed_payload"]["user_chose_key"] = True
    origin["seed_payload"]["user_chose_bpm"] = True
    origin["seed_payload"]["user_chose_meter"] = True


def _render_phase_vision(session_state: dict, doc: dict[str, Any]) -> None:
    prepare_vision_widget_state(session_state, doc)
    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]
    center, side = st.columns([2.3, 1])
    with center:
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Song Vision</h3>
  <p>Establish genre, mood, and the song's key / BPM / meter. Structure and section writing come next — freely, not as a locked wizard.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.selectbox("Genre / style", COMPOSITION_GENRES, key="composer_vision_genre")
        st.text_area(
            "What kind of song do you want to create?",
            key="composer_vision_idea",
            height=100,
            placeholder="One or two sentences about theme, story, or feeling.",
        )

        st.markdown("**Key · BPM · Meter** — owned by this composition")
        k1, k2, k3 = st.columns(3)
        with k1:
            st.selectbox("Key", key_labels, key="composer_vision_key")
        with k2:
            st.number_input("BPM", min_value=40, max_value=240, step=1, key="composer_vision_bpm")
        with k3:
            st.selectbox("Meter", meter_options, key="composer_vision_meter")
        if str(session_state.get("composer_vision_meter") or "") == COMPOSITION_METER_CUSTOM:
            st.text_input("Custom meter (e.g. 11/8)", key="composer_vision_meter_custom", placeholder="11/8")

        st.text_input("Working title", key="composer_vision_title")
        with st.expander("Mood, energy & inspiration"):
            st.text_input("Mood / emotion", key="composer_vision_mood")
            st.selectbox("Energy level", COMPOSITION_ENERGY_LEVELS, key="composer_vision_energy")
            st.text_input("Artists or songs that inspire this", key="composer_vision_refs")
            st.checkbox("Instrumental piece (lyrics not applicable)", key="composer_vision_instrumental")

        if st.button("Suggest mood / energy from idea (does not overwrite Key/BPM/Meter)", key="composer_vision_resuggest"):
            # Streamlit-safe pending path — do not mutate widget keys after instantiation.
            queue_vision_mood_energy_suggest(
                session_state,
                genre=str(session_state.get("composer_vision_genre") or "Pop"),
                song_idea=str(session_state.get("composer_vision_idea") or ""),
            )
            st.rerun()

        idea = str(session_state.get("composer_vision_idea") or "").strip()
        if not idea:
            st.warning("Add a sentence or two about your song idea before continuing.")
        elif st.button("Continue to Song Structure →", type="primary", key="composer_vision_continue"):
            _apply_vision_widgets_to_doc(doc)
            advance_workflow(doc, from_phase="vision")
            _save_doc(session_state, doc)
            st.rerun()

    with side:
        _apply_vision_widgets_to_doc(doc)
        _render_coach_panel(doc, lead=_vision_coach_html(doc))
        _render_library_sidebar(session_state)


def _structure_timeline_html(doc: dict[str, Any], selected_id: str) -> str:
    sections = ordered_sections(doc)
    if not sections:
        return (
            '<div class="composer-structure-empty">'
            "<strong>Your song form starts here.</strong><br>"
            "Pick a starter template or add your first section below."
            "</div>"
        )
    chunks: list[str] = ['<div class="composer-structure-track">']
    for idx, sec in enumerate(sections):
        sid = str(sec.get("id") or "")
        css = section_css_type(sec)
        selected = " is-selected" if sid == selected_id else ""
        variant = str(sec.get("label_variant") or sec.get("label") or "Section")
        label = str(sec.get("label") or "Section")
        link = chord_link_display(sec, doc)
        link_html = f'<span class="composer-section-link">{link}</span>' if link else ""
        if idx > 0:
            chunks.append('<div class="composer-structure-arrow">→</div>')
        chunks.append(
            f'<div class="composer-section-block composer-section-{css}{selected}">'
            f'<div class="composer-section-type">{label}</div>'
            f'<div class="composer-section-name">{variant}</div>'
            f"{link_html}"
            f"</div>"
        )
    chunks.append("</div>")
    return "".join(chunks)


def _ensure_structure_selection(session_state: dict, doc: dict[str, Any]) -> str:
    sections = ordered_sections(doc)
    if not sections:
        session_state.pop(COMPOSER_ACTIVE_SECTION_KEY, None)
        return ""
    order = [str(s.get("id") or "") for s in sections]
    active = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    if active not in order:
        active = order[0]
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = active
    return active


def _structure_coach_html(doc: dict[str, Any]) -> str:
    sections = ordered_sections(doc)
    if not sections:
        return (
            "Before chords or melody, sketch the <strong>shape</strong> of your song — "
            "where the energy rises, where it breathes, and where the hook lands."
        )
    names = " → ".join(str(s.get("label_variant") or s.get("label") or "Section") for s in sections[:8])
    extra = " …" if len(sections) > 8 else ""
    return (
        f"Your form so far: <strong>{names}{extra}</strong><br><br>"
        "Repeated sections can share chord progressions — Verse 2 will follow Verse 1 until you break the link."
    )


def _render_phase_structure(session_state: dict, doc: dict[str, Any]) -> None:
    selected_id = _ensure_structure_selection(session_state, doc)
    sections = ordered_sections(doc)
    order_ids = [str(s.get("id") or "") for s in sections]
    center, side = st.columns([2.3, 1])

    with center:
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Song Structure</h3>
  <p>Arrange your song like blocks on a timeline — then jump freely into Chords, Melody, or Lyrics.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="composer-structure-scroll">{_structure_timeline_html(doc, selected_id)}</div>',
            unsafe_allow_html=True,
        )

        if sections:
            st.markdown("**Song sections** — select one, then rearrange")
            strip_cols = st.columns(min(len(sections), 8))
            labels = [str(s.get("label_variant") or s.get("label") or "Section") for s in sections]
            ids = [str(s.get("id") or "") for s in sections]
            for i, (sid, label) in enumerate(zip(ids, labels)):
                sec = sections[i]
                link = sec.get("chord_link") or {}
                link_mark = " 🔗" if link.get("linked") else ""
                with strip_cols[i % len(strip_cols)]:
                    btn_type = "primary" if sid == selected_id else "secondary"
                    if st.button(
                        f"{label}{link_mark}",
                        key=f"composer_structure_sec_{sid}",
                        type=btn_type,
                        use_container_width=True,
                    ):
                        session_state[COMPOSER_ACTIVE_SECTION_KEY] = sid
                        st.rerun()

            active = section_by_id(doc, selected_id) if selected_id else None
            if active:
                idx = order_ids.index(selected_id) if selected_id in order_ids else 0
                st.markdown(f"**Selected:** {active.get('label_variant') or active.get('label')}")
                link = active.get("chord_link") or {}
                if link.get("linked"):
                    st.caption(f"🔗 {chord_link_display(active, doc)}")
                mv = st.columns(4)
                with mv[0]:
                    if st.button(
                        "← Move earlier",
                        key="composer_struct_left",
                        use_container_width=True,
                        disabled=idx <= 0,
                    ):
                        if move_section(doc, selected_id, -1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[1]:
                    if st.button(
                        "Move later →",
                        key="composer_struct_right",
                        use_container_width=True,
                        disabled=idx >= len(order_ids) - 1,
                    ):
                        if move_section(doc, selected_id, 1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[2]:
                    if st.button("Duplicate", key="composer_struct_dup", use_container_width=True):
                        # Independent copy — linking is explicit elsewhere, not automatic.
                        clone = duplicate_section(doc, selected_id, link_chords=False)
                        if clone:
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = clone["id"]
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[3]:
                    if st.button(
                        "Remove",
                        key="composer_struct_remove",
                        use_container_width=True,
                        disabled=len(sections) <= 1,
                    ):
                        prior = list(order_ids)
                        if remove_section(doc, selected_id):
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = neighbor_section_after_remove(
                                doc, selected_id, prior
                            )
                            _save_doc(session_state, doc)
                            st.rerun()
                if link.get("linked"):
                    if st.button("Break chord link (write unique harmony)", key="composer_struct_unlink"):
                        break_chord_link(doc, selected_id)
                        _save_doc(session_state, doc)
                        st.rerun()
        else:
            st.markdown("**Start with a template**")
            t1, t2, t3 = st.columns(3)
            with t1:
                if st.button("Pop song form", key="composer_tpl_pop", use_container_width=True):
                    created = apply_structure_template(doc, "pop")
                    session_state[COMPOSER_ACTIVE_SECTION_KEY] = created[0]["id"] if created else ""
                    _save_doc(session_state, doc)
                    st.rerun()
            with t2:
                if st.button("Simple Verse–Chorus", key="composer_tpl_simple", use_container_width=True):
                    created = apply_structure_template(doc, "simple")
                    session_state[COMPOSER_ACTIVE_SECTION_KEY] = created[0]["id"] if created else ""
                    _save_doc(session_state, doc)
                    st.rerun()
            with t3:
                if st.button("Ballad form", key="composer_tpl_ballad", use_container_width=True):
                    created = apply_structure_template(doc, "ballad")
                    session_state[COMPOSER_ACTIVE_SECTION_KEY] = created[0]["id"] if created else ""
                    _save_doc(session_state, doc)
                    st.rerun()

        st.markdown("---")
        st.markdown("**Add section**")
        a1, a2 = st.columns([2, 1])
        with a1:
            new_label = st.selectbox("Section type", COMPOSER_SECTION_LABELS, key="composer_structure_add_label")
        with a2:
            insert_after = st.checkbox(
                "Insert after selected",
                value=bool(selected_id and sections),
                key="composer_structure_insert_after",
            )
        custom_name = ""
        if str(new_label) == "Custom":
            custom_name = st.text_input(
                "Custom section name",
                key="composer_structure_custom_name",
                placeholder="e.g. Final Chorus · Tag",
            )
        if st.button("+ Add section", key="composer_structure_add_btn", use_container_width=True):
            after = selected_id if insert_after and selected_id else None
            label = "Custom" if str(new_label) == "Custom" else str(new_label)
            sec = add_section(doc, label, after_id=after)
            if str(new_label) == "Custom" and str(custom_name or "").strip():
                sec["label_variant"] = str(custom_name).strip()[:80]
            session_state[COMPOSER_ACTIVE_SECTION_KEY] = sec["id"]
            _save_doc(session_state, doc)
            st.rerun()

        if sections:
            c_cont, c_mel = st.columns(2)
            with c_cont:
                if st.button("Continue to Chords →", type="primary", key="composer_structure_continue", use_container_width=True):
                    advance_workflow(doc, from_phase="structure")
                    _save_doc(session_state, doc)
                    st.rerun()
            with c_mel:
                if st.button("Jump to Melody", key="composer_structure_jump_melody", use_container_width=True):
                    complete_workflow_phase(doc, "structure")
                    set_workflow_phase(doc, "melody")
                    _save_doc(session_state, doc)
                    st.rerun()
        else:
            st.caption("Add at least one section before composing chords or melody.")

    with side:
        _render_coach_panel(doc, lead=_structure_coach_html(doc))
        _render_library_sidebar(session_state)


def _hum_proposal_key(section_id: str) -> str:
    return f"composer_hum_proposal_{section_id}"


def _hum_audio_key(section_id: str) -> str:
    return f"composer_hum_audio_{section_id}"


def _clear_hum_proposal(session_state: dict, section_id: str) -> None:
    session_state.pop(_hum_proposal_key(section_id), None)
    session_state.pop(_hum_audio_key(section_id), None)


def _render_melody_staff(
    events: list[dict[str, Any]],
    *,
    key: str,
    meter: str,
    bpm: int,
    title: str,
    height: int = 200,
    chords: list[Any] | None = None,
    lyrics_text: str = "",
    lyric_syllables: list[str] | None = None,
) -> None:
    """Primary musician-facing score: staff, then chord symbols, then lyrics."""
    score = build_section_score_model(
        events=events,
        chords=chords,
        key=key,
        meter=meter,
        bpm=bpm,
        title=title,
        lyrics_text=lyrics_text,
        lyric_syllables=lyric_syllables,
    )
    st.markdown('<div class="composer-score-wrap">', unsafe_allow_html=True)
    if score["has_melody"]:
        try:
            import streamlit.components.v1 as components

            components.html(
                render_abc_html(str(score["abc"]), height=height),
                height=height,
                scrolling=False,
            )
        except Exception:
            st.code(str(score["abc"]), language="text")
    elif score["has_chords"]:
        st.markdown(
            '<div class="composer-score-empty">Melody not written yet — chords below.</div>',
            unsafe_allow_html=True,
        )
    if score.get("chord_strip_html"):
        st.markdown(str(score["chord_strip_html"]), unsafe_allow_html=True)
    if score.get("lyrics_text"):
        st.markdown(
            f'<div class="composer-score-lyrics">{html.escape(str(score["lyrics_text"]))}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _section_lyrics_text(section: dict[str, Any] | None) -> str:
    if not isinstance(section, dict):
        return ""
    lyrics = section.get("lyrics") or {}
    if not isinstance(lyrics, dict):
        return ""
    return str(lyrics.get("raw_text") or "").strip()


def _render_section_score_view(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    play_key: str,
) -> None:
    """Progressive section score: chords → staff+chords → staff+chords+lyrics."""
    pg = playback_globals(doc)
    events = section_melody_events(section)
    chords = list(section.get("chords") or [])
    lyrics = _section_lyrics_text(section)
    has_chords = bool(chords)
    has_melody = bool(events)
    title = str(section.get("label_variant") or section.get("label") or "Section")

    if not has_chords and not has_melody:
        st.info("Start by choosing or creating harmony for this section.")
        return

    if has_melody:
        _render_melody_staff(
            events,
            key=str(pg.get("key_center") or "C"),
            meter=str(pg.get("time_signature") or "4/4"),
            bpm=int(pg.get("bpm") or 96),
            title=title,
            chords=chords,
            lyrics_text=lyrics,
            lyric_syllables=[
                str(row.get("syllable") or "")
                for row in section_lyric_alignment(section)
                if row.get("event_index") is not None
            ],
        )
    elif has_chords:
        meter = str(pg.get("time_signature") or "4/4")
        chart = cpl_progression_bar_chart_html(chords, time_signature=meter)
        if chart:
            st.markdown(chart, unsafe_allow_html=True)
        st.caption("Your chords are ready. Build or record a melody over them.")

    sid = str(section.get("id") or "")
    _render_section_transport(
        session_state,
        doc,
        sid,
        preview_key=play_key,
        button_label="▶ Play section (chords + melody)" if has_melody else "▶ Play chords",
        loops_key=f"composer_score_loops_{sid}",
        include_melody=has_melody,
        render_preview=False,
    )


def _render_hum_event_editor(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    proposal: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    """Edit proposed (or accepted-copy) events in place; returns updated proposal."""
    pg = playback_globals(doc)
    key = str(pg.get("key_center") or "C")
    meter = str(pg.get("time_signature") or "4/4")
    events = list(proposal.get("events") or [])
    if not events:
        return proposal

    dur_opts = duration_choice_labels(meter)
    dur_values = [d for d, _ in dur_opts]
    dur_labels = {d: lab for d, lab in dur_opts}

    st.caption("Edit any note: pitch, duration, timing, or remove it.")
    from composition_document import section_by_id, section_playback_bars

    sec = section_by_id(doc, section_id)
    max_beats = None
    if sec:
        bars = section_playback_bars(doc, sec)
        try:
            num = int(str(meter).split("/", 1)[0])
        except ValueError:
            num = 4
        max_beats = float(max(1, bars) * num)

    def _commit(updated: list[dict[str, Any]]) -> None:
        proposal["events"] = updated
        session_state[_hum_proposal_key(section_id)] = proposal

    for i, ev in enumerate(events):
        is_rest = bool(ev.get("is_rest")) or str(ev.get("pitch") or "").lower() == "rest"
        cols = st.columns([1.8, 0.7, 0.7, 1.7, 0.7, 0.7, 0.8, 0.7])
        with cols[0]:
            label = "rest" if is_rest else str(ev.get("pitch") or "?")
            flag = " · uncertain" if ev.get("uncertain") else ""
            st.markdown(f"**{i + 1}. {label}{flag}**")
        with cols[1]:
            if not is_rest and st.button("↑", key=f"{prefix}_up_{section_id}_{i}", help="Raise a semitone"):
                _commit(nudge_event_pitch(events, i, semitones=1, key=key))
                st.rerun()
        with cols[2]:
            if not is_rest and st.button("↓", key=f"{prefix}_dn_{section_id}_{i}", help="Lower a semitone"):
                _commit(nudge_event_pitch(events, i, semitones=-1, key=key))
                st.rerun()
        with cols[3]:
            cur_dur = float(ev.get("duration_beats") or 1.0)
            if cur_dur not in dur_values:
                dur_values_local = sorted(set(dur_values + [cur_dur]))
            else:
                dur_values_local = dur_values
            try:
                idx = dur_values_local.index(cur_dur)
            except ValueError:
                idx = 0
            picked = st.selectbox(
                "Duration",
                options=dur_values_local,
                index=idx,
                format_func=lambda d: dur_labels.get(d, f"{d:g} beat"),
                key=f"{prefix}_dur_{section_id}_{i}",
                label_visibility="collapsed",
            )
            if float(picked) != cur_dur:
                _commit(set_event_duration(events, i, float(picked), meter=meter))
                st.rerun()
        with cols[4]:
            if st.button("←", key=f"{prefix}_ear_{section_id}_{i}", help="Move earlier by half a beat"):
                _commit(shift_event_onset(events, i, -0.5, meter=meter, max_beats=max_beats))
                st.rerun()
        with cols[5]:
            if st.button("→", key=f"{prefix}_lat_{section_id}_{i}", help="Move later by half a beat"):
                _commit(shift_event_onset(events, i, 0.5, meter=meter, max_beats=max_beats))
                st.rerun()
        with cols[6]:
            if st.button("Del", key=f"{prefix}_del_{section_id}_{i}", help="Delete note"):
                _commit(delete_melody_event(events, i, meter=meter))
                st.rerun()
        with cols[7]:
            if st.button("+", key=f"{prefix}_ins_{section_id}_{i}", help="Insert note after"):
                midi_ref = int(ev.get("midi") or 60) if not is_rest else 60
                _commit(
                    insert_melody_event(
                        events,
                        i + 1,
                        pitch_midi=midi_ref,
                        duration_beats=1.0,
                        key=key,
                        meter=meter,
                    )
                )
                st.rerun()
    return proposal


def _render_accepted_melody_editor(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
) -> None:
    """Light editor over the canonical timed melody — staff, play, persist, lyrics stay one authority."""
    sec = section_by_id(doc, section_id)
    events = section_melody_events(sec)
    if not events:
        return
    pg = playback_globals(doc)
    key = str(pg.get("key_center") or "C")
    meter = str(pg.get("time_signature") or "4/4")
    dur_choices = duration_choice_labels(meter)
    dur_values = [d for d, _ in dur_choices]
    dur_labels = {d: name for d, name in dur_choices}
    bars = section_playback_bars(doc, sec) if sec else 0
    try:
        num = int(str(meter).split("/", 1)[0])
    except ValueError:
        num = 4
    max_beats = float(max(1, bars) * num)

    st.markdown("**Edit this melody**")
    st.caption("Change pitch, duration, or timing. Staff, playback, and lyric alignment update together.")

    def _commit(updated: list[dict[str, Any]]) -> None:
        apply_accepted_melody_edits(doc, section_id, updated)
        invalidate_composer_preview(session_state)
        _save_doc(session_state, doc)

    for i, ev in enumerate(events):
        is_rest = bool(ev.get("is_rest")) or str(ev.get("pitch") or "").lower() == "rest"
        cols = st.columns([1.8, 0.7, 0.7, 1.7, 0.7, 0.7, 0.8])
        with cols[0]:
            label = "rest" if is_rest else str(ev.get("pitch") or "?")
            st.markdown(f"**{i + 1}. {label}** · beat {float(ev.get('beat') or 0):g}")
        with cols[1]:
            if not is_rest and st.button("↑", key=f"composer_acc_up_{section_id}_{i}", help="Raise a semitone"):
                _commit(nudge_event_pitch(events, i, semitones=1, key=key))
                st.rerun()
        with cols[2]:
            if not is_rest and st.button("↓", key=f"composer_acc_dn_{section_id}_{i}", help="Lower a semitone"):
                _commit(nudge_event_pitch(events, i, semitones=-1, key=key))
                st.rerun()
        with cols[3]:
            cur_dur = float(ev.get("duration_beats") or 1.0)
            local_durs = dur_values if cur_dur in dur_values else sorted(set(dur_values + [cur_dur]))
            try:
                idx = local_durs.index(cur_dur)
            except ValueError:
                idx = 0
            picked = st.selectbox(
                "Duration",
                options=local_durs,
                index=idx,
                format_func=lambda d: dur_labels.get(d, f"{d:g} beat"),
                key=f"composer_acc_dur_{section_id}_{i}",
                label_visibility="collapsed",
            )
            if float(picked) != cur_dur:
                _commit(set_event_duration(events, i, float(picked), meter=meter))
                st.rerun()
        with cols[4]:
            if st.button("←", key=f"composer_acc_ear_{section_id}_{i}", help="Move earlier"):
                _commit(shift_event_onset(events, i, -0.5, meter=meter, max_beats=max_beats))
                st.rerun()
        with cols[5]:
            if st.button("→", key=f"composer_acc_lat_{section_id}_{i}", help="Move later"):
                _commit(shift_event_onset(events, i, 0.5, meter=meter, max_beats=max_beats))
                st.rerun()
        with cols[6]:
            if st.button("Del", key=f"composer_acc_del_{section_id}_{i}", help="Remove note"):
                _commit(delete_melody_event(events, i, meter=meter))
                st.rerun()


_ORIGIN_MIC_FIRST = "mic_first"
_ORIGIN_RECORDER_LATE = "recorder_late"


def _record_origin_keys(section_id: str) -> dict[str, str]:
    sid = str(section_id or "")
    return {
        "mode": f"composer_record_origin_mode_{sid}",
        "lead": f"composer_mic_lead_{sid}",
        "late": f"composer_record_delay_{sid}",
        "armed_at": f"composer_mic_armed_at_{sid}",
        "resolved": f"composer_resolved_origin_{sid}",
    }


def _init_record_origin_widgets(session_state: dict, section_id: str, timeline: dict[str, Any] | None) -> None:
    """Seed origin widgets from a persisted timeline once per section."""
    keys = _record_origin_keys(section_id)
    tl = timeline if isinstance(timeline, dict) else {}
    try:
        lead = float(tl.get("mic_lead_beats") or 0.0)
    except (TypeError, ValueError):
        lead = 0.0
    try:
        late = float(tl.get("recorder_late_beats") or tl.get("recorder_start_delay_beats") or 0.0)
    except (TypeError, ValueError):
        late = 0.0
    if keys["mode"] not in session_state:
        session_state[keys["mode"]] = _ORIGIN_RECORDER_LATE if late > 0 and lead <= 0 else _ORIGIN_MIC_FIRST
    if keys["lead"] not in session_state:
        session_state[keys["lead"]] = lead
    if keys["late"] not in session_state:
        session_state[keys["late"]] = late
    if keys["resolved"] not in session_state and tl:
        session_state[keys["resolved"]] = {
            "mic_lead_beats": lead,
            "recorder_late_beats": late,
        }


def _armed_record_offsets_from_panel(
    session_state: dict,
    section_id: str,
    *,
    bpm: int,
) -> tuple[float, float]:
    """Return (mic_lead_beats, recorder_late_beats) from the honest origin panel.

    Mic-first is the primary workflow: backing/count-in began ``mic_lead`` capture
    beats after the recorder. A leftover ``Mark I'm recording now`` timestamp
    estimates that lead when the number field is still 0.
    """
    keys = _record_origin_keys(section_id)
    mode = str(session_state.get(keys["mode"]) or _ORIGIN_MIC_FIRST)
    try:
        widget_lead = max(0.0, float(session_state.get(keys["lead"]) or 0.0))
    except (TypeError, ValueError):
        widget_lead = 0.0
    try:
        widget_late = max(0.0, float(session_state.get(keys["late"]) or 0.0))
    except (TypeError, ValueError):
        widget_late = 0.0
    resolved = session_state.get(keys["resolved"])
    resolved = resolved if isinstance(resolved, dict) else {}

    if mode == _ORIGIN_RECORDER_LATE:
        return 0.0, widget_late

    if widget_lead > 0:
        return widget_lead, 0.0
    try:
        stored_lead = max(0.0, float(resolved.get("mic_lead_beats") or 0.0))
    except (TypeError, ValueError):
        stored_lead = 0.0
    if stored_lead > 0:
        return stored_lead, 0.0
    armed_at = session_state.get(keys["armed_at"])
    if armed_at:
        try:
            elapsed = max(0.0, time.time() - float(armed_at))
        except (TypeError, ValueError):
            elapsed = 0.0
        return elapsed * float(max(40, int(bpm or 96))) / 60.0, 0.0
    return 0.0, 0.0


def _render_hum_sing_panel(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    active_id: str,
) -> None:
    """Record melody (voice or instrument) → staff proposal → edit → accept."""
    pg = playback_globals(doc)
    key = str(pg.get("key_center") or "C")
    meter = str(pg.get("time_signature") or "4/4")
    bpm = int(pg.get("bpm") or 96)
    accepted = section_melody_events(section)
    chords = list(section.get("chords") or [])
    proposal = session_state.get(_hum_proposal_key(active_id))
    if not isinstance(proposal, dict):
        proposal = None

    st.markdown("**Play / Hum My Melody**")
    st.caption("Hum, sing, or play one melodic line over the selected chords. We’ll write it as sheet music.")
    timeline = session_state.get(f"composer_record_timeline_{active_id}")
    if not isinstance(timeline, dict):
        capture = ((section.get("melody") or {}).get("intent") or {}).get("hum_capture") or {}
        timeline = capture.get("timeline") if isinstance(capture, dict) else None
    origin_keys = _record_origin_keys(active_id)
    _init_record_origin_widgets(session_state, active_id, timeline if isinstance(timeline, dict) else None)

    st.info(
        "The Streamlit microphone cannot start with the backing from one click, so this is not a locked sync. "
        "**1. Start recording first.** Optionally click **Mark I'm recording now**. "
        "**2. Start the count-in + backing.** "
        "A note on beat 1 of the section is at capture beat (mic lead + count-in). "
        "Alignment is `section_beat = capture_beat − backing_origin_in_capture_beats`. "
        "If the recorder started after the backing, switch to that mode instead of claiming a lock."
    )

    if not hum_analysis_available():
        st.info(
            "Pitch transcription needs librosa on this server. "
            "Recording still works as a capture marker; explore melody ideas below."
        )

    st.markdown("**1. Arm the microphone**")
    try:
        audio = st.audio_input(
            "Start recording now (voice or instrument)",
            key=f"composer_melody_record_{active_id}",
        )
    except Exception:
        audio = None
        st.caption("Audio recording will appear here when your browser supports it.")

    st.radio(
        "Recorder vs backing start",
        options=[_ORIGIN_MIC_FIRST, _ORIGIN_RECORDER_LATE],
        format_func=lambda v: (
            "Microphone first (normal)"
            if v == _ORIGIN_MIC_FIRST
            else "Recorder started after backing"
        ),
        key=origin_keys["mode"],
        help=(
            "Primary flow: the mic is already running when count-in + backing begin. "
            "Use the other option only if recording started after the backing."
        ),
    )
    origin_mode = str(session_state.get(origin_keys["mode"]) or _ORIGIN_MIC_FIRST)
    if origin_mode == _ORIGIN_RECORDER_LATE:
        st.number_input(
            "Recorder started after backing by (beats)",
            min_value=0.0,
            max_value=32.0,
            step=0.5,
            key=origin_keys["late"],
            help="Mic started this many beats after backing/count-in. backing_origin = count-in − this value.",
        )
    else:
        mark_col, lead_col = st.columns([1, 1])
        with mark_col:
            if st.button(
                "Mark I'm recording now",
                key=f"composer_mark_mic_{active_id}",
                use_container_width=True,
                help="Store the moment you started the recorder so Start can measure mic lead.",
            ):
                session_state[origin_keys["armed_at"]] = time.time()
                st.rerun()
        with lead_col:
            st.number_input(
                "Backing began this many beats after I started recording",
                min_value=0.0,
                max_value=32.0,
                step=0.5,
                key=origin_keys["lead"],
                help=(
                    "Primary offset D: mic at capture beat 0, backing/count-in starts D beats later. "
                    "A note on section beat 0 is at capture beat D + count-in. "
                    "Leave 0 and use Mark I'm recording now to measure D."
                ),
            )
        armed_at = session_state.get(origin_keys["armed_at"])
        if armed_at:
            try:
                elapsed = max(0.0, time.time() - float(armed_at))
                est = elapsed * float(max(40, bpm)) / 60.0
                st.caption(
                    f"Recorder marked running · about {est:g} beats at {bpm} BPM. "
                    "Start count-in will use this as mic lead if the box is still 0."
                )
            except (TypeError, ValueError):
                pass

    mic_lead_beats, recorder_late_beats = _armed_record_offsets_from_panel(
        session_state, active_id, bpm=bpm
    )

    st.markdown("**2. Start count-in + backing**")
    if st.button(
        "Start count-in + backing",
        key=f"composer_hum_play_backing_{active_id}",
        type="primary",
        use_container_width=True,
        disabled=not bool(chords),
    ):
        timeline = prepare_armed_record_transport(
            doc,
            active_id,
            mic_lead_beats=float(mic_lead_beats or 0.0),
            recorder_late_beats=float(recorder_late_beats or 0.0),
            count_in_bars=1,
        )
        session_state[f"composer_record_timeline_{active_id}"] = timeline
        session_state[origin_keys["resolved"]] = {
            "mic_lead_beats": float(timeline.get("mic_lead_beats") or 0.0),
            "recorder_late_beats": float(timeline.get("recorder_late_beats") or 0.0),
        }
        intent = section.setdefault("melody", {}).setdefault("intent", {})
        capture = intent.setdefault("hum_capture", {})
        capture["timeline"] = timeline
        capture["analysis_status"] = "ready_to_record"
        capture["origin"] = timeline.get("origin")
        capture["sync_locked"] = False
        capture["mic_lead_beats"] = timeline.get("mic_lead_beats")
        capture["recorder_late_beats"] = timeline.get("recorder_late_beats")
        capture["backing_origin_in_capture_beats"] = timeline.get("backing_origin_in_capture_beats")
        result = play_composer_preview(
            session_state,
            doc,
            section_id=active_id,
            include_melody=False,
            loops=1,
            count_in_bars=1,
        )
        _save_doc(session_state, doc)
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Add chords first so backing can play while you record."))
        st.rerun()
    if isinstance(timeline, dict) and timeline.get("chord_changes"):
        lead_beats = float(timeline.get("mic_lead_beats") or 0.0)
        late_beats = float(timeline.get("recorder_late_beats") or 0.0)
        cin = float(timeline.get("count_in_beats") or 0.0)
        origin_in_capture = float(timeline.get("backing_origin_in_capture_beats") or 0.0)
        st.caption(
            f"Armed count-in transport · {timeline.get('meter')} · {timeline.get('bpm')} BPM · "
            f"{int(timeline.get('section_bars') or 0)} bars · count-in {cin:g} beats · "
            f"mic lead {lead_beats:g} · recorder late {late_beats:g} · "
            f"backing_origin_in_capture_beats {origin_in_capture:g}. "
            "section_beat = capture_beat − backing_origin. Not a locked mic/speaker sync."
        )
    elif not chords:
        st.caption("Add chords first — then arm the microphone and start the count-in.")

    if audio is not None:
        try:
            raw = audio.getvalue() if hasattr(audio, "getvalue") else b""
        except Exception:
            raw = b""
        if raw:
            session_state[_hum_audio_key(active_id)] = raw
            intent = section.setdefault("melody", {}).setdefault("intent", {})
            capture = intent.setdefault("hum_capture", {})
            capture["captured"] = True
            capture["bytes_len"] = len(raw)
            capture["analysis_status"] = "ready_to_analyze"
            capture["note_detection"] = False

    has_audio = bool(session_state.get(_hum_audio_key(active_id)))
    a1, a2, a3 = st.columns(3)
    with a1:
        analyze = st.button(
            "Analyze recording",
            type="primary",
            key=f"composer_hum_analyze_{active_id}",
            disabled=not has_audio,
            use_container_width=True,
        )
    with a2:
        if st.button("Record again", key=f"composer_hum_again_{active_id}", use_container_width=True):
            _clear_hum_proposal(session_state, active_id)
            intent = section.setdefault("melody", {}).setdefault("intent", {})
            capture = intent.setdefault("hum_capture", {})
            capture["analysis_status"] = "cleared"
            capture["note_detection"] = False
            st.rerun()
    with a3:
        if proposal and st.button("Dismiss proposal", key=f"composer_hum_dismiss_{active_id}", use_container_width=True):
            _clear_hum_proposal(session_state, active_id)
            st.rerun()

    if analyze:
        audio_bytes = session_state.get(_hum_audio_key(active_id)) or b""
        mic_lead_beats, recorder_late_beats = _armed_record_offsets_from_panel(
            session_state, active_id, bpm=bpm
        )
        if not isinstance(timeline, dict):
            timeline = prepare_armed_record_transport(
                doc,
                active_id,
                mic_lead_beats=float(mic_lead_beats or 0.0),
                recorder_late_beats=float(recorder_late_beats or 0.0),
                count_in_bars=1,
            )
        else:
            timeline = apply_record_origin(
                timeline,
                mic_lead_beats=float(mic_lead_beats or 0.0),
                recorder_late_beats=float(recorder_late_beats or 0.0),
                count_in_beats=timeline.get("count_in_beats"),
                origin=str(timeline.get("origin") or "armed_count_in"),
            )
        session_state[f"composer_record_timeline_{active_id}"] = timeline
        session_state[origin_keys["resolved"]] = {
            "mic_lead_beats": float(timeline.get("mic_lead_beats") or 0.0),
            "recorder_late_beats": float(timeline.get("recorder_late_beats") or 0.0),
        }
        result = transcribe_hum_audio(
            audio_bytes,
            bpm=bpm,
            meter=meter,
            key=key,
            timeline=timeline,
        )
        session_state[_hum_proposal_key(active_id)] = result
        intent = section.setdefault("melody", {}).setdefault("intent", {})
        capture = intent.setdefault("hum_capture", {})
        capture["timeline"] = timeline
        capture["origin"] = timeline.get("origin")
        capture["sync_locked"] = False
        capture["mic_lead_beats"] = timeline.get("mic_lead_beats")
        capture["recorder_late_beats"] = timeline.get("recorder_late_beats")
        capture["backing_origin_in_capture_beats"] = timeline.get("backing_origin_in_capture_beats")
        capture["analysis_status"] = str(result.get("status") or "unclear")
        capture["note_detection"] = bool(result.get("events"))
        _save_doc(session_state, doc)
        st.rerun()

    proposal = session_state.get(_hum_proposal_key(active_id))
    if isinstance(proposal, dict) and proposal.get("status"):
        status = str(proposal.get("status") or "")
        msg = str(proposal.get("message") or "")
        events = list(proposal.get("events") or [])
        if status in {"unavailable", "unclear"} or not events:
            st.warning(msg or "Could not transcribe that recording.")
        else:
            if status == "uncertain":
                st.info(msg or "Check the staff — some notes look uncertain.")
            else:
                st.success("Here’s what we heard — check the sheet music before using this melody.")

            # PRIMARY: sheet music (not a raw note list).
            st.markdown("**You sang / played this:**")
            _render_melody_staff(
                events,
                key=key,
                meter=meter,
                bpm=bpm,
                title=f"{section.get('label_variant') or section.get('label') or 'Section'} — proposed",
                chords=chords,
            )
            _render_active_preview(session_state, stop_key=f"composer_hum_preview_stop_{active_id}")

            p1, p2 = st.columns(2)
            with p1:
                if st.button(
                    "▶ Preview with chords",
                    key=f"composer_hum_preview_{active_id}",
                    use_container_width=True,
                ):
                    result = play_composer_preview(
                        session_state,
                        doc,
                        section_id=active_id,
                        include_melody=True,
                        melody_override=events,
                        loops=1,
                    )
                    if result.get("ok"):
                        st.rerun()
                    else:
                        st.warning(str(result.get("reason") or "Add chords to this section first."))
            with p2:
                use_label = "Replace existing melody" if accepted else "Use this melody"
                if st.button(
                    use_label,
                    type="primary",
                    key=f"composer_hum_use_{active_id}",
                    use_container_width=True,
                ):
                    apply_melody_events(
                        doc,
                        active_id,
                        events,
                        concept={
                            "id": "hum_transcription",
                            "name": "Recorded melody",
                            "motif_hint": "Transcribed from your recording",
                            "contour": "Captured from your recording — check the staff.",
                        },
                        replace=True,
                        source="recorded",
                    )
                    align_lyrics_to_melody(doc, active_id)
                    _clear_hum_proposal(session_state, active_id)
                    invalidate_composer_preview(session_state)
                    _save_doc(session_state, doc)
                    st.rerun()

            # SECONDARY: note editor behind an expander — not the default face.
            with st.expander("Edit melody (notes)", expanded=False):
                proposal = _render_hum_event_editor(
                    session_state, doc, active_id, proposal, prefix="composer_hum_edit"
                )
                # Staff refreshes from edited events on next widgets pass.
                edited = list(proposal.get("events") or [])
                if edited != events:
                    st.caption("Staff above updates after each edit.")

            if accepted:
                st.caption(
                    "This section already has an accepted melody. "
                    "Preview leaves it untouched; Replace updates it explicitly."
                )


def _render_melody_concept_card(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    concept: dict[str, Any],
    *,
    prefix: str,
) -> None:
    cid = str(concept.get("id") or prefix)
    name = str(concept.get("name") or "Melodic idea")
    contour = str(concept.get("contour") or "")
    why = str(concept.get("why") or "")
    events = list(concept.get("events") or concept.get("notes_events") or [])
    sec = section_by_id(doc, section_id) or {}
    chords = list(sec.get("chords") or [])
    pg = playback_globals(doc)

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(name)}</h4>
  <p class="composer-suggestion-why">{html.escape(contour)}</p>
  {f'<p class="composer-suggestion-why">{html.escape(why)}</p>' if why else ""}
</div>
        """,
        unsafe_allow_html=True,
    )
    if events:
        _render_melody_staff(
            events,
            key=str(pg.get("key_center") or "C"),
            meter=str(pg.get("time_signature") or "4/4"),
            bpm=int(pg.get("bpm") or 96),
            title=name,
            height=180,
            chords=chords,
        )
    p1, p2 = st.columns(2)
    with p1:
        if st.button("▶ Preview with chords", key=f"{prefix}_preview_{cid}", use_container_width=True):
            result = play_composer_preview(
                session_state,
                doc,
                section_id=section_id,
                include_melody=True,
                melody_override=events or None,
            )
            if result.get("ok"):
                st.rerun()
            elif section_has_resolved_chords(doc, section_id):
                st.warning(str(result.get("reason") or "Could not generate preview."))
            else:
                st.info("Add chords to this section first — then hear melody ideas in context.")
    with p2:
        if st.button("Use this melody", key=f"{prefix}_use_{cid}", type="primary", use_container_width=True):
            if events:
                apply_melody_events(
                    doc, section_id, events, concept=concept, replace=True, source="ai"
                )
            else:
                apply_melody_concept(doc, section_id, concept)
            align_lyrics_to_melody(doc, section_id)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()


def _render_melody_phrases_editor(session_state: dict, doc: dict[str, Any], section_id: str) -> None:
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    melody = sec.setdefault("melody", {"intent": {}, "phrases": []})
    phrases = list(melody.get("phrases") or [])

    if phrases:
        st.markdown("**Your melodic phrases**")
        for phrase in phrases:
            if not isinstance(phrase, dict):
                continue
            pid = str(phrase.get("id") or "")
            plabel = str(phrase.get("label") or "Phrase")
            pmotif = str(phrase.get("motif") or "")
            pnotes = str(phrase.get("notes") or "")
            st.markdown(f"**{plabel}**")
            if pmotif:
                st.caption(pmotif)
            if pnotes:
                st.code(pnotes)
            if st.button("Remove phrase", key=f"composer_melody_rm_{section_id}_{pid}"):
                remove_melody_phrase(doc, section_id, pid)
                _save_doc(session_state, doc)
                st.rerun()

    st.markdown("**Add a phrase manually**")
    label = st.text_input("Phrase label", value="Main hook", key=f"composer_melody_phrase_label_{section_id}")
    motif = st.text_area(
        "Describe the contour or motif",
        key=f"composer_melody_phrase_motif_{section_id}",
        placeholder="e.g. Step up from root to 5th, hold, step down",
    )
    notes = st.text_area(
        "Notes (optional)",
        key=f"composer_melody_phrase_notes_{section_id}",
        placeholder="e.g. C D E G E or solfege / ABC paste",
    )
    if st.button("Save phrase", key=f"composer_melody_phrase_save_{section_id}"):
        add_melody_phrase(doc, section_id, label=label, motif=motif, notes=notes)
        _save_doc(session_state, doc)
        st.rerun()


def _render_phase_melody(session_state: dict, doc: dict[str, Any]) -> None:
    _ensure_active_section(session_state, doc)
    sections = ordered_sections(doc)
    if not sections:
        st.warning("Your song has no sections yet. Head back to **Song Structure** first.")
        return

    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    section = section_by_id(doc, active_id) or sections[0]
    active_id = str(section.get("id") or "")
    session_state[COMPOSER_ACTIVE_SECTION_KEY] = active_id

    melody = section.setdefault("melody", {"intent": {}, "phrases": []})
    intent = melody.setdefault("intent", {})

    center, side = st.columns([2.3, 1])
    with center:
        done, total = melodized_section_count(doc)
        st.markdown(
            f'<p class="composer-harmony-progress">Melody progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_compact_song_settings(session_state, doc, key_prefix=f"composer_melody_settings_{doc.get('id')}")
        _render_section_nav_strip(session_state, doc, button_prefix="composer_melody_nav")
        _render_section_lane_switcher(session_state, doc, active_lane="melody")
        _render_section_workspace_header(session_state, doc, section, lane="melody")
        _render_active_preview(session_state, stop_key=f"composer_melody_preview_stop_{active_id}")

        has_harmony = section_has_resolved_chords(doc, active_id)
        if not has_harmony:
            st.markdown(
                '<div class="composer-chords-first-banner">'
                "<strong>Tip:</strong> Shape harmony first when you can — then write the melody on top.</div>",
                unsafe_allow_html=True,
            )
            if st.button("Go to Chords for this section", key=f"composer_melody_to_chords_{active_id}"):
                set_workflow_phase(doc, "chords")
                _save_doc(session_state, doc)
                st.rerun()
        else:
            # A. Current melody status as score (staff + chords + lyrics when present)
            st.markdown("**This section**")
            _render_section_score_view(
                session_state,
                doc,
                section,
                play_key=f"composer_melody_hear_structure_{active_id}",
            )
            if section_melody_events(section):
                _render_accepted_melody_editor(session_state, doc, active_id)

        feel_ids = [f[0] for f in MELODY_FEELINGS]
        current_feel = str(intent.get("feel") or default_melody_feel_for_section(section))
        if current_feel not in feel_ids:
            current_feel = default_melody_feel_for_section(section)
        style_ids = [s[0] for s in MELODY_STYLES]
        current_style = str(intent.get("style") or "simple")
        if current_style not in style_ids:
            current_style = "simple"

        with st.expander("Melody feel & notes (optional)", expanded=not bool(section_melody_events(section))):
            remember = st.text_input(
                "What should listeners remember?",
                value=str(intent.get("remember") or ""),
                key=f"composer_melody_remember_{active_id}",
                placeholder="e.g. The rising hook on the word 'home'",
            )
            picked_feel = st.radio(
                "Melody feel",
                options=feel_ids,
                index=feel_ids.index(current_feel),
                format_func=lambda fid: next(l for i, l in MELODY_FEELINGS if i == fid),
                key=f"composer_melody_feel_{active_id}",
            )
            picked_style = st.radio(
                "Style",
                options=style_ids,
                index=style_ids.index(current_style),
                format_func=lambda sid: next(l for i, l in MELODY_STYLES if i == sid),
                key=f"composer_melody_style_{active_id}",
                horizontal=True,
            )
            hum = st.text_area(
                "Optional jot notes",
                value=str(intent.get("hum_notes") or ""),
                key=f"composer_melody_hum_{active_id}",
                height=60,
                placeholder="Optional text notes — recording below is preferred.",
            )
            if (
                remember != intent.get("remember")
                or picked_feel != intent.get("feel")
                or picked_style != intent.get("style")
                or hum != intent.get("hum_notes")
            ):
                intent["remember"] = remember
                intent["feel"] = picked_feel
                intent["style"] = picked_style
                intent["hum_notes"] = hum
                _save_doc(session_state, doc)

        # B. Record a melody
        if has_harmony:
            _render_hum_sing_panel(session_state, doc, section, active_id=active_id)
        else:
            st.caption("Add chords for this section to hear harmony while you record.")

        # C. Explore melody ideas (notation-first cards)
        st.markdown("**Explore melody ideas**")
        concepts = suggest_melody_concepts(doc, section, picked_feel, picked_style, limit=3)
        for i, concept in enumerate(concepts):
            _render_melody_concept_card(
                session_state, doc, active_id, concept, prefix=f"composer_melody_explore_{active_id}_{i}"
            )

        with st.expander("Shape / refine accepted melody", expanded=False):
            st.caption("Local refinements adjust your accepted events — staff updates after Apply.")
            ref_cols = st.columns(min(4, len(MELODY_REFINEMENTS)))
            for i, (rid, label, _) in enumerate(MELODY_REFINEMENTS[:4]):
                with ref_cols[i % len(ref_cols)]:
                    if st.button(label, key=f"composer_melody_ref_{active_id}_{rid}", use_container_width=True):
                        apply_melody_refinement_to_section(doc, active_id, rid)
                        _save_doc(session_state, doc)
                        st.rerun()

        with st.expander("Advanced phrase editor", expanded=False):
            _render_melody_phrases_editor(session_state, doc, active_id)

        if done > 0 and st.button("Continue →", type="primary", key="composer_melody_continue"):
            advance_workflow(doc, from_phase="melody")
            _save_doc(session_state, doc)
            st.rerun()

    with side:
        _render_coach_panel(
            doc,
            lead=coach_line_for_melody(
                doc,
                section,
                feel=str(intent.get("feel") or picked_feel),
                remember=str(intent.get("remember") or remember),
            ),
        )
        st.caption("Record or explore ideas — sheet music is the main result.")
        _render_library_sidebar(session_state)


def _render_phase_placeholder(session_state: dict, doc: dict[str, Any], phase: str) -> None:
    labels = {
        "lyrics": (
            "Lyrics",
            "Write words section by section, tied to your song form.",
            "CS-B4",
        ),
        "review": (
            "Review",
            "See the whole song, jump to edit, and play through from top to bottom.",
            "CS-B5",
        ),
    }
    title, blurb, sprint = labels.get(phase, ("Phase", "Coming soon.", "CS-B?"))
    center, side = st.columns([2.3, 1])
    with center:
        st.markdown(
            f"""
<div class="composer-phase-card">
  <h3>{title}</h3>
  <p>{blurb}</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.info(f"This workspace ships in **{sprint}**. Use the journey rail to revisit Song Vision or Chords.")
        wf = ensure_workflow(doc)
        back_phase = COMPOSITION_PHASES[max(0, COMPOSITION_PHASES.index(phase) - 1)]
        if phase != "review":
            nxt = COMPOSITION_PHASES[COMPOSITION_PHASES.index(phase) + 1] if phase in COMPOSITION_PHASES else None
            if nxt == "lyrics" and wf.get("skip_lyrics"):
                nxt = "review"
            if nxt and st.button(f"Mark done & continue →", key=f"composer_stub_advance_{phase}"):
                advance_workflow(doc, from_phase=phase)
                _save_doc(session_state, doc)
                st.rerun()
        if st.button(f"← Back to {COMPOSITION_PHASE_LABELS.get(back_phase, back_phase)}", key=f"composer_stub_back_{phase}"):
            set_workflow_phase(doc, back_phase)
            _save_doc(session_state, doc)
            st.rerun()
    with side:
        _render_coach_panel(
            doc,
            lead=f"You're making progress — {title.lower()} is the next layer of your original song.",
        )
        _render_library_sidebar(session_state)


def _ensure_active_section(session_state: dict, doc: dict[str, Any]) -> None:
    order = list((doc.get("form") or {}).get("section_order") or [])
    active = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    if order and active not in order:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0]
    elif order and not active:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0]
    elif not order:
        sec = add_section(doc, "Verse")
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = sec["id"]
        _save_doc(session_state, doc)


def _render_snapshot_strip(session_state: dict, doc: dict[str, Any]) -> None:
    section_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    lane = str(session_state.get(COMPOSER_FOCUS_LANE_KEY) or "chords")
    snap = build_composition_snapshot(doc, active_section_id=section_id, focus_lane=lane)
    session_state["composer_snapshot_stamp"] = snapshot_invalidate_token(doc)
    g = snap.get("global") or {}
    commit = snap.get("commitment") or {}
    bits = [
        f"<strong>{snap.get('active_section_label') or 'Section'}</strong>",
        f"Key {g.get('key_center', 'C')}",
        f"{g.get('bpm', 96)} BPM",
        str(g.get("time_signature") or "4/4"),
    ]
    if g.get("style"):
        bits.append(str(g["style"]))
    if g.get("mood"):
        bits.append(str(g["mood"]))
    flags = []
    if commit.get("has_chords"):
        flags.append("chords")
    if commit.get("has_lyrics"):
        flags.append("lyrics")
    if commit.get("has_melody"):
        flags.append("melody")
    flag_txt = f" · Connected: {', '.join(flags)}" if flags else ""
    st.markdown(
        f'<div class="composer-snapshot-strip">{" · ".join(bits)}{flag_txt}</div>',
        unsafe_allow_html=True,
    )


def _render_structure_column(session_state: dict, doc: dict[str, Any]) -> None:
    st.markdown("**Form**")
    sections = ordered_sections(doc)
    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    for sec in sections:
        sid = str(sec.get("id") or "")
        label = str(sec.get("label_variant") or sec.get("label") or "Section")
        chord_line = format_entries_bar_line(sec.get("chords") or [], max_chords=6)
        is_active = sid == active_id
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"{label}", key=f"composer_sec_pick_{sid}", type=btn_type, use_container_width=True):
            session_state[COMPOSER_ACTIVE_SECTION_KEY] = sid
            invalidate_composer_preview(session_state)
            st.rerun()
        if chord_line and chord_line != "(empty)":
            st.caption(chord_line[:80])

    st.markdown("---")
    add_cols = st.columns(2)
    with add_cols[0]:
        new_label = st.selectbox("Add section", COMPOSER_SECTION_LABELS, key="composer_add_section_label")
        if st.button("+ Add", key="composer_add_section_btn", use_container_width=True):
            sec = add_section(doc, new_label)
            session_state[COMPOSER_ACTIVE_SECTION_KEY] = sec["id"]
            _save_doc(session_state, doc)
            st.rerun()
    with add_cols[1]:
        if st.button("Duplicate", key="composer_dup_section", use_container_width=True) and active_id:
            clone = duplicate_section(doc, active_id, link_chords=False)
            if clone:
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = clone["id"]
                _save_doc(session_state, doc)
                st.rerun()

    mv1, mv2, rm = st.columns(3)
    with mv1:
        if st.button("↑", key="composer_sec_up", disabled=not active_id) and active_id:
            if move_section(doc, active_id, -1):
                _save_doc(session_state, doc)
                st.rerun()
    with mv2:
        if st.button("↓", key="composer_sec_down", disabled=not active_id) and active_id:
            if move_section(doc, active_id, 1):
                _save_doc(session_state, doc)
                st.rerun()
    with rm:
        if st.button("Remove", key="composer_sec_remove", disabled=len(sections) <= 1) and active_id:
            if remove_section(doc, active_id):
                order = list((doc.get("form") or {}).get("section_order") or [])
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0] if order else ""
                _save_doc(session_state, doc)
                st.rerun()


def _render_chords_lane(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    owner_id: str | None = None,
) -> None:
    sid = str(section.get("id") or "")
    owner_id = owner_id or sid
    entries = section.setdefault("chords", [])
    g = doc.setdefault("global", {})
    meter = str(g.get("time_signature") or "4/4")

    chart = cpl_progression_bar_chart_html(entries, time_signature=meter)
    if chart:
        st.markdown(chart, unsafe_allow_html=True)
    else:
        st.caption("Build your progression below — one chord at a time, or paste a full line.")

    pending_key = _pending_chord_key(sid)
    pending = st.session_state.get(pending_key)

    vocab = guided_chord_vocabulary(doc, section) or list(_COMPOSER_QUICK_CHORDS)
    rows = [list(vocab[i : i + 5]) for i in range(0, len(vocab), 5)]
    for ri, row in enumerate(rows):
        cols = st.columns(len(row))
        for ci, chord in enumerate(row):
            with cols[ci]:
                if st.button(chord, key=f"composer_ch_{sid}_{ri}_{ci}", use_container_width=True):
                    sym = normalize_chord_symbol(chord)
                    if sym:
                        entries.append({"chord": sym, "bars": 1})
                        st.session_state.pop(pending_key, None)
                        sync_linked_chord_sections(doc, owner_id)
                        _save_doc(session_state, doc)
                        st.rerun()

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Same as previous (%)", key=f"composer_repeat_{sid}", use_container_width=True):
            entries.append({"repeat": True, "bars": 1})
            sync_linked_chord_sections(doc, owner_id)
            _save_doc(session_state, doc)
            st.rerun()
    with c2:
        if st.button("Undo last chord", key=f"composer_undo_chord_{sid}", use_container_width=True):
            if entries:
                entries.pop()
                sync_linked_chord_sections(doc, owner_id)
                _save_doc(session_state, doc)
                st.rerun()
    with c3:
        if st.button("Clear section", key=f"composer_clear_{sid}", use_container_width=True):
            section["chords"] = []
            sync_linked_chord_sections(doc, owner_id)
            _save_doc(session_state, doc)
            st.rerun()

    paste = st.text_input("Paste progression", key=f"composer_paste_{sid}", placeholder="| G | Am | C | D |")
    if st.button("Apply paste", key=f"composer_paste_apply_{sid}") and paste:
        section["chords"] = parse_chord_paste(paste)
        sync_linked_chord_sections(doc, owner_id)
        _save_doc(session_state, doc)
        st.rerun()

    if pending:
        st.info(f"Pending chord: {pending} (legacy — use grid buttons)")


def _render_rhythm_lane(session_state: dict, doc: dict[str, Any]) -> None:
    g = doc.setdefault("global", {})
    meta = doc.setdefault("metadata", {})
    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]
    c1, c2, c3 = st.columns(3)
    with c1:
        g["bpm"] = coerce_composition_bpm(
            st.number_input(
                "BPM",
                min_value=40,
                max_value=240,
                value=coerce_composition_bpm(g.get("bpm")),
                step=1,
                key="composer_rhythm_bpm",
            )
        )
    with c2:
        stored_meter = coerce_composition_meter(str(g.get("time_signature") or "4/4"))
        if "composer_rhythm_meter" not in session_state:
            if stored_meter in COMPOSITION_METERS:
                session_state["composer_rhythm_meter"] = stored_meter
                session_state["composer_rhythm_meter_custom"] = ""
            else:
                session_state["composer_rhythm_meter"] = COMPOSITION_METER_CUSTOM
                session_state["composer_rhythm_meter_custom"] = stored_meter
        meter_choice = st.selectbox("Meter", meter_options, key="composer_rhythm_meter")
        if meter_choice == COMPOSITION_METER_CUSTOM:
            custom = st.text_input("Custom meter", key="composer_rhythm_meter_custom", placeholder="11/8")
            g["time_signature"] = coerce_composition_meter(custom)
        else:
            g["time_signature"] = coerce_composition_meter(meter_choice)
    with c3:
        g["progression_style"] = st.selectbox(
            "Style",
            CPL_PROGRESSION_STYLES,
            index=CPL_PROGRESSION_STYLES.index(g.get("progression_style") or "Pop")
            if g.get("progression_style") in CPL_PROGRESSION_STYLES
            else 0,
            key="composer_rhythm_style",
        )
    g["groove_style"] = st.selectbox(
        "Groove",
        ["Auto", "Ballad", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova"],
        index=0,
        key="composer_rhythm_groove",
    )
    current_label = coerce_composition_key_choice(
        str(g.get("original_key_label") or "")
        or composition_key_label_from_token(str(g.get("original_key_center") or "C"))
    )
    if "composer_rhythm_key" not in session_state:
        session_state["composer_rhythm_key"] = current_label
    picked_label = st.selectbox("Song key", key_labels, key="composer_rhythm_key")
    label = coerce_composition_key_choice(str(picked_label or current_label))
    g["original_key_label"] = label
    g["original_key_center"] = composition_key_token_from_choice(label)
    meta["mood"] = st.text_input("Mood / emotion (optional)", value=str(meta.get("mood") or ""), key="composer_rhythm_mood")
    if st.button("Apply rhythm settings", key="composer_apply_rhythm", type="primary"):
        meta["style"] = g.get("progression_style") or meta.get("style")
        _save_doc(session_state, doc)
        st.rerun()


def _render_section_transport(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    *,
    chord_override: list[str] | None = None,
    preview_key: str = "composer_play_btn",
    button_label: str = "▶ Preview section",
    loops_key: str = "composer_play_loops",
    include_melody: bool = False,
    melody_override: list[dict[str, Any]] | None = None,
    render_preview: bool = True,
    stop_key: str = "composer_preview_stop",
) -> None:
    loops = int(session_state.get(loops_key) or session_state.get("composer_play_loops") or 2)
    has_mel = bool(melody_override) or bool(section_melody_events(section_by_id(doc, section_id)))
    if include_melody and has_mel:
        button_label = button_label if "melody" in button_label.lower() or "+" in button_label else "▶ Play section (chords + melody)"
    elif not include_melody:
        button_label = button_label if button_label else "▶ Play chords"

    t1, t2 = st.columns([2, 3])
    with t1:
        loops = st.slider("Loops", 1, 4, loops, key=loops_key)
        session_state["composer_play_loops"] = loops
    with t2:
        play = st.button(button_label, type="primary", key=preview_key, use_container_width=True)

    if play:
        result = play_composer_preview(
            session_state,
            doc,
            scope="section",
            section_id=section_id,
            loops=loops,
            chord_override=chord_override,
            include_melody=include_melody,
            melody_override=melody_override,
        )
        if result.get("ok"):
            st.rerun()
        else:
            st.warning(str(result.get("reason") or "Add chords to this section first — melody sits on your harmony."))

    if render_preview:
        _render_active_preview(session_state, stop_key=stop_key)


def _render_workflow_section_strip(
    session_state: dict,
    doc: dict[str, Any],
    *,
    done_fn,
    button_prefix: str,
    jump_key: str,
) -> None:
    sections = ordered_sections(doc)
    if not sections:
        st.info("Add sections in Song Structure first.")
        return
    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    st.caption("Song sections — select any section anytime")
    cols = st.columns(min(len(sections), 6))
    for i, sec in enumerate(sections):
        sid = str(sec.get("id") or "")
        label = str(sec.get("label_variant") or sec.get("label") or "Section")
        done = " ✓" if done_fn(sec) else ""
        with cols[i % len(cols)]:
            btn_type = "primary" if sid == active_id else "secondary"
            if st.button(
                f"{label}{done}",
                key=f"{button_prefix}_{sid}",
                type=btn_type,
                use_container_width=True,
            ):
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = sid
                invalidate_composer_preview(session_state)
                st.rerun()
    if active_id:
        st.markdown(_section_status_html(doc, active_id), unsafe_allow_html=True)
    if len(sections) > 6:
        labels = [str(s.get("label_variant") or s.get("label") or "Section") for s in sections]
        ids = [str(s.get("id") or "") for s in sections]
        pick = st.selectbox(
            "Jump to section",
            options=range(len(ids)),
            index=ids.index(active_id) if active_id in ids else 0,
            format_func=lambda i: labels[i],
            key=jump_key,
        )
        if ids[pick] != active_id:
            session_state[COMPOSER_ACTIVE_SECTION_KEY] = ids[pick]
            invalidate_composer_preview(session_state)
            st.rerun()


def _render_chords_section_strip(session_state: dict, doc: dict[str, Any]) -> None:
    _render_workflow_section_strip(
        session_state,
        doc,
        done_fn=section_has_chords,
        button_prefix="composer_chord_sec",
        jump_key="composer_chords_jump_section",
    )


def _render_melody_section_strip(session_state: dict, doc: dict[str, Any]) -> None:
    _render_workflow_section_strip(
        session_state,
        doc,
        done_fn=section_has_melody,
        button_prefix="composer_melody_sec",
        jump_key="composer_melody_jump_section",
    )


def _render_lyrics_section_strip(session_state: dict, doc: dict[str, Any]) -> None:
    _render_workflow_section_strip(
        session_state,
        doc,
        done_fn=section_has_lyrics,
        button_prefix="composer_lyrics_sec",
        jump_key="composer_lyrics_jump_section",
    )


def _render_lyric_prompt_card(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    prompt: dict[str, Any],
    *,
    prefix: str,
) -> None:
    pid = str(prompt.get("id") or prefix)
    name = str(prompt.get("name") or "Writing prompt")
    body = str(prompt.get("prompt") or "")
    why = str(prompt.get("why") or "")

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{name}</h4>
  <div class="composer-suggestion-chords">{body}</div>
  <p class="composer-suggestion-why">{why}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns(2)
    with p1:
        if st.button("Use as starter", key=f"{prefix}_use_{pid}", type="primary", use_container_width=True):
            apply_lyric_prompt_to_section(doc, section_id, prompt)
            _save_doc(session_state, doc)
            st.rerun()
    with p2:
        if st.button("+ Compare", key=f"{prefix}_compare_{pid}", use_container_width=True):
            queue_key = f"composer_lyrics_compare_{section_id}"
            queue = list(session_state.get(queue_key) or [])
            if pid not in queue:
                queue.append(pid)
            session_state[queue_key] = queue[-3:]
            st.rerun()


def _render_lyrics_editor(session_state: dict, doc: dict[str, Any], section_id: str) -> None:
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    lyrics = sec.setdefault(
        "lyrics",
        {"intent": {}, "lines": [], "raw_text": ""},
    )
    raw = st.text_area(
        "Lyrics for this section",
        value=str(lyrics.get("raw_text") or ""),
        key=f"composer_lyrics_raw_{section_id}",
        height=220,
        placeholder="Write lines here when you're ready — one section at a time.",
    )
    if raw != lyrics.get("raw_text"):
        apply_lyrics_text(doc, section_id, raw)
        _save_doc(session_state, doc)


def _render_phase_lyrics(session_state: dict, doc: dict[str, Any]) -> None:
    wf = ensure_workflow(doc)
    if wf.get("skip_lyrics"):
        st.info("This song is marked **instrumental** — lyrics are skipped.")
        if st.button("Continue to Review →", type="primary", key="composer_lyrics_skip_to_review"):
            set_workflow_phase(doc, "review")
            _save_doc(session_state, doc)
            st.rerun()
        return

    _ensure_active_section(session_state, doc)
    sections = ordered_sections(doc)
    if not sections:
        st.warning("Your song has no sections yet. Head back to **Song Structure** first.")
        return

    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    section = section_by_id(doc, active_id) or sections[0]
    active_id = str(section.get("id") or "")
    session_state[COMPOSER_ACTIVE_SECTION_KEY] = active_id

    lyrics = section.setdefault("lyrics", {"intent": {}, "lines": [], "raw_text": ""})
    intent = lyrics.setdefault("intent", {})
    variant = str(section.get("label_variant") or section.get("label") or "Section")

    center, side = st.columns([2.3, 1])
    with center:
        done, total = lyrics_section_count(doc)
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Lyrics</h3>
  <p>What story or message are you telling? Discover what you want to say before you worry about rhymes.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="composer-harmony-progress">Lyrics progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_lyrics_section_strip(session_state, doc)
        _render_section_lane_switcher(session_state, doc, active_lane="lyrics")
        st.markdown(f"### {variant}")

        # Combined section score when chords/melody exist (lyrics appear once written).
        if section_has_chords(section) or section_melody_events(section):
            st.markdown("**This section**")
            _render_section_score_view(
                session_state,
                doc,
                section,
                play_key=f"composer_lyrics_score_play_{active_id}",
            )

        st.markdown("**What is this section trying to communicate?**")
        communicate = st.text_input(
            "Communicate",
            value=str(intent.get("communicate") or ""),
            key=f"composer_lyrics_communicate_{active_id}",
            placeholder="e.g. The loneliness of leaving home for the first time",
            label_visibility="collapsed",
        )

        emotion_ids = [e[0] for e in LYRIC_EMOTIONS]
        current_emotion = str(intent.get("emotion") or "")
        if current_emotion not in emotion_ids:
            current_emotion = emotion_ids[0]

        st.markdown("**What emotion should listeners feel here?**")
        picked_emotion = st.radio(
            "Lyric emotion",
            options=emotion_ids,
            index=emotion_ids.index(current_emotion),
            format_func=lambda eid: next(l for i, l in LYRIC_EMOTIONS if i == eid),
            key=f"composer_lyrics_emotion_{active_id}",
            label_visibility="collapsed",
        )

        role_ids = [r[0] for r in LYRIC_SECTION_ROLES]
        current_role = str(intent.get("role") or default_role_for_section(section))
        if current_role not in role_ids:
            current_role = default_role_for_section(section)

        st.markdown("**What role does this section play?**")
        picked_role = st.radio(
            "Lyric role",
            options=role_ids,
            index=role_ids.index(current_role),
            format_func=lambda rid: next(l for i, l in LYRIC_SECTION_ROLES if i == rid),
            key=f"composer_lyrics_role_{active_id}",
            label_visibility="collapsed",
        )

        st.markdown("**What should someone remember after hearing this section?**")
        remember = st.text_input(
            "Remember",
            value=str(intent.get("remember") or ""),
            key=f"composer_lyrics_remember_{active_id}",
            placeholder="e.g. That home is still there, even when you're far away",
            label_visibility="collapsed",
        )

        if (
            communicate != intent.get("communicate")
            or picked_emotion != intent.get("emotion")
            or picked_role != intent.get("role")
            or remember != intent.get("remember")
        ):
            intent["communicate"] = communicate
            intent["emotion"] = picked_emotion
            intent["role"] = picked_role
            intent["remember"] = remember
            _save_doc(session_state, doc)

        raw_preview = str(lyrics.get("raw_text") or "").strip()
        if raw_preview:
            st.markdown("**Current lyrics**")
            preview_lines = raw_preview.splitlines()[:4]
            for line in preview_lines:
                st.markdown(f"- {line}")
            if len(raw_preview.splitlines()) > 4:
                st.caption("…more in the lyric editor below")

        st.markdown("**How would you like to explore?**")
        path = st.radio(
            "Lyrics workflow",
            ["brainstorm", "explore", "compare", "write"],
            horizontal=True,
            key=f"composer_lyrics_path_{active_id}",
            format_func=lambda x: {
                "brainstorm": "Brainstorm ideas",
                "explore": "Explore writing prompts",
                "compare": "Compare directions",
                "write": "Write my own lyrics",
            }[x],
        )

        prompts = suggest_lyric_prompts(doc, section, picked_role, limit=3)
        brainstorm = suggest_lyric_brainstorm_ideas(
            doc,
            section,
            picked_role,
            emotion=picked_emotion,
            communicate=communicate,
            remember=remember,
            limit=3,
        )

        if path == "brainstorm":
            st.caption("Quick angles to spark a line — adopt a starter or let it point you somewhere new.")
            for i, idea in enumerate(brainstorm):
                _render_lyric_prompt_card(
                    session_state,
                    doc,
                    active_id,
                    idea,
                    prefix=f"composer_lyrics_brain_{active_id}_{i}",
                )
        elif path == "explore":
            st.caption("Structured prompts for this section's role — use one as a jumping-off point.")
            for i, prompt in enumerate(prompts):
                _render_lyric_prompt_card(
                    session_state,
                    doc,
                    active_id,
                    prompt,
                    prefix=f"composer_lyrics_explore_{active_id}_{i}",
                )
        elif path == "compare":
            queue_key = f"composer_lyrics_compare_{active_id}"
            all_items = brainstorm + prompts
            pids = [str(p.get("id") or "") for p in all_items]
            labels_map = {pid: str(p.get("name") or pid) for pid, p in zip(pids, all_items)}
            queue = st.multiselect(
                "Select up to 3 directions to compare",
                options=pids,
                default=[q for q in list(session_state.get(queue_key) or []) if q in pids][:3],
                format_func=lambda x: labels_map.get(x, x),
                key=f"composer_lyrics_compare_select_{active_id}",
            )
            session_state[queue_key] = queue[:3]
            if queue:
                by_id = {str(p.get("id")): p for p in all_items}
                for i, qid in enumerate(queue[:3]):
                    item = by_id.get(qid)
                    if item:
                        _render_lyric_prompt_card(
                            session_state,
                            doc,
                            active_id,
                            item,
                            prefix=f"composer_lyrics_cmp_{active_id}_{i}",
                        )
            else:
                st.info("Pick directions above to compare different lyrical approaches.")
        else:
            st.caption("Direct writing when you already know what you want to say.")
            with st.expander("Lyric editor", expanded=not bool(raw_preview)):
                _render_lyrics_editor(session_state, doc, active_id)

        if done > 0 and st.button("Continue to Review →", type="primary", key="composer_lyrics_continue"):
            advance_workflow(doc, from_phase="lyrics")
            _save_doc(session_state, doc)
            st.rerun()
        elif done == 0:
            st.caption("Write at least one section's lyrics (or use a starter prompt) before continuing.")

    with side:
        _render_coach_panel(
            doc,
            lead=coach_line_for_lyrics(
                doc,
                section,
                role=picked_role,
                emotion=picked_emotion,
                remember=remember,
            ),
        )
        _render_library_sidebar(session_state)


def _render_suggestion_card(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    suggestion: dict[str, Any],
    *,
    prefix: str,
) -> None:
    sid = str(suggestion.get("id") or prefix)
    line = str(suggestion.get("line") or "")
    why = str(suggestion.get("why") or "")
    name = str(suggestion.get("name") or "Suggestion")
    entries = list(suggestion.get("chords") or [])
    chord_syms = expand_entries_to_chords(entries)
    queue_key = _compare_queue_key(section_id)
    in_compare = sid in list(session_state.get(queue_key) or [])
    preview_sig = session_state.get(COMPOSER_PREVIEW_SIG_KEY)
    is_active_preview = (
        isinstance(preview_sig, tuple)
        and len(preview_sig) >= 4
        and tuple(chord_syms) == tuple(preview_sig[3] or ())
        and bool(session_state.get(COMPOSER_PREVIEW_WAV_KEY))
    )

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(name)}{" · previewing" if is_active_preview else ""}{" · comparing" if in_compare else ""}</h4>
  <div class="composer-suggestion-chords">{html.escape(line)}</div>
  <p class="composer-suggestion-why">{html.escape(why)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("▶ Preview", key=f"{prefix}_preview_{sid}", use_container_width=True):
            if _play_chord_idea(session_state, doc, section_id, chord_syms):
                st.rerun()
            else:
                st.warning("Could not generate preview for that progression.")
    with p2:
        if st.button("Use this", key=f"{prefix}_use_{sid}", type="primary", use_container_width=True):
            apply_section_chords(doc, section_id, entries)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
    with p3:
        cmp_label = "Comparing ✓" if in_compare else "+ Compare"
        if st.button(cmp_label, key=f"{prefix}_compare_{sid}", use_container_width=True):
            queue = list(session_state.get(queue_key) or [])
            if sid in queue:
                queue = [x for x in queue if x != sid]
            else:
                queue.append(sid)
            session_state[queue_key] = queue[-3:]
            st.rerun()


def _render_chord_refinement_panel(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    section: dict[str, Any],
) -> None:
    entries = list(section.get("chords") or [])
    if not entries:
        return
    st.markdown("**Refine this progression**")
    st.caption("Describe the musical change — we propose an edit you can preview before accepting.")
    intent_ids = [i[0] for i in CHORD_REFINEMENT_INTENTS]
    picked = st.selectbox(
        "I want this to…",
        intent_ids,
        format_func=refinement_intent_label,
        key=f"composer_refine_intent_{section_id}",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Propose change", key=f"composer_refine_propose_{section_id}", type="primary", use_container_width=True):
            proposal = propose_chord_refinement(doc, section, picked, entries=entries)
            session_state[f"composer_refine_proposal_{section_id}"] = proposal
            st.rerun()
    with c2:
        if st.button("Clear proposal", key=f"composer_refine_clear_{section_id}", use_container_width=True):
            session_state.pop(f"composer_refine_proposal_{section_id}", None)
            st.rerun()

    proposal = session_state.get(f"composer_refine_proposal_{section_id}")
    if not isinstance(proposal, dict):
        return
    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(str(proposal.get('name') or 'Proposed change'))}</h4>
  <div class="composer-suggestion-chords">
    <span style="opacity:0.65">{html.escape(str(proposal.get('source_line') or ''))}</span>
    <br>→ <strong>{html.escape(str(proposal.get('line') or ''))}</strong>
  </div>
  <p class="composer-suggestion-why">{html.escape(str(proposal.get('why') or ''))}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    chord_syms = expand_entries_to_chords(list(proposal.get("chords") or []))
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("▶ Preview", key=f"composer_refine_preview_{section_id}", use_container_width=True):
            if _play_chord_idea(session_state, doc, section_id, chord_syms):
                st.rerun()
            else:
                st.warning("Could not preview that proposal.")
    with a2:
        if st.button("Use this", key=f"composer_refine_use_{section_id}", type="primary", use_container_width=True):
            apply_section_chords(doc, section_id, list(proposal.get("chords") or []))
            session_state.pop(f"composer_refine_proposal_{section_id}", None)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
    with a3:
        if st.button("Try another", key=f"composer_refine_another_{section_id}", use_container_width=True):
            # Rotate to next intent for a fresh local proposal.
            idx = intent_ids.index(picked) if picked in intent_ids else 0
            nxt = intent_ids[(idx + 1) % len(intent_ids)]
            session_state[f"composer_refine_intent_{section_id}"] = nxt
            session_state[f"composer_refine_proposal_{section_id}"] = propose_chord_refinement(
                doc, section, nxt, entries=entries
            )
            st.rerun()
    with a4:
        if st.button("Dismiss", key=f"composer_refine_dismiss_{section_id}", use_container_width=True):
            session_state.pop(f"composer_refine_proposal_{section_id}", None)
            st.rerun()


def _render_transport(session_state: dict, doc: dict[str, Any]) -> None:
    section_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    scope = str(session_state.get("composer_play_scope") or "section")
    loops = int(session_state.get("composer_play_loops") or 2)
    t1, t2, t3 = st.columns([2, 2, 3])
    with t1:
        scope = st.radio("Play scope", ["section", "song"], horizontal=True, key="composer_play_scope")
    with t2:
        loops = st.slider("Loops", 1, 4, loops, key="composer_play_loops")
    with t3:
        play = st.button("▶ Play", type="primary", key="composer_play_btn", use_container_width=True)

    if play:
        result = play_composer_preview(
            session_state,
            doc,
            scope=scope,
            section_id=section_id if scope == "section" else None,
            loops=loops,
            include_melody=True,
        )
        if result.get("ok"):
            st.rerun()
        else:
            st.warning(str(result.get("reason") or "Add at least one chord before playing."))

    _render_active_preview(session_state)


def _render_phase_chords(session_state: dict, doc: dict[str, Any]) -> None:
    _ensure_active_section(session_state, doc)
    sections = ordered_sections(doc)
    if not sections:
        st.warning("Your song has no sections yet. Head back to **Song Structure** to design the form.")
        return

    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    section = section_by_id(doc, active_id) or sections[0]
    active_id = str(section.get("id") or "")
    session_state[COMPOSER_ACTIVE_SECTION_KEY] = active_id

    edit_id, edit_section = harmony_edit_target(doc, active_id)
    is_linked = edit_id != active_id
    link = section.get("chord_link") or {}
    target_id = edit_id or active_id

    center, side = st.columns([2.3, 1])
    with center:
        done, total = harmonized_section_count(doc)
        st.markdown(
            f'<p class="composer-harmony-progress">Harmony progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_compact_song_settings(session_state, doc, key_prefix=f"composer_chords_settings_{doc.get('id')}")
        _render_section_nav_strip(session_state, doc, button_prefix="composer_chords_nav")
        _render_section_lane_switcher(session_state, doc, active_lane="chords")
        _render_section_workspace_header(session_state, doc, section, lane="chords")
        # Always show audition dock so Preview works even before chords are accepted.
        _render_active_preview(session_state, stop_key=f"composer_chords_preview_stop_{active_id}")

        if is_linked and link.get("linked"):
            source = section_by_id(doc, edit_id)
            src_label = str((source or {}).get("label_variant") or (source or {}).get("label") or "source section")
            st.markdown(
                f'<div class="composer-linked-banner">🔗 Harmony is linked to <strong>{src_label}</strong>. '
                f"Edit there, or break the link to write independent chords.</div>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Edit harmony on {src_label}", key="composer_chords_goto_source", use_container_width=True):
                    session_state[COMPOSER_ACTIVE_SECTION_KEY] = edit_id
                    invalidate_composer_preview(session_state)
                    st.rerun()
            with c2:
                if st.button("Break link & edit here", key="composer_chords_break_link", use_container_width=True):
                    break_chord_link(doc, active_id)
                    _save_doc(session_state, doc)
                    st.rerun()
            if edit_section and section_has_chords(edit_section):
                g = doc.setdefault("global", {})
                meter = str(g.get("time_signature") or "4/4")
                chart = cpl_progression_bar_chart_html(edit_section.get("chords") or [], time_signature=meter)
                if chart:
                    st.markdown(chart, unsafe_allow_html=True)
                _render_section_transport(session_state, doc, edit_id)
        else:
            harmony = edit_section.setdefault("harmony", {"feeling": ""}) if edit_section else {"feeling": ""}
            if not isinstance(harmony, dict):
                harmony = {"feeling": ""}
                if edit_section is not None:
                    edit_section["harmony"] = harmony
            feeling_ids = [f[0] for f in SECTION_HARMONY_FEELINGS]
            current_feeling = str(harmony.get("feeling") or default_feeling_for_section(section))
            if current_feeling not in feeling_ids:
                current_feeling = default_feeling_for_section(section)
            st.markdown("**Feeling for this section**")
            picked = st.radio(
                "Section feeling",
                options=feeling_ids,
                index=feeling_ids.index(current_feeling),
                format_func=lambda fid: next(l for i, l in SECTION_HARMONY_FEELINGS if i == fid),
                key=f"composer_feeling_{active_id}",
                label_visibility="collapsed",
            )
            if picked != harmony.get("feeling"):
                harmony["feeling"] = picked
                _save_doc(session_state, doc)

            entries = list(edit_section.get("chords") or []) if edit_section else []

            # A. Current progression / empty state
            if entries:
                st.markdown("**Current progression**")
                g = doc.setdefault("global", {})
                meter = str(g.get("time_signature") or "4/4")
                chart = cpl_progression_bar_chart_html(entries, time_signature=meter)
                if chart:
                    st.markdown(chart, unsafe_allow_html=True)
                # B. Hear it
                _render_section_transport(
                    session_state,
                    doc,
                    target_id,
                    button_label="▶ Play chords",
                    preview_key=f"composer_chords_play_{active_id}",
                    loops_key=f"composer_chords_loops_{active_id}",
                    include_melody=False,
                    render_preview=False,
                )
                st.info("Your chords are ready. Build or hum a melody over them — or keep refining harmony.")
                if st.button("Build a melody over these chords →", key=f"composer_chords_to_melody_{active_id}"):
                    session_state[COMPOSER_FOCUS_LANE_KEY] = "melody"
                    set_workflow_phase(doc, "melody")
                    _save_doc(session_state, doc)
                    st.rerun()
            else:
                st.info("Start by choosing or creating harmony for this section.")

            more_key = f"composer_chords_more_{active_id}"
            more = bool(session_state.get(more_key))
            suggestions = suggest_progressions(doc, section, picked, limit=3, more=more)

            # Visible compare tray (works from Explore or Compare path)
            _render_compare_tray(session_state, doc, target_id, suggestions)

            # C. Harmony suggestions
            st.markdown("**Harmony suggestions**")
            st.caption("Preview to hear · Use this to accept · Compare to keep options side by side.")
            for i, sug in enumerate(suggestions):
                _render_suggestion_card(
                    session_state, doc, target_id, sug, prefix=f"composer_explore_{active_id}_{i}"
                )
            more_c1, more_c2 = st.columns(2)
            with more_c1:
                if st.button(
                    "More options" if not more else "Show fewer options",
                    key=f"composer_chords_more_btn_{active_id}",
                    use_container_width=True,
                ):
                    session_state[more_key] = not more
                    st.rerun()
            with more_c2:
                st.caption("Additional choices stay in this song's style and key.")

            # D. Refine
            if entries:
                _render_chord_refinement_panel(session_state, doc, target_id, edit_section or section)

            # E. Manual / Advanced
            with st.expander("Manual / advanced chord editor", expanded=False):
                if edit_section:
                    _render_chords_lane(session_state, doc, edit_section, owner_id=target_id)

        if done > 0 and st.button("Continue to Melody →", type="primary", key="composer_chords_continue"):
            advance_workflow(doc, from_phase="chords")
            _save_doc(session_state, doc)
            st.rerun()

    with side:
        feeling = str((edit_section or section).get("harmony", {}).get("feeling") or default_feeling_for_section(section))
        _render_coach_panel(doc, lead=coach_line_for_section(doc, section, feeling=feeling))
        _render_library_sidebar(session_state)


def render_composition_studio_page() -> None:
    session_state = st.session_state
    try:
        from composition_workspace_state_persistence import prepare_composition_workspace_for_render

        prepare_composition_workspace_for_render(session_state)
    except ImportError:
        pass
    init_composer_page_state(session_state)
    inject_composition_studio_styles()

    needs_welcome = bool(session_state.get(COMPOSER_NEEDS_SEED_KEY)) and not get_active_document(session_state)
    if needs_welcome:
        _render_welcome_entry(session_state)
        return

    doc = get_active_document(session_state)
    if not doc:
        session_state[COMPOSER_NEEDS_SEED_KEY] = True
        st.rerun()
        return

    ensure_workflow(doc)
    # Align focus lane with restored workflow when landing on section lanes.
    phase = get_workflow_phase(doc)
    if phase in {"chords", "melody", "lyrics", "review"}:
        session_state[COMPOSER_FOCUS_LANE_KEY] = phase
    _render_journey_rail(session_state, doc)

    if phase == "vision":
        _render_phase_vision(session_state, doc)
    elif phase == "structure":
        _render_phase_structure(session_state, doc)
    elif phase == "chords":
        _render_phase_chords(session_state, doc)
    elif phase == "melody":
        _render_phase_melody(session_state, doc)
    elif phase == "lyrics":
        _render_phase_lyrics(session_state, doc)
    elif phase == "review":
        _render_phase_review(session_state, doc)
    else:
        _render_phase_vision(session_state, doc)
