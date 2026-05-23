"""Streamlit UI — Improvisation Intelligence (Creative Lab)."""

from __future__ import annotations

import html
from typing import Any, Callable

from improvisation_intelligence import (
    CATALOG_IMPROV_PRESETS,
    DIFFICULTY_LEVELS,
    GROOVE_INTENSITY,
    MOOD_OPTIONS,
    PRACTICE_MISSIONS,
    STYLE_JAM_STYLES,
    ChordCoachInsight,
    ImprovSessionContext,
    ai_feedback_preview_lines,
    chord_coach_insight,
    creativity_metrics_placeholder,
    flatten_sections,
    generate_jam_session,
    generate_motif,
    generate_style_progression,
    harmony_flow_map,
    level_coaching_summary,
)


def render_improvisation_intelligence_lab(
    st: Any,
    *,
    ctx: dict[str, Any],
    session_state: dict,
    chart_key: str,
    sections: dict[str, list[str]],
    song_data: dict,
    bpm: int,
    genre: str,
    is_custom: bool,
    on_open_backing: Callable[[], None] | None = None,
    on_open_practice: Callable[[], None] | None = None,
    on_open_analysis: Callable[[], None] | None = None,
) -> None:
    """Full Improvisation Intelligence workspace under Creative Lab."""
    instrument = str(ctx.get("instrument") or "Guitar")
    level = str(ctx.get("level") or "Intermediate")
    song_title = str(ctx.get("song") or "Song")
    artist = str(ctx.get("artist") or "")

    st.markdown(
        '<div class="ui-card soft" style="margin-bottom:1rem;border-left:4px solid #8b5cf6;">'
        '<p class="ui-card-title">🎷 Improvisation Intelligence</p>'
        '<p class="ui-card-sub">Interactive improvisation coach + creative laboratory — '
        "song-based jams, style generators, live harmony coach, motifs, and missions.</p></div>",
        unsafe_allow_html=True,
    )

    improv_ctx = ImprovSessionContext(
        song_title=song_title,
        artist=artist,
        key_center=str(song_data.get("key") or "C"),
        display_key=chart_key,
        instrument=instrument,
        level=level,
        focus=str(ctx.get("focus") or "Improvisation"),
        sections=sections,
        bpm=bpm,
        style_label=genre,
        progression_flat=flatten_sections(sections),
    )

    tabs = st.tabs(
        [
            "Entry & Jam",
            "Live Coach",
            "Phrase / Motif",
            "Missions",
            "Harmony Map",
            "Metrics & AI",
        ]
    )

    with tabs[0]:
        _tab_entry_modes(
            st,
            session_state=session_state,
            improv_ctx=improv_ctx,
            is_custom=is_custom,
            on_open_backing=on_open_backing,
            on_open_practice=on_open_practice,
        )
    with tabs[1]:
        _tab_live_coach(st, session_state=session_state, improv_ctx=improv_ctx)
    with tabs[2]:
        _tab_motif(st, session_state=session_state, level=level)
    with tabs[3]:
        _tab_missions(st, session_state=session_state, level=level)
    with tabs[4]:
        _tab_harmony_map(st, improv_ctx=improv_ctx)
    with tabs[5]:
        _tab_metrics_ai(st, session_state=session_state, on_open_analysis=on_open_analysis)


def _tab_entry_modes(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: ImprovSessionContext,
    is_custom: bool,
    on_open_backing: Callable[[], None] | None,
    on_open_practice: Callable[[], None] | None,
) -> None:
    entry = st.radio(
        "Improvisation entry mode",
        ["Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator"],
        horizontal=True,
        key="improv_entry_mode",
    )

    if entry == "Song-Based Improvisation":
        st.markdown("#### 🎼 Song-based improvisation")
        preset = st.selectbox(
            "Song source",
            list(CATALOG_IMPROV_PRESETS),
            index=0,
            key="improv_song_preset",
        )
        if preset == "Use active studio song":
            st.info(
                f"**Active:** {improv_ctx.song_title} — {improv_ctx.artist} · "
                f"Key **{improv_ctx.display_key}** · {len(improv_ctx.progression_flat)} chords in chart."
            )
            active_sections = improv_ctx.sections
        elif preset == "Custom progression (CPL)":
            if is_custom:
                st.success("Using your **Custom Progression** from the studio.")
                active_sections = improv_ctx.sections
            else:
                st.warning("Switch source to Custom Progression Lab or pick a catalog song.")
                active_sections = improv_ctx.sections
        else:
            st.caption(
                f"Preset **{preset}** — using active chart if it matches; otherwise use Song Selection."
            )
            active_sections = improv_ctx.sections

        if active_sections:
            st.caption("Progression preview: " + " | ".join(flatten_sections(active_sections)[:12]))
        c1, c2 = st.columns(2)
        with c1:
            if on_open_backing and st.button("Open in Backing Track", key="improv_to_backing", type="primary"):
                on_open_backing()
        with c2:
            if on_open_practice and st.button("Open Practice", key="improv_to_practice"):
                on_open_practice()

    elif entry == "Style Jam Mode":
        st.markdown("#### 🎹 Style Jam Mode")
        c1, c2, c3 = st.columns(3)
        with c1:
            style = st.selectbox("Style", list(STYLE_JAM_STYLES), key="improv_style")
            key_center = st.selectbox(
                "Key",
                ["C", "D", "Eb", "E", "F", "G", "A", "Bb", "Dm", "Em", "Am"],
                index=5,
                key="improv_style_key",
            )
        with c2:
            difficulty = st.selectbox("Difficulty", list(DIFFICULTY_LEVELS), key="improv_difficulty")
            mood = st.selectbox("Mood", list(MOOD_OPTIONS), key="improv_mood")
        with c3:
            tempo = st.slider("Tempo (BPM)", 60, 200, 110, 5, key="improv_style_bpm")
            groove = st.selectbox("Groove intensity", list(GROOVE_INTENSITY), key="improv_groove")

        prompt = st.text_input(
            "Describe your jam (optional)",
            placeholder="e.g. medium jazz-funk progression in D minor",
            key="improv_style_prompt",
        )
        if st.button("Generate progression", type="primary", key="improv_gen_style"):
            k = key_center.replace("m", "") if "minor" in (prompt or "").lower() and "Dm" in prompt else key_center
            if "d minor" in (prompt or "").lower():
                k = "Dm"
            session_state["improv_generated_sections"] = generate_style_progression(
                style=style,
                key_center=k,
                difficulty=difficulty,
                mood=mood,
            )
            session_state["improv_style_meta"] = {
                "style": style,
                "bpm": tempo,
                "groove": groove,
                "prompt": prompt,
            }
            st.rerun()

        gen = session_state.get("improv_generated_sections")
        if gen:
            st.success(f"Generated **{style}** progression in **{key_center}** · {mood} · {tempo} BPM")
            for sec, chs in gen.items():
                st.markdown(f"**{sec}:** " + " | ".join(chs))
            if on_open_backing and st.button("Send to Backing Track", key="improv_style_to_backing"):
                session_state["improv_use_generated"] = True
                on_open_backing()

    else:
        st.markdown("#### 🌙 Jam Session Generator")
        e1, e2 = st.columns(2)
        with e1:
            ensemble = st.selectbox(
                "Ensemble",
                ["Jazz trio", "Jazz quartet", "Neo-soul band", "Rock trio", "Latin quartet", "Lo-fi duo"],
                key="improv_ensemble",
            )
            style = st.selectbox("Groove style", list(STYLE_JAM_STYLES), key="improv_jam_style")
        with e2:
            key_c = st.selectbox("Key", ["Eb", "C", "D", "F", "G", "Am", "Dm", "Bbm"], key="improv_jam_key")
            tempo = st.slider("Tempo", 70, 180, 120, 5, key="improv_jam_bpm")
            mood = st.selectbox("Atmosphere", list(MOOD_OPTIONS), key="improv_jam_mood")

        if st.button("Generate jam session", type="primary", key="improv_gen_jam"):
            session_state["improv_jam_session"] = generate_jam_session(
                ensemble=ensemble,
                style=style,
                key_center=key_c,
                tempo=tempo,
                mood=mood,
            )
            st.rerun()

        jam = session_state.get("improv_jam_session")
        if jam:
            st.markdown(f"### {jam.get('title', 'Jam session')}")
            st.caption(jam.get("prompt", ""))
            for sec, chs in (jam.get("sections") or {}).items():
                st.write(f"**{sec}:** " + " | ".join(chs))


def _tab_live_coach(st: Any, *, session_state: dict, improv_ctx: ImprovSessionContext) -> None:
    st.markdown("#### Real-time improvisation coach")
    summary = level_coaching_summary(improv_ctx.level)
    st.caption(
        f"**{improv_ctx.level}:** {summary['focus']} · {summary['harmony']}"
    )

    prog = session_state.get("improv_generated_sections")
    chords = flatten_sections(prog) if prog else improv_ctx.progression_flat
    if not chords:
        st.warning("No chords in the active chart — pick a song or generate a style progression.")
        return

    idx = st.slider(
        "Current chord in form",
        0,
        max(0, len(chords) - 1),
        int(session_state.get("improv_chord_idx", 0)),
        key="improv_chord_idx_slider",
    )
    session_state["improv_chord_idx"] = idx
    cur = chords[idx]
    nxt = chords[idx + 1] if idx + 1 < len(chords) else ""

    insight = chord_coach_insight(
        cur,
        key_center=improv_ctx.display_key,
        next_chord=nxt,
        instrument=improv_ctx.instrument,
        level=improv_ctx.level,
    )
    _render_chord_coach_card(st, insight)

    st.markdown("##### Instrument-adaptive coaching")
    for line in insight.instrument_tips:
        st.markdown(f"- {line}")

    if session_state.get("_last_backing_timeline"):
        st.caption(
            "Tip: play your backing track and step through chords with the slider to mirror the form."
        )


def _render_chord_coach_card(st: Any, insight: ChordCoachInsight) -> None:
    st.markdown(
        f'<div class="ui-card soft" style="border-left:4px solid #22c55e;">'
        f'<p class="ui-card-title">Current chord: {html.escape(insight.chord)}</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Suggested scales**")
        for s in insight.scales:
            st.markdown(f"- {s}")
        st.markdown("**Chord tones**")
        st.markdown("`" + " · ".join(insight.chord_tones) + "`")
    with c2:
        st.markdown("**Tensions / extensions**")
        for t in insight.tensions:
            st.markdown(f"- {t}")
        st.markdown("**Avoid**")
        for a in insight.avoid_notes:
            st.markdown(f"- {a}")
    st.markdown("**Target notes:** " + ", ".join(insight.target_notes))
    st.info(insight.motif_idea)
    if insight.resolve_hint:
        st.success(insight.resolve_hint)


def _tab_motif(st: Any, *, session_state: dict, level: str) -> None:
    st.markdown("#### Phrase / motif training")
    if st.button("Generate new motif", key="improv_gen_motif"):
        session_state["improv_motif"] = generate_motif()
        st.rerun()
    motif = session_state.get("improv_motif") or generate_motif()
    session_state.setdefault("improv_motif", motif)
    st.markdown(f"### Motif: **{motif['display']}**")
    st.caption(f"Rhythm idea: {motif['rhythm']}")
    st.markdown(motif["variation_prompt"])
    st.markdown(
        """
**Training steps:**
1. Play the motif exactly as written (any octave).
2. Imitate — same rhythm, different notes in the scale.
3. Develop — sequence up or down; rhythmic transformation.
4. Inversion — flip the interval direction on repetition.
        """
    )
    if level == "Beginner":
        st.caption("Beginner: repeat the motif 4× with identical rhythm before changing notes.")
    elif level == "Advanced":
        st.caption("Advanced: displace rhythm by 8th note; superimpose over next chord.")


def _tab_missions(st: Any, *, session_state: dict, level: str) -> None:
    st.markdown("#### Practice missions")
    mission = st.selectbox("Choose a mission", list(PRACTICE_MISSIONS), key="improv_mission_pick")
    if st.button("Set active mission", key="improv_set_mission"):
        session_state["improv_active_mission"] = mission
        st.rerun()
    active = session_state.get("improv_active_mission")
    if active:
        st.success(f"Active mission: **{active}**")
    st.markdown("**Level focus**")
    summ = level_coaching_summary(level)
    for k, v in summ.items():
        st.markdown(f"- **{k.title()}:** {v}")


def _tab_harmony_map(st: Any, *, improv_ctx: ImprovSessionContext) -> None:
    st.markdown("#### Harmony visualization")
    rows = harmony_flow_map(improv_ctx.sections, improv_ctx.display_key)
    if not rows:
        st.info("No harmony to map yet.")
        return
    html_rows = []
    for r in rows:
        html_rows.append(
            f'<div style="display:flex;align-items:center;gap:0.5rem;margin:0.25rem 0;">'
            f'<span style="background:{r["color"]};color:#fff;padding:0.2rem 0.5rem;'
            f'border-radius:6px;font-weight:700;">{html.escape(r["chord"])}</span>'
            f'<span style="font-size:0.85rem;color:#64748b;">{html.escape(r["role"])}</span>'
            f'<span style="font-size:0.85rem;">{html.escape(r["arrow"])}</span></div>'
        )
    st.markdown(
        '<div class="ui-card soft">' + "".join(html_rows[:20]) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Green = tonic/release · Amber = dominant/tension · Indigo = minor color")


def _tab_metrics_ai(
    st: Any,
    *,
    session_state: dict,
    on_open_analysis: Callable[[], None] | None,
) -> None:
    st.markdown("#### Creativity metrics (non-judgmental)")
    st.caption("Exploratory indices — not good/bad scores. Full analysis coming with recorded takes.")
    metrics = creativity_metrics_placeholder()
    cols = st.columns(3)
    labels = list(metrics.keys())
    for i, (label, val) in enumerate(metrics.items()):
        with cols[i % 3]:
            st.metric(label.replace("_", " ").title(), f"{int(val * 100)}%")
    st.progress(metrics["motif_development"], text="Motif development (demo)")

    st.markdown("---")
    st.markdown("#### AI improvisation feedback (preview)")
    for line in ai_feedback_preview_lines():
        st.markdown(f"- {line}")
    if on_open_analysis and st.button("Upload take for AI coach", key="improv_to_analysis"):
        on_open_analysis()
