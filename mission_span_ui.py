"""MC3 — Missions page, Target Scope 2 / 3 chords.

Single chord stays the default and keeps the existing Missions flow untouched. For a span
scope this renders the shared HarmonicSpan picker (same one Phrase / Motif uses), only the
Missions that make sense on the chosen span, Easier / Harder / New Idea inside the player's
Level, and the example: notes per chord, *where* the Mission happens, the MC2.2 localized
explanation, notation and (for guitar) TAB.

State (all span-Mission-only keys, so nothing leaks to or from single-chord Missions):

- ``_improv_mission_target_scope_choice`` — Single / 2 / 3 chords.
- ``_improv_mission_span_selection`` — picked span id per scope, per progression.
- ``improv_span_mission`` — ``{context, bucket, ideas, history, example}``. ``context`` is
  Mission id | span id | Level | song | style: any change resets to Normal, idea 0.
"""

from __future__ import annotations

import html
from typing import Any

MISSION_TARGET_SCOPE_STATE_KEY = "_improv_mission_target_scope_choice"
MISSION_TARGET_SCOPE_WIDGET_KEY = "improv_mission_target_scope"
MISSION_SPAN_SELECTION_STATE_KEY = "_improv_mission_span_selection"
MISSION_AMI_SPAN_PICK_KEY = "_improv_mission_ami_span_pick"  # one-shot: the span an AMI exercise was made on
MISSION_SPAN_WIDGET_PREFIX = "improv_mission_span_pick"
SPAN_MISSION_STATE_KEY = "improv_span_mission"
SPAN_MISSION_PICK_KEY = "improv_span_mission_pick"
SPAN_MISSION_ABC_KEY = "improv_span_mission_abc"
SPAN_MISSION_CHOICE_KEY = "_improv_span_mission_choice"
_BUCKETS = ("easier", "normal", "harder")
_BUCKET_LABELS = {"easier": "Easier", "normal": "Normal", "harder": "Harder"}


def render_mission_target_scope(st: Any, session_state: dict) -> str:
    """Missions Target Scope (Single chord is the default)."""
    from improvisation_intelligence_ui import _MOTIF_TARGET_SCOPE_LABELS, _MOTIF_TARGET_SCOPES, SCOPE_SINGLE

    stored = session_state.get(MISSION_TARGET_SCOPE_STATE_KEY)
    if stored not in _MOTIF_TARGET_SCOPES:
        stored = SCOPE_SINGLE
    if session_state.get(MISSION_TARGET_SCOPE_WIDGET_KEY) not in (None, *_MOTIF_TARGET_SCOPES):
        session_state.pop(MISSION_TARGET_SCOPE_WIDGET_KEY, None)
    choice = st.radio(
        "Target scope",
        list(_MOTIF_TARGET_SCOPES),
        index=_MOTIF_TARGET_SCOPES.index(stored),
        format_func=lambda scope: _MOTIF_TARGET_SCOPE_LABELS.get(scope, scope),
        horizontal=True,
        key=MISSION_TARGET_SCOPE_WIDGET_KEY,
    )
    if choice not in _MOTIF_TARGET_SCOPES:
        choice = SCOPE_SINGLE
    session_state[MISSION_TARGET_SCOPE_STATE_KEY] = choice
    return choice


def span_mission_context(mission_id: str, span_id: str, level: str, song_title: object, style: str) -> str:
    """Identity of one Mission-on-a-span session; a different one resets the Mission's example and history."""
    return "|".join((mission_id, span_id, level, str(song_title or ""), style))


def adopt_ami_example_span_id(example: dict, span: Any) -> None:
    """Point an AMI-made example at this page's span object (the id also depends on the page's song context)."""
    example["span_id"] = span.span_id
    example["span_chords"] = list(span.chords)
    if isinstance(example.get("handoff"), dict):
        example["handoff"]["span_id"] = span.span_id
    if isinstance(example.get("motif"), dict):
        example["motif"]["span_id"] = span.span_id


def span_mission_intent(state: dict, *, context: str, intent: str) -> tuple[str, int]:
    """Difficulty state machine (same semantics as single-chord Missions, separate state).

    A new Mission / span / Level / song context resets to Normal, idea 0. Easier / Harder
    move one bucket inside the Level; at the floor / ceiling they vary the idea instead.
    New Idea keeps the bucket and advances the idea.
    """
    if state.get("context") != context:
        state.clear()
        state.update({"context": context, "bucket": "normal", "ideas": {}, "history": []})
    bucket = str(state.get("bucket") or "normal")
    ideas = dict(state.get("ideas") or {})
    idx = _BUCKETS.index(bucket) if bucket in _BUCKETS else 1
    if intent == "easier":
        if idx > 0:
            bucket = _BUCKETS[idx - 1]
        else:
            ideas[bucket] = int(ideas.get(bucket) or 0) + 1
    elif intent == "harder":
        if idx < len(_BUCKETS) - 1:
            bucket = _BUCKETS[idx + 1]
        else:
            ideas[bucket] = int(ideas.get(bucket) or 0) + 1
    elif intent == "new":
        ideas[bucket] = int(ideas.get(bucket) or 0) + 1
    else:
        ideas.setdefault(bucket, 0)
    state["bucket"] = bucket
    state["ideas"] = ideas
    return bucket, int(ideas.get(bucket) or 0)


def render_span_missions(
    st: Any,
    *,
    session_state: dict,
    improv_ctx: Any,
    scope: str,
    level: str,
    instrument: str,
    focus: str,
    bpm: int,
    focus_slot: Any = None,
    on_open_backing: Any = None,
    on_open_analysis: Any = None,
) -> None:
    from improvisation_intelligence_ui import SPAN_SONG_STYLE_STATE_KEY, _fill_mission_focus_slot, _render_span_picker
    from improvisation_motif import resolve_improv_section_rows
    from mission_span_engine import (
        MISSIONS_BY_ID,
        SPAN_MISSIONS,
        available_span_missions,
        generate_mission_span_example,
        unavailable_reason,
    )
    from span_motif_engine import _level

    lvl = _level(level)
    style = str(session_state.get(SPAN_SONG_STYLE_STATE_KEY) or "default")
    section_rows = resolve_improv_section_rows(session_state, improv_ctx)
    if not section_rows:
        st.warning("Select a song with chords first (Song Selection or Custom Progression).")
        return
    picked = _render_span_picker(
        st, session_state=session_state, improv_ctx=improv_ctx, section_rows=section_rows, scope=scope, level=lvl,
        widget_key_prefix=MISSION_SPAN_WIDGET_PREFIX, state_key=MISSION_SPAN_SELECTION_STATE_KEY,
    )
    if picked is None:
        return
    span, project, concert_key = picked

    missions = available_span_missions(span, level=lvl, style=style)
    if not missions:
        st.info("No Mission fits this span at your level — try another span.")
        return
    ids = [m.id for m in missions]
    state = session_state.get(SPAN_MISSION_STATE_KEY)
    state = dict(state) if isinstance(state, dict) else {}
    # The widget key is dropped whenever Missions is not on screen (Backing, other tabs);
    # the non-widget mirror keeps the player's Mission so the example survives the trip.
    stored_pick = session_state.get(SPAN_MISSION_PICK_KEY)
    if stored_pick is None:
        stored_pick = session_state.get(SPAN_MISSION_CHOICE_KEY)
    if stored_pick is not None and stored_pick not in ids:
        stored_pick = None
        session_state.pop(SPAN_MISSION_PICK_KEY, None)
    default = stored_pick if stored_pick in ids else ids[0]
    mission_id = st.selectbox(
        "Choose a mission",
        ids,
        index=ids.index(default),
        format_func=lambda mid: MISSIONS_BY_ID[mid].label,
        key=SPAN_MISSION_PICK_KEY,
    )
    if mission_id not in ids:
        mission_id = default
    session_state[SPAN_MISSION_CHOICE_KEY] = mission_id
    mission = MISSIONS_BY_ID[mission_id]
    hidden = [(m, unavailable_reason(m, span, level=lvl, style=style)) for m in SPAN_MISSIONS if m.id not in ids]
    if hidden:
        shown = "; ".join(f"{m.label} ({why})" for m, why in hidden[:3])
        more = f" and {len(hidden) - 3} more" if len(hidden) > 3 else ""
        st.caption(f"Not offered on this span: {shown}{more}.")

    chart_chords = [project(c) for c in span.chords]
    if focus_slot is not None:
        _fill_mission_focus_slot(
            focus_slot, session_state, level=lvl, instrument=instrument, focus=focus, mission=mission.label,
            scope=scope, chords=chart_chords, relationship=span.relationship if span.relationship_label else "",
        )

    st.markdown("##### Mission instructions")
    st.markdown(f"**{html.escape(mission.label)}** — {html.escape(mission.brief)}")
    st.caption("Improvise freely — you are not required to copy any example notes.")

    # span_id is transposition-invariant, so a Practice Key change keeps this Mission
    # example (re-projected below) instead of throwing it away.
    context = span_mission_context(mission.id, span.span_id, lvl, getattr(improv_ctx, "song_title", ""), style)
    if state.get("context") != context:
        handoff = state.get("ami_handoff")
        if (
            isinstance(handoff, dict) and isinstance(state.get("example"), dict) and handoff.get("mission_id") == mission.id
            and (tuple(handoff.get("chords") or ()), str(handoff.get("section") or "")) == (tuple(span.chords), span.section_label)
        ):
            # An AMI example for this Mission on this very span (same chords, same section): this page now owns it as it
            # is. Only the span's id is re-pointed at the span object this page uses; the notes and rhythm are untouched.
            state["context"] = context
            adopt_ami_example_span_id(state["example"], span)
        else:
            state = {"context": context, "bucket": "normal", "ideas": {}, "history": []}

    intent = ""
    with st.container(key="improv_span_mission_actions"):
        g1, g2, g3, g4 = st.columns(4)
        for col, label, key, kind, value in (
            (g1, "Generate example", "improv_span_mission_gen", "primary", "generate"),
            (g2, "Easier example", "improv_span_mission_easier", "secondary", "easier"),
            (g3, "Harder example", "improv_span_mission_harder", "secondary", "harder"),
            (g4, "New idea", "improv_span_mission_new", "secondary", "new"),
        ):
            with col:
                if st.button(label, key=key, type=kind, use_container_width=True):
                    intent = value
    if intent:
        bucket, idea = span_mission_intent(state, context=context, intent=intent)
        history = list(state.get("history") or [])
        example = generate_mission_span_example(
            mission, span, level=lvl, variant=bucket, instrument=instrument, idea=idea, style=style, focus=focus,
            avoid=[h for h in history if h.get("difficulty") == bucket][-3:] if intent == "new" else (),
        )
        example["handoff"]["practice_key"] = str(concert_key or "")
        state["example"] = example
        state.pop("ami_handoff", None)  # a page-made example replaces the AMI one
        state["history"] = (history + [{"motif": example["motif"], "difficulty": bucket}])[-6:]
    session_state[SPAN_MISSION_STATE_KEY] = state

    example = state.get("example")
    _store_span_recording_context(
        session_state, span=span, scope=scope, mission=mission, concert_key=concert_key,
        chart_chords=chart_chords, instrument=instrument, level=lvl, style=style, focus=focus,
        example=example if isinstance(example, dict) else None,
    )
    if not isinstance(example, dict):
        st.info("Click **Generate example** to hear one way to carry this Mission through the changes.")
    else:
        _render_span_mission_example(
            st, session_state=session_state, span=span, example=example, project=project, concert_key=concert_key,
            instrument=instrument, bpm=bpm, level=lvl, style=style, focus=focus, on_open_backing=on_open_backing,
        )
    _render_span_recording(st, session_state=session_state, on_open_analysis=on_open_analysis)


def _store_span_recording_context(
    session_state: dict, *, span: Any, scope: str, mission: Any, concert_key: str, chart_chords: list[str],
    instrument: str, level: str, style: str, focus: str, example: dict[str, Any] | None,
) -> None:
    """MC4: the span this Mission is on — what a live / uploaded take will be analyzed against."""
    from improvisation_intelligence_ui import _coherent_improv_key_pair_for_concert
    from mission_span_recording_context import store_span_recording_base

    try:
        _, chart_key = _coherent_improv_key_pair_for_concert(session_state, concert_key)
    except Exception:
        chart_key = concert_key
    store_span_recording_base(
        session_state, span=span, scope=scope, mission_id=mission.id, mission_label=mission.label,
        concert_key=concert_key, chart_key=chart_key, chart_chords=chart_chords, instrument=instrument,
        level=level, style=style, focus=focus, example=example,
    )


def _render_span_recording(st: Any, *, session_state: dict, on_open_analysis: Any = None) -> None:
    """The same optional Mission Live Recording expander the one-chord Missions use."""
    from mission_upload_recording_ui import MISSIONS_RECORDING_KEY_PREFIX, render_mission_recording_upload_expander

    def _open_upload_analysis() -> None:
        if not on_open_analysis:
            return
        from mission_analysis_ui import prepare_mission_upload_from_missions

        # The span take is sealed by the handoff; the one-chord Mission name is left untouched.
        prepare_mission_upload_from_missions(session_state)
        on_open_analysis()

    st.markdown("---")
    try:
        render_mission_recording_upload_expander(
            st, session_state, key_prefix=f"{MISSIONS_RECORDING_KEY_PREFIX}_span",
            on_open_upload_analysis=_open_upload_analysis if on_open_analysis else None,
        )
    except Exception as exc:  # the optional recorder must never take the Mission down
        import logging

        logging.getLogger(__name__).exception("span mission recording expander failed: %r", exc)


def span_example_projection(
    example: dict[str, Any], span: Any, *, concert_key: str, chart_key: str, project: Any,
) -> tuple[dict[str, Any], list[str], str, bool]:
    """The stored example as the player sees it now: (motif, chords, abc key, re-read?).

    The example was generated at the Practice Key of its click; a later Practice Key change
    moves it by the nearest interval, then the written / shape chart projection applies.
    """
    from mission_span_backing import key_change_semitones
    from music_theory import semitone_distance
    from span_motif_engine import project_span_motif

    motif = example["motif"]
    made_in = str((example.get("handoff") or {}).get("practice_key") or concert_key or "")
    key_shift = key_change_semitones(made_in, concert_key) if made_in and concert_key else 0
    shift = key_shift + (semitone_distance(concert_key, chart_key) or 0)
    timeline = [t["chord"] for t in motif.get("chord_timeline") or []]
    span_map = dict(zip(timeline, span.chords)) if key_shift else {}
    shown = project_span_motif(
        motif, semitones=shift, chart_key=chart_key, project_chord=lambda c: project(span_map.get(c, c)),
    )
    chords = [project(span_map.get(c, c)) for c in timeline]
    abc_key = span.key_center if not shift else chart_key
    return shown, chords, abc_key, bool(shift)


def _render_span_mission_example(
    st: Any,
    *,
    session_state: dict,
    span: Any,
    example: dict[str, Any],
    project: Any,
    concert_key: str,
    instrument: str,
    bpm: int,
    level: str,
    style: str,
    focus: str = "",
    on_open_backing: Any = None,
) -> None:
    from improvisation_intelligence_ui import (
        _coherent_improv_key_pair_for_concert,
        _focus_expression_abc,
        _render_motif_sheet_music,
        _render_span_motif_card,
    )
    from improvisation_motif import build_motif_abc, build_motif_guitar_tab, notation_clef_for_instrument
    from mission_span_engine import validate_mission_line
    from span_choice_display import span_heading

    motif = example["motif"]
    _, chart_key = _coherent_improv_key_pair_for_concert(session_state, concert_key)
    shown, chords, abc_key, reread = span_example_projection(
        example, span, concert_key=concert_key, chart_key=chart_key, project=project,
    )

    st.markdown("---")
    bucket = _BUCKET_LABELS.get(str(example.get("difficulty")), "Normal")
    st.markdown(
        f"##### Mission example · {html.escape(level)} · {bucket}"
        + (f" · idea {int(example.get('idea') or 0) + 1}" if int(example.get("idea") or 0) else "")
    )
    # What the Mission is, and what harmonic situation it is practised in.
    seq = " → ".join(project(c) for c in span.chords)
    st.markdown(
        '<div class="mc-mission-head">'
        f'<div><strong>Mission:</strong> {html.escape(str(example.get("mission_label") or ""))}</div>'
        f"<div><strong>{html.escape(span_heading(span.relationship_label, [project(c) for c in span.chords]))}</strong>"
        + (f' <span class="mc-mission-head-chords">({html.escape(seq)})</span>' if span.relationship_label else "")
        + "</div></div>",
        unsafe_allow_html=True,
    )
    # The Mission evidence, re-read in the chart the player sees (written key / shape key).
    report = validate_mission_line(
        example["mission_id"], shown, span, level=level, style=style, key=abc_key if reread else None,
        chords=chords if reread else None,
    )
    lines = [f"• **{html.escape(ev['where'])}** — {html.escape(ev['text'])}" for ev in report.evidence()]
    if lines:
        st.markdown("**Where the Mission happens**  \n" + "  \n".join(lines))
    if example.get("common_scale") and not reread:
        cs = example["common_scale"]
        st.caption(f"Common scale: {cs['name']} — {'–'.join(cs['notes'])}")
    if not report.valid:
        st.caption("This idea only partly shows the Mission — try New idea.")
    _render_span_motif_card(st, shown, key=abc_key, chords=chords, seed_motif=None, concert=motif)
    abc = build_motif_abc(
        shown,
        key_center=abc_key,
        bpm=bpm,
        title=f"Mission: {example.get('mission_label') or ''}",
        clef=notation_clef_for_instrument(instrument),
    )
    abc, expression_note = _focus_expression_abc(session_state, abc, shown, instrument=instrument, level=level)
    session_state[SPAN_MISSION_ABC_KEY] = abc
    if expression_note:
        st.caption(expression_note)
    _render_motif_sheet_music(st, abc)
    if "guitar" in str(instrument or "").lower():
        st.markdown("**Guitar TAB**")
        st.code(build_motif_guitar_tab(shown), language=None)
    _render_span_mission_backing(
        st, session_state=session_state, span=span, example=example, project=project, concert_key=concert_key,
        instrument=instrument, bpm=bpm, level=level, style=style, focus=focus, on_open_backing=on_open_backing,
    )


def _render_span_mission_backing(
    st: Any,
    *,
    session_state: dict,
    span: Any,
    example: dict[str, Any],
    project: Any,
    concert_key: str,
    instrument: str,
    bpm: int,
    level: str,
    style: str,
    focus: str,
    on_open_backing: Any,
) -> None:
    """Jam / Practice in Backing Jam for the span, through the one-chord Mission handoff."""
    if on_open_backing is None:
        return
    from improvisation_intelligence_ui import nav_icon_button_label
    from span_choice_display import span_heading

    st.markdown("---")
    heading = span_heading(span.relationship_label, [project(c) for c in span.chords])
    with st.container(key="improv_span_mission_backing_row"):
        practice_lick = st.checkbox(
            "Practice this example in Backing Jam",
            value=True,
            key="improv_span_mission_practice_lick_toggle",
            help="Backing loops this span; the example is shown for reference — not required.",
        )

        def _go() -> None:
            start_span_mission_backing(
                session_state, example=example, heading=heading, section_label=str(span.section_label or ""),
                practice_key=str(concert_key or ""),
                with_practice_lick=bool(session_state.get("improv_span_mission_practice_lick_toggle", True)),
                instrument=instrument, level=level, style=style, focus=focus, bpm=bpm,
                relationship_label=str(span.relationship_label or ""),
            )

        st.button(
            "▶ Practice in Backing Jam" if practice_lick else nav_icon_button_label("backing") + " Jam",
            key="improv_span_mission_backing",
            type="primary",
            use_container_width=True,
            on_click=_go,
            help=f"Loops {' → '.join(project(c) for c in span.chords)}",
        )
    st.caption("Backing loops the whole span. Record or upload a take of this span below.")


def start_span_mission_backing(
    session_state: dict,
    *,
    example: dict[str, Any],
    heading: str,
    section_label: str,
    practice_key: str,
    with_practice_lick: bool,
    instrument: str,
    level: str,
    style: str,
    focus: str,
    bpm: int,
    relationship_label: str = "",
) -> None:
    """Stage the span, then the same Mission Backing click intent as one-chord Missions.

    The intent carries the *single-chord* Mission state exactly as it is (never retargeted),
    so the Mission owner, its Practice Key seal and the return route are the existing ones.
    """
    from mission_span_backing import stage_span_backing
    from music_workflow_mission_backing_click import capture_mission_backing_click_intent

    # The timeline chords are spelled in the key the example was generated in; the live
    # Mission Practice Key (sealed by the handoff below) may already be another one.
    chords_key = str((example.get("handoff") or {}).get("practice_key") or practice_key or "")
    stage_span_backing(
        session_state, example=example, mission_label=str(example.get("mission_label") or ""),
        span_heading=heading, section_label=section_label, practice_key=chords_key,
        with_practice_lick=with_practice_lick, instrument=instrument, level=level, style=style, focus=focus,
        bpm=bpm, relationship_label=relationship_label,
    )
    try:
        from creative_chord_selection_authority import read_authoritative_mission_chord_selection

        chord, section, idx = read_authoritative_mission_chord_selection(session_state)
    except ImportError:
        chord = str(session_state.get("ii_selected_chord") or "")
        section = str(session_state.get("ii_selected_section") or "")
        idx = int(session_state.get("ii_selected_chord_index") or 0)
    if not str(chord or "").strip():
        # No one-chord selection yet: the span's first chord seeds the Mission chord identity.
        first = list((example.get("motif") or {}).get("span_chords") or [""])
        chord = str(first[0] if first else "")
        section = section_label
    # A span Mission owns its own picker/state. Falling back to the single-chord
    # Mission keys made a fresh AMI-opened span return with no identity (or with a
    # stale earlier Mission), allowing page restoration to resurrect stale output.
    mission = str(example.get("mission_label") or example.get("mission_id") or "").strip()
    capture_mission_backing_click_intent(
        session_state,
        with_practice_lick=False,  # the span example travels in its own payload
        mission=mission,
        cur_chord=str(chord or ""),
        section_label=str(section or ""),
        chord_idx=int(idx or 0),
        song_title=str(session_state.get("song") or ""),
        concert_key=str(practice_key or ""),
        display_key=str(session_state.get("display_key") or ""),
    )
    # The generic handoff seals its return destination only after aligning a
    # single-chord Mission. A span deliberately has no such single-chord state,
    # so seal the same destination contract from the span's authoritative
    # identity now. Practice-Key changes update this sealed destination through
    # the existing Mission Backing key-sync path.
    try:
        from mission_backing_alignment import build_mission_backing_alignment_payload
        from mission_return_destination import (
            build_mission_return_destination,
            seal_mission_return_destination,
        )

        alignment = build_mission_backing_alignment_payload(
            session_state, mission=mission, cur_chord=str(chord or ""), section_label=str(section or ""),
            chord_idx=int(idx or 0), song_title=str(session_state.get("song") or ""),
            concert_key=str(practice_key or ""), display_key=str(session_state.get("display_key") or ""),
            with_practice_lick=False, backing_scope="mission_span",
        )
        seal_mission_return_destination(
            session_state,
            build_mission_return_destination(
                alignment, handoff_mode="mission_span_backing", with_practice_lick=False,
            ),
        )
    except ImportError:
        pass
    try:
        from music_workflow_pending_backing_handoff import mission_backing_click_must_defer

        session_state["_mission_backing_click_must_defer"] = mission_backing_click_must_defer(session_state)
    except ImportError:
        pass


__all__ = [
    "MISSION_SPAN_SELECTION_STATE_KEY",
    "MISSION_TARGET_SCOPE_STATE_KEY",
    "SPAN_MISSION_ABC_KEY",
    "SPAN_MISSION_CHOICE_KEY",
    "SPAN_MISSION_PICK_KEY",
    "SPAN_MISSION_STATE_KEY",
    "render_mission_target_scope",
    "render_span_missions",
    "span_example_projection",
    "start_span_mission_backing",
    "span_mission_intent",
]
