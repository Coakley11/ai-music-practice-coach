"""Music Coach semantic fingerprint — context-aware duplicate identity."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def _clean(text: object) -> str:
    return str(text or "").strip()


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", _clean(text).lower())


def _short_hash(text: str) -> str:
    blob = _norm(text)
    if not blob:
        return ""
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]


# Ordered dimensions that materially change a musical generation answer.
MUSIC_COACH_FP_DIMENSIONS: tuple[str, ...] = (
    "normalized_question",
    "pick_key",
    "song_title",
    "section",
    "practice_key",
    "instrument",
    "level",
    "focus",
    "current_chord",
    "progression_digest",
    "musical_object",
    "explicit_key",
    "explicit_difficulty",
    "explicit_register",
    "explicit_style",
    "capo_enabled",
    "capo_shape_key",
    "written_key_hint",
    "duration_minutes",
)


def _snap(ctx: dict[str, Any]) -> dict[str, Any]:
    snap = ctx.get("practice_snapshot")
    return snap if isinstance(snap, dict) else {}


def _active_song(ctx: dict[str, Any]) -> dict[str, Any]:
    active = ctx.get("active_song")
    return active if isinstance(active, dict) else {}


def _progression_digest(ctx: dict[str, Any]) -> str:
    """Stable digest of relevant harmony — not full raw session."""
    summary = _clean(ctx.get("progression_summary"))
    if summary:
        return _short_hash(summary)
    sections = ctx.get("chart_sections")
    if isinstance(sections, dict) and sections:
        parts: list[str] = []
        for name in sorted(sections.keys()):
            chords = sections.get(name) or []
            if isinstance(chords, list):
                parts.append(f"{name}:" + ",".join(_clean(c) for c in chords[:8]))
        if parts:
            return _short_hash("|".join(parts))
    active = _active_song(ctx)
    for key in ("chart_sections", "sections"):
        raw = active.get(key)
        if isinstance(raw, dict) and raw:
            return _progression_digest({"chart_sections": raw})
        if isinstance(raw, list) and raw:
            return _short_hash(",".join(_clean(c) for c in raw[:12]))
    return ""


def _capo_fields(ctx: dict[str, Any]) -> tuple[str, str]:
    enabled = ctx.get("guitar_capo_enabled")
    if enabled is None:
        enabled = ctx.get("capo_enabled")
    shape = _clean(ctx.get("guitar_capo_shape_key") or ctx.get("capo_shape_key") or ctx.get("capo_shape"))
    if enabled in (True, 1, "1", "true", "True", "yes", "on"):
        return "1", shape
    if enabled in (False, 0, "0", "false", "False", "no", "off", None, ""):
        # Only include shape when capo is on — off+empty is the default.
        return "0", ""
    return _norm(enabled), shape


def _idea_fields(question: str, ctx: dict[str, Any]) -> dict[str, str]:
    try:
        from music_coach_ami.musical_idea_request import parse_musical_idea_request

        idea = parse_musical_idea_request(
            question,
            default_object="",
            practice_focus=_clean(ctx.get("focus") or ctx.get("practice_focus")),
            level=_clean(ctx.get("level")),
        )
        return {
            "musical_object": _norm(idea.object_type) or _infer_object(question),
            "explicit_key": _norm(idea.explicit_key),
            "explicit_difficulty": _norm(idea.difficulty),
            "explicit_register": _norm(idea.register),
            "explicit_style": _norm(idea.style),
        }
    except ImportError:
        return {
            "musical_object": _infer_object(question),
            "explicit_key": "",
            "explicit_difficulty": "",
            "explicit_register": "",
            "explicit_style": "",
        }


def _infer_object(question: str) -> str:
    low = _norm(question)
    if "walking bass" in low or "bass line" in low or "bassline" in low:
        return "bass_line"
    if "scale" in low:
        return "scale"
    if "lick" in low:
        return "lick"
    if "riff" in low:
        return "riff"
    if "phrase" in low:
        return "phrase"
    return "general"


def _duration_minutes(ctx: dict[str, Any], question: str) -> str:
    for key in ("requested_duration_minutes", "practice_minutes", "available_practice_minutes"):
        val = ctx.get(key)
        if val is not None and str(val).strip() != "":
            try:
                return str(int(val))
            except (TypeError, ValueError):
                return _norm(val)
    try:
        from music_coach_ami.entities import parse_duration_minutes

        mins = parse_duration_minutes(question)
        if mins:
            return str(int(mins))
    except ImportError:
        pass
    return ""


def music_coach_semantic_dimensions(
    question: str,
    resolved_context: dict[str, Any] | None,
) -> dict[str, str]:
    """Resolved musically material inputs used for duplicate identity."""
    ctx = dict(resolved_context or {})
    snap = _snap(ctx)
    active = _active_song(ctx)
    idea = _idea_fields(question, ctx)
    capo_enabled, capo_shape = _capo_fields(ctx)

    practice_key = _clean(
        ctx.get("display_key")
        or ctx.get("concert_key")
        or ctx.get("practice_key")
        or snap.get("display_key")
        or ""
    )
    instrument = _clean(ctx.get("instrument") or snap.get("instrument") or "")
    level = _clean(ctx.get("level") or snap.get("level") or "")
    focus = _clean(ctx.get("focus") or ctx.get("practice_focus") or snap.get("focus") or "")
    section = _clean(
        ctx.get("practice_focus_section")
        or ctx.get("active_section")
        or snap.get("practice_focus_section")
        or ""
    )
    pick = _clean(ctx.get("pick_key") or snap.get("pick_key") or active.get("pick_key") or "")
    title = _clean(active.get("title") or snap.get("title") or ctx.get("active_song_title") or "")
    chord = _clean(ctx.get("current_chord") or ctx.get("ii_selected_chord") or "")
    written = ""
    if _clean(ctx.get("written_key") or ctx.get("written_key_hint")):
        written = _clean(ctx.get("written_key") or ctx.get("written_key_hint"))
    else:
        pk_trace = ctx.get("practice_key_trace")
        if isinstance(pk_trace, dict):
            written = _clean(pk_trace.get("written_key"))


    return {
        "normalized_question": _norm(question),
        "pick_key": _norm(pick),
        "song_title": _norm(title),
        "section": _norm(section),
        "practice_key": _norm(practice_key),
        "instrument": _norm(instrument),
        "level": _norm(level),
        "focus": _norm(focus),
        "current_chord": _norm(chord),
        "progression_digest": _progression_digest(ctx),
        "musical_object": idea["musical_object"],
        "explicit_key": idea["explicit_key"],
        "explicit_difficulty": idea["explicit_difficulty"],
        "explicit_register": idea["explicit_register"],
        "explicit_style": idea["explicit_style"],
        "capo_enabled": capo_enabled,
        "capo_shape_key": _norm(capo_shape),
        "written_key_hint": _norm(written),
        "duration_minutes": _duration_minutes(ctx, question),
    }


def music_coach_semantic_fingerprint(
    question: str,
    resolved_context: dict[str, Any] | None = None,
) -> str:
    """Deterministic 12-char fingerprint from normalized musical semantics."""
    dims = music_coach_semantic_dimensions(question, resolved_context)
    parts = [f"{key}={dims.get(key, '')}" for key in MUSIC_COACH_FP_DIMENSIONS]
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def music_coach_fingerprint_diff(
    previous: dict[str, str] | None,
    current: dict[str, str] | None,
) -> list[str]:
    """Return dimension names that differ between two fingerprint payloads."""
    prev = previous or {}
    cur = current or {}
    changed: list[str] = []
    for key in MUSIC_COACH_FP_DIMENSIONS:
        if _norm(prev.get(key)) != _norm(cur.get(key)):
            changed.append(key)
    return changed
