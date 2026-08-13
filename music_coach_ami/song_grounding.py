"""Musician-facing song/section header for song-grounded AMI answers."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.types import CoachIntent, CoachRequest, CoachResponse

_INTERNAL_TITLE_RE = re.compile(r"^(pk_|id_|fp_)|[a-f0-9]{12,}$", re.I)
_GENERIC_INTENTS = frozenset(
    {
        CoachIntent.APP_NAVIGATION,
        CoachIntent.FEATURE_EXPLANATION,
        CoachIntent.CREATIVE_FEATURE_HELP,
        CoachIntent.APP_FEATURE_RECOMMENDATION,
    }
)


def musician_facing_song_title(title: str, pick_key: str = "") -> str:
    """Return a displayable song title, or empty if missing / internal-looking."""
    text = str(title or "").strip()
    pick = str(pick_key or "").strip()
    if not text:
        return ""
    if pick and text == pick:
        return ""
    if _INTERNAL_TITLE_RE.search(text):
        return ""
    if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", text):
        return ""
    if "fingerprint" in text.lower() or "catalog_id" in text.lower():
        return ""
    return text


def musician_facing_section_label(section: str) -> str:
    text = str(section or "").strip()
    if not text:
        return ""
    low = re.sub(r"\s+", " ", text.lower()).strip()
    if low in {"full song", "whole song", "entire song", "all", "the song"}:
        return ""
    try:
        from music_coach_ami.musical_idea_knowledge import format_section_display_label

        return format_section_display_label(text) or text
    except ImportError:
        return text


def song_answer_header(title: str, section: str = "") -> str:
    name = musician_facing_song_title(title)
    if not name:
        return ""
    lines = [f"**Song:** *{name}*"]
    sec = musician_facing_section_label(section)
    if sec:
        lines.append(f"**Section:** {sec}")
    return "\n".join(lines)


def is_song_grounded_answer(req: CoachRequest, response: CoachResponse) -> bool:
    """True when the answer actually used the active song/chart as evidence."""
    title = musician_facing_song_title(
        req.context.active_song_title,
        req.context.active_song_pick_key,
    )
    if not title:
        return False
    intent = req.intent or response.intent
    diag = response.diagnostics if isinstance(response.diagnostics, dict) else {}
    q = str(req.normalized_question or req.raw_question or "").lower()
    section_ok = bool((diag.get("section_resolution") or {}).get("ok")) if isinstance(diag.get("section_resolution"), dict) else False
    used_harmony = bool(
        diag.get("harmonic_timeline_concert")
        or diag.get("effective_concert_chords")
        or diag.get("written_chords")
        or diag.get("notation_abc_present")
        and (diag.get("resolved_section") or section_ok or diag.get("musical_idea_content"))
    )

    if intent in _GENERIC_INTENTS:
        return False
    if intent == CoachIntent.SCALE_PRACTICE:
        if diag.get("musical_idea_content") and (
            diag.get("song_relative")
            or diag.get("resolved_section")
            or section_ok
            or diag.get("harmonic_timeline_concert")
        ):
            return True
        return False
    if intent == CoachIntent.THEORY_EXPLANATION:
        return bool(used_harmony or section_ok or diag.get("resolved_section"))
    if intent == CoachIntent.REPERTOIRE_RECOMMENDATION:
        return str(diag.get("selection_reason") or "") == "active_song"
    if intent in {CoachIntent.SONG_COACHING, CoachIntent.SONG_EDITING_WORKFLOW}:
        return True
    if intent == CoachIntent.PRACTICE_PLAN:
        return bool(diag.get("active_song_title") or req.context.active_song_title)
    if intent == CoachIntent.IMPROVISATION_COACHING:
        if "what is improvisation" in q:
            return False
        return bool(
            req.context.active_section
            or req.context.progression_summary
            or used_harmony
            or "this song" in q
            or "over the" in q
        )
    if diag.get("musical_idea_content"):
        return bool(
            diag.get("song_relative")
            or diag.get("resolved_section")
            or section_ok
            or diag.get("harmonic_timeline_concert")
        )
    solver = str(response.source_solver or "").lower()
    if "bass" in solver:
        return bool(used_harmony or req.context.progression_summary or req.context.active_song_title)
    return bool(used_harmony)


def resolved_section_for_header(req: CoachRequest, response: CoachResponse) -> str:
    diag = response.diagnostics if isinstance(response.diagnostics, dict) else {}
    for key in ("resolved_section", "active_section", "display_song_section"):
        val = diag.get(key)
        if str(val or "").strip():
            return str(val).strip()
    sec_res = diag.get("section_resolution")
    if isinstance(sec_res, dict) and str(sec_res.get("section") or "").strip():
        return str(sec_res.get("section")).strip()
    return str(req.context.active_section or "").strip()


def attach_song_grounding(req: CoachRequest, response: CoachResponse) -> CoachResponse:
    """Stamp diagnostics used by composer; do not invent titles."""
    title = musician_facing_song_title(
        req.context.active_song_title,
        req.context.active_song_pick_key,
    )
    grounded = bool(title) and is_song_grounded_answer(req, response)
    section = resolved_section_for_header(req, response) if grounded else ""
    diag = dict(response.diagnostics or {})
    diag["song_grounded"] = grounded
    if grounded and title:
        diag["display_song_title"] = title
        sec_label = musician_facing_section_label(section)
        if sec_label:
            diag["display_song_section"] = sec_label
        else:
            diag.pop("display_song_section", None)
    else:
        diag.pop("display_song_title", None)
        diag.pop("display_song_section", None)
    response.diagnostics = diag
    return response


def header_from_response(response: CoachResponse) -> str:
    diag = response.diagnostics if isinstance(response.diagnostics, dict) else {}
    if not diag.get("song_grounded"):
        return ""
    return song_answer_header(
        str(diag.get("display_song_title") or ""),
        str(diag.get("display_song_section") or ""),
    )
