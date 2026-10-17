"""Song-Aware Coaching (S3) — the Creative → Improvisation Intelligence tab.

An interactive lesson over the active song: pick a section (and bars), a level and a focus,
build a plan with the S2 engine, then work through its challenges one at a time.

Ownership:

- **Song, chart and keys** come from the Creative page's own resolution this run
  (``ImprovSessionContext``: concert sections, concert Practice Key, player-facing chart
  key), validated by :func:`song_coach_context.song_coach_context_from_session`. There is no
  song selector here.
- **Coaching state** lives in :mod:`song_coach_state` (choices and progress only).
- **Display projection only.** Plans are concert pitch; note and chord names are projected to
  the player's Written / Shape key when rendered, so an instrument change never touches the plan.
- **No global writes**: Practice Focus, Practice Key, instrument, level and Backing settings
  are only read.
- **Examples (S4)** are hidden until asked for, generated in concert pitch by
  :mod:`song_coach_examples` and projected for the live instrument only when drawn.
- **Continue in Song-Based Improvisation (S7)**: a button hands the musician to Entry & Jam →
  Song-Based Improvisation on the same authoritative song (shared helper
  :func:`creative_sbi_navigation.request_song_based_improvisation`, Song source lane reset to
  the global owner), saving where they were; Back or the coaching tab returns to the lesson.
- **Practice loop (S5)**: :mod:`song_coach_player` plays the challenge's bars with the shared
  backing arranger inside the card, with its own isolated playback.
"""

from __future__ import annotations

import html
from typing import Any, Callable

from song_coach_state import (
    NOTICE_MESSAGES,
    SONG_COACH_STATE_KEY,
    CoachState,
    Reconciled,
    build_plan_for,
    cache_plan,
    commit,
    done_stages,
    example_for,
    reconcile,
    valid_selection,
    with_built_plan,
    with_check,
    with_draft,
    with_example,
    with_new_example_idea,
    with_stage,
)

TAB_NAME = "Song-Aware Coaching"
FLASH_KEY = "_song_coach_flash"  # session-only one-off message
CTX_DIAG_KEY = "_song_coach_ctx_diag"  # session-only: the inputs the coaching context was built from
EXAMPLE_DIAG_KEY = "_song_coach_example_diag"  # session-only: what the shown example drew this run

W_SECTION = "song_coach_section"
W_FROM = "song_coach_bar_from"
W_TO = "song_coach_bar_to"
W_LEVEL = "song_coach_level"
W_FOCUS = "song_coach_focus"
W_BUILD = "song_coach_build"
W_PREV = "song_coach_prev"
W_NEXT = "song_coach_next"
W_EXAMPLE = "song_coach_example_toggle"
W_EXAMPLE_NEW = "song_coach_example_new"
W_CONTINUE_SBI = "song_coach_continue_sbi"
RETURN_SEEN_KEY = "_song_coach_return_seen"  # session-only: the handoff whose welcome-back was shown
HANDOFF_EXPLAIN = ("Song-Based Improvisation will open the full song. Your coaching section and bars will be saved "
                   "so you can return to them.")
EXAMPLE_HONESTY = "An original practice phrase built from the chart's chords — not the song's melody or a recorded solo."
WIDGET_KEYS = (W_SECTION, W_FROM, W_TO, W_LEVEL, W_FOCUS)

_SOURCE_LABELS = {"catalog": "Song library", "custom": "Custom progression", "composition": "Composition"}


# --------------------------------------------------------------------------- context & projection


def creative_coach_context(session: Any, improv_ctx: Any) -> Any:
    """The coached song, from what the Creative page resolved this run (read-only)."""
    from song_coach_context import song_coach_context_from_session

    concert = str(getattr(improv_ctx, "key_center", "") or "").strip()
    chart = str(getattr(improv_ctx, "display_key", "") or concert).strip() or concert
    return song_coach_context_from_session(
        session,
        concert_sections=getattr(improv_ctx, "sections", None),
        concert_key=concert,
        chart_key=chart,
        written_key=chart if chart != concert else "",
        instrument=str(getattr(improv_ctx, "instrument", "") or session.get("instrument") or ""),
        section_order=list(getattr(improv_ctx, "section_order", None) or []) or None,
        song_title=str(getattr(improv_ctx, "song_title", "") or ""),
        artist=str(getattr(improv_ctx, "artist", "") or ""),
        meter=song_meter(session, improv_ctx),
        bpm=int(getattr(improv_ctx, "bpm", 0) or 0),
        style=str(session.get("improv_span_song_style") or "default"),
    )


def song_meter(session: Any, improv_ctx: Any) -> str:
    """The meter the song plays in: the Backing meter only when the musician overrode it,
    else the Catalog song's own meter (``backing_time_signature`` is not settled until a page
    applies the song's meter, so it must not be read on its own). Custom / Composition: ""
    (their own record's meter is used)."""
    try:
        from songs.meter_state import BACKING_METER_KEY, BACKING_METER_OVERRIDE_KEY

        if session.get(BACKING_METER_OVERRIDE_KEY) and session.get(BACKING_METER_KEY):
            return str(session.get(BACKING_METER_KEY))
    except ImportError:
        pass
    try:
        from song_coach_context import SOURCE_CATALOG, live_catalog_record, source_owner
        from songs.meter import default_time_signature_for_record

        if source_owner(session) != SOURCE_CATALOG:
            return ""
        record = live_catalog_record(session)
        return default_time_signature_for_record(
            record, getattr(improv_ctx, "sections", None), song_title=str(getattr(improv_ctx, "song_title", "") or "")
        )
    except Exception:
        return ""


def projectors(ctx: Any) -> tuple[Callable[[Any], str], Callable[[str], str]]:
    """Note / chord name projection from concert pitch into the player's chart key."""
    from effective_practice_context import musician_facing_chord
    from music_theory import semitone_distance, spell_note_in_key

    concert, chart = ctx.concert_key, ctx.chart_key or ctx.concert_key
    shift = int(semitone_distance(concert, chart) or 0) if concert and chart else 0
    if not shift:
        return (lambda n: n.name), (lambda c: c)

    def note(n: Any) -> str:
        return spell_note_in_key((int(n.pc) + shift) % 12, chart)

    def chord(c: str) -> str:
        return musician_facing_chord(c, concert_key=concert, chart_key=chart)

    return note, chord


def chart_key_label(session: Any, ctx: Any) -> str:
    """'Written key' for a transposing instrument with Written Charts, 'Shape key' with a capo."""
    if not ctx.chart_key or ctx.chart_key == ctx.concert_key:
        return ""
    try:
        from guitar_capo import CAPO_ENABLED_KEY

        if "guitar" in ctx.instrument.lower() and session.get(CAPO_ENABLED_KEY):
            return "Shape key"
    except ImportError:
        pass
    return "Written key"


def _transposing_type(session: Any, ctx: Any) -> str:
    """The selected transposing type ("Tenor saxophone (Bb)" …) when written charts are shown."""
    if not ctx.chart_key or ctx.chart_key == ctx.concert_key:
        return ""
    try:
        from instrument_transposition import selected_transposing_type

        return str(selected_transposing_type(session, ctx.instrument) or "")
    except ImportError:
        return ""


def instrument_label(session: Any, instrument: str) -> str:
    try:
        from instrument_transposition import instrument_display_name, selected_transposing_type

        kind = selected_transposing_type(session, instrument)
        if kind:
            return instrument_display_name(kind, instrument)
    except ImportError:
        pass
    return instrument or "Instrument"


# --------------------------------------------------------------------------- state plumbing


def _defaults(session: Any) -> tuple[str, str]:
    from song_coach_plan import default_coaching_focus, normalize_level

    return normalize_level(str(session.get("level") or "")), default_coaching_focus(str(session.get("focus") or ""))


def current(session: Any, ctx: Any) -> Reconciled:
    level, focus = _defaults(session)
    return reconcile(session, ctx, level=level, focus=focus)


def _flash(session: Any, text: str) -> None:
    session[FLASH_KEY] = text


def _bar(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _seed_widgets(session: Any, state: CoachState, ctx: Any) -> None:
    """Widgets show the stored draft. A value is assigned (before the widgets exist this run)
    only when it is missing or really differs, so Streamlit's own widget value is kept."""
    d = state.draft
    for key, want in (
        (W_SECTION, d.section_id), (W_FROM, d.start_bar), (W_TO, d.end_bar), (W_LEVEL, d.level), (W_FOCUS, d.focus)
    ):
        if session.get(key) != want:
            session[key] = want


def on_selection_change(session: Any, ctx: Any) -> None:
    """Section / bars / level / focus changed: update the draft (the built plan stays until rebuilt)."""
    from song_coach_scope import MAX_SCOPE_BARS, find_section, suggested_ranges

    rec = current(session, ctx)
    section_id = str(session.get(W_SECTION) or rec.state.draft.section_id)
    sec = find_section(ctx, section_id)
    if sec is None:
        return
    old = rec.state.draft
    start, end = _bar(session.get(W_FROM)), _bar(session.get(W_TO))
    if section_id != old.section_id or start is None or end is None:
        start, end = suggested_ranges(sec)[0]
    else:
        start, end = max(1, min(start, sec.bar_count)), max(1, min(end, sec.bar_count))
        if end < start:  # "From" moved past "To": keep the previous length from the new start
            end = min(sec.bar_count, start + max(0, old.end_bar - old.start_bar))
        if end - start + 1 > MAX_SCOPE_BARS:
            end = start + MAX_SCOPE_BARS - 1
            _flash(session, f"Choose at most {MAX_SCOPE_BARS} bars at a time — your range was shortened to bars {start}–{end}.")
    session[W_FROM], session[W_TO] = start, end
    state = with_draft(
        rec.state, section_id=section_id, start_bar=start, end_bar=end,
        level=str(session.get(W_LEVEL) or rec.state.draft.level), focus=str(session.get(W_FOCUS) or rec.state.draft.focus),
    )
    if state.draft == rec.state.draft:
        return  # nothing really changed (e.g. a widget re-reporting its value): no write
    commit(session, state, interaction="selection")


def on_build(session: Any, ctx: Any) -> None:
    rec = current(session, ctx)
    state = rec.state
    if not valid_selection(ctx, state.draft):
        _flash(session, "Choose a section and bars first.")
        return
    try:
        plan, scope = build_plan_for(ctx, state.draft)
    except Exception as exc:  # e.g. bars with no chords
        _flash(session, str(exc) or "These bars can't be coached yet.")
        return
    built = with_built_plan(state, plan)
    cache_plan(session, built, ctx, plan, scope)
    commit(session, built, interaction="build_plan")


def on_stage(session: Any, ctx: Any, delta: int) -> None:
    rec = current(session, ctx)
    if rec.plan is None:
        return
    commit(session, with_stage(rec.state, rec.state.stage + delta, len(rec.plan.challenges)), interaction="stage")


def on_check(session: Any, ctx: Any, stage: int, item: int, widget_key: str) -> None:
    rec = current(session, ctx)
    if rec.plan is None:
        return
    commit(session, with_check(rec.state, stage, item, bool(session.get(widget_key))), interaction="self_check")


def on_continue_sbi(session: Any, ctx: Any) -> None:
    """Continue in Song-Based Improvisation: same song, Practice Key and instrument; the lesson
    and its progress stay as they are, with a note of where the musician was."""
    from datetime import datetime, timezone

    from creative_sbi_navigation import request_song_based_improvisation
    from song_coach_state import handoff_record, with_handoff

    rec = current(session, ctx)
    if rec.plan is None or not ctx.available:
        _flash(session, "Build a coaching plan for this song first.")
        return
    if str(session.get("studio_page") or "").strip() != "creative":
        _flash(session, "Song-Based Improvisation isn't available from here.")
        return
    record = handoff_record(rec.state, ctx, rec.scope, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    # Saved first: the Back step recorded by the navigation snapshots this page, handoff included.
    commit(session, with_handoff(rec.state, record), interaction="handoff_sbi")
    request_song_based_improvisation(session, "song_coach_handoff", sync_source_to_global_owner=True)


def on_example(session: Any, ctx: Any, stage: int) -> None:
    rec = current(session, ctx)
    if rec.plan is None:
        return
    commit(session, with_example(rec.state, stage, stage not in rec.state.examples), interaction="example")


def on_example_new(session: Any, ctx: Any) -> None:
    rec = current(session, ctx)
    if rec.plan is None:
        return
    commit(session, with_new_example_idea(rec.state), interaction="example_new_idea")


# --------------------------------------------------------------------------- rendering


def _render_header(st: Any, session: Any, ctx: Any) -> None:
    try:
        from music_feature_icons import format_icon_html, semantic_field_icon
    except ImportError:
        format_icon_html = html.escape  # type: ignore[assignment]
        semantic_field_icon = lambda *_a, **_k: ""  # type: ignore[assignment]  # noqa: E731
    inst = instrument_label(session, ctx.instrument)
    title = html.escape(ctx.song_title or "Active song")
    artist = f' <span style="font-weight:600;color:#64748b;">— {html.escape(ctx.artist)}</span>' if ctx.artist else ""
    meta = [
        f"<span>{html.escape(_SOURCE_LABELS.get(ctx.source_kind, 'Active song'))}</span>",
        f"<span>{format_icon_html(semantic_field_icon('written_key', instrument=ctx.instrument)) if ctx.instrument else ''} {html.escape(inst)}</span>",
        f'<span data-song-coach-concert-key="{html.escape(ctx.concert_key)}">Practice Key {html.escape(ctx.concert_key)} (concert)</span>',
    ]
    label = chart_key_label(session, ctx)
    if label:
        meta.append(f'<span data-song-coach-chart-key="{html.escape(ctx.chart_key)}">{label} {html.escape(ctx.chart_key)}</span>')
    if ctx.available:
        meta.append(f"<span>{html.escape(ctx.chart_label)}</span>")
    st.markdown(
        '<div class="ui-creative-song-card active">'
        '<p class="ui-creative-song-kicker">Coaching for your active song</p>'
        f'<p class="ui-creative-song-title">{title}{artist}</p>'
        f'<div class="ui-creative-song-meta">{"".join(meta)}</div></div>',
        unsafe_allow_html=True,
    )
    if ctx.available:
        st.caption(ctx.chart_note)


def _render_selectors(st: Any, session: Any, ctx: Any, rec: Reconciled) -> None:
    from song_coach_plan import FOCUS_LABELS, FOCUSES, LEVELS
    from song_coach_scope import coach_sections, find_section, suggested_ranges

    sections = coach_sections(ctx)
    labels = {
        s.section_id: f"{s.label} · {s.bar_count} bar{'s' if s.bar_count != 1 else ''}" + (f" · plays {s.occurrences}×" if s.occurrences > 1 else "")
        for s in sections
    }
    _seed_widgets(session, rec.state, ctx)
    cb = {"on_change": on_selection_change, "args": (session, ctx)}
    st.markdown('<p class="ui-creative-section-label">What to practise</p>', unsafe_allow_html=True)
    st.selectbox("Section", list(labels), format_func=lambda sid: labels.get(sid, sid), key=W_SECTION, **cb)
    sec = find_section(ctx, rec.state.draft.section_id)
    if sec is not None and sec.bar_count > 1:
        bars = list(range(1, sec.bar_count + 1))
        b1, b2 = st.columns(2)
        with b1:
            st.selectbox("From bar", bars, key=W_FROM, **cb)
        with b2:
            st.selectbox("To bar", bars, key=W_TO, **cb)
        hints = ", ".join(f"{a}–{b}" for a, b in suggested_ranges(sec))
        st.caption(f"Phrase-sized ranges for this section: {hints} (up to 16 bars at a time).")
    c1, c2 = st.columns(2)
    with c1:
        st.radio("Level", list(LEVELS), horizontal=True, key=W_LEVEL, **cb)
    with c2:
        st.selectbox("Coaching focus", list(FOCUSES), format_func=lambda f: FOCUS_LABELS[f], key=W_FOCUS, **cb)
    global_focus = str(session.get("focus") or "").strip()
    if global_focus:
        st.caption(f"The focus starts from your Practice Focus ({global_focus}); changing it here only affects this coaching.")


def _render_line(st: Any, line: Any, note: Callable, chord: Callable) -> None:
    from song_coach_plan import BASIS_STYLE

    text = line.render(note, chord)
    if line.basis == BASIS_STYLE:
        st.markdown(f"- *Style tip: {text}*")
    else:
        st.markdown(f"- {text}")


def _render_plan(st: Any, session: Any, ctx: Any, rec: Reconciled) -> None:
    from song_coach_plan import FOCUS_LABELS, KIND_ROADMAP

    plan, state = rec.plan, rec.state
    note, chord = projectors(ctx)
    total = len(plan.challenges)
    done = done_stages(state, plan)
    stage = state.stage
    ch = plan.challenges[stage]

    st.markdown(f"#### Your plan · {plan.range_label}")
    st.caption(f"{plan.level} · {FOCUS_LABELS[plan.focus]} · {total} challenges")
    _render_welcome_back(st, session, ctx, state)
    if state.draft != state.built:
        st.info("You've changed the section, bars, level or focus. Press **Build My Coaching Plan** to update the plan — your current plan stays until then.")
    st.progress(len(done) / total, text=f"{len(done)} of {total} challenges done")
    chips = " ".join(
        f"**[{i + 1}]**" if i == stage else (f"✓{i + 1}" if i in done else str(i + 1)) for i in range(total)
    )
    st.markdown(f"Challenges: {chips}")

    with st.expander("About these bars", expanded=stage == 0):
        for line in plan.summary:
            _render_line(st, line, note, chord)
        if plan.material is not None:
            st.markdown(f"**Notes to improvise with — {plan.material.name}**")
            for line in plan.material.lines:
                _render_line(st, line, note, chord)

    with st.container(border=True, key="song_coach_challenge_card"):
        st.markdown(f"### {stage + 1}. {ch.title}")
        st.markdown(ch.goal.render(note, chord))
        chords = " → ".join(chord(c) for c in ch.chords)
        st.caption(f"Practice bars {ch.loop_start}–{ch.loop_end} · {chords}")
        for line in ch.steps:
            _render_line(st, line, note, chord)
        if ch.targets and ch.kind != KIND_ROADMAP:
            shown = list(dict.fromkeys(f"{note(t)} over {chord(t.chord)}" for t in ch.targets))[:6]
            st.markdown("**Landing notes:** " + ", ".join(shown))
        from song_coach_player import render_practice_loop

        render_practice_loop(st, session, ctx, rec, ch, chord_label=chord)
        _render_example(st, session, ctx, rec, stage, chord)
        if ch.checklist:
            st.markdown("**Self-check**")
            ticked = set(state.checks.get(str(stage), ()))
            for i, item in enumerate(ch.checklist):
                key = f"song_coach_check_{plan.plan_id}_{stage}_{i}"
                session[key] = i in ticked
                st.checkbox(item, key=key, on_change=on_check, args=(session, ctx, stage, i, key))

    c_prev, c_mid, c_next = st.columns([1, 2, 1])
    with c_prev:
        st.button("← Previous", key=W_PREV, disabled=stage <= 0, use_container_width=True,
                  on_click=on_stage, args=(session, ctx, -1))
    with c_mid:
        st.markdown(f"<p style='text-align:center;margin-top:0.4rem'>Challenge {stage + 1} of {total}</p>", unsafe_allow_html=True)
    with c_next:
        st.button("Next →", key=W_NEXT, disabled=stage >= total - 1, use_container_width=True,
                  on_click=on_stage, args=(session, ctx, 1))
    _render_continue_sbi(st, session, ctx, plan, stage == total - 1)
    if plan.reading_notes:
        with st.expander("How the chords were read"):
            for n in plan.reading_notes:
                st.markdown(f"- {n}")


def _render_welcome_back(st: Any, session: Any, ctx: Any, state: CoachState) -> None:
    """A brief note on returning from Song-Based Improvisation, while the handoff still matches."""
    from song_coach_state import HANDOFF_VALID, handoff_status

    h = state.handoff or {}
    if handoff_status(state, ctx) != HANDOFF_VALID or session.get(RETURN_SEEN_KEY) == h.get("at"):
        return
    bars = f"bar {h['start_bar']}" if h["start_bar"] == h["end_bar"] else f"bars {h['start_bar']}–{h['end_bar']}"
    st.success(f"Welcome back — your coaching on {h.get('section_label') or 'this section'}, {bars}, is where you left it.")
    session[RETURN_SEEN_KEY] = h.get("at")


def _render_continue_sbi(st: Any, session: Any, ctx: Any, plan: Any, last_stage: bool) -> None:
    with st.container(border=True, key="song_coach_continue_card"):
        st.markdown("**Ready to improvise freely?**" if last_stage else "**Improvise over the whole song**")
        st.caption(HANDOFF_EXPLAIN)
        st.button("Continue in Song-Based Improvisation", key=W_CONTINUE_SBI, disabled=not ctx.available,
                  on_click=on_continue_sbi, args=(session, ctx), use_container_width=True)


def _render_example(st: Any, session: Any, ctx: Any, rec: Reconciled, stage: int, chord: Callable[[str], str]) -> None:
    """The optional example for this challenge: a toggle, then validated notation (or the reason
    there is none). Shown phrases are projected for the live instrument at draw time only."""
    from song_coach_examples import segment_notation

    state = rec.state
    shown = stage in state.examples
    st.button("🎼 Hide the example" if shown else "🎼 Show an Example", key=W_EXAMPLE,
              on_click=on_example, args=(session, ctx, stage))
    if not shown:
        return
    ex = example_for(session, state, rec.plan, rec.scope, stage)
    diag: dict[str, Any] = {"plan_id": state.plan_id, "stage": stage, "kind": ex.kind, "nonce": state.example_nonce,
                            "available": ex.available, "limitation": ex.limitation, "segments": []}
    if not ex.available:
        st.info(ex.limitation)
        session[EXAMPLE_DIAG_KEY] = diag
        return
    st.markdown(f"**Example** — {ex.caption}")
    st.caption(EXAMPLE_HONESTY)
    if ex.limitation:
        st.caption(f"ℹ️ {ex.limitation}")
    try:
        from improvisation_intelligence_ui import _render_motif_sheet_music
    except ImportError:  # pragma: no cover - the tab lives inside that page
        _render_motif_sheet_music = None  # type: ignore[assignment]
    kind = _transposing_type(session, ctx)
    for seg in ex.segments:
        n = segment_notation(seg, concert_key=ctx.concert_key, chart_key=ctx.chart_key, project_chord=chord,
                             instrument=ctx.instrument, bpm=ctx.bpm, title=seg.label, transposing_type=kind)
        bars = f"bar {seg.start_bar}" if seg.start_bar == seg.end_bar else f"bars {seg.start_bar}–{seg.end_bar}"
        st.markdown(f"*{seg.label}* · {bars} · {' → '.join(n.chords)}")
        if _render_motif_sheet_music is not None:
            _render_motif_sheet_music(st, n.abc)
        st.caption("Notes: " + " ".join(n.notes) + (f" · {n.note}" if n.note else ""))
        if n.tab:
            st.code(n.tab, language=None)
        diag["segments"].append({"label": seg.label, "bars": [seg.start_bar, seg.end_bar], "chords": list(n.chords),
                                 "notes": list(n.notes), "midi": list(n.midi), "abc": n.abc, "key": n.key,
                                 "tab": bool(n.tab), "concert_midi": [int(m) for m in seg.motif.get("midi") or []],
                                 "shift": n.shift, "transposing_type": kind})
    if ex.kind != "idea" and ex.continuity.get("same_rhythm_cell"):
        st.caption("🔁 Same rhythm cell as the starting idea, so the idea stays recognisable.")
    session[EXAMPLE_DIAG_KEY] = diag
    st.button("Try a different example idea", key=W_EXAMPLE_NEW, on_click=on_example_new, args=(session, ctx),
              help="A new starting idea — every example in this plan changes with it.")


def render_song_aware_coaching_tab(st: Any, *, session_state: Any, improv_ctx: Any) -> None:
    """Creative → Improvisation Intelligence → Song-Aware Coaching."""
    try:
        from studio_page_state import creative_tool_heading_markdown

        st.markdown(creative_tool_heading_markdown(TAB_NAME))
    except ImportError:
        st.markdown(f"#### {TAB_NAME}")
    st.caption("Turn the techniques you've practised into one connected improvisation over this song's real chords.")
    ctx = creative_coach_context(session_state, improv_ctx)
    session_state.pop(EXAMPLE_DIAG_KEY, None)  # describes only what this run draws
    from song_coach_player import LOOP_DIAG_KEY

    session_state.pop(LOOP_DIAG_KEY, None)
    session_state[CTX_DIAG_KEY] = {
        "identity": ctx.identity, "fingerprint": ctx.fingerprint, "concert_key": ctx.concert_key, "meter": ctx.meter,
        "sections": [[name, list(bars)] for name, bars in ctx.sections], "reason": ctx.reason,
    }
    _render_header(st, session_state, ctx)
    if not ctx.available:
        st.info(ctx.unavailable_message or "This song can't be coached yet.")
        return
    rec = current(session_state, ctx)
    if rec.notice:
        st.info(NOTICE_MESSAGES[rec.notice])
    flash = session_state.pop(FLASH_KEY, "") if hasattr(session_state, "pop") else ""
    if flash:
        st.warning(flash)
    _render_selectors(st, session_state, ctx, rec)
    st.button("Build My Coaching Plan", key=W_BUILD, type="primary", use_container_width=True,
              on_click=on_build, args=(session_state, ctx))
    if rec.plan is None:
        st.caption("Your plan will be a short series of challenges that grow one idea through these bars.")
        return
    cache_plan(session_state, rec.state, ctx, rec.plan, rec.scope)
    _render_plan(st, session_state, ctx, rec)


__all__ = [
    "FLASH_KEY",
    "SONG_COACH_STATE_KEY",
    "TAB_NAME",
    "WIDGET_KEYS",
    "chart_key_label",
    "creative_coach_context",
    "current",
    "instrument_label",
    "on_build",
    "on_check",
    "on_selection_change",
    "on_stage",
    "projectors",
    "render_song_aware_coaching_tab",
]
