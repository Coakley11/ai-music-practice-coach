"""Resolve the active musical context for an AMI exercise request (read-only).

Key authority, in order:

1. a key the user named in the request;
2. the Mission Practice/Concert Key, **only while a Mission is actively authoritative for this request**;
3. the normal Practice / chart key;
4. ``C``.

Chord authority, in order: a chord named in the request; a chord built from a collection the request
names; the active Mission's chord (same condition as 2); the first chord of the active chart section;
the tonic chord of the effective key. A stale Mission selection (``ii_selected_chord`` and friends) is
never read outside an active Mission.

"A Mission is actively authoritative" needs BOTH

* surface evidence — the user is on a Mission-owned surface right now: Creative → Missions tab, or the
  Backing page while Mission owns the backing; and
* engagement evidence — the user took a deliberate Mission action: generated a Mission example for the
  open Mission, has live Mission-owned backing, or the request itself refers to the Mission ("this
  Mission", "my Mission", "the Mission chord"...). The Creative page seeds a default chord selection, a
  "chord click" record and a snapshot on its own, so those are not evidence.

Missions merely being the default Creative tab, leftover Mission keys in session, or an earlier visit
are not authority. Nothing here mutates the session: the Mission key resolver writes a legacy mirror
key, so it runs on a copy.
"""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.exercise_model import ActiveContext, ExerciseIntent

_MISSION_MENTION_RE = re.compile(
    r"\b(?:this|my|the (?:current|selected|open|active))\s+mission\b|\bmission (?:chord|key)\b|\bselected mission\b",
    re.I,
)


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


def _open_mission_id(session: dict[str, Any]) -> str:
    return _clean(session.get("improv_active_mission") or session.get("improv_mission_pick"))


def _mission_surface(session: dict[str, Any]) -> str:
    """Which Mission-owned surface the user is on right now ('' when none)."""
    page = _clean(session.get("studio_page")).lower()
    tab = _clean(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab"))
    if page == "creative" and tab == "Missions":
        return "creative_missions_tab"
    if page == "backing":
        try:
            from mission_owner_contract import live_backing_owner_is_mission

            if live_backing_owner_is_mission(session):
                return "mission_backing"
        except Exception:
            pass
    return ""


def _engagement(session: dict[str, Any], question: str) -> list[str]:
    """Deliberate actions that show the user engaged a Mission.

    A recorded "chord click" or chord snapshot is NOT evidence: the Creative page writes both itself,
    with a default chord, as soon as the Missions tab is shown. Likewise ``ii_selected_chord``.
    """
    evidence: list[str] = []
    example = session.get("improv_mission_example")
    open_id = _open_mission_id(session)
    if isinstance(example, dict) and _clean(example.get("mission")) and (
        not open_id or _clean(example.get("mission")) == open_id
    ):
        evidence.append("generated_example")
    try:
        from mission_owner_contract import live_backing_owner_is_mission

        if live_backing_owner_is_mission(session):
            evidence.append("mission_backing_live")
    except Exception:
        pass
    if _MISSION_MENTION_RE.search(question or ""):
        evidence.append("request_mentions_mission")
    return evidence


def mission_authority(session_ref: Any, question: str = "") -> dict[str, Any]:
    """Is a Mission actively authoritative for this request, and what does it say? (read-only)."""
    session = _session_copy(session_ref)
    surface = _mission_surface(session)
    if not surface:
        return {"active": False, "reason": "not on a Mission-owned surface"}
    evidence = _engagement(session, question)
    if not evidence:
        return {
            "active": False,
            "surface": surface,
            "reason": "on a Mission surface but no Mission engaged (default tab, nothing selected or generated)",
        }
    key = ""
    try:
        from creative_key_sync import canonical_mission_practice_key

        key = _clean(canonical_mission_practice_key(session))
    except Exception:
        key = _clean(session.get("display_key") or session.get("concert_key"))
    chord = _clean(session.get("ii_selected_chord"))
    return {
        "active": True,
        "surface": surface,
        "evidence": evidence,
        "key": normalize_key_token(key),
        "mission": _open_mission_id(session),
        "chord": chord,
        "chord_origin": "mission_selected_chord" if chord else "",
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
    mission = mission_authority(session_ref, intent.raw_question)
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

    chords = [_clean(c) for c in section_chords if _clean(c)]
    if mission.get("active") and mission.get("chord"):
        selected, chord_source = _clean(mission["chord"]), _clean(mission.get("chord_origin")) or "mission_selected_chord"
    elif chords:
        selected, chord_source = chords[0], "chart_active_section_first_chord"
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
        mission_authority={k: v for k, v in mission.items() if k != "key" or mission.get("active")},
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
