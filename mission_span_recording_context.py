"""MC4 — the span block that 2- and 3-chord Missions add to recording + Upload Analysis.

The Missions page stores the span *identity* (Mission, song, span, concert chord timeline,
Practice Key, chart key, instrument, level) whenever a span Mission is on screen. The
transport (BPM, meter, loops, count-in) is merged in from the same session fields the
single-chord recorder already uses, so the backing panel controls both paths.

The block belongs to one song: a stored span for another song is never returned. A later
Practice Key change re-keys the concert timeline (nearest interval) instead of keeping the
pre-transposition chords. Single-chord Missions never read any of this.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Sequence

MISSION_SPAN_RECORDING_CONTEXT_KEY = "_mission_span_recording_context"
SPAN_CONTEXT_VERSION = 1
SPAN_SCOPES = ("span2", "span3")


# --------------------------------------------------------------------------- timeline


def build_timeline(events: Sequence[Any], *, meter: str) -> list[dict[str, Any]]:
    """Chart events (chord, bars) → slots with start/duration in bars and beats."""
    from songs.meter import meter_timing

    pulses = meter_timing(100, meter).pulses_per_bar
    out: list[dict[str, Any]] = []
    bar = 0
    for i, ev in enumerate(events):
        chord = str(getattr(ev, "chord", None) or (ev.get("chord") if isinstance(ev, dict) else "") or "").strip()
        bars = int(getattr(ev, "bars", None) or (ev.get("bars") if isinstance(ev, dict) else 1) or 1)
        bars = max(1, bars)
        out.append(
            {
                "index": i,
                "chord": chord,
                "start_bar": bar,
                "bars": bars,
                "start_beat": bar * pulses,
                "beats": bars * pulses,
            }
        )
        bar += bars
    return out


def retime_timeline(timeline: Sequence[dict[str, Any]], *, meter: str) -> list[dict[str, Any]]:
    """Recompute beat positions for a meter (chords and bar counts unchanged)."""
    return build_timeline([{"chord": t.get("chord"), "bars": t.get("bars")} for t in timeline], meter=meter)


def timeline_fingerprint(timeline: Sequence[dict[str, Any]]) -> str:
    blob = json.dumps([(str(t.get("chord") or ""), int(t.get("bars") or 1)) for t in timeline], separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def loop_geometry(timeline: Sequence[dict[str, Any]], *, bpm: int, meter: str) -> dict[str, Any]:
    from songs.meter import meter_timing

    timing = meter_timing(int(bpm or 100), meter)
    loop_bars = sum(int(t.get("bars") or 1) for t in timeline) or 1
    return {
        "loop_bars": loop_bars,
        "loop_beats": loop_bars * timing.pulses_per_bar,
        "loop_sec": round(loop_bars * timing.bar_sec, 4),
        "pulse_sec": round(timing.pulse_sec, 6),
        "bar_sec": round(timing.bar_sec, 6),
        "pulses_per_bar": timing.pulses_per_bar,
    }


def per_bar_chords(timeline: Sequence[dict[str, Any]]) -> list[str]:
    """One chord per bar — the backing generator plays one chord per list entry."""
    out: list[str] = []
    for t in timeline:
        out.extend([str(t.get("chord") or "")] * max(1, int(t.get("bars") or 1)))
    return [c for c in out if c]


# --------------------------------------------------------------------------- identity


def _song_session(session: dict[str, Any]) -> str:
    try:
        from mission_span_backing import _song_session as song_session

        return song_session(session)
    except ImportError:  # pragma: no cover
        return str(session.get("active_catalog_pick_key") or session.get("song") or "")


def _example_id(example: Any) -> str:
    if not isinstance(example, dict):
        return ""
    handoff = example.get("handoff") if isinstance(example.get("handoff"), dict) else {}
    if handoff.get("example_id"):
        return str(handoff["example_id"])
    motif = example.get("motif") if isinstance(example.get("motif"), dict) else {}
    blob = json.dumps([motif.get("midi"), example.get("difficulty"), example.get("idea")], default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _common_collection(span: Any) -> dict[str, Any] | None:
    try:
        from mission_span_engine import common_collection

        found = common_collection(span)
    except Exception:
        found = None
    if not found:
        return None
    name, pcs, notes = found
    return {"name": str(name), "pcs": [int(p) for p in pcs], "notes": list(notes)}


def store_span_recording_base(
    session: dict[str, Any],
    *,
    span: Any,
    scope: str,
    mission_id: str,
    mission_label: str,
    concert_key: str,
    chart_key: str,
    chart_chords: Sequence[str],
    instrument: str,
    level: str,
    style: str,
    focus: str,
    example: Any = None,
) -> dict[str, Any]:
    """What the Missions page knows about the span Mission on screen (no transport)."""
    events = list(getattr(span, "raw_events", None) or [])
    if not events:
        events = [{"chord": c, "bars": 1} for c in getattr(span, "chords", ())]
    timeline = build_timeline(events, meter="4/4")
    for t, shown in zip(timeline, list(chart_chords) or []):
        t["chart_chord"] = str(shown or t["chord"])
    base = {
        "version": SPAN_CONTEXT_VERSION,
        "scope": str(scope),
        "length": len(getattr(span, "chords", ()) or timeline),
        "mission_id": str(mission_id),
        "mission_label": str(mission_label),
        "song_title": str(session.get("song") or "").strip(),
        "song_session": _song_session(session),
        "pick_key": str(session.get("active_catalog_pick_key") or "").strip(),
        "span_id": str(getattr(span, "span_id", "") or ""),
        "section": str(getattr(span, "section_label", "") or ""),
        "relationship": str(getattr(span, "relationship", "") or ""),
        "relationship_label": str(getattr(span, "relationship_label", "") or ""),
        "span_key_center": str(getattr(span, "key_center", "") or concert_key or ""),
        "practice_key": str(concert_key or ""),
        "chart_key": str(chart_key or concert_key or ""),
        "instrument": str(instrument or ""),
        "level": str(level or ""),
        "style": str(style or "default"),
        "evaluation_focus": str(focus or ""),
        "example_id": _example_id(example),
        "timeline": timeline,
        "common_collection": _common_collection(span),
    }
    session[MISSION_SPAN_RECORDING_CONTEXT_KEY] = base
    return base


def clear_span_recording_base(session: dict[str, Any]) -> None:
    session.pop(MISSION_SPAN_RECORDING_CONTEXT_KEY, None)


def span_scope_active(session: dict[str, Any]) -> bool:
    try:
        from mission_span_ui import MISSION_TARGET_SCOPE_STATE_KEY
    except ImportError:  # pragma: no cover
        MISSION_TARGET_SCOPE_STATE_KEY = "_improv_mission_target_scope_choice"
    return str(session.get(MISSION_TARGET_SCOPE_STATE_KEY) or "") in SPAN_SCOPES


def _live_practice_key(session: dict[str, Any]) -> str:
    try:
        from songs.key_state import resolve_active_musical_key

        return str(resolve_active_musical_key(session).practice_concert_key or "").strip()
    except Exception:
        return str(session.get("concert_key") or session.get("display_key") or "").strip()


def _live_chart_key(session: dict[str, Any]) -> str:
    try:
        from songs.key_state import resolve_active_musical_key

        return str(resolve_active_musical_key(session).chart_key or "").strip()
    except Exception:
        return ""


def _chart_chord(chord: str, *, concert_key: str, chart_key: str) -> str:
    """Player-facing spelling (written / shape chart) of a concert chord."""
    if not chord or not concert_key or not chart_key or concert_key == chart_key:
        return chord
    try:
        from effective_practice_context import musician_facing_chord

        return str(musician_facing_chord(chord, concert_key=concert_key, chart_key=chart_key) or chord)
    except Exception:
        return chord


def _rekey(base: dict[str, Any], to_key: str) -> dict[str, Any]:
    """The same span at another Practice Key (nearest interval), chart spelling re-projected."""
    from mission_span_backing import _to_key, key_change_semitones

    from_key = str(base.get("practice_key") or "")
    if not from_key or not to_key or from_key == to_key or not key_change_semitones(from_key, to_key):
        return base
    out = copy.deepcopy(base)
    for t in out.get("timeline") or []:
        t["chord"] = _to_key(str(t.get("chord") or ""), from_key=from_key, to_key=to_key)
        t.pop("chart_chord", None)
    out["practice_key"] = to_key
    out["span_key_center"] = to_key
    out["chart_key"] = to_key
    coll = out.get("common_collection")
    if isinstance(coll, dict) and coll.get("pcs"):
        shift = key_change_semitones(from_key, to_key)
        coll["pcs"] = [(int(p) + shift) % 12 for p in coll["pcs"]]
        coll["name"] = ""
        coll["notes"] = []
    out["rekeyed_from"] = from_key
    return out


def current_span_base(session: dict[str, Any]) -> dict[str, Any] | None:
    """The stored span identity — only for the live song, re-keyed to the live Practice Key."""
    raw = session.get(MISSION_SPAN_RECORDING_CONTEXT_KEY)
    if not (isinstance(raw, dict) and raw.get("timeline") and raw.get("mission_id")):
        return None
    staged_for = str(raw.get("song_session") or "")
    if staged_for and staged_for != _song_session(session):
        return None  # another song's span never becomes this song's recording context
    live_key = _live_practice_key(session)
    if live_key and live_key != str(raw.get("practice_key") or ""):
        return _rekey(raw, live_key)
    return copy.deepcopy(raw)


def build_span_block(
    session: dict[str, Any], *, bpm: int, meter: str, loops: int, count_in_bars: int,
) -> dict[str, Any] | None:
    """Span identity + live transport (from the same fields as the one-chord recorder)."""
    if not span_scope_active(session):
        return None
    base = current_span_base(session)
    if base is None:
        return None
    meter = str(meter or "4/4")
    timeline = retime_timeline(base["timeline"], meter=meter)
    chart_key = _live_chart_key(session) or str(base.get("chart_key") or base.get("practice_key") or "")
    concert_key = str(base.get("practice_key") or "")
    for t, old in zip(timeline, base["timeline"]):
        t["chart_chord"] = _chart_chord(str(t["chord"]), concert_key=concert_key, chart_key=chart_key) or str(
            old.get("chart_chord") or t["chord"]
        )
    block = dict(base)
    block["chart_key"] = chart_key or concert_key
    block["timeline"] = timeline
    block["bpm"] = int(bpm or 100)
    block["meter"] = meter
    block["loops"] = max(1, int(loops or 1))
    block["count_in_bars"] = max(0, int(count_in_bars or 0))
    block.update(loop_geometry(timeline, bpm=block["bpm"], meter=meter))
    block["count_in_sec"] = round(block["count_in_bars"] * block["bar_sec"], 4)
    block["timeline_fingerprint"] = timeline_fingerprint(timeline)
    block["span_fingerprint"] = span_fingerprint(block)
    return block


def span_fingerprint(block: dict[str, Any]) -> str:
    """Identity that makes a span take stale when it changes (never UI-only state)."""
    payload = {
        "song": block.get("song_session") or block.get("pick_key"),
        "span": block.get("span_id"),
        "mission": block.get("mission_id"),
        "key": block.get("practice_key"),
        "timeline": block.get("timeline_fingerprint") or timeline_fingerprint(block.get("timeline") or []),
        "bpm": block.get("bpm"),
        "meter": block.get("meter"),
        "instrument": block.get("instrument"),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def span_stale_reasons(sealed: dict[str, Any], live: dict[str, Any] | None) -> list[str]:
    """Material differences between the span a take was made for and the live span."""
    if live is None:
        return ["the span Mission is no longer selected"]
    out: list[str] = []
    if (sealed.get("song_session") or sealed.get("pick_key")) != (live.get("song_session") or live.get("pick_key")):
        out.append("the song changed")
    if sealed.get("span_id") != live.get("span_id"):
        out.append("the chord span changed")
    if sealed.get("mission_id") != live.get("mission_id"):
        out.append(f"the Mission changed to “{live.get('mission_label')}”")
    if sealed.get("practice_key") != live.get("practice_key"):
        out.append(f"the Practice Key changed from {sealed.get('practice_key')} to {live.get('practice_key')}")
    if int(sealed.get("bpm") or 0) != int(live.get("bpm") or 0):
        out.append(f"tempo changed from {sealed.get('bpm')} to {live.get('bpm')} BPM")
    if sealed.get("meter") != live.get("meter"):
        out.append(f"meter changed from {sealed.get('meter')} to {live.get('meter')}")
    if sealed.get("instrument") != live.get("instrument"):
        out.append(f"instrument changed to {live.get('instrument')}")
    return out


# --------------------------------------------------------------------------- display


def span_chart_label(block: dict[str, Any]) -> str:
    chords = [str(t.get("chart_chord") or t.get("chord") or "") for t in block.get("timeline") or []]
    try:
        from span_motif_explain import pretty
    except ImportError:  # pragma: no cover
        pretty = str  # type: ignore[assignment]
    line = " → ".join(pretty(c) for c in chords if c)
    rel = str(block.get("relationship_label") or "").strip()
    return f"{line} · {rel}" if rel else line


def key_label(key: str) -> str:
    k = str(key or "").strip()
    if not k:
        return ""
    try:
        from span_motif_explain import pretty
    except ImportError:  # pragma: no cover
        pretty = str  # type: ignore[assignment]
    if k.endswith("m") and not k.endswith("maj"):
        return f"{pretty(k[:-1])} minor"
    return f"{pretty(k)} major"


def span_summary_rows(block: dict[str, Any]) -> list[tuple[str, str]]:
    """Player-facing summary shown before recording (no internal ids)."""
    bars = int(block.get("loop_bars") or 0)
    secs = float(block.get("loop_sec") or 0)
    length = f"{bars} bar{'s' if bars != 1 else ''}" + (f" (~{secs:.1f}s per loop)" if secs else "")
    practice, chart = str(block.get("practice_key") or ""), str(block.get("chart_key") or "")
    rows = [
        ("Mission", str(block.get("mission_label") or "")),
        ("Span", span_chart_label(block)),
        ("Practice key", key_label(practice)),
    ]
    if chart and chart != practice:
        guitar = "guitar" in str(block.get("instrument") or "").lower()
        rows.append(("Capo shape key" if guitar else "Written key", key_label(chart)))
    return rows + [
        ("Tempo", f"{int(block.get('bpm') or 0)} BPM"),
        ("Meter", str(block.get("meter") or "4/4")),
        ("Length", length),
    ]


__all__ = [
    "MISSION_SPAN_RECORDING_CONTEXT_KEY",
    "SPAN_SCOPES",
    "build_span_block",
    "build_timeline",
    "clear_span_recording_base",
    "current_span_base",
    "key_label",
    "loop_geometry",
    "per_bar_chords",
    "span_chart_label",
    "span_fingerprint",
    "span_scope_active",
    "span_stale_reasons",
    "span_summary_rows",
    "store_span_recording_base",
    "timeline_fingerprint",
]
