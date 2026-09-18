"""Composition Studio — guided six-phase songwriting workspace (CS-B0+)."""

from __future__ import annotations

import copy
import html
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
    suggest_progressions,
)
from composition_chord_refinements import (
    CHORD_REFINEMENT_INTENTS,
    propose_chord_refinement,
    refinement_intent_label,
)
from composition_chord_repeats import (
    CHORD_REPEAT_MAX,
    CHORD_REPEAT_MIN,
    COMPLETION_COPY,
    accept_chord_pattern,
    accept_full_progression,
    chords_are_tiled,
    ensure_harmony_chord_meta,
    entry_symbols,
    format_full_progression_display,
    get_chord_repeats,
    get_chord_source_id,
    pattern_length_for_display,
    set_section_chord_repeats,
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
    describe_melody_from_events,
    suggest_melody_concepts,
    MELODY_REFINEMENTS,
    apply_melody_refinement_to_section,
)
from composition_melody_shape import (
    apply_natural_language_melody_edit,
    delete_melody_note_preserve_gap,
    events_signature,
    insert_melody_note,
    propose_melody_refinement,
    resolve_melody_edit_choice,
)
from composition_document import (
    COMPOSITION_ENERGY_LEVELS,
    COMPOSITION_GENRES,
    COMPOSITION_JEWISH_DIRECTIONS,
    COMPOSITION_METER_CUSTOM,
    COMPOSITION_METERS,
    COMPOSITION_PHASE_LABELS,
    COMPOSITION_PHASES,
    COMPOSER_SECTION_LABELS,
    DEFAULT_JEWISH_DIRECTION,
    add_section,
    add_melody_phrase,
    advance_workflow,
    apply_melody_concept,
    apply_lyric_prompt_to_section,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    break_chord_link,
    chord_link_display,
    chords_for_playback,
    coerce_composition_bpm,
    coerce_composition_key_choice,
    coerce_composition_key_choice_for_doc,
    coerce_composition_meter,
    coerce_jewish_direction,
    complete_workflow_phase,
    composition_key_choice_labels,
    composition_key_choice_labels_for_family,
    composition_key_label_from_token,
    composition_key_token_from_choice,
    composition_mode_family_from_key,
    document_has_structure,
    document_summary_line,
    duplicate_section,
    ensure_original_mode_family,
    ensure_workflow,
    get_workflow_phase,
    get_active_melody_source_id,
    harmonized_section_count,
    harmony_edit_target,
    lyrics_section_count,
    melodized_section_count,
    melody_harmony_is_stale,
    move_section,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    playback_globals,
    remove_section,
    set_original_mode_family_from_key,
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
    apply_melody_events,
    section_lane_status,
    set_workflow_phase,
    suggest_musical_defaults,
    sync_linked_chord_sections,
    touch_composition,
)
from composition_preview import (
    composer_preview_slot,
    generate_preview_wav,
    invalidate_composer_preview,
    play_composer_preview,
    preview_signature,
    render_local_composer_playback,
    set_composer_preview,
)
from composition_chord_manual_editor import (
    ALTERATION_OPTIONS,
    QUALITY_OPTIONS,
    ROOT_OPTIONS,
    annotate_chromatic,
    build_chord_symbol,
    chord_timeline,
    clear_draft,
    draft_key,
    draft_playback_chords,
    ensure_draft,
    insert_draft_chord,
    is_chromatic_to_key,
    parse_chord_parts,
    pop_undo,
    push_undo,
    remove_draft_chord,
    suggest_insert_chords,
    update_draft_chord,
)
from composition_key_transpose import (
    KEY_UNDO_KEY,
    apply_song_key_change,
    apply_song_tempo_change,
    apply_undo_key_change,
    push_key_undo,
    transpose_composition_to_key,
)
from composition_melody_improve import (
    QUICK_ACTIONS,
    apply_plain_language_improvement,
    apply_quick_action,
    improve_undo_button_key,
    pop_improve_undo,
    preserve_original_take,
    push_improve_undo,
    restore_original_take,
)
from composition_melody_repeats import (
    EDIT_SCOPE_ALL,
    EDIT_SCOPE_FIRST,
    MELODY_REPEAT_MAX,
    MELODY_REPEAT_MIN,
    expand_melody_events_by_repeats,
    get_melody_repeats,
    heal_melody_tiling_if_safe,
    mark_melody_customized,
    melody_is_tiled,
    melody_repeats_are_editable,
    set_section_melody_repeats,
)
from composition_sync_transport import (
    COUNT_IN_CHOICES,
    COUNT_IN_ONE_BAR,
    build_chord_span_timeline,
    count_in_seconds,
    render_synced_transport,
)
from composition_hum_transcription import (
    hum_analysis_available,
    transcribe_hum_audio,
)
from composition_melody_notation import (
    build_section_score_model,
    render_abc_html,
)
from composition_session_state import (
    COMPOSER_ACTIVE_SECTION_KEY,
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
/* Keep Composition desktop split as a true left/right row (do not wrap under). */
.st-key-composer_desktop_split [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important;
  align-items: flex-start !important;
  gap: 1.15rem;
}
.st-key-composer_desktop_split [data-testid="column"] {
  min-width: 0 !important;
}
.st-key-composer_desktop_split [data-testid="column"]:last-child {
  flex: 1 1 280px !important;
  max-width: 340px;
}
.st-key-composer_utility_panel {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.10);
  border-radius: 14px;
  padding: 0.65rem 0.75rem 0.8rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.composer-utility-kicker {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  font-weight: 700;
  margin: 0 0 0.55rem 0.1rem;
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
.composer-suggestion-card.is-active {
  border: 2px solid #2563eb;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 55%);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.12);
}
.composer-suggestion-card.is-active h4 {
  color: #1d4ed8;
}
.composer-active-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #1d4ed8;
  background: #dbeafe;
  border-radius: 999px;
  padding: 0.12rem 0.55rem;
  margin-left: 0.35rem;
  vertical-align: middle;
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
  white-space: pre-line;
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
    touch_composition(doc)
    set_active_document(session_state, doc)
    save_document_to_library(session_state, doc)
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


def _render_phase_review(session_state: dict, doc: dict[str, Any], *, host_side_panel: bool = True) -> None:
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

    center, side = _phase_main_side(host_side_panel=host_side_panel)
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
        st.markdown("**Full song playthrough**")
        st.caption("Hear the entire composition in order — melody and chords together when both exist.")
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
        # Prefer the first section that has material for a clear score cursor; full-song audio still scopes song.
        review_sec = section_by_id(doc, selected_id) if selected_id else (sections[0] if sections else None)
        review_events = list(section_melody_events(review_sec) or []) if review_sec else []
        review_chords = (
            chords_for_playback(doc, scope="section", section_id=str(review_sec.get("id") or ""))
            if review_sec
            else []
        )
        song_chords = chords_for_playback(doc, scope="song")
        has_any_melody = any(section_melody_events(s) for s in sections)
        if play_full:
            if not song_chords and not has_any_melody:
                st.warning("Add chords or a melody to at least one section before playing.")
            else:
                # Build concatenated song-scoped play: prefer include_melody when any section has it.
                result = play_composer_preview(
                    session_state,
                    doc,
                    section_id=str((review_sec or {}).get("id") or "") or None,
                    scope="song",
                    loops=int(loops),
                    include_melody=bool(has_any_melody),
                    chord_override=song_chords if song_chords else [],
                    slot="review:full_song",
                    label="Playing · full song",
                )
                if not result.get("ok"):
                    # Fallback: play selected section with both parts
                    result = play_composer_preview(
                        session_state,
                        doc,
                        section_id=str((review_sec or {}).get("id") or ""),
                        loops=int(loops),
                        include_melody=bool(review_events),
                        chord_override=review_chords or [],
                        slot="review:section",
                        label="Playing · section",
                    )
                if not result.get("ok"):
                    st.warning(str(result.get("reason") or "Could not generate playback."))
        # Synced visualization for the selected section (cursor follows melody when present).
        review_slot = composer_preview_slot(session_state) or ""
        if review_slot.startswith("review:"):
            if review_events or review_chords:
                _attach_synced_score_preview(
                    session_state,
                    doc,
                    slot=review_slot,
                    events=review_events or None,
                    chord_syms=review_chords or song_chords or None,
                    caption=(
                        "Review — follow the highlighted melody note"
                        if review_events
                        else "Review — follow the highlighted chord"
                    ),
                    dom_id="review_play",
                    height=280,
                )
            else:
                _attach_local_preview(session_state, slot=review_slot)
        elif session_state.get(COMPOSER_PREVIEW_WAV_KEY):
            st.audio(session_state[COMPOSER_PREVIEW_WAV_KEY], format="audio/wav")

        # Per-section play inside expanders
        if sections and review_sec:
            sid = str(review_sec.get("id") or "")
            sec_slot = f"review:sec:{sid}"
            if st.button(
                "▶ Play selected section",
                key="composer_review_play_selected",
                use_container_width=True,
            ):
                if not review_events and not review_chords:
                    st.info("Nothing composed for this section yet.")
                else:
                    ok = play_composer_preview(
                        session_state,
                        doc,
                        section_id=sid,
                        loops=1,
                        include_melody=bool(review_events),
                        chord_override=review_chords or [],
                        slot=sec_slot,
                        label="Playing · selected section",
                    )
                    if not ok.get("ok"):
                        st.warning(str(ok.get("reason") or "Could not play section."))
            if composer_preview_slot(session_state) == sec_slot:
                _attach_synced_score_preview(
                    session_state,
                    doc,
                    slot=sec_slot,
                    events=review_events or None,
                    chord_syms=review_chords or None,
                    caption=(
                        "Follow the highlighted melody note"
                        if review_events
                        else "Follow the highlighted chord"
                    ),
                    dom_id=f"rev_{sid[:8]}",
                )

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

        m1, m2 = st.columns(2)
        with m1:
            if st.button("Mark song ready", type="primary", key="composer_review_mark_ready", disabled=not ready):
                doc["status"] = "ready"
                complete_workflow_phase(doc, "review")
                _save_doc(session_state, doc)
                st.rerun()
        with m2:
            if st.button("Keep refining", key="composer_review_keep_refining", use_container_width=True):
                set_workflow_phase(doc, "chords")
                _save_doc(session_state, doc)
                st.rerun()

        if str(doc.get("status") or "") == "ready":
            st.caption("You've marked this song **ready** — it's saved in your library whenever you need it.")

    _stash_or_render_phase_side(
        session_state,
        doc,
        side,
        coach_lead=coach_line_for_review(doc),
        caption=document_summary_line(doc),
        show_sections=False,
    )


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
    if st.button("Save song", key="composer_save_btn", use_container_width=True):
        doc = get_active_document(session_state)
        if doc:
            save_document_to_library(session_state, doc)
            st.success("Saved to My Compositions.")
    with st.expander("My compositions"):
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


COMPOSER_SIDE_COACH_KEY = "composer_side_coach_lead"
COMPOSER_SIDE_CAPTION_KEY = "composer_side_caption"
COMPOSER_DESKTOP_SPLIT_PHASES = frozenset({"structure", "chords", "melody", "lyrics", "review"})


def _phase_main_side(*, host_side_panel: bool):
    """Return (main, side). When host_side_panel is False, side is None (page owns right column)."""
    if host_side_panel:
        return st.columns([2.6, 1.0])
    return st.container(), None


def _stash_or_render_phase_side(
    session_state: dict,
    doc: dict[str, Any],
    side,
    *,
    coach_lead: str,
    caption: str = "",
    show_sections: bool = True,
    include_utility: bool = True,
) -> None:
    """Render utilities+coach+library in side, or stash coach when page-level right column owns them."""
    if side is None:
        session_state[COMPOSER_SIDE_COACH_KEY] = coach_lead
        session_state[COMPOSER_SIDE_CAPTION_KEY] = caption
        return
    with side:
        if include_utility and document_has_structure(doc):
            with st.container(key="composer_utility_panel"):
                st.markdown(
                    '<p class="composer-utility-kicker">Composition panel</p>',
                    unsafe_allow_html=True,
                )
                _render_composition_utility_panel(
                    session_state,
                    doc,
                    settings_key_prefix=_utility_settings_prefix(doc),
                    section_button_prefix="composer_utility_sec",
                    show_sections=show_sections,
                )
        _render_coach_panel(doc, lead=coach_lead)
        if caption:
            st.caption(caption)
        _render_library_sidebar(session_state)


def _render_page_right_utility(
    session_state: dict,
    doc: dict[str, Any],
    *,
    phase: str,
) -> None:
    """Canonical right-column utilities after structure exists."""
    show_sections = phase in {"chords", "melody", "lyrics"}
    with st.container(key="composer_utility_panel"):
        st.markdown(
            '<p class="composer-utility-kicker">Composition panel</p>',
            unsafe_allow_html=True,
        )
        _render_composition_utility_panel(
            session_state,
            doc,
            settings_key_prefix=_utility_settings_prefix(doc),
            section_button_prefix="composer_utility_sec",
            show_sections=show_sections,
        )
    lead = str(session_state.get(COMPOSER_SIDE_COACH_KEY) or "").strip()
    if not lead:
        lead = "Jump freely between Structure, Chords, Melody, Lyrics, and Review — this panel stays with your song."
    _render_coach_panel(doc, lead=lead)
    caption = str(session_state.get(COMPOSER_SIDE_CAPTION_KEY) or "").strip()
    if caption:
        st.caption(caption)
    _render_library_sidebar(session_state)


def _render_journey_rail(
    session_state: dict,
    doc: dict[str, Any],
    *,
    vertical: bool = False,
) -> None:
    """Guided Path navigation — same workflow keys/behavior in top or right panel."""
    wf = ensure_workflow(doc)
    current = get_workflow_phase(doc)
    st.markdown(
        '<p class="composer-journey-title">Guided path · jump freely after structure exists</p>',
        unsafe_allow_html=True,
    )

    def _journey_button(phase: str) -> None:
        label = COMPOSITION_PHASE_LABELS[phase]
        if phase == "lyrics" and wf.get("skip_lyrics"):
            label = "Lyrics · N/A"
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

    if vertical:
        # Compact 2-up grid so Song Settings / Song Sections stay near the top.
        batch: list[str] = []
        for i, phase in enumerate(COMPOSITION_PHASES):
            batch.append(phase)
            if len(batch) == 2 or i == len(COMPOSITION_PHASES) - 1:
                cols = st.columns(len(batch))
                for col, ph in zip(cols, batch):
                    with col:
                        _journey_button(ph)
                batch = []
    else:
        cols = st.columns(len(COMPOSITION_PHASES))
        for col, phase in zip(cols, COMPOSITION_PHASES):
            with col:
                _journey_button(phase)


def _render_composition_utility_panel(
    session_state: dict,
    doc: dict[str, Any],
    *,
    settings_key_prefix: str,
    section_button_prefix: str | None = None,
    show_sections: bool = True,
) -> None:
    """Persistent right-side utilities: Guided Path, Song Settings, Song Sections."""
    _render_journey_rail(session_state, doc, vertical=True)
    _render_compact_song_settings(session_state, doc, key_prefix=settings_key_prefix)
    if show_sections and section_button_prefix and ordered_sections(doc):
        _render_section_nav_strip(
            session_state,
            doc,
            button_prefix=section_button_prefix,
            stacked=True,
        )


def _utility_settings_prefix(doc: dict[str, Any]) -> str:
    """One Song Settings widget namespace for the whole Composition page."""
    return f"composer_utility_settings_{doc.get('id')}"


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
    """Fallback audition dock when no item-local player owns the armed slot."""
    if composer_preview_slot(session_state):
        # Item-local Preview mounts under the suggestion/edit that armed this slot.
        return
    wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
    if not wav:
        return
    from composition_preview import render_composer_playback

    render_composer_playback(st, session_state, stop_key=stop_key)


def _play_chord_idea(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    chord_syms: list[str],
    *,
    loops: int = 1,
    slot: str = "",
    label: str = "",
    include_melody: bool | None = None,
) -> bool:
    """Generate transient chord preview. Returns True if a playable payload was armed.

    When the section already has an active melody, Preview auditions proposed
    chords together with that melody (melody-first harmonization workflow).
    """
    if include_melody is None:
        try:
            sec = section_by_id(doc, section_id)
            include_melody = bool(sec and section_melody_events(sec))
        except Exception:
            include_melody = False
    play_label = label or (
        "Playing melody + proposed chords" if include_melody else "Playing chords"
    )
    result = play_composer_preview(
        session_state,
        doc,
        section_id=section_id,
        loops=loops,
        chord_override=chord_syms,
        include_melody=bool(include_melody),
        slot=slot or f"chords:{section_id}",
        label=play_label,
    )
    return bool(result.get("ok"))


def _attach_local_preview(
    session_state: dict,
    *,
    slot: str,
    stop_key: str | None = None,
) -> bool:
    """Mount the armed player under the item that requested it (same click-run)."""
    return render_local_composer_playback(st, session_state, slot=slot, stop_key=stop_key)


def _attach_synced_score_preview(
    session_state: dict,
    doc: dict[str, Any],
    *,
    slot: str,
    events: list[dict[str, Any]] | None = None,
    chord_syms: list[str] | None = None,
    caption: str = "",
    dom_id: str = "",
    height: int = 260,
) -> bool:
    """Mount synced notation/chord highlight for the armed preview slot."""
    from composition_playback_sync import build_playback_bundle, mount_synced_score_playback
    from composition_melody_notation import build_abc_from_melody_events, chord_symbols_by_measure
    from composition_preview import composer_preview_slot

    if composer_preview_slot(session_state) != slot:
        return False
    wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
    if not wav:
        return False
    pg = playback_globals(doc)
    bpm = int(pg.get("bpm") or 96)
    meter = str(pg.get("time_signature") or "4/4")
    key = str(pg.get("key_center") or "C")
    bundle = build_playback_bundle(
        events=events,
        chord_syms=chord_syms,
        bpm=bpm,
        meter=meter,
        loops=1,
        count_in_bars=0,
    )
    abc = ""
    if events:
        abc = build_abc_from_melody_events(
            events, key=key, meter=meter, bpm=bpm, title="Playback"
        )
    from composition_melody_notation import melody_measure_count

    measures = melody_measure_count(events, meter=meter) if events else None
    if chord_syms:
        n_ch = len([c for c in chord_syms if str(c).strip()])
        if measures is None:
            measures = max(1, n_ch)
        else:
            measures = max(int(measures), n_ch)
    labels = (
        chord_symbols_by_measure(list(chord_syms or []), meter=meter, measures=measures)
        if chord_syms
        else []
    )
    mount_synced_score_playback(
        st,
        wav_bytes=bytes(wav),
        abc_text=abc,
        chord_labels=labels,
        bundle=bundle,
        caption=caption
        or (
            "Follow the highlighted note"
            if bundle.get("primary") == "melody"
            else "Follow the highlighted chord"
        ),
        dom_id=dom_id or slot.replace(":", "_")[:40],
        height=height,
    )
    return True


def _section_has_accepted_melody(section: dict[str, Any] | None) -> bool:
    return bool(section and section_melody_events(section))


def _melody_defines_section_length(section: dict[str, Any] | None) -> bool:
    """True when an active melody already owns section duration (repeats or full timeline)."""
    return _section_has_accepted_melody(section)


def _compare_queue_key(section_id: str) -> str:
    """Legacy key helper — Compare UI removed; kept for tests that assert the key shape."""
    return f"composer_compare_{section_id}"


def _render_compare_tray(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    suggestions: list[dict[str, Any]],
) -> None:
    """Compare UI removed — clear any leftover queue state and render nothing."""
    del doc, suggestions  # unused; signature kept for call-site compatibility
    session_state.pop(_compare_queue_key(section_id), None)


def _render_compact_song_settings(session_state: dict, doc: dict[str, Any], *, key_prefix: str) -> None:
    """Keep Key/BPM/Meter (+ genre) editable but out of the way while composing."""
    pg = playback_globals(doc)
    meta = doc.setdefault("metadata", {})
    genre_now = str(meta.get("style") or "Pop")
    summary = (
        f"{pg.get('key_label') or pg.get('key_center')} · "
        f"{pg['bpm']} BPM · {pg['time_signature']} · "
        f"{genre_now or 'Song'}"
    )
    with st.expander(f"Song settings — {summary}", expanded=False):
        g = doc.setdefault("global", {})
        genre_key = f"{key_prefix}_genre"
        if genre_key not in session_state:
            session_state[genre_key] = genre_now if genre_now in COMPOSITION_GENRES else "Other"
        if session_state.get(genre_key) not in COMPOSITION_GENRES:
            session_state[genre_key] = "Other"
        st.selectbox("Genre / style", COMPOSITION_GENRES, key=genre_key)
        genre_picked = str(session_state.get(genre_key) or "Pop")
        if genre_picked == "Jewish":
            jd_key = f"{key_prefix}_jewish_direction"
            if jd_key not in session_state:
                session_state[jd_key] = coerce_jewish_direction(meta.get("jewish_direction"))
            if session_state.get(jd_key) not in COMPOSITION_JEWISH_DIRECTIONS:
                session_state[jd_key] = DEFAULT_JEWISH_DIRECTION
            st.selectbox("Jewish direction", COMPOSITION_JEWISH_DIRECTIONS, key=jd_key)
            st.caption("Guidance for Jewish songs — your description can still nudge a section.")

        mode_family = ensure_original_mode_family(doc)
        key_labels = composition_key_choice_labels_for_family(mode_family)
        current_label = coerce_composition_key_choice_for_doc(
            doc,
            str(g.get("original_key_label") or "")
            or composition_key_label_from_token(str(g.get("original_key_center") or "C")),
        )
        key_widget = f"{key_prefix}_key"
        if key_widget not in session_state or session_state.get(key_widget) not in key_labels:
            session_state[key_widget] = current_label
        picked = st.selectbox(
            "Key",
            key_labels,
            key=key_widget,
            help=f"This song is {mode_family} — Song Settings only offer {mode_family} keys.",
        )
        st.caption(f"Original tonal family: **{mode_family}** (locked for this Composition).")
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
            label = coerce_composition_key_choice_for_doc(doc, str(picked or current_label))
            new_token = composition_key_token_from_choice(label)
            old_token = str(g.get("original_key_center") or "")
            if new_token != old_token:
                apply_song_key_change(
                    session_state, doc, new_token, new_key_label=label, push_undo=True
                )
            else:
                g["original_key_label"] = label
                g["original_key_center"] = new_token
                ensure_original_mode_family(doc)
            apply_song_tempo_change(doc, bpm_val)
            meter_choice = str(session_state.get(meter_key) or "4/4")
            if meter_choice == COMPOSITION_METER_CUSTOM:
                meter_choice = str(session_state.get(custom_key) or "").strip()
            g["time_signature"] = coerce_composition_meter(meter_choice)
            meta["style"] = genre_picked
            if genre_picked in CPL_PROGRESSION_STYLES:
                g["progression_style"] = genre_picked
            if genre_picked == "Jewish":
                meta["jewish_direction"] = coerce_jewish_direction(
                    session_state.get(f"{key_prefix}_jewish_direction")
                )
            # Keep stored direction if switching away, but it must not affect non-Jewish genres.
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
        if session_state.get(KEY_UNDO_KEY) and st.button(
            "Undo key change",
            key=f"{key_prefix}_undo_key",
        ):
            if apply_undo_key_change(session_state, doc):
                invalidate_composer_preview(session_state)
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


def _select_active_section(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    *,
    persist: bool = True,
) -> None:
    """Authoritative section selection — persist so prepare_render cannot reassert a stale id."""
    sid = str(section_id or "").strip()
    if not sid:
        return
    _clear_all_hum_sync_transports(session_state)
    session_state[COMPOSER_ACTIVE_SECTION_KEY] = sid
    invalidate_composer_preview(session_state)
    if persist:
        try:
            from composition_workspace_state_persistence import checkpoint_composition_workspace

            checkpoint_composition_workspace(
                session_state,
                reason="composer_section_select",
                force_disk=True,
                st=st,
            )
        except Exception:
            # Fall back to document save path when workspace helper is unavailable.
            try:
                _save_doc(session_state, doc)
            except Exception:
                pass


def _render_section_nav_strip(
    session_state: dict,
    doc: dict[str, Any],
    *,
    button_prefix: str,
    stacked: bool = False,
) -> None:
    """Prominent song-section navigation."""
    sections = ordered_sections(doc)
    if not sections:
        st.info("Add sections in Song Structure first.")
        return
    active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    st.markdown("**Song sections**")

    def _section_button(sec: dict[str, Any]) -> None:
        sid = str(sec.get("id") or "")
        label = str(sec.get("label_variant") or sec.get("label") or "Section")
        btn_type = "primary" if sid == active_id else "secondary"
        if st.button(
            label,
            key=f"{button_prefix}_{sid}",
            type=btn_type,
            use_container_width=True,
        ):
            _select_active_section(session_state, doc, sid)
            st.rerun()

    if stacked:
        for sec in sections:
            _section_button(sec)
    else:
        cols = st.columns(min(len(sections), 8))
        for i, sec in enumerate(sections):
            with cols[i % len(cols)]:
                _section_button(sec)
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
    "composer_welcome_jewish_direction",
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
    """Queue Song Vision settings suggestions — applied only after the user clicks Suggest.

    Fills Key / BPM / Meter / mood / energy from genre + song idea on the next
    prepare pass (same Streamlit-safe pending pattern as Welcome). Never writes
    widget keys in the same run as the button click.
    """
    hints = suggest_musical_defaults(genre=str(genre or "Pop"), song_idea=str(song_idea or ""))
    suggested_meter = coerce_composition_meter(hints.get("meter"))
    payload: dict[str, Any] = {
        "key": coerce_composition_key_choice(hints.get("key_label") or hints.get("key") or "C major"),
        "bpm": coerce_composition_bpm(hints.get("bpm")),
        "mood": str(hints.get("mood") or ""),
        "energy": str(hints.get("energy") or COMPOSITION_ENERGY_LEVELS[1]),
    }
    if suggested_meter in COMPOSITION_METERS:
        payload["meter"] = suggested_meter
        payload["meter_custom"] = ""
    else:
        payload["meter"] = COMPOSITION_METER_CUSTOM
        payload["meter_custom"] = suggested_meter
    session_state[COMPOSER_VISION_PENDING_SUGGEST_KEY] = payload
    return payload


# Alias — Vision "Suggest song settings" uses the same queue.
queue_vision_song_settings_suggest = queue_vision_mood_energy_suggest


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
        # User knowingly clicked Suggest — apply full song-settings proposal.
        if pending.get("key") is not None:
            session_state["composer_vision_key"] = coerce_composition_key_choice(pending.get("key"))
        if pending.get("bpm") is not None:
            session_state["composer_vision_bpm"] = coerce_composition_bpm(pending.get("bpm"))
        meter = str(pending.get("meter") or "")
        if meter:
            if meter == COMPOSITION_METER_CUSTOM or meter not in COMPOSITION_METERS:
                session_state["composer_vision_meter"] = COMPOSITION_METER_CUSTOM
                session_state["composer_vision_meter_custom"] = coerce_composition_meter(
                    pending.get("meter_custom") or meter
                )
            else:
                session_state["composer_vision_meter"] = meter
                session_state["composer_vision_meter_custom"] = ""
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
    if "composer_vision_jewish_direction" not in session_state:
        session_state["composer_vision_jewish_direction"] = coerce_jewish_direction(
            meta.get("jewish_direction") or origin_payload.get("jewish_direction")
        )
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
    if session_state.get("composer_vision_jewish_direction") not in COMPOSITION_JEWISH_DIRECTIONS:
        session_state["composer_vision_jewish_direction"] = DEFAULT_JEWISH_DIRECTION

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
        if str(session_state.get("composer_welcome_genre") or "") == "Jewish":
            if "composer_welcome_jewish_direction" not in session_state:
                session_state["composer_welcome_jewish_direction"] = DEFAULT_JEWISH_DIRECTION
            if session_state.get("composer_welcome_jewish_direction") not in COMPOSITION_JEWISH_DIRECTIONS:
                session_state["composer_welcome_jewish_direction"] = DEFAULT_JEWISH_DIRECTION
            st.selectbox(
                "Jewish direction",
                COMPOSITION_JEWISH_DIRECTIONS,
                key="composer_welcome_jewish_direction",
            )
            st.caption("Optional guidance — your song idea can still steer individual sections.")
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
                    jewish_direction=str(session_state.get("composer_welcome_jewish_direction") or ""),
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
    if genre == "Jewish":
        meta["jewish_direction"] = coerce_jewish_direction(
            st.session_state.get("composer_vision_jewish_direction")
        )
    doc["title"] = str(st.session_state.get("composer_vision_title") or "").strip() or "Untitled Song"

    key_label = coerce_composition_key_choice(str(st.session_state.get("composer_vision_key") or ""))
    g["original_key_label"] = key_label
    g["original_key_center"] = composition_key_token_from_choice(key_label)
    set_original_mode_family_from_key(doc, key_label)
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
    origin["seed_payload"]["jewish_direction"] = meta.get("jewish_direction") or ""
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
        if str(session_state.get("composer_vision_genre") or "") == "Jewish":
            st.selectbox(
                "Jewish direction",
                COMPOSITION_JEWISH_DIRECTIONS,
                key="composer_vision_jewish_direction",
            )
            st.caption("Guidance for this Jewish song — section notes can still add modal/traditional color.")
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

        if st.button(
            "Suggest song settings from idea",
            key="composer_vision_resuggest",
            help="Uses your Song Vision text + genre to propose Key, BPM, Meter, mood, and energy. "
            "Click to apply the suggestion into the fields above — nothing changes until you click.",
        ):
            # Streamlit-safe pending path — do not mutate widget keys after instantiation.
            queue_vision_song_settings_suggest(
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
        if document_has_structure(doc):
            # Vision owns full song metadata in center — only restore Guided Path here.
            _render_journey_rail(session_state, doc, vertical=True)
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


def _render_phase_structure(session_state: dict, doc: dict[str, Any], *, host_side_panel: bool = True) -> None:
    selected_id = _ensure_structure_selection(session_state, doc)
    sections = ordered_sections(doc)
    order_ids = [str(s.get("id") or "") for s in sections]
    center, side = _phase_main_side(host_side_panel=host_side_panel)

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

    _stash_or_render_phase_side(
        session_state,
        doc,
        side,
        coach_lead=_structure_coach_html(doc),
        show_sections=False,
        include_utility=bool(ordered_sections(doc)),
    )


def _hum_proposal_key(section_id: str) -> str:
    return f"composer_hum_proposal_{section_id}"


def _hum_audio_key(section_id: str) -> str:
    return f"composer_hum_audio_{section_id}"


def _clear_hum_proposal(session_state: dict, section_id: str) -> None:
    session_state.pop(_hum_proposal_key(section_id), None)
    session_state.pop(_hum_audio_key(section_id), None)


def _clear_hum_sync_transport(session_state: dict, section_id: str) -> None:
    session_state.pop(f"composer_hum_sync_wav_{section_id}", None)
    session_state.pop(f"composer_hum_sync_spans_{section_id}", None)
    session_state.pop(f"composer_hum_sync_count_in_{section_id}", None)


def _clear_all_hum_sync_transports(session_state: dict) -> None:
    """Stop stale highlight/audio when leaving a section or restarting."""
    for key in list(session_state.keys()):
        sk = str(key)
        if sk.startswith("composer_hum_sync_wav_") or sk.startswith("composer_hum_sync_spans_"):
            session_state.pop(key, None)
        if sk.startswith("composer_hum_sync_count_in_"):
            session_state.pop(key, None)


def _apply_melody_refinement_scoped(
    doc: dict[str, Any],
    section_id: str,
    refinement_id: str,
    *,
    scope: str = EDIT_SCOPE_ALL,
) -> None:
    """Apply Shape/Refine with an explicit all-repeats vs first-occurrence rule."""
    from composition_document import normalize_melody_events, section_by_id, section_melody_events

    if str(scope) != EDIT_SCOPE_FIRST:
        apply_melody_refinement_to_section(doc, section_id, refinement_id)
        return
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    events = list(section_melody_events(sec) or [])
    if not events or not any(e.get("repeat_index") is not None for e in events):
        apply_melody_refinement_to_section(doc, section_id, refinement_id)
        return
    first = [copy.deepcopy(e) for e in events if int(e.get("repeat_index") or 0) == 0]
    rest = [copy.deepcopy(e) for e in events if int(e.get("repeat_index") or 0) != 0]
    melody = sec.setdefault("melody", {"intent": {}, "phrases": [], "events": []})
    melody["events"] = first
    apply_melody_refinement_to_section(doc, section_id, refinement_id)
    updated = list(section_melody_events(sec) or [])
    for ev in updated:
        ev["repeat_index"] = 0
    melody["events"] = normalize_melody_events(updated + rest)


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
        )
    elif has_chords:
        meter = str(pg.get("time_signature") or "4/4")
        chart = cpl_progression_bar_chart_html(chords, time_signature=meter)
        if chart:
            st.markdown(chart, unsafe_allow_html=True)
        st.caption("Your chords are ready. Build or record a melody over them.")

    # Chord playback lives in the Hum/Play workspace — no redundant top transport here.


def _render_hum_sing_panel(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    active_id: str,
) -> None:
    """Record melody (hum, sing, or instrument) → staff proposal → edit → accept."""
    pg = playback_globals(doc)
    key = str(pg.get("key_center") or "C")
    meter = str(pg.get("time_signature") or "4/4")
    bpm = int(pg.get("bpm") or 96)
    accepted = section_melody_events(section)
    chords = list(section.get("chords") or [])
    flat_chords = expand_entries_to_chords(chords) if chords else list(chords_for_playback(doc, scope="section", section_id=active_id))
    proposal = session_state.get(_hum_proposal_key(active_id))
    if not isinstance(proposal, dict):
        proposal = None

    st.markdown("**Hum or sing your melody**")
    st.caption(
        "Hum, sing, or play one melodic line. Words are optional — we capture the pitch contour as sheet music, not lyrics."
    )
    st.caption(
        "For the clearest results, record one melody line at a time — hum, sing, or play a single-note instrument. "
        "Background chords or multiple instruments may make the melody harder to detect."
    )

    count_in_key = f"composer_hum_count_in_{active_id}"
    if count_in_key not in session_state:
        session_state[count_in_key] = COUNT_IN_ONE_BAR
    count_in_bars = st.selectbox(
        "Count-in",
        options=[c[0] for c in COUNT_IN_CHOICES],
        format_func=lambda v: next(lab for val, lab in COUNT_IN_CHOICES if val == v),
        key=count_in_key,
        help="Audible clicks once before the section chords begin",
    )
    # Full accepted Chords progression plays once — no separate Melody repeat control.
    hum_loops = 1
    session_state["composer_play_loops"] = 1
    session_state[f"composer_hum_loops_{active_id}"] = 1
    count_in_bars = int(count_in_bars)
    cin_sec = count_in_seconds(bpm=bpm, meter=meter, bars=count_in_bars)
    session_state[f"composer_hum_count_in_sec_{active_id}"] = cin_sec

    if flat_chords:
        timeline = " → ".join(flat_chords)
        cin_label = "Off" if count_in_bars <= 0 else f"{count_in_bars} bar"
        st.caption(f"Count-in: {cin_label} · Section chords ({len(flat_chords)}): {timeline}")
        if st.button("▶ Play chords with highlight", key=f"composer_hum_play_chords_{active_id}"):
            wav = generate_preview_wav(
                doc,
                section_id=active_id,
                loops=1,
                include_melody=False,
                count_in_bars=count_in_bars,
                chord_override=flat_chords,
            )
            if wav:
                spans = build_chord_span_timeline(
                    flat_chords,
                    bpm=bpm,
                    meter=meter,
                    loops=1,
                    count_in_bars=count_in_bars,
                )
                session_state[f"composer_hum_sync_wav_{active_id}"] = wav
                session_state[f"composer_hum_sync_spans_{active_id}"] = spans
                session_state[f"composer_hum_sync_count_in_{active_id}"] = count_in_bars
                set_composer_preview(
                    session_state,
                    wav,
                    ("hum_chords", active_id, 1, count_in_bars, tuple(flat_chords)),
                )
                st.rerun()
        sync_wav = session_state.get(f"composer_hum_sync_wav_{active_id}")
        sync_spans = session_state.get(f"composer_hum_sync_spans_{active_id}")
        if sync_wav and isinstance(sync_spans, list) and sync_spans:
            render_synced_transport(
                st,
                sync_wav,
                sync_spans,
                key=f"composer_hum_sync_{active_id}",
                caption="Sing or play — the highlighted chord is sounding now",
            )
            if st.button("Stop chord highlight", key=f"composer_hum_sync_stop_{active_id}"):
                _clear_hum_sync_transport(session_state, active_id)
                invalidate_composer_preview(session_state)
                st.rerun()

    # Mix for recorded melody playback (persisted on the composition document)
    g_mix = doc.setdefault("global", {})
    mix = g_mix.setdefault("preview_mix", {})
    if "composer_melody_mix_gain" not in session_state:
        session_state["composer_melody_mix_gain"] = float(mix.get("melody_gain") or 0.55)
    if "composer_backing_mix_gain" not in session_state:
        session_state["composer_backing_mix_gain"] = float(mix.get("backing_gain") or 0.75)
    m1, m2 = st.columns(2)
    with m1:
        session_state["composer_melody_mix_gain"] = st.slider(
            "Melody volume",
            0.15,
            1.0,
            float(session_state.get("composer_melody_mix_gain") or 0.55),
            key=f"composer_melody_mix_gain_w_{active_id}",
        )
    with m2:
        session_state["composer_backing_mix_gain"] = st.slider(
            "Backing volume",
            0.15,
            1.0,
            float(session_state.get("composer_backing_mix_gain") or 0.75),
            key=f"composer_backing_mix_gain_w_{active_id}",
        )
    mix["melody_gain"] = float(session_state["composer_melody_mix_gain"])
    mix["backing_gain"] = float(session_state["composer_backing_mix_gain"])

    if not hum_analysis_available():
        st.info(
            "Pitch transcription needs librosa on this server. "
            "Recording still works as a capture marker; explore melody ideas below."
        )

    try:
        audio = st.audio_input(
            "Hum or sing your melody (or play one melodic line)",
            key=f"composer_melody_record_{active_id}",
        )
    except Exception:
        audio = None
        st.caption("Audio recording will appear here when your browser supports it.")

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
    a1, a2 = st.columns(2)
    with a1:
        analyze = st.button(
            "Analyze recording",
            type="primary",
            key=f"composer_hum_analyze_{active_id}",
            disabled=not has_audio,
            use_container_width=True,
        )
    with a2:
        if proposal and st.button("Dismiss proposal", key=f"composer_hum_dismiss_{active_id}", use_container_width=True):
            _clear_hum_proposal(session_state, active_id)
            st.rerun()

    if analyze:
        audio_bytes = session_state.get(_hum_audio_key(active_id)) or b""
        cin_bars = int(session_state.get(f"composer_hum_count_in_{active_id}") or COUNT_IN_ONE_BAR)
        result = transcribe_hum_audio(
            audio_bytes,
            bpm=bpm,
            meter=meter,
            key=key,
            count_in_bars=cin_bars,
        )
        session_state[_hum_proposal_key(active_id)] = result
        intent = section.setdefault("melody", {}).setdefault("intent", {})
        capture = intent.setdefault("hum_capture", {})
        capture["analysis_status"] = str(result.get("status") or "unclear")
        capture["note_detection"] = bool(result.get("events"))
        capture["count_in_bars"] = cin_bars
        capture["count_in_sec"] = float(result.get("count_in_sec") or 0.0)
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
            st.markdown("**You hummed / sang / played this:**")
            _render_melody_staff(
                events,
                key=key,
                meter=meter,
                bpm=bpm,
                title=f"{section.get('label_variant') or section.get('label') or 'Section'} — proposed",
                chords=chords,
            )

            hum_slot = f"melody:{active_id}:hum_proposal"
            p1, p2 = st.columns(2)
            with p1:
                if st.button(
                    "▶ Preview with chords" if flat_chords else "▶ Preview melody",
                    key=f"composer_hum_preview_{active_id}",
                    use_container_width=True,
                ):
                    cin_bars = int(session_state.get(f"composer_hum_count_in_{active_id}") or COUNT_IN_ONE_BAR)
                    recorded = session_state.get(_hum_audio_key(active_id)) or b""
                    trim_sec = float(proposal.get("count_in_sec") or 0.0)
                    if trim_sec <= 0:
                        trim_sec = float(session_state.get(f"composer_hum_count_in_sec_{active_id}") or 0.0)
                    preview_label = (
                        "Playing · your recording + chords"
                        if flat_chords and recorded
                        else (
                            "Playing · your recording"
                            if recorded
                            else (
                                "Playing · transcribed melody + chords"
                                if flat_chords
                                else "Playing · transcribed melody"
                            )
                        )
                    )
                    if recorded:
                        result = play_composer_preview(
                            session_state,
                            doc,
                            section_id=active_id,
                            include_melody=False,
                            loops=1,
                            melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.55),
                            backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.75),
                            count_in_bars=0,
                            chord_override=flat_chords or [],
                            recorded_audio=bytes(recorded),
                            recorded_trim_sec=trim_sec,
                            slot=hum_slot,
                            label=preview_label,
                        )
                    else:
                        result = play_composer_preview(
                            session_state,
                            doc,
                            section_id=active_id,
                            include_melody=True,
                            melody_override=events,
                            loops=1,
                            melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.55),
                            backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.75),
                            count_in_bars=cin_bars if flat_chords else 0,
                            chord_override=flat_chords or [],
                            slot=hum_slot,
                            label=preview_label,
                        )
                    if result.get("ok") and result.get("wav"):
                        if flat_chords:
                            session_state[f"composer_hum_sync_wav_{active_id}"] = result["wav"]
                            session_state[f"composer_hum_sync_spans_{active_id}"] = build_chord_span_timeline(
                                flat_chords,
                                bpm=bpm,
                                meter=meter,
                                loops=1,
                                count_in_bars=0 if recorded else cin_bars,
                            )
                    elif not result.get("ok"):
                        st.warning(str(result.get("reason") or "Could not build a preview."))
                if session_state.get(_hum_audio_key(active_id)):
                    if flat_chords:
                        st.caption(
                            "Preview plays your exact recording with the section chord backing. "
                            "Note highlight follows the transcribed timing (approximate)."
                        )
                    else:
                        st.caption(
                            "No chords yet — Preview plays your recording alone. "
                            "Note highlight follows the transcribed timing (approximate)."
                        )
                # Visual cursor uses transcribed events even when audio is the original mic take.
                _attach_synced_score_preview(
                    session_state,
                    doc,
                    slot=hum_slot,
                    events=events or None,
                    chord_syms=flat_chords or None,
                    caption=(
                        "Follow the highlighted note (transcription timing)"
                        if events
                        else "Preview"
                    ),
                    dom_id=f"hum_{active_id[:8]}",
                )
            with p2:
                use_label = "Use this melody"
                if st.button(
                    use_label,
                    type="primary",
                    key=f"composer_hum_use_{active_id}",
                    use_container_width=True,
                ):
                    preserve_original_take(session_state, active_id, events)
                    audio_snap = session_state.get(_hum_audio_key(active_id))
                    if audio_snap:
                        session_state[f"composer_hum_original_audio_{active_id}"] = audio_snap
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
                    )
                    session_state[f"composer_melody_active_source_{active_id}"] = "hum_transcription"
                    session_state[f"composer_melody_just_accepted_{active_id}"] = True
                    session_state.pop(f"composer_melody_repeats_{active_id}", None)
                    intent = section.setdefault("melody", {}).setdefault("intent", {})
                    capture = intent.setdefault("hum_capture", {})
                    capture["accepted"] = True
                    capture["has_original_audio"] = bool(audio_snap)
                    capture["original_audio_len"] = len(audio_snap) if audio_snap else 0
                    _clear_hum_proposal(session_state, active_id)
                    invalidate_composer_preview(session_state)
                    _save_doc(session_state, doc)
                    st.rerun()

            # Compact post-recording take polish (proposal only — not active-melody tools)
            st.markdown("**Tweak this take**")
            st.caption("Adjust the transcription before you Use it — or record another take above.")
            preserve_original_take(session_state, active_id, events)
            qcols = st.columns(2)
            for qi, (qid, qlabel) in enumerate(QUICK_ACTIONS):
                with qcols[qi % 2]:
                    if st.button(qlabel, key=f"composer_hum_quick_{active_id}_{qid}", use_container_width=True):
                        push_improve_undo(session_state, active_id, events)
                        result = apply_quick_action(events, qid, key=key, meter=meter)
                        if result.get("needs_clarification"):
                            st.warning(result.get("message") or "Need clarification.")
                        elif result.get("events") is not None:
                            proposal["events"] = result["events"]
                            session_state[_hum_proposal_key(active_id)] = proposal
                            st.success(result.get("summary") or "Updated.")
                            st.rerun()
            instruction = st.text_input(
                "Or describe a small change",
                key=f"composer_hum_nl_{active_id}",
                placeholder='e.g. "Change the last note to E" or "Shorten the first note"',
            )
            i1, i2, i3 = st.columns(3)
            with i1:
                if st.button("Apply adjustment", key=f"composer_hum_nl_go_{active_id}", use_container_width=True):
                    push_improve_undo(session_state, active_id, events)
                    result = apply_plain_language_improvement(events, instruction, key=key, meter=meter)
                    if result.get("needs_clarification"):
                        st.warning(result.get("message") or "Need clarification.")
                    elif result.get("events") is not None:
                        proposal["events"] = result["events"]
                        session_state[_hum_proposal_key(active_id)] = proposal
                        st.success(result.get("summary") or "Updated.")
                        st.rerun()
            with i2:
                if st.button(
                    "Undo previous adjustment",
                    key=improve_undo_button_key(active_id),
                    use_container_width=True,
                ):
                    prev = pop_improve_undo(session_state, active_id)
                    if prev is not None:
                        proposal["events"] = prev
                        session_state[_hum_proposal_key(active_id)] = proposal
                        st.rerun()
            with i3:
                if st.button("Restore original take", key=f"composer_hum_restore_orig_{active_id}", use_container_width=True):
                    orig = restore_original_take(session_state, active_id)
                    if orig is not None:
                        proposal["events"] = orig
                        session_state[_hum_proposal_key(active_id)] = proposal
                        st.rerun()

            if accepted:
                st.caption(
                    "This section already has an accepted melody. "
                    "Preview leaves it untouched; Replace updates it explicitly."
                )

    # In-place active recorded melody — stays in the Hum/Sing/Play area (not a top page block).
    active_src = get_active_melody_source_id(section) or str(
        session_state.get(f"composer_melody_active_source_{active_id}") or ""
    )
    if active_src == "hum_transcription" and section_melody_events(section):
        sticky = _accepted_melody_concept_from_section(section)
        if sticky:
            _render_melody_concept_card(
                session_state,
                doc,
                active_id,
                sticky,
                prefix=f"composer_melody_hum_active_{active_id}",
                is_active=True,
            )
        _render_active_melody_inplace_tools(
            session_state,
            doc,
            section,
            active_id,
            has_harmony=bool(chords or flat_chords),
            active_melody_source="hum_transcription",
        )


def _melody_intent_ready(intent: dict[str, Any]) -> bool:
    """Feel & Notes gate — feel always chosen; require a note of intent or explicit continue."""
    if not isinstance(intent, dict):
        return False
    if bool(intent.get("feel_confirmed")):
        return True
    remember = str(intent.get("remember") or "").strip()
    notes = str(intent.get("hum_notes") or "").strip()
    return bool(remember or notes)


def _active_melody_history_key(section_id: str) -> str:
    return f"composer_melody_active_history_{section_id}"


def _push_active_melody_history(session_state: dict, section_id: str, events: list[dict[str, Any]], source_id: str) -> None:
    key = _active_melody_history_key(section_id)
    stack = list(session_state.get(key) or [])
    stack.append({"events": copy.deepcopy(list(events or [])), "source_id": str(source_id or "")})
    session_state[key] = stack[-20:]


def _pop_active_melody_history(session_state: dict, section_id: str) -> dict[str, Any] | None:
    key = _active_melody_history_key(section_id)
    stack = list(session_state.get(key) or [])
    if not stack:
        return None
    prev = stack.pop()
    session_state[key] = stack
    return prev if isinstance(prev, dict) else None


def _refine_proposal_key(section_id: str) -> str:
    return f"composer_melody_refine_proposal_{section_id}"


def _editor_draft_key(section_id: str) -> str:
    return f"composer_melody_editor_draft_{section_id}"


def _accepted_melody_concept_from_section(section: dict[str, Any]) -> dict[str, Any] | None:
    """Build a display concept for the section's accepted melody (sticky active card)."""
    events = section_melody_events(section)
    if not events:
        return None
    source_id = get_active_melody_source_id(section) or "accepted_melody"
    if source_id == "hum_transcription":
        return {
            "id": "hum_transcription",
            "name": "Recorded melody",
            "contour": "Accepted from your hummed / sung / played take.",
            "why": "Chosen melody for this section.",
            "events": events,
        }
    melody = section.get("melody") if isinstance(section.get("melody"), dict) else {}
    name = "Accepted melody"
    contour = "Currently chosen melody for this section."
    for phrase in list((melody or {}).get("phrases") or []):
        if not isinstance(phrase, dict):
            continue
        if str(phrase.get("concept_id") or "") == source_id:
            name = str(phrase.get("label") or name)
            contour = str(phrase.get("motif") or contour)
            break
    return {
        "id": source_id,
        "name": name,
        "contour": contour,
        "why": "Chosen melody for this section.",
        "events": events,
    }


def _render_melody_concept_card(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    concept: dict[str, Any],
    *,
    prefix: str,
    is_active: bool = False,
) -> None:
    cid = str(concept.get("id") or prefix)
    name = str(concept.get("name") or "Melodic idea")
    contour = str(concept.get("contour") or concept.get("why") or "")
    events = list(concept.get("events") or concept.get("notes_events") or [])
    sec = section_by_id(doc, section_id) or {}
    chords = list(sec.get("chords") or [])
    pg = playback_globals(doc)
    card_class = "composer-suggestion-card is-active" if is_active else "composer-suggestion-card"
    badge = '<span class="composer-active-badge">Active</span>' if is_active else ""
    # Match Chords active marker so Streamlit keeps the attribute and QA can find it.
    active_attr = ' data-composer-active="1" data-composer-active-melody="1"' if is_active else ""

    st.markdown(
        f"""
<div class="{card_class}"{active_attr}>
  <h4>{html.escape(name)}{badge}</h4>
  {"" if is_active else f'<p class="composer-suggestion-why">{html.escape(contour)}</p>'}
</div>
        """,
        unsafe_allow_html=True,
    )
    if events:
        n_ev = len(events)
        staff_h = 180 if n_ev <= 12 else (220 if n_ev <= 24 else 280)
        _render_melody_staff(
            events,
            key=str(pg.get("key_center") or "C"),
            meter=str(pg.get("time_signature") or "4/4"),
            bpm=int(pg.get("bpm") or 96),
            title=name,
            height=staff_h,
            chords=chords,
        )
    p1, p2 = st.columns(2)
    with p1:
        concept_slot = f"melody:{section_id}:{cid}"
        preview_label = "▶ Preview with chords" if chords else "▶ Preview melody"
        if st.button(preview_label, key=f"{prefix}_preview_{cid}", use_container_width=True):
            result = play_composer_preview(
                session_state,
                doc,
                section_id=section_id,
                include_melody=True,
                melody_override=events or None,
                loops=1,
                melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.45),
                backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.85),
                chord_override=[str(c.get("chord") or c) for c in chords] if chords else [],
                slot=concept_slot,
                label=(
                    f"Playing melody + chords · {name}"
                    if chords
                    else f"Playing melody · {name}"
                ),
            )
            if not result.get("ok"):
                st.warning(str(result.get("reason") or "Could not generate preview."))
        _attach_synced_score_preview(
            session_state,
            doc,
            slot=concept_slot,
            events=events or None,
            chord_syms=[str(c.get("chord") or c) for c in chords] if chords else None,
            caption=(
                "Follow the highlighted melody note"
                if events
                else "Preview"
            ),
            dom_id=f"mel_{cid[:16]}",
        )
    with p2:
        if is_active:
            st.caption("In use — preview other ideas freely.")
        elif st.button("Use this melody", key=f"{prefix}_use_{cid}", type="primary", use_container_width=True):
            if events:
                apply_melody_events(
                    doc,
                    section_id,
                    events,
                    concept=concept,
                    replace=True,
                )
            else:
                apply_melody_concept(doc, section_id, concept)
            session_state[f"composer_melody_active_source_{section_id}"] = cid
            session_state[f"composer_melody_just_accepted_{section_id}"] = True
            # Reset widget so repeats control seeds from the newly accepted pattern.
            session_state.pop(f"composer_melody_repeats_{section_id}", None)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()


def _render_active_melody_phrase_editor(session_state: dict, doc: dict[str, Any], section_id: str) -> None:
    """Select-one-note Advanced Phrase Editor over the active melody (proposal until Accept)."""
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    active_events = list(section_melody_events(sec) or [])
    if not active_events:
        st.info("Accept a melody first — this editor only edits the highlighted active melody.")
        return

    pg = playback_globals(doc)
    key = str(pg.get("key_center") or "C")
    meter = str(pg.get("time_signature") or "4/4")
    bpm = int(pg.get("bpm") or 96)
    chords = list(sec.get("chords") or [])
    flat = chords_for_playback(doc, scope="section", section_id=section_id)

    draft_key = _editor_draft_key(section_id)
    sel_key = f"composer_melody_ed_sel_{section_id}"
    choice_key = f"composer_melody_ed_nl_choice_{section_id}"
    if draft_key not in session_state or not isinstance(session_state.get(draft_key), list):
        session_state[draft_key] = copy.deepcopy(active_events)
    draft = list(session_state.get(draft_key) or [])

    from composition_chord_repeats import format_full_progression_display

    st.caption(
        f"Full section harmony ({len(flat) or len(chords)} chords). "
        "Edits update a proposal — the highlighted active melody stays unchanged until Accept changes."
    )
    if flat or chords:
        st.markdown(
            format_full_progression_display(list(chords or flat), pattern_len=None).replace("\n", "  ")
        )
    _render_melody_staff(
        draft,
        key=key,
        meter=meter,
        bpm=bpm,
        title="Edited melody proposal",
        height=220,
        chords=chords,
    )

    # Compact note markers — select one note (not a form per note).
    labels = []
    for i, ev in enumerate(draft):
        pitch = "rest" if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest" else str(ev.get("pitch") or "?")
        pass_i = ev.get("pass_index")
        if pass_i is None:
            pass_i = ev.get("repeat_index")
        pass_bit = f" · pass {int(pass_i) + 1}" if pass_i is not None else ""
        labels.append(
            f"{i + 1}. {pitch} · {float(ev.get('duration_beats') or 1):g} beats{pass_bit}"
        )
    if not labels:
        st.info("No events to edit.")
        return
    if sel_key not in session_state:
        session_state[sel_key] = 0
    selected = st.selectbox(
        "Select note",
        options=list(range(len(labels))),
        format_func=lambda i: labels[i],
        key=sel_key,
    )
    selected = int(selected)
    ev = draft[selected] if 0 <= selected < len(draft) else {}

    st.markdown("**Selected note**")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        pitch = st.text_input(
            "Pitch",
            value=str(ev.get("pitch") or ("rest" if ev.get("is_rest") else "C4")),
            key=f"composer_melody_ed_one_pitch_{section_id}_{selected}",
        )
    with c2:
        dur = st.number_input(
            "Duration (beats)",
            min_value=0.25,
            max_value=8.0,
            value=float(ev.get("duration_beats") or 1.0),
            step=0.25,
            key=f"composer_melody_ed_one_dur_{section_id}_{selected}",
        )
    with c3:
        is_rest = st.checkbox(
            "Rest",
            value=bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest"),
            key=f"composer_melody_ed_one_rest_{section_id}_{selected}",
        )
    d1, d2 = st.columns(2)
    with d1:
        if st.button("Apply to selected note", key=f"composer_melody_ed_apply_sel_{section_id}"):
            row = copy.deepcopy(ev) if isinstance(ev, dict) else {}
            row["duration_beats"] = float(dur)
            if is_rest:
                row["is_rest"] = True
                row["pitch"] = "rest"
                row["midi"] = None
            else:
                row["is_rest"] = False
                row["pitch"] = str(pitch or "C4")
                try:
                    from composition_melody_shape import insert_melody_note as _ins

                    probe = _ins([], at_index=0, pitch=row["pitch"], duration_beats=float(dur), key=key)
                    if probe:
                        row["midi"] = probe[0].get("midi")
                        row["pitch"] = probe[0].get("pitch") or row["pitch"]
                except Exception:
                    pass
            draft[selected] = row
            beat = 0.0
            for e in draft:
                e["beat"] = beat
                beat += float(e.get("duration_beats") or 1.0)
            session_state[draft_key] = draft
            st.rerun()
    with d2:
        if st.button("Delete selected note", key=f"composer_melody_ed_delete_{section_id}"):
            # Pending proposal only — replace with rest to preserve measure timing.
            session_state[draft_key] = delete_melody_note_preserve_gap(draft, selected)
            st.rerun()

    st.markdown("**Add a note**")
    a1, a2, a3, a4 = st.columns([2, 2, 2, 2])
    with a1:
        add_pitch = st.text_input("New pitch", value="E4", key=f"composer_melody_ed_add_pitch_{section_id}")
    with a2:
        add_dur = st.number_input(
            "New duration",
            min_value=0.25,
            max_value=4.0,
            value=0.5,
            step=0.25,
            key=f"composer_melody_ed_add_dur_{section_id}",
        )
    with a3:
        where = st.radio(
            "Placement",
            options=["before", "after"],
            horizontal=True,
            key=f"composer_melody_ed_add_where_{section_id}",
        )
    with a4:
        st.write("")
        if st.button("Add note", key=f"composer_melody_ed_add_go_{section_id}", use_container_width=True):
            draft = insert_melody_note(
                draft,
                at_index=selected,
                pitch=str(add_pitch or "E4"),
                duration_beats=float(add_dur),
                key=key,
                before=(where == "before"),
            )
            session_state[draft_key] = draft
            st.rerun()

    st.markdown("**Describe a change**")
    nl = st.text_input(
        "Natural-language edit",
        key=f"composer_melody_ed_nl_{section_id}",
        placeholder='e.g. "Delete the short E before the F" or "Hold the final note of the second pass"',
    )
    if st.button("Apply description", key=f"composer_melody_ed_nl_go_{section_id}"):
        result = apply_natural_language_melody_edit(draft, nl, key=key, meter=meter)
        if result.get("needs_choice"):
            session_state[choice_key] = {
                "choices": list(result.get("choices") or []),
                "pending_action": dict(result.get("pending_action") or {}),
                "message": str(result.get("message") or ""),
            }
            st.warning(str(result.get("message") or "Which note?"))
        elif result.get("ok"):
            session_state[draft_key] = list(result.get("events") or draft)
            session_state.pop(choice_key, None)
            st.success(str(result.get("message") or "Updated proposal."))
            st.rerun()
        else:
            st.warning(str(result.get("message") or "Could not apply that edit."))

    pending_choice = session_state.get(choice_key)
    if isinstance(pending_choice, dict) and pending_choice.get("choices"):
        st.caption(str(pending_choice.get("message") or "Choose a note:"))
        for ch in pending_choice["choices"]:
            idx = int(ch.get("index"))
            if st.button(str(ch.get("label") or f"Note {idx + 1}"), key=f"composer_melody_ed_choice_{section_id}_{idx}"):
                resolved = resolve_melody_edit_choice(
                    draft,
                    dict(pending_choice.get("pending_action") or {}),
                    idx,
                    key=key,
                )
                if resolved.get("ok"):
                    session_state[draft_key] = list(resolved.get("events") or draft)
                    session_state.pop(choice_key, None)
                    st.rerun()
                else:
                    st.warning(str(resolved.get("message") or "Could not resolve."))

    pending_changed = events_signature(draft) != events_signature(active_events)
    if pending_changed:
        st.caption("Proposal differs from the active melody — Preview freely, Accept when ready.")

    ed_slot = f"melody:{section_id}:editor_draft"
    e1, e2, e3 = st.columns(3)
    with e1:
        if st.button("▶ Preview", key=f"composer_melody_ed_preview_{section_id}", use_container_width=True):
            play_composer_preview(
                session_state,
                doc,
                section_id=section_id,
                include_melody=True,
                melody_override=draft,
                loops=1,
                melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.45),
                backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.85),
                chord_override=[str(c.get("chord") or c) for c in chords] if chords else [],
                slot=ed_slot,
                label="Playing · editor proposal",
            )
        _attach_synced_score_preview(
            session_state,
            doc,
            slot=ed_slot,
            events=draft,
            chord_syms=[str(c.get("chord") or c) for c in chords] if chords else None,
            caption="Follow the highlighted note (proposal)",
            dom_id=f"ed_{section_id[:8]}",
        )
    with e2:
        if st.button("Accept changes", key=f"composer_melody_ed_accept_{section_id}", type="primary", use_container_width=True):
            before = list(active_events)
            src = get_active_melody_source_id(sec) or "active_melody"
            _push_active_melody_history(session_state, section_id, before, src)
            new_id = "edited_active_melody"
            apply_melody_events(
                doc,
                section_id,
                draft,
                concept={
                    "id": new_id,
                    "name": "Edited melody",
                    "motif_hint": "Edited in Advanced Phrase Editor",
                    "contour": "Manually edited active melody",
                },
                replace=True,
            )
            # Occurrence-level edits freeze tiling so repeat slider cannot wipe them.
            mark_melody_customized(section_by_id(doc, section_id))
            session_state[f"composer_melody_active_source_{section_id}"] = new_id
            session_state.pop(f"composer_melody_repeats_{section_id}", None)
            session_state[draft_key] = copy.deepcopy(draft)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
    with e3:
        if st.button("Reset proposal", key=f"composer_melody_ed_reset_{section_id}", use_container_width=True):
            session_state[draft_key] = copy.deepcopy(active_events)
            session_state.pop(choice_key, None)
            st.rerun()


def _render_melody_phrases_editor(session_state: dict, doc: dict[str, Any], section_id: str) -> None:
    """Legacy phrase list helper — prefer `_render_active_melody_phrase_editor`."""
    _render_active_melody_phrase_editor(session_state, doc, section_id)


def _render_phase_melody(session_state: dict, doc: dict[str, Any], *, host_side_panel: bool = True) -> None:
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

    center, side = _phase_main_side(host_side_panel=host_side_panel)
    with center:
        done, total = melodized_section_count(doc)
        st.markdown(
            f'<p class="composer-harmony-progress">Melody progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_section_lane_switcher(session_state, doc, active_lane="melody")
        _render_section_workspace_header(session_state, doc, section, lane="melody")
        _render_active_preview(session_state, stop_key=f"composer_melody_preview_stop_{active_id}")

        has_harmony = section_has_resolved_chords(doc, active_id)
        if not has_harmony:
            st.markdown(
                '<div class="composer-chords-first-banner">'
                "<strong>Melody-first is fine.</strong> Record or choose a melody now — "
                "you can add chords later that fit this melody. "
                "Preview plays the melody alone until harmony exists.</div>",
                unsafe_allow_html=True,
            )
            c_jump, _ = st.columns([1, 2])
            with c_jump:
                if st.button("Go to Chords for this section", key=f"composer_melody_to_chords_{active_id}"):
                    set_workflow_phase(doc, "chords")
                    _save_doc(session_state, doc)
                    st.rerun()
        elif melody_harmony_is_stale(doc, active_id):
            st.warning(
                "Chords changed after this melody was accepted. "
                "Preview still works, but consider choosing or recording a melody that fits the new progression."
            )

        # Sync durable active-source id (do NOT render a separate top Active Melody block).
        doc_active_early = get_active_melody_source_id(section)
        if doc_active_early:
            session_state[f"composer_melody_active_source_{active_id}"] = doc_active_early

        # 1) Melody Feel & Notes
        feel_ids = [f[0] for f in MELODY_FEELINGS]
        current_feel = str(intent.get("feel") or default_melody_feel_for_section(section))
        if current_feel not in feel_ids:
            current_feel = default_melody_feel_for_section(section)
        style_ids = [s[0] for s in MELODY_STYLES]
        current_style = str(intent.get("style") or "simple")
        if current_style not in style_ids:
            current_style = "simple"

        st.markdown("**Melody Feel & Notes**")
        st.caption("Set your musical direction before recording or exploring AI ideas.")
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
            "Notes for this melody",
            value=str(intent.get("hum_notes") or ""),
            key=f"composer_melody_hum_{active_id}",
            height=60,
            placeholder="Contour, lyric stress, range — anything that guides this section's melody.",
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

        intent_ready = _melody_intent_ready(intent) or bool(section_melody_events(section))
        if not intent_ready:
            if st.button(
                "Continue with this feel",
                key=f"composer_melody_feel_continue_{active_id}",
                type="primary",
            ):
                intent["feel"] = picked_feel
                intent["style"] = picked_style
                intent["remember"] = remember
                intent["hum_notes"] = hum
                intent["feel_confirmed"] = True
                _save_doc(session_state, doc)
                st.rerun()
            st.info("Add a short remember/notes line, or click Continue with this feel, to unlock recording and suggestions.")
        else:
            # 2) Hum / sing / play BEFORE AI suggestions (works with or without chords)
            _render_hum_sing_panel(session_state, doc, section, active_id=active_id)

            # 3) AI melody suggestions (consume Feel & Notes + full chords when present)
            st.markdown("**AI Melody Suggestions**")
            if has_harmony:
                st.caption(
                    "Preview to hear · Use this melody to accept. "
                    "Suggestions follow your Feel & Notes across the full section progression."
                )
            else:
                st.caption(
                    "No chords yet — suggestions use key, style, Feel & Notes, and section role. "
                    "You can harmonize this melody later on Chords."
                )
            doc_active = get_active_melody_source_id(section)
            if doc_active:
                session_state[f"composer_melody_active_source_{active_id}"] = doc_active
            active_melody_source = str(
                session_state.get(f"composer_melody_active_source_{active_id}")
                or doc_active
                or ""
            )
            concepts = suggest_melody_concepts(
                doc,
                section,
                picked_feel,
                picked_style,
                limit=3,
                remember=str(intent.get("remember") or remember or ""),
                notes=str(intent.get("hum_notes") or hum or ""),
            )
            # In-place active: highlight the matching suggestion card; tools sit beneath it.
            # Hum-sourced active is handled inside the hum panel (not duplicated here).
            matched_active_in_list = False
            tools_rendered = False
            for i, concept in enumerate(concepts):
                cid = str(concept.get("id") or "")
                is_active = bool(
                    active_melody_source
                    and cid == active_melody_source
                    and active_melody_source != "hum_transcription"
                )
                display = dict(concept)
                if is_active:
                    matched_active_in_list = True
                    # Show the full accepted timeline (incl. repeats) on the active card.
                    display["events"] = list(section_melody_events(section) or concept.get("events") or [])
                _render_melody_concept_card(
                    session_state,
                    doc,
                    active_id,
                    display,
                    prefix=f"composer_melody_explore_{active_id}_{i}",
                    is_active=is_active,
                )
                if is_active and not tools_rendered:
                    _render_active_melody_inplace_tools(
                        session_state,
                        doc,
                        section,
                        active_id,
                        has_harmony=has_harmony,
                        active_melody_source=active_melody_source,
                    )
                    tools_rendered = True

            # Accepted melody whose source is no longer in this suggestion list
            # (refine/APE accept, restored id, etc.) — compact in-place card here, not above Feel.
            if (
                section_melody_events(section)
                and active_melody_source
                and active_melody_source != "hum_transcription"
                and not matched_active_in_list
                and not tools_rendered
            ):
                sticky = _accepted_melody_concept_from_section(section)
                if sticky:
                    _render_melody_concept_card(
                        session_state,
                        doc,
                        active_id,
                        sticky,
                        prefix=f"composer_melody_sticky_{active_id}",
                        is_active=True,
                    )
                    _render_active_melody_inplace_tools(
                        session_state,
                        doc,
                        section,
                        active_id,
                        has_harmony=has_harmony,
                        active_melody_source=active_melody_source,
                    )

        if done > 0 and st.button("Continue →", type="primary", key="composer_melody_continue"):
            advance_workflow(doc, from_phase="melody")
            _save_doc(session_state, doc)
            st.rerun()

    _stash_or_render_phase_side(
        session_state,
        doc,
        side,
        coach_lead=coach_line_for_melody(
            doc,
            section,
            feel=str(intent.get("feel") or picked_feel),
            remember=str(intent.get("remember") or remember),
        ),
        caption="Record or explore ideas — sheet music is the main result.",
        show_sections=True,
    )


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
    """Keep active section id valid among existing sections. Do not invent structure.

    Auto-creating a Verse mid-render used to race the page-level Guided Path
    (pre-structure) against the phase side utility panel and duplicate
    ``composer_journey_*`` Streamlit keys.
    """
    order = list((doc.get("form") or {}).get("section_order") or [])
    active = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    if order and active not in order:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0]
    elif order and not active:
        session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0]


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
    """Manual / advanced chord editor — edit each chord in place with Preview/Accept/Cancel/Undo."""
    sid = str(section.get("id") or "")
    owner_id = owner_id or sid
    g = doc.setdefault("global", {})
    meter = str(g.get("time_signature") or "4/4")
    key_token = str(g.get("original_key_center") or "C")
    live_entries = list(section.get("chords") or [])
    draft = ensure_draft(session_state, sid, live_entries)
    editing_key = f"composer_chord_edit_idx_{sid}"
    insert_key = f"composer_chord_insert_at_{sid}"

    rows = annotate_chromatic(chord_timeline(draft, meter=meter), key_token)
    st.caption("Edit this section’s progression. Accepted changes update notation, melody alignment, and playback.")

    if rows:
        for row in rows:
            i = int(row["index"])
            chrom = " · outside key" if row.get("chromatic") else ""
            c1, c2, c3, c4, c5 = st.columns([2.2, 1.2, 1.0, 1.0, 1.0])
            with c1:
                st.markdown(
                    f"**{row.get('chord') or '?'}**  \n"
                    f"<span style='color:#64748b;font-size:0.85rem;'>m{row.get('measure')} "
                    f"beat {row.get('beat')}{chrom}</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Edit", key=f"composer_ch_edit_{sid}_{i}", use_container_width=True):
                    session_state[editing_key] = i
                    session_state.pop(insert_key, None)
                    st.rerun()
            with c3:
                if st.button("Insert after", key=f"composer_ch_ins_after_{sid}_{i}", use_container_width=True):
                    session_state[insert_key] = i + 1
                    session_state.pop(editing_key, None)
                    st.rerun()
            with c4:
                if st.button("Del", key=f"composer_ch_del_{sid}_{i}", use_container_width=True):
                    session_state[draft_key(sid)] = remove_draft_chord(draft, i)
                    st.rerun()
            with c5:
                bars = st.number_input(
                    "Bars",
                    min_value=1,
                    max_value=8,
                    value=int(row.get("bars") or 1),
                    key=f"composer_ch_bars_{sid}_{i}",
                    label_visibility="collapsed",
                )
                if int(bars) != int(row.get("bars") or 1):
                    session_state[draft_key(sid)] = update_draft_chord(draft, i, bars=int(bars))
                    st.rerun()
    else:
        st.info("No chords yet — insert the first chord below.")

    edit_idx = session_state.get(editing_key)
    if isinstance(edit_idx, int) and 0 <= edit_idx < len(draft):
        st.markdown("---")
        st.markdown(f"**Editing chord {edit_idx + 1}**")
        cur = draft[edit_idx] if isinstance(draft[edit_idx], dict) else {}
        parts = parse_chord_parts(str(cur.get("chord") or "C"))
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            root = st.selectbox("Root", ROOT_OPTIONS, index=ROOT_OPTIONS.index(parts["root"]) if parts["root"] in ROOT_OPTIONS else 0, key=f"composer_ch_root_{sid}")
        with e2:
            q_opts = list(QUALITY_OPTIONS)
            q_idx = q_opts.index(parts["quality"]) if parts["quality"] in q_opts else 0
            quality = st.selectbox("Quality", q_opts, index=q_idx, key=f"composer_ch_qual_{sid}")
        with e3:
            a_opts = list(ALTERATION_OPTIONS)
            a_idx = a_opts.index(parts["alteration"]) if parts["alteration"] in a_opts else 0
            alteration = st.selectbox("Alteration", a_opts, index=a_idx, key=f"composer_ch_alt_{sid}")
        with e4:
            bass_opts = [""] + list(ROOT_OPTIONS)
            bass_cur = parts.get("bass") or ""
            bass = st.selectbox("Bass /", bass_opts, index=bass_opts.index(bass_cur) if bass_cur in bass_opts else 0, key=f"composer_ch_bass_{sid}")
        built = build_chord_symbol(root=root, quality=quality, alteration=alteration, bass=bass)
        if is_chromatic_to_key(built, key_token):
            st.warning(f"`{built}` is outside the main key ({key_token}) — intentional chromatic color.")
        else:
            st.caption(f"Result: `{built}`")
        if st.button("Apply to draft", key=f"composer_ch_apply_edit_{sid}"):
            session_state[draft_key(sid)] = update_draft_chord(draft, edit_idx, chord=built)
            session_state.pop(editing_key, None)
            st.rerun()

    insert_at = session_state.get(insert_key)
    if insert_at is None and not rows:
        insert_at = 0
        session_state[insert_key] = 0
    if isinstance(insert_at, int):
        st.markdown("---")
        st.markdown(f"**Insert chord at position {insert_at + 1}**")
        before = ""
        after = ""
        if insert_at > 0 and insert_at - 1 < len(draft):
            before = str((draft[insert_at - 1] or {}).get("chord") or "")
        if insert_at < len(draft):
            after = str((draft[insert_at] or {}).get("chord") or "")
        suggestions = suggest_insert_chords(key_token=key_token, before=before, after=after)
        scols = st.columns(min(3, max(1, len(suggestions))))
        for si, sug in enumerate(suggestions[:6]):
            with scols[si % len(scols)]:
                label = str(sug.get("chord") or "")
                why = str(sug.get("why") or "")
                if sug.get("chromatic"):
                    why = f"{why} (chromatic)"
                if st.button(label, key=f"composer_ch_sug_{sid}_{insert_at}_{si}", help=why, use_container_width=True):
                    session_state[draft_key(sid)] = insert_draft_chord(draft, insert_at, label)
                    session_state.pop(insert_key, None)
                    st.rerun()
        custom = st.text_input("Or type a chord", key=f"composer_ch_insert_custom_{sid}", placeholder="G7 / Bbmaj7 / F#m7b5")
        if st.button("Insert typed chord", key=f"composer_ch_insert_go_{sid}") and custom.strip():
            session_state[draft_key(sid)] = insert_draft_chord(draft, int(insert_at), custom.strip())
            session_state.pop(insert_key, None)
            st.rerun()
        if st.button("Cancel insert", key=f"composer_ch_insert_cancel_{sid}"):
            session_state.pop(insert_key, None)
            st.rerun()

    if not rows:
        if st.button("Insert first chord…", key=f"composer_ch_first_{sid}"):
            session_state[insert_key] = 0
            st.rerun()

    st.markdown("---")
    paste = st.text_input("Paste progression", key=f"composer_paste_{sid}", placeholder="| G | Am | C | D |")
    if st.button("Apply paste to draft", key=f"composer_paste_apply_{sid}") and paste:
        session_state[draft_key(sid)] = parse_chord_paste(paste)
        st.rerun()

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        edit_slot = f"chords:{sid}:manual"
        mel_evs = list(section_melody_events(section) or [])
        if st.button("▶ Preview", key=f"composer_ch_preview_{sid}", use_container_width=True):
            chords = draft_playback_chords(session_state.get(draft_key(sid)) or draft)
            if not _play_chord_idea(
                session_state,
                doc,
                sid,
                chords,
                slot=edit_slot,
                label=(
                    "Playing · edited progression + melody"
                    if mel_evs
                    else "Playing · edited progression"
                ),
                include_melody=bool(mel_evs),
            ):
                st.warning("Add at least one chord to preview.")
        draft_syms = draft_playback_chords(session_state.get(draft_key(sid)) or draft)
        if mel_evs:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=edit_slot,
                events=mel_evs,
                chord_syms=draft_syms,
                caption="Follow the highlighted melody note",
                dom_id=f"man_{sid[:8]}",
            )
        else:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=edit_slot,
                events=None,
                chord_syms=draft_syms,
                caption="Follow the highlighted chord",
                dom_id=f"man_{sid[:8]}",
            )
    with a2:
        if st.button("Accept", key=f"composer_ch_accept_{sid}", type="primary", use_container_width=True):
            push_undo(session_state, sid, live_entries)
            new_entries = list(session_state.get(draft_key(sid)) or draft)
            accept_full_progression(doc, sid, new_entries, source_id="", tiled=False)
            clear_draft(session_state, sid)
            session_state.pop(editing_key, None)
            session_state.pop(insert_key, None)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
    with a3:
        if st.button("Cancel", key=f"composer_ch_cancel_{sid}", use_container_width=True):
            clear_draft(session_state, sid)
            session_state.pop(editing_key, None)
            session_state.pop(insert_key, None)
            st.rerun()
    with a4:
        if st.button("Undo", key=f"composer_ch_undo_{sid}", use_container_width=True):
            prev = pop_undo(session_state, sid)
            if prev is not None:
                accept_full_progression(doc, sid, prev, source_id="", tiled=False)
                clear_draft(session_state, sid)
                invalidate_composer_preview(session_state)
                _save_doc(session_state, doc)
                st.rerun()
            else:
                st.caption("Nothing to undo.")


def _render_rhythm_lane(session_state: dict, doc: dict[str, Any]) -> None:
    g = doc.setdefault("global", {})
    meta = doc.setdefault("metadata", {})
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
    current_label = coerce_composition_key_choice_for_doc(
        doc,
        str(g.get("original_key_label") or "")
        or composition_key_label_from_token(str(g.get("original_key_center") or "C")),
    )
    mode_family = ensure_original_mode_family(doc)
    key_labels = composition_key_choice_labels_for_family(mode_family)
    if "composer_rhythm_key" not in session_state or session_state.get("composer_rhythm_key") not in key_labels:
        session_state["composer_rhythm_key"] = current_label
    picked_label = st.selectbox(
        "Song key",
        key_labels,
        key="composer_rhythm_key",
        help=f"Locked to {mode_family} keys for this Composition.",
    )
    label = coerce_composition_key_choice_for_doc(doc, str(picked_label or current_label))
    meta["mood"] = st.text_input("Mood / emotion (optional)", value=str(meta.get("mood") or ""), key="composer_rhythm_mood")
    if st.button("Apply rhythm settings", key="composer_apply_rhythm", type="primary"):
        new_token = composition_key_token_from_choice(label)
        old_token = str(g.get("original_key_center") or "")
        if new_token != old_token:
            apply_song_key_change(
                session_state, doc, new_token, new_key_label=label, push_undo=True
            )
        else:
            g["original_key_label"] = label
            g["original_key_center"] = new_token
            ensure_original_mode_family(doc)
        meta["style"] = g.get("progression_style") or meta.get("style")
        invalidate_composer_preview(session_state)
        _save_doc(session_state, doc)
        st.rerun()
    if session_state.get(KEY_UNDO_KEY) and st.button("Undo key change", key="composer_rhythm_undo_key"):
        if apply_undo_key_change(session_state, doc):
            invalidate_composer_preview(session_state)
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
    # Normalize widget-owned keys BEFORE construction. Never assign a
    # widget key after st.slider creates it in the same run.
    if loops_key not in session_state:
        session_state[loops_key] = int(session_state.get("composer_play_loops") or 2)
    if (
        loops_key != "composer_play_loops"
        and "composer_play_loops" not in session_state
    ):
        session_state["composer_play_loops"] = int(session_state.get(loops_key) or 2)
    loops = int(session_state.get(loops_key) or 2)
    has_mel = bool(melody_override) or bool(section_melody_events(section_by_id(doc, section_id)))
    if include_melody and has_mel:
        button_label = (
            button_label
            if "melody" in button_label.lower() or "+" in button_label
            else "▶ Play section (chords + melody)"
        )
    elif not include_melody:
        button_label = button_label if button_label else "▶ Play chords"

    t1, t2 = st.columns([2, 3])
    with t1:
        loops = st.slider("Loops", 1, 4, loops, key=loops_key)
    with t2:
        play = st.button(button_label, type="primary", key=preview_key, use_container_width=True)

    transport_slot = f"transport:{preview_key}"
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
            slot=transport_slot,
            label=button_label.replace("▶ ", "Playing · "),
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Add chords to this section first — melody sits on your harmony."))

    if render_preview:
        sec = section_by_id(doc, section_id)
        mel_evs = list(melody_override or []) or (
            list(section_melody_events(sec) or []) if include_melody else []
        )
        ch_syms = list(chord_override or []) or list(
            chords_for_playback(doc, scope="section", section_id=section_id) or []
        )
        if mel_evs or ch_syms:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=transport_slot,
                events=mel_evs or None,
                chord_syms=ch_syms or None,
                caption=(
                    "Follow the highlighted melody note"
                    if mel_evs
                    else "Follow the highlighted chord"
                ),
                dom_id=f"tr_{preview_key[-12:]}",
            )
        else:
            _attach_local_preview(session_state, slot=transport_slot, stop_key=stop_key)
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
        lyrics["raw_text"] = raw
        lyrics["lines"] = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        _save_doc(session_state, doc)


def _render_phase_lyrics(session_state: dict, doc: dict[str, Any], *, host_side_panel: bool = True) -> None:
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

    center, side = _phase_main_side(host_side_panel=host_side_panel)
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

    _stash_or_render_phase_side(
        session_state,
        doc,
        side,
        coach_lead=coach_line_for_lyrics(
            doc,
            section,
            role=picked_role,
            emotion=picked_emotion,
            remember=remember,
        ),
        show_sections=True,
    )


def _render_active_melody_repeat_controls(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    section_id: str,
) -> None:
    """Section-scoped Melody repeats — always visible for an active accepted melody."""
    events = list(section_melody_events(section) or [])
    if not events:
        return

    # Heal legacy / incomplete meta so a clean accepted melody always gets a slider.
    # Durable condition: active events exist + tiling is still safe (not just_accepted).
    editable = melody_repeats_are_editable(section)
    repeats = get_melody_repeats(section)
    active_slot = f"melody:{section_id}:active_loop"

    st.markdown("**Melody repeats**")
    if editable:
        st.caption(
            "How many times this phrase covers the section (1–4). "
            "Changing this rebuilds the full active melody timeline in the staff."
        )
        repeats_key = f"composer_melody_repeats_{section_id}"
        # Keep widget key aligned with durable section state (section-scoped).
        session_state[repeats_key] = int(repeats)
        # Explicit 1–4 choices — more visible/usable than a thin Streamlit slider.
        choice_cols = st.columns(MELODY_REPEAT_MAX - MELODY_REPEAT_MIN + 1)
        chosen: int | None = None
        for i, n in enumerate(range(MELODY_REPEAT_MIN, MELODY_REPEAT_MAX + 1)):
            with choice_cols[i]:
                if st.button(
                    str(n),
                    key=f"composer_melody_repeats_btn_{section_id}_{n}",
                    type="primary" if n == int(repeats) else "secondary",
                    use_container_width=True,
                    help=f"Tile this melody phrase {n} time(s) for this section.",
                ):
                    chosen = int(n)
        if chosen is not None and chosen != int(repeats):
            if set_section_melody_repeats(doc, section_id, int(chosen)):
                session_state[repeats_key] = int(chosen)
                session_state.pop(_editor_draft_key(section_id), None)
                session_state.pop(_refine_proposal_key(section_id), None)
                invalidate_composer_preview(session_state)
                _save_doc(session_state, doc)
                st.rerun()
            else:
                st.warning("Could not update melody repeats for this section.")
                session_state[repeats_key] = int(repeats)
        n_rep = int(get_melody_repeats(section))
        n_ev = len(list(section_melody_events(section) or []))
        if n_rep > 1:
            st.success(
                f"Full active melody = phrase × {n_rep} "
                f"({n_ev} events across all passes) — shown in the staff above."
            )
        else:
            st.caption(f"Currently 1 pass ({n_ev} events). Choose 2–4 to expand the section.")
    else:
        st.info(
            "Repeats are locked because individual passes have been edited. "
            "The full custom timeline stays as written."
        )
        st.caption(f"{len(events)} events in the active customized melody.")
        if st.button(
            "Unlock Melody repeats (use current melody as the new phrase)",
            key=f"composer_melody_unlock_repeats_{section_id}",
            help="Treat the current full melody as a new 1-pass pattern so you can tile it again.",
        ):
            from composition_melody_repeats import ensure_melody_repeat_meta

            melody = ensure_melody_repeat_meta(section)
            cur = list(section_melody_events(section) or [])
            melody["melody_pattern"] = [dict(e) for e in cur]
            melody["melody_repeats"] = 1
            melody["melody_tiled"] = True
            melody["melody_customized"] = False
            session_state.pop(f"composer_melody_repeats_{section_id}", None)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()

    chords = list(section.get("chords") or [])
    flat = chords_for_playback(doc, scope="section", section_id=section_id) if chords else []
    if st.button("▶ Play full melody", key=f"composer_melody_active_play_{section_id}", use_container_width=True):
        result = play_composer_preview(
            session_state,
            doc,
            section_id=section_id,
            include_melody=True,
            loops=1,
            melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.45),
            backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.85),
            chord_override=[str(c) for c in flat] if flat else [],
            slot=active_slot,
            label=(
                "Playing · full active melody + chords"
                if flat
                else "Playing · full active melody"
            ),
        )
        if not result.get("ok"):
            st.warning(str(result.get("reason") or "Could not play the active melody."))
    _attach_synced_score_preview(
        session_state,
        doc,
        slot=active_slot,
        events=list(section_melody_events(section) or []),
        chord_syms=[str(c) for c in flat] if flat else None,
        caption="Follow the highlighted melody note",
        dom_id=f"act_mel_{section_id[:8]}",
    )


def _render_active_melody_inplace_tools(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    active_id: str,
    *,
    has_harmony: bool = False,
    active_melody_source: str = "",
) -> None:
    """Repeats + Shape/Refine + APE directly beneath the in-place active melody.

    Does not render a separate page-top Active Melody card — the caller already
    highlighted the chosen suggestion/recording in its original list position.
    """
    if not section_melody_events(section):
        return
    heal_melody_tiling_if_safe(section)

    if session_state.pop(f"composer_melody_just_accepted_{active_id}", None):
        st.info(
            "Melody accepted. Set **Melody repeats** below so the full section "
            "timeline is ready before writing Chords."
        )

    if has_harmony:
        flat = chords_for_playback(doc, scope="section", section_id=active_id)
        if flat:
            from composition_chord_repeats import format_full_progression_display

            st.caption(
                f"Section harmony ({len(flat)} chords): "
                + format_full_progression_display(
                    list(section.get("chords") or []), pattern_len=None
                ).replace("\n", " · ")
            )

    _render_active_melody_repeat_controls(session_state, doc, section, active_id)

    st.markdown("**Shape / refine active melody**")
    st.caption(
        "Creates a proposal from the full highlighted active melody "
        "(all repeats). Preview leaves it active; Accept replaces it."
    )
    pg = playback_globals(doc)
    key_center = str(pg.get("key_center") or "C")
    ref_cols = st.columns(min(4, len(MELODY_REFINEMENTS)))
    for i, (rid, label, _) in enumerate(MELODY_REFINEMENTS[:4]):
        with ref_cols[i % len(ref_cols)]:
            if st.button(label, key=f"composer_melody_ref_{active_id}_{rid}", use_container_width=True):
                before = list(section_melody_events(section) or [])
                src = get_active_melody_source_id(section) or active_melody_source
                result = propose_melody_refinement(before, rid, key=key_center)
                if result.get("unchanged") or not result.get("ok"):
                    st.warning(str(result.get("summary") or "No musical change from that shape."))
                else:
                    prop_events = list(result.get("events") or [])
                    session_state[_refine_proposal_key(active_id)] = {
                        "events": prop_events,
                        "from_source": src,
                        "refinement_id": rid,
                        "label": label,
                        "summary": describe_melody_from_events(
                            prop_events, chord_count=len(list(section.get("chords") or []))
                        ),
                    }
                    st.rerun()
    with st.expander("More local refinements", expanded=False):
        more_cols = st.columns(min(3, max(1, len(MELODY_REFINEMENTS) - 4)))
        for i, (rid, label, _) in enumerate(MELODY_REFINEMENTS[4:]):
            with more_cols[i % len(more_cols)]:
                if st.button(label, key=f"composer_melody_ref_more_{active_id}_{rid}", use_container_width=True):
                    before = list(section_melody_events(section) or [])
                    src = get_active_melody_source_id(section) or active_melody_source
                    result = propose_melody_refinement(before, rid, key=key_center)
                    if result.get("unchanged") or not result.get("ok"):
                        st.warning(str(result.get("summary") or "No musical change from that shape."))
                    else:
                        prop_events = list(result.get("events") or [])
                        session_state[_refine_proposal_key(active_id)] = {
                            "events": prop_events,
                            "from_source": src,
                            "refinement_id": rid,
                            "label": label,
                            "summary": describe_melody_from_events(
                                prop_events, chord_count=len(list(section.get("chords") or []))
                            ),
                        }
                        st.rerun()

    proposal = session_state.get(_refine_proposal_key(active_id))
    if isinstance(proposal, dict) and proposal.get("events"):
        st.markdown("**Refinement proposal**")
        if proposal.get("summary"):
            st.caption(str(proposal.get("summary")))
        prop_events = list(proposal.get("events") or [])
        prop_name = str(proposal.get("label") or "Refined melody")
        _render_melody_staff(
            prop_events,
            key=key_center,
            meter=str(pg.get("time_signature") or "4/4"),
            bpm=int(pg.get("bpm") or 96),
            title=prop_name,
            height=180,
            chords=list(section.get("chords") or []),
        )
        rp1, rp2, rp3 = st.columns(3)
        refine_slot = f"melody:{active_id}:refine_proposal"
        with rp1:
            if st.button("▶ Preview", key=f"composer_melody_refine_preview_{active_id}", use_container_width=True):
                play_composer_preview(
                    session_state,
                    doc,
                    section_id=active_id,
                    include_melody=True,
                    melody_override=prop_events,
                    loops=1,
                    melody_gain=float(session_state.get("composer_melody_mix_gain") or 0.45),
                    backing_gain=float(session_state.get("composer_backing_mix_gain") or 0.85),
                    chord_override=list(
                        chords_for_playback(doc, scope="section", section_id=active_id) or []
                    ),
                    slot=refine_slot,
                    label=f"Playing proposal · {prop_name}",
                )
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=refine_slot,
                events=prop_events,
                chord_syms=list(
                    chords_for_playback(doc, scope="section", section_id=active_id) or []
                )
                or None,
                caption="Follow the highlighted note (proposal)",
                dom_id=f"ref_{active_id[:8]}",
            )
        with rp2:
            if st.button("Accept refinement", key=f"composer_melody_refine_accept_{active_id}", type="primary", use_container_width=True):
                before = list(section_melody_events(section) or [])
                src = get_active_melody_source_id(section) or active_melody_source
                _push_active_melody_history(session_state, active_id, before, src)
                new_id = f"refined_{proposal.get('refinement_id') or 'edit'}"
                apply_melody_events(
                    doc,
                    active_id,
                    prop_events,
                    concept={
                        "id": new_id,
                        "name": prop_name,
                        "motif_hint": f"Refined from {src}",
                        "contour": prop_name,
                    },
                    replace=True,
                )
                mark_melody_customized(section_by_id(doc, active_id))
                session_state[f"composer_melody_active_source_{active_id}"] = new_id
                session_state.pop(f"composer_melody_repeats_{active_id}", None)
                session_state.pop(_refine_proposal_key(active_id), None)
                session_state.pop(_editor_draft_key(active_id), None)
                invalidate_composer_preview(session_state)
                _save_doc(session_state, doc)
                st.rerun()
        with rp3:
            if st.button("Dismiss proposal", key=f"composer_melody_refine_dismiss_{active_id}", use_container_width=True):
                session_state.pop(_refine_proposal_key(active_id), None)
                st.rerun()

    hist = session_state.get(_active_melody_history_key(active_id)) or []
    if hist and st.button(
        "Undo last accepted shape/refine",
        key=f"composer_melody_active_undo_btn_{active_id}",
        use_container_width=True,
    ):
        prev = _pop_active_melody_history(session_state, active_id)
        if prev and isinstance(prev.get("events"), list):
            apply_melody_events(
                doc,
                active_id,
                list(prev["events"]),
                concept={
                    "id": str(prev.get("source_id") or "restored_melody"),
                    "name": "Restored melody",
                    "motif_hint": "Restored from active-melody history",
                    "contour": "Restored previous active melody",
                },
                replace=True,
            )
            session_state[f"composer_melody_active_source_{active_id}"] = str(
                prev.get("source_id") or "restored_melody"
            )
            session_state.pop(_editor_draft_key(active_id), None)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()

    with st.expander("Advanced Phrase Editor", expanded=False):
        _render_active_melody_phrase_editor(session_state, doc, active_id)


def _render_active_melody_workspace(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    active_id: str,
    *,
    has_harmony: bool,
    active_melody_source: str = "",
) -> None:
    """Deprecated alias — tools only; callers should highlight the card in place."""
    _render_active_melody_inplace_tools(
        session_state,
        doc,
        section,
        active_id,
        has_harmony=has_harmony,
        active_melody_source=active_melody_source,
    )


def _render_active_progression_card(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    section_id: str,
    *,
    title: str = "Active progression",
    why: str = "This is the harmony currently used for this section.",
) -> None:
    """Highlighted card for the authoritative full section progression."""
    ensure_harmony_chord_meta(section)
    entries = list(section.get("chords") or [])
    if not entries:
        return
    plen = pattern_length_for_display(section)
    display = format_full_progression_display(entries, pattern_len=plen)
    display_html = html.escape(display).replace("\n", "<br>")
    st.markdown(
        f"""
<div class="composer-suggestion-card is-active" data-composer-active="1">
  <h4>{html.escape(title)}<span class="composer-active-badge">Active</span></h4>
  <div class="composer-suggestion-chords">{display_html}</div>
  <p class="composer-suggestion-why">{html.escape(why)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Active progression for this section")
    _render_active_progression_controls(session_state, doc, section, section_id)


def _render_active_progression_controls(
    session_state: dict,
    doc: dict[str, Any],
    section: dict[str, Any],
    section_id: str,
) -> None:
    """Repeat slider (when tiled) + play the full active progression."""
    tiled = chords_are_tiled(section)
    repeats = get_chord_repeats(section)
    active_slot = f"chords:{section_id}:active"
    melody_owns_length = _melody_defines_section_length(section)
    mel_events = list(section_melody_events(section) or [])
    c1, c2 = st.columns([2, 2])
    with c1:
        if melody_owns_length:
            st.caption(
                "Harmony length follows the active melody "
                f"({len(mel_events)} events) — no separate chord-repeat control."
            )
        elif tiled:
            repeats_key = f"composer_chord_repeats_{section_id}"
            if repeats_key not in session_state:
                session_state[repeats_key] = repeats
            new_repeats = st.slider(
                "Repeats",
                CHORD_REPEAT_MIN,
                CHORD_REPEAT_MAX,
                int(session_state.get(repeats_key) or repeats),
                key=repeats_key,
                help="How many times this progression covers the section",
            )
            if int(new_repeats) != int(repeats):
                if set_section_chord_repeats(doc, section_id, int(new_repeats)):
                    from composition_chord_manual_editor import clear_draft

                    clear_draft(session_state, section_id)
                    invalidate_composer_preview(session_state)
                    _save_doc(session_state, doc)
                    st.rerun()
        else:
            st.caption("Customized progression — each chord occurrence is kept as written.")
    with c2:
        if st.button("▶ Play", key=f"composer_active_play_{section_id}", type="primary", use_container_width=True):
            syms = entry_symbols(list(section.get("chords") or []))
            if not _play_chord_idea(
                session_state,
                doc,
                section_id,
                syms,
                loops=1,
                slot=active_slot,
                label=(
                    "Playing · melody + active progression"
                    if mel_events
                    else "Playing · active progression"
                ),
                include_melody=bool(mel_events),
            ):
                st.warning("Could not play the active progression.")
        if mel_events:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=active_slot,
                events=mel_events,
                chord_syms=entry_symbols(list(section.get("chords") or [])),
                caption="Follow the highlighted melody note",
                dom_id=f"active_ch_{section_id[:8]}",
            )
        else:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=active_slot,
                events=None,
                chord_syms=entry_symbols(list(section.get("chords") or [])),
                caption="Follow the highlighted chord",
                dom_id=f"active_ch_only_{section_id[:8]}",
            )


def _render_suggestion_card(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    suggestion: dict[str, Any],
    *,
    prefix: str,
    section: dict[str, Any] | None = None,
    is_active: bool = False,
) -> None:
    sid = str(suggestion.get("id") or prefix)
    line = str(suggestion.get("line") or "")
    why = str(suggestion.get("why") or "")
    name = str(suggestion.get("name") or "Suggestion")
    entries = list(suggestion.get("chords") or [])
    chord_syms = expand_entries_to_chords(entries)
    preview_sig = session_state.get(COMPOSER_PREVIEW_SIG_KEY)
    is_active_preview = (
        isinstance(preview_sig, tuple)
        and len(preview_sig) >= 4
        and tuple(chord_syms) == tuple(preview_sig[3] or ())
        and bool(session_state.get(COMPOSER_PREVIEW_WAV_KEY))
        and composer_preview_slot(session_state) == f"chords:{section_id}:{sid}"
    )

    if is_active and section is not None:
        ensure_harmony_chord_meta(section)
        display = format_full_progression_display(
            list(section.get("chords") or []),
            pattern_len=pattern_length_for_display(section),
        )
        display_html = html.escape(display).replace("\n", "<br>")
        badge = '<span class="composer-active-badge">Active</span>'
        card_class = "composer-suggestion-card is-active"
        subtitle = " · previewing" if is_active_preview else ""
        st.markdown(
            f"""
<div class="{card_class}" data-composer-active="1">
  <h4>{html.escape(name)}{badge}{html.escape(subtitle)}</h4>
  <div class="composer-suggestion-chords">{display_html}</div>
  <p class="composer-suggestion-why">{html.escape(why)}</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Active progression for this section")
        _render_active_progression_controls(session_state, doc, section, section_id)
        return

    card_class = "composer-suggestion-card"
    st.markdown(
        f"""
<div class="{card_class}">
  <h4>{html.escape(name)}{" · previewing" if is_active_preview else ""}</h4>
  <div class="composer-suggestion-chords">{html.escape(line)}</div>
  <p class="composer-suggestion-why">{html.escape(why)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns(2)
    with p1:
        card_slot = f"chords:{section_id}:{sid}"
        has_mel = bool(section and section_melody_events(section))
        preview_btn = "▶ Preview with melody" if has_mel else "▶ Preview"
        if st.button(preview_btn, key=f"{prefix}_preview_{sid}", use_container_width=True):
            if not _play_chord_idea(
                session_state,
                doc,
                section_id,
                chord_syms,
                slot=card_slot,
                label=(
                    f"Playing melody + proposed chords · {name}"
                    if has_mel
                    else f"Playing · {name}"
                ),
                include_melody=has_mel,
            ):
                st.warning("Could not generate preview for that progression.")
        mel_ev = list(section_melody_events(section) or []) if has_mel else None
        if has_mel and mel_ev:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=card_slot,
                events=mel_ev,
                chord_syms=chord_syms,
                caption="Proposed harmony under your active melody — follow the highlighted note",
                dom_id=f"sug_{sid}"[:40],
            )
        else:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=card_slot,
                events=None,
                chord_syms=chord_syms,
                caption="Follow the highlighted chord",
                dom_id=f"sug_ch_{sid}"[:40],
            )
    with p2:
        if st.button("Use this", key=f"{prefix}_use_{sid}", type="primary", use_container_width=True):
            # When melody already defines section length, accept the full proposed
            # progression as-written (no separate chord-repeat tiling).
            if section is not None and _melody_defines_section_length(section):
                accept_full_progression(
                    doc,
                    section_id,
                    entries,
                    source_id=sid,
                    tiled=False,
                )
            else:
                accept_chord_pattern(
                    doc,
                    section_id,
                    entries,
                    source_id=sid,
                    repeats=get_chord_repeats(section) if section else 1,
                )
            session_state.pop(f"composer_refine_proposal_{section_id}", None)
            from composition_chord_manual_editor import clear_draft

            clear_draft(session_state, section_id)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()


def _render_chord_refinement_panel(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    section: dict[str, Any],
) -> None:
    ensure_harmony_chord_meta(section)
    entries = list(section.get("chords") or [])
    if not entries:
        return
    st.markdown("**Refine this progression**")
    st.caption(
        "Describe the musical change — refinements use the full active progression "
        "(including repeats). Preview before accepting."
    )
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
    proposed_entries = list(proposal.get("chords") or [])
    plen = pattern_length_for_display(section)
    source_display = format_full_progression_display(entries, pattern_len=plen)
    proposed_display = format_full_progression_display(proposed_entries, pattern_len=plen)
    source_html = html.escape(source_display).replace("\n", "<br>")
    proposed_html = html.escape(proposed_display).replace("\n", "<br>")
    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(str(proposal.get('name') or 'Proposed change'))}</h4>
  <div class="composer-suggestion-chords">
    <span style="opacity:0.65">{source_html}</span>
    <br>→ <strong>{proposed_html}</strong>
  </div>
  <p class="composer-suggestion-why">{html.escape(str(proposal.get('why') or ''))}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    chord_syms = expand_entries_to_chords(proposed_entries)
    refine_slot = f"chords:{section_id}:refine"
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        mel_evs = list(section_melody_events(section_by_id(doc, section_id)) or [])
        if st.button("▶ Preview", key=f"composer_refine_preview_{section_id}", use_container_width=True):
            if not _play_chord_idea(
                session_state,
                doc,
                section_id,
                chord_syms,
                loops=1,
                slot=refine_slot,
                label=(
                    "Playing · refinement + melody"
                    if mel_evs
                    else "Playing · refinement"
                ),
                include_melody=bool(mel_evs),
            ):
                st.warning("Could not preview that proposal.")
        if mel_evs:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=refine_slot,
                events=mel_evs,
                chord_syms=chord_syms,
                caption="Follow the highlighted melody note",
                dom_id=f"chref_{section_id[:8]}",
            )
        else:
            _attach_synced_score_preview(
                session_state,
                doc,
                slot=refine_slot,
                events=None,
                chord_syms=chord_syms,
                caption="Follow the highlighted chord",
                dom_id=f"chref_{section_id[:8]}",
            )
    with a2:
        if st.button("Use this", key=f"composer_refine_use_{section_id}", type="primary", use_container_width=True):
            accept_full_progression(
                doc,
                section_id,
                proposed_entries,
                source_id=str(proposal.get("id") or "refine"),
                tiled=False,
            )
            session_state.pop(f"composer_refine_proposal_{section_id}", None)
            session_state.pop(f"composer_chord_repeats_{section_id}", None)
            from composition_chord_manual_editor import clear_draft

            clear_draft(session_state, section_id)
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
        sig = preview_signature(
            doc,
            scope=scope,
            section_id=section_id if scope == "section" else None,
            loops=loops,
        )
        wav = generate_preview_wav(
            doc,
            scope=scope,
            section_id=section_id if scope == "section" else None,
            loops=loops,
            include_melody=(scope == "section"),
        )
        if wav:
            set_composer_preview(session_state, wav, sig)
        else:
            st.warning("Add at least one chord before playing.")

    _render_active_preview(session_state)


def _render_phase_chords(session_state: dict, doc: dict[str, Any], *, host_side_panel: bool = True) -> None:
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

    center, side = _phase_main_side(host_side_panel=host_side_panel)
    with center:
        done, total = harmonized_section_count(doc)
        st.markdown(
            f'<p class="composer-harmony-progress">Harmony progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
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
                    _select_active_section(session_state, doc, edit_id)
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
            if edit_section is not None:
                ensure_harmony_chord_meta(edit_section)

            if not entries:
                st.info("Start by choosing or creating harmony for this section.")

            suggestions = suggest_progressions(doc, section, picked, limit=3)

            # Clear any leftover Compare queue — workflow is Preview → Use only.
            _render_compare_tray(session_state, doc, target_id, suggestions)

            # Harmony suggestions — the accepted card (if any) is the active progression.
            st.markdown("**Harmony suggestions**")
            if _melody_defines_section_length(edit_section or section):
                mel_n = len(list(section_melody_events(edit_section or section) or []))
                st.caption(
                    f"Harmony length follows the active melody ({mel_n} events) — "
                    "no separate chord-repeat question. Suggestions cover the full melody timeline."
                )
            else:
                st.caption("Preview to hear · Use this to accept.")
            active_source = get_chord_source_id(edit_section) if edit_section else ""
            sug_ids = {str(s.get("id") or "") for s in suggestions}
            if entries and active_source and active_source not in sug_ids:
                _render_active_progression_card(
                    session_state,
                    doc,
                    edit_section or section,
                    target_id,
                    title="Active progression",
                    why="Refined or manually edited harmony for this section.",
                )
            elif entries and not active_source:
                # Legacy / pasted chords with no suggestion source — still one active card.
                _render_active_progression_card(
                    session_state,
                    doc,
                    edit_section or section,
                    target_id,
                )

            for i, sug in enumerate(suggestions):
                sug_id = str(sug.get("id") or "")
                _render_suggestion_card(
                    session_state,
                    doc,
                    target_id,
                    sug,
                    prefix=f"composer_explore_{active_id}_{i}",
                    section=edit_section,
                    is_active=bool(entries) and sug_id == active_source and sug_id != "",
                )

            if entries:
                st.info(COMPLETION_COPY)
                if st.button("Build a melody over these chords →", key=f"composer_chords_to_melody_{active_id}"):
                    session_state[COMPOSER_FOCUS_LANE_KEY] = "melody"
                    set_workflow_phase(doc, "melody")
                    _save_doc(session_state, doc)
                    st.rerun()
                _render_chord_refinement_panel(session_state, doc, target_id, edit_section or section)
                with st.expander("Manual / advanced chord editor", expanded=False):
                    if edit_section:
                        _render_chords_lane(session_state, doc, edit_section, owner_id=target_id)

        if done > 0 and st.button("Continue to Melody →", type="primary", key="composer_chords_continue"):
            advance_workflow(doc, from_phase="chords")
            _save_doc(session_state, doc)
            st.rerun()

    feeling = str(
        (edit_section or section).get("harmony", {}).get("feeling") or default_feeling_for_section(section)
    )
    _stash_or_render_phase_side(
        session_state,
        doc,
        side,
        coach_lead=coach_line_for_section(doc, section, feeling=feeling),
        show_sections=True,
    )


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

    has_structure = document_has_structure(doc)
    # After structure exists, ONE page-level main/right split owns the utility panel.
    # Phases render creative content into main only (host_side_panel=False).
    use_page_split = has_structure and phase in COMPOSER_DESKTOP_SPLIT_PHASES

    # Before structure exists, keep a top Guided Path so early phases remain navigable.
    # Phases must not also render journey buttons in a side column in this mode
    # (duplicate Streamlit keys). Side utilities only appear after structure exists
    # via the page-level right column (use_page_split) or phase host_side_panel.
    if not has_structure:
        _render_journey_rail(session_state, doc)

    def _dispatch(*, host_side_panel: bool) -> None:
        if phase == "vision":
            _render_phase_vision(session_state, doc)
        elif phase == "structure":
            _render_phase_structure(session_state, doc, host_side_panel=host_side_panel)
        elif phase == "chords":
            _render_phase_chords(session_state, doc, host_side_panel=host_side_panel)
        elif phase == "melody":
            _render_phase_melody(session_state, doc, host_side_panel=host_side_panel)
        elif phase == "lyrics":
            _render_phase_lyrics(session_state, doc, host_side_panel=host_side_panel)
        elif phase == "review":
            _render_phase_review(session_state, doc, host_side_panel=host_side_panel)
        else:
            _render_phase_vision(session_state, doc)

    if use_page_split:
        session_state.pop(COMPOSER_SIDE_COACH_KEY, None)
        session_state.pop(COMPOSER_SIDE_CAPTION_KEY, None)
        with st.container(key="composer_desktop_split"):
            main_col, right_col = st.columns([2.6, 1.0])
            with main_col:
                _dispatch(host_side_panel=False)
            with right_col:
                _render_page_right_utility(session_state, doc, phase=phase)
    else:
        _dispatch(host_side_panel=True)
