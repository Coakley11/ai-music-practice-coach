"""Composition Studio — guided six-phase songwriting workspace (CS-B0+)."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from composition_review import (
    build_readiness_checklist,
    coach_line_for_review,
    harmony_overview_rows,
    lyrics_overview_rows,
    melody_overview_rows,
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
    melody_notation_line,
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
    generate_preview_wav,
    invalidate_composer_preview,
    preview_signature,
    set_composer_preview,
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
    touch_composition(doc)
    set_active_document(session_state, doc)
    save_document_to_library(session_state, doc)


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

        st.markdown('<div class="composer-review-block"><h4>Harmony</h4></div>', unsafe_allow_html=True)
        for row in harmony_overview_rows(doc):
            link_bit = f' <em>({html.escape(str(row["note"]))})</em>' if row.get("note") else ""
            st.markdown(
                f'<div class="composer-review-section-row"><strong>{html.escape(row["variant"])}</strong> — '
                f'{html.escape(str(row["line"]))}{link_bit}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="composer-review-block"><h4>Melody</h4></div>', unsafe_allow_html=True)
        for row in melody_overview_rows(doc):
            status = "✓" if row["complete"] else "○ needs work"
            extra = f' — <em>{html.escape(str(row["summary"]))}</em>' if row.get("summary") else ""
            st.markdown(
                f'<div class="composer-review-section-row">{status} <strong>{html.escape(row["variant"])}</strong>{extra}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="composer-review-block"><h4>Lyrics</h4></div>', unsafe_allow_html=True)
        if skip_lyrics:
            st.markdown(
                '<p class="composer-review-section-row">This is an <strong>instrumental</strong> '
                "composition — lyrics are not part of this song.</p>",
                unsafe_allow_html=True,
            )
        else:
            lyric_rows = lyrics_overview_rows(doc)
            if not any(r["has_lyrics"] for r in lyric_rows):
                st.caption("No lyrics yet — jump to the Lyrics phase to write section by section.")
            for row in lyric_rows:
                with st.expander(row["variant"], expanded=False):
                    if row["has_lyrics"]:
                        st.text(row["raw_text"] or "")
                    else:
                        st.caption("No lyrics for this section yet.")

        st.markdown("---")
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
            if not chords_for_playback(doc, scope="song"):
                st.warning("Add chords to at least one section before playing.")
            else:
                sig = preview_signature(doc, scope="song", loops=loops)
                wav = generate_preview_wav(doc, scope="song", loops=loops)
                if wav:
                    session_state[COMPOSER_PREVIEW_WAV_KEY] = wav
                    session_state[COMPOSER_PREVIEW_SIG_KEY] = sig
                else:
                    st.warning("Could not generate playback.")
        wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
        if wav:
            st.audio(wav, format="audio/wav")

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
    st.caption("Work on this section")
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


def _render_active_preview(session_state: dict) -> None:
    wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
    if not wav:
        return
    c1, c2 = st.columns([4, 1])
    with c1:
        st.audio(wav, format="audio/wav")
    with c2:
        if st.button("Stop", key="composer_preview_stop", use_container_width=True):
            invalidate_composer_preview(session_state)
            st.rerun()


def _play_chord_idea(
    session_state: dict,
    doc: dict[str, Any],
    section_id: str,
    chord_syms: list[str],
    *,
    loops: int = 2,
) -> None:
    sig = preview_signature(
        doc,
        section_id=section_id,
        loops=loops,
        chord_override=chord_syms,
        include_melody=False,
    )
    wav = generate_preview_wav(
        doc,
        section_id=section_id,
        loops=loops,
        chord_override=chord_syms,
        include_melody=False,
    )
    set_composer_preview(session_state, wav, sig)

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

    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]

    # Prefill widget defaults once (before widgets) from light heuristics — user can change freely.
    if "composer_welcome_key" not in session_state:
        hints0 = suggest_musical_defaults(genre="Pop", song_idea="")
        session_state["composer_welcome_key"] = coerce_composition_key_choice(hints0.get("key_label") or "C major")
        session_state["composer_welcome_bpm"] = coerce_composition_bpm(hints0.get("bpm"))
        session_state["composer_welcome_meter"] = coerce_composition_meter(hints0.get("meter"))
        session_state["composer_welcome_meter_custom"] = ""

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
            hints = suggest_musical_defaults(genre=str(genre or "Pop"), song_idea=str(song_idea or ""))
            session_state["composer_welcome_key"] = coerce_composition_key_choice(
                hints.get("key_label") or hints.get("key") or "C major"
            )
            session_state["composer_welcome_bpm"] = coerce_composition_bpm(hints.get("bpm"))
            suggested_meter = coerce_composition_meter(hints.get("meter"))
            if suggested_meter in COMPOSITION_METERS:
                session_state["composer_welcome_meter"] = suggested_meter
            else:
                session_state["composer_welcome_meter"] = COMPOSITION_METER_CUSTOM
                session_state["composer_welcome_meter_custom"] = suggested_meter
            if not str(session_state.get("composer_welcome_mood") or "").strip():
                session_state["composer_welcome_mood"] = str(hints.get("mood") or "")
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


def _sync_vision_fields_from_doc(doc: dict[str, Any]) -> None:
    meta = doc.setdefault("metadata", {})
    g = doc.setdefault("global", {})
    wf = ensure_workflow(doc)
    origin_payload = (doc.get("origin") or {}).get("seed_payload") or {}
    key_labels = composition_key_choice_labels()
    meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]

    if "composer_vision_genre" not in st.session_state:
        genre = str(meta.get("style") or "Pop")
        st.session_state["composer_vision_genre"] = genre if genre in COMPOSITION_GENRES else "Other"
    if "composer_vision_idea" not in st.session_state:
        st.session_state["composer_vision_idea"] = str(meta.get("description") or "")
    if "composer_vision_title" not in st.session_state:
        st.session_state["composer_vision_title"] = str(doc.get("title") or "")
    if "composer_vision_mood" not in st.session_state:
        st.session_state["composer_vision_mood"] = str(meta.get("mood") or "")
    if "composer_vision_energy" not in st.session_state:
        energy = str(meta.get("energy") or origin_payload.get("energy") or COMPOSITION_ENERGY_LEVELS[1])
        st.session_state["composer_vision_energy"] = energy if energy in COMPOSITION_ENERGY_LEVELS else COMPOSITION_ENERGY_LEVELS[1]
    if "composer_vision_refs" not in st.session_state:
        st.session_state["composer_vision_refs"] = str(meta.get("references") or "")
    if "composer_vision_instrumental" not in st.session_state:
        st.session_state["composer_vision_instrumental"] = bool(wf.get("skip_lyrics"))
    if "composer_vision_key" not in st.session_state:
        stored_label = str(g.get("original_key_label") or "").strip()
        token = str(g.get("original_key_center") or "C")
        st.session_state["composer_vision_key"] = coerce_composition_key_choice(
            stored_label or composition_key_label_from_token(token)
        )
    if "composer_vision_bpm" not in st.session_state:
        st.session_state["composer_vision_bpm"] = coerce_composition_bpm(g.get("bpm"))
    if "composer_vision_meter" not in st.session_state:
        meter = coerce_composition_meter(str(g.get("time_signature") or "4/4"))
        if meter in COMPOSITION_METERS:
            st.session_state["composer_vision_meter"] = meter
            st.session_state["composer_vision_meter_custom"] = ""
        else:
            st.session_state["composer_vision_meter"] = COMPOSITION_METER_CUSTOM
            st.session_state["composer_vision_meter_custom"] = meter
    elif "composer_vision_meter_custom" not in st.session_state:
        st.session_state["composer_vision_meter_custom"] = ""
    # Ensure selectbox values remain valid after list changes.
    if st.session_state.get("composer_vision_key") not in key_labels:
        st.session_state["composer_vision_key"] = coerce_composition_key_choice(
            st.session_state.get("composer_vision_key")
        )
    if st.session_state.get("composer_vision_meter") not in meter_options:
        st.session_state["composer_vision_meter"] = coerce_composition_meter(
            str(st.session_state.get("composer_vision_meter") or "4/4")
        )
        if st.session_state["composer_vision_meter"] not in COMPOSITION_METERS:
            custom = st.session_state["composer_vision_meter"]
            st.session_state["composer_vision_meter"] = COMPOSITION_METER_CUSTOM
            st.session_state["composer_vision_meter_custom"] = custom


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
    _sync_vision_fields_from_doc(doc)
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
            genre = str(st.session_state.get("composer_vision_genre") or "Pop")
            idea = str(st.session_state.get("composer_vision_idea") or "")
            hints = suggest_musical_defaults(genre=genre, song_idea=idea)
            st.session_state["composer_vision_mood"] = hints["mood"]
            st.session_state["composer_vision_energy"] = hints["energy"]
            st.rerun()

        idea = str(st.session_state.get("composer_vision_idea") or "").strip()
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
    center, side = st.columns([2.3, 1])

    with center:
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Song Structure</h3>
  <p>Arrange your song like blocks on a timeline — order, repeats, and section types.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="composer-structure-hint">'
            "<strong>Your blueprint:</strong> left → right is the order listeners hear. "
            "Sections with 🔗 share the same chord progression (Verse 2 follows Verse 1 until you break the link). "
            "Tap a section below to select it, then move, duplicate, or remove.</p>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="composer-structure-scroll">{_structure_timeline_html(doc, selected_id)}</div>',
            unsafe_allow_html=True,
        )

        if sections:
            st.markdown("**Sections** — tap to select")
            strip_cols = st.columns(min(len(sections), 6))
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

            if len(sections) > 6:
                pick_idx = ids.index(selected_id) if selected_id in ids else 0
                picked = st.selectbox(
                    "More sections",
                    options=range(len(ids)),
                    index=pick_idx,
                    format_func=lambda i: labels[i],
                    key="composer_structure_pick_overflow",
                )
                if ids[picked] != selected_id:
                    session_state[COMPOSER_ACTIVE_SECTION_KEY] = ids[picked]
                    st.rerun()

            active = section_by_id(doc, selected_id) if selected_id else None
            if active:
                with st.container(border=True):
                    st.markdown(f"**Selected:** {active.get('label_variant') or active.get('label')}")
                    link = active.get("chord_link") or {}
                    if link.get("linked"):
                        st.caption(f"🔗 {chord_link_display(active, doc)}")
                    mv = st.columns(4)
                with mv[0]:
                    if st.button("← Move earlier", key="composer_struct_left", use_container_width=True):
                        if move_section(doc, selected_id, -1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[1]:
                    if st.button("Move later →", key="composer_struct_right", use_container_width=True):
                        if move_section(doc, selected_id, 1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[2]:
                    if st.button("Duplicate", key="composer_struct_dup", use_container_width=True):
                        clone = duplicate_section(doc, selected_id)
                        if clone:
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = clone["id"]
                            _save_doc(session_state, doc)
                            st.rerun()
                with mv[3]:
                    if st.button("Remove", key="composer_struct_remove", use_container_width=True, disabled=len(sections) <= 1):
                        if remove_section(doc, selected_id):
                            order = list((doc.get("form") or {}).get("section_order") or [])
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0] if order else ""
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
        st.markdown("**Add a section**")
        a1, a2 = st.columns([2, 1])
        with a1:
            new_label = st.selectbox("Section type", COMPOSER_SECTION_LABELS, key="composer_structure_add_label")
        with a2:
            insert_after = st.checkbox("Insert after selected", value=bool(selected_id and sections), key="composer_structure_insert_after")
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
            st.caption(
                "After this blueprint exists, jump freely between sections and Chords / Melody / Lyrics — "
                "you are not locked into finishing every Verse before touching the Chorus."
            )
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
        elif not sections:
            st.caption("Add at least one section before composing chords or melody.")

    with side:
        _render_coach_panel(doc, lead=_structure_coach_html(doc))
        _render_library_sidebar(session_state)


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
    motif = str(concept.get("motif_hint") or "")
    why = str(concept.get("why") or "")
    notes_line = str(concept.get("notes_line") or "")
    events = list(concept.get("events") or concept.get("notes_events") or [])

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(name)}</h4>
  <div class="composer-melody-notation">{html.escape(melody_notation_line(concept))}</div>
  <div class="composer-suggestion-chords">{html.escape(notes_line or motif)}</div>
  <p class="composer-suggestion-why">{html.escape(contour)}<br>{html.escape(why)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns(2)
    with p1:
        if st.button("▶ Preview with chords", key=f"{prefix}_preview_{cid}", use_container_width=True):
            sig = preview_signature(
                doc,
                section_id=section_id,
                include_melody=True,
                melody_override=events or None,
            )
            wav = generate_preview_wav(
                doc,
                section_id=section_id,
                include_melody=True,
                melody_override=events or None,
            )
            if wav:
                set_composer_preview(session_state, wav, sig)
                st.rerun()
            elif section_has_resolved_chords(doc, section_id):
                st.warning("Could not generate preview.")
            else:
                st.info("Add chords to this section first — then hear melody ideas in context.")
    with p2:
        if st.button("Use this melody", key=f"{prefix}_use_{cid}", type="primary", use_container_width=True):
            if events:
                apply_melody_events(doc, section_id, events, concept=concept, replace=True)
            else:
                apply_melody_concept(doc, section_id, concept)
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
    variant = str(section.get("label_variant") or section.get("label") or "Section")

    center, side = st.columns([2.3, 1])
    with center:
        done, total = melodized_section_count(doc)
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Melody</h3>
  <p>What musical idea will people remember? Discover your song's voice before worrying about notation.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="composer-harmony-progress">Melody progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_melody_section_strip(session_state, doc)
        _render_section_lane_switcher(session_state, doc, active_lane="melody")
        st.markdown(f"### {variant}")

        edit_id, edit_section = harmony_edit_target(doc, active_id)
        has_harmony = section_has_resolved_chords(doc, active_id)

        if not has_harmony:
            st.markdown(
                '<div class="composer-chords-first-banner">'
                "<strong>Tip:</strong> Most songwriters shape the chord progression first, then write the melody on top. "
                "You can stay here if inspiration struck — or add harmony in the <strong>Chords</strong> phase for this section.</div>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Go to Chords for this section", key=f"composer_melody_to_chords_{active_id}"):
                    set_workflow_phase(doc, "chords")
                    _save_doc(session_state, doc)
                    st.rerun()
        else:
            g = doc.setdefault("global", {})
            meter = str(g.get("time_signature") or "4/4")
            chart = cpl_progression_bar_chart_html((edit_section or section).get("chords") or [], time_signature=meter)
            if chart:
                st.caption("Harmony for this section")
                st.markdown(chart, unsafe_allow_html=True)
            _render_section_transport(
                session_state,
                doc,
                edit_id or active_id,
                preview_key=f"composer_melody_hear_structure_{active_id}",
                button_label="▶ Play section (chords + melody)"
                if section_melody_events(section)
                else "▶ Play chords",
                loops_key=f"composer_melody_loops_{active_id}",
                include_melody=bool(section_melody_events(section)),
            )

        st.markdown("**What should listeners remember most?**")
        remember = st.text_input(
            "Memorable idea",
            value=str(intent.get("remember") or ""),
            key=f"composer_melody_remember_{active_id}",
            placeholder="e.g. The rising hook on the word 'home' in the chorus",
            label_visibility="collapsed",
        )

        feel_ids = [f[0] for f in MELODY_FEELINGS]
        current_feel = str(intent.get("feel") or default_melody_feel_for_section(section))
        if current_feel not in feel_ids:
            current_feel = default_melody_feel_for_section(section)

        st.markdown("**How should this melody feel?**")
        picked_feel = st.radio(
            "Melody feel",
            options=feel_ids,
            index=feel_ids.index(current_feel),
            format_func=lambda fid: next(l for i, l in MELODY_FEELINGS if i == fid),
            key=f"composer_melody_feel_{active_id}",
            label_visibility="collapsed",
        )

        style_ids = [s[0] for s in MELODY_STYLES]
        current_style = str(intent.get("style") or "simple")
        if current_style not in style_ids:
            current_style = "simple"
        st.markdown("**Simple & singable, or more expressive?**")
        picked_style = st.radio(
            "Melody style",
            options=style_ids,
            index=style_ids.index(current_style),
            format_func=lambda sid: next(l for i, l in MELODY_STYLES if i == sid),
            key=f"composer_melody_style_{active_id}",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown("**Hum or sing your idea**")
        hum = st.text_area(
            "Hum notes",
            value=str(intent.get("hum_notes") or ""),
            key=f"composer_melody_hum_{active_id}",
            height=70,
            placeholder="Describe what you're hearing — or record below when ready.",
        )
        if has_harmony:
            st.markdown(
                '<div class="composer-coming-soon">'
                "<strong>Hum → notation:</strong> browser recording is available. "
                "Automatic pitch/rhythm detection and staff notation are "
                "<em>Coming soon</em> — recordings are kept as a capture marker, "
                "not claimed as transcribed notes."
                "</div>",
                unsafe_allow_html=True,
            )
            try:
                audio = st.audio_input(
                    "Record a hum or melody idea",
                    key=f"composer_melody_record_{active_id}",
                )
                if audio is not None:
                    # Persist capture metadata only — do not invent note detection.
                    capture = intent.setdefault("hum_capture", {})
                    try:
                        raw = audio.getvalue() if hasattr(audio, "getvalue") else b""
                    except Exception:
                        raw = b""
                    capture["captured"] = True
                    capture["bytes_len"] = len(raw or b"")
                    capture["analysis_status"] = "coming_soon"
                    capture["note_detection"] = False
                    st.info(
                        "Recording captured for this section. "
                        "Note and rhythm detection is Coming soon — "
                        "describe what you sang above or pick a melody concept below."
                    )
            except Exception:
                st.caption("Audio recording will appear here in your browser when supported.")
        else:
            st.caption("Add chords for this section to loop harmony while you hum.")

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

        phrases = list(melody.get("phrases") or [])
        accepted_events = section_melody_events(section)
        if accepted_events:
            note_line = " ".join(str(e.get("pitch") or "") for e in accepted_events)
            st.markdown(f"**Accepted melody notes:** `{note_line}`")
        if phrases:
            st.markdown("**Current melodic ideas**")
            for phrase in phrases[:4]:
                if isinstance(phrase, dict):
                    st.markdown(f"- **{phrase.get('label') or 'Phrase'}:** {phrase.get('motif') or phrase.get('notes') or '…'}")

        st.markdown("**Shape your melody**")
        st.caption("Pick a refinement — we'll adjust your latest phrase or hum notes (no note-by-note editing required).")
        ref_cols = st.columns(min(4, len(MELODY_REFINEMENTS)))
        for i, (rid, label, _) in enumerate(MELODY_REFINEMENTS[:4]):
            with ref_cols[i % len(ref_cols)]:
                if st.button(label, key=f"composer_melody_ref_{active_id}_{rid}", use_container_width=True):
                    apply_melody_refinement_to_section(doc, active_id, rid)
                    _save_doc(session_state, doc)
                    st.rerun()
        ref_cols2 = st.columns(min(3, max(0, len(MELODY_REFINEMENTS) - 4)))
        for j, (rid, label, _) in enumerate(MELODY_REFINEMENTS[4:]):
            with ref_cols2[j % len(ref_cols2)]:
                if st.button(label, key=f"composer_melody_ref2_{active_id}_{rid}", use_container_width=True):
                    apply_melody_refinement_to_section(doc, active_id, rid)
                    _save_doc(session_state, doc)
                    st.rerun()

        st.markdown("**How would you like to explore?**")
        path = st.radio(
            "Melody workflow",
            ["explore", "compare", "write"],
            horizontal=True,
            key=f"composer_melody_path_{active_id}",
            format_func=lambda x: {
                "explore": "Explore concepts",
                "compare": "Compare approaches",
                "write": "Write / refine directly",
            }[x],
        )

        concepts = suggest_melody_concepts(doc, section, picked_feel, picked_style, limit=3)

        if path == "explore":
            st.caption("Each concept describes contour and intent — hear the harmony, then adopt what fits.")
            for i, concept in enumerate(concepts):
                _render_melody_concept_card(
                    session_state, doc, active_id, concept, prefix=f"composer_melody_explore_{active_id}_{i}"
                )
        elif path == "compare":
            queue_key = f"composer_melody_compare_{active_id}"
            cids = [str(c.get("id") or "") for c in concepts]
            labels_map = {cid: str(c.get("name") or cid) for cid, c in zip(cids, concepts)}
            queue = st.multiselect(
                "Select up to 3 concepts to compare",
                options=cids,
                default=[q for q in list(session_state.get(queue_key) or []) if q in cids][:3],
                format_func=lambda x: labels_map.get(x, x),
                key=f"composer_melody_compare_select_{active_id}",
            )
            session_state[queue_key] = queue[:3]
            if queue:
                by_id = {str(c.get("id")): c for c in concepts}
                for i, qid in enumerate(queue[:3]):
                    concept = by_id.get(qid)
                    if concept:
                        _render_melody_concept_card(
                            session_state,
                            doc,
                            active_id,
                            concept,
                            prefix=f"composer_melody_cmp_{active_id}_{i}",
                        )
            else:
                st.info("Pick concepts above to compare different melodic approaches.")
        else:
            st.caption("Direct control when you already hear the line clearly.")
            with st.expander("Advanced phrase editor", expanded=not bool(phrases)):
                _render_melody_phrases_editor(session_state, doc, active_id)

        wf = ensure_workflow(doc)
        next_label = "Review" if wf.get("skip_lyrics") else "Lyrics"
        if done > 0 and st.button(f"Continue to {next_label} →", type="primary", key="composer_melody_continue"):
            advance_workflow(doc, from_phase="melody")
            _save_doc(session_state, doc)
            st.rerun()
        elif done == 0:
            st.caption("Capture at least one melodic idea (concept, hum notes, or phrase) before continuing.")

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
        st.caption("Full melody preview with AI/humming arrives in a later sprint — for now, hear your harmony while you shape the line.")
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
            clone = duplicate_section(doc, active_id)
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

    rows = [list(_COMPOSER_QUICK_CHORDS[i : i + 5]) for i in range(0, len(_COMPOSER_QUICK_CHORDS), 5)]
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
        sig = preview_signature(
            doc,
            scope="section",
            section_id=section_id,
            loops=loops,
            chord_override=chord_override,
            include_melody=include_melody,
            melody_override=melody_override,
        )
        wav = generate_preview_wav(
            doc,
            scope="section",
            section_id=section_id,
            loops=loops,
            chord_override=chord_override,
            include_melody=include_melody,
            melody_override=melody_override,
        )
        if wav:
            set_composer_preview(session_state, wav, sig)
            st.rerun()
        else:
            st.warning("Add chords to this section first — melody sits on your harmony.")

    _render_active_preview(session_state)


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

        if section_has_chords(section):
            g = doc.setdefault("global", {})
            meter = str(g.get("time_signature") or "4/4")
            chart = cpl_progression_bar_chart_html(section.get("chords") or [], time_signature=meter)
            if chart:
                st.caption("Harmony for this section")
                st.markdown(chart, unsafe_allow_html=True)

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

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{html.escape(name)}</h4>
  <div class="composer-suggestion-chords">{html.escape(line)}</div>
  <p class="composer-suggestion-why">{html.escape(why)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("▶ Preview", key=f"{prefix}_preview_{sid}", use_container_width=True):
            _play_chord_idea(session_state, doc, section_id, chord_syms)
            st.rerun()
    with p2:
        if st.button("Use this", key=f"{prefix}_use_{sid}", type="primary", use_container_width=True):
            apply_section_chords(doc, section_id, entries)
            invalidate_composer_preview(session_state)
            _save_doc(session_state, doc)
            st.rerun()
    with p3:
        if st.button("+ Compare", key=f"{prefix}_compare_{sid}", use_container_width=True):
            queue_key = f"composer_compare_{section_id}"
            queue = list(session_state.get(queue_key) or [])
            if sid not in queue:
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
            _play_chord_idea(session_state, doc, section_id, chord_syms)
            st.rerun()
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

    center, side = st.columns([2.3, 1])
    with center:
        done, total = harmonized_section_count(doc)
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Chords</h3>
  <p>What harmony best supports each section? Start with the feeling — then explore, compare, or write your own.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="composer-harmony-progress">Harmony progress: <strong>{done}/{total}</strong> sections</p>',
            unsafe_allow_html=True,
        )
        _render_chords_section_strip(session_state, doc)
        _render_section_lane_switcher(session_state, doc, active_lane="chords")

        variant = str(section.get("label_variant") or section.get("label") or "Section")
        st.markdown(f"### {variant}")

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
            feeling_ids = [f[0] for f in SECTION_HARMONY_FEELINGS]
            current_feeling = str(harmony.get("feeling") or default_feeling_for_section(section))
            if current_feeling not in feeling_ids:
                current_feeling = default_feeling_for_section(section)
            st.markdown(f"**What feeling should {variant} create?**")
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

            entries = edit_section.get("chords") or [] if edit_section else []
            if entries:
                g = doc.setdefault("global", {})
                meter = str(g.get("time_signature") or "4/4")
                chart = cpl_progression_bar_chart_html(entries, time_signature=meter)
                if chart:
                    st.markdown(chart, unsafe_allow_html=True)
                _render_section_transport(
                    session_state,
                    doc,
                    edit_id or active_id,
                    button_label="▶ Play chords",
                    preview_key=f"composer_chords_play_{active_id}",
                    loops_key=f"composer_chords_loops_{active_id}",
                    include_melody=False,
                )
                _render_chord_refinement_panel(session_state, doc, edit_id or active_id, edit_section or section)
                st.info("Next creative step: build a melody over these chords — or keep refining harmony.")
                if st.button("Build a melody over these chords →", key=f"composer_chords_to_melody_{active_id}"):
                    session_state[COMPOSER_FOCUS_LANE_KEY] = "melody"
                    set_workflow_phase(doc, "melody")
                    _save_doc(session_state, doc)
                    st.rerun()

            st.markdown("**How would you like to work?**")
            path = st.radio(
                "Chord workflow",
                ["explore", "compare", "write"],
                horizontal=True,
                key=f"composer_chords_path_{active_id}",
                format_func=lambda x: {
                    "explore": "Explore suggestions",
                    "compare": "Compare ideas",
                    "write": "Write my own",
                }[x],
            )

            suggestions = suggest_progressions(doc, section, picked, limit=3)

            if path == "explore":
                st.caption("Suggestions use your Composition key, section role, and song mood — preview before you commit.")
                for i, sug in enumerate(suggestions):
                    _render_suggestion_card(session_state, doc, edit_id or active_id, sug, prefix=f"composer_explore_{active_id}_{i}")

            elif path == "compare":
                queue_key = f"composer_compare_{active_id}"
                ids = [str(s.get("id") or "") for s in suggestions]
                labels_map = {sid: f"{s.get('name')} — {s.get('line')}" for sid, s in zip(ids, suggestions)}
                queue = st.multiselect(
                    "Select up to 3 progressions to compare",
                    options=ids,
                    default=[q for q in list(session_state.get(queue_key) or []) if q in ids][:3],
                    format_func=lambda x: labels_map.get(x, x),
                    key=f"composer_compare_select_{active_id}",
                )
                session_state[queue_key] = queue[:3]

                if queue:
                    st.markdown("**Compare queue**")
                    by_id = {str(s.get("id")): s for s in suggestions}
                    for i, qid in enumerate(queue[:3]):
                        sug = by_id.get(qid)
                        if sug:
                            _render_suggestion_card(
                                session_state,
                                doc,
                                edit_id or active_id,
                                sug,
                                prefix=f"composer_cmp_{active_id}_{i}",
                            )
                else:
                    st.info("Pick ideas above to compare them side by side.")

            else:
                st.caption("Direct control when you know exactly what you want.")
                with st.expander("Advanced chord grid", expanded=not bool(entries)):
                    if edit_section:
                        _render_chords_lane(session_state, doc, edit_section, owner_id=edit_id or active_id)

        if done > 0 and st.button("Continue to Melody →", type="primary", key="composer_chords_continue"):
            advance_workflow(doc, from_phase="chords")
            _save_doc(session_state, doc)
            st.rerun()
        elif done == 0:
            st.caption("Harmonize at least one section before continuing.")

    with side:
        feeling = str((edit_section or section).get("harmony", {}).get("feeling") or default_feeling_for_section(section))
        _render_coach_panel(doc, lead=coach_line_for_section(doc, section, feeling=feeling))
        with st.expander("Song key · BPM · meter"):
            g = doc.setdefault("global", {})
            key_labels = composition_key_choice_labels()
            current_label = coerce_composition_key_choice(
                str(g.get("original_key_label") or "")
                or composition_key_label_from_token(str(g.get("original_key_center") or "C"))
            )
            if f"composer_chords_key_{doc.get('id')}" not in session_state:
                session_state[f"composer_chords_key_{doc.get('id')}"] = current_label
            picked = st.selectbox(
                "Key",
                key_labels,
                key=f"composer_chords_key_{doc.get('id')}",
            )
            bpm_val = st.number_input(
                "Tempo (BPM)",
                min_value=40,
                max_value=240,
                value=coerce_composition_bpm(g.get("bpm")),
                step=1,
                key=f"composer_chords_bpm_{doc.get('id')}",
            )
            meter_options = list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM]
            stored_meter = coerce_composition_meter(str(g.get("time_signature") or "4/4"))
            meter_key = f"composer_chords_meter_{doc.get('id')}"
            custom_key = f"composer_chords_meter_custom_{doc.get('id')}"
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
            if st.button("Apply song settings", key="composer_chords_apply_globals"):
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
        _render_library_sidebar(session_state)


def render_composition_studio_page() -> None:
    session_state = st.session_state
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
    _render_journey_rail(session_state, doc)

    phase = get_workflow_phase(doc)
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
