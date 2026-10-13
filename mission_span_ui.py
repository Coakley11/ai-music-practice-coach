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
MISSION_SPAN_WIDGET_PREFIX = "improv_mission_span_pick"
SPAN_MISSION_STATE_KEY = "improv_span_mission"
SPAN_MISSION_PICK_KEY = "improv_span_mission_pick"
SPAN_MISSION_ABC_KEY = "improv_span_mission_abc"
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
) -> None:
    from improvisation_intelligence_ui import SPAN_SONG_STYLE_STATE_KEY, _render_span_picker
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
    stored_pick = session_state.get(SPAN_MISSION_PICK_KEY)
    if stored_pick is not None and stored_pick not in ids:
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
    mission = MISSIONS_BY_ID[mission_id]
    hidden = [(m, unavailable_reason(m, span, level=lvl, style=style)) for m in SPAN_MISSIONS if m.id not in ids]
    if hidden:
        shown = "; ".join(f"{m.label} ({why})" for m, why in hidden[:3])
        more = f" and {len(hidden) - 3} more" if len(hidden) > 3 else ""
        st.caption(f"Not offered on this span: {shown}{more}.")

    st.markdown("##### Mission instructions")
    st.markdown(f"**{html.escape(mission.label)}** — {html.escape(mission.brief)}")
    st.caption("Improvise freely — you are not required to copy any example notes.")

    context = "|".join((mission.id, span.span_id, lvl, str(getattr(improv_ctx, "song_title", "") or ""), style))
    if state.get("context") != context:
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
        state["history"] = (history + [{"motif": example["motif"], "difficulty": bucket}])[-6:]
    session_state[SPAN_MISSION_STATE_KEY] = state

    example = state.get("example")
    if not isinstance(example, dict):
        st.info("Click **Generate example** to hear one way to carry this Mission through the changes.")
        return
    _render_span_mission_example(
        st, session_state=session_state, span=span, example=example, project=project, concert_key=concert_key,
        instrument=instrument, bpm=bpm, level=lvl, style=style,
    )


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
) -> None:
    from improvisation_intelligence_ui import (
        _coherent_improv_key_pair_for_concert,
        _render_motif_sheet_music,
        _render_span_motif_card,
    )
    from improvisation_motif import build_motif_abc, build_motif_guitar_tab, notation_clef_for_instrument
    from mission_span_engine import validate_mission_line
    from music_theory import semitone_distance
    from span_motif_engine import project_span_motif

    motif = example["motif"]
    _, chart_key = _coherent_improv_key_pair_for_concert(session_state, concert_key)
    shift = semitone_distance(concert_key, chart_key) or 0
    shown = project_span_motif(motif, semitones=shift, chart_key=chart_key, project_chord=project)
    abc_key = span.key_center if not shift else chart_key
    chords = [project(t["chord"]) for t in shown.get("chord_timeline") or []]

    st.markdown("---")
    bucket = _BUCKET_LABELS.get(str(example.get("difficulty")), "Normal")
    st.markdown(
        f"##### Mission example · {html.escape(level)} · {bucket}"
        + (f" · idea {int(example.get('idea') or 0) + 1}" if int(example.get("idea") or 0) else "")
    )
    # The Mission evidence, re-read in the chart the player sees (written key / shape key).
    report = validate_mission_line(
        example["mission_id"], shown, span, level=level, style=style, key=abc_key if shift else None,
        chords=chords if shift else None,
    )
    lines = [f"• **{html.escape(ev['where'])}** — {html.escape(ev['text'])}" for ev in report.evidence()]
    if lines:
        st.markdown("**Where the Mission happens**  \n" + "  \n".join(lines))
    if example.get("common_scale") and not shift:
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
    session_state[SPAN_MISSION_ABC_KEY] = abc
    _render_motif_sheet_music(st, abc)
    if "guitar" in str(instrument or "").lower():
        st.markdown("**Guitar TAB**")
        st.code(build_motif_guitar_tab(shown), language=None)


__all__ = [
    "MISSION_SPAN_SELECTION_STATE_KEY",
    "MISSION_TARGET_SCOPE_STATE_KEY",
    "SPAN_MISSION_ABC_KEY",
    "SPAN_MISSION_PICK_KEY",
    "SPAN_MISSION_STATE_KEY",
    "render_mission_target_scope",
    "render_span_missions",
    "span_mission_intent",
]
