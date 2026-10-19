"""Resolve the active musical context for an AMI exercise request (read-only).

Key authority, in order:

1. a key the user named in the request;
2. the Mission Practice/Concert Key, while a Mission surface owns the visit;
3. the normal Practice / chart key;
4. ``C``.

The catalog's saved/original key is recorded as a candidate but never overrides 2 or 3. Nothing here
mutates the session: the Mission key resolver writes a legacy mirror key, so it is run on a copy.
"""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.exercise_model import ActiveContext, ExerciseIntent


def _clean(value: object) -> str:
    return str(value or "").strip()


def normalize_key_token(token: object) -> str:
    """"A minor" / "a min" / "Am" → "Am"; "C major" / "C" → "C"."""
    text = _clean(token)
    if not text:
        return ""
    m = re.match(r"^([A-Ga-g])([#b♯♭]?)\s*(major|maj|minor|min|m)?$", text, re.I)
    if not m:
        return text
    root = m.group(1).upper() + {"♯": "#", "♭": "b"}.get(m.group(2), m.group(2))
    word = _clean(m.group(3))
    minor = word.lower() in ("minor", "min") or word == "m"
    return root + ("m" if minor else "")


def key_mode(token: str) -> str:
    return "minor" if normalize_key_token(token).endswith("m") else "major"


def key_tonic(token: str) -> str:
    return normalize_key_token(token).rstrip("m") or "C"


def _session_copy(session_ref: Any) -> dict[str, Any]:
    try:
        from music_coach_ami.session_access import as_mutable_session

        raw = as_mutable_session(session_ref)
    except ImportError:
        raw = session_ref
    try:
        return dict(raw) if raw is not None else {}
    except Exception:
        return {}


def mission_context(session_ref: Any) -> dict[str, Any]:
    """Is a Mission surface active, and what do the Mission authorities say? (on a copy of the session)."""
    session = _session_copy(session_ref)
    active = False
    try:
        from mission_owner_contract import missions_surface_owns

        active = bool(missions_surface_owns(session))
    except Exception:
        tab = _clean(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab"))
        active = _clean(session.get("studio_page")).lower() == "creative" and tab == "Missions"
    if not active:
        return {"active": False}
    key = ""
    try:
        from creative_key_sync import canonical_mission_practice_key

        key = _clean(canonical_mission_practice_key(session))
    except Exception:
        key = _clean(session.get("display_key") or session.get("concert_key"))
    mission = _clean(session.get("improv_active_mission") or session.get("improv_mission_pick"))
    return {
        "active": True,
        "key": normalize_key_token(key),
        "mission": mission,
        "chord": _clean(session.get("ii_selected_chord")),
        "section": _clean(session.get("ii_selected_section")),
    }


def resolve_active_context(
    req: Any,
    idea: Any,
    intent: ExerciseIntent,
    *,
    session_ref: Any,
    chart: dict[str, Any],
    instrument: str,
    notation_instrument: str,
    section_label: str,
    section_chords: list[str],
    bpm: int,
    meter: str,
) -> tuple[ActiveContext, Any]:
    """Return (``ActiveContext``, ``WrittenMusicContext``)."""
    from music_coach_ami.written_music_context import build_written_music_context

    ctx = req.context
    mission = mission_context(session_ref)
    chart_key = normalize_key_token(chart.get("practice_key") or ctx.current_practice_key)
    original_key = normalize_key_token(ctx.song_original_key)

    candidates: dict[str, str] = {}
    if chart_key:
        candidates["practice_chart_key"] = chart_key
    if original_key:
        candidates["catalog_original_key"] = original_key
    if mission.get("active") and mission.get("key"):
        candidates["mission_practice_key"] = _clean(mission["key"])

    if intent.explicit_key:
        concert_key, source = normalize_key_token(intent.explicit_key), "explicit_request"
    elif mission.get("active") and mission.get("key"):
        concert_key, source = _clean(mission["key"]), "mission_practice_key"
    elif chart_key:
        concert_key, source = chart_key, "practice_chart_key"
    else:
        concert_key, source = "C", "default"
    losers = {k: v for k, v in candidates.items() if v != concert_key or k.startswith("catalog")}

    if mission.get("active") and mission.get("chord"):
        selected, chord_source = _clean(mission["chord"]), "mission_selected_chord"
    elif _clean(ctx.current_chord):
        selected, chord_source = _clean(ctx.current_chord), "chart_current_chord"
    elif section_chords:
        selected, chord_source = _clean(section_chords[0]), "chart_current_chord"
    else:
        selected, chord_source = "", "none"

    level = _clean(intent.level_override)
    if level:
        level_source = "explicit_request"
    elif _clean(ctx.level):
        level, level_source = _clean(ctx.level), "context"
    else:
        level, level_source = "Intermediate", "default"

    written = build_written_music_context(
        instrument=instrument,
        practice_concert_key=concert_key,
        original_song_key=original_key or concert_key,
        concert_chords=[selected] if selected else [],
        session_state=_session_copy(session_ref),
        register=_clean(getattr(idea, "register", "")),
        chart_already_in_practice_key=True,
        chart_source=_clean(chart.get("chart_source")),
    )
    sources = {
        "concert_key": source,
        "level": level_source,
        "chord": chord_source,
        "instrument": "context",
        "meter": "explicit_request" if intent.explicit_fields.get("meter") else "context",
        "tempo_bpm": "explicit_request" if _clean(getattr(idea, "tempo_bpm", "")) else "context",
    }
    active = ActiveContext(
        concert_key=concert_key,
        key_source=source,
        key_candidates=losers,
        written_key=_clean(written.written_key),
        written_transposition_applied=bool(written.written_transposition_applied),
        transposition_semitones=int(written.transposition_semitones or 0),
        instrument=instrument,
        notation_instrument=notation_instrument,
        song_title=_clean(ctx.active_song_title),
        section=section_label,
        selected_chord=selected,
        chord_source=chord_source,
        mission_active=bool(mission.get("active")),
        active_mission=_clean(mission.get("mission")) if mission.get("active") else "",
        level=level,
        level_source=level_source,
        style=_clean(getattr(idea, "style", "")),
        meter=meter or "4/4",
        tempo_bpm=int(bpm or 96),
        practice_focus=_clean(ctx.practice_focus),
        span=None,
        field_sources=sources,
    )
    return active, written
