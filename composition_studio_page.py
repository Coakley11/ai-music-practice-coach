"""Composition Studio — guided six-phase songwriting workspace (CS-B0+)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from composition_chord_suggestions import (
    SECTION_HARMONY_FEELINGS,
    coach_line_for_section,
    default_feeling_for_section,
    suggest_progressions,
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
)
from composition_document import (
    COMPOSITION_ENERGY_LEVELS,
    COMPOSITION_GENRES,
    COMPOSITION_PHASE_LABELS,
    COMPOSITION_PHASES,
    COMPOSITION_PRACTICE_KEYS,
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
    remove_section,
    remove_melody_phrase,
    section_by_id,
    section_css_type,
    section_has_chords,
    section_has_lyrics,
    section_has_melody,
    set_workflow_phase,
    suggest_musical_defaults,
    sync_linked_chord_sections,
    touch_composition,
)
from composition_preview import generate_preview_wav, invalidate_composer_preview, preview_signature
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
    CPL_TIME_SIGNATURES,
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


def _vision_coach_html(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    g = doc.get("global") or {}
    genre = str(meta.get("style") or "your genre")
    mood = str(meta.get("mood") or "the feeling you're chasing")
    idea = str(meta.get("description") or "").strip()
    refs = str(meta.get("references") or "").strip()
    ref_bit = f" I hear shades of <em>{refs}</em> in this." if refs else ""
    idea_bit = f' "{idea[:160]}"' if idea else ""
    return (
        f"So we're writing a <strong>{genre}</strong> song with a <strong>{mood.lower()}</strong> feel"
        f"{ref_bit}.{idea_bit}<br><br>"
        f"I've suggested <strong>{g.get('original_key_center', 'C')}</strong> at "
        f"<strong>{g.get('bpm', 96)} BPM</strong> in <strong>{g.get('time_signature', '4/4')}</strong> — "
        f"tweak anytime. Next we'll shape the song's structure before touching chords."
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
    st.markdown('<p class="composer-journey-title">Your songwriting journey</p>', unsafe_allow_html=True)
    cols = st.columns(len(COMPOSITION_PHASES))
    for col, phase in zip(cols, COMPOSITION_PHASES):
        label = COMPOSITION_PHASE_LABELS[phase]
        if phase == "lyrics" and wf.get("skip_lyrics"):
            label = "Lyrics · skipped"
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


def _render_welcome_entry(session_state: dict) -> None:
    st.markdown(
        """
<div class="composer-hero">
  <h2>What kind of song do you want to write?</h2>
  <p>Start with the spark — genre and a sentence or two about your idea.
  We'll suggest tempo, key, and feel; you can adjust everything as you go.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    center, side = st.columns([2.3, 1])
    with center:
        genre = st.selectbox("Genre", COMPOSITION_GENRES, key="composer_welcome_genre")
        song_idea = st.text_area(
            "Describe your song idea",
            key="composer_welcome_idea",
            height=110,
            placeholder='e.g. "A hopeful pop song about finding your way home after a long trip."',
        )
        preview = suggest_musical_defaults(genre=genre, song_idea=song_idea or "")
        st.markdown(
            f'<div class="composer-suggest-strip">Suggested starting point: '
            f"{preview['key']} · {preview['bpm']} BPM · {preview['meter']} · "
            f"{preview['mood']}</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Optional details"):
            st.text_input("Working title", key="composer_welcome_title")
            st.text_input("Mood / emotion", key="composer_welcome_mood", placeholder=preview["mood"])
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
                doc = bootstrap_from_vision(
                    genre=str(session_state.get("composer_welcome_genre") or "Pop"),
                    song_idea=idea,
                    title=str(session_state.get("composer_welcome_title") or ""),
                    mood=str(session_state.get("composer_welcome_mood") or ""),
                    energy=str(session_state.get("composer_welcome_energy") or ""),
                    references=str(session_state.get("composer_welcome_refs") or ""),
                    instrumental=bool(session_state.get("composer_welcome_instrumental")),
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
                "Think of this as the first five minutes with a songwriter in the room. "
                "No chord grids yet — just the story and the feeling."
            ),
        )


def _sync_vision_fields_from_doc(doc: dict[str, Any]) -> None:
    meta = doc.setdefault("metadata", {})
    g = doc.setdefault("global", {})
    wf = ensure_workflow(doc)
    origin_payload = (doc.get("origin") or {}).get("seed_payload") or {}

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
        key = str(g.get("original_key_center") or "C")
        st.session_state["composer_vision_key"] = key if key in COMPOSITION_PRACTICE_KEYS else "C"
    if "composer_vision_bpm" not in st.session_state:
        st.session_state["composer_vision_bpm"] = int(g.get("bpm") or 96)
    if "composer_vision_meter" not in st.session_state:
        meter = str(g.get("time_signature") or "4/4")
        st.session_state["composer_vision_meter"] = meter if meter in CPL_TIME_SIGNATURES else "4/4"


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
    g["original_key_center"] = str(st.session_state.get("composer_vision_key") or "C")
    g["bpm"] = int(st.session_state.get("composer_vision_bpm") or 96)
    g["time_signature"] = str(st.session_state.get("composer_vision_meter") or "4/4")
    g["progression_style"] = genre if genre in CPL_PROGRESSION_STYLES else g.get("progression_style") or "Pop"
    wf["skip_lyrics"] = bool(st.session_state.get("composer_vision_instrumental"))
    origin["seed_summary"] = idea[:500]
    origin.setdefault("seed_payload", {})["genre"] = genre
    origin["seed_payload"]["energy"] = meta["energy"]
    origin["seed_payload"]["references"] = meta["references"]


def _render_phase_vision(session_state: dict, doc: dict[str, Any]) -> None:
    _sync_vision_fields_from_doc(doc)
    center, side = st.columns([2.3, 1])
    with center:
        st.markdown(
            """
<div class="composer-phase-card">
  <h3>Song Vision</h3>
  <p>Capture the heart of your song before structure or chords. Only genre and your idea are required.</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.selectbox("Genre", COMPOSITION_GENRES, key="composer_vision_genre")
        st.text_area(
            "What kind of song do you want to write?",
            key="composer_vision_idea",
            height=100,
            placeholder="One or two sentences about theme, story, or feeling.",
        )
        st.text_input("Working title", key="composer_vision_title")
        with st.expander("Mood, energy & inspiration"):
            st.text_input("Mood / emotion", key="composer_vision_mood")
            st.selectbox("Energy level", COMPOSITION_ENERGY_LEVELS, key="composer_vision_energy")
            st.text_input("Artists or songs that inspire this", key="composer_vision_refs")
            st.checkbox("Instrumental piece (skip lyrics phase)", key="composer_vision_instrumental")
        with st.expander("Practice key, tempo & time signature"):
            k1, k2, k3 = st.columns(3)
            with k1:
                st.selectbox("Practice key", COMPOSITION_PRACTICE_KEYS, key="composer_vision_key")
            with k2:
                st.number_input("Tempo (BPM)", min_value=40, max_value=220, step=1, key="composer_vision_bpm")
            with k3:
                st.selectbox("Time signature", CPL_TIME_SIGNATURES, key="composer_vision_meter")

        if st.button("Refresh suggestions from idea", key="composer_vision_resuggest"):
            genre = str(st.session_state.get("composer_vision_genre") or "Pop")
            idea = str(st.session_state.get("composer_vision_idea") or "")
            hints = suggest_musical_defaults(genre=genre, song_idea=idea)
            st.session_state["composer_vision_mood"] = hints["mood"]
            st.session_state["composer_vision_energy"] = hints["energy"]
            st.session_state["composer_vision_key"] = hints["key"]
            st.session_state["composer_vision_bpm"] = hints["bpm"]
            st.session_state["composer_vision_meter"] = hints["meter"]
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
  <p>Design your song form before writing chords. Drag the story forward — intro, verses, chorus, bridge, outro.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="composer-structure-scroll">{_structure_timeline_html(doc, selected_id)}</div>',
            unsafe_allow_html=True,
        )

        if sections:
            labels = [str(s.get("label_variant") or s.get("label") or "Section") for s in sections]
            ids = [str(s.get("id") or "") for s in sections]
            pick_idx = ids.index(selected_id) if selected_id in ids else 0
            picked = st.selectbox(
                "Selected section",
                options=range(len(ids)),
                index=pick_idx,
                format_func=lambda i: labels[i],
                key="composer_structure_pick",
            )
            if ids[picked] != selected_id:
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = ids[picked]
                st.rerun()

            active = section_by_id(doc, selected_id) if selected_id else None
            if active:
                st.markdown(f"**Editing:** {active.get('label_variant') or active.get('label')}")
                link = active.get("chord_link") or {}
                if link.get("linked"):
                    st.caption(f"🔗 {chord_link_display(active, doc)} — changes to the source section apply here too.")
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    if st.button("← Earlier", key="composer_struct_left", use_container_width=True):
                        if move_section(doc, selected_id, -1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with c2:
                    if st.button("Later →", key="composer_struct_right", use_container_width=True):
                        if move_section(doc, selected_id, 1):
                            _save_doc(session_state, doc)
                            st.rerun()
                with c3:
                    if st.button("Duplicate", key="composer_struct_dup", use_container_width=True):
                        clone = duplicate_section(doc, selected_id)
                        if clone:
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = clone["id"]
                            _save_doc(session_state, doc)
                            st.rerun()
                with c4:
                    if link.get("linked") and st.button("Break link", key="composer_struct_unlink", use_container_width=True):
                        break_chord_link(doc, selected_id)
                        _save_doc(session_state, doc)
                        st.rerun()
                with c5:
                    if st.button("Remove", key="composer_struct_remove", use_container_width=True, disabled=len(sections) <= 1):
                        if remove_section(doc, selected_id):
                            order = list((doc.get("form") or {}).get("section_order") or [])
                            session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0] if order else ""
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
        if st.button("+ Add section", key="composer_structure_add_btn", use_container_width=True):
            after = selected_id if insert_after and selected_id else None
            sec = add_section(doc, new_label, after_id=after)
            session_state[COMPOSER_ACTIVE_SECTION_KEY] = sec["id"]
            _save_doc(session_state, doc)
            st.rerun()

        if sections and st.button("Continue to Chords →", type="primary", key="composer_structure_continue"):
            advance_workflow(doc, from_phase="structure")
            _save_doc(session_state, doc)
            st.rerun()
        elif not sections:
            st.caption("Add at least one section before continuing to chords.")

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

    st.markdown(
        f"""
<div class="composer-suggestion-card">
  <h4>{name}</h4>
  <div class="composer-suggestion-chords">{motif}</div>
  <p class="composer-suggestion-why">{contour}<br>{why}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns(2)
    with p1:
        if st.button("▶ Hear harmony context", key=f"{prefix}_preview_{cid}", use_container_width=True):
            wav = generate_preview_wav(doc, section_id=section_id)
            if wav:
                session_state[COMPOSER_PREVIEW_WAV_KEY] = wav
            elif section_has_chords(section_by_id(doc, section_id) or {}):
                st.warning("Could not generate preview.")
            else:
                st.info("Add chords to this section first — melody sits on your harmony.")
    with p2:
        if st.button("Use this concept", key=f"{prefix}_use_{cid}", type="primary", use_container_width=True):
            apply_melody_concept(doc, section_id, concept)
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
        st.markdown(f"### {variant}")

        if section_has_chords(section):
            g = doc.setdefault("global", {})
            meter = str(g.get("time_signature") or "4/4")
            chart = cpl_progression_bar_chart_html(section.get("chords") or [], time_signature=meter)
            if chart:
                st.caption("Harmony for this section")
                st.markdown(chart, unsafe_allow_html=True)

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

        st.markdown("**Hum or imagine it first**")
        hum = st.text_area(
            "Hum notes",
            value=str(intent.get("hum_notes") or ""),
            key=f"composer_melody_hum_{active_id}",
            height=70,
            placeholder="Describe what you're hearing in your head — no notation required. (Future: capture audio here.)",
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

        phrases = list(melody.get("phrases") or [])
        if phrases:
            st.markdown("**Current melodic ideas**")
            for phrase in phrases[:4]:
                if isinstance(phrase, dict):
                    st.markdown(f"- **{phrase.get('label') or 'Phrase'}:** {phrase.get('motif') or phrase.get('notes') or '…'}")
            _render_section_transport(session_state, doc, active_id, preview_key=f"composer_melody_play_{active_id}")

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
    c1, c2, c3 = st.columns(3)
    with c1:
        g["bpm"] = st.number_input("BPM", min_value=40, max_value=220, value=int(g.get("bpm") or 96), step=1)
    with c2:
        g["time_signature"] = st.selectbox(
            "Meter",
            CPL_TIME_SIGNATURES,
            index=CPL_TIME_SIGNATURES.index(g.get("time_signature") or "4/4")
            if g.get("time_signature") in CPL_TIME_SIGNATURES
            else 0,
        )
    with c3:
        g["progression_style"] = st.selectbox(
            "Style",
            CPL_PROGRESSION_STYLES,
            index=CPL_PROGRESSION_STYLES.index(g.get("progression_style") or "Pop")
            if g.get("progression_style") in CPL_PROGRESSION_STYLES
            else 0,
        )
    g["groove_style"] = st.selectbox(
        "Groove",
        ["Auto", "Ballad", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova"],
        index=0,
    )
    g["original_key_center"] = st.selectbox(
        "Written key",
        list(COMPOSITION_PRACTICE_KEYS),
        index=list(COMPOSITION_PRACTICE_KEYS).index(g.get("original_key_center") or "C")
        if g.get("original_key_center") in COMPOSITION_PRACTICE_KEYS
        else 0,
    )
    meta["mood"] = st.text_input("Mood / emotion (optional)", value=str(meta.get("mood") or ""))
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
) -> None:
    loops = int(session_state.get("composer_play_loops") or 2)
    t1, t2 = st.columns([2, 3])
    with t1:
        loops = st.slider("Loops", 1, 4, loops, key="composer_play_loops")
    with t2:
        play = st.button("▶ Preview section", type="primary", key=preview_key, use_container_width=True)

    if play:
        wav = generate_preview_wav(
            doc,
            scope="section",
            section_id=section_id,
            loops=loops,
            chord_override=chord_override,
        )
        if wav:
            session_state[COMPOSER_PREVIEW_WAV_KEY] = wav
        else:
            st.warning("No chords to preview yet.")

    wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
    if wav:
        st.audio(wav, format="audio/wav")


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
  <h4>{name}</h4>
  <div class="composer-suggestion-chords">{line}</div>
  <p class="composer-suggestion-why">{why}</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("▶ Preview", key=f"{prefix}_preview_{sid}", use_container_width=True):
            wav = generate_preview_wav(doc, section_id=section_id, chord_override=chord_syms)
            if wav:
                session_state[COMPOSER_PREVIEW_WAV_KEY] = wav
            else:
                st.warning("Could not preview this progression.")
    with p2:
        if st.button("Use this", key=f"{prefix}_use_{sid}", type="primary", use_container_width=True):
            apply_section_chords(doc, section_id, entries)
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
        )
        if wav:
            session_state[COMPOSER_PREVIEW_WAV_KEY] = wav
            session_state[COMPOSER_PREVIEW_SIG_KEY] = sig
        else:
            st.warning("Add at least one chord before playing.")

    wav = session_state.get(COMPOSER_PREVIEW_WAV_KEY)
    if wav:
        st.audio(wav, format="audio/wav")


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
                _render_section_transport(session_state, doc, edit_id or active_id)

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
                st.caption("Suggestions are transposed to your practice key — preview before you commit.")
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
        with st.expander("Song tempo & key"):
            g = doc.setdefault("global", {})
            g["original_key_center"] = st.selectbox(
                "Practice key",
                list(COMPOSITION_PRACTICE_KEYS),
                index=list(COMPOSITION_PRACTICE_KEYS).index(g.get("original_key_center") or "C")
                if g.get("original_key_center") in COMPOSITION_PRACTICE_KEYS
                else 0,
                key=f"composer_chords_key_{doc.get('id')}",
            )
            g["bpm"] = st.number_input(
                "Tempo (BPM)",
                min_value=40,
                max_value=220,
                value=int(g.get("bpm") or 96),
                step=1,
                key=f"composer_chords_bpm_{doc.get('id')}",
            )
            if st.button("Apply", key="composer_chords_apply_globals"):
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
        _render_phase_placeholder(session_state, doc, phase)
    else:
        _render_phase_vision(session_state, doc)
