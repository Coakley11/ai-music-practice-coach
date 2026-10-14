"""MC3.1 — 2 / 3-chord Missions in Mission Backing Jam, through the existing Mission handoff.

No parallel Backing system: the Jam click goes through the same
:func:`capture_mission_backing_click_intent` → Mission-owned handoff as a one-chord
Mission, carrying the *single-chord* Mission state unchanged (so single-chord Missions are
never retargeted). The span rides alongside in :data:`SPAN_BACKING_KEY`:

- :func:`build_mission_context` loops the span's chords (one entry per bar, from the
  example's chord timeline) instead of the one Mission chord;
- the Backing banner names the span (``Dm7 → G7 → Cmaj7``);
- "Practice this lick" shows the span example (its own payload, :data:`SPAN_LICK_KEY`,
  never the single-chord lick payload).

The span chords are stored at the concert Practice Key of the handoff. Whenever the
Mission Practice Key moves (inside Backing too), they are transposed to it and then
projected to the player's chart through the app's own projection
(:func:`effective_practice_context.musician_facing_chord`), exactly like the one-chord
Mission chord. A one-chord Jam click clears the span payload.
"""

from __future__ import annotations

from typing import Any

SPAN_BACKING_KEY = "_mission_span_backing"
SPAN_LICK_KEY = "improv_span_mission_lick"


def stage_span_backing(
    session: dict[str, Any],
    *,
    example: dict[str, Any],
    mission_label: str,
    span_heading: str,
    section_label: str,
    practice_key: str,
    with_practice_lick: bool,
    instrument: str,
    level: str,
    style: str,
    focus: str,
    bpm: int,
    relationship_label: str = "",
) -> dict[str, Any]:
    """Record the span Mission the next Mission Backing Jam should loop."""
    handoff = dict(example.get("handoff") or {})
    timeline = [
        {"chord": str(t.get("chord") or ""), "bars": int(t.get("bars") or 1)}
        for t in (handoff.get("chord_timeline") or (example.get("motif") or {}).get("chord_timeline") or [])
    ]
    payload = {
        "active": True,
        "mission_id": str(example.get("mission_id") or ""),
        "mission_label": str(mission_label or example.get("mission_label") or ""),
        "span_id": str(example.get("span_id") or handoff.get("span_id") or ""),
        "span_heading": str(span_heading or ""),
        "relationship_label": str(relationship_label or ""),
        "level": str(level or ""),
        "section_label": str(section_label or ""),
        "timeline": timeline,
        "practice_key": str(practice_key or handoff.get("practice_key") or ""),
        "example_id": str(handoff.get("example_id") or ""),
        "meter": str(handoff.get("meter") or "4/4"),
        "loop_bars": int(handoff.get("loop_bars") or sum(t["bars"] for t in timeline) or 1),
        "with_practice_lick": bool(with_practice_lick),
        "song_session": _song_session(session),
    }
    session[SPAN_BACKING_KEY] = payload
    if with_practice_lick:
        session[SPAN_LICK_KEY] = {
            "motif": dict(example.get("motif") or {}),
            "mission_label": payload["mission_label"],
            "span_heading": payload["span_heading"],
            "section_label": payload["section_label"],
            "practice_key": payload["practice_key"],
            "instrument": str(instrument or ""),
            "level": str(level or ""),
            "style": str(style or "default"),
            "focus": str(focus or ""),
            "bpm": int(bpm or 100),
            "difficulty": str(example.get("difficulty") or "normal"),
            "example_id": payload["example_id"],
        }
    else:
        session.pop(SPAN_LICK_KEY, None)
    return payload


def clear_span_backing(session: dict[str, Any]) -> None:
    session.pop(SPAN_BACKING_KEY, None)
    session.pop(SPAN_LICK_KEY, None)


def _song_session(session: dict[str, Any]) -> str:
    """The live song's Mission session id (catalog / custom / composition) — the song identity."""
    try:
        from music_workflow_mission_session import mission_blob_session_id

        return str(mission_blob_session_id(session) or "")
    except Exception:
        return str(session.get("active_catalog_pick_key") or session.get("song") or "")


def active_span_backing(session: dict[str, Any]) -> dict[str, Any] | None:
    """The staged span — only while it belongs to the song that is active now."""
    raw = session.get(SPAN_BACKING_KEY)
    if not (isinstance(raw, dict) and raw.get("active") and raw.get("timeline")):
        return None
    staged_for = str(raw.get("song_session") or "")
    if staged_for and staged_for != _song_session(session):
        return None  # another song is active: this span (and its lick) no longer applies
    return raw


def key_change_semitones(from_key: str, to_key: str) -> int:
    """Nearest move between two Practice Keys (−5 … +6), so a line stays in register."""
    from music_theory import semitone_distance

    if not from_key or not to_key:
        return 0
    d = int(semitone_distance(from_key, to_key) or 0) % 12
    return d - 12 if d > 6 else d


def _to_key(chord: str, *, from_key: str, to_key: str) -> str:
    from effective_practice_context import musician_facing_chord

    if not from_key or not to_key:
        return chord
    return musician_facing_chord(chord, concert_key=from_key, chart_key=to_key)


def span_concert_chords(payload: dict[str, Any], concert_key: str) -> list[tuple[str, int]]:
    """(concert chord at the live Mission Practice Key, bars) per span chord."""
    src = str(payload.get("practice_key") or "")
    return [
        (_to_key(str(t["chord"]), from_key=src, to_key=concert_key), int(t.get("bars") or 1))
        for t in payload.get("timeline") or []
    ]


def span_chart_chords(session: dict[str, Any], payload: dict[str, Any], concert_key: str) -> list[tuple[str, int]]:
    """Player-facing (written / shape) chord per span slot, via the app's chart projection."""
    from effective_practice_context import musician_facing_chart_key, musician_facing_chord

    chart = musician_facing_chart_key(session, concert_key) if concert_key else ""
    out = []
    for chord, bars in span_concert_chords(payload, concert_key):
        shown = musician_facing_chord(chord, concert_key=concert_key, chart_key=chart) if chart else chord
        out.append((shown or chord, bars))
    return out


def span_backing_progression(session: dict[str, Any], payload: dict[str, Any], concert_key: str) -> list[str]:
    """Mission Backing loop: one chart chord per bar across the span."""
    return [chord for chord, bars in span_chart_chords(session, payload, concert_key) for _ in range(max(1, bars))]


def span_backing_label(session: dict[str, Any], payload: dict[str, Any], concert_key: str) -> str:
    return " → ".join(chord for chord, _bars in span_chart_chords(session, payload, concert_key))


def span_backing_summary(session: dict[str, Any], concert_key: str) -> dict[str, str] | None:
    """What every Mission Backing surface shows for an active span Mission — from the span
    handoff only (never the one-chord Mission name or selected chord).

    ``chords`` are projected to the live Mission Practice Key and the player's chart.
    """
    payload = active_span_backing(session)
    if payload is None:
        return None
    chords = span_backing_label(session, payload, concert_key)
    rel = str(payload.get("relationship_label") or "").strip()
    return {
        "mission": str(payload.get("mission_label") or "Mission"),
        "section": str(payload.get("section_label") or ""),
        "level": str(payload.get("level") or ""),
        "chords": chords,
        "relationship": rel,
        "span_line": f"{chords} · {rel}" if rel else chords,
        "span_id": str(payload.get("span_id") or ""),
        "example_id": str(payload.get("example_id") or ""),
    }


def render_span_lick_on_backing(st: Any, session: dict[str, Any], *, applied_bpm: int, concert_key: str) -> bool:
    """The span example on Backing Jam, rebuilt at the current tempo and Practice Key. True if shown."""
    payload = active_span_backing(session)
    lick = session.get(SPAN_LICK_KEY)
    if payload is None or not isinstance(lick, dict) or not lick.get("motif"):
        return False
    import html

    from effective_practice_context import musician_facing_chart_key
    from improvisation_motif import build_motif_abc, build_motif_guitar_tab, notation_clef_for_instrument
    from music_theory import semitone_distance
    from span_motif_engine import project_span_motif

    motif = dict(lick["motif"])
    src = str(lick.get("practice_key") or payload.get("practice_key") or concert_key or "C")
    live = str(concert_key or src)
    chart = musician_facing_chart_key(session, live) or live
    shift = key_change_semitones(src, live) + (semitone_distance(live, chart) or 0)
    mapping = dict(zip([str(t["chord"]) for t in payload.get("timeline") or []],
                       [c for c, _b in span_chart_chords(session, payload, live)]))
    shown = project_span_motif(motif, semitones=shift, chart_key=chart,
                               project_chord=lambda ch: mapping.get(ch, ch)) if shift else motif
    abc = build_motif_abc(
        shown, key_center=chart if shift else str(motif.get("key_center") or chart), bpm=int(applied_bpm or lick.get("bpm") or 100),
        title=f"Mission: {lick.get('mission_label') or ''}",
        clef=notation_clef_for_instrument(str(lick.get("instrument") or "")),
    )
    try:
        from phrase_expression import apply_focus_expression, expression_caption

        abc, plan = apply_focus_expression(
            abc, shown, focus=str(lick.get("focus") or ""), level=str(lick.get("level") or ""),
            instrument=str(lick.get("instrument") or ""), style=str(lick.get("style") or "default"),
        )
        note = expression_caption(plan)
    except Exception:
        note = ""
    summary = span_backing_summary(session, live) or {}
    section_bits = [b for b in (summary.get("section"), str(lick.get("level") or "")) if b]
    st.markdown("---")
    st.markdown(
        '<div class="ui-card soft mc-span-lick-card">'
        f'<p class="ui-card-sub"><strong>Mission:</strong> {html.escape(summary.get("mission") or "")}</p>'
        f'<p class="ui-card-sub"><strong>Span:</strong> {html.escape(summary.get("span_line") or "")}</p>'
        + (f'<p class="ui-card-sub"><strong>Section:</strong> {html.escape(" · ".join(section_bits))}</p>' if section_bits else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Notes:** `{shown.get('display', '')}`")
    if note:
        st.caption(note)
    from improvisation_intelligence_ui import _render_motif_sheet_music

    _render_motif_sheet_music(st, abc)
    if "guitar" in str(lick.get("instrument") or "").lower():
        st.markdown("**Guitar TAB**")
        st.code(build_motif_guitar_tab(shown), language=None)
    return True


__all__ = [
    "SPAN_BACKING_KEY",
    "SPAN_LICK_KEY",
    "active_span_backing",
    "clear_span_backing",
    "render_span_lick_on_backing",
    "span_backing_label",
    "span_backing_progression",
    "span_backing_summary",
    "span_chart_chords",
    "span_concert_chords",
    "stage_span_backing",
]
