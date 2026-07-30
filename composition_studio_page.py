"""Composition Studio — guided six-phase songwriting workspace (CS-B0+)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from composition_document import (
    COMPOSITION_ENERGY_LEVELS,
    COMPOSITION_GENRES,
    COMPOSITION_PHASE_LABELS,
    COMPOSITION_PHASES,
    COMPOSITION_PRACTICE_KEYS,
    COMPOSER_SECTION_LABELS,
    add_section,
    advance_workflow,
    bootstrap_from_vision,
    document_summary_line,
    duplicate_section,
    ensure_workflow,
    get_workflow_phase,
    move_section,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    remove_section,
    set_workflow_phase,
    suggest_musical_defaults,
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


def _render_phase_placeholder(session_state: dict, doc: dict[str, Any], phase: str) -> None:
    labels = {
        "structure": (
            "Song Structure",
            "Design your form — Intro, Verse, Chorus, Bridge — before writing chords.",
            "CS-B1",
        ),
        "melody": (
            "Melody",
            "Sketch phrases that ride your harmony — framework only for now.",
            "CS-B3",
        ),
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


def _render_chords_lane(session_state: dict, doc: dict[str, Any], section: dict[str, Any]) -> None:
    sid = str(section.get("id") or "")
    entries = section.setdefault("chords", [])
    g = doc.setdefault("global", {})
    meter = str(g.get("time_signature") or "4/4")

    chart = cpl_progression_bar_chart_html(entries, time_signature=meter)
    if chart:
        st.markdown(chart, unsafe_allow_html=True)
    else:
        st.caption("Tap chords below — each click adds to this section. Use Play to hear it.")

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
                        _save_doc(session_state, doc)
                        st.rerun()

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Same as previous (%)", key=f"composer_repeat_{sid}", use_container_width=True):
            entries.append({"repeat": True, "bars": 1})
            _save_doc(session_state, doc)
            st.rerun()
    with c2:
        if st.button("Undo last chord", key=f"composer_undo_chord_{sid}", use_container_width=True):
            if entries:
                entries.pop()
                _save_doc(session_state, doc)
                st.rerun()
    with c3:
        if st.button("Clear section", key=f"composer_clear_{sid}", use_container_width=True):
            section["chords"] = []
            _save_doc(session_state, doc)
            st.rerun()

    paste = st.text_input("Paste progression", key=f"composer_paste_{sid}", placeholder="| G | Am | C | D |")
    if st.button("Apply paste", key=f"composer_paste_apply_{sid}") and paste:
        section["chords"] = parse_chord_paste(paste)
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
    st.markdown(
        """
<div class="composer-phase-card">
  <h3>Chord Progressions</h3>
  <p>Harmonize each section of your song. A guided coach-first workflow arrives in CS-B2 — for now, build progressions here.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(document_summary_line(doc))
    _render_snapshot_strip(session_state, doc)
    _render_transport(session_state, doc)

    left, center, right = st.columns([1.05, 2.2, 1.1])
    with left:
        _render_structure_column(session_state, doc)
    with center:
        lane = st.radio(
            "Focus",
            ["chords", "rhythm", "structure"],
            horizontal=True,
            key=COMPOSER_FOCUS_LANE_KEY,
            format_func=lambda x: {"chords": "Chords", "rhythm": "Rhythm / feel", "structure": "Overview"}[x],
        )
        sections = ordered_sections(doc)
        active_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
        section = next((s for s in sections if str(s.get("id")) == active_id), sections[0] if sections else None)
        if section and lane == "chords":
            _render_chords_lane(session_state, doc, section)
        elif lane == "rhythm":
            _render_rhythm_lane(session_state, doc)
        else:
            st.markdown("**Song form**")
            for sec in sections:
                st.markdown(
                    f"**{sec.get('label_variant') or sec.get('label')}** — "
                    f"{format_entries_bar_line(sec.get('chords') or [])}"
                )
    with right:
        section_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
        snap = build_composition_snapshot(
            doc,
            active_section_id=section_id,
            focus_lane=str(session_state.get(COMPOSER_FOCUS_LANE_KEY) or "chords"),
        )
        has_chords = snap.get("commitment", {}).get("has_chords")
        _render_coach_panel(
            doc,
            lead=(
                "Add a chord or two, then hit <strong>Play</strong> to hear how this section feels."
                if not has_chords
                else "Nice — keep building section by section. Repeated sections can share progressions (CS-B2)."
            ),
        )
        _render_library_sidebar(session_state)
        if st.button("Continue to Melody →", type="primary", key="composer_chords_continue"):
            advance_workflow(doc, from_phase="chords")
            _save_doc(session_state, doc)
            st.rerun()


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
    elif phase == "chords":
        _render_phase_chords(session_state, doc)
    elif phase in {"structure", "melody", "lyrics", "review"}:
        _render_phase_placeholder(session_state, doc, phase)
    else:
        _render_phase_vision(session_state, doc)
