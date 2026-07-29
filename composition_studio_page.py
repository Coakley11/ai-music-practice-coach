"""Composition Studio — Sprint A workspace (seed entry, form, chords, preview)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from composition_document import (
    COMPOSER_SECTION_LABELS,
    add_section,
    bootstrap_from_seed,
    document_summary_line,
    duplicate_section,
    move_section,
    ordered_sections,
    parse_chord_paste,
    remove_section,
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

_SEED_CHIPS: tuple[tuple[str, str], ...] = (
    ("style_intent", "Style / intent"),
    ("chords", "Chords"),
    ("lyrics", "Lyrics"),
    ("title", "Title"),
    ("mood", "Emotion"),
    ("rhythm", "Groove"),
    ("exploring", "Just exploring"),
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
  padding: 1.25rem 1.4rem 1.1rem;
  margin-bottom: 0.85rem;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
}
.composer-hero h2 {
  margin: 0 0 0.35rem 0;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.composer-hero p {
  margin: 0;
  color: #cbd5e1;
  font-size: 0.92rem;
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
  padding: 0.75rem 0.85rem;
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
  line-height: 1.5;
  margin: 0;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _pending_chord_key(section_id: str) -> str:
    return f"composer_pending_chord_{section_id}"


def _render_seed_entry(session_state: dict) -> None:
    st.markdown(
        """
<div class="composer-hero">
  <h2>What do you have so far?</h2>
  <p>Start with any idea — a style, chords, a lyric, a mood, or simply curiosity.
  The studio grows around <em>your</em> seed; nothing is filled in for you without your say.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    if "composer_seed_type" not in session_state:
        session_state["composer_seed_type"] = "style_intent"
    cols = st.columns(4)
    for i, (seed_id, label) in enumerate(_SEED_CHIPS):
        with cols[i % 4]:
            if st.button(label, key=f"composer_seed_chip_{seed_id}", use_container_width=True):
                session_state["composer_seed_type"] = seed_id
                st.rerun()

    seed_type = str(session_state.get("composer_seed_type") or "exploring")
    seed_text = st.text_area(
        "Describe your idea (optional)",
        key="composer_seed_text",
        height=100,
        placeholder='e.g. "A jazz ballad about distance" or paste | Am7 | D7 | Gmaj7 |',
    )
    title = st.text_input("Working title (optional)", key="composer_seed_title")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Begin composing →", type="primary", use_container_width=True):
            doc = bootstrap_from_seed(
                seed_type=seed_type,
                seed_text=seed_text or "",
                seed_payload={"title": title} if title else {},
            )
            set_active_document(session_state, doc)
            order = list((doc.get("form") or {}).get("section_order") or [])
            if order:
                session_state[COMPOSER_ACTIVE_SECTION_KEY] = order[0]
            save_document_to_library(session_state, doc)
            st.rerun()
    with c2:
        lib = list_library_documents(session_state)
        if lib and st.button("Resume last composition", use_container_width=True):
            load_library_document(session_state, str(lib[0].get("id") or ""))
            st.rerun()


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


def _render_beside_panel(doc: dict[str, Any], snap: dict[str, Any]) -> None:
    origin = doc.get("origin") or {}
    seed = str(origin.get("seed_summary") or "").strip()
    lead = (
        "When you're ready, ask <em>What if…?</em> — reharm, change the feel, or explore a modulation. "
        "Suggestions will explain the musical effect, and you choose what to keep."
    )
    if not snap.get("commitment", {}).get("has_chords"):
        lead = (
            "Add a chord or two, then hit <strong>Play section</strong> to hear the groove. "
            "Harmony and rhythm stay linked to your song settings."
        )
    seed_bit = f'<p class="composer-beside-body">Started from: {seed}</p>' if seed else ""
    st.markdown(
        f"""
<div class="composer-beside-panel">
  <p class="composer-beside-kicker">Composer beside you</p>
  <p class="composer-beside-body">{lead}</p>
  {seed_bit}
  <p class="composer-beside-body" style="margin-top:0.5rem;font-size:0.8rem;color:#64748b;">
    AI assist arrives in the next sprint — your snapshot is already wired for connected suggestions.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _save_doc(session_state: dict, doc: dict[str, Any]) -> None:
    touch_composition(doc)
    set_active_document(session_state, doc)
    save_document_to_library(session_state, doc)


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
        g["time_signature"] = st.selectbox("Meter", CPL_TIME_SIGNATURES, index=CPL_TIME_SIGNATURES.index(g.get("time_signature") or "4/4") if g.get("time_signature") in CPL_TIME_SIGNATURES else 0)
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
        ["C", "G", "D", "A", "E", "F", "Bb", "Eb", "Ab", "Db", "Am", "Em", "Dm"],
        index=0,
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


def render_composition_studio_page() -> None:
    session_state = st.session_state
    init_composer_page_state(session_state)
    inject_composition_studio_styles()

    needs_seed = bool(session_state.get(COMPOSER_NEEDS_SEED_KEY)) and not get_active_document(session_state)
    if needs_seed:
        _render_seed_entry(session_state)
        return

    doc = get_active_document(session_state)
    if not doc:
        session_state[COMPOSER_NEEDS_SEED_KEY] = True
        st.rerun()
        return

    title = st.text_input("Song title", value=str(doc.get("title") or ""), key="composer_title_input")
    if title != doc.get("title"):
        doc["title"] = title.strip() or "Untitled Song"
        _save_doc(session_state, doc)

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
                st.markdown(f"**{sec.get('label_variant') or sec.get('label')}** — {format_entries_bar_line(sec.get('chords') or [])}")

    with right:
        section_id = str(session_state.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
        snap = build_composition_snapshot(doc, active_section_id=section_id, focus_lane=str(session_state.get(COMPOSER_FOCUS_LANE_KEY) or "chords"))
        _render_beside_panel(doc, snap)
        if st.button("Save", key="composer_save_btn", use_container_width=True):
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
        if st.button("Start new song", key="composer_new_song"):
            session_state.pop("composer_active_document", None)
            session_state[COMPOSER_NEEDS_SEED_KEY] = True
            invalidate_composer_preview(session_state)
            st.rerun()
